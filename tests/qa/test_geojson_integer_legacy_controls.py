"""new-case: named legacy characterization tests of current behaviour (PR #699 follow-up), not delivery acceptance.

Synthetic OKS and Ground GeoJSON bytes record the measured integer-token behaviour of
read_json, the coordinate helpers, geojson_findings, single-file validate, the VPM JSON
CLI, and a stored one-member VPM ZIP. These witnesses are not a delivery acceptance gate
and do not add a bound, a coercion, or a policy.
"""
import base64
import json
import subprocess
import sys
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

import validate_package as vp
from twinqa.geojson import _decimals, _number, geojson_findings
from twinqa.io import read_json
from twinqa.profiles import load_profiles

PROFILES = load_profiles()
PROFILE = PROFILES.vpm
_VALIDATOR = Path(__file__).resolve().parents[2] / "tools" / "qa" / "validate_package.py"
_STEM = "SM_SynthCtrl"
_X_MARK = "__X__"
_Y_MARK = "__Y__"
_DEV_MARK = "__DEVELOPER__"
_ORD_X = "12345.678"
_ORD_Y = "6789.012"
_DEV_TEXT = "synthetic-developer"


def _measured_runtime_reason() -> str:
    """Skip witnesses whose integer boundary was measured on CPython 3.14.7."""
    if sys.version_info[:2] != (3, 14):
        return f"measured on CPython 3.14, found {sys.version_info[0]}.{sys.version_info[1]}"
    digits = sys.get_int_max_str_digits()
    if digits < 4300:
        return f"sys.get_int_max_str_digits()={digits} < 4300"
    limit = sys.getrecursionlimit()
    if limit < 1000:
        return f"recursion limit {limit} < measured default 1000"
    try:
        finite = float(10**308) != float("inf") and float(-(10**308)) != float("-inf")
    except OverflowError:
        finite = False
    if not finite:
        return "float(10**308) is not finite; measured returning boundary differs"
    try:
        float(10**309)
    except OverflowError:
        return ""
    return "float(10**309) did not raise OverflowError; measured overflow boundary differs"


_RUNTIME_REASON = _measured_runtime_reason()
needs_measured_runtime = pytest.mark.skipif(
    bool(_RUNTIME_REASON),
    reason=_RUNTIME_REASON or "CPython 3.14 integer boundary",
)


def _jpeg_base64() -> str:
    buffer = BytesIO()
    Image.new("RGB", (256, 256), (210, 180, 140)).save(buffer, format="JPEG", quality=30)
    payload = buffer.getvalue()
    image = Image.open(BytesIO(payload))
    assert image.format == "JPEG" and image.size == (256, 256) and image.mode == "RGB"
    return base64.b64encode(payload).decode("ascii")


def _template() -> str:
    keys = PROFILE["geojson"]["properties_keys"]
    props = {key: "synthetic" for key in keys}
    props["act_AGR"] = "synthetic-act"
    props["FNO_code"] = "123456"
    props["imageBase64"] = _jpeg_base64()
    props["developer"] = _DEV_MARK
    props["other"] = ""
    document = {
        "type": "FeatureCollection",
        "features": [{
            "type": "ObjectFeature",
            "properties": props,
            "geometry": {"type": "Point", "coordinates": [_X_MARK, _Y_MARK]},
            "Glasses": [],
        }],
    }
    text = json.dumps(document, ensure_ascii=False)
    assert text.count(f'"{_X_MARK}"') == 1
    assert text.count(f'"{_Y_MARK}"') == 1
    assert text.count(f'"{_DEV_MARK}"') == 1
    return text


_TEMPLATE = _template()


def _digits(zeros: int, negative: bool = False) -> str:
    body = "1" + ("0" * zeros)
    return f"-{body}" if negative else body


def geojson_bytes(x_token: str, y_token: str, developer_token: str | None = None) -> bytes:
    """Substitute raw JSON tokens for placeholders. Integer tokens are never json.dumps'd."""
    text = _TEMPLATE.replace(f'"{_X_MARK}"', x_token, 1).replace(f'"{_Y_MARK}"', y_token, 1)
    if developer_token is None:
        text = text.replace(f'"{_DEV_MARK}"', json.dumps(_DEV_TEXT), 1)
    else:
        text = text.replace(f'"{_DEV_MARK}"', developer_token, 1)
    data = text.encode("utf-8")
    assert _X_MARK.encode("ascii") not in data
    assert _Y_MARK.encode("ascii") not in data
    assert _DEV_MARK.encode("ascii") not in data
    return data


