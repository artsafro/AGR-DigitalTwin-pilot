"""Probes for the read-only UCX audit geometry (src/twinqa/geometry/ucx_audit.py, #165)."""
import math
import random

import pytest

from twinqa.geometry import ucx_audit as ua

BOX_TRIS = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1),
            (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]


def box(lo, hi, yaw=0.0, centre=None):
    """8 vertices (index bits x,y,z) of a box, optionally rotated about Z around `centre`."""
    pts = [(hi[0] if i & 4 else lo[0], hi[1] if i & 2 else lo[1], hi[2] if i & 1 else lo[2]) for i in range(8)]
    if yaw:
        cx, cy = centre or ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2)
        c, s = math.cos(yaw), math.sin(yaw)
        pts = [(cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c, z) for x, y, z in pts]
    return pts, list(BOX_TRIS)


def test_box_tris_close_the_box():
    v, t = box((0, 0, 0), (1, 2, 3))
    assert ua.is_closed(t) and ua.is_convex(v, t)


def test_classify_kinds():
    assert ua.classify(*box((0, 0, 0), (3, 2, 1)))["kind"] == "box_aabb"
    assert ua.classify(*box((0, 0, 0), (3, 2, 1), yaw=0.3))["kind"] == "box_oriented"
    v, t = box((0, 0, 0), (3, 2, 1))
    skew = [(x + 0.5 * y, y, z) for x, y, z in v]  # parallelogram plan: convex, not a box
    assert ua.classify(skew, t)["kind"] == "convex"
    dent = list(v)
    dent[7] = (1.5, 1.0, 0.5)  # pull a corner inside: non-convex
    assert ua.classify(dent, t)["kind"] == "custom"
    open_box = ua.classify(v, t[:-2])
    assert open_box["kind"] == "custom" and not open_box["closed"]


def test_classify_welds_split_fbx_vertices():
    v, t = box((0, 0, 0), (1, 1, 1))
    split_v = [v[i] for tri in t for i in tri]  # one vertex per corner per triangle, as FBX import may
    split_t = [(3 * k, 3 * k + 1, 3 * k + 2) for k in range(len(t))]
    assert ua.classify(split_v, split_t) == {"kind": "box_aabb", "closed": True, "convex": True, "verts": 8, "tris": 12}


@pytest.mark.parametrize("seed", range(40))
def test_gap_matches_construction(seed):
    """Two rotated boxes pushed apart along X by a known gap: measured gap == gap, class by threshold."""
    rng = random.Random(seed)
    yaw = rng.uniform(-math.pi, math.pi)
    gap = rng.choice([0.0005, 0.0015, 0.002, 0.006, 0.01, 0.03, 0.08])
    a = box((0, 0, 0), (2, 1, 3))
    b = box((2 + gap, rng.uniform(-0.5, 0.5), rng.uniform(-1, 1)), (4, 1.5, 3.5))
    rot = lambda hull: ([(x * math.cos(yaw) - y * math.sin(yaw), x * math.sin(yaw) + y * math.cos(yaw), z)
                         for x, y, z in hull[0]], hull[1])
    cls, measured, pen = ua.pair_relation(rot(a), rot(b))
    assert measured == pytest.approx(gap, abs=1e-7)
    assert pen == 0.0
    assert cls == ("below_band" if gap < 0.002 else "in_band" if gap <= 0.01 else "wide")


@pytest.mark.parametrize("seed", range(40))
def test_overlap_depth_matches_construction(seed):
    rng = random.Random(1000 + seed)
    depth = rng.choice([0.001, 0.045, 0.26])
    a = box((0, 0, 0), (2, 2, 2), yaw=rng.uniform(0, 1.5), centre=(0, 0))
    b = box((0, 0, 2 - depth), (2, 2, 4), yaw=0.0)
    b = (b[0], b[1])
    a2 = box((0, 0, 0), (2, 2, 2))
    cls, gap, pen = ua.pair_relation(a2, b)  # stacked boxes, vertical overlap by `depth`
    assert cls == "overlap" and pen == pytest.approx(depth, abs=1e-7) and gap == 0.0
    assert ua.pair_relation(a, b)[0] == "overlap"


