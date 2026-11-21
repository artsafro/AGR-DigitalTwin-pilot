"""Hook `before` stage `body` (#1619 polygon 63B v007): stack the typical ring A and the belt ring B.

Pattern: n/a | new-case: two-ring tower on the 63A module builder (jobs/POLY63-A + garibaldi22 module_build).

    python stack63b.py floor_A.json floor_B.json CROP.npz KEYS.json OUT_DIR [--max-side 3.6] [--snap 0.03]

Tower 63B (FBX world metres, +4.65..+51.90, 3.15 m storeys): typical storeys use ring A, the two belt
storeys (+23.55, +39.30) the recessed ring B. Every station (corner, cut, max-side split) of one ring is projected
onto the other and becomes a station there too, so both rings carry the same station sequence and every belt cap
cell is a quad between station i and i+1 of A and B (no Delaunay fan, no T-junction, belt-cap-quad-ladder rule 1/3).
B stations within `--snap` of their A partner take the A point (one wall, one line: no sliver cap).
Writes OUT_DIR/module_<run>.json (body core plan input, schemas/BodyPlan.schema.json, floor-to-floor modules, base = floor level) and
OUT_DIR/caps.json (cap cells by xy, z and material). Pure Python; the Blender side is assemble63b.py.
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from shapely.geometry import Polygon

STEP = 3.15
FLOOR0 = 4.65
RUNS = [("A1", "A", 4.65, 6), ("B1", "B", 23.55, 1), ("A2", "A", 26.70, 4), ("B2", "B", 39.30, 1), ("A3", "A", 42.45, 3)]
LOOPS = {"A": [0.0, 0.70, 2.65], "B": [0.0, 0.70, 0.90, 2.65]}  # floor, sill(s), head: source wall vertex levels
CAPS_Z = [23.55, 26.70, 39.30, 42.45]
RETURN_DOT = float(os.environ.get("RETURN_DOT", "0"))  # 0.35 cast along returns: 48 T-junctions on 63B, off


def ring_ccw(xy):
    """True when the plan ring runs counter-clockwise (positive shoelace area)."""
    n = len(xy)
    return sum(xy[k][0] * xy[(k + 1) % n][1] - xy[(k + 1) % n][0] * xy[k][1] for k in range(n)) > 0


def perim_s(xy):
    s = [0.0]
    for i in range(len(xy)):
        s.append(s[-1] + math.dist(xy[i], xy[(i + 1) % len(xy)]))
    return s


def point_at(xy, cum, s):
    L = cum[-1]
    s = s % L
    i = max(0, min(len(xy) - 1, int(np.searchsorted(cum, s, side="right")) - 1))
    a, b = xy[i], xy[(i + 1) % len(xy)]
    seg = cum[i + 1] - cum[i]
    t = 0.0 if seg <= 0 else (s - cum[i]) / seg
    return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))


def project(xy, cum, p):
    """Closest point of the closed polyline to p: (s, distance)."""
    best = (0.0, float("inf"))
    for i in range(len(xy)):
        a, b = xy[i], xy[(i + 1) % len(xy)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
        d = math.hypot(a[0] + t * dx - p[0], a[1] + t * dy - p[1])
        if d < best[1]:
            best = (cum[i] + t * math.sqrt(L2), d)
    return best


def ring_stations(xy, cuts, max_side):
    """Perimeter stations s of one ring: corners, cuts, then max-side splits (body_lattice.ring_points order)."""
    cum = perim_s(xy)
    corners = [round(c, 6) for c in cum[:-1]]
    ss = []
    for s in sorted(set(corners + [round(c, 6) for c in cuts if 0 <= c < cum[-1]])):
        if ss and s - ss[-1] < 0.012:  # a cut within 12 mm of a corner: one station, the corner wins
            if s in corners:
                ss[-1] = s
            continue
        ss.append(s)
    if len(ss) > 1 and cum[-1] - ss[-1] < 0.012:
        ss.pop()
    out = []
    for k, s in enumerate(ss):
        out.append(s)
        nxt = ss[k + 1] if k + 1 < len(ss) else cum[-1]
        parts = math.ceil((nxt - s) / max_side - 1e-9) if max_side > 0 else 1
        out += [s + j * (nxt - s) / parts for j in range(1, parts)]
    return out, cum


def ray_hit(xy, cum, p, d, max_t=4.0):
    """First crossing of the ray p + t*d (0 < t <= max_t) with the closed polyline: (s, t) or None."""
    best = None
    for i in range(len(xy)):
        a, b = xy[i], xy[(i + 1) % len(xy)]
        ex, ey = b[0] - a[0], b[1] - a[1]
        den = d[0] * ey - d[1] * ex
        if abs(den) < 1e-12:
            continue
        wx, wy = a[0] - p[0], a[1] - p[1]
        t = (wx * ey - wy * ex) / den
        u = (wx * d[1] - wy * d[0]) / den
        if 1e-9 < t <= max_t and -1e-9 <= u <= 1 + 1e-9 and (best is None or t < best[1]):
            best = (cum[i] + u * math.hypot(ex, ey), t)
    return best


def station_dir(xy, cum, s, other, cother, sign):
    """Cast direction at station s of a CCW ring towards the other ring (sign +1 inward/left, -1 outward/right).

    Edge interior: the edge normal. Vertex: the bisector; but a vertex on a RETURN edge (an edge across the other
    ring's local direction) casts along that return, so the return's cap cell collapses to a line (no wedge)."""
    n = len(xy)
    L = cum[-1]
    s = s % L
    k = next((i for i in range(n) if abs(cum[i] - s) < 1e-6), None)
    def nrm(i):
        a, b = xy[i % n], xy[(i + 1) % n]
        ex, ey = b[0] - a[0], b[1] - a[1]
        h = math.hypot(ex, ey) or 1.0
        return (-ey / h * sign, ex / h * sign), (ex / h, ey / h)
    if k is None:
        i = max(0, int(np.searchsorted(cum, s, side="right")) - 1)
        return nrm(i)[0]
    (n0, t0), (n1, t1) = nrm(k - 1), nrm(k)
    p = xy[k]
    so = project(other, cother, p)[0]
    q0, q1 = point_at(other, cother, so - 0.05), point_at(other, cother, so + 0.05)
    ot = (q1[0] - q0[0], q1[1] - q0[1])
    h = math.hypot(*ot) or 1.0
    ot = (ot[0] / h, ot[1] / h)
    for (ex, ey), into in (((-t0[0], -t0[1]), None), ((t1[0], t1[1]), None)):
        if abs(ex * ot[0] + ey * ot[1]) < RETURN_DOT:  # this adjacent edge is a return: cast along it, towards the other ring
            cand = (ex, ey) if (ex * n0[0] + ey * n0[1] + ex * n1[0] + ey * n1[1]) > 0 else (-ex, -ey)
            if ray_hit(other, cother, p, cand):
                return cand
    bx, by = n0[0] + n1[0], n0[1] + n1[1]
    h = math.hypot(bx, by)
    return (bx / h, by / h) if h > 1e-9 else n1


def cast(xy, cum, s, other, cother, sign):
    p = point_at(xy, cum, s)
    hit = ray_hit(other, cother, p, station_dir(xy, cum, s, other, cother, sign))
    return hit[0] if hit else project(other, cother, p)[0]


def sync(xa, cuts_a, xb, cuts_b, max_side, snap):
    """Shared station sequence of rings A and B: list of (sA, sB) with sB unwrapped to start at A's s=0 partner."""
    sa, ca = ring_stations(xa, cuts_a, max_side)
    sb, cb = ring_stations(xb, cuts_b, max_side)
    La, Lb = ca[-1], cb[-1]
    sgn = 1.0 if Polygon(xa).contains(Polygon(xb).representative_point()) else -1.0
    pairs = []
    for s in sa:
        pairs.append([s, cast(xa, ca, s, xb, cb, sgn), "A"])
    for s in sb:
        pairs.append([cast(xb, cb, s, xa, ca, -sgn), s, "B"])
    # rings that cross (a B fin poking through A) share the crossing point: a station of both, else that cap
    # cell is a bow-tie
    from shapely.geometry import LineString as _LS
    cross = _LS(list(xa) + [xa[0]]).intersection(_LS(list(xb) + [xb[0]]))
    for g in getattr(cross, "geoms", [cross]):
        if g.geom_type == "Point":
            pairs.append([project(xa, ca, (g.x, g.y))[0], project(xb, cb, (g.x, g.y))[0], "AB"])
    b0 = pairs[0][1]
    for p in pairs:
        p[1] = (p[1] - b0) % Lb
        if p[0] < 0.25 * La and p[1] > 0.75 * Lb:  # unwrap across the start
            p[0] += La
        elif p[0] > 0.75 * La and p[1] < 0.25 * Lb:
            p[1] += Lb
    pairs.sort(key=lambda p: (p[0], p[1]))
    # Arcs (D337 fillets): a cast from an arc vertex lands in a cluster on the other ring's shorter arc. Map arc
    # stations of either ring by arc length between the nearest non-arc stations of that ring instead.
    def arc_flags(xy):
        n = len(xy)
        out = set()
        for i in range(n):
            a, b, c = xy[i - 1], xy[i], xy[(i + 1) % n]
            t = math.degrees(abs(math.atan2((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]),
                                            (b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1]))))
            if 2.0 < t < 30.0 and math.dist(a, b) < 0.6 and math.dist(b, c) < 0.6:
                out.add(i)
        return out
    for col, xy_, cum_, own in ((0, xa, ca, "A"), (1, xb, cb, "B")):
        arcs = {round(cum_[i], 6) for i in arc_flags(xy_)}
        oc = 1 - col
        anchors = [p for p in pairs if p[2] == own and round(p[col] if col == 0 else (p[col] + b0) % Lb, 6) not in arcs]
        for p in pairs:
            raw = p[col] if col == 0 else round((p[col] + b0) % Lb, 6)
            if p[2] != own or round(raw, 6) not in arcs:
                continue
            lo = max((q for q in anchors if q[col] < p[col]), default=None, key=lambda q: q[col])
            hi = min((q for q in anchors if q[col] > p[col]), default=None, key=lambda q: q[col])
            if lo is None or hi is None or hi[oc] <= lo[oc] or hi[col] - lo[col] > 4.0:
                continue
            p[oc] = lo[oc] + (hi[oc] - lo[oc]) * (p[col] - lo[col]) / (hi[col] - lo[col])
    pairs.sort(key=lambda p: (p[0], p[1]))
    # merge partner pairs that land within `snap` on either ring: keep each side's own station (no sliver strip)
    merged = []
    for p in pairs:
        q = merged[-1] if merged else None
        if q and abs(p[0] - q[0]) < snap and abs(p[1] - q[1]) < snap and p[2] != q[2] and "AB" not in q[2]:
            if p[2] == "A":
                q[0] = p[0]
            else:
                q[1] = p[1]
            q[2] = "AB"
            continue
        merged.append(p)
    # B order must follow A order. Keep the longest chain of pairs monotone on both rings (LIS on sB); a dropped
    # pair keeps its own-ring station and gets its partner by linear interpolation between the kept neighbours
    # (still one quad per cell, no fan, no T-junction).
    # weighted LIS (O(n^2), n ~ 300): a pair that is a station of BOTH rings ("AB") must stay
    wgt = [1000.0 if p[2] == "AB" else 1.0 for p in merged]
    best_w, prev = [0.0] * len(merged), [-1] * len(merged)
    for i, p in enumerate(merged):
        best_w[i] = wgt[i]
        for k in range(i):
            if merged[k][1] <= p[1] + 1e-9 and merged[k][0] <= p[0] + 1e-9 and best_w[k] + wgt[i] > best_w[i]:
                best_w[i], prev[i] = best_w[k] + wgt[i], k
    keep, i = set(), (max(range(len(merged)), key=lambda k: best_w[k]) if merged else -1)
    while i >= 0:
        keep.add(i)
        i = prev[i]
    if any(p[2] == "AB" and k not in keep for k, p in enumerate(merged)):
        sys.exit("refused: two shared stations cross")
    viol = len(merged) - len(keep)
    kept = sorted(keep)
    for i in range(len(merged)):
        if i in keep:
            continue
        col = 1 if merged[i][2] == "B" else 0  # neighbours along the ring that owns the station
        lo = max((k for k in kept if merged[k][col] <= merged[i][col]), default=None, key=lambda k: merged[k][col])
        hi = min((k for k in kept if merged[k][col] >= merged[i][col]), default=None, key=lambda k: merged[k][col])
        a0, b0_ = (merged[lo][0], merged[lo][1]) if lo is not None else (0.0, 0.0)
        a1, b1_ = (merged[hi][0], merged[hi][1]) if hi is not None else (La, Lb)
        t = 0.0 if a1 - a0 <= 1e-9 else (merged[i][0] - a0) / (a1 - a0)
        if merged[i][2] == "B":  # a B corner keeps sB; its A partner is interpolated
            u = 0.0 if b1_ - b0_ <= 1e-9 else (merged[i][1] - b0_) / (b1_ - b0_)
            merged[i][0] = a0 + u * (a1 - a0)
        else:
            merged[i][1] = b0_ + t * (b1_ - b0_)
    merged.sort(key=lambda p: (p[0], p[1]))
    for i in range(1, len(merged)):
        if merged[i][1] < merged[i - 1][1] - 1e-6:
            print([(round(p[0], 3), round(p[1], 3), p[2]) for p in merged[max(0, i - 3):i + 3]], La, Lb)
            sys.exit("refused: station order still crossed at sA=%.3f" % merged[i][0])
    # Spread: projections clamped at a corner give runs of pairs with one partner position (a fan). Keep the run's
    # own-ring station (anchor) and spread the others evenly along the partner ring between the neighbours.
    for col, own, L in ((1, "B", Lb), (0, "A", La)):
        n = len(merged)
        i = 0
        while i < n:
            j = i
            while j + 1 < n and abs(merged[j + 1][col] - merged[i][col]) < 1e-6:
                j += 1
            if j > i:
                run = list(range(i, j + 1))
                anc = next((k for k in run if merged[k][2] in (own, "AB")), None)
                if anc is None:
                    anc = run[0] if i > 0 else run[-1]
                lo_v = merged[i - 1][col] if i > 0 else merged[-1][col] - L
                hi_v = merged[j + 1][col] if j + 1 < n else merged[0][col] + L
                before = [k for k in run if k < anc]
                after = [k for k in run if k > anc]
                for m, k in enumerate(before):
                    merged[k][col] = lo_v + (merged[anc][col] - lo_v) * (m + 1) / (len(before) + 1)
                for m, k in enumerate(after):
                    merged[k][col] = merged[anc][col] + (hi_v - merged[anc][col]) * (m + 1) / (len(after) + 1)
            i = j + 1
    # Relax: a station that is not its ring's own corner and sits < 2 cm from a neighbour moves to the middle of its
    # two neighbours on that ring (no sliver strip, order kept).
    relaxed = 0
    for _ in range(300):
        moved = False
        n = len(merged)
        for col, own, L in ((0, "A", La), (1, "B", Lb)):
            for k in range(n):
                pv = merged[k - 1][col] - (L if k == 0 else 0.0)
                nx = merged[(k + 1) % n][col] + (L if k == n - 1 else 0.0)
                cur = merged[k][col]
                if merged[k][2] in (own, "AB") or min(cur - pv, nx - cur) >= 0.02 or nx - pv < 1e-3:
                    continue
                new = (pv + nx) / 2
                if abs(new - cur) > 1e-5:
                    merged[k][col] = new
                    moved = True
                    relaxed += 1
        if not moved:
            break
    # Triangle repair (belt-cap-quad-ladder rule 2): a cell with 3 distinct corners gets a new station so that it
    # splits into a dropped zero-area sliver and a quad; a pair sharing one ring position is moved to the middle
    # of the next ring edge. Each fix adds at most one full-height station.
    def pts(m):
        return [point_at(xa, ca, p[0]) for p in m], [point_at(xb, cb, p[1] + b0) for p in m]

    def ulen(q):
        u = []
        for p in q:
            if not any(math.dist(p, r) < 1e-6 for r in u):
                u.append(p)
        ar = 0.5 * sum(u[k][0] * u[(k + 1) % len(u)][1] - u[(k + 1) % len(u)][0] * u[k][1] for k in range(len(u)))
        return len(u), abs(ar)

    fixes = 0
    for _ in range(200):
        pa, pb = pts(merged)
        n = len(merged)
        bad = next((i for i in range(n) if ulen([pa[i], pa[(i + 1) % n], pb[(i + 1) % n], pb[i]]) [0] == 3
                    and ulen([pa[i], pa[(i + 1) % n], pb[(i + 1) % n], pb[i]])[1] > 1e-6), None)
        if bad is None:
            break
        if os.environ.get("DBG") and _ > 190:
            print("DBG", bad, [(tuple(round(v, 3) for v in merged[k][:2]), merged[k][2],
                                tuple(round(v, 3) for v in pa[k]), tuple(round(v, 3) for v in pb[k]))
                               for k in range(bad - 1, min(bad + 3, n))])
        i, j = bad, (bad + 1) % n
        sAj = merged[j][0] + (La if j == 0 else 0.0)
        sBj = merged[j][1] + (Lb if j == 0 else 0.0)
        la, lb = math.dist(pa[i], pa[j]), math.dist(pb[i], pb[j])
        if math.dist(pa[i], pb[i]) < 1e-6 or math.dist(pa[j], pb[j]) < 1e-6:
            k = i if math.dist(pa[i], pb[i]) < 1e-6 else j
            sAk, sBk = (merged[i][0], merged[i][1]) if k == i else (sAj, sBj)
            new = [(merged[i][0] + sAj) / 2, sBk, "M"] if la >= lb else [sAk, (merged[i][1] + sBj) / 2, "M"]
            merged.insert(i + 1, new)
        elif la < 1e-6 or lb < 1e-6:
            col, L = (0, La) if la < 1e-6 else (1, Lb)
            own = "A" if col == 0 else "B"
            mv = i if merged[j][2] in (own, "AB") else j
            if merged[mv][2] in (own, "AB"):
                sys.exit("refused: two own stations of ring %s coincide at cell %d" % (own, i))
            nb = (mv - 1) % n if mv == i else (mv + 1) % n
            other = merged[nb][col] + (L if (mv == j and nb == 0) else 0.0) - (L if (mv == i and mv == 0) else 0.0)
            merged[mv][col] = (merged[mv][col] + other) / 2
        else:
            sys.exit("refused: cap cell %d is a triangle with no shared corner" % i)
        fixes += 1
    pa, pb = pts(merged)
    snapped = 0
    for i in range(len(merged)):
        if 0 < math.dist(pa[i], pb[i]) < snap:
            pb[i] = pa[i]
            snapped += 1
    return merged, pa, pb, {"stations_A": len(sa), "stations_B": len(sb), "pairs": len(merged), "order_fixes": viol,
                            "triangle_fixes": fixes, "snapped": snapped, "b0": b0, "La": La, "Lb": Lb}


