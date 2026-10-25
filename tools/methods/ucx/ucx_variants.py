"""UCX collision variants for the methods catalog (docs/methods/ucx-collisions/VARIANTS.md).

Pattern: new-case: alternative Main UCX constructions measured side by side (methods catalog #706).
numpy only (no bpy): runs inside Blender (`build_variant_blender.py`) and under pytest. The convex hull
of a point set is injected (`hull_fn(points) -> (verts, tris)`): Blender passes bmesh.ops.convex_hull,
tests pass a box hull. Our own code; no team script text.

Input: a triangle mesh in world metres (`verts` (N, 3), `tris` (M, 3)) = every non-UCX mesh of the FBX.
Output: list of (verts, tris) convex pieces. Every variant fails closed (VariantError) instead of
returning an empty, non-finite or unnamed (> 999 pieces) set.

Variants
- kernel-boxes: the shared builder `dt_ai.geometry.ucx_build.build_main` (voxel + greedy boxes, 4 mm gap).
- part-boxes: one box per connected part in the facade frame; parts closer than `gap` are merged until
  every pair of boxes is at least `gap` apart.
- part-hulls: one convex hull per connected part; hulls closer than `gap` (numpy SAT) are merged and
  re-hulled until every pair is at least `gap` apart.
- slice-prisms: the mesh is cut at its levels (z of horizontal faces with >= 1 m2 area); each band
  becomes one prism over the plan convex hull of the band (vertices plus edge/plane crossings), bands
  `gap` apart vertically, so pieces never intersect; plan vertices within 1 cm of their neighbours' chord
  are dropped (no sliver caps).
- single-hull: one convex hull of the whole mesh (baseline: always valid, loosest fit).
"""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
VARIANTS = ("kernel-boxes", "slice-prisms", "part-boxes", "part-hulls", "single-hull")
LEVEL_AREA_M2 = 1.0  # slice-prisms: a horizontal face area at one z of at least this starts a level
LEVEL_MIN_M = 0.5  # slice-prisms: levels closer than this are one level
SIMPLIFY_M = 0.01  # slice-prisms: a plan vertex closer than this to its neighbours' chord is dropped
MERGE_GAP_M = 0.003  # = ucx_build.GAP_BUILD_M[0]: float32 read-back stays inside the [D098] 2 mm - 1 cm band
WELD_M = 1e-4  # parts: vertices closer than this (grid) are one vertex; FBX splits vertices per face
MIN_THICK_M = 0.02  # a flat part (glass pane) gets a box this thick so the piece has a volume
MAX_PIECES = 999  # reg p.34 §4.2 index 001..999


class VariantError(ValueError):
    """The variant cannot give a valid UCX set for this input."""


def _load_builder():
    name = "dt_ai_ucx_build_for_methods"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "src/dt_ai/geometry/ucx_build.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _check(verts, tris):
    v = np.asarray(verts, dtype=float).reshape(-1, 3)
    t = np.asarray(tris, dtype=np.int64).reshape(-1, 3)
    if not len(v) or not len(t):
        raise VariantError("empty mesh")
    if not np.isfinite(v).all():
        raise VariantError("non-finite vertex coordinates")
    if t.min() < 0 or t.max() >= len(v):
        raise VariantError("triangle index out of range")
    return v, t


def parts(verts, tris, weld_m: float = WELD_M) -> list[np.ndarray]:
    """Vertex index arrays, one per connected part (triangles sharing a welded vertex)."""
    v, t = _check(verts, tris)
    key = np.round(v / weld_m).astype(np.int64)
    _, wid = np.unique(key, axis=0, return_inverse=True)
    wid = wid.reshape(-1)
    parent = np.arange(wid.max() + 1)

    def find(a):
        root = a
        while parent[root] != root:
            root = parent[root]
        while parent[a] != root:
            parent[a], a = root, parent[a]
        return root

    for a, b, c in wid[t]:
        ra, rb, rc = find(a), find(b), find(c)
        parent[rb] = ra
        parent[find(rc)] = ra
    used = np.unique(t.reshape(-1))
    roots = np.array([find(w) for w in wid[used]])
    return [used[roots == r] for r in np.unique(roots)]


