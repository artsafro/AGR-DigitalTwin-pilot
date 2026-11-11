"""Gate 1 approval reference (#1205, KPP1 cold-run F5). All data is SYNTHETIC.

`Approval.ref` is optional and names the proof of the user's answer: an https issue/comment URL,
a kanban card id (`t_<hex>`) or a decision id (`D<n>`). The pydantic model and the committed
`schemas/PartsList.schema.json` must accept and reject the same instances.
"""
import copy
import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from dt_ai.core.provenance import Approval
from dt_ai.parts.model import PartsList

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "schemas" / "PartsList.schema.json").read_text(encoding="utf-8"))
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)
LISTING = {
    "synthetic": True, "object_id": "SYN1", "source_tier": "B", "status": "confirmed",
    "sources": [{"kind": "synthetic", "reference": "fixture"}],
    "triangle_budget": {"npm": 1000, "vpm": 2000},
    "parts": [{"id": "wall_a", "part_class": "wall", "sources": [{"kind": "object", "reference": "Wall_A"}],
               "operation": "keep", "triangle_budget": {"npm": 100, "vpm": 200}}],
    "joints": [],
    "gate1": {"actor": "synthetic fixture", "date": "2026-11-11", "scope": "synthetic_fixture", "note": "gate 1"},
}
GOOD_REFS = [
    "https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1205#issuecomment-123",
    "https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1205",
    "t_81cfd638", "D111", "D1",
]
BAD_REFS = ["", " ", "D0", "D", "d111", "D12a", "t_", "t_XYZ", "t_81cfd638 ", " D111",
            "http://example.com/x", "https://", "https://a b", "ftp://x", "#1205", "1205", "see issue",
            "D111\n", "https://x\n", 1205, "null"]


def instance(ref=...):
    data = copy.deepcopy(LISTING)
    if ref is not ...:
        data["gate1"]["ref"] = ref
    return data


def model_ok(data):
    try:
        PartsList.model_validate(data)
        return True
    except ValidationError:
        return False


def schema_ok(data):
    return not list(VALIDATOR.iter_errors(data))


def test_partslist_without_ref_validates():
    data = instance()
    assert model_ok(data) and schema_ok(data)
    assert PartsList.model_validate(data).gate1.ref is None


@pytest.mark.parametrize("ref", GOOD_REFS)
def test_partslist_with_ref_validates(ref):
    data = instance(ref)
    assert model_ok(data) and schema_ok(data)
    assert PartsList.model_validate(data).gate1.ref == ref


def test_explicit_null_ref_is_absent():
    data = instance(None)
    assert model_ok(data) and schema_ok(data)


@pytest.mark.parametrize("ref", BAD_REFS)
def test_bad_ref_rejected_by_model_and_schema(ref):
    data = instance(ref)
    assert not model_ok(data)
    assert not schema_ok(data)


def test_ref_roundtrips_through_json():
    item = Approval(actor="synthetic fixture", date="2026-11-11", scope="project", note="gate 1", ref="D111")
    assert Approval.model_validate_json(item.model_dump_json()) == item


def test_schema_has_optional_ref():
    approval = SCHEMA["$defs"]["Approval"]
    assert "ref" in approval["properties"]
    assert "ref" not in approval["required"]


# Job parts files that validate on origin/main 42c3bdb9 (elv_full_parts_v002/v003 already fail there on
# SourceRef.kind "pdf" and extra keys, F6 territory); gate1 is set or null; none may break because of gate1.
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


def test_no_job_file_fails_on_gate1():
    files = [p for p in (ROOT / "jobs").rglob("*.json") if '"gate1"' in p.read_text(encoding="utf-8")]
    assert len(files) >= len(VALID_ON_MAIN)
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "parts" not in data:
            continue
        try:
            PartsList.model_validate(data)
        except ValidationError as exc:
            assert not [e for e in exc.errors() if e["loc"][:1] == ("gate1",)], path


def test_schemas_in_sync_with_models():
    result = subprocess.run([sys.executable, "-m", "dt_ai.cli.main", "schemas", "--check"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_task_to_model_parts_row_names_gate1_channel():
    text = (ROOT / "docs/procedure/TASK_TO_MODEL.md").read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if line.startswith("| parts |"))
    for needle in ("Needs you", "issue comment", "waits: user", "gate1", "ref"):
        assert needle in row, needle
