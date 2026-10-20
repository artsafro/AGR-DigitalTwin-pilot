"""new-case: synthetic checker-weld characterization, not delivery certification or extractor QA.

The oracle uses only sorted/set, math.dist and a quadratic greedy scan; it does
not use the checker's pair search or any dt_ai weld. Corpus/seeds are fixed below.
"""
from itertools import permutations
from math import dist
from random import Random

import numpy as np
import pytest

from twinqa.geometry.mesh import weld

WELD_M = 0.003
EPS_M = 1e-9  # Freeze the current contract independently of the production constant.
SEEDS = (101, 709, 2027, 65537)
SHIFTS = (
    (0.0, 0.0, 0.0),
    (0.0002, -0.0003, 0.0004),
    (-0.0002, 0.0003, -0.0004),
    (WELD_M + EPS_M, 0.0, -WELD_M - EPS_M),
    (-WELD_M - EPS_M, WELD_M + EPS_M, 0.0),
)
CHAIN = np.array([[0.0, 0.0, 0.0], [0.002, 0.0, 0.0], [0.004, 0.0, 0.0]])
# Exhaust every ordering of the base cloud and of two copies of each position.
ORDERS = tuple(permutations(range(3))) + tuple(sorted(set(permutations((0, 0, 1, 1, 2, 2)))))


def _oracle_partition(vertices):
    """First free lexicographic position takes all still-free positions in reach."""
    positions = [tuple(float(x) for x in row) for row in vertices]
    free = set(positions)
    groups = []
    for leader in sorted(free):
        if leader not in free:
            continue
        members = {point for point in free if dist(leader, point) <= WELD_M + EPS_M}
        free.difference_update(members)
        groups.append(frozenset(i for i, point in enumerate(positions) if point in members))
    return frozenset(groups)


def _partition(ids):
    return frozenset(frozenset(i for i, value in enumerate(ids) if value == group)
                     for group in set(ids.tolist()))


def _check(vertices):
    before = vertices.copy()
    expected = _oracle_partition(vertices)
    ids = weld(vertices, WELD_M)
    np.testing.assert_array_equal(vertices, before)
    assert ids.shape == (len(vertices),)
    assert np.issubdtype(ids.dtype, np.integer)
    assert _partition(ids) == expected
    assert sorted(set(ids.tolist())) == list(range(len(expected)))

    # Check ID order separately from partition equality: IDs follow the sorted
    # lexicographic leaders, not input order, group size, or an arbitrary index.
    ordered = sorted(expected, key=lambda group: min(tuple(vertices[i]) for i in group))
    for group_id, group in enumerate(ordered):
        leader = min(tuple(vertices[i]) for i in group)
        for i in group:
            assert ids[i] == group_id
            assert dist(leader, vertices[i]) <= WELD_M + EPS_M
    return ids


def test_three_point_chain_is_greedy_not_transitive():
    ids = _check(CHAIN.copy())
    assert _partition(ids) == frozenset((frozenset((0, 1)), frozenset((2,))))


@pytest.mark.parametrize("order", ORDERS)
def test_all_chain_permutations_and_duplicates_preserve_equivalence(order):
    vertices = CHAIN[list(order)].copy()
    ids = _check(vertices)
    # Undo permutation/duplication by comparing every pair with its source index.
    expected = (0, 0, 1)
    for i, source_i in enumerate(order):
        for j, source_j in enumerate(order):
            assert (ids[i] == ids[j]) == (expected[source_i] == expected[source_j])


@pytest.mark.parametrize("positions", (
    # Leaders tie on X; the contested point is equidistant, but listed first.
    ((0.001, 0.002, 0.0), (0.0, 0.004, 0.0), (0.0, 0.0, 0.0)),
    # Leaders tie on X and Y, so Z decides; the later leader is closer.
    ((0.001, 0.0, 0.0025), (0.0, 0.0, 0.004), (0.0, 0.0, 0.0)),
    # X takes priority over Y; neither input order nor nearest leader wins.
    ((0.0, 0.0025, 0.0), (0.0, 0.004, 0.0), (-0.001, 0.0, 0.0)),
))
def test_first_free_lexicographic_leader_wins_competition(positions):
    vertices = np.array(positions)
    assert dist(vertices[1], vertices[2]) > WELD_M + EPS_M
    assert dist(vertices[0], vertices[1]) <= WELD_M + EPS_M
    assert dist(vertices[0], vertices[2]) <= WELD_M + EPS_M
    ids = _check(vertices)
    assert _partition(ids) == frozenset((frozenset((0, 2)), frozenset((1,))))


@pytest.mark.parametrize("axis", range(3))
@pytest.mark.parametrize("extra,groups", ((0.0, 1), (0.5e-9, 1), (2e-9, 2)))
def test_inclusive_epsilon_boundary_on_each_axis(axis, extra, groups):
    vertices = np.zeros((2, 3))
    vertices[1, axis] = WELD_M + extra
    ids = _check(vertices)
    assert len(_partition(ids)) == groups


def test_empty_array_returns_empty_integer_ids():
    ids = _check(np.empty((0, 3), dtype=float))
    assert ids.size == 0


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("shift", SHIFTS)
def test_fixed_finite_clouds_match_complete_oracle_partition(seed, shift):
    rng = Random(seed)
    # Small clouds spanning both signs and several cells, with guaranteed close
    # pairs near cell boundaries as well as random 3-D competition and duplicates.
    points = [tuple(rng.uniform(-0.006, 0.006) for _ in range(3)) for _ in range(12)]
    points += [(-0.0031, 0.0, 0.0), (-0.0029, 0.0, 0.0),
               (0.0029, -0.0031, 0.0031), (0.0031, -0.0029, 0.0029)]
    points += [points[i] for i in (0, 3, 12, 15)]
    vertices = np.array(points) + np.array(shift)
    assert np.isfinite(vertices).all()
    assert np.any(vertices < 0)
    assert len(set(map(tuple, vertices))) < len(vertices)
    ids = _check(vertices)

    order = list(range(len(vertices)))
    rng.shuffle(order)
    shuffled_ids = _check(vertices[order].copy())
    restored = np.empty_like(shuffled_ids)
    restored[order] = shuffled_ids
    assert _partition(restored) == _partition(ids)
    np.testing.assert_array_equal(restored, ids)  # deterministic compact order too
