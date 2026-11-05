"""elv-tc-vpm build-v007 probe (read only): what lies behind every MainGlass face of build-v006b.

blender -b <elv_full_v006b.blend> --python probe_glass_v007.py -- <out.json>
Per glass face: part (attribute part_idx of the glass object), centre, normal, area, and a ray from the centre
inward (-normal) through Main and Glass: first hit distance / part / whether the hit is a front or back face.
Grouped summary per part. Never saves.
"""
import bpy, sys, os, json
from mathutils.bvhtree import BVHTree

out = sys.argv[sys.argv.index("--") + 1:][0]
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
STEM = "SM_Elevatornaya_1A"
om, og = bpy.data.objects[STEM + "_Main"], bpy.data.objects[STEM + "_MainGlass"]
pm, pg = json.loads(om["part_ids"]), json.loads(og["part_ids"])
am, ag = om.data.attributes["part_idx"], og.data.attributes["part_idx"]
vm = [v.co.copy() for v in om.data.vertices]
fm = [list(p.vertices) for p in om.data.polygons]
bm_ = BVHTree.FromPolygons(vm, fm)
rows = []
for p in og.data.polygons:
    c, n = p.center.copy(), p.normal.copy()
    hit = bm_.ray_cast(c - n * 0.002, -n, 5.0)
    h = None
    if hit[0] is not None:
        fi = hit[2]
        mp = om.data.polygons[fi]
        h = {"d": round(hit[3], 3), "part": pm[am.data[fi].value], "id": mp.material_index + 1,
             "front": bool(mp.normal.dot(n) > 0)}
    rows.append({"i": p.index, "part": pg[ag.data[p.index].value], "c": [round(x, 3) for x in c],
                 "n": [round(x, 3) for x in n], "a": round(p.area, 3), "hit": h})
summ = {}
for r in rows:
    s = summ.setdefault(r["part"], {"faces": 0, "area": 0.0, "no_hit_5m": 0, "hit_back": 0, "hit_front": 0, "hit_parts": {}})
    s["faces"] += 1
    s["area"] = round(s["area"] + r["a"], 2)
    if r["hit"] is None:
        s["no_hit_5m"] += 1
    else:
        s["hit_front" if r["hit"]["front"] else "hit_back"] += 1
        k = "%s/ID%02d/%s" % (r["hit"]["part"], r["hit"]["id"], "front" if r["hit"]["front"] else "back")
        s["hit_parts"][k] = s["hit_parts"].get(k, 0) + 1
json.dump({"summary": summ, "faces": rows}, open(out, "w", encoding="utf-8"), indent=1)
print("SUMMARY", json.dumps(summ, indent=1))
