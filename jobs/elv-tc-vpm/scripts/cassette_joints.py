"""elv-tc-vpm: measure the cassette / sandwich joint lattice of the FBX reference (read-only on the blend).

"C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" -b outputs/ref-v001/elv_ref_clean_v001.blend \
    --python scripts/cassette_joints.py -- <out.json>

For every object of the collections wood_cassette, metal_cassette and sandwich inside the pilot zone, the world bbox
is projected onto the pilot outlines (U = upper wood/CW face, L = ground-floor metal face, build_pilot_ia.py) as an
arc-length interval [u0, u1] plus [z0, z1]. Joint centres = midpoints between neighbouring panel edges of one row
(gap <= 40 mm). Per run (straight E / S / N parts and the corner arcs) the joints are reduced modulo the cassette pitch
and the circular mean gives the lattice phase; residuals show how well one lattice fits the FBX.
"""
import bpy, sys, os, json, math
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = os.path.abspath(argv[0])
if os.path.exists(OUT):
    raise SystemExit("output exists: " + OUT)

from pilot_outlines import U, L  # noqa: E402  (outlines exactly as in build_pilot_ia.py)

SETS = {"wood_cassette": (U, 1.0, 1.53), "metal_cassette": (L, 1.5, 0.5), "sandwich": (U, 1.19, 2.0)}


def run_of(poly, u):
    """label of the outline part at arc length u: straight runs S/E*/N and arcs (by segment direction)"""
    i = poly.seg(u)
    t = poly.t[i]
    if abs(t[1]) < 1e-6 and t[0] > 0:
        return "S"
    if abs(t[1]) < 1e-6 and t[0] < 0:
        return "N"
    if abs(t[0]) < 1e-6:
        return "E"
    while i > 0 and abs(poly.t[i - 1][0]) > 1e-6 and abs(poly.t[i - 1][1]) > 1e-6:
        i -= 1
    return "arc%d" % (i)


rep = {}
for coll, (poly, pu, pv) in SETS.items():
    c = bpy.data.collections.get(coll)
    if c is None:
        rep[coll] = "missing"
        continue
    panels = []
    for ob in c.all_objects:
        if ob.type != "MESH":
            continue
        ws = [ob.matrix_world @ v.co for v in ob.data.vertices]
        if not ws:
            continue
        xs, ys, zs = [w.x for w in ws], [w.y for w in ws], [w.z for w in ws]
        if max(xs) < 41.0 or min(ys) < -52 or max(ys) > 4.5 or max(zs) > 15:
            continue
        us = [poly.project((w.x, w.y)) for w in ws]
        d = min(math.hypot(w.x - poly.base(u)[0], w.y - poly.base(u)[1]) for w, u in zip(ws, us))
        if d > 0.8:
            continue
        panels.append((round(min(us), 4), round(max(us), 4), round(min(zs), 3), round(max(zs), 3), ob.name[-12:]))
    rows = defaultdict(list)
    for p in panels:
        rows[(p[2], p[3])].append(p)
    joints_u, joints_z, joints_xyz = [], set(), []
    for (z0, z1), ps in rows.items():
        ps.sort()
        for a, b in zip(ps, ps[1:]):
            g = b[0] - a[1]
            if -0.005 <= g <= 0.04:
                jm = (a[1] + b[0]) / 2
                joints_u.append((round(jm, 4), run_of(poly, jm), z0))
                bx, by = poly.base(jm)
                nx, ny = poly.n[poly.seg(jm)]
                joints_xyz.append([round(bx, 4), round(by, 4), z0, z1, round(nx, 4), round(ny, 4)])
    zb = sorted({p[2] for p in panels})
    zt = sorted({p[3] for p in panels})
    for t in zt:
        for b in zb:
            if 0.0 <= b - t <= 0.04:
                joints_z.add(round((t + b) / 2, 4))
    runs = defaultdict(list)
    for u, r, z in joints_u:
        runs[r].append(u)
    phase = {}
    for r, us in runs.items():
        ang = [2 * math.pi * (u % pu) / pu for u in us]
        cx, cy = sum(math.cos(a) for a in ang), sum(math.sin(a) for a in ang)
        ph = (math.atan2(cy, cx) / (2 * math.pi) * pu) % pu
        res = [((u - ph + pu / 2) % pu) - pu / 2 for u in us]
        phase[r] = {"n": len(us), "phase_u": round(ph, 4), "u_range": [round(min(us), 3), round(max(us), 3)],
                    "max_abs_resid": round(max(abs(x) for x in res), 4),
                    "resid_hist_cm": dict(sorted(defaultdict(int, {}).items())),
                    "off_lattice": sorted({round(u, 3) for u, x in zip(us, res) if abs(x) > 0.02})[:40]}
        h = defaultdict(int)
        for x in res:
            h[round(x * 100)] += 1
        phase[r]["resid_hist_cm"] = dict(sorted(h.items()))
    zph = None
    if joints_z:
        ang = [2 * math.pi * (z % pv) / pv for z in joints_z]
        cx, cy = sum(math.cos(a) for a in ang), sum(math.sin(a) for a in ang)
        zph = (math.atan2(cy, cx) / (2 * math.pi) * pv) % pv
    rep[coll] = {"pitch": [pu, pv], "panels": len(panels), "rows": {f"{k[0]}-{k[1]}": len(v) for k, v in sorted(rows.items())},
                 "joint_z": sorted(joints_z), "phase_z": None if zph is None else round(zph, 4),
                 "runs": phase, "joints": sorted(joints_u), "joints_xyz": joints_xyz, "panels_list": sorted(panels), "outline": "U" if poly is U else "L",
                 "run_ranges": {}}
for name, poly in (("U", U), ("L", L)):
    rr = {}
    for i in range(len(poly.t)):
        r = run_of(poly, (poly.cum[i] + poly.cum[i + 1]) / 2)
        a = rr.setdefault(r, [poly.cum[i], poly.cum[i + 1]])
        a[0], a[1] = min(a[0], poly.cum[i]), max(a[1], poly.cum[i + 1])
    rep["outline_" + name] = {k: [round(x, 4) for x in v] for k, v in rr.items()}
json.dump(rep, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
for k in SETS:
    v = rep[k]
    if isinstance(v, str):
        print(k, v)
        continue
    print(k, "panels", v["panels"], "phase_z", v["phase_z"], "joint_z", v["joint_z"][:12])
    for r, p in sorted(v["runs"].items()):
        print("  ", r, p["n"], "phase", p["phase_u"], "maxres", p["max_abs_resid"], p["u_range"], p["resid_hist_cm"])
