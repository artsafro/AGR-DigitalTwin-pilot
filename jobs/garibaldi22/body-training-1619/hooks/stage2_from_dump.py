"""Hook `after` stage `body` (#1619 polygon stage 2): window fills, capsules and AC baskets read from the Revit crop.

Pattern: n/a | new-case: stage-2 inset spec (frame + glass + flashing + capsule per opening, AC box) for an accepted
stage-1 body.

uv run python stage2_from_dump.py CROP.npz FLOOR.json STAGE2.json [--clip CLIP.json] [--embed 0.05]

FLOOR.json is the stage-1 spec the accepted body was built from (floor_from_dump.py --openings + zones); the body
itself is never rebuilt here. For every opening [ring, s0, s1, wl, wh, r] of FLOOR.json the Revit window of the
reference floor whose centre projects into it is read in its own frame (u along the opening, d = depth behind the
facade line, z from its sill):
- glass panes = the thin (<= 4 cm) 12-triangle boxes of the family; pane edges closer than --snap are snapped to
  their mean (one bar line instead of a 3 cm sliver row, BM-09) and the largest shift is reported;
- frame depth = the back of the frame part (largest component) minus the opening's reveal r; bars (frame, mullions,
  transoms) = the opening minus the panes (mullions/transoms are geometry because they are geometry in Revit);
- flashing (отлив) = the frame part's horizontal top face in front of the frame (height, front depth).
AC baskets (Artem 2026-11-17: «бокс врезается в стену без заднего полигона»): Revit box size and outward depth; the
back side goes --embed m behind the facade line (no back face, no niche: the wall stays whole). A basket whose top
reaches the sill of an opening above is lowered 1 cm so its in-wall strip never lies in the sill reveal plane.
Capsules (D205): front open at the frame middle, 100 mm outline, 1.0 m deep; each is checked against the contour.
Refuses an output equal to an input, an opening without exactly one window, a window without panes.
"""
import argparse
import collections
import json
import math
import os
import re
import sys

import numpy as np
from shapely.geometry import Point, Polygon
from shapely.ops import substring

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from floor_from_dump import KEYS, classify  # noqa: E402

CAPSULE = {"depth": 1.0, "outline": 0.1}  # D205


def components(tris, nd=5):
    """Connected parts of a triangle soup (shared rounded vertices). Returns a list of index arrays."""
    key = np.round(np.asarray(tris, dtype=float).reshape(-1, 3), nd)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1, 3)
    par = list(range(int(inv.max()) + 1))

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    for a, b, c in inv:
        for x, y in ((a, b), (b, c)):
            rx, ry = find(int(x)), find(int(y))
            if rx != ry:
                par[rx] = ry
    comp = collections.defaultdict(list)
    for i, (a, _, _) in enumerate(inv):
        comp[find(int(a))].append(i)
    return [np.array(v) for v in comp.values()]


def snap_edges(vals, tol):
    """Cluster sorted values closer than tol (chained) and replace each by its cluster mean.

    Returns (mapping {value: snapped}, max shift)."""
    vs = sorted(set(float(v) for v in vals))
    groups, cur = [], []
    for v in vs:
        if cur and v - cur[-1] > tol:
            groups.append(cur)
            cur = []
        cur.append(v)
    if cur:
        groups.append(cur)
    out, shift = {}, 0.0
    for g in groups:
        m = sum(g) / len(g)
        for v in g:
            out[v] = m
            shift = max(shift, abs(v - m))
    return out, shift


