import bpy, bmesh, math, random
from pathlib import Path
from mathutils import Vector, noise

ROOT=Path(__file__).resolve().parents[1]
scene=bpy.context.scene
random.seed(117)

# Repair the snow mask to use the upward normal, not its east-facing component.
m=bpy.data.materials['MOUNTAIN • sedimentary bands, snow gullies & exposed ridges']
n=m.node_tree.nodes;l=m.node_tree.links
l.new(n['Separate XYZ'].outputs['Z'],n['Math'].inputs[0])
n['Vector Math'].inputs[1].default_value=(.008,.008,.027)
n['Bump'].inputs['Distance'].default_value=.4
n['Color Ramp.001'].color_ramp.elements[0].position=.68
n['Color Ramp.001'].color_ramp.elements[1].position=.86
n['Mix (Legacy)'].inputs[2].default_value=(.88,.93,1.0,1)

# Cold, desaturated rock rather than moss-green moraine or warm sandstone.
for name in ['ROCK • fractured Himalayan limestone / photographed 4K','MORAINE • snow pockets over shattered rock / 4K']:
    m=bpy.data.materials[name];n=m.node_tree.nodes;l=m.node_tree.links
    for bs in [x for x in n if x.type=='BSDF_PRINCIPLED' and not x.label.startswith('snow')]:
        link=next((x for x in l if x.to_socket==bs.inputs['Base Color']),None)
        if link:
            source=link.from_socket
            hs=n.new('ShaderNodeHueSaturation');hs.label='Desaturated alpine limestone';hs.inputs['Saturation'].default_value=.11;hs.inputs['Value'].default_value=.50 if name.startswith('ROCK') else .40
            l.new(source,hs.inputs['Color']);l.new(hs.outputs[0],bs.inputs['Base Color'])

# Weld the snow blankets: disconnected triangles caused artificial faceting.
for me in [m for m in bpy.data.meshes if m.name.startswith('Snow mantle')]:
    bm=bmesh.new();bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.001)
    bmesh.ops.subdivide_edges(bm,edges=list(bm.edges),cuts=2,use_grid_fill=True,smooth=.65)
    bm.to_mesh(me);bm.free()
    for p in me.polygons:p.use_smooth=True
for ob in scene.objects:
    if ob.name.startswith('Windward snow cap'):
        sol=ob.modifiers.new('Rounded accumulated snow edge','SOLIDIFY');sol.thickness=.025

ice=bpy.data.materials['ICE • blue glacier core / wind-eroded opaque crust']
n=ice.node_tree.nodes;l=ice.node_tree.links
n['Color Ramp'].color_ramp.elements[0].color=(.11,.29,.38,1)
n['Color Ramp'].color_ramp.elements[1].color=(.66,.84,.91,1)
n['Color Ramp'].color_ramp.elements[0].position=.15
n['Color Ramp'].color_ramp.elements[1].position=.77
n['Principled BSDF'].inputs['Roughness'].default_value=.43
n['Bump'].inputs['Distance'].default_value=.095
fine=n.new('ShaderNodeTexNoise');fine.label='Ice grains & sublimation pits';fine.inputs['Scale'].default_value=24;fine.inputs['Detail'].default_value=3
l.new(n['Geometry'].outputs['Position'],fine.inputs['Vector'])
fb=n.new('ShaderNodeBump');fb.inputs['Strength'].default_value=.42;fb.inputs['Distance'].default_value=.018
l.new(fine.outputs['Fac'],fb.inputs['Height']);l.new(n['Bump'].outputs['Normal'],fb.inputs['Normal'])
l.new(fb.outputs['Normal'],n['Principled BSDF'].inputs['Normal']);l.new(fb.outputs['Normal'],n['Principled BSDF.001'].inputs['Normal'])
v=n.new('ShaderNodeTexVoronoi');v.feature='DISTANCE_TO_EDGE';v.inputs['Scale'].default_value=.65;l.new(n['Geometry'].outputs['Position'],v.inputs['Vector'])
vr=n.new('ShaderNodeValToRGB');vr.label='Fine stress fractures';vr.color_ramp.elements[0].position=.004;vr.color_ramp.elements[1].position=.018
l.new(v.outputs['Distance'],vr.inputs[0])
mix=n.new('ShaderNodeMixRGB');mix.inputs[1].default_value=(.12,.3,.39,1)
l.new(vr.outputs[0],mix.inputs[0]);l.new(n['Color Ramp'].outputs[0],mix.inputs[2]);l.new(mix.outputs[0],n['Principled BSDF'].inputs['Base Color'])

