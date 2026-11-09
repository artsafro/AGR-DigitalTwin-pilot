"""new-case: agr-mcp stdio MCP server, one process per client (plan section 3; v2 envelope #1024 branch 0).

Run: `uv run agr-mcp` (console script) or `python -m agr_mcp.server`. Every tools/call - success, error,
refusal, unknown tool - writes exactly one audit line (audit.py) and is recorded in the one panel/MCP journal
(journal.py: a line here, or the runtime's own line inside Max). Input is validated here (not by the SDK) so that
rejected calls are audited too. A held host lock refuses the call at once (error_code busy).

Answers: envelope v2 (envelope.py). v1 tools keep content = the JSON envelope and the full `result`; v2 tools
answer content = the <=10 line summary. Errors are isError results with structuredContent.error_code.
"""
from __future__ import annotations

import hashlib
import os
import time

import anyio
import jsonschema
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.types import LATEST_PROTOCOL_VERSION

from . import SERVER_NAME, SERVER_VERSION, TOOL_SCHEMA_VERSION, audit, envelope, journal, locks, tools
from .max_side import max_bridge
from .preview_store import PreviewStore, current_instance
from .spec import Outcome

INSTRUCTIONS = (f"AGR checkers and AGR Tools rows over MCP. tool_schema_version={TOOL_SCHEMA_VERSION} (envelope "
                f"v2: status, summary, counts, findings_top, report_uri, next_actions, error_code); protocol "
                f"{LATEST_PROTOCOL_VERSION} (mcp SDK 1.30.0). Max tools need AGR_MCP_MAX_PID. Editing rows: "
                f"preview only (agr_op_preview / stage tools -> preview_id); agr_op_apply only for 0.8 rows, "
                f"everything else needs_human (the AGR Tools panel/dock button). v1 tools are deprecated.")


def unsafe_enabled(env=None) -> bool:
    return (os.environ if env is None else env).get("AGR_MCP_UNSAFE") == "1"


def envelope_schema(result: dict, v1: bool = True) -> dict:
    return envelope.schema(result, v1)


def _client_name(server: Server) -> str | None:
    try:
        info = server.request_context.session.client_params.clientInfo
        return info.name if info else None
    except (LookupError, AttributeError):
        return None


def _journal_doc(meta: dict, arguments: dict) -> str:
    if meta.get("doc"):
        return meta["doc"]
    scene = arguments.get("scene")
    return scene if isinstance(scene, str) and scene and scene != "live" else "untitled"


def _journal_mode(spec, meta: dict, arguments: dict) -> str:
    if meta.get("mode"):
        return meta["mode"]
    if spec is not None and spec.name == "agr_op_apply":
        return "apply"
    route = max_bridge.ROUTES.get(spec.row) if spec is not None and spec.row else None
    if route and route[0].startswith("e"):  # an edits_080/090/100 row: the runtime's own mode
        return str(arguments.get("mode") or "preview")
    return "read"


