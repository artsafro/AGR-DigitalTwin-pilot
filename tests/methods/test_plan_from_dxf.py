"""Regression for the kpp1 drawing plan reader (#967). Fails before plan_from_dxf.py exists.

Pattern: wall-from-contour
"""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import ezdxf
import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "plan_from_dxf", ROOT / "tools" / "methods" / "body" / "plan_from_dxf.py")
pf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pf)


def _rect(msp, layer, x0, y0, x1, y1):
    msp.add_line((x0, y0), (x1, y0), dxfattribs={"layer": layer})
    msp.add_line((x1, y0), (x1, y1), dxfattribs={"layer": layer})
    msp.add_line((x1, y1), (x0, y1), dxfattribs={"layer": layer})
    msp.add_line((x0, y1), (x0, y0), dxfattribs={"layer": layer})


def _doc():
    doc = ezdxf.new("R2018")
    doc.layers.add("WALL")
    doc.layers.add("NOTE")
    return doc


def _square(side_mm, layer="WALL"):
    doc = _doc()
    _rect(doc.modelspace(), layer, 0, 0, side_mm, side_mm)
    return doc


def test_closed_rectangle_is_one_contour_in_metres():
    doc = _square(2000)
    out = pf.extract_plan(doc, {"WALL": "wall"}, z0=0.0, z1=3.0)
    assert out["provisional"] is False and out["synthetic_drawing"] is False
    assert out["bands"][0]["z0"] == 0.0 and out["bands"][0]["z1"] == 3.0
    poly = out["bands"][0]["polygons"][0]["exterior"]
    xs, ys = zip(*poly)
    assert max(xs) - min(xs) == pytest.approx(2.0, abs=1e-3)
    assert max(ys) - min(ys) == pytest.approx(2.0, abs=1e-3)
    assert len(out["entities"]) == 4
    assert sum(1 for e in out["entities"] if e["status"] == "used") == 4


def test_piece_of_area_exactly_half_a_square_metre_is_dropped():
    side = math.sqrt(pf.MIN_PIECE_M2) * 1000.0  # area == 0.5 m2 exactly
    doc = _doc()
    _rect(doc.modelspace(), "WALL", 0, 0, side, side)
    _rect(doc.modelspace(), "WALL", 5000, 0, 7000, 2000)  # 4 m2, kept
    out = pf.extract_plan(doc, {"WALL": "wall"}, z0=0.0, z1=1.0)
    assert len(out["bands"][0]["polygons"]) == 1
    dropped = [e for e in out["entities"] if e["status"] == "dropped"]
    assert dropped and all("0.5" in e["reason"] for e in dropped)


def test_gap_exactly_two_gap_close_stays_two_pieces_and_a_narrower_gap_joins():
    doc = _doc()
    _rect(doc.modelspace(), "WALL", 0, 0, 2000, 2000)
    gap = 2 * pf.GAP_CLOSE_M * 1000.0  # exactly the close distance, in mm
    _rect(doc.modelspace(), "WALL", 2000 + gap, 0, 4000 + gap, 2000)
    exact = pf.extract_plan(doc, {"WALL": "wall"}, z0=0.0, z1=1.0)
    assert len(exact["bands"][0]["polygons"]) == 2
    doc2 = _doc()
    _rect(doc2.modelspace(), "WALL", 0, 0, 2000, 2000)
    _rect(doc2.modelspace(), "WALL", 2000 + 1000, 0, 4000 + 1000, 2000)  # 1.0 m < 1.5 m
    joined = pf.extract_plan(doc2, {"WALL": "wall"}, z0=0.0, z1=1.0)
    assert len(joined["bands"][0]["polygons"]) == 1


def test_unmapped_layer_is_an_error_naming_it_and_cli_writes_nothing(tmp_path):
    doc = _square(2000)
    doc.modelspace().add_line((0, 0), (10, 0), dxfattribs={"layer": "EXTRA"})
    with pytest.raises(ValueError, match="EXTRA"):
        pf.extract_plan(doc, {"WALL": "wall"}, z0=0.0, z1=1.0)
    dxf = tmp_path / "in.dxf"
    doc.saveas(dxf)
    before = dxf.read_bytes()
    out, report = tmp_path / "out.json", tmp_path / "out.report.json"
    code = pf.main(["extract", str(dxf), str(out), str(report), "--map", "WALL=wall",
                    "--z0", "0", "--z1", "1"])
    assert code == 2 and not out.exists() and not report.exists() and dxf.read_bytes() == before


def test_non_finite_coordinate_is_an_error():
    doc = _square(2000)
    line = doc.modelspace().add_line((0, 0), (1, 0), dxfattribs={"layer": "WALL"})
    line.dxf.start = (math.nan, 0, 0)
    with pytest.raises(ValueError, match="non-finite"):
        pf.extract_plan(doc, {"WALL": "wall"}, z0=0.0, z1=1.0)


def test_empty_model_and_unsupported_wall_entity_are_errors():
    doc = _doc()
    with pytest.raises(ValueError, match="empty"):
        pf.extract_plan(doc, {"WALL": "wall"}, z0=0.0, z1=1.0)
    doc.modelspace().add_circle((0, 0), 1, dxfattribs={"layer": "WALL"})
    with pytest.raises(ValueError, match="CIRCLE"):
        pf.extract_plan(doc, {"WALL": "wall"}, z0=0.0, z1=1.0)