def test_nested_piece_is_overlap_not_gap():
    """GeoAGR ucx_check misses fully nested volumes (validation.md); the audit must not."""
    outer, inner = box((0, 0, 0), (10, 10, 10)), box((4, 4, 4), (5, 5, 5))
    cls, _, pen = ua.pair_relation(outer, inner)
    assert cls == "overlap" and pen > 1


def test_touching_faces_are_touch():
    assert ua.pair_relation(box((0, 0, 0), (1, 1, 1)), box((1, 0, 0), (2, 1, 1)))[0] == "touch"


def test_edge_edge_gap_rotated_45():
    a = box((-1, -1, 0), (1, 1, 1), yaw=math.pi / 4)  # corner reaches x = sqrt(2)
    b = box((math.sqrt(2) + 0.005, -1, 0), (4, 1, 1))
    cls, gap, _ = ua.pair_relation(a, b)
    assert gap == pytest.approx(0.005, abs=1e-7) and cls == "in_band"


@pytest.mark.parametrize("gap,expected", [
    (0.0001, "touch"), (0.0019, "below_band"), (0.002, "in_band"), (0.002 - 5e-6, "in_band"),
    (0.01, "in_band"), (0.0101, "wide"), (0.0999, "wide"), (0.1001, "apart")])
def test_gap_band_boundaries_d098(gap, expected):
    """[D098]: 2 mm - 1 cm inclusive; float32 read-back noise below 0.01 mm stays in band."""
    assert ua.pair_relation(box((0, 0, 0), (1, 1, 1)), box((1 + gap, 0, 0), (2, 1, 1)))[0] == expected


@pytest.mark.parametrize("seed", range(15))
def test_surface_distance_vs_brute_force_sampling(seed):
    """Exact distance <= every sampled pair distance and within sampling resolution of the minimum."""
    rng = random.Random(500 + seed)
    a = box((0, 0, 0), (1, 1, 1), yaw=rng.uniform(0, 3))
    off = (rng.uniform(1.6, 2.5), rng.uniform(-1, 1), rng.uniform(-1, 1))
    b = box(off, (off[0] + 1, off[1] + 1, off[2] + 1), yaw=rng.uniform(0, 3))
    exact = ua.surface_distance(a, b)

    def samples(hull, n=12):
        v, t = hull
        out = []
        for i, j, k in t:
            for p in range(n + 1):
                for q in range(n + 1 - p):
                    r1, r2 = p / n, q / n
                    out.append(tuple(v[i][d] + (v[j][d] - v[i][d]) * r1 + (v[k][d] - v[i][d]) * r2 for d in range(3)))
        return out
    sa, sb = samples(a), samples(b)
    brute = min(math.dist(p, q) for p in sa for q in sb)
    assert exact <= brute + 1e-9
    assert brute - exact < 0.15  # sample spacing ~ 1/12 m on unit faces


def test_sat_agrees_with_inside_sampling():
    rng = random.Random(7)
    v, t = box((0, 0, 0), (2, 3, 4), yaw=0.4)
    for _ in range(300):
        p = (rng.uniform(-2, 4), rng.uniform(-2, 5), rng.uniform(-1, 5))
        dist = min(ua.point_triangle_distance(p, v[a], v[b], v[c]) for a, b, c in t)
        inside = ua.inside_convex(p, v, t)
        if dist > 1e-6:  # off the surface, inside/outside is unambiguous
            q = tuple(p[i] - (sum(x[i] for x in v) / 8) for i in range(3))  # in the box frame
            c, s = math.cos(-0.4), math.sin(-0.4)
            lx, ly = q[0] * c - q[1] * s, q[0] * s + q[1] * c
            assert inside == (abs(lx) < 1 and abs(ly) < 1.5 and abs(q[2]) < 2)


def test_name_report():
    names = ["UCX_SM_A_1_Main_001", "UCX_SM_A_1_Main_002", "UCX_SM_A_1_Main_002", "UCX_SM_A_1_Main_005",
             "UCX_SM_B_Main_003", "UCX_SM_A_1_Main_000", "UCX_SM_A_1_Ground_001", "ucx_sm_A_1_Main_004"]
    r = ua.name_report(names, "SM_A_1_Main")
    assert r["address"] == "A_1"
    assert r["mask_bad_count"] == 3  # wrong address, index 000, lower case prefix
    assert r["Main"] == {"count": 4, "duplicates": [2], "contiguous_from_1": False}
    assert r["Ground"] == {"count": 1, "duplicates": [], "contiguous_from_1": True}
    ok = ua.name_report([f"UCX_SM_A_1_Main_{i:03d}" for i in range(1, 12)], "SM_A_1_Main")
    assert ok["mask_bad_count"] == 0 and ok["Main"]["contiguous_from_1"]
    assert ua.name_report([], "SM_A_1_Main")["Main"]["count"] == 0


