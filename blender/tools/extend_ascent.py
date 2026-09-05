"""Extend the restored original scene through Blender MCP, once per source file."""
import bpy
import bmesh
import math
import json
import random
import numpy as np
from pathlib import Path
from mathutils import Vector, noise

ROOT = Path(__file__).resolve().parents[1]
scene = next(s for s in bpy.data.scenes if s.name.startswith('EVEREST |'))
bpy.context.window.scene = scene
if scene.get('continuous_ascent'):
    raise RuntimeError('Ascent already applied. Reopen the original study before rebuilding.')
ground = bpy.data.objects['Foreground | metre-scale moraine & wind-sculpted snow']
transition = bpy.data.objects['Transition into surveyed landscape']
original_ground = np.array([v.co[:] for v in ground.data.vertices]).reshape(401, 361, 3)
original_mask = np.array([a.value for a in ground.data.attributes['SnowMask'].data]).reshape(401, 361)
massif_source=bpy.data.objects['Everest massif | Copernicus measured 30m elevations']
terrain_shape=np.load(ROOT/'assets/terrain/everest_backdrop.npz')['elevation'].shape
measured=np.array([v.co[:] for v in massif_source.data.vertices]).reshape(*terrain_shape,3)
basis=np.column_stack((measured[0,1,:2]-measured[0,0,:2],measured[1,0,:2]-measured[0,0,:2]))
inverse=np.linalg.inv(basis)
def measured_height(x,y):
    u,v=inverse@(np.array([x,y])-measured[0,0,:2])
    return sample(measured[:,:,2],float(u),float(v),0,0,1)

original_transition = np.array([v.co[:] for v in transition.data.vertices]).reshape(141, 141, 3)
rng = random.Random(82026)

def smooth(a, b, t):
    u = max(0., min(1., (t-a)/(b-a)))
    return u*u*(3-2*u)

def sample(values, x, y, xmin, ymin, step):
    ny, nx = values.shape
    u = max(0., min(nx-1.00001, (x-xmin)/step))
    v = max(0., min(ny-1.00001, (y-ymin)/step))
    i, j = int(u), int(v)
    a, b = u-i, v-j
    return float((values[j,i]*(1-a)+values[j,i+1]*a)*(1-b)+(values[j+1,i]*(1-a)+values[j+1,i+1]*a)*b)

def baseline(x, y):
    if -90 <= x <= 90 and -45 <= y <= 155:
        return sample(original_ground[:,:,2], x, y, -90, -45, .5)
    if -350<=x<=350 and -250<=y<=450:
        return sample(original_transition[:,:,2], x, y, -350, -250, 5)
    return measured_height(x,y)

def fb(x, y, scale):
    return noise.fractal(Vector((x*scale, y*scale, 2.714)), 1., 2., 4)

def route_x(y):
    old = 2.2*math.sin(y*.048)+.024*y
    if y <= 80:
        return old
    lower=old*(1-smooth(80,110,y))+(4+15*math.sin((y-90)*.034))*smooth(80,110,y)
    upper=-45+12*math.sin((y-355)*.023)
    return lower*(1-smooth(330,470,y))+upper*smooth(330,470,y)

def route_z(y):
    # Broad slope changes leave gentle resting shelves between steeper pitches.
    lower=1.8+.025*(min(y,355)-75)+7*smooth(42,120,y)+16*smooth(120,200,y)+19*smooth(200,280,y)+17*smooth(280,355,y)
    if y<=355:return lower
    ramp=lower+.18*(y-355)
    weight=smooth(540,715,y)
    return ramp*(1-weight)+(measured_height(route_x(y),y)+.2)*weight

def sculpted(x, y):
    d = abs(x-route_x(y))
    shoulder = smooth(1.45, 6, d)
    talus = .17*min(d, 45) + 7*math.exp(-((x+39)/18)**2-((y-203)/70)**2)
    ridge = 10*math.exp(-((x-46)/20)**2-((y-280)/80)**2)
    drift = .58*fb(x,y,.095)+.30*fb(x,y,.31)+.075*fb(x,y,1.5)
    track = -.11*math.exp(-(d/1.25)**4)+.035*fb(x,y,.7)
    return route_z(y)+shoulder*(talus+ridge+drift)+track

def height(x, y):
    old = baseline(x,y)
    weight = smooth(35,70,y)*(1-smooth(90,290,abs(x)))*(1-smooth(715,850,y))
    return old*(1-weight)+sculpted(x,y)*weight

