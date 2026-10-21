"""Numeric margin on twinqa findings: measured, threshold, signed safe-side margin.

new-case: signed numeric-margin reporting (measured/threshold/margin + near-threshold summary).

Synthetic values only. The sign oracle is the issue formula, written here independently
of the helper: min -> (measured - threshold) / threshold, max -> (threshold - measured) / threshold.
Positive means on the safe side. Margin is None when the check is not numeric or the
threshold is 0. A pass with 0 <= margin < NEAR_THRESHOLD_MARGIN is a near-threshold line.
"""
import json
import math
import random
from dataclasses import fields

import pytest

from test_scene import mesh, rb
from test_validator import PROFILES
from twinqa.geometry import ucx_audit as ua
from twinqa.report import Finding, Stage, ValidationReport
from twinqa.scene import scene_findings
import twinqa.report as report_mod
import twinqa.uv as uv_mod

EXISTING_FINDING_KEYS = {
    "name", "status", "observed", "expected", "source_pdf_pages", "evidence", "conflicts",
}
EXISTING_STAGE_KEYS = {"id", "check", "gate", "source_pdf_pages", "findings", "status"}
EXISTING_REPORT_KEYS = {
    "profile", "target", "target_sha256", "source_sha256", "source_pdf_verified",
    "passed", "exit_code", "machine_stage_counts", "manual_reviews_pending", "stages", "notes",
}
BOX_TRIS = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1),
            (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]


def _spec_margin(measured, threshold, bound):
    """Independent sign oracle. Not a call into production code."""
    if bound == "min":
        return (measured - threshold) / threshold
    if bound == "max":
        return (threshold - measured) / threshold
    raise AssertionError(f"unmapped bound {bound!r}")


def _signed_margin():
    fn = getattr(report_mod, "signed_margin", None)
    assert fn is not None, "signed_margin missing"
    return fn


def _near_constant():
    value = getattr(report_mod, "NEAR_THRESHOLD_MARGIN", None)
    assert value == 0.05
    return value


def _finding(name, status, observed, expected, pages, **numeric):
    known = {item.name for item in fields(Finding)}
    kwargs = {
        "name": name,
        "status": status,
        "observed": observed,
        "expected": expected,
        "source_pdf_pages": list(pages),
    }
    for key, value in numeric.items():
        if key not in known:
            pytest.fail(f"Finding has no {key}")
        kwargs[key] = value
    return Finding(**kwargs)


def _report(findings):
    stage = Stage("V003", "synthetic check", "blocking", [7], list(findings))
    return ValidationReport("vpm", "synthetic.fbx", "a" * 64, "b" * 64, True, [stage])


def _box(lo, hi):
    verts = [(hi[0] if i & 4 else lo[0], hi[1] if i & 2 else lo[1], hi[2] if i & 1 else lo[2])
             for i in range(8)]
    return verts, list(BOX_TRIS)


def _ucx(name, geom):
    verts, tris = geom
    item = mesh(name=name, tris=12)
    item["hull"] = {"verts": verts, "tris": tris}
    return item


def _quad(y, size):
    return [[0.0, y, 0.0], [0.0, y, size], [size, y, size], [size, y, 0.0]]


def _faced(quads):
    vertices, polygons = [], []
    for quad in quads:
        polygons.append(list(range(len(vertices), len(vertices) + len(quad))))
        vertices.extend(quad)
    item = mesh(tris=len(quads) * 2, degrees={"4": len(quads)})
    item["face_geometry"] = {"vertices": vertices, "polygons": polygons}
    return item


def _old_payload():
    return {
        "profile": "vpm",
        "target": "old.fbx",
        "target_sha256": "c" * 64,
        "source_sha256": "d" * 64,
        "source_pdf_verified": False,
        "passed": False,
        "exit_code": 2,
        "machine_stage_counts": {"pass": 0, "fail": 0, "review": 1, "not_run": 0},
        "manual_reviews_pending": [],
        "notes": ["legacy synthetic"],
        "stages": [{
            "id": "V003",
            "check": "triangles",
            "gate": "blocking",
            "source_pdf_pages": [7],
            "status": "review",
            "findings": [{
                "name": "triangle count",
                "status": "review",
                "observed": "old.fbx: 200000",
                "expected": "<= 150000 project target",
                "source_pdf_pages": [7, 28],
                "evidence": "old.fbx",
                "conflicts": [],
            }],
        }],
    }


def test_min_threshold_margin_is_positive_on_the_safe_side():
    margin = _signed_margin()
    assert margin(600, 500, "min") == pytest.approx(0.2)
    assert margin(400, 500, "min") == pytest.approx(-0.2)
    assert margin(500, 500, "min") == pytest.approx(0.0)


