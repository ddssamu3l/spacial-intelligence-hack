"""Marble-generated worlds: real terrain + a continuous polyline rope.

Every episode directory under `built_worlds/` (made by marble.build_episode)
becomes one world in the app dropdown, named `marble_<directory>`. The plant
is the trained rope-ascender plant re-grounded:

  THE GROUND is the episode's inpainted heightfield -- true inclined terrain
  under normal gravity, where training was flat ground + tilted gravity.

  THE ROPE is the episode's anchor polyline, drawn whole as capsule segments
  (named ropeseg<i>, the prefix the page's rope drawer looks for). The
  trained slide joint + weld + ratchet are kept VERBATIM, but the slide is
  mounted on a mocap RAIL FRAME that `step` re-aims segment by segment:
  within a segment the physics is bit-for-bit the trained plant; a corner is
  a re-base (subtract the finished segment's length from the slide position
  AND its ratchet limit, swing the rail to the next tangent) absorbed by the
  soft weld over a few milliseconds.

  THE POLICY was NOT trained on any of this -- not real terrain, not turning
  ropes. Its stumbles here are the honest result, stated in every label.

`MarbleScene` is duck-compatible with `chloe_worlds.ChloeScene` everywhere
the harness touches a scene (spec/model/data/terrain/route/ascender/reset/
step, plus every field `describe_chloe_scene` reads), so the guide, snow,
skybox, wind, recorder and pose stream all work unchanged, and the episode
class is literally `ChloeAscenderEpisode`.

Inputs  : built_worlds/<name>/episode.json + hfield.npy (MuJoCo frame,
          meters; the contract is documented in marble/build_episode.py).
Outputs : MARBLE_WORLD_DEFINITIONS (name -> definition dict, same shape as
          CHLOE_WORLD_DEFINITIONS with kind "marble_ascender") and
          MarbleSceneLibrary().load(name) -> (scene, meta, definition).
"""

from __future__ import annotations

import json
import math
import os

import numpy as np

from app.harness import chloe_policy
from app.harness import chloe_worlds

REPOSITORY_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
BUILT_WORLDS_DIRECTORY = os.path.join(REPOSITORY_ROOT, "built_worlds")

SPAWN_ARC_METERS = 0.60   # palm starts this far up the rope, so the feet
                          # stand on solver-vetted corridor, not behind it
DEFAULT_POLICY_RELATIVE_PATH = os.path.join(
    "rl", "policies", "g1_ascender_slope20_final_2026-08-30_13-55-14.onnx")


def quaternion_from_tangent(tangent: np.ndarray) -> np.ndarray:
    """Rail frame for a rope tangent: local +x along the rope, z upright.

    R = Rz(heading) @ Ry(-grade), the same composition chloe_worlds uses to
    stand the trained build up on a slope, so the weld's relative pose keeps
    meaning what it meant in training.
    """
    tangent = np.asarray(tangent, dtype=float)
    heading = float(np.arctan2(tangent[1], tangent[0]))
    grade = float(np.arcsin(np.clip(tangent[2] / np.linalg.norm(tangent), -1, 1)))
    yaw = np.array([np.cos(heading / 2), 0.0, 0.0, np.sin(heading / 2)])
    pitch = np.array([np.cos(-grade / 2), 0.0, np.sin(-grade / 2), 0.0])
    return chloe_worlds.quaternion_product(yaw, pitch)


