"""Ground layered cake (model-ground method C): plan, flat mesh, TIN, Z-only projection, skirt, checks.

Pattern: n/a | new-case: Ground surface master from typed SPOZU adapter output (layered cake, issue #295).

Pure Python (shapely + numpy); the DCC side only turns the returned arrays into a mesh and an FBX.

- ``plan_layers``: base plane = surface (boundary minus footprint holes) with the base covering at level 0;
  every other covering at level 1 (+step); where it lies on a larger non-base covering, that part at level 2.
- ``build_flat``: every layer cut by a ``cell`` grid (4 m) plus the covering edges only (curves simplified with
  ``chord`` deviation), each piece triangulated (constrained Delaunay), stacked tiling UV per grid cell.
- ``build_tin`` / ``project_z``: TIN through the source points (no new vertex), Z-only sampling, misses listed.
- ``add_skirt``: vertical skirt down ``depth`` along every open edge of the base layer (GND-03).
- ``measure_*``: coverage, faces-inside-contour, Z steps, texel density.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import shapely
from shapely import STRtree
from shapely.geometry import MultiPoint, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

GRID = 1e-6
_TRI_REPAIRS: list[str] = []  # pieces whose triangulation needed a make_valid repair (reported by build_flat)


def _polys(g) -> list[Polygon]:
    if g is None or g.is_empty:
        return []
    if g.geom_type == "Polygon":
        return [g]
    out: list[Polygon] = []
    for p in getattr(g, "geoms", []):
        out.extend(_polys(p))
    return out


@dataclass
class Layer:
    slot: str  # material slot
    covering: str  # covering type(s) joined by "+"
    level: int  # 0 base, 1 = +step, 2 = +2 step
    geom: MultiPolygon


@dataclass
class Plan:
    surface: MultiPolygon
    holes: list[Polygon]
    layers: list[Layer]
    step: float
    report: dict = field(default_factory=dict)


def plan_layers(boundary: Polygon, coverings: dict[str, list[Polygon]], base: str, slots: dict[str, str],
                footprint_min_area: float = 1000.0, step: float = 0.006) -> Plan:
    """Layer plan of method C. ``slots`` maps covering type -> material slot (several types may share one).

    Footprints: parts of the boundary not covered by any covering with area >= ``footprint_min_area`` become
    holes (no surface); smaller uncovered slivers stay on the base plane (base covering).
    """
    if boundary is None or boundary.is_empty or not boundary.is_valid:
        raise ValueError("boundary missing or invalid")
    if base not in coverings:
        raise ValueError(f"base covering {base!r} not in coverings")
    if not math.isfinite(step) or step <= 0:
        raise ValueError("step must be a positive finite number")
    unions = {t: unary_union([p.intersection(boundary) for p in ps]) for t, ps in coverings.items() if ps}
    allcov = unary_union(list(unions.values())) if unions else Polygon()
    uncovered = _polys(boundary.difference(allcov))
    holes = sorted((p for p in uncovered if p.area >= footprint_min_area), key=lambda p: -p.area)
    surface = boundary.difference(unary_union(holes)) if holes else boundary
    surface = MultiPolygon(_polys(surface))
    layers = [Layer(slots[base], base, 0, surface)]
    # non-base slots: merge covering types that share a slot, larger slot area first
    by_slot: dict[str, list[str]] = {}
    for t in unions:
        if t != base:
            by_slot.setdefault(slots[t], []).append(t)
    slot_geom = {s: unary_union([unions[t] for t in ts]).intersection(surface) for s, ts in by_slot.items()}
    order = sorted((s for s in slot_geom if not slot_geom[s].is_empty), key=lambda s: -slot_geom[s].area)
    below = Polygon()
    overlaps = {}
    for s in order:
        g = slot_geom[s]
        up = g.intersection(below)
        low = g.difference(up)
        for lev, part in ((1, low), (2, up)):
            ps = [p for p in _polys(part) if p.area > 1e-6]
            if ps:
                layers.append(Layer(s, "+".join(sorted(by_slot[s])), lev, MultiPolygon(ps)))
        if up.area > 0:
            overlaps[s] = round(up.area, 4)
        below = unary_union([below, g])
    rep = {"surface_m2": round(surface.area, 3), "holes_m2": [round(h.area, 2) for h in holes],
           "slivers_on_base": len(uncovered) - len(holes),
           "slivers_m2": round(sum(p.area for p in uncovered) - sum(h.area for h in holes), 3),
           "level2_m2": overlaps}
    return Plan(surface, holes, layers, step, rep)


@dataclass
class Mesh:
    verts: np.ndarray  # (n, 3)
    faces: np.ndarray  # (m, 3) int
    slot: list[str]  # per face
    level: np.ndarray  # per face int (-1 = skirt)
    uv: np.ndarray  # (m, 3, 2) per corner, stacked tiling: one grid cell = [0,1]^2
    cell: float
    report: dict = field(default_factory=dict)


def _cut(geom: MultiPolygon, cell: float, origin: tuple[float, float], grid: float = GRID):
    """Yield (ix, iy, piece) of ``geom`` cut by the cell grid anchored at ``origin``."""
    x0, y0 = origin
    minx, miny, maxx, maxy = geom.bounds
    tree_geom = geom
    for ix in range(int(math.floor((minx - x0) / cell)), int(math.ceil((maxx - x0) / cell))):
        for iy in range(int(math.floor((miny - y0) / cell)), int(math.ceil((maxy - y0) / cell))):
            b = box(x0 + ix * cell, y0 + iy * cell, x0 + (ix + 1) * cell, y0 + (iy + 1) * cell)
            if not tree_geom.intersects(b):
                continue
            piece = tree_geom.intersection(b, grid_size=grid)
            for p in _polys(piece):
                if p.area > 1e-8:
                    yield ix, iy, p


def _tri_piece(p: Polygon) -> list[list[tuple[float, float]]]:
    """Constrained Delaunay triangles of one piece, counter-clockwise (normal +Z), degenerate ones dropped."""
    out = []
    try:
        tri = shapely.constrained_delaunay_triangles(p)
    except shapely.errors.GEOSException:
        # a welded ring can carry repeated / spike points; repair, triangulate each part
        tri = unary_union([shapely.constrained_delaunay_triangles(q)
                           for q in _polys(shapely.make_valid(shapely.remove_repeated_points(p, 1e-9)))
                           if q.area > 1e-10]) if p.area > 1e-10 else Polygon()
        _TRI_REPAIRS.append(p.wkt[:200])
    for t in _polys(tri):
        if t.area < 1e-10:
            continue
        cs = list(t.exterior.coords)[:3]
        if (cs[1][0] - cs[0][0]) * (cs[2][1] - cs[0][1]) - (cs[1][1] - cs[0][1]) * (cs[2][0] - cs[0][0]) < 0:
            cs = [cs[0], cs[2], cs[1]]
        out.append(cs)
    return out


def _partition(lines: list, surface, snap: float) -> list[Polygon]:
    """Faces of the planar subdivision of ``lines`` (snap-rounded noding on a ``snap`` grid) inside ``surface``.
    Adjacent faces share identical edges and vertices, so the mesh built from them has no T-junction."""
    noded = shapely.union_all(shapely.GeometryCollection(_flat_lines(lines)), grid_size=snap)
    faces = [p for p in _polys(shapely.polygonize(_lines(noded))) if p.area > 1e-10]
    if not faces:
        return []
    rp = shapely.get_coordinates(shapely.point_on_surface(faces))
    keep = shapely.contains_xy(surface, rp[:, 0], rp[:, 1])
    return [f for f, k in zip(faces, keep) if k]


def _flat_lines(gs) -> list:
    out = []
    for g in gs:
        out.extend(_lines(g))
    return out


def _lines(g) -> list:
    if g is None or g.is_empty:
        return []
    if g.geom_type in ("LineString", "LinearRing"):
        return [g]
    out = []
    for p in getattr(g, "geoms", []):
        out.extend(_lines(p))
    return out


def build_flat(plan: Plan, cell: float = 4.0, chord: float = 0.02, origin: tuple[float, float] | None = None,
               sampler: "ReliefSampler | None" = None, tol: float = 0.01, max_iter: int = 8,
               snap: float = GRID) -> Mesh:
    """Flat Ground mesh: one plane per layer at z = level * step, cut at ``cell`` + covering edges.

    All layers share ONE planar partition (snap-rounded noding of the surface outline, the upper-layer outlines and
    the ``cell`` grid lines): every face is triangulated once and emitted once per layer covering it (own vertices
    per level). Stacked plates therefore have identical triangles and the gap stays exactly (level) * step over any
    relief; adjacent faces share edges (no T-junction). Upper layers are clipped to the surface and made disjoint
    per level (chord simplification must not create same-level overlaps = z-fighting).

    With ``sampler`` (relief refinement, user decision 2026-10-19): faces whose triangles deviate from the relief
    by more than ``tol`` (exact maximum, ``ReliefSampler.max_error``) get the TIN edges inside them added to the
    linework and the partition is rebuilt; the relief is planar inside each resulting face there, so the error is
    0. Faces elsewhere keep the plain 4 m cut (they only gain the vertices where a TIN edge ends on their border).

    ``snap``: noding grid (1 mm for production: no edge shorter than the snap; outlines move <= snap / sqrt(2)).
    """
    if not (math.isfinite(snap) and 0 < snap <= 0.01):
        raise ValueError("snap must be in (0, 0.01] m")
    if not (math.isfinite(cell) and cell > 0 and math.isfinite(chord) and chord >= 0):
        raise ValueError("cell must be > 0 and chord >= 0, finite")
    if sampler is not None and not (math.isfinite(tol) and tol > 0):
        raise ValueError("tol must be a positive finite number")
    if origin is None:
        minx, miny, _, _ = plan.surface.bounds
        origin = (math.floor(minx / cell) * cell, math.floor(miny / cell) * cell)
    _TRI_REPAIRS.clear()
    geoms: list = []
    taken: dict[int, object] = {}
    for li, lay in enumerate(plan.layers):
        if li == 0:
            g = plan.surface
        else:
            g = lay.geom.simplify(chord, preserve_topology=True) if chord > 0 else lay.geom
            g = shapely.make_valid(g).intersection(plan.surface)
            if lay.level in taken:
                g = g.difference(taken[lay.level])
            taken[lay.level] = unary_union([taken.get(lay.level, Polygon()), g])
        geoms.append(MultiPolygon([p for p in _polys(shapely.make_valid(g)) if p.area > 1e-8]))
    surface = geoms[0]
    x0, y0 = origin
    minx, miny, maxx, maxy = surface.bounds
    grid = [shapely.LineString([(x0 + i * cell, miny - 1), (x0 + i * cell, maxy + 1)])
            for i in range(int(math.floor((minx - x0) / cell)), int(math.ceil((maxx - x0) / cell)) + 1)]
    grid += [shapely.LineString([(minx - 1, y0 + j * cell), (maxx + 1, y0 + j * cell)])
             for j in range(int(math.floor((miny - y0) / cell)), int(math.ceil((maxy - y0) / cell)) + 1)]
    grid = [g.intersection(surface) for g in grid]
    lines = [surface.boundary] + [g.boundary for g in geoms[1:]] + grid
    tin_lines = None
    if sampler is not None:
        e = set()
        for t in sampler.tin.tris:
            for i, j in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                e.add((min(i, j), max(i, j)))
        P = sampler.tin.pts[:, :2]
        tin_lines = shapely.linestrings(np.stack([P[[i for i, _ in e]], P[[j for _, j in e]]], axis=1))
        tin_tree = STRtree(tin_lines)
    relief_region = Polygon()
    max_err_before = None
    for it in range(max_iter + 1):
        faces = _partition(lines, surface, snap)
        tris = [_tri_piece(f) for f in faces]
        if sampler is None:
            break
        flat_t = [t for ts in tris for t in ts]
        err = sampler.max_error(np.array(flat_t, float)) if flat_t else np.zeros(0)
        pos = np.cumsum([0] + [len(ts) for ts in tris])
        ferr = np.array([err[pos[i]:pos[i + 1]].max() if pos[i + 1] > pos[i] else 0.0 for i in range(len(faces))])
        if max_err_before is None:
            max_err_before = float(ferr.max()) if len(ferr) else 0.0
        bad = [faces[i] for i in np.nonzero(ferr > tol)[0]]
        if not bad:
            break
        nbad = [i for i in np.nonzero(ferr > tol)[0]
                if not relief_region.buffer(snap).contains(faces[i])]
        if not nbad:  # every remaining bad face is already TIN-cut: residual from the snap grid, reported
            break
        if it == max_iter:
            raise RuntimeError(f"relief refinement did not converge in {max_iter} rounds")
        region = unary_union([faces[i] for i in nbad])
        relief_region = unary_union([relief_region, region])
        cand = tin_lines[tin_tree.query(region, predicate="intersects")]
        lines.append(shapely.intersection(shapely.multilinestrings(list(cand)), region, grid_size=snap))
    # cell statistics on the partition faces
    rp = shapely.get_coordinates(shapely.point_on_surface(faces)) if faces else np.zeros((0, 2))
    cix = np.floor((rp[:, 0] - x0) / cell).astype(int) if len(rp) else np.zeros(0, int)
    ciy = np.floor((rp[:, 1] - y0) / cell).astype(int) if len(rp) else np.zeros(0, int)
    cells_total = set(zip(cix.tolist(), ciy.tolist()))
    per_cell: dict = {}
    for i, c in enumerate(zip(cix.tolist(), ciy.tolist())):
        per_cell.setdefault(c, []).append(i)
    cells_extra = {c for c, ids in per_cell.items()
                   if len(ids) > 1 or abs(faces[ids[0]].area - cell * cell) >= 1e-6}
    xy_relief = set()
    if not relief_region.is_empty:
        inr = shapely.contains_xy(relief_region.buffer(snap), rp[:, 0], rp[:, 1])
        for i in np.nonzero(inr)[0]:
            xy_relief.add((int(cix[i]), int(ciy[i])))
    # one shared triangle list (welded on the partition vertices)
    V: list[tuple[float, float]] = []
    vkey: dict[tuple[float, float], int] = {}
    T: list[list[int]] = []
    for ts in tris:
        for cs in ts:
            ids = []
            for x, y in cs:
                kk = (round(x, 6), round(y, 6))
                if kk not in vkey:
                    vkey[kk] = len(V)
                    V.append(kk)
                ids.append(vkey[kk])
            T.append(ids)
    refine = {}
    if sampler is not None:
        # residual faces (snap moved a vertex across a steep TIN break): insert the point of maximum deviation
        # (interior split or shared-edge split, no T-junction) until every triangle is within ``tol``; fail closed
        V, T, refine = _refine_relief(V, T, sampler, tol)
    V, T, outl = _recover_outlines(V, T, geoms[1:], snap)
    if sampler is not None and outl["points_inserted"]:  # new points can bend the relief again
        V, T, ref2 = _refine_relief(V, T, sampler, tol)
        refine["points_inserted"] += ref2["points_inserted"]
        refine["max_error_mm"] = ref2["max_error_mm"]
        refine["tri_ids"] = sorted(set(refine["tri_ids"]) | set(ref2["tri_ids"]))
    Va = np.array(V, float).reshape(-1, 2)
    Ta = np.array(T, int).reshape(-1, 3)
    cen = Va[Ta].mean(axis=1) if len(Ta) else np.zeros((0, 2))
    # labels per TRIANGLE (convex, never crossed by a partition line): base + first layer per level whose
    # geometry contains the centroid. A partition face can carry a snap spike into a neighbouring covering, so a
    # face-level interior point may sit in the spike and mislabel the whole face (Mulch faces 3575-3579, v005).
    labels = [[0] for _ in range(len(Ta))]
    for lev in sorted({l.level for l in plan.layers[1:]}):
        free = np.ones(len(Ta), bool)
        for li in range(1, len(geoms)):
            if plan.layers[li].level != lev or geoms[li].is_empty:
                continue
            inside = shapely.contains_xy(geoms[li], cen[:, 0], cen[:, 1]) & free
            for i in np.nonzero(inside)[0]:
                labels[i].append(li)
            free &= ~inside
    tix = np.floor((cen[:, 0] - x0) / cell).astype(int)
    tiy = np.floor((cen[:, 1] - y0) / cell).astype(int)
    if refine:
        for i in refine.pop("tri_ids"):
            xy_relief.add((int(tix[i]), int(tiy[i])))
    outline_cells = sorted({(int(tix[i]), int(tiy[i])) for i in outl.pop("tri_ids")})
    tri_edges = np.linalg.norm(Va[Ta] - Va[np.roll(Ta, 1, axis=1)], axis=2) if len(Ta) else np.zeros((0, 3))
    refined_edges = []
    if xy_relief:
        inr = np.array([(a, b) in xy_relief for a, b in zip(tix.tolist(), tiy.tolist())], bool)
        refined_edges = tri_edges[inr].ravel().tolist()
    verts: list[tuple[float, float, float]] = []
    fl, slots, levels, uvs = [], [], [], []
    index: dict[tuple[int, int], int] = {}
    for i in range(len(Ta)):
        cx0, cy0 = x0 + tix[i] * cell, y0 + tiy[i] * cell
        cs = Va[Ta[i]]
        for li in labels[i]:
            lay = plan.layers[li]
            z = lay.level * plan.step
            ids = []
            for v in Ta[i]:
                kk = (lay.level, int(v))  # same level welded across slots
                if kk not in index:
                    index[kk] = len(verts)
                    verts.append((Va[v, 0], Va[v, 1], z))
                ids.append(index[kk])
            fl.append(ids)
            slots.append(lay.slot)
            levels.append(lay.level)
            # stacked tiling UV: one grid cell = [0, 1]^2, clipped to the closed tile (vertices sit on the cell
            # border at most; the clip only removes float noise)
            uvs.append(np.clip([((x - cx0) / cell, (y - cy0) / cell) for x, y in cs], 0.0, 1.0).tolist())
    m = Mesh(np.array(verts, float), np.array(fl, int).reshape(-1, 3), slots, np.array(levels, int),
             np.array(uvs, float).reshape(-1, 3, 2), cell)
    m.report = {"triangulation_repairs": len(_TRI_REPAIRS), "xy_cells": len(cells_total),
                "xy_cells_with_extra_cuts": len(cells_extra), "partition_faces": len(faces),
                "triangles": len(fl), "origin": list(origin),
                "outline_recovery": {**outl, "cells": [list(c) for c in outline_cells]}, "chord_m": chord, "cell_m": cell, "snap_m": snap}
    if sampler is not None:
        m.report.update({"relief_tol_m": tol, "relief_rounds": it, "relief_cut_xy_cells": len(xy_relief),
                         "relief_cut_xy_list": sorted([list(c) for c in xy_relief]),
                         "relief_region_m2": round(relief_region.area, 3),
                         "relief_max_error_before_mm": (max_err_before or 0.0) * 1000,
                         "relief_residual_partition_faces_over_tol": int((ferr > tol).sum()),
                         **{f"relief_refine_{k}": v for k, v in refine.items()},
                         "relief_shortest_edge_m": min(refined_edges) if refined_edges else None,
                         "shortest_edge_m": float(tri_edges.min()) if len(tri_edges) else None})
    return m


def _insert_points(V: list, T: list, evaluate, what: str, max_rounds: int = 60,
                   eps: float = 1e-6) -> tuple[list, list, dict]:
    """Insert points into a CCW triangle list until ``evaluate`` reports no bad triangle (fail closed).

    ``evaluate(V, T, ids) -> (score, where)``: score > 0 = bad (larger first), where = (x, y) to insert. A point
    strictly inside splits its triangle in 3; a point on an edge (within ``eps``) splits that edge in BOTH
    triangles sharing it (no T-junction). Raises when a round makes no progress or ``max_rounds`` is exceeded.
    Returns (V, T, report) with report["tri_ids"] = final triangles created by a split.
    """
    V = [tuple(v) for v in V]
    T = [list(t) for t in T]
    key = {(round(x, 6), round(y, 6)): i for i, (x, y) in enumerate(V)}
    created = [False] * len(T)
    sc, w = evaluate(V, T, list(range(len(T))))
    score, where = list(map(float, sc)), [tuple(p) for p in w]
    before = int((np.asarray(sc) > 0).sum())
    inserted = 0
    for rnd in range(max_rounds + 1):
        bad = sorted((i for i in range(len(T)) if score[i] > 0), key=lambda i: -score[i])
        if not bad:
            return V, T, {"rounds": rnd, "triangles_bad_before": before, "points_inserted": inserted,
                          "tri_ids": [i for i, c in enumerate(created) if c]}
        if rnd == max_rounds:
            raise RuntimeError(f"{what}: {len(bad)} triangles still bad after {max_rounds} rounds")
        emap: dict[tuple[int, int], list[int]] = {}
        for ti, (a, b, c) in enumerate(T):
            for u, v in ((a, b), (b, c), (c, a)):
                emap.setdefault((min(u, v), max(u, v)), []).append(ti)
        touched: set[int] = set()
        changed: list[int] = []
        for ti in bad:
            if ti in touched:
                continue
            p = np.array(where[ti], float)
            if not np.isfinite(p).all():
                continue
            a, b, c = T[ti]
            P = np.array([V[a], V[b], V[c]], float)
            best = None
            for k, (u, v) in enumerate(((a, b), (b, c), (c, a))):
                A, B = P[k], P[(k + 1) % 3]
                d = B - A
                t = float(np.clip(np.dot(p - A, d) / np.dot(d, d), 0.0, 1.0))
                dist = float(np.linalg.norm(A + t * d - p))
                if dist < eps and (best is None or dist < best[0]):
                    best = (dist, u, v, A + t * d)
            q = best[3] if best else p
            kq = (round(float(q[0]), 6), round(float(q[1]), 6))
            if kq in key:
                continue  # rounds onto an existing vertex: no progress from this point
            if best is not None:
                u, v = best[1], best[2]
                adj = emap[(min(u, v), max(u, v))]
                if any(t in touched for t in adj):
                    continue
                key[kq] = n = len(V)
                V.append(kq)
                for t in adj:
                    tri = T[t]
                    j = next(j for j in range(3) if {tri[j], tri[(j + 1) % 3]} == {u, v})
                    x, y, o = tri[j], tri[(j + 1) % 3], tri[(j + 2) % 3]
                    T[t] = [x, n, o]
                    T.append([n, y, o])
                    created[t] = True
                    created.append(True)
                    touched.add(t)
                    changed += [t, len(T) - 1]
            else:
                key[kq] = n = len(V)
                V.append(kq)
                T[ti] = [a, b, n]
                T += [[b, c, n], [c, a, n]]
                created[ti] = True
                created += [True, True]
                touched.add(ti)
                changed += [ti, len(T) - 2, len(T) - 1]
            inserted += 1
        if not changed:
            raise RuntimeError(f"{what} stuck: {len(bad)} bad triangles, no insertable point")
        score += [0.0] * (len(T) - len(score))
        where += [(np.nan, np.nan)] * (len(T) - len(where))
        sc, w = evaluate(V, T, changed)
        for i, ev, wv in zip(changed, sc, w):
            score[i], where[i] = float(ev), tuple(wv)
    raise AssertionError("unreachable")


def _refine_relief(V: list, T: list, sampler: "ReliefSampler", tol: float) -> tuple[list, list, dict]:
    """Insert the point of maximum relief deviation into every triangle off by more than ``tol`` (exact
    maximum) until none is; residuals come from the snap moving a vertex across a steep TIN break."""
    def ev(V, T, ids):
        if not ids:
            return np.zeros(0), np.zeros((0, 2))
        e, w = sampler.max_error(np.array(V, float)[np.array([T[i] for i in ids], int)], return_where=True)
        return np.where(e > tol, e, 0.0), w
    V, T, rep = _insert_points(V, T, ev, "relief refinement")
    xy = np.array(V, float)[np.array(T, int)]
    rep["max_error_mm"] = float(sampler.max_error(xy).max() * 1000) if len(T) else 0.0
    return V, T, rep


def _recover_outlines(V: list, T: list, regions: list, snap: float) -> tuple[list, list, dict]:
    """Insert outline crossings into every triangle whose centroid side of a layer outline disagrees with a part
    of it farther than 2 ``snap`` on the other side (noding can drop a collapsed sliver of a narrow covering as a cut edge, so its outline never
    reaches the partition); afterwards each triangle is on one side and its centroid label is right."""
    prepped = []
    for g in regions:
        if g.is_empty:
            continue
        inner, outer = g.buffer(-2 * snap), g.buffer(2 * snap)
        shapely.prepare(inner)
        shapely.prepare(outer)
        shapely.prepare(g)
        prepped.append((g, inner, outer, g.boundary))

    def ev(V, T, ids):
        sc = np.zeros(len(ids))
        w = np.full((len(ids), 2), np.nan)
        if not ids:
            return sc, w
        tri = shapely.polygons(np.array(V, float)[np.array([T[i] for i in ids], int)])
        for g, inner, outer, bnd in prepped:
            c = shapely.centroid(tri)
            inside = shapely.contains(g, c)
            cand = np.nonzero(np.where(inside, ~shapely.within(tri, outer), shapely.intersects(tri, inner))
                              & (sc == 0))[0]
            for k in cand:
                corners = shapely.get_coordinates(tri[k])[:3]
                pts = np.vstack([shapely.get_coordinates(shapely.intersection(tri[k].boundary, bnd)),
                                 shapely.get_coordinates(shapely.intersection(bnd, tri[k]))])
                if len(pts):
                    dmin = np.min(np.linalg.norm(pts[:, None, :] - corners[None], axis=2), axis=1)
                    pts, dmin = pts[dmin > 1e-5], dmin[dmin > 1e-5]
                sc[k] = float(tri[k].area) + 1e-12
                ln = np.linalg.norm(corners - np.roll(corners, -1, axis=0), axis=1)
                j = int(np.argmax(ln))
                if len(pts) and 2 * tri[k].area / ln[j] >= 2 * snap:
                    w[k] = pts[int(np.argmax(dmin))]
                else:  # sliver along the outline (crossings numerically unstable): bisect its longest edge
                    w[k] = (corners[j] + corners[(j + 1) % 3]) / 2
        return sc, w
    return _insert_points(V, T, ev, "outline recovery")


# ---------------------------------------------------------------- relief


@dataclass
class Tin:
    pts: np.ndarray  # (n, 3) unique source points
    tris: np.ndarray  # (m, 3) index into pts
    contradictory: list[tuple[float, float, list[float]]]
    merged: int


def build_tin(points: list[tuple[float, float, float]], xy_tol: float = 0.001, z_tol: float = 0.001) -> Tin:
    """Delaunay TIN through the source points; same XY + same Z merged, same XY + other Z -> contradictory (dropped)."""
    groups: dict[tuple[int, int], list[float]] = {}
    for x, y, z in points:
        if not all(math.isfinite(v) for v in (x, y, z)):
            raise ValueError(f"non-finite elevation point {(x, y, z)}")
        groups.setdefault((round(x / xy_tol), round(y / xy_tol)), []).append(z)
    pts, contra, merged = [], [], 0
    for (kx, ky), zs in groups.items():
        if max(zs) - min(zs) > z_tol:
            contra.append((kx * xy_tol, ky * xy_tol, sorted(zs)))
            continue
        merged += len(zs) - 1
        pts.append((kx * xy_tol, ky * xy_tol, zs[0]))
    if len(pts) < 3:
        raise ValueError("fewer than 3 distinct elevation points: no relief")
    arr = np.array(pts, float)
    tri = shapely.delaunay_triangles(MultiPoint(arr[:, :2]))
    lookup = {(round(x / xy_tol), round(y / xy_tol)): i for i, (x, y, _) in enumerate(arr)}
    tris = []
    for t in _polys(tri):
        cs = list(t.exterior.coords)[:3]
        tris.append([lookup[(round(x / xy_tol), round(y / xy_tol))] for x, y in cs])
    if not tris:
        raise ValueError("elevation points are collinear: no relief")
    return Tin(arr, np.array(tris, int), contra, merged)


class ReliefSampler:
    def __init__(self, tin: Tin):
        self.tin = tin
        self.polys = [Polygon(tin.pts[t, :2]) for t in tin.tris]
        self.tree = STRtree(self.polys)
        P = tin.pts[tin.tris]  # (m, 3, 3)
        A = np.concatenate([P[:, :, :2], np.ones((len(P), 3, 1))], axis=2)
        self.planes = np.linalg.solve(A, P[:, :, 2:3])[:, :, 0]  # z = a x + b y + c per TIN triangle

    def max_error(self, xy: np.ndarray, z: np.ndarray | None = None, return_where: bool = False):
        """Exact max |face plane - relief| per triangle (m, 3, 2); ``z`` (m, 3) defaults to the relief at the
        corners. The relief is piecewise planar, so the maximum lies at a vertex of face ∩ TIN triangle."""
        xy = np.asarray(xy, float).reshape(-1, 3, 2)
        m = len(xy)
        if z is None:
            zz, hit = self.sample(xy.reshape(-1, 2))
            if not hit.all():
                raise ValueError("face corner outside the TIN: relief error undefined")
            z = zz.reshape(-1, 3)
        A = np.concatenate([xy, np.ones((m, 3, 1))], axis=2)
        ok = np.abs(np.linalg.det(A)) > 1e-14
        fp = np.zeros((m, 3))
        fp[ok] = np.linalg.solve(A[ok], np.asarray(z, float)[ok][:, :, None])[:, :, 0]
        polys = shapely.polygons(xy)
        qi, ti = self.tree.query(polys, predicate="intersects")
        inter = shapely.intersection(polys[qi], np.array(self.polys, dtype=object)[ti])
        coords, idx = shapely.get_coordinates(inter, return_index=True)
        f, t = qi[idx], ti[idx]
        x, y = coords[:, 0], coords[:, 1]
        d = np.abs(fp[f, 0] * x + fp[f, 1] * y + fp[f, 2]
                   - (self.planes[t, 0] * x + self.planes[t, 1] * y + self.planes[t, 2]))
        err = np.zeros(m)
        np.maximum.at(err, f, d)
        err[~ok] = 0.0
        if not return_where:
            return err
        where = np.full((m, 2), np.nan)
        if len(d):
            order = np.lexsort((-d, f))
            first = order[np.r_[True, f[order][1:] != f[order][:-1]]]
            where[f[first]] = coords[first]
        where[~ok] = np.nan
        return err, where

    def sample(self, xy: np.ndarray, eps: float = 1e-7) -> tuple[np.ndarray, np.ndarray]:
        """Relief Z straight below every XY; returns (z, hit mask). Misses get NaN."""
        xy = np.asarray(xy, float).reshape(-1, 2)
        z = np.full(len(xy), np.nan)
        pts = shapely.points(xy)
        qi, ti = self.tree.query(pts, predicate="intersects")
        done = np.zeros(len(xy), bool)
        P = self.tin.pts
        for q, t in zip(qi, ti):
            if done[q]:
                continue
            a, b, c = P[self.tin.tris[t]]
            d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(d) < 1e-14:
                continue
            x, y = xy[q]
            l1 = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / d
            l2 = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / d
            l3 = 1 - l1 - l2
            if min(l1, l2, l3) < -eps:
                continue
            z[q] = l1 * a[2] + l2 * b[2] + l3 * c[2]
            done[q] = True
        return z, done


def project_z(mesh: Mesh, sampler: ReliefSampler, step: float) -> tuple[Mesh, list[int]]:
    """Z-only projection: z = relief(x, y) + level * step per vertex; misses listed and never moved.

    Raises when a vertex is used by faces of different levels (a layer must not share vertices).
    """
    lev_of = np.full(len(mesh.verts), -99)
    for f, lv in zip(mesh.faces, mesh.level):
        for v in f:
            if lev_of[v] not in (-99, lv):
                raise ValueError(f"vertex {v} shared by levels {lev_of[v]} and {lv}")
            lev_of[v] = lv
    z, hit = sampler.sample(mesh.verts[:, :2])
    misses = [int(i) for i in np.nonzero(~hit)[0]]
    nv = mesh.verts.copy()
    ok = hit & (lev_of >= 0)
    nv[ok, 2] = z[ok] + lev_of[ok] * step
    out = Mesh(nv, mesh.faces.copy(), list(mesh.slot), mesh.level.copy(), mesh.uv.copy(), mesh.cell, dict(mesh.report))
    out.report["projection_misses"] = len(misses)
    return out, misses


def add_skirt(mesh: Mesh, depth: float = 1.0, slot: str = "Skirt") -> Mesh:
    """Vertical skirt down ``depth`` m along every open (single-face) edge of the base layer."""
    if not math.isfinite(depth) or depth < 1.0:
        raise ValueError("skirt depth must be >= 1 m (GND-03)")
    count: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for fi, (f, lv) in enumerate(zip(mesh.faces, mesh.level)):
        if lv != 0:
            continue
        for a, b in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
            count.setdefault((min(a, b), max(a, b)), []).append((a, b))
    verts = [tuple(v) for v in mesh.verts]
    low: dict[int, int] = {}
    faces, uvs = [], []
    for k, uses in count.items():
        if len(uses) != 1:
            continue
        a, b = uses[0]  # directed as in the CCW face: outside is to the right
        for v in (a, b):
            if v not in low:
                low[v] = len(verts)
                x, y, z = mesh.verts[v]
                verts.append((x, y, z - depth))
        la, lb = low[a], low[b]
        # wall facing outward: (b, a, la) and (b, la, lb) — normal points right of a->b
        faces += [[b, a, la], [b, la, lb]]
        uvs += [[(0.5, 0.5)] * 3] * 2
    n = len(faces)
    out = Mesh(np.array(verts, float), np.vstack([mesh.faces, np.array(faces, int).reshape(-1, 3)]),
               list(mesh.slot) + [slot] * n, np.concatenate([mesh.level, -np.ones(n, int)]),
               np.concatenate([mesh.uv, np.array(uvs, float).reshape(-1, 3, 2)]), mesh.cell, dict(mesh.report))
    out.report["skirt_faces"] = n
    out.report["skirt_depth_m"] = depth
    return out


# ---------------------------------------------------------------- measurements


def face_polys(mesh: Mesh, mask=None) -> list[Polygon]:
    idx = range(len(mesh.faces)) if mask is None else np.nonzero(mask)[0]
    return [Polygon(mesh.verts[mesh.faces[i], :2]) for i in idx]


def measure_inside(mesh: Mesh, plan: Plan, tol: float = 0.02) -> dict:
    """Every surface face of a layer inside that layer's contour buffered by ``tol`` (the chord)."""
    bad = 0
    total = 0
    for lay in plan.layers:
        region = lay.geom.buffer(tol, quad_segs=64)  # 8 segments inscribe the arc 0.4 mm inside a 22 mm buffer
        tree_ok = region
        m = np.array([s == lay.slot for s in mesh.slot]) & (mesh.level == lay.level)
        for p in face_polys(mesh, m):
            total += 1
            if not tree_ok.covers(p):
                bad += 1
    return {"faces": total, "outside": bad, "tol_m": tol}


