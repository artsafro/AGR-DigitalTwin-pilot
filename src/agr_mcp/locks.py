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
Reclaim (#872, #896, #972): a stale lock is removed only while this process holds a short-lived mutex
file, `.<lockname>.mutex`. The mutex is published by hard-linking an already-written file onto that name
(O_EXCL via FileExistsError), so its pid / until / token body is never visible half-written. Under the
mutex the caller re-reads the lock and deletes it only when that same inode is still stale. A live lock
is never renamed aside and never unlinked. The mutex is stale when its owner pid is dead, its until has
passed, or its body does not prove a live owner — a crashed or wedged reclaimer cannot block the host.
A live pid whose `until` is NaN or infinite has not proved expiry, so the mutex stays held. Taking a
stale mutex deletes only a name whose own bytes are still stale at the unlink. It never renames that
name aside: an empty name lets a second holder link. On POSIX the critical section takes fcntl.flock
on a persistent sentinel `.<lock>.reclaim` that is never unlinked. `_flock` is injectable because
Windows has no fcntl (the fallback is msvcrt.locking, and tests monkeypatch `_flock`). Windows deletes
a stale file through the handle that read those bytes. A live holder's file is not deleted. The owner
unlinks the mutex only while that same inode still carries its token. O_EXCL create of the lock then
picks the single holder. Reclaim leaves no `*.reclaim-*` or `*.take-*` aside file.
Release (#1043): the owner deletes its lock under the same sentinel (bounded wait) and through the
same byte + inode re-check, so a reclaimer never unlinks by name a fresh lock O_EXCL'd after release.
"""
from __future__ import annotations

import json
import math
import os
import secrets
import stat
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from time import monotonic as _monotonic
from time import sleep as _sleep

LOCK_NAMES = {"max-live": "agr-3dsmax-live.lock", "blender-batch": "agr-blender-batch.lock"}
# A leaked os.remove (Windows error 32 while a reader keeps the file open) is retried, then reported.
_RELEASE_ATTEMPTS = 4
_RELEASE_PAUSE_S = 0.05
# A reclaimer that dies is stale at once (dead pid). A live reclaimer that stops is stale past this ttl.
_MUTEX_TTL_S = 5.0
# Release waits at most this long for a reclaimer's sentinel critical section (#1043).
_RELEASE_WAIT_S = _MUTEX_TTL_S


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


def _read_bytes(path: Path) -> bytes:
    """`path.read_bytes()`, retrying a Windows sharing violation.

    A contender's `_consume_handle` holds the file with DELETE access for a moment; a plain open
    then fails with PermissionError (EACCES, no winerror). Reading that as "not ours"/"not stale"
    made every hammer thread give up. Other errors and the last attempt still raise.
    """
    for attempt in range(_RELEASE_ATTEMPTS):
        try:
            return path.read_bytes()
        except PermissionError:
            if os.name != "nt" or attempt + 1 >= _RELEASE_ATTEMPTS or path.is_dir():
                raise
        _sleep(_RELEASE_PAUSE_S)
    raise AssertionError("unreachable")


def _read_info(path: Path) -> dict | None:
    try:
        info = json.loads(_read_bytes(path).decode("utf-8"))
    except (OSError, ValueError):
        return None
    return info if isinstance(info, dict) else None


def _number(value: object) -> bool:
    return type(value) in (int, float)


def _info_stale(info: dict | None) -> bool:
    """True only when the body proves the holder is gone. Odd or unreadable bodies are held."""
    if not isinstance(info, dict):
        return False
    pid = info.get("pid")
    if type(pid) is int and not _alive(pid):
        return True  # dead pid: stale even before `until`
    until = info.get("until")
    return _number(until) and time.time() >= until


def _stale(path: Path) -> bool:
    return _info_stale(_read_info(path))


def _bytes_stale(raw: bytes) -> bool:
    try:
        info = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        return False
    return _info_stale(info if isinstance(info, dict) else None)


def _mutex_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.mutex")


def _json_constant(name: str) -> float:
    return {"NaN": float("nan"), "Infinity": float("inf"), "-Infinity": float("-inf")}[name]


def _load_mutex_json(raw: bytes):
    """Mutex JSON, including NaN/Infinity. None when the bytes are not an object."""
    try:
        info = json.loads(raw.decode("utf-8"), parse_constant=_json_constant)
    except (UnicodeError, ValueError):
        return None
    return info if isinstance(info, dict) else None


def _mutex_token_ours(raw: bytes, token: str) -> bool:
    info = _load_mutex_json(raw)
    return isinstance(info, dict) and info.get("token") == token and info.get("pid") == os.getpid()


def _mutex_is_ours(mutex: Path, token: str) -> bool:
    try:
        raw = _read_bytes(mutex)
    except OSError:
        return False
    return _mutex_token_ours(raw, token)


def _mutex_info_stale(info) -> bool:
    """Stale unless the body proves a live owner whose until is still ahead.

    Unreadable, odd, dead, or expired: one later caller may remove this inode. A live pid with
    NaN or infinite `until` has not proved expiry (fail closed: the mutex stays held). Exactly
    `until` (== now) has passed, same rule as a host lock. A crashed reclaimer does not wedge the host.
    """
    if not isinstance(info, dict):
        return True
    pid = info.get("pid")
    until = info.get("until")
    if type(pid) is not int or pid <= 0 or not _number(until):
        return True
    if not _alive(pid):
        return True
    if type(until) is int and abs(until) > 2**63:
        return until <= 0  # live pid, until outside the float range: only a past value has expired
    if not math.isfinite(float(until)):
        return False
    return time.time() >= until


def _mutex_bytes_stale(raw: bytes) -> bool:
    return _mutex_info_stale(_load_mutex_json(raw))


def _mutex_stale(mutex: Path) -> bool:
    try:
        raw = mutex.read_bytes()
    except OSError:
        return True
    return _mutex_bytes_stale(raw)


def _mutex_acquire(path: Path, token: str) -> bool:
    """O_EXCL the mutex by linking a finished body onto `.<lock>.mutex`. False = busy."""
    mutex = _mutex_path(path)
    payload = json.dumps({"pid": os.getpid(), "until": time.time() + _MUTEX_TTL_S,
                          "token": token}).encode()
    for _attempt in range(2):
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.mutex-", dir=path.parent)
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)
        try:
            try:
                os.link(temporary, mutex)
            except FileExistsError:
                if not (_mutex_stale(mutex) and _consume_stale_mutex(mutex)):
                    return False
                continue
            except OSError:
                if mutex.exists() and _mutex_stale(mutex) and _consume_stale_mutex(mutex):
                    continue
                return False
            if _mutex_is_ours(mutex, token):
                return True
            try:  # our link did not stick as our body: drop that inode only, never a later file
                _consume_if(mutex, lambda raw, payload=payload: raw == payload, allow_dir=False)
            except OSError:
                pass
            return False
        finally:
            try:
                os.remove(temporary)
            except OSError:
                pass
    return False


def _mutex_release(path: Path, token: str) -> None:
    """Unlink the mutex inode that still carries our token. A replacement at this name stays."""
    mutex = _mutex_path(path)
    for _attempt in range(_RELEASE_ATTEMPTS):
        outcome = _consume_if(mutex, lambda raw, token=token: _mutex_token_ours(raw, token), allow_dir=False)
        if outcome in ("gone", "foreign"):
            return
        _sleep(_RELEASE_PAUSE_S)


def _drop_stale_inode(path: Path, token: str) -> bool:
    """Delete the inode we open, and only if its own bytes are stale. Never a later file at this path."""
    if os.name == "nt":
        return _drop_stale_inode_win(path, token)
    return _drop_stale_inode_posix(path, token)


# fcntl.LOCK_* values. Windows has no fcntl; `_flock` is what tests monkeypatch.
try:
    import fcntl as _fcntl
    _LOCK_EX = _fcntl.LOCK_EX
    _LOCK_NB = _fcntl.LOCK_NB
    _LOCK_UN = _fcntl.LOCK_UN
except ImportError:  # Windows: fcntl is absent
    _LOCK_EX, _LOCK_NB, _LOCK_UN = 2, 4, 8


def _flock(fd: int, operation: int) -> None:
    """Exclusive-lock or unlock a reclaim sentinel fd.

    POSIX uses fcntl.flock. Windows has no fcntl; tests monkeypatch this function,
    and the body below uses msvcrt.locking so the POSIX routines still exclude each
    other when they run on Windows.
    """
    try:
        import fcntl
    except ImportError:
        _flock_fallback(fd, operation)
        return
    fcntl.flock(fd, operation)


def _flock_fallback(fd: int, operation: int) -> None:
    import msvcrt
    os.lseek(fd, 0, os.SEEK_SET)
    if operation & _LOCK_UN:
        try:
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        return
    mode = msvcrt.LK_NBLCK if operation & _LOCK_NB else msvcrt.LK_LOCK
    msvcrt.locking(fd, mode, 1)


@contextmanager
def _reclaim_exclusion(path: Path, wait_s: float = 0.0):
    """Critical section on the sentinel, polled for up to `wait_s` (0 = one non-blocking try).

    The sentinel file is never unlinked.
    """
    sentinel = path.with_name(f".{path.name}.reclaim")
    fd = None
    locked = False
    try:
        fd = os.open(os.fspath(sentinel), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            if os.fstat(fd).st_size < 1:
                os.lseek(fd, 0, os.SEEK_SET)
                os.write(fd, b"\0")
        except OSError:
            pass
        deadline = _monotonic() + wait_s
        while True:
            try:
                _flock(fd, _LOCK_EX | _LOCK_NB)
            except OSError:
                if _monotonic() >= deadline:
                    raise
                _sleep(_RELEASE_PAUSE_S)
                continue
            locked = True
            break
    except OSError:
        locked = False
    try:
        yield locked
    finally:
        if fd is not None:
            if locked:
                try:
                    _flock(fd, _LOCK_UN)
                except OSError:
                    pass
            os.close(fd)


def _unlink_named_if(path: Path, pred) -> str:
    """'gone' | 'foreign' | 'failed'. Unlink `path` only when its bytes still satisfy `pred`.

    Never renames the name aside, so the name is not empty while another inode sits beside it.
    """
    try:
        fd = os.open(os.fspath(path), os.O_RDONLY)
    except FileNotFoundError:
        return "gone"
    except OSError:
        return "failed"
    try:
        try:
            raw = os.read(fd, 65536)
            held = os.fstat(fd)
        except OSError:
            return "failed"
    finally:
        os.close(fd)
    if not pred(raw):
        return "foreign"
    try:
        # A hook (or a racer) may replace the file during this stat. The re-read below sees that.
        os.stat(os.fspath(path))
    except FileNotFoundError:
        return "gone"
    except OSError:
        return "failed"
    try:
        again = path.read_bytes()
    except FileNotFoundError:
        return "gone"
    except OSError:
        return "failed"
    if again != raw or not pred(again):
        return "foreign"
    try:
        now = os.lstat(path)
    except FileNotFoundError:
        return "gone"
    except OSError:
        return "failed"
    if (now.st_dev, now.st_ino) != (held.st_dev, held.st_ino) or stat.S_ISDIR(now.st_mode):
        return "foreign"
    try:
        os.remove(path)
    except FileNotFoundError:
        return "gone"
    except OSError:
        return "failed"
    return "gone"


def _consume_posix(path: Path, pred) -> str:
    """'gone' | 'foreign' | 'failed'. Deletes only the file whose bytes still satisfy `pred`."""
    with _reclaim_exclusion(path) as held:
        if not held:
            return "failed"
        return _unlink_named_if(path, pred)


def _consume_if(path: Path, pred, *, allow_dir: bool) -> str:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return "gone"
    except OSError:
        return "failed"
    if stat.S_ISDIR(info.st_mode):
        if not allow_dir:
            return "foreign"
        # rmdir this directory only. A file that took the name fails the rmdir and stays.
        try:
            os.rmdir(path)
        except FileNotFoundError:
            return "gone"
        except OSError:
            return "failed"
        return "gone"
    if os.name == "nt":
        return _consume_handle(path, pred)
    return _consume_posix(path, pred)


def _consume_stale_mutex(mutex: Path) -> bool:
    """Remove the mutex inode iff its own bytes are stale. False leaves whatever is at the name."""
    return _consume_if(mutex, _mutex_bytes_stale, allow_dir=True) == "gone"


def _drop_stale_inode_posix(path: Path, token: str) -> bool:
    def pred(raw: bytes, path: Path = path, token: str = token) -> bool:
        return _bytes_stale(raw) and _mutex_is_ours(_mutex_path(path), token)

    return _consume_posix(path, pred) == "gone"


def _kernel32():
    dll = getattr(_kernel32, "dll", None)
    if dll is not None:
        return dll
    import ctypes
    from ctypes import wintypes
    dll = ctypes.WinDLL("kernel32", use_last_error=True)
    dll.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    dll.CreateFileW.restype = wintypes.HANDLE
    dll.ReadFile.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    dll.ReadFile.restype = wintypes.BOOL
    dll.SetFileInformationByHandle.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    dll.SetFileInformationByHandle.restype = wintypes.BOOL
    dll.CloseHandle.argtypes = [wintypes.HANDLE]
    dll.CloseHandle.restype = wintypes.BOOL
    _kernel32.dll = dll
    _kernel32.wintypes = wintypes
    return dll


def _consume_handle(path: Path, pred) -> str:
    """'gone' | 'foreign' | 'failed'. Delete disposition applies to this handle's inode only."""
    import ctypes
    k = _kernel32()
    wintypes = _kernel32.wintypes
    # GENERIC_READ | DELETE, share read/write/delete, OPEN_EXISTING
    invalid = ctypes.c_void_p(-1).value
    handle = None
    for attempt in range(_RELEASE_ATTEMPTS):
        handle = k.CreateFileW(os.fspath(path), 0x80000000 | 0x00010000, 0x1 | 0x2 | 0x4,
                               None, 3, 0x80, None)
        if handle is not None and ctypes.c_void_p(handle).value not in (None, 0, invalid):
            break
        err = ctypes.get_last_error()
        if err in (2, 3):
            return "gone"
        # 32 = sharing violation: another caller is reading this file with a plain open (no
        # FILE_SHARE_DELETE). Transient; giving up here left every contender busy on a stale file.
        if err != 32 or attempt + 1 >= _RELEASE_ATTEMPTS:
            return "failed"
        _sleep(_RELEASE_PAUSE_S)
    try:
        chunks = []
        buf = ctypes.create_string_buffer(4096)
        got = wintypes.DWORD()
        while sum(len(part) for part in chunks) < 65536:
            if not k.ReadFile(handle, buf, 4096, ctypes.byref(got), None):
                err = ctypes.get_last_error()
                if err == 38 or got.value == 0:  # EOF
                    break
                return "failed"
            if got.value == 0:
                break
            chunks.append(buf.raw[:got.value])
        if not pred(b"".join(chunks)):
            return "foreign"

        class _Disposition(ctypes.Structure):
            _fields_ = [("Flags", wintypes.DWORD)]

        # FileDispositionInfoEx: DELETE | POSIX_SEMANTICS. Closes this inode only.
        info = _Disposition(0x1 | 0x2)
        if not k.SetFileInformationByHandle(handle, 21, ctypes.byref(info), ctypes.sizeof(info)):
            return "gone" if not path.exists() else "failed"
        return "gone"
    finally:
        k.CloseHandle(handle)


def _drop_stale_inode_win(path: Path, token: str) -> bool:
    def pred(raw: bytes, path: Path = path, token: str = token) -> bool:
        return _bytes_stale(raw) and _mutex_is_ours(_mutex_path(path), token)

    return _consume_handle(path, pred) == "gone"


def _reclaim(path: Path, token: str) -> bool:
    """Remove a lock that is still stale under the reclaim mutex. False = busy, lock untouched."""
    if not _mutex_acquire(path, token):
        return False
    try:
        if not _mutex_is_ours(_mutex_path(path), token):
            return False
        if not path.exists():
            return True
        if not _stale(path):
            return False
        return _drop_stale_inode(path, token)
    finally:
        _mutex_release(path, token)


def _lock_token_ours(raw: bytes, token: str) -> bool:
    try:
        info = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        return False  # not a lock we can prove is ours: fail closed, do not delete
    return isinstance(info, dict) and info.get("token") == token


def _release(path: Path, token: str) -> None:
    """Remove our lock. Retry a sharing violation, then report it. Never raise.

    #1043: the delete runs under the same `.<lock>.reclaim` sentinel as a POSIX reclaimer and
    through the same byte + inode re-check (`_unlink_named_if`). Otherwise a reclaimer that had
    checked our stale inode could unlink, by name, a fresh lock O_EXCL'd after our release.
    The sentinel wait is bounded; on timeout the lock stays (it expires at `until`) and is reported.
    """
    with _reclaim_exclusion(path, wait_s=_RELEASE_WAIT_S) as held:
        if not held:
            last = f"reclaim sentinel busy for {_RELEASE_WAIT_S} s"
        else:
            last = "failed"
            for attempt in range(_RELEASE_ATTEMPTS):
                outcome = _unlink_named_if(path, lambda raw, token=token: _lock_token_ours(raw, token))
                if outcome in ("gone", "foreign"):
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
