"""new-case: per-host file locks of agr-mcp, interoperable with max_exec.py and dcc_batch.py.

One lock file per host (plan section 3):
  max-live      -> %LOCALAPPDATA%\\Temp\\agr-3dsmax-live.lock   (same file as max_exec.py)
  blender-batch -> %LOCALAPPDATA%\\Temp\\agr-blender-batch.lock (new)
  offline       -> no lock
Acquire is O_CREAT|O_EXCL (dcc_batch.acquire rules). A held, unexpired lock refuses the call at once:
agr-mcp never waits and never steals a lock before `until`. A lock whose holder pid is dead, or whose
`until` (max_exec.py format) has passed, is stale and removed, including when that pid is the live
agr-mcp server (the server outlives one call, so `until` is what bounds the lease). The file carries
both formats so that max_exec.py (`card`, `until`) and dcc_batch.py (`pid`, `t`, `timeout`) see it as held.

Lifetime (#871, #895): callers pass the wrapped call's own timeout, so `until` = now + timeout + 120;
that grace already covers the wrapped call. Past `until` the lock is stale even if the holder pid is
alive, so a leaked release cannot pin the host until the server exits. A release that fails (Windows
sharing violation while a reader still has the file open) is retried a few times, then reported on
stderr; it is not swallowed.
Reclaim (#872): a stale file is atomically renamed to a unique name first; only the caller whose rename
succeeded and whose renamed file is still stale removes it. A caller that renamed a fresh lock (another
reclaimer won in between) renames it back and reports busy. Then O_EXCL create decides the single winner.
"""
from __future__ import annotations

import json
import os
import secrets
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from time import sleep as _sleep

LOCK_NAMES = {"max-live": "agr-3dsmax-live.lock", "blender-batch": "agr-blender-batch.lock"}
# A leaked os.remove (Windows error 32 while a reader keeps the file open) is retried, then reported.
_RELEASE_ATTEMPTS = 4
_RELEASE_PAUSE_S = 0.05


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
        raise ValueError(f"unknown host {host!r}")
    return lock_dir() / LOCK_NAMES[host]


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
    if isinstance(pid, int) and not _alive(pid):
        return True  # dead pid: stale even before `until`
    until = info.get("until")
    return isinstance(until, (int, float)) and time.time() >= until


def _reclaim(path: Path, token: str) -> bool:
    """Atomically take a stale lock out of the way; False when another caller got there first."""
    aside = path.with_name(f"{path.name}.reclaim-{os.getpid()}-{token}")
    try:
        os.rename(path, aside)  # atomic: at most one caller moves any given file
    except FileNotFoundError:
        return True  # another reclaimer moved it; O_EXCL create decides who holds it
    except OSError:
        return False
    if _stale(aside):
        try:
            os.remove(aside)
        except OSError:
            pass
        return True
    try:  # we moved a fresh lock created by the winning reclaimer: put it back
        os.rename(aside, path)
    except OSError:
        pass
    return False


def _release(path: Path, token: str) -> None:
    """Remove our lock. Retry a sharing violation, then report it. Never raise."""
    last: BaseException | None = None
    for attempt in range(_RELEASE_ATTEMPTS):
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return
        except OSError as exc:
            last = exc
        else:
            try:
                info = json.loads(raw)
            except ValueError:
                return  # not a lock we can prove is ours: fail closed, do not delete
            if not isinstance(info, dict) or info.get("token") != token:
                return
            try:
                os.remove(path)
            except FileNotFoundError:
                return
            except OSError as exc:
                last = exc
            else:
                return
        if attempt + 1 < _RELEASE_ATTEMPTS:
            _sleep(_RELEASE_PAUSE_S)
    sys.stderr.write(
        f"agr-mcp lock release failed after {_RELEASE_ATTEMPTS} attempts: {path}: {last}\n")
    sys.stderr.flush()


@contextmanager
def hold(host: str, card: str, timeout: float):
    """Hold the host lock for one tool call; yields the lock path (None for offline)."""
    path = lock_path(host)
    if path is None:
        yield None
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(8)
    now = time.time()
    body = json.dumps({"card": card, "pid": os.getpid(), "t": now, "timeout": timeout,
                       "until": now + timeout + 120, "owner": "agr-mcp", "token": token}).encode()
    for attempt in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if attempt == 0 and _stale(path) and _reclaim(path, token):
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
        _release(path, token)
