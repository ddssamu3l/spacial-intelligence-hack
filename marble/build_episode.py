"""Turn one Marble world export into one flyable climbing episode.

    python -m marble.build_episode world_meshes/<name> [--out built_worlds/<name>]

Input (a directory, exactly what `marble_client.py` saves):
    world.json               Marble world record. The two numbers that matter:
                             assets.splats.semantics_metadata.metric_scale_factor
                             (multiply raw vertices -> meters) and
                             ground_plane_offset (camera height above ground;
                             subtract on the raw Y axis so the ground lands at 0).
    collider_mesh_url.glb    the collider mesh, raw Marble units, OpenCV frame
                             (+Y DOWN, so up = -Y). NOT watertight: sky and
                             occluded regions are holes.
    trail.json  (optional)   hand override: {"trail_points_xy_meters": [[x,y]..]}
                             in the OUTPUT (MuJoCo) frame, ordered uphill. When
                             present the path solver is skipped.

Output (a directory):
    episode.json    everything the sim needs, all in MuJoCo frame (x,y
                    horizontal meters, z up meters, ground near z=0):
                    - heightfield: grid origin (x0,y0), resolution, shape
                    - trail_points_xyz_meters: solved (or overridden) walk path,
                      dense polyline on the ground surface, ordered uphill
                    - anchor_points_xyz_meters: simplified piecewise-straight
                      rope anchors, LIFTED rope_height above ground
                    - spawn: xy + heading along the first segment
                    - goal: xy of the last anchor + radius_meters
                    - wind_speed_meters_per_second, time_limit_seconds
                    - provenance: input hashes, script version, solver stats
    hfield.npy      float32 (rows=y, cols=x) height in meters, holes inpainted
    walkable.npy    bool, same shape: cell is real geometry with slope under cap
    preview.png     top-down: height colormap, walkable tint, trail, spawn/goal

Every stage prints its distributional sanity numbers (hole fraction, slope
histogram, corridor size); read them before trusting an episode.
"""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import os

import cv2
import numpy as np

SCRIPT_VERSION = "2026-09-05.1"

GRID_RESOLUTION_METERS = 0.05
WALKABLE_SLOPE_LIMIT_DEGREES = 35.0
ROPE_HEIGHT_METERS = 0.60        # rope_rail.ROPE_HEIGHT: the trained channel height
ANCHOR_SIMPLIFY_TOLERANCE_METERS = 0.35
GOAL_RADIUS_METERS = 1.0
DEFAULT_TIME_LIMIT_SECONDS = 60.0
EDGE_CLEARANCE_METERS = 0.60     # path cost punishes cells nearer than this to a wall


def load_marble_vertices_faces(input_directory: str) -> tuple[np.ndarray, np.ndarray, dict]:
    """Collider GLB -> (vertices, faces) in the MuJoCo frame, plus metadata.

    Output vertices: float32 (N,3) meters, x/y horizontal, z up, ground ~ z=0.

    Two source frames, selected by world.json's optional "frame" key:
    - default (API asset, Marble RAW): scale by metric_scale_factor, subtract
      ground_plane_offset on raw Y (+Y DOWN), then
      (x, y, z)_mujoco = (x_raw, z_raw, -y_raw).
    - "gltf_y_up" (console download): already metric and Y-UP; the metadata
      fields are absent, so ground_plane_offset here means the mujoco-z shift
      that puts the ground under the camera origin at z ~ 0.
      (x, y, z)_mujoco = (x, -z, y) - (0, 0, offset).
    """
    import trimesh

    with open(os.path.join(input_directory, "world.json")) as handle:
        world_record = json.load(handle)
    semantics = world_record["assets"]["splats"]["semantics_metadata"]
    scale = float(semantics["metric_scale_factor"])
    ground_offset = float(semantics["ground_plane_offset"])
    frame = world_record.get("frame", "marble_raw")

    mesh = trimesh.load(os.path.join(input_directory, "collider_mesh_url.glb"), force="mesh")
    raw = np.asarray(mesh.vertices, dtype=np.float64) * scale
    if frame == "gltf_y_up":
        vertices = np.stack([raw[:, 0], -raw[:, 2],
                             raw[:, 1] - ground_offset], axis=1).astype(np.float32)
    else:
        raw[:, 1] -= ground_offset
        vertices = np.stack([raw[:, 0], raw[:, 2], -raw[:, 1]], axis=1).astype(np.float32)
    faces = np.asarray(mesh.faces, dtype=np.uint32)

    crop = world_record.get("crop_xy_meters")
    if crop:
        (x_min, x_max), (y_min, y_max) = crop
        centroids = vertices[faces].mean(axis=1)
        keep = ((centroids[:, 0] > x_min) & (centroids[:, 0] < x_max)
                & (centroids[:, 1] > y_min) & (centroids[:, 1] < y_max))
        faces = faces[keep]
        used, inverse = np.unique(faces.reshape(-1), return_inverse=True)
        vertices, faces = vertices[used], inverse.reshape(-1, 3).astype(np.uint32)
        print(f"[load] crop x [{x_min},{x_max}] y [{y_min},{y_max}]: "
              f"{keep.sum()} of {len(keep)} faces kept")

    extent = vertices.max(axis=0) - vertices.min(axis=0)
    print(f"[load] scale {scale:.4f}  camera_height {ground_offset:.2f} m  "
          f"tris {len(faces)}  extent x {extent[0]:.1f} y {extent[1]:.1f} z {extent[2]:.1f} m")
    return vertices, faces, world_record


