"""Fail-closed regression cases for the six adversarial DXF classes.

Source: docs/experiments/bim-autocad-agr.md, "Verdict and follow-up" — preserve the
clean fixture and the six adversarial classes (bulge, HATCH with a hole, nested
INSERT, missing xref, SPLINE, open contour) as regression cases for
``dt_ai.cad.plan_dxf``. Bulge is covered in tests/test_plan_dxf_transforms.py; it is
repeated here so the census of all classes lives in one place.

Each case starts from a clean B02 plan written by ``write_plan_dxf`` and is edited
with ezdxf. Synthetic geometry only (benchmark spec proxy, not a real object).
"""

from __future__ import annotations

import json
from pathlib import Path

import ezdxf
import pytest

from dt_ai.cad.plan_dxf import (
    build_plan_features,
    census,
    compare_plan,
    read_plan_dxf,
    spec_from_mapping,
    write_plan_dxf,
)

BENCH = Path(__file__).resolve().parents[1] / "benchmark"
B02 = "bench-b02-corner-niche"
MISSING_XREF = "C:/missing/agr-e2-xref.dwg"


@pytest.fixture
def clean(tmp_path):
    spec = spec_from_mapping(json.loads((BENCH / B02 / "spec.json").read_text(encoding="utf-8")))
    expected = build_plan_features([spec])
    path = tmp_path / "b02-clean.dxf"
    write_plan_dxf(expected, path)
    return expected, path


def _first_contour(doc):
    return next(entity for entity in doc.modelspace() if entity.dxftype() == "LWPOLYLINE")


def _edit(path: Path, variant: str) -> Path:
    doc = ezdxf.readfile(path)
    model = doc.modelspace()
    contour = _first_contour(doc)
    if variant == "bulge":
        x, y, start, end, _bulge = contour[0]
        contour[0] = (x, y, start, end, 0.5)
    elif variant == "hatch":
        hatch = model.add_hatch(dxfattribs={"layer": "HOLE"})
        outer = [(point[0], point[1]) for point in contour.get_points("xy")]
        hatch.paths.add_polyline_path(outer, is_closed=True, flags=1)
        xs, ys = [p[0] for p in outer], [p[1] for p in outer]
        cx, cy = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
        span = min(max(xs) - min(xs), max(ys) - min(ys)) * 0.1
        hole = [(cx - span, cy - span), (cx + span, cy - span), (cx + span, cy + span), (cx - span, cy + span)]
        hatch.paths.add_polyline_path(hole, is_closed=True, flags=0)
    elif variant == "spline":
        model.add_spline([(0, 0, 0), (100, 50, 0), (200, 0, 0)], dxfattribs={"layer": "SPLINE"})
    elif variant == "nested_insert":
        inner = doc.blocks.new("INNER_CONTOUR")
        inner.add_lwpolyline(
            [(p[0], p[1]) for p in contour.get_points("xy")], close=True,
            dxfattribs={"layer": contour.dxf.layer, "elevation": float(contour.dxf.elevation)})
        outer = doc.blocks.new("OUTER_REF")
        outer.add_blockref("INNER_CONTOUR", (0, 0), dxfattribs={"rotation": 15.0, "xscale": 2.0, "yscale": 0.5})
        model.add_blockref("OUTER_REF", (0, 0), dxfattribs={"rotation": 5.0})
        # The contour now lives only inside the nested, non-uniformly scaled block.
        model.delete_entity(contour)
    elif variant == "missing_xref":
        block = doc.blocks.new("MISSING_XREF")
        block.block.dxf.flags = int(block.block.dxf.flags) | 4
        block.block.dxf.xref_path = MISSING_XREF
        model.add_blockref("MISSING_XREF", (0, 0))
    elif variant == "open_contour":
        contour.closed = False
    else:
        raise ValueError(variant)
    edited = path.with_name(f"b02-{variant}.dxf")
    doc.saveas(edited)
    return edited


def _compare(expected, path):
    actual, info = read_plan_dxf(path)
    return actual, compare_plan(expected, actual, info["insunits"])


def test_clean_b02_accepted_with_zero_deviation(clean):
    expected, path = clean
    actual, report = _compare(expected, path)
    assert report["ok"] is True and report["errors"] == []
    assert report["max_deviation_mm"] == 0.0
    assert census(actual) == census(expected)


CASES = [
    ("bulge", "unsupported curve"),
    ("hatch", "unsupported"),
    ("spline", "unsupported"),
    ("nested_insert", "unsupported"),
    ("missing_xref", "unsupported"),
    ("open_contour", "wrong closed flag"),
]


@pytest.mark.parametrize(("variant", "reason"), CASES, ids=[case[0] for case in CASES])
def test_adversarial_class_rejected(clean, variant, reason):
    expected, path = clean
    _actual, report = _compare(expected, _edit(path, variant))
    assert report["ok"] is False
    assert reason in report["errors"]


def test_hatch_with_hole_is_not_read_as_geometry(clean):
    expected, path = clean
    actual, report = _compare(expected, _edit(path, "hatch"))
    hatch = [item for item in actual if item["kind"] == "HATCH"]
    assert hatch == [{"layer": "HOLE", "kind": "HATCH", "unsupported": True}]
    assert "extra" in report["errors"]


def test_spline_is_not_approximated(clean):
    expected, path = clean
    actual, _report = _compare(expected, _edit(path, "spline"))
    spline = [item for item in actual if item["kind"] == "SPLINE"]
    assert spline == [{"layer": "SPLINE", "kind": "SPLINE", "unsupported": True}]


def test_nested_insert_is_not_expanded(clean):
    expected, path = clean
    actual, report = _compare(expected, _edit(path, "nested_insert"))
    assert census(actual)["INSERT"] == 1
    assert census(actual)["LWPOLYLINE"] == census(expected)["LWPOLYLINE"] - 1
    assert "missing" in report["errors"]


def test_missing_xref_is_not_opened(clean):
    expected, path = clean
    assert not Path(MISSING_XREF).exists()
    actual, _report = _compare(expected, _edit(path, "missing_xref"))
    inserts = [item for item in actual if item["kind"] == "INSERT"]
    assert inserts == [{"layer": "0", "kind": "INSERT", "unsupported": True}]


def test_open_contour_flags(clean):
    expected, path = clean
    actual, report = _compare(expected, _edit(path, "open_contour"))
    contour = next(item for item in actual if item["kind"] == "LWPOLYLINE")
    assert contour["closed"] is False and contour["raw_flag"] == 0
    assert "wrong raw flag" in report["errors"]
