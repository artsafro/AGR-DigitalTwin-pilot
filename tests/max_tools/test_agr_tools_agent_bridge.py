"""new-case: AGR Tools 1.0 (#1024) branch U - agent bridge: agent.request / agent.accept, the D108 gate, our listener in
Max, one daemon per host, profiles, the Claude dock, and the К4 agent-simulation eval (fake Max, no pymxs).

Named defects are RED on behaviour models of the source (agr-mcp 0.1 of branch 0 and the third-party 3dsmax-mcp as
the pipe/chat it replaces; mcp-review REPORT.md §2.4) and GREEN on branch U:
* D1 §2.4.5  the host lock is released when the client times out while Max still works;
* D2 §2.4.3  no instance registry: two Max instances are not told apart (no instance_ambiguous);
* D3 §2.4.6/3.9 one global lock file, no per-instance lease (a second client reaches a busy Max);
* D4 §2.4.7  no D108 operation in MCP (ops_d108 stub registers nothing);
* D5 К4      a write outside AGENT_<req> is not rolled back (no gate);
* D6 #1024   agr_exec_unsafe is reachable by any client with AGR_MCP_UNSAFE=1 (must not exist in the bridge);
* D7 3dsmax-mcp pipe: any MAXScript text is executed (our listener takes only the bridge call as data);
* D8 3dsmax-mcp chat: a tool call is applied at once, no preview/confirm, no undo record (dock: needs_human, one undo).
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "adapters" / "max" / "agr_tools"
SIDE = ROOT / "src" / "agr_mcp" / "max_side"
EVAL = ROOT / "evals" / "agent-sim-k4"
sys.path.insert(0, str(ROOT / "src"))
if str(SIDE) not in sys.path:
    sys.path.insert(0, str(SIDE))
if str(EVAL) not in sys.path:
    sys.path.insert(0, str(EVAL))

import agr_gate as gate_top  # noqa: E402  (the module the listener and the dock use inside Max)
import agr_listener  # noqa: E402
import fake_max  # noqa: E402
from agr_mcp import locks, max_pipe, ops_d108, tools  # noqa: E402
from agr_mcp.max_side import agr_client, agr_dock_core, agr_profiles, agr_registry  # noqa: E402


def _load(name, alias):
    spec = importlib.util.spec_from_file_location(alias, PKG / name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


core = _load("agentbridge_core.py", "agr_tools_agentbridge_core")
contract = _load("contract_core.py", "agr_tools_contract_core_u")
edit = _load("edit_core.py", "agr_tools_edit_core_u")
SCHEMA = json.loads((ROOT / "schemas" / "AgentRequest.schema.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("AGR_MCP_REGISTRY_DIR", str(tmp_path / "registry"))
    monkeypatch.setenv("AGR_JOURNAL_DIR", str(tmp_path / "journal"))
    monkeypatch.setenv("AGR_MCP_AUDIT", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("AGR_MCP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AGR_MCP_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.delenv("AGR_MCP_MAX_PID", raising=False)
    monkeypatch.delenv("AGR_MCP_PROFILE", raising=False)
    gate_top._CONFIRMED.clear()
    del gate_top._REFUSED[:]
    ops_d108._CFG.clear()
    yield
    agr_listener.stop()
    ops_d108._CFG.clear()


# ---- world: fake Max + listener (pump thread = Max main thread) -------------------------------------------------------
def scene_world():
    s = fake_max.FakeScene("C:/jobs/KPP1/scene.max")
    body = s.add("BODY_Brick_001", "0", fake_max.box((0, 0, 0), (4, 3, 6)), {"agr_role": "body"})
    odd_a = fake_max.box((10, 0, 0), (14, 1, 3))
    odd_b = fake_max.box((10, 1, 0), (11, 4, 3))
    n = len(odd_a["verts"])
    odd = {"verts": odd_a["verts"] + odd_b["verts"], "tris": odd_a["tris"] + [[a + n, b + n, c + n]
                                                                               for a, b, c in odd_b["tris"]]}
    odd_h = s.add("SM_Odd_Main", "0", odd, {})
    outside = s.add("SM_Decor_Main", "DECOR_main", fake_max.box((20, 0, 0), (21, 1, 1)), {"agr_role": "decor"})
    return s, {"body": body, "odd": odd_h, "outside": outside}


class World:
    def __init__(self, tmp_path, scene=None, pump=True):
        self.scene, self.h = scene_world() if scene is None else (scene, {})
        self.listener = agr_listener.Listener(host_factory=lambda: self.scene, bridge=FakeBridge()).start()
        self.stop = threading.Event()
        self.thread = None
        if pump:
            self.thread = threading.Thread(target=self._pump, daemon=True)
            self.thread.start()
        self.tmp = tmp_path

    def _pump(self):
        while not self.stop.is_set():
            self.listener.pump()
            time.sleep(0.005)

    def close(self):
        self.stop.set()
        self.listener.stop()

    def ref(self, key):
        h = self.h[key]
        return {"host": "max", "doc": self.scene.doc(), "handle": h, "name": self.scene.objs[h]["name"]}

    def request(self, rid="r001", ops=core.DEFAULT_OPS):
        folder = self.tmp / "jobs" / "KPP1" / "agent" / rid
        folder.mkdir(parents=True)
        objs = [{"ref": self.ref(k), "role": self.scene.objs[self.h[k]]["props"].get("agr_role"), "layer": "0"}
                for k in ("body", "odd")]
        opt = core.options({"task": "mark the openings of BODY_Brick_001", "job_dir": str(self.tmp / "jobs/KPP1"),
                            "allowed_ops": list(ops)})
        req = core.build_request(opt, rid, "KPP1", objs, ["LEVEL_1"], "snapshot.fbx", "a" * 64, {}, [], "claude")
        path = folder / "request.json"
        path.write_text(json.dumps(req), encoding="utf-8")
        return str(path)


class FakeBridge:
    """max_bridge.call stand-in: echoes the tool (the real one is covered by the agr_mcp tests)."""

    def call(self, tool, root_hex, args_hex):
        args = json.loads(bytes.fromhex(args_hex).decode("utf-8"))
        return json.dumps({"ok": True, "result": {"schema": 1, "tool": tool, "status": "pass", "objects": []},
                           "doc": "untitled", "runtime_version": "0.9.0", "echo": args})


@pytest.fixture
def world(tmp_path):
    w = World(tmp_path)
    yield w
    w.close()


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Daemon:
    def __init__(self, profile="modeller", env=None):
        import uvicorn
        from agr_mcp.max_side import agr_daemon
        self.app, self.info = agr_daemon.build(profile, env=env)
        self.port = _free_port()
        self.url = "http://127.0.0.1:{}/mcp".format(self.port)
        self.server = uvicorn.Server(uvicorn.Config(self.app, host="127.0.0.1", port=self.port, log_level="error",
                                                    lifespan="on"))
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        end = time.time() + 20
        while not self.server.started and time.time() < end:
            time.sleep(0.02)
        assert self.server.started

    def close(self):
        self.server.should_exit = True
        self.thread.join(10)


@pytest.fixture
def daemon(world, monkeypatch):
    monkeypatch.setenv("AGR_MCP_UNSAFE", "1")  # D6: the bridge profile must still not expose agr_exec_unsafe
    d = Daemon("modeller")
    yield d
    d.close()


# ======================================================================================================================
# D1 - lease past a client timeout
def test_d1_red_source_releases_the_host_lock_on_timeout():
    """Source (server.py + max_pipe): the transport times out -> MaxError -> `locks.hold` releases in finally,
    although Max still runs the call; the next call is free to go (REPORT §2.4.5)."""
    busy = {"max": True}
    with pytest.raises(max_pipe.MaxError):
        with locks.hold("max-live", "t", 1):
            raise max_pipe.MaxError("timeout: Max may still be running the call; do not resend")
    assert busy["max"] and not locks.lock_path("max-live").exists()  # RED: Max busy, lock gone


def test_d1_green_lease_held_until_the_host_reports_idle(tmp_path):
    w = World(tmp_path, pump=False)  # Max main thread not draining yet = Max busy
    try:
        leases = agr_client.Leases()
        host = agr_client.Host(leases=leases, client_factory=lambda e: agr_client.ListenerClient(e, poll_s=0.05))
        out = {}
        t = threading.Thread(target=lambda: out.setdefault("a", host.run("gate_read", {"handles": []}, 0.1)))
        t.start()
        time.sleep(0.5)  # well past the client timeout of 0.1 s
        assert t.is_alive() and leases.held(os.getpid())  # still waiting: the lease is not released
        with pytest.raises(agr_client.HostError, match="^busy"):
            host.run("gate_read", {"handles": []}, 0.1)  # a second call never reaches the busy Max
        w.listener.pump_until(lambda: not t.is_alive(), 5)
        t.join(5)
        assert out["a"]["ok"] and not leases.held(os.getpid())
    finally:
        w.close()


def test_d1_green_hard_cap_poisons_the_lease_until_idle(tmp_path):
    w = World(tmp_path, pump=False)
    try:
        leases = agr_client.Leases()
        host = agr_client.Host(leases=leases, client_factory=lambda e: agr_client.ListenerClient(
            e, poll_s=0.05, hard_cap_s=0.3))
        with pytest.raises(agr_client.HostError, match="^busy: .*lease stays held"):
            host.run("gate_read", {"handles": []}, 0.05)
        with pytest.raises(agr_client.HostError, match="not reported idle"):
            host.run("gate_read", {"handles": []}, 0.05)
        w.listener.pump()  # Max finishes the old job -> idle
        ok = []
        t = threading.Thread(target=lambda: ok.append(host.run("status_probe" if False else "gate_read",
                                                               {"handles": []}, 5)))
        t.start()
        w.listener.pump_until(lambda: not t.is_alive(), 5)
        assert ok and ok[0]["ok"]
    finally:
        w.close()


# D2 - instance registry
def test_d2_red_source_has_no_instance_choice(monkeypatch):
    """Source: max_pipe.pinned_env takes any pid string and has no list of instances, so two Max are never told
    apart and a dead pid is not detected before the call."""
    env = max_pipe.pinned_env({"AGR_MCP_MAX_PID": "99999999"})
    assert env["MCP_MAX_PID"] == "99999999"  # RED: accepted blindly


def test_d2_green_registry_selects_or_refuses(tmp_path):
    env = {"AGR_MCP_REGISTRY_DIR": str(tmp_path / "reg")}
    alive = {101: True, 102: True}
    for pid in alive:
        agr_registry.write("max", pid, {"pid": pid, "port": 1, "token": "t", "started": pid}, env)
    check = lambda p: alive.get(int(p), False)  # noqa: E731
    with pytest.raises(agr_registry.RegistryError, match="^instance_ambiguous"):
        agr_registry.select(None, env, check)
    assert agr_registry.select(102, env, check)["pid"] == 102
    with pytest.raises(agr_registry.RegistryError, match="^host_unavailable"):
        agr_registry.select(103, env, check)
    alive[101] = False
    assert agr_registry.select(None, env, check)["pid"] == 102


# D3 - per-instance lease, one writer
def test_d3_green_listener_refuses_a_second_job_while_busy(tmp_path):
    w = World(tmp_path, pump=False)
    try:
        tok = w.listener.token
        job = w.listener.handle({"token": tok, "kind": "gate_read"}, wait=False)
        ans = w.listener.handle({"token": tok, "kind": "gate_read"})
        assert ans["ok"] is False and ans["error"].startswith("busy")
        st = w.listener.handle({"token": tok, "kind": "status"})  # status never waits for the main thread
        assert st["busy"] and st["current"] == job.id
        w.listener.pump()
        assert job.done.is_set() and not w.listener.status()["busy"]
    finally:
        w.close()


def test_listener_needs_the_token_and_refuses_exec(tmp_path):
    w = World(tmp_path)
    try:
        assert w.listener.handle({"kind": "status"})["error"].startswith("forbidden")
        assert w.listener.handle({"token": w.listener.token, "kind": "exec", "code": "1"})["error"].startswith(
            "forbidden")
        entry = agr_registry.select()
        assert entry["port"] == w.listener.port and entry["exec"] is False
    finally:
        w.close()


# D4 - D108 operations in MCP
def test_d4_red_base_stub_registers_nothing():
    src = "def register(catalog):  # noqa: ARG001 - branch U fills this\n    return []\n"
    ns = {}
    exec(src, ns)  # the branch 0 stub of ops_d108.register (source behaviour)
    assert ns["register"]({}) == []


def test_d4_green_catalog_has_the_agent_tools():
    cat = tools.catalog()
    for name in ("agr_agent_context", "agr_agent_op_preview", "agr_agent_op_apply"):
        assert name in cat and cat[name].schema == 2
    assert set(cat["agr_agent_op_preview"].input["properties"]["op"]["enum"]) == set(core.OPS)
    assert not cat["agr_agent_op_apply"].read_only


# D5 - the gate
def _plan(scene, h, layer="AGENT_r001", actions=None):
    objs = scene.objects()
    return {"op": "set_role", "request_id": layer[6:], "layer": layer, "doc": scene.doc(),
            "state_hash": gate_top.state_hash(objs),
            "actions": actions or [{"do": "set_prop", "handle": h, "key": "agr_role", "value": "decor"}]}


def test_d5_red_naive_apply_leaves_the_outside_change():
    s, h = scene_world()
    before = gate_top.hashes(s.objects(), outside_of="AGENT_r001")
    s.set_prop(h["outside"], "agr_role", "decor2")  # what an ungated apply does
    assert gate_top.hashes(s.objects(), outside_of="AGENT_r001") != before


def test_d5_green_gate_rolls_back_with_proof_and_question():
    s, h = scene_world()
    s.sel = [h["body"]]
    plan = _plan(s, h["outside"], actions=[{"do": "set_prop", "handle": h["outside"], "key": "agr_role",
                                            "value": "glass"}])
    all_before = gate_top.hashes(s.objects())
    gate_top.confirm(gate_top.plan_id(plan))
    ans = gate_top.apply(s, plan)
    assert ans["status"] == "rolled_back" and ans["rollback_proved"] is True
    assert [v["code"] for v in ans["violations"]] == ["outside_changed"]
    assert gate_top.hashes(s.objects()) == all_before and s.undo_stack == [] and s.sel == [h["body"]]
    assert "Only objects in AGENT_r001 may change" in ans["question"]


def test_gate_rolls_back_a_hidden_outside_write_and_a_bad_marker():
    s, h = scene_world()
    s.bad_action = lambda sc: sc.set_prop(h["body"], "agr_role", "roof")  # touches outside inside the transaction
    plan = _plan(s, None, actions=[{"do": "create_point", "layer": "AGENT_r001", "name": "OPEN_001",
                                    "pos": [0, 0, 1], "props": {"agr_role": "opening", "agr_opening": "{}"}}])
    gate_top.confirm(gate_top.plan_id(plan))
    ans = gate_top.apply(s, plan)
    codes = sorted(v["code"] for v in ans["violations"])
    assert ans["status"] == "rolled_back" and codes == ["marker_opening", "outside_changed"]
    assert ans["rollback_proved"] and all(o["layer"] != "AGENT_r001" for o in s.objects())


def test_gate_refuses_unconfirmed_stale_and_foreign_plans():
    s, h = scene_world()
    plan = _plan(s, h["body"])
    with pytest.raises(gate_top.GateError, match="^needs_human"):
        gate_top.apply(s, plan)
    assert gate_top.refused() == [gate_top.plan_id(plan)]
    s.set_prop(h["odd"], "x", "1")
    gate_top.confirm(gate_top.plan_id(plan))
    with pytest.raises(gate_top.GateError, match="^stale_preview"):
        gate_top.apply(s, plan)
    with pytest.raises(gate_top.GateError, match="^invalid_plan"):
        gate_top.check_plan(dict(plan, layer="BODY_main"))
    with pytest.raises(gate_top.GateError, match="^invalid_plan"):
        gate_top.check_plan(dict(plan, actions=[{"do": "create_mesh", "layer": "0", "name": "x"}]))
    with pytest.raises(gate_top.GateError, match="^invalid_plan"):
        gate_top.check_plan(dict(plan, actions=[{"do": "set_prop", "handle": 1, "key": "evil", "value": 1}]))
    with pytest.raises(gate_top.GateError, match="^invalid_plan"):
        gate_top.apply(s, plan, "f" * 64)


# D6 - no exec in the bridge
def test_d6_red_source_unsafe_env_exposes_exec():
    from agr_mcp import server
    srv = server.build_server(env={"AGR_MCP_UNSAFE": "1"})
    names = {t.name for t in asyncio.run(_list(srv))}
    assert "agr_exec_unsafe" in names  # RED: the stdio server lists it to any client with the variable


async def _list(srv):
    from mcp.types import ListToolsRequest
    handler = srv.request_handlers[ListToolsRequest]
    res = await handler(ListToolsRequest(method="tools/list"))
    return res.root.tools


@pytest.mark.parametrize("profile", ["observer", "operator", "modeller"])
def test_d6_green_profiles_never_expose_exec(profile, monkeypatch):
    monkeypatch.setenv("AGR_MCP_UNSAFE", "1")
    names = {t.name for t in asyncio.run(_list(agr_profiles.build_server(profile)))}
    assert "agr_exec_unsafe" not in names
    assert ("agr_agent_op_preview" in names) == (profile != "observer")
    assert ("agr_op_apply" in names) == (profile == "modeller")
    assert "agr_check_run" in names and "agr_agent_context" in names


def test_profiles_dev_has_exec_and_unknown_profile_fails():
    names = {t.name for t in asyncio.run(_list(agr_profiles.build_server("dev")))}
    assert "agr_exec_unsafe" in names
    with pytest.raises(ValueError):
        agr_profiles.profile_of(value="root")
    assert agr_profiles.profile_of({}) == "operator"
    assert tools.catalog.__name__ == "catalog" and tools.catalog.__module__ == "agr_mcp.tools"  # patch undone


# D7 - pipe takes only the bridge call
def test_d7_red_source_pipe_sends_any_maxscript(monkeypatch):
    sent = []
    monkeypatch.setattr(max_pipe.subprocess, "run", lambda *a, **k: sent.append(k["input"]) or type(
        "R", (), {"stdout": json.dumps({"status": "success", "result": {"success": True, "result": "1"}}),
                  "stderr": ""})())
    monkeypatch.setenv("AGR_MCP_MAX_PID", "1")
    max_pipe.pipe_transport('deleteFile @"C:/x"', 5)
    assert "deleteFile" in sent[0]  # RED: arbitrary MAXScript reaches Max


def test_d7_green_transport_only_the_bridge_expression(world):
    host = agr_client.Host()
    code = max_pipe.bridge_script("agr_check_run", "", {"scene": "live", "handles": [1], "check_ids": ["qa.xview"]})
    raw = host.transport(code, 5)
    assert json.loads(raw)["echo"]["check_ids"] == ["qa.xview"]
    with pytest.raises(max_pipe.MaxError, match="^forbidden"):
        host.transport('deleteFile @"C:/x"', 5)
    with pytest.raises(max_pipe.MaxError, match="^forbidden"):
        host.transport(code.replace('b.call', 'deleteFile @"x"; b.call'), 5)
    # the whole v1/v2 catalogue goes through it unchanged
    payload = max_pipe.call_bridge("agr_xview_check", {"scene": "live", "handles": [1]}, 5, transport=host.transport)
    assert payload["result"]["tool"] == "agr_xview_check"


# D8 - the dock: confirm, one undo record
def test_d8_red_source_chat_applies_at_once():
    """3dsmax-mcp chat model: the model's tool call runs immediately in Max; there is no preview, no human button
    and no undo record (cards/U.md: «без undo и без preview/apply»)."""
    s, h = scene_world()
    s.set_prop(h["body"], "agr_role", "roof")  # the call itself
    assert s.objects()[0]["state"]["props"] and s.undo_stack == []  # RED


def test_d8_green_needs_human_then_one_undo_record():
    s, h = scene_world()
    plan = {"op": "mark_opening", "request_id": "r001", "layer": "AGENT_r001", "doc": s.doc(),
            "state_hash": gate_top.state_hash(s.objects()),
            "actions": [{"do": "create_point", "layer": "AGENT_r001", "name": "OPEN_001", "pos": [1, 0, 1],
                         "props": {"agr_role": "opening", "agr_opening": contract.dump_opening(
                             1.2, 1.5, 0.9, 0.25, "BODY_Brick_001", False)}}]}
    with pytest.raises(gate_top.GateError, match="^needs_human"):
        gate_top.apply(s, plan)
    before = gate_top.hashes(s.objects())
    gate_top.confirm(gate_top.plan_id(plan))
    ans = gate_top.apply(s, plan)
    assert ans["status"] == "applied" and len(s.undo_stack) == 1 and s.undo_stack[0][0] == "AGR agent: mark_opening"
    s.undo()  # one undo returns the scene
    assert gate_top.hashes(s.objects()) == before
    assert not gate_top.confirmed(gate_top.plan_id(plan))  # a confirmation is used once


# ======================================================================================================================
# The К4 acceptance: the agent simulation through MCP (eval evals/agent-sim-k4)
def test_eval_agent_simulation_k4(world, daemon):
    import run as sim
    path = world.request()

    def press(pid):  # the dock's «Применить»: confirm inside Max (here: the listener's module)
        gate_top.confirm(pid)
    outside_before = gate_top.hashes(world.scene.objects(), outside_of="AGENT_r001")
    refs = {k: world.ref(k) for k in ("body", "odd", "outside")}
    rep = asyncio.run(sim.scenario(daemon.url, daemon.info["token"], path, refs, press))
    failed = [r for r in rep["rows"] if not r["passed"]]
    assert not failed, failed
    assert len(rep["rows"]) == 9
    assert gate_top.hashes(world.scene.objects(), outside_of="AGENT_r001") == outside_before
    layer = [o for o in world.scene.objects() if o["layer"] == "AGENT_r001"]
    assert sorted(o["name"] for o in layer) == ["BODY_Brick_001", "OPEN_001", "OPEN_002"]
    assert len(world.scene.undo_stack) == 4  # 4 applied operations = 4 undo records, the rollback left none
    # journal: one agent line per apply, in the scene journal and the request folder
    lines = [json.loads(x) for x in (Path(path).parent / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [x["status"] for x in lines] == ["applied", "applied", "applied", "rolled_back", "applied"]
    assert {x["actor"] for x in lines} == {"agent"}
    (world.tmp / "agent-sim-k4.report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")


def test_daemon_http_routes_need_the_token_and_list_pending(world, daemon):
    import httpx
    base = daemon.url.rsplit("/mcp", 1)[0]
    assert httpx.get(base + "/agr/health").status_code == 401
    r = httpx.get(base + "/agr/health", headers={"Authorization": "Bearer " + daemon.info["token"]})
    assert r.json()["profile"] == "modeller" and r.json()["instance"] == os.getpid()
    assert httpx.post(daemon.url, json={}).status_code == 401
    pid = "0" * 64
    r = httpx.post(base + "/agr/apply", json={"preview_id": pid},
                   headers={"Authorization": "Bearer " + daemon.info["token"]})
    assert r.status_code == 409 and r.json()["error"].startswith("stale_preview")


def test_one_daemon_per_host(tmp_path):
    env = {"AGR_MCP_REGISTRY_DIR": str(tmp_path / "reg")}
    me = os.getpid()
    agr_registry.write("daemon", 4242, {"pid": 4242, "owner_pid": me, "port": 1, "url": "u", "token": "t"}, env)
    other = {"pid": 4242, "owner_pid": me + 1, "port": 2}
    orig = agr_registry.os.getpid
    try:
        agr_registry.os.getpid = lambda: me + 1  # a second daemon process for the same Max
        with pytest.raises(agr_registry.RegistryError, match="^busy"):
            agr_registry.write("daemon", 4242, other, env)
    finally:
        agr_registry.os.getpid = orig


def test_ops_preview_refusals(world):
    path = world.request(ops=("set_role", "keep", "make_capsule"))
    req, _ = ops_d108.load_request(path)
    with pytest.raises(ValueError, match="invalid input: mark_opening is not in allowed_ops"):
        ops_d108.plan_op(req, {"op": "mark_opening", "params": {}})
    plan, ans = ops_d108.plan_op(req, {"op": "make_capsule", "ref": world.ref("body")})
    assert plan is None and ans["status"] == "not_implemented" and "K (body.capsules)" in ans["why"]
    with pytest.raises(ValueError, match="unknown agr_role"):
        ops_d108.plan_op(req, {"op": "set_role", "ref": world.ref("body"), "params": {"role": "wall"}})
    bad = dict(world.ref("body"), doc="C:/other.max")
    with pytest.raises(ValueError, match="^scene_mismatch"):
        ops_d108.plan_op(req, {"op": "set_role", "ref": bad, "params": {"role": "body"}})
    plan, ans = ops_d108.plan_op(req, {"op": "keep", "ref": world.ref("body")})
    assert ans["invariants"]["passed"] and plan["actions"][0]["props"]["agr_role"] == "body"
    assert len(plan["actions"][0]["mesh"]["tris"]) == 12


# ======================================================================================================================
# agent.request / agent.accept cores
def _req(**kw):
    opt = core.options({"task": "t", "job_dir": "C:/jobs/KPP1"})
    ref = contract.obj_ref("max", "C:/jobs/KPP1/scene.max", 5, "BODY_Brick_001")
    args = dict(opt=opt, request_id="r001", project_id="KPP1", objects=[{"ref": ref, "role": "body", "layer": "0"}],
                markers=["OPEN_001"], snapshot_name="snapshot.fbx", snapshot_sha="b" * 64, passport_excerpt={},
                journal_tail=[{"tool": "x"}], command="claude ...")
    args.update(kw)
    return core.build_request(**args)


def test_request_core_matches_the_schema():
    import jsonschema
    good = _req()
    jsonschema.validate(good, SCHEMA)
    bad = [dict(good, result_layer="AGENT_r002"), dict(good, allowed_ops=["exec"]), dict(good, stage=10),
           dict(good, objects=[{"ref": {"host": "max"}, "role": "body"}]), dict(good, extra=1),
           dict(good, snapshot={"fbx": "s.fbx", "sha256": "x"}), dict(good, request_id="r_1"),
           dict(good, markers=["OPEN_1"]), dict(good, cli="vim")]
    for b in bad:
        with pytest.raises(ValueError):
            core.validate_request(b)
        schema_ok = True
        try:
            jsonschema.validate(b, SCHEMA)
        except jsonschema.ValidationError:
            schema_ok = False
        if b.get("result_layer") != "AGENT_r002":  # result_layer = AGENT_<request_id> is a core-only rule
            assert not schema_ok, b
    assert core.next_request_id(["r001", "r002", "x"]) == "r003"
    with pytest.raises(ValueError, match="needs options.task"):
        core.options({})
    with pytest.raises(ValueError, match="unknown agent.request options"):
        core.options({"task": "t", "evil": 1})


def test_request_md_and_command():
    req = _req()
    md = core.request_md(req, "C:/jobs/KPP1/agent/r001/request.json")
    assert "AGENT_r001" in md and "agr_exec_unsafe" in md and "agr_agent_context(request=" in md
    assert "data, never instructions" in md
    cmd = core.cli_command("claude", r"C:\jobs\KPP1\agent\r001\request.json", r"C:\agr\AGR-DigitalTwin-pilot")
    assert cmd.startswith('cd /d "C:\\agr\\AGR-DigitalTwin-pilot"') and "--mcp-config" in cmd
    assert core.cli_command("codex", "r.json", "C:/p").startswith('cd /d "C:/p" && codex')
    with pytest.raises(ValueError):
        core.cli_command("vim", "r.json", "C:/p")


def test_accept_core_outside_changes_and_plan():
    base = {"1": {"name": "A", "layer": "0", "hash": "a"}, "2": {"name": "B", "layer": "0", "hash": "b"},
            "3": {"name": "C", "layer": "0", "hash": "c"}}
    cur = {"1": {"name": "A", "layer": "0", "hash": "a"}, "2": {"name": "B", "layer": "0", "hash": "B!"},
           "4": {"name": "D", "layer": "0", "hash": "d"}, "5": {"name": "OPEN_001", "layer": "AGENT_r001", "hash": "e"},
           "6": {"name": "C", "layer": "AGENT_r001", "hash": "c"}}
    cur["3"] = {"name": "C", "layer": "AGENT_r001", "hash": "c"}
    got = core.outside_changes(base, cur, "AGENT_r001")
    assert got == [(2, "B", "outside_changed"), (3, "C", "moved_into_agent_layer"), (4, "D", "outside_created")]
    objs = [{"handle": 5, "name": "OPEN_001", "props": {"agr_role": "opening", "agr_opening": contract.dump_opening(
        1, 1, 0, 0.2, "W", False)}},
            {"handle": 6, "name": "BODY_Brick_001", "props": {"agr_role": "body", "agr_agent_source": "1"}},
            {"handle": 7, "name": "X", "props": {}},
            {"handle": 8, "name": "OPEN_9", "props": {"agr_role": "opening"}}]
    f = core.layer_findings(objs, contract)
    assert {c for _h, _n, c, _d in f} == {"marker_name", "marker_opening"}
    moves, hides, amb = core.accept_plan("r001", objs[:3], ["0", "BODY_main", "AGENT_r001"])
    assert moves == [(5, "OPEN_001", "OPENING_r001"), (6, "BODY_Brick_001", "BODY_main")] and hides == [1]
    assert amb == [(7, "X", "no agr_role: set_role first")]
    assert core.accept_plan("r001", objs[:2], [], originals="keep")[1] == []
    assert "AGENT_r001" in core.question("r001", got)


def test_runtime_registry_points_at_the_glue():
    text = (PKG / "runtime.py").read_text(encoding="utf-8")
    assert "'agent.request': ('agentbridge_core.py', 'agent_request')" in text
    glue = _load("agentbridge_max.py", "agr_tools_agentbridge_max_u")
    assert callable(glue.agent_request) and callable(glue.agent_accept) and callable(glue.agent_dock)


# ======================================================================================================================
# the dock
def test_dock_command_is_mcp_only():
    argv = agr_dock_core.command("claude.exe", "C:/cfg.json", session="0f1e2d3c-aaaa-bbbb-cccc-1234567890ab")
    assert argv[argv.index("--tools") + 1] == "" and "--strict-mcp-config" in argv
    assert argv[argv.index("--allowedTools") + 1] == "mcp__agr__*"
    assert argv[argv.index("--resume") + 1].startswith("0f1e2d3c")
    assert "--input-format" in argv and "stream-json" in argv and "--verbose" in argv
    with pytest.raises(ValueError):
        agr_dock_core.command("claude", "c", session="x; rm")
    with pytest.raises(ValueError, match="never dev"):
        agr_dock_core.check_profile("dev")
    env = agr_dock_core.environment({"ANTHROPIC_API_KEY": "k", "AGR_MCP_UNSAFE": "1", "PATH": "p"}, "local")
    assert env == {"PATH": "p"}
    assert agr_dock_core.environment({"ANTHROPIC_API_KEY": "k"}, "api_key")["ANTHROPIC_API_KEY"] == "k"
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        agr_dock_core.environment({}, "api_key")


STREAM = [
    {"type": "system", "subtype": "init", "session_id": "0f1e2d3c-aaaa-bbbb-cccc-1234567890ab"},
    {"type": "assistant", "session_id": "0f1e2d3c-aaaa-bbbb-cccc-1234567890ab", "message": {"content": [
        {"type": "text", "text": "Читаю сцену."},
        {"type": "tool_use", "id": "tu1", "name": "mcp__agr__agr_agent_op_preview",
         "input": {"op": "mark_opening", "request": "r.json"}}]}},
    {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "tu1", "content": [
        {"type": "text", "text": "agr_agent_op_preview: pass - findings 0\npreview_id " + "c" * 64}]}]}},
    {"type": "result", "subtype": "success", "is_error": False, "result": "Готово",
     "session_id": "0f1e2d3c-aaaa-bbbb-cccc-1234567890ab"},
]


def test_dock_stream_parsing_and_sessions(tmp_path):
    st = agr_dock_core.Stream()
    data = "".join(json.dumps(x) + "\n" for x in STREAM)
    evs = st.feed_bytes(data[:50].encode()) + st.feed_bytes(data[50:].encode())
    kinds = [k for k, _ in evs]
    assert kinds == ["session", "text", "tool", "tool_result", "result"]
    res = dict(evs)["tool_result"]
    assert res["preview_id"] == "c" * 64 and res["status"] == "pass"
    assert agr_dock_core.applicable("mcp__agr__agr_agent_op_preview", res)
    assert not agr_dock_core.applicable("mcp__agr__agr_check_run", res)
    agr_dock_core.save_session("C:/a.max", "s1", str(tmp_path))
    assert agr_dock_core.load_session("C:/A.max".lower() if os.name != "nt" else "C:/A.max", str(tmp_path)) == "s1"
    assert json.loads(agr_dock_core.user_message("привет"))["message"]["content"][0]["text"] == "привет"


def test_dock_widget_cards_apply_and_screens(qtbot, tmp_path, monkeypatch):
    agr_dock = pytest.importorskip("agr_dock")
    from PySide6 import QtGui, QtWidgets
    posted = []
    monkeypatch.setattr(agr_dock, "post_apply", lambda url, tok, pid, timeout=3600: posted.append(pid) or {
        "status": "applied", "undo_label": "AGR agent: mark_opening"})
    dock = agr_dock.AgentDock(str(ROOT), exe="claude", profile="modeller", doc=str(tmp_path / "s.max"),
                              daemon={"url": "http://127.0.0.1:1/mcp", "token": "t"})
    qtbot.addWidget(dock)
    dock.resize(420, 560)
    for ev in agr_dock_core.Stream().feed_bytes("".join(json.dumps(x) + "\n" for x in STREAM)):
        dock.on_event(ev)
    card = dock.cards["tu1"]
    assert card.preview_id == "c" * 64 and not card.button.isHidden()
    card.button.click()
    qtbot.waitUntil(lambda: "Применено" in card.body.text(), timeout=5000)
    assert posted == ["c" * 64] and gate_top.confirmed("c" * 64)
    out = Path(os.environ.get("AGR_U_EVIDENCE", str(tmp_path)))
    out.mkdir(parents=True, exist_ok=True)
    app = QtWidgets.QApplication.instance()
    for name, base, text in (("dark", "#2b2b2b", "#dcdcdc"), ("light", "#f0f0f0", "#202020")):
        pal = QtGui.QPalette()
        for role in (QtGui.QPalette.Window, QtGui.QPalette.Base, QtGui.QPalette.Button):
            pal.setColor(role, QtGui.QColor(base))
        for role in (QtGui.QPalette.WindowText, QtGui.QPalette.Text, QtGui.QPalette.ButtonText):
            pal.setColor(role, QtGui.QColor(text))
        app.setPalette(pal)
        dock.setPalette(pal)
        dock.show()
        qtbot.wait(50)
        assert dock.grab().save(str(out / "dock-{}.png".format(name)))
