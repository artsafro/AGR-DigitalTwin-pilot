"""Two-way surface-coverage identity of two triangle meshes, fail-closed.

Pattern: n/a | new-case: NPM/VPM surface identity - two-way area coverage of triangle soups, fail-closed (#305).

Two meshes are the ``same`` surface only when BOTH directions hold: every face area of A lies strictly
closer than ``tolerance_m`` to B, every face area of B lies strictly closer than ``tolerance_m`` to A, and
the summed face areas agree. Coverage is measured as area (exact 2D polygon clipping per face with shapely),
not as a vertex cloud, so a hole, a missing face or an extra face is seen even when every vertex of one mesh
lies on the other. "Closer than" is the Euclidean 3D distance: the uncovered area is bracketed by a lower and
an upper bound (height levels of the other mesh around each face plane, inscribed / circumscribed buffers).

Verdicts:

- ``same``       - the uncovered-area UPPER bounds of both directions and the face-area difference are all
                   ``<= same_area_m2``.
- ``different``  - an uncovered-area LOWER bound or the area difference is ``>= different_area_m2`` (default
                   1 mm^2; a 1 cm hole or face is >= 40 mm^2).
- ``unverified`` - anything else (in between, or bounds inconclusive); never promoted to ``same``.
- ``error``      - unusable input: not a list, empty, malformed face record, NaN/inf, no face with area.

The comparison frame is the Flora library pivot [D100]: each mesh is translated so that the centre of its
XY bounding box and its lowest Z are at the origin. Rotation and scale are not normalised: a scaled or
rotated copy is ``different``.
"""
from __future__ import annotations

import math

import numpy as np
import shapely
from shapely.geometry import Polygon

TOLERANCE_M = 1e-4
SAME_AREA_M2 = 1e-12
DIFFERENT_AREA_M2 = 1e-6
DEGENERATE_AREA_M2 = 1e-14
VERDICTS = ("same", "different", "unverified", "error")
FRAMES = ("pivot", "world")
_STRICT = 1.0 - 1e-6  # "strictly closer than tolerance": a distance of exactly tolerance is not covered
_CHUNK = 256


class SurfaceInputError(ValueError):
    """The mesh cannot be compared (empty, malformed, NaN/inf or without any face area)."""


def compare_surfaces(
    a_faces,
    b_faces,
    tolerance_m: float = TOLERANCE_M,
    *,
    same_area_m2: float = SAME_AREA_M2,
    different_area_m2: float = DIFFERENT_AREA_M2,
    frame: str = "pivot",
) -> dict:
    """Return ``{verdict, reason, tolerance_m, frame, a, b, area_difference_m2}``; never raises on bad meshes."""
    _check_parameters(tolerance_m, same_area_m2, different_area_m2, frame)
    result = {
        "verdict": "error",
        "reason": "",
        "tolerance_m": tolerance_m,
        "frame": frame,
        "same_area_m2": same_area_m2,
        "different_area_m2": different_area_m2,
        "a": None,
        "b": None,
        "area_difference_m2": None,
    }
    try:
        a = triangles(a_faces, "a")
        b = triangles(b_faces, "b")
    except SurfaceInputError as exc:
        result["reason"] = str(exc)
        return result
    if frame == "pivot":
        a = a - pivot(a)
        b = b - pivot(b)
    a_area = face_areas(a)
    b_area = face_areas(b)
    difference = abs(float(a_area.sum()) - float(b_area.sum()))
    for levels in (COARSE_LEVELS, FINE_LEVELS):  # fine levels only when the coarse bounds are inconclusive
        a_lower, a_uncovered = uncovered_bounds(a, b, tolerance_m, levels)
        b_lower, b_uncovered = uncovered_bounds(b, a, tolerance_m, levels)
        verdict, _ = classify(
            a_uncovered, b_uncovered, difference, same_area_m2, different_area_m2, a_lower=a_lower, b_lower=b_lower
        )
        if verdict != "unverified":
            break
    result["levels"] = len(levels)
    result["a"] = _side(a, a_area, a_uncovered, a_lower)
    result["b"] = _side(b, b_area, b_uncovered, b_lower)
    result["area_difference_m2"] = difference
    verdict, reason = classify(
        a_uncovered, b_uncovered, difference, same_area_m2, different_area_m2, a_lower=a_lower, b_lower=b_lower
    )
    result["verdict"] = verdict
    result["reason"] = reason
    return result


