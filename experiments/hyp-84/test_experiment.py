"""Offline tests for hypothesis 84. Synthetic benchmark fixtures, no AutoCAD."""

import importlib.util
import json
import math
import shutil
import sys
from copy import deepcopy
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parent / "experiment.py"
_SPEC = importlib.util.spec_from_file_location("hyp84_experiment", _PATH)
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "benchmark"
IDENTITY = ("AGR_IDENTITY|25.0s (LMS Tech)|drawing.dwg|4|"
            "0.000000000000,0.000000000000,0.000000000000")


@pytest.fixture(autouse=True)
def copied_inputs(tmp_path, monkeypatch):
    copied = tmp_path / "inputs"
    for name in ("bench-b01-box", "bench-b02-corner-niche", "bench-b02t-terrace"):
        target = copied / name
        target.mkdir(parents=True)
        for filename in ("spec.json", "object.json", "etalon.json", "tolerances.json"):
            shutil.copy2(BENCH / name / filename, target / filename)
    monkeypatch.setattr(sys.modules[__name__], "BENCH", copied)


def _raws():
    specs, raws = mod.load_inputs(BENCH)
    assert [item["id"] for item in raws] == ["bench-b01-box", "bench-b02-corner-niche", "bench-b02t-terrace"]
    return specs, raws


def _proc(code, stdout=""):
    return type("Proc", (), {"returncode": code, "stdout": stdout, "stderr": ""})()


def _log(*lines):
    return "\n".join(lines) + "\n"


def test_oracle_inventory_inheritance_marker_and_composition():
    _specs, raws = _raws()
    inventories = []
    for name in mod.ORDER:
        features = mod.oracle_features(raws, name)
        found = mod.inventory(features)
        inventories.append(found)
        assert mod.inventory_ok(features)
        assert found["unique_layers"] and found["entities"] == 21 and found["coordinates"] == 69
    assert inventories == [inventories[0]] * 4

    identity = mod.oracle_features(raws, "identity")
    b01_l0 = next(item for item in identity if item["layer"] == "B01_L0_OPEN_0")
    b01_l1 = next(item for item in identity if item["layer"] == "B01_L1_OPEN_0")
    assert b01_l0["vertices_mm"] == [[2000.0, 0.0, 900.0], [3500.0, 0.0, 900.0],
                                     [3500.0, 0.0, 2400.0], [2000.0, 0.0, 2400.0]]
    assert [(v[0], v[1]) for v in b01_l1["vertices_mm"]] == [(v[0], v[1]) for v in b01_l0["vertices_mm"]]
    assert [v[2] for v in b01_l1["vertices_mm"]] == [4200.0, 4200.0, 5700.0, 5700.0]
    roof = next(item for item in identity if item["layer"] == "B01_roof_LEVEL")
    assert roof["vertices_mm"] == [[0.0, 0.0, 6600.0]]

    rotated = mod.oracle_features(raws, "rotation37")
    assert next(item for item in rotated if item["layer"] == "B01_roof_LEVEL")["vertices_mm"] == [[0.0, 0.0, 6600.0]]
    moved = next(item for item in mod.oracle_features(raws, "translation") if item["layer"] == "B01_roof_LEVEL")
    assert moved["vertices_mm"][0] == pytest.approx([600000000.0, 7500000000.0, 156600.0])

    cos_a, sin_a = math.cos(math.radians(37)), math.sin(math.radians(37))
    x, y, z = mod.transform_metres(3, 4, 5, "rotation37_then_translation")
    assert float(x) == pytest.approx(3 * cos_a - 4 * sin_a + 600000, abs=1e-9)
    assert float(y) == pytest.approx(3 * sin_a + 4 * cos_a + 7500000, abs=1e-9)
    assert float(z) == pytest.approx(155)
    wrong = (3 + 600000) * cos_a - (4 + 7500000) * sin_a
    assert float(x) != pytest.approx(wrong, abs=1)
    assert mod.transform_metres(8, 9, 1, "identity") == (mod._d(8), mod._d(9), mod._d(1))


def test_roundtrip_writer_precision_and_perturbation(tmp_path):
    pytest.importorskip("ezdxf")
    specs, raws = _raws()
    assert mod.legacy.to_mm(1) == 1000.0
    for name in mod.ORDER:
        oracle = mod.oracle_features(raws, name)
        written = mod.writer_features(specs, name)
        assert mod.legacy.to_mm(2.5) == 2500.0
        for feature in written:
            for vertex in feature["vertices_mm"]:
                assert vertex == [round(number, 6) for number in vertex]
        report = mod._offline(written, oracle, tmp_path / f"{name}.dxf")
        assert report["ok"] and report["audit"]["errors"] == 0 and report["audit"]["fixes"] == 0
        assert report["audit"]["count_before"] == 21 and report["units"] == 4 and report["census_ok"]
        assert report["file"]["bytes"] > 0
        for value in report["classes"].values():
            assert value is not None and value <= mod.TOL_MM
    rotated_oracle = mod.oracle_features(raws, "rotation37")
    rotated_writer = mod.writer_features(specs, "rotation37")
    assert rotated_writer[0]["vertices_mm"] != rotated_oracle[0]["vertices_mm"]
    shifted = deepcopy(rotated_oracle)
    shifted[0]["vertices_mm"][0][0] += 0.011
    rejected = mod.evaluate(rotated_oracle, shifted, 4)
    assert rejected["ok"] is False and rejected["compare"]["max_deviation_mm"] >= 0.011
    assert "coordinate deviation" in rejected["compare"]["errors"]


