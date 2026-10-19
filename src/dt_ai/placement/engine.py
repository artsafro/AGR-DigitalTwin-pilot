"""Placement engine: Flora / MAF instances on SPOZU points over a Ground triangle mesh (#316).

Pattern: none (REVIEW_CHECKLIST Q1: new-case: seeded, fail-closed placement of library entries on SPOZU points,
pure numpy / shapely, no DCC).

Rules implemented
- Flora [D100] (FLO-17, model-flora step 8): the plant's horizontal centre (bbox centre) on the SPOZU point, its
  lowest point ``sink_m`` (0.10 m) below the topmost Ground surface; random Z rotation uniform in [0, 360) and
  uniform scale in [0.9, 1.1] narrowed so that height x scale and crown x scale stay inside the schedule band
  +-20 % [D099]. The point rotation is ignored. Randomness is derived from ``sha256(seed, point handle)``, so the
  result does not depend on the point order.
- MAF [D095] (MAF-23, model-maf step 8): pivot = footprint centre (bbox centre XY) at the lowest point + 0.10 m,
  projected onto the Ground; rot_z = the SPOZU INSERT rotation, DXF convention: degrees, counter-clockwise about
  +Z (``adapters/cad/spozu.py`` ``PointItem.rotation`` = ``INSERT.dxf.rotation``). Bottom faces [D096] (MAF-20):
  ``delete`` only when the Ground covers the face (every candidate point has a height, no Ground border edge
  touches or lies inside the outline) and the topmost Ground is strictly above the face plane at every point
  where the piecewise-linear gap can be minimal: face vertices, Ground vertices inside the outline, Ground edge /
  outline crossings, and for stacked layers (triangles overlapping in XY, whatever the mesh connectivity) their
  edge / edge crossings, switch lines plane_a == plane_b and switch-line crossings. Otherwise ``review``.
  Dimension deviation from ``spec_dims_m`` > 0.10 m [D094] is reported as a warning, not enforced.
- Fail-closed [D108, D126]: every point gets an instance or a ``failed`` record with a code; any failure makes
  the run status ``fail``; nothing is dropped silently. ``placed + failed == input`` per library id.

Ground heights: vertical downward ray, topmost hit (stacked plates 6 mm apart: the top plate wins). Triangles
with zero XY area (vertical or degenerate) are not hit by a vertical ray and are skipped (counted in the report).

CLI: ``uv run python -m dt_ai.placement.engine --input in.json --output out.json``; exit 0 pass, 3 review,
1 fail, 2 bad invocation (unreadable input, output path or existing output file identity (hard link) equal to
the input: nothing is written).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import shapely
from shapely.geometry import LineString, Polygon

SCHEMA = "dt_ai.placement/1"
SINK_M = 0.10            # [D095], [D100]
SCALE_JITTER = 0.10      # [D100]
BAND_TOL = 0.20          # [D099]
DIMS_TOL_M = 0.10        # [D094], reported only
COVER_EPS_M = 1e-6       # "strictly above": gap must exceed this
XY_AREA_EPS = 1e-12      # twice the XY area below which a triangle is not hit by a vertical ray
BARY_EPS = 1e-9
WELD_M = 1e-6            # position weld for border-edge topology
PLANAR_TOL_M = 1e-4
BAND_EPS = 1e-9

ERROR, REVIEW, WARN, INFO = "error", "review", "warn", "info"


class GroundError(ValueError):
    pass


# ---------------------------------------------------------------------------- Ground
class GroundIndex:
    """Topmost-hit vertical ray queries on a triangle mesh, plus its border edges (mesh border and holes)."""

    def __init__(self, vertices: Any, triangles: Any):
        try:
            V = np.asarray(vertices, dtype=float)
            T0 = np.asarray(triangles)
        except (TypeError, ValueError) as exc:
            raise GroundError(f"not numeric arrays: {exc}") from None
        if V.ndim != 2 or V.shape[1] != 3:
            raise GroundError(f"vertices shape {V.shape}, expected (N, 3)")
        if T0.size == 0:
            raise GroundError("no triangles")
        if T0.ndim != 2 or T0.shape[1] != 3:
            raise GroundError(f"triangles shape {T0.shape}, expected (M, 3)")
        if not np.issubdtype(T0.dtype, np.integer):
            if not (np.issubdtype(T0.dtype, np.floating) and np.all(np.isfinite(T0)) and np.all(T0 == np.round(T0))):
                raise GroundError("triangle indices are not integers")
        T = T0.astype(np.int64)
        if T.min() < 0 or T.max() >= len(V):
            raise GroundError(f"triangle index out of range 0..{len(V) - 1}")
        if not np.all(np.isfinite(V[np.unique(T)])):
            raise GroundError("non-finite vertex coordinate")
        P = V[T]
        a2 = ((P[:, 1, 0] - P[:, 0, 0]) * (P[:, 2, 1] - P[:, 0, 1])
              - (P[:, 2, 0] - P[:, 0, 0]) * (P[:, 1, 1] - P[:, 0, 1]))
        keep = np.abs(a2) > XY_AREA_EPS
        if not keep.any():
            raise GroundError(f"degenerate: all {len(T)} triangles have zero XY area")
        self.n_input = int(len(T))
        self.skipped = int((~keep).sum())
        self.T = T[keep]
        self.V = V
        self.P = P[keep]
        self.a2 = a2[keep]
        e1 = self.P[:, 1] - self.P[:, 0]
        e2 = self.P[:, 2] - self.P[:, 0]
        nrm = np.cross(e1, e2)  # nrm[:, 2] == a2 != 0
        self.alpha = -nrm[:, 0] / nrm[:, 2]  # triangle plane z = alpha x + beta y + gamma
        self.beta = -nrm[:, 1] / nrm[:, 2]
        self.gamma = self.P[:, 0, 2] - self.alpha * self.P[:, 0, 0] - self.beta * self.P[:, 0, 1]
        lo = self.P[:, :, :2].min(1)
        hi = self.P[:, :, :2].max(1)
        self.tlo, self.thi = lo, hi
        self.xmin, self.ymin = lo.min(0)
        self.xmax, self.ymax = hi.max(0)
        n = len(self.T)
        span = max(self.xmax - self.xmin, self.ymax - self.ymin, 1e-9)
        self.cell = max(span / max(1.0, math.sqrt(n / 2.0)), 1e-6)
        cells: dict[tuple[int, int], list[int]] = {}
        i0 = np.floor((lo - [self.xmin, self.ymin]) / self.cell).astype(int)
        i1 = np.floor((hi - [self.xmin, self.ymin]) / self.cell).astype(int)
        for t in range(n):
            for i in range(i0[t, 0], i1[t, 0] + 1):
                for j in range(i0[t, 1], i1[t, 1] + 1):
                    cells.setdefault((i, j), []).append(t)
        self.cells = {k: np.asarray(v, dtype=np.int64) for k, v in cells.items()}
        self._topology()

    def _topology(self) -> None:
        keys = np.round(self.V / WELD_M).astype(np.int64)
        _, weld = np.unique(keys, axis=0, return_inverse=True)
        weld = weld.ravel()
        W = weld[self.T]
        e = np.concatenate([W[:, [0, 1]], W[:, [1, 2]], W[:, [2, 0]]])
        e.sort(axis=1)
        _, inv, cnt = np.unique(e, axis=0, return_inverse=True, return_counts=True)
        inv = inv.ravel()
        border = cnt[inv] == 1
        tri_of_edge = np.tile(np.arange(len(self.T)), 3)
        corner = np.concatenate([self.T[:, [0, 1]], self.T[:, [1, 2]], self.T[:, [2, 0]]])
        segs = self.V[corner][:, :, :2]
        self.border = segs[border]
        # welded vertex ids per triangle: same-sheet neighbours (shared welded vertex, no XY overlap) agree where
        # they touch; connectivity is NOT used as a proof that two sheets do not overlap (review r1, PR #323)
        self.W = W
        self.edge_tri = tri_of_edge
        self.edge_segs = segs

    def _cells(self, x0: float, y0: float, x1: float, y1: float) -> np.ndarray:
        i0 = math.floor((x0 - self.xmin) / self.cell)
        i1 = math.floor((x1 - self.xmin) / self.cell)
        j0 = math.floor((y0 - self.ymin) / self.cell)
        j1 = math.floor((y1 - self.ymin) / self.cell)
        found = [self.cells[(i, j)] for i in range(i0, i1 + 1) for j in range(j0, j1 + 1) if (i, j) in self.cells]
        return np.unique(np.concatenate(found)) if found else np.zeros(0, dtype=np.int64)

    def tris_in_box(self, x0: float, y0: float, x1: float, y1: float) -> np.ndarray:
        c = self._cells(x0, y0, x1, y1)
        if len(c) == 0:
            return c
        ok = ((self.tlo[c, 0] <= x1) & (self.thi[c, 0] >= x0) & (self.tlo[c, 1] <= y1) & (self.thi[c, 1] >= y0))
        return c[ok]

    def height(self, x: float, y: float) -> float | None:
        """Topmost Ground z under (x, y), or None when no triangle covers the point."""
        c = self.tris_in_box(x, y, x, y)
        if len(c) == 0:
            return None
        P = self.P[c]
        x0, y0 = P[:, 0, 0], P[:, 0, 1]
        x1, y1 = P[:, 1, 0], P[:, 1, 1]
        x2, y2 = P[:, 2, 0], P[:, 2, 1]
        d = self.a2[c]
        l1 = ((x - x0) * (y2 - y0) - (x2 - x0) * (y - y0)) / d
        l2 = ((x1 - x0) * (y - y0) - (x - x0) * (y1 - y0)) / d
        l0 = 1.0 - l1 - l2
        hit = (l0 >= -BARY_EPS) & (l1 >= -BARY_EPS) & (l2 >= -BARY_EPS)
        if not hit.any():
            return None
        z = l0 * P[:, 0, 2] + l1 * P[:, 1, 2] + l2 * P[:, 2, 2]
        return float(z[hit].max())

    def in_extent(self, x: float, y: float) -> bool:
        return self.xmin <= x <= self.xmax and self.ymin <= y <= self.ymax


def _seg_cross(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """Pairwise proper/touching intersection points of XY segments A (n,2,2) and B (m,2,2); parallel pairs skipped."""
    if len(A) == 0 or len(B) == 0:
        return np.zeros((0, 2))
    p, r = A[:, None, 0], (A[:, 1] - A[:, 0])[:, None]
    q, s = B[None, :, 0], (B[:, 1] - B[:, 0])[None]
    den = r[..., 0] * s[..., 1] - r[..., 1] * s[..., 0]
    qp = q - p
    with np.errstate(divide="ignore", invalid="ignore"):
        t = (qp[..., 0] * s[..., 1] - qp[..., 1] * s[..., 0]) / den
        u = (qp[..., 0] * r[..., 1] - qp[..., 1] * r[..., 0]) / den
        ok = (np.abs(den) > 1e-15) & (t >= -BARY_EPS) & (t <= 1 + BARY_EPS) & (u >= -BARY_EPS) & (u <= 1 + BARY_EPS)
        pts = p + t[..., None] * r
    return pts[ok]


def _line_cross(a: np.ndarray, b: np.ndarray, c: np.ndarray, S: np.ndarray) -> np.ndarray:
    """Points where the lines a x + b y + c = 0 (n,) cross the segments S (n, k, 2, 2)."""
    s0 = a[:, None] * S[..., 0, 0] + b[:, None] * S[..., 0, 1] + c[:, None]
    s1 = a[:, None] * S[..., 1, 0] + b[:, None] * S[..., 1, 1] + c[:, None]
    ok = (s0 * s1 <= 0) & (s0 != s1)
    with np.errstate(divide="ignore", invalid="ignore"):
        t = s0 / (s0 - s1)
        pts = S[..., 0, :] + t[..., None] * (S[..., 1, :] - S[..., 0, :])
    return pts[ok]


def _layer_pairs(g: GroundIndex, tris: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Triangle pairs whose XY footprints overlap, i.e. stacked Ground layers, whatever the mesh connectivity:
    every pair whose closures intersect, except same-sheet neighbours (a shared welded vertex and no XY area
    overlap), which agree wherever they touch. Two sheets joined outside the footprint are still two layers."""
    if len(tris) < 2:
        z = np.zeros(0, dtype=np.int64)
        return z, z
    polys = shapely.polygons(g.P[tris][:, :, :2])
    i, j = shapely.STRtree(polys).query(polys, predicate="intersects")
    m = i < j
    i, j = i[m], j[m]
    Wa, Wb = g.W[tris[i]], g.W[tris[j]]
    shared = (Wa[:, :, None] == Wb[:, None, :]).any(axis=(1, 2))
    if shared.any():
        k = np.nonzero(shared)[0]
        area = shapely.area(shapely.intersection(polys[i[k]], polys[j[k]]))
        drop = np.zeros(len(i), dtype=bool)
        drop[k[area <= XY_AREA_EPS]] = True
        i, j = i[~drop], j[~drop]
    return tris[i], tris[j]


