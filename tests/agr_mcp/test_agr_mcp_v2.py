"""new-case: agr-mcp v2 (#1024 branch 0): catalogue generated from docs/plans/agr-tools-suite.json, envelope v2,
server-held previews (preview_id, binding, stale_preview), needs_human for apply of 0.9/1.0 rows, one panel/MCP
journal line per call, machine error codes, ObjRef targets. Synthetic data only: fake pymxs + a fake installed
runtime on the real edit_core / journal_core contract, executed by an in-process "pipe"; one test uses the real
adapters/max/agr_tools/runtime.py (1.0 stub rows).
"""
import copy
import importlib.util
import json
import os
import re
import sys
import types
from pathlib import Path

import anyio
import jsonschema
import pytest
from mcp.shared.memory import create_connected_server_and_client_session as connect

from agr_mcp import (ERROR_CODES, TOOL_SCHEMA_VERSION, catalog, envelope, ops_d108, preview_store, server,
                     spec as spec_mod, tools)
from agr_mcp.max_side import max_bridge

ROOT = Path(__file__).resolve().parents[2]
AGR = ROOT / "adapters" / "max" / "agr_tools"
PLAN = json.loads((ROOT / "docs/plans/agr-tools-suite.json").read_text(encoding="utf-8"))
NEW_15 = ["project.passport", "source.intake", "body.prepare", "win.place", "win.generate", "body.capsules",
          "body.roof", "mat.table", "mat.tiles", "vpm.build", "npm.build", "npm.to_vpm", "pack.deliver",
          "agent.request", "agent.accept"]  # SPLIT.md item 2


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("AGR_MCP_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setenv("AGR_MCP_AUDIT", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("AGR_JOURNAL_DIR", str(tmp_path / "journal"))
    monkeypatch.setenv("AGR_MCP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AGR_MCP_CARD", "test-1024")
    for k in ("AGR_MCP_UNSAFE", "AGR_MCP_MAX_PID", "MCP_MAX_PID", "MCP_MAX_PIPE", "AGR_MCP_INLINE_MAX",
              "AGR_MCP_PREVIEW_STORE", "AGR_MCP_PREVIEW_TTL"):
        monkeypatch.delenv(k, raising=False)


def journal_lines(tmp_path):
    out = []
    for p in sorted((tmp_path / "journal").glob("*.jsonl")):
        out += [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()]
    return out


def run_calls(calls, transport=None, store=None, env=None):
    async def main():
        srv = server.build_server(env=env, max_transport=transport, store=store)
        async with connect(srv) as client:
            listed = {t.name: t for t in (await client.list_tools()).tools}
            return listed, [await client.call_tool(n, a) for n, a in calls]
    return anyio.run(main)


def ok2(res):
    assert not res.isError, res.content[0].text
    sc = res.structuredContent
    assert sc["tool_schema_version"] == TOOL_SCHEMA_VERSION == 2
    return sc


def err(res, code):
    assert res.isError, res.structuredContent
    sc = res.structuredContent
    assert sc["status"] == "error" and sc["error_code"] == code, (sc, res.content[0].text)
    return sc


# ---- fake installed runtime on the real edit_core / journal_core contract -----------------------------------------
FAKE_RUNTIME = '''
import importlib.util, os, sys
VERSION = "0.9.0"
CALLS = []
STATE = {"scene": "s1"}
NOT_IMPLEMENTED = set()
def _load(name, path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod; spec.loader.exec_module(mod)
    return sys.modules[name]
EC = _load("fake_rt_edit_core", AGR + "/edit_core.py")
JC = _load("fake_rt_journal_core", AGR + "/journal_core.py")
def _objs(row, nodes):
    return [EC.entry(n.handle, n.name, [EC.finding("f_" + row.replace(".", "_"), [1], "synthetic")]
                     if n.handle % 2 else []) for n in nodes]
def _edits(group, row, mode, preview, nodes, options, actor):
    CALLS.append((group, row, mode, [n.handle for n in nodes], actor, options))
    status = "error"
    try:
        if group == "100" and mode == "apply" and actor != "panel":
            raise ValueError("needs_human: apply of " + row + " is confirmed only by a button in the panel/dock")
        if row in NOT_IMPLEMENTED:
            rep = EC.not_implemented(row, mode, "#1024")
        elif mode == "apply":
            EC.check_preview(row, preview)
            EC.require_current(preview, STATE)
            rep = EC.report(row, "apply", _objs(row, nodes), done=[{"item": "copy", "of": row}])
        else:
            rep = EC.report(row, "preview", _objs(row, nodes), done=[{"item": "copy", "of": row}],
                            state_hash=EC.fingerprint(STATE))
        status = rep["status"]
        return rep
    finally:
        from pymxs import runtime as rt  # like runtime._scene_doc
        doc = os.path.join(str(rt.maxFilePath), str(rt.maxFileName)) if str(rt.maxFileName) else "untitled"
        if actor is not None:  # None: an old runtime (no actor, no journal hook)
            JC.append(JC.record(row, mode, status, {}, None, 0.0, actor, doc), doc)
def edits_080(tool, mode, preview=None, nodes=None, options=None, actor="panel"):
    return _edits("080", tool, mode, preview, nodes, options, actor)
def edits_090(tool, mode, preview=None, nodes=None, options=None, actor="panel"):
    return _edits("090", tool, mode, preview, nodes, options, actor)
def edits_100(tool, mode, preview=None, nodes=None, options=None, actor="panel"):
    return _edits("100", tool, mode, preview, nodes, options, actor)
def checks_070(tool, nodes=None, select=True):
    CALLS.append(("070", tool, [n.handle for n in nodes], select))
    objs = [{"handle": n.handle, "name": n.name, "findings": [{"code": "c_" + tool, "ids": [1], "detail": "d"}]}
            for n in nodes]
    return {"schema": 1, "tool": tool, "status": "fail", "objects": objs}
def checks_050(tool, nodes=None, path=None):
    CALLS.append(("050", tool, [n.handle for n in nodes], path))
    return {"schema": 1, "tool": tool, "status": "pass", "objects": []}
def _rep(tool, nodes):
    CALLS.append(("fn", tool, [n.handle for n in nodes]))
    return {"schema": 1, "tool": tool, "status": "pass", "objects": [{"handle": n.handle, "name": n.name,
            "findings": []} for n in nodes]}
def xview(nodes=None): return _rep("xview", nodes)
def matid(nodes=None): return _rep("matid", nodes)
def texel_preview(nodes=None): return _rep("texel", nodes)
'''


class FakeNode:
    def __init__(self, handle):
        self.handle, self.name = handle, f"Box{handle:03d}"


@pytest.fixture
def fake_max(tmp_path, monkeypatch):
    root = tmp_path / "AGRTools-0.9.0"
    root.mkdir()
    (root / "runtime.py").write_text("AGR = {!r}\n".format(str(AGR).replace("\\", "/")) + FAKE_RUNTIME,
                                     encoding="utf-8")
    nodes = {h: FakeNode(h) for h in (1, 2, 3)}
    rt = types.SimpleNamespace(
        maxFilePath="C:/scenes/", maxFileName="synthetic.max", name=lambda s: s, getDir=lambda _n: str(tmp_path),
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
        m = re.search(r'b\.call "(\w+)" "([0-9a-f]*)" "([0-9a-f]*)"', code)
        assert m, code
        sent.append((m.group(1), json.loads(bytes.fromhex(m.group(3)))))
        return max_bridge.call(*m.groups())
    yield types.SimpleNamespace(root=root, nodes=nodes, transport=transport, sent=sent, rt=rt,
                                doc=os.path.join("C:/scenes/", "synthetic.max"))
    sys.path[:] = [p for p in sys.path if not (p and Path(p).is_relative_to(tmp_path))]
    for k in [k for k in sys.modules if k.startswith("fake_rt_")]:
        del sys.modules[k]


def rtmod():
    return sys.modules["runtime"]


# ---- 1. catalogue from the plan -------------------------------------------------------------------------------------
def _independent_rules():
    """The plan rules recomputed here from the JSON, independent of catalog.py."""
    rel = {v["version"] for v in PLAN["versions"] if v["status"] == "done"}
    blocks = {b["id"] for b in PLAN["blocks"]}
    stage = [r["id"] for r in PLAN["rows"] if r["version"] == "1.0" and r["fate"] == "stage" and r["mcp"] == "yes"
             and r["id"].split(".")[0] not in blocks]
    checks = {r["id"] for r in PLAN["rows"] if r["mcp"] == "yes" and r["mode"] in ("read", "select")
              and (r["version"] in rel or (r["version"] == "1.0" and r["fate"] == "stage"))}
    ops = {r["id"] for r in PLAN["rows"] if r["mcp"] == "yes" and r["mode"] in ("copy", "undo", "file", "agent")
           and r["id"] not in stage and (r["version"] in ("0.8", "0.9") or (r["version"] == "1.0"
                                                                          and r["fate"] == "stage"))}
    apply = {r["id"] for r in PLAN["rows"] if r["version"] == "0.8" and r["mode"] in ("copy", "undo", "file")}
    return stage, checks, ops, apply


def test_catalogue_is_generated_from_the_plan():
    """RED on the v1 code: no stage tools, no agr_check_run / agr_op_preview / agr_op_apply."""
    stage, checks, ops, apply = _independent_rules()
    assert sorted(stage) == sorted(NEW_15)
    big = {s["big_button"] for s in PLAN["stages"]}
    assert big <= set(stage), "every big stage button has its own tool"
    cat = tools.catalog()
    for row in NEW_15:
        name = "agr_" + row.replace(".", "_")
        s = cat[name]
        assert s.schema == 2 and s.row == row and s.read_only and not s.destructive, name
        assert "preview only" in s.description
        assert "mode" not in s.input["properties"] and "preview" not in s.input["properties"]
    assert set(cat["agr_check_run"].input["properties"]["check_ids"]["items"]["enum"]) == checks
    assert set(cat["agr_op_preview"].input["properties"]["op"]["enum"]) == ops
    assert set(catalog.apply_ids(PLAN)) == apply == set(max_bridge.APPLY_OVER_MCP)
    assert len(checks) == 38 and len(ops) == 32 and len(apply) == 11
    hook = {x.name for x in ops_d108.register({})}  # branch U's tools (empty with the stub)
    assert set(tools.LISTED) | hook == set(cat) and len(cat) == 52 + 15 + 3 + len(hook)
    for n in tools.PHASE0:
        assert "Deprecated" in cat[n].description, n
    assert not cat["agr_op_apply"].read_only and set(cat["agr_op_apply"].input["properties"]) == {
        "preview_id", "idempotency_key"}


def test_bridge_routes_equal_the_runtime_tables():
    sys.path.insert(0, str(AGR))
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("agr_v2_runtime_tables", AGR / "runtime.py")
        rt = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rt)
    finally:
        sys.path.remove(str(AGR))
    assert list(max_bridge.ROWS_100) == list(rt.EDITS_100)
    assert set(max_bridge.READ_100) == set(rt.READ_100) and set(max_bridge.READ_090) == set(rt.READ_090)
    assert set(max_bridge.READ_080) == set(rt.READ_080)
    assert set(max_bridge.ROWS_050.values()) == set(rt.CHECKS_050)
    assert set(max_bridge.ROWS_070.values()) == set(rt.CHECKS_070)
    assert {tools._ROW_070[n] for n, _ in tools.CHECKS_070} == set(max_bridge.ROWS_070)


def test_plan_row_without_a_route_fails_the_build():
    plan = copy.deepcopy(PLAN)
    plan["rows"].append(dict(plan["rows"][0], id="qa.unrouted", mode="read", mcp="yes", version="0.9"))
    with pytest.raises(RuntimeError, match="qa.unrouted"):
        catalog.specs(plan)


def test_ops_d108_hook_adds_specs_without_editing_tools(monkeypatch):
    extra = spec_mod.Spec("agr_d108_keep", "D108 keep (branch U)", {"type": "object"}, {"type": "object"},
                          lambda a: {"ok": 1}, lambda a: "offline", schema=2)
    own = ops_d108.register({})  # [] with the stub; branch U's tools after it lands
    assert all(isinstance(x, spec_mod.Spec) for x in own) and len({x.name for x in own}) == len(own)
    monkeypatch.setattr(ops_d108, "register", lambda cat: [extra])
    assert tools.catalog()["agr_d108_keep"] is extra
    monkeypatch.setattr(ops_d108, "register", lambda cat: [dataclass_copy(extra, "agr_check_run")])
    with pytest.raises(RuntimeError, match="duplicate"):
        tools.catalog()


def dataclass_copy(s, name):
    import dataclasses
    return dataclasses.replace(s, name=name)


# ---- 2. envelope v2 -------------------------------------------------------------------------------------------------
def test_check_run_answers_envelope_v2_with_objref_findings(fake_max, tmp_path):
    """RED: agr_check_run does not exist; v1 answers carried only {tool_schema_version: 1, server_version, result}."""
    _, (res,) = run_calls([("agr_check_run", {"scene": "live", "handles": [1, 3],
                                              "check_ids": ["scene.census", "udim.slots", "qa.xview"]})],
                          transport=fake_max.transport)
    sc = ok2(res)
    assert set(sc) >= {"tool_schema_version", "server_version", "tool", "status", "summary", "counts",
                       "findings_top", "truncated", "report_uri", "next_actions", "result"}
    assert sc["status"] == "fail" and sc["truncated"] is False and sc["report_uri"] is None
    assert res.content[0].text == sc["summary"] and len(sc["summary"].splitlines()) <= 10
    assert set(sc["result"]["checks"]) == {"scene.census", "udim.slots", "qa.xview"}
    assert sc["counts"]["checks"] == 3 and sc["counts"]["findings"] == len(sc["findings_top"]) == 4
    cc = catalog.contract()
    for f in sc["findings_top"]:
        assert cc.check_ref(f["ref"]) == {"host": "max", "doc": fake_max.doc, "handle": f["handle"],
                                          "name": f["object"]}
    assert ("070", "census", [1, 3], False) in rtmod().CALLS  # select=False, explicit nodes
    assert [n.handle for n in fake_max.rt.selection] == [2]


def test_envelope_truncates_findings_and_stores_the_report(tmp_path, monkeypatch):
    result = {"schema": 1, "tool": "x", "status": "fail",
              "objects": [{"handle": h, "name": "N%d" % h, "findings": [{"code": "c", "ids": [1], "detail": "d"}]}
                          for h in range(1, 51)]}
    env = envelope.build("agr_check_run", result, schema=2, meta={"doc": "C:/s.max"})
    assert len(env["findings_top"]) == envelope.FINDINGS_TOP == 20 and env["truncated"] is True
    assert env["counts"] == {"findings": 50, "objects": 50} and env["result"] == result
    path = envelope.report_path(env["report_uri"])
    assert path.is_relative_to(tmp_path / "data") and json.loads(path.read_text()) == result
    assert env["report_uri"] == "agr://report/" + envelope.sha256(result)
    assert len(env["summary"].splitlines()) <= 10 and env["next_actions"]
    jsonschema.validate(env, envelope.schema({"type": "object"}, v1=False))
    monkeypatch.setenv("AGR_MCP_INLINE_MAX", "100")
    v2 = envelope.build("agr_check_run", result, schema=2)
    v1 = envelope.build("agr_xview_check", result, schema=1)
    assert "result" not in v2 and v2["truncated"] and v2["report_uri"]
    assert v1["result"] == result, "a deprecated v1 tool always keeps its full result"
    small = envelope.build("agr_mesh_names", [{"name": "n", "status": "pass", "observed": "a", "expected": "a"}])
    assert small["status"] == "ok" and small["truncated"] is False and small["report_uri"] is None


def test_v1_tools_answer_the_v2_envelope_with_their_result():
    """RED: v1 answered tool_schema_version 1 with only server_version + result."""
    args = {"names": ["SM_Vatutino_Ground", "bad name"], "kind": "vpm", "role": "ground",
            "fbx_stem": "SM_Vatutino_Ground", "limit": 254, "src": "synthetic"}
    _, (res,) = run_calls([("agr_mesh_names", args)])
    sc = ok2(res)
    assert json.loads(res.content[0].text) == sc, "v1: content stays the JSON of the envelope"
    from twinqa.naming import mesh_name_findings
    assert sc["result"] == tools.jsonable(mesh_name_findings(**args))
    assert sc["status"] in ("fail", "ok") and sc["counts"]["items"] == len(sc["result"])


# ---- 3. preview held by the server ----------------------------------------------------------------------------------
def test_preview_id_is_bound_and_apply_takes_only_it(fake_max, tmp_path):
    """RED: no agr_op_preview / agr_op_apply; v1 apply took the whole preview report from the agent."""
    store = preview_store.PreviewStore()
    _, (pre,) = run_calls([("agr_op_preview", {"scene": "live", "handles": [1], "op": "model.triangulate",
                                               "options": {"a": 1}})], fake_max.transport, store)
    sc = ok2(pre)
    report = sc["result"]
    pid = sc["preview_id"]
    assert pid == envelope.sha256(report) and sc["next_actions"] == ["agr_op_apply(preview_id='{}')".format(pid)]
    held = store.get(pid, {})
    assert held.binding == {"host": "max-live", "instance": None, "doc": fake_max.doc, "runtime_version": "0.9.0",
                            "state_hash": report["plan"]["state_hash"], "op": "model.triangulate"}
    assert held.targets == {"scene": "live", "handles": [1]}
    _, (app, again) = run_calls([("agr_op_apply", {"preview_id": pid}), ("agr_op_apply", {"preview_id": pid})],
                                fake_max.transport, store)
    out = ok2(app)
    assert out["result"]["plan"]["mode"] == "apply" and out["preview_id"] == pid
    assert ("080", "model.triangulate", "apply", [1], "mcp", None) in rtmod().CALLS
    assert fake_max.sent[-1][1]["preview"] == report and fake_max.sent[-1][1]["expect"] == {
        "doc": fake_max.doc, "runtime_version": "0.9.0"}
    err(again, "stale_preview")
    with pytest.raises(jsonschema.ValidationError):  # apply takes only preview_id (+ idempotency_key)
        jsonschema.validate({"preview_id": pid, "preview": report}, tools.catalog()["agr_op_apply"].input)


def _held(fake_max, store, row="model.triangulate"):
    _, (pre,) = run_calls([("agr_op_preview", {"scene": "live", "handles": [1], "op": row})], fake_max.transport,
                          store)
    return ok2(pre)["preview_id"]


def test_stale_preview_on_every_binding_change(fake_max, monkeypatch):
    clock = [1000.0]
    store = preview_store.PreviewStore(ttl=60, clock=lambda: clock[0])
    # unknown id
    _, (res,) = run_calls([("agr_op_apply", {"preview_id": "0" * 64})], fake_max.transport, store)
    err(res, "stale_preview")
    # TTL
    pid = _held(fake_max, store)
    clock[0] += 61
    _, (res,) = run_calls([("agr_op_apply", {"preview_id": pid})], fake_max.transport, store)
    assert "older than" in err(res, "stale_preview")["error"]
    # another Max instance
    clock[0] = 1000.0
    pid = _held(fake_max, store)
    monkeypatch.setenv("AGR_MCP_MAX_PID", "4242")
    _, (res,) = run_calls([("agr_op_apply", {"preview_id": pid})], fake_max.transport, store)
    assert "instance" in err(res, "stale_preview")["error"]
    monkeypatch.delenv("AGR_MCP_MAX_PID")
    # another document open in Max
    pid = _held(fake_max, store)
    fake_max.rt.maxFileName = "other.max"
    _, (res,) = run_calls([("agr_op_apply", {"preview_id": pid})], fake_max.transport, store)
    assert "document changed" in err(res, "stale_preview")["error"]
    fake_max.rt.maxFileName = "synthetic.max"
    # runtime replaced
    pid = _held(fake_max, store)
    rtmod().VERSION = "0.9.1"
    _, (res,) = run_calls([("agr_op_apply", {"preview_id": pid})], fake_max.transport, store)
    assert "runtime changed" in err(res, "stale_preview")["error"]
    rtmod().VERSION = "0.9.0"
    # scene state changed (runtime edit_core.require_current -> StalePreview)
    pid = _held(fake_max, store)
    rtmod().STATE["scene"] = "s2"
    _, (res,) = run_calls([("agr_op_apply", {"preview_id": pid})], fake_max.transport, store)
    assert "scene changed" in err(res, "stale_preview")["error"]
    applied = [c for c in rtmod().CALLS if c[2] == "apply"]
    assert len(applied) == 1, "only the stale-state apply reached the runtime (and was refused there)"


def test_idempotency_key_replays_and_conflicts(fake_max):
    store = preview_store.PreviewStore()
    pid = _held(fake_max, store)
    pid2 = _held(fake_max, store, "tex.placeholders")
    _, (a, b, c) = run_calls([("agr_op_apply", {"preview_id": pid, "idempotency_key": "k1"}),
                              ("agr_op_apply", {"preview_id": pid, "idempotency_key": "k1"}),
                              ("agr_op_apply", {"preview_id": pid2, "idempotency_key": "k1"})],
                             fake_max.transport, store)
    assert ok2(a)["result"] == ok2(b)["result"]
    assert sum(1 for x in rtmod().CALLS if x[2] == "apply") == 1, "a replay must not apply twice"
    err(c, "idempotency_conflict")


def test_file_store_survives_a_server_restart(fake_max, tmp_path):
    pid = _held(fake_max, preview_store.PreviewStore(persist=True))
    assert (tmp_path / "data" / "previews" / (pid + ".json")).is_file()
    _, (res,) = run_calls([("agr_op_apply", {"preview_id": pid})], fake_max.transport,
                          preview_store.PreviewStore(persist=True))
    ok2(res)
    assert not (tmp_path / "data" / "previews" / (pid + ".json")).exists()


# ---- 4. needs_human --------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("call", [("agr_op_preview", {"op": "model.glass_planes"}),  # 1.0 small row
                                  ("agr_op_preview", {"op": "place.replace"}),  # 0.9 row
                                  ("agr_win_place", {}),  # 1.0 stage button
                                  ("agr_agent_request", {})])
