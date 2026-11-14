"""new-case: cold-entry KPP1 authority and current-run documentation regressions."""

import hashlib
import json
from pathlib import Path

import yaml

from dt_ai.procedure import walk

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
    result = walk(data, ROOT)
    inputs = next(r for r in result["gates"] if r["gate"] == "inputs")
    assert {"path": authority["path"], "verified": True} in inputs["evidence_exists"]
    assert hashlib.sha256((ROOT / authority["path"]).read_bytes()).hexdigest() == authority["sha256"]
