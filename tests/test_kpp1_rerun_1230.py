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


# --- #1246: a corner post seen edge-on in two perpendicular views is ONE measured member ---------------
_INV = {"Южный": lambda u: u * 1000, "Северный": lambda u: 70955 - u * 1000,
        "Западный": lambda u: 92848 - u * 1000, "Восточный": lambda u: 102956 + u * 1000}
_POST = "Прямоугольный импост - 200х75 мм"


def _corner_item(mod, facade, lo, hi, za, zb, block=_POST):
    """An L01 insert whose measured along-facade extent is lo..hi in the OBJECT frame (m)."""
    along = 0 if mod.R9.FACADES[facade]["axis"] == "y" else 1
    x0, x1 = sorted((_INV[facade](lo - mod.R9.SHIFT[along]), _INV[facade](hi - mod.R9.SHIFT[along])))
    return {"facade": facade, "block": block, "rect": (x0, x1, za * 1000, zb * 1000)}


def _vol_overlap(a, b):
    return all(min(a["max"][k], b["max"][k]) - max(a["min"][k], b["min"][k]) > 0.001 for k in range(3))


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("corner, facade, measured, xy", [
    ("SW", "Южный", (-15.075, -14.985), ((-15.075, -5.775), (-14.985, -5.685))),
    ("NW", "Северный", (-15.0753, -14.9853), ((-15.0753, 5.9746), (-14.9853, 6.0646))),
])
def test_corner_post_seen_in_two_views_is_one_measured_member(corner, facade, measured, xy, reverse):
    mod = _parts()
    west = (-5.775, -5.685) if corner == "SW" else (5.9746, 6.0646)
    items = [_corner_item(mod, facade, *measured, 4.85, 6.65, block=f"{_POST}-A-О_АР_Ф_{facade}"),
             _corner_item(mod, "Западный", *west, 4.85, 6.65, block=f"{_POST}-B-О_АР_Ф_Западный")]
    built, dropped = mod.place_mullions([], items[::(-1 if reverse else 1)], [], [])
    assert dropped == []
    assert len(built) == 1, built            # not a cross of two guessed 210 mm boxes
    m = built[0]
    assert m["min"] == pytest.approx([xy[0][0], xy[0][1], 4.85])
    assert m["max"] == pytest.approx([xy[1][0], xy[1][1], 6.65])
    assert m["placement"].startswith("corner member: seen in two perpendicular views")
    assert sorted(v["facade"] for v in m["views"]) == sorted([facade, "Западный"])
    assert sorted(v["block"] for v in m["views"]) == sorted(i["block"] for i in items)


def test_corner_seen_in_one_view_keeps_profile_depth():
    mod = _parts()
    items = [_corner_item(mod, "Южный", -15.075, -14.985, 1.2, 2.7),          # Южный only (#1246 example)
             _corner_item(mod, "Западный", -5.775, -5.685, 4.85, 6.65)]       # West only, other z
    built, dropped = mod.place_mullions([], items, [], [])
    assert dropped == [] and len(built) == 2
    south, west = sorted(built, key=lambda b: b["min"][2])
    assert south["placement"] == west["placement"] == "corner member: no built perpendicular counterpart"
    assert south["max"][1] - south["min"][1] == pytest.approx(0.21)          # declared 200 mm + 10 mm embed
    assert west["max"][0] - west["min"][0] == pytest.approx(0.21)
    assert not _vol_overlap(south, west)


def test_partial_z_overlap_keeps_only_one_view_remainder_guessed():
    mod = _parts()
    items = [_corner_item(mod, "Южный", -15.075, -14.985, 4.775, 6.65),
             _corner_item(mod, "Западный", -5.775, -5.685, 4.85, 6.65)]
    built, dropped = mod.place_mullions([], items, [], [])
    assert dropped == []
    pair = [b for b in built if "views" in b]
    rest = [b for b in built if "views" not in b]
    assert len(pair) == len(rest) == 1
    assert pair[0]["min"][2] == pytest.approx(4.85) and pair[0]["max"][2] == pytest.approx(6.65)
    assert rest[0]["facade"] == "Южный"
    assert (rest[0]["min"][2], rest[0]["max"][2]) == pytest.approx((4.775, 4.85))
    assert rest[0]["rect_m"][2:] == pytest.approx([4.775, 4.85])


@pytest.mark.parametrize("overlap_mm, paired", [(0.1, False), (1.0, False), (1.1, True), (75.0, True)])
def test_corner_pair_z_overlap_threshold(overlap_mm, paired):
    mod = _parts()
    top = 6.65
    items = [_corner_item(mod, "Южный", -15.075, -14.985, 4.85, top),
             _corner_item(mod, "Западный", -5.775, -5.685, top - overlap_mm / 1000, top + 0.075)]
    built, dropped = mod.place_mullions([], items, [], [])
    assert dropped == []
    assert any("views" in b for b in built) is paired


