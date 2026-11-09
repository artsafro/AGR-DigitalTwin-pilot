"""TOW02 body: a stack of rings with step soffits, plus ribbon-opening glass planes (runs inside Blender).

Engine gap: EG6 (panelised curtain-wall source: body built from measurements, docs/backlog.md).

A ring = spandrel band (base .. base+band_h) + glazed storey (.. base+ring_h) on one closed outline. All rings of
a stack have outlines with the same vertex count and order (vertex i of ring k = vertex i of ring k+1;
outputs/measure-v002/bend_rings/bend_rings.json). Outline edges carry intervals `flush solid` / `recessed (glass
behind)`; a recessed run is a hole in the storey row with reveals `reveal_m` deep (mitred at outline vertices,
jambs only at run ends) and a glass plane at mid reveal, `plane_overlap_m` beyond the opening on all sides.

Edges are of two kinds across the stack:
- fixed: one end (or both) never moves. Its columns are shared by all rings (no T-junctions): measured from the
  fixed end, they are every ring's end point plus the interval breakpoints, snapped within `snap_m` to the
  reference (last) ring's breakpoints.
- moving ("own"): the edge moves in every ring; each ring uses its own breakpoints (same count in every ring).
A run of moving edges between two fixed edges is a chain. Where ring k+1 differs from ring k, the step between
them is filled with quads between corresponding columns of the chain, cut into strips at the fractions where
the fixed edges at the chain ends have columns in their extension zone (between the two rings' end points); the
same fractions are added as columns to both fixed edges, so the strips meet the walls without T-junctions.
An edge that collapses in a ring (< 5 mm, a jog that disappears) is kept as one column and the next edge starts
`collapse_shift_m` further along itself, so the step stays quads.
Sliding walls (user decision 2026-10-21, F8 option A): a moving edge whose line between ring k and ring k+1 stays
within LINE_M (its ends only slide along it, e.g. the side walls of the bend projections) would give a step strip
narrower than its line offset (0.1-4 mm, xView Overlapping Faces). At such a join the upper ring's bottom points of
that edge are snapped onto the lower ring's line (the upper wall's band leans by <= LINE_M), no step is built for it,
and the walls and the neighbouring steps are cut where they share points on that line (resolve_tjunctions: every
point on the line becomes a vertex of every face edge it lies on; the n-gons are split into quads, a triangle only
where a point stays unpaired). Steps of moving edges between two sliding walls are not cut into strips; strips that
start at a fixed edge end on the sliding wall; a strip fraction that would give a strip < MIN_STRIP_M is dropped.
Fixed-edge columns are unchanged, so the stack top and bottom loops (seams to TOW02_top 64.7 and TOW02_soffit 6.9)
keep their vertices.
Coordinates: building-local (inspect_sections.py, rotation 56.7 deg) -> world on output. Faces are quads, triangles
only from resolve_tjunctions / seal_leftovers (reported).

    ns = {}; exec(open(path).read(), ns); ns["build"](cfg)   # from the Blender MCP / Python console
    blender -b <master.blend> --python scripts/build_body_blender.py -- <out_dir>
        rebuilds TOW02_body / TOW02_body_glass with CFG_TOW02 and puts the new meshes into the objects of that name
        (object, transform, collections kept); saves ONLY <out_dir>/tow02_master.blend and <out_dir>/body_info.json.
"""
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

LOCAL_ANGLE_DEG = 56.7
MAX_SIDE_M = 3.8
EPS_POS = 0.01           # positions closer than this are one column (user 2026-10-20: <= 1 cm is skipped)
END_EPS = 0.02           # interval breakpoints closer than this to an edge end are the end (piers >= 0.3 m)
COLLAPSE_M = 0.005       # an edge shorter than this has collapsed in that ring
WELD_M = 0.01            # generated points closer than this are one vertex (user: <= 1 cm is skipped)
LINE_M = 0.01            # a moving edge whose line moves less than this between two rings is one wall (sliding wall)
TJ_TOL_M = 1e-4          # a point closer than this to an edge interior (on a join line) is on that edge
MIN_STRIP_M = 0.006      # step strips narrower than this are not built (xView Overlapping Faces 5 mm + margin)


def to_world(x, y, z):
    """Building-local -> world: inverse of co_local = co_world @ R (R = rotZ(56.7 deg))."""
    a = math.radians(LOCAL_ANGLE_DEG)
    c, s = math.cos(a), math.sin(a)
    return Vector((x * c - y * s, x * s + y * c, z))


def V(p):
    return Vector((p[0], p[1]))


class Builder:
    """bmesh of generated quads: points within WELD_M are one vertex, degenerate and duplicate quads refused."""

    def __init__(self):
        self.bm = bmesh.new()
        self.grid, self.fset = {}, set()
        self.skipped = {"degenerate": 0, "duplicate": 0}

    def v(self, p):
        cell = tuple(int(math.floor(c / WELD_M)) for c in p)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for q, vert in self.grid.get((cell[0] + dx, cell[1] + dy, cell[2] + dz), ()):
                        if (Vector(q) - Vector(p)).length <= WELD_M:
                            return vert
        vert = self.bm.verts.new(to_world(*p))
        self.grid.setdefault(cell, []).append((tuple(p), vert))
        return vert

    def quad(self, pts, mat, want=None):
        vs = [self.v(p) for p in pts]
        if len(set(vs)) < 4:
            self.skipped["degenerate"] += 1
            return None
        a, b, c, d = (Vector(p) for p in pts)
        if ((c - a).cross(d - b)).length < 1e-8:
            self.skipped["degenerate"] += 1
            return None
        key = frozenset(vs)
        if key in self.fset:
            self.skipped["duplicate"] += 1
            return None
        self.fset.add(key)
        f = self.bm.faces.new(vs)
        f.material_index = mat
        if want is not None:
            f.normal_update()
            if f.normal.dot(want) < 0:
                f.normal_flip()
        return f


