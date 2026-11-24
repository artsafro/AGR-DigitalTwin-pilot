from pathlib import Path
import runpy

import numpy as np
import pytest


def replay():
    path = Path(__file__).with_name('replay.py')
    assert path.is_file(), 'width experiment is not implemented'
    return runpy.run_path(str(path))


def test_profile_width_and_injected_controls():
    m = replay()
    runs = m['pinned']()[2]
    profiles = np.full((3, 128, 3), 180, np.uint8)
    # Synthetic: three complete 8 px seams, and one incomplete edge run.
    for a, b in [(0, 2), (25, 33), (55, 63), (85, 93)]:
        profiles[:, a:b] = 40
    raw = profiles.tobytes()
    result = m['measure'](profiles, runs, 1.0)
    assert result['clean'] == {'width_mm': 8.0, 'width_px': 8.0, 'runs': [3, 3, 3]}
    assert result['widen']['width_mm'] == 16
    assert result['widen']['changed_px'] == 84
    assert result['brightness']['width_mm'] == 8
    assert result['brightness']['changed_px'] == 384
    assert profiles.tobytes() == raw


def test_solid_profile_is_not_measured():
    m = replay()
    with pytest.raises(ValueError, match='not measured'):
        m['measure'](np.full((3, 128, 3), 50, np.uint8), m['pinned']()[2], 1.0)


@pytest.mark.parametrize(('status', 'pairs', 'controls', 'expected'), [
    ('complete', [2, 2, 2], True, 'confirmed'),
    ('complete', [0, 0, 0], True, 'refuted'),
    ('complete', [2, 2, 2], False, 'inconclusive'),
    ('complete', [2, 1, 2], True, 'inconclusive'),
    ('budget_stop', [2], True, 'inconclusive'),
])
def test_verdict_is_separate_from_run_status(status, pairs, controls, expected):
    rows = [{'errors_mm': {'v007': x, 'v010': 0}, 'controls_ok': controls} for x in pairs]
    assert replay()['classify'](status, rows)['hypothesis'] == expected
