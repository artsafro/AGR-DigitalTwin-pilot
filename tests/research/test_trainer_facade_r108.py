"""Synthetic controls for the OBSERVE replay, not trainer acceptance."""
from pathlib import Path
import runpy

import pytest


REPLAY = Path(__file__).resolve().parents[2] / 'docs/research/trainer_facade_r108/replay.py'


def test_ablation_uses_exact_family_and_preserves_baseline():
    r = runpy.run_path(str(REPLAY))
    r107 = r['prior_module']()
    rows = [(1, 'Базовая стена Вентфасад 250 250 к', [0, 0, 0], [2, 1, 1]),
            (2, 'Базовая стена Вентфасад 250 2500 к', [0, 0, 0], [1, 1, 1]),
            (3, 'Ограждение glass', [0, 0, 0], [3, 1, 1])]
    assert r['select'](r107, rows, (0, 1), ablate=False)['ids'] == [1, 2]
    assert r['select'](r107, rows, (0, 1), ablate=True) == {
        'ids': [2], 'bounds_m': [[0, 0, 0], [1, 1, 1]]}
    assert r['select'](r107, rows, None, ablate=True) is None


@pytest.mark.parametrize(('a', 'b', 'direction', 'expected'), [
    (True, 'pass', True, 'confirmed'), (True, 'fail', False, 'refuted'),
    (False, 'pass', True, 'inconclusive'), (True, 'pass', False, 'inconclusive'),
])
def test_verdict_requires_active_accepted_control(a, b, direction, expected):
    r = runpy.run_path(str(REPLAY))
    pair = {'status': 'complete', '63A': {'eligible': a, 'native': {'status': 'pass'}},
            '63B': {'eligible': True, 'native': {'status': b}, 'direction_ok': direction}}
    assert r['verdict']([pair] * 3, 'complete') == expected
    assert r['verdict']([pair] * 2, 'complete') == 'inconclusive'
