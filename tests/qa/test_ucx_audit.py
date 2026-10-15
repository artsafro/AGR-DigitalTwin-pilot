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
    gap = rng.choice([0.0005, 0.002, 0.006, 0.03, 0.08])
    a = box((0, 0, 0), (2, 1, 3))
    b = box((2 + gap, rng.uniform(-0.5, 0.5), rng.uniform(-1, 1)), (4, 1.5, 3.5))
    rot = lambda hull: ([(x * math.cos(yaw) - y * math.sin(yaw), x * math.sin(yaw) + y * math.cos(yaw), z)
                         for x, y, z in hull[0]], hull[1])
    cls, measured, pen = ua.pair_relation(rot(a), rot(b))
    assert measured == pytest.approx(gap, abs=1e-7)
    assert pen == 0.0
    assert cls == ("recommended" if gap <= 0.01 else "wide")


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
    assert gap == pytest.approx(0.005, abs=1e-7) and cls == "recommended"


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
