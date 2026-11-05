"""elv-tc-vpm build-v008 = build-v007c geometry (delivery v004, accepted) + the Max review rework of v004 (user 2026-11-05):

item 2 — joint cover strips P44 (Batten_FS-8P 165 x 22 mm, ID20 RAL 7021, G = 6 mm off the facade [D201]) rebuilt as
  CONTINUOUS runs: the Revit strip segments of one height are chained along the contour (ends within 0.6 m) and joined at
  the corners by mitres (intersection of the offset facade lines at G and G + 22 mm), one connected closed mesh element
  per run (quads, <= 3.9 m long faces, end caps only at the run ends). Run ends that are not corners stay where v007 ended
  them (album / Revit extents; behind-cladding parts still not built, accepted 2026-11-05). The v007 cuts at the fire
  ladders (5 cm, ray hit the stringer 0.25 m out, no geometry in the strip slab) disappear by construction; where a
  fixture is in the strip slab it is MOVED, not the strip:
  - Arktos boxes (P40) whose bottom sits on the strip top: raised by G (bottom G above the strip top);
  - light housings (P42) that span the strip height: moved out by 22 mm + G (housing back G in front of the strip face);
  every moved island is listed (build_v008_report.json) and re-checked for overlap / 5 mm proximity.
item 3 — corner glazing (convex R3.15 arcs and the concave junctions of the И-А upper curtain wall, the T1 convex
  corner): every glass pane whose nearest neighbouring pane (<= 0.35 m) stands at 3..177 deg (revolving door and skylight
  excluded) becomes a 6 mm shell of its two large faces only: the existing outer face + an inner face 6 mm behind it
  (reversed winding); no edge faces. The interior capsules are re-checked against the new inner faces.
Everything else is byte-for-byte the v007c geometry (no other vertex moves).

blender -b --factory-startup --disable-autoexec <build-v007/elv_full_v007c.blend> --python-exit-code 1 \
    --python build_v008.py -- <out.blend> <report.json>
"""
import bpy, bmesh, json, math, os, sys
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import capsules_v007 as CAP  # noqa: E402
from full_geom import lin  # noqa: E402

OUT, REP = [os.path.abspath(p) for p in sys.argv[sys.argv.index("--") + 1:][:2]]
for p in (OUT, REP):
    if os.path.exists(p):
        raise SystemExit("output exists: " + p)
JOB = os.path.abspath(os.path.join(HERE, ".."))
STEM = "SM_Elevatornaya_Vl_1_A_001"
OFF = (35.1000, -24.2535)              # delivered = build - OFF
G, T_STRIP, SHELL = 0.006, 0.022, 0.006
ob = bpy.data.objects[STEM + "_Main"]
og = bpy.data.objects[STEM + "_MainGlass"]
PART_IDS = json.loads(ob["part_ids"])
P44 = PART_IDS.index("P44_CoverStrips")
ID_STRIP = 20
REPORT = {"strips": {}, "moved_fixtures": [], "glass_shell": {}, "checks": {}}


def dl(p):
    return [round(p[0] - OFF[0], 3), round(p[1] - OFF[1], 3)] + ([round(p[2], 3)] if len(p) > 2 else [])


bm = bmesh.new()
bm.from_mesh(ob.data)
lay = bm.faces.layers.int["part_idx"]
n0 = {"faces": len(bm.faces), "verts": len(bm.verts)}
# ------------------------------------------------------------------ 1. drop the v007 strip pieces
old = [f for f in bm.faces if f[lay] == P44]
REPORT["strips"]["v007_faces_removed"] = len(old)
bmesh.ops.delete(bm, geom=old, context="FACES")
loose = [v for v in bm.verts if not v.link_faces]
bmesh.ops.delete(bm, geom=loose, context="VERTS")
bm.faces.ensure_lookup_table()
bm.verts.ensure_lookup_table()
bvh = BVHTree.FromBMesh(bm)

# ------------------------------------------------------------------ 2. segments: Revit outline + fitted facade line
STR = {s["name"]: s for s in json.load(open(os.path.join(JOB, "outputs", "build-v007", "strips_selected_v007.json"),
                                             encoding="utf-8"))}
