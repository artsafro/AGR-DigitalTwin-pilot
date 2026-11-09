"""new-case: UCX collision findings (SINTEZ too-close < 0.2 mm, D098 band, intersect, nested) req 2.13.4.

UCX collision findings: SINTEZ too-close and the D098 band, intersect, nested (req 2.13.4, D162).

TODO: cross-check these findings in the SINTEZ parity harness (PR #429 next task 1, sibling of
#433) when that harness exists. It is not in this tree.
"""
import math
import random

import pytest

from twinqa.geometry import ucx_audit as ua

BOX_TRIS = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1),
            (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]
REQ = "2.13.4"


def box(lo, hi, yaw=0.0, centre=None):
    """8 vertices (index bits x,y,z) of a box, optionally rotated about Z around `centre`."""
    pts = [(hi[0] if i & 4 else lo[0], hi[1] if i & 2 else lo[1], hi[2] if i & 1 else lo[2]) for i in range(8)]
    if yaw:
        cx, cy = centre or ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2)
        c, s = math.cos(yaw), math.sin(yaw)
        pts = [(cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c, z) for x, y, z in pts]
    return pts, list(BOX_TRIS)


def hull(name, geom):
    verts, tris = geom
    return {"name": name, "verts": verts, "tris": tris}


def gap_pair(gap):
    return box((0, 0, 0), (1, 1, 1)), box((1 + gap, 0, 0), (2 + gap, 1, 1))


def expected_gap_types(gap):
    """Independent reading of the D162 table. Uses the module thresholds, not pair_findings."""
    if gap < ua.TOUCH_M:
        return {"too_close", "gap_out_of_band"}
    if gap < ua.GAP_BAND_M[0] - ua.BAND_TOL_M:
        return {"gap_out_of_band"}
    if gap <= ua.GAP_BAND_M[1] + ua.BAND_TOL_M:
        return set()
    if gap <= ua.NEIGHBOUR_M:
        return {"gap_out_of_band"}
    return set()


def assert_reqs(findings):
    for finding in findings:
        assert finding["req"] == REQ


def test_acceptance_cases_report_req_2134():
    """Touching, 0.1 mm, 1 mm, 5 mm, 2 cm, intersecting, nested — exact type sets."""
    touching = ua.pair_findings(*gap_pair(0.0), name_a="L", name_b="R")
    close = ua.pair_findings(*gap_pair(0.0001), name_a="L", name_b="R")
    one_mm = ua.pair_findings(*gap_pair(0.001), name_a="L", name_b="R")
    five_mm = ua.pair_findings(*gap_pair(0.005), name_a="L", name_b="R")
    two_cm = ua.pair_findings(*gap_pair(0.02), name_a="L", name_b="R")
    overlapping = ua.pair_findings(box((0, 0, 0), (1, 1, 1)), box((0.5, 0, 0), (1.5, 1, 1)),
                                   name_a="L", name_b="R")
    nested = ua.pair_findings(box((0, 0, 0), (10, 10, 10)), box((4, 4, 4), (5, 5, 5)),
                              name_a="outer", name_b="inner")
    assert [f["type"] for f in touching] == ["too_close", "gap_out_of_band"]
    assert [f["type"] for f in close] == ["too_close", "gap_out_of_band"]
    assert [f["type"] for f in one_mm] == ["gap_out_of_band"]
    assert five_mm == []
    assert [f["type"] for f in two_cm] == ["gap_out_of_band"]
    assert [f["type"] for f in overlapping] == ["intersect"]
    assert [f["type"] for f in nested] == ["nested"]
    for group in (touching, close, one_mm, two_cm, overlapping, nested):
        assert_reqs(group)
        assert all(f["a"] and f["b"] for f in group)
    assert close[0]["gap_m"] == pytest.approx(0.0001, abs=1e-7)
    assert close[0]["penetration_m"] == 0.0 and close[1]["penetration_m"] == 0.0
    assert overlapping[0]["gap_m"] == 0.0 and overlapping[0]["penetration_m"] > ua.TOUCH_M
    assert nested[0]["gap_m"] == 0.0 and nested[0]["penetration_m"] > 1
    assert nested[0]["a"] == "outer" and nested[0]["b"] == "inner"


