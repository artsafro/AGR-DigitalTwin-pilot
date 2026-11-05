"""Shared reading of a finished DCC batch result (#986).

Skip only after the caller has already waited, and only when a decoded JSON
object says ``status`` is exactly ``busy``. Exit 0 never skips. Any other
non-zero result fails.
"""
from __future__ import annotations

import json

import pytest


def _as_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value if isinstance(value, str) else str(value)


def _json_objects(text: str):
    decoder = json.JSONDecoder()
    start = 0
    while True:
        brace = text.find("{", start)
        if brace < 0:
            return
        try:
            value, _end = decoder.raw_decode(text, brace)
        except json.JSONDecodeError:
            start = brace + 1
            continue
        if isinstance(value, dict):
            yield value
        start = brace + 1


def _busy_holder(stdout: str, stderr: str):
    for text in (stdout, stderr):
        for obj in _json_objects(text):
            if obj.get("status") == "busy":
                return obj["held_by"] if "held_by" in obj else "<missing>"
    return None


def skip_if_dcc_session_busy(returncode: int, stdout: str = "", stderr: str = "") -> None:
    """Skip when the batch answer is an explicit busy lock; fail on any other non-zero."""
    if returncode == 0:
        return
    stdout_text = _as_text(stdout)
    stderr_text = _as_text(stderr)
    holder = _busy_holder(stdout_text, stderr_text)
    if holder is not None:
        pytest.skip(f"DCC session lock is busy, held_by={holder!r}")
    detail = (stdout_text + stderr_text)[-2000:]
    pytest.fail(f"dcc batch exited {returncode}: {detail}")