def _breaks(e):
    """Interior interval breakpoints of an edge, sorted, merged within EPS_POS."""
    ts = sorted(t for iv in e["intervals"] for t in (iv["t0"], iv["t1"]) if END_EPS < t < e["length"] - END_EPS)
    out = []
    for t in ts:
        if not out or t - out[-1] > EPS_POS:
            out.append(t)
    return out


def _gaps(breaks, L):
    full = [0.0] + breaks + [L]
    return [full[k + 1] - full[k] for k in range(len(full) - 1)]


def _add(pos, p, tol):
    if all(abs(p - q) > tol for q in pos):
        pos.append(p)


def prepare(rings, cfg):
    """Edge kinds, shared positions of fixed edges, splits of moving edges, chains and step fractions."""
    n = len(rings[0]["edges"])
    if any(len(r["edges"]) != n for r in rings):
        raise ValueError("rings differ in vertex count")
    for r in rings:                      # collapsed edge i: start edge i+1 `collapse_shift_m` further along it
        r["start_shift"] = [0.0] * n
        for i, e in enumerate(r["edges"]):
            if e["length"] < COLLAPSE_M:
                j = (i + 1) % n
                first = min([iv["t0"] for iv in r["edges"][j]["intervals"] if iv["t0"] > 1e-4] +
                            [r["edges"][j]["length"]])
                r["start_shift"][j] = min(cfg["collapse_shift_m"], 0.5 * first)
    ref_ring = rings[-1]
    kinds, pos, splits = [], [], []
    for i in range(n):
        A0, B0 = V(ref_ring["edges"][i]["a"]), V(ref_ring["edges"][i]["b"])
        ma = max((V(r["edges"][i]["a"]) - A0).length for r in rings)
        mb = max((V(r["edges"][i]["b"]) - B0).length for r in rings)
        if ma < 1e-3 and mb < 1e-3:
            kind = "still"
        elif ma < 1e-3:
            kind = "a"                   # end a fixed, end b moves
        elif mb < 1e-3:
            kind = "b"
        else:
            kind = "own"
        kinds.append(kind)
    snapped = _snap_fixed_lines(rings, kinds)
    for i in range(n):
        kind = kinds[i]
        if kind == "own":
            counts = {len(_breaks(r["edges"][i])) for r in rings if r["edges"][i]["length"] >= COLLAPSE_M}
            if len(counts) > 1:
                raise ValueError(f"edge {i}: moving edge with a different number of breakpoints per ring {counts}")
            gaps = _gaps(_breaks(ref_ring["edges"][i]), ref_ring["edges"][i]["length"])
            splits.append([max(1, math.ceil(g / MAX_SIDE_M - 1e-9)) for g in gaps])
            pos.append(None)
            continue
        splits.append(None)
        p = []
        for r in rings:                  # every ring's end point, exactly
            _add(p, r["edges"][i]["length"], EPS_POS)
        dist = (lambda r, t: t) if kind in ("a", "still") else (lambda r, t: r["edges"][i]["length"] - t)
        for t in _breaks(ref_ring["edges"][i]):
            _add(p, dist(ref_ring, t), cfg["snap_m"])
        for r in rings:
            for t in _breaks(r["edges"][i]):
                _add(p, dist(r, t), cfg["snap_m"])
        p.sort()
        full = [0.0] + p
        out = []
        for k in range(len(full) - 1):
            g = full[k + 1] - full[k]
            m = max(1, math.ceil(g / MAX_SIDE_M - 1e-9))
            out += [full[k] + g * s / m for s in range(1, m + 1)]
        pos.append(out)
    # chains: maximal runs of moving edges, bounded by fixed edges whose moving end touches the run
    chains = []
    i = 0
    seen = set()
    for start in range(n):
        if kinds[start] == "own" and kinds[(start - 1) % n] != "own" and start not in seen:
            run = []
            j = start
            while kinds[j % n] == "own":
                run.append(j % n)
                seen.add(j % n)
                j += 1
            left, right = (start - 1) % n, j % n
            if kinds[left] != "a" or kinds[right] != "b":
                raise ValueError(f"chain {run}: bounded by {left}:{kinds[left]} / {right}:{kinds[right]}")
            chains.append({"edges": run, "left": left, "right": right})
    # step fractions per chain and ring pair; add the matching columns to both bounding edges
    fracs = {}
    for k in range(len(rings) - 1):
        for c, ch in enumerate(chains):
            s_set = []
            for side in ("left", "right"):
                e = ch[side]
                L0, L1 = rings[k]["edges"][e]["length"], rings[k + 1]["edges"][e]["length"]
                if abs(L1 - L0) < 1e-4:
                    continue
                lo, hi = min(L0, L1), max(L0, L1)
                for d in pos[e]:
                    if lo + 1e-4 < d < hi - 1e-4:
                        _add(s_set, (d - L0) / (L1 - L0), EPS_POS / abs(L1 - L0))
            s_set.sort()
            fracs[(k, c)] = s_set
            for side in ("left", "right"):
                e = ch[side]
                L0, L1 = rings[k]["edges"][e]["length"], rings[k + 1]["edges"][e]["length"]
                if abs(L1 - L0) < 1e-4:
                    continue
                for s in s_set:
                    _add(pos[e], L0 + s * (L1 - L0), EPS_POS)
                pos[e].sort()
    return kinds, pos, splits, chains, fracs, snapped