def dedup(points):
    """Unique consecutive station points -> (ring xy, index of each pair's vertex)."""
    xy, idx = [], []
    for p in points:
        if xy and math.dist(xy[-1], p) < 1e-3:
            idx.append(len(xy) - 1)
            continue
        xy.append(p)
        idx.append(len(xy) - 1)
    if len(xy) > 1 and math.dist(xy[0], xy[-1]) < 1e-3:
        xy.pop()
        idx = [i if i < len(xy) else 0 for i in idx]
    return xy, idx


def remap(old_s, merged, side, new_cum, idx, L_old, b0=0.0):
    """Old ring s (a station) -> s on the station polyline."""
    col = 0 if side == "A" else 1
    v = (old_s - b0) % L_old if side == "B" else old_s
    k = min(range(len(merged)), key=lambda i: abs(merged[i][col] - v))
    if abs(merged[k][col] - v) > 0.015 and abs(abs(merged[k][col] - v) - L_old) > 0.015:
        print("DBG remap", v, [(round(m[0], 3), round(m[1], 3), m[2]) for m in merged if abs(m[col] - v) < 0.5])
        sys.exit("refused: s=%.4f (%s) is not a station (nearest %.4f)" % (old_s, side, merged[k][col]))
    return new_cum[idx[k]]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("floor_a")
    ap.add_argument("floor_b")
    ap.add_argument("crop")
    ap.add_argument("keys")
    ap.add_argument("out")
    ap.add_argument("--max-side", type=float, default=3.6)
    ap.add_argument("--snap", type=float, default=0.03)
    a = ap.parse_args(argv)
    if os.path.exists(a.out):
        sys.exit("refused: OUT_DIR exists, outputs are versioned")
    fa = json.load(open(a.floor_a, encoding="utf-8"))
    fb = json.load(open(a.floor_b, encoding="utf-8"))
    ra, rb = fa["rings"][0], fb["rings"][0]
    merged, pa, pb, rep = sync(ra["xy"], ra.get("cuts", []), rb["xy"], rb.get("cuts", []), a.max_side, a.snap)
    xa, ia = dedup(pa)
    xb, ib = dedup(pb)
    ca, cb = perim_s(xa), perim_s(xb)
    La_old, Lb_old = rep["La"], rep["Lb"]

    # B window sills from the source (two sill levels in the belt storey)
    d = np.load(a.crop)
    tri, obj, names = d["tri"], d["obj"], [str(n) for n in d["names"]]
    keys = json.load(open(a.keys, encoding="utf-8"))
    win = [i for i, n in enumerate(names) if any(k in n for k in keys["windows"])]
    sills = []
    for o in win:
        m = obj == o
        if not m.any():
            continue
        p = tri[m].reshape(-1, 3)
        z0 = float(p[:, 2].min())
        if 24.1 <= z0 <= 24.5:
            sills.append((project(rb["xy"], perim_s(rb["xy"]), p[:, :2].mean(0))[0], z0))

    def spec(side, z0, floors):
        f, ring, cum, idx, L_old = (fa, ra, ca, ia, La_old) if side == "A" else (fb, rb, cb, ib, Lb_old)
        b0 = 0.0 if side == "A" else rep["b0"]
        xy = xa if side == "A" else xb
        zones = []
        for s0, s1, m in ring["zones"]:
            n0 = remap(s0, merged, side, cum, idx, L_old, b0)
            n1 = cum[-1] if abs(s1 - L_old) < 2e-3 else remap(s1, merged, side, cum, idx, L_old, b0)
            if n1 < n0:  # the zone wraps the new start: split it
                zones += [[n0, cum[-1], m], [0.0, n1, m]]
            else:
                zones.append([n0, n1, m])
        wins = []
        for w in f["windows"]:
            n0 = remap(w[1], merged, side, cum, idx, L_old, b0)
            n1 = remap(w[2], merged, side, cum, idx, L_old, b0)
            if n1 <= n0:
                sys.exit("refused: window %r spans the station start" % (w,))
            if side == "A":
                wl, wh = 1, 2
            else:
                mid = (w[1] + w[2]) / 2
                near = [z for s, z in sills if abs(s - mid) < (w[2] - w[1]) / 2 + 0.05]
                if not near:
                    sys.exit("refused: belt window %r has no source sill" % (w,))
                wl, wh = (1 if min(near) < 24.33 else 2), 3
            wins.append([0, round(n0, 6), round(n1, 6), wl, wh, w[5]])
        return {"units": "m", "step": STEP, "z0": z0, "floors": floors, "loops": LOOPS[side],
                "rings": [{"xy": [[round(x, 6), round(y, 6)] for x, y in xy], "cuts": [], "zones": zones}],
                "windows": wins, "insets": [], "materials": f["materials"], "wall_tile_m": 3.0,
                "source": {"floor": os.path.basename(a.floor_a if side == "A" else a.floor_b), "ring": side}}

    os.makedirs(a.out)
    for run, side, z0, floors in RUNS:
        json.dump(spec(side, z0, floors), open(os.path.join(a.out, "module_%s.json" % run), "w", encoding="utf-8"), indent=1)
    # caps: cell i between pair i and i+1 (wrapping); degenerate cells (<= 2 distinct corners or zero area) dropped
    zone_a = spec("A", 0, 1)["rings"][0]["zones"]
    cells, tris, dropped, short = [], [], 0, []
    n = len(merged)
    for i in range(n):
        j = (i + 1) % n
        quad = [xa[ia[i]], xa[ia[j]], xb[ib[j]], xb[ib[i]]]
        uniq = []
        for p in quad:
            if not any(math.dist(p, q) < 1e-3 for q in uniq):
                uniq.append(p)
        area = 0.5 * sum(uniq[k][0] * uniq[(k + 1) % len(uniq)][1] - uniq[(k + 1) % len(uniq)][0] * uniq[k][1]
                         for k in range(len(uniq))) if len(uniq) >= 3 else 0.0
        if len(uniq) < 3 or abs(area) < 1e-6:
            dropped += 1
            continue
        sm = (ca[ia[i]] + (ca[ia[j]] if ia[j] else ca[-1])) / 2
        mat = next((m for s0, s1, m in zone_a if s0 - 1e-4 <= sm <= s1 + 1e-4), zone_a[0][2])
        cells.append({"xy": [[round(x, 6), round(y, 6)] for x, y in uniq], "mat": mat})
        if min(math.dist(uniq[k], uniq[(k + 1) % len(uniq)]) for k in range(len(uniq))) < 0.02:
            short.append([round(uniq[0][0], 3), round(uniq[0][1], 3)])
        if len(uniq) == 3:
            tris.append({"at": [round(uniq[0][0], 3), round(uniq[0][1], 3)], "pair": i})
    caps = {"z": CAPS_Z, "a_ccw": ring_ccw(xa), "cells": cells,
            "report": dict(rep, cells=len(cells), triangles=len(tris), dropped=dropped,
                           triangle_cells=tris, short_edge_cells=short, ring_A=len(xa), ring_B=len(xb))}
    json.dump(caps, open(os.path.join(a.out, "caps.json"), "w", encoding="utf-8"), indent=1)
    print(json.dumps(caps["report"])[:1500])


if __name__ == "__main__":
    main()
