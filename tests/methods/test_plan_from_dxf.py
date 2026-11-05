"""Regression for the kpp1 drawing plan reader (#967). Fails before plan_from_dxf.py exists.

Pattern: wall-from-contour
"""
from __future__ import annotations

import importlib.util
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
    assert cov["status"] == "pass" and cov["hatch_area_m2"] == pytest.approx(5.7, abs=1e-3)
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
