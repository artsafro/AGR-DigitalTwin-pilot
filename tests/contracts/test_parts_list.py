"""Parts list contract (`parts.json`, cloud card C1-C7 line, C2). All data is SYNTHETIC."""
import copy

import pytest
from pydantic import ValidationError

from dt_ai.parts.model import PartsList

PART = {
    "id": "wall_a", "part_class": "wall", "sources": [{"kind": "object", "reference": "Wall_A"}],
    "legend_item": "Plaster, RAL 9003", "operation": "keep", "triangle_budget": {"npm": 100, "vpm": 200},
}
RAIL = {
    "id": "rail_a", "part_class": "railing", "sources": [{"kind": "layer", "reference": "Railings"}],
    "operation": "primitive", "build_as": "box", "triangle_budget": {"npm": 50, "vpm": 400},
}
LISTING = {
    "synthetic": True, "object_id": "SYN1", "source_tier": "B",
    "sources": [{"kind": "synthetic", "reference": "fixture"}],
    "triangle_budget": {"npm": 1000, "vpm": 2000},
    "parts": [PART, RAIL],
    "joints": [{"parts": ["wall_a", "rail_a"], "decision": "embed", "reason": "welding cuts loops into the wall",
                "extra_edges": 24, "embed_depth_m": 0.015}],
}


def make(**changes):
    data = copy.deepcopy(LISTING)
    data.update(changes)
    return PartsList.model_validate(data)


def finish_listing():
    data = copy.deepcopy(LISTING)
    data["finish_sheets"] = [{"image": "sheet.jpg", "multi_building": True}]
    data["parts"][0]["finish_refs"] = [{"image": "sheet.jpg", "bbox": [10, 20, 100, 200],
                                       "crop": "crops/wall.png"}]
    return data


def test_finish_reference_roundtrip():
    import json
    from pathlib import Path
    import jsonschema

    data = finish_listing()
    result = PartsList.model_validate(data)
    assert result.parts[0].finish_refs[0].bbox == [10, 20, 100, 200]
    assert PartsList.model_validate_json(result.model_dump_json()) == result
    schema = json.loads((Path(__file__).resolve().parents[2] / "schemas/PartsList.schema.json").read_text())
    jsonschema.validate(data, schema)


@pytest.mark.parametrize("missing", ["bbox", "crop"])
def test_multi_building_finish_requires_crop(missing):
    data = finish_listing()
    del data["parts"][0]["finish_refs"][0][missing]
    with pytest.raises(ValidationError, match=f"wall_a.*{missing}"):
        PartsList.model_validate(data)


@pytest.mark.parametrize("change", [
    {"image": "unknown.jpg"}, {"image": ""}, {"crop": " "}, {"crop": "sheet.jpg"},
    {"bbox": []}, {"bbox": [1, 2, 3]}, {"bbox": [0, 0, 0, 10]},
    {"bbox": [10, 0, 1, 10]}, {"bbox": [-1, 0, 1, 10]},
    {"bbox": [0, 0, float("nan"), 10]}, {"bbox": [0, 0, float("inf"), 10]},
    {"bbox": [False, 0, 1, 10]}, {"bbox": ["0", 0, 1, 10]},
])
def test_finish_reference_invalid(change):
    data = finish_listing()
    data["parts"][0]["finish_refs"][0].update(change)
    with pytest.raises(ValidationError):
        PartsList.model_validate(data)


def test_finish_ref_repeated_failure_reset():
    data = finish_listing()
    data["parts"][0]["finish_refs"][0].pop("bbox")
    for _ in range(2):
        with pytest.raises(ValidationError, match="wall_a.*bbox"):
            PartsList.model_validate(data)
    assert PartsList.model_validate(finish_listing()).parts[0].finish_refs


@pytest.mark.parametrize("alias", ["sheet.jpg", "./sheet.jpg", "SHEET.JPG", "crops/../sheet.jpg"])
def test_finish_sheet_duplicate_alias(alias):
    data = finish_listing()
    data["finish_sheets"].append({"image": alias, "multi_building": False})
    with pytest.raises(ValidationError, match="duplicate finish sheet"):
        PartsList.model_validate(data)


@pytest.mark.parametrize("key,value", [
    ("finish_sheets", []), ("finish_sheets", [{}]),
    ("finish_sheets", [{"image": "sheet.jpg", "multi_building": "true"}]),
    ("finish_refs", []), ("finish_refs", [{}]),
])
def test_finish_metadata_empty_partial_unsupported(key, value):
    data = finish_listing()
    target = data if key == "finish_sheets" else data["parts"][0]
    target[key] = value
    with pytest.raises(ValidationError):
        PartsList.model_validate(data)


