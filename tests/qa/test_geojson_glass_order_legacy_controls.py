"""LEGACY characterization of measured current behavior, pending the user's duplicate-identity/equivalence decision; NOT approved identity semantics; does not adopt either proposed production change; legacy V011 pass is not delivery acceptance.

new-case

Synthetic FeatureCollection only. The handwritten tables below pin the current
public ``geojson_findings`` result for JSON member order. They are not an
identity rule and they do not choose either proposed production change.
"""
import base64
import hashlib
import json
import subprocess
import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

import twinqa.geojson as geo
from twinqa.io import read_json
from twinqa.profiles import load_profiles

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "tools" / "qa" / "validate_package.py"
PROFILE = load_profiles().vpm
PROPERTY_KEYS = PROFILE["geojson"]["properties_keys"]

M1 = "M_Test_K_1_MainGlass_1"
M2 = "M_Test_K_1_MainGlass_2"
DUP_OBSERVED = "M_Test_K_1_MainGlass_1, M_Test_K_1_MainGlass_2"

CANON_RGB = ("Red", "Green", "Blue")
CANON_OUTER = ("color_RGB", "transparency", "refraction", "roughness", "metallicity")
REVERSED_OUTER = ("metallicity", "roughness", "refraction", "transparency", "color_RGB")

# row -> (color_RGB member order, Blue, refraction, outer key order) for the second glass.
# First glass is always Red, Green, Blue and the canonical outer order.
M2_SPEC = {
    "rgb_Red_Green_Blue": (("Red", "Green", "Blue"), 140, 1.5, CANON_OUTER),
    "rgb_Red_Blue_Green": (("Red", "Blue", "Green"), 140, 1.5, CANON_OUTER),
    "rgb_Green_Red_Blue": (("Green", "Red", "Blue"), 140, 1.5, CANON_OUTER),
    "rgb_Green_Blue_Red": (("Green", "Blue", "Red"), 140, 1.5, CANON_OUTER),
    "rgb_Blue_Red_Green": (("Blue", "Red", "Green"), 140, 1.5, CANON_OUTER),
    "rgb_Blue_Green_Red": (("Blue", "Green", "Red"), 140, 1.5, CANON_OUTER),
    "outer_reorder": (("Red", "Green", "Blue"), 140, 1.5, REVERSED_OUTER),
    "blue_141": (("Red", "Green", "Blue"), 141, 1.5, CANON_OUTER),
    "refraction_1_6": (("Red", "Green", "Blue"), 140, 1.6, CANON_OUTER),
}

ROW_IDS = (
    "one_glass",
    "rgb_Red_Green_Blue",
    "rgb_Red_Blue_Green",
    "rgb_Green_Red_Blue",
    "rgb_Green_Blue_Red",
    "rgb_Blue_Red_Green",
    "rgb_Blue_Green_Red",
    "outer_reorder",
    "blue_141",
    "refraction_1_6",
)
PERM_ROWS = (
    "rgb_Red_Blue_Green",
    "rgb_Green_Red_Blue",
    "rgb_Green_Blue_Red",
    "rgb_Blue_Red_Green",
    "rgb_Blue_Green_Red",
)
ORDER_EQUAL_ROWS = (
    "rgb_Red_Green_Blue",
    "rgb_Red_Blue_Green",
    "rgb_Green_Red_Blue",
    "rgb_Green_Blue_Red",
    "rgb_Blue_Red_Green",
    "rgb_Blue_Green_Red",
    "outer_reorder",
)

