"""Current GeoJSON coordinate overflow caller controls (new-case).

Characterization only. A numeric token such as ``1e400`` becomes a non-finite float in
``twinqa.io.read_json`` and still reaches ``schema: pass`` (legacy gap, not approval).
The literals ``Infinity`` / ``-Infinity`` / ``NaN`` raise ``ValueError`` and a ``JSON``
fail. This file adopts neither proposed fix: parser-boundary rejection versus a
field-level finiteness check, and fail versus review, stay user decisions.

PKG-19 syntax and PKG-24 insertion-point precision are the rows under test. Glasses
optical matrices and the AGR contract parser are out of scope.
"""
import base64
import hashlib
import json
import math
import subprocess
import sys
from dataclasses import asdict
from io import BytesIO
from pathlib import Path

from PIL import Image

import twinqa.geojson as geo
import twinqa.io as io
from twinqa.geojson import geojson_findings
from twinqa.profiles import load_profiles

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "tools" / "qa" / "validate_package.py"
sys.path.insert(0, str(ROOT / "tools" / "qa"))
import validate_package  # noqa: E402

PRODUCTION = (ROOT / "src" / "twinqa" / "geojson.py", ROOT / "src" / "twinqa" / "io.py")
PRODUCTION_SHA256 = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in PRODUCTION}

PROFILE = load_profiles().vpm
KEYS = PROFILE["geojson"]["properties_keys"]
DECIMAL_PLACES = PROFILE["geojson"]["coordinates"]["decimal_places"]
PASS_FINDINGS = (("imageBase64", "pass"), ("Glasses", "pass"), ("schema", "pass"))
AXES = (0, 1)
SIGNS = (1, -1)
ROLES = ("oks", "ground")
# 1e309 is the first power of ten that overflows to inf; 1e400 is the documented witness.
OVERFLOW_EXPONENTS = (400, 309)
LITERALS = ("Infinity", "-Infinity", "NaN")
_WHOLE = {0: "12345", 1: "6789"}
_FRAC = {0: "67890123", 1: "01234567"}


def _jpeg_b64() -> str:
    buf = BytesIO()
    Image.new("RGB", (256, 256), (120, 130, 140)).save(buf, "JPEG")
    raw = buf.getvalue()
    assert raw[:2] == b"\xff\xd8" and raw[-2:] == b"\xff\xd9"
    with Image.open(BytesIO(raw)) as img:
        assert img.format == "JPEG" and img.size == (256, 256)
    return base64.b64encode(raw).decode("ascii")


def _props() -> dict:
    props = {key: "synthetic" for key in KEYS}
    props.update(FNO_code="123 456", other="", act_AGR="synthetic", imageBase64=_jpeg_b64())
    assert props["act_AGR"] not in ("", None)
    return props


PROPS = _props()
_TEMPLATE = json.dumps({
    "type": "FeatureCollection",
    "features": [{
        "type": "ObjectFeature",
        "geometry": {"type": "Point", "coordinates": ["<X>", "<Y>"]},
        "properties": PROPS,
        "Glasses": [],
    }],
}, ensure_ascii=False)
assert _TEMPLATE.count('"<X>"') == 1 and _TEMPLATE.count('"<Y>"') == 1


def _decimal_token(axis: int, sign: int, places: int) -> str:
    body = _WHOLE[axis] + "." + _FRAC[axis][:places]
    assert len(body.split(".")[1]) == places
    return body if sign > 0 else "-" + body


def _pair(axis: int, sign: int, places: int) -> tuple[str, str]:
    tokens = [_decimal_token(0, 1, DECIMAL_PLACES), _decimal_token(1, 1, DECIMAL_PLACES)]
    tokens[axis] = _decimal_token(axis, sign, places)
    return tokens[0], tokens[1]


