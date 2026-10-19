"""Two-way surface-coverage identity of two triangle meshes, fail-closed.

Pattern: n/a | new-case: NPM/VPM surface identity - two-way area coverage of triangle soups, fail-closed (#305).

Two meshes are the ``same`` surface only when BOTH directions hold: every face area of A lies strictly
closer than ``tolerance_m`` to B, every face area of B lies strictly closer than ``tolerance_m`` to A, and
the summed face areas agree. Coverage is measured as area (exact 2D polygon clipping per face with shapely),
not as a vertex cloud, so a hole, a missing face or an extra face is seen even when every vertex of one mesh
lies on the other.

Verdicts:

- ``same``       - uncovered area in both directions and the face-area difference are all ``<= same_area_m2``.
- ``different``  - any of them is ``>= different_area_m2`` (default 1 mm^2; a 1 cm hole or face is >= 40 mm^2).
- ``unverified`` - anything in between; never promoted to ``same``.
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
    a_uncovered = uncovered_area(a, b, tolerance_m)
    b_uncovered = uncovered_area(b, a, tolerance_m)
    difference = abs(float(a_area.sum()) - float(b_area.sum()))
    result["a"] = _side(a, a_area, a_uncovered)
    result["b"] = _side(b, b_area, b_uncovered)
    result["area_difference_m2"] = difference
    verdict, reason = classify(a_uncovered, b_uncovered, difference, same_area_m2, different_area_m2)
    result["verdict"] = verdict
    result["reason"] = reason
    return result


def classify(
    a_uncovered: float,
    b_uncovered: float,
    area_difference: float,
    same_area_m2: float = SAME_AREA_M2,
    different_area_m2: float = DIFFERENT_AREA_M2,
) -> tuple[str, str]:
    """Tri-state decision; a value exactly at ``different_area_m2`` is ``different``, NaN is ``error``."""
    values = {"a_uncovered": a_uncovered, "b_uncovered": b_uncovered, "area_difference": area_difference}
    for name, value in values.items():
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            return "error", f"{name} is not a finite non-negative number: {value!r}"
    worst = max(values, key=lambda name: values[name])
    if values[worst] >= different_area_m2:
        return "different", f"{worst} {values[worst]:.6g} m2 >= {different_area_m2:g} m2"
    if values[worst] <= same_area_m2:
        return "same", f"both directions covered; max deviation {values[worst]:.3g} m2 <= {same_area_m2:g} m2"
    return "unverified", (
        f"{worst} {values[worst]:.3g} m2 is between {same_area_m2:g} and {different_area_m2:g} m2"
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
    """Area of A's faces not strictly closer than ``tolerance_m`` to any face of B (m^2)."""
    limit = tolerance_m * _STRICT
    areas = face_areas(a)
    a_low, a_high = a.min(axis=1) - limit, a.max(axis=1) + limit
    b_low, b_high = b.min(axis=1), b.max(axis=1)
    total = 0.0
    for start in range(0, len(a), _CHUNK):
        stop = min(start + _CHUNK, len(a))
        overlap = (
            (a_low[start:stop, None, :] <= b_high[None, :, :]) & (a_high[start:stop, None, :] >= b_low[None, :, :])
        ).all(axis=2)
        for offset, row in enumerate(overlap):
            index = start + offset
            if areas[index] <= DEGENERATE_AREA_M2:
                continue
            total += _uncovered_face(a[index], areas[index], b[np.flatnonzero(row)], limit)
    return total


def _uncovered_face(face: np.ndarray, area: float, candidates: np.ndarray, limit: float) -> float:
    origin = face[0]
    u = face[1] - origin
    u = u / np.linalg.norm(u)
    normal = np.cross(face[1] - origin, face[2] - origin)
    normal = normal / np.linalg.norm(normal)
    v = np.cross(normal, u)
    basis = np.stack([u, v])
    target = Polygon((face - origin) @ basis.T)
    if not candidates.size:
        return float(area)
    heights = (candidates - origin) @ normal
    candidates = candidates[~((heights > limit).all(axis=1) | (heights < -limit).all(axis=1))]
    pieces = []
    for other in candidates:
        clipped = _clip_slab(other - origin, normal, limit)
        if len(clipped) >= 2:
            flat = np.asarray(clipped) @ basis.T
            pieces.append(_shape(flat))
    if not pieces:
        return float(area)
    covered = shapely.intersection(shapely.buffer(shapely.union_all(pieces), limit), target).area
    return max(float(target.area) - float(covered), 0.0)


def _shape(points: np.ndarray):
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


def _side(tris: np.ndarray, areas: np.ndarray, uncovered: float) -> dict:
    return {
        "faces": int(len(tris)),
        "degenerate_faces": int((areas <= DEGENERATE_AREA_M2).sum()),
        "area_m2": float(areas.sum()),
        "uncovered_m2": float(uncovered),
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
