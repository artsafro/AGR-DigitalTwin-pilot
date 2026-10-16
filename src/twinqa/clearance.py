# Ported from AGR adapters/sketchup/check_model_clearance.py (sha256 ba09d4967981)
# on 2026-10-06; changes: importable function + CLI wrapper, tolerance from the profile
# (geometry.near_coplanar_spacing_m.min), AGR window/ac/sill categories dropped.
"""Near-parallel face overlap check (reg p.8, 29: 5 mm-2 cm spacing; docs/domain/validation.md).

Finds pairs of almost parallel faces (|cos| > 0.999999), in either orientation, whose planes
are closer than the tolerance and whose projections overlap by more than 1e-7 m2. It is an
independent area test, not a pass of any third-party checker; hits still need classifying
(deliberate embeds vs defects, docs/domain/validation.md "General QA procedure").
Candidate search (issue #202) is a provable superset of every pair the exact tests can accept.
The exact per-pair tests (parallel cosine, distance, projected area) are unchanged.
"""
import numpy as np
import shapely

PARALLEL_COS_MIN = 0.999999
AREA_MIN_M2 = 1e-7


def _normal(points: np.ndarray) -> np.ndarray:
    # Whole-polygon area vector: robust to collinear leading vertices on welded borders.
    q = points - points.mean(0)
    n = np.cross(q, np.roll(q, -1, axis=0)).sum(0)
    length = np.linalg.norm(n)
    return n / length if length > 1e-12 else np.zeros(3)


# 3x3x3 neighbourhood of a normal cell, including the cell itself.
_OFFSETS = tuple((a, b, c) for a in (-1, 0, 1) for b in (-1, 0, 1) for c in (-1, 0, 1))


def _candidate_pairs(normals, centers, lows, highs, first, tolerance_m):
    """Superset of pairs (i, j), j > i, that can pass the exact overlap tests."""
    finite = (np.isfinite(normals).all(1) & np.isfinite(centers).all(1) & np.isfinite(lows).all(1)
              & np.isfinite(highs).all(1) & np.isfinite(first).all(1))
    valid = np.flatnonzero(finite & (np.linalg.norm(normals, axis=1) >= 0.9))
    empty = np.empty(0, np.intp), np.empty(0, np.intp)
    if valid.size == 0:
        return empty
    keys = np.floor(normals[valid] / 0.005).astype(np.int64)
    uniq, inv = np.unique(keys, axis=0, return_inverse=True)
    cell_faces = np.split(valid[np.argsort(inv, kind="stable")], np.cumsum(np.bincount(inv))[:-1])
    cell_of = {tuple(map(int, uniq[c])): cell_faces[c] for c in range(len(uniq))}
    dominant = np.argmax(np.abs(normals), axis=1)
    fin_lo, fin_hi = lows[finite], highs[finite]
    D = float(np.linalg.norm(fin_hi.max(0) - fin_lo.min(0)))
    R = float(max(np.max(np.abs(fin_lo)), np.max(np.abs(fin_hi))))
    # (c_j - p_i0)·n_i = (o_j - q_i) + (c_j - p_i0)·(n_i - g), and |c_j - p_i0| <= D,
    # so a true pair has |o_j - q_i| <= (tolerance + 1e-5) + D*e, plus 1e-9*(1+D+R) for dot ulps.
    found_i, found_j = [], []
    for c, key_row in enumerate(uniq):
        key = tuple(map(int, key_row))
        opp = tuple(-k - 1 for k in key)
        parts, seen = [], set()
        for base in (key, opp):
            for off in _OFFSETS:
                near = (base[0] + off[0], base[1] + off[1], base[2] + off[2])
                if near in seen:
                    continue
                hit = cell_of.get(near)
                if hit is not None:
                    seen.add(near)
                    parts.append(hit)
        joined = np.unique(np.concatenate(parts))
        members = cell_faces[c]
        for axis in range(3):
            ax = [a for a in range(3) if a != axis]
            I = members[dominant[members] == axis]
            I = I[(highs[I, ax[0]] > lows[I, ax[0]]) & (highs[I, ax[1]] > lows[I, ax[1]])]
            J = joined[(highs[joined, ax[0]] > lows[joined, ax[0]]) & (highs[joined, ax[1]] > lows[joined, ax[1]])]
            if I.size == 0 or J.size == 0:
                continue
            g = normals[I[0]]
            e = float(np.linalg.norm(normals[I] - g, axis=1).max())
            W = (tolerance_m + 1e-5) + D * e + 1e-9 * (1.0 + D + R)
            if not (W >= 0):  # NaN, or a negative window: this group has no pairs. +inf stays.
                continue
            oJ, qI = centers[J] @ g, first[I] @ g
            if I.size * J.size <= 20000:
                ii, jj = np.repeat(I, J.size), np.tile(J, I.size)
                mask = (jj > ii) & (np.abs(np.tile(oJ, I.size) - np.repeat(qI, J.size)) <= W)
                ii, jj = ii[mask], jj[mask]
            else:
                tree = shapely.STRtree(shapely.box(lows[J, ax[0]], lows[J, ax[1]], highs[J, ax[0]], highs[J, ax[1]]))
                hits = np.asarray(tree.query(shapely.box(lows[I, ax[0]], lows[I, ax[1]], highs[I, ax[0]], highs[I, ax[1]])))
                if hits.ndim == 1:  # scalar query geometry: indices into the tree only
                    hits = np.stack((np.zeros(hits.size, dtype=int), hits))
                if hits.size == 0:
                    continue
                ii, jj = I[hits[0]], J[hits[1]]
                mask = (jj > ii) & (np.abs(oJ[hits[1]] - qI[hits[0]]) <= W)
                ii, jj = ii[mask], jj[mask]
            if ii.size == 0:
                continue
            overlap = np.all(np.minimum(highs[jj][:, ax], highs[ii][:, ax])
                             > np.maximum(lows[jj][:, ax], lows[ii][:, ax]), axis=1)
            if np.any(overlap):
                found_i.append(ii[overlap])
                found_j.append(jj[overlap])
    if not found_i:
        return empty
    ii, jj = np.concatenate(found_i), np.concatenate(found_j)
    order = np.lexsort((jj, ii))
    ii, jj = ii[order], jj[order]
    if ii.size > 1:
        dup = np.empty(ii.size, dtype=bool)
        dup[0] = False
        dup[1:] = (ii[1:] == ii[:-1]) & (jj[1:] == jj[:-1])
        ii, jj = ii[~dup], jj[~dup]
    return ii, jj


