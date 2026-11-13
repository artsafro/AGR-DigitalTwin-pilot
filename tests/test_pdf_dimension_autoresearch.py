"""new-case: frozen native dimension research scoring and zero-prediction guard."""
from __future__ import annotations

import importlib.util


def test_zero_prediction_guard():
    name = 'tools.research.pdf_album.dimension_autoresearch'
    assert importlib.util.find_spec(name) is not None, 'frozen research guard is missing'
    from tools.research.pdf_album.dimension_autoresearch import precision_guard
    metrics = {'found': 0, 'correct': 0, 'wrong': 0, 'truth': 6,
               'missed': 6, 'precision': None, 'recall': 0.0}
    assert precision_guard(metrics) == 'zero_prediction_pass'
    assert metrics['precision'] is None
