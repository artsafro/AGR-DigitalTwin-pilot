"""ground-terrain variant meshers (methods catalog, #733): plan polygon, constrained Delaunay, grid cut, relief.

Pattern: new-case: Ground surface meshers compared in docs/methods/ground-terrain (CDT per grid cell, grid cut).

Pure numpy / shapely (shapely imported lazily so Blender's Python can import `inside_even_odd` and `mesh_dict`).
Our own code; the plan polygon comes from the same method-C planner the Ground builder uses
(`dt_ai.geometry.ground_cake.plan_layers` with build_ground.py's slot map and step), never from the reference FBX.
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
BUILD_GROUND = ROOT / "jobs" / "VATUTINO-SITE" / "build_ground.py"
UV_PER_M = 1280.0 / 4096.0  # world-planar UV at the builder's VPM density (1280 px/m on a 4K map), tiling
WELD_DECIMALS = 6  # vertices of neighbouring cells are welded at 1 micrometre


def _check_cell(cell) -> float:
    if isinstance(cell, bool) or not isinstance(cell, (int, float)) or not math.isfinite(cell) or cell <= 0:
        raise ValueError(f"cell must be a finite number > 0, got {cell!r}")
    return float(cell)


def _builder():
    spec = importlib.util.spec_from_file_location("methods_build_ground", BUILD_GROUND)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def plan_polygon(adapter: dict, footprint_min: float = 1000.0):
    """Plan surface of the typed adapter: boundary minus footprints (uncovered parts >= footprint_min), exactly as
    build_ground.py calls the planner (same covering parsing, slot map and step). Stairs are not cut here."""
    from shapely.geometry import MultiPolygon, shape

    from dt_ai.geometry import ground_cake as gc

    bg = _builder()
    boundary = shape(adapter["boundary"])
    cov = {t: list(getattr(shape(c["geometry"]), "geoms", [])) for t, c in adapter["coverings"].items()}
    plan = gc.plan_layers(boundary, cov, adapter["base_covering"], bg.SLOTS, footprint_min_area=footprint_min,
                          step=bg.STEP)
    surface = plan.surface
    return surface if isinstance(surface, MultiPolygon) else MultiPolygon([surface])


def relief_points(adapter: dict) -> list[tuple[float, float, float]]:
    """Every adapter elevation (spot heights + contour vertices), as build_ground.py feeds its TIN."""
    return [(e["x"], e["y"], e["z"]) for e in adapter["elevations"]]


def plan_rings(poly) -> list[list[tuple[float, float]]]:
    """Exterior and interior rings of every part (even-odd: holes toggle back to outside)."""
    parts = getattr(poly, "geoms", [poly])
    return [list(r.coords) for p in parts if not p.is_empty for r in (p.exterior, *p.interiors)]


def inside_even_odd(points, rings, chunk: int = 512) -> np.ndarray:
    """Even-odd point-in-polygon of (n, 2) points against closed rings; numpy only (also runs in Blender)."""
    pts = np.asarray(points, float).reshape(-1, 2)
    inside = np.zeros(len(pts), bool)
    seg = []
    for ring in rings:
        r = np.asarray(ring, float).reshape(-1, 2)
        if len(r) and not np.array_equal(r[0], r[-1]):
            r = np.vstack([r, r[:1]])
        seg.append(np.hstack([r[:-1], r[1:]]))
    if not seg:
        return inside
    seg = np.vstack(seg)
    px, py = pts[:, 0:1], pts[:, 1:2]
    for s in range(0, len(seg), chunk):
        e = seg[s:s + chunk]
        x1, y1, x2, y2 = e[:, 0], e[:, 1], e[:, 2], e[:, 3]
        straddle = (y1 > py) != (y2 > py)
        with np.errstate(divide="ignore", invalid="ignore"):
            xc = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
        inside ^= (np.count_nonzero(straddle & (px < xc), axis=1) % 2).astype(bool)
    return inside


def cdt_mesh(poly, cell: float) -> tuple[np.ndarray, np.ndarray]:
    """Constrained Delaunay of the plan split on a cell x cell grid (the grid lines are the Steiner constraints):
    each grid cell's piece of the plan is triangulated by GEOS CDT keeping every plan edge, then welded."""
    import shapely

    cell = _check_cell(cell)
    if poly is None or poly.is_empty or poly.area <= 0:
        raise ValueError("empty plan polygon")
    minx, miny, maxx, maxy = poly.bounds
    x0, y0 = math.floor(minx / cell) * cell, math.floor(miny / cell) * cell
    nx, ny = max(1, math.ceil((maxx - x0) / cell)), max(1, math.ceil((maxy - y0) / cell))
    gi, gj = np.meshgrid(np.arange(nx), np.arange(ny))
    lx, ly = x0 + gi.ravel() * cell, y0 + gj.ravel() * cell
    boxes = shapely.box(lx, ly, lx + cell, ly + cell)
    shapely.prepare(poly)
    pieces = shapely.intersection(boxes[shapely.intersects(poly, boxes)], poly)
    tris = []
    for piece in pieces:
        for part in getattr(piece, "geoms", [piece]):
            if part.geom_type != "Polygon" or part.is_empty or part.area <= 0:
                continue
            part = shapely.set_precision(part, 10.0 ** -WELD_DECIMALS)
            for t in getattr(shapely.constrained_delaunay_triangles(part), "geoms", []):
                tris.append(np.asarray(t.exterior.coords)[:3])
    if not tris:
        raise ValueError("empty plan polygon: no triangle")
    tri = np.round(np.asarray(tris, float), WELD_DECIMALS)
    verts, inv = np.unique(tri.reshape(-1, 2), axis=0, return_inverse=True)
    faces = inv.reshape(-1, 3)
    a, b, c = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    area2 = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
    faces = faces[np.abs(area2) > 1e-12]
    flip = ((verts[faces[:, 1], 0] - verts[faces[:, 0], 0]) * (verts[faces[:, 2], 1] - verts[faces[:, 0], 1])
            - (verts[faces[:, 1], 1] - verts[faces[:, 0], 1]) * (verts[faces[:, 2], 0] - verts[faces[:, 0], 0])) < 0
    faces[flip] = faces[flip][:, [0, 2, 1]]  # counter-clockwise in XY: normals up
    return verts, faces


