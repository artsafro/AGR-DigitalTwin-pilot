"""Shared reading of a finished DCC batch result (#986).

Pattern: n/a | new-case: test helper that turns a dcc_batch busy-lock answer into a pytest skip.

Skip only after the caller has already waited, only when the exit code is 3
(dcc_batch.py and max_exec.py: "3 busy (lock held)") AND a whole line of
stdout or stderr is a top-level JSON object whose ``status`` is exactly
``busy``. Exit 0 never skips. Any other non-zero result fails, including
exit 3 without that answer and a busy answer with another exit code.
"""
from __future__ import annotations

import json

import pytest

BUSY_EXIT_CODE = 3


def _as_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value if isinstance(value, str) else str(value)


def _top_level_objects(text: str):
    """Yield every line of ``text`` that is, as a whole, one JSON object (nested ones are not yielded)."""
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            yield value


def _busy_holder(stdout: str, stderr: str):
    for text in (stdout, stderr):
        for obj in _top_level_objects(text):
            if obj.get("status") == "busy":
                return obj["held_by"] if "held_by" in obj else "<missing>"
    return None


def skip_if_dcc_session_busy(returncode: int, stdout: str = "", stderr: str = "") -> None:
    """Skip on exit 3 with a top-level busy answer; fail on any other non-zero."""
    if returncode == 0:
        return
    stdout_text = _as_text(stdout)
    stderr_text = _as_text(stderr)
    if returncode == BUSY_EXIT_CODE:
        holder = _busy_holder(stdout_text, stderr_text)
        if holder is not None:
            pytest.skip(f"DCC session lock is busy, held_by={holder!r}")
    detail = (stdout_text + stderr_text)[-2000:]
    pytest.fail(f"dcc batch exited {returncode}: {detail}")