def load_splat_points(input_directory: str, world_record: dict) -> np.ndarray:
    """splats.spz -> surface points in the MuJoCo frame (crop applied).

    The splats are the world's DENSE surface truth (~2M points) where the
    collider is a coarse proxy; a world.json with "geometry_source": "splats"
    builds its heightfield from these instead. Same frame handling as the
    collider path (only gltf_y_up console downloads are wired)."""
    from marble.paint_collider_from_splats import load_spz

    if world_record.get("frame") != "gltf_y_up":
        raise SystemExit("[load] splat geometry is only wired for gltf_y_up")
    semantics = world_record["assets"]["splats"]["semantics_metadata"]
    ground_offset = float(semantics["ground_plane_offset"])
    positions, _, alpha = load_spz(os.path.join(input_directory, "splats.spz"))
    points = np.stack([positions[:, 0], -positions[:, 2],
                       positions[:, 1] - ground_offset], axis=1)[alpha > 0.3]
    crop = world_record.get("crop_xy_meters")
    if crop:
        (x_min, x_max), (y_min, y_max) = crop
        inside = ((points[:, 0] > x_min) & (points[:, 0] < x_max)
                  & (points[:, 1] > y_min) & (points[:, 1] < y_max))
        points = points[inside]
    print(f"[load] {len(points)} splat surface points after alpha/crop")
    return points


def _bin_percentile(points: np.ndarray, x_low: float, y_low: float,
                    resolution: float, rows: int, columns: int,
                    percentile: float) -> np.ndarray:
    column_of = np.clip(((points[:, 0] - x_low) / resolution).astype(int), 0, columns - 1)
    row_of = np.clip(((points[:, 1] - y_low) / resolution).astype(int), 0, rows - 1)
    flat = row_of * columns + column_of
    order = np.argsort(flat)
    flat_sorted, z_sorted = flat[order], points[order, 2]
    boundaries = np.searchsorted(flat_sorted, np.arange(rows * columns + 1))
    height = np.full(rows * columns, np.nan, dtype=np.float32)
    occupied = np.nonzero(np.diff(boundaries))[0]
    for cell in occupied:
        height[cell] = np.percentile(z_sorted[boundaries[cell]:boundaries[cell + 1]],
                                     percentile)
    return height.reshape(rows, columns)


