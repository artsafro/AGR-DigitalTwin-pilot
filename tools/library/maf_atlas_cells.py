"""Segment a MAF texture atlas into rectangular material cells (issue #524).

Pattern: verify actual artifacts, not exporter return codes (docs/domain/patterns/INDEX.md).
new-case: guillotine (XY-cut) segmentation of hand-made MAF atlases into solid / patterned cells.

MAF atlases are assembled in Photoshop from rectangular tiles (flat paint patches, wood, patterns,
decals). A cell boundary is a straight line, running across the whole current region, where the
colour jumps on (almost) every pixel of the line AND the two sides differ as materials. The region
is cut recursively at the strongest such line (guillotine cut). Measured on a box-downsampled
working copy (``work`` px on the long side), reported in source pixels.

A leaf is ``solid`` when at least ``solid_share`` of its pixels lie within ``solid_tol`` (RGB L1/3)
of the leaf median - a drawn ID number over a flat patch keeps it solid - otherwise ``patterned``.
Telegram copies are compressed: cells are layout measurements, not exact pixel values.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


@dataclass
class Cell:
    x: int  # source px, left
    y: int  # source px, top
    w: int
    h: int
    kind: str  # solid | patterned | mixed (leaf remainder around flat blocks; overlaps them)
    color: str  # median colour, #RRGGBB
    mean: str  # mean colour, #RRGGBB
    solid_share: float
    std: float

    def to_dict(self) -> dict:
        return asdict(self)


def _hex(c) -> str:
    r, g, b = (int(round(float(v))) for v in c[:3])
    return '#%02X%02X%02X' % (r, g, b)


def load_rgb(path: str, work: int) -> tuple[np.ndarray, float, tuple[int, int]]:
    """Return (working float RGB array, source px per working px, source size)."""
    with Image.open(path) as im:
        src = im.size
        rgb = im.convert('RGB')
        scale = max(src) / float(work) if max(src) > work else 1.0
        if scale > 1.0:
            rgb = rgb.resize((max(1, round(src[0] / scale)), max(1, round(src[1] / scale))), Image.BOX)
        arr = np.asarray(rgb).astype(np.float32)
    if not np.isfinite(arr).all():
        raise ValueError(f'{path}: non-finite pixel values')
    return arr, scale, src


def _side_stats(a: np.ndarray) -> tuple[np.ndarray, float]:
    flat = a.reshape(-1, 3)
    return flat.mean(0), float(flat.std(0).mean())


def _best_cut(a, x0, y0, x1, y1, min_px, edge_t, line_share, mat_diff):
    best = None
    region = a[y0:y1, x0:x1]
    # vertical lines: jump between column c-1 and c
    dv = np.abs(np.diff(region, axis=1)).sum(2) / 3.0  # (h, w-1); index c-1 -> cut at c
    dh = np.abs(np.diff(region, axis=0)).sum(2) / 3.0  # (h-1, w)
    w, h = x1 - x0, y1 - y0
    for axis, d, n, length in (('x', dv, w, h), ('y', dh, h, w)):
        share = (d > edge_t).mean(axis=0 if axis == 'x' else 1)
        for c in np.argsort(-share):
            cut = int(c) + 1
            if share[c] < line_share:
                break
            if cut < min_px or n - cut < min_px:
                continue
            k = max(2, min(32, cut // 2, (n - cut) // 2))
            if axis == 'x':
                sa, sb = region[:, cut - k:cut], region[:, cut:cut + k]
            else:
                sa, sb = region[cut - k:cut, :], region[cut:cut + k, :]
            (ma, va), (mb, vb) = _side_stats(sa), _side_stats(sb)
            diff = float(np.abs(ma - mb).mean())
            if diff < mat_diff and abs(va - vb) < mat_diff:
                continue  # same material on both sides (plank seam, grain line)
            score = float(share[c]) + diff / 255.0
            if best is None or score > best[0]:
                best = (score, axis, cut)
            break
    return best


def _merge_same(a, leaves, mat_diff):
    """Merge neighbouring leaves sharing a full edge whose contents match (plank strips of one wood)."""
    leaves = list(leaves)
    changed = True
    while changed:
        changed = False
        for i in range(len(leaves)):
            for j in range(len(leaves)):
                if i == j:
                    continue
                p, q = leaves[i], leaves[j]
                if p[1] == q[1] and p[3] == q[3] and p[2] == q[0]:
                    m = (p[0], p[1], q[2], p[3])
                elif p[0] == q[0] and p[2] == q[2] and p[3] == q[1]:
                    m = (p[0], p[1], p[2], q[3])
                else:
                    continue
                (ma, va), (mb, vb) = (_side_stats(a[r[1]:r[3], r[0]:r[2]]) for r in (p, q))
                if float(np.abs(ma - mb).mean()) < mat_diff and abs(va - vb) < mat_diff and min(va, vb) > 3:
                    leaves = [r for k, r in enumerate(leaves) if k not in (i, j)] + [m]
                    changed = True
                    break
            if changed:
                break
    return leaves


def _components(mask: np.ndarray) -> np.ndarray:
    """4-connected labels of ``mask`` by min-label propagation (no scipy); 0 = background."""
    h, w = mask.shape
    lab = np.where(mask, np.arange(1, h * w + 1, dtype=np.int64).reshape(h, w), 0)
    big = h * w + 1
    while True:
        cur = np.where(mask, lab, big)
        nb = cur.copy()
        nb[1:, :] = np.minimum(nb[1:, :], cur[:-1, :])
        nb[:-1, :] = np.minimum(nb[:-1, :], cur[1:, :])
        nb[:, 1:] = np.minimum(nb[:, 1:], cur[:, :-1])
        nb[:, :-1] = np.minimum(nb[:, :-1], cur[:, 1:])
        new = np.where(mask, nb, 0)
        if np.array_equal(new, lab):
            return lab
        lab = new


def _flat_blocks(a, rect, min_cell, solid_tol):
    """Split a mixed (non-guillotine) leaf into near-rectangular flat-colour blocks + the rest.

    A flat block is a 4-connected component of pixels whose neighbours differ by < 2 (RGB mean)
    filling >= 90 % of its bounding box, both box sides >= ``min_cell``. Blocks are returned as
    extra cells; the leaf itself is kept as a ``mixed`` remainder only when the blocks cover < 90 % of it.
    """
    x0, y0, x1, y1 = rect
    reg = a[y0:y1, x0:x1]
    h, w = reg.shape[:2]
    px = reg.reshape(-1, 3)
    if (np.abs(px - np.median(px, 0)).mean(1) <= solid_tol).mean() >= 0.85 or min(h, w) < 2 * min_cell:
        return [(rect, False)]
    d = np.zeros((h, w), np.float32)
    dx = np.abs(np.diff(reg, axis=1)).mean(2)
    dy = np.abs(np.diff(reg, axis=0)).mean(2)
    d[:, 1:] = np.maximum(d[:, 1:], dx)
    d[:, :-1] = np.maximum(d[:, :-1], dx)
    d[1:, :] = np.maximum(d[1:, :], dy)
    d[:-1, :] = np.maximum(d[:-1, :], dy)
    lab = _components(d < 2.0)
    blocks = []
    ids, counts = np.unique(lab[lab > 0], return_counts=True)
    for k, n in zip(ids, counts):
        if n < min_cell * min_cell:
            continue
        ys, xs = np.nonzero(lab == k)
        bx0, bx1, by0, by1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        if n < 0.9 * (bx1 - bx0) * (by1 - by0):
            continue  # not a rectangle
        # the flat mask loses the block's 1-px rim (its neighbour across the border differs): grow back
        bx0, by0, bx1, by1 = max(0, bx0 - 1), max(0, by0 - 1), min(w, bx1 + 1), min(h, by1 + 1)
        if bx1 - bx0 < min_cell or by1 - by0 < min_cell:
            continue
        blocks.append((x0 + int(bx0), y0 + int(by0), x0 + int(bx1), y0 + int(by1)))
    if not blocks:
        return [(rect, False)]
    covered = sum((b[2] - b[0]) * (b[3] - b[1]) for b in blocks)
    return [(b, False) for b in blocks] + ([(rect, True)] if covered < 0.9 * w * h else [])


def segment(path: str, *, work: int = 512, min_cell: int = 8, edge_t: float = 10.0,
            line_share: float = 0.9, mat_diff: float = 8.0, solid_tol: float = 6.0,
            solid_share: float = 0.85) -> dict:
    """Segment ``path``; returns {"path", "size", "work_scale", "cells": [Cell dict...]}."""
    for name, v in (('work', work), ('min_cell', min_cell)):
        if not isinstance(v, int) or v <= 0:
            raise ValueError(f'{name} must be a positive int, got {v!r}')
    for name, v in (('edge_t', edge_t), ('line_share', line_share), ('mat_diff', mat_diff),
                    ('solid_tol', solid_tol), ('solid_share', solid_share)):
        if not np.isfinite(v) or v <= 0:
            raise ValueError(f'{name} must be a finite positive number, got {v!r}')
    a, scale, src = load_rgb(path, work)
    h, w = a.shape[:2]
    if min(h, w) < 2 * min_cell:
        raise ValueError(f'{path}: image {src} too small to segment (min_cell={min_cell} work px)')
    leaves = []
    stack = [(0, 0, w, h)]
    while stack:
        x0, y0, x1, y1 = stack.pop()
        cut = _best_cut(a, x0, y0, x1, y1, min_cell, edge_t, line_share, mat_diff)
        if cut is None:
            leaves.append((x0, y0, x1, y1))
            continue
        _, axis, c = cut
        if axis == 'x':
            stack += [(x0, y0, x0 + c, y1), (x0 + c, y0, x1, y1)]
        else:
            stack += [(x0, y0, x1, y0 + c), (x0, y0 + c, x1, y1)]
    leaves = _merge_same(a, leaves, mat_diff)
    rects = []
    for r in leaves:
        rects += _flat_blocks(a, r, min_cell, solid_tol)
    cells = []
    for (x0, y0, x1, y1), mixed in sorted(rects, key=lambda r: (r[0][1], r[0][0])):
        px = a[y0:y1, x0:x1].reshape(-1, 3)
        med = np.median(px, 0)
        share = float((np.abs(px - med).mean(1) <= solid_tol).mean())
        sx0, sy0 = round(x0 * scale), round(y0 * scale)
        sx1, sy1 = min(src[0], round(x1 * scale)), min(src[1], round(y1 * scale))
        cells.append(Cell(sx0, sy0, sx1 - sx0, sy1 - sy0,
                          'mixed' if mixed else ('solid' if share >= solid_share else 'patterned'),
                          _hex(med), _hex(px.mean(0)), round(share, 3),
                          round(float(px.std(0).mean()), 2)))
    return {'path': path, 'size': list(src), 'work_scale': round(scale, 4),
            'cells': [c.to_dict() for c in cells]}
