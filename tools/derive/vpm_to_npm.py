"""Driver of the skeleton cell `vpm-to-npm` stages 1-5 (#1737): accepted VPM FBX -> NPM FBX + reports.

Pattern: n/a | new-case: one driver for tris-count / remove-interiors / atlas / glass-merge / budget-ladder; calls
the shared owners only (tools/derive/vpm_npm_core.py, tools/materials/npm_atlas_udim.py --mode oks, headless Blender
glue tools/blender/vpm_to_npm_bl.py) and stops on the first failure.

Usage: uv run python tools/derive/vpm_to_npm.py --job jobs/<ID> --out NEW_DIR [--blender EXE]
Config = `config` of jobs/<ID>/skeleton.json (scenario `vpm-to-npm`): vpm (VPM FBX copy), interiors {udims, objects},
glass [object names merged into ONE <Main>Glass], budget (tris, default NPM_STANDARD oks_triangles_per_fbx_max),
atlas {size, diffuse: UDIM file pattern next to the VPM FBX}. The input VPM is never written; NEW_DIR must not exist.
Writes NEW_DIR/vpm_to_npm_report.json (tris before/after, dropped faces by reason, atlas, glass cell + white samples,
ladder ran/skipped/missing), NEW_DIR/atlas/ (npm_atlas_udim outputs + T_*_d.png with the white glass cell) and
NEW_DIR/npm/<name>.fbx. Exit 0 within budget, 1 over budget (a ladder step missing), 2 bad input / failed stage.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.derive import vpm_npm_core as core  # noqa: E402
from tools.materials import npm_atlas_udim as atlas_tool  # noqa: E402

DEFAULT_BUDGET = 150000  # standards/NPM_STANDARD.yaml geometry.oks_triangles_per_fbx_max
GLASS_CELL_PX = 16
CONFIG_KEYS = ("vpm", "interiors", "glass", "budget", "atlas")


def _blender(exe, mode, *args):
    from dt_ai.core.blender_runner import blender_command
    cmd = blender_command(str(ROOT / "tools" / "blender" / "vpm_to_npm_bl.py"), [mode, *map(str, args)], executable=exe)
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or "VPM2NPM-OK" not in r.stdout:
        tail = "\n".join((r.stdout + r.stderr).splitlines()[-15:])
        raise core.VpmNpmError(f"blender {mode} failed (exit {r.returncode}):\n{tail}")


def _write_obj(path, faces, mtl_name, diffuse):
    """OBJ + MTL with one material per UDIM tile (npm_atlas_udim: one material = one tile)."""
    by_tile = {}
    for f in faces:
        by_tile.setdefault(core.face_udim(f["uv"]), []).append(f)
    lines, vlines, tlines, mtl = [f"mtllib {mtl_name}.mtl"], [], [], []
    for tile in sorted(by_tile):
        tex = Path(diffuse.replace("<UDIM>", str(tile)))
        if not tex.is_file():
            raise core.VpmNpmError(f"atlas: diffuse of UDIM {tile} missing: {tex}")
        mtl.append(f"newmtl M_{tile}\nKd 1 1 1\nmap_Kd {tex.as_posix()}\n")
        lines.append(f"usemtl M_{tile}")
        for f in by_tile[tile]:
            idx = []
            for p, t in zip(f["verts"], f["uv"]):
                vlines.append("v %.6f %.6f %.6f" % tuple(p))
                tlines.append("vt %.7f %.7f" % tuple(t))
                idx.append(f"{len(vlines)}/{len(tlines)}")
            lines.append("f " + " ".join(idx))
    path.write_text("\n".join(vlines + tlines + lines) + "\n", encoding="utf-8")
    (path.parent / f"{mtl_name}.mtl").write_text("\n".join(mtl), encoding="utf-8")


def run(job, out, exe=None):
    sk = json.loads((Path(job) / "skeleton.json").read_text(encoding="utf-8"))
    if sk.get("scenario") != "vpm-to-npm":
        raise core.VpmNpmError(f"{job}/skeleton.json scenario is {sk.get('scenario')!r}, not 'vpm-to-npm'")
    cfg = sk.get("config", {})
    for k in CONFIG_KEYS:
        if k not in cfg:
            raise core.VpmNpmError(f"config: missing key {k!r}")
    vpm = Path(cfg["vpm"]).resolve()
    out = Path(out).resolve()
    if out.exists():
        raise core.VpmNpmError(f"output {out} already exists; choose a new version")
    if vpm.parent == out or out in vpm.parents:
        raise core.VpmNpmError(f"output {out} aliases the input {vpm}")
    budget = cfg["budget"] if cfg["budget"] is not None else DEFAULT_BUDGET
    glass_names = cfg["glass"]
    if not isinstance(glass_names, list) or not glass_names:
        raise core.VpmNpmError("config: glass must list the glass object names")
    out.mkdir(parents=True)
    work = out / "work"
    work.mkdir()
    # stage 1 tris-count (Blender dumps the VPM render meshes; UCX excluded)
    _blender(exe, "dump", vpm, work / "vpm_faces.json")
    dump = json.loads((work / "vpm_faces.json").read_text(encoding="utf-8"))
    objs = dump["objects"]
    for g in glass_names:
        if g not in objs:
            raise core.VpmNpmError(f"config: glass object {g} is not in the VPM ({sorted(objs)})")
    mains = [n for n in objs if n not in glass_names]
    if len(mains) != 1:
        raise core.VpmNpmError(f"expected exactly one non-glass render object, got {mains}")
    main = mains[0]
    main_faces = objs[main]
    glass_faces = [f for g in glass_names for f in objs[g]]
    tris_vpm = {n: core.count_tris(f) for n, f in objs.items()}
    # stage 2 remove-interiors
    rem = core.remove_interiors(main_faces, cfg["interiors"])
    kept = [main_faces[i] for i in rem["kept"]]
    by_reason = {}
    for d in rem["dropped"]:
        by_reason[d["reason"]] = by_reason.get(d["reason"], 0) + 1
    # stage 3 atlas (npm_atlas_udim --mode oks)
    adir = out / "atlas"
    _write_obj(work / "main_kept.obj", kept, "main_kept", str(vpm.parent / cfg["atlas"]["diffuse"]))
    base = f"T_{main[3:-5]}_Main"  # SM_<A>_<NNN>_Main -> T_<A>_<NNN>_Main
    size = int(cfg["atlas"].get("size", 2048))
    mesh, mats = atlas_tool.read_obj(work / "main_kept.obj")
    res = atlas_tool.pack(mesh, mats, mode="oks", size=size)
    if not res["report"]["passed"]:
        (work / "atlas_report_failed.json").write_text(json.dumps(res["report"], indent=1, default=str), "utf-8")
        raise core.VpmNpmError("atlas: npm_atlas_udim report fails (work/atlas_report_failed.json)")
    paths = atlas_tool.write_outputs(mesh, res, adir, base, [work / "main_kept.obj"])
    meas = atlas_tool.readback(paths, mesh, res["cells"], mode="oks", pad_min=atlas_tool.PADDING_MIN_PX)
    if not meas["passed"]:
        raise core.VpmNpmError("atlas: read-back of the written atlas fails")
    # stage 4 glass-merge on pure white atlas pixels
    px = np.array(Image.open(paths["diffuse"]).convert("RGB"))
    cell = core.find_white(px, min_px=GLASS_CELL_PX)
    reserved = cell is None
    if reserved:
        cell = core.reserve_white(px, occupied=[tuple(c) for c in res["cells"].values()], size_px=GLASS_CELL_PX,
                                  pad=atlas_tool.PADDING_MIN_PX)
    glass_name = main + "Glass"
    gm = core.glass_merge(glass_faces, px, name=glass_name, cell=cell)
    final_d = adir / f"{base}_d_1.png"
    Image.fromarray(px).save(final_d)
    if core.find_white(np.array(Image.open(final_d).convert("RGB")), min_px=cell[2]) is None:
        raise core.VpmNpmError("glass-merge: white cell not found on the written atlas")
    (work / "glass.json").write_text(json.dumps({"name": glass_name, "faces": gm["faces"]}), encoding="utf-8")
    # stage 5 budget-ladder (no ladder step hooks in this driver: a needed step is reported missing)
    tris_npm = rem["tris_after"] + core.count_tris(gm["faces"])
    ladder = core.budget_ladder(tris_npm, budget, {})
    report = {"tool": "tools/derive/vpm_to_npm.py", "issue": "#1737", "vpm": str(vpm), "job": str(job),
              "tris_count": {"vpm": tris_vpm, "vpm_total": sum(tris_vpm.values())},
              "remove_interiors": {"config": cfg["interiors"], "tris_before": rem["tris_before"],
                                   "tris_after": rem["tris_after"], "dropped_faces": len(rem["dropped"]),
                                   "dropped_by_reason": by_reason},
              "atlas": {"size": size, "diffuse": str(final_d), "obj": str(paths["obj"]),
                        "materials": len(res["report"]["materials"]), "used": res["report"]["used"],
                        "min_island_gap_px": res["report"].get("min_island_gap_px"), "readback_passed": True},
              "glass_merge": {"object": glass_name, "merged_from": gm["merged_from"], "cell": list(cell),
                              "reserved": reserved, "uv_samples": gm["uv_samples"],
                              "white_samples": gm["white_samples"], "tris": core.count_tris(gm["faces"])},
              "budget_ladder": ladder, "npm_tris": tris_npm}
    if ladder["within"]:
        _blender(exe, "build", paths["obj"], work / "glass.json", final_d, main, out / "npm")
        report["npm_fbx"] = str(out / "npm" / f"{main}.fbx")
    (out / "vpm_to_npm_report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--job", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--blender")
    a = ap.parse_args(argv)
    try:
        rep = run(a.job, a.out, a.blender)
    except (core.VpmNpmError, atlas_tool.AtlasError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    lad = rep["budget_ladder"]
    print(f"vpm-to-npm: vpm {rep['tris_count']['vpm_total']} tris -> npm {rep['npm_tris']} (budget {lad['budget']}); "
          f"ladder ran={lad['ran']} missing={lad['missing']}")
    return 0 if lad["within"] else 1


if __name__ == "__main__":
    sys.exit(main())
