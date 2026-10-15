"""No-DCC tests for the E2 fail-closed probe. Synthetic fixtures only."""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parent / "experiment.py"
_SPEC = importlib.util.spec_from_file_location("bim_autocad_agr_e2", _PATH)
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)

FEAT = [
    {"layer": "SYN_L0_CONTOUR", "kind": "LWPOLYLINE", "closed": True,
     "vertices_mm": [[0.0, 0.0, 0.0], [1000.0, 0.0, 0.0], [1000.0, 500.0, 0.0], [0.0, 500.0, 0.0]]},
    {"layer": "SYN_L0_OPEN_0", "kind": "POLYLINE", "closed": True,
     "vertices_mm": [[0.0, 0.0, 0.0], [100.0, 0.0, 0.0], [100.0, 0.0, 100.0], [0.0, 0.0, 100.0]]},
    {"layer": "SYN_L0_LEVEL", "kind": "POINT", "closed": False, "vertices_mm": [[0.0, 0.0, 0.0]]},
]


def _dxf(tmp_path, variant=None):
    pytest.importorskip("ezdxf")
    path = tmp_path / f"{variant or 'clean'}.dxf"
    mod.base.write_dxf(FEAT, path)
    if variant:
        mod.apply_variant(path, variant)
    return path


def test_clean_accepts_with_zero_deviation(tmp_path):
    result = mod.strict_read(_dxf(tmp_path))
    report = mod.base.compare_features(FEAT, result["features"], result["insunits"], 0.01)
    assert result["accepted"] is True and result["diagnostics"] == []
    assert report["ok"] is True and report["max_deviation_mm"] == 0


@pytest.mark.parametrize("variant,reason", [
    ("bulge", "curved_segment"), ("hatch", "unsupported_type"), ("nested_insert", "block_not_normalized"),
    ("missing_xref", "missing_xref"), ("spline", "unsupported_type"), ("open_contour", "open_contour"),
])
def test_mutations_fail_closed(tmp_path, variant, reason):
    path = _dxf(tmp_path, variant)
    result = mod.strict_read(path)
    reasons = {item["reason"] for item in result["diagnostics"]}
    assert result["accepted"] is False and result["features"] == []
    assert reason in reasons and result["inventory"]
    if variant == "missing_xref":
        assert "block_not_normalized" in reasons
        assert any(str(item.get("xref_path", "")).replace("\\", "/").endswith("agr-e2-xref.dwg") for item in result["diagnostics"])
    if variant == "hatch":
        hatch = next(item for item in result["inventory"] if item["type"] == "HATCH")
        assert hatch["layer"] == "hole"
        saved = mod.base._import_ezdxf().readfile(path)
        assert len(next(entity for entity in saved.modelspace() if entity.dxftype() == "HATCH").paths) == 2
    if variant == "open_contour":
        entities, audit = mod.base.read_dxf(path)
        assert mod.base.compare_features(FEAT, entities, audit["insunits"])["ok"] is False


def test_baseline_silently_accepts_bulge_and_spline(tmp_path):
    for variant in ("bulge", "spline"):
        path = _dxf(tmp_path, variant)
        entities, audit = mod.base.read_dxf(path)
        assert mod.base.compare_features(FEAT, entities, audit["insunits"])["ok"] is True
        assert mod.strict_read(path)["features"] == []


def test_nested_insert_parent_chain(tmp_path):
    path = _dxf(tmp_path, "nested_insert")
    result = mod.strict_read(path)
    nested = [item for item in result["inventory"] if item["type"] == "LWPOLYLINE" and item["parents"]]
    assert result["features"] == [] and len(nested[0]["parents"]) == 2
    doc = mod.base._import_ezdxf().readfile(path)
    inner = next(entity for entity in doc.blocks.get("OUTER_REF") if entity.dxftype() == "INSERT")
    assert inner.dxf.xscale != inner.dxf.yscale and inner.dxf.rotation != 0


def test_wrong_units_reject_without_features(tmp_path):
    path = _dxf(tmp_path)
    doc = mod.base._import_ezdxf().readfile(path)
    doc.header["$INSUNITS"] = 6
    doc.saveas(path)
    result = mod.strict_read(path)
    assert result["accepted"] is False and result["features"] == []
    assert any(item["reason"] == "unit_mismatch" for item in result["diagnostics"])
    assert any(item["type"] == "LWPOLYLINE" for item in result["inventory"])


