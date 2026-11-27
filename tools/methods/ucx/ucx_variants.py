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
- section-boxes (#2053): level bands; per band the plan shadow of the band's geometry on a 0.25 m grid,
  rooms filled (enclosed and roofed), courtyards and through-passages left open, cells grouped by their
  height range, greedy rectangles per group, exposed rectangle sides pulled to the facade samples, rectangles
  that repeat over consecutive bands stacked into one box; boxes shrink by gap/2. No triangle budget.
- ground-coarse-faces (#2053, Ground target): up-facing triangles of the highest surface grow into planar
  clusters (minimax plane within `tol`) whose plan union stays convex: large prisms on flat parts, the
  existing faces on curved slopes; each cluster is a prism over its plan shrunk by gap/2.
"""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
VARIANTS = ("kernel-boxes", "slice-prisms", "part-boxes", "part-hulls", "single-hull", "section-boxes")
GROUND_VARIANTS = ("ground-coarse-faces",)  # Ground target: not part of the Main benchmark batch
ALL_VARIANTS = VARIANTS + GROUND_VARIANTS
SECTION_CELL_M = 0.25  # section-boxes plan grid (K10 depth-map step)
SECTION_Q_M = 0.5  # section-boxes: cells whose bottom / top differ by less than this share one rectangle group
SECTION_LEVEL_SHARE = 0.2  # section-boxes: a level needs this share of the largest level's horizontal area
SECTION_GROW = 1.25  # section-boxes: cell growth while the pieces exceed the 999 names
SECTION_MIN_M = 0.05  # section-boxes: R04 thin-element limit, the thinnest box side
GROUND_TOL_M = 0.08  # ground-coarse-faces: = ucx_build.build_ground default tol (max |surface z - top|)
GROUND_MIN_NZ = 0.05  # ground-coarse-faces: steeper faces (|n_z| < this) get no own prism
GROUND_SLOPE_DEG = 15.0  # ground-coarse-faces: faces steeper than this are "slope" and keep their own shape
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
    src = ROOT / "src"
    if str(src) not in sys.path:  # Blender needs the shared twinqa budget owner without an editable install.
        sys.path.insert(0, str(src))
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


# ---- section-boxes (#2053, Codex K9-K13) ------------------------------------------------------------------------

def _dilate(m: np.ndarray) -> np.ndarray:
    d = m.copy()
    d[1:] |= m[:-1]
    d[:-1] |= m[1:]
    d[:, 1:] |= m[:, :-1]
    d[:, :-1] |= m[:, 1:]
    return d


def _runs(ext: np.ndarray, free: np.ndarray) -> np.ndarray:
    """Every run of free cells along axis 1 that holds an exterior cell becomes exterior."""
    r, c = free.shape
    start = ~free
    start[:, 0] = True
    ids = np.cumsum(start.ravel()) - 1
    hit = np.bincount(ids[ext.ravel()], minlength=int(ids[-1]) + 1) > 0
    return (hit[ids].reshape(r, c) & free) | ext


def flood2d(free: np.ndarray) -> np.ndarray:
    """4-connected flood of `free` cells from the grid border (row / column run propagation)."""
    ext = np.zeros_like(free)
    ext[0, :] = ext[-1, :] = ext[:, 0] = ext[:, -1] = True
    ext &= free
    while True:
        new = _runs(_runs(ext, free).T, free.T).T
        if np.array_equal(new, ext):
            return ext
        ext = new


def section_levels(verts, tris, share: float = SECTION_LEVEL_SHARE, min_m: float = LEVEL_MIN_M) -> list[float]:
    """Levels whose horizontal area is at least `share` of the largest level (slabs, roofs, terraces; not
    window sills, which would cut every window into the plan section)."""
    v, t = _check(verts, tris)
    n = np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]])
    a = np.linalg.norm(n, axis=1) / 2
    flat = (a > 0) & (np.abs(n[:, 2]) >= 0.999 * np.linalg.norm(n, axis=1))
    zs: dict[float, float] = {}
    for z, ar in zip(np.round(v[t[flat]][:, :, 2].mean(axis=1), 2), a[flat]):
        zs[float(z)] = zs.get(float(z), 0.0) + float(ar)
    lo, hi = float(v[:, 2].min()), float(v[:, 2].max())
    big = max(zs.values(), default=0.0)
    cuts = [lo] + [z for z in sorted(zs) if zs[z] >= max(LEVEL_AREA_M2, share * big) and lo < z < hi] + [hi]
    out = [cuts[0]]
    for z in cuts[1:]:
        if z - out[-1] >= min_m:
            out.append(z)
    out[-1] = hi
    return out


def _cell_stat(shape, ix, iy, val, fn, init):
    out = np.full(shape, init, dtype=float)
    fn.at(out, (ix, iy), val)
    return out


def _layer_rects(m, lo, hi, used, layer_pts, shape, cell, origin):
    """Greedy rectangles of the cells `m` (one height group of one layer) with their exact extents.

    `layer_pts` = (ix, iy, points) of this layer. A rectangle side with no used cell beyond it is pulled to
    the outermost sample inside the rectangle, so only empty volume is removed."""
    ub = _load_builder()
    best = None
    for order in ((0, 1, 2), (1, 0, 2)):
        b = ub.greedy_boxes(m[:, :, None], order)
        if best is None or len(b) < len(best):
            best = b
    bx, by, bp = layer_pts
    stat = {}
    for k, (fn, init) in enumerate(((np.minimum, np.inf), (np.maximum, -np.inf))):
        for a in range(3):
            stat[(k, a)] = _cell_stat(shape, bx, by, bp[:, a], fn, init)
    has = np.zeros(shape, bool)
    has[bx, by] = True
    out = []
    for (x0, y0, _), (x1, y1, _) in best:
        sl = (slice(x0, x1), slice(y0, y1))
        g = [origin[0] + x0 * cell, origin[1] + y0 * cell, origin[0] + x1 * cell, origin[1] + y1 * cell]
        box_lo = [g[0], g[1], float(lo[sl][m[sl]].min())]
        box_hi = [g[2], g[3], float(hi[sl][m[sl]].max())]
        pin = has[sl] & m[sl]
        pz = None
        if pin.any():
            pz = (float(stat[(0, 2)][sl][pin].min()), float(stat[(1, 2)][sl][pin].max()))
            if x0 == 0 or not used[x0 - 1, y0:y1].any():
                box_lo[0] = max(box_lo[0], float(stat[(0, 0)][sl][pin].min()))
            if x1 >= shape[0] or not used[x1, y0:y1].any():
                box_hi[0] = min(box_hi[0], float(stat[(1, 0)][sl][pin].max()))
            if y0 == 0 or not used[x0:x1, y0 - 1].any():
                box_lo[1] = max(box_lo[1], float(stat[(0, 1)][sl][pin].min()))
            if y1 >= shape[1] or not used[x0:x1, y1].any():
                box_hi[1] = min(box_hi[1], float(stat[(1, 1)][sl][pin].max()))
        for k, (glo, ghi) in enumerate(((g[0], g[2]), (g[1], g[3]))):
            if box_hi[k] - box_lo[k] < SECTION_MIN_M:  # flat sheet (glass, slab edge): keep the R04 thickness
                mid = (box_hi[k] + box_lo[k]) / 2
                box_lo[k] = max(glo, min(mid - SECTION_MIN_M / 2, ghi - SECTION_MIN_M))
                box_hi[k] = min(ghi, box_lo[k] + SECTION_MIN_M)
        out.append(((x0, y0, x1, y1), box_lo, box_hi, pz))
    return out


def _band_rects(pf, ix, iy, shape, z0, z1, first, colmax, q, cell, origin):
    """Rectangles of one level band: (grid key, lo xyz, hi xyz, sample z range or None, full_bottom, full_top).

    The band is split in height bins of about `q`. Per plan cell: rooms (enclosed by the band's plan shadow
    and roofed) are full height; any other occupied cell gives layer A = its lowest run of occupied bins and
    layer B = the rest up to its top sample, so a canopy over a pavement does not become a pillar. Cells are
    grouped by the bins their range starts and ends in, so two rectangles of one band never overlap."""
    eps = 1e-4
    sel = ((pf[:, 2] >= z0 - eps) if first else (pf[:, 2] > z0 + eps)) & (pf[:, 2] <= z1 + eps)
    if not sel.any():
        return []
    bx, by, bp = ix[sel], iy[sel], pf[sel]
    nb = max(1, int(math.ceil((z1 - z0) / q - 1e-9)))
    hq = (z1 - z0) / nb
    bz = np.clip(np.floor((bp[:, 2] - z0) / hq).astype(np.int64), 0, nb - 1)
    occ3 = np.zeros(shape + (nb,), bool)
    occ3[bx, by, bz] = True
    occ = occ3.any(axis=2)
    # walls block the plan flood: samples above the band's floor bin and below its ceiling bin (a pavement
    # under a canopy is no wall, a sill or lintel under / over a window is)
    barrier = occ3[:, :, 1:-1].any(axis=2) if nb >= 3 else occ
    ext = flood2d(~_dilate(barrier))  # one-cell closing: a gap of up to 2 cells in a wall does not let the flood in
    ext = ext | (_dilate(ext) & ~barrier)
    enclosed = ~ext
    zmax = _cell_stat(shape, bx, by, bp[:, 2], np.maximum, -np.inf)
    full = enclosed & ((colmax > z1 + eps) | (occ & (zmax >= z1 - hq)))  # rooms: enclosed and roofed
    first_bin = np.argmax(occ3, axis=2)
    after = (np.arange(nb)[None, None, :] > first_bin[:, :, None]) & ~occ3
    run_end = np.where(after.any(axis=2), np.argmax(after, axis=2), nb)
    in_a = bz < run_end[bx, by]
    rects = []
    for layer in ("A", "B"):
        pm = in_a | full[bx, by] if layer == "A" else ~in_a & ~full[bx, by]
        lx, ly, lp = bx[pm], by[pm], bp[pm]
        cells = np.zeros(shape, bool)
        cells[lx, ly] = True
        if layer == "A":
            cells |= full
        if not cells.any():
            continue
        lo = _cell_stat(shape, lx, ly, lp[:, 2], np.minimum, np.inf)
        hi = _cell_stat(shape, lx, ly, lp[:, 2], np.maximum, -np.inf)
        if layer == "A":
            lo = np.where(full | (enclosed & cells), z0, lo)  # enclosed things stand on the band floor
            hi = np.where(full, z1, hi)
        klo = np.where(cells, np.floor((lo - z0) / hq + 1e-9), -1).astype(np.int64)
        khi = np.where(cells, np.ceil((hi - z0) / hq - 1e-9), -1).astype(np.int64)
        for key in sorted({(int(a), int(b)) for a, b in zip(klo[cells], khi[cells])}):
            m = cells & (klo == key[0]) & (khi == key[1])
            for gk, blo, bhi, pz in _layer_rects(m, lo, hi, cells, (lx, ly, lp), shape, cell, origin):
                rects.append((gk, blo, bhi, pz, blo[2] <= z0 + eps, bhi[2] >= z1 - eps))
    return rects


def _section_stacks(vf, t, zs, cell, q):
    """Box stacks of section-boxes for one plan cell size (see section_boxes)."""
    ub = _load_builder()
    pf = ub.sample_surface(vf, t, cell / 2)
    origin = pf[:, :2].min(axis=0) - cell
    shape = tuple(int(n) for n in np.ceil((pf[:, :2].max(axis=0) - origin) / cell).astype(np.int64) + 2)
    if shape[0] * shape[1] > 20_000_000:
        raise VariantError(f"section-boxes: plan grid {shape} too large for cell {cell} m")
    ix = np.clip(np.floor((pf[:, 0] - origin[0]) / cell).astype(np.int64), 0, shape[0] - 1)
    iy = np.clip(np.floor((pf[:, 1] - origin[1]) / cell).astype(np.int64), 0, shape[1] - 1)
    colmax = _cell_stat(shape, ix, iy, pf[:, 2], np.maximum, -np.inf)
    stacks: list[dict] = []
    open_by_key: dict = {}
    for b, (z0, z1) in enumerate(zip(zs[:-1], zs[1:])):
        nxt = {}
        for key, lo, hi, pz, full_bottom, full_top in _band_rects(pf, ix, iy, shape, z0, z1, b == 0, colmax, q,
                                                                 cell, origin):
            s = open_by_key.get(key) if full_bottom else None
            if s is not None:  # the same rectangle continues from the band below: one taller box
                s["lo"][:2] = np.minimum(s["lo"][:2], lo[:2])
                s["hi"] = np.array([max(s["hi"][0], hi[0]), max(s["hi"][1], hi[1]), hi[2]])
                s["band_hi"], s["pz_top"] = z1, (pz[1] if pz else None)
            else:
                lo = np.array(lo)
                if pz:  # a new bottom stands on its lowest sample (a room without a floor slab stays open)
                    lo[2] = max(lo[2], pz[0])
                s = {"lo": lo, "hi": np.array(hi), "band_lo": z0, "band_hi": z1, "pz_top": pz[1] if pz else None}
                stacks.append(s)
            if full_top:
                nxt[key] = s
        open_by_key = nxt
    return stacks


def section_boxes(verts, tris, cell: float = SECTION_CELL_M, gap: float | None = None, q: float = SECTION_Q_M,
                  share: float = SECTION_LEVEL_SHARE):
    ub = _load_builder()
    v, t = _check(verts, tris)
    gap = float(ub.GAP_M if gap is None else gap)
    if not (cell > 2 * gap and q > 0):
        raise VariantError("section-boxes: need cell > 2 gap and q > 0")
    angle = ub.facade_angle(v, t)
    vf = v @ ub._rot(-angle).T
    zs = section_levels(vf, t, share)
    if len(zs) < 2 or zs[-1] - zs[0] < SECTION_MIN_M:
        raise VariantError("section-boxes: the mesh has no height")
    attempts = []
    while True:
        stacks = _section_stacks(vf, t, zs, cell, q)
        attempts.append({"cell_m": round(cell, 4), "pieces": len(stacks)})
        if len(stacks) <= MAX_PIECES or len(attempts) >= 8:
            break
        cell *= SECTION_GROW  # reg p.34 §4.2: names 001..999 cap the piece count, not the triangle budget
    back = ub._rot(angle)
    h = gap / 2
    pieces = []
    for s in stacks:
        lo, hi = s["lo"].copy(), s["hi"].copy()
        if s["pz_top"] is not None:  # the top of a stack is its highest sample
            hi[2] = min(hi[2], s["pz_top"])
        if hi[2] - lo[2] < SECTION_MIN_M:
            mid = (hi[2] + lo[2]) / 2
            lo[2] = max(s["band_lo"], min(mid - SECTION_MIN_M / 2, s["band_hi"] - SECTION_MIN_M))
            hi[2] = min(s["band_hi"], lo[2] + SECTION_MIN_M)
        pieces.append(box_piece(lo + h, hi - h, back))
    return pieces, {"angle_deg": angle, "cell_m": cell, "levels_m": [round(z, 3) for z in zs],
                    "bands": len(zs) - 1, "gap_m": gap, "q_m": q, "attempts": attempts}


# ---- ground-coarse-faces (#2053, Codex K16) ----------------------------------------------------------------------

def _tri_plan_area(p):
    return 0.5 * np.abs((p[:, 1, 0] - p[:, 0, 0]) * (p[:, 2, 1] - p[:, 0, 1])
                        - (p[:, 2, 0] - p[:, 0, 0]) * (p[:, 1, 1] - p[:, 0, 1]))


def _minimax_plane(p):
    """Least-squares plane z = a x + b y + c through points, c shifted to the minimax; (plane, max |dev|)."""
    a = np.column_stack([p[:, 0], p[:, 1], np.ones(len(p))])
    sol = np.linalg.lstsq(a, p[:, 2], rcond=None)[0]
    d = p[:, 2] - a @ sol
    sol[2] += (d.max() + d.min()) / 2
    return sol, float((d.max() - d.min()) / 2)


def ground_coarse_faces(verts, tris, tol: float = GROUND_TOL_M, depth: float = 0.5, gap: float | None = None,
                        min_nz: float = GROUND_MIN_NZ, slope_deg: float = GROUND_SLOPE_DEG,
                        model_triangles: int | None = None):
    """Flat part (faces up to `slope_deg`): the shared `build_ground` BSP (large planar prisms); slopes: the
    existing faces, merged into planar clusters whose plan union stays convex."""
    ub = _load_builder()
    v, t = _check(verts, tris)
    gap = float(ub.GAP_M if gap is None else gap)
    if not (tol > 0 and depth > 0):
        raise VariantError("ground-coarse-faces: need tol > 0 and depth > 0")
    n = np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]])
    ln = np.linalg.norm(n, axis=1)
    up = (ln > 1e-12) & (n[:, 2] > min_nz * ln)
    if not up.any():
        raise VariantError("ground-coarse-faces: no up-facing faces")
    hf = ub.HeightField(v, t[up])
    cen = v[t].mean(axis=1)
    top = np.full(len(t), -np.inf)
    top[up] = np.nan_to_num(hf.z(cen[up, :2]), nan=-np.inf)
    keep = up & (cen[:, 2] >= top - 0.01)  # the highest surface only, as build_ground's HeightField
    slope = keep & (n[:, 2] < math.cos(math.radians(slope_deg)) * ln)
    flat_pieces, flat_info = [], {}
    flat_t = t[~slope]
    if len(flat_t) and (up & ~slope).any():
        try:
            res = ub.build_ground(v, flat_t, tol=tol, depth=depth, gap=gap,
                                  model_triangles=len(t) if model_triangles is None else int(model_triangles))
        except ub.UcxBuildError as exc:
            raise VariantError(f"ground-coarse-faces: flat part: {exc}") from exc
        flat_pieces = [(p.verts, p.tris) for p in res.pieces]
        flat_info = {"flat_pieces": len(flat_pieces), "flat_max_vertical_dev_m": res.max_vertical_dev_m,
                     "flat_uncovered_strip_m": res.uncovered_strip_m}
    kid = np.flatnonzero(slope)
    if not len(kid):
        return flat_pieces, {"tol_m": tol, "gap_m": gap, "slope_deg": slope_deg, "slope_faces": 0, **flat_info}
    tp = v[t[kid]]
    area = _tri_plan_area(tp)
    ok = area > 1e-6
    kid, tp, area = kid[ok], tp[ok], area[ok]
    if not len(kid):
        return flat_pieces, {"tol_m": tol, "gap_m": gap, "slope_deg": slope_deg, "slope_faces": 0, **flat_info}
    wkey = np.round(v / WELD_M).astype(np.int64)
    _, wid = np.unique(wkey, axis=0, return_inverse=True)
    wid = wid.reshape(-1)
    wt = wid[t[kid]]
    edge_tris: dict = {}
    for i, (a, b, c) in enumerate(wt.tolist()):
        for e in ((a, b), (b, c), (c, a)):
            edge_tris.setdefault((min(e), max(e)), []).append(i)
    nbr = [set() for _ in range(len(kid))]
    for ts in edge_tris.values():
        for i in ts:
            nbr[i].update(j for j in ts if j != i)
    steep_low: dict[int, float] = {}  # steep faces at a cluster vertex pull its bottom down (kerbs, walls)
    for f in np.flatnonzero((ln > 1e-12) & (np.abs(n[:, 2]) <= min_nz * ln)):
        zlo = float(v[t[f], 2].min())
        for w in wid[t[f]].tolist():
            steep_low[w] = min(steep_low.get(w, np.inf), zlo)
    owner = np.full(len(kid), -1)

    def convex_union(p, ua):
        hull = plan_hull(p[:, :2])
        return len(hull) >= 3 and abs(ub._poly_area(hull)) - ua <= 1e-4 + 1e-3 * ua

    clusters = []  # [members, points, plan area, plane, dev]
    for seed in np.argsort(-area, kind="stable").tolist():
        if owner[seed] >= 0:
            continue
        cid = len(clusters)
        members = [seed]
        owner[seed] = cid
        pts, uarea = tp[seed], float(area[seed])
        plane, dev = _minimax_plane(pts)
        front = sorted(nbr[seed], key=lambda j: -area[j])
        grown = True
        while grown:
            grown = False
            for j in list(front):
                if owner[j] >= 0:
                    front.remove(j)
                    continue
                cand = np.concatenate([pts, tp[j]])
                if not convex_union(cand, uarea + float(area[j])):
                    continue  # the plan union would not be convex
                pl, d = _minimax_plane(cand)
                if d > tol:
                    continue
                members.append(j)
                owner[j] = cid
                pts, uarea, plane, dev = cand, uarea + float(area[j]), pl, d
                front.remove(j)
                front += [k for k in nbr[j] if owner[k] < 0 and k not in front]
                grown = True
        clusters.append([members, pts, uarea, plane, dev])
    # pass 2: merge whole neighbouring clusters (two convex parts can make a convex union that no single
    # face addition reaches), largest combined area first, until no pair passes the plan / plane tests
    merged = True
    while merged:
        merged = False
        pairs = set()
        for i in range(len(kid)):
            for j in nbr[i]:
                a, b = int(owner[i]), int(owner[j])
                if a != b and clusters[a] is not None and clusters[b] is not None:
                    pairs.add((min(a, b), max(a, b)))
        for a, b in sorted(pairs, key=lambda p: -(clusters[p[0]][2] + clusters[p[1]][2])):
            ca, cb = clusters[a], clusters[b]
            if ca is None or cb is None:
                continue
            cand = np.concatenate([ca[1], cb[1]])
            if not convex_union(cand, ca[2] + cb[2]):
                continue
            pl, d = _minimax_plane(cand)
            if d > tol:
                continue
            clusters[a] = [ca[0] + cb[0], cand, ca[2] + cb[2], pl, d]
            clusters[b] = None
            owner[cb[0]] = a
            merged = True
    clusters = [c for c in clusters if c is not None]
    pieces, dropped = [], 0
    for members, pts, _, plane, _ in clusters:
        q = ub._simplify(plan_hull(pts[:, :2]), 0.002)
        q = ub._inset(q, gap / 2) if len(q) >= 3 else np.zeros((0, 2))
        if len(q) < 3:
            dropped += 1
            continue
        tops = q @ plane[:2] + plane[2]
        low = min([steep_low.get(w, np.inf) for w in set(wt[members].ravel().tolist())])
        pc = ub._prism(q, plane, min(low, float(tops.min())) - depth)
        pieces.append((pc.verts, pc.tris))
    return flat_pieces + pieces, {"tol_m": tol, "gap_m": gap, "slope_deg": slope_deg, **flat_info,
                                  "slope_faces": int(len(kid)), "clusters": len(clusters), "dropped_slivers": dropped,
                                  "max_vertical_dev_m": round(max(c[4] for c in clusters), 4),
                                  "single_face_clusters": int(sum(1 for c in clusters if len(c[0]) == 1))}


def build(variant: str, verts, tris, *, model_triangles: int, hull_fn=None, **kw):
    """Run one variant; returns (pieces, info). Raises VariantError, never returns an invalid set."""
    if variant not in ALL_VARIANTS:
        raise VariantError(f"unknown variant {variant!r}; expected one of {ALL_VARIANTS}")
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
    elif variant == "section-boxes":
        pieces, info = section_boxes(verts, tris, **kw)
    elif variant == "ground-coarse-faces":
        pieces, info = ground_coarse_faces(verts, tris, model_triangles=model_triangles, **kw)
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
