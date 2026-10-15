# Ported from AGR adapters/sketchup/check_model_clearance.py (sha256 ba09d4967981)
# on 2026-10-06; changes: importable function + CLI wrapper, tolerance from the profile
# (geometry.near_coplanar_spacing_m.min), AGR window/ac/sill categories dropped.
"""Near-parallel face overlap check (reg p.8, 29: 5 mm-2 cm spacing; docs/domain/validation.md).

Finds pairs of almost parallel faces (|cos| > 0.999999), in either orientation, whose planes
are closer than the tolerance and whose projections overlap by more than 1e-7 m2. It is an
independent area test, not a pass of any third-party checker; hits still need classifying
(deliberate embeds vs defects, docs/domain/validation.md "General QA procedure").

new-case: co-directional overlap clearance band 5 mm-2 cm on FBX readback (BODY-K, #161).
"""
from collections import defaultdict

import numpy as np
import shapely
from shapely.geometry import Polygon

PARALLEL_COS_MIN = 0.999999
AREA_MIN_M2 = 1e-7
# Band-edge tolerance: FBX stores float32 coordinates (~1e-5 m at 100 m from the origin), so a pair
# modelled at exactly 20 mm reads back as 20.001 mm. Same value as the CheckToolBox intersection epsilon.
BAND_EDGE_TOL_M = 1e-5


def _normal(points: np.ndarray) -> np.ndarray:
    # Whole-polygon area vector: robust to collinear leading vertices on welded borders.
    q = points - points.mean(0)
    n = np.cross(q, np.roll(q, -1, axis=0)).sum(0)
    length = np.linalg.norm(n)
    return n / length if length > 1e-12 else np.zeros(3)


def near_parallel_overlaps(faces: list[dict], tolerance_m: float) -> list[dict]:
    """faces: [{object, index, points: [[x,y,z], ...]}] -> overlapping pairs closer than tolerance."""
    pts = [np.asarray(f["points"], dtype=float) for f in faces]
    if not pts:
        return []
    normals = np.array([_normal(p) for p in pts])
    centers = np.array([p.mean(0) for p in pts])
    lows, highs = np.array([p.min(0) for p in pts]), np.array([p.max(0) for p in pts])
    pairs = []
    for i, face in enumerate(faces):
        n = normals[i]
        if np.linalg.norm(n) < 0.9:
            continue
        dot = normals @ n
        cand = np.where((np.abs(dot) > PARALLEL_COS_MIN) & (np.abs((centers - pts[i][0]) @ n) < tolerance_m + 1e-5))[0]
        axes = [k for k in range(3) if k != int(np.argmax(np.abs(n)))]  # project on the dominant plane
        cand = cand[np.all(np.minimum(highs[cand][:, axes], highs[i, axes]) > np.maximum(lows[cand][:, axes], lows[i, axes]), axis=1)]
        a = Polygon(pts[i][:, axes])
        for j in cand:
            if j <= i:
                continue
            area = a.intersection(Polygon(pts[j][:, axes])).area
            if area < AREA_MIN_M2:
                continue
            dist = abs(float((centers[j] - pts[i][0]) @ n))
            if dist >= tolerance_m - 1e-7:
                continue
            pairs.append({"a": [face["object"], face["index"]], "b": [faces[j]["object"], faces[j]["index"]],
                          "distance_m": dist, "same_direction": bool(dot[j] > 0), "projected_area_m2": float(area)})
    return pairs


def summary(pairs: list[dict], tolerance_m: float, face_count: int) -> dict:
    objects = {}
    for p in pairs:
        key = " / ".join(sorted({p["a"][0], p["b"][0]}))
        objects[key] = objects.get(key, 0) + 1
    return {"tool": "near-parallel area-overlap test", "tolerance_m": tolerance_m,
            "parallel_cosine_min": PARALLEL_COS_MIN, "area_threshold_m2": AREA_MIN_M2, "face_count": face_count,
            "pair_count": len(pairs), "by_objects": objects,
            "same_direction": sum(p["same_direction"] for p in pairs),
            "opposite_direction": sum(not p["same_direction"] for p in pairs)}


# Quantised normal cells. Co-directional faces (dot > PARALLEL_COS_MIN) land in the same cell or one of
# the 26 neighbours: a 2-cell gap is already a larger angle than the parallel test allows.
_NORMAL_CELL = 2e-3
_HISTOGRAM_MM = (
    ("0-1", 0.0, 1.0, True, False),
    ("1-5", 1.0, 5.0, True, False),
    ("5-10", 5.0, 10.0, True, False),
    ("10-20", 10.0, 20.0, True, True),
    ("20-50", 20.0, 50.0, False, True),
    ("50-100", 50.0, 100.0, False, True),
    ("100-1000", 100.0, 1000.0, False, True),
    ("1000+", 1000.0, np.inf, False, False),
)


