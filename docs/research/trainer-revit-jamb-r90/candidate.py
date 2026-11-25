"""Observe-only BodyPlan transform; never applied by the product."""
from copy import deepcopy
from itertools import accumulate
import math


def align(plan, eps):
    result = deepcopy(plan)
    changes = []
    for ri, ring in enumerate(result['rings']):
        xy = ring['xy']
        corners = list(accumulate(math.dist(a, b) for a, b in zip(xy, xy[1:])))
        cuts = ring.get('cuts', [])
        replacements = {}
        for wi, window in enumerate(result.get('windows', [])):
            if window[0] != ri:
                continue
            for end in (1, 2):
                old = window[end]
                if old not in cuts:
                    continue
                near = [s for s in corners if abs(s - old) <= 2 * eps]
                if len(near) > 1:
                    raise ValueError('ambiguous jamb corner')
                if not near or old == near[0]:
                    continue
                window[end] = replacements[old] = near[0]
                changes.append({'ring': ri, 'window': wi, 'endpoint': end, 'from_m': old, 'to_m': near[0]})
            if window[1] >= window[2]:
                raise ValueError('alignment collapses an opening')
        if replacements:
            ring['cuts'] = sorted({replacements.get(s, s) for s in cuts})
    return result, changes
