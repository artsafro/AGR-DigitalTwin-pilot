"""#1338: KPP1 windowgen test harness (jobs/KPP1/scripts/kpp1_windowgen.py).

Bays below are SYNTHETIC fixtures shaped like KPP1 openings_spec.json bays (rect [u0, u1, z0, z1], AGS68 window
bboxes 50 mm inside the bay); they are not data of a real object.
"""
import copy
import json
import math
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "jobs/KPP1/scripts"))
import kpp1_windowgen as kw  # noqa: E402

TYPES, STANDARD = kw.load_library()
FRAME = 0.07
TOL = STANDARD["criteria"]["apply_tol_m"]


def bay(bid, u0, z0, w, h, windows=None, glass=None):
    """Bay with AGS68 windows given relative to the bay corner as [x0, x1, z0, z1]."""
    rel = windows if windows is not None else [[0.05, w - 0.05, 0.05, h - 0.05]]
    return {"id": bid, "rect": [u0, u0 + w, z0, z0 + h],
            "windows": [[u0 + a, u0 + b, z0 + c, z0 + d] for a, b, c, d in rel],
            "glass": [[u0 + a, u0 + b, z0 + c, z0 + d] for a, b, c, d in (glass or [])]}


def spec_of(*bays):
    return {"S": {"surrounds": [{"rect": [0, 30, 0, 9], "mullions": [], "bays": list(bays)}], "features": []}}


W01 = lambda bid=1, u0=0.38: bay(bid, u0, 4.85, 1.18, 1.8)  # noqa: E731
W02 = lambda bid=2: bay(bid, 12.96, 1.2, 1.18, 5.45,  # noqa: E731
                        windows=[[0.05, 1.13, 0.05, 0.875], [0.05, 1.13, 2.05, 3.75], [0.05, 1.13, 3.8, 5.4]],
                        glass=[[0.05, 1.13, 0.925, 2.0]])
W03 = lambda bid=3: bay(bid, 5.45, 4.85, 2.0, 1.8,  # noqa: E731
                        windows=[[0.05, 0.975, 0.05, 1.75], [1.025, 1.95, 0.05, 1.75]])


def plan(*bays, types=TYPES, standard=STANDARD):
    return kw.plan_bays(spec_of(*bays), types, standard, frame=FRAME)


# ---- glass_rects: one source, accepted rule unchanged without a plan ------------------------------------------
def test_glass_rects_without_plan_is_the_accepted_v005_rule():
    b = W02()
    old = [[w[0] + FRAME, w[1] - FRAME, w[2] + FRAME, w[3] - FRAME] for w in b["windows"]] + b["glass"]
    assert kw.glass_rects(b, None, FRAME) == old


def test_glass_rects_requires_frame_and_known_bay():
    with pytest.raises(ValueError):
        kw.glass_rects(W01(), None, None)
    p = plan(W01(1))
    with pytest.raises(KeyError, match="99"):
        kw.glass_rects(W01(99), p, FRAME)


def test_build_kpp1_uses_one_glass_rects_source():
    src = (ROOT / "jobs/KPP1/scripts/build_kpp1.py").read_text(encoding="utf-8")
    assert "glass = glass_rects(b)" in src and "rects += glass_rects(b)" in src  # surround_cell + openings
    assert "w[0] + WINDOW_FRAME" not in src


# ---- substitution on matching bays ----------------------------------------------------------------------------
def test_w01_bay_substituted_with_7mm_inset():
    p = plan(W01())
    row = p["bays"]["1"]
    assert (row["type"], row["status"], row["why"]) == ("KPP1-W01", "substituted", [])
    assert row["pairs"][0]["delta_m"] == {"u0": 0.007, "u1": 0.007, "z0": 0.007, "z1": 0.007}
    assert row["pairs"][0]["old_delta_m"] == {"u0": FRAME, "u1": FRAME, "z0": FRAME, "z1": FRAME}
    assert kw.glass_rects(W01(), p, FRAME) == [[0.437, 1.503, 4.907, 6.593]]