def _parallel_mask(normals, ii, jj):
    # Row-wise dots differ from gemv in the last ulps. They decide pairs farther than 1e-12 from
    # the cosine threshold; the band falls back to normals[J] @ n, matching `normals @ n` bit-for-bit.
    dot = (normals[ii] * normals[jj]).sum(1)
    band = np.abs(np.abs(dot) - PARALLEL_COS_MIN) <= 1e-12
    keep = np.abs(dot) > PARALLEL_COS_MIN
    if np.any(band):
        pos = np.flatnonzero(band)
        bi, bj = ii[pos], jj[pos]
        cuts = np.flatnonzero(np.diff(bi)) + 1
        decided = np.empty(pos.size, dtype=bool)
        for s, e in zip(np.r_[0, cuts], np.r_[cuts, pos.size]):
            decided[s:e] = np.abs(normals[bj[s:e]] @ normals[int(bi[s])]) > PARALLEL_COS_MIN
        keep[pos] = decided
    return keep, dot


def _face_arrays(pts):
    """Per-face normals, centers, bounds and the first vertex, in face order."""
    count = len(pts)
    groups = {}
    for i, p in enumerate(pts):
        # Malformed rows stay on the original per-face expressions, exceptions included.
        if not (p.ndim == 2 and p.shape[0] >= 1 and p.shape[1] == 3):
            return (
                np.array([_normal(q) for q in pts]),
                np.array([q.mean(0) for q in pts]),
                np.array([q.min(0) for q in pts]),
                np.array([q.max(0) for q in pts]),
                np.array([q[0] for q in pts]),
            )
        groups.setdefault(p.shape, []).append(i)
    normals, centers = np.empty((count, 3)), np.empty((count, 3))
    lows, highs, first = np.empty((count, 3)), np.empty((count, 3)), np.empty((count, 3))
    for idxs in groups.values():
        P = np.stack([pts[i] for i in idxs])
        c = P.mean(1)
        q = P - c[:, None, :]
        n = np.cross(q, np.roll(q, -1, axis=1)).sum(1)
        length = np.linalg.norm(n, axis=1)
        # Bit-identical to per-face _normal / mean / min / max on a 72 000-face probe (V = 3, 4, 5, 7, 9, 12; scales 1e-3, 1, 1e4; offsets up to 100x).
        normal = np.divide(n, length[:, None], out=np.zeros_like(n), where=(length > 1e-12)[:, None])
        idx = np.asarray(idxs, dtype=np.intp)
        normals[idx] = normal
        centers[idx] = c
        lows[idx] = P.min(1)
        highs[idx] = P.max(1)
        first[idx] = P[:, 0]
    return normals, centers, lows, highs, first


