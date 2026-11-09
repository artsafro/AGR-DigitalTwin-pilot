"""new-case: previews held by the agr-mcp server (mcp-review REPORT.md 3.3, #1024 branch 0).

`preview_id = sha256(canonical(report))` of the preview report the runtime answered (edit_core contract: the report
carries plan.hash and plan.state_hash). The server keeps the report and its binding; the agent gets only the id and
`agr_op_apply` takes only the id (+ optional idempotency_key). Binding: host, instance (AGR_MCP_MAX_PID), doc
(the open document the bridge reported), runtime_version, state_hash (plan.state_hash), op (plan row), targets
(scene + handles/scope of the preview call). TTL: AGR_MCP_PREVIEW_TTL seconds (default 1800).

Apply refuses with `stale_preview` when the id is unknown (never issued, expired, server restarted without the file
store, already applied) or the binding differs from now (another Max pid). The bridge then re-checks the doc and the
runtime version in Max (stale_preview) and the runtime glue re-checks plan.hash and state_hash
(edit_core.check_preview / require_current -> StalePreview -> stale_preview).

Storage: in memory per server process. AGR_MCP_PREVIEW_STORE=file additionally writes <data>/previews/<id>.json so a
restarted server (same machine) can still apply within the TTL. Nothing else reads those files.
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from . import envelope

BINDING_KEYS = ("host", "instance", "doc", "runtime_version", "state_hash", "op")


class PreviewError(ValueError):
    """str() starts with the machine code (stale_preview, idempotency_conflict)."""


@dataclass
class Held:
    preview_id: str
    report: dict
    binding: dict
    targets: dict
    created: float
    applied: bool = False
    meta: dict = field(default_factory=dict)


def current_instance(env=None) -> str | None:
    env = os.environ if env is None else env
    return env.get("AGR_MCP_MAX_PID") or env.get("MCP_MAX_PID") or env.get("MCP_MAX_PIPE") or None


class PreviewStore:
    def __init__(self, ttl: float | None = None, clock: Callable[[], float] = time.time, folder: Path | None = None,
                 persist: bool | None = None):
        self.ttl = float(os.environ.get("AGR_MCP_PREVIEW_TTL", "1800")) if ttl is None else float(ttl)
        self.clock = clock
        self.persist = (os.environ.get("AGR_MCP_PREVIEW_STORE") == "file") if persist is None else persist
        self.folder = folder
        self._held: dict[str, Held] = {}
        self._done: dict[str, tuple[str, object]] = {}  # idempotency_key -> (preview_id, outcome)
        self._lock = threading.Lock()

    def _dir(self) -> Path:
        return self.folder or (envelope.data_dir() / "previews")

    def put(self, report: dict, binding: dict, targets: dict) -> str:
        pid = envelope.sha256(report)
        held = Held(pid, report, {k: binding.get(k) for k in BINDING_KEYS}, dict(targets), self.clock())
        with self._lock:
            self._held[pid] = held
        if self.persist:
            path = self._dir() / (pid + ".json")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(asdict(held), sort_keys=True), encoding="utf-8")
        return pid

    def _load(self, pid: str) -> Held | None:
        with self._lock:
            held = self._held.get(pid)
        if held is None and self.persist:
            path = self._dir() / (pid + ".json")
            if path.is_file():
                held = Held(**json.loads(path.read_text(encoding="utf-8")))
                with self._lock:
                    self._held[pid] = held
        return held

    def get(self, pid: str, binding_now: dict) -> Held:
        """The held preview while fresh and bound to the same host/instance; else stale_preview."""
        held = self._load(pid)
        if held is None:
            raise PreviewError("stale_preview: unknown preview_id (never issued here, expired or the server "
                               "restarted); run the preview again")
        if self.clock() - held.created > self.ttl:
            self.drop(pid)
            raise PreviewError("stale_preview: preview older than {:.0f} s; run the preview again".format(self.ttl))
        if held.applied:
            raise PreviewError("stale_preview: this preview was already applied; run the preview again")
        for k, v in binding_now.items():
            if k in held.binding and held.binding[k] != v:
                raise PreviewError("stale_preview: {} changed since the preview ({!r} -> {!r})"
                                   .format(k, held.binding[k], v))
        return held

    def drop(self, pid: str) -> None:
        with self._lock:
            self._held.pop(pid, None)
        if self.persist:
            try:
                (self._dir() / (pid + ".json")).unlink()
            except OSError:
                pass

    def mark_applied(self, pid: str) -> None:
        with self._lock:
            if pid in self._held:
                self._held[pid].applied = True
        if self.persist:
            self.drop(pid)

    def replay(self, key: str | None, pid: str):
        """The outcome of an earlier apply with this idempotency_key, or None."""
        if not key:
            return None
        with self._lock:
            done = self._done.get(key)
        if done is None:
            return None
        if done[0] != pid:
            raise PreviewError("idempotency_conflict: idempotency_key was used for another preview_id")
        return done[1]

    def remember(self, key: str | None, pid: str, outcome) -> None:
        if key:
            with self._lock:
                self._done[key] = (pid, outcome)