def test_polyface_and_curved_polyline(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4
    model = doc.modelspace()
    face = model.add_polyface(dxfattribs={"layer": "PF"})
    face.append_face([(0, 0, 0), (1, 0, 0), (0, 1, 0)])
    curve = model.add_polyline2d([(0, 0), (2, 0), (2, 1)], close=True, dxfattribs={"layer": "C2"})
    curve.vertices[0].dxf.bulge = 0.4
    path = tmp_path / "poly.dxf"
    doc.saveas(path)
    result = mod.strict_read(path)
    reasons = {item["reason"] for item in result["diagnostics"]}
    assert result["features"] == [] and {"unsupported_polyline", "curved_segment"} <= reasons


def test_duplicate_layer(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4
    model = doc.modelspace()
    model.add_point((0, 0, 0), dxfattribs={"layer": "DUP"})
    model.add_point((1, 0, 0), dxfattribs={"layer": "DUP"})
    path = tmp_path / "dup.dxf"
    doc.saveas(path)
    result = mod.strict_read(path)
    assert result["accepted"] is False and result["features"] == []
    assert sum(item["reason"] == "duplicate_layer" for item in result["diagnostics"]) == 2


def test_empty_document_rejects(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4
    path = tmp_path / "empty.dxf"
    doc.saveas(path)
    result = mod.strict_read(path)
    assert result["accepted"] is False and result["features"] == []
    assert any(item["reason"] == "empty_document" for item in result["diagnostics"])


def test_missing_block_and_cycle_emit_diagnostics(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4
    doc.modelspace().add_blockref("NO_SUCH_BLOCK", (0, 0))
    first, second = doc.blocks.new("CYCLE_A"), doc.blocks.new("CYCLE_B")
    first.add_blockref("CYCLE_B", (0, 0))
    second.add_blockref("CYCLE_A", (0, 0))
    doc.modelspace().add_blockref("CYCLE_A", (0, 0))
    path = tmp_path / "cycle.dxf"
    doc.saveas(path)
    reasons = {item["reason"] for item in mod.strict_read(path)["diagnostics"]}
    assert {"missing_block", "block_cycle", "block_not_normalized"} <= reasons


def test_depth_limit_emits_diagnostic(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4
    names = [f"NEST_{index:02d}" for index in range(mod.BLOCK_DEPTH + 1)]
    for index, name in enumerate(names):
        block = doc.blocks.new(name)
        if index + 1 < len(names):
            block.add_blockref(names[index + 1], (0, 0))
        else:
            block.add_point((0, 0, 0), dxfattribs={"layer": "DEEP"})
    doc.modelspace().add_blockref(names[0], (0, 0))
    path = tmp_path / "deep.dxf"
    doc.saveas(path)
    result = mod.strict_read(path)
    assert any(item["reason"] == "depth_limit" for item in result["diagnostics"])
    assert result["accepted"] is False and result["features"] == []


def test_other_xref_is_unresolved_without_expansion(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4
    block = doc.blocks.new("OTHER_XREF")
    block.block.dxf.flags = int(block.block.dxf.flags) | 4
    block.block.dxf.xref_path = "nested/other.dwg"
    doc.modelspace().add_blockref("OTHER_XREF", (0, 0))
    path = tmp_path / "xref.dxf"
    doc.saveas(path)
    result = mod.strict_read(path)
    reasons = {item["reason"] for item in result["diagnostics"]}
    assert result["accepted"] is False and result["features"] == []
    assert "unresolved_xref" in reasons and "missing_xref" not in reasons
    assert any(item.get("xref_path") == "nested/other.dwg" for item in result["diagnostics"])


def test_census_script_matches_baseline_newlines(tmp_path):
    path = tmp_path / "census.scr"
    mod.base.write_script(path, mod.CENSUS)
    raw = path.read_bytes()
    assert raw.endswith(b"(princ)\r\n")
    assert not raw.endswith(b"\r\n\r\n")
    assert b"\r\r\n" not in raw
    assert raw.count(b"\n") == raw.count(b"\r\n")


def _completed(code, stdout="", stderr=""):
    return type("Proc", (), {"returncode": code, "stdout": stdout, "stderr": stderr})()


def _census_dwg(tmp_path):
    pytest.importorskip("ezdxf")
    path = tmp_path / "copy.dxf"
    mod.base.write_dxf(FEAT[:1], path)
    entity = next(iter(mod.base._import_ezdxf().readfile(path).modelspace()))
    raw = f"AGR_RAW|{str(entity.dxf.handle).upper()}|{entity.dxftype()}|{entity.dxf.layer}"
    log = f"AGR_ID|25.0|{path.name}|4\n{raw}\nAGR_CENSUS_DONE\n"
    return path, log


def _invoke_patched(monkeypatch, tmp_path, dwg, payload, code=0, stdout="", stderr="", expire=False):
    def fake_run(cmd, **kwargs):
        out = Path(cmd[cmd.index("--out") + 1])
        out.write_text(json.dumps(payload), encoding="utf-8")
        if expire:
            raise subprocess.TimeoutExpired(cmd, 120, output=stdout, stderr=stderr)
        return _completed(code, stdout, stderr)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    return mod._invoke(tmp_path / "wrapper.py", dwg, tmp_path / "census.scr", tmp_path / "census.json")


def test_invoke_parses_payload_log_once(tmp_path, monkeypatch):
    dwg, log = _census_dwg(tmp_path)
    poisoned = json.dumps({"log": log + "AGR_RAW|DEAD|LINE|0\n", "note": "error: ; error bad argument"})
    result = _invoke_patched(
        monkeypatch, tmp_path, dwg, {"status": "ok", "code": 0, "log": log}, stdout=poisoned)
    assert result["ok"] is True and result["cause"] is None
    assert result["match"] is True and result["identity_ok"] is True
    assert result["diagnostics"]["marker"] is True
    assert result["diagnostics"]["log_tokens"] == [] and result["diagnostics"]["stderr_tokens"] == []


def test_invoke_rejects_timeout_nonzero_marker_and_mismatch(tmp_path, monkeypatch):
    dwg, log = _census_dwg(tmp_path)
    good = {"status": "ok", "code": 0, "log": log}
    timed = _invoke_patched(monkeypatch, tmp_path, dwg, {"status": "timeout", "code": 0, "log": log})
    assert timed["ok"] is False and timed["cause"] == "timeout"
    assert timed["match"] is True and timed["identity_ok"] is True and timed["diagnostics"]["marker"] is True

    expired = _invoke_patched(monkeypatch, tmp_path, dwg, good, expire=True, stdout='{"error": "bad argument"}')
    assert expired["ok"] is False and expired["cause"] == "timeout" and expired["match"] is True

    wrapper_timeout = _invoke_patched(monkeypatch, tmp_path, dwg, good, code=5)
    assert wrapper_timeout["ok"] is False and wrapper_timeout["cause"] == "timeout" and wrapper_timeout["identity_ok"] is True

    nonzero = _invoke_patched(monkeypatch, tmp_path, dwg, good, code=2)
    assert nonzero["ok"] is False and nonzero["cause"] == "exit_2" and nonzero["match"] is True

    unmarked = log.replace("AGR_CENSUS_DONE\n", "")
    missing = _invoke_patched(monkeypatch, tmp_path, dwg, {"status": "ok", "code": 0, "log": unmarked})
    assert missing["ok"] is False and missing["cause"] == "missing_marker"
    assert missing["identity_ok"] is True and missing["diagnostics"]["marker"] is False

    mismatch = _invoke_patched(
        monkeypatch, tmp_path, dwg,
        {"status": "ok", "code": 0, "log": "AGR_ID|25.0|copy.dxf|4\nAGR_RAW|0|LINE|0\nAGR_CENSUS_DONE\n"})
    assert mismatch["ok"] is False and mismatch["cause"] == "inventory_mismatch" and mismatch["match"] is False

    stderr_hit = _invoke_patched(monkeypatch, tmp_path, dwg, good, stderr="error: real")
    assert stderr_hit["ok"] is False and stderr_hit["cause"] == "error_token"
    assert stderr_hit["diagnostics"]["stderr_tokens"] == ["error:"] and stderr_hit["match"] is True


def test_summary_rejects_partial_empty_and_missing_native(tmp_path, monkeypatch):
    ids = mod._expected_case_ids()
    assert len(ids) == 15 and len(set(ids)) == 15
    metas = {case_id: {"id": case_id} for case_id in ids}
    assert mod._stored_ok({"repeats": 3, "cases": []}, metas, lambda meta, row: True) is False
    partial = [{"id": ids[0], "seconds_raw": [0.1, 0.2, 0.3]}]
    assert mod._stored_ok({"repeats": 3, "cases": partial}, metas, lambda meta, row: True) is False
    duplicated = [{"id": ids[0], "seconds_raw": [0.1, 0.2, 0.3]} for _ in ids]
    assert mod._stored_ok({"repeats": 3, "cases": duplicated}, metas, lambda meta, row: True) is False
    short = [{"id": case_id, "seconds_raw": [0.1, 0.2]} for case_id in ids]
    assert mod._stored_ok({"repeats": 3, "cases": short}, metas, lambda meta, row: True) is False
    good_rows = [{"id": case_id, "accepted": True, "seconds_raw": [0.1, 0.2, 0.3, 0.4]} for case_id in ids]
    assert mod._stored_ok({"repeats": 3, "cases": good_rows}, metas, lambda meta, row: True) is True

    def buckets(ok_reps, fail_reps=0):
        reps = [{"ok": False} for _ in range(fail_reps)] + [{"ok": True} for _ in range(ok_reps)]
        return {case_id: {"repetitions": list(reps)} for case_id in ids}

    case_doc = {"repeats": 3, "cases": [{"id": case_id} for case_id in ids]}
    assert mod._native_contract({"repeats": 3, "aborted": None, "cases": buckets(3, 2)}, case_doc) is True
    assert mod._native_contract({"repeats": 3, "aborted": None, "cases": buckets(5, 1)}, case_doc) is True
    assert mod._native_contract({"repeats": 3, "aborted": None, "cases": buckets(2, 4)}, case_doc) is False
    assert mod._native_contract({"repeats": 0, "aborted": None, "cases": buckets(3)}, case_doc) is False
    assert mod._native_contract({"repeats": 3, "aborted": None, "cases": {}}, {"repeats": 3, "cases": []}) is False
    extra = buckets(3)
    extra["unknown_case"] = {"repetitions": [{"ok": True}, {"ok": True}, {"ok": True}]}
    assert mod._native_contract({"repeats": 3, "aborted": None, "cases": extra}, case_doc) is False
    assert mod._native_contract(None, case_doc) is None

    scratch = tmp_path / "scratch"
    scratch.mkdir()
    for name in ("cases.json", "baseline.json", "strict.json"):
        (scratch / name).write_text("{}", encoding="utf-8")
    monkeypatch.setattr(mod, "_hash_report", lambda path: (True, [], []))
    reads = {
        "cases.json": case_doc,
        "baseline.json": {"repeats": 3, "cases": good_rows},
        "strict.json": {"repeats": 3, "cases": good_rows},
    }
    monkeypatch.setattr(mod, "_read", lambda path: reads[Path(path).name])
    monkeypatch.setattr(mod, "_baseline_ok", lambda meta, row: True)
    monkeypatch.setattr(mod, "_strict_ok", lambda meta, row: True)
    assert mod.phase_summary(scratch) == 1
    summary = json.loads((scratch / "summary.json").read_text(encoding="utf-8"))
    assert summary["baseline_contract"] is True and summary["strict_contract"] is True
    assert summary["native_contract"] is None

    reads["baseline.json"] = {"repeats": 3, "cases": []}
    reads["strict.json"] = {"repeats": 3, "cases": []}
    reads["native.json"] = {"repeats": 3, "aborted": None, "cases": {}}
    (scratch / "native.json").write_text("{}", encoding="utf-8")
    assert mod.phase_summary(scratch) == 1
    summary = json.loads((scratch / "summary.json").read_text(encoding="utf-8"))
    assert summary["baseline_contract"] is False and summary["strict_contract"] is False
    assert summary["native_contract"] is False
