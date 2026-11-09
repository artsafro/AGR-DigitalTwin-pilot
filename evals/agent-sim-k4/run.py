"""new-case: scenario eval «agent simulation» - acceptance К4 of #1024 (branch U), through the real MCP protocol.

A scripted agent talks to the agr-mcp daemon over Streamable HTTP exactly like the dock's CLI would, and a scripted
human presses «Применить» (`press(preview_id)`: in the dock this is agr_gate.confirm inside Max + POST /agr/apply).
Checks (each a row of report.json, pass/fail; the eval passes when every row passes):

  profile_no_exec      tools/list of the bridge has the agr_agent_* tools and NO agr_exec_unsafe (even with
                       AGR_MCP_UNSAFE=1 in the daemon's environment); calling it is refused
  context              agr_agent_context(request) returns the request and the target objects as ObjRefs
  needs_human          apply before the button answers needs_human; nothing changed
  mark_opening         preview -> press -> applied: OPEN_<nnn> in AGENT_<req> with role opening, one undo record
  keep_copy            keep(body) -> press -> applied: a copy in AGENT_<req> (D115 invariants passed on the server)
  set_role_in_layer    set_role on the agent's own copy -> applied
  outside_rollback     set_role on an object OUTSIDE the layer -> preview warns; press -> rolled_back, rollback proved,
                       question written to questions.md
  invariant_refusal    primitive_box on a non-box part -> rolled_back at the preview (silhouette), no preview_id
  stale_after_change   a preview made before another apply is stale (scene fingerprint) and is refused

Used by tests/max_tools/test_agr_tools_agent_bridge.py (fake Max) and by the native job (real 3ds Max 2024, the human
press goes through files: `--press-dir`). Run standalone:
    python evals/agent-sim-k4/run.py --url http://127.0.0.1:<port>/mcp --token <t> --request <request.json>
           --body <handle> --odd <handle> --outside <handle> --press-dir <dir> --out <report.json>
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path


class Agent:
    """A minimal MCP client over Streamable HTTP with the daemon's bearer token."""

    def __init__(self, url: str, token: str):
        self.url, self.token = url, token
        self.calls = []

    async def __aenter__(self):
        import httpx
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client
        self._http = httpx.AsyncClient(headers={"Authorization": "Bearer " + self.token},
                                       timeout=httpx.Timeout(30, read=600))
        self._cm = streamable_http_client(self.url, http_client=self._http)
        read, write, _ = await self._cm.__aenter__()
        self._session_cm = ClientSession(read, write)
        self.session = await self._session_cm.__aenter__()
        await self.session.initialize()
        return self

    async def __aexit__(self, *exc):
        await self._session_cm.__aexit__(*exc)
        await self._cm.__aexit__(*exc)
        await self._http.aclose()

    async def tools(self):
        return [t.name for t in (await self.session.list_tools()).tools]

    async def call(self, name, args):
        t0 = time.time()
        r = await self.session.call_tool(name, args)
        out = r.structuredContent or {}
        self.calls.append({"tool": name, "status": out.get("status"), "error_code": out.get("error_code"),
                           "is_error": r.isError, "s": round(time.time() - t0, 3)})
        return r.isError, out


def file_press(press_dir: str, timeout_s: float = 120):
    """The human of the native run: ask the Max harness to confirm a preview id, wait for its ack."""
    def press(pid: str):
        d = Path(press_dir)
        d.mkdir(parents=True, exist_ok=True)
        (d / (pid + ".press")).write_text("press", encoding="utf-8")
        end = time.time() + timeout_s
        while time.time() < end:
            if (d / (pid + ".ack")).is_file():
                return True
            time.sleep(0.1)
        raise TimeoutError("the Max harness did not confirm " + pid)
    return press