def classify(
    a_uncovered: float,
    b_uncovered: float,
    area_difference: float,
    same_area_m2: float = SAME_AREA_M2,
    different_area_m2: float = DIFFERENT_AREA_M2,
    *,
    a_lower: float | None = None,
    b_lower: float | None = None,
) -> tuple[str, str]:
    """Tri-state decision on uncovered-area bounds; NaN or lower > upper is ``error``.

    ``a_uncovered``/``b_uncovered`` are upper bounds, ``a_lower``/``b_lower`` lower bounds (default: equal
    to the upper bound). ``different`` needs a lower bound (or the area difference) ``>= different_area_m2``;
    ``same`` needs every upper bound and the area difference ``<= same_area_m2``; else ``unverified``.
    """
    upper = {"a_uncovered": a_uncovered, "b_uncovered": b_uncovered, "area_difference": area_difference}
    lower = {
        "a_uncovered": a_uncovered if a_lower is None else a_lower,
        "b_uncovered": b_uncovered if b_lower is None else b_lower,
        "area_difference": area_difference,
    }
    for name in upper:
        for value in (upper[name], lower[name]):
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                return "error", f"{name} is not a finite non-negative number: {value!r}"
        if lower[name] > upper[name]:
            return "error", f"{name} lower bound {lower[name]!r} exceeds upper bound {upper[name]!r}"
    proven = max(lower, key=lambda name: lower[name])
    if lower[proven] >= different_area_m2:
        return "different", f"{proven} >= {lower[proven]:.6g} m2 >= {different_area_m2:g} m2"
    worst = max(upper, key=lambda name: upper[name])
    if upper[worst] <= same_area_m2:
        return "same", f"both directions covered; max deviation <= {upper[worst]:.3g} m2 <= {same_area_m2:g} m2"
    return "unverified", (
        f"{worst} in [{lower[worst]:.3g}, {upper[worst]:.3g}] m2; not proven <= {same_area_m2:g} "
        f"or >= {different_area_m2:g} m2"
    )


def triangles(faces, label: str = "mesh") -> np.ndarray:
    """Validate a face list ``[[[x, y, z] * 3], ...]`` into an ``(n, 3, 3)`` float array."""
    if isinstance(faces, np.ndarray):
        data = faces
    else:
        if not isinstance(faces, (list, tuple)):
            raise SurfaceInputError(f"{label}: faces is not a list")
        if not faces:
            raise SurfaceInputError(f"{label}: no faces")
        for index, face in enumerate(faces):
            if not isinstance(face, (list, tuple)) or len(face) != 3 or not all(
                isinstance(point, (list, tuple)) and len(point) == 3
                and all(isinstance(c, (int, float)) and not isinstance(c, bool) for c in point)
                for point in face
            ):
                raise SurfaceInputError(f"{label}: face {index} is not three [x, y, z] points")
        data = np.asarray(faces, dtype=np.float64)
    if data.ndim != 3 or data.shape[1:] != (3, 3):
        raise SurfaceInputError(f"{label}: faces shape {data.shape} is not (n, 3, 3)")
    if data.shape[0] == 0:
        raise SurfaceInputError(f"{label}: no faces")
    data = data.astype(np.float64)
    if not np.isfinite(data).all():
        raise SurfaceInputError(f"{label}: NaN or infinite coordinate")
    if not (face_areas(data) > DEGENERATE_AREA_M2).any():
        raise SurfaceInputError(f"{label}: every face is degenerate (no area)")
    return data


def pivot(tris: np.ndarray) -> np.ndarray:
    """[D100] library pivot without the 10 cm lift: centre of the XY bbox, lowest Z."""
    points = tris.reshape(-1, 3)
    low = points.min(axis=0)
    high = points.max(axis=0)
    return np.array([(low[0] + high[0]) / 2.0, (low[1] + high[1]) / 2.0, low[2]])


