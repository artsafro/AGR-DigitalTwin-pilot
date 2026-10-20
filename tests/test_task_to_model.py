"""Task-to-model gate contract; all generated bundle data is SYNTHETIC."""
import importlib.util
from pathlib import Path

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