def _snap_fixed_lines(rings, kinds):
    """Put every ring's vertices of fixed edges on the reference ring's lines (rings measured separately differ
    by ~1 mm, which would leave seams between rings). Returns the largest vertex move."""
    n = len(kinds)
    ref = rings[-1]["edges"]
    worst = 0.0
    for r in rings:
        E = r["edges"]
        verts = [V(E[i]["a"]) for i in range(n)]
        new = []
        for i in range(n):
            prev, cur = kinds[(i - 1) % n], kinds[i]
            if prev in ("still", "b") or cur in ("still", "a"):
                p = V(ref[i]["a"])                       # this vertex never moves
            elif prev == "a":                            # moving end b of the previous fixed edge
                p = _project(verts[i], V(ref[(i - 1) % n]["a"]), V(ref[(i - 1) % n]["b"]))
            elif cur == "b":                             # moving end a of this fixed edge
                p = _project(verts[i], V(ref[i]["a"]), V(ref[i]["b"]))
            else:
                p = verts[i]
            worst = max(worst, (p - verts[i]).length)
            new.append(p)
        edges = []
        for i in range(n):
            e = dict(E[i])
            a, b = new[i], new[(i + 1) % n]
            e["a"], e["b"], e["length"] = [a.x, a.y], [b.x, b.y], (b - a).length
            edges.append(e)
        r["edges"] = edges
    return worst


def _project(p, a, b):
    d = (b - a).normalized()
    return a + d * (p - a).dot(d)


def ring_columns(r, kinds, pos, splits):
    """Cyclic columns of one ring: (x, y, edge, recessed_after)."""
    cols = []
    for i, e in enumerate(r["edges"]):
        L = e["length"]
        a, b = V(e["a"]), V(e["b"])
        if L < COLLAPSE_M:               # kept as one column; the next edge starts `start_shift` further on
            cols.append((a.x, a.y, i, False))
            continue
        t_start = r["start_shift"][i]
        ts = [t_start]
        if kinds[i] == "own":
            full = [0.0] + _breaks(e) + [L]
            for k, m in enumerate(splits[i]):
                ts += [full[k] + (full[k + 1] - full[k]) * s / m for s in range(1, m + 1)]
            ts = [t for t in ts if t_start - 1e-9 <= t < L - EPS_POS]
        else:
            for d in pos[i]:
                t = d if kinds[i] in ("a", "still") else L - d
                if t_start + 1e-4 < t < L - 1e-4:
                    ts.append(t)
        ts = sorted(set(round(t, 7) for t in ts))
        for k, t in enumerate(ts):
            t1 = ts[k + 1] if k + 1 < len(ts) else L
            mid = 0.5 * (t + t1)
            rec = any(iv["kind"].startswith("recessed") and iv["t0"] - 1e-4 <= mid <= iv["t1"] + 1e-4
                      for iv in e["intervals"])
            p = a + (b - a) * (t / L)
            cols.append((p.x, p.y, i, rec))
    return cols


def edge_points(cols, i):
    """Columns of edge i plus its closing point (the next column in cyclic order)."""
    idx = [q for q, c in enumerate(cols) if c[2] == i]
    nxt = cols[(idx[-1] + 1) % len(cols)]
    return [(cols[q][0], cols[q][1]) for q in idx] + [(nxt[0], nxt[1])]


def offset_points(cols, depth):
    """Point `depth` inside the outline at every column (mitred at corners)."""
    n = len(cols)
    out = []
    for i in range(n):
        p0, p1, p2 = (Vector(cols[(i + k) % n][:2]) for k in (-1, 0, 1))
        d0, d1 = (p1 - p0).normalized(), (p2 - p1).normalized()
        n0, n1 = Vector((d0.y, -d0.x)), Vector((d1.y, -d1.x))   # outward = right of a CCW edge
        m = n0 + n1
        if m.length < 1e-6:
            m = n1
        m.normalize()
        out.append(p1 - m * (depth / max(m.dot(n1), 0.2)))
    return out


def sliding_walls(rings, chains):
    """{k: {edge}}: chain edges whose line between ring k and k+1 stays within LINE_M while an end moves."""
    out = {}
    for k in range(len(rings) - 1):
        s = set()
        for ch in chains:
            for i in ch["edges"]:
                e0, e1 = rings[k]["edges"][i], rings[k + 1]["edges"][i]
                if e0["length"] < COLLAPSE_M or e1["length"] < COLLAPSE_M:
                    continue
                a0, b0, a1, b1 = V(e0["a"]), V(e0["b"]), V(e1["a"]), V(e1["b"])
                if (a1 - a0).length < 1e-4 and (b1 - b0).length < 1e-4:
                    continue
                if max(_line_dist(a1, a0, b0), _line_dist(b1, a0, b0)) < LINE_M:
                    s.add(i)
        out[k] = s
    return out


def _line_dist(p, a, b):
    return (p - _project(p, a, b)).length


