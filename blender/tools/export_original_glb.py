"""Bake the restored scene and export one GLB; run in background Blender.

The source blend is never saved by this script. Temporary bake images are
embedded in the GLB and are not required to open it.
"""
import bpy
import json
import math
import os
import tempfile
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'exports'
OUT.mkdir(exist_ok=True)
scene = next(s for s in bpy.data.scenes if s.name.startswith('EVEREST |'))
bpy.context.window.scene = scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 8
scene.render.bake.use_pass_direct = False
scene.render.bake.use_pass_indirect = False
scene.render.bake.use_pass_color = True
scene.render.bake.margin = 12
try:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'METAL'
    prefs.get_devices()
    for device in prefs.devices:
        device.use = device.type == 'METAL'
    scene.cycles.device = 'GPU'
except Exception:
    scene.cycles.device = 'CPU'

original_objects = [o for o in scene.objects if not o.hide_render]
groups = {}
for ob in original_objects:
    if ob.type not in {'MESH', 'CURVE'}:
        continue
    key = (ob.data.name, tuple((m.type, getattr(m, 'levels', 0), getattr(m, 'strength', 0)) for m in ob.modifiers))
    groups.setdefault(key, []).append(ob)

cache = os.environ.get('EVEREST_GLB_BAKE_CACHE')
temporary = None if cache else tempfile.TemporaryDirectory(prefix='everest-glb-bake-')
bake_dir = Path(cache or temporary.name)
bake_dir.mkdir(parents=True, exist_ok=True)
export_collection = bpy.data.collections.new('Original Everest — complete GLB')
scene.collection.children.link(export_collection)
export_objects = []
report = {'source': 'outputs/everest-before-realism.blend', 'original_objects': len(original_objects), 'groups': [],
          'units': 'meters', 'coordinate_system': 'glTF right-handed Y-up',
          'source_to_gltf': '(x, y, z) -> (x, z, -y)',
          'attribution': 'Contains modified Copernicus DEM GLO-30 (2021), European Union, DLR and Airbus. Poly Haven textures: CC0.',
          'limitations': 'Shared rock instances reuse a prototype material bake. Renderer tone mapping and environment lighting may differ from Cycles. Visual terrain, not validated robot collisions.'}

for ob in original_objects:
    if ob.type in {'MESH', 'CURVE'}:
        ob.hide_render = True