def _read(data: bytes):
    snapshot = data
    try:
        return read_json(data)
    finally:
        assert data == snapshot


def _findings(data: bytes, ground: bool):
    snapshot = data
    try:
        return geojson_findings(data, PROFILE, ground)
    finally:
        assert data == snapshot


def _write_geojson(tmp_path: Path, data: bytes, ground: bool) -> Path:
    name = f"{_STEM}_Ground.geojson" if ground else f"{_STEM}.geojson"
    path = tmp_path / name
    path.write_bytes(data)
    assert path.read_bytes() == data
    return path


def _validate(tmp_path: Path, data: bytes, ground: bool):
    path = _write_geojson(tmp_path, data, ground)
    before = path.read_bytes()
    try:
        return vp.validate(path, "vpm", PROFILES)
    finally:
        assert path.read_bytes() == before


def _run_cli_path(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_VALIDATOR), str(path), "--profile", "vpm", "--json"],
        capture_output=True,
        timeout=60,
        check=False,
    )


def _run_cli(tmp_path: Path, data: bytes, *, ground: bool) -> subprocess.CompletedProcess:
    path = _write_geojson(tmp_path, data, ground)
    before = path.read_bytes()
    proc = _run_cli_path(path)
    assert path.read_bytes() == before
    assert list(tmp_path.glob("*.json")) == []
    return proc


def _reject_constant(name: str):
    raise ValueError(name)


def _parse_report_stdout(raw: bytes) -> dict:
    return json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)


def _assert_schema_pass(findings) -> None:
    assert any(item.name == "schema" and item.status == "pass" for item in findings)
    assert all(item.status == "pass" for item in findings)


def _assert_v011_report(report, *, exit_code: int) -> None:
    stages = {stage.id: stage for stage in report.stages}
    assert stages["V011"].status == "pass"
    assert report.passed is False
    assert report.exit_code == exit_code
    assert report.profile == "vpm"


def _assert_cli_report(proc: subprocess.CompletedProcess, *, exit_code: int) -> dict:
    raw = proc.stdout
    assert proc.returncode == exit_code
    assert proc.stderr == b""
    assert raw.startswith(b"{")
    report = _parse_report_stdout(raw)
    stages = {stage["id"]: stage for stage in report["stages"]}
    assert stages["V011"]["status"] == "pass"
    assert report["passed"] is False
    assert report["exit_code"] == exit_code
    assert report["profile"] == "vpm"
    return report


def _assert_overflow_cli(proc: subprocess.CompletedProcess) -> None:
    raw = proc.stdout
    assert proc.returncode == 1
    assert raw == b""
    assert b"OverflowError" in proc.stderr


def _assert_integer_x(tmp_path: Path, token: str, ground: bool) -> None:
    data = geojson_bytes(token, _ORD_Y)
    assert f"[{token}, {_ORD_Y}]".encode("ascii") in data
    x_value, y_value = _read(data)["features"][0]["geometry"]["coordinates"]
    assert type(x_value) is int and str(x_value) == token
    assert _number(x_value) is True and _decimals(x_value) == 0
    assert type(y_value) is float and _number(y_value) is True and _decimals(y_value) == 3
    _assert_schema_pass(_findings(data, ground))
    _assert_v011_report(_validate(tmp_path, data, ground), exit_code=2)


def test_synthetic_fixture_is_complete_and_shared_by_ground_stem(tmp_path):
    data = geojson_bytes(_ORD_X, _ORD_Y)
    assert b'"act_AGR": "synthetic-act"' in data
    assert b'"FNO_code": "123456"' in data
    assert f"[{_ORD_X}, {_ORD_Y}]".encode("ascii") in data
    image = _read(data)["features"][0]["properties"]["imageBase64"]
    parsed = Image.open(BytesIO(base64.b64decode(image, validate=True)))
    assert parsed.format == "JPEG" and parsed.size == (256, 256) and parsed.mode == "RGB"
    oks = _write_geojson(tmp_path, data, False)
    ground = _write_geojson(tmp_path, data, True)
    assert oks.name == f"{_STEM}.geojson"
    assert ground.name.endswith("_Ground.geojson")
    assert oks.read_bytes() == ground.read_bytes() == data


