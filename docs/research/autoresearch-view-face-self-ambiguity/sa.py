"""#143 self-ambiguity gate (research only, OBSERVE). No design or finish authority.

Frozen before scoring: an answered decision abstains when the winning face scores within TAU of its
best at an offset >= max(MIN_SEP_PX, ceil(view_px / 2)) away from the best offset. Only adds abstentions.
"""
import math

import numpy as np

TAU = 0.10
MIN_SEP_PX = 10  # 1.0 m at 0.1 m/px


def separation(view_px):
    return max(MIN_SEP_PX, math.ceil(view_px / 2))


def self_second(per_offset, view_px):
    """Best score at offsets far from the best offset; None when no such offset exists."""
    arr = np.asarray(per_offset, float)
    if arr.size == 0:
        return None
    i = int(np.argmax(arr))
    far = np.abs(np.arange(arr.size) - i) >= separation(view_px)
    return float(arr[far].max()) if far.any() else None


def gate(best, per_offset, view_px):
    """Return (fires, self2)."""
    s2 = self_second(per_offset, view_px)
    return (s2 is not None and best - s2 < TAU), s2


def slide_all(score_mod, view, face, slack):
    """Per-offset NCC of the #141 1D scorer (same smoothing/padding as score.slide); empty if impossible."""
    view, face = np.asarray(view, float), np.asarray(face, float)
    lv, lf = len(view), len(face)
    if lv == 0 or lv > lf + 2 * slack or not view.any() or not face.any() or np.ptp(view) == 0:
        return np.zeros(0)
    fp = np.concatenate([np.zeros(slack), face, np.zeros(slack)])
    sv = score_mod.smooth(view)
    return np.array([score_mod.ncc(sv, score_mod.smooth(fp[o:o + lv])) for o in range(0, lf + 2 * slack - lv + 1)])


def face_score_all(score_mod, view, model, occupied, slack):
    """Per-x best of the #140 2D scorer (max over the +-2 row shifts); empty when the face is impossible."""
    rows = np.flatnonzero(view.any(axis=1))
    if not len(rows) or not occupied.any() or not model.any():
        return np.zeros(0)
    h, w = view.shape
    pad_y = h + 2
    model = np.pad(model, ((pad_y, pad_y), (slack, slack)))
    presence = np.pad(occupied.any(axis=1)[:, None] & occupied, ((pad_y, pad_y), (slack, slack)))
    hits_view = score_mod.nearby(view)
    count_view = np.count_nonzero(view)
    out = np.full(model.shape[1] - w + 1, -1.0)
    for x in range(model.shape[1] - w + 1):
        columns = slice(x, x + w)
        top = np.flatnonzero(presence[:, columns].any(axis=1))
        if not len(top):
            continue
        for shift in range(-2, 3):
            y = int(top[0]) - int(rows[0]) + shift
            crop = model[y:y + h, columns]
            count_model = np.count_nonzero(crop)
            if not count_model:
                continue
            precision = np.count_nonzero(view & score_mod.nearby(crop)) / count_view
            recall = np.count_nonzero(crop & hits_view) / count_model
            s = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
            out[x] = max(out[x], s)
    return out
