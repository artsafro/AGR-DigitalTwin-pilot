"""Build the two parametric parts through SolidCraft's MCP stdio server.

new-case: SolidCraft MCP variant for repeatable parts (#713).

SolidCraft 0.23.1 exports OBJ, not FBX. OBJ positions are millimetres. Coincident OBJ
vertices (closer than 1e-9 m) are welded, then written as FBX 7400 binary in metres.
The bench is the catalogue silhouette extruded by the length parameter. The aerator is
three 16-gon extrudes (flange, pipe, cap) joined on the same axis, with pipe_length as
a parameter. There is no solid.box stand-in: an unsupported command is not_measured.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "methods" / "parametric_parts"))
import mesh_recipe as recipe  # noqa: E402

CLI = Path(r"C:\x\methods\solidcraft\app\solidcraft-0.23.1-windows-x64-portable\solidcraft-cli.exe")
OUT = Path(r"C:\x\methods\parametric-parts")
TIMING_BUILD = "build + OBJ export + OBJ to FBX"
TIMING_PARAM = "parameter change + OBJ export + OBJ to FBX"


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
    first = raw.split("\nNote:", 1)[0].strip()
    try:
        return json.loads(first)
    except json.JSONDecodeError:
        return {"raw": first[:1500]}


def _same_file(a: Path, b: Path) -> bool:
    try:
        if os.path.samefile(a, b):
            return True
    except OSError:
        pass
    try:
        left = os.stat(a)
        right = os.stat(b)
    except OSError:
        return False
    return left.st_ino != 0 and left.st_dev == right.st_dev and left.st_ino == right.st_ino


def _weld(verts, tris, tol_m=1e-9):
    """Collapse OBJ vertices that export on top of each other. Distinct corners stay."""
    buckets = {}
    remap = []
    unique = []
    for x, y, z in verts:
        key = (round(x / tol_m), round(y / tol_m), round(z / tol_m))
        if key not in buckets:
            buckets[key] = len(unique)
            unique.append((x, y, z))
        remap.append(buckets[key])
    welded = []
    for a, b, c in tris:
        aa, bb, cc = remap[a], remap[b], remap[c]
        if len({aa, bb, cc}) == 3:
            welded.append((aa, bb, cc))
    return unique, welded


def _obj_to_fbx(obj_path: Path, fbx_path: Path):
    if obj_path.exists() and fbx_path.exists() and (
        _same_file(obj_path, fbx_path)
        or os.path.normcase(os.path.abspath(obj_path)) == os.path.normcase(os.path.abspath(fbx_path))
    ):
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
    verts, tris = _weld(verts, tris)
    if not tris:
        raise McpError("SolidCraft OBJ has no faces after welding coincident vertices")
    recipe.write_ascii_fbx(fbx_path, verts, tris, protected=[obj_path])


def _export(mcp: Mcp, obj_path: Path, fbx_path: Path):
    if obj_path.exists() and fbx_path.exists() and _same_file(obj_path, fbx_path):
        raise McpError("refusing to write FBX onto the OBJ")
    fd, tmp_name = tempfile.mkstemp(prefix=obj_path.name + ".", suffix=".obj", dir=str(obj_path.parent))
    os.close(fd)
    os.remove(tmp_name)
    tmp = Path(tmp_name)
    try:
        mcp.tool("export", {"path": str(tmp), "format": "obj"})
        _obj_to_fbx(tmp, fbx_path)
        os.replace(tmp, obj_path)
    except Exception:
        if tmp.exists() and not (obj_path.exists() and _same_file(tmp, obj_path)):
            os.remove(tmp)
        raise


def _bench_commands(length_mm: float):
    profile = recipe.bench_profile(recipe.BENCH_WIDTH_M, recipe.BENCH_HEIGHT_M)
    points = [[y * 1000.0, z * 1000.0] for y, z in profile]
    return [
        {"command": "sketch.create", "params": {"plane": "YZ"}},
        {"command": "sketch.line", "params": {"points": points, "closed": True}},
        {"command": "sketch.finish"},
        {"command": "solid.extrude", "params": {"distance": length_mm}},
    ]


def _ngon_mm(radius_m: float):
    points = []
    for i in range(recipe.AERATOR_SIDES):
        angle = 2.0 * math.pi * i / recipe.AERATOR_SIDES
        points.append([
            radius_m * 1000.0 * math.cos(angle),
            radius_m * 1000.0 * math.sin(angle),
        ])
    return points


def _aerator_commands():
    """Flange, pipe and cap as joined 16-gon extrudes. pipe_length drives the stack."""
    flange_h = f"{recipe.FLANGE_H_M * 1000.0:g}"
    cap_h = f"{recipe.CAP_H_M * 1000.0:g}"
    pipe_mm = f"{recipe.PIPE_LENGTH_M * 1000.0:g}"
    steps = (
        ("flange", recipe.FLANGE_R_M, flange_h, None, "new"),
        ("pipe", recipe.PIPE_R_M, "pipe_length", flange_h, "join"),
        ("cap", recipe.CAP_R_M, cap_h, flange_h + " + pipe_length", "join"),
    )
    commands = [{
        "command": "parameters.change",
        "params": {"name": "pipe_length", "expression": pipe_mm, "unit": "mm"},
    }]
    for name, radius, distance, offset, operation in steps:
        commands.append({"command": "sketch.create", "params": {"plane": "XY", "name": name}})
        commands.append({"command": "sketch.line", "params": {"points": _ngon_mm(radius), "closed": True}})
        commands.append({"command": "sketch.finish"})
        params = {"distance": distance, "sketch": name, "operation": operation, "name": name}
        if offset is not None:
            params["start_offset"] = offset
        commands.append({"command": "solid.extrude", "params": params})
    return commands


def _fail(rows, part, kind, reason):
    rows.append({
        "part": part,
        "tool": "solidcraft",
        "kind": kind,
        "status": "not_measured",
        "reason": str(reason)[:800],
    })


def _timed(mcp: Mcp, work, obj_path: Path, fbx_path: Path):
    started = time.perf_counter()
    reply = work()
    _export(mcp, obj_path, fbx_path)
    return time.perf_counter() - started, reply


def _row(part, kind, build_s, fbx, version, feature, boundary):
    return {
        "part": part,
        "tool": "solidcraft",
        "kind": kind,
        "build_s": build_s,
        "fbx": str(fbx),
        "version": version,
        "feature": feature,
        "timing_boundary": boundary,
        "status": "built",
    }


def main() -> int:
    if not CLI.is_file():
        print("not_measured: solidcraft-cli missing at " + str(CLI))
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    version = subprocess.run([str(CLI), "--version"], capture_output=True, text=True, check=False)
    ver = (version.stdout or version.stderr or "").strip()
    rows = []
    try:
        mcp = Mcp(CLI, OUT)
    except (McpError, OSError, json.JSONDecodeError) as exc:
        print("not_measured: SolidCraft MCP failed to start: " + str(exc))
        return 1
    bench_ok = False
    aerator_ok = False
    try:
        try:
            mcp.tool("new_design", {"name": "bench"})
            build_s, reply = _timed(
                mcp,
                lambda: mcp.tool("batch", {"verbose": False, "commands": _bench_commands(1800.0)}),
                OUT / "bench-solidcraft.obj",
                OUT / "bench-solidcraft.fbx",
            )
            rows.append(_row("bench", "build", build_s, OUT / "bench-solidcraft.fbx", ver, "sketch.line + solid.extrude", TIMING_BUILD))
            bench_ok = True
        except (McpError, OSError, json.JSONDecodeError, ValueError) as exc:
            _fail(rows, "bench", "build", exc)
        if bench_ok:
            try:
                build_s, reply = _timed(
                    mcp,
                    lambda: mcp.tool("execute", {
                        "command": "timeline.edit",
                        "params": {"feature": "Extrude1", "set": {"extent": {"distance": 1900.0}}},
                        "verbose": False,
                    }),
                    OUT / "bench-solidcraft-param.obj",
                    OUT / "bench-solidcraft-param.fbx",
                )
                rows.append(_row(
                    "bench", "param_change", build_s, OUT / "bench-solidcraft-param.fbx", ver,
                    "timeline.edit Extrude1 length", TIMING_PARAM,
                ))
            except (McpError, OSError, json.JSONDecodeError, ValueError) as exc:
                _fail(rows, "bench", "param_change", exc)
        else:
            _fail(rows, "bench", "param_change", "bench build failed")
        try:
            mcp.tool("new_design", {"name": "aerator"})
            build_s, reply = _timed(
                mcp,
                lambda: mcp.tool("batch", {"verbose": False, "commands": _aerator_commands()}),
                OUT / "aerator-solidcraft.obj",
                OUT / "aerator-solidcraft.fbx",
            )
            rows.append(_row(
                "aerator", "build", build_s, OUT / "aerator-solidcraft.fbx", ver,
                "solid.extrude flange + pipe + cap, 16-gon", TIMING_BUILD,
            ))
            aerator_ok = True
        except (McpError, OSError, json.JSONDecodeError, ValueError) as exc:
            _fail(rows, "aerator", "build", exc)
        if aerator_ok:
            try:
                pipe_mm = f"{recipe.PIPE_LENGTH_PARAM_M * 1000.0:g}"
                build_s, reply = _timed(
                    mcp,
                    lambda: mcp.tool("execute", {
                        "command": "parameters.change",
                        "params": {"name": "pipe_length", "expression": pipe_mm},
                        "verbose": False,
                    }),
                    OUT / "aerator-solidcraft-param.obj",
                    OUT / "aerator-solidcraft-param.fbx",
                )
                rows.append(_row(
                    "aerator", "param_change", build_s, OUT / "aerator-solidcraft-param.fbx", ver,
                    "parameters.change pipe_length", TIMING_PARAM,
                ))
            except (McpError, OSError, json.JSONDecodeError, ValueError) as exc:
                _fail(rows, "aerator", "param_change", exc)
        else:
            _fail(rows, "aerator", "param_change", "aerator build failed")
    finally:
        mcp.close()
    recipe.publish_bytes(
        OUT / "solidcraft-build.json",
        json.dumps({"version": ver, "timing_boundary": TIMING_BUILD, "rows": rows}, indent=2).encode("utf-8"),
    )
    print(json.dumps(rows, indent=2))
    expected = {("bench", "build"), ("bench", "param_change"), ("aerator", "build"), ("aerator", "param_change")}
    got = {(row.get("part"), row.get("kind")) for row in rows if row.get("fbx")}
    return 0 if got == expected else 1


if __name__ == "__main__":
    sys.exit(main())