def measure_coverage(mesh: Mesh, plan: Plan, tol: float = 0.0) -> dict:
    """Top-down coverage of the surface (boundary minus holes) by the base layer faces; with ``tol`` (the vertex
    snap) also the gap left after shrinking the surface by ``tol`` (coverage within the stated tolerance)."""
    base = unary_union(face_polys(mesh, mesh.level == 0))
    gap = plan.surface.difference(base).area
    out = {"surface_m2": plan.surface.area, "base_m2": base.area, "uncovered_m2": gap,
           "coverage_pct": 100.0 * (1 - gap / plan.surface.area)}
    if tol > 0:
        out["tol_m"] = tol
        out["uncovered_beyond_tol_m2"] = plan.surface.buffer(-tol).difference(base).area
        out["outside_surface_beyond_tol_m2"] = base.difference(plan.surface.buffer(tol)).area
    return out


def measure_steps(mesh: Mesh, sampler: ReliefSampler, step: float) -> dict:
    """Layer gap against the relief at vertices and face centres: |z - relief - level*step| in metres."""
    surf = mesh.level >= 0
    vids = np.unique(mesh.faces[surf])
    lev_v = np.zeros(len(mesh.verts), int)
    for f, lv in zip(mesh.faces[surf], mesh.level[surf]):
        lev_v[f] = lv
    zr, hit = sampler.sample(mesh.verts[vids, :2])
    dv = np.abs(mesh.verts[vids, 2] - zr - lev_v[vids] * step)
    cent = mesh.verts[mesh.faces[surf]].mean(axis=1)
    zc, hitc = sampler.sample(cent[:, :2])
    dc = np.abs(cent[:, 2] - zc - mesh.level[surf] * step)
    return {"vertex_max_mm": float(np.nanmax(dv) * 1000) if len(dv) else 0.0,
            "centre_max_mm": float(np.nanmax(dc) * 1000) if len(dc) else 0.0,
            "centres_over_1mm": int(np.sum(dc > 0.001)), "centres": int(len(dc)),
            "misses": int(np.sum(~hit) + np.sum(~hitc))}


