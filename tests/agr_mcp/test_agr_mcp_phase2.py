"""new-case: agr-mcp phase 2 (#1021) - edit tools on copies through an in-process MCP client against a synthetic
Max (fake pymxs world + fake installed runtime 0.9.0). Parity with the direct runtime call, the selection contract
of plan section 2 (#851), preview single use, new-path rules, lock and audit. Synthetic data only.
"""
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
DIRECT = {"cleanup": ("cleanup_preview", "cleanup_apply"), "nudge": ("nudge_preview", "nudge_apply"),
          "atlas": ("atlas_preview", "atlas_apply"), "ucx": ("ucx_preview", "ucx_apply"),
          "export": ("export_preview", "export_commit")}

# Fake installed runtime 0.9.0 with the signatures and behaviour that matter here: previews hold tuples (a JSON
# round trip would turn them into lists and break the runtime's own `preview != current` check), apply makes new
# copies and selects them, ucx_preview selects nodes with findings (runtime default select=True), export_commit
# makes temporary copies, selects them, writes the FBX + report exclusively, deletes the copies.
FAKE_RUNTIME_090 = '''
VERSION = "0.9.0"
CALLS = []
from pathlib import Path
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
def _apply(fam, nodes, preview, suffix, current):
    CALLS.append((fam + "_apply", [n.handle for n in nodes]))
    if preview != current:
        raise ValueError("stale or altered " + fam + " preview; run dry-run again")
    rt = _rt()
    copies = []
    for n in nodes:
        c = rt.copy(n)
        c.name = n.name + suffix
        c.uv = [u + 1.0 for u in n.uv]
        copies.append(c)
    rt.select(copies)
    return copies, _report(fam, copies, "after", select=False)
def cleanup_preview(nodes=None, options=None):
    return _preview("cleanup", nodes, options=options)
def cleanup_apply(nodes, preview):
    return _apply("cleanup", nodes, preview, "_AGR_export_", cleanup_preview(nodes, preview.get("options")))
def nudge_preview(nodes=None):
    return _preview("nudge", nodes, plans=tuple(("tile", n.handle) for n in nodes))
def nudge_apply(nodes, preview):
    return _apply("nudge", nodes, preview, "_AGR_nudge_", nudge_preview(nodes))
def atlas_preview(nodes=None):
    return _preview("atlas", nodes, plans=tuple(("cell", n.handle) for n in nodes))
def atlas_apply(nodes, preview):
    return _apply("atlas", nodes, preview, "_AGR_atlas_", atlas_preview(nodes))
def ucx_preview(nodes=None):
    return _preview("ucx", nodes, select=True, digest="d" + str(len(nodes)))
def ucx_apply(nodes, preview):
    copies, report = _apply("ucx", nodes, preview, "_AGR_ucx_", ucx_preview(nodes))
    rt = _rt()
    for n in list(copies):
        u = rt.copy(n)
        u.name = "UCX_" + n.name + "_001"
        copies.append(u)
    return copies, report
def export_preview(nodes=None, target=None):
    CALLS.append(("export_preview", [n.handle for n in nodes]))
    return {"schema": 1, "tool": "export", "status": "pass", "objects": [],
            "plan": {"target": target, "state": _state(nodes)}}
def export_commit(nodes, preview, target=None):
    CALLS.append(("export_commit", [n.handle for n in nodes]))
    current = export_preview(nodes, target)
    CALLS.pop()
    if current != preview:
        raise ValueError("stale preview")
    rt = _rt()
    tmp = [rt.copy(n) for n in nodes]
    rt.select(tmp)
    p = Path(target)
    with open(p, "xb") as f:
        f.write(b"FBX synthetic")
    with open(p.with_suffix(".report.json"), "x") as f:
        f.write("{}")
    rt.delete(tmp)
    return dict(current, plan=dict(current["plan"], readback={"object_count": len(nodes)}))
'''


class Node:
    def __init__(self, handle, name, uv):
        self.handle, self.name, self.uv = handle, name, list(uv)


