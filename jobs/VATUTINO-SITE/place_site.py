"""Vatutino site slice: MAF + Flora placement through the #316 engine and Blender instancing (#296).

Job script (not a shared tool). Inputs are COPIES / outputs outside git; the gate-1 answers of the user
(Artem 2026-10-20) are encoded in FLORA_PICKS / the exclusion reasons. Points over missing Ground are never
removed by handle here: the engine stops on them unless ``ground-exceptions.json`` holds a user-approved
exception bound to the sha256 of the Ground master being placed on (a repaired Ground re-places them).
Exit codes: 0 pass; 1 engine stop / invalid exception (nothing instanced); 3 scene technical QA failed
(scene equality or sinking): diagnostics kept in results.json, the scene renamed ``*.QA_FAILED.blend``. Nothing here computes placement:
``dt_ai.placement.engine.place`` does, ``tools/placement_site.py`` wraps it, ``tools/blender/
placement_instance.py`` instances it.

  uv run python jobs/VATUTINO-SITE/place_site.py --out C:/x/t_5e4ea2be/run_v001 --seed 296
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from dt_ai.placement import engine  # noqa: E402
from tools import placement_site as ps  # noqa: E402
from twinqa.scene import find_blender  # noqa: E402

CFG = {"adapter": Path("C:/x/t_d94665f2/paving_ground_inputs_v4.json"),
       "ground": Path("C:/x/t_d94665f2/ground_v014"),
       "flora_fbx": Path("C:/x/t_5e4ea2be/flora_fbx"),
       "site_parts": ROOT / "jobs/VATUTINO-SITE/site-parts.json",
       "maf_set": ROOT / "jobs/VATUTINO-SITE/maf/site-maf-set.json",
       "exceptions": ROOT / "jobs/VATUTINO-SITE/ground-exceptions.json",
       "flora_library": "C:/x/flora-library/v003/flora-library-v003.max"}
SCRIPT = ROOT / "tools/blender/placement_instance.py"
# gate-1 F2 (accepted 2026-10-20): schedule position -> library catalogue id
FLORA_PICKS = {1: 101, 3: 120, 4: 115, 6: 105, 7: 103, 9: 205, 11: 212, 12: 204, 14: 230, 15: 223, 17: 224}
EXACT = {11, 14, 15}


def spec_dims(v):
    ok = isinstance(v, list) and len(v) == 3 and all(isinstance(x, (int, float)) and x > 0 for x in v)
    return v if ok else None


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def blender(*args) -> dict:
    cmd = [find_blender(), "--background", "--factory-startup", "--python-exit-code", "1", "--python",
           str(SCRIPT), "--", *map(str, args)]
    t = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    rec = {"cmd": " ".join(f'"{c}"' if " " in c else c for c in cmd), "exit_code": r.returncode,
           "seconds": round(time.time() - t, 1)}
    if r.returncode:
        raise SystemExit(f"blender failed {rec}\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}")
    return rec


def _rel(p: Path) -> str:
    try:
        return Path(p).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


def run(cfg: dict, out: Path, seed: int, dcc=blender) -> int:
    out = Path(out)
    if out.exists():
        raise SystemExit(f"{out} exists: new versioned output dirs only")
    out.mkdir(parents=True)
    a_seed = seed
    adapter = json.loads(cfg["adapter"].read_text(encoding="utf-8"))
    parts = json.loads(cfg["site_parts"].read_text(encoding="utf-8"))
    mafset = json.loads(cfg["maf_set"].read_text(encoding="utf-8"))["positions"]
    exc_path = Path(cfg["exceptions"])
    exceptions = json.loads(exc_path.read_text(encoding="utf-8"))["exceptions"] if exc_path.is_file() else []
    FLORA_FBX, GROUND = Path(cfg["flora_fbx"]), Path(cfg["ground"])
    inputs = {"adapter": {"path": str(cfg["adapter"]), "sha256": sha(cfg["adapter"])},
              "site_parts": {"path": _rel(cfg["site_parts"]), "sha256": sha(cfg["site_parts"])},
              "maf_set": {"path": _rel(cfg["maf_set"]), "sha256": sha(cfg["maf_set"])},
              "ground_exceptions": {"path": _rel(exc_path), "sha256": sha(exc_path) if exc_path.is_file() else None,
                                    "entries": len(exceptions)},
              "flora_library": {"path": str(cfg["flora_library"]), "export_dir": str(FLORA_FBX)}}
    flora_rows = {}
    for f in parts["flora"]:
        pick = FLORA_PICKS.get(f["pos"])
        c = next((c for c in f["cands"] if c["id"] == pick), None) if pick else None
        flora_rows[f["block"]] = {"pos": f["pos"], "ru": f["ru"], "latin": f["latin"], "qty": f["qty"],
                                  "h_m": [f["h_cm"][0] / 100.0, f["h_cm"][1] / 100.0], "cand": c,
                                  "spozu_in": f["spozu_in"], "spozu_total": f["spozu_total"],
                                  "match": "exact" if f["pos"] in EXACT else ("substitute" if c else "no_model")}
    export = json.loads((FLORA_FBX / "export.json").read_text(encoding="utf-8"))["objects"]
    results = {"seed": a_seed, "inputs": inputs, "status": "running", "variants": {}}
    qa_failed = False
    for var in ("npm", "vpm"):
        V = var.upper()
        vdir = out / var
        vdir.mkdir()
        gm_path = GROUND / f"ground_master_{var}.json"
        gm = json.loads(gm_path.read_text(encoding="utf-8"))
        offset = json.loads((GROUND / f"readback_{var}.json").read_text(encoding="utf-8"))["placement_offset"]
        g_fbx = GROUND / var / "SM_Vatutino_Ground.fbx"
        inputs[f"ground_{var}"] = {"master": str(gm_path), "master_sha256": sha(gm_path), "fbx": str(g_fbx),
                                   "fbx_sha256": sha(g_fbx), "offset": offset}
        libs, assign, kind_of, meta = [], {}, {}, {}
        missing_vpm = []
        for block, r in flora_rows.items():
            c = r["cand"]
            if c is None:
                assign[block] = None
                continue
            obj = c["obj"].get(V)
            if obj is None or export.get(obj) is None:
                assign[block] = None
                missing_vpm.append({"pos": r["pos"], "block": block, "object": c["obj"].get("NPM")})
                continue
            e = export[obj]
            h = e["bbmax"][2] - e["bbmin"][2]
            bs = ps.flora_base_scale(h, tuple(r["h_m"]))
            fbx = FLORA_FBX / f"{obj}.fbx"
            libs.append({"id": obj, "fbx": str(fbx), "base_scale": bs})
            inputs.setdefault("flora_fbx", {})[obj] = sha(fbx)
            assign[block], kind_of[obj] = obj, "flora"
            meta[obj] = {"kind": "flora", "block": block, "h_m": r["h_m"], "base_scale": bs}
        for p in mafset:
            fbx = Path(p[var]["fbx"])
            libs.append({"id": p["set_id"], "fbx": str(fbx)})
            inputs.setdefault(f"maf_fbx_{var}", {})[p["set_id"]] = sha(fbx)
            assign[p["spozu_block"]], kind_of[p["set_id"]] = p["set_id"], "maf"
            meta[p["set_id"]] = {"kind": "maf", "block": p["spozu_block"], "spec": spec_dims(p["schedule_size_m"]),
                                 "spec_raw": p["schedule_size_m"]}
        spec = {"libraries": libs, "ground": {"fbx": str(g_fbx)}}
        (vdir / "spec.json").write_text(json.dumps(spec, indent=1), encoding="utf-8")
        cmds = [dcc("facts", vdir / "spec.json", vdir / "facts.json")]
        facts = json.loads((vdir / "facts.json").read_text(encoding="utf-8"))
        lib = []
        for lid, m in meta.items():
            if m["kind"] == "flora":
                lib.append(ps.flora_entry(lid, facts[lid], tuple(m["h_m"])))
            else:
                lib.append(ps.maf_entry(lid, facts[lid], m["spec"]))
        pts = adapter["planting"] + adapter["maf"]
        keep, excl = ps.select_points(pts, assign)
        try:
            keep, gx, stale = ps.apply_ground_exceptions(keep, exceptions, var, inputs[f"ground_{var}"]["master_sha256"],
                                                         assign)
        except ps.PlacementStopped as exc:
            results["variants"][var] = {"stopped": exc.reasons}
            results["status"] = "stopped"
            (out / "results.json").write_text(ps.dumps(results), encoding="utf-8")
            print(f"{var}: STOPPED {exc.reasons}")
            return 1
        excl += gx
        assert len(keep) + len(excl) == len(pts)
        for x in excl:
            if x["reason"] == "no_library_model" and var == "vpm" and any(
                    m["block"] == x["label"] for m in missing_vpm):
                x["reason"] = "no_confirmed_vpm"
        t = time.time()
        rep = engine.place(keep, gm["verts"], gm["faces"], lib, a_seed, label_map=assign)
        eng_s = round(time.time() - t, 1)
        (vdir / "engine_report.json").write_text(engine.report_json(rep), encoding="utf-8")
        vr = {"engine_status": rep["status"], "engine_seconds": eng_s, "totals": rep["totals"],
              "engine_sinking": rep["sinking"], "findings": Counter(f["code"] for f in rep["findings"]),
              "excluded": excl, "missing_vpm": missing_vpm, "facts": facts, "meta": meta,
              "counts": rep["counts"], "commands": cmds, "library_summary": rep["library"],
              "ground_exceptions_stale": stale}
        results["variants"][var] = vr
        try:
            plan = ps.make_plan(rep, facts, offset)
        except ps.PlacementStopped as exc:
            vr["stopped"] = exc.reasons
            results["status"] = "stopped"
            (out / "results.json").write_text(ps.dumps(results), encoding="utf-8")
            print(f"{var}: STOPPED {len(exc.reasons)} reasons, first: {exc.reasons[:5]}")
            return 1
        (vdir / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
        spec["run_record"] = {"seed": rep["seed"], "engine_schema": rep["schema"],
                              "engine_report_sha256": ps.report_sha256(rep), "input_hashes": rep["input_hashes"],
                              "totals": rep["totals"], "issue": 296, "variant": var}
        (vdir / "spec.json").write_text(json.dumps(spec, indent=1), encoding="utf-8")
        blend = vdir / f"VATUTINO-SITE_placement_{var}_v001.blend"
        cmds.append(dcc("instance", vdir / "spec.json", vdir / "plan.json", blend, vdir / "readback.json"))
        rb = json.loads((vdir / "readback.json").read_text(encoding="utf-8"))
        vr["scene_mismatches"] = ps.compare_scene(rep, rb, facts, offset)
        vr["sinking_scene"] = ps.sinking(rb, kind_of=kind_of)
        try:
            vr["scene_triangles"] = ps.scene_triangles(rb)
            tri_bad = []
        except ps.PlacementStopped as exc:
            vr["scene_triangles"], tri_bad = None, exc.reasons
        vr["qa_failed"] = ps.qa_gate(vr["scene_mismatches"], vr["sinking_scene"]) + tri_bad
        if vr["qa_failed"]:
            qa_failed = True
            bad = blend.with_name(blend.stem + ".QA_FAILED.blend")
            blend.rename(bad)               # quarantine: never a deliverable scene name
            blend = bad
        vr["blend"] = {"path": str(blend), "sha256": sha(blend)}
        vr["bottom_faces"] = {
            "deleted": sum(i.get("bottom_faces_deleted", 0) for i in rep["instances"]),
            "review": sum(v["action"] == "review" for i in rep["instances"] for v in i.get("bottom_faces", [])),
            "exposed": rep["exposed_bottoms"]}
        print(f"{var}: engine {rep['status']} {rep['totals']} mismatches {len(vr['scene_mismatches'])} "
              f"sink {vr['sinking_scene']['per_kind']} ok={vr['sinking_scene']['ok']} qa_failed={len(vr['qa_failed'])}")
    results["status"] = "qa_failed" if qa_failed else "pass"
    (out / "results.json").write_text(ps.dumps(results), encoding="utf-8")
    return 3 if qa_failed else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=296)
    a = ap.parse_args()
    return run(CFG, Path(a.out), a.seed)


if __name__ == "__main__":
    raise SystemExit(main())