def rasterize_heightfield_from_points(points: np.ndarray, resolution: float) -> dict:
    """Sky-robust two-pass surface from splat centers; holes inpainted.

    Splat clouds contain the SKY as well as the ground, and one sky splat in
    an otherwise-empty cell poisons any single-pass statistic (measured: 90%
    holes and a z-median 9 m high). Pass one takes a 10th-percentile ground
    consensus on a 1 m grid; everything more than SKY_CLEARANCE above that
    consensus is discarded as sky/floaters; pass two bins the survivors at
    the target resolution (30th percentile: the LOW surface, matching the
    collider path's bottom-up raycast convention).
    Same output contract as rasterize_heightfield."""
    SKY_CLEARANCE_METERS = 3.0
    x_low, y_low = points[:, 0].min(), points[:, 1].min()
    coarse = 1.0
    coarse_columns = int(np.ceil((points[:, 0].max() - x_low) / coarse)) + 1
    coarse_rows = int(np.ceil((points[:, 1].max() - y_low) / coarse)) + 1
    ground = _bin_percentile(points, x_low, y_low, coarse, coarse_rows,
                             coarse_columns, 10.0)
    coarse_row = np.clip(((points[:, 1] - y_low) / coarse).astype(int), 0, coarse_rows - 1)
    coarse_column = np.clip(((points[:, 0] - x_low) / coarse).astype(int), 0, coarse_columns - 1)
    local_ground = ground[coarse_row, coarse_column]
    surface = points[np.isfinite(local_ground)
                     & (points[:, 2] < local_ground + SKY_CLEARANCE_METERS)]
    print(f"[hfield] sky filter kept {len(surface)} of {len(points)} points "
          f"(<{SKY_CLEARANCE_METERS} m above the 1 m ground consensus)")
    points = surface
    x_low, y_low = points[:, 0].min(), points[:, 1].min()
    columns = int(np.ceil((points[:, 0].max() - x_low) / resolution)) + 1
    rows = int(np.ceil((points[:, 1].max() - y_low) / resolution)) + 1
    height = _bin_percentile(points, x_low, y_low, resolution, rows, columns, 30.0)
    real = np.isfinite(height)
    hole_fraction = 1.0 - real.mean()

    filled = height.copy()
    for _ in range(max(rows, columns)):
        missing = np.isnan(filled)
        if not missing.any():
            break
        padded = np.pad(filled, 1, constant_values=np.nan)
        stack = np.stack([padded[dr:dr + rows, dc:dc + columns]
                          for dr in range(3) for dc in range(3)])
        with np.errstate(invalid="ignore"):
            neighbor_mean = np.nanmean(stack, axis=0)
        filled[missing] = neighbor_mean[missing]
    filled = np.nan_to_num(filled, nan=float(np.nanmedian(height)))

    finite = height[real]
    print(f"[hfield] grid {columns}x{rows} @ {resolution} m (from splats)  "
          f"holes {hole_fraction * 100:.1f}%  z range {finite.min():.2f}..{finite.max():.2f} m  "
          f"z median {np.median(finite):.2f} m")
    return {"height": filled, "real": real, "origin_xy": (float(x_low), float(y_low)),
            "resolution": resolution, "hole_fraction": float(hole_fraction)}


