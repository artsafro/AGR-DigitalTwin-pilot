import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from dt_ai.core import run_record as run_record_module
from dt_ai.core.io import json_bytes, write_json
from dt_ai.core.run_record import (
    EvidenceMismatch, OwnershipConflict, RunRecord, RunStopped, StageStillRunning,
    StageUnresolved, resource_lock,
)


def fixture_run(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("approved")
    inputs = {"source": source}
    run = RunRecord.create(tmp_path / "runs", "fixture", inputs, {"tool": "fixture-v1"})
    return run, inputs


def plant_newer_running(run, stage, pid=None, *, include_pid=True):
    """Append an unreleased running row as attempt N+1. Leaves earlier outputs alone."""
    ledger = run.read()
    number = len(ledger["attempts"]) + 1
    attempt_dir = run.directory / f"attempt-{number:03d}"
    attempt_dir.mkdir(exist_ok=False)
    record = {
        "status": "running",
        "signature": "planted-running-newer",
        "argv": ["planted"],
        "cwd": str(run.directory),
        "outputs": {},
    }
    if include_pid:
        record["spawned_pid"] = pid
    ledger["attempts"].append({
        "number": number,
        "directory": str(attempt_dir),
        "stages": {stage: record},
    })
    write_json(run.path, ledger)


def plant_running(run, stage, pid=None, *, include_pid=True, releases=None):
    """Crash leftover: a running stage row and no outputs on disk."""
    ledger = run.read()
    attempt_dir = run.directory / "attempt-001"
    attempt_dir.mkdir(exist_ok=True)
    record = {
        "status": "running",
        "signature": "planted-running",
        "argv": ["planted"],
        "cwd": str(run.directory),
        "outputs": {},
    }
    if include_pid:
        record["spawned_pid"] = pid
    ledger["attempts"].append({
        "number": 1,
        "directory": str(attempt_dir),
        "stages": {stage: record},
    })
    if releases is not None:
        ledger["releases"] = releases
    write_json(run.path, ledger)


def exited_child():
    """Exited process. Keep the Popen: Windows reuses the pid after the last handle closes."""
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    assert child.returncode is not None
    return child


def fully_dead_pid(pid_file):
    """Pid with no open process handle, as after a crashed parent.

    A helper starts ``python -c pass``, writes that pid, and exits. Its exit
    closes the only handle. The sleep lets the OS reap the grandchild.
    """
    script = (
        "import subprocess, sys\n"
        "from pathlib import Path\n"
        f"Path({str(pid_file)!r}).write_text(str("
        "subprocess.Popen([sys.executable, '-c', 'pass']).pid))\n"
    )
    subprocess.run([sys.executable, "-c", script], check=True)
    time.sleep(0.5)
    return int(pid_file.read_text())


def writer(output, counter):
    script = (
        "from pathlib import Path; "
        f"p=Path({str(counter)!r}); "
        "p.write_text(str(int(p.read_text())+1) if p.exists() else '1'); "
        f"Path({str(output)!r}).write_text('exported')"
    )
    return [sys.executable, "-c", script]


def test_crash_after_produced_resumes_without_second_export(tmp_path):
    run, inputs = fixture_run(tmp_path)
    output, counter = tmp_path / "fbx.txt", tmp_path / "counter"
    argv = writer(output, counter)
    assert run.run_stage("export", argv, {"fbx": output})["status"] == "produced"
    restarted = RunRecord.open(run.directory, inputs, {"tool": "fixture-v1"})
    assert restarted.run_stage("export", argv, {"fbx": output})["status"] == "produced"
    assert restarted.verify_stage("export", lambda files: Path(files["fbx"]).read_text() == "exported")["status"] == "verified"
    assert counter.read_text() == "1"
    assert len(restarted.read()["attempts"]) == 1


def test_stale_output_rejected_even_if_ledger_says_produced(tmp_path):
    run, _ = fixture_run(tmp_path)
    output, counter = tmp_path / "out", tmp_path / "counter"
    argv = writer(output, counter)
    run.run_stage("export", argv, {"out": output})
    output.write_text("corrupted")
    with pytest.raises(EvidenceMismatch, match="Stale output"):
        run.run_stage("export", argv, {"out": output})
    assert counter.read_text() == "1"


def test_changed_input_cannot_reuse_or_overwrite_prior_output(tmp_path):
    run, inputs = fixture_run(tmp_path)
    output, counter = tmp_path / "out", tmp_path / "counter"
    argv = writer(output, counter)
    run.run_stage("export", argv, {"out": output})
    inputs["source"].write_text("revised")
    with pytest.raises(EvidenceMismatch, match="fresh output"):
        run.run_stage("export", argv, {"out": output})
    replacement = tmp_path / "out-v2"
    record = run.run_stage("export", writer(replacement, counter), {"out": replacement})
    assert record["status"] == "produced"
    assert counter.read_text() == "2"
    assert len(run.read()["attempts"]) == 2


def test_concurrent_output_owner_rejected_before_command(tmp_path):
    run, _ = fixture_run(tmp_path)
    other = RunRecord.create(tmp_path / "runs", "other", run.inputs)
    output, counter = tmp_path / "shared", tmp_path / "counter"
    with resource_lock(output, str(other.directory)):
        with pytest.raises(OwnershipConflict, match="already owned"):
            run.run_stage("export", writer(output, counter), {"out": output})
    assert not counter.exists()
    assert not run.read()["attempts"]


def test_timeout_preserves_partial_stdout_and_stderr(tmp_path):
    run, _ = fixture_run(tmp_path)
    argv = [sys.executable, "-u", "-c",
            "import sys,time; print('partial out',flush=True); print('partial err',file=sys.stderr,flush=True); time.sleep(20)"]
    record = run.run_stage("export", argv, {"out": tmp_path / "missing"}, timeout=1)
    assert record["status"] == "interrupted"
    assert record["reason"] == "timeout"
    assert isinstance(record["spawned_pid"], int)
    if os.name == "nt":
        assert record["timeout_cleanup_argv"] == ["taskkill", "/PID", str(record["spawned_pid"]), "/T", "/F"]
        assert record["timeout_cleanup_returncode"] == 0
    assert "partial out" in Path(record["stdout"]).read_text()
    assert "partial err" in Path(record["stderr"]).read_text()
    assert json.loads(run.path.read_text())["attempts"][0]["stages"]["export"]["status"] == "interrupted"


def test_two_same_cause_failures_stop_run_and_keep_attempts(tmp_path):
    run, _ = fixture_run(tmp_path)
    argv = [sys.executable, "-c", "import sys; print('tool failed'); sys.exit(3)"]
    for _ in range(2):
        record = run.run_stage("export", argv, {"out": tmp_path / "out"}, reason="tool:missing-addon")
        assert record["status"] == "failed"
        assert record["returncode"] == 3
    ledger = run.read()
    assert ledger["stopped"] is True
    assert ledger["stop_reason"] == "tool:missing-addon"
    assert len(ledger["attempts"]) == 2
    with pytest.raises(RunStopped, match="missing-addon"):
        run.run_stage("export", argv, {"out": tmp_path / "out"})


def test_run_and_attempt_directories_never_reused(tmp_path):
    run, inputs = fixture_run(tmp_path)
    with pytest.raises(FileExistsError):
        RunRecord.create(tmp_path / "runs", "fixture", inputs)
    (run.directory / "attempt-001").mkdir()
    with pytest.raises(FileExistsError):
        run.new_attempt()


def test_verifier_cannot_modify_output_and_mark_verified(tmp_path):
    run, _ = fixture_run(tmp_path)
    output = tmp_path / "out"
    run.run_stage("export", writer(output, tmp_path / "counter"), {"out": output})

    def bad_verifier(files):
        Path(files["out"]).write_text("modified")
        return True

    with pytest.raises(EvidenceMismatch, match="during verification"):
        run.verify_stage("export", bad_verifier)
    assert run.read()["attempts"][0]["stages"]["export"]["status"] == "produced"


def test_stage_named_output_directory_does_not_conflict_with_logs(tmp_path):
    run, _ = fixture_run(tmp_path)
    attempt = run.new_attempt()
    output_directory = attempt / "export"
    output = output_directory / "snapshot.fbx"
    record = run.run_stage("export", writer(output, tmp_path / "counter"),
                           {"fbx": output}, resources=[output_directory])
    assert record["status"] == "produced"
    assert Path(record["stdout"]).parent == attempt / "logs" / "export"
    assert output.read_text() == "exported"


def test_distinct_generic_tool_failures_do_not_trigger_same_cause_stop(tmp_path):
    run, _ = fixture_run(tmp_path)
    for message in ("missing addon", "invalid mesh"):
        argv = [sys.executable, "-c", f"import sys; print({message!r},file=sys.stderr); sys.exit(3)"]
        record = run.run_stage("export", argv, {"out": tmp_path / "missing"})
        assert record["status"] == "failed"
    ledger = run.read()
    assert ledger["stopped"] is False
    assert ledger["attempts"][0]["stages"]["export"]["reason_fingerprint"] != record["reason_fingerprint"]


def test_repeated_identical_generic_stderr_and_exit_code_stop(tmp_path):
    run, _ = fixture_run(tmp_path)
    argv = [sys.executable, "-c", "import sys; print('missing addon',file=sys.stderr); sys.exit(3)"]
    for _ in range(2):
        run.run_stage("export", argv, {"out": tmp_path / "missing"})
    ledger = run.read()
    assert ledger["stopped"] is True
    fingerprints = [a["stages"]["export"]["reason_fingerprint"] for a in ledger["attempts"]]
    assert fingerprints[0] == fingerprints[1]


def test_stage_pid_records_exact_spawned_process(tmp_path):
    run, _ = fixture_run(tmp_path)
    output = tmp_path / "pid.txt"
    argv = [sys._base_executable, "-c", f"import os; from pathlib import Path; Path({str(output)!r}).write_text(str(os.getpid()))"]
    record = run.run_stage("pid", argv, {"pid": output})
    assert record["status"] == "produced"
    assert record["spawned_pid"] == int(output.read_text())
    assert run.read()["attempts"][0]["stages"]["pid"]["spawned_pid"] == int(output.read_text())


def test_running_record_declares_intended_output_paths(tmp_path):
    run, _ = fixture_run(tmp_path)
    output = tmp_path / "out.txt"
    record = run.run_stage("export", writer(output, tmp_path / "counter"), {"out": output})
    assert record["status"] == "produced"
    saved = run.read()["attempts"][0]["stages"]["export"]
    assert saved["declared_outputs"] == {"out": str(output.resolve())}
    assert record["declared_outputs"] == {"out": str(output.resolve())}


def test_running_record_records_started_at(tmp_path):
    run, _ = fixture_run(tmp_path)
    output = tmp_path / "out.txt"
    record = run.run_stage("export", writer(output, tmp_path / "counter"), {"out": output})
    saved = run.read()["attempts"][0]["stages"]["export"]
    assert isinstance(saved["started_at"], float)
    assert saved["started_at"] > 0
    assert saved["started_at"] <= Path(saved["declared_outputs"]["out"]).stat().st_mtime


def test_cached_earlier_stage_verifies_exact_returned_evidence(tmp_path):
    run, _ = fixture_run(tmp_path)
    first, second = tmp_path / "a", tmp_path / "b"
    counter = tmp_path / "counter"
    argv_a = writer(first, counter)
    run.run_stage("export", argv_a, {"out": first})
    run.run_stage("export", writer(second, counter), {"out": second})
    cached_a = run.run_stage("export", argv_a, {"out": first})
    assert counter.read_text() == "2"
    with pytest.raises(EvidenceMismatch, match="Ambiguous"):
        run.verify_stage("export", lambda _: True)
    verified = run.verify_stage("export", lambda files: Path(files["out"]) == first,
                                expected_signature=cached_a["signature"])
    assert verified["outputs"]["out"]["path"] == str(first.resolve())
    assert run.read()["attempts"][0]["stages"]["export"]["status"] == "verified"
    assert run.read()["attempts"][1]["stages"]["export"]["status"] == "produced"


def test_stage_requires_evidence_output(tmp_path):
    run, _ = fixture_run(tmp_path)
    with pytest.raises(ValueError, match="Stage must declare at least one evidence output"):
        run.run_stage("export", [sys.executable, "-c", "pass"], {})


def test_inputs_changed_while_stage_ran(tmp_path):
    run, inputs = fixture_run(tmp_path)
    source, output = inputs["source"], tmp_path / "out.txt"
    script = (
        "from pathlib import Path; "
        f"Path({str(output)!r}).write_text('exported'); "
        f"Path({str(source)!r}).write_text('revised-during-stage')"
    )
    record = run.run_stage("export", [sys.executable, "-c", script], {"out": output})
    assert record["status"] == "failed"
    assert record["error"] == "Inputs changed while stage ran"
    assert record["outputs"]["out"]["path"] == str(output.resolve())
    assert record["outputs"]["out"]["bytes"] == len(b"exported")
    saved = run.read()["attempts"][0]["stages"]["export"]
    assert saved["status"] == "failed"
    assert saved["error"] == "Inputs changed while stage ran"


@pytest.mark.skipif(os.name != "nt", reason="Windows taskkill cleanup")
def test_windows_timeout_cleanup_nonzero_returncode(tmp_path, monkeypatch):
    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 128, stdout=b"denied", stderr=b"err")

    monkeypatch.setattr(run_record_module.subprocess, "run", fake_run)
    monkeypatch.setattr(run_record_module, "CLEANUP_GRACE_SECONDS", 1)
    run, _ = fixture_run(tmp_path)
    record = run.run_stage("export", [sys.executable, "-c", "import time; time.sleep(30)"],
                           {"out": tmp_path / "missing"}, timeout=0.5)
    assert record["status"] == "interrupted"
    assert record["reason"] == "timeout"
    assert record["timeout_cleanup_returncode"] == 128
    assert record["timeout_cleanup_stdout"] == "denied"
    assert record["timeout_cleanup_error"] == "Tree cleanup did not terminate root promptly; direct root killed"
    assert record["returncode"] is not None
    ledger = run.read()
    assert ledger["stopped"] is True
    assert ledger["stop_reason"] == "timeout_cleanup_failed"
    assert run.read()["attempts"][0]["stages"]["export"]["status"] == "interrupted"


