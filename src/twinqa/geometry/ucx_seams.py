"""UCX checks ported from the Codex UCX skill pack (#2097), OBSERVE only (no gate, no refusal).

Pattern: n/a | new-case: Codex pack checks c3/c12/v5extra ported (facing-face seam gap, winding, slivers).

Source: `oks-collision-builder/scripts/check/` of the pack received 2026-11-28 (zip SHA-256 90d706a9...). Only the
checks our shared UCX checks lacked are ported; the rest is covered by `twinqa.geometry.ucx_audit`, V010 and
`ucx10_core.pair_census` [D339] (see docs/research/ucx-skill-pack-codex-2097.md):

- `seam_face_gaps` (their c3.py): the gap between two FACING faces over their whole projected overlap. The pair
  minimum (SAT, [D339]) does not prove the seam: a wedge seam can start at 5 mm and open to 25 mm. The gap between
  two planes is affine over the overlap polygon, so its minimum and maximum are exact at the overlap vertices.
  Classes against [D098] 2 mm - 1 cm: ok / tight (< 2 mm somewhere) / wedge (in band at one end, > 1 cm at the
  other) / slot (> 1 cm everywhere, up to `reach_m`).
- `winding_report` (their c12.py `badori` / negative volume): consistent winding and outward normals.
- `sliver_report` (their v5extra.py check 7): shortest edge and lowest triangle height (micro-faces).

numpy + shapely (project dependencies), no DCC.
"""
from __future__ import annotations

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

GAP_MIN_M, GAP_MAX_M = 0.002, 0.010  # [D098]
REACH_M = 0.30  # their c3 PAD / gap ceiling: facing faces farther apart are not a seam
FACING_DOT = -0.95  # their c3: anti-parallel within ~18 deg
MIN_OVERLAP_M2 = 0.005  # their c3
EDGE_MIN_M, HEIGHT_MIN_M = 0.01, 0.005  # their v5extra check 7 diagnostic thresholds (not a norm)


def _arr(verts, tris):
    return np.asarray(verts, float).reshape(-1, 3), np.asarray(tris, int).reshape(-1, 3)


def weld(verts, tris, tol=1e-5):
    """Merge coincident vertices (FBX splits them per face); drop triangles that collapse."""
    v, t = _arr(verts, tris)
    _, first, inv = np.unique(np.round(v / tol).astype(np.int64), axis=0, return_index=True, return_inverse=True)
    inv = inv.ravel()
    order = np.argsort(first)
    remap = np.empty_like(order)
    remap[order] = np.arange(len(order))
    vw = v[first[order]]
    tw = remap[inv][t]
    keep = (tw[:, 0] != tw[:, 1]) & (tw[:, 1] != tw[:, 2]) & (tw[:, 0] != tw[:, 2])
    return vw, tw[keep]


def planes(verts, tris, merge_m=1e-4):
    """Outward H-representation of a convex body: (normals (k,3), offsets (k,)), n.x <= d inside; coplanar merged.
    Orientation comes from the centroid, not from the winding (winding is reported separately)."""
    v, t = _arr(verts, tris)
    c = v.mean(axis=0)
    a, b, cc = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    n = np.cross(b - a, cc - a)
    ln = np.linalg.norm(n, axis=1)
    ok = ln > 1e-12
    n = n[ok] / ln[ok, None]
    d = (n * a[ok]).sum(axis=1)
    flip = (n @ c) > d
    n[flip], d[flip] = -n[flip], -d[flip]
    out_n, out_d = [], []
    for ni, di in zip(n, d):
        if any(float(ni @ m) > 1 - 1e-6 and abs(di - e) <= merge_m for m, e in zip(out_n, out_d)):
            continue
        out_n.append(ni)
        out_d.append(di)
    return np.array(out_n).reshape(-1, 3), np.array(out_d)


def _basis(n):
    a = np.array([1.0, 0, 0]) if abs(n[0]) < 0.9 else np.array([0, 1.0, 0])
    u = np.cross(n, a)
    u /= np.linalg.norm(u)
    return u, np.cross(n, u)


def faces(verts, tris):
    """Planar faces of a convex body: [(outward normal, offset, triangle corner array (m,3,3))]."""
    v, t = _arr(verts, tris)
    pn, pd = planes(v, t)
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    n = np.cross(b - a, c - a)
    ln = np.linalg.norm(n, axis=1)
    out = []
    for ni, di in zip(pn, pd):
        on = (ln > 1e-12) & (np.abs((a @ ni) - di) < 1e-4) & (np.abs((b @ ni) - di) < 1e-4) & (
            np.abs((c @ ni) - di) < 1e-4)
        if on.any():
            out.append((ni, float(di), np.stack([a[on], b[on], c[on]], axis=1)))
    return out


def _face_polygon(corners, u, w):
    return unary_union([Polygon(np.c_[tri @ u, tri @ w]) for tri in corners]).buffer(0)


def _aabb(v):
    return v.min(axis=0), v.max(axis=0)


