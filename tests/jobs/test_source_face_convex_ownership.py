"""new-case: independent convex ownership, plane and pivot controls for match_source_faces.

Synthetic rectangles and triangles, not package acceptance. Oracles are the
hand-labelled tuples below. Two separated convex rectangles, R0 = [0, 4] x
[0, 4] and R1 = [10, 14] x [0, 4], on the XY, XZ and YZ planes. Default tol
and shift [0, 0, 0] unless a control names another shift.

Acceptance table (input -> expected):

1. triangle contained in rectangle 0 -> [(0,)]
2. triangle on rectangle 1 -> [(1,)]
3. coplanar triangle outside both -> [()]
4. contained triangle displaced 0.001 m along its source normal -> [()]
5. same triangle displaced 0.0001 m along the normal (default tol=0.0002) -> [(0,)]
6. two coincident source rectangles -> [(0, 1)] (all hits kept, not first hit)

Repeated controls, same literal coordinates per plane: reverse winding and every
cyclic start of the output triangle and of each source face keep the owners;
swapping R0/R1 renumbers owners; subtracting pivot [0.5, -0.25, 0.125] from
delivered coordinates and passing that pivot as shift keeps ownership; duplicate
output triangles stay one tuple per output, in output order; deep-copied inputs
are unchanged and a repeat call matches.
"""
import copy
import math
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "jobs" / "TEC26-OKS" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import qa_packages  # noqa: E402

PLANES = ("xy", "xz", "yz")
PIVOT = [0.5, -0.25, 0.125]

# Literal convex rectangles and interior triangles. Displacement is along +Z
# (XY), +Y (XZ) and +X (YZ), the plane normal of the listed winding.
_COORDS = {
    "xy": {
        "r0": [[0, 0, 0], [4, 0, 0], [4, 4, 0], [0, 4, 0]],
        "r1": [[10, 0, 0], [14, 0, 0], [14, 4, 0], [10, 4, 0]],
        "in_r0": [[1, 1, 0], [3, 1, 0], [2, 3, 0]],
        "in_r1": [[11, 1, 0], [13, 1, 0], [12, 3, 0]],
        "outside": [[6, 1, 0], [8, 1, 0], [7, 3, 0]],
        "off_0_001": [[1, 1, 0.001], [3, 1, 0.001], [2, 3, 0.001]],
        "off_0_0001": [[1, 1, 0.0001], [3, 1, 0.0001], [2, 3, 0.0001]],
    },
    "xz": {
        "r0": [[0, 0, 0], [0, 0, 4], [4, 0, 4], [4, 0, 0]],
        "r1": [[10, 0, 0], [10, 0, 4], [14, 0, 4], [14, 0, 0]],
        "in_r0": [[1, 0, 1], [3, 0, 1], [2, 0, 3]],
        "in_r1": [[11, 0, 1], [13, 0, 1], [12, 0, 3]],
        "outside": [[6, 0, 1], [8, 0, 1], [7, 0, 3]],
        "off_0_001": [[1, 0.001, 1], [3, 0.001, 1], [2, 0.001, 3]],
        "off_0_0001": [[1, 0.0001, 1], [3, 0.0001, 1], [2, 0.0001, 3]],
    },
    "yz": {
        "r0": [[0, 0, 0], [0, 4, 0], [0, 4, 4], [0, 0, 4]],
        "r1": [[0, 10, 0], [0, 14, 0], [0, 14, 4], [0, 10, 4]],
        "in_r0": [[0, 1, 1], [0, 3, 1], [0, 2, 3]],
        "in_r1": [[0, 11, 1], [0, 13, 1], [0, 12, 3]],
        "outside": [[0, 6, 1], [0, 8, 1], [0, 7, 3]],
        "off_0_001": [[0.001, 1, 1], [0.001, 3, 1], [0.001, 2, 3]],
        "off_0_0001": [[0.0001, 1, 1], [0.0001, 3, 1], [0.0001, 2, 3]],
    },
}


def _finite(points):
    for point in points:
        assert len(point) == 3
        assert all(math.isfinite(coord) for coord in point)


