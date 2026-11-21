"""new-case: R1 painter adapter for frozen NPM derivation benchmark, not a production recipe.

Reuses the pinned #1230 diffuse painter; the shared atlas's widened-joint suggestion
is intentionally not used: R1's 3 mm grid is retained, and no 1.5 px joint claim is made.
"""
from r1_painter import diffuse


def make_full(t, size):
    if t['S'] != 2.048 or size != 2048 or t.get('pattern') not in ('tile300', 'cassette'):
        raise ValueError(f"unsupported R1 painter contract: {t}")
    return diffuse(t, size, t['S']), None, None, None
