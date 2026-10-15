"""Offline lifecycle tests; model payloads below are SYNTHETIC opaque bytes."""
import hashlib
import json

import pytest


def test_stage_copies_synthetic_fixture_without_modifying_source(tmp_path):
    from tools.mcp.fixture_manager import stage_fixture

    source = tmp_path / "synthetic source.rvt"
    payload = b"SYNTHETIC fixture, not a valid Revit model"
    source.write_bytes(payload)
    run = tmp_path / "run v001"

    manifest = stage_fixture(source, run)

    assert source.read_bytes() == payload
    assert (run / "working.rvt").read_bytes() == payload
    assert manifest["source_sha256"] == hashlib.sha256(payload).hexdigest()
    assert manifest["source"] == str(source.resolve())
    assert manifest["working_copy"] == "working.rvt"
    assert manifest["delivery_passed"] is False
    assert json.loads((run / "fixture.json").read_text()) == manifest


def test_verify_allows_working_edits_but_detects_changed_etalon(tmp_path):
    from tools.mcp.fixture_manager import stage_fixture, verify_fixture

    source = tmp_path / "synthetic.blend"
    source.write_bytes(b"SYNTHETIC original")
    run = tmp_path / "run"
    stage_fixture(source, run)
    (run / "working.blend").write_bytes(b"SYNTHETIC edited working copy")
    result = verify_fixture(run)
    assert result["source_unchanged"] is True
    assert result["working_copy_changed"] is True
    assert result["working_copy_exists"] is True
    assert result["delivery_passed"] is False

    source.write_bytes(b"SYNTHETIC unexpected etalon change")
    assert verify_fixture(run)["source_unchanged"] is False
    assert (run / "working.blend").exists()


def test_stage_rejects_copy_that_changed_during_staging(tmp_path, monkeypatch):
    from tools.mcp import fixture_manager

    source = tmp_path / "synthetic.max"
    source.write_bytes(b"SYNTHETIC before")
    real_copy = fixture_manager.shutil.copyfile

    def concurrent_edit(src, dst):
        real_copy(src, dst)
        source.write_bytes(b"SYNTHETIC concurrent change")

    monkeypatch.setattr(fixture_manager.shutil, "copyfile", concurrent_edit)
    run = tmp_path / "run"
    with pytest.raises(RuntimeError, match="changed during staging"):
        fixture_manager.stage_fixture(source, run)
    assert (run / "working.max").exists()  # No automatic disposal of evidence.
    assert not (run / "fixture.json").exists()


@pytest.mark.parametrize("field,value", [
    ("schema_version", "future"),
    ("source", "relative.rvt"),
    ("source_sha256", "not-a-sha256"),
    ("working_copy", "../outside.rvt"),
    ("working_copy", "working.max"),
    ("delivery_passed", True),
])
def test_verify_rejects_invalid_manifest(tmp_path, field, value):
    from tools.mcp.fixture_manager import stage_fixture, verify_fixture

    source = tmp_path / "synthetic.rvt"
    source.write_bytes(b"SYNTHETIC")
    run = tmp_path / "run"
    manifest = stage_fixture(source, run)
    manifest[field] = value
    (run / "fixture.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid fixture manifest"):
        verify_fixture(run)


@pytest.mark.parametrize("suffix", [".txt", ".json", ""])
def test_stage_rejects_unsupported_source_before_creating_run(tmp_path, suffix):
    from tools.mcp.fixture_manager import stage_fixture

    source = tmp_path / ("synthetic" + suffix)
    source.write_bytes(b"SYNTHETIC")
    run = tmp_path / "run"
    with pytest.raises(ValueError, match="Expected .blend, .max or .rvt"):
        stage_fixture(source, run)
    assert not run.exists()


def test_existing_run_is_never_overwritten(tmp_path):
    from tools.mcp.fixture_manager import stage_fixture, verify_fixture

    source = tmp_path / "synthetic.max"
    source.write_bytes(b"SYNTHETIC")
    run = tmp_path / "run"
    stage_fixture(source, run)
    original = (run / "fixture.json").read_bytes()
    with pytest.raises(FileExistsError):
        stage_fixture(source, run)
    assert (run / "fixture.json").read_bytes() == original
    (run / "working.max").unlink()
    assert verify_fixture(run)["working_copy_exists"] is False
    source.unlink()
    assert verify_fixture(run)["source_unchanged"] is False


def test_cli_stages_and_verifies_without_importing_dcc(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / "tools/mcp/fixture_manager.py"
    source = tmp_path / "synthetic.rvt"
    source.write_bytes(b"SYNTHETIC CLI model")
    run = tmp_path / "new run"

    def invoke(*args):
        return subprocess.run([sys.executable, str(script), *map(str, args)],
                              capture_output=True, text=True, timeout=10)

    staged = invoke("stage", source, run)
    assert staged.returncode == 0, staged.stderr
    assert json.loads(staged.stdout)["working_copy"] == "working.rvt"
    verified = invoke("verify", run)
    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)["source_unchanged"] is True
    source.write_bytes(b"SYNTHETIC changed")
    changed = invoke("verify", run)
    assert changed.returncode == 1
    assert json.loads(changed.stdout)["source_unchanged"] is False
    assert invoke("stage", source, run).returncode == 2
    (run / "fixture.json").write_text("broken json", encoding="utf-8")
    assert invoke("verify", run).returncode == 2
