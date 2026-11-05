"""Regression for #930: the mangled-basetemp dir is ignored in any subdirectory (not only the repo root)."""
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("path", [
    "UsersartsafroAppDataLocalTemppytest_tmp/x.txt",
    "sub/UsersartsafroAppDataLocalTemppytest_tmp/x.txt",
    "a/b/UsersxTemppytest_tmp/y",
])
def test_mangled_pytest_tmp_is_ignored(path):
    proc = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", path])
    assert proc.returncode == 0


def test_no_tracked_file_matches_the_rule():
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True).stdout
    assert not [p for p in out.splitlines() if "pytest_tmp" in p and "Users" in p]