def _plane_basis(normal: np.ndarray) -> np.ndarray:
    """Orthonormal 3x2 basis of the plane perpendicular to a unit normal."""
    axis = int(np.argmin(np.abs(normal)))
    tangent = np.cross(normal, np.eye(3)[axis])
    tangent /= np.linalg.norm(tangent)
    bitangent = np.cross(normal, tangent)
    return np.column_stack((tangent, bitangent))


def _normal_cell(normal: np.ndarray) -> tuple[int, int, int]:
    quantized = np.round(normal / _NORMAL_CELL).astype(np.int64)
    return int(quantized[0]), int(quantized[1]), int(quantized[2])


def _pair_record(prepared, i: int, j: int, distance_m: float, area: float) -> dict:
    face_i, face_j = prepared[i][0], prepared[j][0]
    return {"a": [face_i["object"], int(face_i["index"])], "b": [face_j["object"], int(face_j["index"])],
            "distance_m": float(distance_m), "projected_area_m2": float(area)}


def _evaluate_pair(prepared, i: int, j: int, window_m: float | None = None) -> dict | None:
    """Exact co-directional test: face i's normal and an orthonormal basis of its plane.

    `window_m=None` applies no distance cutoff. Scalar definition the vectorised path must match.
    """
    _, _, normal_i, centroid_i = prepared[i]
    _, points_j, normal_j, centroid_j = prepared[j]
    if float(np.dot(normal_i, normal_j)) <= PARALLEL_COS_MIN:
        return None
    distance = abs(float(np.dot(normal_i, centroid_j - centroid_i)))
    if window_m is not None and distance > window_m + 1e-9:
        return None
    basis = _plane_basis(normal_i)
    area = float(Polygon(prepared[i][1] @ basis).intersection(Polygon(points_j @ basis)).area)
    if area < AREA_MIN_M2:
        return None
    return _pair_record(prepared, i, j, distance, area)


def _plane_bases(normals: np.ndarray) -> np.ndarray:
    """Vectorised `_plane_basis`: one 3x2 orthonormal frame per unit normal."""
    axis = np.argmin(np.abs(normals), axis=1)
    tangent = np.cross(normals, np.eye(3)[axis])
    tangent /= np.linalg.norm(tangent, axis=1)[:, None]
    bitangent = np.cross(normals, tangent)
    return np.stack((tangent, bitangent), axis=-1)


# Bounds memory for one cell-pair's candidate arrays (stacked layers can pair every column).
_CANDIDATE_CHUNK = 200_000


def _pack_faces(prepared):
    """Points grouped by vertex count so candidate projections index a dense array."""
    widths = np.array([item[1].shape[0] for item in prepared], dtype=np.int64)
    packed: dict[int, np.ndarray] = {}
    slot = np.empty(len(prepared), dtype=np.int64)
    for width in np.unique(widths):
        chosen = np.flatnonzero(widths == width)
        slot[chosen] = np.arange(len(chosen))
        packed[int(width)] = np.stack([prepared[int(i)][1] for i in chosen])
    return widths, packed, slot


def _expanded_boxes(packed, slot, widths, centroids, indices, basis, direction, height0):
    """Cell-plane AABBs expanded by the conservative projection slack of each face."""
    indices = np.asarray(indices, dtype=np.int64)
    bounds = np.empty((len(indices), 4), dtype=float)
    for width in np.unique(widths[indices]):
        chosen = np.flatnonzero(widths[indices] == width)
        points = packed[int(width)][slot[indices[chosen]]]
        centers = centroids[indices[chosen]]
        projected = points @ basis
        low, high = projected.min(axis=1), projected.max(axis=1)
        diameter = np.linalg.norm(points - centers[:, None, :], axis=2).max(axis=1) * 2.0
        along = np.abs(points @ direction - height0).max(axis=1)
        slack = (0.01 * (along + diameter) + 1e-6)[:, None]
        bounds[chosen, 0:2] = low - slack
        bounds[chosen, 2:4] = high + slack
    return shapely.box(bounds[:, 0], bounds[:, 1], bounds[:, 2], bounds[:, 3])


