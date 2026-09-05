"""Replant existing boulders that overlap the new marked bend."""
import bpy
import json
import math
from mathutils import Vector

scene=next(s for s in bpy.data.scenes if s.name.startswith('EVEREST |'))
route=json.loads(scene['trail_route'])
ground=bpy.data.objects['Foreground | metre-scale moraine & wind-sculpted snow']
grid=json.loads(ground['walk_grid']);nx=grid['nx']
def height(x,y):
    u=max(0,min(nx-1.001,(x-grid['xmin'])/grid['step']))
    v=max(0,min(grid['ny']-1.001,(y-grid['ymin'])/grid['step']))
    i,j=int(u),int(v);a,b=u-i,v-j
    h=ground.data.vertices
    return (h[j*nx+i].co.z*(1-a)+h[j*nx+i+1].co.z*a)*(1-b)+(h[(j+1)*nx+i].co.z*(1-a)+h[(j+1)*nx+i+1].co.z*a)*b
col=bpy.data.collections['04 • stones & boulders']
caps={tuple(round(v,4) for v in o.location):o for o in col.objects if 'snow cap' in o.name.lower()}
moved=0
for ob in col.objects:
    if ob.name.startswith('Ascent') or ob.type!='MESH' or 'snow cap' in ob.name.lower():continue
    x,y,z=ob.location
    if not 40<y<155:continue
    path=route[max(0,min(len(route)-1,round(y)+16))]['x']
    corners=[ob.matrix_world@Vector(c) for c in ob.bound_box]
    radius=max(max(c.x for c in corners)-min(c.x for c in corners),max(c.y for c in corners)-min(c.y for c in corners))*.5
    if abs(x-path)>2.3+radius:continue
    cap=caps.get(tuple(round(v,4) for v in ob.location))
    xx=path+math.copysign(3+radius,x-path)
    dz=height(xx,y)-height(x,y)
    ob.location.x=xx;ob.location.z+=dz
    if cap:cap.location=ob.location
    moved+=1
bpy.context.view_layer.update()
print('Replanted original trail-side rocks:',moved)
