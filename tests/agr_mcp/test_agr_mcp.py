"""new-case: agr-mcp phase-0 exit test (plan section 5): every tool through an in-process MCP client equals the
direct call of the wrapped function on the same synthetic input; locks, audit, unsafe gate. Synthetic data only.
"""
import base64
import json
import math
import re
import sys
import threading
import types
import zipfile
from pathlib import Path

import anyio
import pytest
from mcp.shared.memory import create_connected_server_and_client_session as connect

from agr_mcp import TOOL_SCHEMA_VERSION, audit, locks, max_pipe, server, tools
from agr_mcp.max_side import max_bridge

# Tools of the ops_d108 hook (branch U, #1024): not in tools.LISTED, tested by their owner. Empty with the stub.
HOOK = tuple(s.name for s in __import__("agr_mcp.ops_d108", fromlist=["register"]).register({}))
HOOK_EDITING = tuple(s.name for s in __import__("agr_mcp.ops_d108", fromlist=["register"]).register({})
                     if not s.read_only)

ROOT = Path(__file__).resolve().parents[2]
PNG_1PX = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg==")


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("AGR_MCP_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setenv("AGR_MCP_AUDIT", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("AGR_MCP_CARD", "test-841")
    monkeypatch.setenv("AGR_JOURNAL_DIR", str(tmp_path / "journal"))  # v2: every call journals (never the user's)
    monkeypatch.setenv("AGR_MCP_DATA_DIR", str(tmp_path / "data"))  # v2: report_uri store
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
        isValidNode=lambda n: n is not None, selection=[nodes[2]],
        getHandleByAnim=lambda n: n.handle + 1000, getAnimByHandle=lambda h: nodes.get(h - 1000),
        maxOps=types.SimpleNamespace(getNodeByHandle=lambda h: nodes.get(h)))
    rt.clearSelection = lambda: rt.selection.clear()
    rt.select = lambda ns: rt.selection.extend(n for n in ns if n not in rt.selection)
    monkeypatch.setitem(sys.modules, "pymxs", types.SimpleNamespace(runtime=rt))
    monkeypatch.delitem(sys.modules, "runtime", raising=False)
    monkeypatch.setenv("AGR_TOOLS_ROOT", str(root))
    sent = []

    def transport(code, timeout):
        sent.append(code)
        m = re.search(r'b\.call "(\w+)" "([0-9a-f]*)" "([0-9a-f]*)"', code)
        assert m, code
        return max_bridge.call(*m.groups())
    yield types.SimpleNamespace(root=root, nodes=nodes, transport=transport, sent=sent, rt=rt)
    sys.path[:] = [p for p in sys.path if not (p and Path(p).is_relative_to(tmp_path))]


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
    """#1024 branch 0 changes the catalogue fact: v1 (PHASE0) + the v2 tools generated from the plan (LISTED)."""
    listed, _ = run_calls([], list_only=True)
    assert sorted(listed) == sorted(tools.LISTED + HOOK) and set(tools.PHASE0) < set(listed)
    editing = {n for n, _row, _what, kind in tools.EDITS_080 if kind != "read"}  # 0.8 preview -> apply (#908)
    editing.add("agr_op_apply")  # v2: applies a held 0.8 preview
    for spec in tools.catalog().values():
        assert "code" not in json.dumps(spec.input), spec.name
        if spec.name in HOOK:
            continue
        assert spec.read_only == (spec.name not in editing), spec.name
        assert spec.destructive == (spec.name in ("agr_ucx_rename", "agr_op_apply")), spec.name  # in place


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
@pytest.mark.parametrize("handles", [[1, 2], [3]])
def test_exit_max_tools_equal_direct_runtime_call(fake_max, tmp_path, tool, fn, handles):
    _, (res,) = run_calls([(tool, {"scene": "live", "handles": handles})], transport=fake_max.transport)
    got = ok(res)
    assert got == direct_runtime(fake_max, fn, handles)
    calls = sys.modules["runtime"].CALLS
    assert calls[0] == calls[1] == (got["tool"], handles), "wrapper changed the node set"
    assert "select" not in fake_max.sent[0]
    line, = audit_lines(tmp_path)
    assert line["host"] == "max-live" and line["status"] == "ok" and line["lock"].endswith("agr-3dsmax-live.lock")


@pytest.mark.parametrize("args,needle", [
    ({"scene": "live", "handles": [9]}, "unknown node handle 9"),
    ({"scene": "C:/other.max", "handles": [1]}, "scene_mismatch"),
])
def test_max_unknown_handle_or_scene_is_an_error_naming_it(fake_max, args, needle):
    _, (res,) = run_calls([("agr_xview_check", args)], transport=fake_max.transport)
    assert res.isError and needle in res.content[0].text


def test_max_wrong_runtime_version_is_an_error(fake_max):
    (fake_max.root / "runtime.py").write_text(FAKE_RUNTIME.replace('"0.5.0"', '"0.4.0"'), encoding="utf-8")
    _, (res,) = run_calls([("agr_matid_check", {"scene": "live", "handles": [1]})], transport=fake_max.transport)
    assert res.isError and "0.4.0" in res.content[0].text and "version_mismatch" in res.content[0].text


def test_max_without_pinned_pid_is_refused(monkeypatch):
    for k in ("AGR_MCP_MAX_PID", "MCP_MAX_PID", "MCP_MAX_PIPE"):
        monkeypatch.delenv(k, raising=False)
    _, (res,) = run_calls([("agr_xview_check", {"scene": "live", "handles": [1]})])
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
    _, (res,) = run_calls([("agr_texel_readout", {"scene": "live", "handles": [1]})], transport=fake_max.transport)
    assert res.isError and "busy" in res.content[0].text
    assert lock.read_text(encoding="utf-8") == body
    assert fake_max.sent == []


@pytest.mark.parametrize("info", [{"pid": 999999999}, {"card": "x", "until": 1.0}])
def test_stale_lock_is_reclaimed(fake_max, tmp_path, info):
    lock = tmp_path / "locks" / "agr-3dsmax-live.lock"
    lock.parent.mkdir()
    lock.write_text(json.dumps(info), encoding="utf-8")
    _, (res,) = run_calls([("agr_xview_check", {"scene": "live", "handles": [1]})], transport=fake_max.transport)
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
    """#871: a 1800 s readback keeps its lock past the old fixed 900 + 120 s window.
    #895: once `until` itself has passed, a live agr-mcp pid does not keep the lock."""
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
        probe(1021)  # past the old fixed 900 + 120 window, still inside `until`
        probe(1800 + 121)  # past `until`: a live agr-mcp pid does not keep the lock
        return {"source": "synthetic"}

    monkeypatch.setattr(tools, "h_fbx_readback", fake_readback)
    _, (res,) = run_calls([("agr_fbx_readback", {"fbx_path": str(fbx), "timeout": 1800})])
    ok(res)
    assert seen == {1021: "busy", 1921: "acquired"}


def test_leaked_live_agr_mcp_lock_is_acquired_an_hour_past_until(tmp_path, monkeypatch):
    """#895 witness: os.remove fails, the server pid stays alive, hold() an hour past `until` acquires."""
    import os
    clock = [1_000_000.0]
    monkeypatch.setattr(locks, "time", types.SimpleNamespace(time=lambda: clock[0]))
    real_remove = os.remove

    def sharing_violation(path):
        raise PermissionError(32, "The process cannot access the file because it is being used by another process")

    monkeypatch.setattr(os, "remove", sharing_violation)
    with locks.hold("blender-batch", "a", 900) as path:
        assert path is not None
        body = path.read_text(encoding="utf-8")
    assert path.exists(), "a failed release leaves the lock behind"
    info = json.loads(body)
    until = info["until"]
    assert info["owner"] == "agr-mcp" and info["pid"] == os.getpid() and locks._alive(info["pid"])
    assert until == 1_000_000.0 + 900 + 120
    monkeypatch.setattr(os, "remove", real_remove)
    clock[0] = until - 1  # live agr-mcp pid, still inside the lease: not stolen
    with pytest.raises(locks.LockBusy):
        with locks.hold("blender-batch", "early", 60):
            pass
    assert path.read_text(encoding="utf-8") == body
    clock[0] = until + 3600  # one hour past `until`, same live process
    with locks.hold("blender-batch", "b", 60) as taken:
        assert json.loads(taken.read_text(encoding="utf-8"))["card"] == "b"
    assert not path.exists()


