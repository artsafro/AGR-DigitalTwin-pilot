"""#1230 KPP1 R1 rerun receipts: V004 topology within its limit, Stair built, every L01 mullion accounted for,
textures (V006/V007/V009) run and pass, UCX gaps in band; fail-closed probes of the parts builder.

new-case: receipt tests for the KPP1 #1230 offline rerun (jobs/KPP1/rerun-1230/).
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

RUN = Path(__file__).resolve().parents[1] / "jobs" / "KPP1" / "rerun-1230"


def _load(name):
    return json.loads((RUN / name).read_text(encoding="utf-8"))


def _findings(rep, stage):
    return [f for s in rep["stages"] if s["id"] == stage for f in s["findings"]]


def _parts():
    spec = importlib.util.spec_from_file_location("kpp1_r1230_parts", RUN / "build_parts.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("receipt", ["SM_Kpp_1.zip.r1-v002.validate.json", "0000_Kpp_1_01.r1-v002.validate.json"])
def test_v004_topology_passes_and_no_pair_below_5mm(receipt):
    rep = _load(receipt)
    topo = [f for f in _findings(rep, "V004") if f["name"] == "topology defects"]
    assert topo and all(f["status"] == "pass" for f in topo), topo
    clear = [f for f in _findings(rep, "V004") if f["name"] == "co-directional clearance"]
    assert clear and all(": 0 < 5 mm" in f["observed"] for f in clear), clear


def test_vpm_textures_density_and_ucx_gap_pass():
    rep = _load("SM_Kpp_1.zip.r1-v002.validate.json")
    for stage in ("V007", "V009"):
        fs = _findings(rep, stage)
        assert fs and all(f["status"] == "pass" for f in fs), (stage, fs)
    gap = [f for f in _findings(rep, "V010") if f["name"] == "UCX piece gap (advisory)"]
    assert gap and gap[0]["status"] == "pass", gap


def test_npm_embedded_atlas_passes():
    fs = _findings(_load("0000_Kpp_1_01.r1-v002.validate.json"), "V006")
    assert fs and all(f["status"] == "pass" for f in fs), fs


def test_receipts_never_claim_passed():
    for name in ("SM_Kpp_1.zip.r1-v002.validate.json", "0000_Kpp_1_01.r1-v002.validate.json"):
        assert _load(name)["passed"] is False      # V001/V011/V013/V014 deferred, manual V015-V017 open


def test_every_mullion_insert_is_built_or_reported_and_stair_built():
    sched = _load("parts-schedule-r1-v002.json")
    built, dropped = sched["mullions"], sched["mullions_dropped"]
    assert len(built) == sched["mullion_inserts"] == 244
    assert dropped == []
    previous = _load("parts-schedule-v001.json")
    assert built[:len(previous["mullions"])] == previous["mullions"]
    assert sched["stair"] == previous["stair"]
    missing_ids = ("1856177", "1857706", "1858064", "1856176", "1858448", "1858062")
    for block_id in missing_ids:
        assert any(f"-{block_id}-" in b["block"] and b["placement"].startswith("corner member") for b in built)
    assert len(sched["stair"]) >= 10
    rep = _load("build-report-r1-v002.json")
    assert rep["mullions_built"] == len(built) and rep["stair_boxes"] == len(sched["stair"])
    assert rep["triangles_parts_before_union"]["Stair"] > 0


@pytest.mark.parametrize("facade", ["Западный", "Восточный"])
@pytest.mark.parametrize("rect", [(-0.4579, -0.3829, 3.300, 4.775),
                                  (11.3821, 11.4571, 3.075, 4.815),
                                  (11.3296, 11.4196, 6.725, 8.550)])
def test_missing_corner_members_are_built(facade, rect):
    mod = _parts()
    # Real L01 review witnesses, in facade metres; no perpendicular counterpart.
    inverse = ((lambda u: 92848 - u * 1000) if facade == "Западный"
               else (lambda u: 102956 + u * 1000))
    a, b, za, zb = rect
    x0, x1 = sorted((inverse(a), inverse(b)))
    item = {"facade": facade, "block": "Прямоугольный импост - 200х75 мм",
            "rect": (x0, x1, za * 1000, zb * 1000)}
    built, dropped = mod.place_mullions([], [item], [], [])
    assert not dropped, dropped
    assert len(built) == 1
    assert built[0]["min"][2] == pytest.approx(za)
    assert built[0]["max"][2] == pytest.approx(zb)
    assert all(a < b for a, b in zip(built[0]["min"], built[0]["max"]))


@pytest.mark.parametrize("change", ["none", "profile", "height", "far_end", "parallel"])
def test_edge_alias_requires_same_profile_height_and_corner(change):
    mod = _parts()
    f, name, rect = "Западный", "импост 200х75", (-0.42, -0.33, 3.3, 4.775)
    member = {"facade": "Южный", "block": name,
              **mod.R9.cutter("Южный", (-0.33, -0.255, 3.3, 4.775), -0.2, 0.01)}
    if change == "profile":
        member["block"] = "импост 50х100"
    elif change == "height":
        member["max"][2] += .021
    elif change == "far_end":
        member["min"][0] += 5
        member["max"][0] += 5
    elif change == "parallel":
        member["facade"] = f
    assert mod.edge_counterpart(f, name, rect, [member]) == (0 if change == "none" else None)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_corner_nonfinite_rect_is_an_error(bad):
    mod = _parts()
    with pytest.raises(SystemExit, match="non-finite"):
        mod.place_mullions([], [{"facade": "Восточный", "block": "импост 200х75",
                                 "rect": (102500, 102575, 3300, bad)}], [], [])


@pytest.mark.parametrize("offset", [-0.020001, -0.02, -0.019999, 0.019999, 0.02, 0.020001])
def test_edge_height_tolerance_boundary(offset):
    mod = _parts()
    name = "импост 200х75"
    member = {"facade": "Южный", "block": name,
              **mod.R9.cutter("Южный", (-.33, -.255, 3.3, 4.775), -.2, .01)}
    member["min"][2] = 3.3 + offset
    member["max"][2] = 4.775 + offset
    expected = 0 if abs(offset) <= .02 else None
    assert mod.edge_counterpart("Западный", name, (-.42, -.33, 3.3, 4.775), [member]) == expected


@pytest.mark.parametrize("reverse", [False, True])
def test_edge_alias_names_real_counterpart_independent_of_order(monkeypatch, reverse):
    mod = _parts()
    monkeypatch.setattr(mod.R9, "first_hit", lambda bands, f, u, z: 0 if f == "Южный" else None)
    name = "импост 200х75"
    direct = {"facade": "Южный", "block": name, "rect": (-330, -255, 3300, 4775)}
    edge = {"facade": "Западный", "block": name, "rect": (93178, 93268, 3300, 4775)}
    built, dropped = mod.place_mullions([], [direct, edge][::(-1 if reverse else 1)], [], [])
    assert len(built) == len(dropped) == 1
    assert dropped[0]["counterpart_index"] == 0
    assert dropped[0]["counterpart_block"] == built[0]["block"]
    assert dropped[0]["reason"].startswith("edge-on view: verified")


def test_unhosted_interior_member_does_not_get_edge_alias():
    mod = _parts()
    built, dropped = mod.place_mullions([], [{"facade": "Южный", "block": "импост 200х75",
                                             "rect": (1000, 1075, 3300, 4775)}], [], [])
    assert not built
    assert len(dropped) == 1
    assert "no corner placement" in dropped[0]["reason"]
    assert "counterpart_index" not in dropped[0]


def test_exported_six_corner_surface_witnesses():
    rep = _load("corner-readback-r1-v002.json")
    assert rep["passed"] is True  # only this scoped surface witness, not delivery acceptance
    assert {r["source_block_id"] for r in rep["members"]} == {
        "1856177", "1857706", "1858064", "1856176", "1858448", "1858062"}
    assert all(r["sample_count"] == 9 and r["max_distance_m"] < .004 for r in rep["members"])


def test_profile_of_unknown_is_an_error():
    mod = _parts()
    assert mod.profile_of("Прямоугольный импост - 200х75 мм") == (0.075, 0.200)
    with pytest.raises(SystemExit, match="unknown mullion profile"):
        mod.profile_of("Импост 60х60")


def test_output_equal_to_input_exits_4(tmp_path):
    mod = _parts()
    plan = tmp_path / "plan.json"
    plan.write_text("{}", encoding="utf-8")
    l01, l03 = tmp_path / "L01.dxf", tmp_path / "L03.dxf"
    assert mod.main([str(plan), str(l01), str(l03), str(plan)]) == 4
    assert plan.read_text(encoding="utf-8") == "{}"


def test_stair_window_without_lines_fails_closed(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    mod = _parts()
    doc = ezdxf.new()
    doc.modelspace().add_line((0, 0), (1000, 0), dxfattribs={"layer": "S-STRS-____-OTLN"})
    p = tmp_path / "empty.dxf"
    doc.saveas(p)
    with pytest.raises(SystemExit, match="no S-STRS"):
        mod.stair_boxes(p)