def test_regression_nested_and_too_close_are_separate_findings():
    """Fails on measurement-only main: no pair_findings, and overlap is not split into nested."""
    outer, inner = box((0, 0, 0), (10, 10, 10)), box((4, 4, 4), (5, 5, 5))
    kinds = [f["type"] for f in ua.pair_findings(outer, inner)]
    assert kinds == ["nested"]
    close = ua.pair_findings(*gap_pair(0.0001))
    assert [f["type"] for f in close] == ["too_close", "gap_out_of_band"]
    assert all(f["req"] == REQ for f in close)


def test_thresholds_match_d098_band_test():
    """Same gaps as test_gap_band_boundaries_d098, plus the exact 0.2 mm / 2 mm / 1 cm edges."""
    expect = {
        0.0: ["too_close", "gap_out_of_band"],
        0.0001: ["too_close", "gap_out_of_band"],
        # 1.0 + 0.0002 measures 1 ulp under TOUCH_M, so pair_relation calls it touch.
        0.0002: ["too_close", "gap_out_of_band"],
        # First constructed gap that measures >= 0.2 mm: below the 2 mm band, not too-close.
        0.000201: ["gap_out_of_band"],
        0.0019: ["gap_out_of_band"],
        0.002: [],
        0.002 - 5e-6: [],
        0.01: [],
        0.0101: ["gap_out_of_band"],
        0.0999: ["gap_out_of_band"],
        # 1.0 + 0.10 measures 1 ulp over NEIGHBOUR_M, so pair_relation calls it apart.
        0.10: [],
        0.1001: [],
    }
    for gap, kinds in expect.items():
        got = [f["type"] for f in ua.pair_findings(*gap_pair(gap))]
        assert got == kinds, gap
        if kinds:
            assert ua.pair_findings(*gap_pair(gap))[0]["gap_m"] == pytest.approx(gap, abs=1e-7)


def test_gap_sweep_matches_band_table():
    """Grid across 0.2 mm, 2 mm and 1 cm. N/N against the D162 table."""
    gaps = (
        0.0, 1e-5, 0.0001, 0.00015, 0.000199, 0.0002, 0.000201, 0.00025, 0.0005, 0.001, 0.0015,
        0.0019, 0.002 - 5e-6, 0.002, 0.003, 0.005, 0.009, 0.01, 0.01001, 0.0101, 0.02, 0.05,
        0.0999, 0.10, 0.1001, 0.2, 0.5,
    )
    matched = 0
    for gap in gaps:
        pair = gap_pair(gap)
        _, measured, _ = ua.pair_relation(*pair)
        findings = ua.pair_findings(*pair)
        # Table is applied to the measured gap: 1+0.0002 and 1+0.10 each miss their literal by 1 ulp.
        assert {f["type"] for f in findings} == expected_gap_types(measured)
        assert_reqs(findings)
        if findings and "intersect" not in {f["type"] for f in findings}:
            assert findings[0]["gap_m"] == pytest.approx(measured, abs=1e-12)
        matched += 1
    assert matched == len(gaps) == 27


def _deep_inside(verts, outer, margin=0.001):
    ov, ot = outer
    return all(ua.inside_convex(p, ov, ot, tol=-margin) for p in verts)


def _any_outside(verts, outer):
    ov, ot = outer
    return any(not ua.inside_convex(p, ov, ot) for p in verts)


def test_nested_iff_vertices_inside_yaw_depth_sweep():
    """nested iff every vertex of the smaller box is inside the larger, against inside_convex. N/N."""
    outer = box((0, 0, 0), (4, 4, 4))
    samples = []
    rng = random.Random(433)
    for _ in range(24):
        yaw = rng.uniform(0, math.pi)
        inner = box((1.5, 1.5, 1.5), (2.5, 2.5, 2.5), yaw=yaw, centre=(2.0, 2.0))
        samples.append(inner)
        # Shift past the +X face, and lift clear of the top face. Both leave at least one vertex outside.
        samples.append(([(x + 2.0, y, z) for x, y, z in inner[0]], inner[1]))
        samples.append(([(x, y, z + 3.0) for x, y, z in inner[0]], inner[1]))
    assert len(samples) == 72
    matched = nested_n = outside_n = 0
    for inner in samples:
        inside = all(ua.inside_convex(p, outer[0], outer[1]) for p in inner[0])
        types = {f["type"] for f in ua.pair_findings(outer, inner)}
        assert ("nested" in types) == inside
        if inside:
            assert types == {"nested"}
            assert _deep_inside(inner[0], outer)
            nested_n += 1
        else:
            assert "nested" not in types
            assert _any_outside(inner[0], outer)
            outside_n += 1
        matched += 1
    assert matched == 72 and nested_n == 24 and outside_n == 48


