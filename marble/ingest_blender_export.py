"""Turn Brandon's Blender browser-scene export into a Marble-shaped world dir.

    python -m marble.ingest_blender_export          # writes world_meshes/rongbuk_trail/
    python -m marble.ingest_blender_export --exam   # grades built_worlds/rongbuk_trail/

Input : blender/browser-scene/public/scene/{scene.json, geometry.bin}
        (git lfs pull first). The manifest's `ground` block is a 361x401
        heightfield of the moraine (metres, Blender Z-up, x-fast rows), and
        `obstacles` are conservative boulder/ice cylinders.
Output: world_meshes/rongbuk_trail/ in the exact shape build_episode expects —
        world.json (identity scale, zero offset), collider_mesh_url.glb in
        Marble RAW conventions (+Y down), and truth_trail.json from the scene's
        own carved trail centerline x = 2.2*sin(0.048*y) + 0.024*y (read out of
        build_everest_preview.py), so the trail solver can be graded here too.

The crop keeps a corridor around the carved trail (the full 180x200 m grid is
backdrop, not episode); boulder cylinders inside the crop are baked into the
height grid as flat-topped plateaus so the walkable mask sees them as walls.
"""

from __future__ import annotations

import argparse
import json
import math
import os

import numpy as np

SCENE_DIRECTORY = os.path.join("blender", "browser-scene", "public", "scene")
INPUT_DIRECTORY = os.path.join("world_meshes", "rongbuk_trail")
BUILT_DIRECTORY = os.path.join("built_worlds", "rongbuk_trail")

# Crop window in the scene's metre frame (trail spans x in [-2.5, 3.6] here).
CROP_X_MIN, CROP_X_MAX = -12.0, 12.0
CROP_Y_MIN, CROP_Y_MAX = -15.0, 65.0

CORRIDOR_HALF_WIDTH_METERS = 1.7   # from height(): terrain flattens where trail < 1.7


def trail_x(y: np.ndarray) -> np.ndarray:
    return 2.2 * np.sin(y * 0.048) + 0.024 * y


def load_ground():
    with open(os.path.join(SCENE_DIRECTORY, "scene.json")) as handle:
        manifest = json.load(handle)
    blob = open(os.path.join(SCENE_DIRECTORY, "geometry.bin"), "rb").read()
    ground = manifest["ground"]
    spec = ground["heights"]
    heights = np.frombuffer(blob, dtype="<f4", count=spec["count"],
                            offset=spec["offset"]).astype(float)
    nx, ny, step = ground["nx"], ground["ny"], ground["step"]
    grid = heights.reshape(ny, nx)  # rows = y (outer loop), columns = x (inner)
    x = ground["xmin"] + np.arange(nx) * step
    y = ground["ymin"] + np.arange(ny) * step
    return grid, x, y, manifest