def measure_relief_error(mesh: Mesh, sampler: ReliefSampler, step: float, tol: float = 0.01) -> dict:
    """Exact max deviation of every surface face from relief + level*step (whole face, not only centres)."""
    surf = mesh.level >= 0
    f = mesh.faces[surf]
    p = mesh.verts[f]
    err = sampler.max_error(p[:, :, :2], p[:, :, 2] - mesh.level[surf][:, None] * step)
    return {"faces": int(len(err)), "max_mm": float(err.max() * 1000) if len(err) else 0.0,
            "faces_over_tol": int((err > tol).sum()), "tol_mm": tol * 1000}


def measure_stack_gaps(mesh: Mesh, step: float) -> dict:
    """At the centroid of every upper-layer face: Z gap to the face below it of every lower level against
    (level difference) * step; and the area where two faces of the same level overlap top-down."""
    surf = np.nonzero(mesh.level >= 0)[0]
    polys = shapely.polygons(mesh.verts[mesh.faces[surf], :2])
    P = mesh.verts[mesh.faces[surf]]
    A = np.concatenate([P[:, :, :2], np.ones((len(P), 3, 1))], axis=2)
    ok = np.abs(np.linalg.det(A)) > 1e-14
    pl = np.zeros((len(P), 3))
    pl[ok] = np.linalg.solve(A[ok], P[ok][:, :, 2:3])[:, :, 0]
    lev = mesh.level[surf]
    up = np.nonzero((lev > 0) & ok)[0]
    cen = P[up].mean(axis=1)
    tree = STRtree(polys)
    qi, ti = tree.query(shapely.points(cen[:, :2]), predicate="intersects")
    a, b = up[qi], ti
    k = (lev[b] < lev[a]) & ok[b]
    a, b, c = a[k], b[k], cen[qi[k]]
    zb = pl[b, 0] * c[:, 0] + pl[b, 1] * c[:, 1] + pl[b, 2]
    err = np.abs(c[:, 2] - zb - (lev[a] - lev[b]) * step)
    i, j = tree.query(polys, predicate="intersects")
    k = (i < j) & (lev[i] == lev[j])
    inter = shapely.area(shapely.intersection(polys[i[k]], polys[j[k]])) if k.any() else np.zeros(0)
    return {"checked": int(len(err)), "max_gap_error_mm": float(err.max() * 1000) if len(err) else 0.0,
            "min_gap_mm": float((c[:, 2] - zb).min() * 1000) if len(err) else None,
            "same_level_overlap_m2": float(inter.sum())}