@pytest.mark.parametrize("ground", [False, True], ids=["oks", "ground"])
def test_ordinary_three_decimal_control(tmp_path, ground):
    data = geojson_bytes(_ORD_X, _ORD_Y)
    x_value, y_value = _read(data)["features"][0]["geometry"]["coordinates"]
    assert type(x_value) is float and type(y_value) is float
    assert _number(x_value) is True and _number(y_value) is True
    assert _decimals(x_value) == 3 and _decimals(y_value) == 3
    _assert_schema_pass(_findings(data, ground))
    _assert_v011_report(_validate(tmp_path, data, ground), exit_code=2)


@pytest.mark.parametrize("ground", [False, True], ids=["oks", "ground"])
def test_small_integer_coordinate(tmp_path, ground):
    _assert_integer_x(tmp_path, "12345", ground)


@needs_measured_runtime
@pytest.mark.parametrize("zeros,negative", [
    (307, False),
    (307, True),
    (308, False),
    (308, True),
], ids=["307-zeros", "307-zeros-negative", "308-zeros", "308-zeros-negative"])
@pytest.mark.parametrize("ground", [False, True], ids=["oks", "ground"])
def test_large_returning_integer_coordinate(tmp_path, zeros, negative, ground):
    _assert_integer_x(tmp_path, _digits(zeros, negative), ground)


@needs_measured_runtime
@pytest.mark.parametrize("axis,zeros,negative", [
    ("x", 309, False),
    ("x", 309, True),
    ("x", 400, False),
    ("x", 400, True),
    ("y", 400, False),
], ids=["x-309-zeros", "x-309-zeros-negative", "x-400-zeros", "x-400-zeros-negative", "y-400-zeros"])
@pytest.mark.parametrize("ground", [False, True], ids=["oks", "ground"])
def test_overflow_integer_coordinate(tmp_path, axis, zeros, negative, ground):
    token = _digits(zeros, negative)
    if axis == "x":
        data = geojson_bytes(token, _ORD_Y)
        assert f"[{token}, {_ORD_Y}]".encode("ascii") in data
    else:
        data = geojson_bytes(_ORD_X, token)
        assert f"[{_ORD_X}, {token}]".encode("ascii") in data
    x_value, y_value = _read(data)["features"][0]["geometry"]["coordinates"]
    offending, ordinary = (x_value, y_value) if axis == "x" else (y_value, x_value)
    assert type(offending) is int and str(offending) == token and _number(offending) is True
    with pytest.raises(OverflowError):
        _decimals(offending)
    assert type(ordinary) is float and _number(ordinary) is True and _decimals(ordinary) == 3
    with pytest.raises(OverflowError):
        _findings(data, ground)
    with pytest.raises(OverflowError):
        _validate(tmp_path, data, ground)


@needs_measured_runtime
@pytest.mark.parametrize("ground", [False, True], ids=["oks", "ground"])
def test_developer_integer_leaves_coordinates_ordinary(tmp_path, ground):
    token = _digits(400)
    assert len(token) == 401
    data = geojson_bytes(_ORD_X, _ORD_Y, developer_token=token)
    assert f'"developer": {token}'.encode("ascii") in data
    loaded = _read(data)
    developer = loaded["features"][0]["properties"]["developer"]
    x_value, y_value = loaded["features"][0]["geometry"]["coordinates"]
    assert type(developer) is int and str(developer) == token
    assert type(x_value) is float and type(y_value) is float
    assert _decimals(x_value) == 3 and _decimals(y_value) == 3
    _assert_schema_pass(_findings(data, ground))
    _assert_v011_report(_validate(tmp_path, data, ground), exit_code=2)


@pytest.mark.parametrize("ground", [False, True], ids=["oks", "ground"])
def test_coordinate_true_fails_coordinates(ground):
    data = geojson_bytes("true", _ORD_Y)
    assert b"[true, 6789.012]" in data
    x_value, y_value = _read(data)["features"][0]["geometry"]["coordinates"]
    assert x_value is True and _number(x_value) is False
    assert type(y_value) is float and _decimals(y_value) == 3
    found = _findings(data, ground)
    assert any(item.name == "coordinates" and item.status == "fail" for item in found)


