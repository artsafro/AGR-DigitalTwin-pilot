"""Blender-only sources-dwg intake (#1857): a hash-bound DXF derivative or a fail-closed stop.

Pattern: new-case: tests for the Autodesk-free DWG intake (synthetic DWG bytes + ezdxf DXF).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import random
import subprocess
import sys
from pathlib import Path

import ezdxf
import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "methods" / "body" / "dxf_intake.py"
_spec = importlib.util.spec_from_file_location("dxf_intake", TOOL)
di = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(di)

SYMBOL = "Дверь 1000x2100 отм_ 0_000"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _dxf(path: Path, units=4, entities=True) -> Path:
    doc = ezdxf.new("R2018")
    if units is None:
        del doc.header["$INSUNITS"]
    else:
        doc.header["$INSUNITS"] = units
    if entities:
        msp = doc.modelspace()
        msp.add_lwpolyline([(0, 0), (6000, 0), (6000, 4000), (0, 4000)], close=True, dxfattribs={"layer": "WALL"})
        doc.blocks.new(SYMBOL)
        msp.add_blockref(SYMBOL, (2000, -100), dxfattribs={"layer": "DOOR"})
        doc.blocks.new("Logo")
        msp.add_blockref("Logo", (0, 0), dxfattribs={"layer": "0"})
    doc.saveas(path)
    return path


def _receipt(path: Path, dwg_p: Path, dxf_p: Path, **over) -> Path:
    data = {"receipt": "dwg-to-dxf/1", "tool": "tools/methods/body/dwg_to_dxf.py", "status": "pass", "reason": None,
            "returncode": 0, "command": ["accoreconsole.exe", "/i", "C:/x/copy.dwg"],
            "source": {"path": "C:/elsewhere/L03.dwg", "sha256": _sha(dwg_p)},
            "source_sha256_after": _sha(dwg_p), "dxf": {"path": "C:/elsewhere/L03.dxf", "sha256": _sha(dxf_p)}}
    data.update(over)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture()
def case(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    dwg = src / "L03 план.dwg"
    dwg.write_bytes(b"AC1024" + bytes(range(64)))
    dxf = _dxf(src / "L03.dxf")
    rec = _receipt(src / "L03.receipt.json", dwg, dxf)
    return dwg, dxf, rec, tmp_path / "out" / "intake.json"


def _cli(*args):
    return subprocess.run([sys.executable, str(TOOL), *map(str, args)], capture_output=True, text=True,
                          encoding="utf-8", timeout=120)


def test_positive_fresh_process_reports_hashes_units_and_inputs(case):
    dwg, dxf, rec, out = case
    before = {p: _sha(p) for p in (dwg, dxf, rec)}
    proc = _cli(dwg, dxf, rec, out)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["status"] == "pass" and data["passed"] is False and data["stage"] == "sources-dwg"
    assert data["source"]["sha256"] == before[dwg] and data["dxf"]["sha256"] == before[dxf]
    assert data["provenance"]["sha256"] == before[rec] and data["provenance"]["kind"] == "dwg-to-dxf/1"
    assert data["units"]["insunits"] == 4 and data["units"]["name"] == "mm"
    assert data["parity"]["status"] == "not measured" and data["autodesk_launched"] is False
    assert data["inputs"]["model_layers"] == {"WALL": 1, "DOOR": 1, "0": 1}
    assert data["inputs"]["opening_symbol_blocks"] == {SYMBOL: 1} and data["inputs"]["opening_symbol_inserts"] == 1
    assert data["next"]["tool"] == "tools/methods/body/plan_from_dxf.py"
    assert {p: _sha(p) for p in (dwg, dxf, rec)} == before  # inputs untouched


def test_handoff_dxf_reads_back_through_plan_from_dxf(case, tmp_path):
    dwg, dxf, rec, out = case
    assert _cli(dwg, dxf, rec, out).returncode == 0
    census = tmp_path / "census.json"
    proc = subprocess.run([sys.executable, str(ROOT / "tools/methods/body/plan_from_dxf.py"), "census", str(dxf),
                           str(census)], capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(census.read_text(encoding="utf-8"))["model_layers"] == \
        json.loads(out.read_text(encoding="utf-8"))["inputs"]["model_layers"]


def test_no_process_is_launched(case, monkeypatch):
    dwg, dxf, rec, _ = case

    def boom(*a, **k):
        raise AssertionError("a process was launched")
    monkeypatch.setattr(subprocess, "Popen", boom)
    monkeypatch.setattr(subprocess, "run", boom)
    assert di.verify_dxf_derivative(dwg, dxf, rec)["status"] == "pass"


@pytest.mark.parametrize("missing", ["dwg", "dxf", "rec"])
def test_missing_input_stops_with_forward_path_and_writes_nothing(case, missing):
    dwg, dxf, rec, out = case
    {"dwg": dwg, "dxf": dxf, "rec": rec}[missing].unlink()
    proc = _cli(dwg, dxf, rec, out)
    assert proc.returncode == 2 and "sources-dwg stop" in proc.stderr and "dwg_to_dxf.py" in proc.stderr
    assert not out.exists() and not out.parent.exists()


def _fail(case, proc, needle):
    out = case[3]
    assert proc.returncode == 3, proc.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["status"] == "fail" and data["passed"] is False and "inputs" not in data and "next" not in data
    assert needle in data["reason"] and data["action"]
    assert "sources-dwg stop" in proc.stderr
    return data


def test_stale_dxf_from_an_older_dwg_fails(case):
    dwg, dxf, rec, out = case
    dwg.write_bytes(b"AC1024" + b"changed since conversion")
    _fail(case, _cli(dwg, dxf, rec, out), "stale DXF")


def test_dxf_edited_after_conversion_fails(case):
    dwg, dxf, rec, out = case
    _dxf(dxf, entities=False)
    _fail(case, _cli(dwg, dxf, rec, out), "DXF changed since conversion")


def test_converter_output_is_unverifiable_even_with_matching_hashes(case):
    dwg, dxf, rec, out = case
    rec.write_text(json.dumps({"schema": "dxf-derivative/1", "converter": {"name": "ODA File Converter"},
                               "source": {"sha256": _sha(dwg)}, "dxf": {"sha256": _sha(dxf)}}), encoding="utf-8")
    data = _fail(case, _cli(dwg, dxf, rec, out), "not approved")
    assert "ODA File Converter" in data["reason"] and "Artem" in data["action"]
    assert di.APPROVED_CONVERTERS == frozenset()


@pytest.mark.parametrize("over,needle", [
    ({"status": "fail", "returncode": 1}, "not pass"),
    ({"returncode": None}, "not pass"),
    ({"receipt": "something/2"}, "unverifiable provenance"),
    ({"source_sha256_after": "0" * 64}, "source changed during conversion"),
    ({"dxf": {}}, "lacks"),
])
def test_bad_receipt_fails(case, over, needle):
    dwg, dxf, rec, out = case
    _receipt(rec, dwg, dxf, **over)
    _fail(case, _cli(dwg, dxf, rec, out), needle)


@pytest.mark.parametrize("units", [6, 0, 1, None])
def test_non_millimetre_or_missing_units_fail(case, units):
    dwg, dxf, rec, out = case
    _dxf(dxf, units=units)
    _receipt(rec, dwg, dxf)
    data = _fail(case, _cli(dwg, dxf, rec, out), "$INSUNITS")
    assert "name" not in data["units"]


def test_empty_model_space_fails(case):
    dwg, dxf, rec, out = case
    _dxf(dxf, entities=False)
    _receipt(rec, dwg, dxf)
    _fail(case, _cli(dwg, dxf, rec, out), "empty")


def test_unparsable_dxf_and_non_dwg_source_fail(case):
    dwg, dxf, rec, out = case
    dxf.write_text("not a dxf", encoding="utf-8")
    _receipt(rec, dwg, dxf)
    _fail(case, _cli(dwg, dxf, rec, out), "does not parse")
    out.unlink()
    dwg.write_bytes(b"PK\x03\x04 a zip")
    _receipt(rec, dwg, dxf)
    _fail(case, _cli(dwg, dxf, rec, out), "DWG magic")


def test_output_alias_or_existing_output_is_refused(case):
    dwg, dxf, rec, out = case
    before = _sha(rec)
    proc = _cli(dwg, dxf, rec, rec)
    assert proc.returncode == 4 and _sha(rec) == before
    out.parent.mkdir()
    out.write_text("old", encoding="utf-8")
    assert _cli(dwg, dxf, rec, out).returncode == 4 and out.read_text(encoding="utf-8") == "old"


def test_bad_provenance_json_and_suffix_are_input_errors(case):
    dwg, dxf, rec, out = case
    rec.write_text("{not json", encoding="utf-8")
    assert _cli(dwg, dxf, rec, out).returncode == 2 and not out.exists()
    assert _cli(dwg, dwg, rec, out).returncode == 2 and not out.exists()


def test_probe_pass_iff_both_hashes_bind(case):
    """Generated probe (seed 1857, 200 cases): pass exactly when the receipt binds the current DWG and DXF."""
    dwg, dxf, rec, _ = case
    rng = random.Random(1857)
    good = (_sha(dwg), _sha(dxf))
    results = []
    for _ in range(200):
        s = good[0] if rng.random() < 0.5 else "%064x" % rng.getrandbits(256)
        d = good[1] if rng.random() < 0.5 else "%064x" % rng.getrandbits(256)
        _receipt(rec, dwg, dxf, source={"sha256": s}, source_sha256_after=s, dxf={"sha256": d})
        status = di.verify_dxf_derivative(dwg, dxf, rec)["status"]
        results.append(status == ("pass" if (s, d) == good else "fail"))
    assert all(results) and len(results) == 200


def test_skeleton_names_the_intake_and_keeps_the_autocad_lane():
    sk = json.loads((ROOT / "docs/agents/skeletons.json").read_text(encoding="utf-8"))["stages"]["sources-dwg"]
    assert "tools/methods/body/dxf_intake.py" in sk["owners"] and "verify_dxf_derivative" in sk["entry_defs"]
    assert "tools/methods/body/dwg_to_dxf.py" in sk["owners"] and "dxf_intake.py" in sk["calls"]
    doc = (ROOT / "docs/agents/SKELETONS.md").read_text(encoding="utf-8")
    assert "dxf_intake.py" in doc