def _polygons_by_ring(pts, keys):
    """One polygon per (face, ax0, ax1). shapely.polygons matches Polygon on open and closed rings."""
    by_count = {}
    for key in keys:
        face, ax0, ax1 = key
        ring = pts[face][:, [ax0, ax1]]
        by_count.setdefault(ring.shape[0], []).append((key, ring))
    out = {}
    for group in by_count.values():
        coords = np.stack([ring for _, ring in group])
        geoms = shapely.polygons(coords)
        for (key, _), geom in zip(group, geoms):
            out[key] = geom
    return out


def near_parallel_overlaps(faces: list[dict], tolerance_m: float) -> list[dict]:
    """faces: [{object, index, points: [[x,y,z], ...]}] -> overlapping pairs closer than tolerance."""
    pts = [np.asarray(f["points"], dtype=float) for f in faces]
    if not pts:
        return []
    normals, centers, lows, highs, first = _face_arrays(pts)
    ii, jj = _candidate_pairs(normals, centers, lows, highs, first, tolerance_m)
    if ii.size == 0:
        return []
    keep, dot = _parallel_mask(normals, ii, jj)
    ii, jj, dot = ii[keep], jj[keep], dot[keep]
    if ii.size == 0:
        return []
    thr = tolerance_m - 1e-7
    surv_i, surv_j, surv_dist, surv_same, surv_axes = [], [], [], [], []
    cuts = np.flatnonzero(np.diff(ii)) + 1
    for s, e in zip(np.r_[0, cuts], np.r_[cuts, ii.size]):
        i = int(ii[s])
        n, p0 = normals[i], pts[i][0]
        axes = tuple(k for k in range(3) if k != int(np.argmax(np.abs(n))))
        for t in range(s, e):
            j = int(jj[t])
            dist = abs(float((centers[j] - p0) @ n))
            if dist >= thr:
                continue
            surv_i.append(i)
            surv_j.append(j)
            surv_dist.append(dist)
            surv_same.append(bool(dot[t] > 0))
            surv_axes.append(axes)
    if not surv_i:
        return []
    needed = {}
    for i, j, axes in zip(surv_i, surv_j, surv_axes):
        needed.setdefault((i, axes[0], axes[1]), None)
        needed.setdefault((j, axes[0], axes[1]), None)
    polys = _polygons_by_ring(pts, needed)
    polys_a = np.empty(len(surv_i), dtype=object)
    polys_b = np.empty(len(surv_i), dtype=object)
    for t, (i, j, axes) in enumerate(zip(surv_i, surv_j, surv_axes)):
        polys_a[t] = polys[(i, axes[0], axes[1])]
        polys_b[t] = polys[(j, axes[0], axes[1])]
    areas = np.atleast_1d(shapely.area(shapely.intersection(polys_a, polys_b)))
    pairs = []
    for t, area in enumerate(areas):
        if area < AREA_MIN_M2:  # NaN < x is False, so a NaN area is kept, as in the scalar path.
            continue
        i, j = surv_i[t], surv_j[t]
        face = faces[i]
        pairs.append({"a": [face["object"], face["index"]], "b": [faces[j]["object"], faces[j]["index"]],
                      "distance_m": surv_dist[t], "same_direction": surv_same[t],
                      "projected_area_m2": float(area)})
    return pairs


def summary(pairs: list[dict], tolerance_m: float, face_count: int) -> dict:
    objects = {}
    for p in pairs:
        key = " / ".join(sorted({p["a"][0], p["b"][0]}))
        objects[key] = objects.get(key, 0) + 1
    return {"tool": "near-parallel area-overlap test", "tolerance_m": tolerance_m,
            "parallel_cosine_min": PARALLEL_COS_MIN, "area_threshold_m2": AREA_MIN_M2, "face_count": face_count,
            "pair_count": len(pairs), "by_objects": objects,
            "same_direction": sum(p["same_direction"] for p in pairs),
            "opposite_direction": sum(not p["same_direction"] for p in pairs)}
