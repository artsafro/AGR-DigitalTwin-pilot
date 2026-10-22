"""AC07 (Пункт редуцирования газа 2) VPM/NPM build inputs (#564, recipe of the AC08 pilot #559 / PR #574).

Pure Python (no Blender): the spec, the finish split of the real Max dump, the facade rib contract from the sheet,
the lower grey band of the panel tile, glass IDs and the facade-axis regression on near-constant coordinates.
"""
import copy
import json
import math
import os
import sys
from collections import Counter

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(ROOT, "jobs", "TEC26-OKS", "scripts")
AC07 = os.path.join(ROOT, "jobs", "TEC26-OKS", "AC07")
sys.path.insert(0, SCRIPTS)

import finish_map as fm  # noqa: E402


@pytest.fixture(scope="module")
def spec():
    return fm.load(os.path.join(AC07, "vpm_textures.json"))


@pytest.fixture(scope="module")
def kpp():
    return fm.load_kpp()


@pytest.fixture(scope="module")
def body():
    d = fm.load(os.path.join(AC07, "max-dump-007.json"))
    n = [n for n in d["nodes"] if n["name"] == "АС.07"]
    assert len(n) == 1
    return n[0]


@pytest.fixture(scope="module")
def fins(spec, body):
    return fm.assign_finishes(body["vertices"], body["faces"], body["mat_ids"], spec)


def test_spec_validates_against_kpp(spec, kpp):
    assert fm.validate_spec(spec, kpp)


def test_dump_matches_gate1_census(body):
    """Native polygon counts per ID = the #558 census / Gate-1 MATERIALS.md table (source unchanged)."""
    want = {1: 181, 2: 671, 3: 300, 4: 772, 5: 24, 6: 200, 7: 120, 8: 504, 9: 30, 10: 88, 11: 64}
    assert dict(Counter(body["mat_ids"])) == want


def test_every_polygon_gets_its_finish(spec, body, fins):
    by = {}
    for m, f in zip(body["mat_ids"], fins):
        by.setdefault(m, Counter())[f] += 1
    assert by[1] == Counter({"PanelVJ68_RAL5015": 53, "PanelVJ55_RAL5015": 32, "Roof_RAL5015": 96})
    assert set(by[3]) == {"PanelVJ68_RAL5015", "PanelVJ55_RAL5015"} and sum(by[3].values()) == 300
    # slide 44: round vents = light disc (the vertical cap, 7047) with a dark hood/crescent (7004)
    assert by[6] == Counter({"VentDisc_RAL7047": 100, "Insert_RAL7004": 100})
    # slide 44/45: thin 7004 plinth above ±0.000, wall colour 7047 plain (no ribs) below
    assert by[10] == Counter({"Plinth_RAL7004": 44, "BelowGrade_RAL7047": 44})
    assert by[11] == Counter({"Interior": 64})


def test_roof_faces_never_take_a_panel_finish(body, fins):
    for f, fin in zip(body["faces"], fins):
        if fin.startswith("PanelVJ"):
            assert fm.is_vertical(body["vertices"], f)
        if fin == "Roof_RAL5015":
            assert not fm.is_vertical(body["vertices"], f)


def test_nonvertical_without_rule_is_an_error(spec, body):
    s = copy.deepcopy(spec)
    del s["source_ids"]["1"]["nonvertical"]
    with pytest.raises(ValueError, match="material ID 1 .*not vertical"):
        fm.assign_finishes(body["vertices"], body["faces"], body["mat_ids"], s)


def test_undeclared_nonvertical_finish_is_rejected(spec, kpp):
    s = copy.deepcopy(spec)
    s["source_ids"]["1"]["nonvertical"] = "Roof_Missing"
    with pytest.raises(ValueError, match="Roof_Missing is not declared"):
        fm.validate_spec(s, kpp)


