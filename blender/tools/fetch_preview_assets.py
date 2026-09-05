"""Download CC0 material maps from their published Poly Haven asset manifests."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
dest = root / "assets" / "textures"
dest.mkdir(parents=True, exist_ok=True)
jobs = []
manifest = {}
for asset in ["snow_02", "rock_boulder_cracked", "aerial_rocks_02"]:
    source = json.loads((root / "assets/source-manifests" / f"everest-poly-{asset}.json").read_text())
    manifest[asset] = {"source": f"https://polyhaven.com/a/{asset}", "license": "CC0", "maps": {}}
    for channel in ["diff", "rough", "nor_gl"]:
        spec = source[{"diff": "Diffuse", "rough": "Rough", "nor_gl": "nor_gl"}[channel]]["4k"]["jpg"]
        path = dest / f"{asset}_{channel}_4k.jpg"
        manifest[asset]["maps"][channel] = str(path.relative_to(root))
        jobs.append((spec["url"], path))


def fetch(job):
    url, path = job
    if not path.exists():
        subprocess.run(["curl", "--max-time", "120", "--retry", "2", "-fsSL", url, "-o", str(path)], check=True)
    print(path.name, path.stat().st_size, flush=True)


with ThreadPoolExecutor(max_workers=4) as pool:
    list(pool.map(fetch, jobs))
(root / "assets" / "material-sources.json").write_text(json.dumps(manifest, indent=2))