def test_missing_z1_is_provisional_and_the_cli_does_not_succeed(tmp_path):
    doc = _square(2000)
    out = pf.extract_plan(doc, {"WALL": "wall"}, z0=0.0, z1=None)
    assert out["provisional"] is True and "z1" not in out["bands"][0]
    dxf = tmp_path / "in.dxf"
    doc.saveas(dxf)
    contours, report = tmp_path / "c.json", tmp_path / "c.report.json"
    code = pf.main(["extract", str(dxf), str(contours), str(report), "--map", "WALL=wall", "--z0", "0"])
    assert code == 2
    import json
    body = json.loads(contours.read_text(encoding="utf-8"))
    assert body["provisional"] is True


def test_opening_without_a_declared_insert_base_is_not_a_cutter():
    doc = _square(4000)
    doc.layers.add("DOOR")
    doc.blocks.new("Дверь 1000x2100 отм_ 0_000")
    doc.modelspace().add_blockref(
        "Дверь 1000x2100 отм_ 0_000", (2000, 0), dxfattribs={"layer": "DOOR", "rotation": 0})
    out = pf.extract_plan(doc, {"WALL": "wall", "DOOR": "symbol"}, z0=0.0, z1=3.0)
    assert out["openings"] == []
    door = [e for e in out["entities"] if e["layer"] == "DOOR"]
    assert len(door) == 1 and "base point" in door[0]["reason"]


def test_centre_insert_with_a_parsed_name_cuts_the_wall_depth():
    doc = ezdxf.new("R2018")
    doc.layers.add("WALL")
    doc.layers.add("DOOR")
    msp = doc.modelspace()
    # 4 m x 4 m room, plus a second face 200 mm below y=0 (wall thickness).
    _rect(msp, "WALL", 0, 0, 4000, 4000)
    msp.add_line((0, -200), (4000, -200), dxfattribs={"layer": "WALL"})
    doc.blocks.new("ADSK_Дверь - 1000x2100 на отм_ 0_000")
    msp.add_blockref("ADSK_Дверь - 1000x2100 на отм_ 0_000", (2000, -100),
                     dxfattribs={"layer": "DOOR", "rotation": 0})
    out = pf.extract_plan(doc, {"WALL": "wall", "DOOR": "symbol"}, z0=0.0, z1=3.0,
                          opening_insert="centre")
    assert len(out["openings"]) == 1
    box = out["openings"][0]
    assert box["min"][2] == pytest.approx(0.0) and box["max"][2] == pytest.approx(2.1)
    assert box["max"][0] - box["min"][0] == pytest.approx(1.0, abs=1e-3)
    assert box["max"][1] - box["min"][1] == pytest.approx(0.2, abs=1e-3)


def test_a_face_exactly_one_metre_from_the_insert_is_not_a_host_wall():
    doc = ezdxf.new("R2018")
    doc.layers.add("WALL")
    doc.layers.add("DOOR")
    msp = doc.modelspace()
    _rect(msp, "WALL", 0, 0, 4000, 4000)
    # faces at exactly ±1.0 m from the insert; the limit is strict
    msp.add_line((0, -1100), (4000, -1100), dxfattribs={"layer": "WALL"})
    msp.add_line((0, 900), (4000, 900), dxfattribs={"layer": "WALL"})
    doc.blocks.new("Дверь 1000x2100 отм_ 0_000")
    msp.add_blockref("Дверь 1000x2100 отм_ 0_000", (2000, -100),
                     dxfattribs={"layer": "DOOR", "rotation": 0})
    out = pf.extract_plan(doc, {"WALL": "wall", "DOOR": "symbol"}, z0=0.0, z1=3.0,
                          opening_insert="centre")
    door = next(e for e in out["entities"] if e["layer"] == "DOOR")
    assert out["openings"] == [] and "wall depth" in door["reason"]


def test_unknown_opening_insert_mode_is_an_error_naming_it():
    doc = _square(2000)
    with pytest.raises(ValueError, match="hinge"):
        pf.extract_plan(doc, {"WALL": "wall"}, z0=0.0, z1=1.0, opening_insert="hinge")


def test_every_entity_is_used_or_dropped_brute_force():
    doc = _doc()
    _rect(doc.modelspace(), "WALL", 0, 0, 2000, 2000)
    msp = doc.modelspace()
    for i in range(40):
        msp.add_line((i, 10_000), (i + 1, 10_000), dxfattribs={"layer": "NOTE"})
    out = pf.extract_plan(doc, {"WALL": "wall", "NOTE": "drop:note"}, z0=0.0, z1=1.0)
    handles = [e["handle"] for e in out["entities"]]
    assert len(handles) == len(set(handles)) == 44
    assert sum(1 for e in out["entities"] if e["status"] == "dropped" and e["reason"] == "note") == 40


def test_cli_refuses_an_output_that_is_the_input_and_writes_nothing(tmp_path):
    doc = _square(2000)
    dxf = tmp_path / "in.dxf"
    doc.saveas(dxf)
    before = dxf.read_bytes()
    report = tmp_path / "in.dxf.report.json"
    code = pf.main(["extract", str(dxf), str(dxf), str(report), "--map", "WALL=wall",
                    "--z0", "0", "--z1", "1"])
    assert code == 4 and dxf.read_bytes() == before and not report.exists()
    same = tmp_path / "one.json"
    code = pf.main(["extract", str(dxf), str(same), str(same), "--map", "WALL=wall",
                    "--z0", "0", "--z1", "1"])
    assert code == 4 and not same.exists() and dxf.read_bytes() == before