async def scenario(url, token, request, refs, press, unsafe_env=True):
    """refs: {'body': ObjRef, 'odd': ObjRef, 'outside': ObjRef}. Returns the report."""
    rows = []

    def row(name, ok, detail=""):
        rows.append({"check": name, "passed": bool(ok), "detail": str(detail)[:500]})

    async with Agent(url, token) as a:
        names = await a.tools()
        err, out = await a.call("agr_exec_unsafe", {"code": "1+1"})
        row("profile_no_exec", "agr_exec_unsafe" not in names and {"agr_agent_context", "agr_agent_op_preview",
                                                                   "agr_agent_op_apply"} <= set(names)
            and err and out.get("error_code") == "unknown_tool", "tools {} exec {}".format(len(names),
                                                                                          out.get("error_code")))
        err, out = await a.call("agr_agent_context", {"request": request})
        ctx = (out.get("result") or {}).get("context") or {}
        handles = {o["ref"]["handle"] for o in ctx.get("objects") or ()}
        row("context", not err and ctx.get("request", {}).get("result_layer", "").startswith("AGENT_")
            and refs["body"]["handle"] in handles, "objects {}".format(len(handles)))

        err, out = await a.call("agr_agent_op_preview", {
            "request": request, "op": "mark_opening",
            "params": {"pos": [1.0, 0.0, 1.5], "w": 1.2, "h": 1.5, "sill": 0.9, "depth": 0.25,
                       "wall": refs["body"]["name"], "corner": False, "window_type": "WT-01"}})
        pid = out.get("preview_id")
        err2, out2 = await a.call("agr_agent_op_apply", {"preview_id": pid or "0" * 64})
        row("needs_human", pid and not err2 and out2.get("status") == "needs_human", out2.get("status"))
        press(pid)
        err3, out3 = await a.call("agr_agent_op_apply", {"preview_id": pid})
        res3 = out3.get("result") or {}
        row("mark_opening", not err3 and res3.get("status") == "applied" and res3.get("undo_label")
            and res3.get("created", [{}])[0].get("name", "").startswith("OPEN_"), json.dumps(res3)[:300])

        err, out = await a.call("agr_agent_op_preview", {"request": request, "op": "keep", "ref": refs["body"],
                                                         "params": {"role": "body"}})
        pid = out.get("preview_id")
        if pid:
            press(pid)
        err, out = await a.call("agr_agent_op_apply", {"preview_id": pid or "0" * 64})
        res = out.get("result") or {}
        copy_handle = (res.get("created") or [{}])[0].get("handle")
        row("keep_copy", not err and res.get("status") == "applied" and copy_handle, json.dumps(res)[:300])

        doc = refs["body"]["doc"]
        copy_ref = {"host": "max", "doc": doc, "handle": int(copy_handle or 1), "name": refs["body"]["name"]}
        err, out = await a.call("agr_agent_op_preview", {"request": request, "op": "set_role", "ref": copy_ref,
                                                         "params": {"role": "body"}})
        pid = out.get("preview_id")
        if pid:
            press(pid)
        err, out = await a.call("agr_agent_op_apply", {"preview_id": pid or "0" * 64})
        row("set_role_in_layer", not err and (out.get("result") or {}).get("status") == "applied", out.get("status"))

        err, out = await a.call("agr_agent_op_preview", {"request": request, "op": "set_role",
                                                         "ref": refs["outside"], "params": {"role": "glass"}})
        warned = any("outside_layer" in w for w in (out.get("result") or {}).get("warnings") or ())
        pid = out.get("preview_id")
        if pid:
            press(pid)
        err, out = await a.call("agr_agent_op_apply", {"preview_id": pid or "0" * 64})
        res = out.get("result") or {}
        q = Path(request).parent / "questions.md"
        row("outside_rollback", warned and res.get("status") == "rolled_back" and res.get("rollback_proved") is True
            and q.is_file() and "outside_changed" in q.read_text(encoding="utf-8"),
            json.dumps({k: res.get(k) for k in ("status", "rollback_proved", "violations")})[:400])

        err, out = await a.call("agr_agent_op_preview", {"request": request, "op": "primitive_box", "ref": refs["odd"]})
        row("invariant_refusal", not err and out.get("status") == "rolled_back" and not out.get("preview_id")
            and (out.get("result") or {}).get("question"), (out.get("result") or {}).get("question"))

        err, out = await a.call("agr_agent_op_preview", {"request": request, "op": "set_role", "ref": copy_ref,
                                                         "params": {"role": "decor"}})
        stale = out.get("preview_id")
        err, out = await a.call("agr_agent_op_preview", {"request": request, "op": "mark_opening", "params": {
            "pos": [2.0, 0.0, 1.5], "w": 1.0, "h": 1.0, "sill": 0.9, "depth": 0.2, "wall": "x", "corner": False}})
        pid = out.get("preview_id")
        if pid:
            press(pid)
        await a.call("agr_agent_op_apply", {"preview_id": pid or "0" * 64})
        if stale:
            press(stale)
        err, out = await a.call("agr_agent_op_apply", {"preview_id": stale or "0" * 64})
        row("stale_after_change", err and out.get("error_code") == "stale_preview", out.get("error_code"))
        calls = list(a.calls)
    return {"eval": "agent-sim-k4", "passed": all(r["passed"] for r in rows), "rows": rows, "calls": calls,
            "latency_s": {"max": max(c["s"] for c in calls), "median": sorted(c["s"] for c in calls)[len(calls) // 2]}}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--token", required=True)
    ap.add_argument("--request", required=True)
    ap.add_argument("--refs", required=True, help="JSON file {body, odd, outside: ObjRef}")
    ap.add_argument("--press-dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    refs = json.loads(Path(a.refs).read_text(encoding="utf-8"))
    rep = asyncio.run(scenario(a.url, a.token, a.request, refs, file_press(a.press_dir)))
    Path(a.out).write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"passed": rep["passed"], "rows": [(r["check"], r["passed"]) for r in rep["rows"]]}))
    return 0 if rep["passed"] else 1


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    sys.exit(main())
