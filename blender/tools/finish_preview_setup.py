from pathlib import Path
import bpy, math, json
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs'
scene=bpy.context.scene
light_col=bpy.data.collections.get('06 • camera & daylight')
def height(x,y):
    return 0.0
path=ROOT/'tools/build_everest_preview.py'
source=path.read_text()
exec(compile(source[source.index("world=bpy.data.worlds.new"):],str(path),'exec'),globals())
