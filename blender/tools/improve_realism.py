import bpy, math, random, json
from pathlib import Path
from mathutils import Vector,noise
ROOT=Path(__file__).resolve().parents[1];scene=bpy.data.scenes['EVEREST | East Rongbuk — visual study'];bpy.context.window.scene=scene
random.seed(906)
col=bpy.data.collections.get('07 • base camp trail details')
if col is None:col=bpy.data.collections.new('07 • base camp trail details');scene.collection.children.link(col)
terrain=bpy.data.objects['Foreground | metre-scale moraine & wind-sculpted snow']
def ground(x,y):
 hit,p,n,i=terrain.ray_cast(Vector((x,y,200)),Vector((0,0,-1)));return p.z if hit else 0

def mesh(name,vs,fs,mat,smooth=True):
 me=bpy.data.meshes.new(name);me.from_pydata(vs,[],fs);me.update();me.materials.append(mat)
 for p in me.polygons:p.use_smooth=smooth
 ob=bpy.data.objects.new(name,me);col.objects.link(ob);return ob

def material(name,color,rough=.8):
 m=bpy.data.materials.get(name) or bpy.data.materials.new(name);m.use_nodes=True;n=m.node_tree.nodes;l=m.node_tree.links;bs=n.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Roughness'].default_value=rough
 tex=n.new('ShaderNodeTexNoise');tex.inputs['Scale'].default_value=145;tex.inputs['Detail'].default_value=2
 bump=n.new('ShaderNodeBump');bump.inputs['Distance'].default_value=.0015;bump.inputs['Strength'].default_value=.25;l.new(tex.outputs['Fac'],bump.inputs['Height']);l.new(bump.outputs[0],bs.inputs['Normal'])
 return m

yellow=material('FABRIC • sunlit expedition yellow',(.84,.35,.023));orange=material('FABRIC • expedition orange',(.72,.105,.014));dark=material('FABRIC • charcoal nylon',(.016,.024,.031));blue=material('FABRIC • faded blue',(.017,.115,.24));cord=material('CORD • braided guy lines',(.49,.43,.24));pole=material('METAL • tent poles',(.21,.24,.25),.3)
def curve(name,points,radius,mat):
 c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.bevel_depth=radius;c.bevel_resolution=2;sp=c.splines.new('POLY');sp.points.add(len(points)-1)
 for p,co in zip(sp.points,points):p.co=(*co,1)
 ob=bpy.data.objects.new(name,c);col.objects.link(ob);c.materials.append(mat);return ob

# Keep the existing terrain but uncover more moraine near the camp entrance.
for ob in bpy.data.collections['02 • detailed moraine & snow'].objects:
 attr=ob.data.attributes.get('SnowMask')
 if not attr:continue
 for v,a in zip(ob.data.vertices,attr.data):
  x,y,z=v.co;near=max(0,min(1,(45-y)/75));pocket=noise.noise(Vector((x*.23,y*.23,7)))
  a.value=max(0,min(1,(a.value-.46*near-.18+pocket*.16)*1.25))
# Remove sheet-like snow caps; the scanned rock geometry carries the close-up detail.
for ob in bpy.data.collections['04 • stones & boulders'].objects:
 if ob.name.startswith('Windward snow cap'):ob.hide_render=True;ob.hide_set(True)
scans=[]
for name in ['rock_05','rock_09']:
 ob=next(o for o in bpy.data.objects if o.get('scan_source')==name)
 for c in list(ob.users_collection):c.objects.unlink(ob)
 bpy.data.collections['04 • stones & boulders'].objects.link(ob)
 if name=='rock_05':
  bpy.context.view_layer.objects.active=ob;ob.select_set(True);mod=ob.modifiers.new('Scan detail optimized for live walking','DECIMATE');mod.ratio=.28;bpy.ops.object.modifier_apply(modifier=mod.name);ob.select_set(False)
 coords=[ob.matrix_world@v.co for v in ob.data.vertices]
 lo=Vector(tuple(min(v[i] for v in coords) for i in range(3)));hi=Vector(tuple(max(v[i] for v in coords) for i in range(3)));center=(lo+hi)*.5;span=max(hi.x-lo.x,hi.y-lo.y)
 for v,co in zip(ob.data.vertices,coords):v.co=(co-Vector((center.x,center.y,lo.z)))*(2/span)
 ob.matrix_world.identity();ob.data.update();ob.data.name='SCAN '+name+' normalized geometry'
 for m in ob.data.materials:m.name='SCAN • '+name
 ob.hide_render=True;ob.hide_set(True);scans.append(ob.data)
# Replace existing prominent rocks in place, leaving their layout intact.
count=0
for ob in list(bpy.data.collections['04 • stones & boulders'].objects):
 if not ob.name.startswith(('Hero boulder','Moraine fragment')):continue
 if ob.name.startswith('Moraine') and (max(ob.dimensions)<.65 or random.random()>.52):continue
 size=max(ob.dimensions.x,ob.dimensions.y)*.5;x,y=ob.location.x,ob.location.y
 ob.data=random.choice(scans);ob.modifiers.clear();ob.scale=(size*random.uniform(.9,1.1),size*random.uniform(.85,1.15),size*random.uniform(.8,1.1));ob.rotation_euler=(0,0,random.random()*math.tau);ob.location.z=ground(x,y)-.035;count+=1
print('Replaced',count,'rocks with photographed scans')
# Dense fragmented scree, concentrated on the moraine shoulders instead of an even grid.
for i in range(90):
 y=random.uniform(-19,80);side=random.choice([-1,1]);x=side*random.uniform(3.2,25)
 if abs(x-(2.2*math.sin(y*.048)+.024*y))<2:continue
 ob=bpy.data.objects.new('Scanned angular moraine stone',scans[1]);bpy.data.collections['04 • stones & boulders'].objects.link(ob);s=random.uniform(.12,.40);ob.scale=(s,s*random.uniform(.7,1.1),s);ob.rotation_euler.z=random.random()*math.tau;ob.location=(x,y,ground(x,y)-.01)
