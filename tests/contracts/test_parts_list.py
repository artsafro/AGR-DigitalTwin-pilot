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