def _intersect(a0, b0, a1, b1):
    d0, d1 = b0 - a0, b1 - a1
    den = d0.x * d1.y - d0.y * d1.x
    if abs(den) < 1e-12:
        return None
    t = ((a1.x - a0.x) * d1.y - (a1.y - a0.y) * d1.x) / den
    return a0 + d0 * t


def snap_upper_cols(cols, lower, walls):
    """Columns of the upper ring with every point of a sliding wall (its columns and its closing point) projected
    onto the lower ring's line of that edge (onto the intersection when it closes one sliding wall and starts
    another). Returns (cols, largest move)."""
    n, out, worst = len(cols), list(cols), 0.0
    for q in range(n):
        own, prev = cols[q][2], cols[(q - 1) % n][2]
        lines = []
        if prev != own and prev in walls:                    # closing point of sliding wall `prev`
            lines.append(prev)
        if own in walls:
            lines.append(own)
        if not lines:
            continue
        L = [(V(lower["edges"][i]["a"]), V(lower["edges"][i]["b"])) for i in lines]
        p = V(cols[q])
        x = _intersect(*L[0], *L[1]) if len(L) == 2 else None
        x = x if x is not None else _project(p, *L[0])
        worst = max(worst, (x - p).length)
        out[q] = (x.x, x.y, own, cols[q][3])
    return out, worst


def build_stack(rings, cfg, body_name, glass_name, coll):
    kinds, pos, splits, chains, fracs, snapped = prepare(rings, cfg)
    B, G = Builder(), Builder()
    facade, reveal = 0, 1
    allcols = [ring_columns(r, kinds, pos, splits) for r in rings]
    walls = sliding_walls(rings, chains)
    botcols, snap_up = [allcols[0]], 0.0                   # ring k's bottom row: on ring k-1's sliding-wall lines
    for k in range(1, len(rings)):
        c, w = snap_upper_cols(allcols[k], rings[k - 1], walls[k - 1])
        botcols.append(c)
        snap_up = max(snap_up, w)
    for k, r in enumerate(rings):
        cols, bcols = allcols[k], botcols[k]
        n = len(cols)
        z0, z1, z2 = r["base"], r["base"] + r["band_h"], r["base"] + r["ring_h"]
        inner = offset_points(cols, cfg["reveal_m"])
        mid = offset_points(cols, cfg["reveal_m"] / 2)
        P = lambda i, z: (cols[i % n][0], cols[i % n][1], z)
        P0 = lambda i: (bcols[i % n][0], bcols[i % n][1], z0)
        Q = lambda i, z: (inner[i % n].x, inner[i % n].y, z)
        for i in range(n):
            j = (i + 1) % n
            B.quad((P0(i), P0(j), P(j, z1), P(i, z1)), facade)
            if not cols[i][3]:
                B.quad((P(i, z1), P(j, z1), P(j, z2), P(i, z2)), facade)
                continue
            B.quad((Q(i, z1), Q(j, z1), P(j, z1), P(i, z1)), reveal)            # sill
            B.quad((P(i, z2), P(j, z2), Q(j, z2), Q(i, z2)), reveal)            # head
            if not cols[(i - 1) % n][3]:
                B.quad((P(i, z1), P(i, z2), Q(i, z2), Q(i, z1)), reveal)        # jamb at run start
            if not cols[j][3]:
                B.quad((P(j, z1), Q(j, z1), Q(j, z2), P(j, z2)), reveal)        # jamb at run end
        start = next((i for i in range(n) if not cols[i][3]), None)             # glass planes per run
        i0 = None
        for s in range(1, n + 1):
            i = (start + s) % n
            if cols[i][3] and i0 is None:
                i0 = i
            if not cols[i][3] and i0 is not None:
                idx = [(i0 + q) % n for q in range(((i - i0) % n) + 1)]
                pts = [mid[q].copy() for q in idx]
                pts[0] -= (V(cols[idx[1]]) - V(cols[idx[0]])).normalized() * cfg["plane_overlap_m"]
                pts[-1] += (V(cols[idx[-1]]) - V(cols[idx[-2]])).normalized() * cfg["plane_overlap_m"]
                ga, gb = z1 - cfg["plane_overlap_m"], z2 + cfg["plane_overlap_m"]
                for q in range(len(pts) - 1):
                    G.quad(((pts[q].x, pts[q].y, ga), (pts[q + 1].x, pts[q + 1].y, ga),
                            (pts[q + 1].x, pts[q + 1].y, gb), (pts[q].x, pts[q].y, gb)), 0)
                i0 = None
    steps = {"quads": 0, "count_mismatch": [], "sliding_walls": {}}
    tj_z = []
    for k in range(len(rings) - 1):
        lo, up = rings[k], rings[k + 1]
        z = lo["base"] + lo["ring_h"]
        if abs(z - up["base"]) > 1e-6:
            raise ValueError(f"ring {k} top {z} != ring {k + 1} base {up['base']}")
        if walls[k]:
            steps["sliding_walls"][round(z, 3)] = sorted(walls[k])
            tj_z.append(z)
        for c, ch in enumerate(chains):
            full = [0.0] + fracs[(k, c)] + [1.0]
            runs, cur = [], []                             # sub-runs of the chain between sliding walls
            for i in ch["edges"]:
                if i in walls[k]:
                    runs.append(cur)
                    cur = []
                else:
                    cur.append(i)
            runs.append(cur)
            for r_i, run in enumerate(runs):
                # strips only where the run touches a fixed edge (its columns are the strip fractions)
                ss = full if r_i == 0 or r_i == len(runs) - 1 else [0.0, 1.0]
                ss, dropped = _wide_strips(allcols[k], botcols[k + 1], run, ss)
                if dropped:
                    steps.setdefault("narrow_fractions_dropped", []).append([round(z, 3), run[0], run[-1], dropped])
                    if z not in tj_z:
                        tj_z.append(z)
                for i in run:
                    steps["quads"] += _step(B, allcols[k], botcols[k + 1], i, z, ss, facade, steps, k)
    tj = resolve_tjunctions(B.bm, tj_z)
    sealed = seal_leftovers(B.bm, [r["base"] for r in rings[1:]])
    body = _to_object(B.bm, body_name, coll)
    glass = _to_object(G.bm, glass_name, coll)
    return body, glass, {"rings": len(rings), "sealed": sealed, "columns_per_ring": [len(c) for c in allcols],
                         "chains": [(ch["left"], ch["edges"][0], ch["edges"][-1], ch["right"]) for ch in chains],
                         "snap_fixed_lines_max_m": round(snapped, 4), "skipped": B.skipped, "steps": steps,
                         "sliding_wall_snap_max_m": round(snap_up, 5), "tjunctions": tj}


