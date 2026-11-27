"""#149 OBSERVE scoring: finish-partition agreement between a view label raster and a model type raster.

Research only; no design or finish authority.
"""
import numpy as np


def uncertainty(v, m):
    """Chance-corrected U(V|M) = (I - (|V|-1)(|M|-1)/(2N)) / H(V) in nats over paired label vectors (all > 0)."""
    n = v.size
    if n == 0:
        return -1.0
    kv, km = int(v.max()) + 1, int(m.max()) + 1
    joint = np.bincount(v.astype(np.int64) * km + m, minlength=kv * km).reshape(kv, km).astype(float) / n
    pv, pm = joint.sum(1), joint.sum(0)
    pv, pm = pv[pv > 0], pm[pm > 0]
    hv = -float(np.sum(pv * np.log(pv)))
    if hv <= 0:
        return -1.0
    nz = joint > 0
    hm = -float(np.sum(pm * np.log(pm)))
    mi_nats = hv + hm + float(np.sum(joint[nz] * np.log(joint[nz])))
    return (mi_nats - (pv.size - 1) * (pm.size - 1) / (2.0 * n)) / hv


def face_score(view, model, slack, shifts=3, min_overlap=0.30):
    """Max U over horizontal offsets (±slack px) and vertical shifts; view top row aligned to model top hit."""
    filled = view > 0
    total = int(np.count_nonzero(filled))
    if not total or not (model > 0).any():
        return -1.0
    h, w = view.shape
    pad_y = h + 2 * shifts + 2
    mod = np.pad(model, ((pad_y, pad_y), (slack, slack)))
    best = -1.0
    for x in range(mod.shape[1] - w + 1):
        cols = mod[:, x:x + w]
        top = np.flatnonzero((cols > 0).any(axis=1))
        if not len(top):
            continue
        for s in range(-shifts, shifts + 1):
            y = int(top[0]) + s
            crop = cols[y:y + h]
            both = filled & (crop > 0)
            k = int(np.count_nonzero(both))
            if k < min_overlap * total:
                continue
            best = max(best, uncertainty(view[both], crop[both]))
    return best


def decide(scores):
    """#140 decide, unchanged: best >= 0.30 and margin >= 0.10, else abstain (None)."""
    ranked = sorted(scores, key=scores.__getitem__, reverse=True)
    if len(ranked) < 2:
        return None
    best, runner_up = ranked[:2]
    return best if scores[best] >= 0.30 and scores[best] - scores[runner_up] >= 0.10 else None


def majority(fine, k):
    """Reduce a fine label raster by k x k blocks: mode of non-zero sub-pixels if they are >= half the block."""
    h, w = fine.shape[0] // k, fine.shape[1] // k
    blocks = fine[:h * k, :w * k].reshape(h, k, w, k).transpose(0, 2, 1, 3).reshape(h, w, k * k)
    out = np.zeros((h, w), fine.dtype)
    for j in range(h):
        for i in range(w):
            b = blocks[j, i]
            b = b[b > 0]
            if 2 * b.size >= k * k:
                vals, cnt = np.unique(b, return_counts=True)
                out[j, i] = vals[np.argmax(cnt)]
    return out
