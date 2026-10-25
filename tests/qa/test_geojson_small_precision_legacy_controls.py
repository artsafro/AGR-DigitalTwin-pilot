"""new-case: characterization of measured legacy behavior; a legacy schema pass is not approved delivery or a precision-policy decision.

Pins the measured V011 split for small finite GeoJSON coordinates (PKG-19 syntax,
PKG-24 three-decimal insertion point as ``_decimals`` implements it today). A finite
token whose ``repr`` contains an exponent still reaches ``schema: pass``. Scale 4
still reviews. Underflow to ±0 also reaches ``schema: pass``. No numerical-policy fix.
"""
import base64
import hashlib
import json
import math
import subprocess
import sys
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

import twinqa.geojson as geo
from twinqa.geojson import _decimals, geojson_findings
from twinqa.io import read_json
from twinqa.profiles import load_profiles

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "tools" / "qa" / "validate_package.py"
sys.path.insert(0, str(ROOT / "tools" / "qa"))
import validate_package  # noqa: E402

PROFILES = load_profiles()
PROFILE = PROFILES.vpm
KEYS = PROFILE["geojson"]["properties_keys"]
OTHER_X = "6789.012"
SCHEMA_PASS = (("imageBase64", "pass"), ("Glasses", "pass"), ("schema", "pass"))
PRECISION_REVIEW = (
    ("coordinates precision", "review"),
    ("imageBase64", "pass"),
    ("Glasses", "pass"),
)

# Frozen x-axis tokens. Expected ( _decimals, verdict ) is the measured legacy result.
X_TOKENS = (
    "0", "-0.0", "0.001", "1e-3", "0.0001", "1e-4", "0.000001", "1e-6",
    "0.0000001", "1e-7", "-1e-7", "1e-308", "1e-324", "1e-400", "-1e-400",
    "12345.678", "12345.6789",
)
EXPECTED = {
    "0": (0, "schema"),
    "-0.0": (0, "schema"),
    "0.001": (3, "schema"),
    "1e-3": (3, "schema"),
    "0.0001": (4, "review"),
    "1e-4": (4, "review"),
    "0.000001": (0, "schema"),
    "1e-6": (0, "schema"),
    "0.0000001": (0, "schema"),
    "1e-7": (0, "schema"),
    "-1e-7": (0, "schema"),
    "1e-308": (0, "schema"),
    "1e-324": (0, "schema"),
    "1e-400": (0, "schema"),
    "-1e-400": (0, "schema"),
    "12345.678": (3, "schema"),
    "12345.6789": (4, "review"),
}
UNDERFLOW_TOKENS = ("1e-324", "1e-400", "-1e-400")
TRUE_ZERO_TOKENS = ("0", "-0.0")
SCALE7_HEX = "0x1.ad7f29abcaf48p-24"
SCALE4_HEX = "0x1.a36e2eb1c432dp-14"
SUBNORMAL_HEX = "0x0.730d67819e8d2p-1022"