def face_areas(tris: np.ndarray) -> np.ndarray:
    return 0.5 * np.linalg.norm(np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]), axis=1)


def uncovered_area(a: np.ndarray, b: np.ndarray, tolerance_m: float) -> float:
    """Upper bound of the area of A's faces not strictly closer than ``tolerance_m`` to B (m^2)."""
    return uncovered_bounds(a, b, tolerance_m)[1]


def uncovered_bounds(
    a: np.ndarray, b: np.ndarray, tolerance_m: float, levels: tuple = None
) -> tuple[float, float]:
    """``(lower, upper)`` bounds of the area of A's faces not strictly closer than ``tolerance_m`` to B (m^2).

    The covered part of a face of A is the plane of that face intersected with the Euclidean
    ``tolerance_m``-neighbourhood of B. It is bracketed by height levels (see ``_LEVELS``): the part of a
    face of B within ``|h| <= t`` of the plane, projected and dilated by ``sqrt(r^2 - t^2)``, is surely
    covered (inner bound, inscribed buffer); dilated by ``sqrt(r^2 - t_prev^2)`` it surely contains the
    covered region (outer bound, circumscribed buffer). More ``levels`` (fractions of the tolerance, ending
    at 1) give tighter bounds; any level set gives valid bounds.
    """
    levels = FINE_LEVELS if levels is None else levels
    limit = tolerance_m * _STRICT
    areas = face_areas(a)
    a_low, a_high = a.min(axis=1) - limit, a.max(axis=1) + limit
    b_low, b_high = b.min(axis=1), b.max(axis=1)
    lower = upper = 0.0
    for start in range(0, len(a), _CHUNK):
        stop = min(start + _CHUNK, len(a))
        overlap = (
            (a_low[start:stop, None, :] <= b_high[None, :, :]) & (a_high[start:stop, None, :] >= b_low[None, :, :])
        ).all(axis=2)
        for offset, row in enumerate(overlap):
            index = start + offset
            if areas[index] <= DEGENERATE_AREA_M2:
                continue
            face_lower, face_upper = _uncovered_face(a[index], areas[index], b[np.flatnonzero(row)], limit, levels)
            lower += face_lower
            upper += face_upper
    return lower, upper


# Height levels t_k / r. Level 0 is (almost) in-plane so coplanar faces keep nearly the full radius.
COARSE_LEVELS = (1e-3, 0.5, 0.75, 0.9, 1.0)
FINE_LEVELS = (1e-3,) + tuple(k / 32 for k in range(1, 33))
_QUAD_SEGS = 8
_CIRCUMSCRIBE = 1.0 / math.cos(math.pi / (4 * _QUAD_SEGS))  # shapely buffer vertices lie on the arc