def _wide_strips(lcols, ucols, run, ss):
    """Drop strip fractions that would make a strip narrower than MIN_STRIP_M anywhere along the run (a fixed-edge
    column just inside the step's end: its point on the fixed edge is then joined by resolve_tjunctions)."""
    depth = None
    for i in run:
        pl, pu = edge_points(lcols, i), edge_points(ucols, i)
        if len(pl) != len(pu):
            continue
        for q in range(len(pl) - 1):
            a0, b0, a1, b1 = V(pl[q]), V(pl[q + 1]), V(pu[q]), V(pu[q + 1])
            if (b0 - a0).length < 1e-6:
                continue
            d = max(_line_dist(a1, a0, b0), _line_dist(b1, a0, b0))
            if d > 1e-4:
                depth = d if depth is None else min(depth, d)
    if depth is None or len(ss) <= 2:
        return ss, []
    keep, dropped = [0.0], []
    for s in ss[1:-1]:
        if (s - keep[-1]) * depth < MIN_STRIP_M or (1.0 - s) * depth < MIN_STRIP_M:
            dropped.append(round(s, 4))
        else:
            keep.append(s)
    return keep + [1.0], dropped


def _step(B, lcols, ucols, i, z, ss, facade, steps, k):
    """Step quads of moving edge i between the lower ring's top columns and the upper ring's bottom columns."""
    pl, pu = edge_points(lcols, i), edge_points(ucols, i)
    if len(pl) != len(pu):
        steps["count_mismatch"].append({"ring": k, "edge": i, "lo": len(pl), "up": len(pu)})
        return 0
    made = 0
    for q in range(len(pl) - 1):
        a0, b0, a1, b1 = V(pl[q]), V(pl[q + 1]), V(pu[q]), V(pu[q + 1])
        if (a0 - a1).length < 1e-4 and (b0 - b1).length < 1e-4:
            continue
        e = b0 - a0 if (b0 - a0).length > 1e-6 else b1 - a1
        outward = Vector((e.y, -e.x)).dot((a1 + b1) - (a0 + b0)) > 0
        want = Vector((0, 0, -1 if outward else 1))
        for s0, s1 in zip(ss[:-1], ss[1:]):
            A0, B0 = a0.lerp(a1, s0), b0.lerp(b1, s0)
            A1, B1 = a0.lerp(a1, s1), b0.lerp(b1, s1)
            f = B.quad(((A0.x, A0.y, z), (B0.x, B0.y, z), (B1.x, B1.y, z), (A1.x, A1.y, z)), facade, want)
            made += f is not None
    return made


