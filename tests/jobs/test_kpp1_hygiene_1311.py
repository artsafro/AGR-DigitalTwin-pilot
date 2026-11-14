"""new-case: cold-entry KPP1 authority and current-run documentation regressions."""

import hashlib
import json
from pathlib import Path
import re

import pytest
import yaml

from dt_ai.procedure import inspect_job


def assert_header_run(header, data):
    match = re.match(r"Current run: `([^`]+)`;", header)
    assert match is not None, "current-run header missing explicit run_id"
    assert match[1] == data["run_id"], "STATE/job.yaml run_id mismatch"


def test_f13_task_contract_links_answers_and_boundaries():
    task = (JOB / "TASK.md").read_text(encoding="utf-8") if (JOB / "TASK.md").exists() else ""
    assert task, "cold entry needs TASK.md"
    for decision in ("D238", "D249", "D254", "D256", "D262"):
        assert decision in task
    for fact in ("sources.json", "object.json", "job.yaml", "3.900", "7.909",
                 "0.35", "171.050", "not passed", "Do not change", "Ground"):
        assert fact in task


def test_f15_reproduce_uses_registry_source_and_explicit_frame():
    import shlex

    text = (ROOT / "docs/methods/building-body/kpp1-drawing/REPRODUCE.md").read_text(encoding="utf-8")
    registry = json.loads((JOB / "sources.json").read_text(encoding="utf-8"))
    source = next(r["path"] for r in registry["files"] if "L03_" in r["path"])
    commands = [shlex.split(line) for line in text.splitlines() if line.startswith("uv run python ")]
    readback = next(cmd for cmd in commands if cmd[3].endswith("dwg_to_dxf.py"))
    assert readback[4] == source, "readback must use the registered asset-store source"
    assert "Downloads" not in text
    assert "sources.json" in text and "mapping-questions.md" in text and "item 6" in text
    assert any("census" in cmd for cmd in commands), "new sheets need census before a role map"
    assert "new sheet" in text and "Do not reuse" in text
    extract = next(cmd for cmd in commands if "extract" in cmd)
    assert extract[extract.index("--origin-mm") + 1] == "25884.5,0"
    assert "--frame-shift-m=-14.655,-5.355" in extract


def test_f19_current_run_and_checklist_are_consistent():
    data = yaml.safe_load((JOB / "job.yaml").read_text(encoding="utf-8"))
    header = (JOB / "STATE.md").read_text(encoding="utf-8").splitlines()[:3]
    assert_header_run(header[0], data)
    assert "site-1255/REPORT.md" in header[0] and "rerun-1244" in header[0]
    assert "passed=false" in header[0]
    assert data["run_id"] == "issue-1255-site-v004"
    assert "sources.json" in header[1] and "D254" in header[1]
    assert "DWGs still outside" not in json.dumps(data)
    assert "architect question" not in json.dumps(data)
    assert data["inputs"][0]["path"] == "jobs/KPP1/sources.json"
    assert data["inputs"][0]["manifest"] == "external-inputs/1"
    assert all("rerun-1209" not in r["path"] for r in data["inputs"] + data["artifacts"])
    result = inspect_job(data, ROOT)
    assert result["run_id"] == data["run_id"] and result["passed"] is False
    assert not result["errors"]
    assert not [e for row in result["gates"] for e in row["errors"]]
    assert all(row["status"] != "pass" for row in result["gates"] if row["gate"] != "inputs")


ROOT = Path(__file__).resolve().parents[2]
JOB = ROOT / "jobs/KPP1"


@pytest.mark.parametrize("run_id", ["", "issue-1209-rerun-v001", "issue-1255-site-v004-stale"])
def test_header_check_rejects_mismatched_runs(run_id):
    header = (JOB / "STATE.md").read_text(encoding="utf-8").splitlines()[0]
    with pytest.raises(AssertionError, match="mismatch"):
        assert_header_run(header, {"run_id": run_id})


@pytest.mark.parametrize("header", ["", "Current run:", "Current run: #1209"])
def test_header_check_rejects_absent_or_legacy_identity(header):
    with pytest.raises(AssertionError, match="missing"):
        assert_header_run(header, {"run_id": "issue-1255-site-v004"})


@pytest.mark.parametrize("index", range(4))
def test_current_inputs_reject_stale_hashes(index):
    data = yaml.safe_load((JOB / "job.yaml").read_text(encoding="utf-8"))
    # YAML alias updates inventory and inputs-gate evidence together.
    data["inputs"][index]["sha256"] = "0" * 64
    result = inspect_job(data, ROOT)
    inputs = next(r for r in result["gates"] if r["gate"] == "inputs")
    assert result["passed"] is False and inputs["status"] == "fail"
    assert any(data["inputs"][index]["path"] in error for error in inputs["errors"])


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