def project_relief(xy, points) -> tuple[np.ndarray, list[int]]:
    """Relief Z below every XY on the adapter TIN (dt_ai.geometry.ground_cake, same TIN as the builder); a vertex
    outside the TIN takes the nearest relief point's Z and is listed in the returned misses (never NaN)."""
    from dt_ai.geometry import ground_cake as gc

    xy = np.asarray(xy, float).reshape(-1, 2)
    tin = gc.build_tin(list(points))
    z, hit = gc.ReliefSampler(tin).sample(xy)
    misses = [int(i) for i in np.nonzero(~hit | ~np.isfinite(z))[0]]
    for i in misses:
        z[i] = tin.pts[int(np.argmin(np.sum((tin.pts[:, :2] - xy[i]) ** 2, axis=1))), 2]
    return z, misses


def mesh_dict(verts, faces, report: dict) -> dict:
    """Mesh JSON in the layout tools/blender/ground_json_to_fbx.py builds from (one `Surface` slot, world-planar
    UV per face corner, level 0)."""
    v = np.asarray(verts, float)
    f = np.asarray(faces, np.int64)
    if not np.isfinite(v).all():
        raise ValueError("non-finite vertex")
    uv = (v[:, :2] - v[:, :2].min(axis=0)) * UV_PER_M
    return {"verts": v.round(6).tolist(), "faces": f.tolist(), "mat": [0] * len(f), "level": [0] * len(f),
            "uv": uv[f].round(7).tolist(), "slots": ["Surface"], "report": report}
