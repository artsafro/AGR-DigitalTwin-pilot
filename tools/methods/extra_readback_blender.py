"""Methods-catalog readback extras (material slots per polygon, loop triangles), factory Blender.

Pattern: new-case: per-polygon material index and triangle readback for tools/methods/run_variant.py (#706).

    blender --background --factory-startup --python-exit-code 1 \\
        --python tools/methods/extra_readback_blender.py -- <model.fbx> <extra.json>

Facts only; never writes the source. Per mesh: slot material names (None = empty slot), polygon count per
material_index, the material_index of every polygon (readback polygon order), and the loop triangles (vertex indices in the same order as fbx_readback.py's
face_geometry.vertices).
"""
import json
import sys
from pathlib import Path

import bpy

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if len(args) != 2:
    raise SystemExit("usage: ... -- <model.fbx> <extra.json>")
source, out = Path(args[0]).resolve(), Path(args[1]).resolve()
if source == out:
    raise SystemExit("output aliases the input")
report = {"source": str(source), "ok": False, "meshes": {}}
try:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(source))
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        me = obj.data
        me.calc_loop_triangles()
        used = {}
        for poly in me.polygons:
            used[str(poly.material_index)] = used.get(str(poly.material_index), 0) + 1
        report["meshes"][obj.name] = {
            "slots": [s.material.name if s.material else None for s in obj.material_slots],
            "polygons_by_material_index": used,
            "polygon_material_index": [int(p.material_index) for p in me.polygons],
            "tris": [[int(i) for i in tri.vertices] for tri in me.loop_triangles],
        }
    report["ok"] = bool(report["meshes"])
except Exception as exc:  # report, never hide
    report["error"] = f"{type(exc).__name__}: {exc}"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report), encoding="utf-8")
print("METHODS_EXTRA", report["ok"])
sys.exit(0 if report["ok"] else 2)