def _block(*groups):
    points = []
    for group in groups:
        _finite(group)
        points.extend(copy.deepcopy(group))
    return points


def _zero():
    return [0.0, 0.0, 0.0]


def _pair(plane, kind):
    spec = _COORDS[plane]
    if kind == "coincident":
        src_v = _block(spec["r0"], spec["r0"])
    else:
        src_v = _block(spec["r0"], spec["r1"])
    return src_v, [[0, 1, 2, 3], [4, 5, 6, 7]]


def _ring_orders(indices):
    """Forward cyclic starts, then the reversed winding and its cyclic starts."""
    forward = list(indices)
    reverse = list(reversed(forward))
    orders = []
    for winding in (forward, reverse):
        for start in range(len(winding)):
            orders.append(winding[start:] + winding[:start])
    return orders


def _call(src_v, src_faces, out_v, out_faces, shift, matcher=None):
    """Match once, require inputs to equal their deep copies, and require a repeat call to match."""
    fn = qa_packages.match_source_faces if matcher is None else matcher
    _finite(src_v)
    _finite(out_v)
    _finite([shift])
    snap = copy.deepcopy(
        {
            "src_v": src_v,
            "src_faces": src_faces,
            "out_v": out_v,
            "out_faces": out_faces,
            "shift": shift,
        }
    )
    first = fn(src_v, src_faces, out_v, out_faces, shift)
    assert src_v == snap["src_v"]
    assert src_faces == snap["src_faces"]
    assert out_v == snap["out_v"]
    assert out_faces == snap["out_faces"]
    assert shift == snap["shift"]
    second = fn(
        snap["src_v"], snap["src_faces"], snap["out_v"], snap["out_faces"], snap["shift"],
    )
    assert first == second
    return first


def _assert_owners(src_v, src_faces, out_v, out_faces, shift, expected, matcher=None):
    assert _call(src_v, src_faces, out_v, out_faces, shift, matcher) == expected


def _assert_case(plane, point_key, kind, expected, swap=False, matcher=None):
    src_v, src_faces = _pair(plane, kind)
    if swap:
        src_faces = [[4, 5, 6, 7], [0, 1, 2, 3]]
    out_v = copy.deepcopy(_COORDS[plane][point_key])
    _assert_owners(src_v, src_faces, out_v, [[0, 1, 2]], _zero(), expected, matcher)


def _assert_pivot(plane, matcher=None):
    src_v, src_faces = _pair(plane, "pair")
    delivered = [
        [point[0] - PIVOT[0], point[1] - PIVOT[1], point[2] - PIVOT[2]]
        for point in _COORDS[plane]["in_r0"]
    ]
    _assert_owners(src_v, src_faces, delivered, [[0, 1, 2]], copy.deepcopy(PIVOT), [(0,)], matcher)


def _assert_coincident(plane, matcher=None):
    _assert_case(plane, "in_r0", "coincident", [(0, 1)], matcher=matcher)


def _ignore_shift(src_v, src_faces, out_v, out_faces, shift, tol=2e-4):
    """Drop pivot restoration: delivered coordinates are used with a zero shift."""
    return qa_packages.match_source_faces(
        src_v, src_faces, out_v, out_faces, [0.0, 0.0, 0.0], tol,
    )


def _first_hit_only(src_v, src_faces, out_v, out_faces, shift, tol=2e-4):
    """Keep only the first source hit of each output triangle."""
    owners = qa_packages.match_source_faces(
        src_v, src_faces, out_v, out_faces, shift, tol,
    )
    return [hits[:1] for hits in owners]


@pytest.mark.parametrize("plane", PLANES)
def test_contained_triangle_owns_rectangle_0(plane):
    _assert_case(plane, "in_r0", "pair", [(0,)])


@pytest.mark.parametrize("plane", PLANES)
def test_contained_triangle_owns_rectangle_1(plane):
    _assert_case(plane, "in_r1", "pair", [(1,)])


@pytest.mark.parametrize("plane", PLANES)
def test_coplanar_triangle_outside_both_has_no_owner(plane):
    _assert_case(plane, "outside", "pair", [()])


@pytest.mark.parametrize("plane", PLANES)
def test_normal_offset_0_001_m_has_no_owner(plane):
    _assert_case(plane, "off_0_001", "pair", [()])


