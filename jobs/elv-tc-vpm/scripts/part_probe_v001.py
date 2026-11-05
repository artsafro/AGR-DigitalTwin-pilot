"""elv-tc-vpm: read-only probe of Main by part and region (distinct vertex coordinates, face planes).

blender -b --factory-startup --python part_probe_v001.py -- <master.blend> <queries.json>
queries: [{"name":..., "parts":[...], "bbox":[x0,y0,z0,x1,y1,z1]}]; prints per query the distinct x / y / z (mm) of
the vertices of the faces of those parts whose centre lies in the bbox, and the distinct face planes (normal, offset).
"""
import bpy, json, sys
from collections import Counter

a = sys.argv[sys.argv.index("--") + 1:]
bpy.ops.wm.open_mainfile(filepath=a[0])
Q = json.load(open(a[1], encoding="utf-8"))
ob = bpy.data.objects["SM_Elevatornaya_1A_Main"]
me = ob.data
parts = json.loads(ob["part_ids"])
pidx = me.attributes["part_idx"].data
for q in Q:
    b = q["bbox"]
    xs, ys, zs, planes = Counter(), Counter(), Counter(), Counter()
    nf = 0
    for p in me.polygons:
        if parts[pidx[p.index].value] not in q["parts"]:
            continue
        c = p.center
        if not (b[0] <= c.x <= b[3] and b[1] <= c.y <= b[4] and b[2] <= c.z <= b[5]):
            continue
        nf += 1
        for i in p.vertices:
            v = me.vertices[i].co
            xs[round(v.x, 3)] += 1
            ys[round(v.y, 3)] += 1
            zs[round(v.z, 3)] += 1
        n = p.normal
        planes[(tuple(round(c_, 2) for c_ in n), round(n.dot(me.vertices[p.vertices[0]].co), 3))] += 1
    print("Q", q["name"], "faces", nf)
    print("  x", sorted(xs)[:40])
    print("  y", sorted(ys)[:40])
    print("  z", sorted(zs)[:40])
    print("  planes", sorted(planes.items())[:30])