def test_rib_contract_matches_the_sheet(spec, body, fins):
    """Per facade: ribs = sheet joints + 1 (55 short / 68 long), evenly over the measured wall field."""
    lo, hi = fm.body_plan_bbox(body["vertices"], spec["zero_m"])
    frames, rep = fm.field_frames(body["vertices"], body["faces"], fins, spec, lo, hi)
    assert set(rep) == {"1-3", "3-1", "А-Д", "Д-А"}
    for name, r in rep.items():
        fc = spec["facades"][name]
        assert len(r["joints_world"]) == fc["sheet_joints"] == fc["ribs"] - 1
        P = r["pitch_m"]
        assert abs(P - 0.2) < 0.0025  # sheet: one line every 200 mm
        js = r["joints_world"]
        assert abs((js[0] - r["field_lo"]) - (r["field_hi"] - js[-1])) < 1e-5  # symmetric
    assert sum(f is not None for f in frames) == sum(fin.startswith("PanelVJ") for fin in fins)


def test_sheet_facts_recorded(spec):
    sh = fm.load(os.path.join(ROOT, spec["sheet"]["facades_json"]))
    for name, fc in spec["facades"].items():
        f = sh["facades"][name]
        assert f["joints"] == fc["sheet_joints"] and f["ribs"] == fc["ribs"]
        assert f["wall_mm"] == fc["sheet_field_mm"]
        assert set(f["drawn_steps_mm"]) == {200.0}


def test_facade_axis_on_float_noise_wall(body, spec):
    """Regression (AC07 face 621): a -x wall face whose x differs by ~1e-7 m must run along y, not x."""
    V = body["vertices"]
    lo, hi = fm.body_plan_bbox(V, spec["zero_m"])
    for i in (621, 796, 986, 1040):
        assert fm.facade_axis(V, body["faces"][i], lo, hi)[0] == 1
    # brute force: every vertical ID1/ID3 face runs along the axis its facade normal implies
    for f, m in zip(body["faces"], body["mat_ids"]):
        if m in (1, 3) and fm.is_vertical(V, f):
            assert fm.facade_axis(V, f, lo, hi)[0] == 1 - fm.NORMALS[fm.facade_key(V, f)][0]


@pytest.mark.parametrize("noise", [0.0, 1e-9, 1e-7, 5e-6])
def test_facade_axis_generated_noise(noise):
    rng = np.random.default_rng(7)
    lo, hi = [0.0, 0.0], [10.0, 8.0]
    for _ in range(50):
        y0, y1 = sorted(rng.uniform(0, 8, 2))
        z0, z1 = sorted(rng.uniform(0, 3, 2))
        if y1 - y0 < 0.05 or z1 - z0 < 0.05:
            continue
        x = lambda: 0.0 + rng.uniform(-noise, noise)  # noqa: E731
        V = [[x(), y1, z0], [x(), y0, z0], [x(), y0, z1], [x(), y1, z1]]  # -x facade, outward normal -x
        assert fm.facade_key(V, [0, 1, 2, 3]) == "-x"
        assert fm.facade_axis(V, [0, 1, 2, 3], lo, hi)[0] == 1


def test_glass_ids_contract(spec, kpp):
    for bad in ([], [1], ["12"], [True]):
        s = copy.deepcopy(spec)
        s["glass_ids"] = bad
        with pytest.raises(ValueError):
            fm.validate_spec(s, kpp)
    s = copy.deepcopy(spec)
    del s["glass"]
    with pytest.raises(ValueError, match="glass block"):
        fm.validate_spec(s, kpp)


@pytest.mark.parametrize("bad", [{"z_max_m": float("nan"), "rgb": [208, 208, 208]},
                                 {"z_max_m": 0.0, "rgb": [208, 208, 208]},
                                 {"z_max_m": 4.1, "rgb": [208, 208, 208]},
                                 {"z_max_m": 2.5, "rgb": [208, 208, 300]},
                                 {"z_max_m": 2.5, "rgb": [200, 200, 200], "kpp_finish": "Cassette_RAL7047",
                                  "kpp_udim": 1006}])
def test_lower_band_fail_closed(spec, kpp, bad):
    s = copy.deepcopy(spec)
    s["finishes"]["PanelVJ68_RAL5015"]["lower_band"] = bad
    with pytest.raises(ValueError, match="lower_band"):
        fm.validate_spec(s, kpp)


