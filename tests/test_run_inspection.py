import json
from pathlib import Path
import sys

import pytest

from dt_ai.core.adapter_report import AdapterReport, Check
from dt_ai.core.io import digest, json_bytes
from dt_ai.core.run_inspection import inspect_run
from dt_ai.core.run_record import RunRecord, atomic_json, file_evidence


def fixture_run(tmp_path, state="produced"):
    source = tmp_path / "source.txt"
    source.write_text("original")
    inputs = {"source": source}
    context = {"profile": "NPM", "scope": "fixture-only", "tool": "fixture-v1"}
    run = RunRecord.create(tmp_path / "runs", "fixture", inputs, context)
    attempt = run.new_attempt()
    output = attempt / "out.txt"
    output.write_text("exported")
    facts = file_evidence({"out": output})
    argv, cwd = ["fixture-only"], str(tmp_path)
    signature = digest(json_bytes({"fingerprint": run.fingerprint(), "argv": argv,
                                   "cwd": cwd, "outputs": {"out": str(output)}}))
    ledger = run.read()
    ledger["attempts"][0]["stages"]["export"] = {
        "status": state, "signature": signature, "input_fingerprint": run.fingerprint(),
        "argv": argv, "cwd": cwd, "outputs": facts if state in {"produced", "verified"} else {},
    }
    atomic_json(run.path, ledger)
    manifest = attempt / "input-manifest.json"
    atomic_json(manifest, {"inputs": file_evidence(inputs), "context": context})
    return run, manifest, source, output


@pytest.mark.parametrize("state,action", [
    ("produced", "verify_saved_outputs_without_repeating_execution"),
    ("verified", "review_scope_and_acceptance_no_delivery_claim"),
    ("running", "confirm_process_and_artifacts_before_retry"),
    ("interrupted", "classify_failure_before_new_attempt"),
])
def test_scoped_states_do_not_mean_delivery(tmp_path, state, action):
    run, manifest, _, _ = fixture_run(tmp_path, state)
    result = inspect_run(run.directory, manifest)
    assert result["next_action"] == action
    assert result["stages"][0]["state"] == ("uncertain" if state == "running" else state)
    if state in {"running", "interrupted"}:
        assert result["evidence_integrity"] == "incomplete"
    assert result["delivery_passed"] is False


@pytest.mark.parametrize("target,mutation", [
    ("input", "tamper"), ("input", "missing"), ("output", "tamper"), ("output", "missing"),
])
def test_actual_files_are_checked(tmp_path, target, mutation):
    run, manifest, source, output = fixture_run(tmp_path, "verified")
    path = source if target == "input" else output
    path.write_text("changed") if mutation == "tamper" else path.unlink()
    result = inspect_run(run.directory, manifest)
    assert result["evidence_integrity"] == "failed"
    assert result["errors_total"] == 1
    assert result["stages"][0]["evidence_integrity"] == "failed"
    assert "fresh_outputs" in result["next_action"]


def test_manifest_and_stage_signatures_are_bound(tmp_path):
    run, manifest, _, _ = fixture_run(tmp_path)
    data = json.loads(manifest.read_text())
    data["context"]["scope"] = "different"
    atomic_json(manifest, data)
    with pytest.raises(ValueError, match="not bound"):
        inspect_run(run.directory, manifest)
    data["context"]["scope"] = "fixture-only"
    atomic_json(manifest, data)
    ledger = run.read()
    ledger["attempts"][0]["stages"]["export"]["argv"] = ["changed-command"]
    atomic_json(run.path, ledger)
    assert inspect_run(run.directory, manifest)["errors_total"] == 1


def test_latest_failed_attempt_supersedes_old_verified(tmp_path):
    run, manifest, _, _ = fixture_run(tmp_path, "verified")
    run.new_attempt()
    ledger = run.read()
    ledger["attempts"][-1]["stages"]["export"] = {"status": "failed", "outputs": {}}
    atomic_json(run.path, ledger)
    result = inspect_run(run.directory, manifest)
    assert result["stages"][0]["attempt"] == 2
    assert result["next_action"] == "classify_failure_before_new_attempt"


def test_repeated_failure_stop_is_never_reset(tmp_path):
    run, manifest, _, _ = fixture_run(tmp_path, "failed")
    ledger = run.read()
    ledger.update(stopped=True, stop_reason="same_failure")
    atomic_json(run.path, ledger)
    result = inspect_run(run.directory, manifest)
    assert result["stopped"] is True
    assert result["stop_reason"] == "same_failure"
    assert result["next_action"] == "investigate_stop_preserve_evidence"