def _tri_edges(g: GroundIndex, t: np.ndarray) -> np.ndarray:
    Pt = g.P[t][:, :, :2]
    return np.stack([Pt, np.roll(Pt, -1, axis=1)], axis=2)  # (n, 3, 2, 2)


def _pair_edge_cross(Ea: np.ndarray, Eb: np.ndarray) -> np.ndarray:
    """Crossing points of the 3 x 3 edge pairs of each triangle pair (Ea, Eb: (n, 3, 2, 2))."""
    if len(Ea) == 0:
        return np.zeros((0, 2))
    A = np.repeat(Ea, 3, axis=1)  # (n, 9, 2, 2)
    B = np.tile(Eb, (1, 3, 1, 1))
    p, r = A[..., 0, :], A[..., 1, :] - A[..., 0, :]
    q, s = B[..., 0, :], B[..., 1, :] - B[..., 0, :]
    den = r[..., 0] * s[..., 1] - r[..., 1] * s[..., 0]
    qp = q - p
    with np.errstate(divide="ignore", invalid="ignore"):
        t = (qp[..., 0] * s[..., 1] - qp[..., 1] * s[..., 0]) / den
        u = (qp[..., 0] * r[..., 1] - qp[..., 1] * r[..., 0]) / den
        ok = (np.abs(den) > 1e-15) & (t >= -BARY_EPS) & (t <= 1 + BARY_EPS) & (u >= -BARY_EPS) & (u <= 1 + BARY_EPS)
        pts = p + t[..., None] * r
    return pts[ok]


