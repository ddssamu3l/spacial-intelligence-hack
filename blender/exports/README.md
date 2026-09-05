# Original Everest scene — single-file export

## Updated full scene

The extended scene is exported separately as **`everest-ascent-full.glb`**.
See [ASCENT.md](ASCENT.md) for its contents and viewing instructions.
The original export documented below is retained as the earlier version.

**`everest-original-full.glb`** is the complete restored scene shown in
`../outputs/everest-rongbuk-4k.png`. Open this one file; no external textures,
geometry buffers, or other downloads are required once the GLB is present.

The file includes the measured mountain backdrop, detailed foreground,
45 ice formations, rocks and snow caps, scree, cairn, red trail markers,
original camera, directional sunlight, and an unlit blue sky dome.
The default Blender cube and unrelated scene are excluded.

Procedural materials are baked into embedded base-color, tangent-normal,
and roughness maps. Large terrain surfaces use 4096-pixel maps; smaller
objects use 512–1024-pixel maps. Shared rocks reuse their prototype's bake.
No geometry decimation is applied. Renderer lighting and tone mapping can
differ from the original Cycles still render.

Units are meters, with standard glTF Y-up axes. Source Blender coordinates
convert as `(x, y, z) → (x, z, -y)`. Select the embedded **Camera • standing
on the glacier approach** for the original view. Auto-framing the whole
asset includes the distant mountains and 45 km sky dome and will zoom out
far beyond the walking trail.

`everest-original-full.json` records the exported object and material groups.
It is documentation, not a dependency of the GLB.

The active `everest-rongbuk-study.blend` now includes subsequent ascent work.
This GLB remains the original published scene. Rebuild it from the preserved
original source below, not from the extended study.

## Rebuild

Run in a separate background Blender process so the editable scene remains
unchanged:

```sh
blender -b blender/outputs/everest-before-realism.blend \
  --python blender/tools/export_original_glb.py
```

Optionally set `EVEREST_GLB_BAKE_CACHE` to an empty temporary directory to
retain intermediate bake images and resume the same export. Clear this
directory before exporting a changed scene.

## Attribution

Contains modified Copernicus DEM GLO-30 (2021), provided by the European
Union, DLR and Airbus. Photographic surface textures are from Poly Haven,
CC0. The foreground is reconstructed visual terrain, not surveyed close-range
geometry or a validated robot collision environment.

The GLB uses Git LFS. After cloning, run:

```sh
git lfs pull --include="blender/exports/everest-original-full.glb"
```
