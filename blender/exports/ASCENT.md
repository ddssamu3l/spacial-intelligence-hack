# Complete extended Everest scene

Open **`everest-ascent-full.glb`**. It contains the entire updated scene in
one binary glTF file; all geometry and baked textures are embedded.
The file is 373,707,040 bytes (374 MB), containing 7,471 mesh objects,
111 shared meshes, and 309 embedded images.

Includes the original snowy approach, the continuous 770-metre marked trail,
approximately 104 metres of elevation gain, mountain backdrop, snow-covered
boulders, ice formations, scree, red route markers, and corrected rear terrain.
The original starting camera and directional sun are included.

Use the embedded camera for the starting view. Framing the entire model will
zoom out to include the 26-kilometre mountain backdrop. Units are metres;
standard glTF Y-up coordinates correspond to Blender `(x, z, -y)`.

Procedural materials are baked to base-color, normal, and roughness textures.
Terrain uses 4096-pixel textures; smaller assets use 512–1024-pixel textures.
Shared rocks reuse their prototype's textures. No geometry is decimated.

The GLB has no enclosing sky mesh. Set a blue background and environment light
in the receiving viewer. glTF does not carry Blender world shaders, so sky,
environment lighting, and tone mapping depend on the viewer. The browser's
walking controls are application code and are not part of a GLB.

`everest-ascent-full.json` documents source identity and object groups;
`.validation.json` and `.khronos.json` record export validation. These reports
are not needed to open the GLB. Git LFS stores the large binary file.

Rebuild from the current scene in a background Blender process:

```sh
EVEREST_GLB_NAME=everest-ascent-full EVEREST_GLB_SKY=0 \
  blender -b blender/outputs/everest-rongbuk-study.blend \
  --python blender/tools/export_original_glb.py
python3 blender/tools/finalize_glb.py blender/exports/everest-ascent-full.glb
python3 blender/tools/verify_original_glb.py blender/exports/everest-ascent-full.glb
```

Contains modified Copernicus DEM GLO-30 (2021), European Union, DLR and Airbus.
Photographic textures are Poly Haven CC0. The foreground and trail are visual
reconstructions, not surveyed close-range terrain or validated robot collisions.