def _layer_crossings(g: GroundIndex, ta: np.ndarray, tb: np.ndarray, ring: np.ndarray,
                     outline: Polygon) -> list[np.ndarray]:
    """Where stacked Ground layers overlap, the topmost surface can switch layer at an edge / edge crossing or
    along the line plane_a == plane_b; the minimum of the upper envelope can lie at such a crossing, on that
    line where it crosses a triangle edge or the outline, or (three or more layers) where two such lines cross."""
    out: list[np.ndarray] = []
    if len(ta) == 0:
        return out
    Ea, Eb = _tri_edges(g, ta), _tri_edges(g, tb)
    X = _pair_edge_cross(Ea, Eb)
    if len(X):
        out.append(X[shapely.covers(outline, shapely.points(X))])
    a = g.alpha[ta] - g.alpha[tb]
    b = g.beta[ta] - g.beta[tb]
    c = g.gamma[ta] - g.gamma[tb]
    keep = np.hypot(a, b) > 1e-12  # parallel planes (e.g. plates 6 mm apart) never cross
    if not keep.any():
        return out
    a, b, c = a[keep], b[keep], c[keep]
    n = len(a)
    S = np.concatenate([Ea[keep], Eb[keep], np.broadcast_to(ring, (n,) + ring.shape)], axis=1)
    X = _line_cross(a, b, c, S)
    if len(X):
        out.append(X[shapely.covers(outline.buffer(1e-9), shapely.points(X))])
    lines = [np.stack([a, b, c], axis=1)]
    if n >= 2:
        Lm = np.unique(np.concatenate(lines), axis=0)
        for k in range(0, len(Lm), 512):  # pairwise line crossings (triple points), chunked
            L1 = Lm[k:k + 512, None]
            L2 = Lm[None]
            det = L1[..., 0] * L2[..., 1] - L1[..., 1] * L2[..., 0]
            with np.errstate(divide="ignore", invalid="ignore"):
                x = (L1[..., 1] * L2[..., 2] - L1[..., 2] * L2[..., 1]) / det
                y = (L1[..., 2] * L2[..., 0] - L1[..., 0] * L2[..., 2]) / det
            ok = np.abs(det) > 1e-12
            X = np.stack([x[ok], y[ok]], axis=1)
            if len(X):
                out.append(X[shapely.covers(outline, shapely.points(X))])
    return out


