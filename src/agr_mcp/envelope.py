"""new-case: response envelope v2 of agr-mcp (mcp-review REPORT.md 3.7, #1024 branch 0).

structuredContent of every successful call:
  tool_schema_version (2), server_version, tool, status, summary (<= 10 lines), counts, findings_top (<= 20),
  truncated, report_uri (agr://report/<sha256> when the full result is stored), next_actions,
  result (the wrapped function's output; always for v1 tools, for v2 tools only below the inline limit),
  optional preview_id, runtime_version, doc.
An error is an MCP error result (isError) whose structuredContent is {tool_schema_version, server_version, tool,
status: "error", error_code, error, summary, next_actions}; the text content is the error message itself.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from . import ERROR_CODES, SERVER_VERSION, TOOL_SCHEMA_VERSION

FINDINGS_TOP = 20
SUMMARY_LINES = 10
STATUSES = ("pass", "fail", "ok", "not_implemented", "needs_human", "rolled_back", "error")


def inline_limit() -> int:
    """Bytes of canonical result JSON a v2 envelope carries inline (AGR_MCP_INLINE_MAX, default 64 KiB)."""
    return int(os.environ.get("AGR_MCP_INLINE_MAX", str(64 * 1024)))


def canonical(value: Any) -> str:
    """Same canonical form as edit_core.canonical: sorted keys, ASCII, no NaN, compact separators."""
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":"))


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("ascii")).hexdigest()


def data_dir() -> Path:
    """Server data folder: AGR_MCP_DATA_DIR, else %LOCALAPPDATA%/agr-mcp."""
    override = os.environ.get("AGR_MCP_DATA_DIR")
    if override:
        return Path(override)
    return Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()) / "agr-mcp"


def store_report(result: Any) -> str:
    """Write the full result once under <data>/reports/<sha256>.json; returns agr://report/<sha256>."""
    digest = sha256(result)
    path = data_dir() / "reports" / (digest + ".json")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp%d" % os.getpid())
        tmp.write_text(canonical(result), encoding="ascii")
        os.replace(tmp, path)
    return "agr://report/" + digest


def report_path(uri: str) -> Path:
    m = re.fullmatch(r"agr://report/([0-9a-f]{64})", uri or "")
    if not m:
        raise ValueError("not a report uri: " + repr(uri))
    return data_dir() / "reports" / (m.group(1) + ".json")


# ---- error codes ---------------------------------------------------------------------------------------------
_CODE_RE = re.compile(r"(?:^|[\s:(])(" + "|".join(re.escape(c) for c in ERROR_CODES if c != "error") + r"):")


def error_code(text: str, exc: BaseException | None = None) -> str:
    """Machine code of an error: the first leading `code:` the bridge/runtime/server emitted, else a class rule."""
    name = type(exc).__name__ if exc is not None else ""
    if name == "LockBusy":
        return "busy"
    if name == "StalePreview" or "StalePreview:" in text:
        return "stale_preview"
    m = _CODE_RE.search(text)
    if m:
        return m.group(1)
    if text.startswith("invalid input"):
        return "invalid_input"
    if text.startswith("unknown tool"):
        return "unknown_tool"
    if "MAXScript error" in text:
        return "maxscript_error"
    if ("no Max target pinned" in text or text.startswith("unreachable") or "pipe client failed" in text
            or text.startswith("timeout:")):
        return "host_unavailable"
    return "error"


_NEXT = {"busy": "retry after the running call ends (one call per host at a time)",
         "stale_preview": "run the preview again, then apply the new preview_id",
         "scene_mismatch": "pass scene='live' or the open document's exact path",
         "version_mismatch": "install AGR Tools >= the version named in the error, or set AGR_TOOLS_ROOT",
         "runtime_missing": "install AGR Tools in the pinned Max or set AGR_TOOLS_ROOT",
         "needs_human": "ask the user to press Apply in the AGR Tools panel/dock",
         "host_unavailable": "set AGR_MCP_MAX_PID to an open 3ds Max with the 3dsmax-mcp pipe",
         "handles_required": "pass handles, refs or scope='selection'",
         "target_conflict": "pass exactly one target source: handles, refs or scope",
         "unknown_handle": "re-read the scene; the handle is gone",
         "selection_changed": "check the Max selection; the call could not restore it",
         "not_implemented": "the row's module is a stub until its branch lands (#1024)"}


def error_envelope(tool: str, exc: BaseException) -> dict:
    text = str(exc)
    code = error_code(text, exc)
    nxt = [_NEXT[code]] if code in _NEXT else []
    return {"tool_schema_version": TOOL_SCHEMA_VERSION, "server_version": SERVER_VERSION, "tool": tool,
            "status": "error", "error_code": code, "error": text[:2000],
            "summary": "{}: error {}: {}".format(tool, code, text.splitlines()[0][:300] if text else ""),
            "next_actions": nxt}


# ---- findings ------------------------------------------------------------------------------------------------
def _ref(doc: str | None, handle: Any, name: Any) -> dict | None:
    if isinstance(handle, bool) or not isinstance(handle, int) or handle < 1:
        return None
    return {"host": "max", "doc": doc or "untitled", "handle": handle, "name": str(name or "")}