def test_literal_dxf_unicode_escape_decodes():
    assert pf.decode_dxf_text(r"\U+041F\U+043B\U+0430\U+043D") == "План"


def test_storey_levels_copy_one_plan_into_one_band_per_storey():
    """One plan plus the object.json elevations is runnable: two bands, same pieces (#967)."""
    doc = _square(2000)
    out = pf.extract_plan(doc, {"WALL": "wall"}, z0=0.0, levels_m=[0.0, 3.9, 7.909])
    assert out["provisional"] is False
    assert out["levels_m"] == [0.0, 3.9, 7.909]
    assert [(b["z0"], b["z1"]) for b in out["bands"]] == [(0.0, 3.9), (3.9, 7.909)]
    assert out["bands"][0]["polygons"] == out["bands"][1]["polygons"]
    assert out["openings"] == []


def test_bad_level_lists_are_errors_naming_the_value_brute_force():
    """Generated bad level lists. Each must name the problem; a good list still builds every band."""
    import random
    doc = _square(2000)
    bad = [
        [],
        [0.0],
        [1.0, 0.0],
        [0.0, 0.0],
        [0.0, math.nan],
        [0.0, math.inf],
        [math.nan, 1.0],
        [0.0, 1.0, 1.0],
        [True, 2.0],
        [0.0, False],
    ]
    for levels in bad:
        with pytest.raises(ValueError, match="levels_m"):
            pf.extract_plan(doc, {"WALL": "wall"}, z0=0.0, levels_m=levels)
    rng = random.Random(967)
    for _ in range(24):
        levels = [0.0]
        for _step in range(rng.randint(1, 5)):
            levels.append(levels[-1] + rng.uniform(0.05, 4.0))
        out = pf.extract_plan(doc, {"WALL": "wall"}, z0=0.0, levels_m=levels)
        assert out["provisional"] is False and len(out["bands"]) == len(levels) - 1
        assert all(b["polygons"] == out["bands"][0]["polygons"] for b in out["bands"])
        assert out["levels_m"] == pytest.approx(levels)


def test_kpp1_wall_map_keeps_interior_walls_out_and_names_every_sheet_layer():
    import json
    roles = pf.KPP1_LAYER_ROLES
    assert roles["A-WALL-____-MCUT"] == "wall"
    assert roles["A-WALL-____-PATT"] == "hatch"
    assert all(roles[name].startswith("drop:") and roles[name] != "drop:"
               for name in roles if name.startswith("I-WALL"))
    census = json.loads((ROOT / "docs/methods/building-body/kpp1-drawing/sheet-census.json"
                         ).read_text(encoding="utf-8"))
    sheet = next(s for s in census["sheets"] if s["sheet"] == "L03")
    assert set(sheet["model_layers"]) == set(roles)
    for name, spec in roles.items():
        assert spec in ("wall", "symbol", "hatch") or (spec.startswith("drop:") and spec[5:].strip()), name


def test_published_kpp1_contour_is_the_runnable_drawing_input():
    import json
    path = ROOT / "docs/methods/building-body/kpp1-drawing/plan-contours.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    levels = [row["elev_m"] for row in json.loads(
        (ROOT / "jobs/KPP1/object.json").read_text(encoding="utf-8"))["levels"]]
    assert data["provisional"] is False and data["synthetic_drawing"] is False
    assert data["units"] == "m" and data["source_units"] == "mm"
    assert data["origin_mm"] == [25884.5, 0.0]
    assert data["frame_shift_m"] == [-14.655, -5.355]
    assert data["levels_m"] == levels
    assert [(b["z0"], b["z1"]) for b in data["bands"]] == list(zip(levels, levels[1:]))
    assert data["bands"][0]["polygons"] == data["bands"][1]["polygons"]
    assert len(data["bands"][0]["polygons"]) == 1
    assert data["params"]["contour_source"] == "hatch"
    cov = data["coverage"]
    assert cov["status"] == "pass" and cov["hatch_area_m2"] == pytest.approx(33.07, abs=0.01)
    assert cov["covered_share"] > 0.9 and cov["bbox_delta_m"] < 0.1
    assert data["openings"] == []
    assert data["params"]["gap_close_m"] == 0.75
    assert data["params"]["opening_insert"] is None
    assert "not proven" in data["opening_decision"]


# --- review round 1 (#989): wall hatch as the boundary source + fail-closed coverage ---

L03_DXF = Path("C:/x/methods/building-body/kpp1/readback/ascii/L03/L03.dxf")


def _hatch(msp, layer, x0, y0, x1, y1):
    h = msp.add_hatch(dxfattribs={"layer": layer})
    h.paths.add_polyline_path([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], is_closed=True)
    return h


