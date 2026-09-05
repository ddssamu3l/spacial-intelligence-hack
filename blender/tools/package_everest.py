import bpy, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
scene=bpy.context.scene
from mathutils import Vector
scene.camera.data.lens=28
scene.camera.rotation_euler=(Vector((0,125,17))-scene.camera.location).to_track_quat('-Z','Y').to_euler()
scene.render.resolution_x=3840;scene.render.resolution_y=2160;scene.render.resolution_percentage=100
scene.cycles.samples=128;scene.cycles.adaptive_threshold=.015
scene.render.filepath=str(ROOT/'outputs/everest-rongbuk-4k.png')
scene['visual_study_status']='First visual prototype. Foreground reconstructed; not a surveyed digital twin or robot-ready collision environment.'
scene['data_attribution']='Contains modified Copernicus DEM GLO-30 (2021). Terrain data source: European Union, DLR and Airbus. Texture photographs: Poly Haven CC0.'
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'outputs/everest-rongbuk-study.blend'))
report={'scene':scene.name,'objects':len(scene.objects),'render':[3840,2160],'samples':128,'packed_images':[im.name for im in bpy.data.images if im.packed_file],'camera':list(scene.camera.location),'foreground':'reconstructed moraine and glacier, metre units','backdrop':'Copernicus GLO-30 with local transition adjusted','not_yet_implemented':['robot','collision shapes','locomotion policy','surveyed close-range geometry']}
(ROOT/'outputs/scene-manifest.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'saved':str(ROOT/'outputs/everest-rongbuk-study.blend'),'packed_images':len(report['packed_images']),'resolution':report['render']}))
