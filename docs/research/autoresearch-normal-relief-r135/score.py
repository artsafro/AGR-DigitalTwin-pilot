"""#135 scorer: same-camera relief energy ratio per 100 mm cell (frozen in autoresearch-normal-relief-r135.md)."""
from pathlib import Path

import numpy as np
from PIL import Image

CELL = 100
COVER = 0.90
EPS = 1e-4
MIN_CELLS = 4


def _load(path: Path):
    a = np.asarray(Image.open(path).convert('RGBA'), dtype=np.float64) / 255.0
    rgb = a[..., :3]
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    y = lin @ np.array([0.2126, 0.7152, 0.0722])
    return y, a[..., 3] > 0.99


def _sobel(y):
    p = np.pad(y, 1, mode='edge')
    gx = (p[:-2, 2:] + 2 * p[1:-1, 2:] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[1:-1, :-2] + p[2:, :-2])
    gy = (p[2:, :-2] + 2 * p[2:, 1:-1] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[:-2, 1:-1] + p[:-2, 2:])
    return np.hypot(gx, gy)


def shot_score(cand: Path, src: Path, clip_max: float | None = None) -> dict:
    """clip_max (A1): a shot whose masked pixels are clipped (Y >= 0.999) above this fraction in either
    render is not measured; None replays R1 unchanged."""
    yc, mc = _load(cand)
    ys, ms = _load(src)
    clip = max(float((yc[mc] >= 0.999).mean()) if mc.any() else 0.0,
               float((ys[ms] >= 0.999).mean()) if ms.any() else 0.0)
    gc, gs = _sobel(yc), _sobel(ys)
    m = mc & ms
    r, signed = [], []
    h, w = m.shape
    for i in range(0, h - CELL + 1, CELL):
        for j in range(0, w - CELL + 1, CELL):
            mm = m[i:i + CELL, j:j + CELL]
            if mm.mean() < COVER:
                continue
            ec = gc[i:i + CELL, j:j + CELL][mm].mean()
            es = gs[i:i + CELL, j:j + CELL][mm].mean()
            s = float(np.log((ec + EPS) / (es + EPS)))
            signed.append(s)
            r.append(abs(s))
    row: dict = dict(eligible_cells=len(r), masked_px_cand=int(mc.sum()), masked_px_src=int(ms.sum()),
               changed_px=int((np.abs(yc - ys) > 0).sum()))
    row['clip_frac'] = round(clip, 6)
    if clip_max is not None and clip > clip_max:
        row.update(status='not_measured_clipped', score=None, signed_median=None)
    elif len(r) < MIN_CELLS:
        row.update(status='not_measured', score=None, signed_median=None)
    else:
        row.update(status='measured', score=float(np.percentile(r, 95)), signed_median=float(np.median(signed)))
    return row