def test_finish_single_sheet_without_crop_and_reference_order():
    data = finish_listing()
    data["finish_sheets"][0]["multi_building"] = False
    data["parts"][0]["finish_refs"] = [{"image": "sheet.jpg"}]
    assert PartsList.model_validate(data).parts[0].finish_refs[0].bbox is None
    data = finish_listing()
    second = {"image": "other.jpg", "multi_building": False}
    data["finish_sheets"].insert(0, second)
    assert PartsList.model_validate(data).parts[0].finish_refs[0].bbox
    assert PartsList.model_validate(data).approval_sha256() != make().approval_sha256()


def test_finish_generated_bbox_probe():
    # Exhaust an independent integer-grid oracle including zero-size boundaries.
    from itertools import product
    from dt_ai.parts.model import FinishRef
    for left, top, right, bottom in product(range(4), repeat=4):
        bbox = [left, top, right, bottom]
        if right > left and bottom > top:
            assert FinishRef(image="sheet.jpg", bbox=bbox).bbox == bbox
        else:
            with pytest.raises(ValidationError):
                FinishRef(image="sheet.jpg", bbox=bbox)


def test_finish_crop_rule_documented():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    for path in [".agents/skills/analyze-architectural-source/SKILL.md", "docs/agents/task-intake.md"]:
        text = (root / path).read_text(encoding="utf-8")
        assert "finish_refs" in text and "multi_building" in text and "crop path" in text


def test_drawings_only_source_tier():
    import json
    from pathlib import Path
    import jsonschema

    data = copy.deepcopy(LISTING)
    data.update(source_tier="D", sources=[{"kind": "drawing", "reference": "synthetic.dwg"}])
    assert PartsList.model_validate(data).source_tier == "D"
    root = Path(__file__).resolve().parents[2]
    jsonschema.validate(data, json.loads((root / "schemas/PartsList.schema.json").read_text()))
    row = next(line for line in (root / "docs/procedure/TASK_TO_MODEL.md").read_text().splitlines()
               if line.startswith("| parts |"))
    assert "D = drawings-only" in row


def test_parts_budget_is_project_allocation():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    description = PartsList.model_fields["triangle_budget"].description or ""
    assert "allocated project budget" in description
    assert "not the regulatory ceiling" in description
    for relative, prefix in [("docs/procedure/TASK_TO_MODEL.md", "| parts |"),
                             ("docs/scenarios/oks-vpm.md", "| Budget |")]:
        row = next(line for line in (root / relative).read_text(encoding="utf-8").splitlines()
                   if line.startswith(prefix))
        assert "allocated project budget" in row
        assert "[D276]" in row


def test_gate1_identity_ignores_envelope_and_json_format():
    import hashlib
    import json

    draft = make()
    payload = draft.model_dump(mode="json", exclude={"gate1", "status"})
    expected = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                         ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()
    assert draft.approval_sha256() == expected
    confirmed = make(status="confirmed", gate1={"actor": "synthetic fixture", "date": "2026-11-13",
                     "scope": "synthetic_fixture", "note": "test", "ref": "D111",
                     "parts_sha256": expected})
    assert confirmed.approval_sha256() == expected
    reordered = json.loads(json.dumps(confirmed.model_dump(), indent=4), object_pairs_hook=lambda x: dict(reversed(x)))
    assert PartsList.model_validate(reordered).approval_sha256() == expected


@pytest.mark.parametrize("bad", ["", "0" * 63, "0" * 65, "A" * 64, "0" * 64 + "\n", float("nan"), float("inf"), 7])
def test_gate1_hash_validation(bad):
    import json
    from pathlib import Path
    import jsonschema
    from dt_ai.core.provenance import Approval

    root = Path(__file__).resolve().parents[2]
    schema = json.loads((root / "schemas/PartsList.schema.json").read_text())
    data = copy.deepcopy(LISTING)
    data["gate1"] = {"actor": "synthetic fixture", "date": "2026-11-13", "scope": "synthetic_fixture",
                     "note": "test", "parts_sha256": bad}
    assert list(jsonschema.Draft202012Validator(schema).iter_errors(data))
    with pytest.raises(ValidationError):
        Approval.model_validate(data["gate1"])


