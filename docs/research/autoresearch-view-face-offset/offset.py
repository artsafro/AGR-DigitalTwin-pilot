"""Research-only veto on repeated alignments of an already accepted face."""

import numpy as np


def match(view, face, smooth, ncc, slack):
    """Expose the original R2 alignment curve, for an already eligible pair."""
    padded = np.pad(np.asarray(face, float), slack)
    width = len(view)
    query = smooth(np.asarray(view, float))
    return width, [
        (offset - slack, ncc(query, smooth(padded[offset:offset + width])))
        for offset in range(len(padded) - width + 1)
    ]


def veto(curve):
    width, offsets = curve
    best, score = max(offsets, key=lambda row: row[1])
    separation = max(10, (width + 1) // 2)
    second, other = max(
        (row for row in offsets if abs(row[0] - best) >= separation),
        key=lambda row: row[1], default=(None, None),
    )
    return other is not None and other >= score - 0.10, best, score, second, other