def _classify(lo, hi):
    if lo < GAP_MIN_M - 1e-6:
        return "tight"
    if hi <= GAP_MAX_M + 1e-6:
        return "ok"
    if lo <= GAP_MAX_M + 1e-6:
        return "wedge"
    return "slot"


def seam_face_gaps(bodies, reach_m=REACH_M, min_overlap_m2=MIN_OVERLAP_M2, with_prism=False):
    """Every pair of facing faces (anti-parallel, overlapping in projection, apart by -1 mm .. reach_m) of every
    body pair: overlap area, exact gap min/max over the overlap, class. bodies: [{name, verts, tris}].
    with_prism: each row also carries `_prism` = (normals, offsets) of the open seam volume between the two faces
    over their overlap (n.x <= d inside), for a caller that measures what lies in the seam."""
    data = []
    for bd in bodies:
        v, t = weld(bd["verts"], bd["tris"])
        data.append((bd["name"], _aabb(v), faces(v, t)))
    rows = []
    for i in range(len(data)):
        ni, (loi, hii), fi = data[i]
        for j in range(i + 1, len(data)):
            nj, (loj, hij), fj = data[j]
            if np.any(loi - reach_m > hij) or np.any(loj - reach_m > hii):
                continue
            for na, da, ta in fi:
                for nb, db, tb in fj:
                    if float(na @ nb) > FACING_DOT:
                        continue
                    pts = tb.reshape(-1, 3) @ na - da
                    if pts.min() > reach_m or pts.max() < -1e-3:
                        continue
                    u, w = _basis(na)
                    ov = _face_polygon(ta, u, w).intersection(_face_polygon(tb, u, w))
                    if ov.is_empty or ov.area < min_overlap_m2:
                        continue
                    xy = np.vstack([np.asarray(g.exterior.coords) for g in getattr(ov, "geoms", [ov])
                                    if hasattr(g, "exterior")])
                    base = xy[:, :1] * u + xy[:, 1:2] * w
                    # point on face b's plane above each overlap vertex, along na
                    tpar = (db - base @ nb) / float(na @ nb)
                    gap = tpar - da
                    lo, hi = float(gap.min()), float(gap.max())
                    if lo < -1e-3 or lo > reach_m:
                        continue
                    rows.append({"a": ni, "b": nj, "overlap_area_m2": round(float(ov.area), 6),
                                 "gap_min_m": round(lo, 6), "gap_max_m": round(hi, 6),
                                 "gap_mean_m": round(float(gap.mean()), 6), "class": _classify(lo, hi),
                                 "normal_a": [round(float(x), 4) for x in na]})
                    if with_prism:
                        rows[-1]["_prism"] = _prism(ov, u, w, na, da, nb, db)
    return rows


def _prism(ov, u, w, na, da, nb, db, eps=1e-3):
    """Half-spaces of the seam volume: beyond face a, before face b (both by eps), inside the convex overlap."""
    hull = ov.convex_hull
    ring = np.asarray(hull.exterior.coords)[:-1]
    if Polygon(ring).exterior.is_ccw is False:
        ring = ring[::-1]
    pn, pd = [-na, -nb], [-(da + eps), -(db + eps)]
    for k in range(len(ring)):
        p, q = ring[k], ring[(k + 1) % len(ring)]
        e = q - p
        m2 = np.array([e[1], -e[0]])  # outward of a ccw ring
        lm = np.linalg.norm(m2)
        if lm < 1e-12:
            continue
        m2 /= lm
        n3 = m2[0] * u + m2[1] * w
        pn.append(n3)
        pd.append(float(m2 @ p))
    return np.array(pn), np.array(pd)


def winding_report(verts, tris):
    """Every directed edge used once and its reverse once (consistent winding); signed volume > 0 (outward)."""
    v, t = weld(verts, tris)
    directed = np.vstack([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]])
    pairs, counts = np.unique(directed, axis=0, return_counts=True)
    have = {tuple(p): c for p, c in zip(pairs.tolist(), counts.tolist())}
    consistent = bool(have) and all(c == 1 and have.get((b, a)) == 1 for (a, b), c in have.items())
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    vol = float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)
    return {"consistent": consistent, "outward": vol > 0, "signed_volume_m3": vol}


def sliver_report(verts, tris, edge_min_m=EDGE_MIN_M, height_min_m=HEIGHT_MIN_M):
    """Shortest edge and lowest triangle height (2 * area / longest edge); flag when below the thresholds."""
    v, t = weld(verts, tris)
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    e = np.stack([np.linalg.norm(b - a, axis=1), np.linalg.norm(c - b, axis=1), np.linalg.norm(a - c, axis=1)])
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    h = 2 * area / np.maximum(e.max(axis=0), 1e-12)
    me, mh = float(e.min()), float(h.min())
    return {"min_edge_m": round(me, 6), "min_height_m": round(mh, 6),
            "flag": bool(me < edge_min_m or mh < height_min_m)}
