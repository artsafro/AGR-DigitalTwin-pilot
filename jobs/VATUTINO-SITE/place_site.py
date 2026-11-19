"""Vatutino site slice: MAF + Flora placement through the #316 engine and Blender instancing (#296).

Since #1407 this file only RESOLVES the Vatutino inputs (gate-1 Flora picks, MAF set, Verona rows, Flora export
facts) into the placement order of the one site placement command ``dt_ai.placement.site`` (``dt place site`` /
``agr place``) and runs it in its legacy mode: a missing VPM model stays a recorded parity gap
(``results.json`` ``parity``) instead of stopping the run, so the finished delivery reproduces unchanged.

Job script (not a shared tool). Inputs are COPIES / outputs outside git; the gate-1 answers of the user
(Artem 2026-10-20) are encoded in FLORA_PICKS / the exclusion reasons. Points over missing Ground are never
removed by handle here: the engine stops on them unless ``ground-exceptions.json`` holds a user-approved
exception bound to the sha256 of the Ground master being placed on (a repaired Ground re-places them).
Exit codes: 0 pass; 1 non-finite input point / engine stop / invalid or identity-changed exception (nothing instanced); 3 scene technical QA failed
(scene equality or sinking): diagnostics kept in results.json, the scene renamed ``*.QA_FAILED.blend``. Nothing here computes placement:
``dt_ai.placement.site.run`` runs it (``engine.place`` + ``dt_ai.placement.scene``), ``tools/blender/
placement_instance.py`` instances it.

  uv run python jobs/VATUTINO-SITE/place_site.py --out C:/x/t_5e4ea2be/run_v001 --seed 296
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from dt_ai.placement import site  # noqa: E402

CFG = {"adapter": Path("C:/x/t_d94665f2/paving_ground_inputs_v4.json"),
       "ground": Path("C:/x/t_d94665f2/ground_v014"),
       "flora_fbx": Path("C:/x/t_5e4ea2be/flora_fbx"),
       "site_parts": ROOT / "jobs/VATUTINO-SITE/site-parts.json",
       "maf_set": ROOT / "jobs/VATUTINO-SITE/maf/site-maf-set.json",
       "exceptions": ROOT / "jobs/VATUTINO-SITE/ground-exceptions.json",
       "flora_library": "C:/x/flora-library/v003/flora-library-v003.max"}
# #298 option A [D235]: Ground v015 (accepted [D193]) + MAF v005 + «Верона» rows 1-10 (A4.2) + Flora; urns excluded
CFG_V015 = dict(CFG, ground=Path("C:/x/t_e35c49dd/ground-v015-dcc-v001/textured"),
                exceptions=ROOT / "jobs/VATUTINO-SITE/ground-exceptions-v015.json",
                verona={"shapes": ROOT / "jobs/VATUTINO-SITE/maf/verona-plan-shapes.json",
                        "build_report": Path("C:/x/vatutino-maf/gen-v001/rows-v006p-3/build-report.json"),
                        "depth": 0.6})
# gate-1 F2 (accepted 2026-10-20): schedule position -> library catalogue id
FLORA_PICKS = {1: 101, 3: 120, 4: 115, 6: 105, 7: 103, 9: 205, 11: 212, 12: 204, 14: 230, 15: 223, 17: 224}
EXACT = {11, 14, 15}


def spec_dims(v):
    ok = isinstance(v, list) and len(v) == 3 and all(isinstance(x, (int, float)) and x > 0 for x in v)
    return v if ok else None


sha = site.sha
blender = site.blender          # the one placement DCC launch (#1378) lives in the command (#1407)


def _rel(p: Path) -> str:
    try:
        return Path(p).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


def resolve(cfg: dict) -> tuple[dict, dict]:
    """Vatutino cfg -> (placement spec of dt_ai.placement.site, provenance inputs). Reads only."""
    adapter = json.loads(cfg["adapter"].read_text(encoding="utf-8"))
    parts = json.loads(cfg["site_parts"].read_text(encoding="utf-8"))
    # #1146 v007: cfg may carry its own picks / exact set / scene version; maf_set None = Flora only
    picks, exact, version = cfg.get("flora_picks", FLORA_PICKS), cfg.get("exact", EXACT), cfg.get("version", "v001")
    mafset = json.loads(cfg["maf_set"].read_text(encoding="utf-8"))["positions"] if cfg.get("maf_set") else []
    verona_rows, verona_log = [], []
    if cfg.get("verona"):
        import importlib.util
        spec_r = importlib.util.spec_from_file_location("site_assembly_rules", ROOT / "jobs/VATUTINO-SITE/assembly_rules.py")
        rules = importlib.util.module_from_spec(spec_r)
        spec_r.loader.exec_module(rules)
        vcfg = cfg["verona"]
        shapes = json.loads(Path(vcfg["shapes"]).read_text(encoding="utf-8"))
        vreport = json.loads(Path(vcfg["build_report"]).read_text(encoding="utf-8"))
        adapter["maf"], verona_log = rules.verona_points(shapes, vreport, adapter["maf"], vcfg["depth"])
        verona_rows = vreport["rows"]
    exc_path = Path(cfg["exceptions"])
    exceptions = json.loads(exc_path.read_text(encoding="utf-8"))["exceptions"] if exc_path.is_file() else []
    FLORA_FBX, GROUND = Path(cfg["flora_fbx"]), Path(cfg["ground"])
    inputs = {"adapter": {"path": str(cfg["adapter"]), "sha256": sha(cfg["adapter"])},
              "site_parts": {"path": _rel(cfg["site_parts"]), "sha256": sha(cfg["site_parts"])},
              "maf_set": {"path": _rel(cfg["maf_set"]), "sha256": sha(cfg["maf_set"])} if cfg.get("maf_set") else None,
              "ground_exceptions": {"path": _rel(exc_path), "sha256": sha(exc_path) if exc_path.is_file() else None,
                                    "entries": len(exceptions)},
              "flora_library": {"path": str(cfg["flora_library"]), "export_dir": str(FLORA_FBX)}}
    if verona_rows:
        inputs["verona"] = {"shapes": _rel(Path(cfg["verona"]["shapes"])), "shapes_sha256": sha(Path(cfg["verona"]["shapes"])),
                            "build_report": str(cfg["verona"]["build_report"]),
                            "build_report_sha256": sha(Path(cfg["verona"]["build_report"])), "points": verona_log}
    export = json.loads((FLORA_FBX / "export.json").read_text(encoding="utf-8"))["objects"]
    assign, libs = {}, {}

    def add(key, lib):
        if key in libs:
            raise site.SpecError(f"library key {key!r} names two of: Flora block, MAF block, Verona row")
        libs[key] = lib

    for f in parts["flora"]:
        pick = picks.get(f["pos"])
        c = next((c for c in f["cands"] if c["id"] == pick), None) if pick else None
        if c is None:                                   # no library model: excluded as no_library_model
            assign[f["block"]] = None
            continue
        lib = {"kind": "flora", "block": f["block"], "h_m": [f["h_cm"][0] / 100.0, f["h_cm"][1] / 100.0],
               "missing": {"pos": f["pos"], "block": f["block"], "object": c["obj"].get("NPM")},
               "match": "exact" if f["pos"] in exact else "substitute"}
        for var in site.VARIANTS:
            obj = c["obj"].get(var.upper())
            e = export.get(obj) if obj is not None else None
            lib[var] = None if e is None else {"id": obj, "fbx": str(FLORA_FBX / f"{obj}.fbx"),
                                               "model_h_m": e["bbmax"][2] - e["bbmin"][2]}
        assign[f["block"]] = f["block"]
        add(f["block"], lib)
    for p in mafset:
        assign[p["spozu_block"]] = p["spozu_block"]
        add(p["spozu_block"], {"kind": "maf", "block": p["spozu_block"], "spec": spec_dims(p["schedule_size_m"]),
                               "spec_raw": p["schedule_size_m"],
                               **{var: {"id": p["set_id"], "fbx": str(p[var]["fbx"])} for var in site.VARIANTS}})
    for r in verona_rows:
        assign[r["set_id"]] = r["set_id"]
        add(r["set_id"], {"kind": "maf", "block": r["block"], "spec": None, "spec_raw": "generated, checked by #817",
                          **{var: {"id": r["set_id"], "fbx": str(r[var]["fbx"])} for var in site.VARIANTS}})
    spec = {"schema": site.SCHEMA, "job": "VATUTINO-SITE", "version": version, "issue": 296,
            "points": adapter["planting"] + adapter["maf"], "exceptions": exceptions, "assign": assign,
            "libraries": libs,
            "ground": {var: {"master": str(GROUND / f"ground_master_{var}.json"),
                             "readback": str(GROUND / f"readback_{var}.json"),
                             "fbx": str(GROUND / var / "SM_Vatutino_Ground.fbx")} for var in site.VARIANTS}}
    return spec, inputs


def run(cfg: dict, out: Path, seed: int, dcc=blender) -> int:
    """Resolve the Vatutino inputs and run the one site placement command (legacy mode: parity recorded)."""
    out = Path(out)
    if out.exists():
        raise SystemExit(f"{out} exists: new versioned output dirs only")
    spec, inputs = resolve(cfg)
    order = site.normalize(spec, ROOT, strict=False)
    return site.run(order, out, seed, dcc, strict=False, inputs=inputs)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=296)
    ap.add_argument("--site", choices=("v014", "v015"), default="v014")
    a = ap.parse_args()
    return run(CFG_V015 if a.site == "v015" else CFG, Path(a.out), a.seed)


if __name__ == "__main__":
    raise SystemExit(main())
