"""Blender: export the per-instance MAF + Flora objects of a prepared (pre-merge) site scene as a check FBX.

blender --background --factory-startup --python export_check_instances.py -- <prepared.blend> <rename.json> <out.fbx>

rename.json = {object name in the blend: name in the check FBX}. Only those objects are exported, each one
mesh, world transforms kept; a JSON report (<out.fbx>.json) lists exported and missing names. The delivery
FBX merges MAF/Flora per GND-11, so per-object checks (#185 MAF sizes, #191 Flora dimensions) need this
per-instance export of the same geometry before the merge. Opens the blend read-only (never saved).
"""
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

blend, rename_json, out_fbx = sys.argv[sys.argv.index("--") + 1:][:3]
bpy.ops.wm.open_mainfile(filepath=blend)
rename = json.loads(Path(rename_json).read_text(encoding="utf-8"))
keep, missing = [], []
for src, dst in rename.items():
    ob = bpy.data.objects.get(src)
    if ob is None or ob.type != "MESH":
        missing.append(src)
        continue
    keep.append((ob, dst))
keep_set = {ob.name for ob, _ in keep}
for ob in list(bpy.data.objects):
    if ob.name not in keep_set:
        bpy.data.objects.remove(ob, do_unlink=True)
for ob, dst in keep:
    # dimension checks read world AABBs: drop the placement rotation (keep location and scale) so a
    # rotated bench is measured along its own axes, not as its rotated envelope
    loc, _rot, scale = ob.matrix_world.decompose()
    ob.parent = None
    ob.matrix_world = Matrix.Translation(loc) @ Matrix.Diagonal(scale.to_4d())
    ob.hide_set(False)
    ob.hide_viewport = False
    ob.name = dst
    ob.data.name = dst
    ob.select_set(True)
bpy.ops.export_scene.fbx(filepath=out_fbx, use_selection=True, object_types={"MESH"}, apply_unit_scale=True,
                         bake_space_transform=False, mesh_smooth_type="FACE", use_mesh_modifiers=True)
Path(out_fbx + ".json").write_text(json.dumps({"blend": blend, "exported": len(keep), "missing": missing,
                                               "names": sorted(dst for _, dst in keep)}, indent=1),
                                   encoding="utf-8")
print(f"exported {len(keep)} missing {len(missing)}")