@pytest.mark.parametrize("ground", [False, True], ids=["oks", "ground"])
def test_infinity_literal_fails_json(ground):
    data = geojson_bytes("Infinity", _ORD_Y)
    assert b"[Infinity, 6789.012]" in data
    with pytest.raises(ValueError):
        _read(data)
    found = _findings(data, ground)
    assert [(item.name, item.status) for item in found] == [("JSON", "fail")]


@pytest.mark.parametrize("ground", [False, True], ids=["oks", "ground"])
def test_exponent_1e400_is_float_and_schema_passes(ground):
    data = geojson_bytes("1e400", _ORD_Y)
    assert b"[1e400, 6789.012]" in data
    x_value, y_value = _read(data)["features"][0]["geometry"]["coordinates"]
    assert type(x_value) is float and _number(x_value) is True and _decimals(x_value) == 0
    assert type(y_value) is float and _decimals(y_value) == 3
    _assert_schema_pass(_findings(data, ground))


@needs_measured_runtime
def test_cli_positive_x_overflow_has_no_report(tmp_path):
    proc = _run_cli(tmp_path, geojson_bytes(_digits(309), _ORD_Y), ground=False)
    raw = proc.stdout
    assert proc.returncode == 1
    assert raw == b""
    assert b"OverflowError" in proc.stderr


@needs_measured_runtime
def test_cli_negative_x_overflow_has_no_report(tmp_path):
    proc = _run_cli(tmp_path, geojson_bytes(_digits(309, True), _ORD_Y), ground=False)
    _assert_overflow_cli(proc)


@needs_measured_runtime
def test_cli_y_overflow_has_no_report(tmp_path):
    proc = _run_cli(tmp_path, geojson_bytes(_ORD_X, _digits(400)), ground=False)
    _assert_overflow_cli(proc)


@needs_measured_runtime
def test_cli_largest_returning_integer(tmp_path):
    token = _digits(308)
    proc = _run_cli(tmp_path, geojson_bytes(token, _ORD_Y), ground=False)
    _assert_cli_report(proc, exit_code=2)


@needs_measured_runtime
def test_cli_developer_contrast(tmp_path):
    token = _digits(400)
    proc = _run_cli(tmp_path, geojson_bytes(_ORD_X, _ORD_Y, developer_token=token), ground=False)
    _assert_cli_report(proc, exit_code=2)


def test_cli_ground_ordinary_three_decimals(tmp_path):
    proc = _run_cli(tmp_path, geojson_bytes(_ORD_X, _ORD_Y), ground=True)
    _assert_cli_report(proc, exit_code=2)


def _write_zip(tmp_path: Path, payload: bytes) -> Path:
    path = tmp_path / f"{_STEM}.zip"
    member = f"{_STEM}.geojson"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(member, payload)
    with zipfile.ZipFile(path) as archive:
        assert archive.namelist() == [member]
        assert archive.getinfo(member).compress_type == zipfile.ZIP_STORED
        assert archive.read(member) == payload
    return path


def test_stored_zip_ordinary_member_v011_passes_and_v001_fails(tmp_path):
    path = _write_zip(tmp_path, geojson_bytes(_ORD_X, _ORD_Y))
    before = path.read_bytes()
    report = vp.validate(path, "vpm", PROFILES)
    assert path.read_bytes() == before
    stages = {stage.id: stage for stage in report.stages}
    assert stages["V011"].status == "pass"
    assert stages["V001"].status == "fail"
    names = {item.name for item in stages["V001"].findings}
    assert "main FBX" in names and "PNG count" in names
    assert report.passed is False and report.exit_code == 1


@needs_measured_runtime
def test_stored_zip_overflow_member_has_no_report(tmp_path):
    token = _digits(309)
    assert len(token) == 310
    path = _write_zip(tmp_path, geojson_bytes(token, _ORD_Y))
    before = path.read_bytes()
    with pytest.raises(OverflowError):
        vp.validate(path, "vpm", PROFILES)
    assert path.read_bytes() == before
    proc = _run_cli_path(path)
    assert path.read_bytes() == before
    assert list(tmp_path.glob("*.json")) == []
    _assert_overflow_cli(proc)