def rasterize_heightfield(vertices: np.ndarray, faces: np.ndarray) -> dict:
    """Upward raycast on a regular grid -> complete ground surface.

    Rays go BOTTOM-UP (+z from below the mesh): the first surface a rising ray
    meets is the ground, never a ceiling or roof — which makes indoor test
    worlds behave like terrain. Cells with no hit (mesh holes) are inpainted
    from their neighbors and marked not-real in the confidence mask.

    Returns {height (rows=y, cols=x), real (bool), origin_xy, resolution}.
    """
    import open3d as o3d

    x_low, y_low = vertices[:, 0].min(), vertices[:, 1].min()
    x_high, y_high = vertices[:, 0].max(), vertices[:, 1].max()
    columns = int(np.ceil((x_high - x_low) / GRID_RESOLUTION_METERS)) + 1
    rows = int(np.ceil((y_high - y_low) / GRID_RESOLUTION_METERS)) + 1

    scene = o3d.t.geometry.RaycastingScene()
    scene.add_triangles(o3d.core.Tensor(vertices), o3d.core.Tensor(faces))

    grid_x = x_low + np.arange(columns, dtype=np.float32) * GRID_RESOLUTION_METERS
    grid_y = y_low + np.arange(rows, dtype=np.float32) * GRID_RESOLUTION_METERS
    mesh_x, mesh_y = np.meshgrid(grid_x, grid_y)
    z_start = float(vertices[:, 2].min()) - 1.0
    origins = np.stack([mesh_x, mesh_y, np.full_like(mesh_x, z_start)], axis=-1)
    directions = np.broadcast_to(np.array([0.0, 0.0, 1.0], np.float32), origins.shape)
    rays = np.concatenate([origins, directions], axis=-1).reshape(-1, 6).astype(np.float32)
    hit_distance = scene.cast_rays(o3d.core.Tensor(rays))["t_hit"].numpy().reshape(rows, columns)

    real = np.isfinite(hit_distance)
    height = np.where(real, z_start + hit_distance, np.nan).astype(np.float32)

    hole_fraction = 1.0 - real.mean()
    # inpaint: iterative 3x3 mean of known neighbors, until full
    filled = height.copy()
    for _ in range(max(rows, columns)):
        missing = np.isnan(filled)
        if not missing.any():
            break
        padded = np.pad(filled, 1, constant_values=np.nan)
        stack = np.stack([padded[dr:dr + rows, dc:dc + columns]
                          for dr in range(3) for dc in range(3)])
        with np.errstate(invalid="ignore"):
            neighbor_mean = np.nanmean(stack, axis=0)
        filled[missing] = neighbor_mean[missing]
    filled = np.nan_to_num(filled, nan=float(np.nanmedian(height)))

    finite = height[real]
    print(f"[hfield] grid {columns}x{rows} @ {GRID_RESOLUTION_METERS} m  "
          f"holes {hole_fraction * 100:.1f}%  z range {finite.min():.2f}..{finite.max():.2f} m  "
          f"z median {np.median(finite):.2f} m")
    return {"height": filled, "real": real, "origin_xy": (float(x_low), float(y_low)),
            "resolution": GRID_RESOLUTION_METERS, "hole_fraction": float(hole_fraction)}


def walkability(height: np.ndarray, real: np.ndarray,
                slope_limit_degrees: float = WALKABLE_SLOPE_LIMIT_DEGREES,
                resolution: float = GRID_RESOLUTION_METERS
                ) -> tuple[np.ndarray, np.ndarray]:
    """Per-cell slope (degrees) and the walkable mask (real + gentle slope).

    slope_limit_degrees: 35 encodes a walker; a roped ascender tolerates
    more -- world.json may override with walkable_slope_limit_degrees."""
    gradient_y, gradient_x = np.gradient(height, resolution)
    slope_degrees = np.degrees(np.arctan(np.hypot(gradient_x, gradient_y))).astype(np.float32)
    walkable = real & (slope_degrees < slope_limit_degrees)
    histogram, _ = np.histogram(slope_degrees[real], bins=[0, 10, 20, 30, 40, 60, 90])
    print(f"[slope] walkable {walkable.mean() * 100:.1f}% of grid  "
          f"slope histogram (0-10-20-30-40-60-90 deg): {histogram.tolist()}")
    return slope_degrees, walkable


