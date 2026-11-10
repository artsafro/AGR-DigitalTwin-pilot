"""new-case: agr-mcp phase 2 (#1021) - previews of the runtime 0.9.0 copy families through an in-process MCP client
against a synthetic Max (fake pymxs world + fake installed runtime 0.9.0). Parity of the preview with the direct
runtime call, the selection contract of plan section 2 (#851), new-path rules, lock and audit. Every apply/commit
tool answers needs_human and never reaches Max [D231]. Synthetic data only.
"""
import hashlib
import json
import random
import re
import sys
import types
from pathlib import Path

import anyio
import pytest
from mcp.shared.memory import create_connected_server_and_client_session as connect

from agr_mcp import TOOL_SCHEMA_VERSION, locks, server, tools
from agr_mcp.max_side import max_bridge

FAMILIES = ("cleanup", "nudge", "atlas", "ucx", "export")
PREVIEW_TOOL = {"cleanup": "agr_cleanup_preview", "nudge": "agr_uv_nudge_preview", "atlas": "agr_atlas_preview",
                "ucx": "agr_ucx_preview", "export": "agr_export_preview"}
APPLY_TOOL = {"cleanup": "agr_cleanup_apply", "nudge": "agr_uv_nudge_apply", "atlas": "agr_atlas_apply",
              "ucx": "agr_ucx_apply", "export": "agr_export_commit"}
DIRECT = {"cleanup": "cleanup_preview", "nudge": "nudge_preview", "atlas": "atlas_preview", "ucx": "ucx_preview",
          "export": "export_preview"}
SIDE_DIRS = ("locks", "journal", "data")  # server bookkeeping under tmp_path, not scene files

# Fake installed runtime 0.9.0 with the preview signatures that matter here: previews hold tuples, ucx_preview
# selects nodes with findings (runtime default select=True). The apply functions exist and record a call, so a test
# can prove that no MCP call ever reaches them.
FAKE_RUNTIME_090 = '''
VERSION = "0.9.0"
CALLS = []
def _rt():
    from pymxs import runtime
    return runtime
def _report(tool, nodes, code, select=True):
    objs = [{"handle": n.handle, "name": n.name,
             "findings": [{"code": code, "ids": [n.handle], "detail": "synthetic"}] if n.handle % 2 else []}
            for n in nodes]
    r = {"schema": 1, "tool": tool, "status": "fail" if any(o["findings"] for o in objs) else "pass", "objects": objs}
    if select:
        _rt().select([n for n, o in zip(nodes, objs) if o["findings"]])
    return r
def _state(nodes):
    return tuple((n.handle, n.name, tuple(n.uv)) for n in nodes)
def _preview(fam, nodes, select=False, **extra):
    CALLS.append((fam + "_preview", [n.handle for n in nodes]))
    d = {"state": _state(nodes), "report": _report(fam, nodes, fam + "_finding", select=select)}
    d.update(extra)
    return d
def _apply(fam):
    CALLS.append((fam + "_apply", None))
    raise AssertionError("apply must never be reached over MCP")
def cleanup_preview(nodes=None, options=None):
    return _preview("cleanup", nodes, options=options)
def nudge_preview(nodes=None):
    return _preview("nudge", nodes, plans=tuple(("tile", n.handle) for n in nodes))
def atlas_preview(nodes=None):
    return _preview("atlas", nodes, plans=tuple(("cell", n.handle) for n in nodes))
def ucx_preview(nodes=None):
    return _preview("ucx", nodes, select=True, digest="d" + str(len(nodes)))
def export_preview(nodes=None, target=None):
    CALLS.append(("export_preview", [n.handle for n in nodes]))
    return {"schema": 1, "tool": "export", "status": "pass", "objects": [],
            "plan": {"target": target, "state": _state(nodes)}}
def cleanup_apply(nodes, preview):
    _apply("cleanup")
def nudge_apply(nodes, preview):
    _apply("nudge")
def atlas_apply(nodes, preview):
    _apply("atlas")
def ucx_apply(nodes, preview):
    _apply("ucx")
def export_commit(nodes, preview, target=None):
    _apply("export")
'''


class Node:
    def __init__(self, handle, name, uv):
        self.handle, self.name, self.uv = handle, name, list(uv)


