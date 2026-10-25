"""Legacy characterization of escaped lone surrogates in GeoJSON diagnostics (new-case, Pattern: new-case).

Pins CURRENT behaviour from docs/research/geojson-surrogate-report-encoding-boundary.md (PR #695):

* a JSON escape ``\\uD800`` / ``\\uDC00`` as a material key under a non-dict Glasses value parses, is
  copied into the ``Glasses entry`` observed text, and the diagnostic report object is built
  (passed=false, exit_code=1), but ``json.dumps(ensure_ascii=False)`` keeps the lone surrogate, strict
  UTF-8 encoding raises UnicodeEncodeError, and the real ``--profile vpm --json`` CLI exits 1 with
  zero stdout bytes and a UnicodeEncodeError on stderr (the report is lost);
* the same entry under an ASCII key, a Cyrillic key or a valid escaped pair emits a complete UTF-8 report;
* a lone surrogate only in ``developer`` never reaches a finding: CLI rc 2, valid UTF-8 JSON.

This is characterization of legacy behaviour, NOT desired Unicode acceptance or delivery policy.
Escape-versus-parser-rejection and the encoder repair stay user decisions. Self-contained synthetic
ASCII-escaped fixtures, generated JPEG, no C:/x dependency.
"""
import base64
import json
import os
import subprocess
import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from twinqa.io import json_bytes
from twinqa.profiles import load_profiles

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "tools" / "qa" / "validate_package.py"
sys.path.insert(0, str(ROOT / "tools" / "qa"))
import validate_package  # noqa: E402

PROFILES = load_profiles()
KEYS = PROFILES.vpm["geojson"]["properties_keys"]


def _jpeg_b64() -> str:
    buf = BytesIO()
    Image.new("RGB", (256, 256), (200, 200, 200)).save(buf, "JPEG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


IMAGE = _jpeg_b64()
GOOD_GLASS = ('{"M_Address_MainGlass_1":{"color_RGB":{"Red":1,"Green":2,"Blue":3},'
              '"transparency":0.5,"refraction":1.5,"roughness":0.5,"metallicity":0.5}}')


def _geojson(glasses_json: str, developer_json: str = '"value"') -> bytes:
    props = {k: "synthetic" for k in KEYS}
    props.update(FNO_code="123456", other="", act_AGR="", imageBase64=IMAGE)
    body = json.dumps(props, ensure_ascii=True)
    body = body.replace('"developer": "synthetic"', '"developer": ' + developer_json)
    text = ('{"type":"FeatureCollection","features":[{"type":"ObjectFeature",'
            '"geometry":{"type":"Point","coordinates":[12345.678,6789.012]},'
            '"properties":' + body + ',"Glasses":[' + glasses_json + ']}]}\n')
    data = text.encode("ascii")  # raises if anything non-ASCII slipped in
    return data


def _entry(key_escape: str) -> bytes:
    return _geojson('{"' + key_escape + '":1}')


def _write(tmp_path, name, data) -> Path:
    p = tmp_path / f"SM_{name}.geojson"
    p.write_bytes(data)
    return p


def _cli(path: Path):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8:strict"}
    return subprocess.run([sys.executable, str(CLI), str(path), "--profile", "vpm", "--json"],
                          capture_output=True, cwd=ROOT, timeout=180, env=env)


def _v011(report: dict):
    return next(s for s in report["stages"] if s["id"] == "V011")


def _entry_findings(report: dict):
    return [f for f in _v011(report)["findings"] if f["name"] == "Glasses entry"]


LONE = {"high": ("\\uD800", 55296), "low": ("\\uDC00", 56320)}


@pytest.mark.parametrize("which", ["high", "low"])
def test_legacy_lone_surrogate_key_loses_report(tmp_path, which):
    escape, cp = LONE[which]
    p = _write(tmp_path, which, _entry(escape))
    before = p.read_bytes()
    assert b"\\u" in before and max(before) < 128

    report = validate_package.validate(p, None, PROFILES)
    assert report.passed is False and report.exit_code == 1
    d = report.to_dict()
    (entry,) = _entry_findings(d)
    assert entry["status"] == "fail"
    assert [ord(c) for c in entry["observed"]] == [cp, 58, 32, 49]

    text = json.dumps(d, ensure_ascii=False, indent=2)
    assert isinstance(text, str) and escape not in text and chr(cp) in text
    with pytest.raises(UnicodeEncodeError):
        text.encode("utf-8")
    with pytest.raises(UnicodeEncodeError):
        json_bytes(d)

    r = _cli(p)
    assert r.returncode == 1
    assert r.stdout == b""
    assert b"UnicodeEncodeError" in r.stderr
    assert p.read_bytes() == before


@pytest.mark.parametrize("name,escape,expected", [
    ("ascii", "M_Address_MainGlass_1", [77, 95, 65, 100, 100, 114, 101, 115, 115, 95, 77, 97, 105,
                                       110, 71, 108, 97, 115, 115, 95, 49, 58, 32, 49]),
    ("cyrillic", "\\u0421\\u0442\\u0435\\u043a\\u043b\\u043e", [1057, 1090, 1077, 1082, 1083, 1086, 58, 32, 49]),
    ("pair", "\\uD800\\uDC00", [65536, 58, 32, 49]),
])
def test_legacy_non_lone_key_emits_report(tmp_path, name, escape, expected):
    p = _write(tmp_path, name, _entry(escape))
    r = _cli(p)
    assert r.returncode == 1
    assert r.stderr == b""
    text = r.stdout.decode("utf-8", errors="strict")  # raw bytes decode strictly before parsing
    report = json.loads(text)
    assert report["passed"] is False and report["exit_code"] == 1
    (entry,) = _entry_findings(report)
    assert [ord(c) for c in entry["observed"]] == expected
    assert not any(0xD800 <= ord(c) <= 0xDFFF for c in text)
    json_bytes(report)  # strict UTF-8 round-trip succeeds


def test_legacy_lone_surrogate_in_developer_stays_out_of_findings(tmp_path):
    data = _geojson(GOOD_GLASS, developer_json='"\\uD800"')
    p = _write(tmp_path, "dev", data)
    assert b"\\uD800" in data

    from twinqa.io import read_json
    doc = read_json(data)
    assert [ord(c) for c in doc["features"][0]["properties"]["developer"]] == [55296]

    r = _cli(p)
    assert r.returncode == 2
    assert r.stderr == b""
    text = r.stdout.decode("utf-8", errors="strict")
    report = json.loads(text)
    assert report["passed"] is False and report["exit_code"] == 2
    v011 = _v011(report)
    assert v011["status"] == "pass"
    assert all(f["status"] == "pass" for f in v011["findings"])
    assert not any(0xD800 <= ord(c) <= 0xDFFF for c in text)
    assert [s["status"] for s in report["stages"] if s["id"] != "V011"].count("not_run") >= 1