class MarbleGround:
    """The episode heightfield, presenting `SlopeGround`'s surface.

    `guide.Guide` snaps the hiker's boots to `surface_z(x, y)` -- here that is
    a bilinear lookup into the same grid the collision hfield was built from,
    so the hiker walks the REAL terrain. `snow`/`graphics` size textures and
    fog from `size_xy`.
    """

    def __init__(self, height_grid, origin_xy, resolution, slope_degrees, name):
        self.height_grid = np.asarray(height_grid, dtype=np.float32)
        self.origin_xy = np.asarray(origin_xy, dtype=float)
        self.resolution = float(resolution)
        self.slope_deg = float(slope_degrees)
        self.frame = "tilted_plane"
        self.name = name
        self.source = "Marble collider -> raycast heightfield (marble/build_episode.py)"
        rows, columns = self.height_grid.shape
        self.size_xy = ((columns - 1) * self.resolution, (rows - 1) * self.resolution)
        self.res = self.resolution
        self.rough = np.zeros((2, 2))     # relief already lives in the hfield
        self.shape = self.rough.shape

    def surface_z(self, x, y):
        grid = self.height_grid
        rows, columns = grid.shape
        column = np.clip((np.asarray(x, dtype=float) - self.origin_xy[0])
                         / self.resolution, 0, columns - 1.001)
        row = np.clip((np.asarray(y, dtype=float) - self.origin_xy[1])
                      / self.resolution, 0, rows - 1.001)
        c0 = np.floor(column).astype(int)
        r0 = np.floor(row).astype(int)
        fc, fr = column - c0, row - r0
        return (grid[r0, c0] * (1 - fc) * (1 - fr) + grid[r0, c0 + 1] * fc * (1 - fr)
                + grid[r0 + 1, c0] * (1 - fc) * fr + grid[r0 + 1, c0 + 1] * fc * fr)

    @property
    def slope_rad(self) -> float:
        return math.radians(self.slope_deg)


class MarbleAscender:
    """`SlideAscender`'s interface over the re-based rail.

    The slide joint's coordinate resets at every corner re-base, so the honest
    arc is `scene.segment_base_arc + qpos` -- monotone over the whole rope.
    `arclength_meters` is the absolute arc on `scene.route`, which is what the
    hiker's route-following reads.
    """

    def __init__(self, scene, mujoco_module):
        self.scene = scene
        self.rope_tail_meters = 0.0
        self.ratchet = True
        self.s0 = 0.0
        self.bind(scene.model, mujoco_module)

    def bind(self, model, mujoco_module) -> None:
        rope_rail = chloe_policy.rope_rail_module()
        self.model = model
        self.joint_id = int(model.joint(rope_rail.SLIDE_JOINT).id)
        self.qpos_address = int(model.jnt_qposadr[self.joint_id])
        self.dof_address = int(model.jnt_dofadr[self.joint_id])

    def slide_meters(self, data) -> float:
        return float(self.scene.segment_base_arc + data.qpos[self.qpos_address])

    def arclength_meters(self, data) -> float:
        return self.slide_meters(data)

    def progress_meters(self, data) -> float:
        return self.slide_meters(data) - self.s0


