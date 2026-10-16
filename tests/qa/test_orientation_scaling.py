"""Synthetic orientation scaling and exact equivalence (no production data).

Pattern: n/a | new-case: issue-203 synthetic orientation acceleration probes.
"""
import time

import numpy as np
import pytest

from twinqa.geometry import checks
from twinqa.geometry.mesh import Soup


def box(n, size=10.0):
    """Appendix A of mesh-audit-scaling-real-sizes, unchanged construction."""
    verts, index, tris = [], {}, []

    def vid(p):
        key = tuple(round(c, 9) for c in p)
        if key not in index:
            index[key] = len(verts)
            verts.append(key)
        return index[key]

    g = np.linspace(0.0, size, n + 1)
    for axis in range(3):
        for side in (0.0, size):
            u, w = [k for k in range(3) if k != axis]
            for i in range(n):
                for j in range(n):
                    q = []
                    for a, b in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)):
                        p = [0.0, 0.0, 0.0]
                        p[axis], p[u], p[w] = side, g[a], g[b]
                        q.append(vid(p))
                    t1, t2 = (q[0], q[1], q[2]), (q[0], q[2], q[3])
                    if (side == 0.0) == ((u - axis) % 3 == 1):
                        t1, t2 = t1[::-1], t2[::-1]
                    tris += [t1, t2]
    return soup(np.array(verts, float), np.array(tris, int))


def soup(v, t):
    return Soup(v, t, np.ones(len(t), int), np.full(len(t), 3), {}, 0,
                ("model",), np.zeros(len(t), int))


def bipyramid(faces):
    m = max(faces // 2, 3)
    a = np.linspace(0, 2 * np.pi, m, endpoint=False)
    v = np.vstack([np.stack([10 * np.cos(a), 10 * np.sin(a), np.zeros(m)], 1),
                   [[0, 0, 10.0]], [[0, 0, -10.0]]])
    t = [(i, (i + 1) % m, m) for i in range(m)] + [((i + 1) % m, i, m + 1) for i in range(m)]
    return soup(v, np.array(t, int))


@pytest.mark.parametrize("shape,limit", [("box", 10.0), ("slivers", 5.0)])
def test_orientation_real_size_budget(shape, limit):
    model = box(65) if shape == "box" else bipyramid(5000)
    start = time.perf_counter()
    checks.check_orientation(model, {"weld_m": 0.003})
    elapsed = time.perf_counter() - start
    assert elapsed < limit, f"{len(model.triangles)} triangles: {elapsed:.4f}s >= {limit}s"