@pytest.mark.skipif(not os.path.exists("C:/x/tec26-oks/user-textures/panel_RAL5015_vertical_joints_4096.png"),
                    reason="Artem's panel texture is not on this machine")
def test_tile_grey_below_blue_above_same_joints(spec):
    import make_textures as mt
    t = spec["finishes"]["PanelVJ68_RAL5015"]
    dif, _, _, nrm = mt.make_full(t, spec["size_full"])
    size, S = spec["size_full"], t["S"]
    z = (size - np.arange(size) - 0.5) * S / size
    grey_rows, blue_rows = np.where((z > 0.2) & (z < 2.45))[0], np.where((z > 2.55) & (z < 3.9))[0]
    Pp = t["P"][0] * size / S
    d = (np.arange(size) + 0.5 + Pp / 2) % Pp - Pp / 2
    panel_cols = np.abs(d) > 10
    for rows, rgb in ((grey_rows, t["lower_band"]["rgb"]), (blue_rows, t["rgb"])):
        med = np.median(dif[rows][:, panel_cols].reshape(-1, 3), 0)
        assert np.abs(med - np.array(rgb)).max() <= 3, (med, rgb)
    # joints: the same dark columns in both bands, one per period over the tile (vertical only)
    joint_cols = np.abs(d + 0.5) < 2
    for rows in (grey_rows, blue_rows):
        lum = dif[rows].mean((0, 2))
        assert lum[joint_cols].mean() < 0.75 * lum[panel_cols].mean()
    assert math.isclose(dif[grey_rows].mean((0, 2))[joint_cols].mean() / dif[grey_rows].mean((0, 2))[panel_cols].mean(),
                        dif[blue_rows].mean((0, 2))[joint_cols].mean() / dif[blue_rows].mean((0, 2))[panel_cols].mean(),
                        rel_tol=0.25)
    assert np.array_equal(nrm[grey_rows[0]], nrm[blue_rows[0]])  # normal map unchanged by the colour band
    json.dumps(t)  # spec stays JSON


def test_grey_mask_drops_antialiased_door_edge():
    """A 7047 wall row with real joints and a RAL 7004 door whose anti-aliased edge pixels blend into the wall:
    the edge blends must not count as joints (build-v004 counted 2 extra on facade 1-3)."""
    import joint_count as jc
    W = 400
    wall, joint, door = np.array([207, 207, 207]), np.array([73, 73, 73]), np.array([150, 153, 146])
    row = np.tile(wall, (W, 1)).astype(float)
    joints = list(range(40, 400, 40))
    for x in joints:
        row[x] = joint
    row[210:270] = door
    for x, w in ((209, 0.55), (208, 0.3), (270, 0.55), (271, 0.3)):  # blends wall|door
        row[x] = np.round(w * door + (1 - w) * wall)
    img = np.zeros((3, W, 3), np.uint8)
    img[1] = row.astype(np.uint8)
    view = {"center": [W / 2, 0.0, 0.0], "right": [1.0, 0.0, 0.0], "up": [0.0, 0.0, 1.0], "ortho_scale": float(W),
            "res": [W, 3]}
    s, lum = jc.render_row(img, view, 0, 0.0, 0.0, float(W), mask="grey")
    r = jc.count_joints(s, lum, 0.0, float(W), len(joints) + 1, tol=2.0, dark=0.85)
    visible = [x for x in joints if not 208 <= x <= 271]
    assert r["joints_found"] == len(visible) and not r.get("extra"), r


def test_roof_is_ribbed_like_the_slide(spec, kpp):
    """Slide 44 draws the roof RAL 5015 with ribs down the slope at the wall step (54 joints over the 10.9 m eave,
    like the wall band): the roof finish is the ribbed user texture with a plan UV (u = y, v = x) borrowing the
    rib contract of facade А-Д, not a plain placeholder."""
    t = spec["finishes"]["Roof_RAL5015"]
    assert t["kind"] == "full" and t["pattern"] == "user_vjoints" and "lower_band" not in t
    pu = t["plan_uv"]
    assert (pu["u_axis"], pu["v_axis"]) == (1, 0)
    src = spec["facades"][pu["ribs_from"]]
    assert math.isclose(t["P"][0], spec["finishes"][src["finish"]]["P"][0], abs_tol=1e-9)
    assert fm.validate_spec(spec, kpp)