@pytest.mark.skipif(os.name != "nt", reason="Windows taskkill cleanup")
def test_windows_timeout_cleanup_oserror(tmp_path, monkeypatch):
    def fake_run(argv, **kwargs):
        raise OSError("taskkill missing")

    monkeypatch.setattr(run_record_module.subprocess, "run", fake_run)
    monkeypatch.setattr(run_record_module, "CLEANUP_GRACE_SECONDS", 1)
    run, _ = fixture_run(tmp_path)
    record = run.run_stage("export", [sys.executable, "-c", "import time; time.sleep(30)"],
                           {"out": tmp_path / "missing"}, timeout=0.5)
    assert record["status"] == "interrupted"
    assert record["reason"] == "timeout"
    assert record["timeout_cleanup_error"] == "Tree cleanup did not terminate root promptly; direct root killed"
    assert "timeout_cleanup_returncode" not in record
    assert record["returncode"] is not None
    ledger = run.read()
    assert ledger["stopped"] is True
    assert ledger["stop_reason"] == "timeout_cleanup_failed"
    assert run.read()["attempts"][0]["stages"]["export"]["status"] == "interrupted"


def test_running_stage_with_fully_dead_pid_is_unresolved(tmp_path):
    run, _ = fixture_run(tmp_path)
    pid = fully_dead_pid(tmp_path / "grandchild.pid")
    plant_running(run, "X", pid)
    before = run.path.read_bytes()
    output, counter = tmp_path / "out", tmp_path / "counter"
    with pytest.raises(StageUnresolved) as caught:
        run.run_stage("X", writer(output, counter), {"out": output})
    assert type(caught.value) is StageUnresolved
    assert not isinstance(caught.value, StageStillRunning)
    assert not counter.exists()
    assert not output.exists()
    assert run.path.read_bytes() == before


