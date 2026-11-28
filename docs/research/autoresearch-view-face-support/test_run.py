"""Unit checks for the #169 support-refusal runner (no Blender, no native inputs)."""
import importlib.util
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('ar169', HERE / 'run.py')
R = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(R)
D = R.module('score', R.pin('149/score.py'))
V = R.module('score_v', R.variant_source(R.pin('149/score.py')))


def test_variant_is_one_line_change():
    old = R.pin('149/score.py').splitlines()
    new = R.variant_source(R.pin('149/score.py')).splitlines()
    assert len(old) == len(new) and sum(a != b for a, b in zip(old, new)) == 1


def test_one_label_support_refused():
    view = np.full(7, 2, np.int32)
    model = np.arange(7, dtype=np.int32) % 5 + 1
    assert D.uncertainty(view, model) == 1.0  # #168 float residue: H(V)=1e-16 slips past `hv <= 0`
    assert V.uncertainty(view, model) == -1.0


def test_multi_label_scores_identical():
    rng = np.random.default_rng(169)
    for _ in range(50):
        v = rng.integers(1, 5, 300).astype(np.int32)
        m = (v + rng.integers(0, 2, 300)).astype(np.int32)
        assert D.uncertainty(v, m) == V.uncertainty(v, m)


def test_retrace_matches_pinned_face_score():
    rng = np.random.default_rng(7)
    view = rng.integers(0, 3, (12, 20)).astype(np.int32)
    model = rng.integers(0, 4, (30, 40)).astype(np.int32)
    best, labels = R.best_support(D, view, model, 3)
    assert round(best, 9) == round(float(D.face_score(view, model, 3)), 9) and labels >= 1


def _rows():
    return [dict(name=n, clean=dict(d=None, f=f, f_outcome='abstain', exercised=True),
                 blank=dict(f=None), mirror=dict(f=None, f_outcome='abstain', exercised=True))
            for n, f in (('p20 frag 9-10', None), ('p19 6-1', None), ('p18 I-A', 'W08'))]


def test_checks_flags_multi_label_change():
    keep = dict(view='x', state='clean', wall='W1', d=0.5, d_prime=0.5, d_support_labels=3)
    assert all(R.checks(_rows(), [keep]).values())
    bad = dict(keep, d_prime=0.4)
    assert not R.checks(_rows(), [bad])['changed_only_one_label']
    one = dict(keep, d=1.0, d_prime=-1.0, d_support_labels=1)
    assert R.checks(_rows(), [one])['changed_only_one_label']
