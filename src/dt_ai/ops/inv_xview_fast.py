"""Fast xView-exact overlap lists: 3ds Max xView Overlapping Faces (5 mm) / Overlapping Vertices (2 mm) (#553).

Same rule, thresholds and arithmetic as `dt_ai.ops.inv_xview` (the baseline and oracle runner, D152): a polygon pair
(different polygons of one mesh) is an xView face pair when two live triangles of their triangulation have
|cos| >= `parallel_cos_min` and a vertex of one triangle that is not a vertex of the other polygon projects along the
other triangle's normal into it (boundary included, barycentric slack 1e-12) at a plane distance <= `face_m`.
Overlapping vertices: two distinct vertex indices at a distance <= `vertex_m` (`inv_xview.vertex_pairs`).
Only the xView selection is computed (no `area` rule: that is the kernel's extra, see `inv_xview`).

Speed comes from the search order, not from a looser rule: the contact rule is evaluated per (triangle, vertex)
instead of per triangle pair. A vertex grid gives the vertices inside each triangle's bounding box padded by
`face_m / parallel_cos_min` (a superset of every vertex that can project into it), the plane distance and
barycentric test run with the baseline's own expressions on that short list, and only the few hits look up the
triangles that own the vertex (live, another polygon, near-parallel). Convex quads are fanned vectorised; every
polygon whose classification is not clear by a wide margin goes through the baseline's `_polygon_triangles`.
Parity guard: `tools/qa/xview_bench.py` (stored xView lists on TOW02 / Ground v014 + synthetic edge cases).

Fail-closed like the baseline: NaN / inf, bad indices (out of range, bool, fractional, repeated), fewer than 3 sides,
bad thresholds raise `ValueError`; a self-intersecting polygon raises `ValueError`.
numpy only (scipy is not in the environment).
Pattern: none | new-case: per-vertex search order for the xView contact rule with exact baseline arithmetic (#553).
"""
from itertools import chain

import numpy as np

from dt_ai.ops.inv_xview import AREA_EPS_M2, XviewTolerance, _dot, _polygon_triangles, vertex_pairs

_CHUNK = 4_000_000          # (triangle, vertex) candidates per numpy block


def _faces_array(faces, nv: int):
    """(lengths, flat indices) with the PolyMesh checks, vectorised."""
    faces = tuple(faces)
    ln = np.fromiter(map(len, faces), dtype=np.int64, count=len(faces))
    items = list(chain.from_iterable(faces))
    kinds = set(map(type, items))
    for k in kinds:
        if issubclass(k, (bool, np.bool_)) or not issubclass(k, (int, np.integer)):
            bad = next(i for i in items if type(i) is k)
            raise ValueError(f"face index {bad!r} is not an integer")
    flat = np.asarray(items, dtype=np.int64)
    if len(ln) and ln.min() < 3:
        raise ValueError(f"face {int(np.argmax(ln < 3))}: fewer than 3 sides")
    if flat.size and (flat.min() < 0 or flat.max() >= nv):
        raise ValueError("face index outside the vertices")
    start = np.concatenate([[0], np.cumsum(ln)[:-1]]) if len(ln) else ln
    for n in np.unique(ln):
        sel = np.flatnonzero(ln == n)
        blk = np.sort(flat[start[sel][:, None] + np.arange(n)], axis=1)
        dup = (blk[:, 1:] == blk[:, :-1]).any(1)
        if dup.any():
            raise ValueError(f"face {int(sel[np.argmax(dup)])}: repeated vertex index")
    return ln, flat, start


