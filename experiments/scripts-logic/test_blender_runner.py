"""Tests for the prototype runner against the synthetic fake Blender (Windows .cmd wrapper)."""
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import blender_runner  # noqa: E402

pytestmark = pytest.mark.skipif(os.name != "nt", reason="fake Blender is a .cmd wrapper")


@pytest.fixture
def fake(tmp_path):
    cmd = tmp_path / "blender.cmd"
    cmd.write_text(f'@"{sys.executable}" "{HERE / "fake_blender.py"}" %*\r\n', encoding="ascii")
    return cmd


def call(fake, tmp_path, monkeypatch, mode, timeout=30):
    monkeypatch.setenv("FAKE_BLENDER_MODE", mode)
    out = tmp_path / "readback.json"
    return blender_runner.run(fake, Path("readback.py"), "in.fbx", out, outputs=[out],
                              log=tmp_path / "blender.log", timeout=timeout)


def test_ok_returns_parsed_json_and_log(fake, tmp_path, monkeypatch):
    assert call(fake, tmp_path, monkeypatch, "ok")["readback.json"]["fake"] is True
    assert "fake blender ok" in (tmp_path / "blender.log").read_text(encoding="utf-8")


@pytest.mark.parametrize("mode", ["valid_exit7", "no_output", "malformed", "empty"])
def test_bad_runs_rejected(fake, tmp_path, monkeypatch, mode):
    with pytest.raises(blender_runner.BlenderRunError):
        call(fake, tmp_path, monkeypatch, mode)


def test_timeout_kills_tree_fast(fake, tmp_path, monkeypatch):
    t = time.perf_counter()
    with pytest.raises(blender_runner.BlenderRunError, match="timed out"):
        call(fake, tmp_path, monkeypatch, "hang", timeout=2)
    assert time.perf_counter() - t < 20


def test_flags_fixed():
    cmd = blender_runner.command("blender", "x.py", "a")
    assert cmd[1:6] == ["--background", "--factory-startup", "--disable-autoexec", "--python-exit-code", "1"]
    assert subprocess.list2cmdline(cmd).endswith("--python x.py -- a")