def _ring_doc(door_mm=1000):
    """A 6 x 4 m exterior wall, 300 mm thick, hatched, with a door gap in the south wall.

    Wall lines are only the two faces of each wall run (open pairs), the hatch is the cut mass.
    """
    doc = _doc()
    doc.layers.add("PATT")
    msp = doc.modelspace()
    t = 300
    left = (6000 - door_mm) / 2
    for x0, y0, x1, y1 in ((0, 0, left, t), (left + door_mm, 0, 6000, t), (0, 4000 - t, 6000, 4000),
                           (0, t, t, 4000 - t), (6000 - t, t, 6000, 4000 - t)):
        _hatch(msp, "PATT", x0, y0, x1, y1)
    return doc


def _open_pairs_doc():
    """Witness: eight short open wall pairs (0.6 x 0.3 m, 1.6 m apart) and one closed 1.0 x 0.6 m block.

    Each pair fills to 0.18 m2 and is dropped (<= 0.5 m2), so most of the hatched mass is lost.
    """
    doc = _doc()
    doc.layers.add("PATT")
    msp = doc.modelspace()
    for i in range(8):
        x0 = i * 2200
        msp.add_line((x0, 0), (x0 + 600, 0), dxfattribs={"layer": "WALL"})
        msp.add_line((x0, 300), (x0 + 600, 300), dxfattribs={"layer": "WALL"})
        _hatch(msp, "PATT", x0, 0, x0 + 600, 300)
    _rect(msp, "WALL", 30000, 0, 31000, 600)
    _hatch(msp, "PATT", 30000, 0, 31000, 600)
    return doc


def test_hatch_source_closes_the_hatched_ring_into_one_footprint():
    out = pf.extract_plan(_ring_doc(), {"WALL": "wall", "NOTE": "drop:note", "PATT": "hatch"},
                          z0=0.0, z1=3.0, contour_source="hatch")
    polys = out["bands"][0]["polygons"]
    assert len(polys) == 1
    xs, ys = zip(*polys[0]["exterior"])
    assert max(xs) - min(xs) == pytest.approx(6.0, abs=0.1)
    assert max(ys) - min(ys) == pytest.approx(4.0, abs=0.1)
    cov = out["coverage"]
    assert cov["status"] == "pass" and cov["hatch_area_m2"] == pytest.approx(5.34, abs=1e-3)
    assert cov["covered_share"] > pf.COVERAGE_MIN_SHARE and cov["bbox_delta_m"] < pf.COVERAGE_BBOX_M
    assert out["params"]["contour_source"] == "hatch"
    assert {e["status"] for e in out["entities"]} == {"used"} and len(out["entities"]) == 5


def test_open_wall_pairs_mostly_dropped_fail_the_coverage_check_witness():
    doc = _open_pairs_doc()
    roles = {"WALL": "wall", "NOTE": "drop:note", "PATT": "hatch"}
    for source in ("lines", "hatch"):
        with pytest.raises(ValueError, match="coverage"):
            pf.extract_plan(doc, roles, z0=0.0, z1=3.0, contour_source=source)


def test_coverage_exactly_at_the_threshold_fails():
    from shapely.geometry import box
    hatch = box(0, 0, 10, 1)
    at_share = pf.coverage_check([box(0, 0, 9, 1)], hatch)
    assert at_share["covered_share"] == 0.9 and at_share["status"] == "fail"
    at_bbox = pf.coverage_check([box(0, 0, 10, 1.1)], box(0, 0, 10, 1))
    assert at_bbox["bbox_delta_m"] == 0.1 and at_bbox["status"] == "fail"
    assert pf.coverage_check([box(0, 0, 10, 1)], hatch)["status"] == "pass"
    for bad in ([], [box(0, 0, 0, 0)]):
        assert pf.coverage_check(bad, hatch)["status"] == "fail"
    with pytest.raises(ValueError, match="hatch"):
        pf.coverage_check([box(0, 0, 1, 1)], box(0, 0, 0, 0))


def test_contour_source_errors_name_the_problem():
    roles = {"WALL": "wall", "NOTE": "drop:note"}
    with pytest.raises(ValueError, match="contour_source"):
        pf.extract_plan(_square(2000), roles, z0=0.0, z1=3.0, contour_source="mesh")
    with pytest.raises(ValueError, match="hatch layer"):
        pf.extract_plan(_square(2000), roles, z0=0.0, z1=3.0, contour_source="hatch")
    doc = _square(2000)
    doc.layers.add("PATT")
    doc.modelspace().add_line((0, 0), (1, 1), dxfattribs={"layer": "PATT"})
    with pytest.raises(ValueError, match="unsupported LINE on a hatch layer"):
        pf.extract_plan(doc, {**roles, "PATT": "hatch"}, z0=0.0, z1=3.0)
    doc = _square(2000)
    doc.layers.add("PATT")
    h = _hatch(doc.modelspace(), "PATT", 0, 0, 0, 0)
    with pytest.raises(ValueError, match=f"handle {h.dxf.handle}"):
        pf.extract_plan(doc, {**roles, "PATT": "hatch"}, z0=0.0, z1=3.0)


def test_lines_without_a_hatch_reference_record_coverage_not_measured():
    out = pf.extract_plan(_square(2000), {"WALL": "wall", "NOTE": "drop:note"}, z0=0.0, z1=3.0)
    assert out["coverage"]["status"] == "not measured"
    assert out["coverage"]["reason"].startswith("no hatch layer")