class World:
    """Fake pymxs.runtime: nodes by handle, a selection, copy/delete/select."""

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

    def copy(self, n):
        return self.add(n.name, n.uv)

    def delete(self, nodes):
        for n in (nodes if isinstance(nodes, (list, tuple)) else [nodes]):
            self.nodes.pop(n.handle, None)

    def isValidNode(self, n):
        return n is not None and self.nodes.get(getattr(n, "handle", None)) is n

    def name(self, s):
        return s

    def getDir(self, _n):
        return str(self._tmp)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("AGR_MCP_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setenv("AGR_MCP_AUDIT", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("AGR_MCP_CARD", "test-1021")
    monkeypatch.delenv("AGR_MCP_UNSAFE", raising=False)
    for k in ("AGR_MCP_MAX_PID", "MCP_MAX_PID", "MCP_MAX_PIPE"):
        monkeypatch.delenv(k, raising=False)
    max_bridge._PREVIEWS.clear()
    yield
    max_bridge._PREVIEWS.clear()


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


def p2_args(fam, handles, target=None, **extra):
    args = {"scene": "live", "handles": handles}
    if fam == "export":
        args["target"] = str(target)
    args.update(extra)
    return args


# ---- catalog --------------------------------------------------------------------------------------------------
def test_phase2_catalog_ten_tools_flags_and_no_code_argument():
    cat = tools.catalog()
    assert len(tools.PHASE2) == 10 and set(tools.PHASE2) <= set(cat)
    assert set(tools.PHASE2) == set(max_bridge.PHASE2), "server and bridge disagree on the phase-2 names"
    for name in tools.PHASE2:
        spec = cat[name]
        assert "code" not in json.dumps(spec.input), name
        assert spec.read_only == name.endswith("_preview"), name
        assert not spec.destructive and spec.host({}) == "max-live" and spec.timeout and spec.check, name
        assert "scope" in spec.input["properties"] and spec.input["additionalProperties"] is False
    assert "agr_exec_unsafe" not in cat


# ---- parity: MCP output == direct runtime output on the same synthetic scene ---------------------------------
@pytest.mark.parametrize("fam", FAMILIES)
def test_parity_preview_and_apply_equal_direct_runtime_call(fake, tmp_path, fam):
    handles = [1, 2, 3]
    target_a = tmp_path / "direct" / "SM_Syn_001_Main.fbx"
    target_b = tmp_path / "mcp" / "SM_Syn_001_Main.fbx"
    # direct: world A
    fake.use(World(tmp_path))
    mod = fake.runtime()
    world_a = sys.modules["pymxs"].runtime
    nodes = [world_a.nodes[h] for h in handles]
    pfn, afn = (getattr(mod, f) for f in DIRECT[fam])
    if fam == "export":
        target_a.parent.mkdir()
        want_preview = pfn(nodes, str(target_a))
        want_apply = afn(nodes, want_preview, str(target_a))
    else:
        want_preview = pfn(nodes) if fam != "cleanup" else pfn(nodes, None)
        copies, report = afn(nodes, want_preview)
        want_apply = {"copies": [{"handle": c.handle, "name": c.name} for c in copies], "report": report}
    # MCP: world B, identical start
    fake.use(World(tmp_path))
    target_b.parent.mkdir()
    res = session([(PREVIEW_TOOL[fam], p2_args(fam, handles, target_b)),
                   lambda out: (APPLY_TOOL[fam], p2_args(fam, handles, target_b, preview=ok(out[0])))],
                  fake.transport)
    got_preview, got_apply = ok(res[0]), ok(res[1])
    if fam == "export":  # same file name in another folder: the only allowed difference is the folder
        want_preview = json.loads(json.dumps(want_preview).replace(json.dumps(str(target_a))[1:-1],
                                                                    json.dumps(str(target_b))[1:-1]))
        want_apply = json.loads(json.dumps(want_apply).replace(json.dumps(str(target_a))[1:-1],
                                                                json.dumps(str(target_b))[1:-1]))
        assert target_b.read_bytes() == target_a.read_bytes()
    assert got_preview == canon(want_preview)
    assert got_apply == canon(want_apply)
    assert got_preview["report" if fam != "export" else "plan"], "vacuous preview"
    if fam != "export":
        assert got_apply["copies"], "vacuous apply"
    print("PARITY", fam, "preview=equal apply=equal")


# ---- selection contract (plan section 2 rows, #851) -----------------------------------------------------------
@pytest.mark.parametrize("args,select,needle,runtime_nodes", [
    ({"handles": [1, 2]}, [], None, [1, 2]),
    ({"handles": []}, [3], "handles_required", None),
    ({}, [3], "handles_required", None),
    ({"handles": [], "scope": "selection"}, [2, 3], None, [2, 3]),
    ({"scope": "selection"}, [], "selection is empty", None),
    ({"handles": [1], "scope": "selection"}, [3], "two target sources", None),
    ({"handles": [9]}, [], "unknown node handle 9", None),
    ({"handles": [1, 1]}, [], "invalid input", None),
])
def test_selection_contract_rows(fake, tmp_path, args, select, needle, runtime_nodes):
    w = fake.world
    w.select([w.nodes[h] for h in select])
    (res,) = session([("agr_cleanup_preview", dict(scene="live", **args))], fake.transport)
    calls = sys.modules["runtime"].CALLS if "runtime" in sys.modules else []
    line, = audit_lines(tmp_path)
    if needle:
        assert needle in err(res)
        assert calls == [], "runtime called despite a contract error"
        if needle in ("handles_required", "two target sources", "invalid input"):
            assert fake.sent == [] and line["status"] == "invalid", "Max must not be called"
    else:
        ok(res)
        assert calls == [("cleanup_preview", runtime_nodes)]
        assert line["handles"] == runtime_nodes and line["scope"] == args.get("scope")
    assert sorted(n.handle for n in w.selection) == sorted(select), "selection changed"


@pytest.mark.parametrize("fam", FAMILIES)
def test_every_phase2_tool_restores_the_selection(fake, tmp_path, fam):
    w = fake.world
    w.select([w.nodes[3]])
    target = tmp_path / "SM_Syn_001_Main.fbx"
    res = session([(PREVIEW_TOOL[fam], p2_args(fam, [1], target)),
                   lambda out: (APPLY_TOOL[fam], p2_args(fam, [1], target, preview=ok(out[0])))], fake.transport)
    ok(res[0]), ok(res[1])
    assert [n.handle for n in w.selection] == [3]


def test_selection_left_changed_is_an_error(fake, monkeypatch):
    monkeypatch.setattr(max_bridge, "_restore_selection", lambda rt, saved: None)
    w = fake.world
    w.select([w.nodes[3]])
    res = session([("agr_cleanup_preview", p2_args("cleanup", [1])),
                   lambda out: ("agr_cleanup_apply", p2_args("cleanup", [1], preview=ok(out[0])))], fake.transport)
    assert "selection_changed" in err(res[1])


# ---- preview: only the bridge's own, unaltered, single use ---------------------------------------------------
@pytest.mark.parametrize("fam", ("cleanup", "nudge", "atlas", "ucx"))
def test_altered_replayed_or_foreign_preview_is_refused_and_creates_nothing(fake, fam):
    w = fake.world
    count = len(w.nodes)

    def altered(out):
        p = json.loads(json.dumps(ok(out[0])))
        p["report"]["objects"][0]["name"] += "x"
        return APPLY_TOOL[fam], p2_args(fam, [1], preview=p)
    other = "nudge" if fam != "nudge" else "atlas"
    res = session([(PREVIEW_TOOL[fam], p2_args(fam, [1])), altered,
                   lambda out: (APPLY_TOOL[fam], p2_args(fam, [1], preview=ok(out[0]))),
                   lambda out: (APPLY_TOOL[fam], p2_args(fam, [1], preview=ok(out[0]))),
                   (PREVIEW_TOOL[other], p2_args(other, [1])),
                   lambda out: (APPLY_TOOL[fam], p2_args(fam, [1], preview=ok(out[4])))], fake.transport)
    assert "unknown or altered" in err(res[1])
    ok(res[2])
    assert "unknown or altered" in err(res[3]), "a preview was applied twice"
    assert "unknown or altered" in err(res[5]), "another family's preview was accepted"
    assert len(w.nodes) == count + (2 if fam == "ucx" else 1), "only the one good apply may create nodes"


def test_stale_preview_after_scene_change_is_refused(fake):
    w = fake.world

    def change_then_apply(out):
        w.nodes[1].uv[0] += 0.5
        return "agr_uv_nudge_apply", p2_args("nudge", [1], preview=ok(out[0]))
    res = session([("agr_uv_nudge_preview", p2_args("nudge", [1])), change_then_apply], fake.transport)
    assert "stale" in err(res[1]) and len(w.nodes) == 3


# ---- writes only to new nodes / new paths ---------------------------------------------------------------------
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
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file() and "locks" not in p.parts}
    args = p2_args("export", [1], target)
    args["scene"] = doc or "live"
    res = session([("agr_export_preview", args)], fake.transport)
    assert "invalid input" in err(res[0])
    assert fake.sent == [], "Max was called for a forbidden target"
    after = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file() and "locks" not in p.parts
             and p.name != "audit.jsonl"}
    assert after == {p: b for p, b in before.items() if p.name != "audit.jsonl"}