def test_report_pass_strings_do_not_prove_native_checks(tmp_path):
    run, manifest, _, output = fixture_run(tmp_path, "verified")
    report_path = manifest.parent / "report.json"
    report = AdapterReport(operation="fixture", tool_version="v1", scope="fixture",
                           execution="completed", input_manifest=str(manifest),
                           output_manifest=str(output), checks=(
                               Check(id="native", status="pass", evidence="Native app reported OK"),
                               Check(id="visual", status="not_run", evidence="Awaiting human")),
                           pending_decisions=("Approve render",))
    atomic_json(report_path, report.model_dump(mode="json"))
    result = inspect_run(run.directory, manifest, report_path, ["native", "checker"])
    gates = {gate["id"]: gate for gate in result["unresolved_gates"]}
    assert result["report"]["form"] == "valid"
    assert result["report"]["evidence_claims_verified"] is False
    assert gates["native"]["status"] == "reported_pass_unverified"
    assert gates["checker"]["reported_status"] == "missing"
    assert gates["visual"]["status"] == "pending"
    assert result["delivery_passed"] is False


def test_required_checks_pending_without_report(tmp_path):
    run, manifest, _, _ = fixture_run(tmp_path, "verified")
    result = inspect_run(run.directory, manifest, required_checks=["agr"])
    assert result["unresolved_gates"][0]["reported_status"] == "missing"
    assert result["next_action"] == "review_required_evidence_and_pending_decisions"


def test_external_stage_output_rejected(tmp_path):
    run, manifest, source, _ = fixture_run(tmp_path)
    ledger = run.read()
    ledger["attempts"][0]["stages"]["export"]["outputs"] = file_evidence({"out": source})
    atomic_json(run.path, ledger)
    with pytest.raises(ValueError, match="outside"):
        inspect_run(run.directory, manifest)


def test_source_copy_tamper_is_not_hidden_by_intact_original(tmp_path):
    run, manifest, _, _ = fixture_run(tmp_path)
    copy = manifest.parent / "copied-source"
    copy.write_text("original")
    data = json.loads(manifest.read_text())
    data["source_copy"] = file_evidence({"copy": copy})
    atomic_json(manifest, data)
    copy.write_text("different")
    result = inspect_run(run.directory, manifest)
    assert result["current_inputs"] == "intact"
    assert result["evidence_integrity"] == "failed"


def test_report_wrong_manifest_is_not_evidence_for_this_run(tmp_path):
    run, manifest, _, _ = fixture_run(tmp_path, "verified")
    report_path = manifest.parent / "report.json"
    report = AdapterReport(operation="fixture", tool_version="v1", scope="fixture",
                           execution="completed", input_manifest=str(manifest.parent / "different-manifest.json"))
    atomic_json(report_path, report.model_dump(mode="json"))
    result = inspect_run(run.directory, manifest, report_path)
    assert result["report"]["form"] == "valid"
    assert result["report"]["input_manifest_binding"] == "different_or_relative"
    assert result["evidence_integrity"] == "failed"


@pytest.mark.parametrize("kind,integrity", [("missing", "missing"), ("unbound", "not_checked")])
def test_declared_report_output_is_not_silently_accepted(tmp_path, kind, integrity):
    run, manifest, _, _ = fixture_run(tmp_path, "verified")
    claimed = manifest.parent / "unbound-manifest.json"
    if kind == "unbound":
        claimed.write_text('{"claimed": "pass"}')
    report_path = manifest.parent / "report.json"
    report = AdapterReport(operation="fixture", tool_version="v1", scope="fixture",
                           execution="completed", input_manifest=str(manifest), output_manifest=str(claimed))
    atomic_json(report_path, report.model_dump(mode="json"))
    result = inspect_run(run.directory, manifest, report_path)
    assert result["report"]["output_manifest"]["binding"] == "not_stage_bound"
    assert result["report"]["output_manifest"]["integrity"] == integrity
    assert any(gate["id"] == "output_manifest" for gate in result["unresolved_gates"])
    assert result["errors_total"] == (1 if kind == "missing" else 0)
    assert result["next_action"] != "review_scope_and_acceptance_no_delivery_claim"