def test_v002_corner_replay_builds_no_perpendicular_cross():
    """Real data: the 27 corner projections of parts-schedule-r1-v002.json, fed back into place_mullions."""
    mod = _parts()
    corner = [b for b in _load("parts-schedule-r1-v002.json")["mullions"] if b["placement"].startswith("corner")]
    assert len(corner) == 27
    items = []
    for b in corner:
        ua, ub, za, zb = b["rect_m"]
        x0, x1 = sorted((_INV[b["facade"]](ua), _INV[b["facade"]](ub)))
        items.append({"facade": b["facade"], "block": b["block"], "rect": (x0, x1, za * 1000, zb * 1000)})
    built, dropped = mod.place_mullions([], items, [], [])
    assert dropped == []
    pairs = [b for b in built if "views" in b]
    assert len(pairs) == 7                     # SW 3 + NW 4 perpendicular pairs; east corners are one-view
    seen = {v["block"] for b in pairs for v in b["views"]} | {b["block"] for b in built if "views" not in b}
    assert seen == {b["block"] for b in corner}
    crosses = [(a["block"], b["block"]) for i, a in enumerate(built) for b in built[i + 1:] if _vol_overlap(a, b)]
    assert crosses == []
    sw = [b for b in pairs if b["min"][2] == pytest.approx(4.85) and b["min"][1] < 0]
    assert len(sw) == 1
    assert sw[0]["min"][:2] == pytest.approx([-15.075, -5.7754]) and sw[0]["max"][:2] == pytest.approx([-14.985, -5.6854])


@pytest.mark.parametrize("seed", range(200))
def test_corner_pair_probe_never_builds_overlapping_fins(seed):
    """Generated: random z segmentations of one SW post in both views -> no two built boxes overlap > 1 mm,
    every merged member is the measured 2D intersection, every view z (> 1 mm) is covered by a member."""
    import random
    rnd = random.Random(seed)
    mod = _parts()
    xs, ys = (-15.075, -14.985), (-5.775, -5.685)

    def segs():
        cuts = sorted({rnd.randint(0, 9000) for _ in range(rnd.randint(1, 5))} | {0, 9000})
        return [(a / 1000, b / 1000) for a, b in zip(cuts, cuts[1:]) if b > a and rnd.random() < 0.7]
    south, west = segs(), segs()
    items = ([_corner_item(mod, "Южный", *xs, a, b, block=f"{_POST}-S{a}") for a, b in south]
             + [_corner_item(mod, "Западный", *ys, a, b, block=f"{_POST}-W{a}") for a, b in west])
    rnd.shuffle(items)
    built, dropped = mod.place_mullions([], items, [], [])
    assert dropped == []
    assert not [(a, b) for i, a in enumerate(built) for b in built[i + 1:] if _vol_overlap(a, b)]
    for b in built:
        if "views" in b:
            assert b["min"][:2] == pytest.approx([xs[0], ys[0]]) and b["max"][:2] == pytest.approx([xs[1], ys[1]])
    for z0, z1 in south + west:
        for k in range(int(z0 * 1000) + 1, int(z1 * 1000), 50):
            z = k / 1000
            assert any(b["min"][2] <= z <= b["max"][2] for b in built), (z, south, west)


def test_v002_corner_replay_reports_only_real_slivers():
    """Every unbuilt z remainder of a paired view is listed, and is > 0 and <= 1 mm (no empty entries)."""
    mod = _parts()
    corner = [b for b in _load("parts-schedule-r1-v002.json")["mullions"] if b["placement"].startswith("corner")]
    items = []
    for b in corner:
        ua, ub, za, zb = b["rect_m"]
        x0, x1 = sorted((_INV[b["facade"]](ua), _INV[b["facade"]](ub)))
        items.append({"facade": b["facade"], "block": b["block"], "rect": (x0, x1, za * 1000, zb * 1000)})
    built, _ = mod.place_mullions([], items, [], [])
    slivers = [s for b in built for v in b.get("views", []) for s in v.get("unbuilt_slivers_z_m", [])]
    assert slivers                                     # 6.65..6.6501 and 4.8499..4.85 at the SW post
    assert all(0 < (b - a) * 1000 <= 1.0 for a, b in slivers), slivers


def test_r1_v003_schedule_and_exported_readback_have_no_corner_cross():
    """Real L01 rerun after #1246: 7 reported pairs, no box overlap > 1 mm, exported VPM has no fins."""
    sched = _load("parts-schedule-r1-v003.json")
    built = sched["mullions"]
    assert sched["mullion_inserts"] == 244 and sched["mullions_dropped"] == []
    assert built[:217] == _load("parts-schedule-v001.json")["mullions"]
    pairs = [b for b in built if "views" in b]
    assert len(pairs) == 7 and len(built) == 240
    corner = built[217:]
    assert not [(a["block"], b["block"]) for i, a in enumerate(corner) for b in corner[i + 1:] if _vol_overlap(a, b)]
    rb = _load("corner-pairs-readback-r1-v003.json")
    assert rb["passed"] is True  # only this scoped witness, not delivery acceptance
    assert all(v for k, v in rb["v002"]["inside_object"].items() if "fin" in k)       # control: v002 had fins
    assert not any(v for k, v in rb["v003"]["inside_object"].items() if "fin" in k)
    for name in ("SM_Kpp_1.zip.r1-v003.validate.json", "0000_Kpp_1_01.r1-v003.validate.json"):
        rep = _load(name)
        assert rep["passed"] is False
        topo = [f for f in _findings(rep, "V004") if f["name"] == "topology defects"]
        assert topo and all(f["status"] == "pass" for f in topo)
        clear = [f for f in _findings(rep, "V004") if f["name"] == "co-directional clearance"]
        assert clear and all(": 0 < 5 mm" in f["observed"] for f in clear)
    assert _load("build-report-r1-v003.json")["mullions_built"] == 240