def test_flags_counts_extra_entity_nonfinite_and_audit(tmp_path):
    pytest.importorskip("ezdxf")
    specs, raws = _raws()
    oracle = mod.oracle_features(raws, "identity")
    rows = [{"layer": item["layer"], "kind": item["kind"], "flags": mod.expected_flag(item["kind"]),
             "raw_vertices": len(item["vertices_mm"])} for item in oracle]
    assert mod.census_matches(oracle, rows)
    flags = deepcopy(rows)
    flags[0]["flags"] = 0
    short = deepcopy(rows)
    short[0]["raw_vertices"] -= 1
    assert mod.census_matches(oracle, flags) is False and mod.census_matches(oracle, short) is False
    opened = deepcopy(oracle)
    opened[0]["closed"] = False
    assert "wrong closed flag" in mod.evaluate(oracle, opened, 4)["compare"]["errors"]
    assert "missing" in mod.evaluate(oracle, oracle[:-1], 4)["compare"]["errors"]
    poisoned = deepcopy(oracle)
    poisoned[0]["vertices_mm"][0][0] = math.nan
    assert mod.evaluate(oracle, poisoned, 4)["ok"] is False
    assert "nonfinite" in mod.evaluate(oracle, poisoned, 4)["compare"]["errors"]

    written = mod.writer_features(specs, "identity")
    path = tmp_path / "extra.dxf"
    mod.legacy.write_dxf(written, path)
    doc = mod.legacy._import_ezdxf().readfile(path)
    doc.modelspace().add_line((0, 0), (1, 0))
    doc.saveas(path)
    ignored, _basic = mod.legacy.read_dxf(path, expect_count=len(oracle))
    audited = mod.audit_dxf(path)
    assert len(ignored) == 21 and audited["count_before"] == 22
    assert mod.census_matches(oracle, audited["rows"]) is False

    ghost = tmp_path / "ghost.dxf"
    broken = mod.legacy._import_ezdxf().new("R2018")
    broken.header["$INSUNITS"] = 4
    line = broken.modelspace().add_line((0, 0), (1, 0))
    line.dxf.linetype = "GHOST"
    broken.saveas(ghost)
    assert mod.audit_dxf(ghost)["ok"] is False
    real_audit = mod.audit_dxf
    mod.audit_dxf = lambda file: {**real_audit(file), "errors": 1, "fixes": 2, "ok": False}
    try:
        failed = mod._offline(written, oracle, tmp_path / "clean.dxf")
    finally:
        mod.audit_dxf = real_audit
    assert failed["ok"] is False and failed["audit"]["errors"] == 1 and failed["audit"]["fixes"] == 2


