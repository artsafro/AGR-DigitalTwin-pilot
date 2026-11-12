"""SourceRef.kind `drawing` for DWG/DXF sources (#1206, KPP1 cold-run F6). All data is SYNTHETIC.

A `drawing` source names a .dwg/.dxf file, may carry an optional `sheet` (layout / sheet name) and
never a `page`; `pdf` still requires `page` and `sha256`; `sheet` belongs to `drawing` only. The pydantic
model and the committed `schemas/PartsList.schema.json` must accept and reject the same instances.
"""
import copy
import itertools
import json
import re
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from dt_ai.core.provenance import SourceRef
from dt_ai.parts.model import PartsList

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "schemas" / "PartsList.schema.json").read_text(encoding="utf-8"))
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)
SHA = "a" * 64
LISTING = {
    "synthetic": True, "object_id": "SYN1", "source_tier": "B", "status": "confirmed",
    "sources": [{"kind": "synthetic", "reference": "fixture"}],
    "triangle_budget": {"npm": 1000, "vpm": 2000},
    "parts": [{"id": "wall_a", "part_class": "wall", "sources": [{"kind": "object", "reference": "Wall_A"}],
               "operation": "keep", "triangle_budget": {"npm": 100, "vpm": 200}}],
    "joints": [],
}


def listing(source):
    data = copy.deepcopy(LISTING)
    data["sources"].append(source)
    return data


def model_ok(data):
    try:
        PartsList.model_validate(data)
        return True
    except ValidationError:
        return False


def schema_ok(data):
    return not list(VALIDATOR.iter_errors(data))


def both(source):
    data = listing(source)
    return model_ok(data), schema_ok(data)


GOOD_DRAWINGS = [
    {"kind": "drawing", "reference": "synthetic/plan.dwg"},
    {"kind": "drawing", "reference": "synthetic/plan.dwg", "sheet": "Layout1"},
    {"kind": "drawing", "reference": "synthetic/plan.DXF", "sheet": "Model", "sha256": SHA},
    {"kind": "drawing", "reference": "C:/synthetic/фасады_L01.dwg (DWG facades)", "sha256": SHA},
    {"kind": "drawing", "reference": "synthetic/plan.dwg", "sheet": "Лист 1", "region": [0, 0, 10, 10]},
    {"kind": "drawing", "reference": "synthetic/plan.dwg", "sheet": None},
]
BAD_DRAWINGS = [
    {"kind": "drawing", "reference": "synthetic/plan.dwg", "page": 1},
    {"kind": "drawing", "reference": "synthetic/plan.dwg", "page": 1, "sheet": "Layout1"},
    {"kind": "drawing", "reference": "synthetic/plan.dwg", "sheet": ""},
    {"kind": "drawing", "reference": "synthetic/plan.dwg", "sheet": " "},
    {"kind": "drawing", "reference": "synthetic/plan.dwg", "sheet": "\n"},
    {"kind": "drawing", "reference": "synthetic/plan.dwg", "sheet": 1},
    {"kind": "drawing", "reference": "synthetic/plan.pdf"},
    {"kind": "drawing", "reference": "synthetic/plan.dwgx"},
    {"kind": "drawing", "reference": "synthetic/plan_dwg"},
    {"kind": "drawing", "reference": "dwg"},
    {"kind": "drawing", "reference": ""},
    {"kind": "drawing"},
    {"kind": "dwg", "reference": "synthetic/plan.dwg"},
    {"kind": "Drawing", "reference": "synthetic/plan.dwg"},
    {"kind": "drawing", "reference": "synthetic/plan.dwg", "layout": "Layout1"},
]


@pytest.mark.parametrize("source", GOOD_DRAWINGS)
def test_drawing_source_validates_with_and_without_sheet(source):
    assert both(source) == (True, True)


@pytest.mark.parametrize("source", BAD_DRAWINGS)
def test_bad_drawing_source_rejected_by_model_and_schema(source):
    assert both(source) == (False, False)