@pytest.mark.skipif(not L03_DXF.is_file(), reason=f"L03 readback not on this PC: {L03_DXF}")
def test_kpp1_l03_lines_lose_the_wall_and_the_hatch_keeps_it():
    doc = ezdxf.readfile(L03_DXF)
    kw = dict(z0=0.0, levels_m=None, z1=3.9, origin_mm=pf.KPP1_ORIGIN_MM, frame_shift_m=pf.KPP1_FRAME_SHIFT_M)
    with pytest.raises(ValueError, match="coverage"):
        pf.extract_plan(doc, pf.KPP1_LAYER_ROLES, contour_source="lines", **kw)
    out = pf.extract_plan(doc, pf.KPP1_LAYER_ROLES, contour_source="hatch", **kw)
    cov = out["coverage"]
    assert cov["hatch_area_m2"] == pytest.approx(33.07, abs=0.01)
    assert cov["status"] == "pass" and cov["covered_share"] > 0.9 and cov["bbox_delta_m"] < 0.1
    assert len(out["bands"][0]["polygons"]) == 1


def test_wall_line_status_uses_its_true_midpoint_and_a_zero_length_line_is_dropped():
    doc = _doc()
    doc.layers.add("PATT")
    msp = doc.modelspace()
    _hatch(msp, "PATT", 0, 0, 2000, 2000)
    # 0.5 m from the start is inside the 2 x 2 m hatch, the midpoint (2.1 m) is outside
    long_line = msp.add_line((100, 1000), (4100, 1000), dxfattribs={"layer": "WALL"})
    inside = msp.add_line((100, 500), (1900, 500), dxfattribs={"layer": "WALL"})
    dot = msp.add_line((500, 500), (500, 500), dxfattribs={"layer": "WALL"})
    out = pf.extract_plan(doc, {"WALL": "wall", "NOTE": "drop:note", "PATT": "hatch"},
                          z0=0.0, z1=3.0, contour_source="hatch")
    status = {e["handle"]: (e["status"], e["reason"]) for e in out["entities"]}
    assert status[long_line.dxf.handle] == ("dropped", "wall line outside the kept hatch contour")
    assert status[inside.dxf.handle] == ("used", "wall")
    assert status[dot.dxf.handle] == ("dropped", "zero-length wall entity")


# --- #1004: the footprint may not go beyond what the closed hatch outlines account for ---

_L_OUT = [(0, 0), (10, 0), (10, 5), (5, 5), (5, 10), (0, 10)]
_L_IN = [(0.3, 0.3), (9.7, 0.3), (9.7, 4.7), (4.7, 4.7), (4.7, 9.7), (0.3, 9.7)]


def _l_ring():
    from shapely.geometry import Polygon
    return Polygon(_L_OUT, [_L_IN])


def test_over_closed_notch_fails_and_the_plain_l_passes_witness():
    from shapely.geometry import Polygon, box
    hatch = _l_ring()
    over = pf.coverage_check([box(0, 0, 10, 10)], hatch)
    assert over["covered_share"] == 1.0 and over["bbox_delta_m"] == 0.0  # the old gate alone passed this
    assert over["status"] == "fail"
    assert over["unaccounted_m2"] == pytest.approx(25.0, abs=0.2)
    assert over["accounted_area_m2"] == pytest.approx(75.0, abs=0.2)
    assert over["max_unaccounted_m2"] == pf.MAX_UNACCOUNTED_M2
    x0, y0, x1, y1 = over["unaccounted_bbox_m"]
    assert (x0, y0, x1, y1) == pytest.approx((5.0, 5.0, 10.0, 10.0), abs=0.6)
    plain = pf.coverage_check([Polygon(_L_OUT)], hatch)
    assert plain["status"] == "pass" and plain["unaccounted_m2"] == 0.0


def _l_doc(outline):
    """Wall lines trace ``outline`` (metres); the hatch is the 0.3 m L-shaped wall ring."""
    doc = _doc()
    doc.layers.add("PATT")
    msp = doc.modelspace()
    pts = [(x * 1000, y * 1000) for x, y in outline]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        msp.add_line(a, b, dxfattribs={"layer": "WALL"})
    h = msp.add_hatch(dxfattribs={"layer": "PATT"})
    h.paths.add_polyline_path([(x * 1000, y * 1000) for x, y in _L_OUT], is_closed=True)
    h.paths.add_polyline_path([(x * 1000, y * 1000) for x, y in _L_IN], is_closed=True)
    return doc


def test_lines_closing_over_the_notch_are_refused_by_extract():
    roles = {"WALL": "wall", "NOTE": "drop:note", "PATT": "hatch"}
    with pytest.raises(ValueError, match="unaccounted"):
        pf.extract_plan(_l_doc([(0, 0), (10, 0), (10, 10), (0, 10)]), roles, z0=0.0, z1=3.0)
    out = pf.extract_plan(_l_doc(_L_OUT), roles, z0=0.0, z1=3.0)
    assert out["coverage"]["status"] == "pass" and out["coverage"]["unaccounted_m2"] == 0.0
    hatch_out = pf.extract_plan(_l_doc(_L_OUT), roles, z0=0.0, z1=3.0, contour_source="hatch")
    assert hatch_out["coverage"]["status"] == "pass"