def _areas_uniform(points, slot, bases, gi, gj) -> np.ndarray:
    """Exact overlap area on face i's plane. Empty exact AABBs are area 0 (conservative)."""
    projected_i = np.einsum("kvc,kcd->kvd", points[slot[gi]], bases[gi])
    projected_j = np.einsum("kvc,kcd->kvd", points[slot[gj]], bases[gi])
    areas = np.zeros(len(gi), dtype=float)
    low_i, high_i = projected_i.min(axis=1), projected_i.max(axis=1)
    low_j, high_j = projected_j.min(axis=1), projected_j.max(axis=1)
    overlap_w = np.minimum(high_i[:, 0], high_j[:, 0]) - np.maximum(low_i[:, 0], low_j[:, 0])
    overlap_h = np.minimum(high_i[:, 1], high_j[:, 1]) - np.maximum(low_i[:, 1], low_j[:, 1])
    hit = (overlap_w > 0.0) & (overlap_h > 0.0)
    if not np.any(hit):
        return areas
    polygons_i = shapely.polygons(np.ascontiguousarray(projected_i[hit]))
    polygons_j = shapely.polygons(np.ascontiguousarray(projected_j[hit]))
    areas[hit] = np.asarray(shapely.area(shapely.intersection(polygons_i, polygons_j)), dtype=float).reshape(-1)
    return areas


def _areas_fallback(prepared, gi, gj) -> np.ndarray:
    """Scalar exact area, used when a candidate chunk mixes vertex counts."""
    areas = np.empty(len(gi), dtype=float)
    for row, i, j in zip(range(len(gi)), gi.tolist(), gj.tolist()):
        basis = _plane_basis(prepared[i][2])
        areas[row] = float(Polygon(prepared[i][1] @ basis).intersection(Polygon(prepared[j][1] @ basis)).area)
    return areas


def _areas_of_candidates(prepared, packed, slot, widths, bases, gi, gj) -> np.ndarray:
    left = widths[gi]
    right = widths[gj]
    if gi.size and np.all(left == left[0]) and np.all(right == left[0]):
        return _areas_uniform(packed[int(left[0])], slot, bases, gi, gj)
    areas = np.zeros(len(gi), dtype=float)
    matched = left == right
    for width in np.unique(left[matched]):
        chosen = np.flatnonzero(matched & (left == width))
        areas[chosen] = _areas_uniform(packed[int(width)], slot, bases, gi[chosen], gj[chosen])
    ragged = np.flatnonzero(~matched)
    if ragged.size:
        areas[ragged] = _areas_fallback(prepared, gi[ragged], gj[ragged])
    return areas


def _record_candidates(prepared, packed, slot, widths, bases, normals, centroids, gi, gj,
                       window_m: float | None, found: dict) -> None:
    """Parallel test, optional distance window, then the exact area test in chunks."""
    if len(gi) == 0:
        return
    dots = np.einsum("ij,ij->i", normals[gi], normals[gj])
    distances = np.abs(np.einsum("ij,ij->i", normals[gi], centroids[gj] - centroids[gi]))
    keep = dots > PARALLEL_COS_MIN
    if window_m is not None:
        keep &= distances <= window_m + 1e-9
    if not np.any(keep):
        return
    gi, gj, distances = gi[keep], gj[keep], distances[keep]
    for start in range(0, len(gi), _CANDIDATE_CHUNK):
        stop = start + _CANDIDATE_CHUNK
        gii, gjj = gi[start:stop], gj[start:stop]
        dist = distances[start:stop]
        areas = _areas_of_candidates(prepared, packed, slot, widths, bases, gii, gjj)
        # Same rejection as `_evaluate_pair`: area < AREA_MIN_M2 drops the pair.
        accept = areas >= AREA_MIN_M2
        for i, j, distance, area in zip(gii[accept].tolist(), gjj[accept].tolist(),
                                        dist[accept].tolist(), areas[accept].tolist()):
            found[(i, j)] = _pair_record(prepared, i, j, distance, area)


def _ordered_candidates(idx_a, idx_b, left, right, same: bool):
    global_i = idx_a[left]
    global_j = idx_b[right]
    if same:
        keep = global_i < global_j
        return global_i[keep], global_j[keep]
    swap = global_i > global_j
    if np.any(swap):
        global_i = global_i.copy()
        global_j = global_j.copy()
        global_i[swap], global_j[swap] = global_j[swap], global_i[swap]
    return global_i, global_j


