import bpy, json, struct, math
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'browser-scene/public/scene';OUT.mkdir(parents=True,exist_ok=True)
scene=bpy.data.scenes['EVEREST | East Rongbuk — visual study'];bpy.context.window.scene=scene
deps=bpy.context.evaluated_depsgraph_get()
camera=scene.camera
forward=camera.matrix_world.to_quaternion()@__import__('mathutils').Vector((0,0,-1))
aspect=(scene.render.resolution_x*scene.render.pixel_aspect_x)/(scene.render.resolution_y*scene.render.pixel_aspect_y)
manifest={'meshes':[],'groups':[],'lights':[],'spawn':list(camera.location),'camera':{'fov':2*math.atan(math.tan(camera.data.angle_x/2)/aspect),'direction':list(forward)},'coordinateSystem':'Blender Z up','sources':'../README.md'}
blob=bytearray();cache={}
def array(a,dtype):
    a=np.asarray(a,dtype=dtype).reshape(-1)
    while len(blob)%4:blob.append(0)
    offset=len(blob);blob.extend(a.tobytes())
    return {'offset':offset,'count':int(a.size)}
for col in scene.collection.children:
    if col.name.startswith('06'):continue
    for ob in col.objects:
        if ob.type not in {'MESH','CURVE'} or ob.hide_render:continue
        key=(ob.data.name,tuple((m.type,getattr(m,'levels',0),getattr(m,'strength',0)) for m in ob.modifiers))
        if key not in cache:
            ev=ob.evaluated_get(deps);me=ev.to_mesh();me.calc_loop_triangles()
            vs=np.empty(len(me.vertices)*3,np.float32);me.vertices.foreach_get('co',vs)
            ns=np.empty(len(me.vertices)*3,np.float32);me.vertices.foreach_get('normal',ns)
            ix=np.empty(len(me.loop_triangles)*3,np.uint32);me.loop_triangles.foreach_get('vertices',ix)
            attrs={'position':array(vs,'<f4'),'normal':array(ns,'<f4'),'index':array(ix,'<u4')}
            if 'SnowMask' in me.attributes:
                a=np.empty(len(me.vertices),np.float32);me.attributes['SnowMask'].data.foreach_get('value',a);attrs['snow']=array(a,'<f4')
            if 'MountainShade' in me.attributes:
                a=np.empty(len(me.vertices),np.float32);me.attributes['MountainShade'].data.foreach_get('value',a);attrs['mountainShade']=array(a,'<f4')
            mats=[m.name for m in me.materials if m]
            if mats and mats[0].startswith('SCAN') and me.uv_layers:
                # Expand corners so the scan's UV seams remain intact.
                loops=np.empty(len(me.loop_triangles)*3,np.uint32);me.loop_triangles.foreach_get('loops',loops)
                uv=np.empty(len(me.loops)*2,np.float32);me.uv_layers.active.data.foreach_get('uv',uv)
                attrs['position']=array(vs.reshape(-1,3)[ix],'<f4')
                attrs['normal']=array(ns.reshape(-1,3)[ix],'<f4')
                attrs['uv']=array(uv.reshape(-1,2)[loops],'<f4')
                attrs['index']=array(np.arange(len(ix),dtype=np.uint32),'<u4')
            entry={'name':ob.name,'attributes':attrs,'material':mats[0] if mats else 'rock'}
            if me.materials and len(me.materials)>1:
                # Preserve per-face ground/mountain material choices.
                idx=np.array(ix).reshape(-1,3);mi=np.empty(len(me.loop_triangles),np.int32);me.loop_triangles.foreach_get('material_index',mi)
                entry['parts']=[{'material':mats[i],'index':array(idx[mi==i],'<u4')} for i in sorted(set(mi.tolist()))]
            mid=len(manifest['meshes']);manifest['meshes'].append(entry);cache[key]=mid
            manifest['groups'].append({'mesh':mid,'transforms':[],'names':[]})
            ev.to_mesh_clear()
        group=manifest['groups'][cache[key]]
        group['transforms'].append([float(ob.matrix_world[row][column]) for column in range(4) for row in range(4)])
        group['names'].append(ob.name)
ground_object=bpy.data.objects['Foreground | metre-scale moraine & wind-sculpted snow']
fg=ground_object.data
h=np.array([v.co.z for v in fg.vertices],dtype='<f4')
manifest['ground']={**json.loads(ground_object.get('walk_grid','{"nx":361,"ny":401,"xmin":-90,"ymin":-45,"step":0.5}')),'heights':array(h,'<f4')}
if 'walk_bounds' in ground_object:
    manifest['ground']['bounds']=json.loads(ground_object['walk_bounds'])
if 'trail_route' in scene:
    manifest['route']=json.loads(scene['trail_route'])
# Conservative cylinder proxies keep the walker outside major boulders and ice.
obstacles=[]
for colname in ['03 • fractured glacier ice','04 • stones & boulders','07 • base camp trail details']:
    collection=bpy.data.collections.get(colname)
    if collection is None:continue
    for ob in collection.objects:
        if ob.hide_render or 'snow cap' in ob.name or 'scree' in ob.name:continue
        corners=[ob.matrix_world@__import__('mathutils').Vector(c) for c in ob.bound_box]
        lo=np.min(np.array([list(c) for c in corners]),axis=0);hi=np.max(np.array([list(c) for c in corners]),axis=0)
        if hi[2]-lo[2]<.55:continue
        obstacles.append({'x':float((lo[0]+hi[0])/2),'y':float((lo[1]+hi[1])/2),'radius':float(min(hi[0]-lo[0],hi[1]-lo[1])*.40),'bottom':float(lo[2]),'top':float(hi[2])})
manifest['obstacles']=obstacles
manifest['materials']={}
for material in bpy.data.materials:
    bs=next((n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None) if material.use_nodes else None
    if bs:
        manifest['materials'][material.name]={'color':list(bs.inputs['Base Color'].default_value)[:3],'roughness':float(bs.inputs['Roughness'].default_value),'metalness':float(bs.inputs['Metallic'].default_value)}
manifest['revision']=scene.get('realism_revision','1')
(OUT/'geometry.bin').write_bytes(blob)
(OUT/'scene.json').write_text(json.dumps(manifest,separators=(',',':')))
print(json.dumps({'bytes':len(blob),'unique_meshes':len(cache),'objects':sum(len(g['transforms']) for g in manifest['groups']),'obstacles':len(obstacles)}))