def test_max_threshold_margin_is_positive_on_the_safe_side():
    margin = _signed_margin()
    assert margin(100, 200, "max") == pytest.approx(0.5)
    assert margin(250, 200, "max") == pytest.approx(-0.25)
    assert margin(200, 200, "max") == pytest.approx(0.0)


def test_near_threshold_pass_is_flagged_in_summary():
    _near_constant()
    close = _finding("triangle count", "pass", "148500", "<= 150000", [7],
                     measured=148500, threshold=150000, margin=0.01)
    exact = _finding("texel density", "pass", "512", ">= 512", [32],
                     measured=512, threshold=512, margin=0.0)
    text = _report([close, exact]).summary()
    assert "near threshold: triangle count margin 0.01 (measured 148500, threshold 150000)" in text
    assert "near threshold: texel density margin 0 (measured 512, threshold 512)" in text


def test_margin_at_the_cutoff_is_not_flagged_and_a_fail_is_not_flagged():
    _near_constant()
    comfortable = _finding("triangle count", "pass", "100000", "<= 150000", [7],
                           measured=100000, threshold=150000, margin=0.05)
    failed = _finding("triangle count", "fail", "160000", "<= 150000", [7],
                      measured=160000, threshold=150000, margin=0.01)
    text = _report([comfortable, failed]).summary()
    assert "near threshold:" not in text


def test_non_numeric_finding_has_null_measures():
    item = Finding("mesh names", "pass", "ok", "grammar", [11])
    assert getattr(item, "measured", "missing") is None
    assert getattr(item, "threshold", "missing") is None
    assert getattr(item, "margin", "missing") is None


def test_to_dict_adds_numeric_keys_and_keeps_existing_keys():
    item = _finding("triangle count", "pass", "100", "<= 150000", [7],
                    measured=100, threshold=150000, margin=149900 / 150000)
    payload = _report([item]).to_dict()
    assert set(payload) == EXISTING_REPORT_KEYS
    stage = payload["stages"][0]
    assert set(stage) == EXISTING_STAGE_KEYS
    finding = stage["findings"][0]
    assert EXISTING_FINDING_KEYS <= set(finding)
    assert set(finding) == EXISTING_FINDING_KEYS | {"measured", "threshold", "margin"}
    assert finding["measured"] == 100
    assert finding["threshold"] == 150000
    assert finding["margin"] == pytest.approx(149900 / 150000)
    assert finding["name"] == "triangle count"
    assert finding["status"] == "pass"


def test_old_report_json_without_new_keys_loads():
    loader = getattr(ValidationReport, "from_dict", None)
    assert loader is not None, "ValidationReport.from_dict missing"
    loaded = loader(json.loads(json.dumps(_old_payload())))
    finding = loaded.stages[0].findings[0]
    assert finding.measured is None and finding.threshold is None and finding.margin is None
    assert finding.name == "triangle count" and finding.status == "review"
    assert loaded.notes == ["legacy synthetic"]
    assert loaded.passed is False
    again = json.loads(json.dumps(loaded.to_dict()))
    assert {"measured", "threshold", "margin"} <= set(again["stages"][0]["findings"][0])


def test_unmapped_report_key_is_named():
    loader = getattr(ValidationReport, "from_dict", None)
    assert loader is not None, "ValidationReport.from_dict missing"
    payload = _old_payload()
    payload["surprise"] = 1
    with pytest.raises(ValueError, match="surprise"):
        loader(payload)
    finding = dict(payload["stages"][0]["findings"][0])
    payload = _old_payload()
    payload["stages"][0]["findings"][0] = {**finding, "slot": "Diffuse"}
    with pytest.raises(ValueError, match="slot"):
        loader(payload)


def test_margin_none_when_threshold_is_zero_or_not_numeric():
    margin = _signed_margin()
    for threshold in (0, 0.0, -0.0):
        assert margin(5, threshold, "min") is None
        assert margin(5, threshold, "max") is None
    for measured, threshold in (
        ("x", 1), (None, 1), (1, None), ("", 1), (1, ""), ([], 1), ({}, 1),
        (True, 1), (1, False), (1, "0"),
    ):
        assert margin(measured, threshold, "min") is None
        assert margin(measured, threshold, "max") is None


