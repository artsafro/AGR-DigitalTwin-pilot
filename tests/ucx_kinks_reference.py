"""new-case: exact pre-#1227 arithmetic oracle and work/purity probes for kinks compaction.

The dense reference body is frozen from a4621a56 HeightField.kinks. Do not update it to
match the optimized implementation. All geometry here is synthetic, not a real site.
"""
import numpy as np
from dt_ai.geometry import ucx_build as ub


def dense_kinks(self, lo, hi) -> np.ndarray:
    k = self._cands(self._grid, (lo[0], lo[1], hi[0], hi[1]))
    if len(k) < 2:
        return np.zeros((0, 2))
    tt = self.t[k]
    e = np.unique(np.sort(np.concatenate([tt[:, [0, 1]], tt[:, [1, 2]], tt[:, [2, 0]]]), axis=1), axis=0)
    p0, p1 = self.v[e[:, 0]], self.v[e[:, 1]]
    out = []
    r = p1[:, :2] - p0[:, :2]
    for s0 in range(0, len(e), 256):
        a, ra, ea = p0[s0:s0 + 256, None, :2], r[s0:s0 + 256, None], e[s0:s0 + 256, None]
        den = ra[..., 0] * r[None, :, 1] - ra[..., 1] * r[None, :, 0]
        d = p0[None, :, :2] - a
        ok = (np.abs(den) > 1e-12) & (ea[..., 0] != e[None, :, 0]) & (ea[..., 0] != e[None, :, 1]) \
            & (ea[..., 1] != e[None, :, 0]) & (ea[..., 1] != e[None, :, 1])
        dd = np.where(ok, den, 1.0)
        tq = (d[..., 0] * r[None, :, 1] - d[..., 1] * r[None, :, 0]) / dd
        uq = (d[..., 0] * ra[..., 1] - d[..., 1] * ra[..., 0]) / dd
        m = ok & (tq > 0) & (tq < 1) & (uq > 0) & (uq < 1)
        i, _ = np.nonzero(m)
        out.append((a[i, 0] + ra[i, 0] * tq[m][:, None]))
    a0, e1, e2, det, okt = self._a[k], self._e1[k], self._e2[k], self._det[k], self._ok[k]
    nrm = np.cross(e1, e2)
    for s0 in range(0, len(e), 256):
        q0, q1, ee = p0[s0:s0 + 256, None], p1[s0:s0 + 256, None], e[s0:s0 + 256, None]
        f0 = ((q0 - a0[None]) * nrm[None]).sum(-1)
        f1 = ((q1 - a0[None]) * nrm[None]).sum(-1)
        den = f0 - f1
        ok = okt[None] & (np.abs(nrm[None, :, 2]) > 1e-12) & (np.abs(den) > 1e-15)
        s = np.where(ok, f0 / np.where(ok, den, 1.0), -1.0)
        pt = q0[..., :2] + s[..., None] * (q1[..., :2] - q0[..., :2])
        d = pt - a0[None, :, :2]
        u = (d[..., 0] * e2[None, :, 1] - d[..., 1] * e2[None, :, 0]) / det[None]
        w = (e1[None, :, 0] * d[..., 1] - e1[None, :, 1] * d[..., 0]) / det[None]
        shared = (tt[None, :, :] == ee[..., 0:1]).any(-1) | (tt[None, :, :] == ee[..., 1:2]).any(-1)
        m = ok & ~shared & (s > 0) & (s < 1) & (u > 0) & (w > 0) & (u + w < 1)
        out.append(pt[m])
    pts = np.concatenate(out) if out else np.zeros((0, 2))
    return pts[((pts >= np.asarray(lo)) & (pts <= np.asarray(hi))).all(axis=1)]


def assert_kinks_compaction():
    triangles = [[[i * 10., 0, 0], [i * 10. + 1, 0, 0], [i * 10., 1, 0]] for i in range(102)]
    vertices = np.asarray(triangles).reshape(-1, 3)
    faces = np.arange(len(vertices)).reshape(-1, 3)
    field = ub.HeightField(vertices, faces, bucket=2000)
    divisions = []

    class TrackedDeterminant(np.ndarray):
        def __array_ufunc__(self, ufunc, method, *inputs, **kwargs):
            plain = tuple(np.asarray(x) if isinstance(x, TrackedDeterminant) else x for x in inputs)
            if ufunc is np.divide:
                divisions.append(np.broadcast_arrays(*plain)[0].size)
            return getattr(ufunc, method)(*plain, **kwargs)

    field._det = field._det.view(TrackedDeterminant)
    assert field.kinks([0, 0], [1, 1]).shape == (0, 2)
    assert sum(divisions) == 0, "no edge pierces a plane: no barycentric divisions are needed"

    nonempty = 0
    for seed in range(100):
        rng = np.random.default_rng(seed)
        triangles = rng.uniform(-2, 2, (12, 3, 3))
        triangles[0] = [[-1, -1, 0], [1, -1, 1], [0, 1, 0]]
        triangles[1] = [[-1, -1, 1], [1, -1, 0], [0, 1, 1]]
        triangles[2] = triangles[0] + [10, 0, 0]
        triangles[3, 2] = (triangles[3, 0] + (triangles[3, 1] - triangles[3, 0]) * .5
                           + [1e-12, 0, 1e-12])
        for scale, shift in ((1., 0.), (1., 1e6), (1e-3, 0.), (1e3, 0.)):
            vertices = triangles.reshape(-1, 3) * scale + shift
            faces = np.arange(len(vertices)).reshape(-1, 3)
            field = ub.HeightField(vertices, faces, bucket=20 * scale)
            before_v, before_t = field.v.copy(), field.t.copy()
            lo, hi = np.array([-1., -1.]) * scale + shift, np.array([1., 1.]) * scale + shift
            expected = dense_kinks(field, lo, hi)
            actual = field.kinks(lo, hi)
            np.testing.assert_array_equal(actual, expected, err_msg=f"{seed=} {scale=} {shift=}")
            assert actual.tobytes() == expected.tobytes(), f"byte parity: {seed=} {scale=} {shift=}"
            np.testing.assert_array_equal(field.v, before_v)
            np.testing.assert_array_equal(field.t, before_t)
            nonempty += bool(len(expected))
    assert nonempty == 400
