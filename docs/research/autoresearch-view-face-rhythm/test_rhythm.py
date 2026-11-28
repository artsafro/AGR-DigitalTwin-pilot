import runpy
from pathlib import Path

import numpy as np

GATE = runpy.run_path(str(Path(__file__).with_name('run.py')))['rhythm_gate']
PATTERN = np.tile([0., 0., 1., 1., 1., 0., 1., 0.], (3, 1))


def test_gain_and_offset_do_not_change_identical_rhythm():
    answer, score = GATE('wall', 'full', PATTERN * 0.6 + 0.2, PATTERN)
    assert answer == 'wall'
    assert score > 0.999


def test_same_span_and_amount_with_opposite_rhythm_abstains():
    answer, score = GATE('wall', 'full', 1 - PATTERN, PATTERN)
    assert answer is None
    assert score < -0.999


def test_constant_and_missing_profiles_abstain():
    assert GATE('wall', 'full', np.zeros_like(PATTERN), PATTERN) == (None, None)
    assert GATE('wall', 'full', PATTERN, None) == (None, None)


def test_no_answer_creation_and_fragment_parity():
    assert GATE(None, 'full', PATTERN, PATTERN) == (None, None)
    assert GATE('wall', 'fragment', 1 - PATTERN, PATTERN) == ('wall', None)