def _uncovered_face(
    face: np.ndarray, area: float, candidates: np.ndarray, limit: float, levels: tuple
) -> tuple[float, float]:
    origin = face[0]
    u = face[1] - origin
    u = u / np.linalg.norm(u)
    normal = np.cross(face[1] - origin, face[2] - origin)
    normal = normal / np.linalg.norm(normal)
    v = np.cross(normal, u)
    basis = np.stack([u, v])
    target = Polygon((face - origin) @ basis.T)
    if not candidates.size:
        return float(area), float(area)
    heights = (candidates - origin) @ normal
    keep = ~((heights > limit).all(axis=1) | (heights < -limit).all(axis=1))
    candidates, heights = candidates[keep], heights[keep]
    if not len(candidates):
        return float(area), float(area)
    # Keep only faces whose slab part comes within the (circumscribed) tolerance of the target in the plane.
    reach = shapely.buffer(target, limit * _CIRCUMSCRIBE, quad_segs=_QUAD_SEGS)
    shapely.prepare(reach)
    full = [_clipped_shape(other, origin, normal, basis, limit) for other in candidates]
    near = np.array([piece is not None and reach.intersects(piece) for piece in full], dtype=bool)
    if not near.any():
        return float(area), float(area)
    candidates, heights = candidates[near], heights[near]
    crosses = (heights.min(axis=1) <= 0) & (heights.max(axis=1) >= 0)
    h_low = np.where(crosses, 0.0, np.abs(heights).min(axis=1))
    h_high = np.abs(heights).max(axis=1)
    inner, outer = [], []
    previous = 0.0
    for fraction in levels:
        level = limit * fraction
        new = (h_low <= level) & (h_high > previous) if previous else (h_low <= level)
        if new.any():
            pieces = [
                piece for piece in (
                    _clipped_shape(other, origin, normal, basis, level) for other in candidates[h_low <= level]
                ) if piece is not None
            ]
            if pieces:
                union = shapely.union_all(pieces)
                inner_radius = math.sqrt(max(limit * limit - level * level, 0.0))
                outer_radius = math.sqrt(max(limit * limit - previous * previous, 0.0)) * _CIRCUMSCRIBE
                inner.append(shapely.buffer(union, inner_radius, quad_segs=_QUAD_SEGS) if inner_radius else union)
                outer.append(shapely.buffer(union, outer_radius, quad_segs=_QUAD_SEGS))
        previous = level
    if not outer:
        return float(area), float(area)
    surely_covered = shapely.intersection(shapely.union_all(inner), target).area
    maybe_covered = shapely.intersection(shapely.union_all(outer), target).area
    total = float(target.area)
    return max(total - float(maybe_covered), 0.0), max(total - float(surely_covered), 0.0)


def _clipped_shape(other: np.ndarray, origin: np.ndarray, normal: np.ndarray, basis: np.ndarray, level: float):
    """Projection onto the face plane of the part of ``other`` within ``|h| <= level``; None if empty."""
    clipped = _clip_slab(other - origin, normal, level)
    if not clipped:
        return None
    return _shape(np.asarray(clipped) @ basis.T)


def _shape(points: np.ndarray):
    if len(points) == 1:
        return shapely.Point(points[0])
    if len(points) >= 3:
        polygon = Polygon(points)
        if polygon.is_valid and polygon.area > 0:
            return polygon
        return shapely.convex_hull(shapely.MultiPoint(points))
    return shapely.LineString(points)


def _clip_slab(points: np.ndarray, normal: np.ndarray, limit: float) -> list:
    """Part of a 3D polygon within ``|distance to plane| <= limit`` (Sutherland-Hodgman, two half-spaces)."""
    polygon = [p for p in points]
    for sign in (1.0, -1.0):
        if not polygon:
            break
        distances = [sign * float(np.dot(p, normal)) - limit for p in polygon]
        clipped = []
        for i, current in enumerate(polygon):
            previous = polygon[i - 1]
            d_cur, d_prev = distances[i], distances[i - 1]
            if d_cur <= 0:
                if d_prev > 0:
                    clipped.append(previous + (current - previous) * (d_prev / (d_prev - d_cur)))
                clipped.append(current)
            elif d_prev <= 0:
                clipped.append(previous + (current - previous) * (d_prev / (d_prev - d_cur)))
        polygon = clipped
    return polygon


def _side(tris: np.ndarray, areas: np.ndarray, uncovered: float, uncovered_lower: float) -> dict:
    return {
        "faces": int(len(tris)),
        "degenerate_faces": int((areas <= DEGENERATE_AREA_M2).sum()),
        "area_m2": float(areas.sum()),
        "uncovered_m2": float(uncovered),
        "uncovered_lower_m2": float(uncovered_lower),
    }


def _check_parameters(tolerance_m, same_area_m2, different_area_m2, frame) -> None:
    for name, value in (("tolerance_m", tolerance_m), ("same_area_m2", same_area_m2),
                        ("different_area_m2", different_area_m2)):
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be a positive finite number")
    if same_area_m2 >= different_area_m2:
        raise ValueError("same_area_m2 must be below different_area_m2")
    if frame not in FRAMES:
        raise ValueError(f"frame must be one of {FRAMES}")