def measure_open_edges(mesh: Mesh, plan: Plan, eps: float = 1e-5) -> dict:
    """Open edges of the base layer that do not lie on the surface outline (cracks / T-junctions)."""
    count: dict[tuple[int, int], int] = {}
    for f, lv in zip(mesh.faces, mesh.level):
        if lv != 0:
            continue
        for a, b in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
            k = (min(a, b), max(a, b))
            count[k] = count.get(k, 0) + 1
    open_e = [k for k, c in count.items() if c == 1]
    outline = plan.surface.boundary
    mids = shapely.points((mesh.verts[[a for a, _ in open_e], :2] + mesh.verts[[b for _, b in open_e], :2]) / 2) \
        if open_e else []
    inner = int(np.sum(shapely.distance(mids, outline) > eps)) if open_e else 0  # eps >= the vertex snap
    return {"open_edges": len(open_e), "open_edges_off_outline": inner, "non_manifold": sum(c > 2 for c in count.values())}


def texel_density(verts: np.ndarray, faces: np.ndarray, uv: np.ndarray, tex_px: int) -> np.ndarray:
    """Per face px per linear metre: tex_px * sqrt(uv area / 3D area). NaN for degenerate faces."""
    p = verts[faces]
    a3 = 0.5 * np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1)
    e1, e2 = uv[:, 1] - uv[:, 0], uv[:, 2] - uv[:, 0]
    a2 = 0.5 * np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0])
    with np.errstate(divide="ignore", invalid="ignore"):
        d = tex_px * np.sqrt(a2 / a3)
    d[(a3 < 1e-12) | (a2 < 1e-16)] = np.nan
    return d


