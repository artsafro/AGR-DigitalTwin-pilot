"""Frozen orientation reference from 5e7b855; synthetic regression oracle.

Pattern: n/a | new-case: issue-203 exact legacy orientation oracle.
"""
import numpy as np
from twinqa.geometry.checks import (_proj_bins, _orientation_groups, _ray_basis, ORIENTATION_GRID,
    ORIENTATION_DIRECTIONS, _ORI_BARY, _ORI_EDGE, _ORI_DEPTH)
from twinqa.geometry.mesh import Soup
_ORI_BINS = 64

def _enumerate_bins(lo, hi):
    """(cell_s, cell_t, row) for every integer cell in the inclusive ranges. Vectorised, no Python loop."""
    counts = ((hi[0] - lo[0] + 1) * (hi[1] - lo[1] + 1)).astype(np.int64)
    total = int(counts.sum())
    if total == 0:
        empty = np.zeros(0, dtype=np.int64)
        return empty, empty, empty
    chosen = np.repeat(np.arange(len(counts)), counts)
    base = np.repeat(np.cumsum(counts) - counts, counts)
    local = np.arange(total) - base
    span_t = np.repeat(hi[1] - lo[1] + 1, counts)
    di = local // span_t
    cell_s = np.repeat(lo[0], counts) + di
    cell_t = np.repeat(lo[1], counts) + (local - di * span_t)
    return cell_s, cell_t, chosen


def _first_back_hits(s, t, depth, unit_dot, ray_s, ray_t):
    """First hit of each ray. Returns ``(back, judged)`` — local indices into ``s``.

    ``s``, ``t``, ``depth`` are ``(n, 3)`` projected corners of the triangles kept for this direction;
    ``unit_dot`` is ``(n,)`` (normal · ray). ``ray_s``, ``ray_t`` are ray points in that plane. Candidates
    come from a capped 2D bin grid: each triangle lists the bins its projected bbox covers (plus the bin of
    its own centroid), rays are binned the same way, and the join is exact barycentric. The winning hit on
    a ray is the smallest depth; equal depth keeps the smaller normal dot (the front face). A back hit has
    ``unit_dot > 0``. ``judged`` is every triangle that wins at least one ray."""
    n = len(s)
    empty = np.zeros(0, dtype=np.int64)
    if n == 0 or len(ray_s) == 0:
        return empty, empty
    bins = _ORI_BINS
    s_min, s_max = s.min(1), s.max(1)
    t_min, t_max = t.min(1), t.max(1)
    lo_s = min(float(s_min.min()), float(ray_s.min()))
    hi_s = max(float(s_max.max()), float(ray_s.max()))
    lo_t = min(float(t_min.min()), float(ray_t.min()))
    hi_t = max(float(t_max.max()), float(ray_t.max()))
    pad_s = max(hi_s - lo_s, 1e-9) * 1e-9 + 1e-9
    pad_t = max(hi_t - lo_t, 1e-9) * 1e-9 + 1e-9
    origin_s, origin_t = lo_s - pad_s, lo_t - pad_t
    extent_s, extent_t = (hi_s - lo_s) + 2.0 * pad_s, (hi_t - lo_t) + 2.0 * pad_t
    grow_s = np.maximum(s_max - s_min, 1e-12) * 1e-8 + 1e-12
    grow_t = np.maximum(t_max - t_min, 1e-12) * 1e-8 + 1e-12
    bs_lo = _proj_bins(s_min - grow_s, origin_s, extent_s, bins)
    bs_hi = _proj_bins(s_max + grow_s, origin_s, extent_s, bins)
    bt_lo = _proj_bins(t_min - grow_t, origin_t, extent_t, bins)
    bt_hi = _proj_bins(t_max + grow_t, origin_t, extent_t, bins)
    # the centroid ray is strictly inside its triangle, so that bin is always one of the candidates
    cb_s = _proj_bins(s.mean(1), origin_s, extent_s, bins)
    cb_t = _proj_bins(t.mean(1), origin_t, extent_t, bins)
    bs_lo, bs_hi = np.minimum(bs_lo, cb_s), np.maximum(bs_hi, cb_s)
    bt_lo, bt_hi = np.minimum(bt_lo, cb_t), np.maximum(bt_hi, cb_t)
    bin_s, bin_t, chosen = _enumerate_bins((bs_lo, bt_lo), (bs_hi, bt_hi))
    if len(chosen) == 0:
        return empty, empty
    tri_bin = bin_s * bins + bin_t
    ray_bin = _proj_bins(ray_s, origin_s, extent_s, bins) * bins + _proj_bins(ray_t, origin_t, extent_t, bins)
    order = np.argsort(ray_bin)
    uniq, start, rcount = np.unique(ray_bin[order], return_index=True, return_counts=True)
    pos = np.searchsorted(uniq, tri_bin)
    pos_c = np.minimum(pos, len(uniq) - 1)
    valid = (pos < len(uniq)) & (uniq[pos_c] == tri_bin)
    if not valid.any():
        return empty, empty
    n_hit = rcount[pos[valid]]
    tri_idx = np.repeat(chosen[valid], n_hit)
    pair_base = np.repeat(np.cumsum(n_hit) - n_hit, n_hit)
    ray_idx = order[np.repeat(start[pos[valid]], n_hit) + (np.arange(int(n_hit.sum())) - pair_base)]
    ps = ray_s[ray_idx] - s[tri_idx, 0]
    pt = ray_t[ray_idx] - t[tri_idx, 0]
    e1s, e1t = s[tri_idx, 1] - s[tri_idx, 0], t[tri_idx, 1] - t[tri_idx, 0]
    e2s, e2t = s[tri_idx, 2] - s[tri_idx, 0], t[tri_idx, 2] - t[tri_idx, 0]
    dot00 = e1s * e1s + e1t * e1t
    dot01 = e1s * e2s + e1t * e2t
    dot11 = e2s * e2s + e2t * e2t
    dot02 = e1s * ps + e1t * pt
    dot12 = e2s * ps + e2t * pt
    den = dot00 * dot11 - dot01 * dot01
    inv = np.divide(1.0, den, out=np.zeros_like(den), where=np.abs(den) > 1e-20)
    bu = (dot11 * dot02 - dot01 * dot12) * inv
    bv = (dot00 * dot12 - dot01 * dot02) * inv
    inside = (np.abs(den) > 1e-20) & (bu >= _ORI_BARY) & (bv >= _ORI_BARY) & (bu + bv <= 1.0 - _ORI_BARY)
    if not inside.any():
        return empty, empty
    picked = tri_idx[inside]
    bw, bv_ = bu[inside], bv[inside]
    hit_depth = (1.0 - bw - bv_) * depth[picked, 0] + bw * depth[picked, 1] + bv_ * depth[picked, 2]
    hit_dot = unit_dot[picked]
    hit_ray = ray_idx[inside]
    # smallest depth; a shared edge (equal depth, within float noise) keeps the front face
    ranked = np.lexsort((hit_dot, np.round(hit_depth / _ORI_DEPTH), hit_ray))
    ranked_ray = hit_ray[ranked]
    first = np.empty(len(ranked), dtype=bool)
    first[0] = True
    first[1:] = ranked_ray[1:] != ranked_ray[:-1]
    winners = picked[ranked][first]
    dots = hit_dot[ranked][first]
    return winners[dots > 0], winners


