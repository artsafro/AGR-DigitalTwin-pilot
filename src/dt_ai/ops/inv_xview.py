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


def _triangulate(mesh: PolyMesh):
    tris, owner = [], []
    for k, f in enumerate(mesh.faces):
        for t in _polygon_triangles(k, f, mesh.vertices):
            tris.append(t)
            owner.append(k)
    return np.asarray(tris, dtype=np.int64).reshape(-1, 3), np.asarray(owner, dtype=np.int64)


def _bbox_pairs(lo, hi, pad):
    """Triangle pairs (s < t in sweep order) whose bounding boxes, padded by `pad`, overlap; yields blocks."""
    n = len(lo)
    order = np.argsort(lo[:, 0], kind="stable")
    los, his = lo[order], hi[order]
    end = np.searchsorted(los[:, 0], his[:, 0] + pad, "right")
    cnt = np.maximum(end - np.arange(n) - 1, 0)
    start = 0
    while start < n:
        stop = start + 1
        acc = np.cumsum(cnt[start:])
        stop = start + max(1, int(np.searchsorted(acc, _CHUNK, "right")))
        c = cnt[start:stop]
        if c.sum():
            i = np.repeat(np.arange(start, stop), c)
            j = i + 1 + (np.arange(c.sum()) - np.repeat(np.cumsum(c) - c, c))
            ok = np.all((los[j, 1:] <= his[i, 1:] + pad) & (los[i, 1:] <= his[j, 1:] + pad), axis=1)
            yield order[i[ok]], order[j[ok]]
        start = stop


def _contact(v, tris, nrm, s, t, poly_key, owner, nv, face_m):
    """Bool per pair: a vertex of triangle t, not a vertex of the polygon of s, projects into s within face_m."""
    hit = np.zeros(len(s), dtype=bool)
    a, b, c = (v[tris[s, k]] for k in range(3))
    e0, e1 = b - a, c - a
    d00, d01, d11 = _dot(e0, e0), _dot(e0, e1), _dot(e1, e1)
    den = d00 * d11 - d01 * d01
    for k in range(3):
        p_id = tris[t, k]
        own = np.isin(owner[s] * nv + p_id, poly_key)
        w = v[p_id] - a
        dist = _dot(w, nrm[s])
        q = w - dist[:, None] * nrm[s]
        d20, d21 = _dot(q, e0), _dot(q, e1)
        bv = (d11 * d20 - d01 * d21) / den
        bw = (d00 * d21 - d01 * d20) / den
        inside = (bv >= -1e-12) & (bw >= -1e-12) & (bv + bw <= 1 + 1e-12)
        hit |= inside & (np.abs(dist) <= face_m) & ~own
    return hit


def _area(v, tris, nrm, s, t, face_m):
    """(bool, separation_m) per pair: projected overlap area > AREA_MIN_M2 with separation <= face_m on it."""
    n = len(s)
    ax = np.argmax(np.abs(nrm[s]), axis=1)
    keep = np.array([[1, 2], [0, 2], [0, 1]])[ax]
    ps, pt = v[tris[s]], v[tris[t]]
    a2 = np.take_along_axis(ps, np.repeat(keep[:, None, :], 3, axis=1), axis=2)
    b2 = np.take_along_axis(pt, np.repeat(keep[:, None, :], 3, axis=1), axis=2)
    inter = shapely.intersection(shapely.polygons(a2), shapely.polygons(b2))
    area = np.atleast_1d(shapely.area(inter))
    sep = np.full(n, np.inf)
    cand = np.flatnonzero(area > AREA_MIN_M2)
    if cand.size:
        xy, idx = shapely.get_coordinates(inter[cand], return_index=True)
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
    return (area > AREA_MIN_M2) & (sep <= face_m), sep


def face_pairs(mesh: PolyMesh, tol: XviewTolerance) -> list:
    """[(i, j, kind, separation_m)] 0-based polygon pairs i < j."""
    v = mesh.vertices
    tris, owner = _triangulate(mesh)
    if not len(tris):
        return []
    nv = len(v)
    poly_key = np.unique(np.concatenate([np.full(len(f), k, np.int64) * nv + np.asarray(f, np.int64)
                                         for k, f in enumerate(mesh.faces)]))
    p = v[tris]
    origin = p[:, 0]
    cr = np.cross(p[:, 1] - origin, p[:, 2] - origin)
    ln = np.linalg.norm(cr, axis=1)
    if not np.isfinite(ln).all():
        raise ValueError("derived triangle geometry is not finite")
    live = ln / 2 > AREA_EPS_M2
    nrm = np.divide(cr, ln[:, None], out=np.zeros_like(cr), where=live[:, None])
    pad = tol.face_m / max(tol.parallel_cos_min, 1e-9) + 1e-9
    found: dict = {}
    for s, t in _bbox_pairs(p.min(1), p.max(1), pad):
        ok = (owner[s] != owner[t]) & live[s] & live[t]
        s, t = s[ok], t[ok]
        ok = np.abs(_dot(nrm[s], nrm[t])) >= tol.parallel_cos_min
        s, t = s[ok], t[ok]
        if not len(s):
            continue
        con = _contact(v, tris, nrm, s, t, poly_key, owner, nv, tol.face_m) | \
            _contact(v, tris, nrm, t, s, poly_key, owner, nv, tol.face_m)
        hit_a, sep = _area(v, tris, nrm, s, t, tol.face_m)
        for k in np.flatnonzero(con | hit_a):
            i, j = sorted((int(owner[s[k]]), int(owner[t[k]])))
            prev = found.get((i, j), (False, False, np.inf))
            found[(i, j)] = (prev[0] or bool(con[k]), prev[1] or bool(hit_a[k]), min(prev[2], float(sep[k])))
    out = []
    for (i, j), (c, ar, sp) in sorted(found.items()):
        kind = "area+contact" if c and ar else ("contact" if c else "area")
        out.append((i, j, kind, sp if np.isfinite(sp) else None))
    return out


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
