"""Exact V011 Glasses material census and finite optical boundary controls.

Pattern: n/a | new-case: exact material census + finite optical boundary controls
for ``twinqa.geojson._glasses`` via ``geojson_findings`` on a self-contained synthetic
document (generated 256x256 JPEG, numeric coordinates, exact property keys).

Existing tests already cover list/object structure and identical-material duplicates
(``tests/qa/test_validator.py::test_glasses_follow_checker_conflict_13`` and
``tests/twinqa/test_geojson_v011_findings.py``); this module pins the FBX glass-name
material census (``glass_names`` cross-check) and the finite optical boundaries, which
those tests leave unexercised. Every mutation starts from a fresh deep copy and no
fixture is imported from another test module. The document and material names are
synthetic; a ``schema: pass`` here is not delivery or user approval.

Acceptance table (``non-pass`` = findings whose status is not ``pass``):

| Glasses (one object) | glass_names (FBX) | non-pass (name, status, observed) | schema pass |
|---|---|---|---|
| ``[{M1: good}]`` | ``{M1}`` | ``[]`` | yes |
| ``[]`` | ``{M1, M2}`` | ``[("Glasses", "fail", ...)]`` | no |
| ``[{M1: good}]`` | ``{M1, M2}`` | ``[("Glasses material", "fail", "M2")]`` | no |
| ``[{M1: good, M9: extra}]`` | ``{M1}`` | ``[("Glasses material", "fail", "M9")]`` | no |
| ``[{M1: good}]`` | ``None`` | ``[]`` (unknown census is not proof of FBX agreement) | yes |
| transparency/roughness/metallicity = 0 or 1 | ``{M1}`` | ``[]`` | yes |
| transparency/roughness/metallicity = -.125 or 1.125 | ``{M1}`` | ``[("Glasses <field>", "fail", ...)]`` | no |
| refraction = 1 or 3 | ``{M1}`` | ``[]`` | yes |
| refraction = .5 or 3.5 | ``{M1}`` | ``[("Glasses refraction", "fail", ...)]`` | no |
| any optical field = bool or missing | ``{M1}`` | ``[("Glasses <field>", "fail", ...)]`` | no |
| color_RGB = ints 0/255 | ``{M1}`` | ``[]`` | yes |
| color_RGB = channel -1/256/bool or missing/extra channel | ``{M1}`` | ``[("Glasses color_RGB", "fail", ...)]`` | no |

Excluded (separately researched/owned): exponent overflow, nonfinite acceptance policy,
top-level shape, duplicate-glass equivalence policy, image decoding.
"""
import base64
import copy
import json
from io import BytesIO

import pytest
from PIL import Image

from twinqa.geojson import geojson_findings
from twinqa.profiles import load_profiles


PROFILE = load_profiles().vpm
PROPERTY_KEYS = PROFILE["geojson"]["properties_keys"]

M1 = "M_Test_K_1_MainGlass_1"    # valid FBX glass material, present in the valid object
M2 = "M_Test_K_1_MainGlass_2"    # a second FBX glass material
M9 = "M_Test_K_1_MainGlass_9"    # described material that is NOT in the FBX set

GOOD_GLASS = {
    "color_RGB": {"Red": 120, "Green": 130, "Blue": 140},
    "transparency": 0.5,
    "refraction": 1.5,
    "roughness": 0.1,
    "metallicity": 0.84,
}

# (field) -> ((lower, upper) inclusive bounds, (below, above) out-of-range values)
BOUNDS = {
    "transparency": ((0, 1), (-0.125, 1.125)),
    "roughness": ((0, 1), (-0.125, 1.125)),
    "metallicity": ((0, 1), (-0.125, 1.125)),
    "refraction": ((1, 3), (0.5, 3.5)),
}


def _image_b64() -> str:
    buf = BytesIO()
    Image.new("RGB", (256, 256), (120, 130, 140)).save(buf, "JPEG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _working_glasses():
    """A fresh deep copy of the single-material valid Glasses list."""
    return copy.deepcopy([{M1: GOOD_GLASS}])


def _document(glasses):
    properties = {key: "synthetic" for key in PROPERTY_KEYS}
    properties.update(FNO_code="123 456", other="", act_AGR="", imageBase64=_image_b64())
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "ObjectFeature",
            "geometry": {"type": "Point", "coordinates": [12345.678, 6789.012]},
            "properties": properties,
            "Glasses": glasses,
        }],
    }


