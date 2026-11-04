"""new-case: per-host file locks of agr-mcp, interoperable with max_exec.py and dcc_batch.py.

One lock file per host (plan section 3):
  max-live      -> %LOCALAPPDATA%\\Temp\\agr-3dsmax-live.lock   (same file as max_exec.py)
  blender-batch -> %LOCALAPPDATA%\\Temp\\agr-blender-batch.lock (new)
  offline       -> no lock
Acquire is O_CREAT|O_EXCL (dcc_batch.acquire rules). agr-mcp never waits and never steals a lock from a
live holder: a lock whose pid is alive is not stale, even after `until`. A dead pid is stale. A lock
with no pid is stale once `until` (max_exec.py format) has passed. `until` is now + lease + LOCK_MARGIN,
and the lease covers the handler (tool timeout, Max pipe budget, server floor) so a long call stays
exclusive. The file carries both formats so that max_exec.py (`card`, `until`) and dcc_batch.py
(`pid`, `t`, `timeout`) see it as held for that whole lease.
"""
from __future__ import annotations

import json
import math
import os
import secrets
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

LOCK_NAMES = {"max-live": "agr-3dsmax-live.lock", "blender-batch": "agr-blender-batch.lock"}
LOCK_MARGIN = 120  # max_exec.py writes until = now + timeout + 120; same slack here


class LockBusy(RuntimeError):
    """The host lock is held by another live holder."""


def lock_dir() -> Path:
    override = os.environ.get("AGR_MCP_LOCK_DIR")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA")
    return Path(base) / "Temp" if base else Path(tempfile.gettempdir())


def lock_path(host: str) -> Path | None:
    if host == "offline":
        return None
    if host not in LOCK_NAMES:
        raise ValueError(f"unmapped host key {host!r}")
    return lock_dir() / LOCK_NAMES[host]


def require_timeout(value, name: str) -> float:
    """Finite and strictly positive, or an error. Never a lock for NaN, inf, zero, or negative."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"invalid timeout {name}: {value!r}")
    return float(value)


def lease_seconds(tool_timeout, lock_timeout: float, max_timeout: float, slack: float = 60) -> float:
    """Seconds the host stays exclusive before LOCK_MARGIN.

    Covers the tool's own timeout, the Max pipe budget (MAX_TIMEOUT + slack) and the server floor.
    A bad input is an error before any lock file is created.
    """
    lock_s = require_timeout(lock_timeout, "lock_timeout")
    max_s = require_timeout(max_timeout, "max_timeout")
    slack_s = require_timeout(slack, "slack")
    span = max(max_s + slack_s, lock_s)
    if tool_timeout is not None:
        span = max(span, require_timeout(tool_timeout, "timeout"))
    return span


def _alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _stale(path: Path) -> bool:
    try:
        info = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False  # unreadable or half-written: treat as held, never steal
    if not isinstance(info, dict):
        return False
    pid = info.get("pid")
    if isinstance(pid, int) and not isinstance(pid, bool):
        return not _alive(pid)  # a live holder is never stale while that call still runs
    until = info.get("until")
    return (isinstance(until, (int, float)) and not isinstance(until, bool) and math.isfinite(until)
            and time.time() >= until)


@contextmanager
def hold(host: str, card: str, timeout: float):
    """Hold the host lock for one tool call; yields the lock path (None for offline)."""
    path = lock_path(host)  # unmapped host: error, no file
    seconds = require_timeout(timeout, "timeout")  # bad timeout: error, no file
    if path is None:
        yield None
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(8)
    now = time.time()
    body = json.dumps({"card": card, "pid": os.getpid(), "t": now, "timeout": seconds,
                       "until": now + seconds + LOCK_MARGIN, "owner": "agr-mcp", "token": token}).encode()
    for attempt in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if attempt == 0 and _stale(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
                continue
            raise LockBusy(f"busy: lock held: {path}") from None
        try:
            os.write(fd, body)
        finally:
            os.close(fd)
        break
    try:
        yield path
    finally:
        try:
            if json.loads(path.read_text(encoding="utf-8")).get("token") == token:
                os.remove(path)
        except (OSError, ValueError, AttributeError):
            pass
