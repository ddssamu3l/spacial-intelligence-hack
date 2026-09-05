"""Find the fixed rope a Marble world SHIPS WITH and make it the trail.

    python -m marble.find_rope_in_splats "<world>.spz" world_meshes/<name> built_worlds/<name>

Generated worlds made from real climbing photos contain the route's fixed
ropes as geometry-thin colored splats. This reads them out and writes
world_meshes/<name>/trail.json (the build_episode solver override), so the
laid rope follows the world's OWN line instead of a geometry-solved guess.

Filter chain, each step printed:
 1. saturated color  (chroma > CHROMA_FLOOR; snow and ice are grey/blue-grey)
 2. hugs the ground  (within HEIGHT_BAND of the built hfield -- kills sky)
 3. locally 1-D      (PCA of 1 m neighborhoods: top eigenvalue > 85% -- kills
                      rock faces and dirt patches, keeps string-like chains)
 4. connected chain nearest the camera origin (radius graph, union-find)
 5. voxel-collapsed then greedily ordered -- routes are often DOUBLE ropes:
    averaging within 2 m voxels first merges the twins into one centerline
    (elevation-sorting instead braids them: measured 337 m of zigzag for a
    30 m gully), then a nearest-neighbor walk from the lowest voxel orders
    it, with a jump cap so stray clusters cannot teleport the line.

Requires the episode to be built once already (its hfield is filter 2's
ground truth); re-run build_episode after this writes the override.
"""

from __future__ import annotations

import argparse
import json
import os

import numpy as np

CHROMA_FLOOR = 0.12
ALPHA_FLOOR = 0.3
HEIGHT_BAND_METERS = (-0.5, 1.5)
LINEARITY_RADIUS_METERS = 1.0
LINEARITY_SHARE = 0.85
CHAIN_RADIUS_METERS = 3.0
SMOOTH_WINDOW = 5
VOXEL_METERS = 2.0
EDGE_RADIUS_METERS = 5.0


