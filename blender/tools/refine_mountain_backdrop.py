"""Terrain-derived snow gullies and ridge shading for Blender and the browser."""
import bpy
import numpy as np
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
scene=next(s for s in bpy.data.scenes if s.name.startswith('EVEREST |'))
ob=bpy.data.objects['Everest massif | Copernicus measured 30m elevations']
mesh=ob.data
shape=np.load(ROOT/'assets/terrain/everest_backdrop.npz')['elevation'].shape
p=np.array([v.co[:] for v in mesh.vertices]).reshape(*shape,3)
n=np.array([v.normal[:] for v in mesh.vertices]).reshape(*shape,3)
z=p[:,:,2]
curvature=(np.roll(z,2,0)+np.roll(z,-2,0)+np.roll(z,2,1)+np.roll(z,-2,1)-4*z)/4
gully=np.clip(curvature/10,-.16,.18)
variation=.045*np.sin(p[:,:,0]*.013+np.sin(p[:,:,1]*.009)*2)+.025*np.sin(p[:,:,1]*.031)
field=n[:,:,2]+gully+variation
for _ in range(3):
    field=(field*4+np.roll(field,1,0)+np.roll(field,-1,0)+np.roll(field,1,1)+np.roll(field,-1,1))/8
snow=np.clip((field-.69)/.24,0,1)
snow=snow*snow*(3-2*snow)
attribute=mesh.attributes.get('SnowMask') or mesh.attributes.new('SnowMask','FLOAT','POINT')
attribute.data.foreach_set('value',snow.astype(np.float32).ravel())

# Trace the measured height field toward the same sun used by both renderers.
sun=next(o for o in scene.objects if o.type=='LIGHT')
direction=sun.matrix_world.to_quaternion()@Vector((0,0,1))
xy=np.array(direction[:2]);xy/=np.linalg.norm(xy)
slope=direction.z/np.linalg.norm(direction[:2])
basis=np.column_stack((p[0,1,:2]-p[0,0,:2],p[1,0,:2]-p[0,0,:2]))
step=np.linalg.inv(basis)@xy
j,i=np.indices(shape)
occlusion=np.zeros(shape)
for distance in [40,80,140,230,380,600,950,1500,2300,3400]:
    u=i+step[0]*distance;v=j+step[1]*distance
    valid=(u>=0)&(u<shape[1]-1)&(v>=0)&(v<shape[0]-1)
    u=np.clip(u,0,shape[1]-1.001);v=np.clip(v,0,shape[0]-1.001)
    ii=u.astype(int);jj=v.astype(int);a=u-ii;b=v-jj
    sample=(z[jj,ii]*(1-a)+z[jj,ii+1]*a)*(1-b)+(z[jj+1,ii]*(1-a)+z[jj+1,ii+1]*a)*b
    occlusion=np.maximum(occlusion,np.where(valid,np.clip((sample-z-distance*slope)/(distance*.055)+.5,0,1),0))
shade=1-.55*occlusion
attribute=mesh.attributes.get('MountainShade') or mesh.attributes.new('MountainShade','FLOAT','POINT')
attribute.data.foreach_set('value',shade.astype(np.float32).ravel())

material=bpy.data.materials['MOUNTAIN • sedimentary bands, snow gullies & exposed ridges']
nodes,links=material.node_tree.nodes,material.node_tree.links
nodes['Vector Math'].inputs[1].default_value=(.007,.007,.045)
nodes['Noise Texture'].inputs['Detail'].default_value=3
nodes['Color Ramp'].color_ramp.elements[0].color=(.024,.029,.034,1)
nodes['Color Ramp'].color_ramp.elements[1].color=(.105,.099,.088,1)
nodes['Mix (Legacy)'].inputs[2].default_value=(.82,.88,.95,1)
attr=nodes.get('Measured snow gullies') or nodes.new('ShaderNodeAttribute')
attr.name='Measured snow gullies';attr.attribute_name='SnowMask'
def named(name,kind):
    node=nodes.get(name) or nodes.new(kind);node.name=name
    return node
detail=named('Fractured mountain detail','ShaderNodeTexNoise')
detail.inputs['Scale'].default_value=.06;detail.inputs['Detail'].default_value=4
links.new(nodes['Geometry'].outputs['Position'],detail.inputs['Vector'])
offset=named('Snow edge breakup','ShaderNodeMath');offset.operation='MULTIPLY_ADD'
offset.inputs[1].default_value=.5;offset.inputs[2].default_value=-.25
links.new(detail.outputs['Fac'],offset.inputs[0])
edge=named('Snow on ridges and gullies','ShaderNodeMath');edge.operation='ADD'
links.new(attr.outputs['Fac'],edge.inputs[0]);links.new(offset.outputs[0],edge.inputs[1])
ramp=named('Irregular snow edge','ShaderNodeValToRGB')
ramp.color_ramp.elements[0].position=.22;ramp.color_ramp.elements[1].position=.8
links.new(edge.outputs[0],ramp.inputs[0]);links.new(ramp.outputs[0],nodes['Mix (Legacy)'].inputs[0])
tex=named('Photographed limestone mountain faces','ShaderNodeTexImage')
tex.image=next(i for i in bpy.data.images if 'rock_boulder_cracked_diff' in i.name)
tex.projection='BOX';tex.projection_blend=.25
scale=named('Mountain surface metres','ShaderNodeVectorMath');scale.operation='SCALE';scale.inputs[3].default_value=.045
links.new(nodes['Geometry'].outputs['Position'],scale.inputs[0]);links.new(scale.outputs[0],tex.inputs['Vector'])
rock=named('Natural dark sedimentary rock','ShaderNodeHueSaturation')
rock.inputs['Saturation'].default_value=.15;rock.inputs['Value'].default_value=.36
links.new(tex.outputs['Color'],rock.inputs['Color']);links.new(rock.outputs[0],nodes['Mix (Legacy)'].inputs[1])
links.new(detail.outputs['Fac'],nodes['Bump'].inputs['Height'])
nodes['Bump'].inputs['Distance'].default_value=3.2
nodes['Bump'].inputs['Strength'].default_value=.55
nodes['Principled BSDF'].inputs['Roughness'].default_value=.93
scene['mountain_revision']='terrain-derived snow gullies and sun occlusion'
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'outputs/everest-rongbuk-study.blend'))
print('Mountain snow and ridge shadow fields updated:',len(mesh.vertices),'vertices')
