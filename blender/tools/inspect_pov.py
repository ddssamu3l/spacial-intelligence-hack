import bpy, json
p=bpy.context.preferences.inputs
print('INPUTS',[(x.identifier,str(getattr(p,x.identifier))) for x in p.bl_rna.properties if 'walk' in x.identifier or 'navigation' in x.identifier])
w=p.walk_navigation
print('WALK',[(x.identifier,str(getattr(w,x.identifier))) for x in w.bl_rna.properties])
print('SCENE',bpy.context.scene.name,'ENGINE',bpy.context.scene.render.engine)
print('SCREENS',[(a.type,a.width,a.height) for a in bpy.context.screen.areas])
print('ENGINES',[(i.identifier,i.name) for i in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items])
print('EEVEE',[(p.identifier) for p in bpy.context.scene.eevee.bl_rna.properties] if hasattr(bpy.context.scene,'eevee') else 'absent')
