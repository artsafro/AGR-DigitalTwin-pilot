"""Headless Blender runner: argv, logs, failures, and the three migrated call sites."""
import importlib.util
import subprocess
from pathlib import Path

import pytest

import run_benchmark
from twinqa.blender_run import HEADLESS_FLAGS, run_blender_script
from twinqa.scene import readback

ROOT = Path(__file__).resolve().parents[2]
BLENDER = "blender-not-executed"


def _completed(cmd, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)


def test_argv_flag_order_and_run_kwargs(monkeypatch):
    recorded = {}

    def fake_run(cmd, **kwargs):
        recorded["cmd"] = cmd
        recorded["kwargs"] = kwargs
        return _completed(cmd, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    script = Path("tools/blender/do_work.py")
    proc = run_blender_script(script, [Path("model.fbx"), "out.json"], timeout=12, blender=BLENDER)
    assert proc.returncode == 0
    assert recorded["cmd"] == [
        BLENDER, "--background", "--factory-startup", "--disable-autoexec", "--python-exit-code", "1",
        "--python", str(script), "--", "model.fbx", "out.json",
    ]
    assert recorded["cmd"][1:6] == list(HEADLESS_FLAGS)
    assert recorded["kwargs"] == {"capture_output": True, "text": True, "timeout": 12}


def test_success_returns_process_and_writes_logs(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        return _completed(cmd, stdout="from-stdout", stderr="from-stderr")

    monkeypatch.setattr(subprocess, "run", fake_run)
    log_dir = tmp_path / "logs"
    proc = run_blender_script(Path("fbx_readback.py"), [], timeout=3, blender=BLENDER, log_dir=log_dir)
    assert proc.stdout == "from-stdout" and proc.stderr == "from-stderr"
    assert (log_dir / "fbx_readback.stdout.log").read_text(encoding="utf-8") == "from-stdout"
    assert (log_dir / "fbx_readback.stderr.log").read_text(encoding="utf-8") == "from-stderr"


def test_nonzero_exit_uses_stderr_tail_and_writes_logs(tmp_path, monkeypatch):
    head = "HEAD_SHOULD_BE_ABSENT_"
    stderr = head + ("x" * 40) + "TAIL99"
    log_dir = tmp_path / "logs"

    def fake_run(cmd, **kwargs):
        return _completed(cmd, returncode=3, stdout="stdout-body", stderr=stderr)

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError) as exc:
        run_blender_script(Path("export_faces.py"), [], timeout=5, blender=BLENDER, log_dir=log_dir, tail_chars=6)
    msg = str(exc.value)
    assert "export_faces.py" in msg and "exit 3" in msg
    assert stderr[-6:] in msg and head not in msg
    assert (log_dir / "export_faces.stdout.log").read_text(encoding="utf-8") == "stdout-body"
    assert (log_dir / "export_faces.stderr.log").read_text(encoding="utf-8") == stderr

    def fake_stdout_only(cmd, **kwargs):
        return _completed(cmd, returncode=3, stdout="ABCDEFGHIJ", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_stdout_only)
    with pytest.raises(RuntimeError) as exc_stdout:
        run_blender_script("plain.py", [], timeout=5, blender=BLENDER, tail_chars=4)
    text = str(exc_stdout.value)
    assert "plain.py" in text and "exit 3" in text and "GHIJ" in text and "ABCDEF" not in text


def test_timeout_raises_runtime_error_with_cause_and_logs(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs["timeout"], output=b"partial-out", stderr=None)

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError) as exc:
        run_blender_script(Path("measure.py"), ["a"], timeout=45, blender=BLENDER, log_dir=log_dir)
    err = exc.value
    assert "timed out" in str(err) and "45" in str(err) and "measure.py" in str(err)
    assert isinstance(err.__cause__, subprocess.TimeoutExpired)
    assert (log_dir / "measure.stdout.log").read_text(encoding="utf-8") == "partial-out"
    assert (log_dir / "measure.stderr.log").read_text(encoding="utf-8") == ""


def test_missing_blender_raises_before_subprocess(monkeypatch):
    monkeypatch.setattr("twinqa.scene.find_blender", lambda: None)
    called = False

    def fake_run(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("subprocess.run must not be called")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(FileNotFoundError, match="TWINQA_BLENDER"):
        run_blender_script(Path("s.py"), [], timeout=1, blender=None)
    assert called is False


def _load_check_clearance():
    path = ROOT / "tools" / "qa" / "check_clearance.py"
    spec = importlib.util.spec_from_file_location("check_clearance_runner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migrated_call_sites_use_headless_flags(monkeypatch):
    recorded = []

    def fake_run(cmd, **kwargs):
        recorded.append((list(cmd), kwargs))
        dest = Path(cmd[-1])
        if dest.suffix == ".json":
            dest.write_text("[]", encoding="utf-8")
        return _completed(cmd, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    readback(Path("x.fbx"), blender="b")
    argv = recorded[-1][0]
    assert "--disable-autoexec" in argv
    assert argv[1:6] == list(HEADLESS_FLAGS)

    clearance = _load_check_clearance()
    monkeypatch.setattr(clearance, "find_blender", lambda: "b")
    assert clearance.faces_from_fbx(Path("x.fbx")) == []
    argv = recorded[-1][0]
    assert "--disable-autoexec" in argv
    assert argv[1:6] == list(HEADLESS_FLAGS)
    assert argv[0] == "b"

    run_benchmark.blender_run("b", Path("s.py"), "a", timeout=5)
    argv, kwargs = recorded[-1]
    assert argv == [
        "b", "--background", "--factory-startup", "--disable-autoexec", "--python-exit-code", "1",
        "--python", str(Path("s.py")), "--", "a",
    ]
    assert kwargs["timeout"] == 5
    assert kwargs["capture_output"] is True and kwargs["text"] is True
