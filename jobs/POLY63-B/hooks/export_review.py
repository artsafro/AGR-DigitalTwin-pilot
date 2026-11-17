"""new-case: body review export and native occlusion renders in Blender 4.4."""
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector

model, out, stem = sys.argv[sys.argv.index('--')+1:]; model, out = Path(model), Path(out).resolve()
d = json.loads(model.read_text(encoding='utf-8'))
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene
scene.unit_settings.system='METRIC'; scene.unit_settings.scale_length=1
mesh=bpy.data.meshes.new('63B Stage1'); mesh.from_pydata(d['vertices'],[],d['faces']); mesh.update()
assert not mesh.validate(verbose=True), 'unexpected topology repair'
ob=bpy.data.objects.new('POLY63B_Stage1_BODY',mesh); scene.collection.objects.link(ob)
for name,c in [('01_Ventfacade_regular',(.45,.58,.69,1)),('02_Render_return',(.65,.50,.38,1)),('03_Ventfacade_band',(.36,.45,.53,1))]:
    mat=bpy.data.materials.new(name); mat.diffuse_color=c; mesh.materials.append(mat)
for p,idx in zip(mesh.polygons,d['face_zones']): p.material_index=idx
ob.select_set(True); bpy.context.view_layer.objects.active=ob
for suffix in ('blend','fbx'):
    if (out/f'{stem}.{suffix}').exists(): raise FileExistsError(suffix)
bpy.ops.wm.save_as_mainfile(filepath=str(out/f'{stem}.blend'))
bpy.ops.export_scene.fbx(filepath=str(out/f'{stem}.fbx'),use_selection=True,object_types={'MESH'},axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',use_triangles=False,add_leaf_bones=False)

# Only the evidence scene has edge geometry; archive and FBX were written above.
wire=bpy.data.objects.new('review wires',mesh.copy()); scene.collection.objects.link(wire)
black=bpy.data.materials.new('wire'); black.diffuse_color=(.025,.036,.050,1)
wire.data.materials.clear(); wire.data.materials.append(black)
modifier=wire.modifiers.new('edges','WIREFRAME'); modifier.thickness=.009; modifier.use_even_offset=False
camera=bpy.data.objects.new('proof camera',bpy.data.cameras.new('proof camera')); scene.collection.objects.link(camera)
scene.camera=camera; camera.data.type='ORTHO'; camera.data.clip_end=400
scene.render.engine='BLENDER_WORKBENCH'; shade=scene.display.shading
shade.light='STUDIO'; shade.color_type='MATERIAL'; shade.show_shadows=True; shade.show_cavity=True
shade.cavity_type='BOTH'; shade.background_type='WORLD'; scene.world=bpy.data.worlds.new('proof world'); scene.world.color=(.75,.77,.79)
scene.render.resolution_x=1100; scene.render.resolution_y=900; scene.render.resolution_percentage=100
for label,center,direction,scale in [('iso',(75,19,28),(-.9,-1.5,.65),76),('corner',(91,30,34),(1.5,1.0,.1),23),('round',(69.8,2,18.5),(-.22,-1,.18),8.5)]:
    target=Vector(center); camera.location=target+Vector(direction).normalized()*80
    camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler(); camera.data.ortho_scale=scale
    scene.render.filepath=str(out/f'{label}.png'); bpy.ops.render.render(write_still=True)