def test_partial_overlap_is_intersect_not_nested():
    left = box((0, 0, 0), (2, 2, 2))
    right = box((1.5, 0.2, 0.2), (3, 1.5, 1.5))
    findings = ua.pair_findings(left, right)
    assert [f["type"] for f in findings] == ["intersect"]
    assert not all(ua.inside_convex(p, left[0], left[1]) for p in right[0])
    assert not all(ua.inside_convex(p, right[0], right[1]) for p in left[0])


def test_collision_findings_names_every_pair():
    outer = hull("outer", box((0, 0, 0), (10, 10, 10)))
    inner = hull("inner", box((4, 4, 4), (5, 5, 5)))
    neighbour = hull("neighbour", box((10.02, 0, 0), (11, 1, 1)))
    findings = ua.collision_findings([outer, inner, neighbour])
    kinds = {(f["a"], f["b"], f["type"]) for f in findings}
    assert ("outer", "inner", "nested") in kinds
    assert ("outer", "neighbour", "gap_out_of_band") in kinds
    assert all(f["req"] == REQ for f in findings)


def test_empty_hull_list_is_empty_not_a_pass():
    assert ua.collision_findings([]) == []


def test_open_hull_is_not_run_and_later_pairs_still_run():
    """An open piece is dropped; it must not hide a too-close pair later in the list."""
    open_geom = box((0, 0, 0), (1, 1, 1))
    open_hull = {"name": "open", "verts": open_geom[0], "tris": open_geom[1][:-2]}
    left = hull("L", box((0, 0, 0), (1, 1, 1)))
    right = hull("R", box((1.0001, 0, 0), (2, 1, 1)))
    findings = ua.collision_findings([left, right, open_hull])
    dropped = [f for f in findings if f["type"] == "not_run"]
    assert len(dropped) == 1
    assert dropped[0]["hull"] == "open" and dropped[0]["index"] == 2
    assert dropped[0]["reason"] == "open" and dropped[0]["req"] == REQ
    kinds = [f["type"] for f in findings if f["type"] != "not_run"]
    assert kinds == ["too_close", "gap_out_of_band"]
    assert {f["a"] for f in findings if f["type"] == "too_close"} == {"L"}


def test_non_convex_hull_is_not_run():
    verts, tris = box((0, 0, 0), (3, 2, 1))
    dent = list(verts)
    dent[7] = (1.5, 1.0, 0.5)
    findings = ua.collision_findings([hull("dent", (dent, tris)), hull("ok", box((5, 0, 0), (6, 1, 1)))])
    assert [f["type"] for f in findings] == ["not_run"]
    assert findings[0]["reason"] == "non-convex" and findings[0]["hull"] == "dent"


def test_non_finite_coordinates_are_dropped():
    verts, tris = box((0, 0, 0), (1, 1, 1))
    bad = [list(v) for v in verts]
    bad[0][0] = math.nan
    inf_v = [list(v) for v in verts]
    inf_v[1][1] = math.inf
    findings = ua.collision_findings([
        hull("nan", (bad, tris)),
        hull("inf", (inf_v, tris)),
        hull("ok", box((3, 0, 0), (4, 1, 1))),
    ])
    assert findings and all(f["type"] == "not_run" for f in findings)
    assert [f["hull"] for f in findings] == ["nan", "inf"]
    assert all(f["reason"] == "non-finite coordinates" for f in findings)
    assert "" not in {f["reason"] for f in findings}


