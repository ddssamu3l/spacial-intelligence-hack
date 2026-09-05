# spacial-intelligence-hack

Spatial Intelligence + Generative 3D Hackathon (Founders Inc, SF, 2026-09-05),
**Physical AI & Simulation track**.

The pitch: **photo → benchmark**. Real Everest trail photos go into World Labs
Marble, which generates 3-D worlds; we turn each world's collider into MuJoCo
terrain, lay a fixed rope along the trail (piecewise-straight between anchors,
like real fixed lines), and batch-run our rope-ascender RL policy on every
generated episode — wind, start pose, destination — with interactive 3-D
replays. Terrain that used to be hand-faked is now manufactured from ground
truth imagery.

Transplanted from the Himalaya Robotics Hack winner
(`~/Documents/code/himalaya_hack/g1-himalayas`): the MuJoCo harness + web app
(policy dropdown, human guide, vision follow, voice stop/clear, battery model),
the jacketed Unitree G1 with ascender, the rope/ratchet mechanism, and Mrinal's
trained climbing policies.

## Run

```bash
# venv shared with the old repo (all deps installed there)
~/Documents/code/himalaya_hack/.venv_everest/bin/python \
    -m app.harness.runtime --live --world chloe_v2_20 --port 8775
# page: http://localhost:8776/   (ws = port, http = port+1)
```

Headless policy measurement:

```bash
.../python -m app.harness.chloe_worlds --slope 20 --seconds 15 \
    --policy rl/policies/g1_ascender_slope20_final_2026-08-30_13-55-14.onnx
```

## Layout

- `app/` — harness runtime, web viewer, hearing/vision, BMS bridge (from g1-himalayas)
- `assets/` — G1 + ascender MJCF, rope_rail.py, humans, old environments
  (`_menagerie/` meshes and `.reference/` are on-disk but gitignored; regenerate
  with `app/harness/provision_assets.py`)
- `rl/` — environment modules (climb scene, terrain hfield, RopeRoute) + policy ONNX
- `marble/` — World Labs Marble lane: `marble_client.py` (generate/poll/export),
  `analyze_world.py` (scale/floor/collider sanity), `openapi.yaml`, research
  memos, and `worlds/` (gitignored) holding the two 2026-09-04 limit-test worlds
- `.env` (gitignored) — `WORLD_LABS_API_KEY` (~2,200 credits left on our key;
  hackathon issues fresh ones)

## Hack-day build order

1. ~~Transplant + smoke boot~~ (done: policy climbs +2.02 m/5 s at 20°, app serves)
2. Marble collider GLB → rectify (scale/axis/offset) → downward-raycast grid →
   inpainted MuJoCo hfield
3. Transfer exam: policy on a *true inclined* hfield with one straight rope
   (trained plant was flat ground + tilted gravity — never real terrain)
4. Anchored rope segments + re-clip at bends
5. Episode format (trail polyline, wind, spawn, goal) + batch runner + grading
6. Generated-world replays in the 3-D viewer

## Status 2026-09-05 (pre-hack night)

Steps 1-6 all work end-to-end on the two test worlds: `marble_*` worlds appear
in the app dropdown, the terrain renders from the episode heightfield, the
rope draws as the laid polyline, and W drives Mrinal 2 on it (untrained on
real terrain / turning ropes: it stands, holds the ratchet, creeps -- honest).
Scene GLBs are gitignored; regenerate with
`python -m app.harness.export_scene --world marble_<name>` after building
episodes. App runs on ports 8775/8776 (`--port 8775`).