def resolve_tjunctions(bm, zs, tol=TJ_TOL_M, reveal_mat=1):
    """Make every facade boundary edge lying on a join plane z (in zs) share the facade points that lie on it: the
    edge is split at each such vertex within `tol` of its interior and the split points are welded to those
    vertices (overlapping collinear boundary edges become one manifold edge). Reveal faces (open backs by design)
    are not touched. Then the n-gons are made quads again without moving anything:
    - pair_wall_points: a wall face with points on its bottom (band, from the join below) and the wall face above it
      in the same column with points on its top (storey, from the join above) are cut through their shared edge;
    - two coplanar n-gons sharing an edge on the join plane (the lower storey and the upper band of one sliding wall,
      or two steps meeting on a sliding wall) are joined into one polygon;
    - split_ngon splits every n-gon along diagonals (quads; a triangle only where a point stays unpaired).
    Also usable on a finished TOW02_body (same plane test, same splits)."""
    rep = {"points": 0, "wall_pairs": 0, "joined": 0, "ngons": 0, "quads": 0, "triangles": 0, "ngons_left": 0,
           "min_angle_deg": 180.0}
    facade = lambda v: any(f.material_index != reveal_mat for f in v.link_faces)
    for z in zs:
        on = lambda v: abs(v.co.z - z) < 1e-6
        edges = [e for e in bm.edges if e.is_boundary and e.link_faces[0].material_index != reveal_mat and
                 on(e.verts[0]) and on(e.verts[1])]
        verts = [v for v in {v for e in edges for v in e.verts} if facade(v)]
        targetmap = {}
        for e in edges:
            a, b = e.verts
            d = b.co - a.co
            L = d.length
            if L < 2 * tol:
                continue
            u = d / L
            pts = []
            for v in verts:
                if v is a or v is b:
                    continue
                w = v.co - a.co
                t = w.dot(u)
                if tol < t < L - tol and (w - u * t).length < tol:
                    pts.append((t, v))
            pts.sort(key=lambda x: x[0])
            cur, start, done = e, a, 0.0
            for t, v in pts:
                far = cur.other_vert(start)
                _, nv = bmesh.utils.edge_split(cur, start, (t - done) / (L - done))
                nv.co = v.co.copy()
                targetmap[nv] = v
                cur = next(x for x in nv.link_edges if x.other_vert(nv) is far)
                start, done = nv, t
        if targetmap:
            bmesh.ops.weld_verts(bm, targetmap=targetmap)
        rep["points"] += len(targetmap)
    ngons = [f for f in bm.faces if len(f.verts) > 4]
    rep["wall_pairs"] = pair_wall_points(bm, ngons)
    joined = []
    for z in zs:
        for e in [e for e in bm.edges if len(e.link_faces) == 2 and all(abs(v.co.z - z) < 1e-6 for v in e.verts)]:
            if not e.is_valid:
                continue
            f, g = e.link_faces
            if (len(f.verts) > 4 and len(g.verts) > 4 and f.material_index == g.material_index != reveal_mat
                    and f.normal.dot(g.normal) > 0.9999 and f not in joined and g not in joined):
                h = bmesh.utils.face_join([f, g])
                if h is not None:
                    joined.append(h)
                    rep["joined"] += 1
    for f in [f for f in bm.faces if len(f.verts) > 4]:
        for deg in (2.0, 0.5, 0.05):
            if split_ngon(bm, f, rep, deg):
                break
        else:
            rep["ngons_left"] += 1
    rep["min_angle_deg"] = round(rep["min_angle_deg"], 2)
    return rep


def _straight(f, min_deg=178.0):
    """Vertices of face f with a straight corner (points inserted on its sides)."""
    vs = list(f.verts)
    out = []
    for q, v in enumerate(vs):
        d0, d1 = vs[q - 1].co - v.co, vs[(q + 1) % len(vs)].co - v.co
        if d0.length > 1e-9 and d1.length > 1e-9 and math.degrees(d0.angle(d1)) > min_deg:
            out.append(v)
    return out


def _match_in_order(xs, ys):
    """min(len) pairs (x, y), order kept on both sides, smallest total |x - y| (the longer list keeps a subset)."""
    swap = len(xs) > len(ys)
    s, l = (ys, xs) if swap else (xs, ys)
    n, m = len(s), len(l)
    INF = float("inf")
    cost = [[INF] * (m + 1) for _ in range(n + 1)]
    for j in range(m + 1):
        cost[0][j] = 0.0
    for i in range(1, n + 1):
        for j in range(i, m + 1):
            cost[i][j] = min(cost[i][j - 1], cost[i - 1][j - 1] + abs(s[i - 1] - l[j - 1]))
    pairs, i, j = [], n, m
    while i > 0:
        if j > i and cost[i][j] == cost[i][j - 1]:
            j -= 1
            continue
        pairs.append((s[i - 1], l[j - 1]))
        i, j = i - 1, j - 1
    pairs.reverse()
    return [(q, p) for p, q in pairs] if swap else pairs


def pair_wall_points(bm, faces):
    """For a vertical face with inserted points only on its bottom edge whose upper neighbour in the same column
    (sharing its top edge, same plane) has inserted points only on its top edge: pair them in order (as many pairs
    as the smaller count, nearest positions) and add one point per pair on the shared edge, on the straight line
    from the bottom point to the top point, so each pair is a cut through both faces and they split into quads."""
    pairs = 0
    fs = set(faces)
    for f in faces:
        if not f.is_valid or abs(f.normal.z) > 0.1:
            continue
        zs = [v.co.z for v in f.verts]
        zb, zm = min(zs), max(zs)
        ext = _straight(f)
        if not ext or any(abs(v.co.z - zb) > 1e-6 for v in ext):
            continue
        top = [e for e in f.edges if all(abs(v.co.z - zm) < 1e-6 for v in e.verts)]
        if len(top) != 1 or len(top[0].link_faces) != 2:
            continue
        te = top[0]
        g = next(x for x in te.link_faces if x is not f)
        if g not in fs or abs(g.normal.z) > 0.1 or (g.normal - f.normal).length > 1e-3:
            continue
        zt = max(v.co.z for v in g.verts)
        gext = _straight(g)
        if not gext or any(abs(v.co.z - zt) > 1e-6 for v in gext):
            continue
        a, b = te.verts
        d = (b.co - a.co).xy
        L = d.length
        u = d / L
        par = lambda v: (v.co.xy - a.co.xy).dot(u)
        bot, up = [par(v) for v in sorted(ext, key=par)], [par(v) for v in sorted(gext, key=par)]
        fr = (zm - zb) / (zt - zb)
        xs = []
        for p, q in _match_in_order(bot, up):
            x = p + (q - p) * fr
            if WELD_M <= x <= L - WELD_M and (not xs or x - xs[-1] >= WELD_M):
                xs.append(x)
        if not xs:
            continue
        cur, start, done = te, a, 0.0
        for x in xs:
            far = cur.other_vert(start)
            _, nv = bmesh.utils.edge_split(cur, start, (x - done) / (L - done))
            cur = next(e for e in nv.link_edges if e.other_vert(nv) is far)
            start, done = nv, x
        pairs += len(xs)
    return pairs


