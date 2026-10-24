"""Dump the mesh objects of an FBX or .blend for the overlap gate `dt qa xview` (#527); read-only on the source.

Usage (via dt_ai.core.blender_runner.run_blender, Blender 5.1.2):
  blender -b --factory-startup --python tools/blender/xview_dump.py -- <src.fbx|.blend> <out.npz> <manifest.json>

Per mesh object of the active scene (evaluated: modifiers applied), sorted by name: vertices in place in float64
(float32 local co @ matrix_world in float64, as review #514 XCHECK), the polygon loops and the object location
(matrix_world translation), all in raw Blender units: the manifest carries unit_system and unit_scale
(scene.unit_settings.scale_length, a float32: stored as its shortest decimal, 0.001 not 0.0010000000475,
raw value in unit_scale_float32) and the gate converts to metres (dt_ai.ops.xview_gate.to_metres). Non-mesh objects go to `dropped` with the reason. NPZ keys: names, v<i>, lt<i>, lv<i>,
loc<i> (dt_ai.ops.xview_gate.load_npz). The FBX import runs into an empty factory scene; the .blend is opened, never
saved.
Pattern: none | new-case: Blender dump of FBX/.blend mesh objects for the overlap gate (#527).
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
        me.polygons.foreach_get("loop_total", lt)
        me.polygons.foreach_get("loop_start", ls)
        loops = np.zeros(len(me.loops), np.int64)
        me.loops.foreach_get("vertex_index", loops)
        order = np.repeat(ls - (np.cumsum(lt) - lt), lt) + np.arange(int(lt.sum()))
        i = len(names)
        data[f"v{i}"], data[f"lt{i}"], data[f"lv{i}"] = v, lt, loops[order]
        data[f"loc{i}"] = mw[:3, 3].copy()
        names.append(o.name)
        objects.append({"name": o.name, "vertices": len(v), "polygons": n, "location": mw[:3, 3].tolist(),
                        "parent": o.parent.name if o.parent else None})
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
print("XVIEW_DUMP", len(names), "mesh objects,", len(dropped), "dropped")
