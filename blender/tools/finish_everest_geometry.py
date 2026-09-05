import bpy, numpy as np, math
from pathlib import Path
from mathutils import Vector, noise
ROOT=Path(__file__).resolve().parents[1]
scene=bpy.context.scene
source=(ROOT/'tools/polish_everest_preview.py').read_text()
exec(source[source.index('d=np.load'):source.index('for ob in bpy.data.collections')])
def macro(x,y):
    cc,rr=inverse@(x*right+y*f)
    return sample(c+cc,r+rr)
def fb(x,y,s):return noise.fractal(Vector((x*s,y*s,2.714)),1.,2.,4)
def surface(x,y):
    trail=abs(x-(2.2*math.sin(y*.048)+.024*y))
    local=.019*y+.055*min(trail,32)+1.6*math.exp(-((x-21)/11)**2-((y-30)/35)**2)+.52*fb(x,y,.12)+.5*fb(x,y,.032)+.10*fb(x,y,1.3)+.035*fb(x,y,5)
    if trail<1.7:
        t=math.exp(-(trail/1.15)**4);local=local*(1-.75*t)+(.022*y+.1*fb(x,y,.16))*t*.75
    blend=max(0,min(1,((x*x+(y*.8)**2)**.5-75)/230));blend=blend*blend*(3-2*blend)
    return local*(1-blend)+macro(x,y)*blend
ob=bpy.data.objects['Everest massif | Copernicus measured 30m elevations']
verts=[v.co.copy() for v in ob.data.vertices]
for v in verts:
    if -390<v.x<390 and -290<v.y<490:
        v.z=surface(v.x,v.y)-5
faces=[]
for j in range(rows-1):
    for i in range(cols-1):
        a=j*cols+i;faces.append((a,a+1,a+cols+1,a+cols))
me=bpy.data.meshes.new('Continuous elevation terrain with recessed foreground support')
me.from_pydata(verts,[],faces);me.materials.append(ob.data.materials[0]);me.update()
for p in me.polygons:p.use_smooth=True
old=ob.data;ob.data=me;bpy.data.meshes.remove(old)
# Snow grit on the ice receives fine shadows instead of only broad color variation.
ice=bpy.data.materials['ICE • blue glacier core / wind-eroded opaque crust']
n=ice.node_tree.nodes
n['Bump'].inputs['Distance'].default_value=.19
n['Vector Math'].inputs[1].default_value=(.7,.6,4.5)
# Focus on the first few dozen metres of the trail.
cam=scene.camera;cam.data.lens=31
cam.rotation_euler=(Vector((1.0,105,11))-cam.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'outputs/everest-rongbuk-study.blend'))
print('Continuous terrain support completed; no open boundary in the mountain mesh')
