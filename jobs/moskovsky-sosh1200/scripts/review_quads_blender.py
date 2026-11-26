"""QUAD review copy of a Ground OBJ (moskovsky-sosh1200 ground-npm v001) - review only, never the delivery.

Pattern: n/a | new-case: stage 3 (quads) is a skeleton GAP; for the user's 3ds Max QUAD review [D270] this joins
coplanar triangle pairs (Blender tris_to_quads, delimited by UV and material, so no UDIM/ID change) and writes a
new FBX + .blend. The triangulated OBJ from `agr ground site` stays the source of truth.

usage: blender -b --factory-startup --python review_quads_blender.py -- IN.obj NEW_OUT_DIR NAME [EXTRA.obj ...]
(EXTRA objects, e.g. the v002 markings mesh, are imported as their own objects and keep their names)
"""
import json
import math
import sys
from pathlib import Path

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
src, out, name = args[:3]
extra = args[3:]
out = Path(out)
out.mkdir(parents=True, exist_ok=False)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system = "METRIC"
bpy.context.scene.unit_settings.scale_length = 1.0
bpy.ops.wm.obj_import(filepath=src, forward_axis="Y", up_axis="Z")
objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
for x in extra:
    bpy.ops.wm.obj_import(filepath=x, forward_axis="Y", up_axis="Z")
others = [o for o in bpy.context.scene.objects if o.type == "MESH" and o not in objs]
before = {o.name: len(o.data.polygons) for o in objs}
for o in objs:
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.tris_convert_to_quads(face_threshold=math.radians(1), shape_threshold=math.radians(180),
                                       uvs=True, materials=True, seam=False, sharp=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    o.name = name
# one material-ID space for the D420 ID-colour copy: extra objects carry the ground slots first, own slots after
ground_mats = [m for m in objs[0].data.materials] if objs else []
for o in others:
    own = [m for m in o.data.materials]
    idx = [p.material_index for p in o.data.polygons]
    o.data.materials.clear()
    for m in ground_mats + own:
        o.data.materials.append(m)
    for p, i in zip(o.data.polygons, idx):
        p.material_index = i + len(ground_mats)
stats = {}
for o in objs + others:
    sizes = [len(p.vertices) for p in o.data.polygons]
    stats[o.name] = {"faces": len(sizes), "quads": sizes.count(4), "tris": sizes.count(3),
                     "triangles_equivalent": sum(s - 2 for s in sizes), "materials": len(o.data.materials)}
bpy.ops.wm.save_as_mainfile(filepath=str(out / f"{name}_review_quad.blend"))
bpy.ops.export_scene.fbx(filepath=str(out / f"{name}_review_quad.fbx"), use_selection=False, apply_unit_scale=True,
                         apply_scale_options="FBX_SCALE_UNITS", axis_forward="Y", axis_up="Z", path_mode="COPY",
                         embed_textures=False, mesh_smooth_type="FACE", use_triangles=False)
(out / "review-quads.json").write_text(json.dumps({"source_obj": src, "before_faces": before, "after": stats,
                                                    "note": "review copy only; delivery stays the triangulated OBJ"},
                                                   indent=1), encoding="utf-8")
print("REVIEW_QUADS", json.dumps(stats))