def render(x_token: str, y_token: str) -> bytes:
    """Splice raw JSON number tokens. Never ``json.dumps`` a non-finite float."""
    text = _TEMPLATE.replace('"<X>"', x_token, 1).replace('"<Y>"', y_token, 1)
    assert '"<X>"' not in text and '"<Y>"' not in text
    expect = f'"coordinates": [{x_token}, {y_token}]'
    assert expect in text
    return text.encode("utf-8")


def _ground(role: str) -> bool:
    return role == "ground"


def _pairs(findings) -> list[tuple[str, str]]:
    return [(finding.name, finding.status) for finding in findings]


def _no_bare_nonfinite(value) -> None:
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return
    if isinstance(value, float):
        assert math.isfinite(value), "diagnostic payload leaked a non-finite float"
        return
    if isinstance(value, dict):
        for item in value.values():
            _no_bare_nonfinite(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _no_bare_nonfinite(item)


def _assert_strict_json(findings, report) -> None:
    """Findings and the delivery report stay strict-JSON even when the input was non-finite."""
    payloads = ([asdict(finding) for finding in findings], report.to_dict())
    for payload in payloads:
        text = json.dumps(payload, allow_nan=False)
        json.loads(text, parse_constant=io._reject_constant)
        _no_bare_nonfinite(payload)
    for finding in findings:
        assert isinstance(finding.observed, str) and isinstance(finding.expected, str)
    assert "delivery_passed" not in report.to_dict()


def _write(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def _run(data: bytes, role: str, tmp_path: Path, name: str):
    digest = hashlib.sha256(data).hexdigest()
    findings = list(geojson_findings(data, PROFILE, ground=_ground(role)))
    assert hashlib.sha256(data).hexdigest() == digest
    path = _write(tmp_path, name, data)
    report = validate_package.validate(path, "vpm", load_profiles())
    assert path.read_bytes() == data
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    _assert_strict_json(findings, report)
    others = [stage for stage in report.stages if stage.id != "V011"]
    assert others and all(stage.status == "not_run" and stage.findings == [] for stage in others)
    assert report.passed is False
    assert report.to_dict()["passed"] is False
    return findings, report


def _assert_stage(report, status: str, exit_code: int) -> None:
    v011 = next(stage for stage in report.stages if stage.id == "V011")
    assert v011.status == status
    assert report.exit_code == exit_code
    assert report.to_dict()["exit_code"] == exit_code


def _finite_name(role: str, axis: int, sign: int) -> str:
    stem = "SM_Synthetic_Ground" if role == "ground" else "SM_Synthetic"
    return f"{stem}_a{axis}_s{sign}.geojson"


def _assert_finite(axis: int, sign: int, role: str, tmp_path: Path) -> None:
    """Exactly ``decimal_places`` digits: finite parse and schema pass. Not a silent threshold."""
    assert DECIMAL_PLACES == 3
    x_token, y_token = _pair(axis, sign, DECIMAL_PLACES)
    data = render(x_token, y_token)
    doc = io.read_json(data)
    coords = doc["features"][0]["geometry"]["coordinates"]
    for value in coords:
        if isinstance(value, bool) or not isinstance(value, float) or not math.isfinite(value):
            raise AssertionError(f"finite witness saw {value!r}")
    findings, report = _run(data, role, tmp_path, _finite_name(role, axis, sign))
    assert _pairs(findings) == list(PASS_FINDINGS)
    _assert_stage(report, "pass", 2)


def _assert_overflow(exponent: int, axis: int, sign: int, role: str, tmp_path: Path) -> None:
    """Legacy gap, not approval: a non-finite overflow coordinate still schema-passes."""
    token = f"1e{exponent}" if sign > 0 else f"-1e{exponent}"
    tokens = [_decimal_token(0, 1, DECIMAL_PLACES), _decimal_token(1, 1, DECIMAL_PLACES)]
    tokens[axis] = token
    data = render(tokens[0], tokens[1])
    assert token.encode("ascii") in data and b"Infinity" not in data
    doc = io.read_json(data)
    coords = doc["features"][0]["geometry"]["coordinates"]
    value, other = coords[axis], coords[1 - axis]
    if isinstance(value, bool) or not isinstance(value, float) or math.isfinite(value):
        raise AssertionError(f"overflow witness was not a non-finite float: {value!r}")
    assert math.isinf(value) and ((value > 0) == (sign > 0))
    assert type(other) is float and math.isfinite(other)
    findings, report = _run(data, role, tmp_path, f"SM_Overflow_{role}_e{exponent}_a{axis}_s{sign}.geojson")
    assert _pairs(findings) == list(PASS_FINDINGS)
    assert not any("coordinate" in name.lower() for name, _status in _pairs(findings))
    for finding in findings:
        assert "inf" not in finding.observed.lower() and "nan" not in finding.observed.lower()
    _assert_stage(report, "pass", 2)


def _assert_literal(token: str, axis: int, role: str, tmp_path: Path) -> None:
    tokens = [_decimal_token(0, 1, DECIMAL_PLACES), _decimal_token(1, 1, DECIMAL_PLACES)]
    tokens[axis] = token
    data = render(tokens[0], tokens[1])
    assert token.encode("ascii") in data
    try:
        parsed = io.read_json(data)
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError(f"read_json accepted {token!r}: {parsed!r}")
    assert message == f"Nonfinite value: {token}"
    findings, report = _run(data, role, tmp_path, f"SM_Literal_{role}_a{axis}_{token}.geojson")
    assert _pairs(findings) == [("JSON", "fail")]
    assert not any(name == "schema" for name, _status in _pairs(findings))
    _assert_stage(report, "fail", 1)


def _assert_precision(axis: int, sign: int, role: str, tmp_path: Path) -> None:
    """One digit past the 3-decimal threshold is a review and does not schema-pass."""
    x_token, y_token = _pair(axis, sign, DECIMAL_PLACES + 1)
    varied = (x_token, y_token)[axis]
    assert len(varied.lstrip("-").split(".")[1]) == DECIMAL_PLACES + 1
    data = render(x_token, y_token)
    doc = io.read_json(data)
    coords = doc["features"][0]["geometry"]["coordinates"]
    assert all(type(value) is float and math.isfinite(value) for value in coords)
    findings, report = _run(data, role, tmp_path, f"SM_Precision_{role}_a{axis}_s{sign}.geojson")
    assert _pairs(findings) == [
        ("coordinates precision", "review"),
        ("imageBase64", "pass"),
        ("Glasses", "pass"),
    ]
    assert not any(name == "schema" for name, _status in _pairs(findings))
    _assert_stage(report, "review", 2)


def _assert_bool(axis: int, sign: int, role: str, tmp_path: Path) -> None:
    token = "true" if sign > 0 else "false"
    tokens = [_decimal_token(0, 1, DECIMAL_PLACES), _decimal_token(1, 1, DECIMAL_PLACES)]
    tokens[axis] = token
    data = render(tokens[0], tokens[1])
    doc = io.read_json(data)
    coords = doc["features"][0]["geometry"]["coordinates"]
    assert type(coords[axis]) is bool and coords[axis] is (True if sign > 0 else False)
    findings, report = _run(data, role, tmp_path, f"SM_Bool_{role}_a{axis}_s{sign}.geojson")
    assert _pairs(findings) == [
        ("coordinates", "fail"),
        ("imageBase64", "pass"),
        ("Glasses", "pass"),
    ]
    assert not any(name == "schema" for name, _status in _pairs(findings))
    _assert_stage(report, "fail", 1)


def _assert_cliff(axis: int, sign: int, role: str, tmp_path: Path) -> None:
    """``1e308`` is the last power of ten that stays finite. A non-finite value must not pass here."""
    token = "1e308" if sign > 0 else "-1e308"
    tokens = [_decimal_token(0, 1, DECIMAL_PLACES), _decimal_token(1, 1, DECIMAL_PLACES)]
    tokens[axis] = token
    data = render(tokens[0], tokens[1])
    doc = io.read_json(data)
    value = doc["features"][0]["geometry"]["coordinates"][axis]
    if isinstance(value, bool) or not isinstance(value, float) or not math.isfinite(value):
        raise AssertionError(f"float-threshold witness was not finite: {value!r}")
    findings, report = _run(data, role, tmp_path, f"SM_Cliff_{role}_a{axis}_s{sign}.geojson")
    assert _pairs(findings) == list(PASS_FINDINGS)
    _assert_stage(report, "pass", 2)


def _loop(assert_one, tmp_path: Path) -> int:
    checked = 0
    failures = []
    for axis in AXES:
        for sign in SIGNS:
            for role in ROLES:
                try:
                    assert_one(axis, sign, role, tmp_path)
                except AssertionError as exc:
                    failures.append(f"{role} axis={axis} sign={sign}: {exc}")
                checked += 1
    assert checked == len(AXES) * len(SIGNS) * len(ROLES)
    assert not failures, failures
    return checked


def test_profile_is_the_real_loaded_vpm():
    loaded = load_profiles().vpm
    assert KEYS and KEYS == loaded["geojson"]["properties_keys"]
    assert PROFILE["geojson"]["coordinates"]["decimal_places"] == 3
    assert geo.read_json is io.read_json
    assert geojson_findings is geo.geojson_findings


def test_finite_three_decimals_parser_and_schema_pass(tmp_path):
    assert _loop(_assert_finite, tmp_path) == 8


def test_overflow_schema_pass_is_legacy_gap_not_approval(tmp_path):
    """Both documented ``1e400`` and the exact overflow threshold ``1e309``."""
    checked = 0
    failures = []
    for exponent in OVERFLOW_EXPONENTS:
        for axis in AXES:
            for sign in SIGNS:
                for role in ROLES:
                    try:
                        _assert_overflow(exponent, axis, sign, role, tmp_path)
                    except AssertionError as exc:
                        failures.append(f"1e{exponent} {role} axis={axis} sign={sign}: {exc}")
                    checked += 1
    assert checked == len(OVERFLOW_EXPONENTS) * len(AXES) * len(SIGNS) * len(ROLES)
    assert not failures, failures


def test_literal_infinity_and_nan_are_json_fail(tmp_path):
    checked = 0
    failures = []
    for token in LITERALS:
        for axis in AXES:
            for role in ROLES:
                try:
                    _assert_literal(token, axis, role, tmp_path)
                except AssertionError as exc:
                    failures.append(f"{token} {role} axis={axis}: {exc}")
                checked += 1
    assert checked == len(LITERALS) * len(AXES) * len(ROLES)
    assert not failures, failures


def test_one_past_decimal_threshold_is_precision_review(tmp_path):
    assert _loop(_assert_precision, tmp_path) == 8


def test_bool_coordinate_fails(tmp_path):
    assert _loop(_assert_bool, tmp_path) == 8


def test_float_cliff_1e308_stays_finite(tmp_path):
    """Exactly at the finite side of the overflow threshold; a non-finite value cannot take this pass."""
    assert _loop(_assert_cliff, tmp_path) == 8


def _cli(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), str(path), "--profile", "vpm", "--json"],
        capture_output=True, text=True, encoding="utf-8", cwd=ROOT, timeout=120,
    )