def test_export_commit_writes_one_new_fbx_and_a_second_commit_is_refused(fake, tmp_path):
    target = tmp_path / "SM_Syn_001_Main.fbx"
    res = session([("agr_export_preview", p2_args("export", [1], target)),
                   lambda out: ("agr_export_commit", p2_args("export", [1], target, preview=ok(out[0]))),
                   lambda out: ("agr_export_commit", p2_args("export", [1], target, preview=ok(out[0])))],
                  fake.transport)
    assert ok(res[1])["plan"]["readback"] == {"object_count": 1}
    assert "target path exists" in err(res[2])
    assert target.read_bytes() == b"FBX synthetic" and len(fake.world.nodes) == 3
    lines = audit_lines(tmp_path)
    assert lines[1]["written"] == [str(target), str(target.with_suffix(".report.json"))]


def _patch_runtime(fake, src):
    (fake.root / "runtime.py").write_text(FAKE_RUNTIME_090 + src, encoding="utf-8")
    sys.modules.pop("runtime", None)


def test_apply_that_deletes_a_source_is_an_error_naming_it(fake):
    _patch_runtime(fake, '''
_orig = cleanup_apply
def cleanup_apply(nodes, preview):
    out = _orig(nodes, preview)
    _rt().delete([_rt().maxOps.getNodeByHandle(2)])
    return out
''')
    res = session([("agr_cleanup_preview", p2_args("cleanup", [1])),
                   lambda out: ("agr_cleanup_apply", p2_args("cleanup", [1], preview=ok(out[0])))], fake.transport)
    assert "source nodes deleted: [2]" in err(res[1])