def bottom_face_verdict(g: GroundIndex, face: np.ndarray) -> dict:
    """Classify one world-space bottom face (k x 3) as delete / review (model-maf step 8, [D095], [D096])."""
    reasons: list[str] = []
    xy = face[:, :2]
    n = np.zeros(3)
    for i in range(len(face)):  # Newell normal
        a, b = face[i], face[(i + 1) % len(face)]
        n += [(a[1] - b[1]) * (a[2] + b[2]), (a[2] - b[2]) * (a[0] + b[0]), (a[0] - b[0]) * (a[1] + b[1])]
    nn = float(np.linalg.norm(n))
    outline = Polygon(xy)
    if nn == 0 or not outline.is_valid or outline.area <= 1e-9:
        return {"action": "review", "reasons": ["face_degenerate"], "min_gap_m": None}
    if abs(n[2]) <= 1e-6 * nn:
        return {"action": "review", "reasons": ["face_not_horizontal"], "min_gap_m": None}
    c = face.mean(0)

    def plane_z(px, py):
        return c[2] - (n[0] * (px - c[0]) + n[1] * (py - c[1])) / n[2]

    if np.max(np.abs(face[:, 2] - plane_z(face[:, 0], face[:, 1]))) > PLANAR_TOL_M:
        return {"action": "review", "reasons": ["face_nonplanar"], "min_gap_m": None}
    x0, y0 = xy.min(0)
    x1, y1 = xy.max(0)
    B = g.border
    near = ((np.minimum(B[:, 0, 0], B[:, 1, 0]) <= x1) & (np.maximum(B[:, 0, 0], B[:, 1, 0]) >= x0)
            & (np.minimum(B[:, 0, 1], B[:, 1, 1]) <= y1) & (np.maximum(B[:, 0, 1], B[:, 1, 1]) >= y0))
    if near.any() and bool(np.any(shapely.intersects(shapely.linestrings(B[near]), outline))):
        reasons.append("ground_border")
    samples = [xy]
    tris = g.tris_in_box(x0, y0, x1, y1)
    if len(tris):
        gv = g.P[tris][:, :, :2].reshape(-1, 2)
        inside = shapely.covers(outline, shapely.points(gv))
        samples.append(gv[inside])
        sel = np.isin(g.edge_tri, tris)
        E = g.edge_segs[sel]
        ring = np.stack([xy, np.roll(xy, -1, axis=0)], axis=1)
        samples.append(_seg_cross(E, ring))
        ta, tb = _layer_pairs(g, tris)
        samples.extend(_layer_crossings(g, ta, tb, ring, outline))
    S = np.concatenate(samples)
    gaps = []
    missing = False
    for px, py in S:
        h = g.height(float(px), float(py))
        if h is None:
            missing = True
        else:
            gaps.append(h - plane_z(px, py))
    if missing:
        reasons.append("ground_missing")
    min_gap = float(min(gaps)) if gaps else None
    if min_gap is not None and min_gap <= COVER_EPS_M:
        reasons.append("exposed_bottom")
    return {"action": "review" if reasons else "delete", "reasons": reasons, "min_gap_m": min_gap,
            "samples": int(len(S))}