def test_duplicate_hull_terminates_deterministically():
    geom = box((0, 0, 0), (1, 2, 3))
    same = hull("A", geom)
    copy = hull("A", (list(geom[0]), list(geom[1])))
    first = ua.collision_findings([same, copy])
    second = ua.collision_findings([same, same])
    assert first == second
    assert [f["type"] for f in first] == ["nested"]
    assert first[0]["req"] == REQ and first[0]["a"] == "A" and first[0]["b"] == "A"


def test_overlap_01mm_is_intersect_with_penetration():
    """0.1 mm penetration is intersect (req 2.13.4), not a zero-penetration proximity finding."""
    a = box((0, 0, 0), (1, 1, 1))
    b = box((0.9999, 0, 0), (1.9999, 1, 1))
    findings = ua.pair_findings(a, b, name_a="A", name_b="B")
    assert [f["type"] for f in findings] == ["intersect"]
    assert findings[0]["penetration_m"] == pytest.approx(0.0001, abs=1e-6)
    assert findings[0]["gap_m"] == 0.0
    assert findings[0]["req"] == REQ


def test_thin_contained_box_is_nested():
    """A valid box strictly inside a 0.1 mm shell is nested, not too-close."""
    outer = box((0, 0, 0), (0.0001, 1, 1))
    inner = box((0.00002, 0.2, 0.2), (0.00008, 0.8, 0.8))
    findings = ua.pair_findings(outer, inner, name_a="outer", name_b="inner")
    assert [f["type"] for f in findings] == ["nested"]
    assert findings[0]["a"] == "outer" and findings[0]["b"] == "inner"
    assert findings[0]["penetration_m"] > 0
    assert findings[0]["req"] == REQ


def test_flat_hull_is_degenerate_not_clean():
    """Zero thickness is not_run/degenerate, never a clean pair list."""
    findings = ua.collision_findings([
        hull("flat", box((0, 0, 0), (1, 1, 0))),
        hull("ok", box((5, 0, 0), (6, 1, 1))),
    ])
    assert len(findings) == 1
    assert findings[0]["type"] == "not_run"
    assert findings[0]["hull"] == "flat"
    assert findings[0]["reason"] == "degenerate"
    assert findings[0]["req"] == REQ
    assert "a" not in findings[0] and "b" not in findings[0]


def test_collapsed_hull_is_degenerate():
    """All vertices coincident is not_run/degenerate, never a clean pair list."""
    findings = ua.collision_findings([
        hull("point", box((0, 0, 0), (0, 0, 0))),
        hull("ok", box((5, 0, 0), (6, 1, 1))),
    ])
    assert len(findings) == 1
    assert findings[0]["type"] == "not_run"
    assert findings[0]["hull"] == "point"
    assert findings[0]["reason"] == "degenerate"
    assert findings[0]["req"] == REQ


def test_flat_hull_does_not_hide_later_pair():
    """A degenerate hull is dropped; a later too-close pair is still reported."""
    findings = ua.collision_findings([
        hull("flat", box((0, 0, 0), (1, 1, 0))),
        hull("L", box((0, 0, 0), (1, 1, 1))),
        hull("R", box((1.0001, 0, 0), (2, 1, 1))),
    ])
    drops = [f for f in findings if f["type"] == "not_run"]
    pairs = [f for f in findings if f["type"] != "not_run"]
    assert len(drops) == 1
    assert drops[0]["hull"] == "flat" and drops[0]["reason"] == "degenerate"
    assert [f["type"] for f in pairs] == ["too_close", "gap_out_of_band"]
    assert {f["a"] for f in pairs} == {"L"} and {f["b"] for f in pairs} == {"R"}
    assert_reqs(findings)