def cover(x,y):
    d = abs(x-route_x(y))
    packed = math.exp(-(d/(1.05+.13*math.sin(y*.13)))**6)
    fresh = max(.65,min(1., .94+.30*fb(x,y,.16)+.1*fb(x,y,1.6)))
    new = fresh*(1-.84*packed)+.035*fb(x,y,.9)
    if y <= 155 and abs(x)<=90:
        old = sample(original_mask,x,y,-90,-45,.5)
        return old*(1-smooth(35,70,y))+new*smooth(35,70,y)
    return max(.06,min(1.,new))

def replace_grid(ob, xmin, xmax, ymin, ymax, step, skip=False):
    nx, ny = round((xmax-xmin)/step)+1, round((ymax-ymin)/step)+1
    verts, masks, faces = [], [], []
    for j in range(ny):
        y=ymin+j*step
        for i in range(nx):
            x=xmin+i*step
            verts.append((x,y,height(x,y))); masks.append(cover(x,y))
    for j in range(ny-1):
        for i in range(nx-1):
            x,y=xmin+i*step,ymin+j*step
            if skip and -90<=x<90 and -45<=y<715:
                continue
            a=j*nx+i
            faces.append((a,a+1,a+nx+1,a+nx))
    mesh=bpy.data.meshes.new(ob.name+' — continuous ascent')
    mesh.from_pydata(verts,[],faces)
    for material in ob.data.materials: mesh.materials.append(material)
    mesh.attributes.new('SnowMask','FLOAT','POINT').data.foreach_set('value',masks)
    mesh.update()
    for polygon in mesh.polygons:
        polygon.use_smooth=True
        if skip and polygon.center.length>290: polygon.material_index=1
    ob.data=mesh
    return nx,ny

nx,ny=replace_grid(ground,-90,90,-45,715,.5)
replace_grid(transition,-350,350,-250,850,5,True)
ground['walk_grid']=json.dumps({'nx':nx,'ny':ny,'xmin':-90,'ymin':-45,'step':.5})
ground['walk_bounds']=json.dumps({'xmin':-70,'xmax':70,'ymin':-24,'ymax':705})
print('Continuous ground built', nx, ny, flush=True)

# Lift the original dressing with its substrate; world-space ice keeps its shape.
for colname in ['03 • fractured glacier ice','04 • stones & boulders']:
    for ob in bpy.data.collections[colname].objects:
        if ob.location.length>.001:
            x,y=ob.location.x,ob.location.y
            ob.location.z+=height(x,y)-baseline(x,y)
        elif ob.type=='MESH':
            for v in ob.data.vertices:
                x,y=v.co.x,v.co.y
                if y>35: v.co.z+=height(x,y)-baseline(x,y)
            ob.data.update()
massif=bpy.data.objects['Everest massif | Copernicus measured 30m elevations']
for v in massif.data.vertices:
    x,y=v.co.x,v.co.y
    if -340<x<340 and 35<y<845:
        v.co.z=min(v.co.z,height(x,y)-5)
massif.data.update()

rock_col=bpy.data.collections['04 • stones & boulders']
ice_col=bpy.data.collections['03 • fractured glacier ice']
detail_col=bpy.data.collections['05 • expedition trail details']
rocks=sorted([m for m in bpy.data.meshes if m.name.startswith('Fractured rock prototype')],key=lambda m:m.name)
caps=sorted([m for m in bpy.data.meshes if m.name.startswith('Snow mantle')],key=lambda m:m.name)
def rock(x,y,size,cap=True):
    i=rng.randrange(len(rocks))
    ob=bpy.data.objects.new('Ascent • limestone boulder' if size>.7 else 'Ascent • moraine fragment',rocks[i])
    rock_col.objects.link(ob)
    ob.location=(x,y,height(x,y)+size*.17)
    ob.scale=(size*rng.uniform(.8,1.3),size*rng.uniform(.8,1.2),size*rng.uniform(.65,1.))
    ob.rotation_euler=(rng.uniform(-.18,.18),rng.uniform(-.18,.18),rng.random()*math.tau)
    if cap:
        top=bpy.data.objects.new('Ascent • windward snow cap',caps[i]);rock_col.objects.link(top)
        top.location=ob.location;top.scale=ob.scale;top.rotation_euler=ob.rotation_euler
    return ob

for k in range(4000):
    y=rng.uniform(95,715); x=route_x(y)+rng.uniform(-65,65)
    if abs(x)>86 or abs(x-route_x(y))<2.4: continue
    size=rng.uniform(.09,.3) if k<2800 else rng.uniform(.3,.9)
    rock(x,y,size,cap=size>.28 and rng.random()<.75)