# Handwritten expected (name, status) lists. Not computed from a signature helper.
PASS_NAMES = (
    ("imageBase64", "pass"),
    ("Glasses", "pass"),
    ("schema", "pass"),
)
DUP_NAMES = (
    ("imageBase64", "pass"),
    ("Glasses duplicates", "fail"),
)
EXPECTED_NAMES = {
    "one_glass": PASS_NAMES,
    "rgb_Red_Green_Blue": DUP_NAMES,
    "rgb_Red_Blue_Green": PASS_NAMES,
    "rgb_Green_Red_Blue": PASS_NAMES,
    "rgb_Green_Blue_Red": PASS_NAMES,
    "rgb_Blue_Red_Green": PASS_NAMES,
    "rgb_Blue_Green_Red": PASS_NAMES,
    "outer_reorder": DUP_NAMES,
    "blue_141": PASS_NAMES,
    "refraction_1_6": PASS_NAMES,
}
EXPECTED_OBSERVED = {
    "one_glass": "1 glass material(s)",
    "rgb_Red_Green_Blue": DUP_OBSERVED,
    "rgb_Red_Blue_Green": "2 glass material(s)",
    "rgb_Green_Red_Blue": "2 glass material(s)",
    "rgb_Green_Blue_Red": "2 glass material(s)",
    "rgb_Blue_Red_Green": "2 glass material(s)",
    "rgb_Blue_Green_Red": "2 glass material(s)",
    "outer_reorder": DUP_OBSERVED,
    "blue_141": "2 glass material(s)",
    "refraction_1_6": "2 glass material(s)",
}
M2_RGB_ORDER = {row: spec[0] for row, spec in M2_SPEC.items()}