def _query_cell_pair(prepared, packed, slot, widths, normals, centroids, bases, indices_a, indices_b,
                      cell_a, cell_b, window_m: float | None, found: dict) -> None:
    """Expanded cell-plane boxes, then the exact co-directional test. No area prefilter."""
    same = cell_a == cell_b
    if same and len(indices_a) < 2:
        return
    direction = _cell_direction(cell_a)
    basis = _plane_basis(direction)
    idx_a = np.asarray(indices_a, dtype=np.int64)
    idx_b = idx_a if same else np.asarray(indices_b, dtype=np.int64)
    if same:
        heights = centroids[idx_a] @ direction
    else:
        heights = np.concatenate((centroids[idx_a] @ direction, centroids[idx_b] @ direction))
    height0 = float(np.median(heights))
    boxes_a = _expanded_boxes(packed, slot, widths, centroids, idx_a, basis, direction, height0)
    boxes_b = boxes_a if same else _expanded_boxes(packed, slot, widths, centroids, idx_b, basis, direction, height0)
    queried = shapely.STRtree(boxes_b).query(boxes_a)
    if queried.size == 0:
        return
    global_i, global_j = _ordered_candidates(
        idx_a, idx_b, np.asarray(queried[0], dtype=np.int64), np.asarray(queried[1], dtype=np.int64), same)
    _record_candidates(prepared, packed, slot, widths, bases, normals, centroids, global_i, global_j,
                       window_m, found)


def co_directional_pairs(faces: list[dict], window_m: float | None = None) -> list[dict]:
    """Same-direction overlapping faces.

    `window_m` limits the plane distance; None keeps every overlap (no distance cutoff).
    Opposite-facing pairs are not co-directional. Faces are bucketed by quantised normal;
    each unordered pair of a cell and one of its 26 neighbours is searched with expanded
    bounding boxes in the first cell's plane, then the exact per-face test.
    """
    prepared = []
    for face in faces:
        points = np.asarray(face["points"], dtype=float)
        if points.shape[0] < 3:
            continue
        normal = _normal(points)
        if np.linalg.norm(normal) < 0.9:
            continue
        prepared.append((face, points, normal, points.mean(0)))
    if not prepared:
        return []
    normals = np.stack([item[2] for item in prepared])
    centroids = np.stack([item[3] for item in prepared])
    bases = _plane_bases(normals)
    widths, packed, slot = _pack_faces(prepared)
    cells: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    for index, item in enumerate(prepared):
        cells[_normal_cell(item[2])].append(index)
    found: dict[tuple[int, int], dict] = {}
    seen: set[tuple] = set()
    for cell in cells:
        cx, cy, cz = cell
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    other = (cx + dx, cy + dy, cz + dz)
                    if other not in cells:
                        continue
                    key = (cell, other) if cell <= other else (other, cell)
                    if key in seen:
                        continue
                    seen.add(key)
                    _query_cell_pair(prepared, packed, slot, widths, normals, centroids, bases,
                                     cells[key[0]], cells[key[1]], key[0], key[1], window_m, found)
    pairs = list(found.values())
    pairs.sort(key=lambda pair: (pair["distance_m"], pair["a"], pair["b"]))
    return pairs


def _cell_direction(cell: tuple[int, int, int]) -> np.ndarray:
    vector = np.array(cell, dtype=float) * _NORMAL_CELL
    length = float(np.linalg.norm(vector))
    return vector / length if length else np.array([0.0, 0.0, 1.0])


def _histogram_mm(distances_mm: np.ndarray) -> dict[str, int]:
    counts = {}
    for label, low, high, low_inclusive, high_inclusive in _HISTOGRAM_MM:
        above_low = distances_mm >= low if low_inclusive else distances_mm > low
        below_high = distances_mm <= high if high_inclusive else distances_mm < high
        counts[label] = int(np.count_nonzero(above_low & below_high))
    return counts


def co_directional_distribution(pairs: list[dict], band_min_m: float, band_max_m: float) -> dict:
    """Count co-directional pairs below, inside and above the regulatory spacing band."""
    distances = np.array([pair["distance_m"] for pair in pairs], dtype=float)
    count = int(distances.size)
    if count == 0:
        millimetres = np.empty(0)
        minimum = median = maximum = None
    else:
        millimetres = distances * 1000.0
        for edge_mm in (band_min_m * 1000.0, band_max_m * 1000.0):  # histogram agrees with the band counts
            millimetres = np.where(np.abs(millimetres - edge_mm) <= BAND_EDGE_TOL_M * 1000.0, edge_mm, millimetres)
        minimum, median, maximum = float(millimetres.min()), float(np.median(millimetres)), float(millimetres.max())
    below = int(np.count_nonzero(distances < band_min_m - BAND_EDGE_TOL_M))
    above = int(np.count_nonzero(distances > band_max_m + BAND_EDGE_TOL_M))
    return {"pairs": count, "below_band": below, "in_band": count - below - above, "above_band": above,
            "min_mm": minimum, "median_mm": median, "max_mm": maximum, "histogram_mm": _histogram_mm(millimetres)}
