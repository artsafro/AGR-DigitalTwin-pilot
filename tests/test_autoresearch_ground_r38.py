"""Regression for non-vacuous Ground triangulation evidence in OBSERVE #38."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest


RESEARCH = Path(__file__).resolve().parents[1] / 'docs/research'
spec = importlib.util.spec_from_file_location('r38', RESEARCH / 'autoresearch-ground-qe-triangulation-r38.py')
r38 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r38)


def test_already_triangulated_is_not_exercised():
    scorer = r38.load_scorer()
    part = scorer.Part('triangle', np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]]), ((0, 1, 2),), np.zeros(3))
    row = r38.examine(scorer, part)
    assert row.get('status', row.get('invariant')) == 'not_exercised'
    assert 'invariant' not in row
    assert all(s['face_count'] == 1 and s['ngon_faces'] == s['inserted_diagonals'] == 0
               for s in row['states'].values())


def test_short_inserted_diagonal_is_exercised_and_changes_E():
    scorer = r38.load_scorer()
    verts = np.array([[-1, 0, 0], [0, -.0005, 0], [1, 0, 0], [0, .0005, 0]])
    row = r38.examine(scorer, scorer.Part('quad', verts, ((0, 1, 2, 3),), np.zeros(3)))
    assert row.get('status') == 'changed'
    assert row['valid']
    assert [(s['face_count'], s['ngon_faces'], s['inserted_diagonals'], s['runs'][0]['E'])
            for s in row['states'].values()] == [(1, 1, 0, 0), (2, 0, 1, 0), (2, 0, 1, 1)]


@pytest.mark.parametrize(('a', 'f', 'valid', 'margin', 'expected'), [
    ('invariant', 'not_exercised', True, True, 'inconclusive'),
    ('not_exercised', 'invariant', True, True, 'inconclusive'),
    ('invariant', 'invariant', True, True, 'confirmed'),
    ('invariant', 'changed', True, True, 'refuted'),
    ('changed', 'not_exercised', True, True, 'refuted'),
    ('invariant', 'invariant', False, True, 'inconclusive'),
    ('invariant', 'not_exercised', True, False, 'refuted'),
])
def test_verdict_requires_real_coverage_on_both_sides(a, f, valid, margin, expected):
    rows = {'A1': {'status': a}, 'F4': {'status': f}}
    separation = {s: {'pass_margin': margin} for s in r38.STATES}
    assert r38.verdict(rows, separation, valid) == expected
