"""Experiment only: proper boundary crossings of nondegenerate planar polygons.

No planarity validation, overlap/touch detection, mesh-to-mesh checks or delivery gate.
Collinear-only polygons raise ValueError; other degeneracies are unsupported.
"""
from itertools import combinations

TOLERANCE_M2 = 1e-10


def projection(points):
    """Select the largest squared-magnitude cross across ALL vertex triples."""
    best = None
    best_squared = 0.0
    for a, b, c in combinations(points, 3):
        u = tuple(b[k] - a[k] for k in range(3))
        v = tuple(c[k] - a[k] for k in range(3))
        cross = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        squared = sum(x*x for x in cross)
        if squared > best_squared:
            best, best_squared = cross, squared
    if best is None:
        raise ValueError('Unsupported collinear-only polygon')
    dropped = max(range(3), key=lambda axis: abs(best[axis]))
    axes = [axis for axis in range(3) if axis != dropped]
    return [(p[axes[0]], p[axes[1]]) for p in points]


def orientation(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])


def opposite(a, b):
    return (a > TOLERANCE_M2 and b < -TOLERANCE_M2) or (
        b > TOLERANCE_M2 and a < -TOLERANCE_M2)


def proper_crossings(vertices, face):
    points = projection([vertices[index] for index in face])
    n = len(points)
    for i in range(n):
        a, b = points[i], points[(i+1) % n]
        for j in range(i+1, n):
            if j == i+1 or (i == 0 and j == n-1):
                continue  # Adjacent boundary endpoints never count.
            c, d = points[j], points[(j+1) % n]
            if opposite(orientation(a,b,c), orientation(a,b,d)) and opposite(
                    orientation(c,d,a), orientation(c,d,b)):
                return 1  # Count polygons, not intersection pairs.
    return 0


def count(vertices, faces):
    return sum(proper_crossings(vertices, face) for face in faces)