def solve_trail(height: np.ndarray, slope_degrees: np.ndarray,
                walkable: np.ndarray,
                endpoint_cells: tuple | None = None,
                resolution: float = GRID_RESOLUTION_METERS) -> np.ndarray:
    """Least-cost corridor path as (row, col) indices.

    Endpoints: lowest -> highest walkable cell by default (a walled uphill
    corridor determines its own ends), or the author-declared pair from
    endpoints.json when given (open terrain under-determines the destination:
    on the Rongbuk moraine the highest walkable ground is a snow bank, not
    the trail's end). Either way the PATH between them is solved, never given.

    Cost per step: base + slope penalty + wall-hugging penalty (cells closer
    than EDGE_CLEARANCE_METERS to non-walkable pay extra), so the path rides
    the corridor's centerline. 8-connected Dijkstra on the largest walkable
    component. Deterministic.
    """
    from scipy import ndimage

    labels, component_count = ndimage.label(walkable)
    if component_count == 0:
        raise SystemExit("[trail] no walkable cells at all -- not an episode")
    sizes = ndimage.sum(walkable, labels, index=np.arange(1, component_count + 1))
    corridor = labels == (1 + int(np.argmax(sizes)))
    print(f"[trail] walkable components {component_count}, largest "
          f"{corridor.sum() * resolution ** 2:.1f} m^2")

    clearance = ndimage.distance_transform_edt(corridor) * resolution

    if endpoint_cells is not None:
        corridor_cells = np.argwhere(corridor)
        def snap(cell) -> tuple[int, int]:
            distances = np.linalg.norm(corridor_cells - np.asarray(cell), axis=1)
            nearest = corridor_cells[int(np.argmin(distances))]
            offset = distances.min() * resolution
            if offset > 3.0:
                raise SystemExit(f"[trail] endpoint hint {cell} is {offset:.1f} m "
                                 "from any walkable cell -- wrong frame?")
            return int(nearest[0]), int(nearest[1])
        start, goal = snap(endpoint_cells[0]), snap(endpoint_cells[1])
        print(f"[trail] endpoints from endpoints.json (snapped to corridor)")
    else:
        # Start/goal: the MOST-CENTERED cell within the lowest/highest elevation
        # band, not the bare argmin/argmax -- a laterally flat corridor floor makes
        # the extreme cell a corner, and the robot should spawn mid-corridor.
        corridor_height = np.where(corridor, height, np.nan)
        low, high = np.nanmin(corridor_height), np.nanmax(corridor_height)
        def most_centered(band: np.ndarray) -> tuple[int, int]:
            return np.unravel_index(np.argmax(np.where(band, clearance, -1.0)), height.shape)
        start = most_centered(corridor & (height < low + 0.30))
        goal = most_centered(corridor & (height > high - 0.30))
    wall_penalty = np.clip(EDGE_CLEARANCE_METERS - clearance, 0.0, None) * 20.0
    step_cost = 1.0 + (slope_degrees / 10.0) ** 2 + wall_penalty

    rows, columns = height.shape
    total_cost = np.full(height.shape, np.inf, dtype=np.float64)
    came_from = np.full(height.shape, -1, dtype=np.int64)
    total_cost[start] = 0.0
    frontier: list[tuple[float, int, int]] = [(0.0, int(start[0]), int(start[1]))]
    neighbor_offsets = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    while frontier:
        cost_here, row, column = heapq.heappop(frontier)
        if (row, column) == tuple(goal):
            break
        if cost_here > total_cost[row, column]:
            continue
        for delta_row, delta_column in neighbor_offsets:
            next_row, next_column = row + delta_row, column + delta_column
            if not (0 <= next_row < rows and 0 <= next_column < columns):
                continue
            if not corridor[next_row, next_column]:
                continue
            step = np.hypot(delta_row, delta_column) * step_cost[next_row, next_column]
            candidate = cost_here + step
            if candidate < total_cost[next_row, next_column]:
                total_cost[next_row, next_column] = candidate
                came_from[next_row, next_column] = row * columns + column
                heapq.heappush(frontier, (candidate, next_row, next_column))

    if not np.isfinite(total_cost[goal]):
        raise SystemExit("[trail] lowest and highest walkable cells are not connected")
    path = [tuple(goal)]
    while path[-1] != tuple(start):
        flat = came_from[path[-1]]
        path.append((int(flat // columns), int(flat % columns)))
    path.reverse()
    path_array = np.array(path, dtype=np.int64)

    climb = height[goal] - height[start]
    length = len(path_array) * resolution
    print(f"[trail] path {len(path_array)} cells (~{length:.1f} m), climbs {climb:.2f} m, "
          f"mean slope on path {slope_degrees[path_array[:, 0], path_array[:, 1]].mean():.1f} deg")
    return path_array


def simplify_polyline(points_xy: np.ndarray, tolerance: float) -> np.ndarray:
    """Douglas-Peucker on (N,2); returns indices of kept points."""
    keep = np.zeros(len(points_xy), dtype=bool)
    keep[[0, -1]] = True
    stack = [(0, len(points_xy) - 1)]
    while stack:
        first, last = stack.pop()
        if last <= first + 1:
            continue
        segment = points_xy[last] - points_xy[first]
        segment_length = np.linalg.norm(segment)
        relative = points_xy[first + 1:last] - points_xy[first]
        if segment_length < 1e-9:
            deviation = np.linalg.norm(relative, axis=1)
        else:
            unit = segment / segment_length
            deviation = np.abs(relative[:, 0] * unit[1] - relative[:, 1] * unit[0])
        worst = int(np.argmax(deviation))
        if deviation[worst] > tolerance:
            middle = first + 1 + worst
            keep[middle] = True
            stack.extend([(first, middle), (middle, last)])
    return np.flatnonzero(keep)


def cells_to_world(path_cells: np.ndarray, grid: dict, height: np.ndarray) -> np.ndarray:
    """(row, col) path -> (N,3) meters on the ground surface."""
    x0, y0 = grid["origin_xy"]
    resolution = grid["resolution"]
    x = x0 + path_cells[:, 1] * resolution
    y = y0 + path_cells[:, 0] * resolution
    z = height[path_cells[:, 0], path_cells[:, 1]]
    return np.stack([x, y, z], axis=1)


def write_preview(output_directory: str, height: np.ndarray, walkable: np.ndarray,
                  trail_xyz: np.ndarray, anchors_xyz: np.ndarray, grid: dict) -> None:
    normalized = (height - height.min()) / max(1e-6, float(height.max() - height.min()))
    image = cv2.applyColorMap((normalized * 255).astype(np.uint8), cv2.COLORMAP_CIVIDIS)
    image[~walkable] = (image[~walkable] * 0.35).astype(np.uint8)

    def to_pixel(points_xyz):
        x0, y0 = grid["origin_xy"]
        column = ((points_xyz[:, 0] - x0) / grid["resolution"]).astype(int)
        row = ((points_xyz[:, 1] - y0) / grid["resolution"]).astype(int)
        return np.stack([column, row], axis=1)

    cv2.polylines(image, [to_pixel(trail_xyz)], False, (60, 220, 255), 2)
    for pixel in to_pixel(anchors_xyz):
        cv2.circle(image, tuple(pixel), 4, (0, 80, 255), -1)
    start_pixel, goal_pixel = to_pixel(trail_xyz[[0]])[0], to_pixel(trail_xyz[[-1]])[0]
    cv2.circle(image, tuple(start_pixel), 7, (80, 255, 80), 2)
    cv2.circle(image, tuple(goal_pixel), 7, (0, 0, 255), 2)
    image = cv2.flip(image, 0)  # +y up on screen
    scale = max(1, int(600 / max(image.shape[:2])))
    image = cv2.resize(image, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(os.path.join(output_directory, "preview.png"), image)


def file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def build_episode(input_directory: str, output_directory: str) -> dict:
    os.makedirs(output_directory, exist_ok=True)
    with open(os.path.join(input_directory, "world.json")) as handle:
        world_record = json.load(handle)
    if world_record.get("geometry_source") == "splats":
        points = load_splat_points(input_directory, world_record)
        resolution = float(world_record.get("grid_resolution_meters", 0.10))
        grid = rasterize_heightfield_from_points(points, resolution)
    else:
        vertices, faces, world_record = load_marble_vertices_faces(input_directory)
        grid = rasterize_heightfield(vertices, faces)
    resolution = grid["resolution"]
    height, real = grid["height"], grid["real"]
    slope_limit = float(world_record.get("walkable_slope_limit_degrees",
                                         WALKABLE_SLOPE_LIMIT_DEGREES))
    if slope_limit != WALKABLE_SLOPE_LIMIT_DEGREES:
        print(f"[slope] world.json overrides walkable limit: {slope_limit:g} deg")
    slope_degrees, walkable = walkability(height, real, slope_limit, resolution)

    override_path = os.path.join(input_directory, "trail.json")
    if os.path.exists(override_path):
        with open(override_path) as handle:
            override_xy = np.asarray(json.load(handle)["trail_points_xy_meters"], dtype=np.float64)
        x0, y0 = grid["origin_xy"]
        cells = np.stack([((override_xy[:, 1] - y0) / grid["resolution"]).astype(int),
                          ((override_xy[:, 0] - x0) / grid["resolution"]).astype(int)], axis=1)
        print(f"[trail] hand override: {len(cells)} waypoints from trail.json")
        path_cells = cells
    else:
        endpoint_cells = None
        endpoints_path = os.path.join(input_directory, "endpoints.json")
        if os.path.exists(endpoints_path):
            with open(endpoints_path) as handle:
                declared = json.load(handle)
            x0, y0 = grid["origin_xy"]
            def to_cell(xy) -> tuple[float, float]:
                return ((xy[1] - y0) / grid["resolution"], (xy[0] - x0) / grid["resolution"])
            endpoint_cells = (to_cell(declared["spawn_xy_meters"]),
                              to_cell(declared["goal_xy_meters"]))
        path_cells = solve_trail(height, slope_degrees, walkable, endpoint_cells,
                                 resolution)

    trail_xyz = cells_to_world(path_cells, grid, height)
    origin_distance = float(np.linalg.norm(trail_xyz[:, :2], axis=1).min())
    print(f"[trail] closest approach to world origin (camera stood on the trail): "
          f"{origin_distance:.2f} m {'OK' if origin_distance < 2.0 else '** SUSPICIOUS — hand-check this world **'}")

    keep = simplify_polyline(trail_xyz[:, :2], ANCHOR_SIMPLIFY_TOLERANCE_METERS)
    anchors_xyz = trail_xyz[keep].copy()
    anchors_xyz[:, 2] += ROPE_HEIGHT_METERS
    segment_lengths = np.linalg.norm(np.diff(anchors_xyz, axis=0), axis=1)
    print(f"[rope] {len(anchors_xyz)} anchors, segment lengths "
          f"min {segment_lengths.min():.2f} / median {np.median(segment_lengths):.2f} / "
          f"max {segment_lengths.max():.2f} m")

    heading = float(np.arctan2(*(trail_xyz[min(20, len(trail_xyz) - 1), :2]
                                 - trail_xyz[0, :2])[::-1]))
    episode = {
        "episode_name": os.path.basename(os.path.normpath(output_directory)),
        "frame": "mujoco: x,y horizontal meters, z up meters, ground near z=0",
        "heightfield": {"origin_xy": grid["origin_xy"], "resolution_meters": grid["resolution"],
                        "shape_rows_columns": list(height.shape)},
        "trail_points_xyz_meters": trail_xyz.round(4).tolist(),
        "anchor_points_xyz_meters": anchors_xyz.round(4).tolist(),
        "rope_height_meters": ROPE_HEIGHT_METERS,
        "spawn": {"xy_meters": trail_xyz[0, :2].round(4).tolist(),
                  "heading_radians": round(heading, 4)},
        "goal": {"xy_meters": trail_xyz[-1, :2].round(4).tolist(),
                 "radius_meters": GOAL_RADIUS_METERS},
        "wind_speed_meters_per_second": 0.0,
        "time_limit_seconds": DEFAULT_TIME_LIMIT_SECONDS,
        "provenance": {
            "script_version": SCRIPT_VERSION,
            "input_directory": os.path.abspath(input_directory),
            "collider_sha256": (file_sha256(os.path.join(input_directory, "collider_mesh_url.glb"))
                                if os.path.exists(os.path.join(input_directory, "collider_mesh_url.glb")) else None),
            "splats_sha256": (file_sha256(os.path.join(input_directory, "splats.spz"))
                              if os.path.exists(os.path.join(input_directory, "splats.spz")) else None),
            "geometry_source": world_record.get("geometry_source", "collider"),
            "world_json_sha256": file_sha256(os.path.join(input_directory, "world.json")),
            "hole_fraction": grid["hole_fraction"],
            "trail_source": ("trail.json" if os.path.exists(override_path)
                             else "solver+endpoints.json"
                             if os.path.exists(os.path.join(input_directory, "endpoints.json"))
                             else "solver"),
            "origin_distance_meters": origin_distance,
        },
    }
    np.save(os.path.join(output_directory, "hfield.npy"), height)
    np.save(os.path.join(output_directory, "walkable.npy"), walkable)
    with open(os.path.join(output_directory, "episode.json"), "w") as handle:
        json.dump(episode, handle, indent=1)
    write_preview(output_directory, height, walkable, trail_xyz, anchors_xyz, grid)
    print(f"[done] {output_directory}: episode.json + hfield.npy + walkable.npy + preview.png")
    return episode


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input_directory")
    parser.add_argument("--out", default=None,
                        help="output directory (default built_worlds/<input name>)")
    arguments = parser.parse_args()
    default_output = os.path.join(
        "built_worlds", os.path.basename(os.path.normpath(arguments.input_directory)))
    build_episode(arguments.input_directory, arguments.out or default_output)
