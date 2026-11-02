"""Independent scalar oracle for the Methods render score (SSIM, 7x7 box window).

new-case: characterization tests only. Expected values come from explicit sliding windows, math.fsum and
population variance/covariance divided by k*k; production _box/ssim are never used to build an expectation.

Acceptance table (all GREEN characterization, no threshold, no quality verdict):
  identical 7x7 and 9x11 arrays                      -> 1
  constant a=.25 vs b=.75, k=7                       -> (2ab+c1)/(a^2+b^2+c1)
  nonuniform 7x7, 8x9, 9x11 pairs, k=7               -> oracle mean over (H-6)*(W-6) windows, abs 1e-12
  swapped inputs                                     -> same score
  one-sided altered border pixels                    -> oracle agreement
  inputs                                             -> unchanged
  render_score on two RGB PNG view pairs             -> per_view rounded 5, value = mean of rounded,
                                                        independent of dict insertion order; wrong luma
                                                        weights / first-view-only give a different value
"""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools" / "methods"
K = 7
C1, C2 = 0.01**2, 0.03**2
TOL = 1e-12


def _load():
    if "methods_metrics" in sys.modules:
        return sys.modules["methods_metrics"]
    sys.path.insert(0, str(TOOLS))
    spec = importlib.util.spec_from_file_location("methods_metrics", TOOLS / "methods_metrics.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["methods_metrics"] = mod
    spec.loader.exec_module(mod)
    return mod


mm = _load()


def oracle_ssim(a, b, k=K):
    """Mean SSIM over every fully valid k x k window; a, b are lists of rows of floats."""
    h, w = len(a), len(a[0])
    scores = []
    for i in range(h - k + 1):
        for j in range(w - k + 1):
            xs = [a[i + p][j + q] for p in range(k) for q in range(k)]
            ys = [b[i + p][j + q] for p in range(k) for q in range(k)]
            n = k * k
            mx, my = math.fsum(xs) / n, math.fsum(ys) / n
            vx = math.fsum((x - mx) ** 2 for x in xs) / n
            vy = math.fsum((y - my) ** 2 for y in ys) / n
            cv = math.fsum((x - mx) * (y - my) for x, y in zip(xs, ys)) / n
            scores.append(((2 * mx * my + C1) * (2 * cv + C2)) / ((mx * mx + my * my + C1) * (vx + vy + C2)))
    assert len(scores) == (h - k + 1) * (w - k + 1)
    return math.fsum(scores) / len(scores)


def pair(h, w):
    """Frozen nonuniform [0,1] pair: different border and interior values."""
    a = [[((i * 7 + j * 13 + i * j) % 17) / 16 for j in range(w)] for i in range(h)]
    b = [[((i * 5 + j * 3 + 2 * i * j + 4) % 19) / 18 for j in range(w)] for i in range(h)]
    for i in range(h):
        for j in range(w):
            if i in (0, h - 1) or j in (0, w - 1):
                b[i][j] = 1.0 - b[i][j]
    return a, b


@pytest.mark.parametrize("shape", [(7, 7), (9, 11)])
def test_identical_arrays_score_one(shape):
    a, _ = pair(*shape)
    assert mm.ssim(np.array(a), np.array(a)) == pytest.approx(1.0, abs=TOL)
    assert oracle_ssim(a, a) == pytest.approx(1.0, abs=TOL)


def test_constant_pair_closed_form():
    a, b = 0.25, 0.75
    want = (2 * a * b + C1) / (a * a + b * b + C1)
    got = mm.ssim(np.full((7, 7), a), np.full((7, 7), b))
    assert got == pytest.approx(want, abs=TOL)
    assert oracle_ssim([[a] * 7] * 7, [[b] * 7] * 7) == pytest.approx(want, abs=TOL)


@pytest.mark.parametrize("shape", [(7, 7), (8, 9), (9, 11)])
def test_nonuniform_pairs_match_oracle_swap_and_inputs_unchanged(shape):
    a, b = pair(*shape)
    na, nb = np.array(a), np.array(b)
    ca, cb = na.copy(), nb.copy()
    want = oracle_ssim(a, b)
    assert want < 0.999  # the pair is genuinely different: the comparison is not vacuous
    assert mm.ssim(na, nb) == pytest.approx(want, abs=TOL)
    assert mm.ssim(nb, na) == pytest.approx(want, abs=TOL)
    assert (na == ca).all() and (nb == cb).all()


def test_one_sided_border_changes_match_oracle():
    a, b = pair(9, 11)
    base = oracle_ssim(a, b)
    a2 = [row[:] for row in a]
    for i, j in [(0, 0), (0, 5), (8, 10), (4, 0), (4, 10), (8, 3)]:
        a2[i][j] = 1.0 - a2[i][j]
    want = oracle_ssim(a2, b)
    assert abs(want - base) > 1e-4  # border pixels do enter some window
    assert mm.ssim(np.array(a2), np.array(b)) == pytest.approx(want, abs=TOL)


def _png_pairs(tmp_path):
    from PIL import Image

    def make(h, w, seed):
        return [[[(i * 37 + j * 11 + seed * 5) % 256, (i * 3 + j * 29 + seed * 17) % 256,
                  (i * 53 + j * 7 + seed * 41) % 256] for j in range(w)] for i in range(h)]

    refs, rens, ref_px, ren_px = {}, {}, {}, {}
    for name, (h, w, seed) in {"east": (8, 9, 1), "west": (9, 10, 2)}.items():
        ref = make(h, w, seed)
        ren = [[px[:] for px in row] for row in ref]
        for i in range(h):
            for j in range(w):
                r, g, bl = ref[i][j]
                if name == "east":
                    ren[i][j] = [r, 255 - g, bl] if (i + j) % 3 == 0 else [r, g, bl]
                    if i == j == 0:  # rounding witness: rounded-mean .74500 vs raw-mean .74499
                        ren[i][j][0] -= 1
                else:
                    ren[i][j] = [255 - r, g, (bl + 90) % 256] if (i * j) % 4 == 1 else [r, g, bl]
        for d, px, store in ((refs, ref, ref_px), (rens, ren, ren_px)):
            path = tmp_path / f"{'ref' if d is refs else 'ren'}_{name}.png"
            Image.fromarray(np.array(px, dtype=np.uint8)).save(path)
            d[name] = path
            store[name] = px
    return refs, rens, ref_px, ren_px


def _luma_list(px, weights=(0.299, 0.587, 0.114)):
    wr, wg, wb = weights
    return [[(wr * p[0] + wg * p[1] + wb * p[2]) / 255 for p in row] for row in px]


def test_render_score_per_view_rounding_and_mean_match_independent_luma(tmp_path):
    refs, rens, ref_px, ren_px = _png_pairs(tmp_path)
    want = {v: round(oracle_ssim(_luma_list(ref_px[v]), _luma_list(ren_px[v])), 5) for v in ("east", "west")}
    value = round(math.fsum(want.values()) / 2, 5)

    got = mm.render_score(refs, rens)
    assert got["per_view"] == pytest.approx(want, abs=1e-9)
    assert got["value"] == pytest.approx(value, abs=1e-9)
    for v in want:  # rounded to 5 places exactly
        assert got["per_view"][v] == round(got["per_view"][v], 5)

    # insertion order of both dicts does not matter
    rev = mm.render_score(dict(reversed(list(refs.items()))), dict(reversed(list(rens.items()))))
    assert rev["value"] == got["value"] and rev["per_view"] == got["per_view"]

    # detectability: wrong luma weights or one view only give a different value
    assert want["east"] != want["west"]
    for wrong in ((1 / 3, 1 / 3, 1 / 3), (0.114, 0.587, 0.299)):
        alt = round(math.fsum(round(oracle_ssim(_luma_list(ref_px[v], wrong), _luma_list(ren_px[v], wrong)), 5)
                              for v in ("east", "west")) / 2, 5)
        assert abs(alt - value) > 1e-4
    assert abs(want["east"] - value) > 1e-4 and abs(want["west"] - value) > 1e-4

    # aggregation order: mean of rounded per-view scores differs from rounded raw mean
    raw = [oracle_ssim(_luma_list(ref_px[v]), _luma_list(ren_px[v])) for v in ("east", "west")]
    raw_mean = round(math.fsum(raw) / 2, 5)
    assert raw_mean != value
    assert got["value"] == value and got["value"] != raw_mean
