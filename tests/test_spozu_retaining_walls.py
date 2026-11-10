"""SPOZU reader: retaining-wall spot-height pairs reported as an informational Finding.

Source: docs/research/vatutino-ground-80deg-step-source.md (PR #1165), "Proposed next tasks" item 1.
Synthetic ezdxf documents built in the test, no user files.
"""

from __future__ import annotations

import ezdxf
import pytest

from adapters.cad import spozu
from adapters.cad.spozu import SpozuConfig, read_spozu_dxf
from tests.test_adapters_cad_spozu import base_config, clean_doc, rect


def marks_doc(marks, insunits: int = 6, k: float = 1.0):
    """Boundary -50..50 square; each mark (x, y, z) is a TEXT on SPOT at (x, y) * k reading z."""
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = insunits
    msp = doc.modelspace()
    msp.add_lwpolyline(rect(-50, -50, 50, 50, k), close=True, dxfattribs={"layer": "BOUNDARY"})
    handles = [msp.add_text(f"{z:.2f}", dxfattribs={"layer": "SPOT", "insert": (x * k, y * k, 0)}).dxf.handle
               for x, y, z in marks]
    return doc, handles


def walls(res):
    return [f for f in res.findings if f.code == "retaining_wall_marks"]


def read(doc):
    return read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))


def test_close_pair_with_big_drop_is_one_finding():
    doc, (h_top, h_bot) = marks_doc([(0, 0, 145.5), (0, 0.6, 141.8)])
    res = read(doc)
    w = walls(res)
    assert len(w) == 1
    f = w[0]
    assert (f.layer, f.handle, f.ref) == ("SPOT", h_top, h_top)
    assert h_top in f.detail and h_bot in f.detail
    assert "drop 3.70" in f.detail and "145.50" in f.detail and "141.80" in f.detail
    assert [x.code for x in res.findings] == ["retaining_wall_marks"]


def test_bottom_mark_first_still_reports_top_handle():
    doc, (h_bot, h_top) = marks_doc([(0, 0.6, 141.8), (0, 0, 145.5)])
    w = walls(read(doc))
    assert len(w) == 1 and w[0].handle == h_top


@pytest.mark.parametrize("marks", [
    [(0, 0, 145.5), (0, 0.6, 144.7)],   # dZ 0.8
    [(0, 0, 145.5), (0, 1.5, 141.8)],   # planar 1.5 m
    [(0, 0, 145.5), (0.05, 0.6, 141.8)],  # dX 0.05 m
    [(0, 0, 145.5), (0, 0.6, 144.5)],   # dZ exactly 1.0 (strict >)
    [(0, 0, 145.5), (0.0101, 0.6, 141.8)],  # dX just over 0.01
], ids=["dz_small", "planar_far", "dx_off", "dz_at_threshold", "dx_just_over"])
def test_non_pairs_give_no_finding(marks):
    doc, _ = marks_doc(marks)
    res = read(doc)
    assert walls(res) == [] and res.findings == []
    assert len(res.elevations) == len(marks)


def test_thresholds_inclusive_at_limits():
    doc, _ = marks_doc([(0, 0, 145.5), (0.01, 0.0, 141.8), (10, 0, 145.5), (10, 1.0, 141.8)])
    assert len(walls(read(doc))) == 2


def test_three_marks_one_pair_no_duplicates():
    doc, (h1, h2, _) = marks_doc([(0, 0, 145.5), (0, 0.6, 141.8), (30, 30, 150.0)])
    w = walls(read(doc))
    assert len(w) == 1 and w[0].handle == h1 and h2 in w[0].detail


def test_millimetre_drawing_uses_metres_for_xy():
    # 5 mm apart in X (0.005 m) and 600 mm in Y -> a pair; text Z is already metres
    doc, _ = marks_doc([(0, 0, 145.5), (5, 600, 141.8)], insunits=4, k=1.0)
    doc.modelspace().query("LWPOLYLINE")[0].set_points(rect(-50000, -50000, 50000, 50000))
    assert len(walls(read(doc))) == 1


def test_elevations_unchanged_by_detection():
    marks = [(0, 0, 145.5), (0, 0.6, 141.8), (30, 30, 150.0)]
    doc, handles = marks_doc(marks)
    res = read(doc)
    assert [(e.x, e.y, e.z, e.handle) for e in res.elevations] == [
        (x, y, pytest.approx(z), h) for (x, y, z), h in zip(marks, handles)]


def test_existing_clean_fixture_findings_unchanged():
    assert read_spozu_dxf(clean_doc(), SpozuConfig.from_dict(base_config())).findings == []


def test_thresholds_are_module_constants():
    assert spozu.RETAINING_WALL_DX_TOL_M == 0.01
    assert spozu.RETAINING_WALL_MAX_PLANAR_M == 1.0
    assert spozu.RETAINING_WALL_MIN_DROP_M == 1.0
