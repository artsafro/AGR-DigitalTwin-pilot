"""NPM -> VPM placement readback (#1731): VPM position == accepted NPM position - package pivot.

Pattern: n/a | new-case: tests of dt_ai.placement.vpm_readback (pure position gate).

Regression of Staropetrovskiy VPM v001 (2026-11-20): the pivot was subtracted twice after a Blender library append
(stale ``matrix_world``); the check must fail with every offender named, the correct placement must pass.
Fixture placement is SYNTHETIC (Staropetrovskiy pivot value, invented MAF / Flora handles).
"""
import math
import random

import pytest

from dt_ai.placement import vpm_readback as vr

PIVOT = [130.132, 17616.178, 166.49]
NPM = {  # synthetic accepted NPM placement, project coordinates (m)
    "maf:A01#1": [171.872, 17608.536, 166.49],
    "maf:B03#2": [140.5, 17630.25, 167.1],
    "flora:S12#7": [120.0, 17600.0, 165.9],
}


def minus(a, b):
    return [x - y for x, y in zip(a, b)]


def correct_scene():
    return {h: minus(p, PIVOT) for h, p in NPM.items()}


def twice_scene():
    return {h: minus(minus(p, PIVOT), PIVOT) for h, p in NPM.items()}


# --------------------------------------------------------------- incident regression
def test_pivot_subtracted_twice_fails_with_every_offender():
    rep = vr.check(NPM, twice_scene(), PIVOT)
    assert rep["status"] == "fail"
    assert sorted(o["handle"] for o in rep["offenders"]) == sorted(NPM)
    assert {o["diagnosis"] for o in rep["offenders"]} == {"pivot subtracted twice"}
    assert all(math.isclose(o["dev_m"], math.dist([0, 0, 0], PIVOT), rel_tol=1e-9) for o in rep["offenders"])
    with pytest.raises(vr.PlacementReadbackFailed, match="maf:A01#1: pivot subtracted twice"):
        vr.require_pass(rep)


def test_correct_placement_passes():
    rep = vr.check(NPM, correct_scene(), PIVOT)
    assert rep["status"] == "pass", rep
    assert rep["n_ok"] == 3 and rep["offenders"] == [] and rep["errors"] == []
    assert vr.require_pass(rep) is rep


def test_pivot_not_subtracted_is_named():
    rep = vr.check(NPM, dict(NPM), PIVOT)
    assert {o["diagnosis"] for o in rep["offenders"]} == {"pivot not subtracted"}


def test_unlabelled_points_twice_fails_correct_passes():
    """Joined VPM Ground: loose-part centres carry no handle; extra Ground parts are counted, not matched."""
    ground = [[-50.0, 3.0, -1.0], [10.0, 10.0, 0.0]]
    bad = vr.check_points(NPM, list(twice_scene().values()) + ground, PIVOT)
    assert bad["status"] == "fail" and {o["diagnosis"] for o in bad["offenders"]} == {"pivot subtracted twice"}
    good = vr.check_points(NPM, list(correct_scene().values()) + ground, PIVOT)
    assert good["status"] == "pass" and good["n_ok"] == 3 and good["n_scene_unmatched"] == 2


# --------------------------------------------------------------- tolerance and fail-closed
@pytest.mark.parametrize("dev,ok", [(0.0, True), (0.0099, True), (0.0101, False), (0.5, False)])
def test_tolerance_1cm(dev, ok):
    scene = correct_scene()
    scene["maf:A01#1"] = [scene["maf:A01#1"][0] + dev, *scene["maf:A01#1"][1:]]
    assert (vr.check(NPM, scene, PIVOT)["status"] == "pass") is ok
    assert (vr.check_points(NPM, list(scene.values()), PIVOT)["status"] == "pass") is ok


def test_exactly_at_tolerance_fails():
    """Dyadic values so the deviation equals the tolerance bit for bit."""
    npm, piv = {"a": [8.0, 4.0, 2.0]}, [1.0, 1.0, 1.0]
    for scene in ({"a": [7.25, 3.0, 1.0]}, {"a": [6.75, 3.0, 1.0]}):
        assert vr.check(npm, scene, piv, 0.25)["status"] == "fail"
        assert vr.check_points(npm, list(scene.values()), piv, 0.25)["status"] == "fail"
    assert vr.check(npm, {"a": [7.125, 3.0, 1.0]}, piv, 0.25)["status"] == "pass"


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, None, "1.0", True])
def test_non_finite_or_non_numeric_fails(bad):
    scene = correct_scene()
    scene["maf:B03#2"] = [bad, 0.0, 0.0]
    assert vr.check(NPM, scene, PIVOT)["status"] == "fail"
    npm = dict(NPM)
    npm["maf:B03#2"] = [0.0, bad, 0.0]
    assert vr.check(npm, correct_scene(), PIVOT)["status"] == "fail"
    assert vr.check_points(NPM, list(scene.values()), PIVOT)["status"] == "fail"
    assert vr.check(NPM, correct_scene(), [0.0, 0.0, bad])["status"] == "fail"


