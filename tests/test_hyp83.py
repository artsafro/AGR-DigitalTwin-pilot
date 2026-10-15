"""Synthetic hypothesis #83 only; not facade delivery certification."""
import itertools
import numpy as np
import pytest
from experiments.hyp83.compare import (
    baseline, candidate, maximum_matching, XYZ_RADIUS, UV_LIMIT,
)
from experiments.hyp83.fixtures import CASES, FACES, ORDERS, arrays


@pytest.mark.parametrize('case', CASES, ids=lambda c: c.name)
@pytest.mark.parametrize('permutation', range(3))
def test_frozen_verdict(case, permutation):
    reference, observed = arrays(case, permutation)
    result = candidate(reference, observed, FACES, case.faces)
    assert result.accepted == case.expected


@pytest.mark.parametrize('case', CASES, ids=lambda c: c.name)
def test_baseline_false_accepts(case):
    for permutation in range(3):
        reference, observed = arrays(case, permutation)
        assert baseline(reference, observed, FACES, case.faces).accepted


def test_fixture_contract():
    assert len(CASES) == 8 and sum(c.expected for c in CASES) == 4
    assert len(ORDERS) == 3
    for case in CASES:
        assert len(case.reference) == len(case.observed) == 12
        assert len(case.faces) == 4
        assert [len(f) for f in case.faces] == [3] * 4
        assert sorted(i for f in case.faces for i in f) == list(range(12))
    for order in ORDERS:
        assert sorted(order) == list(range(12))


@pytest.mark.parametrize('method', [baseline, candidate])
@pytest.mark.parametrize('xyz_axis', range(3))
@pytest.mark.parametrize('uv_axis', range(3, 5))
@pytest.mark.parametrize('xyz_step', [-1, 0, 1])
@pytest.mark.parametrize('uv_step', [-1, 0, 1])
def test_tolerance_boundaries(method, xyz_axis, uv_axis, xyz_step, uv_step):
    def step(value, direction):
        return value if direction == 0 else np.nextafter(
            value, np.inf if direction > 0 else -np.inf)
    reference = np.zeros((1, 5))
    observed = reference.copy()
    observed[0, xyz_axis] = step(XYZ_RADIUS, xyz_step)
    observed[0, uv_axis] = step(UV_LIMIT, uv_step)
    result = method(reference, observed, ((0,),), ((0,),))
    assert result.accepted == (xyz_step <= 0 and uv_step < 0)


def test_all_small_graphs_against_bruteforce():
    probes = 0
    for n in range(4):
        for mask in range(1 << (n * n)):
            graph = [tuple(j for j in range(n) if mask & (1 << (i*n+j)))
                     for i in range(n)]
            # Independent exhaustive partial injective assignments.
            optimum = max((sum(j >= 0 for j in assignment)
                           for assignment in itertools.product(range(-1, n), repeat=n)
                           if len([j for j in assignment if j >= 0])
                           == len(set(j for j in assignment if j >= 0))
                           and all(j == -1 or j in graph[i]
                                   for i, j in enumerate(assignment))), default=0)
            matched = maximum_matching(graph, n)
            used = [j for j in matched if j >= 0]
            assert len(used) == len(set(used)) == optimum
            assert all(j == -1 or j in graph[i] for i, j in enumerate(matched))
            probes += 1
    assert probes == 531


def test_generated_multiplicities():
    sequences = list(itertools.product(range(3), repeat=3))
    probes = 0
    for a, b in itertools.product(sequences, repeat=2):
        reference = np.array([(0, 0, 0, u, 0) for u in a], dtype=float)
        observed = np.array([(0, 0, 0, u, 0) for u in b], dtype=float)
        result = candidate(reference, observed, ((0, 1, 2),), ((0, 1, 2),))
        assert result.accepted == (sorted(a) == sorted(b))
        used = [j for j in result.assignment if j >= 0]
        assert len(used) == len(set(used)) == result.cardinality
        assert all(j == -1 or a[j] == b[i] for i, j in enumerate(result.assignment))
        probes += 1
    assert probes == 729


def test_augmenting_path_not_greedy():
    reference = np.array([(0, 0, 0, 0, 0), (.003, 0, 0, 0, 0)])
    observed = np.array([(.0015, 0, 0, 0, 0), (0, 0, 0, 0, 0)])
    for a, b in itertools.product(itertools.permutations(range(2)), repeat=2):
        result = candidate(reference[list(a)], observed[list(b)], ((0, 1),), ((0, 1),))
        assert result.accepted and result.cardinality == 2


@pytest.mark.parametrize('method', [baseline, candidate])
@pytest.mark.parametrize('faces', [((0, 1, 2, 3, 4, 5),), ((0, 1), (2, 3, 4, 5))])
def test_face_count_and_degree_guards(method, faces):
    reference = np.zeros((6, 5))
    assert not method(reference, reference, ((0, 1, 2), (3, 4, 5)), faces).accepted


@pytest.mark.parametrize('count', [2, 4])
def test_corner_count_bijection(count):
    result = candidate(np.zeros((3, 5)), np.zeros((count, 5)), FACES, FACES)
    assert not result.accepted
    assert result.cardinality == min(count, 3)
