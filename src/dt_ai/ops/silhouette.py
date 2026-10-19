"""Silhouette test of the pattern `primitive-first`: how far a simpler form strays from a part, in the plan views [D082].

A part may be replaced by its primitive only if the silhouette changes by at most 0.07 m in the views of the
object system: the top (drop z) and the two facade views (drop y, drop x); the opposite facade of an orthographic
view has the same silhouette, so the four facades and the top are three distinct views. The deviation of two
silhouettes is the largest distance from a point of one that the other does not cover to the other (the Hausdorff
distance of the regions), sampled on a grid of `step_m`; it is accurate to about one step.
Pure numpy + shapely.
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
    tri = tri[np.abs(area2) > 1e-12]                                      # edge-on triangles project to a line
    if not len(tri):
        return shapely.Polygon()
    rings = np.concatenate([tri, tri[:, :1]], axis=1)
    return shapely.union_all(shapely.make_valid(shapely.polygons(rings)))


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
        # a sliver thinner than one step: its far corner is the farthest point
        return float(shapely.hausdorff_distance(left, other))
    pts = shapely.points(xs[inside], ys[inside])
    return float(shapely.distance(other, pts).max())


def silhouette_deviation(a: Mesh, b: Mesh, axis: int, step_m: float = SILHOUETTE_MAX_M / 4) -> float:
    """Deviation in metres between the silhouettes of two meshes along `axis`."""
    sa, sb = silhouette(a, axis), silhouette(b, axis)
    if sa.is_empty or sb.is_empty:
        return 0.0 if sa.is_empty and sb.is_empty else float("inf")
    return max(_uncovered_reach(sa, sb, step_m), _uncovered_reach(sb, sa, step_m))


def silhouette_deviations(a: Mesh, b: Mesh, step_m: float = SILHOUETTE_MAX_M / 4) -> dict:
    """{view: deviation in metres} for the top, front and side views."""
    return {name: silhouette_deviation(a, b, axis, step_m) for name, axis in VIEWS.items()}
