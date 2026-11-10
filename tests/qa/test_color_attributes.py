"""SINTEZ 4.1.1 / lp_color_attributes: twinqa reports FBX color attributes from readback dicts (no Blender)."""
import math

import pytest

from test_scene import PROFILES, mesh, rb
from twinqa.scene import color_attribute_finding, scene_findings

COL = {"name": "Col", "domain": "CORNER", "data_type": "BYTE_COLOR"}


def colored(name, attrs, legacy=0):
    facts = mesh(name)
    facts["color_attributes"] = list(attrs)
    facts["legacy_vertex_colors"] = legacy
    return facts


def test_no_color_attributes_pass_with_observed_zero():
    found = color_attribute_finding([colored("SM_A_Ground", []), colored("SM_A_GroundEl", [])], "a.fbx")
    assert found.status == "pass"
    assert found.measured == 0
    assert "0" in found.observed


def test_color_attribute_is_review_and_names_object_and_layer():
    found = color_attribute_finding([colored("SM_A_Ground", []), colored("SM_A_Flora", [COL])], "a.fbx")
    assert found.status == "review"
    assert found.measured == 1
    assert "SM_A_Flora:Col" in found.observed
    assert "SM_A_Ground" not in found.observed
    assert found.data["objects"] == {"SM_A_Flora": ["Col"]}


def test_legacy_vertex_colors_alone_is_review():
    found = color_attribute_finding([colored("SM_A_Flora", [], legacy=2)], "a.fbx")
    assert found.status == "review"
    assert "SM_A_Flora" in found.observed


def test_old_readback_without_key_is_not_run_never_pass():
    found = color_attribute_finding([colored("SM_A_Ground", []), mesh("SM_A_Flora")], "a.fbx")
    assert found.status == "not_run"
    assert "SM_A_Flora" in found.observed


@pytest.mark.parametrize("bad", [None, "Col", [{"domain": "CORNER"}], [COL, 1], {"name": "Col"}])
def test_malformed_color_attributes_are_not_run(bad):
    facts = mesh("SM_A_Flora")
    facts["color_attributes"] = bad
    assert color_attribute_finding([facts], "a.fbx").status == "not_run"


@pytest.mark.parametrize("legacy", [-1, 1.5, math.nan, math.inf, "2", None, True])
def test_malformed_legacy_count_is_not_run(legacy):
    facts = colored("SM_A_Flora", [])
    facts["legacy_vertex_colors"] = legacy
    assert color_attribute_finding([facts], "a.fbx").status == "not_run"


def test_no_meshes_is_not_run():
    assert color_attribute_finding([], "a.fbx").status == "not_run"


def test_ucx_color_layer_is_reported_too():
    found = color_attribute_finding([colored("UCX_SM_A_001", [COL])], "a.fbx")
    assert found.status == "review" and "UCX_SM_A_001:Col" in found.observed


def test_scene_findings_carries_v005_color_attributes():
    found = scene_findings(rb(colored("SM_Test_K_1_Main", [COL])), "npm", "oks", PROFILES.npm)
    names = {f.name: f.status for f in found["V005"]}
    assert names["color attributes"] == "review"
