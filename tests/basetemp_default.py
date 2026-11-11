"""Default pytest basetemp for this repository (#1035, [D063]).

new-case: per-worktree pytest basetemp default, short and outside the repo.

A plain ``uv run pytest`` would use ``%TEMP%\\pytest-of-<user>``, which is inaccessible on the
user's machine [D063]; a basetemp inside the worktree leaves junk that blocks clean status and
CI receipts. ``tests/conftest.py`` applies :func:`default_basetemp` when ``--basetemp`` is not
given. Nothing is written to the user or registry environment (#147).
"""

import hashlib
import os
from pathlib import Path

# Short on purpose: test paths below it must stay under the Win32 MAX_PATH limits (PR #79).
MAX_BASETEMP_LEN = 32
WINDOWS_ROOT = Path("C:/x")
POSIX_ROOT = Path("/tmp")  # not $TMPDIR: it may be long or point into the worktree


def is_inside(path, repo_root):
    """True when ``path`` (relative paths: against the cwd, like pytest) lies in ``repo_root``.

    This also catches the drive-relative ``C:Users...pytest_tmp`` that ``shlex`` makes of a
    backslash ``PYTEST_ADDOPTS=--basetemp=C:\\Users\\...`` (the User env on the user's machine).
    """
    try:
        Path(os.path.abspath(str(path))).resolve().relative_to(Path(repo_root).resolve())
    except ValueError:
        return False
    return True


def default_basetemp(repo_root, *, windows=None, temproot=None):
    """Return ``<temproot>/t-<8 hex of the resolved repo root>``; ``C:/x`` on Windows.

    Raise ``ValueError`` when the result would be inside ``repo_root`` or too long.
    """
    root = Path(repo_root).resolve()
    if windows is None:
        windows = os.name == "nt"
    if temproot is None:
        temproot = WINDOWS_ROOT if windows else POSIX_ROOT
    key = str(root).replace("\\", "/").casefold() if windows else str(root)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]
    path = Path(temproot) / f"t-{digest}"
    if is_inside(path, root):
        raise ValueError(f"default basetemp {path} is inside the repository {root}")
    if len(str(path)) > MAX_BASETEMP_LEN:
        raise ValueError(f"default basetemp {path} is longer than {MAX_BASETEMP_LEN} chars")
    return path
