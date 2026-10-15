"""V011 regression cases using synthetic in-memory GeoJSON bytes only.

The API also emits successful checks: a finding here means a non-pass result.
Each negative case must produce exactly one such result, not merely contain it.
"""
import base64
import json
from io import BytesIO

import pytest
from PIL import Image

from twinqa.geojson import geojson_findings
from twinqa.profiles import load_profiles


PROFILE = load_profiles().vpm
PROPERTY_KEYS = PROFILE["geojson"]["properties_keys"]


@pytest.fixture
def document():
    image = BytesIO()
    Image.new("RGB", (256, 256), (120, 130, 140)).save(image, "JPEG")
    properties = {key: "synthetic" for key in PROPERTY_KEYS}
    properties.update(
        FNO_code="123 456", other="", act_AGR="",
        imageBase64=base64.b64encode(image.getvalue()).decode("ascii"),
    )
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "ObjectFeature",
            "geometry": {"type": "Point", "coordinates": [12345.678, 6789.012]},
            "properties": properties,
            "Glasses": [],
        }],
    }


def findings(data):
    return [
        (finding.name, finding.status)
        for finding in geojson_findings(data, PROFILE, ground=False, glass_names=set())
        if finding.status != "pass"
    ]


def encode(document):
    return json.dumps(document, ensure_ascii=False).encode("utf-8")


@pytest.mark.parametrize("data, expected", [
    pytest.param(b"\xff", [("UTF-8", "fail")], id="invalid-utf8"),
    pytest.param(b'{"type":', [("JSON", "fail")], id="invalid-json"),
])
def test_invalid_bytes_have_one_finding(data, expected):
    assert findings(data) == expected


@pytest.mark.parametrize("case, expected", [
    ("not-feature-collection", ("type", "fail")),
    ("non-point", ("geometry", "fail")),
    ("precision", ("coordinates precision", "review")),
    ("missing-property", ("property keys", "fail")),
    ("extra-property", ("property keys", "fail")),
    ("missing-glasses", ("Glasses", "fail")),
])
def test_single_schema_defect_has_one_finding(document, case, expected):
    feature = document["features"][0]
    if case == "not-feature-collection":
        document["type"] = "Feature"
    elif case == "non-point":
        # Keep numeric coordinates valid to isolate the geometry type check.
        feature["geometry"]["type"] = "LineString"
    elif case == "precision":
        feature["geometry"]["coordinates"][0] = 12345.6789
    elif case == "missing-property":
        del feature["properties"]["address"]
    elif case == "extra-property":
        feature["properties"]["unexpected"] = "synthetic"
    elif case == "missing-glasses":
        del feature["Glasses"]
    assert findings(encode(document)) == [expected]


def test_valid_feature_collection_has_no_findings(document):
    assert findings(encode(document)) == []


@pytest.mark.parametrize("key", PROPERTY_KEYS)
def test_each_missing_property_produces_exactly_one_finding(document, key):
    """Exhaust the required key set, including imageBase64 and nullable fields."""
    del document["features"][0]["properties"][key]
    assert findings(encode(document)) == [("property keys", "fail")]


@pytest.mark.parametrize("axis", [0, 1], ids=["x", "y"])
@pytest.mark.parametrize("sign", [-1, 1], ids=["negative", "positive"])
@pytest.mark.parametrize("places", range(7))
def test_coordinate_precision_boundary(document, axis, sign, places):
    """Generate 28 probes around the <=3 decimal-place acceptance boundary."""
    value = float("12" + ("." + "1" * places if places else "")) * sign
    document["features"][0]["geometry"]["coordinates"][axis] = value
    expected = [] if places <= 3 else [("coordinates precision", "review")]
    assert findings(encode(document)) == expected