# Keep the glacier, with uneven silhouettes and fractures farther along the approach.
for ob in bpy.data.collections['03 • fractured glacier ice'].objects:
 if ob.name.startswith('Serac'):
  ob.location.y+=34
  for v in ob.data.vertices:
   v.co.x+=.45*noise.noise(Vector((v.co.y*.35,v.co.z*.19,3)))
   v.co.z+=.25*noise.noise(Vector((v.co.x*.4,v.co.z*.6,2)))
  for mod in ob.modifiers:
   if mod.type=='DISPLACE':mod.strength=.42

def tent(x,y,rx,ry,h,mat,index):
 z=ground(x,y)-.02;vs=[];fs=[];ns=64;nr=25
 for j in range(nr):
  t=(j/(nr-1))*(math.pi/2-.001)
  for i in range(ns):
   a=i*math.tau/ns;rip=.012*math.sin(a*21+t*32)+.006*math.sin(a*43-t*57)
   vs.append((x+rx*math.cos(t)*math.cos(a)*(1+rip),y+ry*math.cos(t)*math.sin(a)*(1+rip),z+h*math.sin(t)))
 for j in range(nr-1):
  for i in range(ns):a=j*ns+i;b=j*ns+(i+1)%ns;fs.append((a,b,b+ns,a+ns))
 ob=mesh(f'Expedition dome tent {index}',vs,fs,mat);ob.data.materials.append(dark)
 for p in ob.data.polygons:
  a=math.atan2((p.center.y-y)/ry,(p.center.x-x)/rx)
  if p.center.z<z+.09 or (-1.98<a<-1.17 and p.center.z<z+h*.72):p.material_index=1
 for a in [math.pi/4,math.pi*3/4]:
  pts=[]
  for k in range(65):
   t=k*math.pi/64;pts.append((x+rx*math.cos(t)*math.cos(a)*1.005,y+ry*math.cos(t)*math.sin(a)*1.005,z+h*math.sin(t)+.025))
  curve('Flexible crossed tent pole',pts,.012,pole)
 for a in [0,.5*math.pi,math.pi,1.5*math.pi]:
  anchor=(x+rx*1.65*math.cos(a),y+ry*1.65*math.sin(a));az=ground(*anchor)
  curve('Tensioned guy rope',[(x+rx*.82*math.cos(a),y+ry*.82*math.sin(a),z+h*.57),(anchor[0],anchor[1],az+.08)],.007,cord)
  curve('Aluminium tent stake',[(anchor[0],anchor[1],az),(anchor[0]+.05,anchor[1],az+.18)],.013,pole)
for i,spec in enumerate([(-7,2,2.0,2.1,1.5,yellow),(-13,11,1.9,2.2,1.65,orange),(10,-5,2.1,2.2,1.55,yellow),(-20,26,2.5,3,1.85,yellow),(14,20,1.75,2.1,1.45,blue)]):tent(*spec,i)
# A low line of weathered colored flags marks the camp edge.
flags=[blue,dark,orange,yellow,material('FABRIC • weathered green',(.045,.20,.10))]
start=Vector((-15,-4,ground(-15,-4)+2.9));end=Vector((-5,11,ground(-5,11)+2.6))
curve('Camp boundary cord',[start.lerp(end,t/40)+Vector((0,0,-.55*math.sin(t/40*math.pi))) for t in range(41)],.009,cord)
for endpoint in [start,end]:curve('Camp flag pole',[(endpoint.x,endpoint.y,ground(endpoint.x,endpoint.y)),endpoint],.023,pole)
for i in range(22):
 t=(i+.4)/22;p=start.lerp(end,t)+Vector((0,0,-.55*math.sin(t*math.pi)));vs=[];fs=[]
 for j in range(7):
  for k in range(9):u=k/8;v=j/6;vs.append(tuple(p+Vector((u*.38,v*.11*math.sin(u*8+i),-.43*v))))
 for j in range(6):
  for k in range(8):a=j*9+k;fs.append((a,a+1,a+10,a+9))
 mesh('Weathered camp pennant',vs,fs,flags[i%5])
# Real HDR sky illumination replaces the featureless blue environment.
w=scene.world;n=w.node_tree.nodes;l=w.node_tree.links;n.clear();out=n.new('ShaderNodeOutputWorld');env=n.new('ShaderNodeTexEnvironment');env.image=bpy.data.images.load(str(ROOT/'assets/lighting/alpine-daylight.hdr'),check_existing=True);bg=n.new('ShaderNodeBackground');bg.inputs['Strength'].default_value=.45;l.new(env.outputs[0],bg.inputs[0]);l.new(bg.outputs[0],out.inputs[0])
sun=bpy.data.objects['Sun • grazing across ice faces'];sun.rotation_euler=Vector((.75,.3,-.50)).to_track_quat('-Z','Y').to_euler();sun.data.energy=4.0;sun.data.color=(1,.87,.69);sun.data.angle=math.radians(.75)
scene.view_settings.exposure=.05
scene['description']='Existing Everest terrain enhanced with photographed rock scans, reconstructed base-camp trail details, and HDR daylight. Camp placement and compressed approach are illustrative, not surveyed base-camp geography.'
scene['realism_revision']='2 • scanned stone / camp trail / HDR daylight'
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'outputs/everest-rongbuk-study.blend'))
print('Saved realism revision. Visible camp assets:',len(col.objects))