@pytest.mark.parametrize("tier", ["", "E", "drawings", None, 1])
def test_invalid_source_tier(tier):
    with pytest.raises(ValidationError):
        make(source_tier=tier)


@pytest.mark.parametrize("profile", ["npm", "vpm"])
def test_part_budget_allocation_boundary(profile):
    allocation = {"npm": 150, "vpm": 600}
    assert make(triangle_budget=allocation).triangle_budget.model_dump() == allocation
    allocation[profile] -= 1
    with pytest.raises(ValidationError, match="over the total"):
        make(triangle_budget=allocation)


def test_valid_list_roundtrips():
    parts = make()
    assert PartsList.model_validate_json(parts.model_dump_json()) == parts
    assert parts.status == "draft"


@pytest.mark.parametrize("change", [
    {"parts": [PART, PART]},                                           # duplicate id
    {"parts": []},                                                     # no parts
    {"joints": [{"parts": ["wall_a", "wall_z"], "decision": "weld", "reason": "r", "extra_edges": 0}]},
    {"joints": [{"parts": ["wall_a", "wall_a"], "decision": "weld", "reason": "r", "extra_edges": 0}]},
    {"triangle_budget": {"npm": 100, "vpm": 2000}},                    # part budgets over the total
    {"status": "confirmed"},                                           # confirmed without gate 1
    {"unknown_field": 1},
])
def test_invalid_list_rejected(change):
    with pytest.raises(ValidationError):
        make(**change)


def test_joint_decided_once_in_either_order():
    swapped = {"parts": ["rail_a", "wall_a"], "decision": "weld", "reason": "r", "extra_edges": 0}
    with pytest.raises(ValidationError, match="decided twice"):
        make(joints=LISTING["joints"] + [swapped])


@pytest.mark.parametrize("joint", [
    {"decision": "embed", "reason": "r", "extra_edges": 3},                        # embed without depth
    {"decision": "weld", "reason": "r", "extra_edges": 0, "embed_depth_m": 0.015},  # weld with depth
    {"decision": "embed", "reason": "r", "extra_edges": 3, "embed_depth_m": 0.05},  # outside 10-20 mm
    {"decision": "weld", "reason": "", "extra_edges": 0},                           # no reason
    {"decision": "weld", "reason": "r", "extra_edges": -1},
])
def test_joint_rules(joint):
    with pytest.raises(ValidationError):
        make(joints=[{"parts": ["wall_a", "rail_a"], **joint}])


@pytest.mark.parametrize("changes", [
    {"build_as": "box"},                                    # build_as on keep
    {"operation": "primitive"},                             # primitive without build_as
    {"library_ref": "window_pvc_1"},                        # library_ref on keep
    {"operation": "library_replace"},                       # library_replace without library_ref
    {"operation": "to_texture"},                            # texture part with triangles
    {"mesh": "../outside.fbx"},
    {"mesh": "/abs/part.fbx"},
])
def test_operation_fields(changes):
    with pytest.raises(ValidationError):
        make(parts=[{**PART, **changes}])


def test_texture_part_and_library_part_validate():
    texture = {**PART, "id": "joint_lines", "operation": "to_texture", "triangle_budget": {"npm": 0, "vpm": 0}}
    window = {**PART, "id": "win_1", "part_class": "window", "operation": "library_replace",
              "library_ref": "window_pvc_1", "mesh": "parts/win_1.fbx"}
    assert make(parts=[PART, texture, window], joints=[]).parts[2].library_ref == "window_pvc_1"


def test_confirmed_needs_gate1_and_synthetic_cannot_carry_project_approval():
    approval = {"actor": "user", "date": "2026-10-18", "scope": "synthetic_fixture", "note": "gate 1"}
    assert make(status="confirmed", gate1=approval).status == "confirmed"
    with pytest.raises(ValidationError, match="project approval"):
        make(status="confirmed", gate1={**approval, "scope": "project"})
    assert make(synthetic=False, status="confirmed", gate1={**approval, "scope": "project"}).status == "confirmed"


def test_missing_legend_item_is_allowed_and_questions_carry_audience():
    part = {k: v for k, v in PART.items() if k != "legend_item"}
    listing = make(parts=[part], joints=[], questions=[{"audience": "architect", "text": "Which finish is this?"}])
    assert listing.parts[0].legend_item is None
    with pytest.raises(ValidationError):
        make(questions=[{"audience": "worker", "text": "?"}])