def _result(glasses, glass_names):
    """Run geojson_findings; return (non-pass tuples, schema-pass bool)."""
    data = json.dumps(_document(glasses), ensure_ascii=False).encode("utf-8")
    findings = geojson_findings(data, PROFILE, ground=False, glass_names=glass_names)
    non_pass = [(f.name, f.status, f.observed) for f in findings if f.status != "pass"]
    schema = any(f.name == "schema" and f.status == "pass" for f in findings)
    return non_pass, schema


def test_valid_matching_glass_has_no_non_pass_and_schema_pass():
    non_pass, schema = _result(_working_glasses(), {M1})
    assert non_pass == []
    assert schema is True


def test_empty_glasses_with_fbx_glass_fails():
    non_pass, schema = _result([], {M1, M2})
    assert non_pass == [("Glasses", "fail", "[] but the FBX has glass")]
    assert schema is False


def test_missing_fbx_material_is_named():
    non_pass, schema = _result([{M1: GOOD_GLASS}], {M1, M2})
    assert non_pass == [("Glasses material", "fail", M2)]
    assert schema is False


def test_extra_described_material_is_named():
    extra = copy.deepcopy(GOOD_GLASS)
    extra["refraction"] = 2.0  # distinct signature -> no duplicate-glass finding
    non_pass, schema = _result([{M1: GOOD_GLASS, M9: extra}], {M1})
    assert non_pass == [("Glasses material", "fail", M9)]
    assert schema is False


def test_none_census_skips_material_check():
    non_pass, schema = _result([{M1: GOOD_GLASS}], None)
    assert non_pass == []
    assert schema is True


@pytest.mark.parametrize("field", list(BOUNDS))
def test_finite_optical_bounds_pass(field):
    lo, hi = BOUNDS[field][0]
    for value in (lo, hi):
        glasses = _working_glasses()
        glasses[0][M1][field] = value
        non_pass, schema = _result(glasses, {M1})
        assert non_pass == []
        assert schema is True


@pytest.mark.parametrize("field", list(BOUNDS))
def test_finite_optical_bounds_fail(field):
    below, above = BOUNDS[field][1]
    for value in (below, above):
        glasses = _working_glasses()
        glasses[0][M1][field] = value
        non_pass, schema = _result(glasses, {M1})
        assert non_pass == [(f"Glasses {field}", "fail", f"{M1}: {value!r}")]
        assert schema is False


@pytest.mark.parametrize("field", list(BOUNDS))
def test_optical_boolean_fails(field):
    glasses = _working_glasses()
    glasses[0][M1][field] = True
    non_pass, schema = _result(glasses, {M1})
    assert non_pass == [(f"Glasses {field}", "fail", f"{M1}: True")]
    assert schema is False


@pytest.mark.parametrize("field", list(BOUNDS))
def test_optical_missing_fails(field):
    glasses = _working_glasses()
    del glasses[0][M1][field]
    non_pass, schema = _result(glasses, {M1})
    assert non_pass == [(f"Glasses {field}", "fail", f"{M1}: None")]
    assert schema is False


def test_rgb_integers_pass():
    glasses = _working_glasses()
    glasses[0][M1]["color_RGB"] = {"Red": 0, "Green": 255, "Blue": 0}
    non_pass, schema = _result(glasses, {M1})
    assert non_pass == []
    assert schema is True


@pytest.mark.parametrize("rgb", [
    {"Red": -1, "Green": 130, "Blue": 140},
    {"Red": 256, "Green": 130, "Blue": 140},
    {"Red": True, "Green": 130, "Blue": 140},
    {"Red": 120, "Green": 130},
    {"Red": 120, "Green": 130, "Blue": 140, "Alpha": 255},
], ids=["negative", "256", "bool", "missing", "extra"])
def test_rgb_channel_fail(rgb):
    glasses = _working_glasses()
    glasses[0][M1]["color_RGB"] = rgb
    non_pass, schema = _result(glasses, {M1})
    assert len(non_pass) == 1
    assert non_pass[0][:2] == ("Glasses color_RGB", "fail")
    assert non_pass[0][2].startswith(f"{M1}: ")
    assert schema is False


def test_inputs_are_not_mutated():
    glasses = _working_glasses()
    doc = _document(glasses)
    data = json.dumps(doc, ensure_ascii=False).encode("utf-8")
    glass_names = {M1, M2}
    profile_snapshot = copy.deepcopy(PROFILE)
    geojson_findings(data, PROFILE, ground=False, glass_names=glass_names)
    assert data == json.dumps(doc, ensure_ascii=False).encode("utf-8")  # bytes unchanged
    assert PROFILE == profile_snapshot  # profile not mutated
    assert glass_names == {M1, M2}  # glass-name set not mutated
