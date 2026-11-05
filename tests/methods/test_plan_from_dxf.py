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
