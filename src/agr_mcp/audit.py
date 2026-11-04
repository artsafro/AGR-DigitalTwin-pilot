"""new-case: JSONL audit of agr-mcp tool calls, one line per tools/call (plan section 3).

Path: %LOCALAPPDATA%\\agr-mcp\\audit.jsonl, override AGR_MCP_AUDIT. Script bodies and file bytes are never
written: arguments go in as `args_sha256`, unsafe code as `code_sha256` + `code_bytes`.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

FIELDS = ("ts", "tool", "tool_schema_version", "server_version", "client", "card", "pid", "lock", "host",
          "scene", "target", "args_sha256", "status", "duration_ms", "error")


def audit_path() -> Path:
    override = os.environ.get("AGR_MCP_AUDIT")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    return Path(base) / "agr-mcp" / "audit.jsonl"


def args_sha256(arguments: dict) -> str:
    blob = json.dumps(arguments, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def write(record: dict) -> Path:
    """Append one line; every field of FIELDS is present (None when not applicable)."""
    line = {k: record.get(k) for k in FIELDS}
    line.update({k: v for k, v in record.items() if k not in line})
    path = audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(line, ensure_ascii=False, default=str) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0))
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    return path