def findings(result: Any, doc: str | None = None, check: str | None = None) -> list[dict]:
    """Flat findings of a result: runtime reports (objects[].findings[]), check_run ({checks: {row: report}}),
    twinqa findings (lists of {name, status, observed, expected} with status fail), validate_package stages."""
    out: list[dict] = []
    if isinstance(result, dict) and isinstance(result.get("checks"), dict) and "objects" not in result:
        for row, rep in result["checks"].items():
            out.extend(findings(rep, doc, row))
        return out
    if isinstance(result, dict) and isinstance(result.get("objects"), list):
        for o in result["objects"]:
            if not isinstance(o, dict):
                continue
            for f in o.get("findings") or ():
                if not isinstance(f, dict):
                    continue
                item = {"code": str(f.get("code", "")), "object": o.get("name"), "handle": o.get("handle"),
                        "ids": f.get("ids"), "why": f.get("detail") or ""}
                ref = _ref(doc, o.get("handle"), o.get("name"))
                if ref:
                    item["ref"] = ref
                if check:
                    item["check"] = check
                out.append(item)
        return out
    rows = result if isinstance(result, list) else None
    if rows is None and isinstance(result, dict):
        rows = result.get("findings") if isinstance(result.get("findings"), list) else None
        if rows is None and isinstance(result.get("stages"), list):
            rows = [f for st in result["stages"] if isinstance(st, dict) for f in (st.get("findings") or ())]
    for f in rows or ():
        if isinstance(f, dict) and str(f.get("status", "")).lower() in ("fail", "error"):
            out.append({"code": str(f.get("name") or f.get("code") or ""), "object": f.get("node"),
                        "why": "observed {} / expected {}".format(f.get("observed"), f.get("expected"))})
    return out


def status_of(result: Any, found: list[dict]) -> str:
    if isinstance(result, dict):
        st = result.get("status")
        if st in STATUSES:
            return st
        if isinstance(result.get("checks"), dict) and result["checks"]:
            sts = [r.get("status") for r in result["checks"].values() if isinstance(r, dict)]
            if "fail" in sts:
                return "fail"
            if sts and all(s == "not_implemented" for s in sts):
                return "not_implemented"
            return "pass"
    return "fail" if found else "ok"


def counts_of(result: Any, found: list[dict]) -> dict:
    c = {"findings": len(found)}
    if isinstance(result, dict):
        if isinstance(result.get("objects"), list):
            c["objects"] = len(result["objects"])
        if isinstance(result.get("checks"), dict):
            c["checks"] = len(result["checks"])
            c["objects"] = sum(len(r.get("objects") or ()) for r in result["checks"].values() if isinstance(r, dict))
        plan = result.get("plan")
        if isinstance(plan, dict):
            for k in ("done", "skipped", "ambiguous"):
                if isinstance(plan.get(k), list):
                    c[k] = len(plan[k])
    elif isinstance(result, list):
        c["items"] = len(result)
    return c


def build(tool: str, result: Any, *, schema: int = 2, meta: dict | None = None) -> dict:
    """The v2 envelope of a successful call. `schema` 1 (deprecated tool): `result` always inline."""
    meta = dict(meta or {})
    doc = meta.get("doc")
    found = findings(result, doc)
    status = meta.get("status") or status_of(result, found)
    counts = counts_of(result, found)
    top = found[:FINDINGS_TOP]
    truncated = len(found) > FINDINGS_TOP
    size = len(canonical(result))
    keep_result = schema == 1 or size <= inline_limit()
    uri = None
    if truncated or not keep_result:
        uri = store_report(result)
        truncated = True
    nxt = list(meta.get("next_actions") or ())
    if uri and not nxt:
        nxt = ["read the full report: " + uri]
    lines = ["{}: {} - {}".format(tool, status, ", ".join("{} {}".format(k, v) for k, v in counts.items()))]
    if meta.get("preview_id"):
        lines.append("preview_id " + meta["preview_id"])
    for f in top[:4]:
        lines.append("- {} {} {}".format(f.get("code"), f.get("object") or "", (f.get("why") or "")[:120]).rstrip())
    if len(found) > 4:
        lines.append("... {} more finding(s){}".format(len(found) - 4, " in " + uri if uri else ""))
    for a in nxt[:2]:
        lines.append("next: " + a)
    out = {"tool_schema_version": TOOL_SCHEMA_VERSION, "server_version": SERVER_VERSION, "tool": tool,
           "status": status, "summary": "\n".join(lines[:SUMMARY_LINES]), "counts": counts, "findings_top": top,
           "truncated": truncated, "report_uri": uri, "next_actions": nxt}
    for k in ("preview_id", "runtime_version", "doc"):
        if meta.get(k):
            out[k] = meta[k]
    if keep_result:
        out["result"] = result
    return out


def schema(result: dict, v1: bool) -> dict:
    """outputSchema of a tool: the v2 envelope; v1 tools require `result` (and validate it)."""
    req = ["tool_schema_version", "server_version", "tool", "status", "summary", "counts", "findings_top",
           "truncated", "next_actions"] + (["result"] if v1 else [])
    return {"type": "object", "required": req,
            "properties": {"tool_schema_version": {"const": TOOL_SCHEMA_VERSION},
                           "server_version": {"type": "string"}, "tool": {"type": "string"},
                           "status": {"enum": list(STATUSES)}, "summary": {"type": "string"},
                           "counts": {"type": "object"},
                           "findings_top": {"type": "array", "maxItems": FINDINGS_TOP,
                                            "items": {"type": "object", "required": ["code"]}},
                           "truncated": {"type": "boolean"},
                           "report_uri": {"type": ["string", "null"], "pattern": "^agr://report/[0-9a-f]{64}$"},
                           "next_actions": {"type": "array", "items": {"type": "string"}},
                           "preview_id": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                           "result": result}}
