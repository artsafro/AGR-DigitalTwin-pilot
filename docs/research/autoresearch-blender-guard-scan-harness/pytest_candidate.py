"""pytest plugin: substitute a bench candidate into the collected guard module (parity check 4).

  BLENDER_GUARD_CANDIDATE=r1_one_walk uv run pytest -q -p pytest_candidate tests/test_blender_exit_code_guard.py
(with this directory on PYTHONPATH). Fails the session if the module was not patched.
"""
from __future__ import annotations

import os
import sys

import candidates

_PATCHED: list[str] = []


def pytest_collection_finish(session):
    name = os.environ["BLENDER_GUARD_CANDIDATE"]
    for key, mod in list(sys.modules.items()):
        if key.endswith("test_blender_exit_code_guard") and hasattr(mod, "_scan_py_source"):
            setattr(mod, "_scan_py_source", candidates.CANDIDATES[name](mod))
            _PATCHED.append(key)
    if not _PATCHED:
        raise RuntimeError("guard module not found: nothing patched")


def pytest_terminal_summary(terminalreporter):
    terminalreporter.write_line(f"candidate {os.environ.get('BLENDER_GUARD_CANDIDATE')} patched into {_PATCHED}")