def test_apply_of_a_09_or_10_row_is_needs_human(fake_max, call):
    """RED: these tools do not exist; v1 had no apply route that refuses with needs_human."""
    store = preview_store.PreviewStore()
    name, extra = call
    _, (pre,) = run_calls([(name, dict({"scene": "live", "handles": [1, 3]}, **extra))], fake_max.transport, store)
    sc = ok2(pre)
    row = sc["result"]["tool"]
    assert sc["preview_id"] and sc["next_actions"][0].startswith("needs_human:")
    assert any(c[1:5] == (row, "preview", [1, 3], "mcp") for c in rtmod().CALLS)
    _, (app,) = run_calls([("agr_op_apply", {"preview_id": sc["preview_id"]})], fake_max.transport, store)
    err(app, "needs_human")
    assert not [c for c in rtmod().CALLS if c[2] == "apply"], "Max must not be asked to apply"
    with pytest.raises(max_bridge.BridgeError, match="needs_human"):
        max_bridge.run("agr_op_apply", str(fake_max.root), {"scene": "live", "handles": [1], "op": row,
                                                            "preview": sc["result"]})


def test_not_implemented_stub_holds_no_preview(fake_max):
    store = preview_store.PreviewStore()
    sys.path.insert(0, str(fake_max.root))
    import importlib
    importlib.import_module("runtime").NOT_IMPLEMENTED.add("body.roof")
    sys.path.remove(str(fake_max.root))
    _, (res,) = run_calls([("agr_body_roof", {"scene": "live", "handles": [1]})], fake_max.transport, store)
    sc = ok2(res)
    assert sc["status"] == "not_implemented" and "preview_id" not in sc
    assert sc["next_actions"][0].startswith("not_implemented")