def box_piece(lo, hi, back: np.ndarray):
    ub = _load_builder()
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    corners = np.array([(lo[0], lo[1], lo[2]), (hi[0], lo[1], lo[2]), (hi[0], hi[1], lo[2]), (lo[0], hi[1], lo[2]),
                        (lo[0], lo[1], hi[2]), (hi[0], lo[1], hi[2]), (hi[0], hi[1], hi[2]), (lo[0], hi[1], hi[2])])
    return corners @ back.T, ub._BOX_TRIS.copy()


def _thick(lo, hi):
    lo, hi = lo.copy(), hi.copy()
    for k in range(3):
        if hi[k] - lo[k] < MIN_THICK_M:
            mid = (hi[k] + lo[k]) / 2
            lo[k], hi[k] = mid - MIN_THICK_M / 2, mid + MIN_THICK_M / 2
    return lo, hi


def _box_sep(lo, hi):
    """(K, K) separation of axis-aligned boxes: max over axes of the interval gap (< 0 = overlap)."""
    g = np.maximum(lo[None, :, :] - hi[:, None, :], lo[:, None, :] - hi[None, :, :])
    return g.max(axis=2)


def part_boxes(verts, tris, gap: float = MERGE_GAP_M):
    ub = _load_builder()
    v, t = _check(verts, tris)
    angle = ub.facade_angle(v, t)
    vf = v @ ub._rot(-angle).T
    groups = parts(v, t)

    def bounds(gs):
        lo = np.array([vf[g].min(axis=0) for g in gs])
        hi = np.array([vf[g].max(axis=0) for g in gs])
        pairs = [_thick(a, b) for a, b in zip(lo, hi)]
        return np.array([p[0] for p in pairs]), np.array([p[1] for p in pairs])

    while True:  # vectorised merge: all boxes closer than gap join the component they touch
        lo, hi = bounds(groups)
        sep = _box_sep(lo, hi)
        np.fill_diagonal(sep, np.inf)
        if not (sep < gap).any():
            break
        groups = _union(groups, sep < gap)
    lo, hi = bounds(groups)
    return [box_piece(a, b, ub._rot(angle)) for a, b in zip(lo, hi)], {"angle_deg": angle, "parts": len(parts(v, t))}


def _union(groups, close: np.ndarray):
    k = len(groups)
    parent = list(range(k))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for i, j in zip(*np.nonzero(np.triu(close, 1))):
        parent[find(int(j))] = find(int(i))
    out = {}
    for i in range(k):
        out.setdefault(find(i), []).append(groups[i])
    return [np.concatenate(gs) for gs in out.values()]


def _edges(tris):
    e = np.sort(np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]]), axis=1)
    return np.unique(e, axis=0)


def sat_gap(a, b) -> float:
    """Separation of two convex hulls over the SAT axes (face normals, edge crosses), numpy.

    > 0: at least that far apart; <= 0: overlap (same convention as twinqa ucx_audit.sat_separation).
    """
    axes = []
    for verts, tris in (a, b):
        n = np.cross(verts[tris[:, 1]] - verts[tris[:, 0]], verts[tris[:, 2]] - verts[tris[:, 0]])
        axes.append(n)
    ea = a[0][_edges(a[1])[:, 1]] - a[0][_edges(a[1])[:, 0]]
    eb = b[0][_edges(b[1])[:, 1]] - b[0][_edges(b[1])[:, 0]]
    axes.append(np.cross(ea[:, None, :], eb[None, :, :]).reshape(-1, 3))
    ax = np.concatenate(axes)
    norm = np.linalg.norm(ax, axis=1)
    ax = ax[norm > 1e-12] / norm[norm > 1e-12, None]
    pa, pb = a[0] @ ax.T, b[0] @ ax.T
    return float(np.maximum(pb.min(axis=0) - pa.max(axis=0), pa.min(axis=0) - pb.max(axis=0)).max())


def _volume(verts, tris) -> float:
    a, b, c = verts[tris[:, 0]], verts[tris[:, 1]], verts[tris[:, 2]]
    return abs(float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum()) / 6.0)


