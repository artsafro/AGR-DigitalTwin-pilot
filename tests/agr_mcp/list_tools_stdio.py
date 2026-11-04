"""new-case: list the agr-mcp tools through a real stdio MCP client against a FRESH server process.

  uv run python tests/agr_mcp/list_tools_stdio.py [--unsafe]
Spawns the installed console script (`.venv/Scripts/agr-mcp[.exe]`), runs initialize + tools/list over stdio
and prints the transcript as JSON (serverInfo, protocolVersion, tool names, annotations).
"""
import json
import os
import shutil
import sys
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[2]


def command() -> str:
    exe = shutil.which("agr-mcp", path=str(ROOT / ".venv" / ("Scripts" if os.name == "nt" else "bin")))
    if not exe:
        raise SystemExit("agr-mcp console script not installed: run `uv sync`")
    return exe


async def transcript(unsafe: bool = False, audit: str | None = None, via_uv: bool = False) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "AGR_MCP_UNSAFE"}
    if unsafe:
        env["AGR_MCP_UNSAFE"] = "1"
    if audit:
        env["AGR_MCP_AUDIT"] = audit
    if via_uv:  # the exact registration form of the README: uv run --directory <clone> agr-mcp
        params = StdioServerParameters(command="uv", args=["run", "--directory", str(ROOT), "agr-mcp"], env=env)
    else:
        params = StdioServerParameters(command=command(), args=[], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            tools = (await session.list_tools()).tools
    return {"command": [params.command, *params.args], "unsafe_env": unsafe, "protocolVersion": init.protocolVersion,
            "serverInfo": init.serverInfo.model_dump(exclude_none=True), "instructions": init.instructions,
            "tools": [{"name": t.name, "readOnlyHint": t.annotations.readOnlyHint,
                       "destructiveHint": t.annotations.destructiveHint,
                       "input": sorted(t.inputSchema.get("properties", {}))} for t in tools]}


if __name__ == "__main__":
    print(json.dumps(anyio.run(transcript, "--unsafe" in sys.argv, None, "--uv" in sys.argv), indent=1))
