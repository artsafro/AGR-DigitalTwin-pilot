"""new-case: offline Max Code Mode prototype over the existing guarded MCP client.

Scripts are bounded JSON operation lists, NOT Python/JS/MAXScript. Not registered
in production. Caller owns the backend session, pinned Max identity and DCC lock.
Request consumption and the unresolved-write latch are process-local: this is not
crash-safe exactly-once execution. After restart reconcile before enabling writes.
"""
from __future__ import annotations

import copy
from contextlib import nullcontext

import anyio
import jsonschema
from mcp import types
from mcp.server.lowlevel import Server

from . import tools
from .envelope import canonical, sha256

ID = {"type": "string", "pattern": "^[A-Za-z0-9_-]{1,64}$"}
PROGRAM = {"type": "object", "additionalProperties": False,
           "required": ["request_id", "steps"], "properties": {
               "request_id": ID, "allow_write": {"type": "boolean", "default": False},
               "steps": {"type": "array", "minItems": 1, "maxItems": 32, "items": {
                   "type": "object", "additionalProperties": False,
                   "required": ["id", "tool", "arguments"], "properties": {
                       "id": ID, "tool": {"type": "string"}, "arguments": {"type": "object"}}}}}}
ALLOWED = ("agr_check_run", "agr_op_preview", "agr_op_apply")


class CodeMode:
    """Sequential stop-on-non-success frontend; execution stays in guarded tools/call."""
    def __init__(self, client):
        self.client = client
        catalog = tools.catalog(unsafe=False)
        self._specs = {name: catalog[name] for name in ALLOWED}
        self._consumed = set()
        self._unresolved_write = False
        self._write_lock = anyio.Lock()

    def search(self, query: str) -> list[dict]:
        if not isinstance(query, str) or not query.strip() or len(query) > 200:
            raise ValueError("query must be 1..200 nonblank characters")
        return [{"name": s.name, "description": s.description, "inputSchema": copy.deepcopy(s.input),
                 "read_only": s.name != "agr_op_apply"}
                for s in self._specs.values() if query.lower() in (s.name + " " + s.description).lower()]

    async def execute(self, request: dict) -> dict:
        # Snapshot before any await: caller mutation cannot change prevalidated operations.
        try:
            request = copy.deepcopy(request)
            canonical(request)
            jsonschema.validate(request, PROGRAM)
            ids = set()
            for step in request["steps"]:
                if step["id"] in ids:
                    raise ValueError("duplicate step id: " + step["id"])
                ids.add(step["id"])
                if step["tool"] not in self._specs:
                    raise ValueError("unsupported operation: " + step["tool"])
                jsonschema.validate(step["arguments"], self._specs[step["tool"]].input)
            writes = any(s["tool"] == "agr_op_apply" for s in request["steps"])
            if writes and request.get("allow_write") is not True:
                raise ValueError("write requires explicit allow_write=true; backend guards still apply")
            if writes and self._unresolved_write:
                raise ValueError("reconcile scene/model before further writes; new session only after readback")
            rid = request["request_id"]
            if rid in self._consumed:
                raise ValueError("request_id already consumed: " + rid + "; reconcile, do not retry")
        except (jsonschema.ValidationError, TypeError, ValueError) as exc:
            raise ValueError(str(exc)) from None
        self._consumed.add(rid)
        receipts, stopped, committed = [], False, False
        for step in request["steps"]:
            receipt = {"request_id": rid, "id": step["id"], "tool": step["tool"],
                       "args_sha256": sha256(step["arguments"]), "status": "skipped"}
            receipts.append(receipt)
            if stopped:
                receipt["reason"] = "earlier operation did not complete successfully"
                continue
            write = step["tool"] == "agr_op_apply"
            # Serialize write admission, dispatch and latch resolution together. Reads
            # may overlap, but cannot clear another program's uncertain write.
            async with self._write_lock if write else nullcontext():
                if write and self._unresolved_write:
                    receipt["reason"] = "reconcile scene/model before further writes"
                    stopped = True
                    continue
                if write:
                    self._unresolved_write = True
                try:
                    response = await self.client.call_tool(step["tool"], step["arguments"])
                    body = response.structuredContent
                    canonical(body)
                    success = not response.isError and isinstance(body, dict) and body.get("status") in ("ok", "pass")
                    receipt["result"] = copy.deepcopy(body)
                    if success:
                        receipt["status"] = "committed_unverified" if write else "ok"
                        committed |= write
                        if write:
                            self._unresolved_write = False
                    else:
                        receipt["status"] = "unknown" if write else "failed"
                        stopped = True
                except Exception as exc:
                    receipt.update(status="unknown", error=f"{type(exc).__name__}: {exc}")
                    stopped = True
        status = (next((r["status"] for r in receipts if r["status"] in ("unknown", "failed")), "failed") if stopped
                  else "committed_unverified" if committed else "ok")
        return {"request_id": rid, "program_sha256": sha256(request), "status": status,
                "receipts": receipts, "next_actions": [
                    "reconcile ids/counts/readback; never blindly retry a write" if stopped
                    else "verify independently after commit" if committed else "read operations completed"]}


def build_server(client) -> Server:
    """Two-tool prototype facade; backend must be a connected AGR server session."""
    mode = CodeMode(client)
    server = Server("agr-max-code-mode-prototype", version="0.1.0")

    @server.list_tools()
    async def list_tools():
        return [types.Tool(name="agr_code_search", description="Search guarded Max operations and schemas",
                           inputSchema={"type": "object", "required": ["query"], "additionalProperties": False,
                                        "properties": {"query": {"type": "string", "minLength": 1, "maxLength": 200}}}),
                types.Tool(name="agr_code_run", description="Run 1..32 JSON steps; read-only default; no arbitrary code",
                           inputSchema=copy.deepcopy(PROGRAM))]

    @server.call_tool()
    async def call_tool(name, arguments):
        if name == "agr_code_search":
            result = {"operations": mode.search(arguments["query"])}
        elif name == "agr_code_run":
            result = await mode.execute(arguments)
        else:
            raise ValueError("unknown tool: " + name)
        return types.CallToolResult(content=[types.TextContent(type="text", text=canonical(result))],
                                    structuredContent=result,
                                    isError=result.get("status") in ("unknown", "failed"))

    return server