class World:
    """Fake pymxs.runtime: nodes by handle (node handle == anim handle here), a selection, delete/select."""

    def __init__(self, tmp_path, doc=""):
        self.nodes, self.next, self._sel = {}, 1, []
        self.maxFilePath, self.maxFileName = (str(Path(doc).parent) + "\\", Path(doc).name) if doc else ("", "")
        self._tmp = tmp_path
        self.maxOps = types.SimpleNamespace(getNodeByHandle=lambda h: self.nodes.get(int(h)))
        for i in range(3):
            self.add(f"SM_Syn_{i + 1:03d}_Main", [0.25 * i, 0.5])

    def add(self, name, uv):
        n = Node(self.next, name, uv)
        self.nodes[n.handle] = n
        self.next += 1
        return n

    @property
    def objects(self):
        return list(self.nodes.values())

    @property
    def selection(self):
        return [n for n in self._sel if self.isValidNode(n)]

    def select(self, nodes):
        self._sel = list(nodes) if isinstance(nodes, (list, tuple)) else [nodes]

    def clearSelection(self):
        self._sel = []

    def delete(self, nodes):
        for n in (nodes if isinstance(nodes, (list, tuple)) else [nodes]):
            self.nodes.pop(n.handle, None)

    def isValidNode(self, n):
        return n is not None and self.nodes.get(getattr(n, "handle", None)) is n

    def getHandleByAnim(self, n):
        return n.handle

    def getAnimByHandle(self, h):
        return self.nodes.get(int(h))

    def name(self, s):
        return s

    def getDir(self, _n):
        return str(self._tmp)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("AGR_MCP_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setenv("AGR_MCP_AUDIT", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("AGR_JOURNAL_DIR", str(tmp_path / "journal"))
    monkeypatch.setenv("AGR_MCP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AGR_MCP_CARD", "test-1021")
    monkeypatch.delenv("AGR_MCP_UNSAFE", raising=False)
    for k in ("AGR_MCP_MAX_PID", "MCP_MAX_PID", "MCP_MAX_PIPE"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def fake(tmp_path, monkeypatch):
    root = tmp_path / "AGRTools-0.9.0"
    root.mkdir()
    (root / "runtime.py").write_text(FAKE_RUNTIME_090, encoding="utf-8")
    monkeypatch.delitem(sys.modules, "runtime", raising=False)
    monkeypatch.setenv("AGR_TOOLS_ROOT", str(root))
    sent = []

    def use(world):
        monkeypatch.setitem(sys.modules, "pymxs", types.SimpleNamespace(runtime=world))
        return world

    def transport(code, timeout):
        sent.append(code)
        m = re.search(r'b\.call "(\w+)" "([0-9a-f]*)" "([0-9a-f]*)"', code)
        assert m, code
        return max_bridge.call(*m.groups())

    def runtime():
        return max_bridge._load_runtime(str(root), "0.9.0")

    world = use(World(tmp_path))
    yield types.SimpleNamespace(root=root, world=world, use=use, sent=sent, transport=transport, runtime=runtime,
                                tmp=tmp_path)
    sys.path[:] = [p for p in sys.path if Path(p) != root]


def audit_lines(tmp_path):
    p = tmp_path / "audit.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def session(calls, transport, env=None):
    """calls: list of (name, args) or callables(previous results) -> (name, args); one MCP client session."""
    async def main():
        srv = server.build_server(env=env, max_transport=transport)
        out = []
        async with connect(srv) as client:
            for c in calls:
                name, args = c(out) if callable(c) else c
                out.append(await client.call_tool(name, args))
        return out
    return anyio.run(main)


def ok(res):
    assert not res.isError, res.content[0].text
    sc = res.structuredContent
    assert sc["tool_schema_version"] == TOOL_SCHEMA_VERSION
    return sc["result"]


def err(res):
    assert res.isError, res.structuredContent
    return res.content[0].text


def canon(value):
    return json.loads(json.dumps(value, allow_nan=False, sort_keys=True))


def runtime_calls():
    return sys.modules["runtime"].CALLS if "runtime" in sys.modules else []


def p2_args(fam, handles, target=None, **extra):
    args = {"scene": "live", "handles": handles}
    if fam == "export":
        args["target"] = str(target)
    args.update(extra)
    return args


def files_under(tmp_path):
    return {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file() and p.name != "audit.jsonl"
            and not set(SIDE_DIRS) & set(p.relative_to(tmp_path).parts)}


# ---- catalog --------------------------------------------------------------------------------------------------
def test_phase2_catalog_five_previews_five_needs_human_and_no_code_argument():
    cat = tools.catalog()
    assert len(tools.PHASE2) == 10 and set(tools.PHASE2) <= set(cat) and set(tools.PHASE2) <= set(tools.LISTED)
    assert set(tools.PHASE2_PREVIEWS) == set(max_bridge.PHASE2_PREVIEW), "server and bridge disagree on previews"
    assert set(tools.PHASE2) - set(tools.PHASE2_PREVIEWS) == set(max_bridge.PHASE2_APPLY)
    for name in tools.PHASE2:
        spec = cat[name]
        assert "code" not in json.dumps(spec.input), name
        assert spec.read_only and not spec.destructive and spec.schema == 1, name
        assert "Deprecated" not in spec.description, name
        if name in tools.PHASE2_PREVIEWS:
            assert spec.host({}) == "max-live" and spec.timeout, name
            assert "scope" in spec.input["properties"] and spec.input["additionalProperties"] is False
            assert "preview" not in spec.input["properties"], name
        else:
            assert spec.host({}) == "offline" and "needs_human" in spec.description, name
    assert "agr_exec_unsafe" not in cat


# ---- parity: MCP preview == direct runtime preview on the same synthetic scene --------------------------------
@pytest.mark.parametrize("fam", FAMILIES)
def test_parity_preview_equals_direct_runtime_call(fake, tmp_path, fam):
    handles = [1, 2, 3]
    target = tmp_path / "SM_Syn_001_Main.fbx"
    fake.use(World(tmp_path))
    mod = fake.runtime()
    world_a = sys.modules["pymxs"].runtime
    nodes = [world_a.nodes[h] for h in handles]
    fn = getattr(mod, DIRECT[fam])
    want = fn(nodes, str(target)) if fam == "export" else fn(nodes, None) if fam == "cleanup" else fn(nodes)
    fake.use(World(tmp_path))
    (res,) = session([(PREVIEW_TOOL[fam], p2_args(fam, handles, target))], fake.transport)
    got = ok(res)
    assert got == canon(want)
    assert got["report" if fam != "export" else "plan"], "vacuous preview"
    assert not target.exists(), "a preview wrote the target"


# ---- apply/commit: needs_human, never reaches Max [D231] -----------------------------------------------------------
@pytest.mark.parametrize("fam", FAMILIES)
def test_apply_answers_needs_human_and_never_reaches_max(fake, tmp_path, fam):
    target = tmp_path / "SM_Syn_001_Main.fbx"
    res = session([(PREVIEW_TOOL[fam], p2_args(fam, [1], target)),
                   lambda out: (APPLY_TOOL[fam], p2_args(fam, [1], target, preview=ok(out[0])))], fake.transport)
    text = err(res[1])
    assert text.startswith("needs_human:") and "D231" in text
    assert res[1].structuredContent["error_code"] == "needs_human"
    assert len(fake.sent) == 1, "the apply call reached Max"
    assert [c for c, _ in runtime_calls()] == [DIRECT[fam]]
    assert len(fake.world.nodes) == 3 and not target.exists()
    lines = audit_lines(tmp_path)
    assert [x["status"] for x in lines] == ["ok", "error"] and lines[1]["error_code"] == "needs_human"
    assert lines[1]["host"] == "offline" and lines[1]["lock"] is None


@pytest.mark.parametrize("name", max_bridge.PHASE2_APPLY)
def test_bridge_refuses_apply_as_a_second_line(fake, name):
    out = json.loads(max_bridge.call(name, "", json.dumps({"scene": "live", "handles": [1]}).encode().hex()))
    assert out["ok"] is False and "needs_human" in out["error"]
    assert runtime_calls() == []


# ---- selection contract (plan section 2 rows, #851) -----------------------------------------------------------
@pytest.mark.parametrize("args,select,needle,runtime_nodes", [
    ({"handles": [1, 2]}, [], None, [1, 2]),
    ({"handles": []}, [3], "handles_required", None),
    ({}, [3], "handles_required", None),
    ({"handles": [], "scope": "selection"}, [2, 3], None, [2, 3]),
    ({"scope": "selection"}, [], "nothing is selected", None),
    ({"handles": [1], "scope": "selection"}, [3], "target_conflict", None),
    ({"handles": [9]}, [], "unknown node handle 9", None),
    ({"handles": [1, 1]}, [], "invalid input", None),
])
def test_selection_contract_rows(fake, tmp_path, args, select, needle, runtime_nodes):
    w = fake.world
    w.select([w.nodes[h] for h in select])
    (res,) = session([("agr_cleanup_preview", dict(scene="live", **args))], fake.transport)
    line, = audit_lines(tmp_path)
    if needle:
        assert needle in err(res)
        assert runtime_calls() == [], "runtime called despite a contract error"
        if needle in ("handles_required", "target_conflict", "invalid input"):
            assert fake.sent == [], "Max must not be called"
    else:
        ok(res)
        assert runtime_calls() == [("cleanup_preview", runtime_nodes)]
        assert line["status"] == "ok"
    assert sorted(n.handle for n in w.selection) == sorted(select), "selection changed"


@pytest.mark.parametrize("fam", FAMILIES)
def test_every_phase2_preview_restores_the_selection(fake, tmp_path, fam):
    w = fake.world
    w.select([w.nodes[3]])
    (res,) = session([(PREVIEW_TOOL[fam], p2_args(fam, [1], tmp_path / "SM_Syn_001_Main.fbx"))], fake.transport)
    ok(res)
    assert [n.handle for n in w.selection] == [3]


def test_selection_left_changed_is_an_error(fake, monkeypatch):
    monkeypatch.setattr(max_bridge, "_restore_selection", lambda rt, before: [])
    w = fake.world
    w.select([w.nodes[2]])
    (res,) = session([("agr_ucx_preview", p2_args("ucx", [1]))], fake.transport)  # ucx_preview selects node 1
    assert "selection_changed" in err(res)


# ---- writes nothing: new-path rules and node set -------------------------------------------------------------------
@pytest.mark.parametrize("case", ["exists", "report_exists", "partial_exists", "relative", "suffix", "no_folder",
                                  "is_scene", "is_scene_case"])
def test_export_target_must_be_a_new_fbx_path(fake, tmp_path, case):
    scene = tmp_path / "scenes" / "poly.fbx"  # an .fbx-named open document makes target == scene reachable
    scene.parent.mkdir()
    scene.write_bytes(b"SCENE")
    target = tmp_path / "out" / "SM_Syn_001_Main.fbx"
    target.parent.mkdir()
    doc = ""
    if case == "exists":
        target.write_bytes(b"OLD")
    elif case == "report_exists":
        target.with_suffix(".report.json").write_text("{}")
    elif case == "partial_exists":
        Path(str(target) + ".partial").write_bytes(b"P")
    elif case == "relative":
        target = Path("out/SM_Syn_001_Main.fbx")
    elif case == "suffix":
        target = target.with_suffix(".obj")
    elif case == "no_folder":
        target = tmp_path / "missing" / "x.fbx"
    elif case in ("is_scene", "is_scene_case"):
        doc, target = str(scene), scene if case == "is_scene" else Path(str(scene).upper())
    fake.use(World(tmp_path, doc=doc))
    before = files_under(tmp_path)
    args = p2_args("export", [1], target)
    args["scene"] = doc or "live"
    (res,) = session([("agr_export_preview", args)], fake.transport)
    assert "invalid_target" in err(res)
    assert fake.sent == [], "Max was called for a forbidden target"
    assert files_under(tmp_path) == before


def _patch_runtime(fake, src):
    (fake.root / "runtime.py").write_text(FAKE_RUNTIME_090 + src, encoding="utf-8")
    sys.modules.pop("runtime", None)


def test_preview_that_creates_a_node_is_an_error(fake):
    _patch_runtime(fake, '''
_orig_p = atlas_preview
def atlas_preview(nodes=None):
    _rt().add("leak", [0, 0])
    return _orig_p(nodes)
''')
    (res,) = session([("agr_atlas_preview", p2_args("atlas", [1]))], fake.transport)
    assert "left new nodes" in err(res)


def test_preview_that_deletes_a_node_is_an_error_naming_it(fake):
    _patch_runtime(fake, '''
_orig_n = nudge_preview
def nudge_preview(nodes=None):
    _rt().delete([_rt().maxOps.getNodeByHandle(2)])
    return _orig_n(nodes)
''')
    (res,) = session([("agr_uv_nudge_preview", p2_args("nudge", [1]))], fake.transport)
    assert "deleted nodes [2]" in err(res)


def test_preview_with_bytes_is_shown_as_length_and_sha(fake):
    """Native run 1 finding: runtime.atlas_preview carries PNG bytes ('images'); json.dumps failed with TypeError."""
    _patch_runtime(fake, '''
_orig_p = atlas_preview
def atlas_preview(nodes=None):
    d = _orig_p(nodes)
    d["images"] = tuple(b"PNG" + bytes([n.handle]) for n in nodes)
    return d
''')
    (res,) = session([("agr_atlas_preview", p2_args("atlas", [1]))], fake.transport)
    assert ok(res)["images"] == [{"bytes": 4, "sha256": hashlib.sha256(b"PNG\x01").hexdigest()}]


def test_missing_runtime_function_is_an_error_naming_it(fake):
    (fake.root / "runtime.py").write_text(FAKE_RUNTIME_090.replace("def ucx_preview", "def _gone_ucx"),
                                          encoding="utf-8")
    sys.modules.pop("runtime", None)
    (res,) = session([("agr_ucx_preview", p2_args("ucx", [1]))], fake.transport)
    assert "has no ucx_preview" in err(res)


def test_wrong_runtime_version_is_an_error(fake):
    (fake.root / "runtime.py").write_text(FAKE_RUNTIME_090.replace('"0.9.0"', '"0.8.0"'), encoding="utf-8")
    sys.modules.pop("runtime", None)
    (res,) = session([("agr_cleanup_preview", p2_args("cleanup", [1]))], fake.transport)
    assert "0.8.0" in err(res)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_arguments_never_reach_max(bad):
    args = p2_args("cleanup", [1], options={"x": bad})
    with pytest.raises(ValueError, match="non-finite"):
        tools._check_finite(args, "arguments")
    from agr_mcp import max_pipe
    with pytest.raises(ValueError):
        max_pipe.bridge_script("agr_cleanup_preview", "", args)


# ---- lock and audit -----------------------------------------------------------------------------------------------
def test_every_phase2_preview_is_refused_while_the_live_lock_is_held(fake, tmp_path):
    lock = tmp_path / "locks" / "agr-3dsmax-live.lock"
    lock.parent.mkdir(parents=True)
    calls = [(PREVIEW_TOOL[f], p2_args(f, [1], tmp_path / f"{f}.fbx")) for f in FAMILIES]
    with locks.hold("max-live", "other-card", 60):
        res = session(calls, fake.transport)
    assert all("busy" in err(r) for r in res)
    lines = audit_lines(tmp_path)
    assert len(lines) == 5 and {x["status"] for x in lines} == {"busy"}
    assert all(x["lock"].endswith("agr-3dsmax-live.lock") for x in lines) and fake.sent == []


# ---- unsafe stays off ----------------------------------------------------------------------------------------
@pytest.mark.parametrize("value", [None, "0", "true", "1 ", "yes"])
def test_unsafe_off_unless_exactly_one_and_phase2_has_no_code(value):
    env = {} if value is None else {"AGR_MCP_UNSAFE": value}
    assert not server.unsafe_enabled(env)
    cat = tools.catalog(unsafe=server.unsafe_enabled(env))
    assert "agr_exec_unsafe" not in cat and set(tools.PHASE2) <= set(cat)
    assert server.unsafe_enabled({"AGR_MCP_UNSAFE": "1"})


# ---- probe: generated target/selection combinations -----------------------------------------------------------
def test_probe_selection_and_targets_seed_1021(fake, tmp_path):
    """Invariants over 120 generated calls (previews and applies): the runtime never gets empty targets; a contract
    error or an apply never reaches the runtime; the selection and the node set are the same before and after every
    Max call; one audit line per call."""
    rng = random.Random(1021)
    w = fake.world
    cases = []
    for _ in range(120):
        fam = rng.choice(("cleanup", "nudge", "atlas", "ucx"))
        handles = rng.sample([1, 2, 3, 9], rng.randint(0, 2))
        scope = rng.choice([None, None, "selection"])
        sel = rng.sample([1, 2, 3], rng.randint(0, 2))
        cases.append((fam, handles, scope, sel, rng.random() < 0.25))
    seen = []

    def guarded(code, timeout):
        before = (sorted(n.handle for n in w.selection), sorted(w.nodes))
        out = fake.transport(code, timeout)
        after = (sorted(n.handle for n in w.selection), sorted(w.nodes))
        seen.append(before == after)
        return out

    def make(case):
        fam, handles, scope, sel, apply = case

        def call(out):
            w.select([w.nodes[h] for h in sel])
            args = {"scene": "live", "handles": handles}
            if scope:
                args["scope"] = scope
            return (APPLY_TOOL if apply else PREVIEW_TOOL)[fam], args
        return call
    res = session([make(c) for c in cases], guarded)
    expected_ok = 0
    for (fam, handles, scope, sel, apply), r in zip(cases, res):
        valid = not apply and bool(handles) != bool(scope) and 9 not in handles and bool(handles or sel)
        assert (not r.isError) == valid, (fam, handles, scope, sel, apply, r.content[0].text)
        if apply:
            assert r.structuredContent["error_code"] == "needs_human"
        expected_ok += valid
    calls = runtime_calls()
    assert all(nodes for _fn, nodes in calls) and len(calls) == expected_ok
    assert all(fn.endswith("_preview") for fn, _ in calls)
    assert seen and all(seen), "a call changed the selection or the node set"
    assert len(audit_lines(tmp_path)) == 120
    print("PROBE seed 1021: 120/120 calls, ok", expected_ok, "max calls", len(seen))
