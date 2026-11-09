"""new-case: agr-mcp side of the one panel/MCP journal (K1, mcp-review REPORT.md 3.9, #1024 branch 0).

The journal is AGR Tools' adapters/max/agr_tools/journal_core.py: one JSON line per action, actor panel|mcp|agent,
file %LOCALAPPDATA%/AGRTools/journal/<sha1(doc)>.jsonl (AGR_JOURNAL_DIR overrides the folder).

Every MCP tools/call gets exactly one line, actor `mcp`:
* a Max call routed to runtime.edits_080/090/100 with `actor` support: the runtime writes it inside Max
  (runtime._journaled); the bridge reports `journaled: true` and the server writes nothing;
* every other call (offline tools, checks, old runtimes without `actor`, errors before Max): the server writes it
  here, with the extra fields host, instance, mcp_tool, error_code, preview_id, client, card, server_version.
The transport audit (audit.py, %LOCALAPPDATA%/agr-mcp/audit.jsonl) stays: it is the security log of every call
(args hash, lock, unsafe code hash); the journal is the action log the panel shares.
A journal write error never hides the tool's own result or error.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "adapters" / "max" / "agr_tools" / "journal_core.py"


def core():
    key = "agr_mcp_journal_core"
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, CORE)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules[key] = mod
    return sys.modules[key]


def write(tool: str, mode: str, status: str, counts: dict | None, preview_sha: str | None, duration: float,
          doc: str | None, extra: dict | None = None):
    """One journal line (actor mcp). Returns the path, or None when it could not be written."""
    try:
        jc = core()
        rec = jc.record(tool, mode, status, counts or {}, preview_sha, duration, "mcp", doc or "untitled")
        rec.update({k: v for k, v in (extra or {}).items() if k not in rec})
        return jc.append(rec, doc or "untitled")
    except Exception as exc:  # noqa: BLE001 - the journal never hides the call's own outcome
        print("agr-mcp: journal line not written: " + str(exc)[:200], file=sys.stderr)
        return None