def test_cli_representative_subset(tmp_path):
    """Fresh-process V011. Pass/review exit 2; fail exits 1. ``passed`` is false; no delivery_passed."""
    cases = [
        ("finite", "SM_Finite.geojson", ("12345.678", "6789.012"), "pass", 2, False),
        ("overflow", "SM_Overflow_Ground.geojson", ("1e400", "6789.012"), "pass", 2, True),
        ("infinity", "SM_Infinity.geojson", ("Infinity", "6789.012"), "fail", 1, False),
        ("precision", "SM_Precision_Ground.geojson", ("12345.6789", "6789.012"), "review", 2, False),
        ("bool", "SM_Bool.geojson", ("true", "6789.012"), "fail", 1, False),
    ]
    assert any(name.endswith("_Ground.geojson") for _label, name, *_rest in cases)
    for label, name, tokens, status, exit_code, legacy in cases:
        data = render(*tokens)
        digest = hashlib.sha256(data).hexdigest()
        path = _write(tmp_path, name, data)
        ground = path.stem.endswith("_Ground")
        completed = _cli(path)
        assert path.read_bytes() == data
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        assert "Traceback" not in (completed.stderr or "")
        assert completed.returncode == exit_code
        payload = json.loads(completed.stdout)
        json.dumps(payload, allow_nan=False)
        _no_bare_nonfinite(payload)
        assert "delivery_passed" not in payload
        assert payload["passed"] is False
        assert payload["exit_code"] == exit_code
        assert payload["profile"] == "vpm"
        v011 = next(stage for stage in payload["stages"] if stage["id"] == "V011")
        others = [stage for stage in payload["stages"] if stage["id"] != "V011"]
        assert others and all(stage["status"] == "not_run" and stage["findings"] == [] for stage in others)
        assert v011["status"] == status
        helper = _pairs(geojson_findings(data, PROFILE, ground=ground))
        assert [(item["name"], item["status"]) for item in v011["findings"]] == helper
        if legacy:
            # legacy gap, not approval
            assert helper == list(PASS_FINDINGS)
            assert b"1e400" in data and b"Infinity" not in data
        if label == "infinity":
            assert helper == [("JSON", "fail")]
        if label == "precision":
            assert ("coordinates precision", "review") in helper and not any(n == "schema" for n, _s in helper)
        if label == "bool":
            assert ("coordinates", "fail") in helper and not any(n == "schema" for n, _s in helper)
        if label == "finite":
            parsed = io.read_json(data)["features"][0]["geometry"]["coordinates"]
            assert all(type(value) is float and math.isfinite(value) for value in parsed)


