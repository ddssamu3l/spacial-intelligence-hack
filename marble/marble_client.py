"""Minimal Marble World API client for the hackathon limit tests.

Subcommands:
  upload <file> --kind video|image           -> prints media_asset_id
  generate --model M --name N (--video ID | --image ID [--is-pano] | --text "...")
                                             -> prints operation_id, writes ops/<op>.json
  poll <operation_id> [--download DIR]       -> waits until done, prints world summary + cost,
                                                downloads collider mesh / pano / full-res mesh
  credits                                    -> remaining credits
The key is read from WORLD_LABS_API_KEY in the repo .env and never printed.
"""
import argparse, json, mimetypes, os, sys, time, pathlib
import requests

BASE = "https://api.worldlabs.ai/marble/v1"
ENV_PATH = "/Users/dengjingxi/Documents/code/wmfpv/.env"
HERE = pathlib.Path(__file__).resolve().parent


def api_key():
    key = os.environ.get("WORLD_LABS_API_KEY")
    if not key and os.path.exists(ENV_PATH):
        for line in open(ENV_PATH):
            if line.startswith("WORLD_LABS_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        sys.exit("WORLD_LABS_API_KEY not found")
    return key


def headers():
    return {"WLT-Api-Key": api_key(), "Content-Type": "application/json"}


def credits():
    r = requests.get(f"{BASE}/credits", headers=headers(), timeout=30)
    r.raise_for_status()
    return r.json()["remaining_credits"]


def upload(path, kind):
    path = pathlib.Path(path)
    ext = path.suffix.lstrip(".")
    r = requests.post(f"{BASE}/media-assets:prepare_upload", headers=headers(),
                      json={"file_name": path.name[:64], "extension": ext, "kind": kind}, timeout=60)
    r.raise_for_status()
    prep = r.json()
    asset_id = prep["media_asset"]["media_asset_id"]
    info = prep["upload_info"]
    put_headers = dict(info.get("required_headers") or {})
    put_headers.setdefault("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
    with open(path, "rb") as fh:
        up = requests.put(info["upload_url"], data=fh, headers=put_headers, timeout=600)
    up.raise_for_status()
    print(f"uploaded {path.name} ({path.stat().st_size/1e6:.1f} MB) -> media_asset_id {asset_id}")
    return asset_id


def generate(model, name, video=None, image=None, text=None, is_pano=None, seed=None, text_prompt=None):
    if video:
        prompt = {"type": "video", "video_prompt": {"source": "media_asset", "media_asset_id": video}}
        if text_prompt:
            prompt["text_prompt"] = text_prompt
    elif image:
        prompt = {"type": "image", "image_prompt": {"source": "media_asset", "media_asset_id": image}}
        if is_pano is not None:
            prompt["is_pano"] = is_pano
        if text_prompt:
            prompt["text_prompt"] = text_prompt
    elif text:
        prompt = {"type": "text", "text_prompt": text}
    else:
        sys.exit("need --video, --image or --text")
    body = {"model": model, "display_name": name[:64], "world_prompt": prompt}
    if seed is not None:
        body["seed"] = seed
    before = credits()
    r = requests.post(f"{BASE}/worlds:generate", headers=headers(), json=body, timeout=60)
    if r.status_code >= 400:
        print("ERROR", r.status_code, r.text[:500]); sys.exit(1)
    op = r.json()
    (HERE / "ops").mkdir(exist_ok=True)
    record = {"request": body, "operation": op, "credits_before": before, "submitted_at": time.time()}
    (HERE / "ops" / f"{op['operation_id']}.json").write_text(json.dumps(record, indent=1))
    print(f"operation_id {op['operation_id']} done={op.get('done')} credits_before={before}")
    return op["operation_id"]


def poll(operation_id, download=None, interval=20, timeout=3600):
    start = time.time()
    last = None
    while True:
        r = requests.get(f"{BASE}/operations/{operation_id}", headers=headers(), timeout=60)
        r.raise_for_status()
        op = r.json()
        meta = op.get("metadata") or {}
        state = (meta.get("progress"), meta.get("status"), meta.get("stage"))
        if state != last:
            print(f"[{time.time()-start:6.0f}s] done={op['done']} metadata={json.dumps(meta)[:200]}", flush=True)
            last = state
        if op["done"]:
            break
        if time.time() - start > timeout:
            print("TIMEOUT"); return op
        time.sleep(interval)
    (HERE / "ops").mkdir(exist_ok=True)
    (HERE / "ops" / f"{operation_id}.result.json").write_text(json.dumps(op, indent=1))
    if op.get("error"):
        print("ERROR:", json.dumps(op["error"])[:800]); return op
    world = op.get("response") or {}
    cost = op.get("cost") or {}
    print("world_id:", world.get("world_id"), "| name:", world.get("display_name"))
    print("cost:", json.dumps(cost))
    sem = ((world.get("assets") or {}).get("splats") or {}).get("semantics_metadata") or {}
    print("metric_scale_factor:", sem.get("metric_scale_factor"), "| ground_plane_offset:", sem.get("ground_plane_offset"))
    print("caption:", (world.get("assets") or {}).get("caption"))
    print("credits_now:", credits())
    if download:
        outdir = pathlib.Path(download); outdir.mkdir(parents=True, exist_ok=True)
        assets = world.get("assets") or {}
        urls = {}
        mesh = assets.get("mesh") or {}
        for k in ("collider_mesh_url", "full_res_mesh_url", "hq_mesh_url"):
            if mesh.get(k): urls[k] = mesh[k]
        img = assets.get("imagery") or {}
        if img.get("pano_url"): urls["pano_url"] = img["pano_url"]
        spz = (assets.get("splats") or {}).get("spz_urls") or {}
        for k, v in spz.items(): urls[f"spz_{k}"] = v
        if assets.get("thumbnail_url"): urls["thumbnail_url"] = assets["thumbnail_url"]
        for k, url in urls.items():
            ext = pathlib.Path(url.split("?")[0]).suffix or ".bin"
            dst = outdir / f"{k}{ext}"
            with requests.get(url, stream=True, timeout=600) as g:
                g.raise_for_status()
                with open(dst, "wb") as fh:
                    for chunk in g.iter_content(1 << 20): fh.write(chunk)
            print(f"  saved {dst.name} {dst.stat().st_size/1e6:.1f} MB")
        (outdir / "world.json").write_text(json.dumps(world, indent=1))
    return op



def export_world(world_id, asset_type="splats", fmt="ply", resolution="150k", download=None):
    body = {"asset_type": asset_type, "format": fmt, "resolution": resolution}
    r = requests.post(f"{BASE}/worlds/{world_id}:export", headers=headers(), json=body, timeout=60)
    if r.status_code >= 400:
        print("ERROR", r.status_code, r.text[:500]); sys.exit(1)
    op = r.json()
    print("export operation", op.get("operation_id"), "done", op.get("done"))
    op_id = op["operation_id"]
    start = time.time()
    while not op.get("done"):
        time.sleep(10)
        op = requests.get(f"{BASE}/operations/{op_id}", headers=headers(), timeout=60).json()
        print(f"[{time.time()-start:5.0f}s] done={op['done']} meta={json.dumps(op.get('metadata') or {})[:120]}", flush=True)
    if op.get("error"):
        print("ERROR", json.dumps(op["error"])[:500]); return op
    print("cost:", json.dumps(op.get("cost")))
    res = op.get("response") or {}
    url = res.get("url") or res.get("asset_url") or next((v for v in res.values() if isinstance(v, str) and v.startswith("http")), None)
    print("result keys:", list(res.keys()), "url:", (url or "")[:80])
    if download and url:
        dst = pathlib.Path(download); dst.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=1200) as g:
            g.raise_for_status()
            with open(dst, "wb") as fh:
                for chunk in g.iter_content(1 << 20): fh.write(chunk)
        print(f"saved {dst} {dst.stat().st_size/1e6:.1f} MB")
    return op


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "export":
    ap2 = argparse.ArgumentParser(); ap2.add_argument("cmd"); ap2.add_argument("world_id"); ap2.add_argument("--resolution", default="150k"); ap2.add_argument("--download")
    a2 = ap2.parse_args(); export_world(a2.world_id, resolution=a2.resolution, download=a2.download)

    sys.exit(0)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("upload"); u.add_argument("file"); u.add_argument("--kind", default="video")
    g = sub.add_parser("generate"); g.add_argument("--model", default="marble-1.1"); g.add_argument("--name", required=True)
    g.add_argument("--video"); g.add_argument("--image"); g.add_argument("--text"); g.add_argument("--is-pano", dest="is_pano", default=None)
    g.add_argument("--seed", type=int); g.add_argument("--text-prompt", dest="text_prompt")
    p = sub.add_parser("poll"); p.add_argument("operation_id"); p.add_argument("--download")
    sub.add_parser("credits")
    a = ap.parse_args()
    if a.cmd == "credits": print(credits())
    elif a.cmd == "upload": upload(a.file, a.kind)
    elif a.cmd == "generate":
        is_pano = None if a.is_pano is None else (a.is_pano if a.is_pano == "auto" else a.is_pano.lower() == "true")
        generate(a.model, a.name, video=a.video, image=a.image, text=a.text, is_pano=is_pano, seed=a.seed, text_prompt=a.text_prompt)
    elif a.cmd == "poll": poll(a.operation_id, download=a.download)