for y,side in [(113,-1),(133,1),(163,-1),(181,1),(207,-1),(224,1),(253,-1),(278,1),(307,-1),(334,1),(380,-1),(430,1),(485,-1),(540,1),(592,-1),(645,1),(687,-1)]:
    rock(route_x(y)+side*rng.uniform(4.8,7),y,rng.uniform(1.4,2.6))
    for _ in range(8):
        yy=y+rng.uniform(-4,4);rock(route_x(yy)+side*rng.uniform(3.5,11),yy,rng.uniform(.25,.9))

# Reuse the original wind-eroded ice silhouettes, with varied proportions.
ice_sources=[o for o in ice_col.objects if o.name.startswith('Serac')]
for i,(y,side) in enumerate([(164,-1),(186,1),(212,-1),(239,1),(273,-1),(309,1),(347,-1),(420,1),(495,-1),(580,1),(668,-1)]):
    source=ice_sources[i%len(ice_sources)]
    ob=source.copy();ob.data=source.data.copy();ob.name=f'Ascent ice shoulder {i+1:02}'
    ice_col.objects.link(ob)
    vertices=ob.data.vertices
    cx=sum(v.co.x for v in vertices)/len(vertices);cy=sum(v.co.y for v in vertices)/len(vertices)
    low=min(v.co.z for v in vertices)
    x=route_x(y)+side*rng.uniform(17,29)
    sx,sy,sz=rng.uniform(.75,1.15),rng.uniform(.8,1.3),rng.uniform(.55,.85)
    for v in vertices:
        xx,yy=x+(v.co.x-cx)*sx,y+(v.co.y-cy)*sy
        rise=(v.co.z-low)*sz
        foot=(height(xx,yy)-height(x,y))*math.exp(-(rise/7)**2)
        v.co=(xx,yy,height(x,y)-2.3+rise+foot)
    ob.data.update()

# A narrow scatter of angular gravel makes the packed route legible at eye level.
bm=bmesh.new();bmesh.ops.create_icosphere(bm,subdivisions=1,radius=1)
proto=bpy.data.meshes.new('Ascent gravel prototype');bm.to_mesh(proto);bm.free()
verts,faces=[],[]
for i in range(12000):
    y=rng.uniform(55,715);x=route_x(y)+rng.gauss(0,1.8)
    radius=rng.uniform(.025,.105);angle=rng.random()*math.tau
    co,si=math.cos(angle),math.sin(angle);z=height(x,y)+radius*.2
    start=len(verts)
    for v in proto.vertices:
        a,b,c=v.co
        verts.append((x+(a*co-b*si)*radius,y+(a*si+b*co)*radius,z+c*radius*.35))
    faces.extend(tuple(start+i for i in p.vertices) for p in proto.polygons)
mesh=bpy.data.meshes.new('Ascent angular trail grit');mesh.from_pydata(verts,[],faces)
mesh.materials.append(bpy.data.materials['ROCK • fractured Himalayan limestone / photographed 4K'])
ob=bpy.data.objects.new('Ascent • fine scree on packed trail',mesh);rock_col.objects.link(ob)

pole=bpy.data.objects['Expedition route wand'];flag=bpy.data.objects['Wind-torn red route pennant']
origin_x=2.2*math.sin(10*.048)+.024*10+2.1
origin_z=baseline(origin_x,10)
for y in range(82,706,14):
    x=route_x(y)+2.35;z=height(x,y)
    for source in [pole,flag]:
        ob=source.copy();ob.name='Ascent • '+source.name;detail_col.objects.link(ob)
        ob.location=(x-origin_x,y-10,z-origin_z)

route=[{'x':route_x(float(y)),'y':float(y),'z':height(route_x(float(y)),float(y))} for y in range(-16,706)]
scene['trail_route']=json.dumps(route)
scene['continuous_ascent']='1'
scene['realism_revision']='original-continuous-ascent-1'
scene['description']='Original Rongbuk approach extended into a continuous reconstructed snowy ascent; original materials and measured distant backdrop retained. Route is artistic, not surveyed.'
scene['ascent_elevation_gain']=route[-1]['z']-route[0]['z']
import runpy
runpy.run_path(str(ROOT/'tools/clear_ascent_corridor.py'),run_name='__main__')
bpy.context.view_layer.update()
scene.render.filepath=str(ROOT/'outputs/everest-ascent-4k.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'outputs/everest-rongbuk-study.blend'))
(ROOT/'outputs/ascent-route.json').write_text(json.dumps({'route':route,'elevation_gain':scene['ascent_elevation_gain'],'limits':json.loads(ground['walk_bounds']),'note':'Reconstructed visual route, not surveyed trail geometry.'},indent=2))
print(json.dumps({'objects':len(scene.objects),'elevation_gain':scene['ascent_elevation_gain'],'end':route[-1]}))
