"""elv-tc-vpm: sandwich panel joints of the WHOLE building from the clean FBX reference (read only) -> cassette_joints_v002.

"C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" -b outputs/ref-v001/elv_ref_clean_v001.blend \
    --python scripts/sandwich_joints_full.py -- <cassette_joints_v001.json> <out cassette_joints_v002.json>
v002 = v001 (pilot wood / metal cassette joints, unchanged) with 'sandwich' rebuilt over every facade:
- each panel of the collection 'sandwich': horizontal plane normal = the face-normal direction with the largest area, interval t
  along the plane (t = (-ny, nx)), z0 / z1, plane offset;
- vertical joints: neighbours in one plane (offset within 5 cm, normals parallel) and one row (z within 2 cm) with a
  gap <= 40 mm -> [x, y, z0, z1, nx, ny] (same format as v001);
- horizontal joints ('sandwich_h'): panels stacked in one plane (t overlap > 0.3 m, gap <= 80 mm) ->
  [x, y, nx, ny, t0, t1, z] at the mid height (the row boundary seen on the facade).
"""
import bpy, sys, os, json, math
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = argv[0], os.path.abspath(argv[1])
if os.path.exists(OUT):
    raise SystemExit("output exists: " + OUT)
rep = json.load(open(SRC, encoding="utf-8"))
coll = bpy.data.collections["sandwich"]
panels = []
for ob in coll.all_objects:
    if ob.type != "MESH" or not ob.data.polygons:
        continue
    mw = ob.matrix_world
    acc = {}
    for p in ob.data.polygons:
        n = (mw.to_3x3() @ p.normal)
        n.z = 0.0
        if n.length < 0.5:
            continue
        n.normalize()
        # fold to one hemisphere so opposite faces add up
        if n.x < -1e-6 or (abs(n.x) <= 1e-6 and n.y < 0):
            n = -n
        k = (round(n.x, 2), round(n.y, 2))       # dominant direction by area (the two big faces), not the mean
        e = acc.setdefault(k, [0.0, Vector((0, 0, 0))])
        e[0] += p.area
        e[1] += n * p.area
    if not acc:
        continue
    n = max(acc.values(), key=lambda e: e[0])[1].normalized()
    t = Vector((-n.y, n.x, 0))
    ws = [mw @ v.co for v in ob.data.vertices]
    ts = [w.dot(t) for w in ws]
    ds = [w.dot(n) for w in ws]
    zs = [w.z for w in ws]
    panels.append({"n": (n.x, n.y), "t0": min(ts), "t1": max(ts), "d": 0.5 * (min(ds) + max(ds)),
                   "z0": min(zs), "z1": max(zs), "name": ob.name[-10:]})


def same_plane(a, b):
    return a["n"][0] * b["n"][0] + a["n"][1] * b["n"][1] > 0.999 and abs(a["d"] - b["d"]) < 0.05


def xy(p, tt):
    n = Vector((p["n"][0], p["n"][1], 0))
    t = Vector((-n.y, n.x, 0))
    c = n * p["d"] + t * tt
    return round(c.x, 4), round(c.y, 4)


vj, hj = [], []
for i, a in enumerate(panels):
    for b in panels[i + 1:]:
        if not same_plane(a, b):
            continue
        if abs(a["z0"] - b["z0"]) < 0.02 and abs(a["z1"] - b["z1"]) < 0.02:
            lo, hi = (a, b) if a["t0"] < b["t0"] else (b, a)
            g = hi["t0"] - lo["t1"]
            if -0.005 <= g <= 0.04:
                x, y = xy(lo, 0.5 * (lo["t1"] + hi["t0"]))
                vj.append([x, y, round(a["z0"], 3), round(a["z1"], 3), round(a["n"][0], 4), round(a["n"][1], 4)])
        ov = min(a["t1"], b["t1"]) - max(a["t0"], b["t0"])
        if ov > 0.3:
            lo, hi = (a, b) if a["z0"] < b["z0"] else (b, a)
            g = hi["z0"] - lo["z1"]
            if -0.005 <= g <= 0.08:
                t0, t1 = max(a["t0"], b["t0"]), min(a["t1"], b["t1"])
                x, y = xy(lo, 0.5 * (t0 + t1))
                hj.append([x, y, round(a["n"][0], 4), round(a["n"][1], 4), round(t0, 3), round(t1, 3),
                           round(0.5 * (lo["z1"] + hi["z0"]), 3)])
rep["sandwich_v001_pilot_only"] = {k: rep["sandwich"][k] for k in ("panels", "joint_z", "runs")}
rep["sandwich"] = {"pitch": [1.19, None], "panels": len(panels), "joints_xyz": vj,
                   "method": "whole building, sandwich_joints_full.py"}
rep["sandwich_h"] = hj
json.dump(rep, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
from collections import Counter  # noqa: E402
print("PANELS", len(panels), "VJ", len(vj), "HJ", len(hj))
print("HZ", Counter(round(h[6], 2) for h in hj).most_common(20))