def _triangulate(v, faces, ln, flat, start):
    """(tris, owner): triangles and 0-based polygon ids; convex quads fanned vectorised, others by the baseline."""
    tri_sel = np.flatnonzero(ln == 3)
    quad_sel = np.flatnonzero(ln == 4)
    parts_t, parts_o = [flat[start[tri_sel][:, None] + np.arange(3)]], [tri_sel]
    slow = list(np.flatnonzero(ln > 4))
    if len(quad_sel):
        qi = flat[start[quad_sel][:, None] + np.arange(4)]
        p = v[qi]                                                    # (m, 4, 3)
        nrm = np.cross(p, np.roll(p, -1, axis=1)).sum(1)             # Newell, 2 x area vector
        an = np.abs(nrm)
        srt = np.sort(an, axis=1)
        ax = np.argmax(an, axis=1)
        keep = np.array([[1, 2], [0, 2], [0, 1]])[ax]
        q = np.take_along_axis(p, np.repeat(keep[:, None, :], 4, axis=1), axis=2)
        q = q - q.mean(1, keepdims=True)
        scale = np.maximum(np.abs(q).max((1, 2)), 1e-12)
        nx = np.roll(q, -1, axis=1)
        nn = np.roll(q, -2, axis=1)
        cr = (nx[..., 0] - q[..., 0]) * (nn[..., 1] - q[..., 1]) - (nx[..., 1] - q[..., 1]) * (nn[..., 0] - q[..., 0])
        sgn = np.sign((q[..., 0] * nx[..., 1] - nx[..., 0] * q[..., 1]).sum(1))
        clear = ((cr * sgn[:, None]) > 1e-9 * scale[:, None] ** 2).all(1) & (srt[:, 2] / 2 > 4 * AREA_EPS_M2) \
            & (srt[:, 2] - srt[:, 1] > 1e-9 * srt[:, 2]) & (sgn != 0)
        fq = qi[clear]
        parts_t += [fq[:, [0, 1, 2]], fq[:, [0, 2, 3]]]
        parts_o += [quad_sel[clear], quad_sel[clear]]
        slow += list(quad_sel[~clear])
    if slow:
        st, so = [], []
        for k in sorted(int(x) for x in slow):
            for t in _polygon_triangles(k, tuple(int(x) for x in flat[start[k]:start[k] + ln[k]]), v):
                st.append(t)
                so.append(k)
        parts_t.append(np.asarray(st, np.int64).reshape(-1, 3))
        parts_o.append(np.asarray(so, np.int64))
    return np.concatenate(parts_t).astype(np.int64), np.concatenate(parts_o).astype(np.int64)