def split_ngon(bm, f, rep, min_deg=2.0):
    """Split an n-gon whose extra vertices lie on its sides into quads (+ triangles) along inner diagonals only:
    fewest triangles, then the largest smallest corner angle; no piece may have a straight corner or a corner below
    min_deg. Returns False (face untouched) when no such split exists."""
    vs = list(f.verts)
    n = len(vs)
    nrm = f.normal.copy()
    ax = Vector((1, 0, 0)) if abs(nrm.x) < 0.9 else Vector((0, 1, 0))
    U = nrm.cross(ax).normalized()
    W = nrm.cross(U)
    P = [Vector(((v.co - vs[0].co).dot(U), (v.co - vs[0].co).dot(W))) for v in vs]

    def cross(o, p, q):
        return (p.x - o.x) * (q.y - o.y) - (p.y - o.y) * (q.x - o.x)

    def inside(p):
        c = False
        for q in range(n):
            a, b = P[q], P[(q + 1) % n]
            if (a.y > p.y) != (b.y > p.y) and p.x < a.x + (p.y - a.y) * (b.x - a.x) / (b.y - a.y):
                c = not c
        return c

    diag = {}

    def diagonal(i, j):                                     # chord i-j lies inside the polygon
        if (j - i) % n in (1, n - 1):
            return True
        if (i, j) not in diag:
            ok = inside((P[i] + P[j]) / 2)
            for q in range(n):
                a, b = q, (q + 1) % n
                if len({a, b, i, j}) < 4:
                    continue
                if cross(P[i], P[j], P[a]) * cross(P[i], P[j], P[b]) < 0 and                         cross(P[a], P[b], P[i]) * cross(P[a], P[b], P[j]) < 0:
                    ok = False
            diag[(i, j)] = ok
        return diag[(i, j)]

    def piece(idx):
        m = len(idx)
        if not all(diagonal(idx[q], idx[(q + 1) % m]) for q in range(m)):
            return None
        angs = []
        for q in range(m):
            p0, p1, p2 = P[idx[q - 1]], P[idx[q]], P[idx[(q + 1) % m]]
            d0, d1 = p0 - p1, p2 - p1
            if d0.length < 1e-9 or d1.length < 1e-9:
                return None
            cr = (p1 - p0).x * (p2 - p1).y - (p1 - p0).y * (p2 - p1).x
            if cr <= 0:                                     # reflex or straight (CCW in the face basis)
                return None
            a = math.degrees(d0.angle(d1))
            if a < min_deg or a > 180 - min_deg:
                return None
            angs.append(a)
        return min(angs)

    memo = {}

    def best(i, j):
        if j == i + 1:
            return (0, -999.0, [])
        if (i, j) in memo:
            return memo[(i, j)]
        res = None
        for k in range(i + 1, j):
            for shape in [(i, k, j)] + [(i, k, l, j) for l in range(k + 1, j)]:
                mn = piece(shape)
                if mn is None:
                    continue
                subs = [best(shape[q], shape[q + 1]) for q in range(len(shape) - 1)]
                if any(s is None for s in subs):
                    continue
                tris = (len(shape) == 3) + sum(s[0] for s in subs)
                worst = min([mn] + [-s[1] for s in subs if s[2]])
                cand = (tris, -worst, [shape] + [p for s in subs for p in s[2]])
                if res is None or cand[:2] < res[:2]:
                    res = cand
        memo[(i, j)] = res
        return res

    r = best(0, n - 1)
    if r is None:
        return False
    rep["ngons"] += 1
    rep["min_angle_deg"] = min(rep["min_angle_deg"], -r[1])
    chords = {tuple(sorted((s[q], s[(q + 1) % len(s)]))) for s in r[2] for q in range(len(s))}
    chords = [c for c in chords if (c[1] - c[0]) % n not in (1, n - 1)]
    faces = [f]
    for a, b in chords:
        va, vb = vs[a], vs[b]
        g = next(g for g in faces if g.is_valid and va in g.verts and vb in g.verts)
        nf, _ = bmesh.utils.face_split(g, va, vb)
        faces.append(nf)
    for g in faces:
        rep["triangles" if len(g.verts) == 3 else "quads"] += 1
    return True


