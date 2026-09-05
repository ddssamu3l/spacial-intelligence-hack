"""Render the saved ascent at its entrance and halfway up, without changing it."""
import bpy
import json
import sys
import math
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
scene=next(s for s in bpy.data.scenes if s.name.startswith('EVEREST |'))
bpy.context.window.scene=scene
scene.render.engine='CYCLES'
prefs=bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type='METAL';prefs.get_devices()
for device in prefs.devices: device.use=device.type=='METAL'
scene.cycles.device='GPU';scene.cycles.samples=32;scene.cycles.use_denoising=True
scene.render.resolution_x=1600;scene.render.resolution_y=900;scene.render.resolution_percentage=100
route=json.loads(scene['trail_route'])
camera=scene.camera
original_position=camera.location.copy();original_rotation=camera.rotation_euler.copy()
views=[('approach',-16),('lower-ascent',68),('upper-ascent',235),('mountain-trail',610),('behind-start',-16)]
if '--' in sys.argv:
    requested=sys.argv[sys.argv.index('--')+1:]
    views=[view for view in views if view[0] in requested]
for name,y in views:
    camera.location=original_position;camera.rotation_euler=original_rotation
    if name=='behind-start':camera.rotation_euler.z+=math.pi
    if y!=-16:
        p=next(p for p in route if p['y']==y)
        target=next(p for p in route if p['y']==y+22)
        camera.location=(p['x'],p['y'],p['z']+1.75)
        camera.rotation_euler=(Vector((target['x'],target['y'],target['z']+1.3))-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(ROOT/f'outputs/everest-{name}.png')
    bpy.ops.render.render(write_still=True)
    print('RENDERED',name,flush=True)
