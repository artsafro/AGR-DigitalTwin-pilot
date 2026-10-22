"""Kernel invariant xview_overlaps: no overlapping vertices (2 mm) or faces (5 mm), with 3ds Max xView parity (#370).

Artem's production check is 3ds Max xView "Overlapping Vertices" at 0.002 m and "Overlapping Faces" at 0.005 m
(`docs/agr/case_studies/KPP1_VPM_NPM_V005.md`; delivery decision in `docs/decisions.md`, #370). One part = one mesh.

Overlapping vertices: two distinct vertex indices of one mesh at a distance <= `vertex_m`. One welded vertex is one
index, so a shared vertex never counts; unused vertices count like xView's.

Overlapping faces: a polygon pair (different polygons of one mesh, either orientation) is reported when one of two
rules holds. Both need near-parallel planes, |cos| >= `parallel_cos_min`.
- `contact` - the rule 3ds Max xView applies (measured headless in Max 2026.3, 146/146 faces on Ground v014,
  `docs/research/xview-parity-ground-v014.md`): a vertex of one polygon that is not a vertex of the other projects
  along the other's normal into it (boundary included) at a plane distance <= `face_m`. It also flags faces that only
  touch (zero area, unwelded coincident vertices or a T-vertex on an edge), exactly like xView.
- `area` - the rule of the issue: the projected overlap has an area > `AREA_MIN_M2` and somewhere on it the two
  surfaces are <= `face_m` apart (measured from points of the overlap on the first plane to the second plane;
  zero when they cross). It catches what xView misses: two faces that cross edge over edge with no vertex inside the
  other, and duplicate faces with the same vertex indices.
`parallel_cos_min` = 0.9999 (0.810 deg) is xView's limit, bisected in Max (0.810 deg flagged, 0.815 deg not).
Thresholds (one block below, overridable per profile or per call): `<=` at the threshold (fail-closed; xView itself
passes vertices at exactly 2.000 mm and flags faces at 5.000 mm, measured).

Polygons are triangulated on their Newell plane: a convex one as a fan from its first vertex (the triangulation the
v014 parity was measured with), a concave one by ear clipping, so a triangle never covers area outside its polygon
whatever the first vertex or the winding; a self-intersecting polygon raises `ValueError` (unsupported, never a
guessed cover). Triangles with zero area (<= `AREA_EPS_M2`) take part in the vertex check only.
Fail-closed: no part to check or a part without faces never passes; NaN / inf, bad indices (out of range, bool,
fractional) or bad thresholds raise `ValueError`. Report-only first [#370]: `check_operation_xview` appends a non-gating result until a person accepts the
v014 parity; `gating=True` makes it a gate.

numpy + shapely (projected overlap area, as `twinqa.clearance`); not pure numpy; no Blender.
Pattern: none | new-case: xView overlapping vertices / faces kernel invariant with measured Max parity (#370).
"""
import math
from dataclasses import dataclass
from typing import Iterable, Mapping

import numpy as np
import shapely

from dt_ai.ops.inv_quads import PolyMesh
from dt_ai.ops.invariants import InvariantReport, InvariantResult, Mesh

VERTEX_M = 0.002            # xView Overlapping Vertices tolerance, Artem's production value [#370]
FACE_M = 0.005              # xView Overlapping Faces tolerance, Artem's production value [#370]
PARALLEL_COS_MIN = 0.9999   # xView near-parallel limit, measured in Max 2026.3 (0.810 deg yes, 0.815 deg no)
AREA_MIN_M2 = 1e-9          # projected overlap area above float noise (0.03 mm square)
AREA_EPS_M2 = 1e-12         # a triangle with no more area has no plane
NAME = "xview_overlaps"
_PROFILE_SUFFIXES = ("", "-OKS", "-GROUND")
_CHUNK = 2_000_000          # candidate pairs per numpy block


@dataclass(frozen=True)
class XviewTolerance:
    vertex_m: float = VERTEX_M
    face_m: float = FACE_M
    parallel_cos_min: float = PARALLEL_COS_MIN

    def validate(self) -> "XviewTolerance":
        for k in ("vertex_m", "face_m", "parallel_cos_min"):
            x = getattr(self, k)
            if not isinstance(x, (int, float)) or not np.isfinite(x) or x < 0:
                raise ValueError(f"{k} must be a finite number >= 0, got {x!r}")
        if not 0 < self.parallel_cos_min <= 1:
            raise ValueError(f"parallel_cos_min must be in (0, 1], got {self.parallel_cos_min!r}")
        return self


PROFILE_TOLERANCE = {"NPM": XviewTolerance(), "VPM": XviewTolerance()}


def tolerance_for(profile: str) -> XviewTolerance:
    for base, tol in PROFILE_TOLERANCE.items():
        if profile in {base + s for s in _PROFILE_SUFFIXES}:
            return tol
    raise ValueError(f"unknown profile {profile!r}; expected NPM / VPM (-OKS / -GROUND)")


@dataclass(frozen=True)
class PartXviewReport:
    part: str
    vertex_pairs: tuple     # (a, b, distance_m), 1-based vertex ids, a < b
    face_pairs: tuple       # (i, j, kind, separation_m), 1-based polygon ids, i < j, kind contact|area|area+contact
    vertices: tuple         # 1-based ids in any vertex pair (xView Overlapping Vertices selection)
    faces: tuple            # 1-based ids in any face pair
    xview_faces: tuple      # 1-based ids in contact pairs (xView Overlapping Faces selection)
    offenders: tuple

    def to_dict(self) -> dict:
        return {"part": self.part, "vertex_pairs": len(self.vertex_pairs), "face_pairs": len(self.face_pairs),
                "face_pairs_by_kind": {k: sum(p[2] == k for p in self.face_pairs)
                                       for k in ("contact", "area", "area+contact")},
                "vertices": list(self.vertices), "faces": list(self.faces), "xview_faces": list(self.xview_faces),
                "offenders": list(self.offenders[:20])}


