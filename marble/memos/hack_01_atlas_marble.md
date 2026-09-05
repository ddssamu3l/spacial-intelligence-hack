# Hackathon memo A: Atlas access + Marble house-scale routes (2026-09-03)
- Atlas: WL X post 2026-09-01 "opening up early access in the coming weeks"; no named partner anywhere; no atlas in openapi (models: marble-1.0-draft|1.0|1.1|1.1-plus); no Atlas feature in app (release notes newest 2026-04-02). Plan for zero Atlas. Form = typeform waitlist.
- Compose: Studio-only, manual XYZ/rot/scale placement, seams by eye; budget 500k/2M splats; export button exists, formats unstated; no API endpoint; worlds:list has no composed flag/bounds.
- Expand: extends boundaries one direction at a time, no vertical, CANNOT expand marble-1.1-plus worlds; not in API.
- marble-1.1-plus: "dynamic world sizing", 1500 + 0-1500 credits; no extent numbers published.
- multi-image reconstruct_images=true: 8 images auto-layout / 4 with azimuth; buys fidelity not size.
- video prompts: <=100 MB; no claim of multi-room.
- Chisel: Studio tool with wall/room blocking, GLB/FBX upload, pano camera; API = pano:depth_to_rgb; openapi also has prompt types depth-pano and inpaint-pano on worlds:generate (absent from docs page). Adherence/cost undocumented. "Meshes can now be imported into Composer" (2026-01-29).
- Extent in metres: never published. NVIDIA hand-scaled a kitchen 2x. Collider: 100-200k tri, artifacts in thin structures/doorways/holes/blobby. Robotics case studies (OmniGibson, RoboSuite) used collider GLB, no metric validation.
- Hackathon: reader found "World Labs Hack [01]" luma page (hosts Ian Curtis + Ben Mildenhall, Fei-Fei Li present; prizes cash + Marble credits) — DIFFERENT prize list from the user's Founders Inc page; may be a separate event or the same one re-listed. Judging rubrics unverified. Precedent: working demos with a legible story win.
