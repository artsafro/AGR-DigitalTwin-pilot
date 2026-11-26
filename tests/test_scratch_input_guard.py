"""Pilot scratch-path ratchet (new-case: non-Markdown additions under rule 57)."""

import itertools
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


def scratch_files(root: Path, allowed: set[str]) -> list[str]:
    # Check the index so a clean post-merge checkout enforces the same rule as a
    # staged change, without fetching history. Treat textual occurrences in new
    # non-Markdown files conservatively; a new receipt needs exact-path review.
    command = ["git", "grep", "--cached", "-alizE", r"c:[/\\]+x[/\\]+", "--"]
    result = subprocess.run(command, cwd=root, capture_output=True)
    if result.returncode == 1 and not result.stderr:
        return []  # git grep: no matches
    result.check_returncode()
    names = result.stdout.decode("utf-8").split("\0")
    return sorted(name for name in names
                  if name and not name.lower().endswith(".md") and name not in allowed)


def test_no_new_scratch_files() -> None:
    baseline = Path(__file__).with_name("fixtures") / "scratch-input-baseline.txt"
    allowed = {line for line in baseline.read_text(encoding="utf-8").splitlines()
               if line and not line.startswith("#")}
    offenders = scratch_files(ROOT, allowed)
    assert not offenders, f"Use a durable input instead of workstation scratch: {offenders}"


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, capture_output=True, check=True)


@pytest.fixture
def checkout(tmp_path):
    git(tmp_path, "init", "-q")
    return tmp_path


def stage(root: Path, name: str, data: bytes) -> None:
    file = root / name
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(data)
    git(root, "add", "--", name)


SCRATCH = b"C:" b"/x/deleted/data.fbx"
INPUT = b'{"input":"' + SCRATCH + b'"}\n'


def test_new_input_rejected_after_commit(checkout):
    stage(checkout, "new.json", INPUT)
    git(checkout, "-c", "user.name=Synthetic", "-c", "user.email=test@example.invalid",
        "-c", "commit.gpgsign=false", "-c", "core.hooksPath=.git/no-hooks", "commit", "-qm", "test")
    assert scratch_files(checkout, set()) == ["new.json"]
    stage(checkout, "pending.json", INPUT)
    assert scratch_files(checkout, set()) == ["new.json", "pending.json"]


def test_receipt_allowance_is_exact(checkout):
    stage(checkout, "receipts/known.json", INPUT)
    stage(checkout, "receipts/other.json", INPUT)
    assert scratch_files(checkout, {"receipts/known.json"}) == ["receipts/other.json"]


def test_replacing_input_clears_finding(checkout):
    stage(checkout, "new.json", INPUT)
    assert scratch_files(checkout, set()) == ["new.json"]
    stage(checkout, "new.json", b'{"input":"G:/source.fbx"}\n')
    assert scratch_files(checkout, set()) == []


@pytest.mark.parametrize("drive,folder,first,second", list(itertools.product(
    (b"C", b"c"), (b"X", b"x"), (b"/", b"\\", b"\\\\"), (b"/", b"\\", b"\\\\"),
)))
def test_scratch_aliases(checkout, drive, folder, first, second):
    alias = drive + b":" + first + folder + second + b"file.fbx"
    stage(checkout, "mixed.cfg", b"valid=G:/source.fbx\nstale=" + alias + b"\n")
    assert scratch_files(checkout, set()) == ["mixed.cfg"]


def test_clean_scan_and_git_error(checkout, monkeypatch):
    stage(checkout, "empty", b"")
    assert scratch_files(checkout, set()) == []
    monkeypatch.setenv("GIT_DIR", str(checkout / "invalid-git"))
    with pytest.raises(subprocess.CalledProcessError):
        scratch_files(checkout, set())


def test_unrelated_content_is_ignored(checkout):
    stage(checkout, "notes.md", INPUT)
    stage(checkout, "other.json", b'{"a":"C:/xx/data.fbx","b":"D:/x/data.fbx"}')
    assert scratch_files(checkout, set()) == []