def build_server(env=None, max_transport=None, lock_timeout: float = 900, store: PreviewStore | None = None) -> Server:
    store = store or PreviewStore()
    catalog = tools.catalog(unsafe=unsafe_enabled(env), max_transport=max_transport, store=store)
    server = Server(SERVER_NAME, version=SERVER_VERSION, instructions=INSTRUCTIONS)

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [types.Tool(name=s.name, description=s.description, inputSchema=s.input,
                           outputSchema=envelope_schema(s.result, s.schema == 1),
                           annotations=types.ToolAnnotations(readOnlyHint=s.read_only,
                                                             destructiveHint=s.destructive,
                                                             openWorldHint=False))
                for s in catalog.values()]

    @server.call_tool(validate_input=False)
    async def call_tool(name: str, arguments: dict | None):
        arguments = arguments or {}
        started = time.perf_counter()
        spec = catalog.get(name)
        record = {"ts": audit.now_utc(), "tool": name, "tool_schema_version": TOOL_SCHEMA_VERSION,
                  "server_version": SERVER_VERSION, "client": _client_name(server),
                  "card": os.environ.get("AGR_MCP_CARD") or os.environ.get("HERMES_KANBAN_TASK"),
                  "pid": os.getpid(), "lock": None, "host": None,
                  "scene": arguments.get("scene"),
                  "target": arguments.get("target") or arguments.get("fbx_path") or arguments.get("path"),
                  "args_sha256": audit.args_sha256(arguments), "status": None, "error": None,
                  "error_code": None, "preview_id": arguments.get("preview_id")}
        if name == "agr_exec_unsafe":
            code = str(arguments.get("code", "")).encode("utf-8")
            record.update(unsafe=True, code_sha256=hashlib.sha256(code).hexdigest(), code_bytes=len(code))
        meta: dict = {}
        env_out: dict | None = None
        try:
            if spec is None:
                record["status"] = "refused"
                raise ValueError(f"unknown tool {name!r}" + (" (agr_exec_unsafe needs AGR_MCP_UNSAFE=1)"
                                                             if name == "agr_exec_unsafe" else ""))
            try:
                jsonschema.validate(arguments, spec.input)
                tools._check_finite(arguments, "arguments")
            except (jsonschema.ValidationError, ValueError) as exc:
                record["status"] = "invalid"
                raise ValueError(f"invalid input: {getattr(exc, 'message', exc)}") from None
            host = spec.host(arguments)
            record["host"] = host
            try:
                call_timeout = spec.timeout(arguments) if spec.timeout else lock_timeout
                with locks.hold(host, record["card"] or "agr-mcp", call_timeout) as lock:
                    record["lock"] = str(lock) if lock else None
                    out = await anyio.to_thread.run_sync(spec.handler, arguments)
            except locks.LockBusy as exc:
                record["status"] = "busy"
                record["lock"] = str(locks.lock_path(host))
                raise ValueError(str(exc)) from None
            if isinstance(out, Outcome):
                result, meta = out.result, dict(out.meta)
            else:
                result = out
            env_out = envelope.build(name, result, schema=spec.schema, meta=meta)
            jsonschema.validate(env_out, envelope_schema(spec.result, spec.schema == 1))
            record["status"] = "ok"
            record["preview_id"] = env_out.get("preview_id") or record["preview_id"]
            if spec.schema == 1:
                return env_out
            return [types.TextContent(type="text", text=env_out["summary"])], env_out
        except Exception as exc:
            record["status"] = record["status"] or "error"
            record["error"] = f"{type(exc).__name__}: {exc}"[:2000]
            err = envelope.error_envelope(name, exc)
            record["error_code"] = err["error_code"]
            meta = dict(meta, **{k: v for k, v in (getattr(exc, "payload", None) or {}).items()
                                 if k in ("journaled", "journaled_rows")})
            env_out = None
            return types.CallToolResult(content=[types.TextContent(type="text", text=str(exc))],
                                        structuredContent=err, isError=True)
        finally:
            duration = time.perf_counter() - started
            record["duration_ms"] = round(duration * 1000, 1)
            audit.write(record)
            _journal(spec, name, arguments, meta, env_out, record, duration)

    return server


def _journal(spec, name, arguments, meta, env_out, record, duration) -> None:
    """One journal line per call unless the runtime already journaled every row this call ran."""
    rows = list(meta.get("journaled_rows") or ())
    if meta.get("journaled") and (name != "agr_check_run" or set(rows) >= set(arguments.get("check_ids") or ())):
        return
    tool = (spec.row if spec is not None and spec.row else None) or meta.get("row") or name
    if env_out is not None:
        status, counts = env_out["status"], env_out["counts"]
    else:
        status, counts = "error", {}
    extra = {"mcp_tool": name, "host": record.get("host"), "instance": current_instance(),
             "client": record.get("client"), "card": record.get("card"), "server_version": SERVER_VERSION,
             "error_code": record.get("error_code"), "preview_id": record.get("preview_id")}
    if name == "agr_check_run":
        extra["rows"] = [r for r in (arguments.get("check_ids") or ()) if r not in rows]
    if record.get("target"):
        extra["target"] = str(record["target"])
    journal.write(tool, _journal_mode(spec, meta, arguments), status, counts,
                  record.get("preview_id"), duration, _journal_doc(meta, arguments), extra)


async def _serve() -> None:
    from mcp.server.stdio import stdio_server
    server = build_server()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:
    anyio.run(_serve)


if __name__ == "__main__":
    main()