def seal_leftovers(bm, open_z, reveal_mat=1):
    """Close what the step logic leaves at ring joins (z in open_z): a closed 4-edge boundary loop gets a quad;
    a collinear 3-edge loop is a T-junction: the T vertex is welded into the long edge and the long edge's face is
    cut from the T vertex to its far corner (one triangle, reported)."""
    report = {"quads_added": 0, "tjunctions": 0, "triangles": 0, "left": 0}

    def candidates():
        out = []
        for e in bm.edges:
            if not e.is_boundary or {f.material_index for f in e.link_faces} == {reveal_mat}:
                continue
            z0, z1 = e.verts[0].co.z, e.verts[1].co.z
            if abs(z0 - z1) < 1e-6 and any(abs(z0 - z) < 1e-4 for z in open_z):
                out.append(e)
        return out

    def loops(edges):
        es, groups = set(edges), []
        while es:
            e = es.pop()
            g, front = [e], [e]
            while front:
                x = front.pop()
                for v in x.verts:
                    for y in v.link_edges:
                        if y in es:
                            es.remove(y)
                            g.append(y)
                            front.append(y)
            groups.append(g)
        return groups

    for g in loops(candidates()):
        vs = list({v for e in g for v in e.verts})
        if len(g) == 4 and len(vs) == 4:
            ordered = [g[0].verts[0], g[0].verts[1]]
            while len(ordered) < 4:
                nxt = next(e.other_vert(ordered[-1]) for e in g
                           if ordered[-1] in e.verts and e.other_vert(ordered[-1]) not in ordered)
                ordered.append(nxt)
            f = bm.faces.new(ordered)
            f.normal_update()
            if f.normal.z > 0:           # step soffit under an overhang faces down
                f.normal_flip()
            report["quads_added"] += 1
        elif len(g) == 3 and len(vs) == 3:
            long_e = max(g, key=lambda e: e.calc_length())
            t = next(v for v in vs if v not in long_e.verts)
            face = long_e.link_faces[0]
            a = long_e.verts[0]
            fac = (t.co - a.co).length / long_e.calc_length()
            new_e, nv = bmesh.utils.edge_split(long_e, a, fac)
            bmesh.ops.pointmerge(bm, verts=[nv, t], merge_co=t.co.copy())
            t = nv if nv.is_valid else t
            report["tjunctions"] += 1
            far = max((v for v in face.verts if v is not t), key=lambda v: (v.co - t.co).length)
            bmesh.ops.connect_verts(bm, verts=[t, far])
            report["triangles"] += sum(1 for f in t.link_faces if len(f.verts) == 3)
        else:
            report["left"] += len(g)
    return report


def _to_object(bm, name, collection):
    if name in bpy.data.objects:
        raise ValueError(f"object {name} exists; use a new name")
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    return ob


def material(name, rgba):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = rgba
    return m


def build(cfg):
    """cfg: collection, name, rings_json, typical_bases, band_h, ring_h, reveal_m, plane_overlap_m,
    collapse_shift_m, snap_m. Bend rings = the non-reference rings of rings_json; typical rings use its reference."""
    coll = bpy.data.collections.get(cfg["collection"])
    if coll is None:
        coll = bpy.data.collections.new(cfg["collection"])
        bpy.context.scene.collection.children.link(coll)
    data = json.load(open(cfg["rings_json"], encoding="utf-8"))["rings"]
    typical = next(r for r in data if r.get("reference"))
    rings = [dict(base=r["base"], band_h=cfg["band_h"], ring_h=cfg["ring_h"], edges=r["edges"])
             for r in data if not r.get("reference")]
    rings += [dict(base=b, band_h=cfg["band_h"], ring_h=cfg["ring_h"], edges=typical["edges"])
              for b in cfg["typical_bases"]]
    rings.sort(key=lambda r: r["base"])
    body, glass, info = build_stack(rings, cfg, cfg["name"], cfg["name"] + "_glass", coll)
    body.data.materials.append(material("TOW02_facade", (0.12, 0.12, 0.12, 1)))
    body.data.materials.append(material("TOW02_reveal", (0.35, 0.35, 0.35, 1)))
    glass.data.materials.append(material("TOW02_glass", (0.25, 0.5, 0.9, 1)))
    info.update(body_faces=len(body.data.polygons), glass_faces=len(glass.data.polygons))
    return info


JOB = os.path.dirname(os.path.dirname(os.path.abspath(globals().get("__file__", "scripts/x.py"))))
# The build-v004 body (unchanged through build-v013): reproduced exactly with these values (2026-10-21 check:
# 0 vertex / face differences); the GUI run that made it did not record them.
CFG_TOW02 = dict(collection="TOW02_rebuild", name="TOW02_rebuild_body",
                 rings_json=os.path.join(JOB, "outputs", "measure-v002", "bend_rings", "bend_rings.json"),
                 typical_bases=[round(37.5 + 3.4 * k, 3) for k in range(8)], band_h=0.7, ring_h=3.4,
                 reveal_m=0.12, plane_overlap_m=0.01, snap_m=0.03, collapse_shift_m=0.3)


def swap_into_master(out_dir, cfg=CFG_TOW02):
    """Rebuild the body and give TOW02_body / TOW02_body_glass the new meshes (old meshes kept as orphans, not saved)."""
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    info = build(cfg)
    coll = bpy.data.collections[cfg["collection"]]
    swapped = {}
    for target, new_name in (("TOW02_body", cfg["name"]), ("TOW02_body_glass", cfg["name"] + "_glass")):
        ob, nob = bpy.data.objects[target], bpy.data.objects[new_name]
        old_me, me = ob.data, nob.data
        if [m.name for m in old_me.materials] != [m.name for m in me.materials]:
            raise RuntimeError(f"{target}: material slots differ {[m.name for m in old_me.materials]}")
        swapped[target] = dict(faces=[len(old_me.polygons), len(me.polygons)],
                               verts=[len(old_me.vertices), len(me.vertices)])
        bpy.data.objects.remove(nob)
        old_name = old_me.name
        old_me.name = old_name + "_prev"
        me.name = old_name
        ob.data = me
    bpy.data.collections.remove(coll)
    info["swapped"] = swapped
    path = os.path.join(out_dir, "tow02_master.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=False)
    json.dump(info, open(os.path.join(out_dir, "body_info.json"), "w"), indent=1)
    print("BODY_SWAP saved", path, json.dumps({k: info[k] for k in ("swapped", "tjunctions", "sliding_wall_snap_max_m")}))


if __name__ == "__main__":
    swap_into_master(sys.argv[sys.argv.index("--") + 1])