# ---- geometry ------------------------------------------------------------------------------------------------------

def _as_poly(mesh) -> PolyMesh:
    if isinstance(mesh, PolyMesh):
        return mesh
    if isinstance(mesh, Mesh):
        return PolyMesh(mesh.vertices, tuple(tuple(t) for t in mesh.triangles))   # PolyMesh checks every index
    raise ValueError(f"expected PolyMesh or Mesh, got {type(mesh).__name__}")


def _dot(a, b):
    return np.einsum("ij,ij->i", a, b)


def vertex_pairs(v: np.ndarray, r: float) -> tuple:
    """(a, b, d) 0-based index pairs a < b with |v[a] - v[b]| <= r: grid hash of cell r, 14 half-neighbour cells."""
    n = len(v)
    if n < 2:
        return np.zeros(0, int), np.zeros(0, int), np.zeros(0)
    cell = max(r, 1e-9)
    k = np.floor((v - v.min(0)) / cell).astype(np.int64) + 1
    dims = k.max(0) + 2
    code = (k[:, 0] * dims[1] + k[:, 1]) * dims[2] + k[:, 2]
    order = np.argsort(code, kind="stable")
    sc = code[order]
    offs = [(a, b, c) for a in (-1, 0, 1) for b in (-1, 0, 1) for c in (-1, 0, 1) if (a, b, c) > (0, 0, 0)]
    out_a, out_b = [], []
    for o in [(0, 0, 0)] + offs:
        nb = sc + (o[0] * dims[1] + o[1]) * dims[2] + o[2]
        lo = np.searchsorted(sc, nb, "left")
        hi = np.searchsorted(sc, nb, "right")
        if o == (0, 0, 0):
            lo = np.maximum(lo, np.arange(n) + 1)
        cnt = np.maximum(hi - lo, 0)
        if not cnt.sum():
            continue
        src = np.repeat(np.arange(n), cnt)
        dst = np.repeat(lo - np.cumsum(cnt) + cnt, cnt) + np.arange(cnt.sum())
        out_a.append(order[src])
        out_b.append(order[dst])
    if not out_a:
        return np.zeros(0, int), np.zeros(0, int), np.zeros(0)
    a, b = np.concatenate(out_a), np.concatenate(out_b)
    d = np.linalg.norm(v[a] - v[b], axis=1)
    keep = d <= r
    a, b, d = a[keep], b[keep], d[keep]
    a, b = np.minimum(a, b), np.maximum(a, b)
    s = np.lexsort((b, a))
    return a[s], b[s], d[s]


