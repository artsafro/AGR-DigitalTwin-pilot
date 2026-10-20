"""Gate-1 summary of the Vatutino Ground (jobs/VATUTINO-SITE/ground_parts.py, issue #295). Synthetic geometry."""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import pytest

pytest.importorskip("shapely")

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("ground_parts", ROOT / "jobs" / "VATUTINO-SITE" / "ground_parts.py")
gp = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(gp)


def _sq(x0, y0, x1, y1, hole=None):
    rings = [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]
    if hole:
        hx0, hy0, hx1, hy1 = hole
        rings.append([[hx0, hy0], [hx0, hy1], [hx1, hy1], [hx1, hy0], [hx0, hy0]])
    return {"type": "Polygon", "coordinates": rings}


def _pt(x, y, z, ref, inside=True):
    return {"x": x, "y": y, "z": z, "ref": ref, "inside": inside, "layer": "H", "container": None}


def _data(elevations=None):
    return {
        "project": "synthetic",
        "units": "m",
        "boundary": _sq(0, 0, 100, 100),
        "boundary_handle": "B1",
        "base_covering": "tile",
        "coverings": {
            "tile": {"label": "t", "layers": ["T"], "area_m2": 5000.0, "sources": ["a"], "geometry": _sq(0, 0, 50, 100)},
            "lawn": {"label": "l", "layers": ["L"], "area_m2": 1500.0, "sources": ["b"],
                     "geometry": _sq(50, 0, 90, 50, hole=(60, 10, 70, 20))},
            "deck": {"label": "d", "layers": ["D"], "area_m2": 0.0, "sources": [], "geometry": None},
        },
        "planting": [],
        "maf": [],
        "elevations": elevations if elevations is not None else [_pt(0, 0, 1, "e1"), _pt(100, 0, 2, "e2"), _pt(0, 100, 3, "e3")],
        "findings": [
            {"code": "self_intersecting_contour", "layer": "L", "handle": "h1", "detail": "loop 0: invalid loop: Self-intersection[55.5 5.5]", "area": None, "ref": "h1"},
            {"code": "self_intersecting_contour", "layer": "T", "handle": "h2", "detail": "Self-intersection[-500 5]", "area": None, "ref": "h2"},
            {"code": "overlapping_coverings", "layer": "tile / lawn", "handle": None, "detail": "", "area": 0.5, "ref": None},
        ],
    }


def test_summary_areas_uncovered_and_findings():
    s = gp.summarize(_data())
    assert s["boundary"]["area_m2"] == 10000.0
    assert s["coverings"]["lawn"]["holes"] == 1
    assert s["coverings"]["deck"]["parts"] == 0
    assert s["covered_union_m2"] == pytest.approx(5000 + 2000 - 100)
    assert s["uncovered_m2"] == pytest.approx(10000 - 6900)
    assert s["covering_ranking"][0] == "tile"
    sides = {(r["layer"], r["side"]): r["count"] for r in s["self_intersecting_by_side"]}
    assert sides == {("L", "in_bbox"): 1, ("T", "outside_bbox"): 1}
    assert s["overlaps"] == [{"pair": "tile / lawn", "area_m2": 0.5}]


def test_contradictory_and_duplicate_z_are_listed():
    pts = [_pt(0, 0, 1, "a"), _pt(0, 0, 1, "b"), _pt(5, 5, 1, "c"), _pt(5, 5, 2, "d"), _pt(9, 1, 0, "e"),
           _pt(500, 500, 9, "out", inside=False)]
    e = gp.elevation_stats(pts)
    assert e["inside"] == 5 and e["outside"] == 1
    assert len(e["duplicates_same_z"]) == 1 and e["duplicates_same_z"][0]["refs"] == ["a", "b"]
    assert len(e["contradictory_z"]) == 1 and e["contradictory_z"][0]["z"] == [1.0, 2.0]
    assert e["collinear"] is False


def test_collinear_points_are_flagged():
    assert gp.elevation_stats([_pt(i, 2 * i, i, str(i)) for i in range(6)])["collinear"] is True
    assert gp.elevation_stats([])["collinear"] is True


@pytest.mark.parametrize(
    ("area", "limit"),
    [(500, 300_000), (500.01, 705_000), (1000, 705_000), (2500, 1_125_000), (5000, 1_650_000), (7500, 1_950_000),
     (10000, 2_625_000), (15000, 3_150_000), (15000.01, 4_500_000), (25854.04, 4_500_000)],
)
def test_gnd06_table_including_thresholds(area, limit):
    assert gp.gnd06_limit(area) == limit


@pytest.mark.parametrize("bad", [0.0, -1.0, math.nan, math.inf])
def test_gnd06_fails_closed(bad):
    with pytest.raises(ValueError):
        gp.gnd06_limit(bad)


def test_out_path_equal_to_input_is_refused(tmp_path):
    src = tmp_path / "in.json"
    src.write_text(json.dumps(_data()), encoding="utf-8")
    before = src.read_bytes()
    with pytest.raises(SystemExit) as exc:
        gp.main([f"x={src}", "--out", str(src)])
    assert exc.value.code != 0
    assert src.read_bytes() == before


def test_cli_writes_json(tmp_path):
    src = tmp_path / "in.json"
    src.write_text(json.dumps(_data()), encoding="utf-8")
    out = tmp_path / "out.json"
    assert gp.main([f"syn={src}", "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["syn"]["base_covering"] == "tile"
