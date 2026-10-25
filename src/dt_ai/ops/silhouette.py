"""Silhouette test of the pattern `primitive-first`: how far a simpler form strays from a part, in the plan views [D082].

A part may be replaced by its primitive only if the silhouette changes by at most 0.07 m in the views of the
object system: the top (drop z) and the two facade views (drop y, drop x); the opposite facade of an orthographic
view has the same silhouette, so the four facades and the top are three distinct views. The deviation of two
silhouettes is the largest distance from a point of one that the other does not cover to the other (the Hausdorff
distance of the regions), sampled on a grid of `step_m`; it is accurate to about one step.
Pure numpy + shapely. Edge-on projections remain line/point geometries, including beside polygon projections.
Pure edge-on comparisons use Hausdorff distance directly; mixed comparisons retain directed
line/point reach alongside the unchanged polygon grid (#292, #353). A difference the grid misses uses the
directed distance from that sliver to the other region. A polygon with holes also contributes an interior point:
both rings can lie on the other region while the material between them does not.
"""
import numpy as np
import shapely

from dt_ai.ops.invariants import Mesh

VIEWS = {"top": 2, "front": 1, "side": 0}     # view name -> dropped axis
SILHOUETTE_MAX_M = 0.07
MAX_SAMPLES = 400_000


def silhouette(mesh: Mesh, axis: int):
    """Union of the triangles of `mesh` projected along `axis` (a shapely geometry; empty for an empty mesh)."""
    keep = [i for i in range(3) if i != axis]
    tri = mesh.vertices[mesh.triangles][:, :, keep]                       # (T, 3, 2)
    if not len(tri):
        return shapely.Polygon()
    e1, e2 = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    area2 = e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]                     # twice the signed area (no 2-D np.cross)
    polygon_mask = np.abs(area2) > 1e-12
    polygons = tri[polygon_mask]
    if not len(polygons):
        # Preserve edge-on triangles as line segments (or points), not empty polygons.
        return shapely.union_all([shapely.MultiPoint(t).convex_hull for t in tri])
    rings = np.concatenate([polygons, polygons[:, :1]], axis=1)
    projected = list(shapely.make_valid(shapely.polygons(rings)))
    projected.extend(shapely.MultiPoint(t).convex_hull for t in tri[~polygon_mask])
    return shapely.union_all(projected)


def _pieces(geom):
    """Polygons, lines and points inside a (multi)geometry, skipping empties."""
    if geom.is_empty:
        return
    kind = geom.geom_type
    if kind == "GeometryCollection" or kind.startswith("Multi"):
        for part in geom.geoms:
            yield from _pieces(part)
        return
    yield geom


def _max_distance(other, points) -> float:
    """Directed distance from `points` to `other`; non-finite results refuse as infinite."""
    dist = np.asarray(shapely.distance(other, points), dtype=float)
    if dist.size == 0:
        return 0.0
    reached = float(np.max(dist))
    return reached if np.isfinite(reached) else float("inf")


def _directed_reach(region, other, step_m: float) -> float:
    """Largest distance from a point of `region` to `other`.

    Symmetric Hausdorff is not used: its reverse leg measures far points of `other` against a sliver.
    Boundary vertices alone are not used for a polygon with holes — the rings can lie on `other` while an
    interior point of the material does not. The inscribed-circle centre is that interior point.
    """
    best = 0.0
    for geom in _pieces(region):
        outline = geom
        if step_m > 0 and geom.geom_type in {"LineString", "LinearRing", "Polygon"} and geom.length > 0:
            outline = shapely.segmentize(geom, step_m)
        coords = shapely.get_coordinates(outline)
        if len(coords):
            best = max(best, _max_distance(other, shapely.points(coords[:, 0], coords[:, 1])))
        if geom.geom_type != "Polygon" or geom.area <= 0:
            continue
        best = max(best, _max_distance(other, geom.representative_point()))
        if len(geom.interiors):
            centre = shapely.get_point(shapely.maximum_inscribed_circle(geom, tolerance=1e-9), 0)
            best = max(best, _max_distance(other, centre))
    return best


def _uncovered_reach(region, other, step_m: float) -> float:
    """Largest distance from a point of `region` that `other` does not cover to `other`."""
    left = region.difference(other)
    if left.is_empty:
        return 0.0
    x0, y0, x1, y1 = left.bounds
    step = max(step_m, float(np.sqrt(max((x1 - x0) * (y1 - y0), 1e-12) / MAX_SAMPLES)))
    xs, ys = np.meshgrid(np.arange(x0, x1 + step, step), np.arange(y0, y1 + step, step))
    xs, ys = xs.ravel(), ys.ravel()
    inside = shapely.contains_xy(left, xs, ys)
    if not inside.any():
        # thinner than one step: directed distance from the sliver, not symmetric Hausdorff
        return _directed_reach(left, other, step)
    pts = shapely.points(xs[inside], ys[inside])
    reached = float(shapely.distance(other, pts).max())
    # contains_xy samples only area. A mixed uncovered region can also contain a
    # separate line/point, which must not disappear because a polygon had samples.
    edge_reach = max((_directed_reach(g, other, step) for g in _pieces(left)
                      if g.geom_type != "Polygon"), default=0.0)
    reached = max(reached, edge_reach)
    return reached if np.isfinite(reached) else float("inf")


def silhouette_deviation(a: Mesh, b: Mesh, axis: int, step_m: float = SILHOUETTE_MAX_M / 4) -> float:
    """Deviation in metres between the silhouettes of two meshes along `axis`."""
    sa, sb = silhouette(a, axis), silhouette(b, axis)
    if sa.is_empty or sb.is_empty:
        return 0.0 if sa.is_empty and sb.is_empty else float("inf")
    if sa.area == 0 or sb.area == 0:
        return float(shapely.hausdorff_distance(sa, sb))
    return max(_uncovered_reach(sa, sb, step_m), _uncovered_reach(sb, sa, step_m))


def silhouette_deviations(a: Mesh, b: Mesh, step_m: float = SILHOUETTE_MAX_M / 4) -> dict:
    """{view: deviation in metres} for the top, front and side views."""
    return {name: silhouette_deviation(a, b, axis, step_m) for name, axis in VIEWS.items()}