def test_ring_with_a_door_gap_is_accounted_by_the_bridge_strip():
    # the 1.0 m door gap is bridged at gap_close 0.75, so the room behind it counts as enclosed
    from shapely.geometry import box
    from shapely.ops import unary_union
    hatch = unary_union([box(0, 0, 2.5, 0.3), box(3.5, 0, 6, 0.3), box(0, 3.7, 6, 4),
                         box(0, 0.3, 0.3, 3.7), box(5.7, 0.3, 6, 3.7)])
    cov = pf.coverage_check([box(0, 0, 6, 4)], hatch)
    # the flat door sill is outside the closing by a chamfer sliver (quad_segs=2), well under the limit
    assert cov["status"] == "pass" and cov["unaccounted_m2"] < 0.2
    closed, _ = pf._fill_pieces([hatch], 0.75)  # the hatch-source footprint itself is fully accounted
    assert pf.coverage_check(closed, hatch)["unaccounted_m2"] == 0.0
    # a 2.0 m opening is wider than 2 * gap_close: the room is not enclosed, the footprint is refused
    wide = unary_union([box(0, 0, 2, 0.3), box(4, 0, 6, 0.3), box(0, 3.7, 6, 4),
                        box(0, 0.3, 0.3, 3.7), box(5.7, 0.3, 6, 3.7)])
    assert pf.coverage_check([box(0, 0, 6, 4)], wide)["status"] == "fail"


def test_unaccounted_area_exactly_at_the_limit_fails_and_bad_gap_close_is_an_error():
    from shapely.geometry import Polygon, box
    from shapely.ops import unary_union
    hatch = _l_ring()
    lim = pf.MAX_UNACCOUNTED_M2
    at = pf.coverage_check([unary_union([Polygon(_L_OUT), box(10 - lim, 9, 10, 10)])], hatch)
    assert at["unaccounted_m2"] == pytest.approx(lim, abs=1e-9) and at["status"] == "fail"
    under = pf.coverage_check([unary_union([Polygon(_L_OUT), box(10 - 0.9 * lim, 9, 10, 10)])], hatch)
    assert under["status"] == "pass"
    for bad in (0.0, -1.0, float("nan"), float("inf"), True, "0.75", None):
        with pytest.raises(ValueError, match="gap_close_m"):
            pf.coverage_check([Polygon(_L_OUT)], hatch, gap_close_m=bad)


def test_unaccounted_gate_brute_force_against_the_notch_area():
    """Generated: a footprint that adds an extra box in the notch fails iff the box is >= the limit."""
    import random
    from shapely.geometry import Polygon, box
    from shapely.ops import unary_union
    rng = random.Random(1004)
    hatch, base = _l_ring(), Polygon(_L_OUT)
    checked = 0
    for _ in range(200):
        w, h = rng.uniform(0.05, 4.0), rng.uniform(0.05, 4.0)
        extra = box(10 - w, 10 - h, 10, 10)  # the notch corner, away from the filleted reflex corner
        cov = pf.coverage_check([unary_union([base, extra])], hatch)
        assert cov["unaccounted_m2"] == pytest.approx(w * h, abs=1e-6)
        assert (cov["status"] == "fail") == (w * h >= pf.MAX_UNACCOUNTED_M2), (w, h, cov)
        checked += 1
    assert checked == 200


# --- #1004 round 1: the reference radius is fixed, not the run's gap_close_m ---

def _open_ring():
    """10x10 m wall ring, 0.3 m thick, with a 2.5 m opening in the top wall (wider than 2 * 0.75)."""
    from shapely.geometry import box
    return box(0, 0, 10, 10).difference(box(0.3, 0.3, 9.7, 9.7)).difference(box(3.75, 9.0, 6.25, 10.0))


def _open_ring_doc():
    doc = _doc()
    doc.layers.add("PATT")
    msp = doc.modelspace()
    pts = [(x * 1000, y * 1000) for x, y in list(_open_ring().exterior.coords)[:-1]]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        msp.add_line(a, b, dxfattribs={"layer": "WALL"})
    h = msp.add_hatch(dxfattribs={"layer": "PATT"})
    h.paths.add_polyline_path(pts, is_closed=True)
    return doc


def test_hatch_source_wide_gap_close_is_measured_at_the_fixed_reference_witness():
    import re
    roles = {"WALL": "wall", "NOTE": "drop:note", "PATT": "hatch"}
    assert pf.COVERAGE_REF_GAP_CLOSE_M == 0.75
    # at gap_close 1.5 the 2.5 m opening is bridged and the room filled: ~87 m2 the 0.75 closing does not account for
    with pytest.raises(ValueError, match="unaccounted") as err:
        pf.extract_plan(_open_ring_doc(), roles, z0=0.0, z1=3.0, gap_close_m=1.5, contour_source="hatch")
    m = re.search(r"([0-9.]+) m2 unaccounted", str(err.value))
    assert m and float(m.group(1)) == pytest.approx(87.0, abs=1.5)
    kept, _ = pf._fill_pieces([_open_ring()], 1.5)
    cov = pf.coverage_check(kept, _open_ring(), gap_close_m=1.5)
    assert cov["status"] == "fail" and cov["unaccounted_m2"] == pytest.approx(87.0, abs=1.5)
    assert cov["ref_gap_close_m"] == 0.75 and cov["gap_close_m"] == 1.5
    ok = pf.extract_plan(_open_ring_doc(), roles, z0=0.0, z1=3.0, gap_close_m=0.75, contour_source="hatch")
    assert ok["coverage"]["status"] == "pass" and ok["coverage"]["unaccounted_m2"] == 0.0


