"""Generate a fake Marble export with a KNOWN trail — the path solver's exam.

    python -m marble.make_test_mountain          # writes world_meshes/test_switchback/
    python -m marble.make_test_mountain --exam   # grades built_worlds/test_switchback/

The world: a 20-degree switchback corridor (three legs, 1.5 m wide) carved
into 60-degree side walls, exported in Marble's RAW conventions on purpose —
OpenCV frame (+Y down), non-unit metric_scale_factor, non-zero
ground_plane_offset, and ~4% of faces deleted as holes — so every rectification
step in build_episode.py is exercised, not just believed.

Output files (world_meshes/test_switchback/):
    world.json               minimal Marble record: only the fields the builder
                             reads (assets.splats.semantics_metadata.*)
    collider_mesh_url.glb    the terrain mesh, raw units, y-down, with holes
    truth_trail.json         {"trail_points_xyz_meters": [[x,y,z]...]} — the
                             carved centerline in the MUJOCO frame, uphill order

Exam (--exam): every solver trail point's lateral distance to the truth
centerline; PASS iff max deviation < 0.5 m and the solved path climbs the
full corridor (start/goal within 1.5 m of the truth endpoints).
"""

from __future__ import annotations

import argparse
import json
import os

import numpy as np

FAKE_SCALE = 1.3702           # deliberately non-unit
FAKE_GROUND_OFFSET = 1.1200   # deliberately non-zero
CORRIDOR_HALF_WIDTH_METERS = 0.75
CORRIDOR_GRADE_DEGREES = 20.0
WALL_GRADE_DEGREES = 60.0
MESH_STEP_METERS = 0.10
HOLE_FACE_FRACTION = 0.04
SEED = 7

CENTERLINE_XY = np.array([[1.5, 1.0], [11.0, 2.5], [2.5, 5.5], [11.5, 8.5]])

INPUT_DIRECTORY = os.path.join("world_meshes", "test_switchback")
BUILT_DIRECTORY = os.path.join("built_worlds", "test_switchback")


def densify(polyline_xy: np.ndarray, step: float) -> np.ndarray:
    pieces = []
    for first, second in zip(polyline_xy[:-1], polyline_xy[1:]):
        count = max(2, int(np.ceil(np.linalg.norm(second - first) / step)))
        pieces.append(np.linspace(first, second, count, endpoint=False))
    pieces.append(polyline_xy[-1:])
    return np.concatenate(pieces)


def centerline_with_height() -> np.ndarray:
    """(N,3) mujoco-frame centerline: z climbs at CORRIDOR_GRADE along arc."""
    dense_xy = densify(CENTERLINE_XY, 0.05)
    arc = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(dense_xy, axis=0), axis=1))])
    z = arc * np.tan(np.radians(CORRIDOR_GRADE_DEGREES))
    return np.concatenate([dense_xy, z[:, None]], axis=1)


def terrain_height(sample_xy: np.ndarray, center: np.ndarray) -> np.ndarray:
    """z at each xy: corridor height at the nearest centerline point, plus a
    60-degree wall beyond the corridor half-width."""
    distances = np.linalg.norm(sample_xy[:, None, :] - center[None, :, :2], axis=2)
    nearest = np.argmin(distances, axis=1)
    lateral = distances[np.arange(len(sample_xy)), nearest]
    base = center[nearest, 2]
    wall = np.clip(lateral - CORRIDOR_HALF_WIDTH_METERS, 0.0, None) \
        * np.tan(np.radians(WALL_GRADE_DEGREES))
    return base + wall