def test_apply_that_leaves_an_unreported_node_is_an_error(fake):
    _patch_runtime(fake, '''
_orig = nudge_apply
def nudge_apply(nodes, preview):
    out = _orig(nodes, preview)
    _rt().add("stray", [0, 0])
    return out
''')
    res = session([("agr_uv_nudge_preview", p2_args("nudge", [1])),
                   lambda out: ("agr_uv_nudge_apply", p2_args("nudge", [1], preview=ok(out[0])))], fake.transport)
    assert "!= reported copies" in err(res[1])


def test_preview_that_creates_a_node_is_an_error(fake):
    _patch_runtime(fake, '''
_orig_p = atlas_preview
def atlas_preview(nodes=None):
    _rt().add("leak", [0, 0])
    return _orig_p(nodes)
''')
    (res,) = session([("agr_atlas_preview", p2_args("atlas", [1]))], fake.transport)
    assert "left new nodes" in err(res)


def test_preview_with_bytes_is_shown_as_length_and_sha_and_still_applies(fake):
    """Native run 1 finding: runtime.atlas_preview carries PNG bytes ('images'); json.dumps failed with TypeError."""
    _patch_runtime(fake, '''
_orig_p = atlas_preview
def atlas_preview(nodes=None):
    d = _orig_p(nodes)
    d["images"] = tuple(b"PNG" + bytes([n.handle]) for n in nodes)
    return d
''')
    res = session([("agr_atlas_preview", p2_args("atlas", [1])),
                   lambda out: ("agr_atlas_apply", p2_args("atlas", [1], preview=ok(out[0])))], fake.transport)
    import hashlib
    assert ok(res[0])["images"] == [{"bytes": 4, "sha256": hashlib.sha256(b"PNG\x01").hexdigest()}]
    assert ok(res[1])["copies"][0]["name"] == "SM_Syn_001_Main_AGR_atlas_"


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
    # The MCP client already turns NaN/inf into null; below it, the server guard and the pipe encoder refuse them.
    args = p2_args("cleanup", [1], options={"x": bad})
    with pytest.raises(ValueError, match="non-finite"):
        tools._check_finite(args, "arguments")
    from agr_mcp import max_pipe
    with pytest.raises(ValueError):
        max_pipe.bridge_script("agr_cleanup_preview", "", args)


