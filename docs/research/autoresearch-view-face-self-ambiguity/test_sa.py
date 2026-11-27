"""Regression tests for the #143 self-ambiguity gate (synthetic, no DCC inputs)."""
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sa  # noqa: E402

R141 = "3716f5395667c17f8be8737313952aaa6285615c"


def upstream_1d():
    src = subprocess.check_output(["git", "show", f"{R141}:docs/research/autoresearch-view-face-raster/score.py"])
    mod = ModuleType("score141")
    exec(compile(src, "score141", "exec"), vars(mod))
    return mod


def periodic(n, period=30, width=8):
    a = np.zeros(n)
    for s in range(5, n - width, period):
        a[s:s + width] = 1.0
    return a


def test_periodic_crop_on_long_face_fires():
    s = upstream_1d()
    face = periodic(380)
    view = face[95:139]  # 4.4 m crop of a repeating rhythm
    per = sa.slide_all(s, view, face, s.SLACK_PX)
    fires, s2 = sa.gate(float(per.max()), per, len(view))
    assert fires and s2 > 0.9


def test_unique_crop_does_not_fire():
    s = upstream_1d()
    rng = np.random.default_rng(143)
    face = (rng.random(380) > 0.7).astype(float)
    view = face[95:139]
    per = sa.slide_all(s, view, face, s.SLACK_PX)
    fires, _ = sa.gate(float(per.max()), per, len(view))
    assert not fires


def test_full_view_has_no_far_offset():
    s = upstream_1d()
    face = periodic(380)
    per = sa.slide_all(s, face, face, s.SLACK_PX)
    assert sa.gate(float(per.max()), per, len(face)) == (False, None)


def test_per_offset_max_equals_upstream_slide():
    s = upstream_1d()
    face = periodic(200, period=23, width=5)
    view = face[40:90] + 0.01 * np.arange(50) / 50
    best, _ = s.slide(view, face)
    assert abs(sa.slide_all(s, view, face, s.SLACK_PX).max() - best) < 1e-12


def test_separation_floor():
    assert sa.separation(8) == 10 and sa.separation(44) == 22 and sa.separation(45) == 23
