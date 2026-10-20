"""Bounding-box contacts for the structure readers; standard library only (Blender loads it by path) [D111] (#339).

Two parts touch when their axis-aligned bounding boxes are at most `tolerance` apart on every axis: the gap is the
largest per-axis separation, 0 for overlapping boxes. Exactly at the tolerance counts as a contact - the reader
then asks "weld or embed?" rather than staying silent [D124].
Pattern: n/a | new-case: bbox contact candidates for the gate-1 parts list (#339).
"""
import itertools
import math


def bbox_gap(a, b) -> float:
    """Largest per-axis separation of two boxes `(min, max)`; 0 when they overlap or touch."""
    (amin, amax), (bmin, bmax) = a, b
    values = [*amin, *amax, *bmin, *bmax]
    if len(values) != 12 or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                                    for v in values):
        raise ValueError("a bounding box is two finite 3-vectors")
    if any(lo > hi for lo, hi in zip([*amin, *bmin], [*amax, *bmax])):
        raise ValueError("bounding box min exceeds max")
    return max(max(0.0, bmin[k] - amax[k], amin[k] - bmax[k]) for k in range(3))


def contacts(boxes: dict, tolerance: float, eps: float = 1e-9) -> list[dict]:
    """Every pair of named boxes within `tolerance` (inclusive, `eps` absorbs float noise), sorted by name."""
    if not (isinstance(tolerance, (int, float)) and math.isfinite(tolerance) and tolerance >= 0):
        raise ValueError("tolerance must be a finite non-negative number")
    result = []
    for a, b in itertools.combinations(sorted(boxes), 2):
        gap = bbox_gap(boxes[a], boxes[b])
        if gap <= tolerance + eps:
            result.append({"a": a, "b": b, "gap_m": round(gap, 9)})
    return result
