"""Focused tests for the throwaway AutoCAD/ezdxf prototype. Synthetic fixtures only."""

import copy
import importlib.util
import json
import math
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parent / "experiment.py"
_SPEC = importlib.util.spec_from_file_location("acad_coreconsole_experiment", _PATH)
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)

SYNTHETIC_NOTE = "synthetic fixture, not a real object or benchmark etalon mesh"


def _frame(name):
    return {"object": name, "source": "synthetic", "to_object": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]}


def synthetic_box():
    return {"synthetic": True, "note": SYNTHETIC_NOTE, "id": "synth-box", "spec_version": "0.3", "profile": "npm_min",
            "frame": _frame("synth-box"),
            "levels": [{"name": "L0", "elev_m": 0.0}, {"name": "L1", "elev_m": 3.3}, {"name": "roof", "elev_m": 6.6}],
            "floors": [{"level": "L0", "contour": [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]],
                        "openings": [{"wall": 0, "x_m": 2.0, "sill_m": 0.9, "w_m": 1.5, "h_m": 1.5}]},
                       {"level": "L1", "typical_of": "L0", "repeat_to": "L1", "openings": []}],
            "roof": {"parapet_h_m": 0.6}}


def synthetic_oblique():
    return {"synthetic": True, "note": SYNTHETIC_NOTE, "id": "synth-oblique", "spec_version": "0.3", "profile": "npm_min",
            "frame": _frame("synth-oblique"),
            "levels": [{"name": "L0", "elev_m": 0.0}, {"name": "L1", "elev_m": 3.3}, {"name": "roof", "elev_m": 6.6}],
            "floors": [{"level": "L1", "contour": [[6.0, 0.0], [12.0, 0.0], [12.0, 6.0], [9.0, 9.0], [6.0, 9.0]],
                        "openings": [{"wall": 2, "x_m": 1.371, "sill_m": 0.9, "w_m": 1.5, "h_m": 1.5}]}],
            "roof": {"parapet_h_m": 0.6}}


def _features(raw):
    assert raw["synthetic"] is True
    assert "not a real object" in raw["note"]
    return mod.build_features([mod.spec_from_mapping(raw)])


def test_expanded_counts_and_prefixes():
    raw = synthetic_box()
    spec = mod.spec_from_mapping(raw)
    floors = spec.expanded_floors()
    assert len(floors) == 2
    assert floors[1].level == "L1"
    assert len(floors[1].openings) == 1
    features = _features(raw)
    assert mod.bench_prefix("bench-b01-box") == "B01"
    assert mod.bench_prefix("bench-b02t-terrace") == "B02T"
    assert sum(item["kind"] == "LWPOLYLINE" for item in features) == 2
    assert sum(item["kind"] == "POLYLINE" for item in features) == 2
    assert sum(item["layer"].endswith("_LEVEL") for item in features) == 3
    assert not any(item["layer"].endswith("roof_CONTOUR") for item in features)
    assert any(item["layer"] == "BOX_roof_LEVEL" for item in features)


def test_unit_conversion():
    features = _features(synthetic_box())
    contour = next(item for item in features if item["layer"] == "BOX_L1_CONTOUR")
    level = next(item for item in features if item["layer"] == "BOX_L1_LEVEL")
    assert contour["vertices_mm"][0][2] == 3300.0
    assert level["vertices_mm"] == [[0.0, 0.0, 3300.0]]
    assert mod.to_mm(6.6) == 6600.0


def test_oblique_opening_coordinates():
    features = _features(synthetic_oblique())
    opening = next(item for item in features if item["layer"] == "OBLIQUE_L1_OPEN_0")
    assert opening["closed"] is True and len(opening["vertices_mm"]) == 4
    dx, dy = -3.0, 3.0
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    start = [mod.to_mm(12.0 + ux * 1.371), mod.to_mm(6.0 + uy * 1.371), mod.to_mm(3.3 + 0.9)]
    end = [mod.to_mm(12.0 + ux * 2.871), mod.to_mm(6.0 + uy * 2.871), mod.to_mm(3.3 + 0.9)]
    assert opening["vertices_mm"][0] == start
    assert opening["vertices_mm"][1] == end
    assert opening["vertices_mm"][1][0] < opening["vertices_mm"][0][0]
    assert opening["vertices_mm"][2][2] == mod.to_mm(3.3 + 0.9 + 1.5)


