"""Regression set and probes for the two-way surface identity check (#305)."""
import math

import numpy as np
import pytest
import shapely

from dt_ai.geometry.surface_identity import (
    DIFFERENT_AREA_M2,
    SAME_AREA_M2,
    TOLERANCE_M,
    classify,
    compare_surfaces,
)


def square(size=1.0, z=0.0):
    a, b, c, d = [0, 0, z], [size, 0, z], [size, size, z], [0, size, z]
    return [[a, b, c], [a, c, d]]


def grid(size=1.0, cells=10, hole=(), z=0.0):
    """Square of ``cells`` x ``cells`` quads (two triangles each); ``hole`` lists (i, j) cells left out."""
    step = size / cells
    faces = []
    for i in range(cells):
        for j in range(cells):
            if (i, j) in hole:
                continue
            x0, y0, x1, y1 = i * step, j * step, (i + 1) * step, (j + 1) * step
            faces += [[[x0, y0, z], [x1, y0, z], [x1, y1, z]], [[x0, y0, z], [x1, y1, z], [x0, y1, z]]]
    return faces


def verdict(a, b, **kwargs):
    return compare_surfaces(a, b, **kwargs)["verdict"]


def hole_10cm():
    # 1 m square of 5 cm cells, a 10 cm x 10 cm hole (2 x 2 cells) away from the border.
    return grid(1.0, 20, hole={(8, 8), (8, 9), (9, 8), (9, 9)})


# --- issue regression set -------------------------------------------------------------------------------


def test_solid_vs_tessellated_square_is_same():
    assert verdict(square(), grid(1.0, 20)) == "same"
    assert verdict(grid(1.0, 20), square()) == "same"


@pytest.mark.parametrize("order", ["npm_solid", "npm_holed"])
def test_square_vs_square_with_10cm_hole_is_different_both_orders(order):
    a, b = (square(), hole_10cm()) if order == "npm_solid" else (hole_10cm(), square())
    result = compare_surfaces(a, b)
    assert result["verdict"] == "different"
    holed = result["b"] if order == "npm_solid" else result["a"]
    assert holed["uncovered_m2"] == 0.0 or holed["uncovered_m2"] < SAME_AREA_M2
    solid = result["a"] if order == "npm_solid" else result["b"]
    assert solid["uncovered_m2"] == pytest.approx(0.01, rel=0.05)


def test_scaled_copy_is_different():
    scaled = (np.asarray(grid(1.0, 4)) * 1.01).tolist()
    assert verdict(square(), scaled) == "different"
    assert verdict(scaled, square()) == "different"


def test_equal_triangle_count_different_shape_is_different():
    # Parallelogram with the same two-triangle count and the same area as the unit square.
    shear = [[[0, 0, 0], [1, 0, 0], [1.5, 1, 0]], [[0, 0, 0], [1.5, 1, 0], [0.5, 1, 0]]]
    assert len(shear) == len(square())
    result = compare_surfaces(square(), shear)
    assert result["area_difference_m2"] == pytest.approx(0.0, abs=1e-12)
    assert result["verdict"] == "different"


@pytest.mark.parametrize("bad", [
    [],
    None,
    "faces",
    [[[0, 0, 0], [1, 0, 0]]],
    [[[0, 0, 0], [1, 0, 0], [1, 1]]],
    [[[0, 0, 0], [1, 0, 0], [2, 0, 0]]],
    [[[0, 0, 0], [0, 0, 0], [0, 0, 0]], [[1, 1, 1], [1, 1, 1], [1, 1, 1]]],
    [[[0, 0, 0], [1, 0, 0], [1, 1, float("nan")]]],
    [[[0, 0, 0], [1, 0, 0], [1, 1, float("inf")]]],
    [[[0, 0, 0], [1, 0, 0], [1, True, 0]]],
    [[[0, 0, 0], [1, 0, 0], [1, "1", 0]]],
    np.zeros((0, 3, 3)),
])
@pytest.mark.parametrize("side", ["a", "b"])
def test_empty_degenerate_nan_input_is_error_never_same(bad, side):
    a, b = (bad, square()) if side == "a" else (square(), bad)
    result = compare_surfaces(a, b)
    assert result["verdict"] == "error"
    assert result["reason"]
    both = compare_surfaces(bad, bad)
    assert both["verdict"] == "error"


