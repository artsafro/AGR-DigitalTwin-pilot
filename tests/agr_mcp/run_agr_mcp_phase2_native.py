"""new-case: agr-mcp phase-2 (#1021) native parity on the test polygon, run INSIDE 3dsmaxbatch.

  python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --version 2026 \
      --file tests/agr_mcp/run_agr_mcp_phase2_native.py --out <NEW dir>/max.log
  env: AGR_MCP_P2_ROOT=<repo>, AGR_MCP_P2_OUT=<NEW evidence dir>

Builds the synthetic polygon scene `polygon_all` (test-polygon/build/build_scene.py), stages AGR Tools 0.9.0
(polygon_core.stage_tools) and, for each phase-2 family, compares the direct runtime call with the MCP route below
the stdio server: the exact MAXScript that agr-mcp sends over the pipe (`max_pipe.bridge_script`) is executed with
`rt.execute`, i.e. max_bridge -> staged runtime. Order per family: direct preview, MCP preview, direct apply
(its copies deleted again), MCP apply with the MCP preview. Copy handles and atlas uuids are normalised; nothing
else. The selection before each MCP call is a station node outside the targets and must be the same after.
Writes parity.json; exit code 0 only when every row is equal. All data is synthetic.
"""
import json
import os
import re
import sys
import traceback
from pathlib import Path

ROOT = Path(os.environ["AGR_MCP_P2_ROOT"])
OUT = Path(os.environ["AGR_MCP_P2_OUT"])
OUT.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(ROOT / "test-polygon" / "build"), str(ROOT / "test-polygon"), str(ROOT), str(ROOT / "src")]
os.environ["AGR_TEST_OUTPUT"] = str(OUT)  # atlas PNGs go to <OUT>/atlases, new uuid names

import build_scene  # noqa: E402
import polygon_core  # noqa: E402
from agr_mcp import max_pipe  # noqa: E402
from agr_mcp.max_side.max_bridge import _canonical  # noqa: E402  the bridge's JSON form (bytes -> len + sha256)
from pymxs import runtime as rt  # noqa: E402

STATIONS = {"cleanup": ["SM_Polygon_001_Main", "SM_Polygon_Chan_Main"],
            "nudge": ["SM_Polygon_NudgeOk_Main", "SM_Polygon_NudgeBad_Main"],
            "atlas": ["SM_Polygon_AtlasOk_Main", "SM_Polygon_AtlasBad_Main"],
            "ucx": ["SM_Polygon_001_Main"]}
TOOLS = {"cleanup": ("agr_cleanup_preview", "agr_cleanup_apply", "cleanup_preview", "cleanup_apply"),
         "nudge": ("agr_uv_nudge_preview", "agr_uv_nudge_apply", "nudge_preview", "nudge_apply"),
         "atlas": ("agr_atlas_preview", "agr_atlas_apply", "atlas_preview", "atlas_apply"),
         "ucx": ("agr_ucx_preview", "agr_ucx_apply", "ucx_preview", "ucx_apply"),
         "export": ("agr_export_preview", "agr_export_commit", "export_preview", "export_commit")}
UUID = re.compile(r"-[0-9a-f]{32}\.png")


def canon(v):
    return _canonical(v)[0]


def node(name):
    n = rt.getNodeByName(name)
    if n is None:
        raise ValueError("missing polygon node " + name)
    return n


def mcp(tool, args):
    raw = rt.execute(max_pipe.bridge_script(tool, str(STAGE), args))
    payload = json.loads(max_pipe.decode_value(str(raw)))
    if payload.get("ok") is not True:
        return {"error": payload.get("error")}
    return {"ok": payload["result"]}


def direct(fn, *a):
    try:
        return {"ok": canon(fn(*a))}
    except Exception as exc:  # noqa: BLE001
        return {"error": type(exc).__name__ + ": " + str(exc)}