def test_penetration_above_overlap_eps_is_intersect_sweep():
    """Penetration deeper than 1e-5 m is intersect; at or below it stays proximity. N/N.

    The constructed depth is the independent expected penetration. The old 0.2 mm cutoff
    must not swallow depths in (1e-5, 0.2 mm].
    """
    depths = (0.0, 1e-5, 1.1e-5, 2e-5, 5e-5, 1e-4, 1.5e-4, 2e-4, 2.1e-4, 5e-4, 1e-3)
    matched = intersect_n = proximity_n = 0
    for depth in depths:
        a = box((0, 0, 0), (1, 1, 1))
        b = box((1 - depth, 0, 0), (2 - depth, 1, 1))
        findings = ua.pair_findings(a, b, name_a="A", name_b="B")
        types = [f["type"] for f in findings]
        assert_reqs(findings)
        if depth > 1e-5:
            assert types == ["intersect"]
            assert findings[0]["penetration_m"] == pytest.approx(depth, abs=1e-6)
            assert findings[0]["gap_m"] == 0.0
            intersect_n += 1
        else:
            assert types == ["too_close", "gap_out_of_band"]
            assert all(f["penetration_m"] == 0.0 for f in findings)
            proximity_n += 1
        matched += 1
    assert matched == len(depths) == 11
    assert intersect_n == 9 and proximity_n == 2


def test_volume_at_or_below_1e9_is_degenerate_sweep():
    """Enclosed volume <= 1e-9 m^3 is not_run/degenerate and does not hide a later pair. N/N.

    Expected volume is the box product dx*dy*dz, not the tetrahedron helper.
    """
    thicknesses = (0.0, 1e-12, 1e-10, 1e-9, 1e-6, 1e-4)
    matched = degenerate_n = solid_n = 0
    for thickness in thicknesses:
        candidate = hull("cand", box((0, 0, 0), (1, 1, thickness)))
        left = hull("L", box((10, 0, 0), (11, 1, 1)))
        right = hull("R", box((11.0001, 0, 0), (12, 1, 1)))
        findings = ua.collision_findings([candidate, left, right])
        volume = abs(1.0 * 1.0 * thickness)
        drops = [f for f in findings if f["type"] == "not_run"]
        pairs = [f for f in findings if f["type"] != "not_run"]
        assert_reqs(findings)
        assert [f["type"] for f in pairs] == ["too_close", "gap_out_of_band"]
        assert {f["a"] for f in pairs} == {"L"} and {f["b"] for f in pairs} == {"R"}
        if volume <= 1e-9:
            assert len(drops) == 1
            assert drops[0]["hull"] == "cand" and drops[0]["reason"] == "degenerate"
            assert "gap_m" not in drops[0]
            degenerate_n += 1
        else:
            assert drops == []
            solid_n += 1
        matched += 1
    assert matched == len(thicknesses) == 6
    assert degenerate_n == 4 and solid_n == 2


# Reviewer round-2 P1: planar tetra whose coordinates sit near 1000 m. The signed
# tetrahedron sum against the global origin cancels; the local-frame volume is ~4e-15 m^3.
PLANAR_FAR_VERTS = [
    (1000.1991318887165, 1000.49685239103, 1000.407536240336),
    (1000.0404634437695, 1000.6185336735048, 1000.4451126045842),
    (1000.8893204056178, 1000.9434298198049, 1000.9271969955487),
    (1000.794621338583, 1000.118105348362, 1000.3210601454282),
]
PLANAR_FAR_TRIS = [(0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3)]
SHIFT_1000 = (1000.0, 1000.0, 1000.0)


def _shift(verts, delta):
    return [(x + delta[0], y + delta[1], z + delta[2]) for x, y, z in verts]


def _assert_flat_degenerate(findings):
    assert len(findings) == 1
    finding = findings[0]
    assert finding == {
        "type": "not_run",
        "req": REQ,
        "reason": "degenerate",
        "hull": "flat",
    }


def test_planar_tetra_near_1000m_is_degenerate_not_clean():
    """A planar tetra near 1000 m is not_run/degenerate, never a clean pair list."""
    far_box = box((1005, 1000, 1000), (1006, 1001, 1001))
    findings = ua.pair_findings(
        (PLANAR_FAR_VERTS, PLANAR_FAR_TRIS), far_box, name_a="flat", name_b="far")
    _assert_flat_degenerate(findings)


def test_planar_tetra_origin_copy_is_the_same_degenerate():
    """Subtracting (1000,1000,1000) from the tetra and the far box keeps not_run/degenerate."""
    verts = _shift(PLANAR_FAR_VERTS, (-SHIFT_1000[0], -SHIFT_1000[1], -SHIFT_1000[2]))
    findings = ua.pair_findings(
        (verts, PLANAR_FAR_TRIS), box((5, 0, 0), (6, 1, 1)), name_a="flat", name_b="far")
    _assert_flat_degenerate(findings)