def test_face_signature():
    assert ua.face_signature(*box((0, 0, 0), (1, 2, 3))) == (1, 2, 0)
    v, t = box((0, 0, 0), (2, 2, 1))
    frustum = [(x * 0.5 + 0.5, y * 0.5 + 0.5, z) if z == 1 else (x, y, z) for x, y, z in v]
    assert ua.face_signature(frustum, t) == (1, 0, 4)  # truncated pyramid: tilted sides (reg p.36 §13.6)


# --- issue #460: a degenerate (zero-area / sliver) triangle must never pass closed/convex ---

DEGENERATE_TETRA_VERTS = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0.5, 0, 0)]
# The sliver (0,1,3) is collinear (D is the midpoint of AB); its three edges are each used
# twice, so is_closed sees a "closed" shell although the sliver closes the hole only in the
# edge count, not geometrically.
DEGENERATE_TETRA_TRIS = [(0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)]


def test_degenerate_triangles_detects_sliver_and_repeated_index():
    assert ua.degenerate_triangles(DEGENERATE_TETRA_VERTS, DEGENERATE_TETRA_TRIS) == [1]
    assert ua.degenerate_triangles(*box((0, 0, 0), (1, 1, 1))) == []
    v, t = box((0, 0, 0), (1, 1, 1))
    t = t[:-1] + [(0, 0, 1)]  # repeated vertex index
    assert ua.degenerate_triangles(v, t) == [11]


def test_sliver_closed_hole_is_review_not_closed():
    """(a) open box whose hole is "closed" by a zero-area triangle -> review, never closed."""
    assert ua.is_closed(DEGENERATE_TETRA_TRIS) is True  # the false pass the fix removes
    result = ua.classify(DEGENERATE_TETRA_VERTS, DEGENERATE_TETRA_TRIS)
    assert result["status"] == "review"
    assert result["closed"] is None and result["convex"] is None
    assert result["degenerate_triangles"] == {"count": 1, "triangles": [1]}


def test_convex_box_plus_sliver_is_review_not_convex():
    """(b) convex box plus one on-face sliver -> review, never convex."""
    v, t = box((0, 0, 0), (1, 1, 1))
    v = list(v) + [(0.5, 0, 0)]  # collinear with (0,0,0) and (1,0,0): a zero-area sliver
    t = list(t) + [(0, 8, 4)]
    assert ua.is_convex(v, t) is True  # the false pass the fix removes (sliver plane is None)
    result = ua.classify(v, t)
    assert result["status"] == "review"
    assert result["closed"] is None and result["convex"] is None
    assert result["degenerate_triangles"] == {"count": 1, "triangles": [12]}


def test_clean_box_verdict_unchanged():
    """(c) clean closed convex box keeps its current verdict bit-for-bit."""
    assert ua.classify(*box((0, 0, 0), (1, 2, 3))) == {
        "kind": "box_aabb", "closed": True, "convex": True, "verts": 8, "tris": 12}


def test_repeated_index_triangle_is_review():
    """(d) a repeated vertex index is a degenerate triangle -> review, never pass."""
    v, t = box((0, 0, 0), (1, 1, 1))
    t = t[:-1] + [(0, 0, 1)]
    result = ua.classify(v, t)
    assert result["status"] == "review"
    assert result["closed"] is None and result["convex"] is None
    assert result["degenerate_triangles"] == {"count": 1, "triangles": [11]}


def test_many_degenerates_report_count_and_first_five():
    """observed = count + first 5 indices: more than 5 slivers report the full count, first 5."""
    v, t = box((0, 0, 0), (1, 1, 1))
    t = list(t) + [(0, 0, 1)] * 7
    result = ua.classify(v, t)
    assert result["status"] == "review"
    assert result["degenerate_triangles"] == {"count": 7, "triangles": [12, 13, 14, 15, 16]}


