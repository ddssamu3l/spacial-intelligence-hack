"""Paint a Marble collider mesh with the world's own splat colors.

    python -m marble.paint_collider_from_splats \
        "<world>.spz" world_meshes/<name> built_worlds/<name>

The collider carries crisp physics-true geometry and zero appearance; the
splat export carries all the appearance and no walkable surface. This tool
marries them: subdivide the collider until edges are short enough to hold
color detail, then give every vertex the opacity-weighted color of its
nearest splats. Output is <built>/decoration.glb with vertex colors, in the
collider's native (console, Y-up metric) frame with the world's z anchor
baked in -- exactly what the app's decoration loader expects.

SPZ decoding follows the open spec (github.com/nianticlabs/spz), version 2:
gzip; 16-byte header; then positions (24-bit fixed point), alphas (uint8),
colors (uint8 SH-DC, rgb = 0.5 + C0*(v/255-0.5)/0.15), scales, rotations, SH.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import struct

import numpy as np

MAXIMUM_EDGE_METERS = 0.25
ALPHA_FLOOR = 0.35             # ignore near-transparent splats (fog, halos)
NEIGHBOR_SPLATS = 8
SH_C0 = 0.28209479


def load_spz(path: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """-> positions (N,3) float32, rgb (N,3) in [0,1], alpha (N,) in [0,1]."""
    raw = gzip.open(path, "rb").read()
    magic, version, count, sh_degree, fractional_bits, flags, _ = struct.unpack(
        "<IIIBBBB", raw[:16])
    if magic != 0x5053474E:
        raise SystemExit(f"[spz] bad magic {magic:#x} -- not an SPZ file")
    offset = 16
    position_bytes = np.frombuffer(raw, np.uint8, count * 9, offset); offset += count * 9
    alphas = np.frombuffer(raw, np.uint8, count, offset); offset += count
    colors = np.frombuffer(raw, np.uint8, count * 3, offset).reshape(count, 3)
    triples = position_bytes.reshape(count, 3, 3).astype(np.int32)
    fixed = triples[:, :, 0] | (triples[:, :, 1] << 8) | (triples[:, :, 2] << 16)
    fixed = np.where(fixed >= 1 << 23, fixed - (1 << 24), fixed)
    positions = (fixed / (1 << fractional_bits)).astype(np.float32)
    spherical_dc = (colors / 255.0 - 0.5) / 0.15
    rgb = np.clip(0.5 + SH_C0 * spherical_dc, 0.0, 1.0).astype(np.float32)
    print(f"[spz] v{version} {count} splats, shDeg {sh_degree}, "
          f"bbox {positions.min(axis=0).round(1)}..{positions.max(axis=0).round(1)}")
    return positions, rgb, (alphas / 255.0).astype(np.float32)


def paint(spz_path: str, world_directory: str, built_directory: str) -> None:
    import trimesh
    from scipy.spatial import cKDTree

    splat_positions, splat_rgb, splat_alpha = load_spz(spz_path)
    keep = splat_alpha > ALPHA_FLOOR
    splat_positions, splat_rgb = splat_positions[keep], splat_rgb[keep]
    print(f"[spz] {keep.mean() * 100:.0f}% of splats above alpha {ALPHA_FLOOR}")

    with open(os.path.join(world_directory, "world.json")) as handle:
        record = json.load(handle)
    z_anchor = float(record["assets"]["splats"]["semantics_metadata"]["ground_plane_offset"])

    mesh = trimesh.load(os.path.join(world_directory, "collider_mesh_url.glb"),
                        force="mesh")
    vertices, faces = mesh.vertices.copy(), mesh.faces.copy()
    vertices, faces = trimesh.remesh.subdivide_to_size(
        vertices, faces, max_edge=MAXIMUM_EDGE_METERS, max_iter=8)
    print(f"[mesh] collider {len(mesh.faces)} tris -> {len(faces)} tris "
          f"({len(vertices)} verts) at max edge {MAXIMUM_EDGE_METERS} m")

    tree = cKDTree(splat_positions)
    distances, indices = tree.query(vertices, k=NEIGHBOR_SPLATS, workers=1)
    weights = 1.0 / np.maximum(distances, 0.02) ** 2
    weights /= weights.sum(axis=1, keepdims=True)
    vertex_rgb = (splat_rgb[indices] * weights[..., None]).sum(axis=1)
    print(f"[paint] nearest-splat distance median "
          f"{np.median(distances[:, 0]):.3f} m  95th {np.percentile(distances[:, 0], 95):.3f} m")

    vertices[:, 1] -= z_anchor   # bake the world's z anchor (loader adds none)
    painted = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    painted.visual = trimesh.visual.ColorVisuals(
        painted, vertex_colors=(np.clip(vertex_rgb, 0, 1) * 255).astype(np.uint8))
    output_path = os.path.join(built_directory, "decoration.glb")
    trimesh.Scene({"splat_painted_collider": painted}).export(output_path)
    print(f"[done] {output_path}: {os.path.getsize(output_path) / 1e6:.1f} MB, "
          f"vertex-colored, Y-up console frame")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("spz_path")
    parser.add_argument("world_directory")
    parser.add_argument("built_directory")
    arguments = parser.parse_args()
    paint(arguments.spz_path, arguments.world_directory, arguments.built_directory)
