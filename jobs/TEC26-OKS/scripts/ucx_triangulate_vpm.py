"""new-case: TEC26 #1016 - AGR Tools ucx.triangulate on a COPY of a delivered VPM export scene, FBX re-export.

Usage: blender --background --factory-startup --python ucx_triangulate_vpm.py -- \
    <VPM_export_tri.blend> <new package dir>/SM_<A> <protected dir>

Opens the export scene saved by export_vpm.py (read only, never saved back), runs the ucx.triangulate core
(ucx_tri_core.triangulate_piece -> adapters/max/agr_tools/geom_core.py::ucx_plan) on every UCX_ object, keeps
every other object as exported, and writes SM_<A>.fbx with the export_vpm.py FBX arguments (FBX_ARGS, kept equal by
tests/test_tec26_ac08_ucx_tri.py) plus <package dir>/../ucx_triangulate.json. Fails (exit 1, no FBX) when a
piece is not closed and convex after triangulation, when there is no UCX, when a UCX has a non-identity
transform, or when the output exists / aliases the input / lies in the protected (accepted) folder.
"""
import bpy, sys, os, json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ucx_tri_core as core  # noqa: E402

FBX_ARGS = dict(use_selection=True, object_types={"MESH"},
                axis_forward="Y", axis_up="Z", apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                global_scale=1.0, bake_space_transform=False, use_mesh_modifiers=False,
                mesh_smooth_type="FACE", use_triangles=False, use_custom_props=False,
                add_leaf_bones=False, bake_anim=False, path_mode="STRIP", embed_textures=False)

src, pkg, protected = sys.argv[sys.argv.index("--") + 1:][:3]
core.check_paths([src], pkg, [protected])
bpy.ops.wm.open_mainfile(filepath=src)
sc = bpy.context.scene
ucx = sorted((o for o in sc.objects if o.type == "MESH" and o.name.startswith("UCX_")), key=lambda o: o.name)
if not ucx:
    sys.exit("no UCX_ object in " + src)
mains = [o for o in sc.objects if o.type == "MESH" and o.name.startswith("SM_")]
address = mains[0].name[3:].rsplit("_", 1)[0] if mains else None
pieces = []
for o in ucx:
    if any(abs(o.matrix_world[i][j] - (1.0 if i == j else 0.0)) > 1e-9 for i in range(4) for j in range(4)):
        sys.exit(f"{o.name}: non-identity transform, refused")
    me = o.data
    pts = [tuple(v.co) for v in me.vertices]
    polys = [list(p.vertices) for p in me.polygons]
    got = core.triangulate_piece(o.name, pts, polys)  # raises -> Blender exit code 1, nothing exported
    me.clear_geometry()
    me.from_pydata(pts, [], [tuple(t) for t in got["tris"]])
    me.update()
    me.shade_flat()
    if len(me.vertices) != got["vertices"] or any(len(p.vertices) != 3 for p in me.polygons):
        sys.exit(f"{o.name}: mesh rebuild changed the vertex count or left an n-gon")
    got.pop("tris")
    pieces.append(got)
deliver = [o for o in sc.objects if o.type == "MESH" and (o.name.startswith("SM_") or o.name.startswith("UCX_"))]
for o in sc.objects:
    o.select_set(o in deliver)
os.makedirs(pkg)
fbx = os.path.join(pkg, os.path.basename(os.path.normpath(pkg)) + ".fbx")
bpy.ops.export_scene.fbx(filepath=fbx, **FBX_ARGS)
rep = {"tool": "ucx.triangulate (AGR Tools geom_core.ucx_plan, nonconvex=report)", "source": src, "fbx": fbx,
       "address": address, "objects": sorted(o.name for o in deliver), "ucx": pieces}
with open(os.path.join(pkg, "..", "ucx_triangulate.json"), "x", encoding="utf-8") as fh:
    json.dump(rep, fh, indent=1)
print("UCX-TRI", json.dumps({"fbx": fbx, "pieces": [(p["name"], p["action"], p["after"]) for p in pieces]}))
