"""Independent engine/checker UV area-cutoff eligibility baseline.

new-case: dyadic origin triangles against the two area cutoffs, both windings.

Literal per-implementation outcomes freeze a baseline GREEN characterization.
This is not delivery acceptance and not a policy decision.
"""
from copy import deepcopy
from fractions import Fraction

import pytest

from dt_ai.geometry import uv as engine
from twinqa import uv as checker


# Frozen acceptance call: tile 1001, size 2048, padding 0.
TILE, SIZE, PADDING = 1001, 2048, 0
LOW_CUTOFF = Fraction(1, 10**12)
HIGH_CUTOFF = Fraction(1, 10**10)


def fraction_signed_area(uv):
    """Scalar Fraction shoelace. No production signed_area participates."""
    points = [(Fraction(point[0]), Fraction(point[1])) for point in uv]
    twice = sum(
        points[i][0] * points[(i + 1) % len(points)][1]
        - points[(i + 1) % len(points)][0] * points[i][1]
        for i in range(len(points))
    )
    return twice / 2


def dyadic_triangle(k):
    return [(0.0, 0.0), (2.0**-k, 0.0), (0.0, 2.0**-k)]


def rotate(points, shift):
    return points[shift:] + points[:shift]


def assert_strict_cutoff_position(k, magnitude):
    if k == 21:
        assert magnitude < LOW_CUTOFF
        assert magnitude < HIGH_CUTOFF
    elif k == 18:
        assert magnitude > LOW_CUTOFF
        assert magnitude < HIGH_CUTOFF
    else:
        assert k == 15
        assert magnitude > LOW_CUTOFF
        assert magnitude > HIGH_CUTOFF


def assert_literal(uv, engine_ok, issue, checker_ok):
    before = deepcopy(uv)
    engine_result = engine.validate_uv(uv, TILE, SIZE, PADDING)
    if engine_ok:
        assert engine_result is True
    else:
        assert engine_result is False
    assert uv == before

    before = deepcopy(uv)
    found = checker.face_issue(uv, TILE, SIZE, PADDING)
    if issue is None:
        assert found is None
    else:
        assert found == issue
    assert uv == before

    before = deepcopy(uv)
    checker_result = checker.validate_uv(uv, TILE, SIZE, PADDING)
    if checker_ok:
        assert checker_result is True
    else:
        assert checker_result is False
    assert uv == before


@pytest.mark.parametrize(
    "k,engine_ok,issue,checker_ok",
    [
        (21, False, "invalid", False),
        (18, False, None, True),
        (15, True, None, True),
    ],
)
@pytest.mark.parametrize("shift", range(3))
def test_forward_dyadic_area_cutoff(k, engine_ok, issue, checker_ok, shift):
    uv = rotate(dyadic_triangle(k), shift)
    area = fraction_signed_area(uv)
    assert area == Fraction(1, 2 ** (2 * k + 1))
    assert_strict_cutoff_position(k, area)
    assert_literal(uv, engine_ok, issue, checker_ok)


@pytest.mark.parametrize(
    "k,engine_ok,issue,checker_ok",
    [
        (21, False, "invalid", False),
        (18, False, "mirrored", False),
        (15, False, "mirrored", False),
    ],
)
@pytest.mark.parametrize("shift", range(3))
def test_reversed_dyadic_area_cutoff(k, engine_ok, issue, checker_ok, shift):
    uv = rotate(list(reversed(dyadic_triangle(k))), shift)
    area = fraction_signed_area(uv)
    exact = Fraction(1, 2 ** (2 * k + 1))
    assert area == -exact
    assert_strict_cutoff_position(k, exact)
    assert_literal(uv, engine_ok, issue, checker_ok)


def test_positive_ordinary_quad_is_eligible():
    uv = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
    assert_literal(uv, True, None, True)


@pytest.mark.parametrize(
    "uv",
    [
        [[0.0, 0.0], [0.0, 0.0], [1.0, 0.0]],
        [[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]],
    ],
    ids=["repeated", "collinear"],
)
def test_zero_area_triangles_are_invalid(uv):
    assert_literal(uv, False, "invalid", False)


def test_scalar_point_raises_has_no_len_without_mutation():
    uv = [1, [0.5, 0], [0.0, 0.5]]
    for call in (engine.validate_uv, checker.face_issue, checker.validate_uv):
        before = deepcopy(uv)
        with pytest.raises(TypeError, match="has no len"):
            call(uv, TILE, SIZE, PADDING)
        assert uv == before
