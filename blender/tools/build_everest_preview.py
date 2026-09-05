"""Build the Everest visual proof through Blender MCP. Units are metres."""
import bpy
import bmesh
import math
import random
import json
from pathlib import Path
import numpy as np
from mathutils import Vector, noise

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs'
OUT.mkdir(exist_ok=True)
random.seed(4129)

# Use a separate scene so the user's starting scene stays available.
scene = bpy.data.scenes.new('EVEREST | East Rongbuk — visual study')
bpy.context.window.scene = scene
scene.unit_settings.system = 'METRIC'
scene['description'] = 'Measured Copernicus Everest skyline with an art-directed 100 m East Rongbuk foreground. Foreground rocks, ice, snow and path are reconstructed, not surveyed.'
scene['source_coordinates'] = '28.045 N, 86.945 E; approximate north-eastern approach viewpoint'

def collection(name):
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    return c

terrain_col = collection('01 • measured mountain backdrop')
ground_col = collection('02 • detailed moraine & snow')
ice_col = collection('03 • fractured glacier ice')
rock_col = collection('04 • stones & boulders')
detail_col = collection('05 • expedition trail details')
light_col = collection('06 • camera & daylight')

def mesh_object(name, verts, faces, col, material=None, smooth=False):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    col.objects.link(obj)
    if material:
        mesh.materials.append(material)
    if smooth:
        for p in mesh.polygons:
            p.use_smooth = True
    return obj