def test_w02_and_w03_match_every_contour_once():
    p = plan(W02(), W03())
    assert p["counts"] == {"substituted": 2, "excluded": 0}
    assert sorted(x["contour"] for x in p["bays"]["2"]["pairs"]) == [0, 1, 2, 3]
    assert [x["src"] for x in p["bays"]["2"]["pairs"]].count("glass") == 1
    assert len(p["bays"]["3"]["pairs"]) == 2


# ---- fail-closed: mismatch stops the substitution ------------------------------------------------------------
@pytest.mark.parametrize("b,needle", [
    (bay(1, 0, 0, 1.18, 1.8, windows=[[0.05, 0.55, 0.05, 1.75], [0.6, 1.13, 0.05, 1.75]]), "count"),
    (bay(1, 0, 0, 1.18, 1.8, windows=[[0.12, 1.13, 0.05, 1.75]]), "outside"),     # 63 mm inset > tol on u0
    (bay(1, 0, 0, 1.18, 1.8, windows=[[0.06, 1.13, 0.06, 1.75]]), "outside"),     # glass beyond the AGS68 bbox
    (bay(1, 0, 0, 1.18, 1.8, windows=[[0.6, 1.13, 0.05, 1.75]]), "outside"),      # window narrower than glass
    (bay(1, 0, 0, 3.3, 1.8), "нет типа"),                                         # no library type of that size
    (bay(1, 0, 0, 1.18, 1.8, windows=[]), "count"),                              # empty source
])
def test_mismatch_excludes_bay_and_keeps_old_rects(b, needle):
    p = plan(b)
    row = p["bays"]["1"]
    assert row["status"] == "excluded" and row["glass"] is None
    assert any(needle in w for w in row["why"]), row["why"]
    assert kw.glass_rects(b, p, FRAME) == kw.old_rects(b, FRAME)
    assert row["contours"] == b["windows"] + b["glass"] and row["old_glass"] == kw.old_rects(b, FRAME)


@pytest.mark.parametrize("bad", [[0, math.nan, 0, 1], [0, math.inf, 0, 1], [1, 0, 0, 1], [0, 1, 0], "x"])
def test_bad_rect_is_an_error(bad):
    b = W01()
    b["windows"] = [bad]
    with pytest.raises(ValueError):
        plan(b)


def test_duplicate_bay_id_is_an_error():
    with pytest.raises(ValueError, match="duplicate"):
        plan(W01(1), W01(1, u0=5.0))


def test_opaque_type_excluded():
    types = copy.deepcopy(TYPES)
    t = next(x for x in types if x["id"] == "KPP1-W01")
    t["panes_m"] = [[0.05, 0.05, 1.13, 1.2]]
    t["opaque_m"] = [[0.05, 1.25, 1.13, 1.75]]
    b = bay(1, 0, 0, 1.18, 1.8, windows=[[0.05, 1.13, 0.05, 1.2], [0.05, 1.13, 1.25, 1.75]])
    row = plan(b, types=types)["bays"]["1"]
    assert row["status"] == "excluded" and any("opaque" in w for w in row["why"])


def test_no_symmetry_assumption_mirrored_asymmetric_source_excluded():
    types = copy.deepcopy(TYPES)
    t = next(x for x in types if x["id"] == "KPP1-W03")
    t["panes_m"] = [[0.05, 0.05, 0.6, 1.75], [0.65, 0.05, 1.95, 1.75]]   # asymmetric split
    ok = bay(1, 0, 0, 2.0, 1.8, windows=[[0.05, 0.6, 0.05, 1.75], [0.65, 1.95, 0.05, 1.75]])
    mirrored = bay(2, 3, 0, 2.0, 1.8, windows=[[0.05, 1.35, 0.05, 1.75], [1.4, 1.95, 0.05, 1.75]])
    p = plan(ok, mirrored, types=types)
    assert p["bays"]["1"]["status"] == "substituted"
    assert p["bays"]["2"]["status"] == "excluded"