# ---------------------------------------------------------------------------- inputs
def _get(rec: Any, name: str, default: Any = KeyError) -> Any:
    if isinstance(rec, dict):
        if name in rec:
            return rec[name]
    elif hasattr(rec, name):
        return getattr(rec, name)
    if default is KeyError:
        raise KeyError(name)
    return default


def _finite(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _vec(v: Any, n: int) -> list[float] | None:
    try:
        seq = list(v)
    except TypeError:
        return None
    if len(seq) != n:
        return None
    out = [_finite(c) for c in seq]
    return None if any(c is None for c in out) else out  # type: ignore[return-value]


def _parse_entry(e: Any) -> tuple[str | None, dict | None, str | None]:
    """-> (id, parsed entry, error)."""
    try:
        eid = _get(e, "id", None)
        eid = str(eid) if eid not in (None, "") else None
        if eid is None:
            return None, None, "id missing"
        kind = _get(e, "kind", None)
        if kind not in ("flora", "maf"):
            return eid, None, f"kind {kind!r} not flora|maf"
        lo, hi = _vec(_get(e, "bbox_min", None), 3), _vec(_get(e, "bbox_max", None), 3)
        if lo is None or hi is None:
            return eid, None, "bbox_min / bbox_max missing or non-finite"
        if any(b < a for a, b in zip(lo, hi)):
            return eid, None, "bbox_max below bbox_min"
        out: dict = {"id": eid, "kind": kind, "bbox_min": lo, "bbox_max": hi,
                     "centre_xy": [(lo[0] + hi[0]) / 2.0, (lo[1] + hi[1]) / 2.0], "lowest_z": lo[2]}
        if kind == "flora":
            hm, cm = hi[2] - lo[2], max(hi[0] - lo[0], hi[1] - lo[1])
            hs, cs = _finite(_get(e, "schedule_height_m", None)), _finite(_get(e, "schedule_crown_m", None))
            if hs is None or cs is None or hs <= 0 or cs <= 0:
                return eid, None, "schedule_height_m / schedule_crown_m missing, non-finite or <= 0"
            if hm <= 0 or cm <= 0:
                return eid, None, "model height or crown is zero"
            out.update(model_height_m=hm, model_crown_m=cm, schedule_height_m=hs, schedule_crown_m=cs)
        else:
            faces = _get(e, "bottom_faces", None)
            if faces is None:
                return eid, None, "bottom_faces missing (use [] for a MAF without bottom faces)"
            parsed = []
            for k, f in enumerate(faces):
                try:
                    pts = [_vec(p, 3) for p in f]
                except TypeError:
                    pts = [None]
                if len(pts) < 3 or any(p is None for p in pts):
                    return eid, None, f"bottom face {k} has < 3 vertices or non-finite coordinates"
                parsed.append(pts)
            out["bottom_faces"] = parsed
            dims = _get(e, "spec_dims_m", None)
            if dims is not None:
                d = _vec(dims, 3)
                if d is None or min(d) <= 0:
                    return eid, None, "spec_dims_m not three finite positive numbers"
                out["spec_dims_m"] = d
        return eid, out, None
    except Exception as exc:  # malformed record: fail closed with the reason
        return None, None, f"unreadable entry: {exc!r}"


def _canon(v: Any) -> Any:
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, dict):
        return {str(k): _canon(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_canon(x) for x in v]
    if isinstance(v, np.ndarray):
        return _canon(v.tolist())
    if isinstance(v, (np.floating, np.integer)):
        return _canon(v.item())
    return v


def _sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(_canon(obj), sort_keys=True, default=repr).encode()).hexdigest()


def _ground_hash(vertices: Any, triangles: Any) -> str:
    try:
        V = np.ascontiguousarray(np.asarray(vertices, dtype=np.float64))
        T = np.ascontiguousarray(np.asarray(triangles, dtype=np.int64))
        h = hashlib.sha256(repr((V.shape, T.shape)).encode())
        h.update(V.tobytes())
        h.update(T.tobytes())
        return h.hexdigest()
    except (TypeError, ValueError):
        return _sha([vertices, triangles])