def norm(value, copies):
    """Copy node/anim handles -> 'copy#i'; atlas PNG uuid -> '-<uuid>.png'. Nothing else is touched."""
    ids = {}
    for i, c in enumerate(copies):
        ids[int(c.handle)] = "copy#%d" % i
        ids[int(rt.getHandleByAnim(c))] = "copy#%d" % i

    def walk(v, key=None):
        if isinstance(v, dict):
            return {k: walk(x, k) for k, x in v.items()}
        if isinstance(v, list):
            return [walk(x, key) for x in v]
        if key in ("handle", "handles", "ids") and isinstance(v, int) and v in ids:
            return ids[v]
        if isinstance(v, str):
            return UUID.sub("-<uuid>.png", v)
        return v
    return walk(value)


def selection():
    return sorted(int(n.handle) for n in rt.selection)


def row(fam, step, want, got, sel_before=None, extra=None):
    equal = want == got
    r = {"family": fam, "step": step, "equal": equal, "direct": want, "mcp": got}
    if sel_before is not None:
        r["selection_before"], r["selection_after"] = sel_before, selection()
        r["equal"] = equal and r["selection_before"] == r["selection_after"]
    if extra:
        r.update(extra)
    status = (got.get("ok") or {}).get("status") if isinstance(got.get("ok"), dict) else None
    if status is None and isinstance(got.get("ok"), dict) and isinstance(got["ok"].get("report"), dict):
        status = got["ok"]["report"].get("status")
    print("ROW", fam, step, "equal=%s" % r["equal"], "status=%s" % (status or got.get("error", "")[:80]))
    ROWS.append(r)


def family(mod, fam):
    tp, ta, fp, fa = TOOLS[fam]
    nodes = [node(n) for n in STATIONS[fam]]
    handles = [int(n.handle) for n in nodes]
    guard = node("SM_Polygon_NudgeOk_Main" if fam != "nudge" else "SM_Polygon_001_Main")
    args = {"scene": "live", "handles": handles}
    pf, af = getattr(mod, fp), getattr(mod, fa)
    want_p = direct(pf, nodes, None) if fam == "cleanup" else direct(pf, nodes)
    rt.select(guard)
    sel = selection()
    got_p = mcp(tp, args)
    row(fam, "preview", want_p, got_p, sel)
    if "ok" not in want_p or "ok" not in got_p:
        return None
    before = set(int(n.handle) for n in rt.objects)
    native_p = pf(nodes, None) if fam == "cleanup" else pf(nodes)
    try:
        copies, report = af(nodes, native_p)
        want_a = {"ok": canon({"copies": [{"handle": int(c.handle), "name": str(c.name)} for c in copies],
                               "report": report})}
        want_a = {"ok": norm(want_a["ok"], copies)}
        rt.delete(copies)
    except Exception as exc:  # noqa: BLE001
        want_a = {"error": type(exc).__name__ + ": " + str(exc)}
    leftover = sorted(set(int(n.handle) for n in rt.objects) - before)
    rt.select(guard)
    sel = selection()
    got_a = mcp(ta, dict(args, preview=got_p["ok"]))
    created = []
    if "ok" in got_a:
        created = [rt.maxOps.getNodeByHandle(c["handle"]) for c in got_a["ok"]["copies"]]
        got_a = {"ok": norm(got_a["ok"], created)}
    row(fam, "apply", want_a, got_a, sel, {"direct_leftover_nodes": leftover})
    return created


