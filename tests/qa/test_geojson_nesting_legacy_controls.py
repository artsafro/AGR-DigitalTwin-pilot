"""Legacy characterization of small deep GeoJSON documents against V011 (new-case).

Pins current behaviour with synthetic bytes built in this file: a complete document
with a string ``developer`` is a V011 schema pass, ``passed`` false, exit 2; ``{`` and a
duplicated ``designer`` key are V011 JSON fails, exit 1; a top-level nest is a V011
``type`` fail; a nested ``developer`` still schema-passes and stays out of the report.

Depth 2048 is a witness only on the measured runtime, CPython 3.14.7. This is
characterization, not a developer type rule, a recursion-limit change, or an
exception-normalization change. No delivery package is accepted (``passed`` stays false).
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from twinqa.geojson import geojson_findings
from twinqa.io import read_json
from twinqa.profiles import load_profiles

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "tools" / "qa" / "validate_package.py"
sys.path.insert(0, str(ROOT / "tools" / "qa"))
import validate_package  # noqa: E402

PROFILES = load_profiles()
PROFILE = PROFILES.vpm

FIXTURE_LIMIT = 64 * 1024
OBSERVED_LIMIT = 60
NEST_RUN_LIMIT = 20
TIMEOUT_S = 60
MEASURED_RUNTIME = (3, 14, 7)
MEASURED_RECURSION_LIMIT = 1000
MEASURED_INT_MAX_STR_DIGITS = 4300
# A complete document whose developer is a nested array is a V011 pass on a single file.
# Other blocking stages stay not_run, so the process exits 2.
DEVELOPER_ARRAY_EXIT = 2
SHAPES = ("array", "object", "doc-array", "doc-object")


def _jpeg_b64() -> str:
    """Synthetic flat 256x256 RGB(200, 200, 200) JPEG, quality 20. Not a real object."""
    buf = BytesIO()
    Image.new("RGB", (256, 256), (200, 200, 200)).save(buf, "JPEG", quality=20)
    return base64.b64encode(buf.getvalue()).decode("ascii")


_IMAGE_B64 = _jpeg_b64()


def _nested_array(depth: int) -> bytes:
    return (b"[" * depth) + b"0" + (b"]" * depth)


def _nested_object(depth: int) -> bytes:
    return (b'{"k":' * depth) + b"0" + (b"}" * depth)


def _nested_list(depth: int):
    """Iterative list of the same shape as ``_nested_array``. Own derivation, not a parser."""
    node = 0
    for _ in range(depth):
        node = [node]
    return node


def _repr_prefix(depth: int, width: int = OBSERVED_LIMIT) -> str:
    return repr(_nested_list(depth))[:width]


ARRAY32_OBSERVED = _repr_prefix(32)


def _shell(developer: bytes, *, duplicate_designer: bool = False) -> bytes:
    before = ("address", "okrug", "rajon", "name")
    after = (
        "designer", "cadNum", "FNO_code", "FNO_name", "ZU_area", "h_relief", "h_otn",
        "h_abs", "s_obsh", "s_naz", "s_podz", "spp_gns", "act_AGR", "imageBase64", "other",
    )
    values = {key: "value" for key in before + after}
    values["FNO_code"] = "123 456"
    values["other"] = ""
    values["imageBase64"] = _IMAGE_B64

    def field(key: str) -> bytes:
        return b'"' + key.encode("ascii") + b'":"' + values[key].encode("ascii") + b'"'

    props = b",".join(field(key) for key in before)
    props += b',"developer":' + developer
    tail = [field(key) for key in after]
    if duplicate_designer:
        tail.insert(1, field("designer"))
    props += b"," + b",".join(tail)
    return (
        b'{"type":"FeatureCollection","features":[{"type":"ObjectFeature","properties":{'
        + props
        + b'},"geometry":{"type":"Point","coordinates":[12345.678,6789.012]},"Glasses":[]}]}'
    )


def _bytes_for(shape: str, depth: int) -> bytes:
    if shape == "array":
        return _nested_array(depth)
    if shape == "object":
        return _nested_object(depth)
    if shape == "doc-array":
        return _shell(_nested_array(depth))
    if shape == "doc-object":
        return _shell(_nested_object(depth))
    raise AssertionError(shape)


def _write(tmp_path: Path, name: str, data: bytes) -> Path:
    assert len(data) < FIXTURE_LIMIT
    data.decode("utf-8")
    path = tmp_path / name
    assert not path.stem.endswith("_Ground")
    path.write_bytes(data)
    return path


def _brace_observed() -> str:
    """Stdlib decode text, sliced the same way a finding stores it. Not ``read_json``."""
    try:
        json.loads("{")
    except json.JSONDecodeError as exc:
        return str(exc)[:120]
    raise AssertionError("stdlib json.loads('{') did not fail")


def _max_run(text: str, char: str) -> int:
    best = cur = 0
    for item in text:
        if item == char:
            cur += 1
            if cur > best:
                best = cur
        else:
            cur = 0
    return best


def _walk(value):
    depth = 0
    cur = value
    while depth < 4096:
        if isinstance(cur, list) and len(cur) == 1:
            cur = cur[0]
            depth += 1
            continue
        if isinstance(cur, dict) and list(cur) == ["k"]:
            cur = cur["k"]
            depth += 1
            continue
        break
    return depth, cur


def _exit_for(shape: str) -> int:
    if shape == "doc-array":
        return DEVELOPER_ARRAY_EXIT
    if shape == "doc-object":
        return 2
    return 1


def _array_observed(depth: int) -> str:
    if depth == 32:
        return ARRAY32_OBSERVED
    if depth == 2048:
        return "[" * OBSERVED_LIMIT
    raise AssertionError(depth)


def _runtime() -> dict:
    return {
        "version": sys.version,
        "recursion_limit": sys.getrecursionlimit(),
        "int_max_str_digits": sys.get_int_max_str_digits(),
    }


def _finding_rows(findings) -> list[dict]:
    return [{"name": f.name, "status": f.status, "observed": f.observed} for f in findings]


def _v011_stage(report):
    return next(stage for stage in report.stages if stage.id == "V011")


def _summarize(doc) -> dict:
    if isinstance(doc, dict) and isinstance(doc.get("features"), list):
        developer = doc["features"][0]["properties"]["developer"]
        if isinstance(developer, str):
            return {"container": "document", "developer": "str"}
        depth, leaf = _walk(developer)
        return {
            "container": "document",
            "developer": type(developer).__name__,
            "depth": depth,
            "leaf": leaf if isinstance(leaf, int) else type(leaf).__name__,
        }
    depth, leaf = _walk(doc)
    return {
        "container": type(doc).__name__,
        "depth": depth,
        "leaf": leaf if isinstance(leaf, int) else type(leaf).__name__,
    }


def _inprocess_payload(path: Path, data: bytes) -> dict:
    try:
        reader = {"outcome": "value", **_summarize(read_json(data))}
    except (UnicodeDecodeError, ValueError) as exc:
        reader = {"outcome": "exception", "type": type(exc).__name__, "message": str(exc)[:200]}
    found = geojson_findings(data, PROFILE, path.stem.endswith("_Ground"))
    report = validate_package.validate(path, "vpm", PROFILES, scene=False)
    stage = _v011_stage(report)
    return {
        "reader": reader,
        "findings": {"outcome": "list", "rows": _finding_rows(found)},
        "validate": {
            "outcome": "report",
            "v011": stage.status,
            "rows": _finding_rows(stage.findings),
            "passed": report.passed,
            "exit": report.exit_code,
            "notes": list(report.notes),
            "other": {s.id: s.status for s in report.stages if s.id != "V011"},
            "serialized": json.dumps(report.to_dict(), ensure_ascii=False),
        },
    }


def _measure_subprocess(path: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--measure", str(path)],
        cwd=ROOT,
        capture_output=True,
        timeout=TIMEOUT_S,
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace")[:800]
    return json.loads(proc.stdout.decode("utf-8", errors="strict"))


def _cli(path: Path) -> tuple[int, dict, str]:
    cmd = [sys.executable, str(CLI), str(path), "--profile", "vpm", "--json"]
    assert "--scene" not in cmd
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, timeout=TIMEOUT_S)
    assert proc.stderr == b""
    text = proc.stdout.decode("utf-8", errors="strict")
    report = json.loads(text)
    assert isinstance(report, dict)
    assert report["exit_code"] == proc.returncode
    v011 = next(stage for stage in report["stages"] if stage["id"] == "V011")
    if v011["status"] == "fail":
        assert proc.returncode == 1
    elif v011["status"] == "pass":
        assert proc.returncode == 2
    else:
        raise AssertionError(v011["status"])
    return proc.returncode, report, text


def _probe_strict_report(report: dict) -> None:
    """Guarantee: the row returns a V011 report as strict JSON. It does not escape."""
    assert isinstance(report.get("stages"), list) and report["stages"]
    assert isinstance(report.get("exit_code"), int)
    assert any(stage.get("id") == "V011" for stage in report["stages"])


def _assert_reader(reader: dict, shape: str, depth: int) -> None:
    assert reader["outcome"] == "value"
    assert reader["depth"] == depth
    assert reader["leaf"] == 0
    if shape == "array":
        assert reader["container"] == "list"
    elif shape == "object":
        assert reader["container"] == "dict"
    elif shape == "doc-array":
        assert reader["container"] == "document" and reader["developer"] == "list"
    else:
        assert reader["container"] == "document" and reader["developer"] == "dict"


def _assert_rows(rows: list[dict], shape: str, depth: int) -> None:
    if shape in ("array", "object"):
        assert len(rows) == 1
        row = rows[0]
        assert row["name"] == "type" and row["status"] == "fail"
        assert isinstance(row["observed"], str)
        assert len(row["observed"]) <= OBSERVED_LIMIT
        if shape == "array":
            assert row["observed"] == _array_observed(depth)
            assert len(row["observed"]) == OBSERVED_LIMIT
        else:
            assert row["observed"] == "None"
        return
    assert [(row["name"], row["status"]) for row in rows] == [
        ("imageBase64", "pass"),
        ("Glasses", "pass"),
        ("schema", "pass"),
    ]


def _assert_excludes_nest(text: str, shape: str, depth: int) -> None:
    if shape == "doc-array":
        assert _max_run(text, "[") < NEST_RUN_LIMIT
        return
    if shape == "doc-object":
        assert '"k"' not in text
        return
    if shape == "array":
        observed = _array_observed(depth)
        assert observed in text
        assert _max_run(text, "[") <= OBSERVED_LIMIT
        if depth == 32:
            full = repr(_nested_list(32))
            assert len(full) > OBSERVED_LIMIT
            assert full not in text
        else:
            assert "[" * (OBSERVED_LIMIT + 1) not in text
        return
    assert '"k"' not in text
    assert '"observed": "None"' in text or '"observed":"None"' in text


def _assert_payload(payload: dict, shape: str, depth: int) -> None:
    _assert_reader(payload["reader"], shape, depth)
    assert payload["findings"]["outcome"] == "list"
    assert payload["validate"]["outcome"] == "report"
    _assert_rows(payload["findings"]["rows"], shape, depth)
    _assert_rows(payload["validate"]["rows"], shape, depth)
    assert payload["validate"]["passed"] is False
    assert payload["validate"]["exit"] == _exit_for(shape)
    assert payload["validate"]["v011"] == ("pass" if shape.startswith("doc-") else "fail")
    assert payload["validate"]["notes"] == ["single GeoJSON: only V011 applies"]
    assert set(payload["validate"]["other"].values()) == {"not_run"}
    _assert_excludes_nest(payload["validate"]["serialized"], shape, depth)


def _assert_cli(code: int, report: dict, text: str, shape: str, depth: int) -> None:
    _probe_strict_report(report)
    assert report["passed"] is False
    assert code == _exit_for(shape) == report["exit_code"]
    v011 = next(stage for stage in report["stages"] if stage["id"] == "V011")
    assert v011["status"] == ("pass" if shape.startswith("doc-") else "fail")
    _assert_rows(v011["findings"], shape, depth)
    assert report["notes"] == ["single GeoJSON: only V011 applies"]
    assert {stage["status"] for stage in report["stages"] if stage["id"] != "V011"} == {"not_run"}
    _assert_excludes_nest(text, shape, depth)


def _assert_measured_limits(payload: dict) -> None:
    before, after = payload["before"], payload["after"]
    assert before["version"] == after["version"]
    assert before["version"].split()[0] == "3.14.7"
    assert before["recursion_limit"] == after["recursion_limit"] == MEASURED_RECURSION_LIMIT
    assert before["int_max_str_digits"] == after["int_max_str_digits"] == MEASURED_INT_MAX_STR_DIGITS


def _skip_unless_measured() -> None:
    if sys.version_info[:3] != MEASURED_RUNTIME:
        pytest.skip(
            "depth 2048 was measured only on CPython 3.14.7 "
            f"(this interpreter is {sys.version.split()[0]}); "
            "no universal nesting limit is asserted"
        )


def _assert_nest_case(tmp_path: Path, shape: str, depth: int, *, subprocess_measure: bool) -> None:
    data = _bytes_for(shape, depth)
    path = _write(tmp_path, f"{shape}-d{depth}.geojson", data)
    if subprocess_measure:
        payload = _measure_subprocess(path)
        _assert_measured_limits(payload)
    else:
        payload = _inprocess_payload(path, data)
    _assert_payload(payload, shape, depth)
    code, report, text = _cli(path)
    _assert_cli(code, report, text, shape, depth)


def test_array_depth_32_prefix_is_an_independent_repr_slice():
    hand = ("[" * 32) + "0" + ("]" * 27)
    assert ARRAY32_OBSERVED == hand
    assert len(ARRAY32_OBSERVED) == OBSERVED_LIMIT
    assert len(repr(_nested_list(32))) == 65


def test_shallow_string_developer_schema_pass_exit_2(tmp_path):
    data = _shell(b'"value"')
    path = _write(tmp_path, "control-valid.geojson", data)
    doc = read_json(data)
    assert isinstance(doc["features"][0]["properties"]["developer"], str)
    assert doc["features"][0]["properties"]["developer"] == "value"
    findings = geojson_findings(data, PROFILE, False)
    assert [(f.name, f.status) for f in findings] == [
        ("imageBase64", "pass"),
        ("Glasses", "pass"),
        ("schema", "pass"),
    ]
    report = validate_package.validate(path, "vpm", PROFILES, scene=False)
    assert report.passed is False and report.exit_code == 2
    assert _v011_stage(report).status == "pass"
    code, body, _text = _cli(path)
    assert code == 2 and body["passed"] is False
    assert next(s for s in body["stages"] if s["id"] == "V011")["status"] == "pass"
    _probe_strict_report(body)


def test_malformed_brace_is_json_decode_error_and_exit_1(tmp_path):
    data = b"{"
    expected = _brace_observed()
    path = _write(tmp_path, "control-malformed.geojson", data)
    with pytest.raises(json.JSONDecodeError) as caught:
        read_json(data)
    assert str(caught.value)[:120] == expected
    findings = geojson_findings(data, PROFILE, False)
    assert len(findings) == 1
    assert findings[0].name == "JSON" and findings[0].status == "fail"
    assert findings[0].observed == expected
    report = validate_package.validate(path, "vpm", PROFILES, scene=False)
    assert report.passed is False and report.exit_code == 1
    assert _v011_stage(report).status == "fail"
    code, body, _text = _cli(path)
    assert code == 1 and body["passed"] is False
    v011 = next(s for s in body["stages"] if s["id"] == "V011")
    assert v011["status"] == "fail"
    assert v011["findings"][0]["name"] == "JSON"
    assert v011["findings"][0]["observed"] == expected
    _probe_strict_report(body)


def test_duplicate_designer_is_value_error_and_exit_1(tmp_path):
    data = _shell(b'"value"', duplicate_designer=True)
    path = _write(tmp_path, "control-duplicate.geojson", data)
    with pytest.raises(ValueError) as caught:
        read_json(data)
    assert type(caught.value) is ValueError
    assert str(caught.value) == "Duplicate key: designer"
    findings = geojson_findings(data, PROFILE, False)
    assert len(findings) == 1
    assert findings[0].name == "JSON" and findings[0].status == "fail"
    assert findings[0].observed == "Duplicate key: designer"
    report = validate_package.validate(path, "vpm", PROFILES, scene=False)
    assert report.passed is False and report.exit_code == 1
    assert _v011_stage(report).status == "fail"
    code, body, _text = _cli(path)
    assert code == 1 and body["passed"] is False
    v011 = next(s for s in body["stages"] if s["id"] == "V011")
    assert v011["status"] == "fail"
    assert v011["findings"][0]["observed"] == "Duplicate key: designer"
    _probe_strict_report(body)


@pytest.mark.parametrize("shape", SHAPES)
def test_depth_32_nest_matches_current_v011(shape, tmp_path):
    _assert_nest_case(tmp_path, shape, 32, subprocess_measure=False)


@pytest.mark.parametrize("shape", SHAPES)
def test_depth_2048_nest_matches_depth_32_on_measured_runtime(shape, tmp_path):
    _skip_unless_measured()
    _assert_nest_case(tmp_path, shape, 2048, subprocess_measure=True)


@pytest.mark.parametrize("depth", (32, 2048))
def test_no_depth_escapes_v011_without_a_report(depth, tmp_path):
    """No depth in {32, 2048} escapes V011 with a report: every row is strict JSON."""
    if depth == 2048:
        _skip_unless_measured()
    for shape in SHAPES:
        data = _bytes_for(shape, depth)
        path = _write(tmp_path, f"probe-{shape}-d{depth}.geojson", data)
        if depth == 2048:
            payload = _measure_subprocess(path)
            _assert_measured_limits(payload)
        else:
            payload = _inprocess_payload(path, data)
        assert payload["findings"]["outcome"] == "list"
        assert payload["validate"]["outcome"] == "report"
        _code, report, _text = _cli(path)
        _probe_strict_report(report)


def _measure_main(path: Path) -> None:
    before = _runtime()
    data = path.read_bytes()
    try:
        reader = {"outcome": "value", **_summarize(read_json(data))}
    except (UnicodeDecodeError, ValueError) as exc:
        reader = {"outcome": "exception", "type": type(exc).__name__, "message": str(exc)[:200]}
    try:
        found = geojson_findings(data, PROFILE, path.stem.endswith("_Ground"))
        findings = {"outcome": "list", "rows": _finding_rows(found)}
    except (UnicodeDecodeError, ValueError) as exc:
        findings = {"outcome": "exception", "type": type(exc).__name__, "message": str(exc)[:200]}
    try:
        report = validate_package.validate(path, "vpm", PROFILES, scene=False)
        stage = _v011_stage(report)
        validated = {
            "outcome": "report",
            "v011": stage.status,
            "rows": _finding_rows(stage.findings),
            "passed": report.passed,
            "exit": report.exit_code,
            "notes": list(report.notes),
            "other": {s.id: s.status for s in report.stages if s.id != "V011"},
            "serialized": json.dumps(report.to_dict(), ensure_ascii=False),
        }
    except (UnicodeDecodeError, ValueError) as exc:
        validated = {"outcome": "exception", "type": type(exc).__name__, "message": str(exc)[:200]}
    after = _runtime()
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps({
        "before": before,
        "after": after,
        "reader": reader,
        "findings": findings,
        "validate": validated,
    }), flush=True)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--measure":
        _measure_main(Path(sys.argv[2]))
    else:
        raise SystemExit("usage: test_geojson_nesting_legacy_controls.py --measure FILE")
