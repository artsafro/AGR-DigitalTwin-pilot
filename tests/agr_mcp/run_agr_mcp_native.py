"""new-case: agr-mcp phase-0 native exit test for the three Max-backed tools (plan section 5).

Runs on the host, NOT inside Max. Needs an EMPTY interactive 3ds Max 2024/2026 with the 3dsmax-mcp pipe,
pinned by pid; it refuses any Max that has a document or objects (never a user scene).
  uv run python tools/max/build_agr_tools.py <new dir>/AGR-Tools-0.5.0.mzp
  AGR_MCP_MAX_PID=<pid> uv run python tests/agr_mcp/run_agr_mcp_native.py <mzp> <NEW evidence dir>
Installs the MZP into <evidence dir>/installed (not userScripts), builds a synthetic scene, then for each tool
compares the MCP result (in-process client -> server -> pipe -> max_bridge -> installed runtime.*) with the
direct call of the same installed runtime function over the same pipe. All data is synthetic. Every pipe call
holds the shared live lock (agr-3dsmax-live.lock). Writes native.json; exit 0 only when every row is equal.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

import anyio
from mcp.shared.memory import create_connected_server_and_client_session as connect

from agr_mcp import locks, max_pipe, server

MZP, OUT = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
OUT.mkdir(parents=True, exist_ok=False)
INSTALLED = OUT / "installed"
os.environ["AGR_TOOLS_ROOT"] = str(INSTALLED)
os.environ.setdefault("AGR_MCP_AUDIT", str(OUT / "audit.jsonl"))
CARD = os.environ.get("HERMES_KANBAN_TASK", "agr-mcp-native")


def ms(code, timeout=300.0):
    with locks.hold("max-live", CARD, timeout):
        return max_pipe.decode_value(max_pipe.pipe_transport(code, timeout))


def fwd(p):
    return str(p).replace("\\", "/")


state = ms('maxFileName + "|" + (objects.count as string) + "|" + ((maxVersion())[1] as string)')
name, count, version = state.split("|")
assert name == "" and count == "0", f"not an empty Max session: file={name!r} objects={count}"
assert version in ("26000", "28000"), version

SETUP = f'''(
(python.import "sys").modules.pop "runtime" undefined  -- a previous run's runtime in this disposable Max
units.SystemType = #meters
global AGRToolsInstallRoot = @"{fwd(INSTALLED)}/"
global AGRToolsStartupRoot = @"{fwd(OUT / 'startup')}/"
makeDir AGRToolsStartupRoot all:true
fileIn @"{fwd(MZP)}"
b = convertToPoly (box name:"AGR_MCP_Box" length:1 width:1 height:1 mapcoords:true)
polyop.setFaceMatID b #{{1,2}} 1001
m = mesh name:"AGR_MCP_Overlap" vertices:#([0,0,0],[1,0,0],[0,1,0],[0.0005,0,0]) faces:#([1,2,3],[4,2,3])
addModifier m (Uvwmap())
convertToPoly m
p = convertToPoly (plane name:"AGR_MCP_Plane" length:1 width:1 lengthsegs:1 widthsegs:1 mapcoords:true pos:[3,0,0])
mat = standardMaterial name:"M_AGR_MCP_Syn"
for n in #(b, m, p) do (n.material = mat; setUserProp n "AGR_TEXEL_PROFILE" "NPM"; setUserProp n "AGR_TEXEL_MAP" "M_AGR_MCP_Syn=2048")
clearSelection()
(b.inode.handle as string) + "," + (m.inode.handle as string) + "," + (p.inode.handle as string)
)'''
handles = [int(h) for h in ms(SETUP).split(",")]
print("SYNTHETIC_HANDLES", handles)
assert (INSTALLED / "runtime.py").is_file(), "MZP did not install runtime.py"


def direct(fn, hs):
    arr = "#(" + ",".join(f"(maxOps.getNodeByHandle {h})" for h in hs) + ")" if hs else "undefined"
    code = f'''(
clearSelection()
local sys = python.import "sys"
sys.path.insert 0 @"{fwd(INSTALLED)}"
local r = (python.import "runtime").{fn} {arr}
(python.import "json").dumps r
)'''
    try:
        return {"ok": json.loads(ms(code))}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def via_mcp(tool, hs):
    async def main():
        ms("clearSelection()")
        async with connect(server.build_server()) as client:
            res = await client.call_tool(tool, {"scene": "live", "handles": hs})
        return res
    res = anyio.run(main)
    if res.isError:
        return {"error": res.content[0].text}
    return {"ok": res.structuredContent["result"]}


rows = []
for tool, fn in (("agr_xview_check", "xview"), ("agr_matid_check", "matid"), ("agr_texel_readout", "texel_preview")):
    for hs in (handles, handles[:1], []):
        want, got = direct(fn, hs), via_mcp(tool, hs)
        equal = "ok" in want and want == got
        rows.append({"tool": tool, "handles": hs, "equal": equal, "direct": want, "mcp": got})
        print(f"ROW {tool} handles={hs} equal={equal} status={got.get('ok', {}).get('status', got.get('error'))}")

after = ms('maxFileName + "|" + (objects.count as string)')
report = {"max_version": version, "pid": os.environ.get("AGR_MCP_MAX_PID"),
          "mzp_sha256": hashlib.sha256(MZP.read_bytes()).hexdigest(), "handles": handles,
          "scene_after": after, "rows": rows, "synthetic": True}
(OUT / "native.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
print("NATIVE_EQUAL", sum(r["equal"] for r in rows), "/", len(rows), "scene_after", after)
sys.exit(0 if all(r["equal"] for r in rows) and after == "|3" else 1)
