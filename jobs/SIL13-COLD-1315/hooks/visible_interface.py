"""new-case: #1315 authorized VPM hidden-interface cut on one copied pilot.

Placement after-hook, D342: keep the buried master/census; this derived mesh
retains exactly the visible subset of each source triangle. No offsets, caps,
Ground edits, species/instance substitutions or implicit missing-coverage drops.
Barycentric partitioning also handles vertical walls (singular XY projection).
"""
import numpy as np
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

DOMAIN = Polygon([(0., 0.), (1., 0.), (0., 1.)])


def halfspace(poly, values):
    """Clip barycentric polygon by a linear scalar >=0 at source corners."""
    if poly.is_empty:
        return poly
    ring = list(poly.exterior.coords)[:-1]
    out = []
    def val(p):
        return values[0] + p[0]*(values[1]-values[0]) + p[1]*(values[2]-values[0])
    for p, q in zip(ring, ring[1:]+ring[:1]):
        a, b = val(p), val(q)
        if a >= 0:
            out.append(p)
        if (a >= 0) != (b >= 0):
            u = a/(a-b)
            out.append((p[0]+u*(q[0]-p[0]), p[1]+u*(q[1]-p[1])))
    return Polygon(out) if len(out) >= 3 else Polygon()


class GroundPartition:
    def __init__(self, ground):
        g = np.asarray(ground, dtype=float)
        if g.ndim != 3 or g.shape[1:] != (3, 3) or not len(g) or not np.isfinite(g).all():
            raise ValueError('empty, unsupported or nonfinite Ground')
        nz = np.cross(g[:, 1]-g[:, 0], g[:, 2]-g[:, 0])[:, 2]
        if not np.isfinite(nz).all() or (nz <= 1e-12).any():
            raise ValueError('Ground must contain upward nonsingular surface triangles only')
        self.g = g
        self.polys = [Polygon(t[:, :2]) for t in g]
        self.tree = STRtree(self.polys)
        self.coeff = np.array([np.linalg.solve(np.column_stack([t[:, :2], np.ones(3)]), t[:, 2]) for t in g])

    def pieces(self, triangle):
        t = np.asarray(triangle, dtype=float)
        if t.shape != (3, 3) or not np.isfinite(t).all():
            raise ValueError('unsupported or nonfinite source triangle')
        area2 = np.linalg.norm(np.cross(t[1]-t[0], t[2]-t[0]))
        if not np.isfinite(area2) or area2 <= 1e-14:
            raise ValueError('degenerate source triangle')
        footprint = Polygon(t[:, :2]).convex_hull
        visible, coverage = DOMAIN, []
        ground_ids = []
        for gi in sorted(map(int, self.tree.query(footprint))):
            ground = self.g[gi]
            patch = DOMAIN
            for a, b in zip(ground, np.roll(ground, -1, axis=0)):
                e = b[:2]-a[:2]
                xy = t[:, :2]-a[:2]
                patch = halfspace(patch, e[0]*xy[:, 1]-e[1]*xy[:, 0])
                if patch.is_empty:
                    break
            if patch.is_empty or patch.area == 0:
                continue
            coverage.append(patch)
            ground_ids.append(gi)
            signed = t[:, 2]-np.column_stack([t[:, :2], np.ones(3)])@self.coeff[gi]
            if signed.min() >= -1e-12:
                continue
            hidden = halfspace(patch, -signed)
            visible = visible.difference(hidden)
        uncovered = DOMAIN.difference(unary_union(coverage))
        if uncovered.area > 1e-10:
            raise ValueError(f'Ground coverage incomplete: barycentric area {uncovered.area}')
        result, degenerate, slivers = [], 0, []
        if not visible.is_empty:
            for p in constrained_delaunay_triangles(visible).geoms:
                co = np.asarray(p.exterior.coords)[:3]
                b = np.column_stack([1-co.sum(axis=1), co])
                determinant = np.linalg.det(np.column_stack([co, np.ones(3)]))
                points = b @ t
                lengths = np.linalg.norm(points-np.roll(points, -1, axis=0), axis=1)
                altitude = np.linalg.norm(np.cross(points[1]-points[0], points[2]-points[0])) / max(float(lengths.max()), 1e-300)
                if determinant == 0 or np.linalg.det(b) == 0 or altitude <= 1e-10:
                    degenerate += 1  # <=0.1nm numerical line, not a visible shape repair.
                    slivers.append({'barycentric': b.tolist(), 'altitude_m': float(altitude),
                                    'barycentric_area': float(abs(determinant)/2)})
                    continue
                if determinant < 0:
                    b = b[[0, 2, 1]]
                result.append(b)
        return result, {'zero_area_triangles_excluded': degenerate, 'numerical_slivers': slivers,
                        'removed_fraction': float(1-visible.area/DOMAIN.area),
                        'uncovered_fraction': float(uncovered.area/DOMAIN.area),
                        'ground_indices': ground_ids, 'output_triangles': len(result)}


def visible_pieces(triangle, ground):
    return GroundPartition(ground).pieces(triangle)
