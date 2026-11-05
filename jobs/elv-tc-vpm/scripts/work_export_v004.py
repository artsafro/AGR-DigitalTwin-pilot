"""elv-tc-vpm: non-triangulated WORK FBX next to delivery v004 [D197].

Same master, pivot offset, object / material names, material slots and UVs as delivery_export_v004.py, but the
faces stay as built (quads / n-gons) and no UCX: a file for the user to edit in 3ds Max. Not part of the package.

blender -b --factory-startup --disable-autoexec --python-exit-code 1 --python work_export_v004.py -- \
    <elv_full_v007_tex.blend> <out_dir>
Writes (never overwrites): <out_dir>/SM_Elevatornaya_Vl_1_A_001_work_quads.fbx, <out_dir>/work_meta_v004.json
"""
import json
import sys
from collections import Counter
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

STEM = "SM_Elevatornaya_Vl_1_A_001"
CENTRE = Vector((35.1000, -24.2535, 0.0))  # the fixed delivery pivot offset (delivery_export_v003/v004)

src, out_dir = sys.argv[sys.argv.index("--") + 1:][:2]
out_dir = Path(out_dir)
fbx_path = out_dir / f"{STEM}_work_quads.fbx"
meta_path = out_dir / "work_meta_v004.json"
for p in (fbx_path, meta_path):
    if p.exists():
        raise SystemExit(f"output exists, refusing to overwrite: {p}")
out_dir.mkdir(parents=True, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=src)
sc = bpy.context.scene
main = bpy.data.objects[f"{STEM}_Main"]
glass = bpy.data.objects[f"{STEM}_MainGlass"]
for o in (main, glass):
    if o.matrix_world != Matrix.Identity(4) or o.parent or o.modifiers:
        raise SystemExit(f"{o.name}: non-identity transform, parent or modifiers")

shift = Matrix.Translation(-CENTRE)
for o in (main, glass):
    o.data.transform(shift)
    for k in list(o.keys()):
        del o[k]
    for k in list(o.data.keys()):
        del o.data[k]
    for name in ("part_idx", "mat_id", "udim"):
        a = o.data.attributes.get(name)
        if a:
            o.data.attributes.remove(a)
    o.data.update()
for m in bpy.data.materials:
    for k in list(m.keys()):
        del m[k]
for o in sc.objects:
    o.select_set(o in (main, glass))

bpy.ops.export_scene.fbx(filepath=str(fbx_path), use_selection=True, object_types={"MESH"},
                         axis_forward="Y", axis_up="Z", apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                         global_scale=1.0, bake_space_transform=False, use_mesh_modifiers=False,
                         mesh_smooth_type="FACE", use_triangles=False, use_custom_props=False,
                         add_leaf_bones=False, bake_anim=False, path_mode="STRIP", embed_textures=False)


def degrees(o):
    c = Counter(min(len(p.vertices), 5) for p in o.data.polygons)
    return {"tris": c[3], "quads": c[4], "ngons": c[5], "faces": len(o.data.polygons)}


meta = {"source_blend": str(Path(src).resolve()), "fbx": str(fbx_path), "pivot_offset_subtracted_m": list(CENTRE),
        "triangulated": False, "ucx": "not included (delivery package only)",
        "main": degrees(main), "glass": degrees(glass), "blender": bpy.app.version_string}
meta_path.write_text(json.dumps(meta, indent=1), encoding="utf-8")
print("WORK_EXPORT", json.dumps(meta))
