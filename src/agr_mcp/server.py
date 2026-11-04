"""new-case: agr-mcp stdio MCP server, phase 0 (read-only), one process per client (plan section 3).

Run: `uv run agr-mcp` (console script) or `python -m agr_mcp.server`. Every tools/call - success, error,
refusal, unknown tool - writes exactly one audit line. Input is validated here (not by the SDK) so that
rejected calls are audited too. A held host lock refuses the call at once.
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

from . import SERVER_NAME, SERVER_VERSION, TOOL_SCHEMA_VERSION, audit, locks, tools

INSTRUCTIONS = (f"AGR checkers over MCP, phase 0, read-only. tool_schema_version={TOOL_SCHEMA_VERSION}; "
                f"protocol {LATEST_PROTOCOL_VERSION} (mcp SDK 1.30.0). Max tools need AGR_MCP_MAX_PID.")


def unsafe_enabled(env=None) -> bool:
    return (os.environ if env is None else env).get("AGR_MCP_UNSAFE") == "1"


def envelope_schema(result: dict) -> dict:
    return {"type": "object", "required": ["tool_schema_version", "server_version", "result"],
            "properties": {"tool_schema_version": {"const": TOOL_SCHEMA_VERSION},
                           "server_version": {"type": "string"}, "result": result}}


def _client_name(server: Server) -> str | None:
    try:
        info = server.request_context.session.client_params.clientInfo
        return info.name if info else None
    except (LookupError, AttributeError):
        return None


def build_server(env=None, max_transport=None, lock_timeout: float = 900) -> Server:
    catalog = tools.catalog(unsafe=unsafe_enabled(env), max_transport=max_transport)
    server = Server(SERVER_NAME, version=SERVER_VERSION, instructions=INSTRUCTIONS)

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [types.Tool(name=s.name, description=s.description, inputSchema=s.input,
                           outputSchema=envelope_schema(s.result),
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
                  "args_sha256": audit.args_sha256(arguments), "status": None, "error": None}
        if name == "agr_exec_unsafe":
            code = str(arguments.get("code", "")).encode("utf-8")
            record.update(unsafe=True, code_sha256=hashlib.sha256(code).hexdigest(), code_bytes=len(code))
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
                with locks.hold(host, record["card"] or "agr-mcp", lock_timeout) as lock:
                    record["lock"] = str(lock) if lock else None
                    result = await anyio.to_thread.run_sync(spec.handler, arguments)
            except locks.LockBusy as exc:
                record["status"] = "busy"
                record["lock"] = str(locks.lock_path(host))
                raise ValueError(str(exc)) from None
            out = {"tool_schema_version": TOOL_SCHEMA_VERSION, "server_version": SERVER_VERSION, "result": result}
            jsonschema.validate(out, envelope_schema(spec.result))
            record["status"] = "ok"
            return out
        except Exception as exc:
            record["status"] = record["status"] or "error"
            record["error"] = f"{type(exc).__name__}: {exc}"[:2000]
            raise
        finally:
            record["duration_ms"] = round((time.perf_counter() - started) * 1000, 1)
            audit.write(record)

    return server


async def _serve() -> None:
    from mcp.server.stdio import stdio_server
    server = build_server()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:
    anyio.run(_serve)


if __name__ == "__main__":
    main()
