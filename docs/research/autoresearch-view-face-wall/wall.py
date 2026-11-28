"""#153 OBSERVE: wall planes from first-hit depth, D localisation profile and the W1 same-wall gate.

new-case: docs/research/autoresearch-view-face-wall/wall.py - #153 wall-level view->face scoring

Research only; no design or finish authority. `uncertainty` comes from the pinned #149 score.py.
"""
from collections import Counter

import numpy as np


def column_depth(depth):
    """Median first-hit depth per column (NaN where the column has no hit)."""
    out = np.full(depth.shape[1], np.nan)
    for i in range(depth.shape[1]):
        col = depth[:, i]
        col = col[np.isfinite(col)]
        if col.size:
            out[i] = float(np.median(col))
    return out


def planes(coldep, gap):
    """Cluster distinct column depths (0.01 m) split at gaps > `gap`; -1 for empty columns."""
    ids = np.full(coldep.shape, -1, np.int32)
    ok = np.isfinite(coldep)
    if not ok.any():
        return ids
    vals = np.unique(np.round(coldep[ok], 2))
    cluster = np.concatenate([[0], np.cumsum(np.diff(vals) > gap)])
    lut = dict(zip(vals.tolist(), cluster.tolist()))
    ids[ok] = [lut[v] for v in np.round(coldep[ok], 2).tolist()]
    return ids


def interval_wall(colplane, a, b):
    """Mode plane id over model columns [a, b) clipped to the model; ties -> lower id; -1 if no plane."""
    seg = colplane[max(a, 0):max(min(b, colplane.size), 0)]
    seg = seg[seg >= 0]
    if not seg.size:
        return -1
    vals, cnt = np.unique(seg, return_counts=True)
    return int(vals[np.argmax(cnt)])


def profile(view, model, slack, uncertainty, shifts=3, min_overlap=0.30):
    """U per horizontal offset of the slack-padded model, exactly the #149 face_score loop; -1 = invalid."""
    filled = view > 0
    total = int(np.count_nonzero(filled))
    h, w = view.shape
    pad_y = h + 2 * shifts + 2
    mod = np.pad(model, ((pad_y, pad_y), (slack, slack)))
    prof = np.full(max(mod.shape[1] - w + 1, 0), -1.0)
    if not total or not (model > 0).any():
        return prof
    for x in range(prof.size):
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
            prof[x] = max(prof[x], uncertainty(view[both], crop[both]))
    return prof


def localise(prof, colplane, slack, w, tau):
    """W0 wall at the first argmax and W1 wall (None if near-best offsets disagree on the wall)."""
    if not prof.size or prof.max() < 0:
        return None, None, None, []
    best = int(np.argmax(prof))
    near = np.flatnonzero(prof >= prof[best] - tau)
    walls = sorted({interval_wall(colplane, int(x) - slack, int(x) - slack + w) for x in near})
    w0 = interval_wall(colplane, best - slack, best - slack + w)
    w1 = w0 if len(walls) == 1 else None
    return best - slack, w0, w1, walls


def outcome(side_pick, gt_az, wall_pick, gt_wall):
    if side_pick is None or wall_pick is None:
        return 'abstain'
    return 'correct' if side_pick == gt_az and wall_pick == gt_wall else 'wrong'


def group(row):
    if row['case'] == 'mirror':
        return 'mirror'
    if row['case'].startswith('partial'):
        return 'synthetic_crop'
    return row['case']


def summarize(rows, key, only=None):
    out = {}
    for name in ('full', 'synthetic_crop', 'fragment', 'fragment_top_cut', 'mirror'):
        c = Counter(r[key] for r in rows if group(r) == name and (only is None or only(r)))
        answered = c['correct'] + c['wrong']
        out[name] = dict(correct=c['correct'], wrong=c['wrong'], abstain=c['abstain'],
                         not_exercised=c['not_exercised'],
                         accuracy=round(c['correct'] / answered, 4) if answered else None)
    return out


def verdict(rows, w1, w1_nt):
    fired = sum(1 for r in rows if r['W0'] in ('correct', 'wrong') and r['W1'] == 'abstain')
    # #2075: a nontrivial crop is exercised only when W1 answers; D/W1 abstentions do not measure the wall.
    nt_rows = [r for r in rows if group(r) == 'synthetic_crop' and r['nontrivial']]
    nt_ex = sum(1 for r in nt_rows if r['W1'] in ('correct', 'wrong'))
    nt_ab = sum(1 for r in nt_rows if r['W1'] == 'abstain')
    checks = dict(full_wrong_0=w1['full']['wrong'] == 0,
                  fragment_wrong_0=w1['fragment']['wrong'] + w1['fragment_top_cut']['wrong'] == 0,
                  crop_wrong_le1=w1['synthetic_crop']['wrong'] <= 1,
                  crop_correct_ge30=w1['synthetic_crop']['correct'] >= 30,
                  nontrivial_wrong_0=w1_nt['synthetic_crop']['wrong'] == 0)
    if not all(checks.values()):
        hyp = 'refuted'
    elif nt_ex < 5:
        hyp = 'inconclusive'
    else:
        hyp = 'confirmed'
    return hyp, checks, dict(gate_fired_rows=fired, gate_measured=fired > 0, nontrivial_crops=len(nt_rows),
                             nontrivial_crops_exercised=nt_ex, nontrivial_crops_abstained=nt_ab,
                             nontrivial_abstain_rate=round(nt_ab / len(nt_rows), 4) if nt_rows else None)