def test_plan_uv_fail_closed(spec, kpp):
    bad = copy.deepcopy(spec)
    bad["finishes"]["Roof_RAL5015"]["plan_uv"]["ribs_from"] = "nope"
    with pytest.raises(ValueError, match="ribs_from"):
        fm.validate_spec(bad, kpp)
    bad = copy.deepcopy(spec)
    bad["finishes"]["Roof_RAL5015"]["P"] = [0.25, 0.25]
    with pytest.raises(ValueError):
        fm.validate_spec(bad, kpp)
    bad = copy.deepcopy(spec)  # a v shift is only for a plan-UV finish (rows carry noise, no joints)
    bad["finishes"]["PanelVJ55_RAL5015"]["shift"] = [True, True]
    with pytest.raises(ValueError, match="shift"):
        fm.validate_spec(bad, kpp)
    bad = copy.deepcopy(spec)
    bad["finishes"]["Roof_RAL5015"]["plan_uv"]["u_axis"] = 2
    with pytest.raises(ValueError, match="plan_uv"):
        fm.validate_spec(bad, kpp)


def test_plan_uv_coordinates():
    V = [[1.0, 2.0, 3.3], [3.0, 2.0, 3.5], [3.0, 4.5, 3.5]]
    assert fm.plan_uv(V, [0, 1, 2], {"u_axis": 1, "v_axis": 0}, 0.5) == [(1.5, 1.0), (1.5, 3.0), (4.0, 3.0)]


# ------------------------------------------------ v006: binding legend, vents, below grade, joint contrast (#564 r2)
def test_legend_covers_every_finish_and_the_grey_band(spec, kpp):
    """«Условные обозначения» [D171]: the RAL 7047 ribbed sandwich row holds the grey lower band of both panel
    finishes; Interior is the only exempt finish (not on a facade)."""
    rows = {(r["ral"], r["texture"]): r for r in spec["legend"]}
    assert set(rows[("7047", "ribbed")]["lower_bands"]) == {"PanelVJ68_RAL5015", "PanelVJ55_RAL5015"}
    assert set(rows[("5015", "ribbed")]["finishes"]) == {"PanelVJ68_RAL5015", "PanelVJ55_RAL5015", "Roof_RAL5015"}
    assert set(spec["legend_exempt"]) == {"Interior"}
    assert fm.validate_legend(spec, kpp) is True


def _legend_row(s, ral, tex):
    return next(r for r in s["legend"] if r["ral"] == ral and r["texture"] == tex)


@pytest.mark.parametrize("mutate,msg", [
    (lambda s: _legend_row(s, "7047", "ribbed")["lower_bands"].remove("PanelVJ55_RAL5015"), "lower band"),
    (lambda s: _legend_row(s, "7047", "ribbed")["lower_bands"].append("Roof_RAL5015"), "no lower_band"),
    (lambda s: _legend_row(s, "7047", "ribbed")["lower_bands"].append("Nope"), "not declared"),
    (lambda s: _legend_row(s, "7004", "plain").__setitem__("lower_bands", ["PanelVJ68_RAL5015"]), "lower band"),
    (lambda s: _legend_row(s, "5015", "ribbed").__setitem__("lower_bands", ["PanelVJ68_RAL5015"]), "lower band"),
    (lambda s: s.__setitem__("legend_exempt", {}), "Interior"),
    (lambda s: s["legend_exempt"].__setitem__("Nope", "x"), "not declared"),
    (lambda s: s["legend_exempt"].__setitem__("Door_RAL7004", "x"), "exempt"),
    (lambda s: s["legend_exempt"].__setitem__("Interior", ""), "reason"),
])
def test_legend_extensions_fail_closed(spec, kpp, mutate, msg):
    s = copy.deepcopy(spec)
    mutate(s)
    with pytest.raises(ValueError, match=msg):
        fm.validate_legend(s, kpp)


