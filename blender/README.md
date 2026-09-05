# Everest — East Rongbuk visual prototype

Moved into `spacial-intelligence-hack` on branch `marble-testing`. Run the
commands below from this `blender/` directory. Large binary assets are stored
with Git LFS: run `git lfs install` and `git lfs pull` after cloning.

A small, editable Blender scene built through Blender MCP, with a walking route between snow-covered moraine and glacier ice pinnacles. The camera frames roughly the first 100 metres of the reconstructed foreground against an Everest-area elevation backdrop.

## Current mountain trail

The original approach now leads directly into a continuous snowy ascent, about
770 m along the marked route with 104 m of elevation gain. Its first incline
starts roughly 50 m from the camera. Walk at 8 m/s or hold Shift for 20 m/s.
Snow-covered boulders, ice shoulders, scree, and red markers continue up the
same terrain mesh to the measured mountain flank.

`outputs/everest-rongbuk-study.blend` and the browser geometry contain this
extension, also exported as one file: `exports/everest-ascent-full.glb`
(374 MB, embedded geometry and textures). The original
`exports/everest-original-full.glb` and original 4K
render remain the earlier published scene. New views are saved as
`outputs/everest-approach.png`, `outputs/everest-lower-ascent.png`,
`outputs/everest-upper-ascent.png`, and `outputs/everest-mountain-trail.png`.

To reproduce from the original `outputs/everest-before-realism.blend`, run
`tools/extend_ascent.py` once through Blender MCP, then
`tools/remove_rear_plane.py`, `tools/refine_mountain_backdrop.py`, and
`tools/export_browser_scene.py`.
The extension script refuses to run twice on an already extended scene.

## First-person browser version

Open **http://127.0.0.1:4174/** and click **Start walking**. WASD moves, the mouse looks around, Shift moves faster, and Escape pauses. See [browser-scene/README.md](browser-scene/README.md) for running and editing the navigable version.

## Open the result

- `outputs/everest-rongbuk-4k.png` — 3840 × 2160 Cycles render.
- `outputs/everest-rongbuk-study.blend` — latest editable scene with its textures and environment lighting packed inside.
- `outputs/everest-before-realism.blend` and `outputs/everest-rongbuk-study.blend1` — preserved earlier revisions.
- `outputs/scene-manifest.json` — scene details and explicit limitations.

Open the `.blend` in Blender 5.2 or newer and select the scene **EVEREST | East Rongbuk — visual study**. Numpad 0 enters the camera view; F12 renders. Scene units are metres. Collections separate the mountain backdrop, foreground ground, glacier ice, rocks, markers, and camera/lighting. The original starting scene is retained separately.

This is a first visual prototype, with reconstructed close-range terrain. It is not yet a photographic digital twin: the foreground, ice formations, snow cover, and route markers are generated artistic approximations. The distant shape uses measured elevation data with a locally adjusted transition. The image is 4K; the terrain source has approximately 30-metre sample spacing, not 4K spatial accuracy. Robot articulation, collision geometry, terrain friction, and a locomotion controller are not implemented.

## Sources

- [Copernicus DEM GLO-30, public 2021 release](https://registry.opendata.aws/copernicus-dem/): elevation backdrop around 28.045° N, 86.945° E; geospatial metadata in `assets/terrain/source.json`. Elevations projected into UTM 45N and translated into a local coordinate system. Contains modified Copernicus DEM data.
- Poly Haven photographed 4K materials, CC0: [Snow 02](https://polyhaven.com/a/snow_02), [Rock Boulder Cracked](https://polyhaven.com/a/rock_boulder_cracked), and [Aerial Rocks 02](https://polyhaven.com/a/aerial_rocks_02). The original texture filenames and links are in `assets/material-sources.json`.
- [AGU East Rongbuk glacier photograph and article](https://news.agu.org/5-9-2024-peak-melt-for-everests-east-rongbuk-glacier-by-2060/): visual reference only; photograph not included or used as a rendered backdrop.

## Blender MCP

The local Blender MCP addon listens on `127.0.0.1:9876`. The project client starts the pinned `blender-mcp==1.9.1` MCP server over stdio and calls its `execute_blender_code` tool. Telemetry is disabled. Blender must be running with the addon server started.

To execute a script:

```sh
uv run --python 3.11 --with blender-mcp==1.9.1 python tools/blender_mcp_client.py tools/start_final_render.py
```

This renders the saved scene in a separate Blender process, using Metal on the local Apple GPU. Logs are in `outputs/final-render.log`; successful completion produces `outputs/final-complete.json`.

The scene was built with `build_everest_preview.py`, then refined once each with `refine_everest_preview.py`, `polish_everest_preview.py`, `finish_everest_geometry.py`, and `package_everest.py`. Refinement scripts are sequential build steps, not repeatable toggles; reopen the saved final `.blend` for everyday editing. `finish_preview_setup.py` was only a compatibility recovery script during the initial build and is not part of a clean rebuild.

Scripts resolve assets relative to this directory. The MCP client supplies a
script filename through Python's `runpy`, so relative project paths work inside
Blender as well as from the command line. Background renders use the running
Blender installation's executable. The Blender addon remains installed on the
local Mac; moving the project does not require reinstalling it.

## Migration contents and current state

- `assets/`: original terrain, 4K maps, HDR lighting, and scanned models,
  including the corrected `rock_07` mesh. `source-manifests/` preserves the
  Poly Haven download manifests previously held in temporary files.
- `outputs/`: all saved Blender revisions, renders, and scene metadata.
- `tools/`: Blender MCP client, build/refinement/export/render scripts.
- `browser-scene/`: the existing navigable Three.js preview, including its
  locally exported geometry. Babylon dependencies were installed for an
  experiment; the redesign was interrupted before a Babylon scene was built.
- `references/`: the original Rongbuk photograph and source attribution.
- `research/`: terrain-data research, moved from the old misspelled directory.

The latest `.blend` has the rock-shape correction; the browser export and older
render PNGs predate that correction. They are preserved as-is. Migration does
not mean the requested visual redesign is complete. The separate World Labs
experiment remains in the original workspace; this folder contains the Blender
project and its browser preview.

Build and dependency caches, browser-test artifacts, and logs were moved on
disk but remain gitignored. The existing robot simulation and `marble/` code
are not wired to this visual scene.
