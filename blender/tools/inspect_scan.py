import bpy
from pathlib import Path
root=Path(__file__).resolve().parents[1]
for name in ['rock_05','rock_09']:
 before=set(bpy.data.objects)
 bpy.ops.import_scene.gltf(filepath=str(root/'assets/models'/name/(name+'.gltf')))
 for ob in set(bpy.data.objects)-before:
  print(name,ob.name,ob.type,tuple(ob.dimensions),len(ob.data.vertices) if ob.type=='MESH' else '')
  ob['scan_source']=name
  if ob.type=='MESH':
   print('mats',[(m.name,[(n.type,n.image.name if n.type=='TEX_IMAGE' else '') for n in m.node_tree.nodes]) for m in ob.data.materials])