def test_area_threshold_is_named_and_inclusive():
    """The degenerate-area constant is named, default 1e-10 m2, and a below-threshold area counts."""
    assert ua.DEGENERATE_AREA_M2 == 1e-10
    below = [(0, 0, 0), (2e-6, 0, 0), (0, 1e-6, 0)]  # area 1e-12 << 1e-10
    assert ua.degenerate_triangles(below, [(0, 1, 2)]) == [0]
    above = [(0, 0, 0), (2e-4, 0, 0), (0, 1e-4, 0)]  # area 1e-8 >> 1e-10
    assert ua.degenerate_triangles(above, [(0, 1, 2)]) == []


@pytest.mark.parametrize("seed", range(30))
def test_generated_degenerate_mesh_never_passes(seed):
    """invariant: a mesh with >= 1 degenerate triangle is review, closed/convex None. N/N."""
    rng = random.Random(7000 + seed)
    v, t = box((0, 0, 0), (rng.uniform(1, 4), rng.uniform(1, 4), rng.uniform(1, 4)))
    v, t = list(v), list(t)
    if seed % 2 == 0:
        # three collinear points on the front (y=0) face: a zero-area sliver
        a = rng.uniform(0.0, 1.0)
        b = a + rng.uniform(0.05, 0.5)
        c = b + rng.uniform(0.05, 0.5)
        v += [(a, 0, 0), (b, 0, 0), (c, 0, 0)]
        t += [(len(v) - 3, len(v) - 2, len(v) - 1)]
    else:
        t += [(0, 0, 1)]  # repeated vertex index
    result = ua.classify(v, t)
    assert result["status"] == "review"
    assert result["closed"] is None and result["convex"] is None
    assert result["degenerate_triangles"]["count"] >= 1


# --- issue #460 round 1 P1: a non-finite area from overflow must fail closed, never pass ---


def _overflow_tris(base):
    """The four triangles over four collinear points, indexed from `base`."""
    return [(base, base + 1, base + 2), (base, base + 1, base + 3),
            (base, base + 2, base + 3), (base + 1, base + 2, base + 3)]


def _collinear_diagonal(s):
    """Four finite collinear points on x=y=z; at large `s` the cross product overflows to NaN."""
    return [(i * s, i * s, i * s) for i in range(4)], _overflow_tris(0)


@pytest.mark.parametrize("s", [1e160, 1e200])
def test_overflow_collinear_is_review_not_closed(s):
    """Regression (round 1 P1): finite collinear verts whose cross product overflows to NaN
    must be review with count 4, never closed=True/convex=True."""
    verts, tris = _collinear_diagonal(s)
    assert ua.is_closed(tris) is True  # the edge count still "closes" the shell
    result = ua.classify(verts, tris)
    assert result["status"] == "review"
    assert result["closed"] is None and result["convex"] is None
    assert result["degenerate_triangles"] == {"count": 4, "triangles": [0, 1, 2, 3]}


def test_collinear_ordinary_scale_is_review():
    """Ordinary-scale control: the same collinear diagonal at s=1 has area exactly 0 and is
    still review with count 4 (the fail-closed branch does not change the ordinary verdict)."""
    verts, tris = _collinear_diagonal(1.0)
    assert ua.degenerate_triangles(verts, tris) == [0, 1, 2, 3]
    assert ua.classify(verts, tris)["status"] == "review"


def test_non_degenerate_ordinary_triangle_not_flagged():
    """Ordinary-scale control: a non-degenerate finite triangle is measured, never flagged."""
    verts = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 3.0, 0.0)]
    assert ua.degenerate_triangles(verts, [(0, 1, 2)]) == []


def test_overflow_and_ordinary_degenerate_combined():
    """Combined: one ordinary repeated-index degenerate + four overflow collinear -> review,
    count = sum, indices reported in triangle order."""
    verts = [(0, 0, 0), (1, 0, 0), (0, 1, 0)] + [(i * 1e160, i * 1e160, i * 1e160) for i in range(4)]
    tris = [(0, 1, 2)] + _overflow_tris(3) + [(0, 0, 1)]
    result = ua.classify(verts, tris)
    assert result["status"] == "review"
    assert result["closed"] is None and result["convex"] is None
    assert result["degenerate_triangles"] == {"count": 5, "triangles": [1, 2, 3, 4, 5]}
