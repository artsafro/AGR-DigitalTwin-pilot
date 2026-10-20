"""Operation `contour_rebuild`: replace a part by a straight prism of its contour in one view [D107, D108, D131, D082].

The contour is the silhouette of the part in a view of the object system (`top` = plan, `front`, `side`; the names of
`dt_ai.ops.silhouette.VIEWS`) or a polygon the caller gives in that view (e.g. from the album). It is extruded along
the dropped axis over the measured extent of the part, or over an explicit `base_m` / `height_m`. The prism replaces the
part only through `run_operation`, so the invariants of `dt_ai.ops.invariants` are checked after it and a break rolls
back. Before that the operation refuses (a question, the scene unchanged) when the view is unknown, the part is empty,
the contour area is below 1e-4 m2, the height is not a positive finite number, the contour splits into several pieces
(unless `allow_multi=True`) or the prism changes the silhouette in any view by more than 0.07 m.

Extrusion is pure numpy + shapely (constrained Delaunay caps, two triangles per side edge, outward normals, holes
kept) behind the small `ExtrudeBackend` protocol, so a bmesh backend [D131] plugs in without changing callers.
Pattern: primitive-first | new-case: rebuild a part by the prism of its view contour (grilling Q8 "contour rebuild").
"""
from dataclasses import replace
import math
from typing import Protocol, runtime_checkable

import numpy as np
import shapely
from shapely.geometry.polygon import orient

from dt_ai.ops.invariants import Context, Mesh, Scene, border_edges
from dt_ai.ops.operations import OperationRefused, OperationResult, run_operation
from dt_ai.ops.silhouette import SILHOUETTE_MAX_M, VIEWS, silhouette, silhouette_deviations

OPERATION = "contour_rebuild"            # the Operation literal of dt_ai.parts.model
CONTOUR_MIN_AREA_M2 = 1e-4
_NOISE_AREA_M2 = 1e-8                    # pieces of a triangle union smaller than this are numerical dust
_SIMPLIFY_M = 1e-6                       # drops collinear vertices of the triangle union, far below the 0.1 mm weld


@runtime_checkable
class ExtrudeBackend(Protocol):
    """Straight extrusion of a polygon with holes along `axis` from `base_m` by `height_m`: a closed outward Mesh."""

    def __call__(self, polygon: shapely.Polygon, axis: int, base_m: float, height_m: float) -> Mesh: ...


def _frame(axis: int):
    keep = [i for i in range(3) if i != axis]
    e = np.eye(3)
    handed = float(np.linalg.det(np.stack([e[keep[0]], e[keep[1]], e[axis]])))     # +1 right-handed (u, v, w)
    return keep, handed


class NumpyExtrude:
    """The default backend: shapely constrained Delaunay for the caps, numpy for everything else."""

    def __call__(self, polygon: shapely.Polygon, axis: int, base_m: float, height_m: float) -> Mesh:
        if axis not in (0, 1, 2):
            raise ValueError(f"axis must be 0, 1 or 2, not {axis!r}")
        if not (math.isfinite(base_m) and math.isfinite(height_m) and height_m > 0):
            raise ValueError("base_m must be finite and height_m finite and positive")
        if polygon.geom_type != "Polygon" or polygon.is_empty or not polygon.is_valid or polygon.area <= 0:
            raise ValueError("the contour must be one valid polygon with a positive area")
        polygon = orient(polygon, 1.0)                                       # exterior CCW, holes CW: material left
        rings = [np.asarray(r.coords)[:-1] for r in (polygon.exterior, *polygon.interiors)]
        points = np.concatenate(rings)
        index = {tuple(p): i for i, p in enumerate(points)}
        if len(index) != len(points):
            raise ValueError("the contour repeats a vertex")
        caps = []
        for tri in shapely.get_parts(shapely.constrained_delaunay_triangles(polygon)):
            corners = np.asarray(tri.exterior.coords)[:3]
            try:
                ids = [index[tuple(c)] for c in corners]
            except KeyError:
                raise ValueError("the cap triangulation added a vertex") from None
            a, b, c = points[ids]
            if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) < 0:
                ids = ids[::-1]
            caps.append(ids)
        caps = np.asarray(caps, dtype=int).reshape(-1, 3)
        cap_area = sum(shapely.Polygon(points[t]).area for t in caps)
        if abs(cap_area - polygon.area) > 1e-9 * max(1.0, polygon.area):
            raise ValueError(f"the cap triangulation covers {cap_area} m2 of {polygon.area} m2")
        n = len(points)
        sides, start = [], 0
        for ring in rings:
            k = np.arange(len(ring)) + start
            a, b = k, np.roll(k, -1)                                         # edge a -> b, material on the left
            sides += np.stack([a, b, b + n], axis=1).tolist() + np.stack([a, b + n, a + n], axis=1).tolist()
            start += len(ring)
        tris = np.concatenate([caps[:, ::-1], caps + n, np.asarray(sides, dtype=int)])  # bottom faces -w, top +w
        keep, handed = _frame(axis)
        if handed < 0:
            tris = tris[:, ::-1]
        vertices = np.zeros((2 * n, 3))
        vertices[:, keep[0]] = np.tile(points[:, 0], 2)
        vertices[:, keep[1]] = np.tile(points[:, 1], 2)
        vertices[:n, axis] = base_m
        vertices[n:, axis] = base_m + height_m
        return Mesh(vertices, tris)


def extrude_polygon(polygon, axis: int, base_m: float, height_m: float, backend: ExtrudeBackend | None = None) -> Mesh:
    """Prism of `polygon` (view coordinates: the two kept axes in order) along `axis`; raises ValueError on bad input."""
    return (backend or NumpyExtrude())(polygon, axis, float(base_m), float(height_m))


