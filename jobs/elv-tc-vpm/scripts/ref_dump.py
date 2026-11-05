"""elv-tc-vpm: dump objects of the clean reference scene east of x_min (name, category, bbox, tris, vertices).

blender -b elv_ref_clean_v001.blend --python ref_dump.py -- <out.json> [x_min]
Read-only on the scene. Output feeds measure_pilot.py (plain Python).
"""
import bpy, sys, json, os

argv = sys.argv[sys.argv.index("--") + 1:]
out = argv[0]; x_min = float(argv[1]) if len(argv) > 1 else 30.0
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
rows = []
for o in bpy.context.scene.objects:
    if o.type != "MESH" or not o.data.vertices:
        continue
    vs = [tuple(round(c, 4) for c in v.co) for v in o.data.vertices]
    mn = [min(v[i] for v in vs) for i in range(3)]; mx = [max(v[i] for v in vs) for i in range(3)]
    if mx[0] < x_min:
        continue
    o.data.calc_loop_triangles()
    rows.append(dict(name=o.name, cat=o.get("ref_category", "?"), mn=mn, mx=mx, t=len(o.data.loop_triangles), v=vs))
json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False)
print("DUMPED", len(rows))
