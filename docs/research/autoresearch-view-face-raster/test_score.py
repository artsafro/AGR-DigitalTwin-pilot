import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score  # noqa: E402


def _pattern(n=200, seed=1):
    rng = np.random.default_rng(seed)
    p = np.zeros(n)
    for a in rng.choice(n - 12, 14, replace=False):
        p[a:a + int(rng.integers(5, 12))] = 1.0
    return p


def test_translated_crop_found_at_its_offset():
    face = _pattern()
    s, off = score.slide(face[40:120], face)
    assert s > 0.99 and off == 40


def test_displaced_pattern_scores_worse():
    face = _pattern()
    other = _pattern(seed=7)
    assert score.slide(other[40:120], face)[0] < score.slide(face[40:120], face)[0]


def test_distinct_candidate_answers_and_equal_candidates_abstain():
    assert score.decide({90: 0.9, 270: 0.4, 0: -1.0, 180: -1.0}, 90)["outcome"] == "correct"
    assert score.decide({90: 0.9, 270: 0.4, 0: -1.0, 180: -1.0}, 270)["outcome"] == "wrong"
    assert score.decide({90: 0.8, 270: 0.75, 0: -1.0, 180: -1.0}, 90)["outcome"] == "abstain"
    assert score.decide({90: 0.25, 270: -1.0, 0: -1.0, 180: -1.0}, 90)["outcome"] == "abstain"


def test_empty_or_flat_view_and_too_wide_view_are_impossible():
    face = _pattern()
    assert score.slide(np.zeros(50), face)[0] == -1.0
    assert score.slide(np.ones(50), face)[0] == -1.0
    assert score.slide(_pattern(300), face)[0] == -1.0
    assert score.slide(face[:50], np.zeros(200))[0] == -1.0


def test_width_baseline_abstains_on_equal_widths():
    widths = {0: 16.3, 90: 88.9, 180: 16.3, 270: 88.9}
    assert score.decide_width(89.0, widths, 90)["outcome"] == "abstain"
    assert score.decide_width(89.0, {0: 16.3, 90: 88.9}, 90)["outcome"] == "correct"


def test_drop_tall_runs_keeps_window_sized_runs_only():
    import sheet
    m = np.zeros((60, 3), bool)
    m[5:20, 0] = True   # 15 px window run: kept
    m[0:40, 1] = True   # 40 px cladding band: dropped
    m[30:56, 2] = True  # 26 px: dropped at max 25
    out = sheet.drop_tall_runs(m, 25)
    assert out[:, 0].sum() == 15 and out[:, 1].sum() == 0 and out[:, 2].sum() == 0