def _jpeg_b64() -> str:
    buf = BytesIO()
    Image.new("RGB", (256, 256), (120, 130, 140)).save(buf, "JPEG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


IMAGE_B64 = _jpeg_b64()


def _ground(role: str) -> bool:
    if role == "oks":
        return False
    if role == "ground":
        return True
    raise AssertionError(f"unknown role {role}")


def _stem(role: str) -> str:
    if role == "oks":
        return "synthetic_oks"
    if role == "ground":
        return "synthetic_Ground"
    raise AssertionError(f"unknown role {role}")


def _properties() -> dict:
    props = {key: "synthetic" for key in KEYS}
    props["FNO_code"] = "123 456"
    props["act_AGR"] = "synthetic-act"
    props["name"] = "synthetic"
    props["imageBase64"] = IMAGE_B64
    return props


def _bytes(x_token: str, y_token: str = OTHER_X) -> bytes:
    """Inject raw coordinate tokens. Floats are never serialized into those two slots."""
    doc = {
        "type": "FeatureCollection",
        "features": [{
            "type": "ObjectFeature",
            "geometry": {"type": "Point", "coordinates": ["__COORD_X__", "__COORD_Y__"]},
            "properties": _properties(),
            "Glasses": [],
        }],
    }
    text = json.dumps(doc, ensure_ascii=False)
    if text.count('"__COORD_X__"') != 1 or text.count('"__COORD_Y__"') != 1:
        raise AssertionError("coordinate placeholders were not unique")
    text = text.replace('"__COORD_X__"', x_token, 1).replace('"__COORD_Y__"', y_token, 1)
    fragment = f'"coordinates": [{x_token}, {y_token}]'
    if fragment not in text:
        raise AssertionError(f"raw tokens were not injected: {fragment}")
    return text.encode("utf-8")


def _coords(x_token: str, y_token: str = OTHER_X):
    data = _bytes(x_token, y_token)
    coords = read_json(data)["features"][0]["geometry"]["coordinates"]
    if not (isinstance(coords, list) and len(coords) == 2):
        raise AssertionError(coords)
    return data, coords


def _pairs(data: bytes, role: str):
    findings = geojson_findings(data, PROFILE, ground=_ground(role))
    return tuple((finding.name, finding.status) for finding in findings), findings


def _assert_axis(role: str, token: str, *, axis: str, other: str, decimals: int, kind: str):
    if axis == "x":
        x_token, y_token, index = token, other, 0
    elif axis == "y":
        x_token, y_token, index = other, token, 1
    else:
        raise AssertionError(axis)
    data, coords = _coords(x_token, y_token)
    parsed = coords[index]
    assert _decimals(parsed) == decimals
    assert _decimals(coords[1 - index]) == 3
    sign = -1.0 if token.startswith("-") else 1.0
    assert math.copysign(1.0, float(parsed)) == sign
    pairs, findings = _pairs(data, role)
    if kind == "schema":
        assert pairs == SCHEMA_PASS
    elif kind == "review":
        assert pairs == PRECISION_REVIEW
        assert findings[0].observed == repr(coords)
        assert all(finding.name != "schema" for finding in findings)
    else:
        raise AssertionError(kind)
    return parsed, findings


def _assert_schema_pass(token: str, y_token: str = OTHER_X):
    pairs, _findings = _pairs(_bytes(token, y_token), "oks")
    assert pairs == SCHEMA_PASS


def _strict_json(text: str):
    def reject(name):
        raise ValueError(f"nonfinite JSON constant {name}")

    return json.loads(text, parse_constant=reject)


def test_frozen_corpus_is_closed():
    assert X_TOKENS == (
        "0", "-0.0", "0.001", "1e-3", "0.0001", "1e-4", "0.000001", "1e-6",
        "0.0000001", "1e-7", "-1e-7", "1e-308", "1e-324", "1e-400", "-1e-400",
        "12345.678", "12345.6789",
    )
    assert set(EXPECTED) == set(X_TOKENS)
    assert len(X_TOKENS) == len(set(X_TOKENS))
    assert all(token in X_TOKENS for token in UNDERFLOW_TOKENS + TRUE_ZERO_TOKENS)


def test_synthetic_document_contract():
    doc = read_json(_bytes("12345.678"))
    feature = doc["features"][0]
    assert doc["type"] == "FeatureCollection"
    assert feature["type"] == "ObjectFeature"
    assert feature["geometry"]["type"] == "Point"
    assert feature["Glasses"] == []
    props = feature["properties"]
    assert set(props) == set(KEYS)
    assert props["act_AGR"] == "synthetic-act"
    assert props["name"] == "synthetic"
    assert props["FNO_code"] == "123 456"
    digits = props["FNO_code"].replace(" ", "")
    assert digits.isdigit() and len(digits) == 6
    raw = base64.b64decode(props["imageBase64"], validate=True)
    with Image.open(BytesIO(raw)) as img:
        img.load()
        assert (img.format, img.size) == ("JPEG", (256, 256))


def test_coordinates_are_raw_tokens_not_serialized_floats():
    text = _bytes("1e-7").decode("utf-8")
    start = text.index('"coordinates": ')
    fragment = text[start:text.index("]", start) + 1]
    assert fragment == '"coordinates": [1e-7, 6789.012]'
    assert "1e-07" not in fragment
    signed = _bytes("-1e-400").decode("utf-8")
    assert '"coordinates": [-1e-400, 6789.012]' in signed
    assert hashlib.sha256(_bytes("1e-7")).digest() != hashlib.sha256(_bytes("0.0000001")).digest()


@pytest.mark.parametrize("role", ["oks", "ground"])
@pytest.mark.parametrize("token", X_TOKENS)
def test_x_token_legacy_verdict(role, token):
    decimals, kind = EXPECTED[token]
    _assert_axis(role, token, axis="x", other=OTHER_X, decimals=decimals, kind=kind)


@pytest.mark.parametrize("role", ["oks", "ground"])
def test_scale7_spellings_share_nonzero_hex_and_schema_pass(role):
    parsed = {}
    for token in ("1e-7", "0.0000001"):
        value, _findings = _assert_axis(
            role, token, axis="x", other=OTHER_X, decimals=0, kind="schema")
        parsed[token] = value
        assert value != 0.0
    assert parsed["1e-7"].hex() == parsed["0.0000001"].hex() == SCALE7_HEX


@pytest.mark.parametrize("role", ["oks", "ground"])
def test_scale4_reviews_with_observed_coordinates(role):
    parsed = {}
    for token in ("1e-4", "0.0001"):
        value, findings = _assert_axis(
            role, token, axis="x", other=OTHER_X, decimals=4, kind="review")
        parsed[token] = value
        assert findings[0].name == "coordinates precision"
        assert findings[0].status == "review"
        assert findings[0].observed == repr(read_json(_bytes(token))["features"][0]["geometry"]["coordinates"])
    assert parsed["1e-4"].hex() == parsed["0.0001"].hex() == SCALE4_HEX


@pytest.mark.parametrize("role", ["oks", "ground"])
def test_three_decimal_passes_and_four_decimal_reviews(role):
    _assert_axis(role, "12345.678", axis="x", other=OTHER_X, decimals=3, kind="schema")
    _assert_axis(role, "12345.6789", axis="x", other=OTHER_X, decimals=4, kind="review")


@pytest.mark.parametrize("role", ["oks", "ground"])
def test_subnormal_1e308_is_nonzero_and_schema_pass(role):
    value, _findings = _assert_axis(
        role, "1e-308", axis="x", other=OTHER_X, decimals=0, kind="schema")
    assert type(value) is float
    assert value != 0.0
    assert abs(value) < sys.float_info.min
    assert value.hex() == SUBNORMAL_HEX
    assert _decimals(value) == 0


@pytest.mark.parametrize("role", ["oks", "ground"])
@pytest.mark.parametrize("token,hex_text", [
    ("1e-324", "0x0.0p+0"),
    ("1e-400", "0x0.0p+0"),
    ("-1e-400", "-0x0.0p+0"),
])
def test_underflow_parses_signed_zero_and_schema_pass(role, token, hex_text):
    value, _findings = _assert_axis(
        role, token, axis="x", other=OTHER_X, decimals=0, kind="schema")
    assert type(value) is float
    assert value == 0.0
    assert value.hex() == hex_text
    if token.startswith("-"):
        assert math.copysign(1.0, value) < 0
    else:
        assert math.copysign(1.0, value) > 0


@pytest.mark.parametrize("role", ["oks", "ground"])
def test_decimal_token_distinguishes_underflow_from_true_zero(role):
    """``Decimal(raw token)`` is the oracle. ``_decimals`` is not consulted."""
    for token in UNDERFLOW_TOKENS:
        exact = Decimal(token)
        _data, coords = _coords(token)
        parsed = coords[0]
        assert exact != 0
        assert parsed == 0.0
        assert type(parsed) is float
    for token in TRUE_ZERO_TOKENS:
        exact = Decimal(token)
        _data, coords = _coords(token)
        parsed = coords[0]
        assert exact == 0
        assert parsed == 0.0
    assert type(_coords("0")[1][0]) is int
    assert _coords("-0.0")[1][0].hex() == "-0x0.0p+0"
    assert _coords("1e-400")[1][0].hex() == "0x0.0p+0"
    assert _coords("-1e-400")[1][0].hex() == "-0x0.0p+0"


@pytest.mark.parametrize("role", ["oks", "ground"])
def test_y_axis_1e7_schema_pass(role):
    value, _findings = _assert_axis(
        role, "1e-7", axis="y", other="12345.678", decimals=0, kind="schema")
    assert value.hex() == SCALE7_HEX
    assert value != 0.0
    text = _bytes("12345.678", "1e-7").decode("utf-8")
    assert '"coordinates": [12345.678, 1e-7]' in text


@pytest.mark.parametrize("role,x_token,y_token,v011_status", [
    ("oks", "12345.678", OTHER_X, "pass"),
    ("oks", "12345.6789", OTHER_X, "review"),
    ("oks", "1e-7", OTHER_X, "pass"),
    ("oks", "-1e-400", OTHER_X, "pass"),
    ("ground", "12345.678", OTHER_X, "pass"),
    ("ground", "1e-4", OTHER_X, "review"),
    ("ground", "1e-7", OTHER_X, "pass"),
    ("ground", "1e-400", OTHER_X, "pass"),
], ids=[
    "clean", "review", "exponent", "underflow",
    "ground-clean", "ground-review", "ground-exponent", "ground-underflow",
])
def test_validate_v011_matches_findings_and_other_blocking_stages_not_run(
        tmp_path, role, x_token, y_token, v011_status):
    data = _bytes(x_token, y_token)
    path = tmp_path / f"{_stem(role)}.geojson"
    path.write_bytes(data)
    assert path.stem.endswith("_Ground") is (role == "ground")
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    report = validate_package.validate(path, "vpm", PROFILES)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert report.passed is False
    assert report.exit_code == 2
    assert "single GeoJSON: only V011 applies" in report.notes
    v011 = [stage for stage in report.stages if stage.id == "V011"]
    assert len(v011) == 1 and v011[0].status == v011_status
    direct = geojson_findings(data, PROFILE, ground=_ground(role))
    assert [(f.name, f.status, f.observed) for f in v011[0].findings] == [
        (f.name, f.status, f.observed) for f in direct]
    rest = [stage for stage in report.stages if stage.gate == "blocking" and stage.id != "V011"]
    assert len(rest) == 11
    assert {stage.status for stage in rest} == {"not_run"}


def _cli(path: Path):
    return subprocess.run(
        [sys.executable, str(CLI), str(path), "--profile", "vpm", "--json"],
        capture_output=True, cwd=ROOT, timeout=120)


def test_strict_json_rejects_nan():
    with pytest.raises(ValueError):
        _strict_json("NaN")
    with pytest.raises(ValueError):
        _strict_json("-Infinity")


@pytest.mark.parametrize("x_token,y_token,v011_status", [
    ("12345.678", OTHER_X, "pass"),
    ("12345.6789", OTHER_X, "review"),
    ("1e-7", OTHER_X, "pass"),
    ("-1e-400", OTHER_X, "pass"),
], ids=["three-decimal", "four-decimal", "1e-7", "signed-underflow"])
def test_cli_v011_strict_json(tmp_path, x_token, y_token, v011_status):
    data = _bytes(x_token, y_token)
    path = tmp_path / "synthetic_oks.geojson"
    path.write_bytes(data)
    before = path.read_bytes()
    result = _cli(path)
    assert path.read_bytes() == before
    assert hashlib.sha256(path.read_bytes()).hexdigest() == hashlib.sha256(before).hexdigest()
    stdout = result.stdout.decode("utf-8")
    stderr = result.stderr.decode("utf-8")
    assert "Traceback" not in stderr
    report = _strict_json(stdout)
    assert isinstance(report["code_commit"], str)
    v011 = [stage for stage in report["stages"] if stage["id"] == "V011"]
    assert len(v011) == 1 and v011[0]["status"] == v011_status
    direct = geojson_findings(data, PROFILE, ground=False)
    assert [(f["name"], f["status"], f["observed"]) for f in v011[0]["findings"]] == [
        (f.name, f.status, f.observed) for f in direct]
    assert report["passed"] is False
    assert result.returncode == 2
    assert report["exit_code"] == 2
    rest = [stage for stage in report["stages"] if stage["gate"] == "blocking" and stage["id"] != "V011"]
    assert len(rest) == 11
    assert {stage["status"] for stage in rest} == {"not_run"}


def test_mutant_large_decimals_on_every_coordinate_is_detected(monkeypatch):
    tokens = ("12345.678", "1e-7", "-1e-400")
    legacy = {token: _pairs(_bytes(token), "oks")[0] for token in tokens}
    assert all(pairs == SCHEMA_PASS for pairs in legacy.values())
    original = geo._decimals

    def large(_value):
        return 12

    monkeypatch.setattr(geo, "_decimals", large)
    try:
        assert geo._decimals is not original
        for token in tokens:
            assert geo._decimals(0) == 12
            mutated = _pairs(_bytes(token), "oks")[0]
            assert mutated != legacy[token]
            assert mutated == PRECISION_REVIEW
            with pytest.raises(AssertionError):
                _assert_schema_pass(token)
    finally:
        monkeypatch.undo()
    assert geo._decimals is original
    for token in tokens:
        assert _pairs(_bytes(token), "oks")[0] == legacy[token]
        _assert_schema_pass(token)


def test_mutant_exponent_repr_only_is_detected(monkeypatch):
    legacy_exponent = _pairs(_bytes("1e-7"), "oks")[0]
    legacy_fixed = _pairs(_bytes("0.0000001"), "oks")[0]
    legacy_control = _pairs(_bytes("12345.678"), "oks")[0]
    legacy_underflow = _pairs(_bytes("-1e-400"), "oks")[0]
    assert legacy_exponent == legacy_fixed == legacy_control == legacy_underflow == SCHEMA_PASS
    original = geo._decimals

    def exponent_only(value):
        if "e" in repr(float(value)):
            return 12
        return original(value)

    monkeypatch.setattr(geo, "_decimals", exponent_only)
    try:
        assert geo._decimals(1e-7) == 12
        assert "e" not in repr(float(12345.678))
        assert geo._decimals(12345.678) == original(12345.678) == 3
        for token in ("1e-7", "0.0000001"):
            mutated = _pairs(_bytes(token), "oks")[0]
            assert mutated != legacy_exponent
            assert mutated == PRECISION_REVIEW
            with pytest.raises(AssertionError):
                _assert_schema_pass(token)
        assert _pairs(_bytes("12345.678"), "oks")[0] == legacy_control
        assert _pairs(_bytes("-1e-400"), "oks")[0] == legacy_underflow
        _assert_schema_pass("12345.678")
        _assert_schema_pass("-1e-400")
    finally:
        monkeypatch.undo()
    assert geo._decimals is original
    assert _pairs(_bytes("1e-7"), "oks")[0] == legacy_exponent
    assert _pairs(_bytes("0.0000001"), "oks")[0] == legacy_fixed
    _assert_schema_pass("1e-7")
    _assert_schema_pass("0.0000001")