def test_running_stage_with_dead_pid_does_not_spawn(tmp_path):
    run, _ = fixture_run(tmp_path)
    child = exited_child()
    plant_running(run, "X", child.pid)
    before = run.path.read_bytes()
    output, counter = tmp_path / "out", tmp_path / "counter"
    with pytest.raises(StageUnresolved):
        run.run_stage("X", writer(output, counter), {"out": output})
    assert not counter.exists()
    assert run.path.read_bytes() == before
    assert len(run.read()["attempts"]) == 1


def test_release_running_stage_keeps_row_and_retries_next_attempt(tmp_path):
    run, _ = fixture_run(tmp_path)
    child = exited_child()
    plant_running(run, "X", child.pid)
    running_before = json_bytes(run.read()["attempts"][0]["stages"]["X"])
    run.release_stage("X", reason="crash")
    ledger = run.read()
    assert json_bytes(ledger["attempts"][0]["stages"]["X"]) == running_before
    assert ledger["releases"] == [{"stage": "X", "attempt": 1, "reason": "crash"}]
    output, counter = tmp_path / "out", tmp_path / "counter"
    record = run.run_stage("X", writer(output, counter), {"out": output})
    assert record["status"] == "produced"
    assert len(run.read()["attempts"]) == 2
    assert json_bytes(run.read()["attempts"][0]["stages"]["X"]) == running_before
    assert run.read()["attempts"][1]["stages"]["X"]["status"] == "produced"
    assert counter.read_text() == "1"