def test_gap_close_sweep_in_hatch_mode_fails_once_it_bridges_beyond_the_reference():
    """Generated: hatch-source footprints over gap_close 0.2..2.5 m. At or under the 0.75 m reference the
    footprint is fully accounted; once the 2.5 m opening is bridged (2 * g > 2.5) the room fails as named
    area; in between the unaccounted area (corner fillets beyond the reference) never decreases."""
    hatch = _open_ring()
    checked, prev = 0, 0.0
    for g in [round(0.05 * k, 2) for k in range(4, 51)]:
        kept, _ = pf._fill_pieces([hatch], g)
        cov = pf.coverage_check(kept, hatch, gap_close_m=g)
        u = cov["unaccounted_m2"]
        if g <= pf.COVERAGE_REF_GAP_CLOSE_M:
            assert cov["status"] == "pass" and u == pytest.approx(0.0, abs=1e-6), (g, cov)
        if 2 * g > 2.5 + 1e-3:
            assert cov["status"] == "fail" and u > 80.0, (g, cov)
        assert u >= prev - 1e-6, (g, u, prev)
        prev = u
        checked += 1
    assert checked == 47


# --- #1203 (KPP1 cold run F3): method follows the contour source, the output records its full invocation ---

def _hatched_square_dxf(tmp_path):
    doc = _square(4000)
    doc.layers.add("PATT")
    _hatch(doc.modelspace(), "PATT", 0, 0, 4000, 4000)
    dxf = tmp_path / "sq.dxf"
    doc.saveas(dxf)
    return dxf


def test_method_names_the_contour_source_for_lines_and_hatch():
    lines = pf.extract_plan(_square(4000), {"WALL": "wall"}, z0=0.0, z1=3.0, contour_source="lines")
    assert lines["method"] == pf.METHODS["lines"] and "wall lines" in lines["method"]
    assert "hatch" not in lines["method"]
    hatch = pf.extract_plan(_ring_doc(), {"WALL": "wall", "NOTE": "drop:note", "PATT": "hatch"},
                            z0=0.0, z1=3.0, contour_source="hatch")
    assert hatch["method"] == pf.METHODS["hatch"]
    # the string the accepted KPP1 file carries (it was hand-edited before #1203)
    committed = json.loads((ROOT / "docs/methods/building-body/kpp1-drawing/plan-contours.json"
                            ).read_text(encoding="utf-8"))
    assert hatch["method"] == committed["method"]
    assert set(pf.METHODS) == set(pf.CONTOUR_SOURCES)


def _extract_argv(dxf, out, rep, *opts):
    return ["extract", str(dxf), str(out), str(rep), *opts]


def test_cli_records_the_full_invocation_and_reruns_from_the_file_alone(tmp_path):
    import hashlib
    dxf = _hatched_square_dxf(tmp_path)
    opts = ["--map", "WALL=wall", "--map", "PATT=hatch", "--z0", "0", "--levels", "0,3,6",
            "--contour-source", "hatch", "--origin-mm", "1000,500", "--frame-shift-m=-2.5,1.25"]
    out, rep = tmp_path / "out.json", tmp_path / "rep.json"
    argv = _extract_argv(dxf, out, rep, *opts)
    assert pf.main(list(argv)) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    inv = data["invocation"]
    assert inv["argv"] == argv
    assert inv["map"] == ["WALL=wall", "PATT=hatch"]
    assert inv["origin_mm"] == [1000.0, 500.0] and inv["frame_shift_m"] == [-2.5, 1.25]
    assert inv["contour_source"] == "hatch" and inv["levels_m"] == [0.0, 3.0, 6.0] and inv["z0"] == 0.0
    tool = ROOT / "tools/methods/body/plan_from_dxf.py"
    assert inv["tool"] == "tools/methods/body/plan_from_dxf.py"
    assert inv["tool_sha256"] == hashlib.sha256(tool.read_bytes()).hexdigest()
    assert "git_sha" in inv and (inv["git_sha"] is None) == ("git_error" in inv)
    if inv["git_sha"] is not None:
        assert len(inv["git_sha"]) == 40
    assert inv["dxf"] == {"path": str(dxf), "sha256": hashlib.sha256(dxf.read_bytes()).hexdigest()}
    assert inv["command"].startswith("uv run python tools/methods/body/plan_from_dxf.py extract ")
    assert "--frame-shift-m=-2.5,1.25" in inv["command"] or "--frame-shift-m -2.5,1.25" in inv["command"]
    # re-run from the file alone: the canonical options, nothing else
    out2, rep2 = tmp_path / "out2.json", tmp_path / "rep2.json"
    assert pf.main(_extract_argv(dxf, out2, rep2, *inv["options_argv"])) == 0
    again = json.loads(out2.read_text(encoding="utf-8"))
    for key in ("bands", "coverage", "levels_m", "origin_mm", "frame_shift_m", "params", "method", "openings"):
        assert again[key] == data[key], key
    assert again["invocation"]["options_argv"] == inv["options_argv"]


