"""elv-tc-vpm customer-clarify-v001: world vertices of the customer's SRC_Накладки_MAN02 outlines, in OUR frame.

blender -b --disable-autoexec <copy.blend> --python clarify_nakl_verts_v001.py -- <out.json>
Each object is a 4-vertex outline (0 faces) of a Revit '(SC)-Batten*' instance. Never saves the blend.
"""
import bpy, sys, os, json
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
out = argv[0]
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
PIVOT = Vector((9676.3555, -7135.6997, 167.65))
SHIFT = Vector((-0.064, 0.578, 0.0))
rows = []
for o in bpy.data.collections["SRC_Накладки_MAN02"].all_objects:
    vs = [list(round(c, 4) for c in (o.matrix_world @ v.co - PIVOT + SHIFT)) for v in o.data.vertices]
    rows.append({"name": o.name, "verts": vs, "edges": [list(e.vertices) for e in o.data.edges],
                 "fam": str(o.get("agr_fam", "")), "ral": str(o.get("agr_ral", "")),
                 "depth": float(o.get("agr_depth", 0) or 0)})
json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("DONE", len(rows))