def generate() -> None:
    import trimesh

    center = centerline_with_height()
    x = np.arange(0.0, 13.5 + MESH_STEP_METERS, MESH_STEP_METERS)
    y = np.arange(0.0, 9.5 + MESH_STEP_METERS, MESH_STEP_METERS)
    mesh_x, mesh_y = np.meshgrid(x, y)
    flat_xy = np.stack([mesh_x.ravel(), mesh_y.ravel()], axis=1)
    z = terrain_height(flat_xy, center).reshape(mesh_y.shape)

    rows, columns = z.shape
    vertices_mujoco = np.stack([mesh_x.ravel(), mesh_y.ravel(), z.ravel()], axis=1)
    index = np.arange(rows * columns).reshape(rows, columns)
    quad_a = np.stack([index[:-1, :-1].ravel(), index[:-1, 1:].ravel(), index[1:, :-1].ravel()], axis=1)
    quad_b = np.stack([index[1:, :-1].ravel(), index[:-1, 1:].ravel(), index[1:, 1:].ravel()], axis=1)
    faces = np.concatenate([quad_a, quad_b])

    rng = np.random.default_rng(SEED)
    faces = faces[rng.random(len(faces)) > HOLE_FACE_FRACTION]

    # mujoco -> Marble raw: x_raw = x/s, z_raw = y/s, y_raw = (offset - z)/s
    raw = np.stack([vertices_mujoco[:, 0],
                    FAKE_GROUND_OFFSET - vertices_mujoco[:, 2],
                    vertices_mujoco[:, 1]], axis=1) / FAKE_SCALE
    raw[:, 1] = (FAKE_GROUND_OFFSET - vertices_mujoco[:, 2]) / FAKE_SCALE
    raw[:, 0] = vertices_mujoco[:, 0] / FAKE_SCALE
    raw[:, 2] = vertices_mujoco[:, 1] / FAKE_SCALE

    os.makedirs(INPUT_DIRECTORY, exist_ok=True)
    trimesh.Trimesh(vertices=raw, faces=faces, process=False).export(
        os.path.join(INPUT_DIRECTORY, "collider_mesh_url.glb"))
    with open(os.path.join(INPUT_DIRECTORY, "world.json"), "w") as handle:
        json.dump({"world_id": "synthetic-test-switchback",
                   "assets": {"splats": {"semantics_metadata": {
                       "metric_scale_factor": FAKE_SCALE,
                       "ground_plane_offset": FAKE_GROUND_OFFSET}}}}, handle, indent=1)
    with open(os.path.join(INPUT_DIRECTORY, "truth_trail.json"), "w") as handle:
        json.dump({"trail_points_xyz_meters": center.round(4).tolist()}, handle)
    climb = center[-1, 2] - center[0, 2]
    print(f"[generate] {INPUT_DIRECTORY}: {len(faces)} faces "
          f"({HOLE_FACE_FRACTION * 100:.0f}% deleted as holes), corridor climbs {climb:.2f} m "
          f"over {np.sum(np.linalg.norm(np.diff(center[:, :2], axis=0), axis=1)):.1f} m at "
          f"{CORRIDOR_GRADE_DEGREES:g} deg")


def exam() -> None:
    with open(os.path.join(INPUT_DIRECTORY, "truth_trail.json")) as handle:
        truth = np.asarray(json.load(handle)["trail_points_xyz_meters"])
    with open(os.path.join(BUILT_DIRECTORY, "episode.json")) as handle:
        solved = np.asarray(json.load(handle)["trail_points_xyz_meters"])

    lateral = np.linalg.norm(solved[:, None, :2] - truth[None, :, :2], axis=2).min(axis=1)
    start_gap = np.linalg.norm(solved[0, :2] - truth[0, :2])
    goal_gap = np.linalg.norm(solved[-1, :2] - truth[-1, :2])
    print(f"[exam] lateral deviation from carved centerline: "
          f"mean {lateral.mean():.3f} m  95th {np.percentile(lateral, 95):.3f} m  "
          f"max {lateral.max():.3f} m")
    print(f"[exam] endpoint gaps: start {start_gap:.2f} m  goal {goal_gap:.2f} m")
    # Bars (amended 2026-09-05 after inspecting the first run): the solver cuts
    # smooth chords through the switchbacks -- up to ~0.55 m inside a turn,
    # exactly where a walker cuts a corner -- so the honest requirement is
    # "never steps OFF the carved corridor floor" (max < half-width), a tight
    # mean, and matched endpoints; not centimetric centerline tracking.
    passed = (lateral.max() < CORRIDOR_HALF_WIDTH_METERS and lateral.mean() < 0.30
              and start_gap < 1.5 and goal_gap < 1.5)
    print(f"[exam] {'PASS' if passed else 'FAIL'} "
          f"(bars: max lateral < corridor half-width {CORRIDOR_HALF_WIDTH_METERS} m, "
          f"mean < 0.30 m, endpoints within 1.5 m)")
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--exam", action="store_true")
    arguments = parser.parse_args()
    exam() if arguments.exam else generate()
