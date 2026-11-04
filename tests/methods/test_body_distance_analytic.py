"""Independent analytic controls for nearest_triangle_distance (point -> SURFACE of a unit box).

Expected distances come from a scalar stdlib box formula, never from production distance code.
Pattern: n/a | new-case: hand-specified box surface oracle for tools/methods/methods_metrics.py.
"""
import itertools
import math

import numpy as np
import pytest

from tools.methods.methods_metrics import nearest_triangle_distance

TOL = 1e-12

# 8 corners (bit i of the index = coordinate i), 12 hand-listed triangles, two per face.
CORNERS = [(float(i & 1), float((i >> 1) & 1), float((i >> 2) & 1)) for i in range(8)]
FACES = [
    (0, 2, 3, 1), (4, 5, 7, 6),  # z=0, z=1
    (0, 1, 5, 4), (2, 6, 7, 3),  # y=0, y=1
    (0, 4, 6, 2), (1, 3, 7, 5),  # x=0, x=1
]
TRIS = [t for a, b, c, d in FACES for t in ((a, b, c), (a, c, d))]

CASES = [  # point, expected metres
    ((.5, .5, .5), .5), ((.5, .5, 2.), 1.), ((2., 2., .5), math.sqrt(2)), ((2., 2., 2.), math.sqrt(3)),
    ((.5, .5, 0.), 0.), ((0., 0., 0.), 0.), ((.1, .4, .7), .1),
]


def box_surface_distance(p):
    """Scalar oracle for the [0,1]^3 surface."""
    ex = [max(-c, c - 1.0, 0.0) for c in p]
    if any(ex):
        return math.sqrt(sum(e * e for e in ex))
    return min(min(c, 1.0 - c) for c in p)


def soup(order=None, flip=False, shift=0.0):
    tris = [TRIS[i] for i in (range(len(TRIS)) if order is None else order)]
    arr = np.array([[CORNERS[v] for v in (t[::-1] if flip else t)] for t in tris]) + shift
    return arr


def test_oracle_matches_literal_table():
    for p, d in CASES:
        assert box_surface_distance(p) == pytest.approx(d, abs=TOL)


def test_box_is_closed_twelve_triangles():
    assert soup().shape == (12, 3, 3)


@pytest.mark.parametrize("r0", [.125, .5, 32.])
def test_literal_points_all_radii(r0):
    pts = np.array([p for p, _ in CASES])
    got = nearest_triangle_distance(pts, soup(), r0=r0)
    assert got.shape == (len(CASES),) and np.isfinite(got).all()
    np.testing.assert_allclose(got, [d for _, d in CASES], atol=TOL, rtol=0)


@pytest.mark.parametrize("r0", [.125, .5, 32.])
def test_grid_plane_sides_and_interior_not_zero(r0):
    # points either side of multiples of 0.125/0.5 (grid planes) and inside the solid
    vals = [-.5, -.125, -1e-3, 0., .125, .25 - 1e-3, .25 + 1e-3, .5, .75, 1., 1.125, 1.5]
    pts = np.array(list(itertools.product(vals[::3] + [.5], vals[1::3] + [.25], vals[2::4] + [.4])))
    got = nearest_triangle_distance(pts, soup(), r0=r0)
    exp = np.array([box_surface_distance(p) for p in pts])
    np.testing.assert_allclose(got, exp, atol=TOL, rtol=0)
    inside = np.all((pts > 0) & (pts < 1), axis=1)
    assert inside.any() and (got[inside] > 0).all()


def test_permutations_winding_and_translation_invariance():
    pts = np.array([p for p, _ in CASES] + [(-.25, .5, .5), (1.5, -.5, .25)])
    exp = np.array([box_surface_distance(p) for p in pts])
    rng = np.random.default_rng(7)
    for r0 in (.125, .5, 32.):
        for order, flip in ((rng.permutation(12), False), (None, True), (rng.permutation(12), True)):
            perm = rng.permutation(len(pts))
            got = nearest_triangle_distance(pts[perm], soup(order, flip), r0=r0)
            np.testing.assert_allclose(got, exp[perm], atol=TOL, rtol=0)
        shift = 2.0 ** -3 * 3  # exact binary
        p2, t2 = pts + shift, soup(shift=shift)
        p2c, t2c = p2.copy(), t2.copy()
        np.testing.assert_allclose(nearest_triangle_distance(p2, t2, r0=r0), exp, atol=TOL, rtol=0)
        assert np.array_equal(p2, p2c) and np.array_equal(t2, t2c)


def test_dropping_a_face_or_centroid_only_would_be_caught():
    # Witness that the oracle distinguishes the failure modes named in the card.
    full = nearest_triangle_distance(np.array([(.5, .5, 2.)]), soup())[0]
    no_top = nearest_triangle_distance(np.array([(.5, .5, 2.)]), np.delete(soup(), [2, 3], axis=0))[0]
    assert full == pytest.approx(1.0, abs=TOL) and no_top > 1.1
    assert nearest_triangle_distance(np.array([(.5, .5, .5)]), soup())[0] == pytest.approx(.5, abs=TOL)


def test_right_triangle_controls_face_edge_vertex():
    tri = np.array([[(0., 0., 0.), (1., 0., 0.), (0., 1., 0.)]])
    pts = np.array([(.25, .25, .5), (.5, -.5, 0.), (-1., -1., 0.), (1., 1., 0.)])
    exp = [.5, .5, math.sqrt(2), math.sqrt(.5)]
    for r0 in (.125, 32.):
        np.testing.assert_allclose(nearest_triangle_distance(pts, tri, r0=r0), exp, atol=TOL, rtol=0)