deps = bpy.context.evaluated_depsgraph_get()
for number, objects in enumerate(groups.values()):
    source = objects[0]
    evaluated = source.evaluated_get(deps)
    mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=deps)
    bake_object = bpy.data.objects.new(source.name + ' — export', mesh)
    export_collection.objects.link(bake_object)
    bake_object.matrix_world = source.matrix_world.copy()
    # Isolate the bake target. Other objects cannot alter an albedo/normal bake.
    bpy.ops.object.select_all(action='DESELECT')
    bake_object.select_set(True)
    bpy.context.view_layer.objects.active = bake_object
    bake_object.hide_set(False)
    procedural = any(m and len(m.node_tree.nodes) > 2 for m in mesh.materials if m.use_nodes)
    if procedural:
        for i, material in enumerate(list(mesh.materials)):
            mesh.materials[i] = material.copy()
        if not mesh.uv_layers:
            mesh.uv_layers.new(name='Baked UV')
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        if source.name.startswith(('Foreground', 'Everest massif', 'Transition')):
            bpy.ops.object.mode_set(mode='OBJECT')
            xs = [v.co.x for v in mesh.vertices]
            ys = [v.co.y for v in mesh.vertices]
            xmin, ymin = min(xs), min(ys)
            width, height = max(xs)-xmin, max(ys)-ymin
            for loop in mesh.loops:
                v = mesh.vertices[loop.vertex_index].co
                mesh.uv_layers.active.data[loop.index].uv = ((v.x-xmin)/max(width, .01)*.996+.002, (v.y-ymin)/max(height, .01)*.996+.002)
        else:
            bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=.02)
            bpy.ops.object.mode_set(mode='OBJECT')
        size = 4096 if source.name.startswith(('Foreground', 'Everest massif', 'Transition')) else 1024 if source.name.startswith(('Serac', 'Ice', 'Fractured')) else 512
        images = {}
        target_nodes = []
        for mat in mesh.materials:
            node = mat.node_tree.nodes.new('ShaderNodeTexImage')
            mat.node_tree.nodes.active = node
            target_nodes.append(node)
        for channel, bake_type in [('color', 'DIFFUSE'), ('normal', 'NORMAL'), ('roughness', 'ROUGHNESS')]:
            cached = bake_dir / f'{number:03d}-{channel}.png'
            if cached.exists():
                image = bpy.data.images.load(str(cached), check_existing=False)
                image.colorspace_settings.name = 'sRGB' if channel == 'color' else 'Non-Color'
                image.pack(); images[channel] = image
                continue
            image = bpy.data.images.new(f'Everest {number:03d} {channel}', width=size, height=size, alpha=False)
            image.colorspace_settings.name = 'sRGB' if channel == 'color' else 'Non-Color'
            for node in target_nodes:
                node.image = image
            bpy.ops.object.bake(type=bake_type)
            image.filepath_raw = str(bake_dir / f'{number:03d}-{channel}.png')
            image.file_format = 'PNG'
            image.save()
            image.pack()
            images[channel] = image
        mat = bpy.data.materials.new(f'Baked original • {source.name}')
        mat.use_nodes = True
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        bs = nodes.get('Principled BSDF')
        bs.inputs['Metallic'].default_value = 0
        for channel, socket in [('color', 'Base Color'), ('roughness', 'Roughness')]:
            node = nodes.new('ShaderNodeTexImage'); node.image = images[channel]
            links.new(node.outputs['Color'], bs.inputs[socket])
        node = nodes.new('ShaderNodeTexImage'); node.image = images['normal']
        normal = nodes.new('ShaderNodeNormalMap')
        links.new(node.outputs['Color'], normal.inputs['Color'])
        links.new(normal.outputs['Normal'], bs.inputs['Normal'])
        mesh.materials.clear(); mesh.materials.append(mat)
        for polygon in mesh.polygons:
            polygon.material_index = 0
    for i, original in enumerate(objects):
        ob = bake_object if i == 0 else bpy.data.objects.new(original.name, mesh)
        if i:
            export_collection.objects.link(ob)
        ob.name = original.name + ' [GLB]'
        ob.matrix_world = original.matrix_world.copy()
        ob.hide_render = True
        export_objects.append(ob)
    report['groups'].append({'name': source.name, 'instances': len(objects), 'vertices': len(mesh.vertices), 'baked': procedural})
    print(f'BAKED {number+1}/{len(groups)} {source.name} instances={len(objects)}', flush=True)

# glTF has no world shader. A separate inward-facing unlit dome keeps the blue
# sky with the asset, while the exported sun remains an actual directional light.
bpy.ops.object.select_all(action='DESELECT')
bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=45000)
sky = bpy.context.object; sky.name = 'Original blue alpine sky (unlit backdrop)'
for col in list(sky.users_collection): col.objects.unlink(sky)
export_collection.objects.link(sky)
sky_mat = bpy.data.materials.new('Original visible alpine sky')
sky_mat.use_nodes = True
nodes, links = sky_mat.node_tree.nodes, sky_mat.node_tree.links
nodes.clear()
out = nodes.new('ShaderNodeOutputMaterial'); emission = nodes.new('ShaderNodeEmission')
emission.inputs['Color'].default_value = (.0144, .0612, .1169, 1)
links.new(emission.outputs[0], out.inputs['Surface'])
sky_mat.use_backface_culling = False; sky.data.materials.append(sky_mat)
export_objects.append(sky)
for ob in original_objects:
    if ob.type in {'CAMERA', 'LIGHT'}:
        export_objects.append(ob)
bpy.ops.object.select_all(action='DESELECT')
for ob in export_objects:
    ob.hide_render = False; ob.hide_set(False); ob.select_set(True)
scene['asset_attribution'] = report['attribution']
scene['asset_limitations'] = report['limitations']
destination = OUT / 'everest-original-full.glb'
bpy.ops.export_scene.gltf(filepath=str(destination), export_format='GLB', use_selection=True, use_active_scene=True,
    export_apply=False, export_yup=True, export_cameras=True, export_lights=True,
    export_animations=False, export_extras=True, export_materials='EXPORT',
    export_image_format='AUTO', export_tangents=True)
report['exported_objects'] = len(export_objects)
report['file'] = destination.name
report['bytes'] = destination.stat().st_size
(OUT / 'everest-original-full.json').write_text(json.dumps(report, indent=2))
print('EXPORT_COMPLETE', json.dumps({'file': str(destination), 'bytes': report['bytes'], 'objects': len(export_objects)}), flush=True)
if temporary:
    temporary.cleanup()
