"""Gate wait reasons in the job walker (#1204, KPP1 cold-run F4).

new-case: optional ``waits`` (user / max / visual) on a JobChecklist gate, counted by the walker.

All jobs here are SYNTHETIC temp files except the read-only walk of the committed KPP1 job.
"""
import hashlib
import json
import random
import subprocess
import sys
from collections import Counter
from pathlib import Path

import jsonschema
import pytest
import yaml

from dt_ai import procedure as p

ROOT = Path(__file__).resolve().parents[1]
REASONS = ("user", "max", "visual")


def make_job(tmp_path, **waits):
    data = b"SYNTHETIC source\n"
    (tmp_path / "src.txt").write_bytes(data)
    ref = {"path": "src.txt", "sha256": hashlib.sha256(data).hexdigest()}
    gates = {g: {"status": "missing", "note": "SYNTHETIC", "evidence": []} for g in p.GATES}
    gates["inputs"] = {"status": "pass", "note": "SYNTHETIC", "evidence": [ref]}
    for gate, reason in waits.items():
        gates[gate]["waits"] = reason
    return {"schema_version": "1.0.0", "job_id": "SYNTHETIC", "run_id": "r1", "synthetic": True,
            "path": "standard", "inputs": [ref], "artifacts": [], "deviations": [], "gates": gates}


def schema():
    return json.loads((ROOT / "schemas/JobChecklist.schema.json").read_text(encoding="utf-8"))


def test_gate_without_waits_reports_null_and_zero_counts(tmp_path):
    result = p.inspect_job(make_job(tmp_path), tmp_path)
    assert result["errors"] == []
    assert all(row["waits"] is None for row in result["gates"])
    assert result["waits"] == {"user": 0, "max": 0, "visual": 0}
    inputs = result["gates"][0]
    assert inputs["status"] == "pass" and inputs["ready"] is True


def test_gate_with_waits_reported_per_gate_and_counted(tmp_path):
    job = make_job(tmp_path, operations="max", export_readback="max", visual="user", checker="visual")
    result = p.inspect_job(job, tmp_path)
    assert result["errors"] == []
    by_gate = {row["gate"]: row["waits"] for row in result["gates"]}
    assert by_gate == {"inputs": None, "parts": None, "operations": "max", "budgets": None,
                       "export_readback": "max", "report": None, "visual": "user", "checker": "visual"}
    assert result["waits"] == {"user": 1, "max": 2, "visual": 1}
    assert result["passed"] is False
    assert not any(row["ready"] for row in result["gates"] if row["waits"])


@pytest.mark.parametrize("bad", ["maxx", "", "USER", "waits-max", ["user"], 1, True, {"max": 1}])
def test_unknown_wait_value_rejected_by_model_and_schema(tmp_path, bad):
    job = make_job(tmp_path, visual=bad)
    result = p.inspect_job(job, tmp_path)
    assert result["passed"] is False and result["errors"]
    assert "waits" in result["errors"][0]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(job, schema())


@pytest.mark.parametrize("status", ["fail", "review", "missing"])
def test_waits_allowed_on_every_non_pass_status(tmp_path, status):
    job = make_job(tmp_path, report="user")
    job["gates"]["report"]["status"] = status
    jsonschema.validate(job, schema())
    result = p.inspect_job(job, tmp_path)
    assert result["errors"] == [] and result["waits"]["user"] == 1
    assert result["gates"][5]["ready"] is False


def test_passed_gate_cannot_wait(tmp_path):
    job = make_job(tmp_path, inputs="user")
    result = p.inspect_job(job, tmp_path)
    assert result["passed"] is False
    assert "pass" in result["errors"][0] and "waits" in result["errors"][0]


def test_malformed_job_keeps_the_waits_shape(tmp_path):
    result = p.inspect_job({}, tmp_path)
    assert result["passed"] is False and result["errors"]
    assert result["waits"] == {"user": 0, "max": 0, "visual": 0}


def test_waits_reported_when_gate_is_forced_to_fail(tmp_path):
    job = make_job(tmp_path, report="user")
    job["gates"]["report"] = {"status": "review", "note": "SYNTHETIC", "waits": "user",
                              "evidence": [{"path": "absent.md", "sha256": "0" * 64}]}
    result = p.inspect_job(job, tmp_path)
    row = result["gates"][5]
    assert row["status"] == "fail" and row["waits"] == "user"
    assert result["waits"]["user"] == 1


def test_generated_jobs_count_equals_declared_waits(tmp_path):
    """Probe: 300 seeded random wait assignments; counts == declared, passed only without waits."""
    rng = random.Random(1204)
    for _ in range(300):
        declared = {g: rng.choice(REASONS) for g in p.GATES[1:] if rng.random() < 0.5}
        result = p.inspect_job(make_job(tmp_path, **declared), tmp_path)
        assert result["errors"] == []
        expected = Counter(declared.values())
        assert result["waits"] == {r: expected.get(r, 0) for r in REASONS}
        assert {row["gate"]: row["waits"] for row in result["gates"] if row["waits"]} == declared
        assert result["passed"] is False  # seven gates stay missing; waits never make them ready


def test_kpp1_job_walk_counts_waits_fresh_process(tmp_path):
    job = yaml.safe_load((ROOT / "jobs/KPP1/job.yaml").read_text(encoding="utf-8"))
    jsonschema.validate(job, schema())
    out = tmp_path / "walk.json"
    proc = subprocess.run([sys.executable, "-m", "dt_ai.procedure", "jobs/KPP1/job.yaml", "--root", ".",
                           "--output", str(out)], cwd=ROOT, capture_output=True, timeout=120)
    assert proc.returncode == 1
    walk = json.loads(out.read_bytes())
    assert walk["passed"] is False
    assert walk["waits"] == {"user": 1, "max": 2, "visual": 1}
    by_gate = {row["gate"]: row["waits"] for row in walk["gates"]}
    assert by_gate["operations"] == by_gate["export_readback"] == "max"
    assert by_gate["visual"] == "user" and by_gate["checker"] == "visual"
