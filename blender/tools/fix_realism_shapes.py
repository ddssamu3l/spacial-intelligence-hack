import bpy,random,math
from pathlib import Path
from mathutils import Vector,noise
ROOT=Path(__file__).resolve().parents[1];scene=bpy.data.scenes['EVEREST | East Rongbuk — visual study'];bpy.context.window.scene=scene
random.seed(923)
terrain=bpy.data.objects['Foreground | metre-scale moraine & wind-sculpted snow']
def ground(x,y):
 hit,p,n,i=terrain.ray_cast(Vector((x,y,200)),Vector((0,0,-1)));return p.z if hit else 0
before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(ROOT/'assets/models/rock_07/rock_07.gltf'))
ob=next(o for o in set(bpy.data.objects)-before if o.type=='MESH');coords=[ob.matrix_world@v.co for v in ob.data.vertices]
lo=Vector(tuple(min(v[i] for v in coords) for i in range(3)));hi=Vector(tuple(max(v[i] for v in coords) for i in range(3)));center=(lo+hi)*.5;span=max(hi.x-lo.x,hi.y-lo.y)
for v,co in zip(ob.data.vertices,coords):v.co=(co-Vector((center.x,center.y,lo.z)))*(2/span)
ob.matrix_world.identity();ob.data.update();ob.data.name='SCAN rock_07 normalized geometry'
for m in ob.data.materials:m.name='SCAN • rock_07'
ob.hide_render=True;ob.hide_set(True);ob['scan_source']='rock_07'
for c in list(ob.users_collection):c.objects.unlink(ob)
bpy.data.collections['04 • stones & boulders'].objects.link(ob)
for rock in list(bpy.data.collections['04 • stones & boulders'].objects):
 if rock.hide_render:continue
 if rock.data.name.startswith('SCAN rock_05'):
  rock.data=ob.data;rock.scale.z*=.7;rock.location.z=ground(rock.location.x,rock.location.y)-.10
# Compact snow into irregular patches rather than a smooth mixed blanket.
for groundob in bpy.data.collections['02 • detailed moraine & snow'].objects:
 attr=groundob.data.attributes.get('SnowMask')
 if not attr:continue
 for v,a in zip(groundob.data.vertices,attr.data):
  threshold=.54 if v.co.y<35 else .35;t=max(0,min(1,(a.value-threshold)/.3));a.value=t*t*(3-2*t)
# Neutral limestone coloration and real coarse scree scale.
for name in ['ROCK • fractured Himalayan limestone / photographed 4K','MORAINE • snow pockets over shattered rock / 4K']:
 m=bpy.data.materials[name]
 for n in m.node_tree.nodes:
  if n.type=='HUE_SAT':n.inputs['Saturation'].default_value=.3;n.inputs['Value'].default_value=.65
  if n.type=='VECT_MATH' and n.operation=='SCALE' and .2<n.inputs['Scale'].default_value<.3:n.inputs['Scale'].default_value=.65
# The large-scale measured slopes gain reconstructed sub-grid crag relief.
back=bpy.data.objects['Everest massif | Copernicus measured 30m elevations']
for v in back.data.vertices:
 x,y,z=v.co
 if y>500 or abs(x)>500:
  n=noise.fractal(Vector((x*.011,y*.011,z*.022)),1.,2.,4)
  v.co.z+=n*12
back.data.update()
# Match dark rock and bright snow seen in the north-side photographs.
m=bpy.data.materials['MOUNTAIN • sedimentary bands, snow gullies & exposed ridges']
n=m.node_tree.nodes;n['Color Ramp'].color_ramp.elements[0].color=(.014,.018,.022,1);n['Color Ramp'].color_ramp.elements[1].color=(.075,.073,.070,1)
n['Bump'].inputs['Distance'].default_value=2.5
# Bring out creases in tent fabric and put stronger directional light across camp.
for m in bpy.data.materials:
 if m.name.startswith('FABRIC'):
  for n in m.node_tree.nodes:
   if n.type=='BUMP':n.inputs['Distance'].default_value=.004
scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.18
sun=bpy.data.objects['Sun • grazing across ice faces'];sun.data.color=(1,.93,.83);sun.data.energy=4.3
scene.view_settings.exposure=-.05
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'outputs/everest-rongbuk-study.blend'))
print('Replaced round material previews with actual scanned rock geometry; improved snow breakup and daylight')