def test_running_stage_with_live_pid_raises_distinct_error(tmp_path):
    run, _ = fixture_run(tmp_path)
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        plant_running(run, "X", child.pid)
        before = run.path.read_bytes()
        output, counter = tmp_path / "out", tmp_path / "counter"
        with pytest.raises(StageStillRunning) as caught:
            run.run_stage("X", writer(output, counter), {"out": output})
        assert type(caught.value) is StageStillRunning
        assert not isinstance(caught.value, StageUnresolved)
        assert not counter.exists()
        assert run.path.read_bytes() == before
    finally:
        child.kill()
        child.wait(timeout=5)


def test_running_stage_without_spawned_pid_blocks(tmp_path):
    run, _ = fixture_run(tmp_path)
    plant_running(run, "X", include_pid=False)
    before = run.path.read_bytes()
    output, counter = tmp_path / "out", tmp_path / "counter"
    with pytest.raises(StageUnresolved):
        run.run_stage("X", writer(output, counter), {"out": output})
    assert not counter.exists()
    assert run.path.read_bytes() == before


def test_release_for_other_stage_or_attempt_does_not_unblock(tmp_path):
    run, _ = fixture_run(tmp_path)
    child = exited_child()
    plant_running(run, "X", child.pid, releases=[
        {"stage": "Y", "attempt": 1, "reason": "other-stage"},
        {"stage": "X", "attempt": 2, "reason": "other-attempt"},
    ])
    before = run.path.read_bytes()
    output, counter = tmp_path / "out", tmp_path / "counter"
    with pytest.raises(StageUnresolved):
        run.run_stage("X", writer(output, counter), {"out": output})
    assert not counter.exists()
    assert run.path.read_bytes() == before


