"""Task-to-model gate contract; all generated bundle data is SYNTHETIC."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
GATES = ("inputs", "parts", "operations", "budgets", "export_readback", "report", "visual", "checker")


def load():
    assert importlib.util.find_spec("dt_ai.procedure") is not None, "Missing task-to-model validator"
    from dt_ai import procedure
    return procedure


def test_each_missing_gate(tmp_path):
    p = load()
    for omitted in GATES:
        job = {"schema_version": "1.0.0", "job_id": "SYNTHETIC", "run_id": "r1",
               "synthetic": True, "path": "standard", "deviations": [],
               "gates": {g: {"status": "missing", "note": "not executed", "evidence": []}
                         for g in GATES if g != omitted}}
        report = p.inspect_job(job, tmp_path)
        assert report["passed"] is False
        assert len(report["gates"]) == 8
        assert omitted in report["errors"][0]


def store(root, name, value):
    path = root / name
    text = json.dumps(value) if not isinstance(value, str) else value
    path.write_text(text, encoding="utf-8")
    return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


@pytest.fixture
def bundle(tmp_path):
    p = load()
    source = store(tmp_path, "source.txt", "SYNTHETIC test source")
    artifact = store(tmp_path, "export.json", {"synthetic": True})
    report = store(tmp_path, "report.md", "# SYNTHETIC test-only report")
    sheet = store(tmp_path, "sheet.html", "SYNTHETIC test-only review page")
    parts = store(tmp_path, "parts.json", {
        "synthetic": True, "object_id": "SYNTH", "source_tier": "B",
        "sources": [{"kind": "synthetic", "reference": "source.txt"}],
        "triangle_budget": {"npm": 10, "vpm": 10},
        "parts": [{"id": "wall", "part_class": "wall", "sources": [{"kind": "object", "reference": "wall"}],
                   "operation": "keep", "triangle_budget": {"npm": 2, "vpm": 2}}],
        "status": "confirmed", "gate1": {"actor": "synthetic test user", "date": "2026-10-20",
                                           "scope": "synthetic_fixture", "note": "TEST ONLY"}})
    gates = {g: {"status": "pass", "note": "SYNTHETIC contract test only", "evidence": []} for g in GATES}
    gates["inputs"]["evidence"] = [source]
    gates["parts"]["evidence"] = [parts]
    gates["report"]["evidence"] = [report]
    for gate in ("operations", "budgets", "export_readback", "visual", "checker"):
        receipt = {"gate": gate, "run_id": "r1", "artifact_sha256": [artifact["sha256"]]}
        if gate == "operations":
            receipt.update(operations=["keep"], checks={f"{phase}.{name}": "pass"
                           for phase in ("before", "after") for name in p.INVARIANTS})
        elif gate == "budgets":
            receipt["measurements"] = [{"value": 2, "limit": 10, "comparison": "le", "rule": "synthetic limit"}]
        elif gate == "export_readback":
            receipt.update(clean_process=True, checks={x: "pass" for x in ("topology", "uv", "materials", "transforms")})
        elif gate == "visual":
            receipt.update(decision="approved", actor_role="user", actor="synthetic test user", date="2026-10-20",
                           scope="synthetic_fixture", review_tool="synthetic board", decision_reference="TEST ONLY",
                           sheet=sheet, checks={x: "pass" for x in
                           ("face_orientation", "album_overlay", "source_overlay", "material_legend", "sections")})
        else:
            receipt.update(tool="SINTEZ AGR Checker", complete=True, checks={"synthetic_check": "pass"})
        gates[gate]["evidence"] = [store(tmp_path, f"{gate}.json", receipt)]
    job = {"schema_version": "1.0.0", "job_id": "SYNTHETIC", "run_id": "r1", "synthetic": True,
           "inputs": [source], "artifacts": [artifact], "path": "standard", "deviations": [], "gates": gates}
    return job


def test_complete_synthetic_walk(bundle, tmp_path):
    assert load().inspect_job(bundle, tmp_path)["passed"] is True
    job = tmp_path / "job.yaml"
    job.write_text(yaml.safe_dump(bundle), encoding="utf-8")
    assert load().main([str(job), "--root", str(tmp_path)]) == 0


@pytest.mark.parametrize("gate", GATES)
def test_missing_gate_cli(bundle, tmp_path, gate):
    del bundle["gates"][gate]
    path = tmp_path / "job.yaml"
    path.write_text(yaml.safe_dump(bundle), encoding="utf-8")
    assert load().main([str(path), "--root", str(tmp_path)]) == 1


def test_gate_map_order(bundle, tmp_path):
    expected = load().inspect_job(bundle, tmp_path)
    bundle["gates"] = dict(reversed(list(bundle["gates"].items())))
    assert load().inspect_job(bundle, tmp_path) == expected


def test_reset_receipts(bundle, tmp_path):
    bundle["run_id"] = "r2"
    result = load().inspect_job(bundle, tmp_path)
    assert not result["passed"]
    assert next(r for r in result["gates"] if r["gate"] == "operations")["status"] == "fail"


def test_repeated_walk(bundle, tmp_path):
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    results = [load().inspect_job(bundle, tmp_path) for _ in range(3)]
    assert results[0] == results[1] == results[2]
    assert before == {p: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize("raw", ["", "null", "{}", "[]", "schema_version: 2", ".nan", ".inf",
                               "gates: 3", "gates: {inputs: null}", "a: 1\na: 2"])
def test_invalid_contract(tmp_path, raw):
    path = tmp_path / "job.yaml"
    path.write_text(raw, encoding="utf-8")
    assert load().main([str(path), "--root", str(tmp_path)]) == 1


@pytest.mark.parametrize("value,limit,comparison,passed", [
    (float("nan"), 10, "le", False), (float("inf"), 10, "le", False),
    (1, float("inf"), "le", False), (10, 10, "lt", False), (10, 10, "le", True),
    (11, 10, "le", False), (-1, 10, "le", False), (True, 10, "le", False), (1, 10, "unknown", False)])
def test_budget_boundaries(bundle, tmp_path, value, limit, comparison, passed):
    ref = bundle["gates"]["budgets"]["evidence"][0]
    receipt = json.loads((tmp_path / ref["path"]).read_text())
    receipt["measurements"][0].update(value=value, limit=limit, comparison=comparison)
    bundle["gates"]["budgets"]["evidence"] = [store(tmp_path, ref["path"], receipt)]
    assert load().inspect_job(bundle, tmp_path)["passed"] is passed


@pytest.mark.parametrize("gate", ("parts", "operations", "budgets", "export_readback", "visual", "checker"))
def test_unrelated_receipts(bundle, tmp_path, gate):
    bundle["gates"][gate]["evidence"] = [bundle["inputs"][0]]
    assert not load().inspect_job(bundle, tmp_path)["passed"]


@pytest.mark.parametrize("mode", ("job", "source", "receipt", "hardlink", "resolved", "missing_input"))
def test_output_alias(bundle, tmp_path, mode):
    path = tmp_path / "job.yaml"
    if mode == "missing_input":
        (tmp_path / "source.txt").unlink()
    path.write_text(yaml.safe_dump(bundle), encoding="utf-8")
    output = {"job": path, "source": tmp_path / "source.txt", "receipt": tmp_path / "checker.json",
              "resolved": tmp_path / "." / "source.txt", "missing_input": tmp_path / "source.txt"}.get(mode)
    if mode == "hardlink":
        output = tmp_path / "alias.yaml"
        os.link(path, output)
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    assert load().main([str(path), "--root", str(tmp_path), "--output", str(output)]) == 1
    assert before == {p: p.read_bytes() for p in tmp_path.iterdir()}


def test_deviations(bundle, tmp_path):
    log = {"gate": "operations", "what_failed": "synthetic failure", "what_was_tried": "synthetic alternative",
           "new_tool_written": "none", "result": "synthetic success"}
    bundle.update(path="deviation", deviations=[log])
    assert load().inspect_job(bundle, tmp_path)["passed"]
    for field in log:
        broken = copy.deepcopy(bundle)
        del broken["deviations"][0][field]
        assert not load().inspect_job(broken, tmp_path)["passed"]
    for gate in GATES:
        broken = copy.deepcopy(bundle)
        broken["gates"][gate] = {"status": "missing", "note": "not run", "evidence": []}
        assert not load().inspect_job(broken, tmp_path)["passed"]


def test_evidence_integrity(bundle, tmp_path):
    for name in ("source.txt", "parts.json", "export.json", "sheet.html"):
        path = tmp_path / name
        old = path.read_bytes()
        path.write_bytes(b"changed")
        assert not load().inspect_job(bundle, tmp_path)["passed"]
        path.write_bytes(old)


def test_repository_walks():
    for name in ("KERNEL-SYNTHETIC", "VATUTINO-SITE"):
        job = yaml.safe_load((ROOT / "jobs" / name / "job.yaml").read_text(encoding="utf-8"))
        result = load().inspect_job(job, ROOT)
        assert not result["passed"] and not result["errors"]
        assert [r["gate"] for r in result["gates"]] == list(GATES)
        assert result["gates"][0]["status"] == ("pass" if name == "KERNEL-SYNTHETIC" else "review")
        assert any(e["verified"] for row in result["gates"] for e in row["evidence_exists"])
        assert not any(row["errors"] for row in result["gates"])
        assert {row["gate"] for row in result["gates"] if row["status"] == "missing"} >= {"visual", "checker"}


def test_playbook_and_schema():
    p = load()
    schema = json.loads((ROOT / "schemas/JobChecklist.schema.json").read_text(encoding="utf-8"))
    assert schema == p.JobChecklist.model_json_schema()
    text = (ROOT / "docs/procedure/TASK_TO_MODEL.md").read_text(encoding="utf-8")
    for name in GATES + ("what_failed", "what_was_tried", "new_tool_written", "result"):
        assert name in text
    assert "docs/procedure/TASK_TO_MODEL.md" in (ROOT / "AGENTS.md").read_text(encoding="utf-8")

@pytest.mark.parametrize("field,bad", [("operations", "keep"), ("operations", {"keep": "pass"}),
                                      ("operations", [""]), ("checks", {"": "pass"})])
def test_malformed_operation_receipt(bundle, tmp_path, field, bad):
    ref = bundle["gates"]["operations"]["evidence"][0]
    receipt = json.loads((tmp_path / ref["path"]).read_text())
    receipt[field] = bad
    bundle["gates"]["operations"]["evidence"] = [store(tmp_path, ref["path"], receipt)]
    assert not load().inspect_job(bundle, tmp_path)["passed"]


def test_generated_gate_subsets(bundle, tmp_path):
    # Exhaust every presence subset, not just the eight one-at-a-time omissions.
    p = load()
    for bits in range(256):
        candidate = copy.deepcopy(bundle)
        candidate["gates"] = {g: v for i, (g, v) in enumerate(candidate["gates"].items()) if bits & (1 << i)}
        assert p.inspect_job(candidate, tmp_path)["passed"] is (bits == 255)


def test_generated_required_checks(bundle, tmp_path):
    p = load()
    for gate in ("operations", "export_readback", "visual"):
        ref = bundle["gates"][gate]["evidence"][0]
        receipt = json.loads((tmp_path / ref["path"]).read_text())
        for check in receipt["checks"]:
            candidate = copy.deepcopy(bundle)
            bad = copy.deepcopy(receipt)
            del bad["checks"][check]
            candidate["gates"][gate]["evidence"] = [store(tmp_path, "bad.json", bad)]
            assert not p.inspect_job(candidate, tmp_path)["passed"]


@pytest.mark.parametrize("status", ("fail", "review", "not_run"))
def test_checker_not_measured_never_passes(bundle, tmp_path, status):
    ref = bundle["gates"]["checker"]["evidence"][0]
    receipt = json.loads((tmp_path / ref["path"]).read_text())
    receipt["checks"]["synthetic_check"] = status
    bundle["gates"]["checker"]["evidence"] = [store(tmp_path, ref["path"], receipt)]
    assert not load().inspect_job(bundle, tmp_path)["passed"]
