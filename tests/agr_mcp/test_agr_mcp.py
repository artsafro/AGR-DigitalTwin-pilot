"""new-case: agr-mcp phase-0 exit test (plan section 5): every tool through an in-process MCP client equals the
direct call of the wrapped function on the same synthetic input; locks, audit, unsafe gate. Synthetic data only.
"""
import base64
import json
import re
import sys
import threading
import types
from pathlib import Path

import anyio
import pytest
from mcp.shared.memory import create_connected_server_and_client_session as connect

from agr_mcp import TOOL_SCHEMA_VERSION, audit, locks, max_pipe, server, tools
from agr_mcp.max_side import max_bridge

ROOT = Path(__file__).resolve().parents[2]
PNG_1PX = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg==")


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("AGR_MCP_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setenv("AGR_MCP_AUDIT", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("AGR_MCP_CARD", "test-841")
    monkeypatch.delenv("AGR_MCP_UNSAFE", raising=False)
    for k in ("AGR_MCP_MAX_PID", "MCP_MAX_PID", "MCP_MAX_PIPE"):  # unit tests never reach a real Max
        monkeypatch.delenv(k, raising=False)


def audit_lines(tmp_path):
    p = tmp_path / "audit.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def run_calls(calls, env=None, transport=None, list_only=False):
    """[(name, args)] -> (tool names, [CallToolResult]) through one in-memory MCP client session."""
    async def main():
        srv = server.build_server(env=env, max_transport=transport)
        async with connect(srv) as client:
            listed = [t.name for t in (await client.list_tools()).tools]
            results = [] if list_only else [await client.call_tool(n, a) for n, a in calls]
            return listed, results
    return anyio.run(main)


def ok(result):
    assert not result.isError, result.content[0].text
    sc = result.structuredContent
    assert sc["tool_schema_version"] == TOOL_SCHEMA_VERSION
    assert json.loads(result.content[0].text) == sc
    return sc["result"]


# ---- synthetic Max: fake pymxs + fake installed runtime, executed by an in-process "pipe" ----------------
FAKE_RUNTIME = '''
VERSION = "0.5.0"
CALLS = []
def _rep(tool, nodes, code):
    CALLS.append((tool, None if nodes is None else [n.handle for n in nodes]))
    nodes = nodes if nodes is not None else [type("N", (), {"handle": 1, "name": "Box001"})()]
    objs = [{"handle": n.handle, "name": n.name,
             "findings": [{"code": code, "ids": [n.handle, 2], "detail": "synthetic"}] if n.handle % 2 else []}
            for n in nodes]
    return {"schema": 1, "tool": tool, "status": "fail" if any(o["findings"] for o in objs) else "pass",
            "objects": objs}
def xview(nodes=None): return _rep("xview", nodes, "overlap_vertex")
def matid(nodes=None): return _rep("matid", nodes, "udim_id")
def texel_preview(nodes=None):
    r = _rep("texel", nodes, "texel_low"); r["median_px_m"] = 512.0; return r
'''


class FakeNode:
    def __init__(self, handle):
        self.handle, self.name = handle, f"Box{handle:03d}"


@pytest.fixture
def fake_max(tmp_path, monkeypatch):
    root = tmp_path / "AGRTools-0.5.0"
    root.mkdir()
    (root / "runtime.py").write_text(FAKE_RUNTIME, encoding="utf-8")
    nodes = {h: FakeNode(h) for h in (1, 2, 3)}
    rt = types.SimpleNamespace(
        maxFilePath="", maxFileName="", name=lambda s: s, getDir=lambda _n: str(tmp_path),
        isValidNode=lambda n: n is not None,
        maxOps=types.SimpleNamespace(getNodeByHandle=lambda h: nodes.get(h)))
    monkeypatch.setitem(sys.modules, "pymxs", types.SimpleNamespace(runtime=rt))
    monkeypatch.delitem(sys.modules, "runtime", raising=False)
    monkeypatch.setenv("AGR_TOOLS_ROOT", str(root))
    sent = []

    def transport(code, timeout):
        sent.append(code)
        m = re.search(r'b\.call "(\w+)" "([0-9a-f]*)" "([0-9a-f]*)"', code)
        assert m, code
        return max_bridge.call(*m.groups())
    yield types.SimpleNamespace(root=root, nodes=nodes, transport=transport, sent=sent)
    sys.path[:] = [p for p in sys.path if Path(p) != root]


def direct_runtime(fake, fn, handles):
    mod = sys.modules["runtime"]
    return getattr(mod, fn)([fake.nodes[h] for h in handles] if handles else None)


# ---- synthetic offline inputs -----------------------------------------------------------------------------
def geojson_file(tmp_path):
    sys.path.insert(0, str(ROOT / "tests/qa"))
    try:
        from test_geojson_fno_legacy_controls import _payload
    finally:
        sys.path.remove(str(ROOT / "tests/qa"))
    p = tmp_path / "SM_Synthetic_Ground.geojson"
    p.write_bytes(_payload("12345"))
    return p


def parity_dump():
    tri = {"class": "Editable_Poly", "verts_type": "#vertices", "faces_type": "#faces",
           "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0.0005, 0, 0]], "faces": [[1, 2, 3], [4, 2, 3]],
           "num_verts": 4, "num_faces": 2}
    return {"m_per_unit": 1.0, "tol_v_units": 0.002, "tol_f_units": 0.005,
            "nodes": [dict(tri, name="A", overlap_vertices=[1, 4], overlap_faces=[]),
                      dict(tri, name="B", overlap_vertices=[], overlap_faces=[1])]}


MESH_ARGS = {"names": ["SM_Vatutino_Ground", "bad name"], "kind": "vpm", "role": "ground",
             "fbx_stem": "SM_Vatutino_Ground", "limit": 254, "src": "synthetic"}


def offline_cases(tmp_path):
    import validate_package
    import xview_parity
    from twinqa.geojson import geojson_findings
    from twinqa.naming import mesh_name_findings
    from twinqa.profiles import load_profiles
    geo = geojson_file(tmp_path)
    png = tmp_path / "T_Synthetic_D.png"
    png.write_bytes(PNG_1PX)
    prof = load_profiles()
    return [
        ("agr_mesh_names", MESH_ARGS, lambda: mesh_name_findings(**MESH_ARGS)),
        ("agr_geojson_check", {"path": str(geo), "ground": True},
         lambda: geojson_findings(geo.read_bytes(), prof.vpm, True, source_name=geo.name)),
        ("agr_package_validate", {"target": str(geo)},
         lambda: validate_package.validate(geo, None, prof)),
        ("agr_package_validate", {"target": str(png), "kind": "npm"},
         lambda: validate_package.validate(png, "npm", prof)),
        ("agr_xview_parity", {"dump": parity_dump()}, lambda: xview_parity.compare(parity_dump())),
    ]




# ---- exit test ----------------------------------------------------------------------------------------------
def test_tools_list_is_the_phase0_eight_without_code_argument():
    listed, _ = run_calls([], list_only=True)
    assert sorted(listed) == sorted(tools.PHASE0)
    for spec in tools.catalog().values():
        assert "code" not in json.dumps(spec.input), spec.name
        assert spec.read_only and not spec.destructive


def test_exit_offline_tools_equal_direct_call(tmp_path):
    cases = offline_cases(tmp_path)
    _, results = run_calls([(n, a) for n, a, _ in cases])
    table = []
    for (name, _args, direct), res in zip(cases, results):
        got = ok(res)
        want = tools.jsonable(direct())
        assert want, f"{name}: synthetic input produced an empty result; the equality would be vacuous"
        table.append((name, got == want))
        assert got == want, name
    assert len(audit_lines(tmp_path)) == len(cases)
    print("EXIT_TABLE", json.dumps(table))


@pytest.mark.parametrize("tool,fn", [("agr_xview_check", "xview"), ("agr_matid_check", "matid"),
                                     ("agr_texel_readout", "texel_preview")])
@pytest.mark.parametrize("handles", [[1, 2], [3], []])
def test_exit_max_tools_equal_direct_runtime_call(fake_max, tmp_path, tool, fn, handles):
    _, (res,) = run_calls([(tool, {"scene": "live", "handles": handles})], transport=fake_max.transport)
    got = ok(res)
    assert got == direct_runtime(fake_max, fn, handles)
    calls = sys.modules["runtime"].CALLS
    assert calls[0] == calls[1] == (got["tool"], handles or None), "wrapper changed the node set"
    assert "select" not in fake_max.sent[0]
    line, = audit_lines(tmp_path)
    assert line["host"] == "max-live" and line["status"] == "ok" and line["lock"].endswith("agr-3dsmax-live.lock")


@pytest.mark.parametrize("args,needle", [
    ({"scene": "live", "handles": [9]}, "unknown node handle 9"),
    ({"scene": "C:/other.max"}, "scene mismatch"),
])
def test_max_unknown_handle_or_scene_is_an_error_naming_it(fake_max, args, needle):
    _, (res,) = run_calls([("agr_xview_check", args)], transport=fake_max.transport)
    assert res.isError and needle in res.content[0].text


def test_max_wrong_runtime_version_is_an_error(fake_max):
    (fake_max.root / "runtime.py").write_text(FAKE_RUNTIME.replace('"0.5.0"', '"0.4.0"'), encoding="utf-8")
    _, (res,) = run_calls([("agr_matid_check", {"scene": "live"})], transport=fake_max.transport)
    assert res.isError and "0.4.0" in res.content[0].text


def test_max_without_pinned_pid_is_refused(monkeypatch):
    for k in ("AGR_MCP_MAX_PID", "MCP_MAX_PID", "MCP_MAX_PIPE"):
        monkeypatch.delenv(k, raising=False)
    _, (res,) = run_calls([("agr_xview_check", {"scene": "live"})])
    assert res.isError and "no Max target pinned" in res.content[0].text


def test_bridge_script_interpolates_only_hex():
    s = max_pipe.bridge_script("agr_xview_check", 'C:/x"; deleteFile "y', {"scene": 'live"; quit()'})
    assert "deleteFile" not in s and "quit" not in s
    with pytest.raises(ValueError):
        max_pipe.bridge_script('x" ; quit', "", {})


@pytest.mark.blender
def test_exit_fbx_readback_equals_scene_readback(tmp_path):
    import subprocess
    from dt_ai.core.blender_runner import blender_executable
    from twinqa.scene import readback
    fbx = tmp_path / "cube.fbx"
    subprocess.run([blender_executable(), "--background", "--factory-startup", "--python-exit-code", "1",
                    "--python-expr", "import bpy,sys;bpy.ops.wm.read_factory_settings(use_empty=True);"
                    "bpy.ops.mesh.primitive_cube_add(size=2);bpy.ops.export_scene.fbx(filepath=sys.argv[-1])",
                    "--", str(fbx)], check=True, capture_output=True, timeout=300)
    _, (res,) = run_calls([("agr_fbx_readback", {"fbx_path": str(fbx)})])
    got, want = ok(res), tools.jsonable(readback(fbx))
    assert got == want and got["source"]
    line, = audit_lines(tmp_path)
    assert line["host"] == "blender-batch" and line["lock"].endswith("agr-blender-batch.lock")
    print("EXIT_TABLE", json.dumps([["agr_fbx_readback", got == want]]))


# ---- fail-closed inputs -----------------------------------------------------------------------------------
@pytest.mark.parametrize("name,args,needle", [
    ("agr_mesh_names", dict(MESH_ARGS, names=[]), "invalid input"),
    ("agr_mesh_names", dict(MESH_ARGS, limit=0), "invalid input"),
    ("agr_mesh_names", {k: v for k, v in MESH_ARGS.items() if k != "src"}, "invalid input"),
    ("agr_mesh_names", dict(MESH_ARGS, code="print 1"), "invalid input"),
    ("agr_xview_parity", {"dump": {"nodes": [], "m_per_unit": 1}}, "no nodes"),
    ("agr_xview_parity", {"dump": dict(parity_dump(), m_per_unit=float("nan"))}, "finite"),
    ("agr_xview_parity", {"dump": dict(parity_dump(), tol_v_units=float("inf"))}, "finite"),
    ("agr_geojson_check", {"path": "C:/no/such.geojson", "ground": True}, "not an existing file"),
    ("agr_package_validate", {"target": "C:/no/such.zip"}, "not an existing file"),
    ("agr_fbx_readback", {"fbx_path": "C:/no/such.fbx"}, "not an existing file"),
    ("agr_xview_check", {"scene": ""}, "invalid input"),
    ("agr_xview_check", {"scene": "live", "handles": [1, 1]}, "invalid input"),
    ("agr_no_such_tool", {}, "unknown tool"),
])
def test_bad_input_is_an_error_and_audited(tmp_path, name, args, needle):
    _, (res,) = run_calls([(name, args)])
    assert res.isError and needle in res.content[0].text, res.content[0].text
    line, = audit_lines(tmp_path)
    assert line["tool"] == name and line["status"] in ("invalid", "error", "refused") and line["error"]


def test_empty_geojson_file_is_an_error_or_fail_never_pass(tmp_path):
    p = tmp_path / "empty.geojson"
    p.write_bytes(b"")
    _, (res,) = run_calls([("agr_geojson_check", {"path": str(p), "ground": False})])
    if not res.isError:
        assert any(f["status"] == "fail" for f in res.structuredContent["result"])


# ---- locks --------------------------------------------------------------------------------------------------
def test_parallel_call_to_same_host_is_refused_while_lock_held(fake_max, tmp_path):
    entered, release = threading.Event(), threading.Event()

    def slow(code, timeout):
        entered.set()
        assert release.wait(30)
        return fake_max.transport(code, timeout)

    async def main():
        srv = server.build_server(max_transport=slow)
        out = {}
        async with connect(srv) as client:
            async def first():
                out["first"] = await client.call_tool("agr_xview_check", {"scene": "live", "handles": [1]})

            async with anyio.create_task_group() as tg:
                tg.start_soon(first)
                await anyio.to_thread.run_sync(entered.wait, 30)
                out["second"] = await client.call_tool("agr_matid_check", {"scene": "live", "handles": [1]})
                out["offline"] = await client.call_tool("agr_mesh_names", MESH_ARGS)
                release.set()
        return out
    out = anyio.run(main)
    assert out["second"].isError and "busy: lock held" in out["second"].content[0].text
    assert not out["offline"].isError, "offline host must not share the Max lock"
    ok(out["first"])
    lines = audit_lines(tmp_path)
    assert len(lines) == 3
    assert sorted(x["status"] for x in lines) == ["busy", "ok", "ok"]
    assert not (tmp_path / "locks" / "agr-3dsmax-live.lock").exists(), "lock not released"


def test_foreign_live_lock_refuses_and_is_not_stolen(fake_max, tmp_path):
    import os
    import time
    lock = tmp_path / "locks" / "agr-3dsmax-live.lock"
    lock.parent.mkdir()
    body = json.dumps({"card": "max_exec-other", "pid": os.getpid(), "until": time.time() + 600})
    lock.write_text(body, encoding="utf-8")
    _, (res,) = run_calls([("agr_texel_readout", {"scene": "live"})], transport=fake_max.transport)
    assert res.isError and "busy" in res.content[0].text
    assert lock.read_text(encoding="utf-8") == body
    assert fake_max.sent == []


@pytest.mark.parametrize("info", [{"pid": 999999999}, {"card": "x", "until": 1.0}])
def test_stale_lock_is_reclaimed(fake_max, tmp_path, info):
    lock = tmp_path / "locks" / "agr-3dsmax-live.lock"
    lock.parent.mkdir()
    lock.write_text(json.dumps(info), encoding="utf-8")
    _, (res,) = run_calls([("agr_xview_check", {"scene": "live"})], transport=fake_max.transport)
    ok(res)
    assert not lock.exists()


def test_half_written_lock_is_held_not_stolen(tmp_path):
    lock = tmp_path / "locks" / "agr-blender-batch.lock"
    lock.parent.mkdir()
    lock.write_text("{", encoding="utf-8")
    with pytest.raises(locks.LockBusy):
        with locks.hold("blender-batch", "c", 10):
            pass
    assert lock.read_text(encoding="utf-8") == "{"


def test_held_lock_format_is_seen_by_max_exec_and_dcc_batch(tmp_path):
    import time
    with locks.hold("max-live", "card-a", 30) as path:
        info = json.loads(path.read_text(encoding="utf-8"))
        assert info["card"] == "card-a" and info["until"] > time.time()  # max_exec.py fields
        assert {"pid", "t", "timeout"} <= set(info)  # dcc_batch.py fields
    assert not path.exists()


def test_lock_lifetime_covers_the_wrapped_call_timeout(tmp_path, monkeypatch):
    """#871: a 1800 s readback keeps its lock past the old fixed 900 + 120 s window while its pid lives."""
    clock = [1_000_000.0]
    monkeypatch.setattr(locks, "time", types.SimpleNamespace(time=lambda: clock[0]))
    fbx = tmp_path / "a.fbx"
    fbx.write_bytes(b"synthetic")
    seen = {}

    def probe(at):
        clock[0] = 1_000_000.0 + at
        try:
            with locks.hold("blender-batch", "other-card", 60):
                seen[at] = "acquired"
        except locks.LockBusy:
            seen[at] = "busy"

    def fake_readback(args):
        assert args["timeout"] == 1800
        probe(1021)
        probe(1800 + 121)  # `until` passed, holder pid alive, owner agr-mcp: still held
        return {"source": "synthetic"}

    monkeypatch.setattr(tools, "h_fbx_readback", fake_readback)
    _, (res,) = run_calls([("agr_fbx_readback", {"fbx_path": str(fbx), "timeout": 1800})])
    ok(res)
    assert seen == {1021: "busy", 1921: "busy"}


@pytest.mark.parametrize("name,args,want", [
    ("agr_fbx_readback", {"fbx_path": "a.fbx", "timeout": 7200}, 7200.0),
    ("agr_fbx_readback", {"fbx_path": "a.fbx"}, 600.0),
    ("agr_package_validate", {"target": "a.zip", "scene": True}, 600.0),
    ("agr_xview_check", {"scene": "live"}, tools.MAX_TIMEOUT),
    ("agr_exec_unsafe", {"code": "1", "timeout": 3000}, 3000.0),
])
def test_every_locked_tool_declares_its_call_timeout(name, args, want):
    spec = tools.catalog(unsafe=True)[name]
    assert spec.host(args) != "offline" and spec.timeout is not None and spec.timeout(args) == want


def test_no_locked_tool_falls_back_to_the_server_default_timeout():
    """Every tool that takes a host lock sizes it from its own call timeout (#871), incl. later-added tools."""
    missing = [s.name for s in tools.catalog(unsafe=True).values()
               if s.timeout is None and s.host({"scene": "live", "fbx_path": "a.fbx", "target": "a.zip",
                                                "code": "1", "path": "a", "dump": {}}) != "offline"]
    assert missing == []


def test_expired_lock_of_dead_holder_is_reclaimed(monkeypatch):
    clock = [1_000_000.0]
    monkeypatch.setattr(locks, "time", types.SimpleNamespace(time=lambda: clock[0]))
    with locks.hold("blender-batch", "card-a", 1800) as path:
        assert path is not None
        first = json.loads(path.read_text(encoding="utf-8"))
        clock[0] += 1800 + 121
        monkeypatch.setattr(locks, "_alive", lambda pid: False)
        with locks.hold("blender-batch", "card-b", 60):
            assert json.loads(path.read_text(encoding="utf-8"))["card"] == "card-b"
        assert first["until"] == 1_000_000.0 + 1800 + 120


def test_two_concurrent_reclaimers_of_one_stale_lock_exactly_one_wins(tmp_path, monkeypatch):
    """#872: both callers see the stale lock before either reclaims it; only one may acquire."""
    lock = tmp_path / "locks" / "agr-blender-batch.lock"
    lock.parent.mkdir()
    real_stale = locks._stale
    for _ in range(50):
        lock.write_text(json.dumps({"card": "dead", "pid": 999999999}), encoding="utf-8")
        seen_stale = threading.Barrier(2, timeout=10)
        both_tried = threading.Barrier(2, timeout=10)
        local = threading.local()
        results = []
        won = threading.Event()

        def stale(path):
            verdict = real_stale(path)
            if not getattr(local, "waited", False):
                local.waited = True
                # both callers judged the old file stale; the second acts only after the first has acquired
                if seen_stale.wait() == 1:
                    won.wait(2)
            return verdict

        def worker():
            try:
                with locks.hold("blender-batch", "c", 60):
                    results.append("acquired")
                    won.set()
                    both_tried.wait()  # keep holding until the other caller has tried
            except locks.LockBusy:
                results.append("busy")
                both_tried.wait()

        monkeypatch.setattr(locks, "_stale", stale)
        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(20)
        assert sorted(results) == ["acquired", "busy"]
        assert not lock.exists()
        assert sorted(p.name for p in lock.parent.iterdir()) == [], "reclaim left a temp file"


# ---- audit --------------------------------------------------------------------------------------------------
def test_audit_lines_equal_calls_and_carry_plan_fields(tmp_path):
    calls = [("agr_mesh_names", MESH_ARGS)] * 3 + [("agr_xview_parity", {"dump": {}})] + [("nope", {})]
    run_calls(calls)
    lines = audit_lines(tmp_path)
    assert len(lines) == len(calls)
    for line, (name, args) in zip(lines, calls):
        assert set(audit.FIELDS) <= set(line)
        assert line["tool"] == name and line["args_sha256"] == audit.args_sha256(args)
        assert line["card"] == "test-841" and line["client"] == "mcp" and line["duration_ms"] >= 0
    assert [x["status"] for x in lines] == ["ok", "ok", "ok", "invalid", "refused"]
    assert "SM_Vatutino" not in (tmp_path / "audit.jsonl").read_text(encoding="utf-8"), "arguments leaked"


# ---- unsafe hatch -------------------------------------------------------------------------------------------
def test_unsafe_absent_by_default_and_refused(tmp_path):
    listed, (res,) = run_calls([("agr_exec_unsafe", {"code": "1+1"})], env={})
    assert "agr_exec_unsafe" not in listed
    assert res.isError and "AGR_MCP_UNSAFE=1" in res.content[0].text
    line, = audit_lines(tmp_path)
    assert line["status"] == "refused" and line["unsafe"] is True and line["code_bytes"] == 3


@pytest.mark.parametrize("value", ["0", "true", "yes", ""])
def test_unsafe_only_with_exact_one(value):
    listed, _ = run_calls([], env={"AGR_MCP_UNSAFE": value}, list_only=True)
    assert "agr_exec_unsafe" not in listed


def test_unsafe_with_flag_is_listed_destructive_and_audited(tmp_path):
    sent = []

    def transport(code, timeout):
        sent.append(code)
        return '"2"'

    async def main():
        srv = server.build_server(env={"AGR_MCP_UNSAFE": "1"}, max_transport=transport)
        async with connect(srv) as client:
            listed = {t.name: t for t in (await client.list_tools()).tools}
            res = await client.call_tool("agr_exec_unsafe", {"code": "1+1"})
            return listed, res
    listed, res = anyio.run(main)
    assert set(listed) == set(tools.PHASE0) | {"agr_exec_unsafe"}
    assert listed["agr_exec_unsafe"].annotations.destructiveHint is True
    assert ok(res) == {"value": "2"} and sent == ["1+1"]
    line, = audit_lines(tmp_path)
    assert line["unsafe"] is True and line["code_bytes"] == 3 and line["host"] == "max-live"
    assert "1+1" not in (tmp_path / "audit.jsonl").read_text(encoding="utf-8"), "code body leaked to audit"


@pytest.mark.parametrize("raw", ["__MCP_MS_ERR__:-- Runtime error: x", '"__MCP_MS_ERR__:-- Runtime error: x"'])
def test_maxscript_error_marker_is_an_error_not_a_value(raw, tmp_path):
    """3dsmax-mcp returns a MAXScript exception as success=true with this marker (seen natively, #841)."""
    with pytest.raises(max_pipe.MaxError, match="MAXScript error"):
        max_pipe.decode_value(raw)
    _, (res,) = run_calls([("agr_matid_check", {"scene": "live"})], transport=lambda c, t: raw)
    assert res.isError and "MAXScript error" in res.content[0].text
    assert audit_lines(tmp_path)[0]["status"] == "error"


@pytest.mark.parametrize("unsafe", [False, True])
def test_fresh_stdio_process_lists_tools(unsafe, tmp_path):
    """Fresh-process witness: the installed console script over real stdio, not the in-memory transport."""
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from list_tools_stdio import transcript
    finally:
        sys.path.pop(0)
    t = anyio.run(transcript, unsafe, str(tmp_path / "stdio-audit.jsonl"))
    names = [x["name"] for x in t["tools"]]
    assert sorted(names) == sorted(tools.PHASE0 + (("agr_exec_unsafe",) if unsafe else ()))
    assert t["serverInfo"]["name"] == "agr-mcp"
    assert all(x["readOnlyHint"] for x in t["tools"] if x["name"] != "agr_exec_unsafe")


# ---- generated probes (invariant -> probe -> N/N) -------------------------------------------------------
def test_probe_lock_refuses_every_second_holder_seed_841():
    import random
    rnd = random.Random(841)
    n = 0
    for _ in range(60):
        host = rnd.choice(["max-live", "blender-batch"])
        other = "blender-batch" if host == "max-live" else "max-live"
        with locks.hold(host, f"c{rnd.randrange(3)}", rnd.uniform(1, 900)) as held:
            with pytest.raises(locks.LockBusy):
                with locks.hold(host, rnd.choice(["c0", "c1", "c2"]), 10):
                    pass
            with locks.hold(other, "x", 10):  # hosts are independent
                pass
            with locks.hold("offline", "x", 10) as none:
                assert none is None
        assert not held.exists()
        n += 1
    assert n == 60


def test_probe_audit_lines_equal_calls_seed_841(tmp_path):
    import random
    rnd = random.Random(841)
    pool = [("agr_mesh_names", MESH_ARGS), ("agr_mesh_names", dict(MESH_ARGS, limit=0)),
            ("agr_xview_parity", {"dump": parity_dump()}), ("agr_xview_parity", {"dump": {}}),
            ("agr_geojson_check", {"path": "C:/no.geojson", "ground": True}), ("agr_unknown", {"a": 1}),
            ("agr_exec_unsafe", {"code": "x"}), ("agr_xview_check", {"scene": "live"})]
    calls = [rnd.choice(pool) for _ in range(40)]
    run_calls(calls, env={})
    lines = audit_lines(tmp_path)
    assert len(lines) == len(calls)
    assert [x["tool"] for x in lines] == [c[0] for c in calls]
    assert all(set(audit.FIELDS) <= set(x) for x in lines)
