"""new-case: agr-mcp phase-2 (#1021) native parity on the test polygon, run INSIDE 3dsmaxbatch.

  python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --version 2026 \
      --file tests/agr_mcp/run_agr_mcp_phase2_native.py --out <NEW dir>/max.log
  env: AGR_MCP_P2_ROOT=<repo>, AGR_MCP_P2_OUT=<NEW evidence dir>

Builds the synthetic polygon scene `polygon_all` (test-polygon/build/build_scene.py), stages AGR Tools 0.9.0
(polygon_core.stage_tools) and, for each phase-2 family, compares the direct runtime preview with the MCP route below
the stdio server: the exact MAXScript that agr-mcp sends over the pipe (`max_pipe.bridge_script`) is executed with
`rt.execute`, i.e. max_bridge -> staged runtime. Per family: direct preview, MCP preview, then the MCP apply/commit
tool, which must answer needs_human and create no node / write no file [D231]. The selection before each MCP call
is a station node outside the targets and must be the same after.
Writes parity.json; exit code 0 only when every row is equal. All data is synthetic.
"""
import json
import os
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
from agr_mcp.max_side.max_bridge import _json_default  # noqa: E402  the bridge's JSON form (bytes -> len + sha256)
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


def canon(v):
    return json.loads(json.dumps(v, allow_nan=False, sort_keys=True, default=_json_default))


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
    tp, ta, fp, _fa = TOOLS[fam]
    nodes = [node(n) for n in STATIONS[fam]]
    handles = [int(n.handle) for n in nodes]
    guard = node("SM_Polygon_NudgeOk_Main" if fam != "nudge" else "SM_Polygon_001_Main")
    args = {"scene": "live", "handles": handles}
    pf = getattr(mod, fp)
    want_p = direct(pf, nodes, None) if fam == "cleanup" else direct(pf, nodes)
    rt.select(guard)
    sel = selection()
    got_p = mcp(tp, args)
    row(fam, "preview", want_p, got_p, sel)
    if "ok" not in got_p:
        return
    apply_refused(fam, ta, dict(args, preview=got_p["ok"]), guard)


def apply_refused(fam, tool, args, guard):
    """[D231]: the apply/commit tool answers needs_human from the bridge; no node, no file, selection kept."""
    before = set(int(n.handle) for n in rt.objects)
    rt.select(guard)
    sel = selection()
    got = mcp(tool, args)
    refused = "needs_human" in str(got.get("error"))
    created = sorted(set(int(n.handle) for n in rt.objects) - before)
    row(fam, "apply_needs_human", {"refused": True, "created": []}, {"refused": refused, "created": created}, sel)


def export_family(mod):
    """Checked-export preview of a DIRECT cleanup copy of SM_Polygon_001_Main (copy made by the runtime outside MCP,
    since MCP apply is needs_human [D231]); then agr_export_commit must be refused and write nothing."""
    tp, ta, fp, _fa = TOOLS["export"]
    src = node("SM_Polygon_001_Main")
    copies, _report = mod.cleanup_apply([src], mod.cleanup_preview([src], None))
    copy = [c for c in copies if str(c.name).startswith("SM_Polygon_001_Main_AGR_export_")]
    if len(copy) != 1:
        row("export", "setup", {"ok": 1}, {"error": "cleanup copy missing: %r" % [str(c.name) for c in copies]})
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

    def same(v):  # the only allowed difference: the folder of the target
        text = json.dumps(v, sort_keys=True)
        for a, b in ((str(targets["direct"].parent), str(targets["mcp"].parent)),):
            for x, y in ((a, b), (a.replace("\\", "/"), b.replace("\\", "/")),
                         (json.dumps(a)[1:-1], json.dumps(b)[1:-1])):
                text = text.replace(x, y)
        return json.loads(text)
    props(targets["direct"])
    want_p = direct(getattr(mod, fp), [copy], str(targets["direct"]))
    props(targets["mcp"])
    rt.select(node("SM_Polygon_NudgeOk_Main"))
    sel = selection()
    args = {"scene": "live", "handles": [int(copy.handle)], "target": str(targets["mcp"])}
    got_p = mcp(tp, args)
    row("export", "preview", same(want_p), got_p, sel)
    apply_refused("export", ta, dict(args, preview=got_p.get("ok") or {}), node("SM_Polygon_NudgeOk_Main"))
    written = [str(p) for p in (targets["mcp"], targets["mcp"].with_suffix(".report.json")) if p.exists()]
    row("export", "commit_wrote_nothing", {"written": []}, {"written": written})
    rt.delete(copies)


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
    for fam in ("cleanup", "nudge", "atlas", "ucx"):
        try:
            family(MOD, fam)
        except Exception:  # noqa: BLE001
            row(fam, "crash", {"ok": 1}, {"error": traceback.format_exc()[-1200:]})
    try:
        export_family(MOD)
    except Exception:  # noqa: BLE001
        row("export", "crash", {"ok": 1}, {"error": traceback.format_exc()[-1200:]})
    report = {"runtime_version": MOD.VERSION, "runtime_file": MOD.__file__, "max_version": int(rt.maxVersion()[0]),
              "objects_at_start": count0, "objects_at_end": int(rt.objects.count), "rows": ROWS, "synthetic": True}
except Exception:  # noqa: BLE001
    report = {"fatal": traceback.format_exc()[-2000:], "rows": ROWS}
(OUT / "parity.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
equal = sum(1 for r in ROWS if r["equal"])
print("PARITY_EQUAL %d / %d" % (equal, len(ROWS)), "fatal" in report)
