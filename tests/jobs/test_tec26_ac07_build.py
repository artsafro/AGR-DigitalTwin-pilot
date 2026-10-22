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
    assert by[1] == Counter({"PanelVJ68": 53, "PanelVJ55": 32, "Roof_RAL5015": 96})
    assert set(by[3]) == {"PanelVJ68", "PanelVJ55"} and sum(by[3].values()) == 300
    assert by[6] == Counter({"Insert_RAL7004": 200})
    assert by[10] == Counter({"Plinth_RAL7004": 88})
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
    s["finishes"]["PanelVJ68"]["lower_band"] = bad
    with pytest.raises(ValueError, match="lower_band"):
        fm.validate_spec(s, kpp)


@pytest.mark.skipif(not os.path.exists("C:/x/tec26-oks/user-textures/panel_RAL5015_vertical_joints_4096.png"),
                    reason="Artem's panel texture is not on this machine")
def test_tile_grey_below_blue_above_same_joints(spec):
    import make_textures as mt
    t = spec["finishes"]["PanelVJ68"]
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
    bad["finishes"]["PanelVJ55"]["shift"] = [True, True]
    with pytest.raises(ValueError, match="shift"):
        fm.validate_spec(bad, kpp)
    bad = copy.deepcopy(spec)
    bad["finishes"]["Roof_RAL5015"]["plan_uv"]["u_axis"] = 2
    with pytest.raises(ValueError, match="plan_uv"):
        fm.validate_spec(bad, kpp)


def test_plan_uv_coordinates():
    V = [[1.0, 2.0, 3.3], [3.0, 2.0, 3.5], [3.0, 4.5, 3.5]]
    assert fm.plan_uv(V, [0, 1, 2], {"u_axis": 1, "v_axis": 0}, 0.5) == [(1.5, 1.0), (1.5, 3.0), (4.0, 3.0)]
