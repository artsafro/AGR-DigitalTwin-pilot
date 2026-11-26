"""Read-only R110 paired edge-incidence observation; no model output."""
from collections import Counter
from math import isfinite


def incidence(polys):
    return Counter(tuple(sorted((u, p[(i + 1) % len(p)])))
                   for p in polys for i, u in enumerate(p))


def measure(vertices, polys):
    if any(len(p) < 3 or any(not 0 <= v < len(vertices) for v in p) for p in polys):
        raise ValueError('invalid polygon indices')
    if any(len(xyz) != 3 or not all(map(isfinite, xyz)) for xyz in vertices):
        raise ValueError('invalid XYZ data')
    first = {}
    ids = [first.setdefault(xyz, i) for i, xyz in enumerate(vertices)]
    candidate = [tuple(ids[i] for i in p) for p in polys]
    raw, exact = incidence(polys), incidence(candidate)
    if sum(raw.values()) != sum(exact.values()):
        raise ValueError('incidence count changed')
    raw_multi, exact_multi = (sum(n > 2 for n in c.values()) for c in (raw, exact))
    return {'raw_open': sum(n == 1 for n in raw.values()),
            'exact_open': sum(n == 1 for n in exact.values()),
            'changed_corners': sum(i != j for p, q in zip(polys, candidate, strict=True)
                                   for i, j in zip(p, q, strict=True)),
            'raw_collapsed': sum(n for (i, j), n in raw.items() if i == j),
            'collapsed': sum(n for (i, j), n in exact.items() if i == j),
            'raw_nonmanifold': raw_multi, 'exact_nonmanifold': exact_multi,
            'extra_nonmanifold': exact_multi - raw_multi}