def fix_density(verts: np.ndarray, faces: np.ndarray, uv: np.ndarray, tex_px: int, lo: float, hi: float,
                target: float) -> tuple[np.ndarray, np.ndarray]:
    """Faces whose texel density is outside [lo, hi] (steep relief stretches the top-down UV) get their UV scaled
    about the face UV centroid to ``target`` px/m; every other face keeps its UV. Returns (uv, fixed face ids)."""
    if not (lo <= target <= hi):
        raise ValueError("target density outside the band")
    d = texel_density(verts, faces, uv, tex_px)
    bad = np.nonzero(np.isfinite(d) & ((d < lo) | (d > hi)))[0]
    out = uv.copy()
    c = uv[bad].mean(axis=1, keepdims=True)
    out[bad] = c + (uv[bad] - c) * (target / d[bad])[:, None, None]
    return out, bad


def side_project_uv(verts: np.ndarray, faces: np.ndarray, uv: np.ndarray, tex_px: int, lo: float,
                    length: float, wrap: bool) -> tuple[np.ndarray, np.ndarray]:
    """Faces whose top-down texel density is below ``lo`` (steep relief: walls, step risers) get a projection onto
    the vertical plane of their dominant horizontal normal axis at the same scale (``length`` metres per UV unit), shifted by whole UV units next to the origin:
    normal mostly along Y -> (x, z), along X -> (y, z); u flipped where needed so no island is mirrored (UV winding
    = face winding). With ``wrap`` every such triangle is shifted by whole UV units into the tile [0, 1]^2 (an
    integer shift is the same texel of a tiling texture). Density after >= tex_px / length * 0.68 (dominant axis
    >= 0.683 of the normal whenever the top-down density failed with lo >= 0.5 * flat). Every other face keeps
    its UV. Returns (uv, side face ids). Their crease with the top-down neighbours is a texture seam (reported)."""
    d = texel_density(verts, faces, uv, tex_px)
    ids = np.nonzero(np.isfinite(d) & (d < lo))[0]
    out = uv.copy()
    if not len(ids):
        return out, ids
    P = verts[faces[ids]]
    n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    alongy = np.abs(n[:, 1]) >= np.abs(n[:, 0])
    h = np.where(alongy[:, None], P[:, :, 0], P[:, :, 1])
    q = np.stack([h / length, P[:, :, 2] / length], axis=2)
    e1, e2 = q[:, 1] - q[:, 0], q[:, 2] - q[:, 0]
    flip = (e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) < 0
    q[flip, :, 0] *= -1
    q -= np.floor(q.min(axis=1, keepdims=True) + 1e-9)  # whole-unit shift: same texel, small float32 UV
    if wrap:
        over = np.any(q.max(axis=1) > 1 + 1e-9, axis=1)  # integer shift cannot fit: shift to 0 (own island)
        q[over] -= q[over].min(axis=1, keepdims=True)
    out[ids] = q
    return out, ids