@pytest.mark.parametrize("plane", PLANES)
def test_normal_offset_0_0001_m_owns_rectangle_0(plane):
    _assert_case(plane, "off_0_0001", "pair", [(0,)])


@pytest.mark.parametrize("plane", PLANES)
def test_coincident_rectangles_keep_every_hit(plane):
    _assert_coincident(plane)


@pytest.mark.parametrize("plane", PLANES)
def test_winding_and_cyclic_start_keep_owners(plane):
    cases = (
        ("in_r0", "pair", [(0,)]),
        ("in_r1", "pair", [(1,)]),
        ("outside", "pair", [()]),
        ("off_0_001", "pair", [()]),
        ("off_0_0001", "pair", [(0,)]),
        ("in_r0", "coincident", [(0, 1)]),
    )
    seen = 0
    for point_key, kind, expected in cases:
        src_v, src_faces = _pair(plane, kind)
        out_v = copy.deepcopy(_COORDS[plane][point_key])
        for face_0 in _ring_orders(src_faces[0]):
            for face_1 in _ring_orders(src_faces[1]):
                for tri in _ring_orders([0, 1, 2]):
                    _assert_owners(
                        src_v, [face_0, face_1], out_v, [tri], _zero(), expected,
                    )
                    seen += 1
    assert seen == 6 * 8 * 8 * 6


@pytest.mark.parametrize("plane", PLANES)
def test_swapped_source_faces_renumber_owners(plane):
    _assert_case(plane, "in_r0", "pair", [(1,)], swap=True)
    _assert_case(plane, "in_r1", "pair", [(0,)], swap=True)
    _assert_case(plane, "outside", "pair", [()], swap=True)
    _assert_case(plane, "off_0_001", "pair", [()], swap=True)
    _assert_case(plane, "off_0_0001", "pair", [(1,)], swap=True)
    _assert_case(plane, "in_r0", "coincident", [(0, 1)], swap=True)


@pytest.mark.parametrize("plane", PLANES)
def test_pivot_shift_keeps_ownership(plane):
    _assert_pivot(plane)


@pytest.mark.parametrize("plane", PLANES)
def test_duplicate_output_triangles_keep_order(plane):
    src_v, src_faces = _pair(plane, "pair")
    spec = _COORDS[plane]
    _assert_owners(
        src_v, src_faces, copy.deepcopy(spec["in_r0"]), [[0, 1, 2], [0, 1, 2]], _zero(),
        [(0,), (0,)],
    )
    both = _block(spec["in_r0"], spec["in_r1"])
    _assert_owners(
        src_v, src_faces, both, [[0, 1, 2], [3, 4, 5]], _zero(), [(0,), (1,)],
    )
    _assert_owners(
        src_v, src_faces, both, [[3, 4, 5], [0, 1, 2]], _zero(), [(1,), (0,)],
    )
    mixed = _block(spec["in_r1"], spec["outside"], spec["in_r0"])
    _assert_owners(
        src_v, src_faces, mixed, [[0, 1, 2], [3, 4, 5], [6, 7, 8]], _zero(),
        [(1,), (), (0,)],
    )


@pytest.mark.parametrize("plane", PLANES)
def test_inputs_unchanged_and_repeat_matches(plane):
    _assert_case(plane, "in_r0", "pair", [(0,)])
    _assert_case(plane, "in_r1", "pair", [(1,)])
    _assert_case(plane, "outside", "pair", [()])
    _assert_case(plane, "off_0_001", "pair", [()])
    _assert_case(plane, "off_0_0001", "pair", [(0,)])
    _assert_coincident(plane)
    _assert_pivot(plane)


@pytest.mark.parametrize("plane", PLANES)
def test_witness_shift_ignored_fails_pivot(plane):
    with pytest.raises(AssertionError):
        _assert_pivot(plane, matcher=_ignore_shift)


@pytest.mark.parametrize("plane", PLANES)
def test_witness_first_hit_fails_coincident_rectangles(plane):
    with pytest.raises(AssertionError):
        _assert_coincident(plane, matcher=_first_hit_only)
