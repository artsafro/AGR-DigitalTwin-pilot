"""Cold-run fixes B (#1310): job.yaml template and per-gate walker errors (F17),
duplicated inputs rows (F20). Everything here is SYNTHETIC test data."""
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from dt_ai import procedure as p

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "jobs/_template/job.yaml"


def ref(root, name, text="SYNTHETIC source"):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def job(tmp_path, inputs=None, **gates):
    inputs = inputs or [ref(tmp_path, "source.txt")]
    rows = {g: {"status": "missing"} for g in p.GATES}
    rows["inputs"] = {"status": "pass", "note": "SYNTHETIC", "evidence": copy.deepcopy(inputs)}
    rows.update(gates)
    return {"schema_version": "1.0.0", "job_id": "SYNTHETIC", "run_id": "r1", "synthetic": True,
            "path": "standard", "inputs": inputs, "artifacts": [], "deviations": [], "gates": rows}


def row(result, gate):
    return next(r for r in result["gates"] if r["gate"] == gate)


def walk_cli(tmp_path, data, root):
    path = tmp_path / "walk.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return subprocess.run([sys.executable, "-m", "dt_ai.procedure", str(path), "--root", str(root)],
                          cwd=ROOT, capture_output=True, text=True, timeout=60)


# --- F17: template -----------------------------------------------------------------------------