def _uniforms(seed: int, handle: str) -> tuple[float, float]:
    d = hashlib.sha256(f"{seed}\x1f{handle}".encode()).digest()
    u = [(int.from_bytes(d[i:i + 8], "big") >> 11) / float(1 << 53) for i in (0, 8)]
    return u[0], u[1]


def _matrix(pivot: list[float], rot_deg: float, scale: float, anchor: list[float]) -> list[list[float]]:
    """World = T(pivot) . Rz(rot) . S(scale) . T(-anchor); row-major 4x4, column vectors."""
    a = math.radians(rot_deg)
    c, s = math.cos(a), math.sin(a)
    R = np.array([[c * scale, -s * scale, 0.0], [s * scale, c * scale, 0.0], [0.0, 0.0, scale]])
    t = np.asarray(pivot) - R @ np.asarray(anchor)
    M = np.eye(4)
    M[:3, :3] = R
    M[:3, 3] = t
    return M.tolist()


def _apply(M: list[list[float]], pts: np.ndarray) -> np.ndarray:
    A = np.asarray(M)
    return pts @ A[:3, :3].T + A[:3, 3]


# ---------------------------------------------------------------------------- engine
def place(points: Any, ground_vertices: Any, ground_triangles: Any, library: Any, seed: Any, *,
          label_map: dict | None = None, sink_m: float = SINK_M) -> dict:
    """Compute one instance per SPOZU point, or a failed record with its code; returns the report dict."""
    findings: list[dict] = []

    def finding(code, severity, handle=None, library_id=None, detail=""):
        findings.append({"code": code, "severity": severity, "handle": handle, "library_id": library_id,
                         "detail": detail})

    points = list(points or [])
    lib_list = list(library or [])
    hashes = {
        "points": _sha(sorted(json.dumps(_canon({k: _get(p, k, None) for k in
                                                ("x", "y", "z", "label", "position", "handle", "inside",
                                                 "rotation")}), sort_keys=True, default=repr) for p in points)),
        "ground": _ground_hash(ground_vertices, ground_triangles),
        "library": _sha(sorted(json.dumps(_canon(e if isinstance(e, dict) else vars(e)), sort_keys=True,
                                          default=repr) for e in lib_list)),
    }

    seed_ok = isinstance(seed, (int, np.integer)) and not isinstance(seed, bool)
    if not seed_ok:
        finding("seed_invalid", ERROR, detail=f"seed must be an int, got {seed!r}")
    seed_val = int(seed) if seed_ok else None

    ground: GroundIndex | None = None
    try:
        ground = GroundIndex(ground_vertices, ground_triangles)
    except GroundError as exc:
        finding("ground_invalid", ERROR, detail=str(exc))
    if ground is not None and ground.skipped:
        finding("ground_triangles_skipped", WARN, detail=f"{ground.skipped} zero-XY-area triangles not ray-hit")

    entries: dict[str, dict] = {}
    entry_err: dict[str, str] = {}
    seen: dict[str, int] = {}
    for e in lib_list:
        eid, parsed, err = _parse_entry(e)
        if eid is None:
            finding("library_entry_invalid", ERROR, detail=err or "")
            continue
        seen[eid] = seen.get(eid, 0) + 1
        if err:
            entry_err[eid] = err
        elif parsed is not None:
            entries[eid] = parsed
    for eid, k in seen.items():
        if k > 1:
            entry_err[eid] = f"library id appears {k} times"
            entries.pop(eid, None)
    lib_summary: dict[str, dict] = {}
    for eid, err in entry_err.items():
        finding("library_entry_invalid", WARN, library_id=eid, detail=err)
        lib_summary[eid] = {"valid": False, "error": err}
    for eid, e in entries.items():
        info: dict = {"valid": True, "kind": e["kind"]}
        if e["kind"] == "flora":
            hr = e["model_height_m"] / e["schedule_height_m"]
            cr = e["model_crown_m"] / e["schedule_crown_m"]
            band_ok = all(1 - BAND_TOL - BAND_EPS <= r <= 1 + BAND_TOL + BAND_EPS for r in (hr, cr))
            info.update(height_ratio=hr, crown_ratio=cr)
            if not band_ok:
                e["band_error"] = f"model/schedule height {hr:.4f}, crown {cr:.4f} outside 1 +- {BAND_TOL}"
                info.update(valid=False, error=e["band_error"])
                finding("flora_out_of_band", WARN, library_id=eid, detail=e["band_error"])
            else:
                lo = max(1 - SCALE_JITTER, (1 - BAND_TOL) / hr, (1 - BAND_TOL) / cr)
                hi = min(1 + SCALE_JITTER, (1 + BAND_TOL) / hr, (1 + BAND_TOL) / cr)
                e["scale_range"] = [min(lo, 1.0), max(hi, 1.0)]
                info["scale_range"] = e["scale_range"]
                if e["scale_range"] != [1 - SCALE_JITTER, 1 + SCALE_JITTER]:
                    finding("flora_scale_narrowed", INFO, library_id=eid,
                            detail=f"scale range {e['scale_range'][0]:.6f}..{e['scale_range'][1]:.6f}")
        else:
            info["bottom_faces"] = len(e["bottom_faces"])
            if "spec_dims_m" in e:
                lo, hi = e["bbox_min"], e["bbox_max"]
                model = sorted([hi[0] - lo[0], hi[1] - lo[1]], reverse=True) + [hi[2] - lo[2]]
                spec = sorted(e["spec_dims_m"][:2], reverse=True) + [e["spec_dims_m"][2]]
                delta = [m - s for m, s in zip(model, spec)]
                info["dims_delta_m"] = delta
                if max(abs(d) for d in delta) > DIMS_TOL_M + BAND_EPS:
                    finding("maf_dims_off_spec", WARN, library_id=eid,
                            detail=f"model - spec (L, W, H) = {[round(d, 4) for d in delta]} m, limit {DIMS_TOL_M}")
        lib_summary[eid] = info

    # read the points
    recs = []
    for p in points:
        r: dict = {}
        for k in ("x", "y", "z", "rotation"):
            raw = _get(p, k, 0.0 if k == "rotation" else None)
            r[k] = _finite(raw)
            r["raw_" + k] = repr(raw)
        h = _get(p, "handle", None)
        r["handle"] = str(h) if h not in (None, "") else None
        lab = _get(p, "label", None)
        r["label"] = str(lab) if lab not in (None, "") else None
        r["inside"] = _get(p, "inside", None)
        recs.append(r)
    handle_count: dict[str, int] = {}
    for r in recs:
        if r["handle"] is not None:
            handle_count[r["handle"]] = handle_count.get(r["handle"], 0) + 1
    if not recs:
        finding("no_points", ERROR, detail="empty point list")

    instances: list[dict] = []
    failed: list[dict] = []
    exposed: list[dict] = []
    counts: dict[str, dict] = {}

    for r in recs:
        lid = None
        if r["label"] is not None:
            lid = str(label_map.get(r["label"], r["label"])) if label_map is not None else r["label"]
            if label_map is not None and r["label"] not in label_map:
                lid = None
        key = lid if lid is not None else (r["label"] if r["label"] is not None else "<no label>")
        cnt = counts.setdefault(key, {"input": 0, "placed": 0, "failed": 0})
        cnt["input"] += 1
        pos = f"x={r['raw_x']} y={r['raw_y']} z={r['raw_z']} rot={r['raw_rotation']}"
        code, detail = None, ""
        e = entries.get(lid) if lid is not None else None
        if not seed_ok:
            code, detail = "seed_invalid", repr(seed)
        elif ground is None:
            code = "ground_invalid"
        elif r["handle"] is None:
            code = "handle_missing"
        elif handle_count[r["handle"]] > 1:
            code = "duplicate_handle"
        elif any(r[k] is None for k in ("x", "y", "z", "rotation")):
            code = "point_non_finite"
        elif r["label"] is None:
            code = "label_missing"
        elif lid is None or (lid not in entries and lid not in entry_err):
            code, detail = "library_id_unknown", f"label {r['label']!r} -> {lid!r}"
        elif lid in entry_err:
            code, detail = "library_entry_invalid", entry_err[lid]
        elif e is not None and e.get("band_error"):
            code, detail = "flora_out_of_band", e["band_error"]
        gz = None
        if code is None:
            assert ground is not None and e is not None
            gz = ground.height(r["x"], r["y"])
            if gz is None:
                code = "point_outside_ground" if not ground.in_extent(r["x"], r["y"]) else "point_over_ground_hole"
        if code is not None:
            cnt["failed"] += 1
            failed.append({"handle": r["handle"], "label": r["label"], "library_id": lid, "code": code,
                           "detail": (detail + "; " if detail else "") + pos})
            finding(code, ERROR, r["handle"], lid, (detail + "; " if detail else "") + pos)
            continue
        assert e is not None and gz is not None and seed_val is not None
        cx, cy = e["centre_xy"]
        pivot = [r["x"], r["y"], gz]
        if e["kind"] == "flora":
            u_rot, u_scale = _uniforms(seed_val, r["handle"])
            rot = 360.0 * u_rot
            s_lo, s_hi = e["scale_range"]
            scale = s_lo + (s_hi - s_lo) * u_scale
        else:
            rot = r["rotation"] % 360.0
            rot = 0.0 if rot >= 360.0 else rot + 0.0
            scale = 1.0
        anchor = [cx, cy, e["lowest_z"] + sink_m / scale]
        M = _matrix(pivot, rot, scale, anchor)
        low = float(_apply(M, np.array([[cx, cy, e["lowest_z"]]]))[0, 2])
        inst = {"handle": r["handle"], "label": r["label"], "library_id": lid, "kind": e["kind"],
                "pivot_x": pivot[0], "pivot_y": pivot[1], "pivot_z": pivot[2], "rot_z_deg": rot, "scale": scale,
                "ground_z": gz, "sink_m": gz - low, "anchor_local": anchor, "matrix": M, "inside": r["inside"]}
        if e["kind"] == "maf":
            verdicts = []
            for k, f in enumerate(e["bottom_faces"]):
                v = bottom_face_verdict(ground,  # type: ignore[arg-type]
                     _apply(M, np.asarray(f, dtype=float)))
                v = {"face": k, **v}
                verdicts.append(v)
                if v["action"] == "review":
                    finding("bottom_face_review", REVIEW, r["handle"], lid, f"face {k}: {', '.join(v['reasons'])}")
                if "exposed_bottom" in v["reasons"]:
                    exposed.append({"handle": r["handle"], "face": k, "min_gap_m": v["min_gap_m"]})
            inst["bottom_faces"] = verdicts
            inst["bottom_faces_deleted"] = sum(v["action"] == "delete" for v in verdicts)
        cnt["placed"] += 1
        instances.append(inst)

    for c in counts.values():
        if c["placed"] + c["failed"] != c["input"]:  # internal invariant; never silently wrong
            raise AssertionError(f"count mismatch {c}")
    totals = {k: sum(c[k] for c in counts.values()) for k in ("input", "placed", "failed")}
    if totals["input"] != len(points) or totals["placed"] != len(instances) or totals["failed"] != len(failed):
        raise AssertionError(f"totals mismatch {totals}")

    def skey(d):
        return json.dumps(_canon(d), sort_keys=True, default=repr)

    instances.sort(key=lambda d: (d["handle"], skey(d)))
    failed.sort(key=lambda d: (d["handle"] or "", skey(d)))
    findings.sort(key=lambda d: (d["code"], d["handle"] or "", d["library_id"] or "", d["detail"]))
    exposed.sort(key=lambda d: (d["handle"], d["face"]))
    sinks = [i["sink_m"] for i in instances]
    sev = {f["severity"] for f in findings}
    status = "fail" if (ERROR in sev or failed or not recs) else ("review" if sev & {REVIEW, WARN} else "pass")
    return {
        "schema": SCHEMA,
        "status": status,
        "seed": seed_val,
        "sink_target_m": sink_m,
        "input_hashes": hashes,
        "constants": {"scale_jitter": SCALE_JITTER, "band_tol": BAND_TOL, "dims_tol_m": DIMS_TOL_M,
                      "cover_eps_m": COVER_EPS_M, "rotation_unit": "degrees ccw about +Z (DXF INSERT rotation)"},
        "ground": None if ground is None else {"triangles": ground.n_input, "skipped_zero_xy_area": ground.skipped,
                                                 "border_edges": int(len(ground.border))},
        "library": lib_summary,
        "instances": instances,
        "failed": failed,
        "findings": findings,
        "exposed_bottoms": exposed,
        "counts": dict(sorted(counts.items())),
        "totals": totals,
        "sinking": {"n": len(sinks), "min_m": min(sinks) if sinks else None, "max_m": max(sinks) if sinks else None},
    }