def uv_tile_report(uv: np.ndarray, eps: float = 1e-9) -> dict:
    """UDIM containment of per-corner UV (m, 3, 2): a triangle is tile-contained when all corners lie in one closed
    tile [i, i+1] x [j, j+1] (corners exactly on a tile border count for that tile). Returns the UDIM numbers used
    (1001 + i + 10 j, sorted) and the number of straddling triangles; u outside [0, 10) or v < 0 is invalid."""
    uv = np.asarray(uv, float).reshape(-1, 3, 2)
    lo = np.floor(uv.min(axis=1) + eps)
    straddle = np.any(uv.max(axis=1) > lo + 1 + eps, axis=1)
    bad_range = (lo[:, 0] < 0) | (lo[:, 0] > 9) | (lo[:, 1] < 0)
    tiles = sorted({int(1001 + i + 10 * j) for i, j in lo[~straddle & ~bad_range].astype(int).tolist()})
    return {"triangles": int(len(uv)), "straddling": int(straddle.sum()), "outside_udim_range": int(bad_range.sum()),
            "tiles": tiles, "u_range": [float(uv[..., 0].min()), float(uv[..., 0].max())] if len(uv) else None,
            "v_range": [float(uv[..., 1].min()), float(uv[..., 1].max())] if len(uv) else None}


def uv_scale_for_density(cell: float, tex_px: int, px_per_m: float) -> float:
    """UV side of one stacked cell for a target density: cell * density / tex_px."""
    return cell * px_per_m / tex_px


def mesh_to_dict(mesh: Mesh, slots_order: list[str]) -> dict:
    sid = {s: i for i, s in enumerate(slots_order)}
    return {"verts": mesh.verts.round(6).tolist(), "faces": mesh.faces.tolist(),
            "mat": [sid[s] for s in mesh.slot], "level": mesh.level.tolist(),
            "uv": mesh.uv.round(7).tolist(), "slots": slots_order, "report": mesh.report}
