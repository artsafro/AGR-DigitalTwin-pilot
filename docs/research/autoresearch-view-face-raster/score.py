"""Research-only 1D window-rhythm view->face scorer (#141, OBSERVE). No design or finish authority.

Frozen before scoring: gaussian smoothing s=1.5 px, NCC, slide with slack 6 px (0.6 m),
answer only when best >= 0.30 and margin to the best other face >= 0.10 (#139 thresholds, unchanged).
"""
import math

import numpy as np

MIN_SCORE = 0.30
TAU_MARGIN = 0.10
SLACK_PX = 6


def smooth(a, s=1.5):
    r = int(3 * s)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / s) ** 2)
    return np.convolve(np.asarray(a, float), k / k.sum(), mode="same")


def ncc(a, b):
    a, b = a - a.mean(), b - b.mean()
    den = math.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / den) if den > 1e-9 else 0.0


def slide(view, face, slack=SLACK_PX):
    """Best NCC of the view profile over every offset of the face profile; -1 when impossible/empty."""
    view, face = np.asarray(view, float), np.asarray(face, float)
    lv, lf = len(view), len(face)
    if lv == 0 or lv > lf + 2 * slack or not view.any() or not face.any() or np.ptp(view) == 0:
        return -1.0, None
    fp = np.concatenate([np.zeros(slack), face, np.zeros(slack)])
    sv = smooth(view)
    best, off = -2.0, None
    for o in range(0, lf + 2 * slack - lv + 1):
        s = ncc(sv, smooth(fp[o:o + lv]))
        if s > best:
            best, off = s, o - slack
    return best, off


def decide(scores, gt):
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    (b, sb), (_, s2) = ranked[0], ranked[1]
    out = {"best": b, "score": round(sb, 4), "margin": round(sb - s2, 4)}
    if sb < MIN_SCORE or sb - s2 < TAU_MARGIN:
        return {**out, "answer": None, "outcome": "abstain"}
    return {**out, "answer": b, "outcome": "correct" if b == gt else "wrong"}


def decide_width(width_m, widths, gt):
    """#139 V0 baseline: nearest face width, abstain when two faces within 3 % or error > 15 %."""
    e = {f: abs(width_m - w) / w for f, w in widths.items()}
    r = sorted(e.items(), key=lambda kv: (kv[1], kv[0]))
    if r[0][1] > 0.15 or r[1][1] - r[0][1] < 0.03:
        return {"answer": None, "best": r[0][0], "err": round(r[0][1], 4), "outcome": "abstain"}
    return {"answer": r[0][0], "best": r[0][0], "err": round(r[0][1], 4),
            "outcome": "correct" if r[0][0] == gt else "wrong"}
