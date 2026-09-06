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
SNAP_RADIUS_METERS = 1.5
TRACE_STEP_METERS = 1.2
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

    rope_color = record.get("rope_color")
    if rope_color == "red":
        colored = (rgb[:, 0] - np.maximum(rgb[:, 1], rgb[:, 2])) > 0.10
    elif rope_color == "blue":
        colored = (rgb[:, 2] - np.maximum(rgb[:, 0], rgb[:, 1])) > 0.10
    else:
        colored = (rgb.max(axis=1) - rgb.min(axis=1)) > CHROMA_FLOOR
    candidate = (colored & (alpha > ALPHA_FLOOR)
                 & (above_ground > HEIGHT_BAND_METERS[0])
                 & (above_ground < HEIGHT_BAND_METERS[1]))
    points = mujoco[candidate]
    # how strongly each splat matches the rope color -- the crisp rope is far
    # more saturated than color bleed on nearby snow; squared, it dominates
    # the voxel centerline means below.
    saturation = (rgb.max(axis=1) - rgb.min(axis=1))[candidate].astype(np.float64)
    # the white-color-white signature (user's rule): a rope is a colored
    # strand whose immediate SURROUNDINGS are bright snow. Each candidate is
    # weighted by the whiteness of its non-candidate neighborhood, so colored
    # patches inside colored regions (rock, gear piles) fade.
    from scipy.spatial import cKDTree as _tree
    background = mujoco[~candidate & (alpha > ALPHA_FLOOR)]
    background_color = rgb[~candidate & (alpha > ALPHA_FLOOR)]
    background_tree = _tree(background)
    whiteness = np.full(len(points), 0.5)
    for index, neighbors in enumerate(background_tree.query_ball_point(
            points, 0.8, workers=1)):
        if len(neighbors) >= 3:
            neighbor_rgb = background_color[neighbors]
            brightness = neighbor_rgb.mean()
            neighbor_chroma = (neighbor_rgb.max(axis=1) - neighbor_rgb.min(axis=1)).mean()
            whiteness[index] = float(np.clip(brightness - neighbor_chroma, 0.0, 1.0))
    saturation = saturation * (0.25 + whiteness)
    print(f"[rope] white-surround weighting: median whiteness {np.median(whiteness):.2f}")
    print(f"[rope] {candidate.sum()} {rope_color or 'saturated'} surface-hugging splats")

    # The linearity gate exists to reject saturated ROCK on mixed worlds; a
    # world that declares its rope color has no confounder, and the gate only
    # shreds the line's thick sections (coils, anchors) into fragments.
    apply_linearity = record.get("rope_linearity", rope_color is None)
    tree = cKDTree(points)
    linear = np.ones(len(points), bool) if not apply_linearity \
        else np.zeros(len(points), bool)
    for index, neighbors in enumerate(
            tree.query_ball_point(points, LINEARITY_RADIUS_METERS, workers=1)
            if apply_linearity else []):
        if len(neighbors) < 4:
            continue
        centered = points[neighbors] - points[neighbors].mean(axis=0)
        eigenvalues = np.linalg.eigvalsh(centered.T @ centered / len(neighbors))
        linear[index] = eigenvalues[-1] / max(eigenvalues.sum(), 1e-9) > LINEARITY_SHARE
    points = points[linear]
    saturation = saturation[linear]
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
    chain_weight = saturation[camera_chain] ** 2
    print(f"[rope] camera chain: {camera_chain.sum()} splats, "
          f"z {chain[:, 2].min():.1f}..{chain[:, 2].max():.1f} m")

    # 3-D keys: a 2-D (xy) voxelization collapses a near-vertical rope run
    # into one averaged point and tears the chain apart in z.
    if rope_color is not None:
        # STRAND TRACER (declared-color worlds): from the strand point nearest
        # the camera, step repeatedly to the saturation^2-weighted centroid of
        # strand splats inside a forward cone -- follows the actual rope and
        # cannot be pulled sideways by off-line colored debris (the failure
        # that bent South Summit's top away from the ridge line).
        strand_tree = cKDTree(chain[:, :2])
        position = chain[int(np.argmin(np.linalg.norm(chain[:, :2], axis=1))), :2].copy()
        heading = None
        waypoints_list = [position.copy()]
        used = np.zeros(len(chain), bool)
        for _ in range(200):
            neighbors = np.array(strand_tree.query_ball_point(position, TRACE_STEP_METERS * 2.5,
                                                              workers=1))
            if len(neighbors) == 0:
                break
            offsets = chain[neighbors, :2] - position
            distances = np.linalg.norm(offsets, axis=1)
            forward = distances > 0.3
            if heading is not None:
                cosines = (offsets @ heading) / np.maximum(distances, 1e-9)
                forward &= cosines > 0.2      # +/- ~78 degree cone
            forward &= ~used[neighbors]
            candidates = neighbors[forward]
            if len(candidates) < 2:
                break
            weights = chain_weight[candidates] * distances[forward]
            step_target = np.average(chain[candidates, :2], axis=0, weights=weights)
            direction = step_target - position
            norm = np.linalg.norm(direction)
            if norm < 1e-6:
                break
            heading = direction / norm
            position = position + heading * TRACE_STEP_METERS
            used[neighbors[distances < TRACE_STEP_METERS]] = True
            waypoints_list.append(position.copy())
        waypoints = np.array(waypoints_list)
        # the stepping oscillates laterally around the strand (visible as
        # zigzag against a straight rope) -- smooth at ~8 m scale, twice.
        for _ in range(2):
            if len(waypoints) >= 7:
                waypoints = np.stack([
                    np.convolve(np.pad(waypoints[:, axis], 3, mode="edge"),
                                np.ones(7) / 7, mode="valid")
                    for axis in (0, 1)], axis=1)
        length = np.linalg.norm(np.diff(waypoints, axis=0), axis=1).sum()
        print(f"[rope] traced {len(waypoints_list)} steps, smoothed to "
              f"{length:.0f} m along the strand")
        output_path = os.path.join(world_directory, "trail.json")
        json.dump({"trail_points_xy_meters": waypoints.round(3).tolist()},
                  open(output_path, "w"))
        print(f"[done] {output_path} -- re-run marble.build_episode to lay the rope on it")
        return

    voxel = np.round(chain / VOXEL_METERS).astype(int)
    centers = {}
    for key, point, weight in zip(map(tuple, voxel), chain, chain_weight):
        centers.setdefault(key, []).append((point, weight))
    collapsed = np.array([
        np.average([point for point, _ in group], axis=0,
                   weights=[weight for _, weight in group])
        for group in centers.values()])
    voxel_saturation = np.array([np.mean([weight for _, weight in group])
                                 for group in centers.values()])
    voxel_saturation /= voxel_saturation.max()
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
    # Marble worlds are shot FROM the route: the camera origin is the one
    # point guaranteed to be on the path, so the rope starts there.
    start = int(np.argmin(np.linalg.norm(collapsed[:, :2], axis=1)))
    summit = int(np.argmax(collapsed[:, 2]))
    print(f"[rope] start voxel {collapsed[start].round(1)} "
          f"({np.linalg.norm(collapsed[start, :2]):.1f} m from camera), "
          f"summit voxel {collapsed[summit].round(1)}")
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
            # distance scaled by how faint the voxel's rope color is: the
            # route prefers the intensely-colored rope over color bleed.
            step = float(np.linalg.norm(collapsed[neighbor] - collapsed[node])
                         * (1.0 + 4.0 * (1.0 - voxel_saturation[neighbor])))
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
    # SNAP: the voxel route is only ~2 m accurate; pull every waypoint to
    # the weighted centroid of the actual rope splats around it.
    chain_tree = cKDTree(chain[:, :2])
    snapped = waypoints.copy()
    snap_success = np.zeros(len(waypoints), bool)
    snap_distances = []
    for index, waypoint in enumerate(waypoints):
        for radius in (SNAP_RADIUS_METERS, 3.0, 5.0):
            neighbors = chain_tree.query_ball_point(waypoint, radius, workers=1)
            if len(neighbors) >= 3:
                weights = chain_weight[neighbors]
                snapped[index] = np.average(chain[neighbors, :2], axis=0, weights=weights)
                snap_distances.append(np.linalg.norm(snapped[index] - waypoint))
                snap_success[index] = True
                break
    # the visible rope ends where its splats end: waypoints past the last
    # snappable one are voxel extrapolation, and they are what made the laid
    # line diverge at the top -- drop them.
    if snap_success.any():
        last = int(np.nonzero(snap_success)[0][-1])
        if last + 1 < len(snapped):
            print(f"[rope] trimmed {len(snapped) - last - 1} unsnappable tail waypoints")
        snapped = snapped[:last + 1]
    print(f"[rope] snapped {snap_success.sum()}/{len(waypoints)} waypoints, "
          f"median pull {np.median(snap_distances):.2f} m")
    waypoints = np.stack([
        np.convolve(np.pad(snapped[:, axis], 1, mode="edge"),
                    np.ones(3) / 3, mode="valid")
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