def _production_untouched() -> None:
    for path, digest in PRODUCTION_SHA256.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def _count_failures(calls) -> int:
    failed = 0
    for call in calls:
        try:
            call()
        except AssertionError:
            failed += 1
    return failed


def test_mutation_finite_only_number_breaks_overflow_witnesses(monkeypatch, tmp_path):
    """Process-local stand-in for a field-level finiteness check. Production bytes stay put."""
    original = geo._number

    def finite_only(value):
        return original(value) and math.isfinite(value)

    monkeypatch.setattr(geo, "_number", finite_only)
    calls = [
        (lambda exponent=exponent, axis=axis, sign=sign, role=role: _assert_overflow(
            exponent, axis, sign, role, tmp_path))
        for exponent in OVERFLOW_EXPONENTS
        for axis in AXES
        for sign in SIGNS
        for role in ROLES
    ]
    failed = _count_failures(calls)
    assert failed == len(calls) == 16
    monkeypatch.undo()
    _production_untouched()
    assert _count_failures(calls) == 0


def test_mutation_permissive_parse_constant_breaks_literal_witnesses(monkeypatch, tmp_path):
    """Process-local stand-in for accepting JSON constants in ``read_json``. Production bytes stay put."""

    def permissive(data):
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return json.loads(data, object_pairs_hook=io.unique_pairs, parse_constant=float)

    monkeypatch.setattr(io, "read_json", permissive)
    monkeypatch.setattr(geo, "read_json", permissive)
    calls = [
        (lambda token=token, axis=axis, role=role: _assert_literal(token, axis, role, tmp_path))
        for token in LITERALS
        for axis in AXES
        for role in ROLES
    ]
    failed = _count_failures(calls)
    assert failed == len(calls) == 12
    monkeypatch.undo()
    _production_untouched()
    assert geo.read_json is io.read_json
    assert _count_failures(calls) == 0


def test_production_files_match_the_import_hashes():
    _production_untouched()