def _simple(q: np.ndarray, eps: float) -> bool:
    """No two non-adjacent edges of the closed 2D polygon `q` touch or cross."""
    n = len(q)

    def orient(a, b, c):
        d = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return 0 if abs(d) <= eps else (1 if d > 0 else -1)

    def on(a, b, c):
        return min(a[0], b[0]) - 1e-15 <= c[0] <= max(a[0], b[0]) + 1e-15 and \
            min(a[1], b[1]) - 1e-15 <= c[1] <= max(a[1], b[1]) + 1e-15

    for i in range(n):
        p1, p2 = q[i], q[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            p3, p4 = q[j], q[(j + 1) % n]
            o1, o2, o3, o4 = orient(p1, p2, p3), orient(p1, p2, p4), orient(p3, p4, p1), orient(p3, p4, p2)
            if o1 != o2 and o3 != o4 and 0 not in (o1, o2, o3, o4):
                return False
            if (o1 == 0 and on(p1, p2, p3)) or (o2 == 0 and on(p1, p2, p4)) or \
                    (o3 == 0 and on(p3, p4, p1)) or (o4 == 0 and on(p3, p4, p2)):
                return False
    return True


def _polygon_triangles(k: int, f: tuple, v: np.ndarray) -> list:
    """Triangles covering exactly polygon `f` (projected on its Newell plane).

    Convex polygon: fan from the first vertex (the triangulation the v014 Max parity was measured with). Concave:
    ear clipping, so no triangle covers area outside the polygon whatever the first vertex or the winding.
    Self-intersecting polygon: ValueError (unsupported, never a guessed cover). Zero-area polygon: fan (all its
    triangles have no area and take part in the vertex check only).
    """
    if len(f) == 3:
        return [f]
    fan = [(f[0], f[m], f[m + 1]) for m in range(1, len(f) - 1)]
    p = v[list(f)]
    nrm = np.cross(p, np.roll(p, -1, axis=0)).sum(0)            # Newell, 2 x area vector
    ax = int(np.argmax(np.abs(nrm)))
    fan_area = sum(np.linalg.norm(np.cross(v[b] - v[a], v[c] - v[a])) / 2 for a, b, c in fan)
    if abs(nrm[ax]) / 2 <= AREA_EPS_M2:
        if fan_area > AREA_EPS_M2:
            raise ValueError(f"face {k}: self-intersecting polygon (no plane area) is not supported")
        return fan
    q = p[:, [i for i in range(3) if i != ax]]
    if (q[:, 0] * np.roll(q[:, 1], -1) - np.roll(q[:, 0], -1) * q[:, 1]).sum() < 0:
        q = q[:, ::-1]                                            # counter-clockwise in 2D
    q = q - q.mean(0)
    scale = max(float(np.abs(q).max()), 1e-12)
    eps = 1e-12 * scale * scale

    def cross(o, a, b):
        return (q[a, 0] - q[o, 0]) * (q[b, 1] - q[o, 1]) - (q[a, 1] - q[o, 1]) * (q[b, 0] - q[o, 0])

    n = len(f)
    if not _simple(q, eps):
        raise ValueError(f"face {k}: self-intersecting polygon is not supported")
    if all(cross(i, (i + 1) % n, (i + 2) % n) >= -eps for i in range(n)):
        return fan
    idx, out = list(range(n)), []
    while len(idx) > 3:
        m = len(idx)
        ear = None
        for e in range(m):
            a, b, c = idx[e - 1], idx[e], idx[(e + 1) % m]
            if cross(a, b, c) <= eps:
                continue
            if not any(cross(a, b, x) >= -eps and cross(b, c, x) >= -eps and cross(c, a, x) >= -eps
                       for x in idx if x not in (a, b, c) and not any((q[x] == q[y]).all() for y in (a, b, c))):
                ear = e
                break
        if ear is None:                                           # collinear corner: drop it, area unchanged
            ear = next((e for e in range(m) if abs(cross(idx[e - 1], idx[e], idx[(e + 1) % m])) <= eps), None)
            if ear is None:
                raise ValueError(f"face {k}: polygon could not be triangulated")
        out.append((idx[ear - 1], idx[ear], idx[(ear + 1) % m]))
        idx.pop(ear)
    out.append(tuple(idx))
    if any(cross(a, b, c) < -eps for a, b, c in out):
        raise ValueError(f"face {k}: polygon could not be triangulated")
    return [tuple(f[i] for i in t) for t in out]


_FAST_AREA_M2 = 1e-6         # fast quad path only above 1 mm2; smaller quads take the exact per-polygon path
_FAST_MARGIN = 4.0          # fast quad path only with every corner turn > 4 eps (the per-polygon eps)


def _fast_quads(v: np.ndarray, q: np.ndarray) -> np.ndarray:
    """Bool per quad (rows of vertex ids): `_polygon_triangles` certainly returns its fan.

    A quad whose every corner turn is > eps in 2D is convex and simple (any 3 of its 4 corners are consecutive, so
    every orientation `_simple` tests is non-zero), hence `_polygon_triangles` returns the fan. The fast path asks for
    a margin (turns > 4 eps, area > 1 mm2, a dominant projection axis that is not a near tie) so float order cannot
    flip the decision; every other quad goes through `_polygon_triangles` itself.
    """
    p = v[q]                                                      # (n, 4, 3)
    c = np.cross(p, np.roll(p, -1, axis=1))
    nrm = ((c[:, 0] + c[:, 1]) + c[:, 2]) + c[:, 3]
    an = np.abs(nrm)
    ax = np.argmax(an, axis=1)
    r = np.arange(len(q))
    top = an[r, ax]
    second = np.sort(an, axis=1)[:, 1]
    keep = np.array([[1, 2], [0, 2], [0, 1]])[ax]
    q2 = np.take_along_axis(p, np.repeat(keep[:, None, :], 4, axis=1), axis=2)   # (n, 4, 2)
    x, y = q2[..., 0], q2[..., 1]
    s = x * np.roll(y, -1, axis=1) - np.roll(x, -1, axis=1) * y
    signed = ((s[:, 0] + s[:, 1]) + s[:, 2]) + s[:, 3]
    q2 = np.where((signed < 0)[:, None, None], q2[..., ::-1], q2)
    q2 = q2 - q2.mean(axis=1, keepdims=True)
    scale = np.maximum(np.abs(q2).reshape(len(q), -1).max(axis=1), 1e-12)
    eps = 1e-12 * scale * scale
    a, b, d = q2, np.roll(q2, -1, axis=1), np.roll(q2, -2, axis=1)
    turn = (b[..., 0] - a[..., 0]) * (d[..., 1] - a[..., 1]) - (b[..., 1] - a[..., 1]) * (d[..., 0] - a[..., 0])
    with np.errstate(invalid="ignore"):
        return (top / 2 > _FAST_AREA_M2) & (second < top * (1 - 1e-6)) & \
            np.all(turn > _FAST_MARGIN * eps[:, None], axis=1) & (np.abs(signed) / 2 > _FAST_AREA_M2)


def _triangulate(mesh: PolyMesh):
    """(triangles, owner polygon) in polygon order; equal to `_polygon_triangles` per polygon.

    Triangles pass through; convex quads with a margin (`_fast_quads`) are fanned in numpy; every other polygon
    goes through `_polygon_triangles` (exact, may raise for a self-intersecting polygon).
    """
    faces, v = mesh.faces, mesh.vertices
    nf = len(faces)
    if not nf:
        return np.zeros((0, 3), np.int64), np.zeros(0, np.int64)
    size = np.fromiter((len(f) for f in faces), np.int64, nf)
    fast = size == 3
    qi = np.flatnonzero(size == 4)
    quads = np.asarray([faces[k] for k in qi], dtype=np.int64).reshape(-1, 4)
    if len(qi):
        fast[qi] = _fast_quads(v, quads)
    slow = {int(k): _polygon_triangles(int(k), faces[k], v) for k in np.flatnonzero(~fast)}
    count = np.where(size == 3, 1, 2)
    for k, ts in slow.items():
        count[k] = len(ts)
    first = np.cumsum(count) - count
    tris = np.zeros((int(count.sum()), 3), np.int64)
    ti = np.flatnonzero((size == 3) & fast)
    if len(ti):
        tris[first[ti]] = np.asarray([faces[k] for k in ti], dtype=np.int64)
    fq = fast[qi] if len(qi) else np.zeros(0, bool)
    if fq.any():
        k, q = qi[fq], quads[fq]
        tris[first[k]] = q[:, [0, 1, 2]]
        tris[first[k] + 1] = q[:, [0, 2, 3]]
    for k, ts in slow.items():
        if ts:
            tris[first[k]:first[k] + len(ts)] = np.asarray(ts, dtype=np.int64)
    return tris, np.repeat(np.arange(nf, dtype=np.int64), count)


def _grid_pairs(lo, hi, pad, active=None):
    """Unordered triangle pairs whose boxes, padded by `pad`, overlap; yields blocks (a, b) with a != b.

    Uniform grid over [lo, hi + pad] per triangle: two such boxes overlap iff lo_j <= hi_i + pad and lo_i <= hi_j +
    pad on every axis (the sweep test of #370), and then they share a grid cell. A pair is emitted only in the lowest
    cell both cover, so each pair comes once. `active` (bool per triangle): only pairs with an active triangle.
    """
    n = len(lo)
    if n < 2:
        return
    top = hi + pad
    ext = (top - lo).max(axis=1)
    cell = max(float(np.percentile(ext, 90)), 4 * pad, 1e-6)
    base = lo.min(axis=0)
    while True:
        cl = np.floor((lo - base) / cell).astype(np.int64)
        ch = np.floor((top - base) / cell).astype(np.int64)
        span = ch - cl + 1
        cnt = span.prod(axis=1)
        if cnt.sum() <= 16 * n + 1_000_000:
            break
        cell *= 2                                                  # a few huge triangles: coarser grid
    dims = ch.max(axis=0) + 1
    tot = int(cnt.sum())
    tri = np.repeat(np.arange(n), cnt)
    k = np.arange(tot) - np.repeat(np.cumsum(cnt) - cnt, cnt)
    syz = (span[:, 1] * span[:, 2])[tri]
    cx = cl[tri, 0] + k // syz
    rem = k % syz
    cy = cl[tri, 1] + rem // span[tri, 2]
    cz = cl[tri, 2] + rem % span[tri, 2]
    code = (cx * dims[1] + cy) * dims[2] + cz
    order = np.argsort(code, kind="stable")
    code, tri, cx, cy, cz = code[order], tri[order], cx[order], cy[order], cz[order]
    if active is not None:                                        # cells with an active triangle only
        hot = np.unique(code[active[tri]])
        sel = np.isin(code, hot)
        code, tri, cx, cy, cz = code[sel], tri[sel], cx[sel], cy[sel], cz[sel]
    m = len(code)
    if m < 2:
        return
    grp_end = np.searchsorted(code, code, "right")
    cntp = grp_end - np.arange(m) - 1
    start = 0
    while start < m:
        acc = np.cumsum(cntp[start:])
        stop = start + max(1, int(np.searchsorted(acc, _CHUNK, "right")))
        c = cntp[start:stop]
        if c.sum():
            i = np.repeat(np.arange(start, stop), c)
            j = i + 1 + (np.arange(c.sum()) - np.repeat(np.cumsum(c) - c, c))
            a, b = tri[i], tri[j]
            ok = (cx[i] == np.maximum(cl[a, 0], cl[b, 0])) & (cy[i] == np.maximum(cl[a, 1], cl[b, 1])) & \
                (cz[i] == np.maximum(cl[a, 2], cl[b, 2]))
            ok &= np.all((lo[b] <= top[a]) & (lo[a] <= top[b]), axis=1)
            if active is not None:
                ok &= active[a] | active[b]
            yield a[ok], b[ok]
        start = stop


def _owns(poly_key, key):
    """Bool per key: key is in the sorted unique array poly_key."""
    if not len(poly_key):
        return np.zeros(len(key), bool)
    i = np.minimum(np.searchsorted(poly_key, key), len(poly_key) - 1)
    return poly_key[i] == key


def _contact(v, tris, nrm, s, t, poly_key, owner, nv, face_m):
    """Bool per pair: a vertex of triangle t, not a vertex of the polygon of s, projects into s within face_m."""
    hit = np.zeros(len(s), dtype=bool)
    a, b, c = (v[tris[s, k]] for k in range(3))
    e0, e1 = b - a, c - a
    d00, d01, d11 = _dot(e0, e0), _dot(e0, e1), _dot(e1, e1)
    den = d00 * d11 - d01 * d01
    for k in range(3):
        p_id = tris[t, k]
        own = _owns(poly_key, owner[s] * nv + p_id)
        w = v[p_id] - a
        dist = _dot(w, nrm[s])
        q = w - dist[:, None] * nrm[s]
        d20, d21 = _dot(q, e0), _dot(q, e1)
        bv = (d11 * d20 - d01 * d21) / den
        bw = (d00 * d21 - d01 * d20) / den
        inside = (bv >= -1e-12) & (bw >= -1e-12) & (bv + bw <= 1 + 1e-12)
        hit |= inside & (np.abs(dist) <= face_m) & ~own
    return hit


_SKIP_M = 1e-6               # area prefilter margin: far above float rounding at site coordinates


def _area(v, tris, nrm, s, t, face_m, prefilter=True):
    """(bool, separation_m) per pair: projected overlap area > AREA_MIN_M2 with separation <= face_m on it.

    Shapely runs only on pairs that can pass: the separation is measured from points of s (its overlap with t lies
    inside s) to the plane of t, so it lies between the min and max over s's corners; when that whole range is
    beyond face_m + `_SKIP_M` on one side, or the projected boxes are apart by more than `_SKIP_M`, the pair fails
    and keeps separation inf. A skipped pair is never a hit, and the reported separation of a polygon pair is the
    minimum over its hit triangle pairs only (as in #370), so skipping changes nothing. Returns (hit, sep, skipped).
    """
    n = len(s)
    ax = np.argmax(np.abs(nrm[s]), axis=1)
    keep = np.array([[1, 2], [0, 2], [0, 1]])[ax]
    ps, pt = v[tris[s]], v[tris[t]]
    a2 = np.take_along_axis(ps, np.repeat(keep[:, None, :], 3, axis=1), axis=2)
    b2 = np.take_along_axis(pt, np.repeat(keep[:, None, :], 3, axis=1), axis=2)
    dk = np.einsum("nkj,nj->nk", ps - pt[:, :1], nrm[t])
    lim = face_m + _SKIP_M
    maybe = np.ones(n, bool) if not prefilter else (dk.min(axis=1) <= lim) & (dk.max(axis=1) >= -lim) & \
        np.all((a2.min(axis=1) <= b2.max(axis=1) + _SKIP_M) & (b2.min(axis=1) <= a2.max(axis=1) + _SKIP_M), axis=1)
    area = np.zeros(n)
    sep = np.full(n, np.inf)
    mi = np.flatnonzero(maybe)
    if not mi.size:
        return np.zeros(n, bool), sep, ~maybe
    inter = shapely.intersection(shapely.polygons(a2[mi]), shapely.polygons(b2[mi]))
    area[mi] = np.atleast_1d(shapely.area(inter))
    sub = np.flatnonzero(area[mi] > AREA_MIN_M2)
    if sub.size:
        cand = mi[sub]
        xy, idx = shapely.get_coordinates(inter[sub], return_index=True)
        pair = cand[idx]
        ns, p0 = nrm[s[pair]], ps[pair, 0]
        k0, k1, kd = keep[pair, 0], keep[pair, 1], ax[pair]
        r = np.arange(len(pair))
        pt3 = np.zeros((len(pair), 3))
        pt3[r, k0], pt3[r, k1] = xy[:, 0], xy[:, 1]
        off = (ns[r, k0] * (xy[:, 0] - p0[r, k0]) + ns[r, k1] * (xy[:, 1] - p0[r, k1]))
        pt3[r, kd] = p0[r, kd] - off / ns[r, kd]
        dj = _dot(pt3 - pt[pair, 0], nrm[t[pair]])
        lo = np.full(n, np.inf); hi = np.full(n, -np.inf); mn = np.full(n, np.inf)
        np.minimum.at(lo, pair, dj); np.maximum.at(hi, pair, dj); np.minimum.at(mn, pair, np.abs(dj))
        sep[cand] = np.where((lo[cand] <= 0) & (hi[cand] >= 0), 0.0, mn[cand])
    return (area > AREA_MIN_M2) & (sep <= face_m), sep, ~maybe


def _prepare(mesh: PolyMesh):
    v = mesh.vertices
    tris, owner = _triangulate(mesh)
    nv = len(v)
    poly_key = np.unique(np.concatenate([np.full(len(f), k, np.int64) * nv + np.asarray(f, np.int64)
                                         for k, f in enumerate(mesh.faces)])) if mesh.faces else np.zeros(0, np.int64)
    return tris, owner, poly_key


def _pairs_found(v, tris, owner, poly_key, tol: XviewTolerance, active=None) -> dict:
    """{(i, j): (contact, area, separation)} 0-based polygons i < j; with `active` only pairs touching it."""
    found: dict = {}
    if not len(tris):
        return found
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
    lo, hi = p.min(1), p.max(1)
    rank = np.empty(len(tris), np.int64)
    rank[np.argsort(lo[:, 0], kind="stable")] = np.arange(len(tris))   # pair orientation of the #370 x sweep
    for s, t in _grid_pairs(lo, hi, pad, active):
        ok = (owner[s] != owner[t]) & live[s] & live[t]
        s, t = s[ok], t[ok]
        ok = np.abs(_dot(nrm[s], nrm[t])) >= tol.parallel_cos_min
        s, t = s[ok], t[ok]
        if not len(s):
            continue
        sw = rank[s] > rank[t]
        s, t = np.where(sw, t, s), np.where(sw, s, t)
        con = _contact(v, tris, nrm, s, t, poly_key, owner, nv, tol.face_m) | \
            _contact(v, tris, nrm, t, s, poly_key, owner, nv, tol.face_m)
        hit_a, sep, _ = _area(v, tris, nrm, s, t, tol.face_m)
        for k in np.flatnonzero(con | hit_a):
            i, j = sorted((int(owner[s[k]]), int(owner[t[k]])))
            prev = found.get((i, j), (False, False, np.inf))
            found[(i, j)] = (prev[0] or bool(con[k]), prev[1] or bool(hit_a[k]), min(prev[2], float(sep[k])))
    return found


def _kind(c: bool, ar: bool) -> str:
    return "area+contact" if c and ar else ("contact" if c else "area")


def face_pairs(mesh: PolyMesh, tol: XviewTolerance) -> list:
    """[(i, j, kind, separation_m)] 0-based polygon pairs i < j."""
    tris, owner, poly_key = _prepare(mesh)
    found = _pairs_found(mesh.vertices, tris, owner, poly_key, tol)
    return [(i, j, _kind(c, ar), sp if np.isfinite(sp) else None) for (i, j), (c, ar, sp) in sorted(found.items())]


# ---- the invariant -------------------------------------------------------------------------------------------------

def part_report(part: str, mesh, tol: XviewTolerance) -> PartXviewReport:
    mesh = _as_poly(mesh)
    a, b, d = vertex_pairs(mesh.vertices, tol.vertex_m)
    vp = tuple((int(x) + 1, int(y) + 1, float(z)) for x, y, z in zip(a, b, d))
    fp = tuple((i + 1, j + 1, k, s) for i, j, k, s in face_pairs(mesh, tol))
    offenders = [f"{part} v{x}/v{y}: {z * 1000:.2f} mm" for x, y, z in vp]
    offenders += [f"{part} f{i}/f{j}: {k}" + ("" if s is None else f", {s * 1000:.2f} mm") for i, j, k, s in fp]
    if not mesh.faces:
        offenders.append(f"{part}: no faces")
    return PartXviewReport(part, vp, fp, tuple(sorted({x for p in vp for x in p[:2]})),
                           tuple(sorted({x for p in fp for x in p[:2]})),
                           tuple(sorted({x for p in fp if "contact" in p[2] for x in p[:2]})), tuple(offenders))


def xview_report(scene: Mapping, profile: str, parts: Iterable[str] | None = None,
                 tol: XviewTolerance | None = None) -> dict:
    """part id -> PartXviewReport for `parts` (None = every part)."""
    base = tolerance_for(profile)          # an unknown profile is an error even with an explicit tol
    tol = (tol or base).validate()
    names = list(dict.fromkeys(scene if parts is None else parts))
    missing = [p for p in names if p not in scene]
    if missing:
        raise ValueError(f"parts not in the scene: {missing}")
    return {p: part_report(p, scene[p], tol) for p in names}


def xview_overlaps(scene: Mapping, profile: str, parts: Iterable[str] | None = None,
                   tol: XviewTolerance | None = None, gating: bool = True) -> InvariantResult:
    """The invariant over `parts` (None = all); no part to check is a failure, never a vacuous pass."""
    reports = xview_report(scene, profile, parts, tol)
    if not reports:
        return InvariantResult(NAME, False, 1, ("no parts to check",), gating)
    offenders = [o for r in reports.values() for o in r.offenders]
    return InvariantResult(NAME, not offenders, len(offenders), tuple(offenders[:5]), gating)


def check_operation_xview(report: InvariantReport, after_polys: Mapping, changed: Iterable[str], profile: str,
                          tol: XviewTolerance | None = None, gating: bool = False) -> InvariantReport:
    """`check_operation`'s report followed by xview_overlaps over the changed parts (report-only by default)."""
    if any(r.name == NAME for r in report.results):
        raise ValueError("the report already has an xview_overlaps result")
    changed = list(changed)
    missing = [p for p in changed if p not in after_polys]
    if missing:
        raise ValueError(f"changed parts without a mesh: {missing}")
    return InvariantReport(tuple(report.results) + (xview_overlaps(after_polys, profile, changed, tol, gating),))


def mesh_report(vertices, faces, profile: str = "NPM", tol: XviewTolerance | None = None, part: str = "mesh") -> dict:
    """JSON-ready report-only entry for one mesh (build reports, e.g. the Ground build)."""
    tol = (tol or tolerance_for(profile)).validate()
    if not np.isfinite(np.asarray(vertices, dtype=float)).all():
        raise ValueError("vertices must be finite")
    faces = faces.tolist() if isinstance(faces, np.ndarray) and faces.dtype.kind in "iu" else faces
    if isinstance(faces, np.ndarray):
        raise ValueError(f"face indices are not an integer array (dtype {faces.dtype})")
    # no int() / np.asarray coercion here: PolyMesh rejects bool and fractional indices by name
    mesh = PolyMesh(np.asarray(vertices, dtype=float), tuple(tuple(f) for f in faces))
    r = part_report(part, mesh, tol)
    return {"name": NAME, "gating": False, "passed": not r.offenders, "count": len(r.offenders),
            "thresholds": {"vertex_m": tol.vertex_m, "face_m": tol.face_m, "parallel_cos_min": tol.parallel_cos_min},
            **r.to_dict()}


# ---- per-part state and incremental re-check (#535) ----------------------------------------------------------------

STATE_NAME = "xview_face_state"
STATE_VERSION = 2                                   # v2: face_pairs_sha256 + validated inventory (#554 review)


def _state_mesh(vertices, faces) -> PolyMesh:
    if not np.isfinite(np.asarray(vertices, dtype=float)).all():
        raise ValueError("vertices must be finite")
    faces = faces.tolist() if isinstance(faces, np.ndarray) and faces.dtype.kind in "iu" else faces
    if isinstance(faces, np.ndarray):
        raise ValueError(f"face indices are not an integer array (dtype {faces.dtype})")
    mesh = PolyMesh(np.asarray(vertices, dtype=float), tuple(tuple(f) for f in faces))
    if not mesh.faces:
        raise ValueError("no faces: nothing to check")
    return mesh


def _labels(face_part, nf: int) -> list:
    labels = list(face_part)
    if len(labels) != nf:
        raise ValueError(f"face_part has {len(labels)} labels for {nf} faces")
    bad = sorted({repr(x) for x in labels if not isinstance(x, str) or not x})
    if bad:
        raise ValueError(f"part labels must be non-empty strings, got {bad[:5]}")
    return labels


def _runs(labels: list) -> list:
    out: list = []
    for x in labels:
        if out and out[-1][0] == x:
            out[-1][1] += 1
        else:
            out.append([x, 1])
    return out


def _digests(mesh: PolyMesh, labels: list):
    """(parts {name: {faces, hash}}, links [[a, b, hash]]): geometry + vertex sharing a face-pair result depends on.

    Part hash: polygon sizes, corner vertex ids renumbered by first use inside the part, and those vertices' float64
    coordinates. Link hash per two parts that share vertex indices: the sorted (local id in a, local id in b) pairs.
    """
    import hashlib
    v = mesh.vertices
    by_part: dict = {}
    for k, x in enumerate(labels):
        by_part.setdefault(x, []).append(k)
    parts, gv, gp, gl = {}, [], [], []
    names = sorted(by_part)
    for pi, name in enumerate(names):
        fs = [mesh.faces[k] for k in by_part[name]]
        sizes = np.fromiter((len(f) for f in fs), np.int64, len(fs))
        cv = np.fromiter((i for f in fs for i in f), np.int64, int(sizes.sum()))
        u, first, inv = np.unique(cv, return_index=True, return_inverse=True)
        rank = np.empty(len(u), np.int64)
        rank[np.argsort(first, kind="stable")] = np.arange(len(u))
        local = rank[inv]
        coords = np.ascontiguousarray(v[u[np.argsort(first, kind="stable")]], dtype=np.float64)
        h = hashlib.sha256(sizes.tobytes() + b"|" + local.tobytes() + b"|" + coords.tobytes()).hexdigest()
        parts[name] = {"faces": len(fs), "hash": h}
        gv.append(u); gp.append(np.full(len(u), pi, np.int64)); gl.append(rank)
    gv, gp, gl = np.concatenate(gv), np.concatenate(gp), np.concatenate(gl)
    o = np.lexsort((gp, gv))
    gv, gp, gl = gv[o], gp[o], gl[o]
    lo = np.searchsorted(gv, gv, "left")
    hi = np.searchsorted(gv, gv, "right")
    shared: dict = {}
    for s in np.flatnonzero((hi - lo > 1) & (np.arange(len(gv)) == lo)):
        grp = range(int(lo[s]), int(hi[s]))
        for x in grp:
            for y in grp:
                if gp[x] < gp[y]:
                    shared.setdefault((names[gp[x]], names[gp[y]]), []).append((int(gl[x]), int(gl[y])))
    links = [[a, b, hashlib.sha256(np.asarray(sorted(pr), np.int64).tobytes()).hexdigest()]
             for (a, b), pr in sorted(shared.items())]
    return parts, links


def _pairs_digest(pairs) -> str:
    """SHA-256 of the canonical JSON of `face_pairs`: a truncated, padded or edited pair list no longer matches."""
    import hashlib
    import json
    rows = [[int(i), int(j), str(k), None if sp is None else float(sp)] for i, j, k, sp in pairs]
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode("ascii")).hexdigest()