def test_process_markers_retries_stdout_and_fresh_path(tmp_path, monkeypatch):
    monkeypatch.setattr(mod.time, "sleep", lambda _seconds: None)
    calls = []

    def install(payloads, codes, stdout=""):
        calls.clear()
        stream = iter(list(zip(payloads, codes)))

        def run(command, **_kwargs):
            calls.append(command)
            payload, code = next(stream)
            Path(command[command.index("--out") + 1]).write_text(json.dumps(payload), encoding="utf-8")
            return _proc(code, stdout)

        monkeypatch.setattr(mod.subprocess, "run", run)

    entity = "AGR_ENTITY|B01_roof_LEVEL|POINT|0|0.000000000000,0.000000000000,6600.000000000000"
    good = {"status": "ok", "code": 0, "log": _log(IDENTITY, entity, "AGR_WRITE_DONE")}
    install([good], [0], stdout=_log(IDENTITY, entity, entity, "AGR_WRITE_DONE"))
    script = tmp_path / "write.scr"
    script.write_text("(princ)\n", encoding="utf-8")
    result = mod.run_native_call(tmp_path / "wrapper.py", "hyp-84", script, tmp_path / "ok.log.json", expect="write")
    command = calls[0]
    assert command[:3] == [sys.executable, str(tmp_path / "wrapper.py"), "acad"]
    assert command[command.index("--card") + 1] == "hyp-84"
    assert command[command.index("--max-chars") + 1] == "1000"
    assert command[command.index("--timeout") + 1] == "60" and command[command.index("--wait") + 1] == "30"
    assert "t_3d8b70a4" not in command and "--dwg" not in command
    assert result["call_ok"] and len(result["parsed"]["entities"]) == 1 and result["retries"] == []
    assert "text" not in result and result["identity_ok"]

    install([{"code": 0, "log": good["log"]}], [0])
    assert mod.run_native_call(tmp_path / "w.py", "hyp-84", script, tmp_path / "status.log.json", expect="write")["call_ok"] is False
    install([{"status": "ok", "log": good["log"]}], [0])
    assert mod.run_native_call(tmp_path / "w.py", "hyp-84", script, tmp_path / "code.log.json", expect="write")["call_ok"] is False
    install([{"status": "error", "code": 1, "log": good["log"]}], [1])
    assert mod.run_native_call(tmp_path / "w.py", "hyp-84", script, tmp_path / "err.log.json", expect="write")["call_ok"] is False
    install([{"status": "ok", "code": 0, "log": _log(IDENTITY)}], [0])
    missing = mod.run_native_call(tmp_path / "w.py", "hyp-84", script, tmp_path / "marker.log.json", expect="write")
    assert missing["call_ok"] is False and missing["write_done"] is False
    install([{"status": "ok", "code": 0, "log": _log("AGR_IDENTITY|24.0|a.dwg|4|0,0,0", "AGR_READ_DONE")}], [0])
    assert mod.run_native_call(tmp_path / "w.py", "hyp-84", script, tmp_path / "ver.log.json")["identity_ok"] is False
    install([{"status": "ok", "code": 0, "log": _log("AGR_IDENTITY|25.0|a.dwg|6|0,0,0", "AGR_READ_DONE")}], [0])
    assert mod.run_native_call(tmp_path / "w.py", "hyp-84", script, tmp_path / "units.log.json")["call_ok"] is False
    install([{"status": "ok", "code": 0, "log": _log("AGR_IDENTITY|25.0|a.dwg|4|1,0,0", "AGR_READ_DONE")}], [0])
    assert mod.run_native_call(tmp_path / "w.py", "hyp-84", script, tmp_path / "ucs.log.json")["call_ok"] is False

    busy = {"status": "busy", "code": 3, "log": ""}
    install([busy, good], [3, 0])
    retried = mod.run_native_call(tmp_path / "w.py", "hyp-84", script, tmp_path / "busy.log.json",
                                  dwg=tmp_path / "new.dwg", expect="write")
    assert retried["call_ok"] and len(retried["retries"]) == 1 and retried["retries"][0]["returncode"] == 3
    assert retried["returncode"] == 0 and calls[-1][calls[-1].index("--dwg") + 1] == str(tmp_path / "new.dwg")
    install([busy, busy, busy, busy], [3, 3, 3, 3])
    exhausted = mod.run_native_call(tmp_path / "w.py", "hyp-84", script, tmp_path / "stuck.log.json", expect="write")
    assert exhausted["call_ok"] is False and len(exhausted["retries"]) == 3 and len(calls) == 4

    read = mod.reader_script()
    assert "(agr-census)" in read and "AGR_CENSUS" in read and "VERTEX" in read
    assert mod.main(["--inputs", str(BENCH), "--output", str(tmp_path), "--wrapper", "w.py", "--card", " "]) == 2
    existing = tmp_path / "existing"
    existing.mkdir()
    assert mod.main(["--inputs", str(BENCH), "--output", str(existing), "--wrapper", "w.py", "--card", "hyp-84"]) == 2
    assert not (existing / "results.json").exists()

    def fail(*_args, **_kwargs):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(mod, "load_inputs", fail)
    fresh = tmp_path / "fresh-results"
    assert mod.main(["--inputs", str(BENCH), "--output", str(fresh), "--wrapper", "w.py",
                     "--card", "hyp-84", "--repeats", "3"]) == 1
    saved = json.loads((fresh / "results.json").read_text(encoding="utf-8"))
    assert saved["verdict"] == "rejected" and "synthetic failure" in saved["exception"]
    assert "AGR_ENTITY" not in json.dumps(saved)


def test_geometry_rejection_does_not_stop_the_matrix(tmp_path, monkeypatch):
    seen = []

    def fake(name, rep, *_args, **_kwargs):
        seen.append((name, rep))
        row = {"transform": name, "rep": rep, "ok": False, "inventory_ok": True, "exception": None}
        for key, timing in (("offline", "seconds"), ("native_write", "wall_s"), ("read_dwg", "wall_s"),
                            ("ezdxf_native", "read_s"), ("native_offline_dxf", "wall_s"), ("native_native_dxf", "wall_s")):
            row[key] = {"called": True, "ok": False, timing: 0.2, "classes": {"contour": 0.011, "opening": 0.0, "level": 0.0}}
        return row

    monkeypatch.setattr(mod, "run_one", fake)
    state = {"repeats": 3, "rows": [], "exception": None}
    mod.run_matrix([], [], tmp_path, "wrapper.py", "hyp-84", 3, state)
    assert seen == [(name, rep) for name in mod.ORDER for rep in (1, 2, 3)]
    assert state["verdict"] == "rejected" and state["aggregate"]["medians"]["identity"]["offline_s"] == 0.2
    assert any("rejected" in reason for reason in state["reasons"])
    complete = {"inventory_ok": True, "exception": None}
    for key in ("offline", "native_write", "read_dwg", "ezdxf_native", "native_offline_dxf", "native_native_dxf"):
        complete[key] = {"called": True, "ok": True}
    assert mod.row_ok(complete) is True
    complete["read_dwg"] = {"called": False, "ok": False}
    assert mod.row_ok(complete) is False
