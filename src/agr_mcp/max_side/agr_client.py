"""new-case: agr-mcp side of the AGR listener (#1024 branch U): client, per-instance lease, Max transport.

`ListenerClient` talks to one Max instance (agr_registry entry). `Leases` is the per-instance lease of the daemon
(mcp-review §3.9): one writer per Max, fencing token per call, and the lease is NOT released when the client side
times out while Max still works (§2.4.5, §3.5): the call keeps reading its answer while `status` says the listener
is busy with this job; only a dead Max (pid gone) or the hard cap ends the wait, and after the hard cap the lease
stays poisoned until the listener reports idle.

`transport(code, timeout)` replaces max_pipe.pipe_transport for the whole v1/v2 catalogue: it accepts ONLY the exact
expression max_pipe.bridge_script builds (tool name + hex arguments) and sends tool/root/args as data; any other
MAXScript is refused unless the instance runs a dev listener (exec allowed) and the daemon runs the dev profile.
"""
from __future__ import annotations

import json
import re
import secrets
import socket
import threading
import time

from . import agr_registry

_SCRIPT = re.compile(r'b\.call "([A-Za-z0-9_]+)" "([0-9a-f]*)" "([0-9a-f]*)"\n\)\Z')


class HostError(RuntimeError):
    """str() starts with a machine code (busy, host_unavailable, forbidden, needs_human, ...)."""

    def __init__(self, text, payload=None):
        super().__init__(text)
        self.payload = payload if isinstance(payload, dict) else {}


class ListenerClient:
    def __init__(self, entry: dict, poll_s: float = 0.5, hard_cap_s: float = 4 * 3600, alive=agr_registry.alive):
        self.entry = dict(entry)
        self.pid = int(entry["pid"])
        self.poll_s, self.hard_cap_s, self.alive = poll_s, hard_cap_s, alive
        self.waited_busy_s = 0.0

    def _send(self, req: dict, timeout: float | None):
        s = socket.create_connection(("127.0.0.1", int(self.entry["port"])), timeout=10)
        s.settimeout(timeout)
        s.sendall((json.dumps(dict(req, token=self.entry["token"]), allow_nan=False) + "\n").encode("utf-8"))
        return s

    @staticmethod
    def _recv(s) -> dict:
        buf = bytearray()
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
            if b"\n" in chunk:
                break
        if not buf:
            raise HostError("host_unavailable: the listener closed the connection without an answer")
        return json.loads(buf.split(b"\n", 1)[0].decode("utf-8"))

    def status(self) -> dict:
        s = self._send({"kind": "status"}, 10)
        try:
            return self._recv(s)
        finally:
            s.close()

    def call(self, kind: str, payload: dict, timeout: float) -> dict:
        """One job; returns the listener answer dict (ok true/false). Waits past `timeout` while Max is busy."""
        job = secrets.token_hex(8)
        try:
            s = self._send(dict(payload, kind=kind, id=job), max(float(timeout), 0.1))
        except OSError as exc:
            raise HostError("host_unavailable: listener of Max pid {} unreachable: {}".format(self.pid, exc)) \
                from None
        started = time.time()
        try:
            while True:
                try:
                    return self._recv(s)
                except socket.timeout:
                    pass
                except OSError as exc:
                    raise HostError("host_unavailable: {}".format(exc)) from None
                # client-side timeout: hold on while Max is still on this job (never release a busy host)
                if not self.alive(self.pid):
                    raise HostError("host_unavailable: Max pid {} exited during the call".format(self.pid))
                try:
                    st = self.status()
                except (OSError, ValueError, HostError):
                    st = {"busy": True, "current": job}
                if st.get("current") != job and not st.get("busy"):
                    s.settimeout(self.poll_s)  # finished: the answer is in flight
                    continue
                if time.time() - started > self.hard_cap_s:
                    raise HostError("busy: Max pid {} still runs job {} after {:.0f} s; the lease stays held until "
                                    "it reports idle".format(self.pid, job, time.time() - started),
                                    {"poisoned": True})
                self.waited_busy_s = time.time() - started
                s.settimeout(self.poll_s)
        finally:
            s.close()


