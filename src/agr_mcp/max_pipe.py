"""new-case: agr-mcp client side of the 3dsmax-mcp named pipe (same route as max_exec.py).

The target Max is never guessed: AGR_MCP_MAX_PID (or the 3dsmax-mcp variables MCP_MAX_PID / MCP_MAX_PIPE)
must pin it, otherwise the call fails. Phase 0 must not bind to whichever user scene happens to be newest.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

MCP_DIR = os.environ.get("AGR_MAX_MCP_DIR", r"C:\Users\artsafro\tools\3dsmax-mcp")
BRIDGE_DIR = Path(__file__).resolve().parent / "max_side"  # only max_bridge.py goes onto Max's sys.path

CHILD = r"""
import json, sys
from maxmcp.max_client import MaxClient
req = json.loads(sys.stdin.read())
c = MaxClient(timeout=req["timeout"])
try:
    r = c.send_command(req["code"], cmd_type="maxscript", timeout=req["timeout"])
    print(json.dumps({"status": "success", "result": r}, default=str))
except ConnectionError as e:
    print(json.dumps({"status": "unreachable", "error": str(e)}))
except Exception as e:
    print(json.dumps({"status": "error", "error": f"{type(e).__name__}: {e}"}))
"""


MS_ERROR = "__MCP_MS_ERR__"


class MaxError(RuntimeError):
    """Max was unreachable, the script failed, or the bridge reported an error."""


def bridge_script(tool: str, tools_root: str, args: dict) -> str:
    """One MAXScript expression; only hex digits and the fixed bridge folder are interpolated."""
    root_hex = tools_root.encode("utf-8").hex()
    args_hex = json.dumps(args, sort_keys=True, allow_nan=False).encode("utf-8").hex()
    if not tool.replace("_", "").isalnum():
        raise ValueError(f"bad tool name {tool!r}")
    folder = str(BRIDGE_DIR).replace("\\", "/")
    if '"' in folder:
        raise ValueError("bridge folder contains a quote")
    return ("(\n"
            '  (python.import "sys").path.insert 0 @"' + folder + '"\n'
            '  local il = python.import "importlib"\n'
            '  local b = il.reload (il.import_module "max_bridge")\n'
            '  b.call "' + tool + '" "' + root_hex + '" "' + args_hex + '"\n'
            ")")


def pinned_env(env=None) -> dict:
    env = dict(os.environ if env is None else env)
    env = {k: v for k, v in env.items() if k not in ("VIRTUAL_ENV", "PYTHONPATH")}
    if env.get("AGR_MCP_MAX_PID"):
        env["MCP_MAX_PID"] = env["AGR_MCP_MAX_PID"]
    if not env.get("MCP_MAX_PID") and not env.get("MCP_MAX_PIPE"):
        raise MaxError("no Max target pinned: set AGR_MCP_MAX_PID (pid of an open 3ds Max with the "
                       "3dsmax-mcp pipe); agr-mcp never picks a user scene by itself")
    return env


def pipe_transport(code: str, timeout: float) -> str:
    """Send MAXScript over the 3dsmax-mcp pipe; return the value of the last expression as text."""
    try:
        r = subprocess.run(["uv", "run", "--directory", MCP_DIR, "python", "-c", CHILD],
                           input=json.dumps({"code": code, "timeout": timeout}), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout + 60, env=pinned_env())
    except subprocess.TimeoutExpired:
        raise MaxError("timeout: Max may still be running the call; do not resend") from None
    line = (r.stdout.strip().splitlines() or [""])[-1]
    try:
        out = json.loads(line)
    except ValueError:
        raise MaxError("pipe client failed: " + (r.stderr or r.stdout).strip()[-1500:]) from None
    if out.get("status") != "success":
        raise MaxError(f"{out.get('status')}: {out.get('error')}")
    resp = out.get("result")
    if not isinstance(resp, dict) or not resp.get("success"):
        raise MaxError("Max error: " + str(resp.get("error") if isinstance(resp, dict) else resp)[:1500])
    return str(resp.get("result"))


def decode_value(value) -> str:
    """The pipe returns the MAXScript value as text; a string value may come back quoted once."""
    if not isinstance(value, str):
        raise MaxError(f"unexpected pipe value type {type(value).__name__}")
    text = value.strip()
    if text.startswith('"'):
        text = json.loads(text)
    if text.startswith(MS_ERROR):  # 3dsmax-mcp reports a MAXScript exception as success + this marker
        raise MaxError("MAXScript error: " + text[len(MS_ERROR):].lstrip(":").strip()[:1500])
    return text


def call_bridge(tool: str, args: dict, timeout: float, transport=None, tools_root: str | None = None) -> dict:
    root = os.environ.get("AGR_TOOLS_ROOT", "") if tools_root is None else tools_root
    raw = (transport or pipe_transport)(bridge_script(tool, root, args), timeout)
    try:
        payload = json.loads(decode_value(raw))
    except ValueError:
        raise MaxError("bridge returned non-JSON: " + str(raw)[:500]) from None
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise MaxError(str(payload.get("error") if isinstance(payload, dict) else payload))
    return payload
