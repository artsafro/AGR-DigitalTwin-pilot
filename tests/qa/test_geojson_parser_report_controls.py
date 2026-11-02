"""new-case: GeoJSON encoding and duplicate-key findings persist into the real CLI report.

The corpus is one synthetic valid document plus raw-byte variants. Expected diagnostics are
literals from one observed run of the current reader. This module does not set an encoding policy.
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

from twinqa.geojson import geojson_findings
from twinqa.profiles import load_profiles

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "tools" / "qa" / "validate_package.py"
sys.path.insert(0, str(ROOT / "tools" / "qa"))
import validate_package  # noqa: E402

PROFILES = load_profiles()
PROFILE = PROFILES.vpm
ADDRESS = "улица Тверская"
NOTE = "single GeoJSON: only V011 applies"

_UTF8 = ("UTF-8", "fail", "not valid UTF-8", "UTF-8", [26])
_BOM = ("JSON", "fail",
        "Unexpected UTF-8 BOM (decode using utf-8-sig): line 1 column 1 (char 0)",
        "valid JSON without duplicate keys", [26, 27])
_DUP_TYPE = ("JSON", "fail", "Duplicate key: type", "valid JSON without duplicate keys", [26, 27])
_DUP_ADDRESS = ("JSON", "fail", "Duplicate key: address", "valid JSON without duplicate keys", [26, 27])
_CLEAN = [
    ("imageBase64", "pass", "JPG 256x256", "JPG 256x256", [54]),
    ("Glasses", "pass", "[] (no glass)",
     "[] or [{glass material name: {...}, ...}] (one object in a list)", [51, 55]),
    ("schema", "pass", "FeatureCollection / ObjectFeature / Point, exact keys", "App.3",
     [26, 27, 51, 52, 53, 54, 55]),
]

# name -> (expected finding rows, V011 status, report and process exit). passed is always false.
CASES = {
    "clean_utf8": (_CLEAN, "pass", 2),
    "utf16_bom": ([_UTF8], "fail", 1),
    "invalid_utf8": ([_UTF8], "fail", 1),
    "utf8_bom": ([_BOM], "fail", 1),
    "duplicate_type": ([_DUP_TYPE], "fail", 1),
    "duplicate_address": ([_DUP_ADDRESS], "fail", 1),
}


def _jpeg_b64() -> str:
    buf = BytesIO()
    Image.new("RGB", (256, 256), (12, 34, 56)).save(
        buf, format="JPEG", quality=85, subsampling=0, optimize=False, progressive=False)
    raw = buf.getvalue()
    with Image.open(BytesIO(raw)) as img:
        if img.format != "JPEG" or img.size != (256, 256):
            raise RuntimeError("generated image is not a 256x256 JPEG")
    return base64.b64encode(raw).decode("ascii")


def _clean_utf8() -> bytes:
    props = {key: "synthetic" for key in PROFILE["geojson"]["properties_keys"]}
    props.update(address=ADDRESS, FNO_code="123 456", other="", act_AGR="", imageBase64=_jpeg_b64())
    document = {
        "type": "FeatureCollection",
        "features": [{
            "type": "ObjectFeature",
            "geometry": {"type": "Point", "coordinates": [12345.678, 6789.012]},
            "properties": props,
            "Glasses": [],
        }],
    }
    return json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _corpus() -> dict[str, bytes]:
    """Raw bytes only. Duplicate keys are spliced into the text so a dict dump cannot drop them."""
    clean = _clean_utf8()
    address_pair = ('"address":"' + ADDRESS + '"').encode("utf-8")
    if clean.count(address_pair) != 1 or ADDRESS.encode("utf-8") not in clean:
        raise RuntimeError("clean document is missing its single non-ASCII address")
    invalid = clean.replace(address_pair, b'"address":"\xff' + ADDRESS.encode("utf-8") + b'"', 1)
    top = clean.replace(
        b'"type":"FeatureCollection"',
        b'"type":"FeatureCollection","type":"FeatureCollection"',
        1,
    )
    escaped = b'"\\u0061ddress":"' + ADDRESS.encode("utf-8") + b'"'
    nested = clean.replace(address_pair, address_pair + b"," + escaped, 1)
    rows = {
        "clean_utf8": clean,
        "utf8_bom": b"\xef\xbb\xbf" + clean,
        "utf16_bom": b"\xff\xfe" + clean.decode("utf-8").encode("utf-16-le"),
        "invalid_utf8": invalid,
        "duplicate_type": top,
        "duplicate_address": nested,
    }
    if any(not blob for blob in rows.values()):
        raise RuntimeError("empty corpus row")
    if len({hashlib.sha256(blob).digest() for blob in rows.values()}) != len(rows):
        raise RuntimeError("corpus rows are not distinct")
    if top.count(b'"type":"FeatureCollection"') != 2 or b"\\u0061ddress" not in nested:
        raise RuntimeError("duplicate keys were not kept as raw JSON text")
    if invalid.count(b"\xff") != 1 or b"\xff" in clean:
        raise RuntimeError("invalid UTF-8 byte is not confined to the address string")
    return rows


CORPUS = _corpus()
DIGESTS = {name: hashlib.sha256(blob).hexdigest() for name, blob in CORPUS.items()}


def _rows(findings):
    out = []
    for finding in findings:
        if isinstance(finding, dict):
            out.append((finding["name"], finding["status"], finding["observed"], finding["expected"],
                        list(finding["source_pdf_pages"])))
        else:
            out.append((finding.name, finding.status, finding.observed, finding.expected,
                        list(finding.source_pdf_pages)))
    return out


def _stage_map(stages):
    mapped = {}
    for stage in stages:
        if isinstance(stage, dict):
            mapped[stage["id"]] = (stage["gate"], stage["status"], stage["findings"])
        else:
            mapped[stage.id] = (stage.gate, stage.status, stage.findings)
    return mapped


def _assert_report(report, expected, v011_status, exit_code, file_sha):
    """Fail closed: an error row is a fail, and every other stage stays unexecuted."""
    if not expected:
        pytest.fail("empty finding list")
    assert report["passed"] is False
    assert report["exit_code"] == exit_code
    assert report["exit_code"] != 0
    assert report["target_sha256"] == file_sha
    assert report["notes"] == [NOTE]
    stages = _stage_map(report["stages"])
    assert "V011" in stages
    _gate, status, findings = stages.pop("V011")
    assert status == v011_status
    assert _rows(findings) == expected
    if v011_status == "fail":
        assert findings and all(
            (row["status"] if isinstance(row, dict) else row.status) == "fail" for row in findings)
        assert all(name != "schema" for name, *_rest in expected)
        assert not any(status_name in ("pass", "not_run") for _name, status_name, *_rest in expected)
    else:
        assert [name for name, status_name, *_rest in expected if status_name == "pass"] == [
            "imageBase64", "Glasses", "schema"]
    assert stages, "report dropped every stage except V011"
    for stage_id, (gate, status, findings) in stages.items():
        assert status == "not_run", stage_id
        assert findings == []
        if gate == "blocking":
            assert status != "pass"


def _write_input(tmp_path, name, data) -> Path:
    input_dir = tmp_path / "input"
    report_dir = tmp_path / "report"
    output_dir = tmp_path / "output"
    for directory in (input_dir, report_dir, output_dir):
        directory.mkdir()
    path = input_dir / f"SM_{name}.geojson"
    assert path.stem.endswith("_Ground") is False
    path.write_bytes(data)
    roles = [input_dir.resolve(), report_dir.resolve(), output_dir.resolve(), tmp_path.resolve()]
    assert len(set(roles)) == 4
    assert not any(report_dir.iterdir())
    assert not any(output_dir.iterdir())
    return path


def _cli(path: Path):
    return subprocess.run(
        [sys.executable, str(CLI), str(path), "--profile", "vpm", "--json"],
        capture_output=True, cwd=ROOT, timeout=60, check=False)


def test_corpus_is_frozen_raw_bytes():
    assert set(CORPUS) == set(CASES)
    assert all(DIGESTS.values())
    clean = CORPUS["clean_utf8"]
    assert CORPUS["utf8_bom"] == b"\xef\xbb\xbf" + clean
    assert CORPUS["utf16_bom"].startswith(b"\xff\xfe")
    assert CORPUS["utf16_bom"].decode("utf-16") == clean.decode("utf-8")
    address_at = CORPUS["invalid_utf8"].find(b'"address":"')
    assert address_at > 0 and CORPUS["invalid_utf8"][address_at + len(b'"address":"')] == 0xFF
    assert b"\\u0061ddress" in CORPUS["duplicate_address"]
    assert CORPUS["duplicate_type"].count(b'"type":"FeatureCollection"') == 2
    assert {name: hashlib.sha256(blob).hexdigest() for name, blob in CORPUS.items()} == DIGESTS


@pytest.mark.parametrize("name", list(CASES))
def test_row_agrees_across_findings_validate_and_cli(tmp_path, name):
    data = CORPUS[name]
    expected, v011_status, exit_code = CASES[name]
    assert data and hashlib.sha256(data).hexdigest() == DIGESTS[name]
    path = _write_input(tmp_path, name, data)
    file_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    assert file_sha == DIGESTS[name]

    findings = geojson_findings(data, PROFILE, ground=False)
    assert hashlib.sha256(data).hexdigest() == DIGESTS[name]
    assert _rows(findings) == expected

    report = validate_package.validate(path, "vpm", PROFILES)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == file_sha
    assert _rows(next(stage.findings for stage in report.stages if stage.id == "V011")) == _rows(findings)
    _assert_report(report.to_dict(), expected, v011_status, exit_code, file_sha)

    completed = _cli(path)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == file_sha
    assert completed.stderr == b""
    assert completed.returncode == exit_code
    payload = json.loads(completed.stdout.decode("utf-8"))
    assert _rows(next(stage["findings"] for stage in payload["stages"] if stage["id"] == "V011")) == _rows(findings)
    _assert_report(payload, expected, v011_status, exit_code, file_sha)
    assert sorted(item.name for item in path.parent.iterdir()) == [path.name]
    assert not any((tmp_path / "report").iterdir())
    assert not any((tmp_path / "output").iterdir())