def _pair():
    features = _features(synthetic_box())
    actual = copy.deepcopy(features)
    return features, actual


def test_comparator_accepts_cyclic_reverse_and_rejects_defects():
    expected, actual = _pair()
    ring = next(item for item in actual if item["kind"] == "LWPOLYLINE")
    verts = list(reversed(ring["vertices_mm"]))
    ring["vertices_mm"] = verts[1:] + verts[:1]
    assert mod.compare_features(expected, actual, 4)["ok"] is True

    mutated = copy.deepcopy(actual)
    mutated[0]["vertices_mm"][0][0] += 1.0
    report = mod.compare_features(expected, mutated, 4)
    assert report["ok"] is False and report["max_deviation_mm"] >= 1.0
    assert "coordinate deviation" in report["errors"]

    duplicated = actual + [copy.deepcopy(actual[0])]
    assert "duplicate layer" in mod.compare_features(expected, duplicated, 4)["errors"]
    assert "missing" in mod.compare_features(expected, actual[:-1], 4)["errors"]

    opened = copy.deepcopy(actual)
    opened[0]["closed"] = False
    assert "wrong closed flag" in mod.compare_features(expected, opened, 4)["errors"]
    units = mod.compare_features(expected, actual, 6)
    assert units["ok"] is False and "wrong units" in units["errors"]
    empty = mod.compare_features(expected, [], 4)
    assert empty["ok"] is False and "empty readback" in empty["errors"]


def test_offline_dxf_roundtrip(tmp_path):
    pytest.importorskip("ezdxf")
    raw = synthetic_oblique()
    features = _features(raw)
    path = tmp_path / "synthetic-oblique.dxf"
    mod.write_dxf(features, path)
    entities, audit = mod.read_dxf(path, expect_count=len(features))
    report = mod.compare_features(features, entities, audit["insunits"])
    assert audit["insunits"] == 4 and report["ok"] is True
    assert path.stat().st_size > 0


def _files():
    return [{"path": "synthetic.dwg", "exists": True, "bytes": 8},
            {"path": "synthetic.dxf", "exists": True, "bytes": 8}]


def _native_call(kind):
    return {"call_ok": True, "returncode": 0, "status": "ok", "wrapper_code": 0, "timeout": False,
            "write_done": kind == "write", "read_done": kind == "read", "files": _files(),
            "compare": {"ok": True}}


def _good_rep():
    return {"write": _native_call("write"), "read_dwg": _native_call("read"),
            "ezdxf_on_native_dxf": {"compare": {"ok": True}},
            "native_on_ezdxf_dxf": _native_call("read"), "native_on_native_dxf": _native_call("read")}


def _offline_ok(count):
    return {"repetitions": [{"compare": {"ok": True}, "error": None} for _ in range(count)]}


def _probes():
    return [{"detected": ["missing file"]}]


def _proc(code):
    return type("Proc", (), {"returncode": code, "stdout": "", "stderr": ""})()


def test_write_script_ends_with_one_newline(tmp_path):
    path = tmp_path / "write.scr"
    mod.write_script(path, "(princ)\n\n")
    assert path.read_bytes() == b"(princ)\r\n"
    feature = {"layer": "SYNTH_LEVEL", "kind": "POINT", "closed": False, "vertices_mm": [[0.0, 0.0, 0.0]]}
    script, _body = mod.write_forms([feature], tmp_path / "a.dwg", tmp_path / "a.dxf")
    assert not script.startswith("FILEDIA\n")
    assert "\nFILEDIA\n0\nCMDECHO\n0\n" not in script
    assert '(setvar "FILEDIA" 0)' in script and '(setvar "CMDECHO" 0)' in script
    assert "QUIT" not in script.upper()


