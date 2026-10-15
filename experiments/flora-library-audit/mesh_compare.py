"""Bijective triangle/corner matching for the isolated FBX audit, in meters."""
import math
from collections import defaultdict
from itertools import product


def compare(expected, actual, position_tolerance=.00005, uv_tolerance=.00002):
    if len(expected) != len(actual):
        return {'equal': False, 'reason': 'triangle_count', 'max_deviation_mm': None}
    buckets = defaultdict(list)
    def key(tri):
        return tuple(math.floor(sum(c[i] for c in tri['corners']) / 3 / position_tolerance) for i in range(3))
    for index, tri in enumerate(expected):
        buckets[key(tri)].append(index)
    used = set()
    max_pos, max_uv = 0., 0.
    for tri in actual:
        cell = key(tri)
        matches = []
        for offset in product((-1, 0, 1), repeat=3):
            for index in buckets.get(tuple(a+b for a, b in zip(cell, offset)), []):
                if index in used or expected[index]['material'] != tri['material']:
                    continue
                ref = expected[index]['corners']
                for shift in range(3):
                    seq = tri['corners'][shift:] + tri['corners'][:shift]
                    if any(len(a) != len(b) for a, b in zip(ref, seq)):
                        continue
                    pd = max(math.dist(a[:3], b[:3]) for a, b in zip(ref, seq))
                    ud = max(math.dist(a[3:], b[3:]) for a, b in zip(ref, seq))
                    if pd <= position_tolerance and ud <= uv_tolerance:
                        matches.append((pd, ud, index))
        if not matches:
            return {'equal': False, 'reason': 'unmatched_geometry_uv_winding_or_material', 'matched': len(used), 'max_deviation_mm': None}
        pd, ud, index = min(matches)
        used.add(index)
        max_pos, max_uv = max(max_pos, pd), max(max_uv, ud)
    return {'equal': len(used) == len(expected), 'matched': len(used), 'max_deviation_mm': max_pos*1000, 'max_uv_deviation': max_uv}