def material(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes.clear()
    n = m.node_tree.nodes
    l = m.node_tree.links
    out = n.new('ShaderNodeOutputMaterial')
    out.location = (1100, 0)
    return m, n, l, out

def node(n, kind, label, loc):
    o = n.new(kind)
    o.label = label
    o.location = loc
    return o

def tex(n, l, asset, channel, vector, pos):
    im = node(n, 'ShaderNodeTexImage', asset + ' • ' + channel + ' • 4K', pos)
    im.image = bpy.data.images.load(str(ROOT / 'assets' / 'textures' / f'{asset}_{channel}_4k.jpg'), check_existing=True)
    if channel != 'diff':
        im.image.colorspace_settings.name = 'Non-Color'
    im.projection = 'BOX'
    im.projection_blend = .25
    l.new(vector, im.inputs['Vector'])
    return im

def mapped(n, l, scale, loc=(-1100,0)):
    g = node(n, 'ShaderNodeNewGeometry', 'Metric world coordinates', (loc[0]-200,loc[1]))
    s = node(n, 'ShaderNodeVectorMath', 'True material scale', loc)
    s.operation = 'SCALE'
    s.inputs['Scale'].default_value = scale
    l.new(g.outputs['Position'],s.inputs[0])
    return s.outputs['Vector']

def pbr(n,l,asset,scale,pos, snow=False):
    x,y=pos
    v=mapped(n,l,scale,(x-700,y))
    diff=tex(n,l,asset,'diff',v,(x-490,y+130))
    rough=tex(n,l,asset,'rough',v,(x-490,y-110))
    normal=tex(n,l,asset,'nor_gl',v,(x-490,y-360))
    bs=node(n,'ShaderNodeBsdfPrincipled',asset,(x,y))
    l.new(diff.outputs['Color'],bs.inputs['Base Color'])
    l.new(rough.outputs['Color'],bs.inputs['Roughness'])
    bump=node(n,'ShaderNodeBump','Surface grain', (x-220,y-170))
    bump.inputs['Strength'].default_value=.3 if snow else .5
    bump.inputs['Distance'].default_value=.025 if snow else .09
    l.new(diff.outputs['Color'],bump.inputs['Height'])
    norm=node(n,'ShaderNodeNormalMap','Photogrammetric normals',(x-220,y-380))
    norm.space='WORLD'
    norm.inputs['Strength'].default_value=.35 if snow else .6
    l.new(normal.outputs['Color'],norm.inputs['Color'])
    # Height-driven bump avoids tangent seams with triplanar mapping.
    l.new(bump.outputs['Normal'],bs.inputs['Normal'])
    if snow:
        bs.inputs['Subsurface Weight'].default_value=.035
        bs.inputs['Subsurface Radius'].default_value=(.05,.1,.16)
        bs.inputs['IOR'].default_value=1.31
    return bs

snow_mat,n,l,o=material('SNOW • wind-compacted / photographed 4K')
snow_bs=pbr(n,l,'snow_02',.32,(0,0),True)
l.new(snow_bs.outputs[0],o.inputs['Surface'])

rock_mat,n,l,o=material('ROCK • fractured Himalayan limestone / photographed 4K')
rock_bs=pbr(n,l,'rock_boulder_cracked',.55,(0,0))
l.new(rock_bs.outputs[0],o.inputs['Surface'])

ground_mat,n,l,o=material('MORAINE • snow pockets over shattered rock / 4K')
rb=pbr(n,l,'aerial_rocks_02',.23,(100,200))
sb=pbr(n,l,'snow_02',.35,(100,-450),True)
attr=node(n,'ShaderNodeAttribute','Snow cover from terrain & trail',(300,430))
attr.attribute_name='SnowMask'
mix=node(n,'ShaderNodeMixShader','Snow accumulation',(800,80))
l.new(attr.outputs['Fac'],mix.inputs[0]);l.new(rb.outputs[0],mix.inputs[1]);l.new(sb.outputs[0],mix.inputs[2]);l.new(mix.outputs[0],o.inputs['Surface'])

mount_mat,n,l,o=material('MOUNTAIN • sedimentary bands, snow gullies & exposed ridges')
g=node(n,'ShaderNodeNewGeometry','Slope & position',(-1100,200))
sep=node(n,'ShaderNodeSeparateXYZ','Normal Z',(-880,320));l.new(g.outputs['Normal'],sep.inputs[0])
scale=node(n,'ShaderNodeVectorMath','Stratified rock coordinates',(-860,-150));scale.operation='MULTIPLY';scale.inputs[1].default_value=(.025,.025,.11);l.new(g.outputs['Position'],scale.inputs[0])
nt=node(n,'ShaderNodeTexNoise','Rock layers',(-630,-120));nt.inputs['Scale'].default_value=1;nt.inputs['Detail'].default_value=5;l.new(scale.outputs[0],nt.inputs['Vector'])
cr=node(n,'ShaderNodeValToRGB','Cold limestone',(-370,-50));cr.color_ramp.elements[0].position=.2;cr.color_ramp.elements[0].color=(.045,.05,.055,1);cr.color_ramp.elements[1].position=.78;cr.color_ramp.elements[1].color=(.24,.23,.215,1);l.new(nt.outputs['Fac'],cr.inputs[0])
add=node(n,'ShaderNodeMath','Snow on ledges',(-420,320));add.operation='ADD';l.new(sep.outputs[0],add.inputs[0])
noisemul=node(n,'ShaderNodeMath','Broken snowline',(-620,500));noisemul.operation='MULTIPLY';noisemul.inputs[1].default_value=.34;l.new(nt.outputs['Fac'],noisemul.inputs[0]);l.new(noisemul.outputs[0],add.inputs[1])
ramp=node(n,'ShaderNodeValToRGB','Angle-dependent snow mask',(-200,320));ramp.color_ramp.elements[0].position=.64;ramp.color_ramp.elements[1].position=.82;l.new(add.outputs[0],ramp.inputs[0])
colmix=node(n,'ShaderNodeMixRGB','Snow gullies',(50,150));colmix.inputs[2].default_value=(.76,.84,.91,1);l.new(ramp.outputs[0],colmix.inputs[0]);l.new(cr.outputs[0],colmix.inputs[1])
bs=node(n,'ShaderNodeBsdfPrincipled','Mountain',(450,0));bs.inputs['Roughness'].default_value=.82;l.new(colmix.outputs[0],bs.inputs['Base Color'])
bump=node(n,'ShaderNodeBump','Sub-grid crags',(220,-200));bump.inputs['Strength'].default_value=.6;bump.inputs['Distance'].default_value=1.3;l.new(nt.outputs['Fac'],bump.inputs['Height']);l.new(bump.outputs[0],bs.inputs['Normal']);l.new(bs.outputs[0],o.inputs['Surface'])

ice_mat,n,l,o=material('ICE • blue glacier core / wind-eroded opaque crust')
g=node(n,'ShaderNodeNewGeometry','Ice geometry',(-1000,150))
scaled=node(n,'ShaderNodeVectorMath','Compressed strata',(-820,-80));scaled.operation='MULTIPLY';scaled.inputs[1].default_value=(.45,.4,2.7);l.new(g.outputs['Position'],scaled.inputs[0])
nt=node(n,'ShaderNodeTexNoise','Glacial lamination',(-600,-50));nt.inputs['Scale'].default_value=2.2;nt.inputs['Detail'].default_value=5;nt.inputs['Roughness'].default_value=.74;l.new(scaled.outputs[0],nt.inputs['Vector'])
ramp=node(n,'ShaderNodeValToRGB','Deep blue to milky ice',(-350,100));ramp.color_ramp.elements[0].position=.22;ramp.color_ramp.elements[0].color=(.035,.15,.23,1);ramp.color_ramp.elements[1].position=.73;ramp.color_ramp.elements[1].color=(.62,.8,.88,1);l.new(nt.outputs['Fac'],ramp.inputs[0])
ib=node(n,'ShaderNodeBsdfPrincipled','Glacier core',(100,0));ib.inputs['Roughness'].default_value=.36;ib.inputs['IOR'].default_value=1.31;ib.inputs['Subsurface Weight'].default_value=.075;ib.inputs['Subsurface Radius'].default_value=(.12,.3,.55);l.new(ramp.outputs[0],ib.inputs['Base Color'])
bump=node(n,'ShaderNodeBump','Melt fluting',(-120,-170));bump.inputs['Strength'].default_value=.6;bump.inputs['Distance'].default_value=.075;l.new(nt.outputs['Fac'],bump.inputs['Height']);l.new(bump.outputs[0],ib.inputs['Normal'])
sep=node(n,'ShaderNodeSeparateXYZ','Upward faces',(-580,430));l.new(g.outputs['Normal'],sep.inputs[0])
mask=node(n,'ShaderNodeValToRGB','Wind-blown snow crust',(-300,440));mask.color_ramp.elements[0].position=.26;mask.color_ramp.elements[1].position=.64;l.new(sep.outputs['Z'],mask.inputs[0])
snowbs=node(n,'ShaderNodeBsdfPrincipled','Snow crust',(100,350));snowbs.inputs['Base Color'].default_value=(.8,.87,.94,1);snowbs.inputs['Roughness'].default_value=.77;l.new(bump.outputs[0],snowbs.inputs['Normal'])
mix=node(n,'ShaderNodeMixShader','Ice & deposited snow',(720,100));l.new(mask.outputs[0],mix.inputs[0]);l.new(ib.outputs[0],mix.inputs[1]);l.new(snowbs.outputs[0],mix.inputs[2]);l.new(mix.outputs[0],o.inputs['Surface'])

dataset=np.load(ROOT/'assets/terrain/everest_backdrop.npz')
dem=dataset['elevation']; east=dataset['easting']; north=dataset['northing']
dist=(dataset['latitude']-28.045)**2+(dataset['longitude']-86.945)**2
origin=np.unravel_index(dist.argmin(),dist.shape)
e0,n0,z0=float(east[origin]),float(north[origin]),float(dem[origin])
forward=np.array([-1970.,-6307.]);forward/=np.linalg.norm(forward)
right=np.array([-forward[1],forward[0]])
xx=(east-e0)*right[0]+(north-n0)*right[1]
yy=(east-e0)*forward[0]+(north-n0)*forward[1]
zz=dem-z0
verts=np.stack([xx,yy,zz],axis=-1).reshape(-1,3).tolist()
rows,cols=dem.shape
faces=[]
for j in range(rows-1):
    for i in range(cols-1):
        if -350<xx[j,i]<350 and -250<yy[j,i]<450:
            continue
        a=j*cols+i
        faces.append((a,a+1,a+cols+1,a+cols))
back=mesh_object('Everest massif | Copernicus measured 30m elevations',verts,faces,terrain_col,mount_mat,True)
print('Backdrop created',len(verts),'vertices',flush=True)

def macro_height(x,y):
    e=e0+x*right[0]+y*forward[0]
    n=n0+x*right[1]+y*forward[1]
    col=(e-east[0,0])/(east[0,-1]-east[0,0])*(cols-1)
    row=(n-north[0,0])/(north[-1,0]-north[0,0])*(rows-1)
    i=max(0,min(cols-2,int(col)));j=max(0,min(rows-2,int(row)))
    tx=max(0,min(1,col-i));ty=max(0,min(1,row-j))
    return float((dem[j,i]*(1-tx)+dem[j,i+1]*tx)*(1-ty)+(dem[j+1,i]*(1-tx)+dem[j+1,i+1]*tx)*ty-z0)

def fb(x,y,s):
    return noise.fractal(Vector((x*s,y*s,2.714)),1.,2.,4)

def trail_x(y):
    return 2.2*math.sin(y*.048)+.024*y

def height(x,y):
    trail=abs(x-trail_x(y))
    fine=.10*fb(x,y,1.3)+.035*fb(x,y,5)
    banks=.52*fb(x,y,.12)+.5*fb(x,y,.032)
    bankheight=.055*min(trail,32)+1.6*math.exp(-((x-21)/11)**2-((y-30)/35)**2)
    local=.019*y+bankheight+banks+fine
    if trail<1.7:
        t=math.exp(-(trail/1.15)**4)
        local=local*(1-.75*t)+(.022*y+.1*fb(x,y,.16))*t*.75
    radius=math.sqrt(x*x+(y*.8)**2)
    blend=max(0,min(1,(radius-75)/230));blend=blend*blend*(3-2*blend)
    return local*(1-blend)+macro_height(x,y)*blend

def ground(name,xmin,xmax,ymin,ymax,step,skip=False):
    nx=round((xmax-xmin)/step)+1;ny=round((ymax-ymin)/step)+1
    vs=[];mask=[]
    for j in range(ny):
        y=ymin+j*step
        for i in range(nx):
            x=xmin+i*step
            z=height(x,y)
            path=abs(x-trail_x(y))
            coverage=.60+.6*fb(x,y,.17)+.15*fb(x,y,1.8)
            if path<1.45:
                coverage-=.67*math.exp(-(path/1.05)**6)
            coverage=max(0,min(1,(coverage-.2)*3))
            vs.append((x,y,z));mask.append(coverage)
    fs=[]
    for j in range(ny-1):
        for i in range(nx-1):
            x=xmin+i*step;y=ymin+j*step
            if skip and -90<=x<90 and -45<=y<155:continue
            a=j*nx+i;fs.append((a,a+1,a+nx+1,a+nx))
    obj=mesh_object(name,vs,fs,ground_col,ground_mat,True)
    a=obj.data.attributes.new('SnowMask','FLOAT','POINT');a.data.foreach_set('value',mask)
    return obj

ground('Foreground | metre-scale moraine & wind-sculpted snow',-90,90,-45,155,.5)
ground('Transition into surveyed landscape',-350,350,-250,450,5,True)
print('Detailed ground created',flush=True)

# Shared rock meshes keep thousands of distinct stones affordable to render.
rock_meshes=[]
cap_meshes=[]
for variant in range(14):
    bm=bmesh.new();bmesh.ops.create_icosphere(bm,subdivisions=3,radius=1)
    for v in bm.verts:
        co=v.co.copy()
        fac=1+.20*noise.noise_vector(co*2.2+Vector((variant*3.1,2,0))).x+.10*noise.noise(co*5)
        v.co=Vector((co.x*fac,co.y*fac,co.z*fac*.70))
        v.co.x+=v.co.z*.18
    me=bpy.data.meshes.new(f'Fractured rock prototype {variant:02}')
    bm.to_mesh(me);bm.free();me.materials.append(rock_mat)
    for p in me.polygons:p.use_smooth=True
    rock_meshes.append(me)
    cv=[];cf=[]
    for p in me.polygons:
        if p.normal.z>.38 and p.center.z>-.1:
            face=[]
            for vi in p.vertices:
                v=me.vertices[vi].co
                face.append(len(cv));cv.append((v.x*1.015,v.y*1.015,v.z+.04))
            cf.append(face)
    cm=bpy.data.meshes.new(f'Snow mantle {variant:02}');cm.from_pydata(cv,[],cf);cm.materials.append(snow_mat)
    for p in cm.polygons:p.use_smooth=True
    cap_meshes.append(cm)

def rock(x,y,size,cap=False,name='Moraine fragment'):
    idx=random.randrange(len(rock_meshes))
    ob=bpy.data.objects.new(name,rock_meshes[idx]);rock_col.objects.link(ob)
    ob.location=(x,y,height(x,y)+size*.22)
    ob.scale=(size*random.uniform(.75,1.3),size*random.uniform(.7,1.2),size*random.uniform(.6,1))
    ob.rotation_euler=(random.uniform(-.25,.25),random.uniform(-.25,.25),random.random()*math.tau)
    if cap:
        capob=bpy.data.objects.new('Windward snow cap',cap_meshes[idx]);rock_col.objects.link(capob)
        capob.location=ob.location;capob.scale=ob.scale;capob.rotation_euler=ob.rotation_euler
    return ob

for k in range(2300):
    x=random.uniform(-65,65);y=random.uniform(-15,145)
    path=abs(x-trail_x(y))
    if path<1.2 and random.random()<.85:continue
    size=random.uniform(.07,.24) if k<1700 else random.uniform(.25,.72)
    rock(x,y,size,cap=(size>.27 and random.random()<.43))
for x,y,s in [(-4,1,1.5),(-6,10,1.7),(6,15,1.25),(-8,22,2.1),(9,37,1.6),(-15,38,2.5),(21,10,2.8),(-11,70,3.1),(-3,54,.7)]:
    rock(x,y,s,True,'Hero boulder • weathered limestone')
print('Rock field created',flush=True)

def serac(name,x,y,width,depth,h,seed):
    rng=random.Random(seed)
    sides=16;layers=18
    angles=[i*math.tau/sides+rng.uniform(-.05,.05) for i in range(sides)]
    radii=[rng.uniform(.74,1.15) for i in range(sides)]
    leanx=rng.uniform(-.30,.30)*width;leany=rng.uniform(-.25,.25)*depth
    verts=[]
    base=height(x,y)-1.2
    for j in range(layers):
        t=j/(layers-1)
        profile=(1-t)**.54*.98+.025
        for i,a in enumerate(angles):
            flute=1+.06*math.sin(t*27+i*2)+.045*math.sin(t*63+i)
            rad=radii[i]*profile*flute
            z=base+t*h+(math.sin(a*3+seed)*.35+math.sin(a*5)*.18)*math.sin(t*math.pi)
            verts.append((x+math.cos(a)*width*.5*rad+leanx*t,y+math.sin(a)*depth*.5*rad+leany*t,z))
    fs=[]
    for j in range(layers-1):
        for i in range(sides):
            a=j*sides+i;b=j*sides+(i+1)%sides
            fs.append((a,b,b+sides,a+sides))
    fs.append(tuple(range((layers-1)*sides,layers*sides)))
    ob=mesh_object(name,verts,fs,ice_col,ice_mat,False)
    bevel=ob.modifiers.new('Softened ice fracture edges','BEVEL');bevel.width=.07;bevel.segments=2
    return ob

for i,spec in enumerate([(14,21,9,13,15),(20,30,11,13,19),(26,46,13,16,22),(16,48,7,10,11),(33,70,18,16,25),(-18,40,8,13,12),(-25,56,12,14,17),(-36,89,18,16,22),(-13,91,9,12,11),(32,120,21,23,26),(-41,140,23,22,30)]):
    serac(f'Serac {i+1:02} • sculpted ice pinnacle',*spec,seed=45+i*17)
for i in range(34):
    y=random.uniform(12,150);side=random.choice([-1,1]);x=side*random.uniform(10,65)
    serac('Broken glacial block',x,y,random.uniform(1,4),random.uniform(1,4),random.uniform(.8,3.5),i+388)

def simple_mat(name,color,rough=.7,metal=0):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Roughness'].default_value=rough;bs.inputs['Metallic'].default_value=metal
    return m

polemat=simple_mat('Weathered aluminium',(.21,.23,.25),.38,.7)
red=simple_mat('Faded red expedition marker',(.43,.022,.012),.9)
rope_mat=simple_mat('Ochre braided route cord',(.42,.23,.055),.95)

def line(name,points,radius,mat):
    c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.resolution_u=2;c.bevel_depth=radius;c.bevel_resolution=2
    sp=c.splines.new('POLY');sp.points.add(len(points)-1)
    for p,co in zip(sp.points,points):p.co=(*co,1)
    ob=bpy.data.objects.new(name,c);detail_col.objects.link(ob);c.materials.append(mat)
    return ob

for j,y in enumerate([10,24,43,64]):
    x=trail_x(y)+2.1;z=height(x,y)
    line('Expedition route wand',[(x,y,z),(x+.05,y,z+1.45)],.018,polemat)
    vs=[];fs=[]
    for iy in range(7):
        for ix in range(17):
            u=ix/16;v=iy/6
            vs.append((x+u*.54,y+.055*math.sin(u*8+v*3+j)*u,z+1.36-v*.20+.025*math.sin(u*10+v)*u))
    for iy in range(6):
        for ix in range(16):
            a=iy*17+ix;fs.append((a,a+1,a+18,a+17))
    mesh_object('Wind-torn red route pennant',vs,fs,detail_col,red,True)

# A modest cairn gives a familiar scale cue without turning the scene into a campsite.
for j in range(6):
    s=.40*(1-j*.11)
    ob=rock(-2.9,17,s,False,'Trail cairn stone')
    ob.location.z=height(-2.9,17)+j*.23
    ob.scale.z*=.5

world=bpy.data.worlds.new('Thin high-altitude atmosphere');world.use_nodes=True;scene.world=world
wn=world.node_tree.nodes;wl=world.node_tree.links;wn.clear()
wo=wn.new('ShaderNodeOutputWorld');bg=wn.new('ShaderNodeBackground');bg.inputs['Strength'].default_value=.32
sky=wn.new('ShaderNodeTexSky');sky.sky_type='MULTIPLE_SCATTERING';sky.sun_elevation=math.radians(23);sky.sun_rotation=math.radians(135);sky.altitude=6200;sky.air_density=.65;sky.aerosol_density=.12;sky.ozone_density=1.4;sky.sun_disc=False
wl.new(sky.outputs[0],bg.inputs[0]);wl.new(bg.outputs[0],wo.inputs[0])
sun_data=bpy.data.lights.new('High altitude morning sun','SUN');sun_data.energy=3.4;sun_data.angle=math.radians(.65);sun_data.color=(1,.91,.8)
sun=bpy.data.objects.new('Sun • grazing across ice faces',sun_data);light_col.objects.link(sun)
sun.rotation_euler=Vector((.65,.3,-.55)).to_track_quat('-Z','Y').to_euler()

cam_data=bpy.data.cameras.new('Expedition camera • 28 mm');cam=bpy.data.objects.new('Camera • standing on the glacier approach',cam_data);light_col.objects.link(cam)
cam.location=(0,-16,height(0,-16)+2.1)
target=Vector((0,125,17));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
cam_data.lens=28;cam_data.sensor_width=36;cam_data.clip_start=.1;cam_data.clip_end=50000
scene.camera=cam
scene.render.engine='CYCLES';scene.cycles.samples=96;scene.cycles.use_denoising=True;scene.cycles.adaptive_threshold=.025
scene.cycles.max_bounces=8;scene.cycles.diffuse_bounces=3;scene.cycles.glossy_bounces=3;scene.cycles.transmission_bounces=4
try:
    prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='METAL';prefs.get_devices()
    for device in prefs.devices:device.use=(device.type=='METAL')
    scene.cycles.device='GPU'
    print('Render devices',[(d.name,d.type,d.use) for d in prefs.devices],flush=True)
except Exception as e:
    scene.cycles.device='CPU';print('CPU render fallback',str(e),flush=True)
scene.render.resolution_x=3840;scene.render.resolution_y=2160;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB';scene.render.image_settings.color_depth='8'
scene.render.film_transparent=False
scene.view_settings.view_transform='AgX'
scene.view_settings.look='AgX - Medium High Contrast'
scene.view_settings.exposure=-.15
scene.render.filepath=str(OUT/'everest-rongbuk-4k.png')
scene.render.use_file_extension=True
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_perspective='CAMERA'
            area.spaces.active.clip_end=50000
            area.spaces.active.shading.type='MATERIAL'
            area.spaces.active.overlay.show_overlays=False
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'everest-rongbuk-study.blend'))
print(json.dumps({'scene':scene.name,'objects':len(scene.objects),'foreground':'reconstructed','backdrop':'Copernicus GLO-30','resolution':[3840,2160],'saved':str(OUT/'everest-rongbuk-study.blend')}),flush=True)