@pytest.mark.parametrize("name,args,want", [
    ("agr_fbx_readback", {"fbx_path": "a.fbx", "timeout": 7200}, 7200.0),
    ("agr_fbx_readback", {"fbx_path": "a.fbx"}, 600.0),
    ("agr_package_validate", {"target": "a.zip", "scene": True}, 21 * 600.0),
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


def test_restore_rename_race_cannot_give_two_holders(tmp_path, monkeypatch):
    """#896: B renames after A has created a fresh lock; C creates before B restores. One holder.

    Barriers force that interleaving when reclaim still renames the lock aside. A reclaim that
    never moves a live lock aside leaves no such window: B finishes busy, and C then sees A's lock.
    """
    import os
    lock = tmp_path / "locks" / "agr-blender-batch.lock"
    lock.parent.mkdir()
    lock.write_text(json.dumps({"card": "dead", "pid": 999999999}), encoding="utf-8")
    real_stale = locks._stale
    real_rename = os.rename
    b_saw_stale = threading.Event()
    a_holding = threading.Event()
    window_open = threading.Event()
    c_holding = threading.Event()
    b_finished = threading.Event()
    race_done = threading.Event()
    state = {"current": 0, "max": 0}
    guard = threading.Lock()
    errors = []

    def enter():
        with guard:
            state["current"] += 1
            state["max"] = max(state["max"], state["current"])

    def leave():
        with guard:
            state["current"] -= 1

    def stale(path):
        verdict = real_stale(path)
        if threading.current_thread().name == "B" and not getattr(stale, "b_waited", False):
            stale.b_waited = True
            b_saw_stale.set()
            if not a_holding.wait(5):
                errors.append("A did not acquire while B was past the stale check")
        return verdict

    def rename(src, dst):
        src_p, dst_p = Path(src), Path(dst)
        aside = src_p == lock and ".reclaim-" in dst_p.name
        if threading.current_thread().name == "B" and aside:
            real_rename(src, dst)
            window_open.set()
            if not c_holding.wait(5):
                errors.append("C did not create before B's restore")
            return
        return real_rename(src, dst)

    def thread_b():
        try:
            with locks.hold("blender-batch", "B", 60):
                enter()
                errors.append("B acquired; the forced window expects B to restore and lose")
                leave()
        except locks.LockBusy:
            pass
        except Exception as exc:  # noqa: BLE001 — reported to the main thread
            errors.append(repr(exc))
        finally:
            b_finished.set()

    def thread_a():
        if not b_saw_stale.wait(5):
            errors.append("B did not reach the stale check")
            return
        try:
            with locks.hold("blender-batch", "A", 60):
                enter()
                a_holding.set()
                if not race_done.wait(5):
                    errors.append("race did not finish while A held")
                leave()
        except locks.LockBusy:
            errors.append("A was busy; A must win the stale lock before B renames")
        except Exception as exc:  # noqa: BLE001
            errors.append(repr(exc))

    def thread_c():
        while not window_open.is_set() and not b_finished.is_set():
            window_open.wait(0.02)
        opened = window_open.is_set()
        try:
            with locks.hold("blender-batch", "C", 60):
                enter()
                c_holding.set()
                if opened and not b_finished.wait(5):
                    errors.append("B did not finish the restore while C held")
                leave()
        except locks.LockBusy:
            if opened:
                errors.append("C found the lock busy inside the aside window")
        except Exception as exc:  # noqa: BLE001
            errors.append(repr(exc))
        finally:
            race_done.set()

    monkeypatch.setattr(locks, "_stale", stale)
    monkeypatch.setattr(os, "rename", rename)
    threads = [
        threading.Thread(target=thread_b, name="B", daemon=True),
        threading.Thread(target=thread_c, name="C", daemon=True),
        threading.Thread(target=thread_a, name="A", daemon=True),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(15)
        if thread.is_alive():
            errors.append(f"{thread.name} still running")
    race_done.set()
    assert errors == []
    assert state["max"] == 1
    aside = [p.name for p in lock.parent.iterdir() if ".reclaim-" in p.name]
    assert aside == []


def _lock_file(host="blender-batch"):
    path = locks.lock_path(host)
    assert path is not None
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _aside_names(path):
    return [p.name for p in path.parent.iterdir() if ".reclaim-" in p.name]


def test_odd_lock_input_is_busy_or_error_and_never_two_holders(tmp_path):
    """Unsupported bodies and a live reclaim mutex fail closed: error or busy, one holder at most."""
    import os
    import time
    with pytest.raises(ValueError):
        with locks.hold("not-a-host", "c", 10):
            pass
    path = _lock_file()
    odd = ["", "{", "[]", "null", '{"pid": true}', '{"pid": false}', '{"pid": "1"}',
           '{"pid": 1.5}', '{"until": "soon"}', '{"until": true}']
    for body in odd:
        path.write_text(body, encoding="utf-8")
        with pytest.raises(locks.LockBusy):
            with locks.hold("blender-batch", "c", 10):
                pass
        assert path.read_text(encoding="utf-8") == body
    path.write_text("{", encoding="utf-8")
    barrier = threading.Barrier(2)
    outcomes = []

    def both():
        barrier.wait(5)
        try:
            with locks.hold("blender-batch", "c", 10):
                outcomes.append("held")
        except locks.LockBusy:
            outcomes.append("busy")

    threads = [threading.Thread(target=both) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert outcomes == ["busy", "busy"]
    assert path.read_text(encoding="utf-8") == "{"
    path.write_text(json.dumps({"pid": 999999999}), encoding="utf-8")
    mutex = path.with_name(f".{path.name}.mutex")
    mutex.write_text(json.dumps({"pid": os.getpid(), "until": time.time() + 30, "token": "live"}),
                     encoding="utf-8")
    with pytest.raises(locks.LockBusy):
        with locks.hold("blender-batch", "c", 10):
            pass
    assert json.loads(path.read_text(encoding="utf-8"))["pid"] == 999999999
    assert mutex.exists()
    mutex.unlink()
    mutex.mkdir()
    with locks.hold("blender-batch", "c", 10) as held:
        assert json.loads(held.read_text(encoding="utf-8"))["card"] == "c"
    assert not path.exists() and not mutex.exists()
    assert _aside_names(path) == []


def test_probe_at_most_one_holder_seed_896(tmp_path):
    """#896: seeded reclaim interleavings, 4 threads x 8 rounds x 6 setups. Max holders is 1."""
    import os
    import random
    import time
    rnd = random.Random(896)
    path = _lock_file()
    kinds = ["absent", "stale", "dead-mutex", "expired-mutex", "garbage-mutex", "dir-mutex"]
    rounds = 8
    n_threads = 4
    seen = 0
    for _round in range(rounds):
        order = kinds[:]
        rnd.shuffle(order)
        for kind in order:
            for child in path.parent.iterdir():
                if child.is_dir():
                    child.rmdir()
                else:
                    child.unlink()
            mutex = path.with_name(f".{path.name}.mutex")
            if kind != "absent":
                path.write_text(json.dumps({"pid": 999999999, "card": "dead"}), encoding="utf-8")
            if kind == "dead-mutex":
                mutex.write_text(json.dumps({"pid": 999999999, "until": time.time() + 30, "token": "d"}),
                                 encoding="utf-8")
            elif kind == "expired-mutex":
                mutex.write_text(json.dumps({"pid": os.getpid(), "until": time.time() - 1, "token": "e"}),
                                 encoding="utf-8")
            elif kind == "garbage-mutex":
                mutex.write_text("{", encoding="utf-8")
            elif kind == "dir-mutex":
                mutex.mkdir()
            started = threading.Barrier(n_threads)
            tried = threading.Barrier(n_threads)
            guard = threading.Lock()
            state = {"current": 0, "max": 0}
            results = []
            errors = []

            def worker():
                try:
                    started.wait(10)
                    try:
                        with locks.hold("blender-batch", "c", 30):
                            with guard:
                                state["current"] += 1
                                state["max"] = max(state["max"], state["current"])
                            tried.wait(10)
                            with guard:
                                state["current"] -= 1
                            results.append("held")
                    except locks.LockBusy:
                        tried.wait(10)
                        results.append("busy")
                except Exception as exc:  # noqa: BLE001
                    errors.append(repr(exc))

            threads = [threading.Thread(target=worker, daemon=True) for _ in range(n_threads)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(15)
                if thread.is_alive():
                    errors.append("thread still running")
            assert errors == []
            assert state["max"] == 1, kind
            assert results.count("held") == 1, (kind, results)
            assert _aside_names(path) == []
            seen += 1
    assert seen == rounds * len(kinds) == 48


def test_probe_reclaim_leaves_no_aside_files_seed_896(tmp_path):
    """#896: no `*.reclaim-*` name is created across seeded reclaim interleavings."""
    import os
    import random
    import time
    rnd = random.Random(896)
    path = _lock_file()
    kinds = ["absent", "stale", "dead-mutex", "expired-mutex", "garbage-mutex", "live"]
    rounds = 8
    n_threads = 4
    seen = 0
    spotted = []
    for _round in range(rounds):
        order = kinds[:]
        rnd.shuffle(order)
        for kind in order:
            for child in path.parent.iterdir():
                if child.is_dir():
                    child.rmdir()
                else:
                    child.unlink()
            mutex = path.with_name(f".{path.name}.mutex")
            if kind == "live":
                path.write_text(json.dumps({"pid": os.getpid(), "until": time.time() + 60, "token": "L",
                                            "card": "live"}), encoding="utf-8")
            elif kind != "absent":
                path.write_text(json.dumps({"pid": 999999999, "card": "dead"}), encoding="utf-8")
            if kind == "dead-mutex":
                mutex.write_text(json.dumps({"pid": 999999999, "until": time.time() + 30, "token": "d"}),
                                 encoding="utf-8")
            elif kind == "expired-mutex":
                mutex.write_text(json.dumps({"pid": os.getpid(), "until": time.time() - 5, "token": "e"}),
                                 encoding="utf-8")
            elif kind == "garbage-mutex":
                mutex.write_text("not-json", encoding="utf-8")
            started = threading.Barrier(n_threads)
            tried = threading.Barrier(n_threads)
            results = []

            def worker():
                started.wait(10)
                spotted.extend(_aside_names(path))
                try:
                    with locks.hold("blender-batch", "c", 30):
                        spotted.extend(_aside_names(path))
                        tried.wait(10)
                        results.append("held")
                    spotted.extend(_aside_names(path))
                except locks.LockBusy:
                    spotted.extend(_aside_names(path))
                    tried.wait(10)
                    results.append("busy")

            threads = [threading.Thread(target=worker, daemon=True) for _ in range(n_threads)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(15)
            spotted.extend(_aside_names(path))
            if kind == "live":
                assert results.count("held") == 0
            else:
                assert results.count("held") == 1, (kind, results)
            seen += 1
    assert spotted == []
    assert seen == rounds * len(kinds) == 48


def test_stale_mutex_unlink_by_name_cannot_admit_two(tmp_path, monkeypatch):
    """#972: X reads a stale reclaim mutex, pauses; Y links a fresh one; X resumes.

    At most one caller may be inside the mutex. Unlinking the mutex by name deletes Y's live file.
    """
    import time
    path = _lock_file()
    path.write_text(json.dumps({"pid": 999999999, "card": "dead"}), encoding="utf-8")
    mutex = path.with_name(f".{path.name}.mutex")
    mutex.write_text(json.dumps({"pid": 999999999, "until": time.time() + 60, "token": "stale"}),
                     encoding="utf-8")
    real_stale = locks._mutex_stale
    real_acquire = locks._mutex_acquire
    real_release = locks._mutex_release
    real_drop = locks._drop_stale_inode
    x_paused = threading.Event()
    y_inside = threading.Event()
    x_finished = threading.Event()
    guard = threading.Lock()
    state = {"current": 0, "max": 0}
    errors = []
    paused = {"x": False}

    def enter():
        with guard:
            state["current"] += 1
            state["max"] = max(state["max"], state["current"])

    def leave():
        with guard:
            state["current"] -= 1

    def mutex_stale(target):
        verdict = real_stale(target)
        if threading.current_thread().name == "X" and verdict and not paused["x"]:
            paused["x"] = True
            x_paused.set()
            if not y_inside.wait(5):
                errors.append("Y did not enter while X held the stale verdict")
        return verdict

    def acquire(lock, token):
        if threading.current_thread().name == "Y" and not x_paused.wait(5):
            errors.append("X did not observe the stale mutex")
        ok = real_acquire(lock, token)
        if ok:
            enter()
        if threading.current_thread().name == "X":
            x_finished.set()
        return ok

    def release(lock, token):
        try:
            real_release(lock, token)
        finally:
            leave()

    def drop(lock, token):
        if threading.current_thread().name == "Y":
            try:
                snapshot = mutex.read_bytes()
            except OSError as exc:
                errors.append(f"Y mutex missing before resume: {exc!r}")
                snapshot = None
            y_inside.set()
            if not x_finished.wait(5):
                errors.append("X did not finish acquire while Y was inside")
            try:
                after = mutex.read_bytes()
            except OSError as exc:
                errors.append(f"Y mutex missing after X resumed: {exc!r}")
            else:
                if snapshot is not None and after != snapshot:
                    errors.append("X unlinked or rewrote Y's live mutex")
        return real_drop(lock, token)

    monkeypatch.setattr(locks, "_mutex_stale", mutex_stale)
    monkeypatch.setattr(locks, "_mutex_acquire", acquire)
    monkeypatch.setattr(locks, "_mutex_release", release)
    monkeypatch.setattr(locks, "_drop_stale_inode", drop)

    def run(name):
        try:
            with locks.hold("blender-batch", name, 30):
                pass
        except locks.LockBusy:
            pass
        except Exception as exc:  # noqa: BLE001 — reported to the main thread
            errors.append(f"{name}: {exc!r}")

    threads = [threading.Thread(target=run, args=(name,), name=name, daemon=True) for name in ("X", "Y")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(15)
        if thread.is_alive():
            errors.append(f"{thread.name} still running")
    x_finished.set()
    assert errors == []
    assert paused["x"] and y_inside.is_set()
    assert state["max"] == 1
    assert state["current"] == 0
    assert [p.name for p in path.parent.iterdir()] == []


def _clear_lock_dir(path):
    for child in list(path.parent.iterdir()):
        if child.is_dir():
            child.rmdir()
        else:
            child.unlink()


def _plant_mutex(path, kind, clock):
    import os
    mutex = path.with_name(f".{path.name}.mutex")
    if kind == "dead":
        body = {"pid": 999999999, "until": clock + 30, "token": "d"}
    elif kind == "expired-live":
        body = {"pid": os.getpid(), "until": clock - 1, "token": "e"}
    elif kind == "exact-until":
        body = {"pid": os.getpid(), "until": clock, "token": "x"}
    elif kind == "empty":
        mutex.write_bytes(b"")
        return mutex
    elif kind == "partial":
        mutex.write_text("{", encoding="utf-8")
        return mutex
    elif kind == "garbled":
        mutex.write_text("not-json", encoding="utf-8")
        return mutex
    elif kind == "dir":
        mutex.mkdir()
        return mutex
    elif kind == "nan":
        body = {"pid": os.getpid(), "until": float("nan"), "token": "n"}
    elif kind == "inf":
        body = {"pid": os.getpid(), "until": float("inf"), "token": "i"}
    elif kind == "future":
        body = {"pid": os.getpid(), "until": clock + 60, "token": "f"}
    else:
        raise AssertionError(kind)
    mutex.write_text(json.dumps(body), encoding="utf-8")
    return mutex


def _leftover_names(path):
    bad = []
    for child in path.parent.iterdir():
        name = child.name
        if ".take-" in name or ".partial" in name or ".mutex-" in name or ".reclaim-" in name:
            bad.append(name)
    return bad


def test_probe_mutex_exclusivity_seed_972(tmp_path, monkeypatch):
    """#972: seeded interleavings and N-thread hammers. At most one caller inside the mutex."""
    import os
    import random
    clock = [1_000_000.0]
    monkeypatch.setattr(locks, "time", types.SimpleNamespace(time=lambda: clock[0]))
    path = _lock_file()
    real_stale = locks._mutex_stale
    real_acquire = locks._mutex_acquire
    real_release = locks._mutex_release
    real_drop = locks._drop_stale_inode
    guard = threading.Lock()
    state = {"current": 0, "max": 0}
    plan = {"pause": False}

    def enter():
        with guard:
            state["current"] += 1
            state["max"] = max(state["max"], state["current"])

    def mutex_stale(target):
        verdict = real_stale(target)
        if (plan["pause"] and verdict and threading.current_thread().name == "X"
                and not plan["did"]):
            plan["did"] = True
            plan["x_paused"].set()
            if not plan["y_inside"].wait(5):
                plan["errors"].append("Y did not enter")
        return verdict

    def acquire(lock, token):
        if plan["pause"] and threading.current_thread().name == "Y":
            if not plan["x_paused"].wait(5):
                plan["errors"].append("X did not observe the stale mutex")
        ok = real_acquire(lock, token)
        if ok:
            enter()
        if plan["pause"] and threading.current_thread().name == "X":
            plan["x_finished"].set()
        return ok

    def release(lock, token):
        try:
            real_release(lock, token)
        finally:
            with guard:
                state["current"] -= 1

    def drop(lock, token):
        if plan["pause"] and threading.current_thread().name == "Y":
            try:
                snapshot = plan["mutex"].read_bytes()
            except OSError as exc:
                plan["errors"].append(repr(exc))
                snapshot = None
            plan["y_inside"].set()
            if not plan["x_finished"].wait(5):
                plan["errors"].append("X did not finish")
            try:
                after = plan["mutex"].read_bytes()
            except OSError as exc:
                plan["errors"].append(repr(exc))
            else:
                if snapshot is not None and after != snapshot:
                    plan["errors"].append("live mutex changed")
        return real_drop(lock, token)

    monkeypatch.setattr(locks, "_mutex_stale", mutex_stale)
    monkeypatch.setattr(locks, "_mutex_acquire", acquire)
    monkeypatch.setattr(locks, "_mutex_release", release)
    monkeypatch.setattr(locks, "_drop_stale_inode", drop)

    stale_kinds = ["dead", "expired-live", "exact-until", "empty", "partial", "garbled", "dir"]
    closed_kinds = ["nan", "inf", "future"]
    rnd = random.Random(972)
    seen = 0

    def run_hold(name, results, started, tried):
        if started is not None:
            started.wait(10)
        try:
            with locks.hold("blender-batch", name, 30):
                if tried is not None:
                    tried.wait(10)
                results.append("held")
        except locks.LockBusy:
            if tried is not None:
                tried.wait(10)
            results.append("busy")
        except Exception as exc:  # noqa: BLE001
            plan["errors"].append(f"{name}: {exc!r}")

    def one(kind, pause, n_threads):
        nonlocal seen
        _clear_lock_dir(path)
        path.write_text(json.dumps({"pid": 999999999, "card": "dead"}), encoding="utf-8")
        mutex = _plant_mutex(path, kind, clock[0])
        state["current"] = 0
        state["max"] = 0
        plan["pause"] = pause
        plan["did"] = False
        plan["errors"] = []
        plan["mutex"] = mutex
        plan["x_paused"] = threading.Event()
        plan["y_inside"] = threading.Event()
        plan["x_finished"] = threading.Event()
        results = []
        if pause:
            names = ["X", "Y"]
            started = tried = None
        else:
            names = [f"t{i}" for i in range(n_threads)]
            started = threading.Barrier(n_threads)
            tried = threading.Barrier(n_threads)
        threads = [threading.Thread(target=run_hold, args=(name, results, started, tried), name=name, daemon=True)
                   for name in names]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(15)
            if thread.is_alive():
                plan["errors"].append(f"{thread.name} still running")
        plan["x_finished"].set()
        expect = 0 if kind in closed_kinds else 1
        assert plan["errors"] == [], (kind, pause, plan["errors"])
        assert state["max"] == expect, (kind, pause, state["max"], results)
        assert state["current"] == 0
        assert results.count("held") == expect, (kind, pause, results)
        assert _leftover_names(path) == []
        if expect == 0:
            assert mutex.exists()
        seen += 1

    for _round in range(4):
        order = stale_kinds[:]
        rnd.shuffle(order)
        for kind in order:
            one(kind, pause=True, n_threads=2)
    for _round in range(4):
        order = stale_kinds + closed_kinds
        rnd.shuffle(order)
        for kind in order:
            one(kind, pause=False, n_threads=4)
    assert seen == 4 * len(stale_kinds) + 4 * (len(stale_kinds) + len(closed_kinds)) == 68


def test_posix_drop_keeps_a_lock_replaced_before_unlink(tmp_path, monkeypatch):
    """#972: POSIX stat/rename-then-remove must not delete a fresh lock swapped in at that window."""
    import os
    import time
    path = _lock_file()
    token = "owner-token"
    mutex = path.with_name(f".{path.name}.mutex")
    mutex.write_text(json.dumps({"pid": os.getpid(), "until": time.time() + 30, "token": token}),
                     encoding="utf-8")
    path.write_text(json.dumps({"pid": 999999999, "card": "dead"}), encoding="utf-8")
    fresh = json.dumps({"pid": os.getpid(), "until": time.time() + 60, "card": "fresh", "token": "live"}).encode()
    real_stat = os.stat
    real_rename = os.rename
    real_remove = os.remove
    swapped = {"done": False}

    def swap():
        if swapped["done"] or not path.exists():
            return
        swapped["done"] = True
        real_remove(path)
        path.write_bytes(fresh)

    def stat(target, *args, **kwargs):
        result = real_stat(target, *args, **kwargs)
        if Path(target) == path:
            swap()
        return result

    def rename(src, dst):
        if Path(src) == path:
            swap()
        return real_rename(src, dst)

    monkeypatch.setattr(os, "stat", stat)
    monkeypatch.setattr(os, "rename", rename)
    assert locks._drop_stale_inode_posix(path, token) is False
    assert path.read_bytes() == fresh
    assert _leftover_names(path) == []
    assert mutex.exists()


def test_probe_posix_inode_drop_seed_972(tmp_path, monkeypatch):
    """#972: seeded POSIX drop windows. A replaced lock survives; a stale inode is the only one removed."""
    import os
    import random
    import time
    rnd = random.Random(972)
    path = _lock_file()
    token = "owner-token"
    mutex = path.with_name(f".{path.name}.mutex")
    real_rename = os.rename
    real_remove = os.remove
    real_stat = os.stat
    seen = 0
    for trial in range(24):
        _clear_lock_dir(path)
        mutex.write_text(json.dumps({"pid": os.getpid(), "until": time.time() + 30, "token": token}),
                         encoding="utf-8")
        stale = json.dumps({"pid": 999999999, "card": f"dead-{trial}"}).encode()
        fresh = json.dumps({"pid": os.getpid(), "until": time.time() + 60, "card": f"fresh-{trial}",
                            "token": "live"}).encode()
        path.write_bytes(stale)
        mode = rnd.choice(["swap-on-rename", "already-fresh", "stale-inode", "garbled"])
        swapped = {"done": False}

        def swap_fresh(swapped=swapped, fresh=fresh):
            if swapped["done"]:
                return
            swapped["done"] = True
            real_remove(path)
            path.write_bytes(fresh)

        def stat(target, *args, swapped=swapped, mode=mode, **kwargs):
            result = real_stat(target, *args, **kwargs)
            if mode == "swap-on-rename" and Path(target) == path:
                swap_fresh()
            return result

        def rename(src, dst, swapped=swapped, mode=mode):
            if mode == "swap-on-rename" and Path(src) == path:
                swap_fresh()
            return real_rename(src, dst)

        monkeypatch.setattr(os, "stat", stat)
        monkeypatch.setattr(os, "rename", rename)
        if mode == "already-fresh":
            path.write_bytes(fresh)
            assert locks._drop_stale_inode_posix(path, token) is False
            assert path.read_bytes() == fresh
        elif mode == "garbled":
            path.write_bytes(b"{")
            assert locks._drop_stale_inode_posix(path, token) is False
            assert path.read_bytes() == b"{"
        elif mode == "stale-inode":
            assert locks._drop_stale_inode_posix(path, token) is True
            assert not path.exists()
        else:
            assert locks._drop_stale_inode_posix(path, token) is False
            assert path.read_bytes() == fresh
            assert swapped["done"]
        assert _leftover_names(path) == []
        assert mutex.read_text(encoding="utf-8").startswith("{")
        seen += 1
    monkeypatch.setattr(os, "rename", real_rename)
    assert seen == 24


def _force_posix_file_consume():
    """Make file reclaim use the POSIX consume path (tests run on Windows too)."""
    import os
    import stat
    real = locks._consume_if

    def consume_if(path, pred, *, allow_dir):
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            return "gone"
        except OSError:
            return "failed"
        if stat.S_ISDIR(info.st_mode):
            return real(path, pred, allow_dir=allow_dir)
        return locks._consume_posix(path, pred)

    return real, consume_if


def _posix_gap_case(kind, plant, gap):
    """One forced schedule.

    `plant` is `on-close` (X has read the stale inode, then Y replaces it) or
    `already` (a live file is in place before X acts). `gap` is where a second
    holder tries O_EXCL / acquire: `rename`, `remove`, or `after`.
    fcntl is absent on Windows; callers observe `locks._flock`.
    Returns (max_inside, leftovers, flock_calls).
    """
    import os
    import time
    path = _lock_file()
    _clear_lock_dir(path)
    mutex = path.with_name(f".{path.name}.mutex")
    token = "owner-token"
    now = time.time()
    path.write_text(json.dumps({"pid": 999999999, "card": "dead"}), encoding="utf-8")
    if kind == "lock":
        mutex.write_text(json.dumps({"pid": os.getpid(), "until": now + 30, "token": token}),
                         encoding="utf-8")
        target = path
        live = json.dumps({"pid": os.getpid(), "until": now + 60, "card": "fresh", "token": "live"}).encode()
    else:
        mutex.write_text(json.dumps({"pid": 999999999, "until": now + 60, "token": "stale"}),
                         encoding="utf-8")
        target = mutex
        live = json.dumps({"pid": os.getpid(), "until": now + 30, "token": "Y"}).encode()
    state = {"current": 0, "max": 0}
    guard = threading.Lock()
    planted = {"done": False}
    second = {"done": False}
    flock_calls = []
    opened = {}

    def enter():
        with guard:
            state["current"] += 1
            state["max"] = max(state["max"], state["current"])

    def plant_live():
        if planted["done"]:
            return
        planted["done"] = True
        if target.exists():
            real_remove(target)
        target.write_bytes(live)
        enter()

    def second_holder():
        if second["done"]:
            return
        second["done"] = True
        if kind == "lock":
            try:
                fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                return
            os.write(fd, b'{"pid": 1, "token": "excl", "until": 9999999999}')
            os.close(fd)
            enter()
            return
        if locks._mutex_acquire(path, "Z"):
            enter()

    if plant == "already":
        if target.exists():
            os.remove(target)
        target.write_bytes(live)
        enter()
        planted["done"] = True

    real_open, real_close = os.open, os.close
    real_rename, real_remove = os.rename, os.remove
    real_consume = locks._consume_if
    real_flock = getattr(locks, "_flock", None)
    _, posix_consume = _force_posix_file_consume()

    def open_(file, flags, *args, **kwargs):
        fd = real_open(file, flags, *args, **kwargs)
        try:
            opened[fd] = Path(file)
        except TypeError:
            pass
        return fd

    def close(fd):
        real_close(fd)
        name = opened.pop(fd, None)
        if plant == "on-close" and name == target:
            plant_live()

    def rename(src, dst):
        src_p, dst_p = Path(src), Path(dst)
        aside = src_p == target and ".take-" in dst_p.name
        if aside and gap == "rename":
            real_rename(src, dst)
            second_holder()
            return
        return real_rename(src, dst)

    def remove(file):
        file_p = Path(file)
        if file_p == target and gap == "remove":
            real_remove(file)
            second_holder()
            return
        return real_remove(file)

    def flock(fd, operation):
        flock_calls.append(operation)
        if real_flock is None:
            raise OSError("locks._flock is not installed")
        return real_flock(fd, operation)

    os.open, os.close = open_, close
    os.rename, os.remove = rename, remove
    locks._consume_if = posix_consume
    if real_flock is not None:
        locks._flock = flock
    try:
        if kind == "lock":
            locks._drop_stale_inode_posix(path, token)
        else:
            locks._mutex_acquire(path, "X")
        if gap == "after" or not second["done"]:
            second_holder()
    finally:
        os.open, os.close = real_open, real_close
        os.rename, os.remove = real_rename, real_remove
        locks._consume_if = real_consume
        if real_flock is not None:
            locks._flock = real_flock
    return state["max"], _leftover_names(path), flock_calls, planted["done"]


def test_three_reclaimers_posix_window_at_most_one_inside(tmp_path, monkeypatch):
    """#972: X reads a dead mutex, Y replaces it and enters, Z acquires if the name is emptied.

    POSIX consume is forced. fcntl is absent on Windows, so exclusion is the injectable
    `locks._flock` (monkeypatched below when the function exists). max_inside == 1, no `.take-*`.
    """
    max_inside, leftovers, flock_calls, planted = _posix_gap_case("mutex", "on-close", "rename")
    problems = []
    if not planted:
        problems.append("Y never replaced the dead mutex")
    if max_inside != 1:
        problems.append(f"max_inside={max_inside}")
    if leftovers:
        problems.append(f"leftover={leftovers}")
    if not flock_calls:
        problems.append("POSIX reclaim did not take locks._flock")
    assert problems == []


def test_posix_lock_gap_o_excl_at_most_one_holder(tmp_path, monkeypatch):
    """#972: a fresh lock is swapped in before POSIX takeover; a holder O_EXCLs if the name is empty.

    At most one holder, and no `.take-*` leftover. `locks._flock` is injectable because Windows has no fcntl.
    """
    max_inside, leftovers, flock_calls, planted = _posix_gap_case("lock", "on-close", "rename")
    problems = []
    if not planted:
        problems.append("fresh lock was not planted before takeover")
    if max_inside != 1:
        problems.append(f"holders={max_inside}")
    if leftovers:
        problems.append(f"leftover={leftovers}")
    if not flock_calls:
        problems.append("POSIX lock drop did not take locks._flock")
    assert problems == []


def _posix_gap_schedules(n, seed):
    import random
    rnd = random.Random(seed)
    kinds = ["mutex", "lock"]
    plants = ["on-close", "already"]
    gaps = ["rename", "remove", "after"]
    return [{"kind": rnd.choice(kinds), "plant": rnd.choice(plants), "gap": rnd.choice(gaps)}
            for _ in range(n)]


def test_probe_at_most_one_inside_posix_seed_972(tmp_path, monkeypatch):
    """#972: generated POSIX interleavings. At most one inside / one holder, N/N."""
    schedules = _posix_gap_schedules(16, 972)
    ok = 0
    for schedule in schedules:
        max_inside, _leftovers, _flock, _planted = _posix_gap_case(**schedule)
        if max_inside <= 1:
            ok += 1
    assert ok == len(schedules) == 16


def test_probe_no_take_leftover_posix_seed_972(tmp_path, monkeypatch):
    """#972: generated POSIX interleavings. No `.take-*` (or other aside) leftover, N/N."""
    schedules = _posix_gap_schedules(16, 973)
    ok = 0
    for schedule in schedules:
        _max_inside, leftovers, _flock, _planted = _posix_gap_case(**schedule)
        if leftovers == []:
            ok += 1
    assert ok == len(schedules) == 16


def _gap_racer_case(kind, monkeypatch, *, flock_works=True):
    """#972 review P1: a second reclaimer runs between X's inode re-check and X's unlink.

    kind="mutex": X takes over a dead mutex; in X's unlink gap W consumes the same dead inode and
    Y links a fresh mutex. Without exclusion X then unlinks Y's live mutex and links its own.
    kind="lock": X (mutex owner) drops a stale lock; in X's unlink gap X's mutex expires, W takes
    the mutex over and drops the same stale lock, H O_EXCLs a fresh lock. Without exclusion X then
    unlinks H's lock and K O_EXCLs a second one.
    POSIX consume is forced (fcntl is absent on Windows: `locks._flock` is the injectable seam).
    Returns (max_inside, leftovers).
    """
    import os
    import time
    path = _lock_file()
    _clear_lock_dir(path)
    mutex = path.with_name(f".{path.name}.mutex")
    _, posix_consume = _force_posix_file_consume()
    monkeypatch.setattr(locks, "_consume_if", posix_consume)
    monkeypatch.setattr(locks, "_drop_stale_inode", locks._drop_stale_inode_posix)
    monkeypatch.setattr(locks, "_sleep", lambda _s: None)
    if not flock_works:
        monkeypatch.setattr(locks, "_flock", lambda fd, op: None)
    now = time.time()
    inside = set()
    target = mutex if kind == "mutex" else path
    path.write_text(json.dumps({"pid": 999999999, "card": "dead", "token": "dead"}), encoding="utf-8")
    if kind == "mutex":
        mutex.write_text(json.dumps({"pid": 999999999, "until": now + 60, "token": "dead"}),
                         encoding="utf-8")
    else:
        mutex.write_text(json.dumps({"pid": os.getpid(), "until": now + 30, "token": "X"}),
                         encoding="utf-8")
    real_remove = os.remove
    fired = {"done": False}

    def o_excl(name):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return
        os.write(fd, json.dumps({"pid": os.getpid(), "until": now + 600, "token": name}).encode())
        os.close(fd)
        inside.add(name)

    def racer():
        if kind == "mutex":
            locks._consume_stale_mutex(mutex)
            if locks._mutex_acquire(path, "Y"):
                inside.add("Y")
            return
        mutex.write_text(json.dumps({"pid": os.getpid(), "until": now - 1, "token": "X"}),
                         encoding="utf-8")  # X stalled past _MUTEX_TTL_S
        if locks._reclaim(path, "W"):
            o_excl("H")

    def remove(file):
        if Path(file) == target and not fired["done"]:
            fired["done"] = True
            racer()
        return real_remove(file)

    monkeypatch.setattr(os, "remove", remove)
    try:
        if kind == "mutex":
            if locks._mutex_acquire(path, "X"):
                inside.add("X")
        elif locks._drop_stale_inode_posix(path, "X"):
            o_excl("K")
    finally:
        monkeypatch.setattr(os, "remove", real_remove)
    assert fired["done"], "X never reached the unlink gap"
    return len(inside), _leftover_names(path)


@pytest.mark.parametrize("kind", ["mutex", "lock"])
def test_second_reclaimer_in_unlink_gap_at_most_one_inside(kind, tmp_path, monkeypatch):
    """#972 review P1: W runs inside X's re-check -> unlink gap. At most one inside / holder."""
    assert _gap_racer_case(kind, monkeypatch) == (1, [])


@pytest.mark.parametrize("kind", ["mutex", "lock"])
def test_unlink_gap_witness_detects_missing_exclusion(kind, tmp_path, monkeypatch):
    """The gap witness is not vacuous: with `_flock` a no-op the same schedule gives two inside."""
    assert _gap_racer_case(kind, monkeypatch, flock_works=False)[0] == 2


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
    assert set(listed) == set(tools.LISTED + HOOK) | {"agr_exec_unsafe"}
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
    _, (res,) = run_calls([("agr_matid_check", {"scene": "live", "handles": [1]})], transport=lambda c, t: raw)
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
    assert sorted(names) == sorted(tools.LISTED + HOOK + (("agr_exec_unsafe",) if unsafe else ()))
    assert t["serverInfo"]["name"] == "agr-mcp"
    editing = {n for n, _row, _what, kind in tools.EDITS_080 if kind != "read"} | {"agr_op_apply"} | set(HOOK_EDITING)
    assert all(x["readOnlyHint"] for x in t["tools"] if x["name"] != "agr_exec_unsafe" and x["name"] not in editing)
    assert not any(x["readOnlyHint"] for x in t["tools"] if x["name"] in editing)


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


def test_failed_release_is_retried_then_reported(tmp_path, monkeypatch, capsys):
    """#895: a sharing violation on os.remove is retried a few times, then written to stderr."""
    import os
    pauses = []
    calls = []
    monkeypatch.setattr(locks, "_sleep", lambda delay: pauses.append(delay), raising=False)

    def sharing_violation(path):
        calls.append(path)
        raise PermissionError(32, "sharing violation")

    monkeypatch.setattr(os, "remove", sharing_violation)
    with locks.hold("blender-batch", "a", 900) as path:
        pass
    assert path.exists()
    assert len(calls) >= 3, f"release tried os.remove {len(calls)} time(s) and swallowed the error"
    assert pauses == [locks._RELEASE_PAUSE_S] * (len(calls) - 1)
    assert 0 < locks._RELEASE_PAUSE_S <= 0.25
    assert len(calls) == locks._RELEASE_ATTEMPTS
    err = capsys.readouterr().err
    assert "release failed" in err.lower()
    assert path.name in err


def test_probe_live_agr_mcp_holder_stale_iff_time_reaches_until(tmp_path, monkeypatch):
    """#895: a live agr-mcp holder is stale iff time >= until, including exactly at until."""
    import os
    t0 = 1_000_000.0
    clock = [t0]
    monkeypatch.setattr(locks, "time", types.SimpleNamespace(time=lambda: clock[0]))
    assert locks._alive(os.getpid())
    timeouts = [0, 0.5, 1, 30, 60, 90, 120, 121, 900, 1800, 3600, 7200]
    deltas = [-3600.0, -120.0, -1.0, -1e-6, 0.0, 1e-6, 1.0, 120.0, 3600.0]
    lock = tmp_path / "locks" / "agr-blender-batch.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    for timeout in timeouts:
        for delta in deltas:
            until = t0 + timeout + 120
            body = json.dumps({"card": "a", "pid": os.getpid(), "t": t0, "timeout": timeout,
                               "until": until, "owner": "agr-mcp", "token": "holder-token"})
            lock.write_text(body, encoding="utf-8")
            clock[0] = until + delta
            expect_stale = clock[0] >= until
            assert locks._stale(lock) is expect_stale
            if expect_stale:
                with locks.hold("blender-batch", "b", 60) as got:
                    assert json.loads(got.read_text(encoding="utf-8"))["card"] == "b"
                assert not lock.exists()
            else:
                with pytest.raises(locks.LockBusy):
                    with locks.hold("blender-batch", "b", 60):
                        pass
                assert lock.read_text(encoding="utf-8") == body
            n += 1
    assert n == len(timeouts) * len(deltas) == 108


def test_probe_dead_holder_is_stale_on_either_side_of_until(tmp_path, monkeypatch):
    """A dead holder pid is stale before and after `until`."""
    t0 = 1_000_000.0
    clock = [t0]
    monkeypatch.setattr(locks, "time", types.SimpleNamespace(time=lambda: clock[0]))
    monkeypatch.setattr(locks, "_alive", lambda pid: False)
    timeouts = [0, 1, 60, 900, 1800, 7200]
    deltas = [-3600.0, -1.0, 0.0, 1.0, 3600.0]
    lock = tmp_path / "locks" / "agr-blender-batch.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    for timeout in timeouts:
        for delta in deltas:
            until = t0 + timeout + 120
            lock.write_text(json.dumps({"card": "dead", "pid": 999_999_999, "t": t0, "timeout": timeout,
                                        "until": until, "owner": "agr-mcp", "token": "dead-token"}),
                            encoding="utf-8")
            clock[0] = until + delta
            assert locks._stale(lock) is True
            with locks.hold("blender-batch", "b", 60) as got:
                assert json.loads(got.read_text(encoding="utf-8"))["card"] == "b"
            assert not lock.exists()
            n += 1
    assert n == len(timeouts) * len(deltas) == 30


def test_probe_release_failures_are_retried_then_reported(tmp_path, monkeypatch, capsys):
    """Every OSError on release is retried, then reported only once the attempts are exhausted."""
    import os
    attempts = getattr(locks, "_RELEASE_ATTEMPTS", 1)
    assert isinstance(attempts, int) and attempts >= 3
    pause = locks._RELEASE_PAUSE_S
    assert 0 < pause <= 0.25
    real_remove = os.remove
    errors = [PermissionError(32, "sharing violation"), OSError(13, "permission denied"),
              BlockingIOError(11, "resource busy"), TimeoutError("file locked")]
    fail_counts = list(range(0, attempts + 3))
    n = 0
    for error in errors:
        for fail_count in fail_counts:
            calls = []
            pauses = []
            left = {"n": fail_count}

            def boom(path, error=error, calls=calls, left=left):
                calls.append(path)
                if left["n"] > 0:
                    left["n"] -= 1
                    raise error
                return real_remove(path)

            monkeypatch.setattr(os, "remove", boom)
            monkeypatch.setattr(locks, "_sleep", lambda delay, pauses=pauses: pauses.append(delay), raising=False)
            with locks.hold("max-live", "a", 30) as path:
                pass
            exhausted = fail_count >= attempts
            expect_calls = attempts if exhausted else fail_count + 1
            assert len(calls) == expect_calls
            assert pauses == [pause] * (expect_calls - 1)
            err = capsys.readouterr().err
            if exhausted:
                assert path.exists()
                assert "release failed" in err.lower() and path.name in err
                real_remove(path)
            else:
                assert not path.exists()
                assert "release failed" not in err.lower()
            n += 1
    assert n == len(errors) * len(fail_counts) == 28


def _zip_with_fbx(path: Path, count: int) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for i in range(count):
            archive.writestr(f"part_{i:02d}.fbx", b"synthetic")


def _lease(path, timeout: float) -> float:
    info = json.loads(path.read_text(encoding="utf-8"))
    return info["until"] - info["t"]


def test_package_validate_scene_lock_covers_two_fbx_readbacks(tmp_path, monkeypatch):
    """#951: a 2-FBX scene=true call keeps blender-batch busy at 721 s and at 1100 s.

    The second holder acquires only once the lease reaches 2*READBACK_TIMEOUT+120
    (the same `until` rule as every other agr-mcp lock: stale when time >= until).
    """
    pkg = tmp_path / "two.zip"
    _zip_with_fbx(pkg, 2)
    spec = tools.catalog()["agr_package_validate"]
    args = {"target": str(pkg), "scene": True}
    timeout = spec.timeout(args)
    assert timeout == 2 * tools.READBACK_TIMEOUT
    assert spec.host(args) == "blender-batch"
    t0 = 1_000_000.0
    clock = [t0]
    monkeypatch.setattr(locks, "time", types.SimpleNamespace(time=lambda: clock[0]))
    with locks.hold("blender-batch", "a", timeout) as path:
        assert _lease(path, timeout) == 2 * tools.READBACK_TIMEOUT + 120
        for elapsed in (721, 1100, tools.READBACK_TIMEOUT + 120):
            clock[0] = t0 + elapsed
            with pytest.raises(locks.LockBusy):
                with locks.hold("blender-batch", "b", tools.READBACK_TIMEOUT):
                    pass
            assert json.loads(path.read_text(encoding="utf-8"))["card"] == "a"
        clock[0] = t0 + 2 * tools.READBACK_TIMEOUT + 120
        with locks.hold("blender-batch", "b", tools.READBACK_TIMEOUT) as taken:
            assert json.loads(taken.read_text(encoding="utf-8"))["card"] == "b"


def test_probe_package_validate_lease_covers_every_fbx_count(tmp_path, monkeypatch):
    """#951: for N = 1..21 the scene lock lease is at least N*READBACK_TIMEOUT+120."""
    spec = tools.catalog()["agr_package_validate"]
    t0 = 1_000_000.0
    clock = [t0]
    monkeypatch.setattr(locks, "time", types.SimpleNamespace(time=lambda: clock[0]))
    seen = 0
    for n in range(1, 22):
        pkg = tmp_path / f"n{n}.zip"
        _zip_with_fbx(pkg, n)
        timeout = spec.timeout({"target": str(pkg), "scene": True})
        assert timeout >= n * tools.READBACK_TIMEOUT
        with locks.hold("blender-batch", "a", timeout) as path:
            assert _lease(path, timeout) >= n * tools.READBACK_TIMEOUT + 120
            clock[0] = t0 + n * tools.READBACK_TIMEOUT + 120 - 1e-6
            with pytest.raises(locks.LockBusy):
                with locks.hold("blender-batch", "b", 60):
                    pass
        clock[0] = t0
        seen += 1
    assert seen == 21


def test_package_validate_scene_lock_fails_closed(tmp_path, monkeypatch):
    """Missing, empty, partial, unsupported and non-finite inputs never take a one-readback lease.

    A count that cannot be read uses the NPM upper bound (21). A readable package with
    no FBX is still at least one readback. Exactly at the one-readback threshold the
    second holder stays busy.
    """
    spec = tools.catalog()["agr_package_validate"]
    upper = tools.PACKAGE_SCENE_FBX_UPPER
    from twinqa.profiles import load_profiles
    assert upper == load_profiles().profile("npm")["archive"]["fbx_total"]["max"] == 21
    assert upper >= 1
    undetermined = [
        {"target": str(tmp_path / "missing.zip"), "scene": True},
        {"target": "", "scene": True},
        {"target": str(tmp_path), "scene": True},  # directory, not a file
    ]
    empty_zip = tmp_path / "empty.zip"
    _zip_with_fbx(empty_zip, 0)
    partial = tmp_path / "partial.zip"
    partial.write_bytes(b"PK\x03\x04truncated")
    unsupported = []
    for suffix in (".png", ".geojson", ".txt", ".fbx.bak"):
        path = tmp_path / f"bad{suffix}"
        path.write_bytes(b"not-a-package")
        unsupported.append({"target": str(path), "scene": True})
    single = tmp_path / "one.FBX"
    single.write_bytes(b"Kaydara FBX Binary")
    offline = tmp_path / "offline.zip"
    _zip_with_fbx(offline, 2)

    t0 = 1_000_000.0
    clock = [t0]
    monkeypatch.setattr(locks, "time", types.SimpleNamespace(time=lambda: clock[0]))

    def assert_busy_past_one_readback(timeout: float) -> None:
        assert timeout >= tools.READBACK_TIMEOUT
        assert math.isfinite(timeout)
        with locks.hold("blender-batch", "a", timeout) as path:
            assert _lease(path, timeout) >= tools.READBACK_TIMEOUT + 120
            clock[0] = t0 + tools.READBACK_TIMEOUT + 120  # exactly the old one-readback lease
            if timeout == tools.READBACK_TIMEOUT:
                with locks.hold("blender-batch", "b", 60) as taken:
                    assert json.loads(taken.read_text(encoding="utf-8"))["card"] == "b"
            else:
                with pytest.raises(locks.LockBusy):
                    with locks.hold("blender-batch", "b", 60):
                        pass
                assert json.loads(path.read_text(encoding="utf-8"))["card"] == "a"
        clock[0] = t0

    for args in undetermined + unsupported:
        timeout = spec.timeout(args)
        assert timeout == upper * tools.READBACK_TIMEOUT
        assert_busy_past_one_readback(timeout)
    # readable, zero FBX: never fewer than one readback, not the 21-wide bound
    zero = spec.timeout({"target": str(empty_zip), "scene": True})
    assert zero == tools.READBACK_TIMEOUT
    assert_busy_past_one_readback(zero)
    # one FBX file, any case of the suffix
    one = spec.timeout({"target": str(single), "scene": True})
    assert one == tools.READBACK_TIMEOUT
    assert_busy_past_one_readback(one)
    # more than the profile max is still the real count
    big = tmp_path / "big.zip"
    _zip_with_fbx(big, upper + 1)
    over = spec.timeout({"target": str(big), "scene": True})
    assert over == (upper + 1) * tools.READBACK_TIMEOUT
    assert_busy_past_one_readback(over)
    # partial / unreadable zip cannot be counted
    broken = spec.timeout({"target": str(partial), "scene": True})
    assert broken == upper * tools.READBACK_TIMEOUT
    assert_busy_past_one_readback(broken)
    # scene false keeps the previous single timeout and does not lock blender
    assert spec.timeout({"target": str(offline), "scene": False}) == float(tools.READBACK_TIMEOUT)
    assert spec.timeout({"target": str(offline)}) == float(tools.READBACK_TIMEOUT)
    assert spec.host({"target": str(offline), "scene": False}) == "offline"
    for bad in (
        {"target": str(offline), "scene": True, "ground_area_m2": float("nan")},
        {"target": str(offline), "scene": True, "ground_area_m2": float("inf")},
        {"target": str(offline), "scene": True, "ground_area_m2": float("-inf")},
        {"target": str(offline), "scene": True, "footprint_holes": [[float("nan"), 0.0]]},
    ):
        with pytest.raises(ValueError):
            spec.timeout(bad)


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


# ---- #1024 PR A: runtime pin is a minimum + selection contract (mcp-review §2.4.1-2.4.2) -------------------------
RUNTIME_090_FAKE = FAKE_RUNTIME.replace('"0.5.0"', '"0.9.0"') + '''
from pymxs import runtime as _rt
def _plan(tool, row, nodes):
    CALLS.append((tool, row, [n.handle for n in nodes]))
    return {"schema": 1, "tool": row, "status": "pass", "objects": [],
            "plan": {"mode": "preview", "done": [], "skipped": [], "ambiguous": []}}
def checks_070(tool, nodes=None, select=True):
    CALLS.append(("checks_070", tool, [n.handle for n in nodes], select))
    if select:
        _rt.clearSelection(); _rt.select(nodes)
    return {"schema": 1, "tool": tool, "status": "pass", "objects": []}
def edits_080(tool, mode, preview=None, nodes=None, options=None): return _plan("edits_080", tool, nodes)
def edits_090(tool, mode, preview=None, nodes=None, options=None):
    _rt.clearSelection(); _rt.select(nodes)  # a `select` row (light.check) selecting in the UI glue
    return _plan("edits_090", tool, nodes)
'''


def install(fake, version, text):
    root = fake.root.parent / ("AGRTools-" + version)
    root.mkdir(exist_ok=True)
    (root / "runtime.py").write_text(text, encoding="utf-8")
    return root


ONE_PER_GROUP = ["agr_xview_check", "agr_matid_check", "agr_texel_readout", "agr_scene_census", "agr_qa_preflight",
                 "agr_scene_missing_maps", "agr_qa_package", "agr_udim_slots", "agr_light_check"]


def test_runtime_090_serves_every_max_group(fake_max, monkeypatch):
    """RED on the exact pin: with only 0.9.0 installed, 0.5/0.7/0.8 tools answered `version != expected`."""
    root = install(fake_max, "0.9.0", RUNTIME_090_FAKE)
    monkeypatch.setenv("AGR_TOOLS_ROOT", str(root))
    _, results = run_calls([(n, {"scene": "live", "handles": [1]}) for n in ONE_PER_GROUP],
                           transport=fake_max.transport)
    for name, res in zip(ONE_PER_GROUP, results):
        ok(res)
    assert sys.modules["runtime"].VERSION == "0.9.0"


def test_every_max_tool_of_the_catalogue_needs_at_most_runtime_090():
    """v1 Max tools (47) by tool name; the v2 tools by plan row (ROUTES), all served by an installed 0.9.0, except
    the 1.0 conveyor rows (edits_100), which need the 1.0 runtime (RUNTIME_100 = package 1.0.1)."""
    names = [n for n, s in tools.catalog().items() if s.host({}) == "max-live" and n in tools.PHASE0]
    assert len(names) == 47
    for n in names:
        minimum, function = max_bridge.requirement(n)
        assert max_bridge.version_key(minimum) <= (0, 9, 0) and function, n
    for row, (group, _key, minimum, function) in max_bridge.ROUTES.items():
        top = (1, 0, 1) if group == "e100" else (0, 9, 0)
        assert max_bridge.version_key(minimum) <= top and function, row
    assert {r for r, v in max_bridge.ROUTES.items() if v[2] == max_bridge.RUNTIME_100} == set(max_bridge.ROWS_100)


def test_default_root_is_the_newest_install_not_a_folder_per_group(fake_max, monkeypatch):
    """RED: the old default was userScripts/AGRTools-<group version>, i.e. AGRTools-0.7.0 for checks_070."""
    install(fake_max, "0.9.0", RUNTIME_090_FAKE)
    (fake_max.root.parent / "AGRTools-0.10.0").mkdir()  # newer folder without runtime.py is skipped
    monkeypatch.delenv("AGR_TOOLS_ROOT", raising=False)
    _, (res,) = run_calls([("agr_scene_census", {"scene": "live", "handles": [1]})], transport=fake_max.transport)
    ok(res)
    assert Path(sys.modules["runtime"].__file__).parent.name == "AGRTools-0.9.0"
    assert max_bridge.default_root(str(fake_max.root.parent), "0.9.1") is None


@pytest.mark.parametrize("version,body,needle", [
    ("0.6.9", "", "< minimum 0.7.0"),
    ("0.9.0", "", "has no checks_070"),
    ("0.9", "", "< minimum 0.7.0"),
])
def test_runtime_below_minimum_or_without_entry_is_version_mismatch(fake_max, monkeypatch, version, body, needle):
    root = install(fake_max, "x", 'VERSION = "{}"\n{}'.format(version, body))
    monkeypatch.setenv("AGR_TOOLS_ROOT", str(root))
    _, (res,) = run_calls([("agr_scene_census", {"scene": "live", "handles": [1]})], transport=fake_max.transport)
    assert res.isError and "version_mismatch" in res.content[0].text and needle in res.content[0].text


@pytest.mark.parametrize("tool", ["agr_xview_check", "agr_scene_census", "agr_qa_package", "agr_udim_slots"])
@pytest.mark.parametrize("args", [{"scene": "live"}, {"scene": "live", "handles": []}])
def test_empty_handles_is_handles_required_and_max_is_not_called(fake_max, tmp_path, tool, args):
    """RED: empty handles went to runtime as nodes=None = the user's selection or all geometry (§2.4.2)."""
    _, (res,) = run_calls([(tool, args)], transport=fake_max.transport)
    assert res.isError and "handles_required" in res.content[0].text
    assert fake_max.sent == []
    with pytest.raises(max_bridge.BridgeError, match="handles_required"):
        max_bridge.run(tool, str(fake_max.root), args)


def test_scope_selection_takes_the_selection_explicitly_and_conflicts_with_handles(fake_max):
    _, (res, bad) = run_calls([("agr_xview_check", {"scene": "live", "scope": "selection"}),
                               ("agr_xview_check", {"scene": "live", "scope": "selection", "handles": [1]})],
                              transport=fake_max.transport)
    assert ok(res)["objects"][0]["handle"] == 2  # fixture selection = node 2, passed as a list, never None
    assert sys.modules["runtime"].CALLS[-1] == ("xview", [2])
    assert bad.isError and "target_conflict" in bad.content[0].text


def test_checks_070_get_select_false_and_selection_is_restored(fake_max, monkeypatch):
    """RED: checks_070 ran with the runtime default select=True and selected the nodes with findings."""
    root = install(fake_max, "0.9.0", RUNTIME_090_FAKE)
    monkeypatch.setenv("AGR_TOOLS_ROOT", str(root))
    _, (census, light) = run_calls([("agr_scene_census", {"scene": "live", "handles": [1, 3]}),
                                    ("agr_light_check", {"scene": "live", "handles": [1, 3]})],
                                   transport=fake_max.transport)
    ok(census), ok(light)
    assert ("checks_070", "census", [1, 3], False) in sys.modules["runtime"].CALLS
    assert [n.handle for n in fake_max.rt.selection] == [2], "selection before the call must survive"
    out = json.loads(max_bridge.call("agr_light_check", str(root).encode().hex(),
                                     json.dumps({"scene": "live", "handles": [1]}).encode().hex()))
    assert out["ok"] and out["selection"] == {"before_count": 1, "restored": True, "scope": "handles"}


def test_selection_that_cannot_be_restored_is_selection_changed(fake_max, monkeypatch):
    root = install(fake_max, "0.9.0", RUNTIME_090_FAKE)
    monkeypatch.setenv("AGR_TOOLS_ROOT", str(root))
    fake_max.rt.select = lambda ns: None  # Max refuses to reselect
    _, (res,) = run_calls([("agr_light_check", {"scene": "live", "handles": [1]})], transport=fake_max.transport)
    assert res.isError and "selection_changed" in res.content[0].text