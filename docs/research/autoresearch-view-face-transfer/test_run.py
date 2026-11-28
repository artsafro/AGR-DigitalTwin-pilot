"""#151 unit checks for the pre-declared G diagnostic wrapper (no inputs, no Blender)."""
import importlib.util
import types
from pathlib import Path

import numpy as np

spec = importlib.util.spec_from_file_location('r151', Path(__file__).with_name('run.py'))
assert spec is not None and spec.loader is not None
r151 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r151)


def _stub():
    calls = []

    def face_score(view, model, slack):
        calls.append(view.shape[1])
        return -1.0 if view.shape[1] > model.shape[1] + 2 * slack else float(view.shape[1]) / 100

    def decide(scores):
        ranked = sorted(scores, key=scores.__getitem__, reverse=True)
        best, second = ranked[:2]
        return best if scores[best] >= 0.30 and scores[best] - scores[second] >= 0.10 else None
    return types.SimpleNamespace(face_score=face_score, decide=decide), calls


def test_g_equals_d_when_view_fits():
    S, calls = _stub()
    log = []
    wrapped = r151.g_wrap(S, log)
    d = wrapped(np.ones((5, 40), np.int32), np.ones((5, 50), np.int32), 3)
    assert d == 0.40 and log == [(0.4, 0.4, 0)] and calls == [40]


def test_g_windows_wider_view_gap_free():
    S, calls = _stub()
    log = []
    wrapped = r151.g_wrap(S, log)
    view = np.zeros((6, 80), np.int32)
    view[2:, :] = 1  # top rows empty: each window is trimmed to its own top row
    d = wrapped(view, np.ones((6, 50), np.int32), 3)
    assert d == -1.0
    assert log[0][1] == 0.50 and log[0][2] == 1
    assert calls[1:] == [50] * len(range(0, 80 - 50 + 1, 7))


def test_attach_g_parity_and_permute_stride():
    S, _ = _stub()
    faces = [0, 90]
    rows = [dict(scores={'0': 0.9, '90': 0.1}, gt_az=0, outcome='correct')]
    log = [(0.9, 0.9, 0), (0.1, 0.1, 0), (0.9, 0.9, 0), (0.1, 0.1, 0)]
    r151.attach_g(rows, log, faces, True, S)
    assert rows[0]['G'] == 'correct' and rows[0]['G_windowed'] == 0
