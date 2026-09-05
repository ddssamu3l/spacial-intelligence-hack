"""Replace the flat rear transition with terrain joined to the starting ground."""
import bpy
import numpy as np
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ground=bpy.data.objects['Foreground | metre-scale moraine & wind-sculpted snow']
transition=bpy.data.objects['Transition into surveyed landscape']
massif=bpy.data.objects['Everest massif | Copernicus measured 30m elevations']
source=np.load(ROOT/'assets/terrain/everest_backdrop.npz')
dem=source['elevation']
origin=np.unravel_index(((source['latitude']-28.045)**2+(source['longitude']-86.945)**2).argmin(),dem.shape)
dem=dem-float(dem[origin])
positions=np.array([v.co[:] for v in massif.data.vertices]).reshape(*dem.shape,3)
basis=np.column_stack((positions[0,1,:2]-positions[0,0,:2],positions[1,0,:2]-positions[0,0,:2]))
inverse=np.linalg.inv(basis)
def measured(x,y):
    u,v=inverse@(np.array([x,y])-positions[0,0,:2])
    u=max(0,min(dem.shape[1]-1.001,u));v=max(0,min(dem.shape[0]-1.001,v))
    i,j=int(u),int(v);a,b=u-i,v-j
    return (dem[j,i]*(1-a)+dem[j,i+1]*a)*(1-b)+(dem[j+1,i]*(1-a)+dem[j+1,i+1]*a)*b
def rear(x,y):
    u=max(0,min(359.999,(x+90)*2));i=int(u);a=u-i
    edge=ground.data.vertices[i].co.z*(1-a)+ground.data.vertices[i+1].co.z*a
    t=max(0,min(1,(-y-45)/140));t=t*t*(3-2*t)
    return edge*(1-t)+(measured(x,y)+.3)*t
for v in transition.data.vertices:
    if v.co.y<=-45:
        v.co.z=rear(v.co.x,v.co.y)
transition.data.update()
# Match the half-metre foreground rim to the five-metre transition edge.
# Otherwise its intermediate vertices leave small openings between the meshes.
import json
grid=json.loads(ground['walk_grid']);nx=grid['nx'];ny=grid['ny']
original=np.array([v.co.z for v in ground.data.vertices]).reshape(ny,nx)
for j in range(9):
    blend=(1-j/8)**2
    for i in range(nx):
        left=min((i//10)*10,nx-11);a=(i-left)/10
        edge=original[0,left]*(1-a)+original[0,left+10]*a
        ground.data.vertices[j*nx+i].co.z+=blend*(edge-original[0,i])
ground.data.update()
for v in massif.data.vertices:
    x,y=v.co.x,v.co.y
    if abs(x)<350 and -250<y<-45:
        v.co.z=min(v.co.z,rear(x,y)-2)
massif.data.update()
transition['rear_surface']='Contoured measured terrain; flat rear sheet removed'
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'outputs/everest-rongbuk-study.blend'))
print('Removed the flat rear sheet and joined its edge to the foreground')