def test_template_walks_exit_1_without_errors(tmp_path):
    data = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
    result = p.inspect_job(data, ROOT)
    assert result["passed"] is False and result["errors"] == []
    assert [r["gate"] for r in result["gates"]] == list(p.GATES)
    assert all(r["status"] == "missing" and not r["errors"] for r in result["gates"])
    proc = subprocess.run([sys.executable, "-m", "dt_ai.procedure", str(TEMPLATE), "--root", str(ROOT)],
                          cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 1, proc.stderr
    out = json.loads(proc.stdout)
    assert out["passed"] is False and out["errors"] == []


def test_template_input_hash_is_live():
    data = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
    (only,) = data["inputs"]
    assert hashlib.sha256((ROOT / only["path"]).read_bytes()).hexdigest() == only["sha256"]


def test_missing_gate_needs_no_note_or_evidence(tmp_path):
    result = p.inspect_job(job(tmp_path), tmp_path)
    assert result["errors"] == []
    assert row(result, "inputs")["status"] == "pass"
    assert all(row(result, g)["status"] == "missing" for g in p.GATES[1:])


@pytest.mark.parametrize("status", ["review", "fail", "pass"])
def test_started_gate_still_needs_note(tmp_path, status):
    gate = {"status": status, "evidence": [ref(tmp_path, "x.txt")]}
    result = p.inspect_job(job(tmp_path, parts=gate), tmp_path)
    assert result["passed"] is False
    assert any("gates.parts" in e and "note" in e for e in row(result, "parts")["errors"])
    assert row(result, "parts")["status"] == "fail"


def test_pass_without_evidence_still_fails_and_names_gate(tmp_path):
    result = p.inspect_job(job(tmp_path, budgets={"status": "pass", "note": "SYNTHETIC"}), tmp_path)
    assert result["passed"] is False
    assert any("gates.budgets" in e and "pass requires evidence" in e for e in row(result, "budgets")["errors"])


def test_one_bad_gate_does_not_blank_the_others(tmp_path):
    # Before #1310 one pydantic error reported every gate as `missing`.
    data = job(tmp_path, visual={"status": "review", "note": "SYNTHETIC", "waits": "someone"})
    result = p.inspect_job(data, tmp_path)
    assert result["passed"] is False
    assert row(result, "inputs")["status"] == "pass"
    assert row(result, "visual")["status"] == "fail"
    assert row(result, "visual")["errors"] and not row(result, "inputs")["errors"]
    assert all(r["ready"] is False for r in result["gates"])  # an invalid checklist is never ready
    assert any(e.startswith("gates.visual.waits") for e in result["errors"])


def test_cli_error_output_names_failing_gate(tmp_path):
    data = job(tmp_path, report={"status": "review"})
    proc = walk_cli(tmp_path, data, tmp_path)
    assert proc.returncode == 1
    out = json.loads(proc.stdout)
    assert any(e.startswith("gates.report.note") for e in out["errors"])
    assert row(out, "report")["status"] == "fail"


def test_top_level_error_named_by_field(tmp_path):
    data = job(tmp_path)
    data["inputs"] = []
    result = p.inspect_job(data, tmp_path)
    assert result["passed"] is False
    assert any(e.startswith("inputs:") for e in result["errors"])


@pytest.mark.parametrize("raw", [None, [], 3, "x", {"gates": 3}, {"gates": {"inputs": None}}])
def test_malformed_never_passes(tmp_path, raw):
    result = p.inspect_job(raw, tmp_path)
    assert result["passed"] is False and result["errors"]
    assert len(result["gates"]) == 8


# --- F20: duplicated inputs rows ---------------------------------------------------------------

@pytest.mark.parametrize("second", ["source.txt", "./source.txt"])
def test_duplicated_inputs_row_is_error_naming_path(tmp_path, second):
    first = ref(tmp_path, "source.txt")
    dup = {**first, "path": second}
    result = p.inspect_job(job(tmp_path, inputs=[first, dup]), tmp_path)
    inputs = row(result, "inputs")
    assert result["passed"] is False and inputs["status"] == "fail" and inputs["ready"] is False
    assert any("duplicated" in e and "source.txt" in e for e in inputs["errors"])


def test_duplicated_path_with_other_hash_is_error(tmp_path):
    first = ref(tmp_path, "source.txt")
    other = {"path": "source.txt", "sha256": "0" * 64}
    result = p.inspect_job(job(tmp_path, inputs=[first, other]), tmp_path)
    assert any("duplicated" in e and "source.txt" in e for e in row(result, "inputs")["errors"])


def test_duplicated_inputs_gate_evidence_is_error_when_not_pass(tmp_path):
    first = ref(tmp_path, "source.txt")
    data = job(tmp_path, inputs=[first])
    data["gates"]["inputs"] = {"status": "review", "note": "SYNTHETIC", "evidence": [first, dict(first)]}
    result = p.inspect_job(data, tmp_path)
    assert row(result, "inputs")["status"] == "fail"
    assert any("duplicated" in e and "source.txt" in e for e in row(result, "inputs")["errors"])


def test_duplicated_manifest_row_rehashed_once(tmp_path):
    ext = ref(tmp_path / "ext", "a.bin", "SYNTHETIC external")
    manifest = ref(tmp_path, "sources.json", json.dumps(
        {"manifest": "external-inputs/1", "files": [{"path": str(tmp_path / "ext/a.bin"), "sha256": ext["sha256"]}]}))
    manifest["manifest"] = "external-inputs/1"
    result = p.inspect_job(job(tmp_path, inputs=[manifest, dict(manifest)]), tmp_path)
    inputs = row(result, "inputs")
    assert inputs["status"] == "fail"
    assert any("duplicated" in e and "sources.json" in e for e in inputs["errors"])
    assert len(inputs["external_inputs"]) == 1


def test_distinct_inputs_still_pass(tmp_path):
    rows = [ref(tmp_path, "a.txt", "A"), ref(tmp_path, "b.txt", "B"), ref(tmp_path, "sub/a.txt", "A")]
    result = p.inspect_job(job(tmp_path, inputs=rows), tmp_path)
    assert row(result, "inputs")["status"] == "pass" and not row(result, "inputs")["errors"]


def test_generated_distinct_vs_duplicated_inputs(tmp_path):
    """Probe: any inputs list with a repeated path fails naming it; a list of distinct paths passes."""
    import random
    rng = random.Random(1310)
    names = [ref(tmp_path, f"f{i}.txt", f"S{i}") for i in range(6)]
    checked = 0
    for _ in range(40):
        picked = rng.sample(names, rng.randint(1, 6))
        dup = rng.random() < 0.5
        rows = copy.deepcopy(picked)
        if dup:
            rows.insert(rng.randint(0, len(rows)), dict(rng.choice(picked)))
        inputs = row(p.inspect_job(job(tmp_path, inputs=rows), tmp_path), "inputs")
        assert (inputs["status"] == "fail") is dup, rows
        if dup:
            assert any("duplicated" in e for e in inputs["errors"])
        checked += 1
    assert checked == 40
