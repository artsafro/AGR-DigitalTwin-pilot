"""elv-tc-vpm: export a triangulated CHECK copy of the pilot blend to FBX 7.4 (metres). Not a delivery export.

blender -b <pilot.blend> --python export_check_fbx.py -- <out.fbx>
"""
import bpy, sys, os

argv = sys.argv[sys.argv.index("--") + 1:]
out = os.path.abspath(argv[0])
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
for o in bpy.context.scene.objects:
    o.select_set(o.type == "MESH")
bpy.ops.export_scene.fbx(filepath=out, use_selection=True, object_types={"MESH"}, global_scale=1.0,
                         apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", use_triangles=True,
                         mesh_smooth_type="FACE", use_mesh_modifiers=True, add_leaf_bones=False,
                         bake_anim=False, path_mode="AUTO", embed_textures=False)
print("EXPORTED", out, os.path.getsize(out))