def window_parts(L, r, snap=0.04):
    """Read one Revit window given in local coords L (n, 3, 3): u along the opening, d depth behind the facade line
    (positive into the body), z from the opening sill. Returns a dict with panes [[u0, u1, z0, z1, d_glass]] in the
    frame of the window bbox (u from its left edge), frame depth fd (frame back - r), flashing (or None), width,
    height and the snap shift. Refuses a window without panes or with a frame back not behind r."""
    L = np.asarray(L, dtype=float)
    if L.ndim != 3 or L.shape[1:] != (3, 3) or not np.isfinite(L).all():
        raise ValueError("window triangles must be a finite (n, 3, 3) array")
    P = L.reshape(-1, 3)
    u_lo, u_hi = float(P[:, 0].min()), float(P[:, 0].max())
    z_lo, z_hi = float(P[:, 2].min()), float(P[:, 2].max())
    comps = components(L)
    frame = max(comps, key=len)
    panes = []
    for idx in comps:
        Q = L[idx].reshape(-1, 3)
        lo, hi = Q.min(0), Q.max(0)
        if len(idx) == 12 and hi[1] - lo[1] <= 0.04 and hi[0] - lo[0] > 0.15 and hi[2] - lo[2] > 0.15:
            panes.append([lo[0] - u_lo, hi[0] - u_lo, lo[2] - z_lo, hi[2] - z_lo, (lo[1] + hi[1]) / 2])
    if not panes:
        raise ValueError("window has no glass panes (12-triangle boxes <= 4 cm thick)")
    F = L[frame]
    fd = float(F[:, :, 1].max()) - r
    if not (0.02 <= fd < 0.5):
        raise ValueError("frame back %.3f m is not 2..500 mm behind the reveal %.3f m" % (F[:, :, 1].max(), r))
    umap, us = snap_edges([p[0] for p in panes] + [p[1] for p in panes], snap)
    zmap, zs = snap_edges([p[2] for p in panes] + [p[3] for p in panes], snap)
    panes = [[umap[p[0]], umap[p[1]], zmap[p[2]], zmap[p[3]], p[4]] for p in panes]
    panes.sort(key=lambda p: (p[2], p[0]))
    # flashing: horizontal up-facing triangles of the frame part in front of the frame, low on the window
    n = np.cross(F[:, 1] - F[:, 0], F[:, 2] - F[:, 0])
    nn = np.linalg.norm(n, axis=1)
    up = (n[:, 2] > 0.98 * nn) & (F[:, :, 1].min(1) < r - 0.02) & (F[:, :, 2].max(1) - z_lo < 0.2)
    flashing = None
    if up.any():
        top = float(F[up][:, :, 2].mean() - z_lo)
        low = F[F[:, :, 2].max(1) - z_lo <= top + 1e-4]
        flashing = {"top": round(top, 4), "front": round(float(low[:, :, 1].min()), 4)}
    for p in panes:
        if not (r <= p[4] <= r + fd):
            raise ValueError("glass depth %.3f outside the frame %.3f..%.3f" % (p[4], r, r + fd))
    return {"width": u_hi - u_lo, "height": z_hi - z_lo, "fd": round(fd, 4), "flashing": flashing,
            "panes": [[round(v, 4) for v in p] for p in panes], "snap_shift": round(max(us, zs), 4)}


def run_points(ring, s0, s1):
    """Plan points of the ring run s0..s1 (contour corners included)."""
    return [tuple(c) for c in substring(ring.exterior, s0, s1).coords]


def straight(pts, tol_deg=1.0):
    """True when the run turns less than tol_deg at every inner point."""
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        t1 = math.atan2(b[1] - a[1], b[0] - a[0])
        t2 = math.atan2(c[1] - b[1], c[0] - b[0])
        if abs(math.degrees((t2 - t1 + math.pi) % (2 * math.pi) - math.pi)) > tol_deg:
            return False
    return True


