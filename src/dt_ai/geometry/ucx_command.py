"""`agr ucx`: one UCX command for a VPM body (Main) and for Ground [D330, narrows D225] (#1404).

Pattern: n/a | new-case: CLI chain over the two UCX cores (build, then readback gap + V010 check), no geometry code.

    agr ucx MODEL OUT Main|Ground [key=value ...] [--blender EXE] [--gap-m M]

One core per function [D330]:
1. BUILD - `src/dt_ai/geometry/ucx_build.py::build` through its Blender driver `tools/blender/ucx_build.py`
   (program: Blender, headless; why: the builder's driver imports/exports FBX with bpy, numpy core, no Max needed).
   key=value options are the driver's (cell, gap, min_cell, tol, depth, object, with) and pass unchanged.
2. READBACK - a fresh Blender process imports OUT (`twinqa.scene.readback`, tools/blender/fbx_readback.py).
3. GAP CHECK - `adapters/max/agr_tools/ucx10_core.py::plan` (the AGR Tools `ucx.gap` core, stdlib; the same code
   runs inside 3ds Max) on the read-back UCX pieces. The command only MEASURES: a pair under the gap or a
   non-convex piece is a failure; the fix is AGR Tools `ucx.gap` in Max on an export copy, never here.
4. V010 - `twinqa.scene.scene_findings(...)["V010"]` on the same readback (role oks for Main, ground for Ground).

Writes OUT (FBX), `OUT.ucx_build.json` (driver) and `OUT.agr_ucx.json` (this command). Never overwrites: OUT and
both reports must not exist, must not alias MODEL and must differ from each other; the model is never written.
Exit 0 every step passed; 1 built and read back but a check failed (gap, V010 fail, Ground tolerance); 2 build or
readback failed; 4 refused before any write.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DRIVER = ROOT / "tools" / "blender" / "ucx_build.py"
UCX10 = ROOT / "adapters" / "max" / "agr_tools" / "ucx10_core.py"
TARGETS = ("Main", "Ground")
ROLE = {"Main": "oks", "Ground": "ground"}
USAGE = "usage: agr ucx MODEL OUT Main|Ground [key=value ...] [--blender EXE] [--gap-m M]"


class Refused(ValueError):
    """Bad arguments or unsafe paths: nothing was written."""


def _ucx10():
    spec = importlib.util.spec_from_file_location("agr_ucx10_core", UCX10)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def parse(argv: list[str]) -> dict:
    """Validated arguments; raises Refused naming the problem."""
    args, blender, gap = [], None, None
    it = iter(argv)
    for a in it:
        if a in ("--blender", "--gap-m"):
            value = next(it, None)
            if not value or value.startswith("--"):
                raise Refused(f"{a} needs a value")
            if a == "--blender":
                if blender is not None:
                    raise Refused("--blender given twice")
                blender = value
            else:
                if gap is not None:
                    raise Refused("--gap-m given twice")
                try:
                    gap = float(value)
                except ValueError:
                    raise Refused("--gap-m must be a number in metres") from None
                if not math.isfinite(gap):
                    raise Refused("--gap-m must be finite")
        elif a.startswith("--"):
            raise Refused(f"unknown option {a!r}")
        else:
            args.append(a)
    if len(args) < 3:
        raise Refused(USAGE)
    model, out, target, opts = Path(args[0]), Path(args[1]), args[2], args[3:]
    if target not in TARGETS:
        raise Refused(f"target must be Main or Ground, got {target!r}")
    for o in opts:
        if "=" not in o:
            raise Refused(f"bad builder option {o!r} (key=value)")
    if gap is not None:
        _ucx10().gap_options({"gap_m": gap})  # 0.002..0.010 m [D098]; ValueError -> refused
    if model.suffix.lower() not in (".fbx", ".blend"):
        raise Refused("MODEL must be an .fbx or .blend file")
    if out.suffix.lower() != ".fbx":
        raise Refused("OUT must be an .fbx path")
    if not model.is_file():
        raise Refused(f"no input file {model}")
    paths = {"out": out, "build_report": out.with_name(out.name + ".ucx_build.json"),
             "report": out.with_name(out.name + ".agr_ucx.json")}
    src = model.resolve()
    for key, p in paths.items():
        if p.exists() or p.is_symlink():
            raise Refused(f"{key} {p} exists; write a new versioned path, nothing overwritten")
        if p.resolve() == src:
            raise Refused(f"{key} {p} aliases the input model")
    if len({p.resolve() for p in paths.values()}) != len(paths):
        raise Refused("output and report paths collide")
    return {"model": model, "target": target, "opts": opts, "blender": blender, "gap_m": gap, **paths}


def gap_check(meshes: list[dict], gap_m: float) -> dict:
    """ucx10_core.plan on read-back UCX meshes ({name, hull: {verts, tris}}); measure only, nothing is written.

    ok is False for an empty set, a mesh without hull data, a non-convex piece, any pair under gap_m (touching and
    overlapping included) or a pair still under it; every UCX mesh ends in `pieces` or in `dropped` with a reason."""
    core = _ucx10()
    opts = core.gap_options({"gap_m": gap_m})
    rows, dropped = [], []
    for i, m in enumerate(meshes):
        hull = m.get("hull") or {}
        if not hull.get("verts") or not hull.get("tris"):
            dropped.append({"name": m.get("name"), "reason": "no hull data in the readback"})
            continue
        rows.append({"handle": i, "name": m["name"], "verts": hull["verts"], "tris": hull["tris"]})
    if not rows:
        return {"ok": False, "error": "no UCX pieces with hull data: an empty set is not a pass",
                "dropped": dropped, "gap_m": opts["gap_m"]}
    res = core.plan(rows, opts)
    names = {r["handle"]: r["name"] for r in rows}
    findings = {names[h]: v for h, v in res["findings"].items()}
    s = res["summary"]
    bad_pairs = list(res["pairs"])
    ok = not (dropped or res["skipped"] or findings or bad_pairs or s["left"] or res["ambiguous"])
    return {"ok": ok, "gap_m": opts["gap_m"], "pieces": len(rows), "families": s["families"],
            "pairs_under_gap": [{k: p[k] for k in ("family", "a", "b", "gap_before_m", "code")} for p in bad_pairs],
            "left": s["left"], "ambiguous": res["ambiguous"], "skipped": res["skipped"], "dropped": dropped,
            "findings": findings, "fix": "AGR Tools ucx.gap (ucx10_core) in 3ds Max on an export copy"}


def _v010(rb: dict, target: str) -> list[dict]:
    from twinqa.profiles import load_profiles
    from twinqa.scene import scene_findings

    found = scene_findings(rb, "vpm", ROLE[target], load_profiles().profile("vpm"))
    return [{"name": f.name, "status": f.status, "observed": f.observed, "expected": f.expected}
            for f in found.get("V010", [])]


def run(a: dict) -> tuple[int, dict]:
    from dt_ai.core.blender_runner import BlenderRunError, run_blender
    from twinqa.scene import readback, readback_log_dir

    report = {"command": "agr ucx", "decision": "D330", "model": str(a["model"]), "out": str(a["out"]),
              "target": a["target"], "options": a["opts"], "steps": {}}
    build_args = [str(a["model"]), str(a["out"]), a["target"], *a["opts"]]
    log = readback_log_dir() / f"agr-ucx-build-{a['out'].stem}.log"
    try:
        build = run_blender(DRIVER, build_args, executable=a["blender"], output_json=a["build_report"],
                            outputs=[a["out"]], timeout=3600, log_path=log)
        build_code = 0
    except BlenderRunError as exc:
        info = getattr(exc, "envelope", None) or {}
        build_code = info.get("returncode")
        build = None
        if build_code == 3 and a["out"].is_file() and a["build_report"].is_file():
            build = json.loads(a["build_report"].read_text(encoding="utf-8"))
        if build is None:
            report["steps"]["build"] = {"ok": False, "exit": build_code, "error": info.get("message", str(exc)),
                                        "log": str(log)}
            return 2, report
    report["steps"]["build"] = {"ok": build.get("ok") is True, "exit": build_code, "pieces": build.get("pieces"),
                                "triangles": build.get("triangles"), "gap_m": build.get("gap_m"),
                                "within_tol": build.get("within_tol"), "report": str(a["build_report"])}
    if build.get("ok") is not True:
        return 2, report
    rb = readback(a["out"], a["blender"])
    if not rb.get("readback_ok"):
        report["steps"]["readback"] = {"ok": False, "error": rb.get("error", "readback failed")}
        return 2, report
    ucx = [m for m in rb["meshes"] if str(m.get("name", "")).upper().startswith("UCX_")]
    report["steps"]["readback"] = {"ok": True, "meshes": len(rb["meshes"]), "ucx": len(ucx)}
    gap_m = a["gap_m"] if a["gap_m"] is not None else build.get("gap_m")
    if gap_m is None:
        report["steps"]["gap_check"] = {"ok": False, "error": "no --gap-m and no gap_m in the build report"}
        return 2, report
    gap = gap_check(ucx, gap_m)
    report["steps"]["gap_check"] = gap
    v010 = _v010(rb, a["target"])
    report["steps"]["V010"] = v010
    v010_ok = bool(v010) and not any(f["status"] == "fail" for f in v010)
    report["passed_checks"] = {"build_within_tol": build.get("within_tol") is True, "gap": gap["ok"],
                               "V010_no_fail": v010_ok}
    return (0 if all(report["passed_checks"].values()) else 1), report


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv in (["--help"], ["-h"]):
        print(__doc__)
        return 0
    try:
        a = parse(argv)
    except (Refused, ValueError) as exc:
        print(f"ERROR: agr ucx refused: {exc}; nothing written", file=sys.stderr)
        return 4
    code, report = run(a)
    report["exit"] = code
    a["report"].write_text(json.dumps(report, ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")
    print(f"AGR_UCX {code} {a['report']}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