class Leases:
    """Per-instance lease of the daemon: one call per Max at a time; fencing token per call."""

    def __init__(self):
        self._locks: dict[int, threading.Lock] = {}
        self._poisoned: set[int] = set()
        self._guard = threading.Lock()
        self.fence = 0
        self.holder: dict[int, int] = {}

    def acquire(self, pid: int, client: ListenerClient | None = None) -> int:
        with self._guard:
            lock = self._locks.setdefault(int(pid), threading.Lock())
        if not lock.acquire(blocking=False):
            raise HostError("busy: another agr-mcp call is running on Max pid {}".format(pid))
        if int(pid) in self._poisoned:
            try:
                idle = client is not None and not client.status().get("busy")
            except Exception:  # noqa: BLE001
                idle = False
            if not idle:
                lock.release()
                raise HostError("busy: Max pid {} has not reported idle since a timed-out call".format(pid))
            self._poisoned.discard(int(pid))
        with self._guard:
            self.fence += 1
            self.holder[int(pid)] = self.fence
            return self.fence

    def release(self, pid: int, poisoned: bool = False) -> None:
        if poisoned:
            self._poisoned.add(int(pid))
        with self._guard:
            self.holder.pop(int(pid), None)
            lock = self._locks.get(int(pid))
        if lock is not None and lock.locked():
            lock.release()

    def held(self, pid: int) -> bool:
        lock = self._locks.get(int(pid))
        return bool(lock and lock.locked())


class Host:
    """The daemon's view of one Max: registry entry + client + lease. `run(kind, payload, timeout)` holds the
    lease for the whole call, including the wait for idle after a client-side timeout."""

    def __init__(self, leases: Leases | None = None, pin=None, env=None, client_factory=None, allow_exec=False):
        self.leases = leases or Leases()
        self.pin, self.env = pin, env
        self.client_factory = client_factory or (lambda entry: ListenerClient(entry))
        self.allow_exec = bool(allow_exec)

    def client(self) -> ListenerClient:
        try:
            entry = agr_registry.select(self.pin, self.env)
        except agr_registry.RegistryError as exc:
            raise HostError(str(exc)) from None
        return self.client_factory(entry)

    def instance(self):
        try:
            return int(agr_registry.select(self.pin, self.env)["pid"])
        except agr_registry.RegistryError:
            return None

    def run(self, kind: str, payload: dict, timeout: float) -> dict:
        client = self.client()
        self.leases.acquire(client.pid, client)
        poisoned = False
        try:
            ans = client.call(kind, payload, timeout)
        except HostError as exc:
            poisoned = bool(exc.payload.get("poisoned"))
            raise
        finally:
            self.leases.release(client.pid, poisoned)
        if not ans.get("ok"):
            raise HostError(str(ans.get("error") or "error: listener answered without ok"), ans)
        ans["instance"] = client.pid
        return ans

    def transport(self, code: str, timeout: float) -> str:
        """max_pipe transport over the listener: only the bridge expression, as data."""
        from .. import max_pipe
        m = _SCRIPT.search(code)
        if m:
            tool, root_hex, args_hex = m.groups()
            try:
                rebuilt = max_pipe.bridge_script(tool, bytes.fromhex(root_hex).decode("utf-8"),
                                                 json.loads(bytes.fromhex(args_hex).decode("utf-8")))
            except (ValueError, UnicodeDecodeError):
                rebuilt = None
            if rebuilt == code:
                try:
                    ans = self.run("bridge", {"tool": tool, "root_hex": root_hex, "args_hex": args_hex}, timeout)
                except HostError as exc:
                    raise max_pipe.MaxError(str(exc), exc.payload) from None
                return ans["value"]
        if not self.allow_exec:
            raise max_pipe.MaxError("forbidden: only the agr-mcp bridge call goes to Max over the AGR listener; "
                                    "arbitrary MAXScript needs the dev profile")
        try:
            return self.run("exec", {"code": code}, timeout)["value"]
        except HostError as exc:
            raise max_pipe.MaxError(str(exc), exc.payload) from None
