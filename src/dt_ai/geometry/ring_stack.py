"""Ring-stack sliding walls: bpy-free port of the vyatskaya-tow02 build helpers.

new-case: ring-stack sliding-wall detection and upper-ring column snapping (pure 2D geometry).

Ported from jobs/vyatskaya-tow02/scripts/build_body_blender.py (sliding_walls, _line_dist,
_intersect, snap_upper_cols); the job script stays the record of the delivered build.
Rings are dicts {"edges": [{"a": (x, y), "b": (x, y), "length": float}, ...]}; chains are
[{"edges": [edge index, ...]}]; columns are tuples (x, y, edge index, flag).
"""

import math

LINE_M = 0.01      # a moving edge whose line moves less than this between two rings is one wall
COLLAPSE_M = 0.005  # an edge shorter than this has collapsed in that ring
STILL_M = 1e-4     # an end that moves less than this has not moved


def _finite(what, *vals):
    """ValueError naming `what` when any value is NaN/inf (checked before any skip or branch)."""
    if not all(math.isfinite(v) for v in vals):
        raise ValueError(f"non-finite geometry in {what}: {vals}")


def _sub(p, q):
    return (p[0] - q[0], p[1] - q[1])


def _len(v):
    return math.hypot(v[0], v[1])


def _project(p, a, b):
    """Orthogonal projection of p onto the infinite line a-b; ValueError on a zero-length or non-finite line."""
    if not all(math.isfinite(c) for c in (*p[:2], *a[:2], *b[:2])):
        raise ValueError(f"non-finite coordinate in point {p} or line {a}-{b}")
    d = _sub(b, a)
    n = _len(d)
    if n == 0.0:
        raise ValueError(f"zero-length line {a}-{b}")
    ux, uy = d[0] / n, d[1] / n
    t = (p[0] - a[0]) * ux + (p[1] - a[1]) * uy
    return (a[0] + ux * t, a[1] + uy * t)


def _line_dist(p, a, b):
    """Distance from p to the infinite line a-b."""
    return _len(_sub(p, _project(p, a, b)))


def _intersect(a0, b0, a1, b1):
    """Intersection of lines a0-b0 and a1-b1, or None when they are parallel; ValueError on NaN/inf."""
    _finite("intersect line endpoints", *a0[:2], *b0[:2], *a1[:2], *b1[:2])
    d0, d1 = _sub(b0, a0), _sub(b1, a1)
    den = d0[0] * d1[1] - d0[1] * d1[0]
    if abs(den) < 1e-12:
        return None
    t = ((a1[0] - a0[0]) * d1[1] - (a1[1] - a0[1]) * d1[0]) / den
    x = (a0[0] + d0[0] * t, a0[1] + d0[1] * t)
    _finite("intersection result", *x)
    return x


def sliding_walls(rings, chains, *, line_m=LINE_M, collapse_m=COLLAPSE_M, still_m=STILL_M):
    """{k: {edge}}: chain edges whose line between ring k and k+1 stays within line_m while an end moves."""
    out = {}
    for k in range(len(rings) - 1):
        s = set()
        for ch in chains:
            for i in ch["edges"]:
                e0, e1 = rings[k]["edges"][i], rings[k + 1]["edges"][i]
                for r, e in ((k, e0), (k + 1, e1)):
                    _finite(f"ring {r} edge {i}", *e["a"][:2], *e["b"][:2], e["length"])
                if e0["length"] < collapse_m or e1["length"] < collapse_m:
                    continue
                a0, b0, a1, b1 = e0["a"], e0["b"], e1["a"], e1["b"]
                if _len(_sub(a1, a0)) < still_m and _len(_sub(b1, b0)) < still_m:
                    continue
                if max(_line_dist(a1, a0, b0), _line_dist(b1, a0, b0)) < line_m:
                    s.add(i)
        out[k] = s
    return out


def snap_upper_cols(cols, lower, walls):
    """Columns of the upper ring with every point of a sliding wall (its columns and its closing point)
    projected onto the lower ring's line of that edge (onto the intersection when it closes one sliding
    wall and starts another; parallel lines fall back to the projection). Returns (cols, largest move)."""
    n, out, worst = len(cols), list(cols), 0.0
    missing = sorted(i for i in walls if not 0 <= i < len(lower["edges"]))
    if missing:
        raise ValueError(f"sliding wall edges {missing} are not edges of the lower ring")
    for q, c in enumerate(cols):
        _finite(f"upper column {q}", c[0], c[1])
    for i in walls:
        e = lower["edges"][i]
        _finite(f"lower edge {i}", *e["a"][:2], *e["b"][:2])
    for q in range(n):
        own, prev = cols[q][2], cols[(q - 1) % n][2]
        lines = []
        if prev != own and prev in walls:                    # closing point of sliding wall `prev`
            lines.append(prev)
        if own in walls:
            lines.append(own)
        if not lines:
            continue
        L = [(tuple(lower["edges"][i]["a"][:2]), tuple(lower["edges"][i]["b"][:2])) for i in lines]
        p = (cols[q][0], cols[q][1])
        x = _intersect(*L[0], *L[1]) if len(L) == 2 else None
        x = x if x is not None else _project(p, *L[0])
        _finite(f"snapped column {q}", *x)
        worst = max(worst, _len(_sub(x, p)))
        out[q] = (x[0], x[1], own, cols[q][3])
    return out, worst
