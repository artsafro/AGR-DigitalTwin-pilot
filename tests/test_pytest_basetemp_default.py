"""The default pytest basetemp is short and outside the repository (#1035, [D063])."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from basetemp_default import MAX_BASETEMP_LEN, default_basetemp

ROOT = Path(__file__).resolve().parents[1]
HEADER_RE = re.compile(r"^basetemp: (?P<path>.+?) \((?P<source>default|--basetemp)\)$", re.M)


def _inside(path, root):
    try:
        Path(path).resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _child_header(*extra):
    """Run a fresh pytest that only collects (no basetemp is created or wiped)."""
    env = {k: v for k, v in os.environ.items() if k not in {"PYTEST_ADDOPTS", "PYTEST_DEBUG_TEMPROOT"}}
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "--co", "-p", "no:cacheprovider", *extra, "tests/test_pytest_basetemp_default.py"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert out.returncode == 0, out.stdout[-2000:] + out.stderr[-2000:]
    found = HEADER_RE.findall(out.stdout)
    assert len(found) == 1, out.stdout[:2000]
    return found[0]


@pytest.mark.parametrize("windows", [True, False])
def test_default_is_outside_repo_and_short(windows):
    path = default_basetemp(ROOT, windows=windows)
    assert not _inside(path, ROOT)
    assert len(str(path)) <= MAX_BASETEMP_LEN
    assert "pytest-of-" not in str(path)
    if windows:
        assert str(path).replace("\\", "/").casefold().startswith("c:/x/t-")


def test_default_is_per_worktree_and_stable(tmp_path):
    a, b = tmp_path / "wt-a", tmp_path / "wt-b"
    a.mkdir()
    b.mkdir()
    assert default_basetemp(a, windows=True) == default_basetemp(a, windows=True)
    assert default_basetemp(a, windows=True) != default_basetemp(b, windows=True)
    # path aliases of one worktree map to one basetemp
    assert default_basetemp(a / "." / ".." / "wt-a", windows=True) == default_basetemp(a, windows=True)


def test_default_inside_repo_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="inside the repository"):
        default_basetemp(tmp_path, windows=False, temproot=tmp_path / "sub")


def test_plain_run_uses_default_basetemp():
    path, source = _child_header()
    assert source == "default"
    assert Path(path) == default_basetemp(ROOT)
    assert not _inside(path, ROOT)
    assert len(path) <= MAX_BASETEMP_LEN


def test_explicit_basetemp_overrides_default(tmp_path):
    want = tmp_path / "explicit"
    path, source = _child_header(f"--basetemp={want}")
    assert source == "--basetemp"
    assert Path(path) == want
    assert not want.exists()  # collection only: nothing created
