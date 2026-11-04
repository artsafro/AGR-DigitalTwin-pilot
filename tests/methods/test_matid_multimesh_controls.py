"""Multi-mesh controls for methods_metrics.matid (baseline-green characterization, literal synthetic dicts).

Extends the one-mesh checks in test_methods_catalog.py: per-mesh slot inventory is independent, the material-ID
union covers model meshes only, and invalid meshes are all reported. Metric integrity is not delivery acceptance.
"""

from __future__ import annotations

import copy
import itertools
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools" / "methods"
sys.path.insert(0, str(TOOLS))
import methods_metrics as mm  # noqa: E402


def _info(slots, used):
    return {"slots": slots, "polygons_by_material_index": {str(k): v for k, v in used.items()}, "tris": []}


def _scene():
    rb = {"meshes": [{"name": "SM_A"}, {"name": "SM_B"}, {"name": "UCX_SM_A_001"}]}
    extra = {"ok": True, "meshes": {
        "SM_A": _info(["M_a0", "M_a1", "M_a2"], {0: 4, 1: 2, 2: 6}),
        "SM_B": _info(["M_b0"], {0: 12}),
        "UCX_SM_A_001": _info([], {0: 3}),
    }}
    return rb, extra


def _without_ucx(rb, extra):
    rb = {"meshes": [m for m in rb["meshes"] if m["name"] != "UCX_SM_A_001"]}
    extra["meshes"].pop("UCX_SM_A_001")
    return rb, extra


def test_two_models_union_and_slot_free_ucx():
    rb, extra = _without_ucx(*_scene())
    r = mm.matid(rb, extra)
    assert r["passed"] is True and r["problems"] == []
    assert r["material_ids"] == [0, 1, 2] and r["meshes_checked"] == 2
    rb, extra = _scene()
    r = mm.matid(rb, extra)
    assert r["passed"] is True and r["problems"] == []
    assert r["material_ids"] == [0, 1, 2] and r["meshes_checked"] == 3


def test_no_cross_mesh_rescue_for_missing_slot():
    rb, extra = _scene()
    extra["meshes"]["SM_A"]["slots"] = ["M_a0", "M_a1"]  # B still owns a valid slot 2? give it one
    extra["meshes"]["SM_B"] = _info(["M_b0", "M_b1", "M_b2"], {0: 4, 2: 1, 1: 1})
    r = mm.matid(rb, extra)
    assert r["passed"] is False
    assert r["problems"] == ["SM_A: 6 polygon(s) use material index 2 without a slot"]


def test_unused_slot_not_rescued_by_same_index_on_other_mesh():
    rb, extra = _scene()
    extra["meshes"]["SM_A"] = _info(["M_a0", "M_a1", "M_a2"], {0: 4, 1: 2})
    extra["meshes"]["SM_B"] = _info(["M_b0", "M_b1", "M_b2"], {0: 1, 1: 1, 2: 1})
    r = mm.matid(rb, extra)
    assert r["passed"] is False
    assert r["problems"] == ["SM_A: unused slot(s) [2]"]


def test_used_none_slot_is_mesh_local():
    rb, extra = _scene()
    extra["meshes"]["SM_A"]["slots"] = ["M_a0", None, "M_a2"]
    r = mm.matid(rb, extra)
    assert r["passed"] is False
    assert r["problems"] == ["SM_A: slot 1 is empty but used by 2 polygon(s)"]


def _invalid_scene():
    rb = {"meshes": [{"name": "SM_A"}, {"name": "SM_B"}, {"name": "SM_C"}, {"name": "UCX_SM_C_001"}]}
    extra = {"ok": True, "meshes": {
        "SM_A": _info(["M"], {0: 1, 3: 2}),
        "SM_B": _info([None, "M"], {0: 5, 1: 1}),
        "SM_C": _info(["M", "M2"], {0: 1}),
        "UCX_SM_C_001": _info(["M_bad"], {0: 1}),
    }}
    return rb, extra


EXPECTED_INVALID = sorted([
    "SM_A: 2 polygon(s) use material index 3 without a slot",
    "SM_B: slot 0 is empty but used by 5 polygon(s)",
    "SM_C: unused slot(s) [1]",
    "UCX_SM_C_001: UCX has 1 material slot(s)",
])


def test_all_independent_problems_retained():
    r = mm.matid(*_invalid_scene())
    assert r["passed"] is False and r["meshes_checked"] == 4
    assert sorted(r["problems"]) == EXPECTED_INVALID


@pytest.mark.parametrize("builder", [_invalid_scene, _scene])
def test_order_independence(builder):
    rb, extra = builder()
    base = mm.matid(rb, extra)
    names = [m["name"] for m in rb["meshes"]]
    for perm in itertools.permutations(rb["meshes"]):
        for key_order in (names, names[::-1]):
            e2 = {"ok": True, "meshes": {k: copy.deepcopy(extra["meshes"][k]) for k in key_order}}
            r = mm.matid({"meshes": list(perm)}, e2)
            assert (r["passed"], r["meshes_checked"], r["material_ids"]) == (
                base["passed"], base["meshes_checked"], base["material_ids"])
            assert sorted(r["problems"]) == sorted(base["problems"])


@pytest.mark.parametrize("extra_value", [None, {}, {"ok": False, "meshes": {}}])
def test_missing_or_not_ok_extra_is_not_measured(extra_value):
    rb, _ = _scene()
    r = mm.matid(rb, extra_value)
    assert r == {"passed": None, "problems": [], "reason": "no extra readback"}


@pytest.mark.parametrize("missing", ["SM_A", "SM_B", "UCX_SM_A_001"])
def test_missing_entry_names_that_mesh(missing):
    rb, extra = _scene()
    del extra["meshes"][missing]
    with pytest.raises(mm.MetricError, match=repr(missing)):
        mm.matid(rb, extra)


def test_inputs_unchanged_after_repeated_calls():
    for builder in (_scene, _invalid_scene):
        rb, extra = builder()
        rb0, extra0 = copy.deepcopy(rb), copy.deepcopy(extra)
        first = mm.matid(rb, extra)
        for _ in range(3):
            assert mm.matid(rb, extra) == first
        assert rb == rb0 and extra == extra0