class MarbleScene:
    """The trained plant re-grounded on one built episode. See module docstring."""

    def __init__(self, built_directory: str, verbose: bool = True):
        import mujoco
        from rl.environment.ascender import RopeRoute

        self._mujoco = mujoco
        rope_rail = chloe_policy.rope_rail_module()
        self._rope_rail = rope_rail

        with open(os.path.join(built_directory, "episode.json")) as handle:
            self.episode = json.load(handle)
        height_grid = np.load(os.path.join(built_directory, "hfield.npy"))
        grid_meta = self.episode["heightfield"]
        origin_xy = np.asarray(grid_meta["origin_xy"], dtype=float)
        resolution = float(grid_meta["resolution_meters"])

        anchors = np.asarray(self.episode["anchor_points_xyz_meters"], dtype=float)
        self.route = RopeRoute(anchors)
        trail = np.asarray(self.episode["trail_points_xyz_meters"], dtype=float)
        horizontal = float(np.sum(np.linalg.norm(np.diff(trail[:, :2], axis=0), axis=1)))
        climb = float(trail[-1, 2] - trail[0, 2])
        self.slope_degrees = float(np.degrees(np.arctan2(abs(climb), max(1e-6, horizontal))))
        self.frame = "tilted_plane"

        self.spawn_arc_meters = min(SPAWN_ARC_METERS, self.route.length / 4.0)
        spawn_anchor = self.route.point_at(self.spawn_arc_meters)
        first_tangent = self.route.tangent_at(self.spawn_arc_meters)
        first_grade_degrees = float(np.degrees(np.arcsin(first_tangent[2])))

        # --- the trained build, in HER flat frame at the spawn grade -------
        her_spawn_position, foot_sphere_count = chloe_worlds.fit_spawn_height(
            first_grade_degrees)
        her_spawn_quaternion = chloe_worlds.slope_quaternion(first_grade_degrees)
        joint_positions = chloe_worlds.body_joint_positions(first_grade_degrees)
        spec = chloe_worlds.base_spec()
        self.default_joint_positions = rope_rail.add_rope_rail(
            spec, her_spawn_position, her_spawn_quaternion, joint_positions)
        grip_her = np.asarray(
            chloe_worlds._spec_body(spec, rope_rail.ROPE_BODY).pos, dtype=float)

        # --- mjlab articulation, the loop from chloe_worlds.build ----------
        hinges = [j for j in spec.joints if j.type == mujoco.mjtJoint.mjJNT_HINGE]
        for joint in hinges:
            stiffness, damping, armature, _sc = chloe_policy.articulation_for(joint.name)
            joint.armature = armature
            joint.damping = [0.0, 0.0, 0.0]
            joint.frictionloss = 0.0
            actuator = spec.add_actuator(name=joint.name, target=joint.name,
                                         trntype=mujoco.mjtTrn.mjTRN_JOINT)
            actuator.gaintype = mujoco.mjtGain.mjGAIN_FIXED
            actuator.biastype = mujoco.mjtBias.mjBIAS_AFFINE
            actuator.gainprm = [stiffness] + [0.0] * 9
            actuator.biasprm = [0.0, -stiffness, -damping] + [0.0] * 7
            actuator.ctrlrange = [-1e6, 1e6]
            actuator.ctrllimited = 0

        # --- transform her frame onto the trail ----------------------------
        rotation_quaternion = quaternion_from_tangent(first_tangent)
        rotation = chloe_worlds.rotation_matrix(rotation_quaternion)
        translation = spawn_anchor - rotation @ grip_her
        self.spawn = rotation @ her_spawn_position + translation
        self.spawn_quaternion = chloe_worlds.quaternion_product(
            rotation_quaternion, her_spawn_quaternion)
        self.uphill_direction_world = np.asarray(first_tangent, dtype=float)

        # --- the carriage moves onto the re-aimable rail frame -------------
        old_weld = next(e for e in spec.equalities if e.name == "ascender_grip")
        weld_data = np.asarray(old_weld.data, dtype=float).copy()
        weld_solref = np.asarray(old_weld.solref, dtype=float).copy()
        weld_solimp = np.asarray(old_weld.solimp, dtype=float).copy()
        spec.delete(old_weld)
        spec.delete(chloe_worlds._spec_body(spec, rope_rail.CARRIER_BODY))

        rail = spec.worldbody.add_body(name="rope_rail_frame", mocap=True,
                                       pos=spawn_anchor.tolist(),
                                       quat=rotation_quaternion.tolist())
        carriage = rail.add_body(name=rope_rail.CARRIER_BODY, pos=[0.0, 0.0, 0.0])
        slide = carriage.add_joint(name=rope_rail.SLIDE_JOINT,
                                   type=mujoco.mjtJoint.mjJNT_SLIDE,
                                   axis=[1, 0, 0],
                                   range=[-rope_rail.ROPE_LENGTH,
                                          rope_rail.ROPE_LENGTH],
                                   damping=2.0,
                                   frictionloss=rope_rail.CAM_FRICTION_N)
        slide.solref_limit = [0.01, 1.0]
        slide.solimp_limit = [0.99, 0.999, 0.001, 0.5, 2.0]
        carriage.add_geom(name="carrier_geom", type=mujoco.mjtGeom.mjGEOM_SPHERE,
                          size=[0.02, 0, 0], mass=rope_rail.CARRIER_MASS,
                          rgba=[1.0, 0.9, 0.0, 1.0],
                          contype=0, conaffinity=0, group=2)
        carriage.add_site(name="carrier_anchor", pos=[0, 0, 0], group=5)
        weld = spec.add_equality(type=mujoco.mjtEq.mjEQ_WELD, name="ascender_grip",
                                 objtype=mujoco.mjtObj.mjOBJ_BODY,
                                 name1=rope_rail.CARRIER_BODY,
                                 name2=rope_rail.WRIST_BODY)
        weld.data = weld_data.tolist()      # relpose lives in the CARRIAGE
        weld.solref = weld_solref.tolist()  # frame, which is her frame carried
        weld.solimp = weld_solimp.tolist()  # by the rail -- verbatim transfer

        # --- the rope drawn whole, as the anchor polyline ------------------
        rope_body = chloe_worlds._spec_body(spec, rope_rail.ROPE_BODY)
        for geom in list(rope_body.geoms):
            spec.delete(geom)
        rope_body.pos = [0.0, 0.0, 0.0]
        rope_body.quat = [1.0, 0.0, 0.0, 0.0]
        for index, (first, second) in enumerate(
                zip(self.route.points[:-1], self.route.points[1:])):
            segment = rope_body.add_geom(
                name=f"ropeseg{index}",
                type=mujoco.mjtGeom.mjGEOM_CAPSULE,
                size=[rope_rail.ROPE_RADIUS, 0.0, 0.0],
                rgba=[0.9, 0.3, 0.1, 1.0],
                contype=1, conaffinity=1, condim=3,
                friction=[0.2, 0.005, 0.0001], group=2)
            segment.fromto = np.concatenate([first, second]).tolist()

        # --- the ground is the episode heightfield --------------------------
        rows, columns = height_grid.shape
        z_low = float(height_grid.min())
        z_span = max(1e-3, float(height_grid.max() - z_low))
        half_x = (columns - 1) * resolution / 2.0
        half_y = (rows - 1) * resolution / 2.0
        hfield = spec.add_hfield(name="terrain", nrow=rows, ncol=columns,
                                 size=[half_x, half_y, z_span, 1.0])
        hfield.userdata = ((height_grid - z_low) / z_span).ravel().tolist()
        floor = spec.worldbody.add_geom(
            name="floor", type=mujoco.mjtGeom.mjGEOM_HFIELD, hfieldname="terrain",
            pos=[origin_xy[0] + half_x, origin_xy[1] + half_y, z_low],
            rgba=[0.86, 0.90, 0.95, 1.0])
        floor.friction = [chloe_worlds.GROUND_FRICTION, 0.005, 0.0001]

        spec.option.timestep = chloe_worlds.PHYSICS_TIMESTEP_SECONDS
        spec.option.iterations = chloe_worlds.SOLVER_ITERATIONS
        spec.option.ls_iterations = chloe_worlds.SOLVER_LINE_SEARCH_ITERATIONS
        spec.option.gravity = [0.0, 0.0, -chloe_worlds.GRAVITY_MAGNITUDE]

        self.spec = spec
        self.model = spec.compile()
        self.data = mujoco.MjData(self.model)
        self.terrain = MarbleGround(height_grid, origin_xy, resolution,
                                    self.slope_degrees,
                                    self.episode["episode_name"])
        self.ascender = MarbleAscender(self, mujoco)
        self.friction_applied = chloe_worlds.GROUND_FRICTION
        self.adapt_report = {
            "source": "app/harness/marble_worlds.build",
            "actuators": "mjlab G1_ARTICULATION (kp/kd/armature per motor group)",
            "feet": f"{foot_sphere_count} spheres, unchanged from the XML",
            "policy_compat": False,
            "frame": self.frame,
        }
        self.reset()
        if verbose:
            print(f"[marble] plant on {self.episode['episode_name']}: hfield"
                  f" {columns}x{rows}, rope {self.route.length:.1f} m over"
                  f" {self.route.n_seg} segments, spawn grade"
                  f" {first_grade_degrees:.1f} deg, mean trail slope"
                  f" {self.slope_degrees:.1f} deg", flush=True)
            print(f"[marble] spawn pelvis {np.round(self.spawn, 3).tolist()}"
                  f"  hand-rope gap {self.hand_rope_distance() * 100:.2f} cm",
                  flush=True)

    # ------------------------------------------------------------- binding
    def _bind(self) -> None:
        """Re-derive every id from `self.model` (decorators recompile)."""
        model = self.model
        mujoco = self._mujoco
        rope_rail = self._rope_rail
        self.torso_body_id = int(model.body("torso_link").id)
        self.pelvis_body_id = int(model.body("pelvis").id)
        self.carriage_body_id = int(model.body(rope_rail.CARRIER_BODY).id)
        self.rail_mocap_id = int(model.body_mocapid[
            int(model.body("rope_rail_frame").id)])
        self.slide_joint_id = int(model.joint(rope_rail.SLIDE_JOINT).id)
        self.slide_qpos_address = int(model.jnt_qposadr[self.slide_joint_id])
        self.imu_torso_site_id = int(model.site("imu_in_torso").id)
        self.palm_site_id = int(model.site("ascender_anchor").id)
        self.grip_equality_id = int(model.equality("ascender_grip").id)
        self.floor_geom_id = int(model.geom("floor").id)
        self.foot_geom_ids = [
            i for i in range(model.ngeom)
            if (mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, i) or "")
            .startswith(("left_foot_", "right_foot_"))]
        names = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, j)
                 for j in range(model.njnt)]
        self.joint_names = [n for n in names
                            if n and n.endswith("_joint") and n != "floating_base_joint"]
        self.joint_qpos_addresses = np.array(
            [int(model.jnt_qposadr[model.joint(n).id]) for n in self.joint_names])

    # --------------------------------------------------------------- state
    def reset(self) -> None:
        mujoco = self._mujoco
        self._bind()
        mujoco.mj_resetData(self.model, self.data)
        self.data.qpos[0:3] = self.spawn
        self.data.qpos[3:7] = self.spawn_quaternion
        for name, address in zip(self.joint_names, self.joint_qpos_addresses):
            self.data.qpos[address] = chloe_policy._matching_value(
                self.default_joint_positions, name)
        self.segment_index = int(np.clip(
            np.searchsorted(self.route.cum, self.spawn_arc_meters, side="right") - 1,
            0, self.route.n_seg - 1))
        self.segment_base_arc = float(self.route.cum[self.segment_index])
        self.data.qpos[self.slide_qpos_address] = (
            self.spawn_arc_meters - self.segment_base_arc)
        self.data.qvel[:] = 0.0
        self.data.ctrl[:] = 0.0
        self._aim_rail()
        mujoco.mj_forward(self.model, self.data)
        self._rope_rail.ratchet_reset(self.model, self.data)
        self.ascender.bind(self.model, mujoco)
        self.ascender.s0 = self.ascender.slide_meters(self.data)

        # feet vs terrain: report (and clear) any residual penetration
        clearance = min(
            float(self.data.geom_xpos[i][2] - self.model.geom_size[i][0]
                  - self.terrain.surface_z(*self.data.geom_xpos[i][:2]))
            for i in self.foot_geom_ids)
        if clearance < 0.0:
            self.data.qpos[2] += -clearance + 0.02
            mujoco.mj_forward(self.model, self.data)
            print(f"[marble] spawn lifted {-clearance + 0.02:.3f} m to clear"
                  f" terrain (palm leaves the rope by as much -- worth a look)",
                  flush=True)

    @property
    def projected_gravity_body(self) -> np.ndarray:
        gravity = np.asarray(self.model.opt.gravity, dtype=float)
        return chloe_policy.quaternion_inverse_rotate(
            self.data.qpos[3:7], gravity / np.linalg.norm(gravity))

    @property
    def palm_xyz(self) -> np.ndarray:
        return np.asarray(self.data.site_xpos[self.palm_site_id], dtype=float).copy()

    def hand_rope_distance(self) -> float:
        return float(self.route.project_arclen(self.palm_xyz)[1])

    def set_friction(self, friction: float) -> None:
        for geom_id in self.foot_geom_ids:
            self.model.geom_friction[geom_id, 0] = float(friction)
        self.model.geom_friction[self.floor_geom_id, 0] = float(friction)
        self.friction_applied = float(friction)

    # ----------------------------------------------------------- one substep
    def _aim_rail(self) -> None:
        j = self.segment_index
        self.data.mocap_pos[self.rail_mocap_id] = self.route.points[j]
        self.data.mocap_quat[self.rail_mocap_id] = quaternion_from_tangent(
            self.route.seg[j] / self.route.seg_len[j])

    def apply_wind(self, wind) -> None:
        """`chloe_worlds.ChloeScene.apply_wind`, same law, same body."""
        if wind is None or wind.speed == 0.0:
            self.data.xfrc_applied[self.torso_body_id, :] = 0.0
            return
        torso_velocity = self.data.cvel[self.torso_body_id, 3:5]
        relative = wind.velocity - torso_velocity
        force = wind.drag_coeff * float(np.linalg.norm(relative)) * relative
        self.data.xfrc_applied[self.torso_body_id, :] = 0.0
        self.data.xfrc_applied[self.torso_body_id, :2] = force

    def step(self, wind=None) -> float:
        """Re-base past corners, wind, ratchet, one mj_step."""
        while (self.segment_index < self.route.n_seg - 1
               and self.data.qpos[self.slide_qpos_address]
               > self.route.seg_len[self.segment_index]):
            finished = float(self.route.seg_len[self.segment_index])
            self.data.qpos[self.slide_qpos_address] -= finished
            self.model.jnt_range[self.slide_joint_id, 0] = max(
                -0.01,
                float(self.model.jnt_range[self.slide_joint_id, 0]) - finished)
            self.segment_base_arc += finished
            self.segment_index += 1
            self._aim_rail()
            self._mujoco.mj_forward(self.model, self.data)
        if wind is not None:
            self.apply_wind(wind)
        self._rope_rail.ratchet(self.model, self.data)
        self._mujoco.mj_step(self.model, self.data)
        return self.ascender.slide_meters(self.data)


