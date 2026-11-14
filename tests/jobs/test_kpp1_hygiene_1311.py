"""new-case: cold-entry KPP1 authority and current-run documentation regressions."""

import hashlib
import json
from pathlib import Path

import yaml

from dt_ai.procedure import inspect_job

def test_f13_task_contract_links_answers_and_boundaries():
    task = (JOB / "TASK.md").read_text(encoding="utf-8") if (JOB / "TASK.md").exists() else ""
    assert task, "cold entry needs TASK.md"
    for decision in ("D238", "D249", "D254", "D256", "D262"):
        assert decision in task
    for fact in ("sources.json", "object.json", "job.yaml", "3.900", "7.909",
                 "0.35", "171.050", "not passed", "Do not change", "Ground"):
        assert fact in task


ROOT = Path(__file__).resolve().parents[2]
JOB = ROOT / "jobs/KPP1"


def test_f12_levels_authority_registered_and_verified():
    registry = json.loads((JOB / "sources.json").read_text(encoding="utf-8"))
    authority = next((r for r in registry.get("repo_inputs", [])
                      if r["path"] == "jobs/KPP1/object.json"), None)
    assert authority is not None, "registry must name the cached Revit levels authority"
    assert "D254" in authority["role"]
    data = yaml.safe_load((JOB / "job.yaml").read_text(encoding="utf-8"))
    assert {"path": authority["path"], "sha256": authority["sha256"]} in data["inputs"]
    result = inspect_job(data, ROOT)
    inputs = next(r for r in result["gates"] if r["gate"] == "inputs")
    assert {"path": authority["path"], "verified": True} in inputs["evidence_exists"]
    assert hashlib.sha256((ROOT / authority["path"]).read_bytes()).hexdigest() == authority["sha256"]