def test_release_stage_without_running_record_raises(tmp_path):
    run, _ = fixture_run(tmp_path)
    before = run.path.read_bytes()
    with pytest.raises(RuntimeError, match="No running record"):
        run.release_stage("X", reason="crash")
    assert run.path.read_bytes() == before
    assert "releases" not in run.read()


def test_release_stage_rejects_unsafe_name(tmp_path):
    run, _ = fixture_run(tmp_path)
    before = run.path.read_bytes()
    with pytest.raises(ValueError, match="Unsafe identifier"):
        run.release_stage("not a stage", reason="crash")
    assert run.path.read_bytes() == before


def test_older_produced_plus_newer_running_dead_pid_blocks_before_cache(tmp_path):
    run, _ = fixture_run(tmp_path)
    output, counter = tmp_path / "out", tmp_path / "counter"
    argv = writer(output, counter)
    assert run.run_stage("X", argv, {"out": output})["status"] == "produced"
    pid = fully_dead_pid(tmp_path / "grandchild.pid")
    plant_newer_running(run, "X", pid)
    before = run.path.read_bytes()
    produced = output.read_bytes()
    with pytest.raises(StageUnresolved) as caught:
        run.run_stage("X", argv, {"out": output})
    assert type(caught.value) is StageUnresolved
    assert not isinstance(caught.value, StageStillRunning)
    assert counter.read_text() == "1"
    assert output.read_bytes() == produced
    assert run.path.read_bytes() == before


def test_older_produced_plus_newer_running_live_pid_blocks_before_cache(tmp_path):
    run, _ = fixture_run(tmp_path)
    output, counter = tmp_path / "out", tmp_path / "counter"
    argv = writer(output, counter)
    assert run.run_stage("X", argv, {"out": output})["status"] == "produced"
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        plant_newer_running(run, "X", child.pid)
        before = run.path.read_bytes()
        produced = output.read_bytes()
        with pytest.raises(StageStillRunning) as caught:
            run.run_stage("X", argv, {"out": output})
        assert type(caught.value) is StageStillRunning
        assert not isinstance(caught.value, StageUnresolved)
        assert counter.read_text() == "1"
        assert output.read_bytes() == produced
        assert run.path.read_bytes() == before
    finally:
        child.kill()
        child.wait(timeout=5)
