"""Count manifold edges whose two loop sides wind the same way.
new-case: shared stdlib winding rule for mesh_audit core and twinqa orientation (#145)
"""
from collections import defaultdict


def same_direction_edges(loops) -> int:
    """Edges used by exactly two loop sides that both traverse it in the same direction."""
    sides = defaultdict(list)
    for loop in loops:
        idx = [int(v) for v in loop]
        n = len(idx)
        for i in range(n):
            a = idx[i]
            b = idx[(i + 1) % n]
            if a == b:
                continue
            sides[(a, b) if a < b else (b, a)].append(a)
    return sum(len(s) == 2 and s[0] == s[1] for s in sides.values())
