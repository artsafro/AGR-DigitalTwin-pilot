"""Research-only 2D line matcher; no design or finish authority."""

import numpy as np


def mesh_edges(depth, normals):
    occupied = np.isfinite(depth)
    finite_depth = np.where(occupied, depth, 0)
    result = np.zeros_like(occupied)
    for before, after in ((np.s_[:-1, :], np.s_[1:, :]), (np.s_[:, :-1], np.s_[:, 1:])):
        both = occupied[before] & occupied[after]
        jump = np.abs(finite_depth[before] - finite_depth[after]) > 0.03
        crease = (normals[before] * normals[after]).sum(axis=2) < np.cos(np.pi / 6)
        transitions = (occupied[before] ^ occupied[after]) | (both & (jump | crease))
        result[after] |= transitions & occupied[after]
        result[before] |= transitions & occupied[before] & ~occupied[after]
    return result


def nearby(mask, radius=2):
    h, w = mask.shape
    expanded = np.pad(mask, radius)
    near = np.zeros_like(mask)
    for y in range(2 * radius + 1):
        for x in range(2 * radius + 1):
            near |= expanded[y:y + h, x:x + w]
    return near


def face_score(view, model, occupied, slack):
    """Search offsets on the metric raster without painting synthetic crop edges."""
    rows = np.flatnonzero(view.any(axis=1))
    if not len(rows) or not occupied.any() or not model.any():
        return -1.0
    h, w = view.shape
    # Allow the measured view region to overhang the native top/bottom.
    pad_y = h + 2
    model = np.pad(model, ((pad_y, pad_y), (slack, slack)))
    presence = np.pad(occupied.any(axis=1)[:, None] & occupied, ((pad_y, pad_y), (slack, slack)))
    hits_view = nearby(view)
    count_view = np.count_nonzero(view)
    best = -1.0
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
            precision = np.count_nonzero(view & nearby(crop)) / count_view
            recall = np.count_nonzero(crop & hits_view) / count_model
            score = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
            best = max(best, score)
    return best


def decide(scores):
    ranked = sorted(scores, key=scores.__getitem__, reverse=True)
    if len(ranked) < 2:
        return None
    best, runner_up = ranked[:2]
    return best if scores[best] >= 0.30 and scores[best] - scores[runner_up] >= 0.10 else None
