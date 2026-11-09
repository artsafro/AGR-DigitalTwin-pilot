"""new-case: one MCP tool of agr-mcp (shared by tools.py, catalog.py and branch U's ops_d108.py)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class Spec:
    name: str
    description: str
    input: dict
    result: dict
    handler: Callable[[dict], Any]
    host: Callable[[dict], str]
    read_only: bool = True
    destructive: bool = False
    timeout: Callable[[dict], float] | None = None  # the wrapped call's own timeout; sizes the host lock (#871)
    # 1: deprecated v1 tool (envelope keeps the full `result`, content = the JSON envelope).
    # 2: tool of the v2 catalogue (content = the <=10 line summary; `result` dropped above the inline limit).
    schema: int = 1
    row: str | None = None  # plan row id of a one-row tool (journal `tool`)


@dataclass
class Outcome:
    """What a handler may return instead of a bare result: the result plus facts for the envelope/journal.

    meta keys (all optional): runtime_version, runtime_file, doc, selection, journaled (the runtime already wrote
    the journal line), preview_id, row, mode, next_actions, status, replay."""
    result: Any
    meta: dict = field(default_factory=dict)
