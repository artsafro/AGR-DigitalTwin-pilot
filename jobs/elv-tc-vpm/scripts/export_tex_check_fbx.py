"""elv-tc-vpm: CHECK export of the textured pilot to FBX 7.4 (metres, quads kept), texture paths stripped (reg p.30 §4.2).

blender -b <pilot_v002.blend> --python export_tex_check_fbx.py -- <out.fbx>
Image nodes are removed in memory only (the blend is never saved), so the FBX materials carry no texture paths.
Not a delivery export (no UCX, no package).
"""
import bpy, sys, os

argv = sys.argv[sys.argv.index("--") + 1:]
out = os.path.abspath(argv[0])
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
for m in bpy.data.materials:
    if m.use_nodes:
        for n in [n for n in m.node_tree.nodes if n.type == "TEX_IMAGE"]:
            m.node_tree.nodes.remove(n)
for o in bpy.context.scene.objects:
    o.select_set(o.type == "MESH")
bpy.ops.export_scene.fbx(filepath=out, use_selection=True, object_types={"MESH"}, global_scale=1.0,
                         apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", use_triangles=False,
                         mesh_smooth_type="FACE", use_mesh_modifiers=True, add_leaf_bones=False,
                         bake_anim=False, path_mode="STRIP", embed_textures=False)
print("EXPORTED", out, os.path.getsize(out))
