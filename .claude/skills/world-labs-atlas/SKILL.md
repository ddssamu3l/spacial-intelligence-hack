---
name: world-labs-atlas
description: Load when generating or exporting 3-D worlds from World Labs (Marble World API today; Atlas when its API exists) — auth, endpoints, export formats, metric scale, cost.
---

# World Labs World API cheat-sheet (researched 2026-09-01)

Full findings and verification markers: `docs/WORLD_LABS_ATLAS.md`.
**Atlas has NO API yet** (early access only, form
https://form.typeform.com/to/zHFR4r3A). Everything below is the Marble
World API, which is live. Check https://docs.worldlabs.ai/llms.txt for an
`atlas-*` model before assuming this is still true.

## Access
- Console (keys, credits): https://platform.worldlabs.ai/
- Base URL: `https://api.worldlabs.ai`, paths under `/marble/v1/`
- Auth header: `WLT-Api-Key: <key>`; env var `WORLDLABS_API_KEY`
  (convention of the official Python client
  https://github.com/worldlabsai/worldlabs-api-python, MIT; import as
  `from worldlabs_api.client import WorldLabsClient`; no PyPI package found —
  plain `requests` is enough).
- OpenAPI: https://docs.worldlabs.ai/api/reference/openapi.yaml
- Key is NOT in this repo's `.env` as of 2026-09-01; add
  `WORLDLABS_API_KEY=...` there and read it with `os.environ`.

## Flow
1. `POST /marble/v1/worlds:generate` with
   `{"model": "marble-1.1", "seed": 123, "display_name": "...",
     "world_prompt": {"type": "text", "text_prompt": "..."}}`
   (`type` may also be `image` / `multi-image` / `video`; media via a public
   `uri`, inline `data_base64`, or `POST .../media-assets:prepare-upload`).
   Response: `{operation_id, done}`.
2. `GET /marble/v1/operations/{operation_id}` until `done` (~5 min).
   `response` is the World: `world_id`, `assets.spz_urls`,
   `assets.collider_mesh_url` (GLB), `assets.pano_url`, `assets.caption`,
   `metric_scale_factor`, `ground_plane_offset`.
3. Optional `POST /marble/v1/worlds/{world_id}:export` with
   `asset_type` "splats"|"mesh", `format` "ply"|"glb",
   `resolution` full_res|500k|150k|100k, `mesh_variant`
   textured|vertex_colored -> another operation to poll; result has `url`.

Verbatim quickstart (https://docs.worldlabs.ai/api):

```python
import requests

url = "https://api.worldlabs.ai/marble/v1/worlds:generate"
payload = {
    "display_name": "Mystical Forest",
    "model": "marble-1.1",
    "world_prompt": {
        "type": "text",
        "text_prompt": "A mystical forest with glowing mushrooms"
    }
}
headers = {
    "WLT-Api-Key": "YOUR_API_KEY",
    "Content-Type": "application/json"
}
response = requests.post(url, json=payload, headers=headers)
data = response.json()
operation_id = data['operation_id']

# Poll until done
while True:
    poll_response = requests.get(
        f"https://api.worldlabs.ai/marble/v1/operations/{operation_id}",
        headers=headers
    )
    poll_data = poll_response.json()
    if poll_data['done']:
        world = poll_data['response']
        break
```

## Geometry facts that bite
- Raw assets are NOT in metres. Multiply positions and linear scales by
  `metric_scale_factor`, then subtract `ground_plane_offset` from Y; ground
  lands at y = 0 m. Log-scale splat fields: add `log(factor)`.
- Frame is OpenCV: +x left, +y DOWN, +z forward. Negate Y and Z for OpenGL;
  the repo's Z-up contract (docs/SCENE_ASSETS_SURVEY.md) needs a further
  rotation — print a bounding box and a floor-height sanity check on import.
- Collider GLB: 100-200k triangles, coarse. HQ mesh GLB: ~600k textured /
  ~1M vertex-coloured, up to 1 h, $2.80, 4/hour. Depth maps and camera
  poses are NOT exportable.
- Worlds are room-sized; larger spaces are composed in the app only.

## Money and limits
- $1 = 1,250 credits, $5 minimum. marble-1.0-draft ~$0.15; marble-1.1
  ~$1.28; marble-1.1-plus ~$1.71 mean. PLY export free; HQ mesh $2.80
  (cached after the first run). App credits and API credits are separate.
- Default rate: ~3 generation starts/min, 60/hour; approved accounts
  ~30/min (standard) / ~90/min (draft) via support@worldlabs.ai. 429 ->
  back off with jitter and honour `Retry-After`. 402 = out of credits.
- Terms: paid accounts own outputs for any purpose; s2.8(d) forbids using
  the service to build competing world-generation models.
