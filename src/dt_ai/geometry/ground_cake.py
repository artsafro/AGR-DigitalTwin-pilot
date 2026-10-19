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


def _cut(geom: MultiPolygon, cell: float, origin: tuple[float, float]):
    """Yield (ix, iy, piece) of ``geom`` cut by the cell grid anchored at ``origin``."""
    x0, y0 = origin
    minx, miny, maxx, maxy = geom.bounds
    tree_geom = geom
    for ix in range(int(math.floor((minx - x0) / cell)), int(math.ceil((maxx - x0) / cell))):
        for iy in range(int(math.floor((miny - y0) / cell)), int(math.ceil((maxy - y0) / cell))):
            b = box(x0 + ix * cell, y0 + iy * cell, x0 + (ix + 1) * cell, y0 + (iy + 1) * cell)
            if not tree_geom.intersects(b):
                continue
            piece = tree_geom.intersection(b, grid_size=GRID)
            for p in _polys(piece):
                if p.area > 1e-8:
                    yield ix, iy, p


def build_flat(plan: Plan, cell: float = 4.0, chord: float = 0.02, origin: tuple[float, float] | None = None) -> Mesh:
    """Flat Ground mesh: one plane per layer at z = level * step, cut at ``cell`` + covering edges."""
    if not (math.isfinite(cell) and cell > 0 and math.isfinite(chord) and chord >= 0):
        raise ValueError("cell must be > 0 and chord >= 0, finite")
    if origin is None:
        minx, miny, _, _ = plan.surface.bounds
        origin = (math.floor(minx / cell) * cell, math.floor(miny / cell) * cell)
    verts: list[tuple[float, float, float]] = []
    faces, slots, levels, uvs = [], [], [], []
    cells_total, cells_extra = set(), set()
    for li, lay in enumerate(plan.layers):
        z = lay.level * plan.step
        # the base plane keeps the exact surface outline (100 % top-down coverage); upper layers follow their
        # covering edges with chord deviation <= chord
        g = lay.geom.simplify(chord, preserve_topology=True) if chord > 0 and lay.level > 0 else lay.geom
        g = MultiPolygon([p for p in _polys(shapely.make_valid(g)) if p.area > 1e-8])
        index: dict[tuple[float, float], int] = {}
        for ix, iy, piece in _cut(g, cell, origin):
            cells_total.add((li, ix, iy))
            is_full = abs(piece.area - cell * cell) < 1e-6
            if not is_full:
                cells_extra.add((li, ix, iy))
            cx0, cy0 = origin[0] + ix * cell, origin[1] + iy * cell
            tris = shapely.constrained_delaunay_triangles(piece)
            for t in _polys(tris):
                if t.area < 1e-10:
                    continue
                cs = list(t.exterior.coords)[:3]
                # counter-clockwise (normal +Z)
                if (cs[1][0] - cs[0][0]) * (cs[2][1] - cs[0][1]) - (cs[1][1] - cs[0][1]) * (cs[2][0] - cs[0][0]) < 0:
                    cs = [cs[0], cs[2], cs[1]]
                ids = []
                for x, y in cs:
                    k = (round(x, 6), round(y, 6))
                    if k not in index:
                        index[k] = len(verts)
                        verts.append((k[0], k[1], z))
                    ids.append(index[k])
                faces.append(ids)
                slots.append(lay.slot)
                levels.append(lay.level)
                uvs.append([((x - cx0) / cell, (y - cy0) / cell) for x, y in cs])
    m = Mesh(np.array(verts, float), np.array(faces, int).reshape(-1, 3), slots, np.array(levels, int),
             np.array(uvs, float).reshape(-1, 3, 2), cell)
    m.report = {"cells": len(cells_total), "cells_with_extra_cuts": len(cells_extra), "triangles": len(faces),
                "origin": list(origin), "chord_m": chord, "cell_m": cell}
    return m


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
        region = lay.geom.buffer(tol)
        tree_ok = region
        m = np.array([s == lay.slot for s in mesh.slot]) & (mesh.level == lay.level)
        for p in face_polys(mesh, m):
            total += 1
            if not tree_ok.covers(p):
                bad += 1
    return {"faces": total, "outside": bad, "tol_m": tol}


def measure_coverage(mesh: Mesh, plan: Plan) -> dict:
    """Top-down coverage of the surface (boundary minus holes) by the base layer faces."""
    base = unary_union(face_polys(mesh, mesh.level == 0))
    gap = plan.surface.difference(base).area
    return {"surface_m2": plan.surface.area, "base_m2": base.area, "uncovered_m2": gap,
            "coverage_pct": 100.0 * (1 - gap / plan.surface.area)}


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


def uv_scale_for_density(cell: float, tex_px: int, px_per_m: float) -> float:
    """UV side of one stacked cell for a target density: cell * density / tex_px."""
    return cell * px_per_m / tex_px


def mesh_to_dict(mesh: Mesh, slots_order: list[str]) -> dict:
    sid = {s: i for i, s in enumerate(slots_order)}
    return {"verts": mesh.verts.round(6).tolist(), "faces": mesh.faces.tolist(),
            "mat": [sid[s] for s in mesh.slot], "level": mesh.level.tolist(),
            "uv": mesh.uv.round(7).tolist(), "slots": slots_order, "report": mesh.report}