def test_real_runtime_edits_100_stub_over_mcp(fake_max, monkeypatch, tmp_path):
    """The repo's runtime.py (edits_100 + actor + journal hook) behind the bridge: a stage stub answers
    not_implemented and the runtime itself writes the one journal line with actor mcp."""
    monkeypatch.setenv("AGR_TOOLS_ROOT", str(AGR))
    monkeypatch.delitem(sys.modules, "runtime", raising=False)
    stub = _a_stage_stub()  # branches F..U fill their buttons; the check follows a button that is still a stub
    if stub is None:
        pytest.skip("every 1.0 stage button is implemented; the branches' native runs own the behaviour")
    name = catalog.tool_name(stub)
    _, (res,) = run_calls([(name, {"scene": "live", "handles": [1]})], fake_max.transport)
    sc = ok2(res)
    assert sc["result"]["status"] == "not_implemented" and sc["result"]["tool"] == stub
    lines = journal_lines(tmp_path)
    assert len(lines) == 1 and lines[0]["actor"] == "mcp" and lines[0]["tool"] == stub
    assert lines[0]["doc"] == fake_max.doc


def _a_stage_stub():
    """The last stage tool (station order) whose glue function is still absent, or None."""
    import ast
    spec = importlib.util.spec_from_file_location("agr_runtime_stub_pick", AGR / "runtime.py")
    rt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rt)
    for row in reversed(catalog.stage_rows(PLAN)):
        core, fn = rt.EDITS_100[row["id"]]
        tree = ast.parse((AGR / rt.glue_file(core, rt.GLUE_100)).read_text(encoding="utf-8"))
        if fn not in {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}:
            return row["id"]
    return None


