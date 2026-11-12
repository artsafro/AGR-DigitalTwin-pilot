"""new-case: KPP1 MSK-77 fit input (#1255) - dump world-space mesh vertices of one FBX (headless Blender).

blender --background --factory-startup --python dump_vertices.py -- <in.fbx> <out.npz> <out.json>
Never overwrites (refuses an existing output). Writes per mesh object: world vertices `o<i>` (float64, metres,
Blender Z-up after the FBX importer's axis conversion), triangles `t<i>` and a JSON summary (names, materials, bbox, counts).
"""
import json
import sys
from pathlib import Path

import bpy
import numpy as np

src, out_npz, out_json = map(Path, sys.argv[sys.argv.index("--") + 1:][:3])
for p in (out_npz, out_json):
    if p.exists() or p.resolve() == src.resolve():
        raise SystemExit(f"refusing to overwrite: {p}")
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(src))
dg = bpy.context.evaluated_depsgraph_get()
arrays, summary = {}, []
for i, ob in enumerate(sorted((o for o in bpy.context.scene.objects if o.type == "MESH"), key=lambda o: o.name)):
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    m = np.array(ob.matrix_world)
    w = co @ m[:3, :3].T + m[:3, 3]
    key = f"o{i:04d}"
    arrays[key] = w
    me.calc_loop_triangles()
    tri = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", tri)
    arrays[f"t{i:04d}"] = tri.reshape(-1, 3)
    summary.append({"key": key, "name": ob.name, "verts": len(w), "faces": len(me.polygons),
                    "materials": [s.material.name if s.material else None for s in ob.material_slots],
                    "location": list(ob.location), "rotation_euler": list(ob.rotation_euler),
                    "scale": list(ob.scale),
                    "min": w.min(0).tolist() if len(w) else None, "max": w.max(0).tolist() if len(w) else None})
    ev.to_mesh_clear()
np.savez(out_npz, **arrays)
out_json.write_text(json.dumps({"source": str(src), "unit_scale": bpy.context.scene.unit_settings.scale_length,
                                "objects": summary}, ensure_ascii=False, indent=1), encoding="utf-8")
print("DUMPED", len(summary))