@pytest.mark.parametrize("source", [
    {"kind": "pdf", "reference": "synthetic/a.pdf"},
    {"kind": "pdf", "reference": "synthetic/a.pdf", "sha256": SHA},
    {"kind": "pdf", "reference": "synthetic/a.pdf", "page": 1},
    {"kind": "pdf", "reference": "synthetic/a.pdf", "sha256": SHA, "sheet": "Layout1"},
    {"kind": "pdf", "reference": "synthetic/a.pdf", "page": 1, "sha256": SHA, "sheet": "Layout1"},
])
def test_pdf_without_page_or_with_sheet_still_fails(source):
    assert both(source) == (False, False)


def test_pdf_with_page_and_sha_validates():
    assert both({"kind": "pdf", "reference": "synthetic/a.pdf", "page": 3, "sha256": SHA}) == (True, True)


@pytest.mark.parametrize("kind", ["synthetic", "model", "user"])
def test_sheet_belongs_to_drawing_only(kind):
    assert both({"kind": kind, "reference": "synthetic/plan.dwg"}) == (True, True)
    assert both({"kind": kind, "reference": "synthetic/plan.dwg", "sheet": "Layout1"}) == (False, False)


def test_drawing_roundtrips_through_json():
    item = SourceRef(kind="drawing", reference="synthetic/plan.dwg", sheet="Layout1", sha256=SHA)
    assert SourceRef.model_validate_json(item.model_dump_json()) == item
    with pytest.raises(ValidationError):
        item.page = 1  # validate_assignment keeps the rule after construction


def expected(kind, ref, page, sha, sheet):
    if sheet is not None and (kind != "drawing" or not sheet.strip()):
        return False
    if kind == "pdf":
        return page is not None and sha is not None
    if kind == "drawing":
        return page is None and re.search(r"\.(dwg|dxf)(?![a-z0-9])", ref.lower()) is not None
    return True


def test_generated_grid_model_schema_and_rule_agree():
    kinds = ["synthetic", "pdf", "model", "user", "drawing"]
    refs = ["s/a.dwg", "s/a.DXF", "s/a.pdf", "s/a.dwgx", "s/a"]
    grid = list(itertools.product(kinds, refs, [None, 1], [None, SHA], [None, "Layout1", " "]))
    for kind, ref, page, sha, sheet in grid:
        source: dict[str, object] = {"kind": kind, "reference": ref}
        for key, value in (("page", page), ("sha256", sha), ("sheet", sheet)):
            if value is not None:
                source[key] = value
        want = expected(kind, ref, page, sha, sheet)
        assert both(source) == (want, want), source
    assert len(grid) == 300


def test_schema_has_drawing_kind_and_optional_sheet():
    ref = SCHEMA["$defs"]["SourceRef"]
    assert "drawing" in ref["properties"]["kind"]["enum"]
    assert "sheet" in ref["properties"] and "sheet" not in ref["required"]


VALID_ON_MAIN = [
    "jobs/COD-20207/parts.json",
    "jobs/elv-tc-vpm/parts/elv_full_parts_v001.json",
    "jobs/elv-tc-vpm/parts/pilot_IA_parts_v001.json",
    "jobs/elv-tc-vpm/parts/pilot_IA_parts_v002.json",
    "jobs/KPP1/cold-run-1172/parts-v001.json",
    "jobs/KPP1/rerun-1209/parts-v002.json",
]


@pytest.mark.parametrize("rel", VALID_ON_MAIN)
def test_existing_job_parts_files_still_validate(rel):
    data = json.loads((ROOT / rel).read_text(encoding="utf-8"))
    PartsList.model_validate(data)
    assert schema_ok(data), rel


def test_cold_run_receipt_not_rewritten():
    data = json.loads((ROOT / "jobs/KPP1/cold-run-1172/parts-v001.json").read_text(encoding="utf-8"))
    kinds = [s["kind"] for s in data["sources"]]
    assert "drawing" not in kinds
    assert sum(1 for s in data["sources"] if s["kind"] == "model" and ".dwg" in s["reference"]) == 3
