"""new-case: GeoJSON structural early-return diagnostics through real CLI reports.

Characterization of standalone ``.geojson`` under profile ``vpm``: real ``validate()``
and a fresh ``validate_package.py`` process. A valid control still leaves mandatory
stages unexecuted, so the report is not a delivery pass.

Excluded: BOM, duplicate keys, surrogates, nesting, numeric overflow or precision,
Glasses key order.
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

import validate_package
from twinqa.profiles import load_profiles

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "tools" / "qa" / "validate_package.py"

# Literal App.3 keys from standards/VPM_STANDARD.yaml geojson.properties_keys.
PROPERTY_KEYS = (
    "address", "okrug", "rajon", "name", "developer", "designer", "cadNum",
    "FNO_code", "FNO_name", "ZU_area", "h_relief", "h_otn", "h_abs",
    "s_obsh", "s_naz", "s_podz", "spp_gns", "act_AGR", "imageBase64", "other",
)

IMAGE_PASS = ("imageBase64", "pass", "JPG 256x256", "JPG 256x256", (54,))
GLASSES_PASS = (
    "Glasses", "pass", "[] (no glass)",
    "[] or [{glass material name: {...}, ...}] (one object in a list)",
    (51, 55),
)
SCHEMA_PASS = (
    "schema", "pass",
    "FeatureCollection / ObjectFeature / Point, exact keys",
    "App.3",
    (26, 27, 51, 52, 53, 54, 55),
)
TYPE_TAIL = (IMAGE_PASS, GLASSES_PASS)
VALID_FINDINGS = (IMAGE_PASS, GLASSES_PASS, SCHEMA_PASS)

# Frozen before the checks. Expected strings are the literals geojson.py emits.
STRUCTURAL_CASES = (
    pytest.param("root-null", "fail", False, 1, (
        ("type", "fail", "None", "FeatureCollection", (51,)),
    ), id="root-null"),
    pytest.param("root-array", "fail", False, 1, (
        ("type", "fail", "[]", "FeatureCollection", (51,)),
    ), id="root-array"),
    pytest.param("features-absent", "fail", False, 1, (
        ("features", "fail", "None", "exactly one feature", (51,)),
    ), id="features-absent"),
    pytest.param("features-null", "fail", False, 1, (
        ("features", "fail", "None", "exactly one feature", (51,)),
    ), id="features-null"),
    pytest.param("features-object", "fail", False, 1, (
        ("features", "fail", "{}", "exactly one feature", (51,)),
    ), id="features-object"),
    pytest.param("features-empty", "fail", False, 1, (
        ("features", "fail", "0", "exactly one feature", (51,)),
    ), id="features-empty"),
    pytest.param("features-two", "fail", False, 1, (
        ("features", "fail", "2", "exactly one feature", (51,)),
    ), id="features-two"),
    pytest.param("feature-null", "fail", False, 1, (
        ("feature", "fail", "None", "object", (51,)),
    ), id="feature-null"),
    pytest.param("feature-false", "fail", False, 1, (
        ("feature", "fail", "False", "object", (51,)),
    ), id="feature-false"),
    pytest.param("feature-number", "fail", False, 1, (
        ("feature", "fail", "42", "object", (51,)),
    ), id="feature-number"),
    pytest.param("feature-array", "fail", False, 1, (
        ("feature", "fail", "[]", "object", (51,)),
    ), id="feature-array"),
    pytest.param("feature-type-missing", "fail", False, 1, (
        ("feature type", "fail", "None", "literal ObjectFeature", (51,)),
        *TYPE_TAIL,
    ), id="feature-type-missing"),
    pytest.param("feature-type-literal-feature", "fail", False, 1, (
        ("feature type", "fail", "'Feature'", "literal ObjectFeature", (51,)),
        *TYPE_TAIL,
    ), id="feature-type-literal-feature"),
    pytest.param("valid", "pass", False, 2, VALID_FINDINGS, id="valid"),
)

CLI_CASES = (
    pytest.param("root-null", id="cli-root"),
    pytest.param("features-two", id="cli-features"),
    pytest.param("feature-null", id="cli-feature-nonobject"),
    pytest.param("feature-type-literal-feature", id="cli-feature-type"),
    pytest.param("valid", id="cli-valid"),
)

_CASE = {param.values[0]: param.values for param in STRUCTURAL_CASES}


def _jpeg_b64() -> str:
    image = BytesIO()
    Image.new("RGB", (256, 256), (120, 130, 140)).save(image, "JPEG")
    return base64.b64encode(image.getvalue()).decode("ascii")


def _feature() -> dict:
    properties = {key: "synthetic" for key in PROPERTY_KEYS}
    properties.update(FNO_code="123 456", other="", act_AGR="", imageBase64=_jpeg_b64())
    return {
        "type": "ObjectFeature",
        "geometry": {"type": "Point", "coordinates": [12345.678, 6789.012]},
        "properties": properties,
        "Glasses": [],
    }


def _document(case_id: str):
    feature = _feature()
    if case_id == "root-null":
        return None
    if case_id == "root-array":
        return []
    if case_id == "features-absent":
        return {"type": "FeatureCollection"}
    if case_id == "features-null":
        return {"type": "FeatureCollection", "features": None}
    if case_id == "features-object":
        return {"type": "FeatureCollection", "features": {}}
    if case_id == "features-empty":
        return {"type": "FeatureCollection", "features": []}
    if case_id == "features-two":
        return {"type": "FeatureCollection", "features": [_feature(), _feature()]}
    if case_id == "feature-null":
        return {"type": "FeatureCollection", "features": [None]}
    if case_id == "feature-false":
        return {"type": "FeatureCollection", "features": [False]}
    if case_id == "feature-number":
        return {"type": "FeatureCollection", "features": [42]}
    if case_id == "feature-array":
        return {"type": "FeatureCollection", "features": [[]]}
    if case_id == "feature-type-missing":
        del feature["type"]
        return {"type": "FeatureCollection", "features": [feature]}
    if case_id == "feature-type-literal-feature":
        feature["type"] = "Feature"
        return {"type": "FeatureCollection", "features": [feature]}
    if case_id == "valid":
        return {"type": "FeatureCollection", "features": [feature]}
    raise AssertionError(case_id)


def _write(tmp_path: Path, case_id: str) -> Path:
    path = tmp_path / f"{case_id}.geojson"
    path.write_bytes(json.dumps(_document(case_id), ensure_ascii=False).encode("utf-8"))
    return path


def _rows(findings):
    return [
        (item.name, item.status, item.observed, item.expected, tuple(item.source_pdf_pages))
        for item in findings
    ]


@pytest.mark.parametrize("case_id,v011_status,passed,exit_code,findings", STRUCTURAL_CASES)
def test_validate_structural_report(tmp_path, case_id, v011_status, passed, exit_code, findings):
    path = _write(tmp_path, case_id)
    report = validate_package.validate(path, "vpm", load_profiles())
    assert report.profile == "vpm"
    assert report.passed is passed
    assert report.exit_code == exit_code
    populated = [stage for stage in report.stages if stage.findings]
    assert [stage.id for stage in populated] == ["V011"]
    stage = populated[0]
    assert stage.status == v011_status
    assert _rows(stage.findings) == list(findings)
    non_pass = [item for item in stage.findings if item.status != "pass"]
    if case_id.startswith("feature-type-"):
        assert len(non_pass) == 1
        assert (non_pass[0].name, non_pass[0].status, non_pass[0].expected) == (
            "feature type", "fail", "literal ObjectFeature",
        )
        assert [item.name for item in stage.findings if item.status == "pass"] == ["imageBase64", "Glasses"]
        assert all(item.name != "schema" for item in stage.findings)
    elif case_id != "valid":
        assert len(stage.findings) == 1
        assert len(non_pass) == 1
        assert stage.findings[0].source_pdf_pages == [51]


def _cli_finding(row):
    name, status, observed, expected, pages = row
    return {
        "name": name,
        "status": status,
        "observed": observed,
        "expected": expected,
        "source_pdf_pages": list(pages),
        "evidence": "GeoJSON",
        "conflicts": [],
        "measured": None,
        "threshold": None,
        "margin": None,
    }


@pytest.mark.parametrize("case_id", CLI_CASES)
def test_cli_structural_report(tmp_path, case_id):
    case_id, v011_status, passed, exit_code, findings = _CASE[case_id]
    path = _write(tmp_path, case_id)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    proc = subprocess.run(
        [sys.executable, str(CLI), str(path), "--profile", "vpm", "--json"],
        capture_output=True,
        cwd=ROOT,
        timeout=90,
    )
    assert proc.stderr == b""
    report = json.loads(proc.stdout.decode("utf-8"))
    assert report["passed"] is passed
    assert report["exit_code"] == exit_code == proc.returncode
    stages = [stage for stage in report["stages"] if stage["id"] == "V011"]
    assert len(stages) == 1
    stage = stages[0]
    assert stage["status"] == v011_status
    assert stage["findings"] == [_cli_finding(row) for row in findings]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
