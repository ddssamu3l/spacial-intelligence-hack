"""Render the saved scene; called in a background Blender process launched by MCP."""
import bpy
import json
from pathlib import Path
import sys
import time

root=Path(__file__).resolve().parents[1]
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else ['preview']
mode=args[0]
scene=next(s for s in bpy.data.scenes if s.name.startswith('EVEREST |'))
bpy.context.window.scene=scene
scene.render.engine='CYCLES'
try:
    prefs=bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type='METAL'
    prefs.get_devices()
    for d in prefs.devices:
        d.use=d.type=='METAL'
    scene.cycles.device='GPU'
except Exception:
    scene.cycles.device='CPU'
scene.cycles.use_denoising=True
scene.render.resolution_percentage=100
if mode=='preview':
    scene.render.resolution_x=1280
    scene.render.resolution_y=720
    scene.cycles.samples=24
    scene.cycles.adaptive_threshold=.08
    scene.render.filepath=str(root/'outputs/everest-preview.png')
else:
    scene.render.resolution_x=3840
    scene.render.resolution_y=2160
    scene.cycles.samples=128
    scene.cycles.adaptive_threshold=.015
    scene.render.filepath=str(root/'outputs/everest-rongbuk-4k.png')
start=time.time()
bpy.ops.render.render(write_still=True)
(root/'outputs'/f'{mode}-complete.json').write_text(json.dumps({'seconds':time.time()-start,'image':scene.render.filepath,'size':[scene.render.resolution_x,scene.render.resolution_y]}))