def test_solid_unit_box_near_1000m_is_not_degenerate():
    """A solid unit box translated to ~1000 m is still measured."""
    solid = box((1000, 1000, 1000), (1001, 1001, 1001))
    far_box = box((1005, 1000, 1000), (1006, 1001, 1001))
    findings = ua.pair_findings(solid, far_box, name_a="solid", name_b="far")
    assert findings == []
    assert ua.DEGENERATE_VOLUME_M3 == 1e-9


def test_overlapping_boxes_near_1000m_are_intersect():
    """Overlap of two solid boxes near 1000 m stays intersect."""
    a = box((1000, 1000, 1000), (1001, 1001, 1001))
    b = box((1000.5, 1000, 1000), (1001.5, 1001, 1001))
    findings = ua.pair_findings(a, b, name_a="A", name_b="B")
    assert [f["type"] for f in findings] == ["intersect"]
    assert findings[0]["req"] == REQ
    assert findings[0]["a"] == "A" and findings[0]["b"] == "B"
    assert findings[0]["penetration_m"] > ua.OVERLAP_EPS_M


def test_planar_tetra_near_1000m_does_not_hide_later_pair():
    """The far planar tetra is dropped; a later too-close pair is still reported."""
    findings = ua.collision_findings([
        hull("flat", (PLANAR_FAR_VERTS, PLANAR_FAR_TRIS)),
        hull("L", box((0, 0, 0), (1, 1, 1))),
        hull("R", box((1.0001, 0, 0), (2, 1, 1))),
    ])
    drops = [f for f in findings if f["type"] == "not_run"]
    pairs = [f for f in findings if f["type"] != "not_run"]
    assert len(drops) == 1
    assert drops[0]["hull"] == "flat" and drops[0]["reason"] == "degenerate"
    assert drops[0]["req"] == REQ
    assert "a" not in drops[0] and "b" not in drops[0]
    assert [f["type"] for f in pairs] == ["too_close", "gap_out_of_band"]
    assert {f["a"] for f in pairs} == {"L"} and {f["b"] for f in pairs} == {"R"}
    assert_reqs(findings)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_volume_is_degenerate_not_clean(monkeypatch, bad):
    """A non-finite enclosed volume is a named not_run, never a clean pair list."""
    monkeypatch.setattr(ua, "_enclosed_volume", lambda verts, tris: bad)
    findings = ua.pair_findings(
        box((0, 0, 0), (1, 1, 1)), box((5, 0, 0), (6, 1, 1)), name_a="bad", name_b="ok")
    assert len(findings) == 2
    assert {f["type"] for f in findings} == {"not_run"}
    assert {f["reason"] for f in findings} == {"degenerate"}
    assert {f["hull"] for f in findings} == {"bad", "ok"}
    assert all(f["req"] == REQ and "a" not in f and "b" not in f for f in findings)


def test_translated_planar_tetra_stays_degenerate_and_solid_box_does_not():
    """invariant: local-frame volume is translation-invariant. probe: random shifts. N/N."""
    rng = random.Random(433)
    n = 64
    planar_local = _shift(PLANAR_FAR_VERTS, (-SHIFT_1000[0], -SHIFT_1000[1], -SHIFT_1000[2]))
    planar_n = solid_n = 0
    for _ in range(n):
        t = (rng.uniform(-5000.0, 5000.0), rng.uniform(-5000.0, 5000.0), rng.uniform(-5000.0, 5000.0))
        partner = box((t[0] + 5.0, t[1], t[2]), (t[0] + 6.0, t[1] + 1.0, t[2] + 1.0))
        flat = ua.pair_findings(
            (_shift(planar_local, t), PLANAR_FAR_TRIS), partner, name_a="flat", name_b="far")
        _assert_flat_degenerate(flat)
        planar_n += 1
        solid = ua.pair_findings(
            box(t, (t[0] + 1.0, t[1] + 1.0, t[2] + 1.0)), partner, name_a="solid", name_b="far")
        assert solid == []
        solid_n += 1
    assert planar_n == n and solid_n == n