def export_family(mod, cleanup_copies):
    """Checked export of the MCP cleanup copy of SM_Polygon_001_Main into two new FBX paths (same file name)."""
    tp, ta, fp, fa = TOOLS["export"]
    copy = [c for c in cleanup_copies if str(c.name).startswith("SM_Polygon_001_Main_AGR_export_")]
    if len(copy) != 1:
        row("export", "setup", {"ok": 1}, {"error": "cleanup copy missing: %r" % [str(c.name) for c in cleanup_copies]})
        return
    copy = copy[0]
    targets = {}
    for side in ("direct", "mcp"):
        t = polygon_core.checked_export_target(OUT / side, str(copy.name))
        t.parent.mkdir(parents=True, exist_ok=True)
        targets[side] = t

    def props(t):
        rt.setUserProp(copy, "AGR_EXPORT_PATH", str(t).replace("\\", "/"))
        rt.setUserProp(copy, "AGR_TEXEL_PROFILE", "NPM")
        mat = copy.material
        names = ([str(s.name) for s in mat.materialList if s is not None] if rt.classOf(mat) == rt.MultiMaterial
                 else [str(mat.name)])
        rt.setUserProp(copy, "AGR_TEXEL_MAP", ";".join(n + "=128" for n in names))

    def same(v):  # the only allowed difference: the folder of the target (FBX and its .report.json)
        text = json.dumps(v, sort_keys=True)
        for a, b in ((str(targets["direct"].parent), str(targets["mcp"].parent)),):
            for x, y in ((a, b), (a.replace("\\", "/"), b.replace("\\", "/")),
                         (json.dumps(a)[1:-1], json.dumps(b)[1:-1])):
                text = text.replace(x, y)
        return json.loads(text)
    props(targets["direct"])
    want_p = direct(getattr(mod, fp), [copy], str(targets["direct"]))
    want_c = direct(getattr(mod, fa), [copy], mod.export_preview([copy], str(targets["direct"])),
                    str(targets["direct"])) if want_p.get("ok", {}).get("status") == "pass" else {"error": "no pass"}
    props(targets["mcp"])
    rt.select(node("SM_Polygon_NudgeOk_Main"))
    sel = selection()
    args = {"scene": "live", "handles": [int(copy.handle)], "target": str(targets["mcp"])}
    got_p = mcp(tp, args)
    row("export", "preview", same(want_p), got_p, sel)
    got_c = mcp(ta, dict(args, preview=got_p.get("ok"))) if "ok" in got_p else {"error": "no preview"}
    diff = []
    if "ok" in want_c and "ok" in got_c:
        a, b = same(want_c["ok"]), got_c["ok"]

        def keys(x, y, path=""):
            if isinstance(x, dict) and isinstance(y, dict):
                for k in sorted(set(x) | set(y)):
                    keys(x.get(k), y.get(k), path + "/" + k)
            elif x != y:
                diff.append(path)
        keys(a, b)
    row("export", "commit", same(want_c), got_c, sel,
        {"differing_keys": diff, "fbx": {s: [str(t), t.is_file(), t.stat().st_size if t.is_file() else None]
                                          for s, t in targets.items()}})


ROWS = []
try:
    STAGE = polygon_core.stage_tools(OUT / "stage", ROOT)
    os.environ["AGR_TOOLS_REPO"] = str(ROOT)
    venv = ROOT / ".venv" / "Scripts" / "python.exe"
    if venv.is_file():
        os.environ.setdefault("AGR_PYTHON", str(venv))
    sys.modules.pop("runtime", None)
    sys.path.insert(0, str(STAGE))
    import runtime as MOD  # noqa: E402  the same module object max_bridge._load_runtime will find
    build_scene.build("polygon_all", texture_dir=str(OUT / "textures"))
    count0 = int(rt.objects.count)
    made = {}
    for fam in ("cleanup", "nudge", "atlas", "ucx"):
        try:
            made[fam] = family(MOD, fam) or []
        except Exception:  # noqa: BLE001
            row(fam, "crash", {"ok": 1}, {"error": traceback.format_exc()[-1200:]})
    try:
        export_family(MOD, made.get("cleanup") or [])
    except Exception:  # noqa: BLE001
        row("export", "crash", {"ok": 1}, {"error": traceback.format_exc()[-1200:]})
    report = {"runtime_version": MOD.VERSION, "runtime_file": MOD.__file__, "max_version": int(rt.maxVersion()[0]),
              "objects_at_start": count0, "objects_at_end": int(rt.objects.count), "rows": ROWS, "synthetic": True}
except Exception:  # noqa: BLE001
    report = {"fatal": traceback.format_exc()[-2000:], "rows": ROWS}
(OUT / "parity.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
equal = sum(1 for r in ROWS if r["equal"])
print("PARITY_EQUAL %d / %d" % (equal, len(ROWS)), "fatal" in report)
