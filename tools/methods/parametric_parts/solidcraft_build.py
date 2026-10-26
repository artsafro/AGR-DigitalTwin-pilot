"""Build the two parametric parts through SolidCraft's MCP stdio server.

new-case: SolidCraft MCP variant for repeatable parts (#713).

SolidCraft 0.23.1 exports OBJ, STL, STEP and 3MF, not FBX. The OBJ triangles are written
into an ASCII FBX unchanged, with millimetre coordinates divided by 1000. A bench is a
YZ sketch extruded by the length parameter when that batch succeeds, otherwise solid.box
at the spec extents. The aerator is solid.box at the spec extents (390 x 390 x 324 mm).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "methods" / "parametric_parts"))
import mesh_recipe as recipe  # noqa: E402

CLI = Path(r"C:\x\methods\solidcraft\app\solidcraft-0.23.1-windows-x64-portable\solidcraft-cli.exe")
OUT = Path(r"C:\x\methods\parametric-parts")


class McpError(RuntimeError):
    pass


class Mcp:
    def __init__(self, exe: Path, allow: Path):
        self.proc = subprocess.Popen(
            [str(exe), "mcp", "--allow-path", str(allow)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self._n = 0
        self._call("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "agr-parametric-parts", "version": "1"},
        })
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def close(self):
        if self.proc.stdin:
            self.proc.stdin.close()
        try:
            self.proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.proc.kill()

    def _send(self, payload: dict):
        if self.proc.stdin is None:
            raise McpError("mcp stdin is closed")
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()

    def _call(self, method: str, params: dict):
        self._n += 1
        self._send({"jsonrpc": "2.0", "id": self._n, "method": method, "params": params})
        if self.proc.stdout is None:
            raise McpError("mcp stdout is closed")
        line = self.proc.stdout.readline()
        if not line:
            err = ""
            if self.proc.stderr:
                err = self.proc.stderr.read()[-2000:]
            raise McpError("mcp closed: " + err)
        reply = json.loads(line)
        if "error" in reply:
            raise McpError(json.dumps(reply["error"])[:2000])
        return reply.get("result")

    def tool(self, name: str, arguments: dict | None = None):
        result = self._call("tools/call", {"name": name, "arguments": arguments or {}})
        if not isinstance(result, dict):
            raise McpError("mcp tool reply is not an object")
        if result.get("isError"):
            raise McpError(_text(result)[:2000])
        body = _json_text(result)
        if isinstance(body, dict) and body.get("ok") is False:
            raise McpError(json.dumps(body)[:2000])
        return body


def _text(result: dict) -> str:
    chunks = []
    for block in result.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text":
            chunks.append(block.get("text") or "")
    return "\n".join(chunks)


def _json_text(result: dict):
    raw = _text(result).strip()
    if not raw:
        return {}
    # The tool reply's first text block is the JSON payload; a note may follow.
    first = raw.split("\nNote:", 1)[0].strip()
    try:
        return json.loads(first)
    except json.JSONDecodeError:
        return {"raw": first[:1500]}


def _same(a: Path, b: Path) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _obj_to_fbx(obj_path: Path, fbx_path: Path):
    if _same(obj_path, fbx_path):
        raise McpError("refusing to write FBX onto the OBJ")
    verts = []
    tris = []
    for line in obj_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("v "):
            parts = line.split()
            verts.append((float(parts[1]) / 1000.0, float(parts[2]) / 1000.0, float(parts[3]) / 1000.0))
        elif line.startswith("f "):
            ids = [int(tok.split("/")[0]) - 1 for tok in line.split()[1:]]
            for k in range(1, len(ids) - 1):
                tris.append((ids[0], ids[k], ids[k + 1]))
    if not tris:
        raise McpError("SolidCraft OBJ has no faces")
    recipe.write_ascii_fbx(fbx_path, verts, tris)


def _export(mcp: Mcp, obj_path: Path, fbx_path: Path):
    if obj_path.exists():
        raise McpError("refusing to overwrite " + str(obj_path))
    mcp.tool("export", {"path": str(obj_path), "format": "obj"})
    _obj_to_fbx(obj_path, fbx_path)


def _bench_sketch(mcp: Mcp, length_mm: float):
    profile = recipe.bench_profile(recipe.BENCH_WIDTH_M, recipe.BENCH_HEIGHT_M)
    points = [[y * 1000.0, z * 1000.0] for y, z in profile]
    mcp.tool("new_design", {"name": "bench"})
    started = time.perf_counter()
    body = mcp.tool("batch", {
        "verbose": False,
        "commands": [
            {"command": "sketch.create", "params": {"plane": "YZ"}},
            {"command": "sketch.line", "params": {"points": points, "closed": True}},
            {"command": "sketch.finish"},
            {"command": "solid.extrude", "params": {"distance": length_mm}},
        ],
    })
    return time.perf_counter() - started, body, "sketch.line + solid.extrude"


def _box(mcp: Mcp, name: str, length: float, width: float, height: float):
    mcp.tool("new_design", {"name": name})
    started = time.perf_counter()
    body = mcp.tool("execute", {
        "command": "solid.box",
        "params": {"length": length, "width": width, "height": height, "name": name},
        "verbose": False,
    })
    return time.perf_counter() - started, body, "solid.box"


def _edit_length(mcp: Mcp, length_mm: float):
    started = time.perf_counter()
    body = mcp.tool("execute", {
        "command": "timeline.edit",
        "params": {"feature": "Extrude1", "set": {"extent": {"distance": length_mm}}},
        "verbose": False,
    })
    return time.perf_counter() - started, body


def main() -> int:
    if not CLI.is_file():
        print("not measured: solidcraft-cli missing at " + str(CLI))
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    version = subprocess.run([str(CLI), "--version"], capture_output=True, text=True, check=False)
    ver = (version.stdout or version.stderr or "").strip()
    rows = []
    try:
        mcp = Mcp(CLI, OUT)
    except (McpError, OSError, json.JSONDecodeError) as exc:
        print("not measured: SolidCraft MCP failed to start: " + str(exc))
        return 1
    try:
        feature = "solid.box"
        try:
            build_s, reply, feature = _bench_sketch(mcp, 1800.0)
        except (McpError, OSError, json.JSONDecodeError) as exc:
            rows.append({"part": "bench", "sketch_error": str(exc)[:800]})
            build_s, reply, feature = _box(mcp, "bench", 1800.0, 500.0, 720.0)
        _export(mcp, OUT / "bench-solidcraft.obj", OUT / "bench-solidcraft.fbx")
        rows.append({
            "part": "bench", "tool": "solidcraft", "kind": "build", "build_s": build_s,
            "fbx": str(OUT / "bench-solidcraft.fbx"), "version": ver, "feature": feature,
        })
        try:
            param_s, edit = _edit_length(mcp, 1900.0)
            how = "timeline.edit length"
        except (McpError, OSError, json.JSONDecodeError) as exc:
            param_s, edit, how = _box(mcp, "bench-param", 1900.0, 500.0, 720.0)
            how = "solid.box rebuild after timeline.edit failed: " + str(exc)[:300]
        _export(mcp, OUT / "bench-solidcraft-param.obj", OUT / "bench-solidcraft-param.fbx")
        rows.append({
            "part": "bench", "tool": "solidcraft", "kind": "param_change", "build_s": param_s,
            "fbx": str(OUT / "bench-solidcraft-param.fbx"), "version": ver, "feature": how,
        })
        build_s, reply, feature = _box(mcp, "aerator", 390.0, 390.0, 324.0)
        _export(mcp, OUT / "aerator-solidcraft.obj", OUT / "aerator-solidcraft.fbx")
        rows.append({
            "part": "aerator", "tool": "solidcraft", "kind": "build", "build_s": build_s,
            "fbx": str(OUT / "aerator-solidcraft.fbx"), "version": ver, "feature": feature,
        })
        try:
            param_s, edit = mcp_edit_height(mcp, 424.0)
            how = "timeline.edit height"
        except (McpError, OSError, json.JSONDecodeError) as exc:
            param_s, edit, feature = _box(mcp, "aerator-param", 390.0, 390.0, 424.0)
            how = "solid.box rebuild: " + str(exc)[:240]
        _export(mcp, OUT / "aerator-solidcraft-param.obj", OUT / "aerator-solidcraft-param.fbx")
        rows.append({
            "part": "aerator", "tool": "solidcraft", "kind": "param_change", "build_s": param_s,
            "fbx": str(OUT / "aerator-solidcraft-param.fbx"), "version": ver, "feature": how,
        })
    except (McpError, OSError, json.JSONDecodeError) as exc:
        rows.append({"tool": "solidcraft", "status": "not measured: " + str(exc)[:800]})
    finally:
        mcp.close()
    report = OUT / "solidcraft-build.json"
    partial = Path(str(report) + ".partial")
    partial.write_text(json.dumps({"version": ver, "rows": rows}, indent=2), encoding="utf-8")
    os.replace(partial, report)
    print(json.dumps(rows, indent=2))
    return 0 if any(row.get("fbx") for row in rows) else 1


def mcp_edit_height(mcp: Mcp, height_mm: float):
    started = time.perf_counter()
    body = mcp.tool("execute", {
        "command": "timeline.edit",
        "params": {"feature": "Box1", "set": {"height": height_mm}},
        "verbose": False,
    })
    return time.perf_counter() - started, body


if __name__ == "__main__":
    sys.exit(main())
