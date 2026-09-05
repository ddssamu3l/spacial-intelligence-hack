import bpy, math, numpy as np
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
scene=bpy.context.scene
d=np.load(ROOT/'assets/terrain/everest_backdrop.npz')
dem=d['elevation'];east=d['easting'];north=d['northing'];rows,cols=dem.shape
origin=np.unravel_index(((d['latitude']-28.045)**2+(d['longitude']-86.945)**2).argmin(),dem.shape)
r,c=origin;e0,n0,z0=float(east[origin]),float(north[origin]),float(dem[origin])
f=np.array([-1970.,-6307.]);f/=np.linalg.norm(f);right=np.array([-f[1],f[0]])
basis=np.array([[east[r,c+1]-e0,east[r+1,c]-e0],[north[r,c+1]-n0,north[r+1,c]-n0]])
inverse=np.linalg.inv(basis)
def sample(col,row):
    i=max(0,min(cols-2,int(col)));j=max(0,min(rows-2,int(row)))
    tx=max(0,min(1,col-i));ty=max(0,min(1,row-j))
    return float((dem[j,i]*(1-tx)+dem[j,i+1]*tx)*(1-ty)+(dem[j+1,i]*(1-tx)+dem[j+1,i+1]*tx)*ty-z0)
for ob in bpy.data.collections['02 • detailed moraine & snow'].objects:
    deltas=[]
    for v in ob.data.vertices:
        x,y,z=v.co
        delta=x*right+y*f;e,n=delta+np.array([e0,n0])
        old=sample((e-east[0,0])/(east[0,-1]-east[0,0])*(cols-1),(n-north[0,0])/(north[-1,0]-north[0,0])*(rows-1))
        cc,rr=inverse@delta
        new=sample(c+cc,r+rr)
        blend=max(0,min(1,((x*x+(y*.8)**2)**.5-75)/230));blend=blend*blend*(3-2*blend)
        v.co.z+=blend*(new-old)
        deltas.append(blend*(new-old))
    print(ob.name,'height correction',min(deltas),max(deltas))
# A slope mask exposes the real ridge shape and snow gullies.
m=bpy.data.materials['MOUNTAIN • sedimentary bands, snow gullies & exposed ridges'];n=m.node_tree.nodes;l=m.node_tree.links
n['Math.001'].inputs[1].default_value=.15
n['Color Ramp.001'].color_ramp.elements[0].position=.86
n['Color Ramp.001'].color_ramp.elements[1].position=.99
n['Color Ramp'].color_ramp.elements[0].color=(.028,.032,.038,1)
n['Color Ramp'].color_ramp.elements[1].color=(.13,.14,.15,1)
n['Vector Math'].inputs[1].default_value=(.025,.025,.055)
n['Bump'].inputs['Distance'].default_value=7.0
n['Bump'].inputs['Strength'].default_value=.7
# The transition uses the same slope treatment as the measured mountains away from the walkable patch.
ob=bpy.data.objects['Transition into surveyed landscape']
ob.data.materials.append(m)
for p in ob.data.polygons:
    if p.center.length>200:p.material_index=1
# Break up the ice's overly regular tessellated crack pattern; preserve subtle melt layering.
m=bpy.data.materials['ICE • blue glacier core / wind-eroded opaque crust'];n=m.node_tree.nodes;l=m.node_tree.links
cr=next(x for x in n if x.label=='Fine stress fractures')
cr.color_ramp.elements[0].color=(.65,.65,.65,1)
cr.color_ramp.elements[0].position=.001
cr.color_ramp.elements[1].position=.006
n['Color Ramp'].color_ramp.elements[0].color=(.18,.38,.46,1)
n['Color Ramp'].color_ramp.elements[1].color=(.69,.84,.88,1)
for ob in bpy.data.collections['03 • fractured glacier ice'].objects:
    ob.modifiers['Sublimation relief'].strength=.28
# Clear high-altitude light with a richer blue sky.
n=scene.world.node_tree.nodes
for node in n:
    if node.type=='VALTORGB':
        node.color_ramp.elements[0].color=(.09,.20,.35,1)
        node.color_ramp.elements[1].color=(.013,.047,.13,1)
scene.view_settings.exposure=-.15
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'outputs/everest-rongbuk-study.blend'))
print('Corrected projected terrain interpolation and refined distant snow and ice')
