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
Reclaim (#872, #896): a stale lock is removed only while this process holds a short-lived mutex file,
`.<lockname>.mutex`. The mutex is published by hard-linking an already-written file onto that name
(O_EXCL via FileExistsError), so its pid / until / token body is never visible half-written. Under the
mutex the caller re-reads the lock and deletes it only when that same inode is still stale. A live lock
is never renamed aside and never unlinked. The mutex is stale when its owner pid is dead, its until has
passed, or its body does not prove a live owner — a crashed or wedged reclaimer cannot block the host.
The owner unlinks the mutex only while the token is still its own. O_EXCL create of the lock then picks
the single holder. Reclaim leaves no `*.reclaim-*` aside file.
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
# A reclaimer that dies is stale at once (dead pid). A live reclaimer that stops is stale past this ttl.
_MUTEX_TTL_S = 5.0


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


def _read_info(path: Path) -> dict | None:
    try:
        info = json.loads(path.read_text(encoding="utf-8"))
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


def _mutex_is_ours(mutex: Path, token: str) -> bool:
    info = _read_info(mutex)
    return bool(info) and info.get("token") == token and info.get("pid") == os.getpid()


def _mutex_stale(mutex: Path) -> bool:
    """Stale unless the body proves a live owner whose until is still ahead.

    Unreadable, odd, dead, or expired: the next caller may remove it. A crashed reclaimer
    (dead pid, or a body never published) does not wedge the host.
    """
    info = _read_info(mutex)
    if not isinstance(info, dict):
        return True
    pid = info.get("pid")
    until = info.get("until")
    if type(pid) is not int or pid <= 0 or not _number(until):
        return True
    if not _alive(pid):
        return True
    return time.time() >= until


def _unlink_mutex(mutex: Path) -> bool:
    try:
        if mutex.is_dir():
            os.rmdir(mutex)
        else:
            os.remove(mutex)
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return True


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
                if not (_mutex_stale(mutex) and _unlink_mutex(mutex)):
                    return False
                continue
            except OSError:
                if mutex.exists() and _mutex_stale(mutex) and _unlink_mutex(mutex):
                    continue
                return False
            if _mutex_is_ours(mutex, token):
                return True
            try:  # our link did not stick as our body: drop it only if it is still the bytes we wrote
                if mutex.read_bytes() == payload:
                    _unlink_mutex(mutex)
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
    mutex = _mutex_path(path)
    for _attempt in range(_RELEASE_ATTEMPTS):
        if not _mutex_is_ours(mutex, token):
            return
        try:
            os.remove(mutex)
        except FileNotFoundError:
            return
        except OSError:
            _sleep(_RELEASE_PAUSE_S)
        else:
            return


def _drop_stale_inode(path: Path, token: str) -> bool:
    """Delete the inode we open, and only if its own bytes are stale. Never a later file at this path."""
    if os.name == "nt":
        return _drop_stale_inode_win(path, token)
    return _drop_stale_inode_posix(path, token)


def _drop_stale_inode_posix(path: Path, token: str) -> bool:
    try:
        fd = os.open(path, os.O_RDONLY)
    except FileNotFoundError:
        return True
    except OSError:
        return False
    try:
        raw = os.read(fd, 65536)
        if not _bytes_stale(raw) or not _mutex_is_ours(_mutex_path(path), token):
            return False
        held = os.fstat(fd)
        try:
            current = os.stat(path)
        except FileNotFoundError:
            return True
        if (current.st_dev, current.st_ino) != (held.st_dev, held.st_ino):
            return False
        os.remove(path)
        return True
    finally:
        os.close(fd)


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


def _drop_stale_inode_win(path: Path, token: str) -> bool:
    import ctypes
    k = _kernel32()
    wintypes = _kernel32.wintypes
    # GENERIC_READ | DELETE, share read/write/delete, OPEN_EXISTING
    handle = k.CreateFileW(os.fspath(path), 0x80000000 | 0x00010000, 0x1 | 0x2 | 0x4,
                           None, 3, 0x80, None)
    invalid = ctypes.c_void_p(-1).value
    if handle is None or ctypes.c_void_p(handle).value in (None, 0, invalid):
        err = ctypes.get_last_error()
        return err in (2, 3)  # not found: already gone; the caller may O_EXCL
    try:
        chunks = []
        buf = ctypes.create_string_buffer(4096)
        got = wintypes.DWORD()
        while sum(len(part) for part in chunks) < 65536:
            if not k.ReadFile(handle, buf, 4096, ctypes.byref(got), None):
                err = ctypes.get_last_error()
                if err == 38 or got.value == 0:  # EOF
                    break
                return False
            if got.value == 0:
                break
            chunks.append(buf.raw[:got.value])
        if not _bytes_stale(b"".join(chunks)):
            return False
        if not _mutex_is_ours(_mutex_path(path), token):
            return False

        class _Disposition(ctypes.Structure):
            _fields_ = [("Flags", wintypes.DWORD)]

        # FileDispositionInfoEx: DELETE | POSIX_SEMANTICS. Closes this inode only.
        info = _Disposition(0x1 | 0x2)
        if not k.SetFileInformationByHandle(handle, 21, ctypes.byref(info), ctypes.sizeof(info)):
            return not path.exists()
        return True
    finally:
        k.CloseHandle(handle)


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