def _image_b64() -> str:
    buf = BytesIO()
    Image.new("RGB", (256, 256), (120, 130, 140)).save(buf, "JPEG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


IMAGE_B64 = _image_b64()


def _glass(rgb_order, blue: int, refraction: float, outer) -> dict:
    channels = {"Red": 120, "Green": 130, "Blue": blue}
    values = {
        "color_RGB": {key: channels[key] for key in rgb_order},
        "transparency": 0.5,
        "refraction": refraction,
        "roughness": 0.1,
        "metallicity": 0.84,
    }
    return {key: values[key] for key in outer}


def _glasses_object(row: str) -> dict:
    first = _glass(CANON_RGB, 140, 1.5, CANON_OUTER)
    if row == "one_glass":
        return {M1: first}
    rgb_order, blue, refraction, outer = M2_SPEC[row]
    return {M1: first, M2: _glass(rgb_order, blue, refraction, outer)}


def document_bytes(row: str) -> bytes:
    """JSON text via json.dumps without sort_keys so member order is the insertion order."""
    properties = {key: "synthetic" for key in PROPERTY_KEYS}
    properties["FNO_code"] = "123 456"
    properties["other"] = ""
    properties["act_AGR"] = ""
    properties["imageBase64"] = IMAGE_B64
    document = {
        "type": "FeatureCollection",
        "features": [{
            "type": "ObjectFeature",
            "geometry": {"type": "Point", "coordinates": [12345.678, 6789.012]},
            "properties": properties,
            "Glasses": [_glasses_object(row)],
        }],
    }
    return json.dumps(document, ensure_ascii=False, sort_keys=False).encode("utf-8")


def _census(row: str) -> set[str]:
    if row == "one_glass":
        return {M1}
    return {M1, M2}


def collect(row: str, mode: str):
    glass_names = None if mode == "none" else _census(row)
    return geo.geojson_findings(document_bytes(row), PROFILE, False, glass_names=glass_names)


def _names(row: str, mode: str):
    return [(finding.name, finding.status) for finding in collect(row, mode)]


def _parsed_glasses(row: str) -> dict:
    document = read_json(document_bytes(row))
    feature = document["features"][0]
    assert feature["type"] == "ObjectFeature"
    assert "Glasses" in feature and "Glasses" not in feature["properties"]
    assert list(feature["properties"]) == list(PROPERTY_KEYS)
    glasses = feature["Glasses"]
    assert isinstance(glasses, list) and len(glasses) == 1
    return glasses[0]


def _glasses_without_duplicates(original):
    """Mutant A: the duplicate finding is never reported. Other checker results stay."""

    def wrapped(value, glass_names):
        found = original(value, glass_names)
        kept = [item for item in found if item.name != "Glasses duplicates"]
        if len(kept) == len(found) or kept:
            return kept
        # The real checker returns the Glasses pass when the duplicate loop adds nothing.
        materials = value[0] if isinstance(value, list) and len(value) == 1 else None
        if not isinstance(materials, dict):
            return kept
        return [geo._f(
            "pass", "Glasses", f"{len(materials)} glass material(s)",
            "colour, transparency, refraction, roughness, metallicity", [55],
        )]

    return wrapped


def _canonicalize_color_rgb(node):
    """Mutant B: nested color_RGB member order becomes Red, Green, Blue."""
    if isinstance(node, dict):
        rebuilt = {key: _canonicalize_color_rgb(value) for key, value in node.items()}
        if set(rebuilt) == {"Red", "Green", "Blue"}:
            return {"Red": rebuilt["Red"], "Green": rebuilt["Green"], "Blue": rebuilt["Blue"]}
        return rebuilt
    if isinstance(node, list):
        return [_canonicalize_color_rgb(item) for item in node]
    return node


def _findings_with_canonical_rgb(original):
    def wrapped(data, profile, ground, glass_names=None):
        document = _canonicalize_color_rgb(read_json(data))
        payload = json.dumps(document, ensure_ascii=False, sort_keys=False).encode("utf-8")
        return original(payload, profile, ground, glass_names)

    return wrapped


@pytest.mark.parametrize("row", ROW_IDS)
@pytest.mark.parametrize("mode", ["none", "census"])
def test_legacy_finding_names_and_statuses(row, mode):
    findings = collect(row, mode)
    assert [(item.name, item.status) for item in findings] == list(EXPECTED_NAMES[row])
    glasses = [item for item in findings if item.name in ("Glasses", "Glasses duplicates")]
    assert len(glasses) == 1
    assert glasses[0].observed == EXPECTED_OBSERVED[row]
    assert not any(item.name == "Glasses color_RGB" for item in findings)
    if EXPECTED_NAMES[row] == DUP_NAMES:
        assert DUP_OBSERVED == glasses[0].observed
        assert not any(item.name == "schema" and item.status == "pass" for item in findings)
    elif row == "one_glass":
        assert "1 glass material(s)" in glasses[0].observed
        assert any(item.name == "schema" and item.status == "pass" for item in findings)
    else:
        assert "2 glass material(s)" in glasses[0].observed
        assert any(item.name == "schema" and item.status == "pass" for item in findings)


@pytest.mark.parametrize("row", ROW_IDS)
def test_glass_names_modes_have_equal_findings(row):
    assert collect(row, "none") == collect(row, "census")


@pytest.mark.parametrize("row", ORDER_EQUAL_ROWS)
def test_order_only_glasses_compare_equal(row):
    glasses = _parsed_glasses(row)
    assert glasses[M1] == glasses[M2]


@pytest.mark.parametrize("row", ["blue_141", "refraction_1_6"])
def test_value_change_glasses_compare_unequal(row):
    glasses = _parsed_glasses(row)
    assert glasses[M1] != glasses[M2]
    if row == "blue_141":
        assert glasses[M1]["color_RGB"]["Blue"] == 140
        assert glasses[M2]["color_RGB"]["Blue"] == 141
        assert type(glasses[M2]["color_RGB"]["Blue"]) is int
    else:
        assert glasses[M1]["refraction"] == 1.5
        assert glasses[M2]["refraction"] == 1.6
        assert type(glasses[M2]["refraction"]) is float


@pytest.mark.parametrize("row", ROW_IDS)
def test_color_rgb_key_sequences(row):
    glasses = _parsed_glasses(row)
    assert tuple(glasses[M1]["color_RGB"]) == ("Red", "Green", "Blue")
    assert tuple(glasses[M1]) == CANON_OUTER
    if row == "one_glass":
        assert list(glasses) == [M1]
        return
    assert tuple(glasses[M2]["color_RGB"]) == M2_RGB_ORDER[row]
    assert list(glasses) == [M1, M2]
    if row == "outer_reorder":
        assert tuple(glasses[M2]) == (
            "metallicity", "roughness", "refraction", "transparency", "color_RGB",
        )


@pytest.mark.parametrize("row", ROW_IDS)
def test_rgb_and_optic_value_types(row):
    glasses = _parsed_glasses(row)
    for props in glasses.values():
        rgb = props["color_RGB"]
        assert [type(rgb[key]) for key in ("Red", "Green", "Blue")] == [int, int, int]
        for key in ("transparency", "refraction", "roughness", "metallicity"):
            assert type(props[key]) is float


@pytest.mark.parametrize("row", ROW_IDS)
def test_number_spellings_are_fixed(row):
    raw = document_bytes(row).decode("utf-8")
    assert '"coordinates": [12345.678, 6789.012]' in raw
    assert '"FNO_code": "123 456"' in raw
    assert '"other": ""' in raw and '"act_AGR": ""' in raw
    assert '"address": "synthetic"' in raw
    assert '"Red": 120' in raw and '"Green": 130' in raw
    assert '"transparency": 0.5' in raw
    assert '"roughness": 0.1' in raw and '"metallicity": 0.84' in raw
    assert "120.0" not in raw and "130.0" not in raw and "0.50" not in raw
    if row == "blue_141":
        assert '"Blue": 140' in raw and '"Blue": 141' in raw
    else:
        assert '"Blue": 140' in raw and '"Blue": 141' not in raw
    if row == "refraction_1_6":
        assert '"refraction": 1.5' in raw and '"refraction": 1.6' in raw
    else:
        assert '"refraction": 1.5' in raw and '"refraction": 1.6' not in raw


@pytest.mark.parametrize("row, v011_status, code", [
    ("rgb_Red_Green_Blue", "fail", 1),
    ("rgb_Blue_Green_Red", "pass", 2),
    ("outer_reorder", "fail", 1),
    ("blue_141", "pass", 2),
])
def test_cli_v011_legacy_exit(tmp_path, row, v011_status, code):
    path = tmp_path / f"synthetic_{row}.geojson"
    path.write_bytes(document_bytes(row))
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    proc = subprocess.run(
        [sys.executable, str(CLI), str(path), "--profile", "vpm", "--json"],
        cwd=ROOT, capture_output=True, timeout=120,
    )
    assert proc.stderr == b""
    report = read_json(proc.stdout)
    v011 = [stage for stage in report["stages"] if stage["id"] == "V011"]
    assert len(v011) == 1 and v011[0]["status"] == v011_status
    assert report["exit_code"] == code
    assert report["passed"] is False
    assert proc.returncode == code
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_mutant_a_duplicate_suppression_is_detected(monkeypatch):
    assert _names("rgb_Red_Green_Blue", "none") == list(DUP_NAMES)
    assert _names("outer_reorder", "census") == list(DUP_NAMES)
    monkeypatch.setattr(geo, "_glasses", _glasses_without_duplicates(geo._glasses))
    for row in ("rgb_Red_Green_Blue", "outer_reorder"):
        for mode in ("none", "census"):
            findings = collect(row, mode)
            names = [(item.name, item.status) for item in findings]
            assert names != list(DUP_NAMES)
            assert names == list(PASS_NAMES)
            assert ("Glasses duplicates", "fail") not in names
            assert ("schema", "pass") in names
            glasses = [item for item in findings if item.name == "Glasses"]
            assert len(glasses) == 1 and glasses[0].observed == "2 glass material(s)"
    for row in PERM_ROWS:
        assert _names(row, "none") == list(PASS_NAMES)


def test_mutant_b_canonical_rgb_is_detected(monkeypatch):
    for row in PERM_ROWS:
        assert _names(row, "none") == list(PASS_NAMES)
    monkeypatch.setattr(geo, "geojson_findings", _findings_with_canonical_rgb(geo.geojson_findings))
    for row in PERM_ROWS:
        for mode in ("none", "census"):
            findings = collect(row, mode)
            names = [(item.name, item.status) for item in findings]
            assert names != list(PASS_NAMES)
            assert names == list(DUP_NAMES)
            assert ("schema", "pass") not in names
            duplicates = [item for item in findings if item.name == "Glasses duplicates"]
            assert len(duplicates) == 1 and duplicates[0].status == "fail"
            assert duplicates[0].observed == DUP_OBSERVED
    assert _names("blue_141", "none") == list(PASS_NAMES)
    assert _names("refraction_1_6", "census") == list(PASS_NAMES)
    assert _names("rgb_Red_Green_Blue", "none") == list(DUP_NAMES)