@pytest.mark.parametrize("rule,msg", [
    ({"split": "vertical", "vertical": "VentDisc_RAL7047"}, "nonvertical"),
    ({"split": "vertical", "vertical": "Nope", "nonvertical": "Insert_RAL7004"}, "not declared"),
    ({"split": "vertical", "vertical": "Insert_RAL7004", "nonvertical": "Insert_RAL7004"}, "differ"),
    ({"split": "normal"}, "unsupported split"),
])
def test_vertical_split_fail_closed(spec, kpp, rule, msg):
    s = copy.deepcopy(spec)
    s["source_ids"]["6"] = rule
    with pytest.raises(ValueError, match=msg):
        fm.validate_spec(s, kpp)


def test_vertical_split_assigns_by_face_orientation(spec):
    V = [[0, 0, 0], [0, 1, 0], [0, 1, 1], [0, 0, 1], [1, 0, 1], [1, 1, 1]]
    faces, ids = [[0, 1, 2, 3], [3, 2, 5, 4]], [6, 6]
    assert fm.assign_finishes(V, faces, ids, spec) == ["VentDisc_RAL7047", "Insert_RAL7004"]


def test_below_grade_is_plain_wall_colour(spec, kpp):
    """Below ±0.000 = wall colour 7047 without ribs (the KPP 7047 colour); the drop check runs on it."""
    t = spec["finishes"]["BelowGrade_RAL7047"]
    assert t["kind"] == "placeholder" and "pattern" not in t
    assert t["rgb"] == kpp["finishes"]["Cassette_RAL7047"]["rgb"]
    assert spec["drop_finish"] == "BelowGrade_RAL7047"
    assert spec["source_ids"]["10"] == {**spec["source_ids"]["10"], "split": "below_zero",
                                        "above": "Plinth_RAL7004", "below": "BelowGrade_RAL7047"}


@pytest.mark.parametrize("bad", [{"core": 0.0, "ao_mm": 10, "ao_min": 0.6}, {"core": 1.0, "ao_mm": 10, "ao_min": 0.6},
                                 {"core": 0.2, "ao_mm": -1, "ao_min": 0.6},
                                 {"core": 0.2, "ao_mm": float("nan"), "ao_min": 0.6},
                                 {"core": 0.2, "ao_mm": 10, "ao_min": 1.5}, {"core": 0.2, "ao_mm": 10},
                                 {"core": 0.2, "ao_mm": 10, "ao_min": 0.6, "normal_strength": float("inf")}])
def test_joint_dark_fail_closed(spec, kpp, bad):
    s = copy.deepcopy(spec)
    s["finishes"]["PanelVJ68_RAL5015"]["joint_dark"] = bad
    with pytest.raises(ValueError, match="joint_dark"):
        fm.validate_spec(s, kpp)


@pytest.mark.skipif(not os.path.exists("C:/x/tec26-oks/user-textures/panel_RAL5015_vertical_joints_4096.png"),
                    reason="Artem's panel texture is not on this machine")
def test_joints_read_dark_on_grey_and_blue(spec):
    """Orchestrator 2026-10-22: joints dark and crisp on both 5015 and 7047 like the slide. Averaged over 10 mm
    (one render pixel at the 100 px/m compare scale) around each joint, the joint column is <= 0.55 of the panel."""
    import make_textures as mt
    t = spec["finishes"]["PanelVJ68_RAL5015"]
    dif, _, _, _ = mt.make_full(t, spec["size_full"])
    size, S = spec["size_full"], t["S"]
    z = (size - np.arange(size) - 0.5) * S / size
    Pp = t["P"][0] * size / S
    d = (np.arange(size) + 0.5 + Pp / 2) % Pp - Pp / 2
    near = np.abs(d) < 0.005 * size / S          # 10 mm wide window around each joint centre
    panel = np.abs(d) > 0.05 * size / S
    for rows in (np.where((z > 0.2) & (z < 2.45))[0], np.where((z > 2.55) & (z < 3.9))[0]):
        lum = dif[rows].mean((0, 2))
        assert lum[near].mean() <= 0.55 * lum[panel].mean(), (lum[near].mean(), lum[panel].mean())


