import bpy
s=bpy.context.scene
print('Scene',s.name,'objects',len(s.objects))
sky=s.world.node_tree.nodes.new('ShaderNodeTexSky')
print('Sky properties',[(p.identifier,p.type) for p in sky.bl_rna.properties])
print('Color looks',[(x.identifier) for x in s.view_settings.bl_rna.properties['look'].enum_items])
print('Shader nodes ready')