# ---- 5. one journal --------------------------------------------------------------------------------------------------
def test_one_journal_line_per_mcp_call(fake_max, tmp_path):
    """RED: v1 wrote only the transport audit; nothing reached the panel journal (journal_core)."""
    mesh = {"names": ["SM_Vatutino_Ground"], "kind": "vpm", "role": "ground", "fbx_stem": "SM_Vatutino_Ground",
            "limit": 254, "src": "synthetic"}
    calls = [("agr_mesh_names", mesh),  # offline: the server journals
             ("agr_op_preview", {"scene": "live", "handles": [1], "op": "model.triangulate"}),  # runtime journals
             ("agr_scene_census", {"scene": "live", "handles": [1]}),  # checks_070: no runtime journal
             ("agr_xview_check", {"scene": "live"}),  # error before Max: handles_required
             ("agr_check_run", {"scene": "live", "handles": [1], "check_ids": ["qa.xform", "udim.slots"]})]
    run_calls(calls, fake_max.transport)
    lines = journal_lines(tmp_path)  # two files: untitled.jsonl and <sha1(doc)>.jsonl
    assert all(x["actor"] == "mcp" for x in lines)
    got = sorted((x["tool"], x["mode"], x["status"]) for x in lines)
    assert got == sorted([("agr_mesh_names", "read", "ok"), ("model.triangulate", "preview", "fail"),
                          ("scene.census", "read", "fail"), ("agr_xview_check", "read", "error"),
                          ("udim.slots", "preview", "fail"), ("agr_check_run", "check", "fail")])
    by = {x["tool"]: x for x in lines}
    assert by["agr_xview_check"]["error_code"] == "handles_required"
    assert by["agr_xview_check"]["mcp_tool"] == "agr_xview_check" and by["agr_xview_check"]["doc"] == "untitled"
    assert by["agr_check_run"]["rows"] == ["qa.xform"], "the runtime journaled udim.slots itself"
    assert by["scene.census"]["doc"] == fake_max.doc and by["agr_mesh_names"]["doc"] == "untitled"
    assert by["model.triangulate"]["doc"] == fake_max.doc and "mcp_tool" not in by["model.triangulate"]