# --- 1 cm features ----------------------------------------------------------------------------------


def test_one_cm_hole_is_different_both_orders():
    holed = grid(0.1, 10, hole={(4, 4)})
    assert verdict(square(0.1), holed) == "different"
    assert verdict(holed, square(0.1)) == "different"


def test_one_cm_missing_face_is_different():
    # One 1 cm x 1 cm quad cell missing at the border (two triangles).
    assert verdict(grid(0.1, 10), grid(0.1, 10, hole={(0, 3)}), frame="world") == "different"


def test_one_cm_extra_face_is_different_both_orders():
    extra = grid(1.0, 4) + [[[0.5, 0.5, 0.3], [0.51, 0.5, 0.3], [0.51, 0.51, 0.3]],
                            [[0.5, 0.5, 0.3], [0.51, 0.51, 0.3], [0.5, 0.51, 0.3]]]
    assert verdict(square(), extra) == "different"
    assert verdict(extra, square()) == "different"


def test_duplicated_coincident_face_is_different():
    # Every point is covered both ways, but an extra coincident 1 cm face doubles that area.
    base = grid(0.1, 10)
    assert verdict(base, base + base[:2]) == "different"


def test_sub_millimetre_hole_is_unverified_not_same():
    # 0.5 mm hole: below the different threshold, above the same threshold -> stays unverified.
    holed = grid(0.01, 20, hole={(10, 10)})
    assert verdict(square(0.01), holed) == "unverified"


# --- tolerance edges ----------------------------------------------------------------------------------


def test_normal_offset_half_tolerance_is_same():
    assert verdict(square(), square(z=TOLERANCE_M / 2), frame="world") == "same"


def test_normal_offset_exactly_tolerance_is_different():
    assert verdict(square(), square(z=TOLERANCE_M), frame="world") == "different"


def test_in_plane_shift_exactly_tolerance_is_not_same():
    shifted = (np.asarray(square()) + [TOLERANCE_M, 0, 0]).tolist()
    assert verdict(square(), shifted, frame="world") != "same"


def test_translated_copy_is_same_in_pivot_frame_only():
    moved = (np.asarray(grid(1.0, 5)) + [12.5, -3.0, 0.7]).tolist()
    assert verdict(square(), moved) == "same"
    assert verdict(square(), moved, frame="world") == "different"


def test_rotated_copy_is_different():
    angle = math.radians(30)
    rot = np.array([[math.cos(angle), -math.sin(angle), 0], [math.sin(angle), math.cos(angle), 0], [0, 0, 1]])
    assert verdict(square(), (np.asarray(square()) @ rot.T).tolist()) == "different"


def test_flipped_winding_is_same_surface():
    flipped = [[face[0], face[2], face[1]] for face in grid(1.0, 3)]
    assert verdict(square(), flipped) == "same"


def test_partial_degenerate_faces_are_counted_not_fatal():
    sliver = [[[0, 0, 0], [0.5, 0, 0], [1, 0, 0]]]
    result = compare_surfaces(square(), square() + sliver)
    assert result["verdict"] == "same"
    assert result["b"]["degenerate_faces"] == 1


# --- classify thresholds ----------------------------------------------------------------------------


@pytest.mark.parametrize("values, expected", [
    ((0.0, 0.0, 0.0), "same"),
    ((SAME_AREA_M2, 0.0, 0.0), "same"),
    ((SAME_AREA_M2 * 2, 0.0, 0.0), "unverified"),
    ((0.0, DIFFERENT_AREA_M2, 0.0), "different"),
    ((0.0, 0.0, DIFFERENT_AREA_M2), "different"),
    ((DIFFERENT_AREA_M2 * 0.999, 0.0, 0.0), "unverified"),
    ((float("nan"), 0.0, 0.0), "error"),
    ((0.0, float("inf"), 0.0), "error"),
    ((0.0, 0.0, -1.0), "error"),
])
def test_classify_thresholds(values, expected):
    assert classify(*values)[0] == expected