def test_wrapper_timeout_exit5_is_never_accepted(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        out = Path(cmd[cmd.index("--out") + 1])
        out.write_text(json.dumps({"status": "timeout", "exit_code": None, "seconds": 60.1,
                                   "log": "AGR_WRITE_DONE\n"}), encoding="utf-8")
        (out.parent / "native.dwg").write_bytes(b"dwg-bytes")
        (out.parent / "native.dxf").write_bytes(b"dxf-bytes")
        return _proc(5)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    out = tmp_path / "native"
    (out / "rep-01").mkdir(parents=True)
    (out / "rep-01" / "offline.dxf").write_bytes(b"offline")
    result = mod.run_native(_features(synthetic_box()), out, 3, tmp_path / "wrapper.py")
    assert len(calls) == 1
    row = result["repetitions"][0]
    assert result["aborted"] and row["write_failed"] is True and "read_dwg" not in row
    assert row["write"]["timeout"] is True and row["write"]["call_ok"] is False
    assert row["write"]["returncode"] == 5 and row["write"]["wrapper_s"] == 60.1
    assert row["write"]["write_done"] is True and row["write"]["files"][0]["bytes"] > 0
    assert mod.results_ok(_offline_ok(3), result, [{"skipped": True}], False, 3) is False

    log = tmp_path / "exit5.log.json"
    log.write_text(json.dumps({"status": "ok", "exit_code": 5, "seconds": 60.1, "log": "AGR_WRITE_DONE\n"}),
                   encoding="utf-8")
    monkeypatch.setattr(mod.subprocess, "run", lambda *args, **kwargs: _proc(0))
    call = mod.run_acad(tmp_path / "wrapper.py", tmp_path / "write.scr", log)
    assert call["timeout"] is True and call["call_ok"] is False and call["wrapper_code"] == 5


def test_geometry_ok_with_error_returncode_fails(tmp_path, monkeypatch):
    log = tmp_path / "read.log.json"
    log.write_text(json.dumps({"status": "error", "exit_code": 1, "seconds": 1.5, "log": "AGR_READ_DONE\n"}),
                   encoding="utf-8")
    monkeypatch.setattr(mod.subprocess, "run", lambda *args, **kwargs: _proc(1))
    call = mod.run_acad(tmp_path / "wrapper.py", tmp_path / "read.scr", log)
    assert call["parsed"]["read_done"] is True and call["call_ok"] is False and call["returncode"] == 1
    record = mod._call_record(call, [tmp_path / "drawing.dwg"])
    record["compare"] = {"ok": True}
    rep = _good_rep()
    rep["read_dwg"] = record
    assert mod.results_ok(_offline_ok(1), {"aborted": None, "repetitions": [rep]}, _probes(), False, 1) is False


def test_missing_cross_check_fails():
    rep = _good_rep()
    del rep["native_on_ezdxf_dxf"]
    assert mod.results_ok(_offline_ok(1), {"aborted": None, "repetitions": [rep]}, _probes(), False, 1) is False
    rep = _good_rep()
    del rep["ezdxf_on_native_dxf"]["compare"]
    assert mod.results_ok(_offline_ok(1), {"aborted": None, "repetitions": [rep]}, _probes(), False, 1) is False


def test_documented_open_failure_is_not_global_success():
    rep = _good_rep()
    rep["native_on_native_dxf"]["documented_open_failure"] = True
    assert mod.results_ok(_offline_ok(1), {"aborted": None, "repetitions": [rep]}, _probes(), False, 1) is False


def test_exact_repeat_count():
    probes = _probes()
    native = {"aborted": None, "repetitions": [_good_rep()]}
    assert mod.results_ok(_offline_ok(1), native, probes, False, 1) is True
    assert mod.results_ok(_offline_ok(1), native, probes, False, 3) is False
    assert mod.results_ok(_offline_ok(3), native, probes, False, 3) is False