def generate() -> None:
    import trimesh

    grid, x, y, manifest = load_ground()
    column_mask = (x >= CROP_X_MIN) & (x <= CROP_X_MAX)
    row_mask = (y >= CROP_Y_MIN) & (y <= CROP_Y_MAX)
    z = grid[np.ix_(row_mask, column_mask)].copy()
    x, y = x[column_mask], y[row_mask]
    print(f"[ingest] crop {z.shape[1]}x{z.shape[0]} cells, x [{x[0]:.1f},{x[-1]:.1f}] "
          f"y [{y[0]:.1f},{y[-1]:.1f}], z [{z.min():.2f},{z.max():.2f}] m")

    baked = 0
    for obstacle in manifest["obstacles"]:
        inside_x = (obstacle["x"] > x[0]) and (obstacle["x"] < x[-1])
        inside_y = (obstacle["y"] > y[0]) and (obstacle["y"] < y[-1])
        if not (inside_x and inside_y):
            continue
        distance = np.hypot(x[None, :] - obstacle["x"], y[:, None] - obstacle["y"])
        within = distance < obstacle["radius"]
        z[within] = np.maximum(z[within], obstacle["top"])
        baked += int(within.any())
    print(f"[ingest] baked {baked} obstacle cylinders of "
          f"{len(manifest['obstacles'])} total into the height grid")

    mesh_x, mesh_y = np.meshgrid(x, y)
    vertices_mujoco = np.stack([mesh_x.ravel(), mesh_y.ravel(), z.ravel()], axis=1)
    rows, columns = z.shape
    index = np.arange(rows * columns).reshape(rows, columns)
    quad_a = np.stack([index[:-1, :-1].ravel(), index[:-1, 1:].ravel(),
                       index[1:, :-1].ravel()], axis=1)
    quad_b = np.stack([index[1:, :-1].ravel(), index[:-1, 1:].ravel(),
                       index[1:, 1:].ravel()], axis=1)
    faces = np.concatenate([quad_a, quad_b])

    # mujoco -> Marble raw with identity scale and zero ground offset:
    # x_raw = x, y_raw = -z (raw +Y is DOWN), z_raw = y.
    raw = np.stack([vertices_mujoco[:, 0], -vertices_mujoco[:, 2],
                    vertices_mujoco[:, 1]], axis=1)

    os.makedirs(INPUT_DIRECTORY, exist_ok=True)
    trimesh.Trimesh(vertices=raw, faces=faces, process=False).export(
        os.path.join(INPUT_DIRECTORY, "collider_mesh_url.glb"))
    with open(os.path.join(INPUT_DIRECTORY, "world.json"), "w") as handle:
        json.dump({"world_id": "blender-rongbuk-trail",
                   "assets": {"splats": {"semantics_metadata": {
                       "metric_scale_factor": 1.0,
                       "ground_plane_offset": 0.0}}}}, handle, indent=1)

    truth_y = np.arange(y[0] + 1.0, y[-1] - 1.0, 0.5)
    truth_xy = np.stack([trail_x(truth_y), truth_y], axis=1)
    interpolate_rows = np.clip((truth_y - y[0]) / (y[1] - y[0]), 0, rows - 1)
    interpolate_cols = np.clip((truth_xy[:, 0] - x[0]) / (x[1] - x[0]), 0, columns - 1)
    truth_z = z[np.round(interpolate_rows).astype(int),
                np.round(interpolate_cols).astype(int)]
    truth = np.concatenate([truth_xy, truth_z[:, None]], axis=1)
    with open(os.path.join(INPUT_DIRECTORY, "truth_trail.json"), "w") as handle:
        json.dump({"trail_points_xyz_meters": truth.round(4).tolist()}, handle)
    # Open moraine: the destination is the author's call, not geometry's --
    # declare the carved trail's ends; the path between them stays solved.
    with open(os.path.join(INPUT_DIRECTORY, "endpoints.json"), "w") as handle:
        json.dump({"spawn_xy_meters": truth[0, :2].round(4).tolist(),
                   "goal_xy_meters": truth[-1, :2].round(4).tolist()}, handle)
    climb = truth[-1, 2] - truth[0, 2]
    print(f"[ingest] {INPUT_DIRECTORY}: {len(faces)} faces, carved trail runs "
          f"{truth_y[-1] - truth_y[0]:.0f} m north and climbs {climb:+.2f} m")


def exam() -> None:
    with open(os.path.join(INPUT_DIRECTORY, "truth_trail.json")) as handle:
        truth = np.asarray(json.load(handle)["trail_points_xyz_meters"])
    with open(os.path.join(BUILT_DIRECTORY, "episode.json")) as handle:
        solved = np.asarray(json.load(handle)["trail_points_xyz_meters"])
    lateral = np.linalg.norm(solved[:, None, :2] - truth[None, :, :2], axis=2).min(axis=1)
    endpoint_gaps = sorted([np.linalg.norm(solved[0, :2] - truth[0, :2]),
                            np.linalg.norm(solved[-1, :2] - truth[-1, :2])])
    print(f"[exam] lateral deviation from carved trail: mean {lateral.mean():.3f} m  "
          f"95th {np.percentile(lateral, 95):.3f} m  max {lateral.max():.3f} m")
    print(f"[exam] endpoint gaps: {endpoint_gaps[0]:.2f} m / {endpoint_gaps[1]:.2f} m")
    passed = (lateral.max() < CORRIDOR_HALF_WIDTH_METERS
              and lateral.mean() < 0.60 and endpoint_gaps[1] < 4.0)
    print(f"[exam] {'PASS' if passed else 'FAIL'} (bars: max lateral < trail "
          f"half-width {CORRIDOR_HALF_WIDTH_METERS} m, mean < 0.60 m, "
          f"endpoints within 4.0 m — open moraine, looser than the walled exam)")
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--exam", action="store_true")
    arguments = parser.parse_args()
    exam() if arguments.exam else generate()
