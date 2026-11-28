"""Unit checks for the #161 glass-pattern scorer (pure functions, no PDF/Blender inputs)."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip('pymupdf')
_spec = importlib.util.spec_from_file_location('ar161_run', Path(__file__).with_name('run.py'))
run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run)

P = dict(min_overlap=0.8, tau=0.30, delta=0.10)


def test_best_offset_finds_embedded_view():
    rng = np.random.default_rng(0)
    model = (rng.random((10, 60)) > 0.6).astype(float)
    view = model[:, 20:35].copy()
    score, off = run.best_offset(view, model, P)
    assert off == 20 and score == pytest.approx(1.0)


def test_blank_view_abstains():
    rng = np.random.default_rng(1)
    masks = {az: (rng.random((10, 40)) > 0.5).astype(float) for az in (0, 90, 180, 270)}
    blank = np.zeros((10, 12))
    scores = {az: run.best_offset(blank, m, P) for az, m in masks.items()}
    assert run.decide(scores, P)[0] is None


def test_margin_rule_abstains_on_near_tie():
    scores = {0: (0.70, 0), 330: (0.65, 0), 90: (0.20, 0)}
    ans, top, margin, best = run.decide(scores, P)
    assert ans is None and best == 0 and margin == pytest.approx(0.05)


def test_outcome_labels():
    assert run.outcome(None, None) == 'diagnostic'
    assert run.outcome(None, [330]) == 'abstain'
    assert run.outcome(0, [330]) == 'wrong'
    assert run.outcome(270, [240, 270]) == 'correct'
