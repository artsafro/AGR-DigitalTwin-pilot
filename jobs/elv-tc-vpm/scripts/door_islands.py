"""elv-tc-vpm: mesh islands of the single In-1H doors in the clean FBX reference (read only) -> census ELV-18.

"C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" -b outputs/ref-v001/elv_ref_clean_v001.blend \
    --python scripts/door_islands.py -- <out.json>
Per object: the facade frame (u along the wall from the left end seen from outside, d = depth, z up) from the
object's bbox orientation, then every connected mesh island with its (u, d, z) extent, rounded to 1 mm.
"""
import bpy, bmesh, sys, os, json, math
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = os.path.abspath(argv[0])
if os.path.exists(OUT):
    raise SystemExit("output exists: " + OUT)
# wall direction t (u axis, viewer's right seen from outside) per door: west x -0.42 (outside -x), TP x -8.82
# (outside -x), skewed north wall (outside +y-ish, normal of SKD = (49.907, 5.388))
SKD = Vector((49.907, 5.388, 0)).normalized()
FRAMES = {"In-1H(C_900x2050)L* 3": Vector((0, -1, 0)), "In-1H(C_1100x2050)L* 2": Vector((0, -1, 0)),
          "In-1H(C_1100x2050)L* [": -SKD}
rep = {}
for ob in bpy.data.objects:
    key = next((k for k in FRAMES if k in ob.name), None)
    if key is None or ob.type != "MESH":
        continue
    t = FRAMES[key]
    n = Vector((-t.y, t.x, 0))   # outward = right of t ... checked by the depth range below
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.transform(ob.matrix_world)
    bm.verts.ensure_lookup_table()
    seen, isl = set(), []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack, comp = [v], []
        seen.add(v.index)
        while stack:
            a = stack.pop()
            comp.append(a.co.copy())
            for e in a.link_edges:
                b = e.other_vert(a)
                if b.index not in seen:
                    seen.add(b.index)
                    stack.append(b)
        isl.append(comp)
    allp = [p for c in isl for p in c]
    u0 = min(p.dot(t) for p in allp)
    z0 = min(p.z for p in allp)
    d0 = min(p.dot(n) for p in allp)
    rows = []
    for c in isl:
        us, ds, zs = [p.dot(t) - u0 for p in c], [p.dot(n) - d0 for p in c], [p.z - z0 for p in c]
        rows.append({"u": [round(min(us), 3), round(max(us), 3)], "d": [round(min(ds), 3), round(max(ds), 3)],
                     "z": [round(min(zs), 3), round(max(zs), 3)], "verts": len(c)})
    rows.sort(key=lambda r: (-(r["u"][1] - r["u"][0]) * (r["z"][1] - r["z"][0])))
    rep[ob.name] = {"origin_u_z": [round(u0, 3), round(z0, 3)], "extent": {
        "u": round(max(p.dot(t) for p in allp) - u0, 3), "d": round(max(p.dot(n) for p in allp) - d0, 3),
        "z": round(max(p.z for p in allp) - z0, 3)}, "islands": rows[:40], "n_islands": len(rows)}
    bm.free()
json.dump(rep, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
for k, v in rep.items():
    print(k, v["extent"], v["n_islands"])
    for r in v["islands"][:14]:
        print("   ", r)
