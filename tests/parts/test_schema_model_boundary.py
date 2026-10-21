"""Schema acceptance is not PartsList acceptance (Proposal 2).

Pattern: n/a | new-case: schema acceptance versus model-only rejection
(``reader.schema_errors == []`` is not gate 1 and not user approval).

The same raw instance goes to ``reader.schema_errors`` and ``PartsList.model_validate``.
An empty schema error list is not gate 1 and is not the user's approval: the schema
does not carry the model-only rules below. Integer and NaN semantics are not decided here.

Acceptance table, each row one fresh deep copy of the synthetic two-part draft:

| raw instance | schema_errors | model |
| unchanged draft | ``[]`` | validation succeeds |
| ``status='confirmed'``, ``gate1`` null | ``[]`` | ``ValidationError`` contains ``confirmed needs the gate 1 approval`` |
| two distinct parts given one identical id | ``[]`` | ``ValidationError`` contains ``part ids must be unique`` |
| total npm budget below the sum of part budgets | ``[]`` | ``ValidationError`` contains ``part budgets add up`` |
| primitive operation without ``build_as`` | ``[]`` | ``ValidationError`` contains ``build_as is required`` |
"""
import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from dt_ai.parts.model import PartsList
from dt_ai.parts.readers import fbx as reader

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "schemas" / "PartsList.schema.json").read_text(encoding="utf-8"))

_MODEL_FRAGMENTS = (
    "confirmed needs the gate 1 approval",
    "part ids must be unique",
    "part budgets add up",
    "build_as is required",
)


def _mesh(name, origin):
    return {"name": name, "type": "MESH", "parent": None, "collections": ["Body"],
            "mesh": name + "_mesh", "material_slots": ["M0"],
            "face_material_counts": {"0": 6}, "triangle_material_counts": {"0": 12},
            "triangles": 12, "polygons": 6,
            "bbox": {"min": [origin, 0, 0], "max": [origin + 1, 1, 1]},
            "connected_components": 1}


def _two_part_facts():
    """Synthetic FBX structure: two separated meshes, no contact, no guessed joint."""
    return {"format": "fbx_structure/1",
            "source": {"name": "model.fbx", "path": "C:/x/model.fbx", "sha256": "a" * 64, "bytes": 10},
            "blender": "5.1.2", "units": {"system": "METRIC", "scale_length": 1.0, "length_unit": "METERS"},
            "sections": "not_in_fbx", "contact_tolerance_m": 0.002,
            "objects": [_mesh("Wall_A", 0), _mesh("Slab_B", 10)],
            "components": [], "contacts": []}


DRAFT = json.loads(reader.convert(_two_part_facts(), synthetic=True).model_dump_json())
_DRAFT_JSON = json.dumps(DRAFT, sort_keys=True)


def fresh():
    return copy.deepcopy(DRAFT)


def _draft_unchanged():
    assert json.dumps(DRAFT, sort_keys=True) == _DRAFT_JSON


def _leaf_diff(left, right, path="$"):
    if type(left) is not type(right):
        return [path]
    if isinstance(left, dict):
        found = []
        for key in set(left) | set(right):
            child = f"{path}.{key}"
            if key not in left or key not in right:
                found.append(child)
            else:
                found.extend(_leaf_diff(left[key], right[key], child))
        return found
    if isinstance(left, list):
        if len(left) != len(right):
            return [path]
        found = []
        for index, (a, b) in enumerate(zip(left, right)):
            found.extend(_leaf_diff(a, b, f"{path}[{index}]"))
        return found
    return [] if left == right else [path]


def _confirm(data):
    data["status"] = "confirmed"
    assert data["gate1"] is None


def _same_id(data):
    first, second = data["parts"]
    assert first is not second and first["id"] != second["id"]
    assert first["sources"] != second["sources"]
    second["id"] = first["id"]


def _npm_below_sum(data):
    part_sum = sum(part["triangle_budget"]["npm"] for part in data["parts"])
    assert data["triangle_budget"]["npm"] == part_sum
    assert data["triangle_budget"]["vpm"] == part_sum
    data["triangle_budget"]["npm"] = part_sum - 1


def _primitive_without_build_as(data):
    part = data["parts"][0]
    assert part["operation"] == "keep" and part.get("build_as") is None
    part["operation"] = "primitive"
    part["build_as"] = None