ADD = json.load(open(os.path.join(JOB, "outputs", "build-v007", "additions_v007c.json"), encoding="utf-8"))
SEG = []
for a_ in ADD["strips"]:
    pcs = [p for p in a_["pieces"] if "s" in p]
    if not pcs:
        continue
    st = STR[a_["name"]]
    vs = [(v[0] + OFF[0], v[1] + OFF[1], v[2]) for v in st["verts"]]
    z0, z1 = round(min(v[2] for v in vs), 4), round(max(v[2] for v in vs), 4)
    bot = sorted([v for v in vs if abs(v[2] - z0) < 1e-3])[:2]
    p0, p1 = Vector((bot[0][0], bot[0][1])), Vector((bot[-1][0], bot[-1][1]))
    L = (p1 - p0).length
    a = (p1 - p0) / L
    out = Vector(a_["out"]).normalized()
    zm = 0.5 * (z0 + z1)
    ss, ds = [], []
    for k in range(int(L / 0.05)):
        s = (k + 0.5) * L / int(L / 0.05)
        q = p0 + a * s
        loc, nrm, fi, dd = bvh.ray_cast(Vector((q.x + out.x * 0.3, q.y + out.y * 0.3, zm)), Vector((-out.x, -out.y, 0)), 0.75)
        if loc is None or Vector(nrm).xy.dot(out) < 0.5 or bm.faces[fi].material_index + 1 not in (1, 5):
            continue
        ss.append(s)
        ds.append(loc.xy.dot(out))
    dmed = sorted(ds)[len(ds) // 2]
    keep = [(s, d) for s, d in zip(ss, ds) if abs(d - dmed) < 0.15]
    sm = sum(s for s, _ in keep) / len(keep)
    dm = sum(d for _, d in keep) / len(keep)
    var = sum((s - sm) ** 2 for s, _ in keep)
    b = sum((s - sm) * (d - dm) for s, d in keep) / var if var > 1e-9 else 0.0

    def B(s, p0=p0, a=a, out=out, dm=dm, sm=sm, b=b):
        q = p0 + a * s
        return q + out * (dm + b * (s - sm) - q.dot(out))
    SEG.append({"name": a_["name"], "z": (z0, z1), "p0": p0, "p1": p1, "L": L, "out": out, "B": B,
                "s_ext": (min(p["s"][0] for p in pcs), max(p["s"][1] for p in pcs)), "fit_mm_per_m": round(b * 1000, 3),
                "samples": len(keep)})

# chains: same strip height, ends within 0.6 m
for s_ in SEG:
    s_["used"] = False


def ends(s_):
    return [(s_["B"](s_["s_ext"][0]), 0), (s_["B"](s_["s_ext"][1]), 1)]


RUNS = []
for s_ in sorted(SEG, key=lambda s: (s["z"][0], s["name"])):
    if s_["used"]:
        continue
    chain = [(s_, False)]
    s_["used"] = True
    for direction in (1, 0):          # grow at the end (1) then at the start (0)
        while True:
            cur, rev = chain[-1] if direction == 1 else chain[0]
            if direction == 1:
                tip = cur["B"](cur["s_ext"][0] if rev else cur["s_ext"][1])
            else:
                tip = cur["B"](cur["s_ext"][1] if rev else cur["s_ext"][0])
            nxt = None
            for o in SEG:
                if o["used"] or abs(o["z"][0] - cur["z"][0]) > 1e-3:
                    continue
                for e, side in ends(o):
                    if (e - tip).length < 0.6:
                        nxt = (o, side)
                        break
                if nxt:
                    break
            if not nxt:
                break
            o, side = nxt
            o["used"] = True
            if direction == 1:
                chain.append((o, side == 1))       # entering at its end -> reversed
            else:
                chain.insert(0, (o, side == 0))
    RUNS.append(chain)


def isect(p, d, q, e):
    den = d.x * e.y - d.y * e.x
    if abs(den) < 1e-9:
        return None
    t = ((q.x - p.x) * e.y - (q.y - p.y) * e.x) / den
    return p + d * t


def seg_line(s_, rev, h):
    """offset line (point, direction along the run) at h off the facade"""
    A, Bp = s_["B"](s_["s_ext"][0]), s_["B"](s_["s_ext"][1])
    d = (Bp - A).normalized()
    if rev:
        A, Bp, d = Bp, A, -d
    return A + s_["out"] * h, Bp + s_["out"] * h, d


MESH_RUNS = []
for chain in RUNS:
    z0, z1 = chain[0][0]["z"]
    stations = []                     # (inner, outer, kind)
    corners = []
    for i, (s_, rev) in enumerate(chain):
        ia, ib, d = seg_line(s_, rev, G)
        oa, ob_, _ = seg_line(s_, rev, G + T_STRIP)
        if i == 0:
            stations.append((ia, oa, "end"))
        else:
            ps, prev = chain[i - 1]
            pia, pib, pd = seg_line(ps, prev, G)
            poa, pob, _ = seg_line(ps, prev, G + T_STRIP)
            ci, co = isect(pia, pd, ia, d), isect(poa, pd, oa, d)
            turn = pd.x * d.y - pd.y * d.x
            convex = turn * (pd.x * ps["out"].y - pd.y * ps["out"].x) < 0   # turning away from the outside
            stations[-1] = None
            stations.append((ci, co, "corner"))
            corners.append({"between": [ps["name"], s_["name"]], "at_delivered": dl(ci),
                            "angle_deg": round(math.degrees(math.asin(max(-1, min(1, turn)))), 1),
                            "kind": "convex (outer)" if convex else "concave (inner)",
                            "extension_m": [round((ci - pib).length, 3), round((ci - ia).length, 3)]})
        stations.append((ib, ob_, "end"))
    stations = [s for s in stations if s is not None]
    # split long legs (<= 3.9 m faces)
    pts = []
    for (ia, oa, ka), (ib, ob_, kb) in zip(stations, stations[1:]):
        Lg = (ib - ia).length
        for t in lin(0.0, 1.0, 3.9 / max(Lg, 1e-6))[:-1]:
            pts.append((ia.lerp(ib, t), oa.lerp(ob_, t)))
    pts.append(stations[-1][:2])
    MESH_RUNS.append({"chain": [(s_["name"], rev) for s_, rev in chain], "z": (z0, z1), "pts": pts,
                      "corners": corners, "out_first": chain[0][0]["out"]})


def run_faces(r):
    z0, z1 = r["z"]
    P = r["pts"]
    fs = []
    for (ia, oa), (ib, ob_) in zip(P, P[1:]):
        IA0, IB0, IA1, IB1 = (ia.x, ia.y, z0), (ib.x, ib.y, z0), (ia.x, ia.y, z1), (ib.x, ib.y, z1)
        OA0, OB0, OA1, OB1 = (oa.x, oa.y, z0), (ob_.x, ob_.y, z0), (oa.x, oa.y, z1), (ob_.x, ob_.y, z1)
        nout = (oa - ia).normalized()
        fs.append(([OA0, OB0, OB1, OA1], (nout.x, nout.y, 0.0)))
        fs.append(([IA0, IB0, IB1, IA1], (-nout.x, -nout.y, 0.0)))
        fs.append(([IA1, IB1, OB1, OA1], (0.0, 0.0, 1.0)))
        fs.append(([IA0, IB0, OB0, OA0], (0.0, 0.0, -1.0)))
    for k, sg in ((0, -1), (-1, 1)):
        ia, oa = P[k]
        t = (P[1][0] - P[0][0]) if k == 0 else (P[-1][0] - P[-2][0])
        t = t.normalized() * sg
        fs.append(([(ia.x, ia.y, z0), (oa.x, oa.y, z0), (oa.x, oa.y, z1), (ia.x, ia.y, z1)], (t.x, t.y, 0.0)))
    return fs


# ------------------------------------------------------------------ 3. fixtures in the strip slab -> move them
def islands(faces):
    """connected components (shared vertices) of the given faces"""
    fs = set(faces)
    seen, comps = set(), []
    for f in faces:
        if f in seen:
            continue
        comp, stack = [], [f]
        seen.add(f)
        while stack:
            g = stack.pop()
            comp.append(g)
            for v in g.verts:
                for h in v.link_faces:
                    if h in fs and h not in seen:
                        seen.add(h)
                        stack.append(h)
        comps.append(comp)
    return comps


FIX_PARTS = {PART_IDS.index("P40_Arktos"), PART_IDS.index("P42_Lights")}
fix_faces = [f for f in bm.faces if f[lay] in FIX_PARTS]
ISL = islands(fix_faces)
moved = set()
MOVED_ISL = []
for r in MESH_RUNS:
    z0, z1 = r["z"]
    e = CAP.NEAR
    fs = run_faces(r)
    vs, ps = [], []
    for pts, _ in fs:
        ps.append(list(range(len(vs), len(vs) + len(pts))))
        vs += [Vector(p) for p in pts]
    # grow: the slab from the facade (G - NEAR) to the strip front + NEAR, z +- NEAR -> any fixture face overlapping it
    grown = []
    for pts, n in fs:
        c = Vector([sum(p[k] for p in pts) / len(pts) for k in range(3)])
        grown.append([Vector(p) + (Vector(p) - c).normalized() * e for p in pts])
    gv, gp = [], []
    for pts in grown:
        gp.append(list(range(len(gv), len(gv) + len(pts))))
        gv += pts
    tb = BVHTree.FromPolygons(gv, gp)
    for isl in ISL:
        key = id(isl[0])
        if key in moved:
            continue
        iv = list({v for f in isl for v in f.verts})
        ib = BVHTree.FromPolygons([v.co for v in iv], [[iv.index(v) for v in f.verts] for f in isl])
        if not tb.overlap(ib):
            near = any(tb.find_nearest(v.co, e)[0] is not None for v in iv)
            if not near:
                continue
        zmin, zmax = min(v.co.z for v in iv), max(v.co.z for v in iv)
        part = PART_IDS[isl[0][lay]]
        c = sum((v.co for v in iv), Vector()) / len(iv)
        # local outward direction of the strip at this fixture
        best = min(range(len(r["pts"]) - 1), key=lambda k: ((r["pts"][k][0] + r["pts"][k + 1][0]) / 2 - c.xy).length)
        (ia, oa), (ib_, _) = r["pts"][best], r["pts"][best + 1]
        tdir = (ib_ - ia).normalized()
        nout = Vector((-tdir.y, tdir.x))
        if nout.dot(oa - ia) < 0:
            nout = -nout
        if zmin >= z1 - 0.002:
            dv = Vector((0, 0, z1 + G - zmin))
            how = "raised: bottom %.3f -> %.3f (strip top %.3f + G)" % (zmin, zmin + dv.z, z1)
        else:
            dv = Vector((nout.x, nout.y, 0)) * (T_STRIP + G)
            how = "moved out by 22 mm + G = %.3f m (fixture z %.3f..%.3f spans the strip z %.3f..%.3f)" % (
                T_STRIP + G, zmin, zmax, z0, z1)
        for v in iv:
            v.co += dv
        moved.add(key)
        MOVED_ISL.append(isl)
        REPORT["moved_fixtures"].append({"part": part, "centre_delivered": dl(c), "faces": len(isl), "how": how,
                                         "run": r["chain"][0][0], "z_strip": [z0, z1],
                                         "move_m": [round(x, 4) for x in dv]})

# ------------------------------------------------------------------ 4. strip runs into the mesh + checks
bm.faces.ensure_lookup_table()
mverts = [tuple(v.co) for v in bm.verts]
vidx = {v: i for i, v in enumerate(bm.verts)}
mpolys = [[vidx[v] for v in f.verts] for f in bm.faces]
gme = og.data
SCN = CAP.Scene(mverts + [tuple(v.co) for v in gme.vertices],
                mpolys + [[i + len(mverts) for i in p.vertices] for p in gme.polygons])
KEYV = {}


def vget(p):
    k = (round(p[0], 5), round(p[1], 5), round(p[2], 5))
    v = KEYV.get(k)
    if v is None:
        v = bm.verts.new(k)
        KEYV[k] = v
    return v


runs_rep = []
for r in MESH_RUNS:
    fs = run_faces(r)
    chk = SCN.conflicts(fs)
    if chk["overlap"]:
        vs_, ps_ = [], []
        for pts, _ in fs:
            ps_.append(list(range(len(vs_), len(vs_) + len(pts))))
            vs_ += [Vector(p) for p in pts]
        hit = SCN.base.overlap(BVHTree.FromPolygons(vs_, ps_))
        det = {}
        for bi, ci in hit:
            nm = PART_IDS[bm.faces[bi][lay]] if bi < len(mpolys) else "glass"
            q = vs_[ps_[ci][0]]
            det.setdefault(nm, []).append(dl(q))
        chk["overlap_parts"] = {k: v[:6] for k, v in det.items()}
    SCN.accept(fs)
    nf = 0
    for pts, nrm in fs:
        vs = [vget(p) for p in pts]
        # winding by the intended normal
        a, b_, c = (Vector(p) for p in pts[:3])
        if (b_ - a).cross(c - a).dot(Vector(nrm)) < 0:
            vs.reverse()
        f = bm.faces.new(vs)
        f.material_index = ID_STRIP - 1
        f[lay] = P44
        nf += 1
    Lr = sum((b_[0] - a[0]).length for a, b_ in zip(r["pts"], r["pts"][1:]))
    runs_rep.append({"segments": [n + (" (reversed)" if rv else "") for n, rv in r["chain"]], "z": list(r["z"]),
                     "length_m_inner": round(Lr, 3), "faces": nf, "corners": r["corners"],
                     "start_delivered": dl(r["pts"][0][0]), "end_delivered": dl(r["pts"][-1][0]), "conflicts": chk})
REPORT["strips"]["runs"] = runs_rep
REPORT["strips"]["segments"] = [{"name": s["name"], "s_ext": [round(x, 3) for x in s["s_ext"]], "L": round(s["L"], 3),
                                 "facade_fit_mm_per_m": s["fit_mm_per_m"], "samples": s["samples"]} for s in SEG]
# moved fixtures: re-check against the rest of the model + the new strips (overlap / 5 mm)
bm.faces.ensure_lookup_table()
bm.normal_update()

# connected elements of P44 (one per run expected)
p44 = [f for f in bm.faces if f[lay] == P44]
REPORT["strips"]["connected_elements"] = len(islands(p44))
REPORT["strips"]["open_edges"] = sum(1 for f in p44 for e in f.edges if len(e.link_faces) == 1)

# ------------------------------------------------------------------ 5. corner glazing -> 6 mm two-face shell
gb = bmesh.new()
gb.from_mesh(gme)
glay = gb.faces.layers.int["part_idx"]
GIDS = json.loads(og["part_ids"])
SKIP = {GIDS.index(p) for p in ("P08_RevolvingDoor", "P35_Skylight") if p in GIDS}
cand = [f for f in gb.faces if f[glay] not in SKIP and abs(f.normal.z) < 0.3]
bnd = []
for f in cand:
    for e in f.edges:
        d = e.verts[1].co - e.verts[0].co
        if abs(d.normalized().z) > 0.99 and d.length > 0.05:
            bnd.append((f, e))
corner = set()
pairs = []
for i, (fa, ea) in enumerate(bnd):          # the NEAREST other pane across each vertical glass edge
    best = None
    ma = (ea.verts[0].co + ea.verts[1].co) / 2
    za = sorted(v.co.z for v in ea.verts)
    for fb, eb in bnd:
        if fb is fa:
            continue
        zb = sorted(v.co.z for v in eb.verts)
        if min(za[1], zb[1]) - max(za[0], zb[0]) < 0.05:
            continue
        mb = (eb.verts[0].co + eb.verts[1].co) / 2
        dxy = (ma.xy - mb.xy).length
        if dxy <= 0.35 and (best is None or dxy < best[0]):
            best = (dxy, fb)
    if best is None:
        continue
    fb = best[1]
    ang = math.degrees(fa.normal.angle(fb.normal))
    if 3 <= ang <= 177:
        corner.update((fa, fb))
        pairs.append((fa.index, fb.index, round(ang, 1), round(best[0], 4)))
GL = []
for f in sorted(corner, key=lambda f: f.index):
    n = f.normal.copy()
    vs = [gb.verts.new(v.co - n * SHELL) for v in f.verts]
    nf = gb.faces.new(list(reversed(vs)))
    nf.material_index = f.material_index
    nf[glay] = f[glay]
    c = f.calc_center_median()
    GL.append({"face": f.index, "part": GIDS[f[glay]], "centre_delivered": dl(c), "normal": [round(x, 3) for x in n],
               "area_m2": round(f.calc_area(), 3)})


def zone(g):
    x, y, z = g["centre_delivered"]
    if x > 39 and y < 0:
        return "И-А upper curtain wall, SOUTH corner (convex R3.15 arc + concave junction)"
    if x > 39:
        return "И-А upper curtain wall, NORTH corner (convex R3.15 arc + concave junction)"
    return "roof superstructure T1, convex 90 deg corner"


zones = {}
for g in GL:
    z = zone(g)
    zones.setdefault(z, {"panes": 0, "area_m2": 0.0, "faces": []})
    zones[z]["panes"] += 1
    zones[z]["area_m2"] = round(zones[z]["area_m2"] + g["area_m2"], 3)
    zones[z]["faces"].append(g["face"])
REPORT["glass_shell"] = {"thickness_m": SHELL, "panes": len(GL), "zones": zones, "pairs_found": len(pairs),
                         "panes_list": GL, "rule": "pane whose NEAREST neighbouring pane across a vertical edge (<= 0.35 m, "
                         "edges overlapping >= 5 cm in z) stands at 3..177 deg; revolving door and skylight excluded"}
# inner faces vs model + capsules (overlap / 5 mm)
gb.faces.ensure_lookup_table()
new_g = gb.faces[len(gme.polygons):]
gfs = [([tuple(v.co) for v in f.verts], tuple(f.normal)) for f in new_g]
bm.verts.ensure_lookup_table()
bm.verts.index_update()
SCN2 = CAP.Scene([tuple(v.co) for v in bm.verts], [[v.index for v in f.verts] for f in bm.faces])
REPORT["checks"]["glass_inner_faces_vs_main"] = SCN2.conflicts(gfs)
# moved fixtures vs everything else of the final Main + glass (overlap / 5 mm), per fixture
for mf, isl in zip(REPORT["moved_fixtures"], MOVED_ISL):
    ids_ = {f.index for f in isl}
    rest = [f for f in bm.faces if f.index not in ids_]
    rv = list({v for f in rest for v in f.verts})
    ri = {v: i for i, v in enumerate(rv)}
    gv = [Vector(v.co) for v in gme.vertices]
    rb = BVHTree.FromPolygons([v.co for v in rv] + gv, [[ri[v] for v in f.verts] for f in rest] +
                              [[i + len(rv) for i in p.vertices] for p in gme.polygons])
    iv = list({v for f in isl for v in f.verts})
    ii = {v: i for i, v in enumerate(iv)}
    ib = BVHTree.FromPolygons([v.co for v in iv], [[ii[v] for v in f.verts] for f in isl])
    mf["check_after"] = {"overlap": len(rb.overlap(ib)),
                         "verts_within_5mm": sum(1 for v in iv if rb.find_nearest(v.co, CAP.NEAR)[0] is not None)}
REPORT["checks"]["main_faces"] = {"before": n0["faces"], "after": len(bm.faces)}
REPORT["checks"]["glass_faces"] = {"before": len(gme.polygons), "after": len(gb.faces)}

gb.to_mesh(gme)
gb.free()
bm.to_mesh(ob.data)
bm.free()
ob.data.update()
gme.update()
ob["build"] = ("jobs/elv-tc-vpm/scripts/build_v008.py on build-v007c: P44 cover strips as continuous mitred runs, "
               "fixtures in the strip slab moved, corner glazing as 6 mm two-face shells (Max review of v004)")
bpy.ops.wm.save_as_mainfile(filepath=OUT)
json.dump(REPORT, open(REP, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("BUILD_V008", json.dumps({"runs": [(r["segments"], r["length_m_inner"], r["conflicts"]) for r in runs_rep],
                                "connected": REPORT["strips"]["connected_elements"],
                                "open_edges": REPORT["strips"]["open_edges"],
                                "moved": [(m["part"], m["centre_delivered"], m["move_m"]) for m in REPORT["moved_fixtures"]],
                                "glass": {k: v["panes"] for k, v in zones.items()},
                                "glass_check": REPORT["checks"]["glass_inner_faces_vs_main"]}, ensure_ascii=False))
