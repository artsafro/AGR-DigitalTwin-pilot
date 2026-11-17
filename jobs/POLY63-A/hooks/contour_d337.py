"""Hook `before` stage `body` (#1619 polygon, site 63 tower A): contour clean-up by D341 + rounded corners by D337.

Pattern: n/a | new-case: facade relief steps flattened and rounded plan corners rebuilt from their radius.

uv run python contour_d337.py FLOOR.json OUT.json [--sagitta 0.02] [--tex-step 0.6] [--max-step 0.4]
    [--max-seg 1.0] [--max-turn 45] [--min-arc 30]

1. D341 relief: a short edge (<= --max-step + 5 cm) between two parallel neighbours offset by <= --max-step is a
   relief step (the +100 mm vent-facade panels of site 63) - texture, not geometry. The run lying INSIDE moves out
   onto the line of the outer run (outer envelope), the step disappears (no vertical without a window or zone
   reason, D340).
2. D337 / BM-07: an arc = a run of vertices turning the same way by <= --max-turn deg each, chords <= --max-seg, total
   turn >= --min-arc. Its radius is the least-squares circle of the run (>= 3 points); the corner is rebuilt as a
   fillet of that radius tangent to the two straight walls; segments per 90 deg = smallest n with
   R * (1 - cos(45 deg / n)) <= --sagitta, ceil(n * angle / 90) for the arc, then snapped to the texture step
   (segment closest to tex_step / k, never fewer than the sagitta needs).
Windows [ring, s0, s1, lo, hi, depth] follow their plan points onto the new ring; the reveal depth changes by the
wall's move (moved out -> deeper). Refuses OUT equal to the input, a window that loses its run, a fillet longer than
its walls, and a ring that already carries zones (run this before the zones).
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from shapely.geometry import LineString, Point, Polygon


def turn_deg(a, b, c):
    t = math.atan2(c[1] - b[1], c[0] - b[0]) - math.atan2(b[1] - a[1], b[0] - a[0])
    return math.degrees((t + math.pi) % (2 * math.pi) - math.pi)


def n_per_90(radius, sagitta=0.02):
    """Smallest segment count per 90 deg whose chord sagitta R * (1 - cos(45 deg / n)) is <= sagitta [D337]."""
    if not (isinstance(radius, (int, float)) and math.isfinite(radius) and radius > 0
            and isinstance(sagitta, (int, float)) and math.isfinite(sagitta) and sagitta > 0):
        raise ValueError("radius and sagitta must be finite and > 0, got %r, %r" % (radius, sagitta))
    n = 1
    while radius * (1 - math.cos(math.radians(45.0 / n))) > sagitta + 1e-12:
        n += 1
    return n


def arc_segments(radius, angle_deg, sagitta=0.02, tex_step=0.0):
    """(n_sagitta, n_snapped, segment_m) for one arc; snapped so the segment ~ tex_step / k (k integer)."""
    if not (math.isfinite(angle_deg) and 0 < angle_deg <= 360):
        raise ValueError("arc angle must be in (0, 360] deg, got %r" % (angle_deg,))
    n0 = max(1, math.ceil(n_per_90(radius, sagitta) * angle_deg / 90.0 - 1e-9))
    length = radius * math.radians(angle_deg)
    if not tex_step or tex_step <= 0:
        return n0, n0, length / n0

    def miss(n):
        seg = length / n
        k = max(1, round(tex_step / seg))
        return abs(seg - tex_step / k) / seg

    # the fewest segments (>= the sagitta count) whose length is within 5 % of tex_step / k; else the closest
    cand = list(range(n0, 2 * n0 + 2))
    good = [n for n in cand if miss(n) <= 0.05]
    n1 = good[0] if good else min(cand, key=lambda n: (round(miss(n), 3), n))
    return n0, n1, length / n1


def fit_circle(pts):
    """Least-squares circle (Kasa) -> (cx, cy, R, rms)."""
    p = np.asarray(pts, float)
    A = np.c_[2 * p, np.ones(len(p))]
    b = (p ** 2).sum(1)
    (cx, cy, c), *_ = np.linalg.lstsq(A, b, rcond=None)
    R = math.sqrt(c + cx * cx + cy * cy)
    rms = float(np.sqrt(((np.hypot(p[:, 0] - cx, p[:, 1] - cy) - R) ** 2).mean()))
    return float(cx), float(cy), R, rms


def _cross(u, v):
    return u[0] * v[1] - u[1] * v[0]


def _meet(p, d, q, e):
    """Intersection of lines p + t d and q + s e (None when parallel)."""
    den = _cross(d, e)
    if abs(den) < 1e-9:
        return None
    t = _cross((q[0] - p[0], q[1] - p[1]), e) / den
    return (p[0] + t * d[0], p[1] + t * d[1])


def _onto(p, q, e, lp, ld, reach=1.0):
    """Vertex p (on the line q + s e) moved onto the line lp + t ld: the intersection of both lines, or - when the
    lines are (near) parallel and the intersection runs off more than `reach` m - the foot of p on the line."""
    v = _meet(q, e, lp, ld)
    if v is not None and math.dist(v, p) <= reach:
        return v
    L = math.hypot(*ld)
    t = ((p[0] - lp[0]) * ld[0] + (p[1] - lp[1]) * ld[1]) / (L * L)
    return (lp[0] + t * ld[0], lp[1] + t * ld[1])


def drop_collinear(xy, tol_deg=0.5):
    out = [tuple(p) for p in xy]
    changed = True
    while changed and len(out) > 3:
        changed = False
        for i in range(len(out)):
            a, b, c = out[i - 1], out[i], out[(i + 1) % len(out)]
            if math.dist(a, b) < 1e-6 or abs(turn_deg(a, b, c)) < tol_deg:
                del out[i]
                changed = True
                break
    return out


def flatten_steps(xy, max_step=0.4, par_deg=10.0, min_ref=1.0):
    """Remove relief steps: edge k short, edges k-1 and k+1 parallel (same direction), offset <= max_step.

    The run lying INSIDE (D341: the contour is the outer envelope) is moved onto the line of the outer run, which
    must be at least `min_ref` long (a wall, not the last chord of an arc); vertices are re-made as the
    intersections of the neighbouring edge lines. Returns (xy, rows)."""
    pts = drop_collinear(xy, 2.0)
    rows = []
    while True:
        n = len(pts)
        hit = None
        for k in range(n):
            a, b = pts[k], pts[(k + 1) % n]
            if math.dist(a, b) > max_step + 0.05:
                continue
            p0, p1 = pts[k - 1], a  # edge k-1
            q0, q1 = b, pts[(k + 2) % n]  # edge k+1
            d = (p1[0] - p0[0], p1[1] - p0[1])
            e = (q1[0] - q0[0], q1[1] - q0[1])
            ld, le = math.hypot(*d), math.hypot(*e)
            if ld < 1e-6 or le < 1e-6:
                continue
            if abs(_cross(d, e)) / (ld * le) > math.sin(math.radians(par_deg)) or d[0] * e[0] + d[1] * e[1] <= 0:
                continue
            off = _cross(d, (q0[0] - p0[0], q0[1] - p0[1])) / ld  # >0: edge k+1 lies left (inside a CCW ring)
            if abs(off) > max_step or abs(off) < 1e-4:
                continue
            if (le if off < 0 else ld) < min_ref:  # the outer run must be a wall, not an arc chord
                continue
            hit = (k, ld, le, off)
            break
        if hit is None:
            return pts, rows
        k, ld, le, off = hit
        n = len(pts)
        # moving edge k-1 onto edge k+1's line (or the reverse): drop the step edge, keep one line for both
        # D341 outer envelope: the run that lies INSIDE moves out onto the outer run's line (never inward)
        if off < 0:  # edge k-1 lies inside: move it (vertices k-1, k) onto the line of edge k+1
            line_p, line_d = pts[(k + 1) % n], (pts[(k + 2) % n][0] - pts[(k + 1) % n][0],
                                                  pts[(k + 2) % n][1] - pts[(k + 1) % n][1])
            prev_p, prev_d = pts[k - 2], (pts[k - 1][0] - pts[k - 2][0], pts[k - 1][1] - pts[k - 2][1])
            v = _onto(pts[k - 1], prev_p, prev_d, line_p, line_d)
            if v is None:
                return pts, rows
            ins = (k - 1) % n
            seq = pts[:]
            seq[ins] = v
            keep = [i for i in range(n) if i not in (k, (k + 1) % n)]
            new = [seq[i] for i in keep]
            moved = "out" if off < 0 else "in"
            rows.append({"at": [round(pts[k][0], 2), round(pts[k][1], 2)], "step_m": round(abs(off), 3),
                         "moved_run_m": round(ld, 3), "moved": moved})
        else:  # move edge k+1 (vertices k+1, k+2) onto the line of edge k-1
            line_p, line_d = pts[k - 1], (pts[k][0] - pts[k - 1][0], pts[k][1] - pts[k - 1][1])
            nxt_p, nxt_d = pts[(k + 2) % n], (pts[(k + 3) % n][0] - pts[(k + 2) % n][0],
                                              pts[(k + 3) % n][1] - pts[(k + 2) % n][1])
            v = _onto(pts[(k + 2) % n], nxt_p, nxt_d, line_p, line_d)
            if v is None:
                return pts, rows
            seq = pts[:]
            seq[(k + 2) % n] = v
            keep = [i for i in range(n) if i not in (k, (k + 1) % n)]
            new = [seq[i] for i in keep]
            moved = "out" if off > 0 else "in"
            rows.append({"at": [round(pts[k][0], 2), round(pts[k][1], 2)], "step_m": round(abs(off), 3),
                         "moved_run_m": round(le, 3), "moved": moved})
        pts = drop_collinear(new, 2.0)


def find_arcs(xy, max_seg=1.0, max_turn=45.0, min_arc=30.0, min_turn=1.0):
    """Arc runs [i0..i1] (cyclic): every vertex turns the same way by min..max_turn, inner chords <= max_seg."""
    n = len(xy)
    t = [turn_deg(xy[i - 1], xy[i], xy[(i + 1) % n]) for i in range(n)]
    L = [math.dist(xy[i], xy[(i + 1) % n]) for i in range(n)]
    ok = [min_turn <= abs(t[i]) <= max_turn for i in range(n)]
    start = next((i for i in range(n) if not ok[i]), None)
    if start is None:
        return []
    runs, cur = [], []
    for m in range(1, n + 1):
        k = (start + m) % n
        if ok[k] and (not cur or (t[k] > 0) == (t[cur[-1]] > 0) and L[cur[-1]] <= max_seg):
            cur.append(k)
            continue
        if len(cur) >= 3 and abs(sum(t[i] for i in cur)) >= min_arc:
            runs.append(cur)
        cur = [k] if ok[k] else []
    return runs


def fillets(xy, sagitta=0.02, tex_step=0.0, min_wall=1.0, **kw):
    """Rebuild every arc run as a fillet of its fitted radius; returns (xy, rows).

    The walls of the fillet are the nearest edges of at least `min_wall` before and after the run (the chord that
    bridges the last arc vertex to the wall is not a wall); every vertex between them is replaced."""
    pts = [tuple(p) for p in xy]
    n = len(pts)
    runs = find_arcs(pts, **kw)
    repl, rows = {}, []
    for run in runs:
        cx, cy, R, rms = fit_circle([pts[i] for i in run])
        j0, j1 = run[0], run[-1]
        for _ in range(2):
            if math.dist(pts[j0 - 1], pts[j0]) < min_wall:
                j0 = (j0 - 1) % n
            if math.dist(pts[j1], pts[(j1 + 1) % n]) < min_wall:
                j1 = (j1 + 1) % n
        span = [j0]
        while span[-1] != j1:
            span.append((span[-1] + 1) % n)
        i0 = run[0]
        a, b = pts[j0 - 1], pts[j0]
        c, d = pts[j1], pts[(j1 + 1) % n]
        d1 = ((b[0] - a[0]) / math.dist(a, b), (b[1] - a[1]) / math.dist(a, b))
        d2 = ((d[0] - c[0]) / math.dist(c, d), (d[1] - c[1]) / math.dist(c, d))
        C = _meet(a, d1, c, d2)
        th = math.atan2(_cross(d1, d2), d1[0] * d2[0] + d1[1] * d2[1])
        if C is None or abs(th) < 1e-3:
            raise ValueError("arc at %r: the walls are parallel" % (pts[i0],))
        tl = R * math.tan(abs(th) / 2)
        if tl > math.dist(a, C) - 0.05 or tl > math.dist(C, d) - 0.05:
            raise ValueError("arc at %r: fillet R %.3f needs %.3f m of wall, walls are shorter" % (pts[i0], R, tl))
        T1 = (C[0] - d1[0] * tl, C[1] - d1[1] * tl)
        T2 = (C[0] + d2[0] * tl, C[1] + d2[1] * tl)
        sg = 1.0 if th > 0 else -1.0
        nrm = (-d1[1] * sg, d1[0] * sg)  # towards the centre
        O = (T1[0] + nrm[0] * R, T1[1] + nrm[1] * R)
        a0 = math.atan2(T1[1] - O[1], T1[0] - O[0])
        ang = math.degrees(abs(th))
        n0, n1, seg = arc_segments(R, ang, sagitta, tex_step)
        arc = [(O[0] + R * math.cos(a0 + th * j / n1), O[1] + R * math.sin(a0 + th * j / n1)) for j in range(n1 + 1)]
        arc[0], arc[-1] = T1, T2
        repl[j0] = (span, arc)
        rows.append({"at": [round(C[0], 2), round(C[1], 2)], "radius_m": round(R, 3), "fit_rms_m": round(rms, 4),
                     "angle_deg": round(ang, 1), "source_vertices": len(span), "n_sagitta": n0, "n": n1,
                     "segment_m": round(seg, 3), "sagitta_m": round(R * (1 - math.cos(math.radians(ang / n1 / 2))), 4)})
    skip = {i for run, _ in repl.values() for i in run}
    out = []
    for k in range(n):
        if k in repl:
            out.extend(repl[k][1])
        elif k not in skip:
            out.append(pts[k])
    return out, rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("floor")
    ap.add_argument("out")
    ap.add_argument("--sagitta", type=float, default=0.02)
    ap.add_argument("--tex-step", type=float, default=0.6)
    ap.add_argument("--max-step", type=float, default=0.4)
    ap.add_argument("--max-seg", type=float, default=1.0)
    ap.add_argument("--max-turn", type=float, default=45.0)
    ap.add_argument("--min-arc", type=float, default=30.0)
    ap.add_argument("--cut-snap", type=float, default=0.1,
                    help="a cut / window end within this of a contour vertex takes the vertex, m (BM-09)")
    a = ap.parse_args(argv)
    if os.path.realpath(a.out) == os.path.realpath(a.floor) or not a.out.endswith(".json"):
        sys.exit("refused: output must be a new .json, not the input")
    spec = json.load(open(a.floor, encoding="utf-8"))
    ring = spec["rings"][0]
    if ring.get("zones"):
        sys.exit("refused: run contour_d337 before the zones")
    old = LineString(ring["xy"] + [ring["xy"][0]])
    xy, steps = flatten_steps(ring["xy"], a.max_step)
    try:
        xy, arcs = fillets(xy, a.sagitta, a.tex_step, max_seg=a.max_seg, max_turn=a.max_turn, min_arc=a.min_arc)
    except ValueError as e:
        sys.exit("refused: %s" % e)
    rnd = []
    for x, y in xy:  # the floor spec keeps 0.1 mm; a point that rounds onto its neighbour is one point
        p = (round(x, 4), round(y, 4))
        if not rnd or math.dist(rnd[-1], p) > 1e-3:
            rnd.append(p)
    if math.dist(rnd[0], rnd[-1]) <= 1e-3:
        rnd.pop()
    xy = rnd
    poly = Polygon(xy)
    if not poly.is_valid or not poly.exterior.is_ccw:
        sys.exit("refused: the new contour is not a valid CCW polygon")
    new = poly.exterior
    corner_s = sorted(new.project(Point(p)) for p in xy)
    snapped = []

    def move(s):
        """Old perimeter position -> new; within --cut-snap of a contour vertex it takes the vertex (BM-09: no
        4-8 cm strip between a jamb and the arc's tangency point)."""
        t = new.project(old.interpolate(s))
        c = min(corner_s, key=lambda v: abs(v - t))
        if 1e-4 < abs(c - t) <= a.cut_snap:
            snapped.append(round(abs(c - t), 3))
            return c
        return t

    wins = []
    for w in spec.get("windows", []):
        s0, s1 = move(w[1]), move(w[2])
        if not s0 < s1 or s1 - s0 < 0.5 * (w[2] - w[1]):
            sys.exit("refused: window [%.3f, %.3f] loses its run on the new ring" % (w[1], w[2]))
        out = list(w[:3])
        out[1], out[2] = round(s0, 4), round(s1, 4)
        if len(w) > 5:  # the wall moved by dz along the outward normal: the frame stays, the reveal follows
            P = old.interpolate((w[1] + w[2]) / 2)
            dz = new.distance(P) * (1 if poly.contains(P) else -1)
            out += list(w[3:5]) + [round(w[5] + dz, 3)]
        wins.append(out)
    ring["cuts"] = sorted({round(move(c), 4) for c in ring.get("cuts", [])})
    ring["xy"] = [[round(x, 4), round(y, 4)] for x, y in xy]
    spec["windows"] = wins
    spec["contour_rules"] = {
        "steps": {"rule": "D341: relief step <= %.2f m is texture; the inner run moves out onto the outer run's line"
                          % a.max_step, "rows": steps},
        "arcs": {"rule": "D337/BM-07: fillet of the fitted radius, n per 90 deg from a %.3f m sagitta, snapped to the "
                         "%.2f m texture step" % (a.sagitta, a.tex_step), "rows": arcs},
        "cuts_snapped_to_vertex_m": snapped}
    spec["counts"]["contour_vertices"] = len(xy)
    spec["counts"]["perimeter_m"] = round(new.length, 3)
    spec["counts"]["reveal_m"] = sorted({w[5] for w in wins if len(w) > 5})
    with open(a.out, "x", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=1)
    print(json.dumps({"steps": len(steps), "arcs": arcs, "vertices": len(xy)}))


if __name__ == "__main__":
    main()