def _hull(points, hull_fn, angle_back, frame):
    """Convex hull of points; a flat part (no volume) becomes its MIN_THICK_M box in the facade frame."""
    try:
        hv, ht = hull_fn(points)
        hv, ht = np.asarray(hv, float).reshape(-1, 3), np.asarray(ht, np.int64).reshape(-1, 3)
        if len(ht) >= 4 and _volume(hv, ht) > 1e-6:
            return hv, ht
    except (ValueError, RuntimeError):
        pass
    pf = points @ frame.T
    lo, hi = _thick(pf.min(axis=0), pf.max(axis=0))
    return box_piece(lo, hi, angle_back)


def part_hulls(verts, tris, hull_fn, gap: float = MERGE_GAP_M):
    ub = _load_builder()
    v, t = _check(verts, tris)
    angle = ub.facade_angle(v, t)
    frame, back = ub._rot(-angle), ub._rot(angle)
    groups = parts(v, t)
    n_parts = len(groups)
    hulls = [_hull(v[g], hull_fn, back, frame) for g in groups]
    while True:
        lo = np.array([h[0].min(axis=0) for h in hulls]) - gap
        hi = np.array([h[0].max(axis=0) for h in hulls])
        cand = _box_sep(lo, hi) < 0  # boxes grown by gap overlap -> hulls may be closer than gap
        np.fill_diagonal(cand, False)
        close = np.zeros_like(cand)
        for i, j in zip(*np.nonzero(np.triu(cand, 1))):
            if sat_gap(hulls[i], hulls[j]) < gap:
                close[i, j] = close[j, i] = True
        if not close.any():
            break
        idx = [np.array([k]) for k in range(len(groups))]
        merged = _union(idx, close)
        new_groups, new_hulls = [], []
        for m in merged:
            if len(m) == 1:
                new_groups.append(groups[m[0]])
                new_hulls.append(hulls[m[0]])
            else:
                g = np.concatenate([groups[k] for k in m])
                pts = np.concatenate([hulls[k][0] for k in m])  # hull of hulls = hull of the parts
                new_groups.append(g)
                new_hulls.append(_hull(pts, hull_fn, back, frame))
        groups, hulls = new_groups, new_hulls
    return hulls, {"angle_deg": angle, "parts": n_parts}


def plan_hull(xy) -> np.ndarray:
    """2D convex hull (Andrew monotone chain), CCW, no collinear points; (k, 2)."""
    pts = sorted({(float(x), float(y)) for x, y in np.round(np.asarray(xy, float), 9)})
    if len(pts) < 3:
        return np.array(pts)

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 1e-12:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 1e-12:
            upper.pop()
        upper.append(p)
    return np.array(lower[:-1] + upper[:-1])


def simplify(poly, tol: float = SIMPLIFY_M) -> np.ndarray:
    """Drop convex-polygon vertices within `tol` of the chord of their neighbours (the polygon shrinks by
    at most `tol`); near-collinear vertices otherwise give sliver cap triangles that read back non-convex."""
    pts = [tuple(p) for p in np.asarray(poly, float)]
    changed = True
    while changed and len(pts) > 3:
        changed = False
        best, idx = tol, None
        for i in range(len(pts)):
            a, p, b = np.array(pts[i - 1]), np.array(pts[i]), np.array(pts[(i + 1) % len(pts)])
            ab = b - a
            n = math.hypot(ab[0], ab[1])
            d = abs(ab[0] * (p[1] - a[1]) - ab[1] * (p[0] - a[0])) / n if n > 0 else 0.0
            if d < best:
                best, idx = d, i
        if idx is not None:
            pts.pop(idx)
            changed = True
    return np.array(pts)


def prism(poly, z0: float, z1: float):
    """Closed convex prism over a CCW convex k-gon: 2k vertices, 4k - 4 outward triangles."""
    k = len(poly)
    verts = np.array([(x, y, z0) for x, y in poly] + [(x, y, z1) for x, y in poly], dtype=float)
    tris = [(0, i + 1, i) for i in range(1, k - 1)] + [(k, k + i, k + i + 1) for i in range(1, k - 1)]
    for i in range(k):
        j = (i + 1) % k
        tris += [(i, j, k + j), (i, k + j, k + i)]
    return verts, np.array(tris, dtype=np.int64)