for ob in bpy.data.collections['03 • fractured glacier ice'].objects:
    for p in ob.data.polygons:p.use_smooth=True
    ob.modifiers.clear()
    sub=ob.modifiers.new('Smooth wind-cut ice ridges','SUBSURF');sub.levels=2;sub.render_levels=2
    tex=bpy.data.textures.new('Ice erosion '+ob.name,'CLOUDS');tex.noise_scale=.35;tex.noise_depth=2
    dis=ob.modifiers.new('Sublimation relief','DISPLACE');dis.texture=tex;dis.texture_coords='GLOBAL';dis.strength=.14;dis.mid_level=.5

terrain=bpy.data.objects['Foreground | metre-scale moraine & wind-sculpted snow']
for p in terrain.data.attributes['SnowMask'].data:
    p.value=.08+.92*p.value

# Thousands of tiny angular fragments make the walking surface read at eye level.
bm=bmesh.new();bmesh.ops.create_icosphere(bm,subdivisions=1,radius=1)
proto=bpy.data.meshes.new('Angular gravel prototype');bm.to_mesh(proto);bm.free()
pv=[v.co.copy() for v in proto.vertices];pf=[tuple(p.vertices) for p in proto.polygons]
groundmesh=terrain.data
def z_at(x,y):
    i=max(0,min(360,round((x+90)*2)));j=max(0,min(400,round((y+45)*2)))
    return groundmesh.vertices[j*361+i].co.z
verts=[];faces=[]
for i in range(11000):
    x=random.uniform(-26,26);y=random.uniform(-10,67)
    ix=max(0,min(360,round((x+90)*2)));iy=max(0,min(400,round((y+45)*2)))
    snow=groundmesh.attributes['SnowMask'].data[iy*361+ix].value
    if snow>.75 and random.random()<.85:continue
    r=random.uniform(.025,.11);z=z_at(x,y)+r*.18
    a=random.random()*math.tau;co=math.cos(a);si=math.sin(a)
    start=len(verts)
    for v in pv:
        verts.append((x+(v.x*co-v.y*si)*r,y+(v.x*si+v.y*co)*r*.8,z+v.z*r*.4))
    for f in pf:faces.append(tuple(start+v for v in f))
me=bpy.data.meshes.new('Fine scree geometry');me.from_pydata(verts,[],faces);me.materials.append(bpy.data.materials['ROCK • fractured Himalayan limestone / photographed 4K'])
ob=bpy.data.objects.new('Thousands of angular scree fragments',me);bpy.data.collections['04 • stones & boulders'].objects.link(ob)

# Keep physical sky illumination and give the visible sky a deeper alpine gradient.
n=scene.world.node_tree.nodes;l=scene.world.node_tree.links
out=next(x for x in n if x.type=='OUTPUT_WORLD')
physical=next(x for x in n if x.type=='BACKGROUND')
physical.inputs['Strength'].default_value=.4
tc=n.new('ShaderNodeTexCoord');sep=n.new('ShaderNodeSeparateXYZ');l.new(tc.outputs['Normal'],sep.inputs[0])
mapr=n.new('ShaderNodeMapRange');mapr.inputs['From Min'].default_value=-.05;mapr.inputs['From Max'].default_value=-.8;l.new(sep.outputs['Z'],mapr.inputs['Value'])
ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=(.20,.34,.52,1);ramp.color_ramp.elements[1].color=(.025,.085,.20,1);l.new(mapr.outputs['Result'],ramp.inputs[0])
visible=n.new('ShaderNodeBackground');visible.inputs['Strength'].default_value=.65;l.new(ramp.outputs[0],visible.inputs[0])
lp=n.new('ShaderNodeLightPath');mix=n.new('ShaderNodeMixShader');l.new(lp.outputs['Is Camera Ray'],mix.inputs[0]);l.new(physical.outputs[0],mix.inputs[1]);l.new(visible.outputs[0],mix.inputs[2]);l.new(mix.outputs[0],out.inputs[0])
sun=bpy.data.lights['High altitude morning sun'];sun.energy=4.2;sun.color=(1,.95,.88);sun.angle=math.radians(.8)
scene.view_settings.exposure=.1
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':area.spaces.active.shading.type='SOLID'
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'outputs/everest-rongbuk-study.blend'))
print('Refined surfaces, mountain snow mask, scree, and daylight. Objects:',len(scene.objects))
