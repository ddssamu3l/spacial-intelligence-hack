import json,subprocess,concurrent.futures
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];tasks=[]
for name in ['rock_05','rock_09']:
 f=(ROOT/'assets/source-manifests'/('everest-'+name.replace('_','')+'.json'));d=json.loads(f.read_text());out=ROOT/'assets/models'/name;out.mkdir(parents=True,exist_ok=True)
 entry=d['gltf']['4k']['gltf'];tasks.append((entry['url'],out/(name+'.gltf')))
 for rel,info in entry['include'].items():tasks.append((info['url'],out/rel))
 (out/'source.json').write_text(json.dumps({'url':'https://polyhaven.com/a/'+name,'license':'CC0'},indent=2))
def fetch(task):
 url,path=task;path.parent.mkdir(parents=True,exist_ok=True)
 if not path.exists():subprocess.run(['curl','-fsSL','--retry','2',url,'-o',str(path)],check=True)
 return path.name,path.stat().st_size
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
 for result in ex.map(fetch,tasks):print(result,flush=True)