def levels(verts, tris, area_m2: float = LEVEL_AREA_M2, min_m: float = LEVEL_MIN_M) -> list[float]:
    v, t = _check(verts, tris)
    n = np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]])
    a = np.linalg.norm(n, axis=1) / 2
    flat = (a > 0) & (np.abs(n[:, 2]) >= 0.999 * np.linalg.norm(n, axis=1))
    zs = {}
    for z, ar in zip(np.round(v[t[flat]][:, :, 2].mean(axis=1), 3), a[flat]):
        zs[float(z)] = zs.get(float(z), 0.0) + float(ar)
    lo, hi = float(v[:, 2].min()), float(v[:, 2].max())
    cuts = [lo] + [z for z in sorted(zs) if zs[z] >= area_m2 and lo < z < hi] + [hi]
    out = [cuts[0]]
    for z in cuts[1:]:
        if z - out[-1] >= min_m:
            out.append(z)
    if out[-1] != hi:
        out[-1] = hi
    return out


def slice_prisms(verts, tris, gap: float = MERGE_GAP_M):
    v, t = _check(verts, tris)
    zs = levels(v, t)
    if len(zs) < 2:
        raise VariantError("slice-prisms: the mesh has no height")
    e = _edges(t)
    a, b = v[e[:, 0]], v[e[:, 1]]
    pieces = []
    for z0, z1 in zip(zs[:-1], zs[1:]):
        pts = [v[(v[:, 2] >= z0) & (v[:, 2] <= z1)][:, :2]]
        for z in (z0, z1):
            cross = (a[:, 2] - z) * (b[:, 2] - z) < 0
            s = (z - a[cross, 2]) / (b[cross, 2] - a[cross, 2])
            pts.append((a[cross] + (b[cross] - a[cross]) * s[:, None])[:, :2])
        poly = simplify(plan_hull(np.concatenate(pts)))
        if len(poly) < 3:
            continue  # no plan area in this band (a line of vertices): reported through the band count
        pieces.append(prism(poly, z0 + gap / 2, z1 - gap / 2))
    return pieces, {"levels_m": [round(z, 3) for z in zs], "bands": len(zs) - 1}


def single_hull(verts, tris, hull_fn):
    ub = _load_builder()
    v, t = _check(verts, tris)
    angle = ub.facade_angle(v, t)
    used = np.unique(t.reshape(-1))
    return [_hull(v[used], hull_fn, ub._rot(angle), ub._rot(-angle))], {"angle_deg": angle}


def kernel_boxes(verts, tris, model_triangles: int, cell: float = 0.25):
    ub = _load_builder()
    v, t = _check(verts, tris)
    try:
        res = ub.build_main(v, t, cell=cell, model_triangles=model_triangles)
    except ub.UcxBuildError as exc:
        raise VariantError(str(exc)) from exc
    return [(p.verts, p.tris) for p in res.pieces], {"angle_deg": res.angle_deg, "cell_m": res.cell_m,
                                                     "attempts": res.attempts}


def build(variant: str, verts, tris, *, model_triangles: int, hull_fn=None, **kw):
    """Run one variant; returns (pieces, info). Raises VariantError, never returns an invalid set."""
    if variant not in VARIANTS:
        raise VariantError(f"unknown variant {variant!r}; expected one of {VARIANTS}")
    if variant in ("part-hulls", "single-hull") and hull_fn is None:
        raise VariantError(f"{variant} needs hull_fn")
    if variant == "kernel-boxes":
        pieces, info = kernel_boxes(verts, tris, model_triangles, **kw)
    elif variant == "slice-prisms":
        pieces, info = slice_prisms(verts, tris, **kw)
    elif variant == "part-boxes":
        pieces, info = part_boxes(verts, tris, **kw)
    elif variant == "part-hulls":
        pieces, info = part_hulls(verts, tris, hull_fn, **kw)
    else:
        pieces, info = single_hull(verts, tris, hull_fn)
    if not pieces:
        raise VariantError(f"{variant}: no pieces")
    if len(pieces) > MAX_PIECES:
        raise VariantError(f"{variant}: {len(pieces)} pieces > {MAX_PIECES} (names UCX_..._001..999)")
    for pv, pt in pieces:
        if not np.isfinite(np.asarray(pv, float)).all():
            raise VariantError(f"{variant}: non-finite piece vertex")
    info["pieces"] = len(pieces)
    info["triangles"] = int(sum(len(pt) for _, pt in pieces))
    return pieces, info
