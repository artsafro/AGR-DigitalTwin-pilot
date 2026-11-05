"""elv-tc-vpm customer-clarify-v001: table of the customer's openings (reveal islands) with fake rooms, vs ours.

py -3 -I clarify_openings_v001.py <blend_probe.json> <fbx_tris_ours_v002_uv.npz> <out.json>
Theirs from blend_probe.json (FCD fw_part islands, our frame). Ours from the delivery-v002 triangle dump (our frame):
per opening, the outer wall plane next to it (udim 1001/1002/1004/1017 tris left and right of the opening) and the
plane of our door / window / glass inside it (udim 1009 ID14 door, 1006 ID11 W72 window, Glass) -> recess depth.
Facade axis by agr_side: 1 N (+Y), 2 W (-X), 3 S (-Y). Read-only.
"""
import sys, os, json
import numpy as np

probe, npz, out = sys.argv[1:4]
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
P = json.load(open(probe, encoding="utf-8"))
D = np.load(npz)
mt, mu = D["Main_tri"], D["Main_udim"]
gt = D["Glass_tri"]
mc = mt.mean(axis=1)
gc = gt.mean(axis=1)
SIDE = {1: ("N", 1, +1), 2: ("W", 0, -1), 3: ("S", 1, -1)}  # name, normal axis, sign (outward)
WALL = np.isin(mu, [1001, 1002, 1017]) & (mt[:, :, 2].min(axis=1) > 0.45)
ELEM = np.isin(mu, [1009, 1006])
isl = P["fcd"]["islands"]
rev, fake, frames, glass = isl["1"], isl["3"], isl["2"], isl["5"]


def inside(b, c, pad=0.05):
    lo, hi = np.array(b[0]) - pad, np.array(b[1]) + pad
    return np.all((c >= lo) & (c <= hi), axis=-1)


def normal_of(tris):
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    return n / ln


rows = []
for k, r in enumerate(sorted(rev, key=lambda r: (r["agr_side"][0], r["bbox"][0][0], r["bbox"][0][1], r["bbox"][0][2]))):
    side, ax, sg = SIDE[r["agr_side"][0]]
    t = 1 - ax  # along-facade axis
    lo, hi = r["bbox"]
    w = hi[t] - lo[t]
    h = hi[2] - lo[2]
    outer_theirs = lo[ax] if sg < 0 else hi[ax]
    fr = [f for f in fake if inside(r["bbox"], np.array([(f["bbox"][0][i] + f["bbox"][1][i]) / 2 if i != ax else
                                                           (r["bbox"][0][i] + r["bbox"][1][i]) / 2 for i in range(3)]), 0.3)
          and abs((f["bbox"][0][ax] + f["bbox"][1][ax]) / 2 - outer_theirs) < 1.5]
    gl = [g for g in glass if inside(r["bbox"], np.array([(g["bbox"][0][i] + g["bbox"][1][i]) / 2 for i in range(3)]), 0.1)]
    leaf = None
    if gl:
        leaf = gl[0]["bbox"][0][ax]
    frs = [f for f in frames if inside(r["bbox"], np.array([(f["bbox"][0][i] + f["bbox"][1][i]) / 2 for i in range(3)]), 0.1)
           and f["nf"] == 1]
    if frs:
        leaf = frs[0]["bbox"][0][ax]
    theirs_recess = abs(outer_theirs - leaf) if leaf is not None else None
    # ours: wall plane beside the opening, element plane inside it
    zc = (lo[2] + hi[2]) / 2
    zm = (np.abs(mc[:, 2] - zc) < h / 2 + 0.5)
    near = np.abs(mc[:, ax] - outer_theirs) < 1.0
    left = zm & near & WALL & (mc[:, t] > lo[t] - 0.8) & (mc[:, t] < lo[t] - 0.05)
    right = zm & near & WALL & (mc[:, t] < hi[t] + 0.8) & (mc[:, t] > hi[t] + 0.05)
    pts = []
    for m in (left, right):
        if m.any():
            v = mt[m].reshape(-1, 3)
            o = v[:, ax].min() if sg < 0 else v[:, ax].max()
            pts.append((v[:, t].mean(), o))
    if len(pts) == 2 and abs(pts[1][0] - pts[0][0]) > 1e-3:
        a = (pts[1][1] - pts[0][1]) / (pts[1][0] - pts[0][0])
        wall_ours = pts[0][1] + a * ((lo[t] + hi[t]) / 2 - pts[0][0])
    elif pts:
        wall_ours = pts[0][1]
    else:
        wall_ours = None
    box = [[lo[0] - 0.15, lo[1] - 0.15, lo[2] - 0.1], [hi[0] + 0.15, hi[1] + 0.15, hi[2] + 0.1]]
    box[0][ax] = outer_theirs - 1.0
    box[1][ax] = outer_theirs + 1.0
    em = ELEM & inside(box, mc, 0)
    nrm = normal_of(mt[em]) if em.any() else np.zeros((0, 3))
    face = em.copy()
    if em.any():
        face[np.where(em)[0]] = np.abs(nrm[:, ax]) > 0.9
    gm = inside(box, gc, 0)
    planes = []
    if face.any():
        planes.append(("door" if (mu[face] == 1009).mean() > 0.5 else "window_frame", float(np.median(mc[face][:, ax]))))
    if gm.any():
        planes.append(("glass", float(np.median(gc[gm][:, ax]))))
    ours_kind = [p[0] for p in planes]
    ours_recess = None
    if wall_ours is not None and planes:
        ours_recess = round(max(abs(wall_ours - p[1]) for p in planes), 3)
    kind = "door" if lo[2] < 0.35 else "window"
    rows.append({
        "facade": side, "kind": kind, "x": round((lo[0] + hi[0]) / 2, 2), "y": round((lo[1] + hi[1]) / 2, 2),
        "z0": round(lo[2], 2), "z1": round(hi[2], 2), "w": round(w, 2), "h": round(h, 2),
        "theirs_reveal_depth": round(hi[ax] - lo[ax], 3), "theirs_recess": None if theirs_recess is None else round(theirs_recess, 3),
        "theirs_fake_room": [round(v, 2) for v in fr[0]["dims"]] if fr else None,
        "theirs_glass": bool(gl),
        "ours_elements": ours_kind, "ours_recess": ours_recess, "ours_wall": None if wall_ours is None else round(float(wall_ours), 3),
    })
for i, r in enumerate(sorted(rows, key=lambda r: ("SNW".index(r["facade"]), r["x"] if r["facade"] != "W" else -r["y"])), 1):
    r["no"] = i
rows.sort(key=lambda r: r["no"])
json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for r in rows:
    print(r)
