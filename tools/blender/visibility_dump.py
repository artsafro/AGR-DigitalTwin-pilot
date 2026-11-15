"""Dump the mesh objects of an FBX or .blend with per-face materials for `dt qa visibility` (#1447); read-only.

Usage (via dt_ai.core.blender_runner.run_blender):
  blender -b --factory-startup --python tools/blender/visibility_dump.py -- <src.fbx|.blend> <out.npz> <manifest.json>

The xview dump (tools/blender/xview_dump.py) plus, per object, `mi<i>` (material slot index per polygon) and `mn<i>`
(slot material names; an empty slot is ""). Only objects visible in the viewport (`visible_get()`) are dumped;
hidden ones go to `dropped` with the reason. Raw Blender units; the manifest carries unit_system and unit_scale and
dt_ai.ops.visibility_gate.run converts to metres. The .blend is opened, never saved.
Pattern: none | new-case: Blender dump with per-face materials for the visibility gate (#1447).
"""
import json
import sys

import bpy
import numpy as np

src, npz_path, manifest_path = sys.argv[sys.argv.index("--") + 1:][:3]
if src.lower().endswith(".blend"):
    bpy.ops.wm.open_mainfile(filepath=src, load_ui=False)
else:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=src)

scene = bpy.context.scene
dg = bpy.context.evaluated_depsgraph_get()
data = {}
names, objects, dropped = [], [], []
for o in sorted(scene.objects, key=lambda x: x.name):
    if o.type != "MESH":
        dropped.append({"name": o.name, "type": o.type, "reason": "not a mesh object"})
        continue
    if not o.visible_get():
        dropped.append({"name": o.name, "type": o.type, "reason": "hidden in the viewport"})
        continue
    eo = o.evaluated_get(dg)
    me = eo.to_mesh()
    try:
        co = np.zeros(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", co)
        mw = np.array(o.matrix_world, dtype=np.float64)
        v = co.reshape(-1, 3).astype(np.float64) @ mw[:3, :3].T + mw[:3, 3]
        n = len(me.polygons)
        lt = np.zeros(n, np.int64)
        ls = np.zeros(n, np.int64)
        mi = np.zeros(n, np.int64)
        me.polygons.foreach_get("loop_total", lt)
        me.polygons.foreach_get("loop_start", ls)
        me.polygons.foreach_get("material_index", mi)
        loops = np.zeros(len(me.loops), np.int64)
        me.loops.foreach_get("vertex_index", loops)
        order = np.repeat(ls - (np.cumsum(lt) - lt), lt) + np.arange(int(lt.sum()))
        slots = [m.name if m else "" for m in me.materials] or [""]
        i = len(names)
        data[f"v{i}"], data[f"lt{i}"], data[f"lv{i}"] = v, lt, loops[order]
        data[f"loc{i}"] = mw[:3, 3].copy()
        data[f"mi{i}"], data[f"mn{i}"] = mi, np.array(slots, dtype=str)
        names.append(o.name)
        objects.append({"name": o.name, "vertices": len(v), "polygons": n, "materials": slots,
                        "collections": [c.name for c in o.users_collection]})
    finally:
        eo.to_mesh_clear()

data["names"] = np.array(names, dtype=str)
with open(npz_path, "wb") as fh:
    np.savez(fh, **data)
with open(manifest_path, "w", encoding="utf-8") as fh:
    json.dump({"source": src, "blender": bpy.app.version_string, "scene": scene.name,
               "unit_system": scene.unit_settings.system,
               "unit_scale": float(str(np.float32(scene.unit_settings.scale_length))),
               "unit_scale_float32": scene.unit_settings.scale_length, "objects": objects, "dropped": dropped}, fh, indent=1)
print("VISIBILITY_DUMP", len(names), "mesh objects,", len(dropped), "dropped")