def test_old_runtime_without_actor_is_still_served_and_journaled_by_the_server(fake_max, tmp_path):
    old = FAKE_RUNTIME + "".join(  # the 0.9.0 signatures: no actor, no journal hook
        "\ndef edits_{0}(tool, mode, preview=None, nodes=None, options=None):\n"
        "    return _edits('{0}', tool, mode, preview, nodes, options, None)\n".format(g) for g in ("080", "090", "100"))
    (fake_max.root / "runtime.py").write_text("AGR = {!r}\n".format(str(AGR).replace("\\", "/")) + old,
                                              encoding="utf-8")
    _, (res,) = run_calls([("agr_op_preview", {"scene": "live", "handles": [1], "op": "tex.placeholders"})],
                          fake_max.transport)
    ok2(res)
    assert not max_bridge.accepts_actor(rtmod().edits_080)
    line, = journal_lines(tmp_path)
    assert line["tool"] == "tex.placeholders" and line["actor"] == "mcp" and line["mode"] == "preview"


# ---- 6. error codes / ObjRef -----------------------------------------------------------------------------------------
@pytest.mark.parametrize("text,code", [
    ("BridgeError: handles_required: pass node handles", "handles_required"),
    ("handles_required: pass node handles", "handles_required"),
    ("BridgeError: unknown_handle: unknown node handle 9", "unknown_handle"),
    ("BridgeError: scene_mismatch: requested a", "scene_mismatch"),
    ("BridgeError: version_mismatch: AGR Tools runtime version 0.4.0 < minimum 0.5.0", "version_mismatch"),
    ("ValueError: needs_human: apply of body.roof", "needs_human"),
    ("StalePreview: scene changed since the preview", "stale_preview"),
    ("busy: lock held: C:/x.lock", "busy"),
    ("no Max target pinned: set AGR_MCP_MAX_PID", "host_unavailable"),
    ("unreachable: pipe closed", "host_unavailable"),
    ("MAXScript error: -- Runtime error: x", "maxscript_error"),
    ("invalid input: [] is too short", "invalid_input"),
    ("unknown tool 'x'", "unknown_tool"),
    ("BridgeError: selection_changed: selection before [1]", "selection_changed"),
    ("ZeroDivisionError: division by zero", "error"),
])
def test_error_code_is_parsed_from_the_leading_code(text, code):
    assert envelope.error_code(text) == code and code in ERROR_CODES


