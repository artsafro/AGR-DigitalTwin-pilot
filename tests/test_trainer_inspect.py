"""Tests for the isolated (no-``uv run``) trainer inspect launcher (#1858).

Pattern: n/a | new-case: sandbox-safe ``agr inspect`` launcher for the trainer's oks-vpm lane.
"""
import importlib
import json
import sys
from pathlib import Path

import pytest

from dt_ai.trainer import inspect as mod


REPO = mod.repo_root()
VALID = REPO / "jobs" / "SYNTH-001" / "project.json"


def _write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


# ---- isolated interpreter discovery / bootstrap ------------------------------------------------
def test_isolated_python_discovers_venv():
    python = mod.isolated_python(REPO)
    assert python.is_file()
    assert "python" in python.name.lower()


def test_isolated_python_override_must_be_a_file(tmp_path):
    missing = tmp_path / "no-python.exe"
    with pytest.raises(mod.BootstrapError):
        mod.isolated_python(REPO, missing)


def test_isolated_python_missing_in_bare_root(tmp_path):
    with pytest.raises(mod.BootstrapError):
        mod.isolated_python(tmp_path)


# ---- outcomes ---------------------------------------------------------------------------------
def test_run_ok_reaches_inspect_logic(capsys):
    assert mod.run(REPO, VALID, override=Path(sys.executable)) == mod.EXIT_OK
    out = json.loads(capsys.readouterr().out)
    assert out == {"project_id": "SYNTH_001", "synthetic": True, "materials": 2, "surfaces": 6}


def test_run_missing_manifest(tmp_path, capsys):
    missing = tmp_path / "absent.json"
    assert mod.run(REPO, missing, override=Path(sys.executable)) == mod.EXIT_MISSING
    assert "manifest missing" in capsys.readouterr().err


@pytest.mark.parametrize("content", [
    "",                                     # empty
    "{",                                    # truncated
    '{"partial":',                          # partial
    "NaN",                                  # non-finite
    "Infinity",                             # non-finite
    "-Infinity",                            # non-finite
    '{"a": 1, "a": 2}',                     # duplicate key
    "{}",                                   # not a BuildJob
    "null",
    "[]",
    '"unsupported"',
])
def test_run_malformed_manifest(tmp_path, capsys, content):
    manifest = _write(tmp_path, "bad.json", content)
    assert mod.run(REPO, manifest, override=Path(sys.executable)) == mod.EXIT_MALFORMED
    assert "manifest" in capsys.readouterr().err


def test_run_manifest_is_a_directory(tmp_path, capsys):
    manifest = tmp_path / "dir"
    manifest.mkdir()
    assert mod.run(REPO, manifest, override=Path(sys.executable)) == mod.EXIT_MALFORMED
    assert "not a file" in capsys.readouterr().err


def test_run_bootstrap_no_venv(tmp_path, capsys):
    assert mod.run(tmp_path, VALID) == mod.EXIT_BOOTSTRAP
    assert "bootstrap" in capsys.readouterr().err


def test_run_bootstrap_unstartable_interpreter(tmp_path, capsys):
    fake = tmp_path / "python.exe"
    fake.write_text("not a binary", encoding="utf-8")
    # A non-executable file fails to spawn: OSError is mapped to bootstrap.
    assert mod.run(REPO, VALID, override=fake) in (mod.EXIT_BOOTSTRAP, mod.EXIT_MALFORMED)


# ---- Gate 1 (pipeline attempts-gate) ----------------------------------------------------------
def test_gate_errors_detects_locked_job(tmp_path):
    job = tmp_path / "jobs" / "LOCKED"
    (job / "pipeline").mkdir(parents=True)
    (job / "pipeline" / "state.json").write_text(json.dumps({
        "failures": [{"item": "check:qa", "kind": "checker", "cause": "code"}] * 3,
        "stops": [],
    }), encoding="utf-8")
    errors = mod.gate_errors(tmp_path, "LOCKED")
    assert errors
    assert any("locked" in e for e in errors)


def test_gate_errors_open_when_no_state(tmp_path):
    (tmp_path / "jobs" / "OPEN").mkdir(parents=True)
    assert mod.gate_errors(tmp_path, "OPEN") == []


def test_manifest_job(tmp_path):
    (tmp_path / "jobs" / "J1").mkdir(parents=True)
    assert mod.manifest_job(tmp_path, tmp_path / "jobs" / "J1" / "x.json") == "J1"
    assert mod.manifest_job(tmp_path, tmp_path / "outside.json") is None


def test_run_gate1_when_locked(monkeypatch, capsys):
    monkeypatch.setattr(mod, "gate_errors", lambda root, job: ["locked item"])
    assert mod.run(REPO, VALID, override=Path(sys.executable)) == mod.EXIT_GATE1
    assert "gate1" in capsys.readouterr().err


# ---- preflight --------------------------------------------------------------------------------
def test_preflight_ready(capsys):
    assert mod.preflight(REPO, override=Path(sys.executable)) == mod.EXIT_OK
    assert "READY" in capsys.readouterr().out


def test_preflight_not_ready(tmp_path, capsys):
    assert mod.preflight(tmp_path) == mod.EXIT_BOOTSTRAP
    assert "NOT READY" in capsys.readouterr().err


# ---- read-only, fail-closed witnesses ---------------------------------------------------------
def test_run_does_not_modify_input(tmp_path):
    manifest = tmp_path / "m.json"
    manifest.write_bytes(VALID.read_bytes())
    before = manifest.read_bytes()
    mod.run(REPO, manifest, override=Path(sys.executable))
    assert manifest.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["m.json"]


def test_cli_is_a_fresh_process(tmp_path, capsys):
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "dt_ai.trainer.inspect", "--manifest", str(VALID)],
        cwd=REPO, capture_output=True, text=True,
    )
    assert result.returncode == mod.EXIT_OK, result.stderr
    assert json.loads(result.stdout)["project_id"] == "SYNTH_001"


def test_exit_codes_are_distinct():
    codes = {mod.EXIT_OK, mod.EXIT_BOOTSTRAP, mod.EXIT_MISSING, mod.EXIT_MALFORMED, mod.EXIT_GATE1}
    assert len(codes) == 5
    assert codes == {0, 2, 3, 4, 5}