def _polygons(geom):
    """Polygons of a (multi)geometry, dropping lines, points and numerical dust."""
    out = []
    for g in shapely.get_parts(geom):
        if g.geom_type == "Polygon" and g.area > _NOISE_AREA_M2:
            out.append(g)
        elif g.geom_type in {"MultiPolygon", "GeometryCollection"}:
            out += _polygons(g)
    return out


def _contour(mesh: Mesh, axis: int, contour):
    if contour is None:
        geom = shapely.simplify(silhouette(mesh, axis), _SIMPLIFY_M, preserve_topology=True)
    elif isinstance(contour, shapely.Geometry):
        geom = contour
    else:
        pts = np.asarray(contour, dtype=float)
        if pts.ndim != 2 or pts.shape[1] != 2 or len(pts) < 3:
            raise OperationRefused("the contour must be at least three (u, v) points in the view; which contour?")
        if not np.isfinite(pts).all():
            raise OperationRefused("the contour has a non-finite coordinate; which contour?")
        geom = shapely.Polygon(pts)
    if not np.isfinite(shapely.get_coordinates(geom)).all():
        raise OperationRefused("the contour has a non-finite coordinate; which contour?")
    if not geom.is_valid:
        geom = shapely.make_valid(geom)
    return _polygons(geom)


def _rebuild(scene: Scene, part: str, view: str, height_m, base_m, contour, allow_multi: bool,
             backend: ExtrudeBackend, silhouette_max_m: float, notes: dict) -> Scene:
    if view not in VIEWS:
        raise OperationRefused(f"unknown view {view!r}; which of {', '.join(VIEWS)}?")
    axis = VIEWS[view]
    mesh = scene[part]
    if not len(mesh.triangles):
        raise OperationRefused("the part has no faces; which source geometry should be rebuilt by contour?")
    span = mesh.vertices[mesh.triangles.ravel(), axis]
    base = float(span.min()) if base_m is None else base_m
    height = float(span.max() - span.min()) if height_m is None else height_m
    for name, value in (("base_m", base), ("height_m", height)):
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            raise OperationRefused(f"{name} {value!r} is not a finite number; which {name} should the prism use?")
    base, height = float(base), float(height)
    if height <= 0:
        why = "the part has no extent along the dropped axis" if height_m is None else f"height_m {height} is not positive"
        raise OperationRefused(f"{why}; which height_m (> 0) should the {view} contour be extruded by?")
    pieces = _contour(mesh, axis, contour)
    area = float(sum(p.area for p in pieces))
    notes.update(view=view, base_m=base, height_m=height, contour_area_m2=area, pieces=len(pieces))
    if area < CONTOUR_MIN_AREA_M2 - 1e-12:
        raise OperationRefused(f"the {view} contour area is {area:.2e} m2 (below {CONTOUR_MIN_AREA_M2:.0e} m2): the part "
                               "is edge-on or degenerate in this view; which other view should be used?")
    if len(pieces) > 1 and not allow_multi:
        raise OperationRefused(f"the {view} contour splits into {len(pieces)} pieces; rebuild each piece as its own part "
                               "or pass allow_multi=True?")
    meshes = []
    for p in pieces:
        try:
            meshes.append(extrude_polygon(p, axis, base, height, backend))
        except ValueError as why:
            raise OperationRefused(f"the {view} contour cannot be extruded ({why}); which contour?") from None
    offsets = np.cumsum([0] + [len(m.vertices) for m in meshes[:-1]])
    prism = Mesh(np.concatenate([m.vertices for m in meshes]),
                 np.concatenate([m.triangles + o for m, o in zip(meshes, offsets)]))
    open_edges = len(border_edges(prism))
    if open_edges:
        raise OperationRefused(f"the prism has {open_edges} open edges after the 0.1 mm weld (contour vertices too "
                               "close); which simplified contour should be used?")
    deviations = silhouette_deviations(mesh, prism, silhouette_max_m / 4)
    notes["deviations_m"] = deviations
    worst = max(deviations.items(), key=lambda kv: kv[1])
    if worst[1] > silhouette_max_m + 1e-9:
        raise OperationRefused(f"the prism would change the silhouette by {worst[1] * 1000:.0f} mm in the {worst[0]} view "
                               f"(limit {silhouette_max_m * 1000:.0f} mm); which view or contour should be used instead?")
    return {**scene, part: prism}


def rebuild_by_contour(scene: Scene, part: str, view: str = "top", height_m: float | None = None,
                       base_m: float | None = None, contour=None, allow_multi: bool = False,
                       ctx: Context = Context(), backend: ExtrudeBackend | None = None,
                       silhouette_max_m: float = SILHOUETTE_MAX_M) -> OperationResult:
    """Replace `part` by the prism of its `view` contour, through `run_operation("contour_rebuild")`.

    `contour`: optional polygon in the view coordinates (shapely geometry or (u, v) points) instead of the silhouette.
    The notes carry faces before / after, view, base, height, contour area, pieces and per-view deviations (m);
    a refusal or rollback returns the incoming scene object with the question.
    """
    notes: dict = {}
    params = {"view": view, "height_m": height_m, "base_m": base_m, "allow_multi": allow_multi,
              "contour": None if contour is None else "caller"}
    result = run_operation(scene, OPERATION, part,
                           lambda s: _rebuild(s, part, view, height_m, base_m, contour, allow_multi,
                                              backend or NumpyExtrude(), silhouette_max_m, notes),
                           ctx, params)
    return replace(result, notes={**(result.notes or {}), **notes})