@pytest.mark.parametrize("kind", ["bound", "null", "outside", "relative"])
def test_report_output_binding_contract(tmp_path, kind):
    run, manifest, source, output = fixture_run(tmp_path, "verified")
    claim = {"bound": str(output), "null": None, "outside": str(source), "relative": "out.txt"}[kind]
    report_path = manifest.parent / "report.json"
    report = AdapterReport(operation="fixture", tool_version="v1", scope="fixture",
                           execution="completed", input_manifest=str(manifest), output_manifest=claim)
    atomic_json(report_path, report.model_dump(mode="json"))
    result = inspect_run(run.directory, manifest, report_path)
    info = result["report"]["output_manifest"]
    if kind == "bound":
        assert info["binding"] == "stage_output"
        assert info["integrity"] == "intact"
        assert result["report"]["evidence_claims_verified"] is False
    elif kind == "null":
        assert info["binding"] == "no_claim"
        assert result["unresolved_gates"] == []
    else:
        assert info["binding"] == "invalid_reference"
        assert info["integrity"] == "not_checked"
        assert result["errors_total"] == 1
        assert result["unresolved_gates"][0]["id"] == "output_manifest"


def test_cli_readonly_and_controlled_rejection(tmp_path, capsys, monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    from harness_status import main
    run, manifest, _, _ = fixture_run(tmp_path)
    lock = run.directory / "orphan.orchestration.lock"
    lock.write_text("preserve")
    before = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    # A read-only inspector must not execute even a valid argv from a ledger.
    import subprocess
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("Inspector executed subprocess"))
    assert main(["--run", str(run.directory), "--manifest", str(manifest)]) == 0
    assert json.loads(capsys.readouterr().out)["delivery_passed"] is False
    assert {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before
    manifest.write_text("[]")
    assert main(["--run", str(run.directory), "--manifest", str(manifest)]) == 2
    assert "must be an object" in json.loads(capsys.readouterr().out)["error"]


def test_error_output_is_bounded(tmp_path):
    run, manifest, _, _ = fixture_run(tmp_path)
    ledger = run.read()
    stage = ledger["attempts"][0]["stages"]["export"]
    original = stage["outputs"]["out"]
    stage["outputs"] = {str(i): {**original, "path": str(manifest.parent / f"missing-{i}")} for i in range(8)}
    stage["signature"] = digest(json_bytes({"fingerprint": run.fingerprint(), "argv": stage["argv"],
                                            "cwd": stage["cwd"], "outputs": {k: v["path"] for k, v in stage["outputs"].items()}}))
    atomic_json(run.path, ledger)
    result = inspect_run(run.directory, manifest)
    assert result["errors_total"] == 8
    assert len(result["errors"]) == 5


@pytest.mark.parametrize("invalid_status", [[], {}])
def test_cli_malformed_stage_state_is_controlled(tmp_path, capsys, invalid_status):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    from harness_status import main
    run, manifest, _, _ = fixture_run(tmp_path)
    ledger = run.read()
    ledger["attempts"][0]["stages"]["export"]["status"] = invalid_status
    atomic_json(run.path, ledger)
    before = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert main(["--run", str(run.directory), "--manifest", str(manifest)]) == 2
    assert json.loads(capsys.readouterr().out) == {"error": "Invalid stage state", "delivery_passed": False}
    assert {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before


def test_manifest_outside_run_directory(tmp_path):
    run, manifest, _, _ = fixture_run(tmp_path)
    outside = tmp_path / "outside-manifest.json"
    outside.write_bytes(manifest.read_bytes())
    with pytest.raises(ValueError, match="Manifest points outside the run directory"):
        inspect_run(run.directory, outside)


@pytest.mark.parametrize("field,value,message", [
    ("version", 2, "Unsupported ledger version"),
    ("version", True, "Unsupported ledger version"),
    ("run_id", "", "Invalid run_id"),
    ("run_id", "../x", "Invalid run_id"),
    ("run_id", "-bad", "Invalid run_id"),
    ("run_id", 5, "Invalid run_id"),
    ("input_fingerprint", "abc", "Invalid ledger fingerprint"),
    ("input_fingerprint", "A" * 64, "Invalid ledger fingerprint"),
    ("stopped", "no", "Invalid stopped state"),
])
def test_malformed_ledger_rejected(tmp_path, field, value, message):
    run, manifest, _, _ = fixture_run(tmp_path)
    ledger = run.read()
    ledger[field] = value
    atomic_json(run.path, ledger)
    with pytest.raises(ValueError, match=message):
        inspect_run(run.directory, manifest)


@pytest.mark.parametrize("change,message", [
    ("empty", "Manifest must declare inputs"),
    ("relative", "inputs:source must be an absolute path"),
    ("blank", "inputs:source must be a nonempty absolute path"),
    ("sha", "inputs:source has invalid size/hash"),
    ("upper", "inputs:source has invalid size/hash"),
    ("negative", "inputs:source has invalid size/hash"),
    ("key", "inputs has an invalid key"),
])
def test_manifest_inputs_rejected(tmp_path, change, message):
    run, manifest, _, _ = fixture_run(tmp_path)
    data = json.loads(manifest.read_text())
    if change == "empty":
        data["inputs"] = {}
    elif change == "relative":
        data["inputs"]["source"]["path"] = "source.txt"
    elif change == "blank":
        data["inputs"]["source"]["path"] = ""
    elif change == "sha":
        data["inputs"]["source"]["sha256"] = "abc"
    elif change == "upper":
        data["inputs"]["source"]["sha256"] = "A" * 64
    elif change == "negative":
        data["inputs"]["source"]["bytes"] = -1
    else:
        data["inputs"] = {"": data["inputs"]["source"]}
    atomic_json(manifest, data)
    with pytest.raises(ValueError, match=message):
        inspect_run(run.directory, manifest)


def test_ledger_fingerprint_mismatch(tmp_path):
    run, manifest, _, _ = fixture_run(tmp_path)
    ledger = run.read()
    ledger["input_fingerprint"] = "a" * 64
    atomic_json(run.path, ledger)
    with pytest.raises(ValueError, match="Manifest inputs/context are not bound to the ledger fingerprint"):
        inspect_run(run.directory, manifest)


@pytest.mark.parametrize("check_id", ["", "x" * 121])
def test_invalid_required_check_identifier(tmp_path, check_id):
    run, manifest, _, _ = fixture_run(tmp_path)
    with pytest.raises(ValueError, match="Invalid required check identifier"):
        inspect_run(run.directory, manifest, required_checks=[check_id])


@pytest.mark.parametrize("failure", ["digest", "oserror"])
def test_inputs_changed_during_inspection(tmp_path, monkeypatch, failure):
    run, manifest, _, _ = fixture_run(tmp_path)

    def changed(inputs, context):
        if failure == "oserror":
            raise OSError("unreadable")
        return "0" * 64

    monkeypatch.setattr("dt_ai.core.run_inspection.input_fingerprint", changed)
    result = inspect_run(run.directory, manifest)
    assert "Inputs changed during inspection" in result["errors"]
    assert result["current_inputs"] == "failed"


def test_attempts_must_be_a_list(tmp_path):
    run, manifest, _, _ = fixture_run(tmp_path)
    ledger = run.read()
    ledger["attempts"] = {"number": 1}
    atomic_json(run.path, ledger)
    with pytest.raises(ValueError, match="Attempts must be a list"):
        inspect_run(run.directory, manifest)


@pytest.mark.parametrize("number", [2, "1"])
def test_attempt_numbers_must_be_consecutive(tmp_path, number):
    run, manifest, _, _ = fixture_run(tmp_path)
    ledger = run.read()
    ledger["attempts"][0]["number"] = number
    atomic_json(run.path, ledger)
    with pytest.raises(ValueError, match="Attempt numbers must be consecutive"):
        inspect_run(run.directory, manifest)


def test_attempt_directory_not_bound_to_number(tmp_path):
    run, manifest, _, _ = fixture_run(tmp_path)
    ledger = run.read()
    ledger["attempts"][0]["directory"] = str(run.directory / "attempt-002")
    atomic_json(run.path, ledger)
    with pytest.raises(ValueError, match="Attempt directory is not bound to its number"):
        inspect_run(run.directory, manifest)


@pytest.mark.parametrize("name", ["bad name", "-x"])
def test_invalid_stage_identifier(tmp_path, name):
    run, manifest, _, _ = fixture_run(tmp_path)
    ledger = run.read()
    stages = ledger["attempts"][0]["stages"]
    stages[name] = stages.pop("export")
    atomic_json(run.path, ledger)
    with pytest.raises(ValueError, match="Invalid stage identifier"):
        inspect_run(run.directory, manifest)


def test_stage_stdout_outside_run(tmp_path):
    run, manifest, source, _ = fixture_run(tmp_path)
    ledger = run.read()
    ledger["attempts"][0]["stages"]["export"]["stdout"] = str(source.resolve())
    atomic_json(run.path, ledger)
    with pytest.raises(ValueError, match="stdout points outside the run directory"):
        inspect_run(run.directory, manifest)


def test_produced_stage_must_declare_outputs(tmp_path):
    run, manifest, _, _ = fixture_run(tmp_path, "produced")
    ledger = run.read()
    ledger["attempts"][0]["stages"]["export"]["outputs"] = {}
    atomic_json(run.path, ledger)
    with pytest.raises(ValueError, match="Produced/verified stage must declare outputs"):
        inspect_run(run.directory, manifest)


@pytest.mark.parametrize("argv", [[], ["a", 1]])
def test_invalid_stage_argv(tmp_path, argv):
    run, manifest, _, _ = fixture_run(tmp_path, "produced")
    ledger = run.read()
    ledger["attempts"][0]["stages"]["export"]["argv"] = argv
    atomic_json(run.path, ledger)
    with pytest.raises(ValueError, match="Invalid stage argv"):
        inspect_run(run.directory, manifest)


def _report(manifest, **kwargs):
    report_path = manifest.parent / "report.json"
    report = AdapterReport(operation="fixture", tool_version="v1", scope="fixture",
                           execution="completed", input_manifest=str(manifest), **kwargs)
    atomic_json(report_path, report.model_dump(mode="json"))
    return report_path


def test_tampered_stage_output_manifest(tmp_path):
    run, manifest, _, output = fixture_run(tmp_path, "verified")
    output.write_text("tampered")
    report_path = _report(manifest, output_manifest=str(output.resolve()))
    result = inspect_run(run.directory, manifest, report_path)
    assert result["report"]["output_manifest"]["binding"] == "stage_output"
    assert result["report"]["output_manifest"]["integrity"] == "failed"
    assert {"id": "output_manifest", "status": "pending", "detail": "stage_evidence_not_intact"} in result["unresolved_gates"]


def test_unreadable_report_output_manifest(tmp_path, monkeypatch):
    run, manifest, _, _ = fixture_run(tmp_path, "verified")
    claimed = run.directory / "side-manifest.json"
    claimed.write_text("{}\n")
    report_path = _report(manifest, output_manifest=str(claimed.resolve()))
    real_open = Path.open

    def guarded_open(self, mode="r", *args, **kwargs):
        if self.resolve() == claimed.resolve():
            raise PermissionError("denied")
        return real_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    result = inspect_run(run.directory, manifest, report_path)
    assert result["report"]["output_manifest"]["integrity"] == "unreadable"
    assert "Report output manifest is unreadable" in result["errors"]
    assert {"id": "output_manifest", "status": "pending", "detail": "unreadable"} in result["unresolved_gates"]


def test_duplicate_report_check_identifiers(tmp_path):
    run, manifest, _, _ = fixture_run(tmp_path, "verified")
    report_path = _report(manifest, checks=(
        Check(id="native", status="pass", evidence="first"),
        Check(id="native", status="fail", evidence="second"),
    ))
    with pytest.raises(ValueError, match="Duplicate report check identifiers"):
        inspect_run(run.directory, manifest, report_path)


@pytest.mark.parametrize("execution", ["failed", "not_run"])
def test_report_execution_not_completed(tmp_path, execution):
    run, manifest, _, _ = fixture_run(tmp_path, "verified")
    report_path = manifest.parent / "report.json"
    report = AdapterReport(operation="fixture", tool_version="v1", scope="fixture",
                           execution=execution, input_manifest=str(manifest))
    atomic_json(report_path, report.model_dump(mode="json"))
    result = inspect_run(run.directory, manifest, report_path)
    assert {"id": "report_execution", "status": "pending", "detail": execution} in result["unresolved_gates"]


def test_check_evidence_binds_to_stage_output(tmp_path):
    run, manifest, _, output = fixture_run(tmp_path, "verified")
    report_path = _report(manifest, checks=(
        Check(id="native", status="pass", evidence=str(output.resolve())),
    ))
    result = inspect_run(run.directory, manifest, report_path)
    gate = {item["id"]: item for item in result["unresolved_gates"]}["native"]
    assert gate["evidence_file_binding"] == "stage_output"
    assert gate["evidence_file_integrity"] == "intact"


def test_zero_attempts_plans_authorized_stage(tmp_path):
    run, manifest, _, _ = fixture_run(tmp_path)
    ledger = run.read()
    ledger["attempts"] = []
    atomic_json(run.path, ledger)
    result = inspect_run(run.directory, manifest)
    assert result["next_action"] == "plan_authorized_stage"
    assert result["evidence_integrity"] == "incomplete"
