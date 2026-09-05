# Everest — first-person browser scene

Open **http://127.0.0.1:4174/** and click **Start walking**.

- WASD: walk, with terrain contact and obstacle avoidance.
- Mouse: look around. If the browser cannot capture the pointer, hold and drag instead.
- Shift: walk faster.
- Escape or the pause button: open controls.
- Reset: return to the beginning of the trail.
- High detail: retain the 4K source textures and allow a display buffer up to 3840 × 2160, depending on window size and pixel density. Balanced caps rendering resolution for smoother movement.
- Touch screens: drag to look and use the movement pad.

## Run

```sh
npm install
npm run dev
```

This serves the app at port 4174. The existing World Labs experiment uses port 4173. No accounts, API keys, or additional world generation are needed to run this scene. Assets are served locally.

## What is rendered

Three.js renders the actual terrain, evaluated ice meshes, shared boulders, snow caps, scree, and trail markers exported from `outputs/everest-rongbuk-study.blend` through Blender MCP. The scene contains 2,580 objects represented by 85 reusable geometries and instanced draws. The geometry buffer is approximately 47 MB. The browser materials approximate the Blender procedural shaders using the same photographed 4K snow and rock textures, world-space projection, surface bump, real-time sun shadows, and sky fill. Real-time lighting differs from the Cycles still render.

The starting position, viewing direction, and field of view now come from the original Blender camera. The walker preserves its starting height above the ground and uses the exported 0.5-metre foreground height grid, substepped movement, and conservative cylindrical proxies around larger rocks and ice. Walking is bounded to the modeled foreground. This is a navigable visual prototype, not a robot locomotion simulator; cylinder proxies approximate the obstacles and can block narrow gaps. Terrain and source attribution are documented in the parent README.

## Verification

```sh
npm test
npm run build
node tests/browser.mjs
```

The browser test requires the dev server and Playwright Chromium (`npx playwright install chromium`). It checks rendering, walking, pause, reset, and quality selection. Screenshots and results are saved under `artifacts/`. It uses a separate headless browser.

## Re-export from Blender

With Blender MCP running, execute from the project root:

```sh
uv run --python 3.11 --with blender-mcp==1.9.1 python tools/blender_mcp_client.py tools/export_browser_scene.py
```

Then rebuild the browser app if serving the production `dist/` output. The exporter reads the original Blender scene and does not modify its geometry.

## Restored original scene

The editable source and browser geometry have been restored from
`outputs/everest-before-realism.blend`, matching the original saved 4K render.
The later tents, scanned replacement rocks, and HDR sky are absent from this
version. The browser uses the original camera and clear blue background;
its real-time material and lighting approximations still differ from Cycles.