# One mutation per row. ``None`` is the unchanged draft.
_CASES = (
    (None, None, []),
    (_confirm, "confirmed needs the gate 1 approval", ["$.status"]),
    (_same_id, "part ids must be unique", ["$.parts[1].id"]),
    (_npm_below_sum, "part budgets add up", ["$.triangle_budget.npm"]),
    (_primitive_without_build_as, "build_as is required", ["$.parts[0].operation", "$.parts[0].build_as"]),
)


def _both(data):
    """Run both validators on ``data`` and return ``(schema_errors, model or ValidationError)``."""
    before = copy.deepcopy(data)
    errors = reader.schema_errors(data, SCHEMA)
    try:
        model = PartsList.model_validate(data)
    except ValidationError as exc:
        model = exc
    assert data == before
    _draft_unchanged()
    return errors, model


def test_unchanged_draft_passes_schema_and_model():
    data = fresh()
    errors, model = _both(data)
    assert errors == []
    assert isinstance(model, PartsList)
    assert model.status == "draft" and model.gate1 is None
    assert len(model.parts) == 2
    assert _leaf_diff(DRAFT, data) == []


@pytest.mark.parametrize("mutate, fragment, touched", _CASES[1:], ids=[
    "confirmed-gate1-null", "duplicate-part-id", "npm-below-part-sum", "primitive-without-build-as",
])
def test_schema_accepts_and_model_rejects_one_rule(mutate, fragment, touched):
    """Empty schema_errors is not gate-1 approval and not user approval."""
    data = fresh()
    mutate(data)
    assert set(_leaf_diff(DRAFT, data)) <= set(touched)
    errors, model = _both(data)
    assert errors == []
    assert isinstance(model, ValidationError)
    text = str(model)
    assert fragment in text
    assert [item for item in _MODEL_FRAGMENTS if item in text] == [fragment]


def test_probe_empty_schema_list_is_never_gate1_approval():
    """Never: schema_errors == [] on a confirmed list with gate1 null is not approval."""
    seen = 0
    for _ in range(48):
        data = fresh()
        _confirm(data)
        errors, model = _both(data)
        assert errors == []
        assert isinstance(model, ValidationError)
        assert "confirmed needs the gate 1 approval" in str(model)
        seen += 1
    assert seen == 48
    _draft_unchanged()


def test_probe_each_mutation_once_on_its_own_copy():
    """Once: every mutation starts from a new deep copy and leaves the draft unchanged."""
    copies = []
    for _ in range(16):
        for mutate, _fragment, _touched in _CASES[1:]:
            data = fresh()
            assert data == DRAFT and data is not DRAFT
            mutate(data)
            copies.append(data)
    assert len(copies) == 64
    assert len({id(item) for item in copies}) == 64
    again = fresh()
    assert again == DRAFT and again["status"] == "draft" and again["gate1"] is None
    assert again["parts"][0]["id"] != again["parts"][1]["id"]
    _draft_unchanged()


def test_probe_at_most_one_model_rule_per_instance():
    """At most one model-only message, and the schema still returns no errors."""
    seen = 0
    for _ in range(24):
        for mutate, fragment, _touched in _CASES[1:]:
            data = fresh()
            mutate(data)
            errors, model = _both(data)
            assert errors == []
            assert isinstance(model, ValidationError)
            hit = [item for item in _MODEL_FRAGMENTS if item in str(model)]
            assert hit == [fragment]
            seen += 1
    assert seen == 96
    _draft_unchanged()


def test_probe_every_npm_total_below_the_part_sum_is_model_rejected():
    """Below the part-budget sum: every integer total in ``0 .. sum-1`` fails the model only."""
    part_sum = sum(part["triangle_budget"]["npm"] for part in DRAFT["parts"])
    assert part_sum >= 1
    seen = 0
    for total in range(part_sum):
        data = fresh()
        assert data["triangle_budget"]["npm"] == part_sum
        data["triangle_budget"]["npm"] = total
        errors, model = _both(data)
        assert errors == []
        assert isinstance(model, ValidationError)
        assert "part budgets add up" in str(model)
        seen += 1
    assert seen == part_sum
    equal = fresh()
    errors, model = _both(equal)
    assert errors == [] and isinstance(model, PartsList)
    _draft_unchanged()