# ------------------------------------------------------------- the catalogue
def _scan_definitions() -> dict:
    definitions = {}
    if not os.path.isdir(BUILT_WORLDS_DIRECTORY):
        return definitions
    for entry in sorted(os.listdir(BUILT_WORLDS_DIRECTORY)):
        built_directory = os.path.join(BUILT_WORLDS_DIRECTORY, entry)
        episode_path = os.path.join(built_directory, "episode.json")
        if not os.path.isfile(episode_path):
            continue
        with open(episode_path) as handle:
            episode = json.load(handle)
        trail = np.asarray(episode["trail_points_xyz_meters"], dtype=float)
        climb = float(trail[-1, 2] - trail[0, 2])
        horizontal = float(np.sum(np.linalg.norm(np.diff(trail[:, :2], axis=0),
                                                 axis=1)))
        slope = float(np.degrees(np.arctan2(abs(climb), max(1e-6, horizontal))))
        source = episode.get("provenance", {}).get("trail_source", "solver")
        definitions[f"marble_{entry}"] = {
            "kind": "marble_ascender",
            "label": f"Marble · {entry} · {slope:.0f}°",
            "patch": "plane",
            "robot": "ascender",
            "rope": True,
            "slope_degrees": slope,
            "slope_provenance": "mean grade of the solved trail",
            "description": (
                f"Marble-generated world '{entry}': {horizontal:.0f} m trail"
                f" climbing {climb:.1f} m ({slope:.0f} deg mean), rope laid by"
                f" the {source} as {len(episode['anchor_points_xyz_meters'])}"
                " anchored segments. Mrinal 2 climbs it UNTRAINED: it never"
                " saw real terrain or a turning rope -- stumbles are the"
                " honest result."),
            "terrain_factory": None,
            "autonomous": True,
            "policy_version": "m2",
            "policy_relative_path": DEFAULT_POLICY_RELATIVE_PATH,
            "built_directory": built_directory,
        }
    return definitions


MARBLE_WORLD_DEFINITIONS = _scan_definitions()


class MarbleSceneLibrary:
    """One compiled plant per episode directory, built lazily and cached."""

    def __init__(self, verbose=True):
        self.verbose = verbose
        self._scenes = {}

    def load(self, name, on_build_start=None):
        import time
        definition = MARBLE_WORLD_DEFINITIONS[name]
        if name not in self._scenes:
            if on_build_start is not None:
                on_build_start()
            started = time.time()
            print(f"[marble] building {name} from"
                  f" {definition['built_directory']}", flush=True)
            scene = MarbleScene(definition["built_directory"],
                                verbose=self.verbose)
            meta = chloe_worlds.describe_chloe_scene(scene, definition)
            meta["kind"] = "marble_ascender"
            meta["terrain_in_training"] = False
            meta["slope_provenance"] = definition["slope_provenance"]
            self._scenes[name] = (scene, meta)
            print(f"[marble] built {name} in {time.time() - started:.2f} s",
                  flush=True)
        scene, meta = self._scenes[name]
        return scene, meta, definition