def report_json(report: dict) -> str:
    """Deterministic strict JSON (sorted keys, no NaN): same seed + same inputs -> same bytes."""
    return json.dumps(report, sort_keys=True, indent=1, allow_nan=False, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m dt_ai.placement.engine", description="Flora / MAF placement on SPOZU points")
    ap.add_argument("--input", required=True, help="JSON: points, ground{vertices,triangles}, library, seed")
    ap.add_argument("--output", required=True, help="report JSON (new path, never the input)")
    a = ap.parse_args(argv)
    inp, out = Path(a.input), Path(a.output)
    same = out.resolve() == inp.resolve()
    try:  # an existing output may be a hard link (or other alias) of the input: same file identity
        same = same or (out.exists() and inp.exists() and os.path.samefile(inp, out))
    except OSError:
        same = True  # identity unknown: fail closed
    if same:
        print("output path is the input file (same path or same file identity); nothing written", file=sys.stderr)
        return 2
    try:
        data = json.loads(inp.read_text(encoding="utf-8"))
        g = data["ground"]
        rep = place(data["points"], g["vertices"], g["triangles"], data["library"], data.get("seed"),
                    label_map=data.get("label_map"))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"input unreadable: {exc!r}", file=sys.stderr)
        return 2
    out.write_text(report_json(rep), encoding="utf-8")
    print(f"status={rep['status']} placed={rep['totals']['placed']} failed={rep['totals']['failed']} -> {out}")
    return {"pass": 0, "review": 3}.get(rep["status"], 1)


if __name__ == "__main__":
    raise SystemExit(main())