def capsule_plan(a, t, w, r, fd, cap=CAPSULE):
    """Plan polygon of a D205 capsule: u -outline..w+outline, d from the frame middle r + fd/2 to +depth."""
    n = (-t[1], t[0])  # left normal of a CCW ring = into the body
    dm = r + fd / 2
    o = cap["outline"]
    pts = []
    for u, d in ((-o, dm), (w + o, dm), (w + o, dm + cap["depth"]), (-o, dm + cap["depth"])):
        pts.append((a[0] + t[0] * u + n[0] * d, a[1] + t[1] * u + n[1] * d))
    return pts


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("crop")
    ap.add_argument("floor")
    ap.add_argument("out")
    ap.add_argument("--clip")
    ap.add_argument("--embed", type=float, default=0.05, help="AC box back side behind the facade line, m")
    ap.add_argument("--snap", type=float, default=0.04, help="merge pane edges closer than this, m")
    a = ap.parse_args(argv)
    ins = {os.path.realpath(p) for p in (a.crop, a.floor, a.clip) if p}
    if os.path.realpath(a.out) in ins or not a.out.endswith(".json"):
        sys.exit("refused: output must be a new .json, not an input")
    if not (0.0 < a.embed < 0.3):
        sys.exit("refused: --embed must be in (0, 0.3) m")
    fl = json.load(open(a.floor, encoding="utf-8"))
    ring = Polygon(fl["rings"][0]["xy"])
    ext = ring.exterior
    ref, step, head = float(fl["ref_sill"]), float(fl["step"]), float(fl["loops"][1])
    d = np.load(a.crop)
    tri, obj, names = d["tri"], d["obj"], [str(n) for n in d["names"]]
    keep = np.ones(len(names), bool)
    if a.clip:
        poly = Polygon(json.load(open(a.clip, encoding="utf-8")))
        cnt = np.bincount(obj, minlength=len(names)).astype(float)
        cx = np.bincount(obj, weights=tri[:, :, 0].mean(1), minlength=len(names)) / np.maximum(cnt, 1)
        cy = np.bincount(obj, weights=tri[:, :, 1].mean(1), minlength=len(names)) / np.maximum(cnt, 1)
        keep = np.array([poly.contains(Point(x, y)) for x, y in zip(cx, cy)])
    cls = classify(names, KEYS)
    by = collections.defaultdict(list)
    for i, o in enumerate(obj):
        if keep[o] and cls[o] in ("windows", "baskets"):
            by[int(o)].append(i)
    openings = [w for w in fl["windows"] if len(w) > 5 and w[5] > 0]
    wins = {}
    for o, idx in by.items():
        if cls[o] != "windows":
            continue
        P = tri[idx].reshape(-1, 3)
        if abs(P[:, 2].min() - ref) > 0.05:
            continue
        sc = ext.project(Point(P[:, 0].mean(), P[:, 1].mean()))
        hit = [k for k, w in enumerate(openings) if w[1] - 0.05 <= sc <= w[2] + 0.05]
        if len(hit) == 1:
            wins.setdefault(hit[0], []).append(o)
    out_w, problems, caps = [], [], []
    for k, w in enumerate(openings):
        if len(wins.get(k, [])) != 1:
            sys.exit("refused: opening %d (s %.2f..%.2f) matches %d Revit windows" % (k, w[1], w[2], len(wins.get(k, []))))
        o = wins[k][0]
        s0, s1, r = float(w[1]), float(w[2]), float(w[5])
        pts = run_points(ring, s0, s1)
        if not straight(pts):
            sys.exit("refused: opening %d runs over a contour corner (unsupported in stage 2)" % k)
        A, B = np.array(pts[0]), np.array(pts[-1])
        W = float(np.linalg.norm(B - A))
        t = (B - A) / W
        nin = np.array([-t[1], t[0]])
        P = tri[by[o]]
        # read the family in its OWN plan frame (PCA, as reveal_depth): a window 3 deg off the contour keeps its
        # frame back and glass in one depth layer; depth from the facade line at its centre
        Q = P.reshape(-1, 3)[:, :2]
        cq = Q.mean(0)
        foot = ext.interpolate(ext.project(Point(*cq)))
        ev, vec = np.linalg.eigh(np.cov((Q - cq).T))
        tw = vec[:, 1] * (1.0 if vec[:, 1] @ t >= 0 else -1.0)
        nw = np.array([-tw[1], tw[0]])
        rel = P[:, :, :2] - [foot.x, foot.y]
        loc = np.stack([rel @ tw, rel @ nw, P[:, :, 2] - ref], 2)
        try:
            part = window_parts(loc, r, a.snap)
        except ValueError as e:
            sys.exit("refused: window %s: %s" % (names[o], e))
        su, sz = W / part["width"], head / part["height"]
        if abs(su - 1) > 0.03 or abs(sz - 1) > 0.03:
            problems.append("window %s: Revit %.3f x %.3f vs opening %.3f x %.3f" % (names[o], part["width"], part["height"], W, head))
        panes = [[p[0] * su, p[1] * su, p[2] * sz, p[3] * sz, p[4]] for p in part["panes"]]
        typ = re.sub(r"\s*\[\d+\].*$|_[0-9a-f]{6,7}$", "", names[o])
        cp = capsule_plan(A, t, W, r, part["fd"])
        cap_poly = Polygon(cp)
        inside = ring.buffer(1e-6).contains(cap_poly)
        caps.append(cap_poly)
        out_w.append({"opening": k, "object": names[o], "type": typ, "a": [round(float(v), 4) for v in A],
                      "t": [round(float(v), 6) for v in t], "w": round(W, 4), "h": head, "r": r, "fd": part["fd"],
                      "panes": [[round(v, 4) for v in p] for p in panes], "flashing": part["flashing"],
                      "snap_shift": part["snap_shift"], "capsule_inside_contour": bool(inside)})
    overlaps = sum(1 for i in range(len(caps)) for j in range(i + 1, len(caps)) if caps[i].intersection(caps[j]).area > 1e-6)
    baskets = []
    for o, idx in by.items():
        if cls[o] != "baskets":
            continue
        P = tri[idx].reshape(-1, 3)
        z0, z1 = float(P[:, 2].min()), float(P[:, 2].max())
        if not (ref - 1.0 < z0 < ref + step - 1.0):
            continue
        sc = ext.project(Point(P[:, 0].mean(), P[:, 1].mean()))
        p0, p1 = ext.interpolate(max(0, sc - 0.05)), ext.interpolate(min(ext.length, sc + 0.05))
        t = np.array([p1.x - p0.x, p1.y - p0.y])
        t /= np.linalg.norm(t)
        nout = np.array([t[1], -t[0]])
        foot = ext.interpolate(sc)
        rel = P[:, :2] - [foot.x, foot.y]
        u, v = rel @ t, rel @ nout
        if v.max() < 0.05:
            problems.append("basket %s is not outside the contour" % names[o])
            continue
        su0, su1 = sc + u.min(), sc + u.max()
        if not straight(run_points(ring, max(0, su0), min(ext.length, su1))):
            sys.exit("refused: basket %s spans a contour corner" % names[o])
        top = z1 - ref
        lowered = False
        if top > step - 0.005 and any(w[1] < su1 and w[2] > su0 for w in openings):
            top, lowered = step - 0.01, True
        c = np.array([foot.x, foot.y]) + t * (u.min() + u.max()) / 2
        baskets.append({"object": names[o], "c": [round(float(x), 4) for x in c], "t": [round(float(x), 6) for x in t],
                        "w": round(float(np.ptp(u)), 4), "out": round(float(v.max()), 4), "revit_back": round(float(v.min()), 4),
                        "embed": a.embed, "z0": round(z0 - ref, 4), "z1": round(top, 4), "top_lowered": lowered})
    baskets.sort(key=lambda b: (b["c"][0], b["c"][1]))
    spec = {"units": "m", "stage": "stage2", "source_crop": os.path.basename(a.crop), "floor": os.path.basename(a.floor),
            "z0": fl["z0"], "step": step, "floors": fl["floors"], "ring": fl["rings"][0]["xy"], "capsule": CAPSULE,
            "windows": out_w, "baskets": baskets, "problems": problems,
            "counts": {"openings": len(openings), "windows": len(out_w), "baskets": len(baskets),
                       "types": dict(collections.Counter(w["type"] for w in out_w)),
                       "panes": sum(len(w["panes"]) for w in out_w), "flashings": sum(1 for w in out_w if w["flashing"]),
                       "max_snap_shift_m": max((w["snap_shift"] for w in out_w), default=0.0),
                       "capsules_outside_contour": sum(1 for w in out_w if not w["capsule_inside_contour"]),
                       "capsule_overlaps": overlaps, "baskets_top_lowered": sum(1 for b in baskets if b["top_lowered"])}}
    with open(a.out, "x", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=1)
    print(json.dumps(spec["counts"], ensure_ascii=False))
    if problems:
        print("PROBLEMS", json.dumps(problems, ensure_ascii=False))


if __name__ == "__main__":
    main()