def main(spz_path: str, world_directory: str, built_directory: str) -> None:
    from scipy.spatial import cKDTree

    from marble.paint_collider_from_splats import load_spz

    positions, rgb, alpha = load_spz(spz_path)

    episode = json.load(open(os.path.join(built_directory, "episode.json")))
    meta = episode["heightfield"]
    height = np.load(os.path.join(built_directory, "hfield.npy"))
    record = json.load(open(os.path.join(world_directory, "world.json")))
    z_anchor = float(record["assets"]["splats"]["semantics_metadata"]["ground_plane_offset"])
    if record.get("frame") != "gltf_y_up":
        raise SystemExit("[rope] only the gltf_y_up (console download) frame is wired up")

    mujoco = np.stack([positions[:, 0], -positions[:, 2],
                       positions[:, 1] - z_anchor], axis=1)
    x0, y0 = meta["origin_xy"]
    resolution = meta["resolution_meters"]
    rows = np.clip(((mujoco[:, 1] - y0) / resolution).astype(int), 0, height.shape[0] - 1)
    columns = np.clip(((mujoco[:, 0] - x0) / resolution).astype(int), 0, height.shape[1] - 1)
    above_ground = mujoco[:, 2] - height[rows, columns]

    chroma = rgb.max(axis=1) - rgb.min(axis=1)
    candidate = ((chroma > CHROMA_FLOOR) & (alpha > ALPHA_FLOOR)
                 & (above_ground > HEIGHT_BAND_METERS[0])
                 & (above_ground < HEIGHT_BAND_METERS[1]))
    points = mujoco[candidate]
    print(f"[rope] {candidate.sum()} saturated surface-hugging splats")

    tree = cKDTree(points)
    linear = np.zeros(len(points), bool)
    for index, neighbors in enumerate(tree.query_ball_point(points, LINEARITY_RADIUS_METERS,
                                                            workers=1)):
        if len(neighbors) < 4:
            continue
        centered = points[neighbors] - points[neighbors].mean(axis=0)
        eigenvalues = np.linalg.eigvalsh(centered.T @ centered / len(neighbors))
        linear[index] = eigenvalues[-1] / max(eigenvalues.sum(), 1e-9) > LINEARITY_SHARE
    points = points[linear]
    print(f"[rope] {linear.sum()} locally line-shaped")

    tree = cKDTree(points[:, :2])
    parent = np.arange(len(points))
    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for a, b in tree.query_pairs(CHAIN_RADIUS_METERS):
        parent[find(a)] = find(b)
    labels = np.array([find(i) for i in range(len(points))])
    camera_chain = labels == labels[int(np.argmin(np.linalg.norm(points[:, :2], axis=1)))]
    chain = points[camera_chain]
    print(f"[rope] camera chain: {camera_chain.sum()} splats, "
          f"z {chain[:, 2].min():.1f}..{chain[:, 2].max():.1f} m")

    # 3-D keys: a 2-D (xy) voxelization collapses a near-vertical rope run
    # into one averaged point and tears the chain apart in z.
    voxel = np.round(chain / VOXEL_METERS).astype(int)
    centers = {}
    for key, point in zip(map(tuple, voxel), chain):
        centers.setdefault(key, []).append(point)
    collapsed = np.array([np.mean(group, axis=0) for group in centers.values()])
    print(f"[rope] {len(collapsed)} centerline voxels at {VOXEL_METERS} m "
          f"(twin ropes merged)")

    # A world often carries SEVERAL ropes converging at the base; a greedy
    # walk braids them into loops. The route = the shortest graph path from
    # the chain's lowest voxel to its highest: one clean curve, loop-free.
    import heapq
    # 3-D edges, tight radius: in a near-vertical gully the summit is only
    # ~10 xy-metres from the base, and 2-D edges shortcut straight up the
    # cliff (measured: a 4-waypoint, 11 m 'route' for a 22 m climb).
    edge_tree = cKDTree(collapsed)
    start = int(np.argmin(collapsed[:, 2]))
    summit = int(np.argmax(collapsed[:, 2]))
    best = np.full(len(collapsed), np.inf)
    came_from = np.full(len(collapsed), -1)
    best[start] = 0.0
    frontier = [(0.0, start)]
    while frontier:
        cost, node = heapq.heappop(frontier)
        if node == summit:
            break
        if cost > best[node]:
            continue
        for neighbor in edge_tree.query_ball_point(collapsed[node],
                                                   EDGE_RADIUS_METERS, workers=1):
            step = float(np.linalg.norm(collapsed[neighbor] - collapsed[node]))
            if cost + step < best[neighbor]:
                best[neighbor] = cost + step
                came_from[neighbor] = node
                heapq.heappush(frontier, (cost + step, neighbor))
    if not np.isfinite(best[summit]):
        raise SystemExit("[rope] lowest and highest voxels are not connected")
    ordered_indices = [summit]
    while ordered_indices[-1] != start:
        ordered_indices.append(int(came_from[ordered_indices[-1]]))
    ordered = collapsed[ordered_indices[::-1]]
    kernel = np.ones(SMOOTH_WINDOW) / SMOOTH_WINDOW
    pad = SMOOTH_WINDOW // 2
    waypoints = np.stack([
        np.convolve(np.pad(ordered[:, axis], pad, mode="edge"), kernel, mode="valid")
        for axis in (0, 1)], axis=1)
    length = np.linalg.norm(np.diff(waypoints, axis=0), axis=1).sum()
    climb = ordered[-1, 2] - ordered[0, 2]
    print(f"[rope] trail: {len(waypoints)} waypoints, {length:.0f} m, climbs {climb:+.1f} m")

    output_path = os.path.join(world_directory, "trail.json")
    json.dump({"trail_points_xy_meters": waypoints.round(3).tolist()},
              open(output_path, "w"))
    print(f"[done] {output_path} -- re-run marble.build_episode to lay the rope on it")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("spz_path")
    parser.add_argument("world_directory")
    parser.add_argument("built_directory")
    arguments = parser.parse_args()
    main(arguments.spz_path, arguments.world_directory, arguments.built_directory)
