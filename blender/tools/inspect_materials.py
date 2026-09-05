import bpy
print('Scene objects',len(bpy.context.scene.objects))
for name in ['MOUNTAIN • sedimentary bands, snow gullies & exposed ridges','ICE • blue glacier core / wind-eroded opaque crust']:
    m=bpy.data.materials.get(name)
    print(name,[(n.name,n.type) for n in m.node_tree.nodes])
print('Camera',tuple(bpy.context.scene.camera.location),tuple(bpy.context.scene.camera.rotation_euler))
o=bpy.data.objects.get('Everest massif | Copernicus measured 30m elevations')
print('Mountain normals',[(tuple(p.center),tuple(p.normal)) for p in list(o.data.polygons)[::60000]])