def _orientation_hits(model: Soup):
    """Per mesh: back-hit triangles, judged triangles, rays cast, non-degenerate triangles.

    Each direction casts the global ``ORIENTATION_GRID`` square about the bounding sphere and one ray
    through the projected centroid of every triangle that is not edge-on. Every ray is tested against
    every mesh, so a closer face still hides what is behind it."""
    names, owner = _orientation_groups(model)
    n_mesh = len(names)
    zeros = np.zeros(n_mesh, dtype=int)
    if len(model.triangles) == 0 or len(model.vertices) == 0:
        return zeros, zeros.copy(), 0, zeros.copy()
    corners = model.corners()
    lo, hi = model.vertices.min(axis=0), model.vertices.max(axis=0)
    centre = (lo + hi) / 2
    radius = float(np.linalg.norm(hi - lo) / 2) + 1.0
    scale = ((np.arange(ORIENTATION_GRID) + 0.5) / ORIENTATION_GRID * 2.0 - 1.0) * radius
    grid_s, grid_t = np.meshgrid(scale, scale, indexing="ij")
    grid_s, grid_t = grid_s.ravel(), grid_t.ravel()
    normals = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    length = np.linalg.norm(normals, axis=1)
    # D093 corner ends leave a 5 mm slit: a descending ray can enter there and hit
    # the back of a correctly downward-facing ground cap. At the global minimum Z,
    # a horizontal downward normal is provably outward (all geometry is above it).
    # Exempt only this supporting plane from back-hit failures, not from winding;
    # elevated caps, sloped faces and upward normals at the minimum remain judged.
    ground_caps = ((corners[:, :, 2] == lo[2]).all(axis=1)
                   & (normals[:, 0] == 0) & (normals[:, 1] == 0) & (normals[:, 2] < 0))
    nondeg = np.zeros(n_mesh, dtype=int)
    np.add.at(nondeg, owner[length > 0], 1)
    back = np.zeros(len(corners), dtype=bool)
    seen = np.zeros(len(corners), dtype=bool)
    ray_total = 0
    for direction in ORIENTATION_DIRECTIONS:
        along, across = _ray_basis(direction)
        unit_dot = (normals @ direction) / np.maximum(length, 1e-30)
        keep = np.flatnonzero((length > 0) & (np.abs(unit_dot) >= _ORI_EDGE))
        if len(keep) == 0:
            continue
        s = corners[keep] @ along
        t = corners[keep] @ across
        depth = corners[keep] @ direction
        su, sv = float(centre @ along), float(centre @ across)
        ray_s = np.concatenate((su + grid_s, s.mean(1)))
        ray_t = np.concatenate((sv + grid_t, t.mean(1)))
        ray_total += int(ray_s.size)
        back_local, win_local = _first_back_hits(s, t, depth, unit_dot[keep], ray_s, ray_t)
        if len(win_local):
            seen[keep[win_local]] = True
        if len(back_local):
            hit = keep[back_local]
            back[hit[~ground_caps[hit]]] = True
    backs = np.zeros(n_mesh, dtype=int)
    judged = np.zeros(n_mesh, dtype=int)
    if back.any():
        np.add.at(backs, owner[back], 1)
    if seen.any():
        np.add.at(judged, owner[seen], 1)
    return backs, judged, ray_total, nondeg