@pytest.mark.parametrize("name,args,code", [
    ("agr_xview_check", {"scene": "live"}, "handles_required"),
    ("agr_check_run", {"scene": "live", "check_ids": ["qa.xform"]}, "handles_required"),
    ("agr_op_preview", {"scene": "live", "op": "model.triangulate", "handles": []}, "handles_required"),
    ("agr_win_place", {"scene": "live", "refs": []}, "handles_required"),
    ("agr_check_run", {"scene": "live", "check_ids": ["qa.xform"], "handles": [1], "scope": "selection"},
     "target_conflict"),
    ("agr_xview_check", {"scene": "live", "handles": [9]}, "unknown_handle"),
    ("agr_xview_check", {"scene": "C:/other.max", "handles": [1]}, "scene_mismatch"),
    ("agr_check_run", {"scene": "live", "check_ids": ["model.triangulate"], "handles": [1]}, "invalid_input"),
    ("agr_op_preview", {"scene": "live", "op": "qa.xform", "handles": [1]}, "invalid_input"),
    ("agr_nope", {}, "unknown_tool"),
])
def test_errors_carry_error_code(fake_max, tmp_path, name, args, code):
    """RED: v1 errors were bare text (SDK error result without structuredContent)."""
    _, (res,) = run_calls([(name, args)], fake_max.transport)
    sc = err(res, code)
    assert sc["tool"] == name and res.content[0].text == sc["error"]
    audit, = [json.loads(x) for x in (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
    assert audit["error_code"] == code


def test_version_busy_and_host_unavailable_codes(fake_max, tmp_path, monkeypatch):
    (fake_max.root / "runtime.py").write_text('VERSION = "0.8.0"\n', encoding="utf-8")
    _, (res,) = run_calls([("agr_check_run", {"scene": "live", "handles": [1], "check_ids": ["udim.slots"]})],
                          fake_max.transport)
    err(res, "version_mismatch")
    _, (res,) = run_calls([("agr_check_run", {"scene": "live", "handles": [1], "check_ids": ["qa.xform"]})])
    err(res, "host_unavailable")  # no transport, no AGR_MCP_MAX_PID
    from agr_mcp import locks
    with locks.hold("max-live", "other-card", 60):
        _, (res,) = run_calls([("agr_check_run", {"scene": "live", "handles": [1], "check_ids": ["qa.xform"]})],
                              fake_max.transport)
    err(res, "busy")


def test_objref_targets(fake_max):
    ref = {"host": "max", "doc": fake_max.doc, "handle": 3, "name": "Box003"}
    _, (good, blender, other_doc, mixed) = run_calls([
        ("agr_check_run", {"scene": "live", "refs": [ref], "check_ids": ["qa.xform"]}),
        ("agr_check_run", {"scene": "live", "refs": [dict(ref, host="blender")], "check_ids": ["qa.xform"]}),
        ("agr_check_run", {"scene": "C:/scenes/b.max", "refs": [ref], "check_ids": ["qa.xform"]}),
        ("agr_check_run", {"scene": "live", "refs": [ref], "handles": [1], "check_ids": ["qa.xform"]})],
        fake_max.transport)
    sc = ok2(good)
    assert fake_max.sent[0][1]["handles"] == [3] and fake_max.sent[0][1]["scene"] == fake_max.doc
    assert sc["findings_top"][0]["ref"] == ref
    err(blender, "target_conflict")
    err(other_doc, "scene_mismatch")
    err(mixed, "target_conflict")
    fake_max.rt.maxFileName = "else.max"  # refs of a document that is no longer open
    _, (gone,) = run_calls([("agr_check_run", {"scene": "live", "refs": [ref], "check_ids": ["qa.xform"]})],
                           fake_max.transport)
    err(gone, "scene_mismatch")


def test_v1_schemas_are_unchanged_by_objref():
    cat = tools.catalog()
    for n in tools.PHASE0:
        props = cat[n].input.get("properties", {})
        assert "refs" not in props, n
