"""Analytic controls for methods_metrics.ground_terrain: sloped-surface p95 and exact coverage accounting.

new-case: characterization controls (baseline GREEN, not a historical RED) for the unchanged public API.
Real geometry only: no monkeypatch of sampling, top_z, distance or reducer functions.

Input -> expected output table (sample_m=1, anchored on the reference bounding box, zero placement offsets):

  A  ref [0,20]x[0,1] z=0; out same rectangle z=(x-.5)/32
       cell centres x=i+.5 -> dz = i/32, i=0..19 (sorted already)
       max = 19/32 = .59375 -> .5938 ; mean = 9.5/32 = .296875 -> .2969
       p95 = sorted linear interpolation at (20-1)*.95 = 18.05 -> (18 + .05)/32 = .5640625 -> .5641
       reference 20, both 20, missing 0, extra 0, dz_reason None
  A' negated plane -> max .5938, p95 .5641, mean -.2969
  B  ref = [0,8]x[0,2] U [10,20]x[0,2] (36 cells), z=0
       out [2,20]x[0,2] (36 cells): both 32, missing 4 (x cells 0,1), extra 4 (x cells 8,9), dz all 0
  B' out [2,19]x[0,2] (30 cells): both 30, missing 6, extra 4, dz all 0
"""
from __future__ import annotations

import copy

import numpy as np
import pytest

from tests.methods.test_ground_terrain import ground_rb, mm

ZERO = np.zeros(3)


def rect(x0, x1, y0, y1, zf=lambda x: 0.0, *, flip=False, diag=0, local=(0.0, 0.0, 0.0)):
    """Rectangle with integer-step vertices split into unit quads, each quad in two triangles."""
    xs, ys = list(range(x0, x1 + 1)), list(range(y0, y1 + 1))
    verts, idx = [], {}
    for y in ys:
        for x in xs:
            idx[(x, y)] = len(verts)
            verts.append([x - local[0], y - local[1], zf(x) - local[2]])
    tris = []
    for y in ys[:-1]:
        for x in xs[:-1]:
            a, b, c, d = idx[(x, y)], idx[(x + 1, y)], idx[(x + 1, y + 1)], idx[(x, y + 1)]
            tris += [[a, b, c], [a, c, d]] if diag == 0 else [[a, b, d], [b, c, d]]
    if flip:
        tris = [[t[0], t[2], t[1]] for t in reversed(tris)]
    return verts, tris


def union(parts, **kw):
    """Several disjoint rectangles in one mesh."""
    verts, tris = [], []
    for p in parts:
        v, t = rect(*p, **kw)
        tris += [[i + len(verts) for i in tri] for tri in t]
        verts += v
    return verts, tris


def run(out, ref, off=ZERO, ref_off=ZERO):
    return mm.ground_terrain(out[0], out[1], ref[0], ref[1], off, ref_off, sample_m=1.0)


def slope(x):
    return (x - 0.5) / 32.0


def expected_dz():
    d = sorted(i / 32.0 for i in range(20))
    pos = (len(d) - 1) * 0.95
    lo = int(pos)
    p95 = d[lo] + (pos - lo) * (d[lo + 1] - d[lo])
    return max(d), p95, sum(d) / len(d)


def test_expected_values_are_the_literal_table():
    mx, p95, mean = expected_dz()
    assert (round(mx, 4), round(p95, 4), round(mean, 4)) == (0.5938, 0.5641, 0.2969)
    assert p95 != mean and p95 != mx and abs(p95 - 0.5640625) < 1e-12


@pytest.mark.parametrize("sign", [1.0, -1.0])
def test_sloped_plane_p95_is_distinct_from_max_and_mean(sign):
    ref = ground_rb(*rect(0, 20, 0, 1))
    out = ground_rb(*rect(0, 20, 0, 1, lambda x: sign * slope(x)))
    g = run(out, ref)
    assert g["dz_max_m"] == 0.5938 and g["dz_p95_m"] == 0.5641
    assert g["dz_mean_m"] == sign * 0.2969
    assert g["dz_p95_m"] not in (g["dz_max_m"], abs(g["dz_mean_m"]))
    assert (g["samples_reference"], g["samples_both"], g["samples_missing"], g["samples_extra"]) == (20, 20, 0, 0)
    assert g["dz_reason"] is None


REF_B = [(0, 8, 0, 2), (10, 20, 0, 2)]


def cells(parts):
    return {(x, y) for x0, x1, y0, y1 in parts for x in range(x0, x1) for y in range(y0, y1)}


@pytest.mark.parametrize("out_parts, both, missing, extra", [
    ([(2, 20, 0, 2)], 32, 4, 4),
    ([(2, 19, 0, 2)], 30, 6, 4),
])
def test_coverage_cell_sets_and_conservation(out_parts, both, missing, extra):
    r, o = cells(REF_B), cells(out_parts)
    assert (len(r), len(r & o), len(r - o), len(o - r)) == (36, both, missing, extra)
    g = run(ground_rb(*union(out_parts)), ground_rb(*union(REF_B)))
    assert (g["samples_reference"], g["samples_both"], g["samples_missing"], g["samples_extra"]) == (
        36, both, missing, extra)
    assert g["samples_both"] + g["samples_missing"] == g["samples_reference"]
    assert g["samples_both"] + g["samples_extra"] == len(o)
    assert g["dz_max_m"] == g["dz_p95_m"] == g["dz_mean_m"] == 0 and g["dz_reason"] is None


def _key(g):
    return {k: g[k] for k in ("dz_max_m", "dz_p95_m", "dz_mean_m", "samples_reference", "samples_both",
                              "samples_missing", "samples_extra", "dz_reason")}


def test_face_order_winding_and_diagonal_do_not_change_the_metrics():
    ref = ground_rb(*rect(0, 20, 0, 1))
    base = _key(run(ground_rb(*rect(0, 20, 0, 1, slope)), ref))
    for kw in ({"flip": True}, {"diag": 1}, {"flip": True, "diag": 1}):
        assert _key(run(ground_rb(*rect(0, 20, 0, 1, slope, **kw)), ref)) == base
    refb = ground_rb(*union(REF_B))
    base = _key(run(ground_rb(*union([(2, 19, 0, 2)])), refb))
    assert _key(run(ground_rb(*union([(2, 19, 0, 2)], flip=True, diag=1)), refb)) == base


def test_dyadic_local_translation_with_matching_offsets_gives_same_world_result():
    d = (4.0, 2.0, 0.5)
    ref = ground_rb(*rect(0, 20, 0, 1))
    base = _key(run(ground_rb(*rect(0, 20, 0, 1, slope)), ref))
    moved_out = ground_rb(*rect(0, 20, 0, 1, slope, local=d))
    moved_ref = ground_rb(*rect(0, 20, 0, 1, local=d))
    assert _key(run(moved_out, moved_ref, np.array(d), np.array(d))) == base
    assert _key(run(moved_out, moved_ref, np.array(d), ZERO)) != base  # one offset forgotten is caught


def test_inputs_are_not_mutated():
    out, ref = ground_rb(*rect(2, 19, 0, 2)), ground_rb(*union(REF_B))
    off, roff = np.array([1.0, 2.0, 0.0]), np.array([1.0, 2.0, 0.0])
    snap = copy.deepcopy((out, ref)), off.copy(), roff.copy()
    mm.ground_terrain(out[0], out[1], ref[0], ref[1], off, roff, sample_m=1.0)
    assert (out, ref) == snap[0] and np.array_equal(off, snap[1]) and np.array_equal(roff, snap[2])