def test_probe_invalid_and_exact_threshold_never_pass_or_not_run():
    """Fail closed: empty, partial, unsupported, NaN/inf, and exact threshold are not a pass."""
    margin = _signed_margin()
    cases = []
    for bound in ("", "median", "MIN", None, 1, "minimum"):
        cases.append(("unsupported", 1.0, 1.0, bound, "error"))
    for bad in (float("nan"), float("inf"), float("-inf")):
        cases.append(("nan", bad, 1.0, "min", "error"))
        cases.append(("nan", 1.0, bad, "max", "error"))
    for measured, threshold in (("", 1.0), (1.0, ""), (None, 1.0), (1.0, None), ([], 2.0)):
        cases.append(("empty", measured, threshold, "min", "error"))
    cases.append(("partial", 1.0, 0.0, "max", "error"))
    cases.append(("exact", 512.0, 512.0, "min", "fail"))
    cases.append(("exact", 150000, 150000, "max", "fail"))
    assert cases
    for kind, measured, threshold, bound, expected in cases:
        got = _probe_disposition(margin, measured, threshold, bound)
        assert got == expected, (kind, measured, threshold, bound, got)
        assert got not in {"pass", "not_run"}


def test_probe_sign_matches_safe_side_for_generated_inputs():
    margin = _signed_margin()
    rng = random.Random(462)
    seen = 0
    for _ in range(200):
        threshold = 10 ** rng.uniform(-4, 6)
        measured = threshold * rng.uniform(0.0, 4.0)
        for bound in ("min", "max"):
            got = margin(measured, threshold, bound)
            expect = _spec_margin(measured, threshold, bound)
            assert got == pytest.approx(expect, rel=1e-12, abs=1e-12)
            safe = measured >= threshold if bound == "min" else measured <= threshold
            if math.isclose(measured, threshold, rel_tol=0.0, abs_tol=0.0):
                assert got == pytest.approx(0.0)
                assert _probe_disposition(margin, measured, threshold, bound) == "fail"
            elif safe:
                assert got > 0
                assert _probe_disposition(margin, measured, threshold, bound) == "pass"
            else:
                assert got < 0
                assert _probe_disposition(margin, measured, threshold, bound) == "fail"
            seen += 1
    assert seen == 400


def test_texel_density_finding_carries_512_margin():
    fn = getattr(uv_mod, "density_findings", None)
    assert fn is not None, "density_findings missing"
    side = 512 / 530
    square = [(0.0, 0.0, 0.0), (side, 0.0, 0.0), (side, side, 0.0), (0.0, side, 0.0)]
    uv = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    findings = fn(square, uv, 512)
    lower = next(item for item in findings if item.threshold == 512)
    assert lower.measured == pytest.approx(530)
    assert lower.margin == pytest.approx((530 - 512) / 512)
    assert lower.margin > 0
    assert lower.status == "pass"
    text = _report([lower]).summary()
    assert "near threshold:" in text and "512" in text
    upper = next(item for item in findings if item.threshold == 1706)
    assert upper.measured == pytest.approx(530)
    assert upper.margin == pytest.approx((1706 - 530) / 1706)
    assert upper.status == "pass"
    empty = fn([], [], 512)
    assert empty and all(item.status == "fail" for item in empty)
    assert all(item.margin is None for item in empty)
    with pytest.raises(ValueError, match="Degenerate"):
        fn([(0.0, 0.0, 0.0), (0.0, 0.0, 0.0)], [(0.0, 0.0), (0.0, 0.0)], 512)


def test_polycount_margins_for_target_and_ceiling():
    def triangle(tris):
        found = scene_findings(rb(mesh(tris=tris)), "vpm", "oks", PROFILES.vpm)
        return next(item for item in found["V003"] if item.name == "triangle count")

    at_target = triangle(150_000)
    assert at_target.status == "pass"
    assert at_target.measured == 150_000
    assert at_target.threshold == 150_000
    assert at_target.margin == pytest.approx(0.0)
    assert "near threshold:" in _report([at_target]).summary()
    near = triangle(148_500)
    assert near.status == "pass"
    assert near.threshold == 150_000
    assert near.margin == pytest.approx((150_000 - 148_500) / 150_000)
    over_ceiling = triangle(1_000_001)
    assert over_ceiling.status == "fail"
    assert over_ceiling.measured == 1_000_001
    assert over_ceiling.threshold == 1_000_000
    assert over_ceiling.margin == pytest.approx((1_000_000 - 1_000_001) / 1_000_000)
    assert over_ceiling.margin < 0
    npm_limit = PROFILES.npm["geometry"]["oks_triangles_per_fbx_max"]
    npm = scene_findings(rb(mesh(tris=100_000)), "npm", "oks", PROFILES.npm)
    npm_item = next(item for item in npm["V003"] if item.name == "triangle count")
    assert npm_item.threshold == npm_limit
    assert npm_item.margin == pytest.approx((npm_limit - 100_000) / npm_limit)