@pytest.mark.parametrize("kwargs", [
    {"tolerance_m": 0}, {"tolerance_m": -1}, {"tolerance_m": float("nan")},
    {"same_area_m2": 1e-3, "different_area_m2": 1e-6}, {"frame": "local"},
])
def test_bad_parameters_raise(kwargs):
    with pytest.raises(ValueError):
        compare_surfaces(square(), square(), **kwargs)


# --- generated probes -------------------------------------------------------------------------------


def _rigid(seed):
    rng = np.random.default_rng(seed)
    q = rng.normal(size=4)
    q /= np.linalg.norm(q)
    w, x, y, z = q
    rot = np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])
    return rot, rng.uniform(-50, 50, size=3), rng


def _delaunay(points):
    tris = shapely.delaunay_triangles(shapely.MultiPoint(points))
    return [[[*xy, 0.0] for xy in list(t.exterior.coords)[:3]] for t in tris.geoms]


PROBE_SEEDS = range(40)


@pytest.mark.parametrize("seed", PROBE_SEEDS)
def test_probe_random_retessellation_is_same(seed):
    """Invariant: the same planar region, tessellated two random ways and rigidly moved together -> same."""
    rot, shift, rng = _rigid(seed)
    corners = [(0, 0), (1, 0), (1, 1), (0, 1)]
    a = _delaunay(corners + [tuple(p) for p in rng.uniform(0.05, 0.95, size=(8, 2))])
    b = _delaunay(corners + [tuple(p) for p in rng.uniform(0.05, 0.95, size=(5, 2))])
    move = lambda faces: (np.asarray(faces) @ rot.T + shift).tolist()  # noqa: E731
    assert verdict(move(a), move(b), frame="world") == "same"


@pytest.mark.parametrize("seed", PROBE_SEEDS)
def test_probe_random_hole_of_1_to_10_cm_is_different(seed):
    """Invariant: a hole >= 1 cm anywhere, any orientation, either order -> different, never same."""
    rot, shift, rng = _rigid(seed)
    side = rng.uniform(0.01, 0.10)
    x0, y0 = rng.uniform(0.05, 0.95 - side, size=2)
    ring = shapely.box(0, 0, 1, 1).difference(shapely.box(x0, y0, x0 + side, y0 + side))
    holed = [[[*xy, 0.0] for xy in list(t.exterior.coords)[:3]]
             for t in shapely.constrained_delaunay_triangles(ring).geoms]
    move = lambda faces: (np.asarray(faces) @ rot.T + shift).tolist()  # noqa: E731
    first, second = (square(), holed) if seed % 2 else (holed, square())
    result = compare_surfaces(move(first), move(second), frame="world")
    assert result["verdict"] == "different"
    assert max(result["a"]["uncovered_m2"], result["b"]["uncovered_m2"]) == pytest.approx(side * side, rel=0.05)


@pytest.mark.parametrize("seed", PROBE_SEEDS)
def test_probe_random_scale_is_different(seed):
    """Invariant: a copy scaled by >= 1 % about the pivot -> different."""
    _, _, rng = _rigid(seed)
    factor = rng.choice([-1, 1]) * rng.uniform(0.01, 0.2) + 1.0
    assert verdict(square(), (np.asarray(grid(1.0, 3)) * factor).tolist()) == "different"


@pytest.mark.parametrize("seed", PROBE_SEEDS)
def test_probe_random_garbage_is_never_same(seed):
    """Invariant: NaN/inf/empty anywhere in either mesh -> error."""
    rng = np.random.default_rng(seed)
    faces = np.asarray(grid(1.0, 3))
    i, j, k = rng.integers(0, faces.shape[0]), rng.integers(0, 3), rng.integers(0, 3)
    faces[i, j, k] = [float("nan"), float("inf"), -float("inf")][seed % 3]
    a, b = (faces.tolist(), square()) if seed % 2 else (square(), faces.tolist())
    assert verdict(a, b) == "error"