def test_exactly_at_threshold_passes_and_just_beyond_fails():
    # the type glass edge is at 57 mm; a window edge at 57 - tol is exactly at tol, 1 mm further is beyond
    at = bay(1, 0, 0, 1.18, 1.8, windows=[[0.057 - TOL, 1.13, 0.05, 1.75]])
    beyond = bay(2, 3, 0, 1.18, 1.8, windows=[[0.057 - TOL - 0.001, 1.13, 0.05, 1.75]])
    p = plan(at, beyond)
    assert p["bays"]["1"]["status"] == "substituted"
    assert p["bays"]["2"]["status"] == "excluded"


def test_random_bays_every_bay_accounted_and_status_iff_deltas_in_range():
    rng = random.Random(1338)
    bays, n = [], 300
    for i in range(n):
        s = [rng.choice([0.05, 0.05, 0.057, 0.03, 0.02, 0.1, 0.06]) for _ in range(4)]
        bays.append(bay(i, i * 3.0, 0, 1.18, 1.8, windows=[[s[0], 1.18 - s[1], s[2], 1.8 - s[3]]]))
    p = plan(*bays)
    assert sum(p["counts"].values()) == n == len(p["bays"])
    for b in bays:
        row = p["bays"][str(b["id"])]
        w = b["windows"][0]
        g = [b["rect"][0] + 0.057, b["rect"][1] - 0.057, b["rect"][2] + 0.057, b["rect"][3] - 0.057]
        d = [g[0] - w[0], w[1] - g[1], g[2] - w[2], w[3] - g[3]]
        expect = all(-0.0005 <= x <= TOL + 1e-9 for x in d)
        assert (row["status"] == "substituted") == expect, (b, row["why"])
        assert row["status"] == "substituted" or row["why"]


# ---- report path guards ---------------------------------------------------------------------------------------
def test_write_plan_refuses_existing_or_input_path(tmp_path):
    census = tmp_path / "census"
    census.mkdir()
    (census / "openings_spec.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="inside the input"):
        kw.write_plan(spec_of(W01()), str(census / "plan.json"), [str(census)])
    with pytest.raises(ValueError, match="exists"):
        kw.write_plan(spec_of(W01()), str(census / "openings_spec.json"), [])
    assert sorted(x.name for x in census.iterdir()) == ["openings_spec.json"]
    assert (census / "openings_spec.json").read_text(encoding="utf-8") == "{}"
    out = tmp_path / "plan.json"
    p = kw.write_plan(spec_of(W01()), str(out), [str(census)])
    assert json.loads(out.read_text(encoding="utf-8"))["counts"] == p["counts"] == {"substituted": 1, "excluded": 0}


# ---- stage 1 --------------------------------------------------------------------------------------------------
def test_isolated_plan_places_each_type_and_unknown_is_error():
    iso = kw.isolated_plan(["KPP1-W01", "KPP1-W02", "KPP1-W03"], TYPES, STANDARD)
    assert {t: kw.mesh_summary(v["mesh"])["parts"]["glass"] for t, v in iso.items()} == \
        {"KPP1-W01": 1, "KPP1-W02": 4, "KPP1-W03": 2}
    with pytest.raises(KeyError, match="KPP1-W99"):
        kw.isolated_plan(["KPP1-W99"], TYPES, STANDARD)


def test_compare_readback_detects_each_difference():
    s = kw.mesh_summary(kw.isolated_plan(["KPP1-W03"], TYPES, STANDARD)["KPP1-W03"]["mesh"])
    assert kw.compare_readback(s, copy.deepcopy(s)) == []
    for mut in (lambda g: g.update(verts=g["verts"] + 1), lambda g: g["parts"].update(glass=1),
                lambda g: g["bbox"][1].__setitem__(0, 2.1), lambda g: g["glass"][0].__setitem__(4, 0.03),
                lambda g: g.update(glass=[]), lambda g: g.update(bbox=None)):
        g = copy.deepcopy(s)
        mut(g)
        assert kw.compare_readback(s, g)