def test_ucx_too_close_and_band_margins():
    gap = 0.0001
    findings = ua.pair_findings(_box((0, 0, 0), (1, 1, 1)), _box((1 + gap, 0, 0), (2 + gap, 1, 1)),
                                name_a="L", name_b="R")
    too_close = next(item for item in findings if item["type"] == "too_close")
    band = next(item for item in findings if item["type"] == "gap_out_of_band")
    measured = too_close["gap_m"]
    assert too_close["measured"] == measured
    assert too_close["threshold"] == ua.TOUCH_M
    assert too_close["margin"] == pytest.approx((measured - ua.TOUCH_M) / ua.TOUCH_M)
    assert too_close["margin"] < 0
    assert band["threshold"] == ua.GAP_BAND_M[0]
    assert band["margin"] == pytest.approx((measured - ua.GAP_BAND_M[0]) / ua.GAP_BAND_M[0])
    wide_gap = 0.02
    wide = ua.pair_findings(_box((0, 0, 0), (1, 1, 1)),
                            _box((1 + wide_gap, 0, 0), (2 + wide_gap, 1, 1)))
    wide_finding = next(item for item in wide if item["type"] == "gap_out_of_band")
    wide_measured = wide_finding["gap_m"]
    assert wide_finding["threshold"] == ua.GAP_BAND_M[1]
    assert wide_finding["margin"] == pytest.approx((ua.GAP_BAND_M[1] - wide_measured) / ua.GAP_BAND_M[1])
    assert wide_finding["margin"] < 0
    overlap = ua.pair_findings(_box((0, 0, 0), (1, 1, 1)), _box((0.5, 0, 0), (1.5, 1, 1)))
    assert overlap[0]["type"] == "intersect"
    assert overlap[0]["measured"] is None and overlap[0]["threshold"] is None and overlap[0]["margin"] is None
    near_gap = 0.0096
    left = _ucx("UCX_SM_Test_K_1_Main_001", _box((0, 0, 0), (1, 1, 1)))
    right = _ucx("UCX_SM_Test_K_1_Main_002", _box((1 + near_gap, 0, 0), (2 + near_gap, 1, 1)))
    found = scene_findings(rb(mesh(tris=100), left, right), "vpm", "oks", PROFILES.vpm)
    advisory = next(item for item in found["V010"] if item.name == "UCX piece gap (advisory)")
    assert advisory.status == "pass"
    assert advisory.threshold == ua.GAP_BAND_M[1]
    assert advisory.margin == pytest.approx((ua.GAP_BAND_M[1] - near_gap) / ua.GAP_BAND_M[1], abs=1e-6)
    assert 0 <= advisory.margin < 0.05
    assert "near threshold:" in _report([advisory]).summary()


def test_clearance_band_margin():
    band = PROFILES.vpm["geometry"]["near_coplanar_spacing_m"]
    found = scene_findings(rb(_faced([_quad(0.0, 1.0), _quad(0.005, 1.0)])), "vpm", "oks", PROFILES.vpm)
    item = next(entry for entry in found["V004"] if entry.name == "co-directional clearance")
    assert item.status == "pass"
    assert item.measured == pytest.approx(band["min"])
    assert item.threshold == pytest.approx(band["min"])
    assert item.margin == pytest.approx(0.0)
    assert "near threshold:" in _report([item]).summary()
    below = scene_findings(rb(_faced([_quad(0.0, 1.0), _quad(0.002, 1.0)])), "vpm", "oks", PROFILES.vpm)
    failed = next(entry for entry in below["V004"] if entry.name == "co-directional clearance")
    assert failed.status == "fail"
    assert failed.threshold == pytest.approx(band["min"])
    assert failed.margin == pytest.approx((0.002 - band["min"]) / band["min"])
    assert failed.margin < 0


def _probe_disposition(margin, measured, threshold, bound):
    """Closed reading of one input. Exact threshold is fail, never an unmarked pass."""
    if not isinstance(bound, str) or bound not in ("min", "max"):
        try:
            margin(measured, threshold, bound)
        except ValueError as exc:
            assert "unmapped bound" in str(exc)
            assert repr(bound) in str(exc)
            return "error"
        pytest.fail(f"unmapped bound {bound!r} was accepted")
    try:
        value = margin(measured, threshold, bound)
    except ValueError:
        return "error"
    if value is None:
        return "error"
    if value == 0:
        return "fail"
    if value < 0:
        return "fail"
    return "pass"
