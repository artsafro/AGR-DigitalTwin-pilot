"""PROTOTYPE (experiment t_d6c8f213): host-global, multi-step DCC lease.

Report docs/research/mcp-dcc-bridges.md section 2.3: one lease per PROGRAM, held across a whole multi-call
workflow (not per call), owner identified by PID + process start time (PID reuse safe), monotonically
increasing fencing token, dead owner -> reclaim only after the DCC answers a ping (else quarantine).

    with Lease("blender", card="t_x", ping=fn) as lease:   # blocks until acquired
        lease.token                                          # fencing token, pass to each step
        lease.check()                                        # raises Fenced if the lease was taken over

Cooperative only: a client that talks to the port directly bypasses it (report 2.3.1).
"""
import ctypes
import json
import os
import time
from ctypes import wintypes

ROOT = os.environ.get("AGR_DCC_LEASE_DIR") or os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Temp", "agr-dcc-leases")

_k32 = ctypes.WinDLL("kernel32", use_last_error=True) if os.name == "nt" else None
_STILL_ACTIVE = 259


def process_start(pid: int):
    """Process creation time (FILETIME as int) or None when the process does not exist / has exited."""
    if _k32 is None:  # POSIX fallback: /proc start time
        try:
            return int(open(f"/proc/{pid}/stat").read().split()[21])
        except OSError:
            return None
    h = _k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return None
    try:
        code = wintypes.DWORD()
        if _k32.GetExitCodeProcess(h, ctypes.byref(code)) and code.value != _STILL_ACTIVE:
            return None
        c, e, k, u = (wintypes.FILETIME() for _ in range(4))
        if not _k32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u)):
            return None
        return (c.dwHighDateTime << 32) | c.dwLowDateTime
    finally:
        _k32.CloseHandle(h)


class Busy(Exception):
    pass


class Fenced(Exception):
    pass


class Quarantined(Exception):
    pass


class Lease:
    def __init__(self, program, card="manual", wait=600.0, poll=0.1, ping=None):
        os.makedirs(ROOT, exist_ok=True)
        self.program, self.card, self.wait, self.poll, self.ping = program, card, wait, poll, ping
        self.path = os.path.join(ROOT, f"{program}.lease")
        self.counter = os.path.join(ROOT, f"{program}.token")
        self.token = None
        self.reclaims = []  # why a previous lease was taken over

    # --- owner liveness -------------------------------------------------------------------------------
    def _owner_alive(self, info) -> bool:
        pid, start = info.get("pid"), info.get("pid_start")
        if not pid:
            return False
        actual = process_start(int(pid))
        return actual is not None and actual == start

    def _read(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def _next_token(self) -> int:
        try:
            n = int(open(self.counter).read().strip() or 0)
        except (OSError, ValueError):
            n = 0
        with open(self.counter, "w") as f:
            f.write(str(n + 1))
        return n + 1

    def acquire(self):
        deadline = time.time() + self.wait
        me = os.getpid()
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                info = self._read()
                if info is None:  # half-written file of a racing writer; retry
                    time.sleep(self.poll)
                    continue
                if not self._owner_alive(info):
                    # dead owner: its last call may still run in the DCC -> reclaim only if the DCC answers
                    if self.ping is not None and not self.ping():
                        raise Quarantined(f"{self.program}: owner {info.get('card')} pid {info.get('pid')} "
                                          f"is gone and the DCC does not answer; manual reconciliation")
                    why = "pid_reused" if process_start(int(info["pid"])) is not None else "owner_dead"
                    self.reclaims.append({"from": info.get("card"), "why": why})
                    try:
                        os.remove(self.path)
                    except OSError:
                        pass
                    continue
                if time.time() >= deadline:
                    raise Busy(f"{self.program} leased by {info.get('card')} (token {info.get('token')})")
                time.sleep(self.poll)
                continue
            # the token counter is only touched by the holder of the O_EXCL file -> no race
            self.token = self._next_token()
            os.write(fd, json.dumps({"program": self.program, "card": self.card, "pid": me,
                                     "pid_start": process_start(me), "token": self.token,
                                     "t": time.time()}).encode())
            os.close(fd)
            return self

    def check(self):
        info = self._read()
        if not info or info.get("token") != self.token:
            raise Fenced(f"lease token {self.token} is no longer current ({info and info.get('token')})")

    def release(self):
        info = self._read()
        if info and info.get("token") == self.token:
            os.remove(self.path)

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc):
        self.release()
