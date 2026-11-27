"""Unit checks for the #149 scorer (synthetic inputs only)."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score as S  # noqa: E402


def test_uncertainty_identical_partition_near_one():
    rng = np.random.default_rng(0)
    v = rng.integers(1, 5, 5000)
    assert S.uncertainty(v, v + 10) > 0.99


def test_uncertainty_independent_near_zero():
    rng = np.random.default_rng(1)
    v, m = rng.integers(1, 5, 5000), rng.integers(1, 40, 5000)
    assert abs(S.uncertainty(v, m)) < 0.01


def test_uncertainty_permutation_invariant():
    rng = np.random.default_rng(2)
    v, m = rng.integers(1, 6, 3000), rng.integers(1, 30, 3000)
    m = np.where(rng.random(3000) < 0.5, v * 3, m)
    perm = np.array([0, 5, 4, 3, 2, 1])
    assert S.uncertainty(v, m) == S.uncertainty(perm[v], m)


def test_single_view_label_is_undefined():
    assert S.uncertainty(np.ones(100, int), np.arange(100) + 1) == -1.0


def test_face_score_finds_shifted_match_and_rejects_low_overlap():
    model = np.zeros((40, 60), np.int32)
    model[5:30, 10:50] = 1
    model[5:30, 20:30] = 2
    model[5:15, 35:45] = 3
    view = np.zeros((25, 20), np.int32)
    view[:, :] = 7
    view[:, 5:15] = 8  # = model columns 15..35 shifted by 15
    assert S.face_score(view, model, slack=3) > 0.9
    assert S.face_score(np.zeros((5, 5), np.int32), model, slack=3) == -1.0


def test_decide_is_140_rule():
    assert S.decide({0: 0.5, 90: 0.39}) == 0
    assert S.decide({0: 0.5, 90: 0.41}) is None
    assert S.decide({0: 0.29, 90: 0.0}) is None


def test_majority_half_rule():
    fine = np.zeros((4, 8), np.int32)
    fine[:, :4] = 3
    fine[:2, 4:] = 5
    fine[2:3, 4:] = 6
    out = S.majority(fine, 4)
    assert out.tolist() == [[3, 5]]
    fine[:, 4:] = 0
    fine[0, 4:] = 6
    assert S.majority(fine, 4).tolist() == [[3, 0]]


def test_type_name_strips_revit_instance_suffixes():
    src = (Path(__file__).resolve().parent / 'rays_type.py').read_text(encoding='utf-8')
    block = src[src.index('SUFFIX = '):src.index('verts, tris, tri_lab')]
    ns = {'re': __import__('re')}
    exec(block, ns)
    tn = ns['type_name']
    assert tn('Прямоугольный импост Rectangular mul_62a1e5a') == 'Прямоугольный импост Rectangular mul'
    assert tn('(SC)-Batten_windows.2 (SC)-Batten_RAL 7021_кровля_971b340') == '(SC)-Batten_windows.2 (SC)-Batten_RAL 7021_кровля'
    assert tn('Ограждение Wall(h-900,PR-50) [12618195]_[8198748].001') == 'Ограждение Wall(h-900,PR-50)'
    assert tn('Системная панель Стемалит [15168820]') == 'Системная панель Стемалит'