@pytest.mark.parametrize("tol", [0, -0.01, math.nan, math.inf, None, True])
def test_bad_tolerance_fails(tol):
    assert vr.check(NPM, correct_scene(), PIVOT, tol)["status"] == "fail"
    assert vr.check_points(NPM, list(correct_scene().values()), PIVOT, tol)["status"] == "fail"


def test_empty_partial_extra_and_duplicate_fail():
    assert vr.check({}, {}, PIVOT)["status"] == "fail"
    assert vr.check_points({}, [], PIVOT)["status"] == "fail"
    assert vr.check_points(NPM, [], PIVOT)["status"] == "fail"
    part = correct_scene()
    del part["flora:S12#7"]
    rep = vr.check(NPM, part, PIVOT)
    assert rep["status"] == "fail" and [o["diagnosis"] for o in rep["offenders"]] == ["missing in scene"]
    extra = correct_scene()
    extra["maf:ZZ#9"] = [0.0, 0.0, 0.0]
    assert "extra in scene maf:ZZ#9" in vr.check(NPM, extra, PIVOT)["errors"]
    recs = [{"handle": h, "position": p} for h, p in correct_scene().items()]
    scene, errs = vr.records_to_map(recs + [recs[0]])
    assert errs == ["duplicate handle maf:A01#1"]
    assert vr.check(NPM, scene, PIVOT, input_errors=errs)["status"] == "fail"
    assert vr.check(NPM, correct_scene(), [1.0, 2.0])["status"] == "fail"


def test_one_scene_point_never_matches_two_instances():
    npm = {"a": [1.0, 1.0, 1.0], "b": [1.0, 1.0, 1.0]}
    assert vr.check_points(npm, [[1.0, 1.0, 1.0]], [0.0, 0.0, 0.0])["status"] == "fail"
    assert vr.check_points(npm, [[1.0, 1.0, 1.0]] * 2, [0.0, 0.0, 0.0])["status"] == "pass"


def test_every_handle_ends_in_ok_or_offenders():
    scene = correct_scene()
    scene["maf:B03#2"] = [0.0, 0.0, 0.0]
    del scene["flora:S12#7"]
    rep = vr.check(NPM, scene, PIVOT)
    assert sorted(rep["ok"] + [o["handle"] for o in rep["offenders"]]) == sorted(NPM)


# --------------------------------------------------------------- generated probe
def test_generated_probe_pivot_twice_always_fails_correct_always_passes():
    rng = random.Random(1731)
    for _ in range(300):
        piv = [rng.uniform(-1e5, 1e5), rng.uniform(-1e5, 1e5), rng.uniform(-500, 500)]
        if math.dist(piv, [0, 0, 0]) < 0.02:
            continue
        npm = {f"h{i}": [rng.uniform(-2e5, 2e5), rng.uniform(-2e5, 2e5), rng.uniform(-100, 600)]
               for i in range(rng.randint(1, 30))}
        ok = {h: [c - q + rng.uniform(-0.005, 0.005) for c, q in zip(p, piv)] for h, p in npm.items()}
        two = {h: [c - 2 * q for c, q in zip(p, piv)] for h, p in npm.items()}
        assert vr.check(npm, ok, piv)["status"] == "pass"
        assert vr.check_points(npm, list(ok.values()), piv)["status"] == "pass"
        r = vr.check(npm, two, piv)
        assert r["status"] == "fail" and len(r["offenders"]) == len(npm)
        assert vr.check_points(npm, list(two.values()), piv)["status"] == "fail"


# --------------------------------------------------------------- report path
def test_report_path_that_is_an_input_writes_nothing(tmp_path):
    src = tmp_path / "npm.json"
    src.write_text("{}", encoding="utf-8")
    rep = vr.check(NPM, correct_scene(), PIVOT)
    with pytest.raises(ValueError, match="is an input"):
        vr.write_report(rep, src, [src])
    assert src.read_text(encoding="utf-8") == "{}"
    with pytest.raises(ValueError):
        vr.write_report(rep, tmp_path / "r.json", [tmp_path / "r.json.partial"])
    assert not (tmp_path / "r.json").exists()
    out = vr.write_report(rep, tmp_path / "r.json", [src])
    assert out.exists() and not (tmp_path / "r.json.partial").exists()
