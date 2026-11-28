"""#159 unit checks for the frozen decision rule (no PDFs, no Drive).

new-case: docs/research/autoresearch-view-face-realism/test_run.py - #159 decision-rule unit test
"""
import runpy
from pathlib import Path

M = runpy.run_path(str(Path(__file__).with_name('run.py')), run_name='t159')


def wall(az, W, H, z0=0.0):
    return {'az': az, 'W': W, 'H': H, 'z0': z0}


def test_unique_ground_answer_and_side():
    walls = [wall(0, 20, 10), wall(90, 40, 10), wall(180, 20, 10, z0=8.0)]
    ans, cand = M['decide']({'W': 20.3, 'H': 10.2}, walls, True)
    assert cand == [0]
    assert ans is None  # wall 2 (not ground) is a 2-tau neighbour -> abstain
    ans, _ = M['decide']({'W': 40.0, 'H': 10.0}, walls, True)
    assert ans == 1 and M['outcome'](ans, walls, 90) == 'correct'
    assert M['outcome'](ans, walls, 270) == 'wrong'


def test_azdiff_wraps():
    assert M['azdiff'](356, 4) == 8
    assert M['outcome'](None, [], 0) == 'abstain'