def _door_profile(remnants, step=0.0005):
    """Panel field 0..2 m, 10 ribs (P 0.2), lum 200, joints 8 mm dark; a door (NaN) over 0.985..1.3 hides the joint at
    1.0 (and 1.2); `remnants` = centres of dark 6 mm runs left beside the door (the hidden joint's darkening halo)."""
    s = np.arange(step / 2, 2.0, step)
    lum = np.full(s.shape, 200.0)
    for k in range(1, 10):
        lum[np.abs(s - 0.2 * k) < 0.004] = 40.0
    for c in remnants:
        lum[np.abs(s - c) < 0.003] = 90.0
    lum[(s > 0.985) & (s < 1.3)] = np.nan
    return s, lum


@pytest.mark.parametrize("remnants,footprint,ok", [
    ([], 0.0, True),                     # control: plain door, nothing beside it
    ([0.982], 0.0, False),               # halo remnant, no footprint declared -> extra (old behaviour, fail-closed)
    ([0.982], 0.021, True),              # remnant touching the door 18 mm from the hidden joint, footprint 21 mm
    ([0.95], 0.06, False),               # 50 mm away, not touching the door: a real extra line, never absorbed
    ([0.97], 0.021, False),              # within reach but free-standing (does not touch the occluder)
    ([0.972, 0.982], 0.03, False),       # two runs for one hidden joint -> one is extra
])
def test_hidden_joint_halo_remnant(remnants, footprint, ok):
    import joint_count as jc
    s, lum = _door_profile(remnants)
    r = jc.count_joints(s, lum, 0.0, 2.0, 10, tol=0.003, footprint=footprint)
    assert r["ok"] is ok, r
    if ok and remnants:
        assert r["hidden_partial"] == [1.0]


@pytest.mark.parametrize("fp", [-0.01, float("nan"), float("inf"), 0.2])
def test_footprint_fail_closed(fp):
    import joint_count as jc
    s, lum = _door_profile([])
    with pytest.raises(ValueError, match="footprint"):
        jc.count_joints(s, lum, 0.0, 2.0, 10, tol=0.003, footprint=fp)


@pytest.mark.parametrize("footprint,ok", [(0.0, False), (0.021, True)])
def test_clipped_joint_beside_door(footprint, ok):
    """NPM 1-3 v006: the door clips a joint's dark footprint, the visible run's centre moves 9 mm (> tol): with the
    declared footprint it is that joint (clipped), without it a missing + extra pair (fail-closed default)."""
    import joint_count as jc
    step = 0.0005
    s = np.arange(step / 2, 2.0, step)
    lum = np.full(s.shape, 200.0)
    for k in range(1, 10):
        lum[np.abs(s - 0.2 * k) < 0.004] = 40.0
    lum[(s > 0.984) & (s < 1.0)] = 90.0          # halo + joint core of the 1.0 joint, left of the door
    lum[(s >= 0.999) & (s < 1.3)] = np.nan
    r = jc.count_joints(s, lum, 0.0, 2.0, 10, tol=0.003, footprint=footprint)
    assert r["ok"] is ok, r
    if ok:
        assert r["clipped"] == [1.0] and not r["missing"] and not r["extra"]


@pytest.mark.parametrize("footprint,ok", [(0.0, False), (0.021, True)])
def test_split_footprint_beside_matched_joint(footprint, ok):
    """Compare render NPM 1-3 v006: the door edge pixel sits inside the halo of a VISIBLE joint 21 mm away and falls
    below the threshold as its own run: with the declared footprint it is that joint's (`split`), else extra."""
    import joint_count as jc
    step = 0.0005
    s = np.arange(step / 2, 2.0, step)
    lum = np.full(s.shape, 200.0)
    for k in range(1, 10):
        lum[np.abs(s - 0.2 * k) < 0.004] = 40.0
    lum[(s > 1.0185) & (s < 1.0195)] = 150.0       # halo + edge blend, separated from the joint core by panel
    lum[(s >= 1.0195) & (s < 1.3)] = np.nan          # the door
    r = jc.count_joints(s, lum, 0.0, 2.0, 10, tol=0.003, footprint=footprint)
    assert r["ok"] is ok, r
    if ok:
        assert r["split"] == [1.0]