# ---- lock and journal -----------------------------------------------------------------------------------------
def test_every_phase2_tool_is_refused_while_the_live_lock_is_held(fake, tmp_path):
    lock = tmp_path / "locks" / "agr-3dsmax-live.lock"
    lock.parent.mkdir(parents=True)
    calls = [(n, p2_args("export" if "export" in n else "x", [1], tmp_path / f"{n}.fbx",
                         **({"preview": {}} if n.endswith(("_apply", "_commit")) else {})))
             for n in tools.PHASE2]
    with locks.hold("max-live", "other-card", 60):
        res = session(calls, fake.transport)
    assert all("busy" in err(r) for r in res)
    lines = audit_lines(tmp_path)
    assert len(lines) == 10 and {x["status"] for x in lines} == {"busy"}
    assert all(x["lock"].endswith("agr-3dsmax-live.lock") for x in lines) and fake.sent == []


def test_journal_has_one_line_per_call_with_written_and_targets(fake, tmp_path):
    w = fake.world
    w.select([w.nodes[2]])
    res = session([("agr_ucx_preview", {"scene": "live", "scope": "selection"}),
                   lambda out: ("agr_ucx_apply", {"scene": "live", "scope": "selection", "preview": ok(out[0])}),
                   ("agr_ucx_apply", {"scene": "live", "handles": [2], "preview": {}}),
                   ("agr_nope", {})], fake.transport)
    ok(res[1])
    lines = audit_lines(tmp_path)
    assert [x["tool"] for x in lines] == ["agr_ucx_preview", "agr_ucx_apply", "agr_ucx_apply", "agr_nope"]
    assert [x["status"] for x in lines] == ["ok", "ok", "error", "refused"]
    assert lines[1]["scope"] == "selection" and lines[1]["handles"] == [2]
    assert lines[1]["written"] == ["SM_Syn_002_Main_AGR_ucx_", "UCX_SM_Syn_002_Main_AGR_ucx__001"]
    assert all(x["host"] == "max-live" for x in lines[:3])


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
    """Invariants over 120 generated calls: the runtime never gets None/empty targets; a contract error never
    reaches Max; the selection is the same before and after every call; nothing in the scene is deleted;
    new nodes only come from a successful apply; one audit line per call."""
    rng = random.Random(1021)
    w = fake.world
    cases, expected_ok = [], 0
    for i in range(120):
        fam = rng.choice(("cleanup", "nudge", "atlas", "ucx"))
        handles = rng.sample([1, 2, 3, 9], rng.randint(0, 2))
        scope = rng.choice([None, None, "selection"])
        sel = rng.sample([1, 2, 3], rng.randint(0, 2))
        cases.append((fam, handles, scope, sel))
    seen = []

    def guarded(code, timeout):
        before = (sorted(n.handle for n in w.selection), sorted(w.nodes))
        out = fake.transport(code, timeout)
        after = (sorted(n.handle for n in w.selection), sorted(w.nodes))
        seen.append(before == after)
        return out

    def make(case):
        fam, handles, scope, sel = case

        def call(out):
            w.select([w.nodes[h] for h in sel])
            args = {"scene": "live", "handles": handles}
            if scope:
                args["scope"] = scope
            return PREVIEW_TOOL[fam], args
        return call
    res = session([make(c) for c in cases], guarded)
    calls = sys.modules["runtime"].CALLS if "runtime" in sys.modules else []
    for (fam, handles, scope, sel), r in zip(cases, res):
        valid = bool(handles) != bool(scope) and 9 not in handles and bool(handles or sel)
        assert (not r.isError) == valid, (fam, handles, scope, sel, r.content[0].text)
        expected_ok += valid
    assert all(nodes for _fn, nodes in calls) and len(calls) == expected_ok
    assert seen and all(seen), "a call changed the selection or the node set"
    assert len(audit_lines(tmp_path)) == 120
    print("PROBE seed 1021: 120/120 calls, ok", expected_ok, "max calls", len(seen))
