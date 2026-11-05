"""elv-tc-vpm: whole-building inventory of the clean reference scene (read-only).

blender -b elv_ref_clean_v001.blend --python ref_inventory_full.py -- <out_dir>
Writes <out_dir>/ref_objects_full_v001.json (name, category, world bbox, tris per object) and
<out_dir>/ref_sections_full_v001.json (plan cuts at several z and vertical cuts; segments [cat, name, p0, p1]).
"""
import bpy, sys, json, os

argv = sys.argv[sys.argv.index("--") + 1:]
outd = os.path.abspath(argv[0])
os.makedirs(outd, exist_ok=True)
o1 = os.path.join(outd, "ref_objects_full_v001.json")
o2 = os.path.join(outd, "ref_sections_full_v001.json")
for p in (o1, o2):
    if os.path.exists(p):
        raise SystemExit("output exists: " + p)
cuts = [("z", v) for v in (-0.5, 0.3, 1.0, 3.0, 4.5, 6.0, 8.0, 9.5, 12.0, 13.0, 13.95, 14.6, 15.2, 15.8, 16.1)] + \
       [("y", v) for v in (-45.0, -30.0, -24.0, -10.0, 0.0)] + [("x", v) for v in (-40.0, -10.0, 10.0, 30.0, 50.0)]
AX = {"x": 0, "y": 1, "z": 2}
res = {f"{a}={v}": [] for a, v in cuts}
rows = []
for o in bpy.context.scene.objects:
    if o.type != "MESH" or not o.data.vertices:
        continue
    me = o.data
    mw = o.matrix_world
    vs = [mw @ v.co for v in me.vertices]
    mn = [min(v[i] for v in vs) for i in range(3)]
    mx = [max(v[i] for v in vs) for i in range(3)]
    me.calc_loop_triangles()
    cat = o.get("ref_category", "?")
    rows.append(dict(name=o.name, cat=cat, mn=[round(c, 4) for c in mn], mx=[round(c, 4) for c in mx],
                     t=len(me.loop_triangles), coll=[c.name for c in o.users_collection]))
    for a, val in cuts:
        i = AX[a]
        if mx[i] < val or mn[i] > val:
            continue
        key = f"{a}={val}"
        for t in me.loop_triangles:
            p = [vs[k] for k in t.vertices]
            d = [q[i] - val for q in p]
            pts = []
            for k in range(3):
                d0, d1 = d[k], d[(k + 1) % 3]
                if (d0 < 0) != (d1 < 0):
                    f = d0 / (d0 - d1)
                    pts.append(p[k].lerp(p[(k + 1) % 3], f))
            if len(pts) == 2:
                res[key].append([cat, o.name[:48]] + [round(c, 4) for c in pts[0]] + [round(c, 4) for c in pts[1]])
json.dump(rows, open(o1, "w", encoding="utf-8"), ensure_ascii=False)
json.dump(res, open(o2, "w", encoding="utf-8"), ensure_ascii=False)
print("INVENTORY", len(rows), {k: len(v) for k, v in res.items()})