def test_map_file_equals_map_entries_and_is_recorded_expanded(tmp_path):
    import hashlib
    dxf = _hatched_square_dxf(tmp_path)
    mf = tmp_path / "map.txt"
    mf.write_bytes(b"WALL=wall\r\n\r\nPATT=hatch\r\n")
    base = ["--z0", "0", "--z1", "3", "--contour-source", "hatch"]
    a, ar = tmp_path / "a.json", tmp_path / "ar.json"
    b, br = tmp_path / "b.json", tmp_path / "br.json"
    assert pf.main(_extract_argv(dxf, a, ar, "--map", "WALL=wall", "--map", "PATT=hatch", *base)) == 0
    assert pf.main(_extract_argv(dxf, b, br, "--map-file", str(mf), *base)) == 0
    da, db = (json.loads(p.read_text(encoding="utf-8")) for p in (a, b))
    assert da["bands"] == db["bands"]
    inv = db["invocation"]
    assert inv["map"] == ["WALL=wall", "PATT=hatch"]
    assert inv["map_file"] == {"path": str(mf), "sha256": hashlib.sha256(mf.read_bytes()).hexdigest()}
    assert "--map-file" not in inv["options_argv"]
    assert inv["options_argv"].count("--map") == 2


def test_duplicate_or_malformed_map_entries_are_errors_naming_them_and_write_nothing(tmp_path, capsys):
    dxf = _hatched_square_dxf(tmp_path)
    cases = [
        (["--map", "WALL=wall", "--map", "WALL=drop:x", "--map", "PATT=hatch"], "WALL"),
        (["--map", "WALL=wall", "--map", "WALL=wall", "--map", "PATT=hatch"], "WALL"),
        (["--map", "WALL=wall", "--map", "PATTERN", "--map", "PATT=hatch"], "PATTERN"),
    ]
    mf = tmp_path / "dup.txt"
    mf.write_text("WALL=wall\nPATT=hatch\n", encoding="utf-8")
    cases.append((["--map-file", str(mf), "--map", "PATT=hatch"], "PATT"))
    empty = tmp_path / "empty.txt"
    empty.write_text("\n\n", encoding="utf-8")
    cases.append((["--map-file", str(empty)], "empty"))
    cases.append((["--map-file", str(tmp_path / "missing.txt")], "missing.txt"))
    for i, (opts, named) in enumerate(cases):
        out, rep = tmp_path / f"o{i}.json", tmp_path / f"r{i}.json"
        code = pf.main(_extract_argv(dxf, out, rep, *opts, "--z0", "0", "--z1", "3"))
        err = capsys.readouterr().err
        assert code == 2 and named in err, (opts, err)
        assert not out.exists() and not rep.exists()


def test_map_file_that_is_an_output_is_refused_and_untouched(tmp_path):
    dxf = _hatched_square_dxf(tmp_path)
    mf = tmp_path / "map.txt"
    mf.write_text("WALL=wall\nPATT=hatch\n", encoding="utf-8")
    before = mf.read_bytes()
    rep = tmp_path / "rep.json"
    code = pf.main(_extract_argv(dxf, mf, rep, "--map-file", str(mf), "--z0", "0", "--z1", "3"))
    assert code == 4 and mf.read_bytes() == before and not rep.exists()


def test_invocation_options_reproduce_brute_force(tmp_path):
    """Probe: for generated origin/shift/source/levels, options_argv alone reproduces the output."""
    import random
    rng = random.Random(1203)
    dxf = _hatched_square_dxf(tmp_path)
    checked = 0
    for i in range(12):
        ox, oy = rng.uniform(-5e4, 5e4), rng.uniform(-5e4, 5e4)
        sx, sy = rng.uniform(-50, 50), rng.uniform(-50, 50)
        src = rng.choice(["lines", "hatch"])
        opts = ["--map", "WALL=wall", "--map", "PATT=hatch", "--z0", "0", "--levels", "0,3.9,7.909",
                "--contour-source", src, f"--origin-mm={ox!r},{oy!r}", f"--frame-shift-m={sx!r},{sy!r}"]
        o1, r1, o2, r2 = (tmp_path / f"{n}{i}.json" for n in ("o", "r", "p", "q"))
        assert pf.main(_extract_argv(dxf, o1, r1, *opts)) == 0
        d1 = json.loads(o1.read_text(encoding="utf-8"))
        assert d1["method"] == pf.METHODS[src]
        assert pf.main(_extract_argv(dxf, o2, r2, *d1["invocation"]["options_argv"])) == 0
        d2 = json.loads(o2.read_text(encoding="utf-8"))
        assert {k: v for k, v in d1.items() if k != "invocation"} == \
            {k: v for k, v in d2.items() if k != "invocation"}
        checked += 1
    assert checked == 12


def test_dxf_changing_while_it_is_read_is_an_error_and_writes_nothing(tmp_path, monkeypatch, capsys):
    import ezdxf as real
    dxf = _hatched_square_dxf(tmp_path)
    orig = real.readfile

    def readfile_then_touch(path, *a, **k):
        doc = orig(path, *a, **k)
        with open(path, "ab") as f:
            f.write(b"\n")
        return doc

    monkeypatch.setattr(real, "readfile", readfile_then_touch)
    out, rep = tmp_path / "o.json", tmp_path / "r.json"
    code = pf.main(_extract_argv(dxf, out, rep, "--map", "WALL=wall", "--map", "PATT=hatch", "--z0", "0", "--z1", "3"))
    assert code == 2 and "changed while it was read" in capsys.readouterr().err
    assert not out.exists() and not rep.exists()