def _vertex_candidates(v, lo, hi, used):
    """Blocks of (triangle, vertex) with vertex inside the triangle's box [lo, hi] (already padded)."""
    vid = np.flatnonzero(used)
    pv = v[vid]
    ext = np.maximum(hi - lo, 0)
    cell = max(float(np.median(ext.max(1))) if len(ext) else 1.0, 1e-6)
    base = pv.min(0) - cell
    kv = np.floor((pv - base) / cell).astype(np.int64)
    dims = kv.max(0) + 2
    code = (kv[:, 0] * dims[1] + kv[:, 1]) * dims[2] + kv[:, 2]
    order = np.argsort(code, kind="stable")
    sc, svid = code[order], vid[order]
    k0 = np.clip(np.floor((lo - base) / cell).astype(np.int64), 0, dims - 1)
    k1 = np.clip(np.floor((hi - base) / cell).astype(np.int64), 0, dims - 1)
    span = k1 - k0 + 1
    ncell = span.prod(1)
    n = len(lo)
    start = 0
    while start < n:
        acc = np.cumsum(ncell[start:])
        stop = start + max(1, int(np.searchsorted(acc, _CHUNK // 4, "right")))
        tid = np.repeat(np.arange(start, stop), ncell[start:stop])
        r = np.arange(len(tid)) - np.repeat(np.cumsum(ncell[start:stop]) - ncell[start:stop], ncell[start:stop])
        sp = span[tid]
        cz = r % sp[:, 2]
        cy = (r // sp[:, 2]) % sp[:, 1]
        cx = r // (sp[:, 2] * sp[:, 1])
        c = ((k0[tid, 0] + cx) * dims[1] + k0[tid, 1] + cy) * dims[2] + k0[tid, 2] + cz
        a = np.searchsorted(sc, c, "left")
        b = np.searchsorted(sc, c, "right")
        cnt = b - a
        if cnt.sum():
            s = np.repeat(tid, cnt)
            j = np.repeat(a - np.cumsum(cnt) + cnt, cnt) + np.arange(cnt.sum())
            p = svid[j]
            pp = v[p]
            ok = np.all((pp >= lo[s]) & (pp <= hi[s]), axis=1)
            yield s[ok], p[ok]
        start = stop


def contact_pairs(v, tris, owner, tol: XviewTolerance):
    """0-based polygon pairs (i < j) of the xView contact rule, as an (m, 2) array."""
    nv = len(v)
    p = v[tris]
    origin = p[:, 0]
    cr = np.cross(p[:, 1] - origin, p[:, 2] - origin)
    ln = np.linalg.norm(cr, axis=1)
    if not np.isfinite(ln).all():
        raise ValueError("derived triangle geometry is not finite")
    live = ln / 2 > AREA_EPS_M2
    nrm = np.divide(cr, ln[:, None], out=np.zeros_like(cr), where=live[:, None])
    pad = tol.face_m / max(tol.parallel_cos_min, 1e-9) + 1e-9
    lt = np.flatnonzero(live)
    if not len(lt):
        return np.zeros((0, 2), np.int64)
    # vertex -> live triangles (CSR)
    vt_v = tris[lt].ravel()
    vt_t = np.repeat(lt, 3)
    o = np.argsort(vt_v, kind="stable")
    vt_v, vt_t = vt_v[o], vt_t[o]
    vptr = np.searchsorted(vt_v, np.arange(nv + 1))
    used = np.zeros(nv, bool)
    used[vt_v] = True
    # polygon membership keys owner * nv + vertex (sorted, unique)
    pk = np.sort(np.concatenate([owner * nv + tris[:, k] for k in range(3)]))      # duplicates are harmless
    # one query box per polygon (union of its live triangles), expanded to the triangles after the own-vertex test
    ol = lt[np.argsort(owner[lt], kind="stable")]
    so = owner[ol]
    ostart = np.flatnonzero(np.concatenate([[True], so[1:] != so[:-1]]))
    upoly, ocnt = so[ostart], np.diff(np.append(ostart, len(so)))
    lo = np.minimum.reduceat(p[ol].min(1), ostart) - pad
    hi = np.maximum.reduceat(p[ol].max(1), ostart) + pad
    hits_s, hits_p = [], []
    for pi, pid in _vertex_candidates(v, lo, hi, used):
        key = upoly[pi] * nv + pid
        pos = np.minimum(np.searchsorted(pk, key), len(pk) - 1)
        ok = pk[pos] != key
        pi, pid = pi[ok], pid[ok]
        c = ocnt[pi]
        s = ol[np.repeat(ostart[pi] - np.cumsum(c) + c, c) + np.arange(c.sum())]
        pid = np.repeat(pid, c)
        a = v[tris[s, 0]]
        w = v[pid] - a
        dist = _dot(w, nrm[s])
        ok = np.abs(dist) <= tol.face_m
        s, pid, a, w, dist = s[ok], pid[ok], a[ok], w[ok], dist[ok]
        if not len(s):
            continue
        e0, e1 = v[tris[s, 1]] - a, v[tris[s, 2]] - a
        d00, d01, d11 = _dot(e0, e0), _dot(e0, e1), _dot(e1, e1)
        den = d00 * d11 - d01 * d01
        q = w - dist[:, None] * nrm[s]
        d20, d21 = _dot(q, e0), _dot(q, e1)
        bv = (d11 * d20 - d01 * d21) / den
        bw = (d00 * d21 - d01 * d20) / den
        inside = (bv >= -1e-12) & (bw >= -1e-12) & (bv + bw <= 1 + 1e-12)
        hits_s.append(s[inside])
        hits_p.append(pid[inside])
    if not hits_s:
        return np.zeros((0, 2), np.int64)
    s, pid = np.concatenate(hits_s), np.concatenate(hits_p)
    cnt = vptr[pid + 1] - vptr[pid]
    ss = np.repeat(s, cnt)
    t = vt_t[np.repeat(vptr[pid] - np.cumsum(cnt) + cnt, cnt) + np.arange(cnt.sum())]
    ok = (owner[ss] != owner[t]) & (np.abs(_dot(nrm[ss], nrm[t])) >= tol.parallel_cos_min)
    i, j = owner[ss[ok]], owner[t[ok]]
    pr = np.stack([np.minimum(i, j), np.maximum(i, j)], 1)
    return np.unique(pr, axis=0) if len(pr) else np.zeros((0, 2), np.int64)


def xview_lists(vertices, faces, tol: XviewTolerance | None = None) -> dict:
    """1-based sorted xView selections: `xview_faces`, `vertices`, plus `vertex_pairs` / `face_pairs`."""
    tol = (tol or XviewTolerance()).validate()
    v = np.asarray(vertices, dtype=float)
    if v.ndim != 2 or v.shape[1] != 3:
        raise ValueError("vertices must be (n, 3)")
    if not np.isfinite(v).all():
        raise ValueError("vertices must be finite")
    ln, flat, start = _faces_array(faces, len(v))
    a, b, d = vertex_pairs(v, tol.vertex_m)
    vp = tuple((int(x) + 1, int(y) + 1, float(z)) for x, y, z in zip(a, b, d))
    fp = np.zeros((0, 2), np.int64)
    if len(ln):
        tris, owner = _triangulate(v, faces, ln, flat, start)
        if len(tris):
            fp = contact_pairs(v, tris, owner, tol)
    return {"xview_faces": tuple(int(x) + 1 for x in np.unique(fp)),
            "vertices": tuple(sorted({x for p in vp for x in p[:2]})),
            "vertex_pairs": vp, "face_pairs": tuple((int(i) + 1, int(j) + 1) for i, j in fp)}
