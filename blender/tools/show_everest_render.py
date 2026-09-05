import bpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'outputs/everest-rongbuk-4k.png'
im=bpy.data.images.load(str(path),check_existing=True)
im.name='Everest • finished 4K visual study'
areas=[a for a in bpy.context.screen.areas if a.type in {'VIEW_3D','IMAGE_EDITOR'}]
if areas:
    area=max(areas,key=lambda a:a.width*a.height)
    area.type='IMAGE_EDITOR';area.spaces.active.image=im
    region=next(r for r in area.regions if r.type=='WINDOW')
    with bpy.context.temp_override(area=area,region=region):
        bpy.ops.image.view_all(fit_view=True)
print('Displayed finished 4K render in Blender; the saved editable scene is unchanged')