def _is_id(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _is_real(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _check_previous(previous: Mapping) -> list:
    """Validate the reusable inventory of a previous state; return its 0-based-ready face labels (old_labels).

    Every key the incremental run reads or reproduces must be present with its shape; the pair list must be sorted,
    unique, in range, match its digest and the `faces` / `xview_faces` summaries. Any gap -> ValueError("previous
    report: ..."), never a silently smaller result.
    """
    def bad(msg):
        raise ValueError(f"previous report: {msg}")
    for key, typ in (("parts", Mapping), ("runs", list), ("links", list), ("vertex_pairs", list), ("face_pairs", list),
                     ("faces", list), ("xview_faces", list), ("vertices", list), ("face_pairs_sha256", str)):
        if not isinstance(previous.get(key), typ):
            bad(f"{key} missing or not a {typ.__name__} (incomplete report: run a full check)")
    parts = previous["parts"]
    for name, p in parts.items():
        if not (isinstance(name, str) and name and isinstance(p, Mapping) and _is_id(p.get("faces"))
                and p["faces"] > 0 and isinstance(p.get("hash"), str) and len(p["hash"]) == 64):
            bad(f"part {name!r}: {p!r} is not {{faces: int > 0, hash: sha256}}")
    old_labels: list = []
    for row in previous["runs"]:
        if not (isinstance(row, list) and len(row) == 2 and row[0] in parts and _is_id(row[1]) and row[1] > 0):
            bad(f"bad run {row!r}")
        old_labels.extend([row[0]] * row[1])
    counts: dict = {}
    for x in old_labels:
        counts[x] = counts.get(x, 0) + 1
    if counts != {k: p["faces"] for k, p in parts.items()}:
        bad("runs and part face counts disagree")
    for row in previous["links"]:
        if not (isinstance(row, list) and len(row) == 3 and row[0] in parts and row[1] in parts
                and isinstance(row[2], str)):
            bad(f"bad link {row!r}")
    n = len(old_labels)
    pairs = previous["face_pairs"]
    for row in pairs:
        if not (isinstance(row, list) and len(row) == 4 and _is_id(row[0]) and _is_id(row[1])
                and 1 <= row[0] < row[1] <= n and row[2] in ("contact", "area", "area+contact")
                and (row[3] is None or _is_real(row[3]))):
            bad(f"bad face pair {row!r}")
    keys = [(r[0], r[1]) for r in pairs]
    if keys != sorted(set(keys)):
        bad("face_pairs not sorted or duplicated")
    if _pairs_digest(pairs) != previous["face_pairs_sha256"]:
        bad("face_pairs do not match face_pairs_sha256 (truncated or edited): run a full check")
    if previous["faces"] != sorted({x for r in pairs for x in r[:2]}) or \
            previous["xview_faces"] != sorted({x for r in pairs if "contact" in r[2] for x in r[:2]}):
        bad("faces / xview_faces summaries disagree with face_pairs")
    return old_labels


def _state(mesh, labels, tol, found: dict) -> dict:
    a, b, d = vertex_pairs(mesh.vertices, tol.vertex_m)
    parts, links = _digests(mesh, labels)
    pairs = [[i + 1, j + 1, _kind(c, ar), sp if np.isfinite(sp) else None]
             for (i, j), (c, ar, sp) in sorted(found.items())]
    return {"name": STATE_NAME, "version": STATE_VERSION,
            "thresholds": {"vertex_m": tol.vertex_m, "face_m": tol.face_m, "parallel_cos_min": tol.parallel_cos_min},
            "parts": parts, "runs": _runs(labels), "links": links,
            "vertex_pairs": [[int(x) + 1, int(y) + 1, float(z)] for x, y, z in zip(a, b, d)],
            "face_pairs": pairs, "face_pairs_sha256": _pairs_digest(pairs),
            "vertices": sorted({int(x) + 1 for x in np.concatenate([a, b])}),
            "faces": sorted({x for p in pairs for x in p[:2]}),
            "xview_faces": sorted({x for p in pairs if "contact" in p[2] for x in p[:2]})}


def xview_state(vertices, faces, face_part, profile: str = "NPM", tol: XviewTolerance | None = None) -> dict:
    """Full face + vertex check of one mesh whose faces are labelled by part; JSON-ready, input of the incremental run.

    `face_pairs` / `xview_faces` / `vertex_pairs` equal `part_report` on the same mesh (1-based ids); `parts`,
    `runs` and `links` record what `xview_state_incremental` must find unchanged to reuse a pair.
    """
    tol = (tol or tolerance_for(profile)).validate()
    mesh = _state_mesh(vertices, faces)
    labels = _labels(face_part, len(mesh.faces))
    tris, owner, poly_key = _prepare(mesh)
    return _state(mesh, labels, tol, _pairs_found(mesh.vertices, tris, owner, poly_key, tol))


def xview_state_incremental(vertices, faces, face_part, previous: Mapping, changed: Iterable[str],
                            profile: str = "NPM", tol: XviewTolerance | None = None) -> dict:
    """`xview_state` of the new mesh, re-checking only the faces of `changed` parts against their neighbours.

    Face pairs between two unchanged parts are taken from `previous` (renumbered to the new face ids); every pair
    with a face of a changed part is computed again, its candidates found in the grid cells of the changed faces
    (padded by face_m). The vertex check is cheap and always runs in full.
    Fail-closed (ValueError naming the cause): `previous` is not a state of this version or has other thresholds; a
    changed name is in neither mesh; a part added, removed or edited (hash) without being in `changed`; vertex sharing
    between two unchanged parts differs; the unchanged faces are in another relative order (pair orientation, hence
    the area separation, depends on it); `previous` is incomplete or inconsistent (a key missing, a pair row malformed,
    out of range, unsorted or duplicated, `face_pairs` not matching `face_pairs_sha256` or the `faces` /
    `xview_faces` summaries, runs not matching part face counts). Then the result equals `xview_state`.
    """
    tol = (tol or tolerance_for(profile)).validate()
    mesh = _state_mesh(vertices, faces)
    labels = _labels(face_part, len(mesh.faces))
    if not isinstance(previous, Mapping) or previous.get("name") != STATE_NAME or \
            previous.get("version") != STATE_VERSION:
        raise ValueError(f"previous is not a {STATE_NAME} v{STATE_VERSION} report")
    want = {"vertex_m": tol.vertex_m, "face_m": tol.face_m, "parallel_cos_min": tol.parallel_cos_min}
    if previous.get("thresholds") != want:
        raise ValueError(f"previous thresholds {previous.get('thresholds')} differ from {want}: run a full check")
    changed = set(changed) if not isinstance(changed, str) else {changed}
    old_labels = _check_previous(previous)
    old_parts = previous["parts"]
    parts, links = _digests(mesh, labels)
    unknown = sorted(changed - set(parts) - set(old_parts))
    if unknown:
        raise ValueError(f"changed parts in neither mesh: {unknown}")
    added = sorted(set(parts) - set(old_parts) - changed)
    removed = sorted(set(old_parts) - set(parts) - changed)
    if added or removed:
        raise ValueError(f"parts added {added} / removed {removed} but not listed as changed")
    keep = set(parts) - changed
    edited = sorted(x for x in keep if parts[x] != old_parts[x])
    if edited:
        raise ValueError(f"parts changed but not listed as changed: {edited}")
    lk = {(a, b, h) for a, b, h in links if a in keep and b in keep}
    old_lk = {(a, b, h) for a, b, h in previous["links"] if a in keep and b in keep}
    if lk != old_lk:
        diff = sorted({(a, b) for a, b, _ in lk ^ old_lk})
        raise ValueError(f"vertex sharing between unchanged parts differs: {diff[:5]}")
    if _runs([x for x in labels if x in keep]) != _runs([x for x in old_labels if x in keep]):
        raise ValueError("unchanged faces are in another relative order: run a full check")
    # (part, local index) -> new 0-based face id, for unchanged parts
    new_id: dict = {}
    seen: dict = {}
    for k, x in enumerate(labels):
        if x in keep:
            new_id[(x, seen.get(x, 0))] = k
        seen[x] = seen.get(x, 0) + 1
    old_loc, seen = [], {}
    for x in old_labels:
        old_loc.append((x, seen.get(x, 0)))
        seen[x] = seen.get(x, 0) + 1
    found: dict = {}
    for i, j, kind, sp in previous["face_pairs"]:                    # validated by _check_previous
        a, b = old_loc[i - 1], old_loc[j - 1]
        if a[0] in keep and b[0] in keep:
            ni, nj = sorted((new_id[a], new_id[b]))
            found[(ni, nj)] = ("contact" in kind, "area" in kind, np.inf if sp is None else float(sp))
    tris, owner, poly_key = _prepare(mesh)
    hot = np.fromiter((x not in keep for x in labels), bool, len(labels))
    if hot.any():
        found.update(_pairs_found(mesh.vertices, tris, owner, poly_key, tol, active=hot[owner]))
    return _state(mesh, labels, tol, found)
