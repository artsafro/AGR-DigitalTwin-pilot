"""Site placement command (#1407): MAF + Flora low-poly (NPM) and high-poly (VPM) at the same points in one run.

Pattern: n/a | new-case: one site placement run over ``dt_ai.placement`` (engine + scene helpers) for both
delivery versions, replacing the job-local ``jobs/VATUTINO-SITE/place_site.py`` run [D293 NPM step: parallel
placement; D329 placement owner = dt_ai.placement].

One run = one spec + one seed -> ``OUT/npm`` and ``OUT/vpm``. The point list, the label -> library assignment
and the exceptions are shared by both versions; only the model of each library key (``npm`` / ``vpm``) and the
Ground differ. Nothing here computes a pivot, rotation, scale or sinking: ``engine.place`` does; the scene plan,
readback comparison and QA gate are ``dt_ai.placement.scene``. Phases: (A) both versions select their points
(boundary, assignment, Ground exceptions) - no DCC; (B) both versions read DCC facts, run the engine and build
the plan; (C) both versions are instanced, read back and gated. The point/ID parity of NPM and VPM is checked
after A and after B; with ``strict`` (CLI default) a mismatch stops the run before any scene is written.

Fail-closed spec (``SpecError`` naming the key, raised before the output folder exists): unknown schema, version
set other than exactly npm + vpm, a library key without an npm AND a vpm model (strict), an assignment to an
unknown library key, an inside point whose label is not assigned (strict; ``null`` = excluded on purpose), an
unused library (strict), one model id for two different files, unknown kind, non-finite / non-positive bands,
heights, dims or offsets, missing files, empty points, unsafe ``job`` / ``version`` names.

Program choice: Blender headless (``tools/blender/placement_instance.py`` via ``blender_runner``) for facts and
instancing - the existing readback-verified instancer. The core takes any ``dcc`` callable with the same
``facts`` / ``instance`` protocol, so a 3ds Max (AGR Tools) adapter calls the same code (roadmap #1374).

Exit codes: 0 pass; 1 stopped (non-finite point, Ground exception, engine stop); 3 scene QA failed (scene renamed
``*.QA_FAILED.blend``); 4 NPM/VPM point-ID parity failed (strict); 2 CLI input error (nothing written).

  dt place site SPEC.json --out NEW_DIR --seed 1407        (alias: agr place SPEC.json --out NEW_DIR --seed 1407)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable

if __package__ in (None, ""):          # run as a file by `dt place site`: make `dt_ai` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dt_ai.core.blender_runner import BlenderRunError, blender_command, run_blender  # noqa: E402
from dt_ai.placement import engine  # noqa: E402
from dt_ai.placement import scene as ps  # noqa: E402

SCHEMA = "dt-placement-site/1"
VARIANTS = ("npm", "vpm")
KINDS = ("flora", "maf")
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tools/blender/placement_instance.py"
PLACEMENT_ARITY = {"facts": 2, "instance": 4}   # tools/blender/placement_instance.py commands


class SpecError(ValueError):
    """The spec is not a complete, unambiguous placement order; nothing was written."""


# ----------------------------------------------------------------------------- DCC (default: headless Blender)
def blender(*args) -> dict:
    """One placement_instance.py step through the shared headless runner (#1378); every promised file is fresh.
    facts spec facts.json -> facts.json; instance spec plan blend readback.json -> readback.json + blend."""
    if not args or args[0] not in PLACEMENT_ARITY or len(args) - 1 != PLACEMENT_ARITY[args[0]]:
        raise ValueError(f"placement_instance.py: unknown command or wrong argument count {list(map(str, args))}; "
                         f"expected one of {PLACEMENT_ARITY}")
    report = Path(args[-1])
    outputs = [Path(args[3])] if args[0] == "instance" else []
    t = time.time()
    try:
        run_blender(SCRIPT, list(args), output_json=report, outputs=outputs, timeout=3600,
                    log_path=report.with_name(report.name + ".blender.log"))
    except BlenderRunError as exc:
        raise SystemExit(f"blender failed {exc}") from exc
    cmd = blender_command(SCRIPT, args)
    return {"cmd": " ".join(f'"{c}"' if " " in c else c for c in cmd), "exit_code": 0,
            "seconds": round(time.time() - t, 1)}


# ----------------------------------------------------------------------------- spec
def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _fin(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _pos_vec(v: Any, n: int) -> bool:
    return isinstance(v, list) and len(v) == n and all(_fin(x) and x > 0 for x in v)


def _file(base: Path, v: Any, where: str) -> Path:
    if not isinstance(v, str) or not v:
        raise SpecError(f"{where}: needs a file path, got {v!r}")
    p = Path(v) if Path(v).is_absolute() else base / v
    if not p.is_file():
        raise SpecError(f"{where}: file not found: {v}")
    return p


def _json_list(base: Path, v: Any, key: str, where: str) -> list:
    if isinstance(v, str):
        data = json.loads(_file(base, v, where).read_text(encoding="utf-8"))
        v = data.get(key) if isinstance(data, dict) else data
    if not isinstance(v, list):
        raise SpecError(f"{where}: needs a list (inline or a JSON file), got {type(v).__name__}")
    return v


def normalize(spec: dict, base: Path, *, strict: bool = True) -> dict:
    """Spec -> run order {job, version, issue, points, exceptions, variants{var: {ground, assign, libraries,
    missing}}}. Raises SpecError naming the offending key; reads only."""
    if not isinstance(spec, dict) or spec.get("schema") != SCHEMA:
        raise SpecError(f"schema: expected {SCHEMA!r}, got {spec.get('schema') if isinstance(spec, dict) else spec!r}")
    for key in ("job", "version"):
        if not isinstance(spec.get(key), str) or not SAFE_NAME.match(spec[key]) or ".." in spec[key]:
            raise SpecError(f"{key}: needs a plain name [A-Za-z0-9_.-], got {spec.get(key)!r}")
    points = _json_list(base, spec.get("points"), "points", "points")
    if not points:
        raise SpecError("points: empty point list")
    exc = spec.get("exceptions")
    exceptions = [] if exc is None else _json_list(base, exc, "exceptions", "exceptions")
    ground = spec.get("ground")
    if not isinstance(ground, dict) or sorted(ground) != sorted(VARIANTS):
        raise SpecError(f"ground: needs exactly the versions {list(VARIANTS)}, "
                        f"got {sorted(ground) if isinstance(ground, dict) else ground!r}")
    libs = spec.get("libraries")
    if not isinstance(libs, dict) or not libs:
        raise SpecError("libraries: needs a non-empty mapping library key -> {kind, npm, vpm}")
    assign = spec.get("assign")
    if not isinstance(assign, dict):
        raise SpecError("assign: needs a mapping point label -> library key or null")
    for label, key in assign.items():
        if key is not None and key not in libs:
            raise SpecError(f"assign[{label!r}]: unknown library key {key!r}")
    if strict:
        used = {k for k in assign.values() if k is not None}
        for key in libs:
            if key not in used:
                raise SpecError(f"libraries[{key!r}]: not assigned to any point label")
        unmapped = sorted({str(p.get("label")) for p in points if isinstance(p, dict) and p.get("inside") is True
                           and p.get("label") not in assign})
        if unmapped:
            raise SpecError(f"assign: no entry for the point labels {unmapped} (map them, or to null to exclude)")
    order = {"job": spec["job"], "version": spec["version"], "issue": spec.get("issue"), "points": points,
             "exceptions": exceptions, "variants": {}}
    for var in VARIANTS:
        g = ground[var]
        where = f"ground[{var}]"
        if not isinstance(g, dict):
            raise SpecError(f"{where}: needs {{master, offset|readback, fbx|mesh}}")
        master = _file(base, g.get("master"), f"{where}.master")
        if "offset" in g:
            offset = g["offset"]
        else:
            rb = _file(base, g.get("readback"), f"{where}.readback (or offset)")
            offset = json.loads(rb.read_text(encoding="utf-8")).get("placement_offset")
        if not (isinstance(offset, list) and len(offset) == 3 and all(_fin(x) for x in offset)):
            raise SpecError(f"{where}.offset: needs 3 finite numbers, got {offset!r}")
        gv = {"master": master, "offset": [float(x) for x in offset]}
        if "mesh" in g:
            gv["mesh"] = g["mesh"]
        else:
            gv["fbx"] = _file(base, g.get("fbx"), f"{where}.fbx")
        entries, fbx_of, missing, var_assign = [], {}, [], {}
        for key, lib in libs.items():
            lw = f"libraries[{key!r}]"
            if not isinstance(lib, dict) or lib.get("kind") not in KINDS:
                raise SpecError(f"{lw}.kind: needs one of {KINDS}, got {lib.get('kind') if isinstance(lib, dict) else lib!r}")
            if lib["kind"] == "flora" and not (_pos_vec(lib.get("h_m"), 2) and lib["h_m"][0] <= lib["h_m"][1]):
                raise SpecError(f"{lw}.h_m: needs [low, high] finite > 0, got {lib.get('h_m')!r}")
            if lib["kind"] == "maf" and lib.get("spec") is not None and not _pos_vec(lib["spec"], 3):
                raise SpecError(f"{lw}.spec: needs null or 3 finite numbers > 0, got {lib.get('spec')!r}")
            model = lib.get(var)
            if model is None:
                if strict:
                    raise SpecError(f"{lw}: no {var} model - NPM and VPM must place the same points (D293)")
                missing.append(dict(lib.get("missing") or {"block": lib.get("block", key)}))
                continue
            mw = f"{lw}.{var}"
            if not isinstance(model, dict) or not isinstance(model.get("id"), str) or not model["id"]:
                raise SpecError(f"{mw}.id: needs a model id")
            mid = model["id"]
            src = model.get("mesh") if "mesh" in model else _file(base, model.get("fbx"), f"{mw}.fbx")
            if "mesh" in model and not isinstance(src, dict):
                raise SpecError(f"{mw}.mesh: needs {{vertices, faces}}")
            ident = json.dumps(src, sort_keys=True) if isinstance(src, dict) else str(Path(src).resolve()).lower()
            if fbx_of.setdefault(mid, ident) != ident:
                raise SpecError(f"{mw}.id: model id {mid!r} names two different models in {var}")
            entry = {"key": key, "id": mid, "kind": lib["kind"], "block": lib.get("block", key)}
            entry["mesh" if isinstance(src, dict) else "fbx"] = src
            if lib["kind"] == "flora":
                mh = model.get("model_h_m")
                if not (_fin(mh) and mh > 0):
                    raise SpecError(f"{mw}.model_h_m: needs a finite model height > 0, got {mh!r}")
                entry["h_m"] = [float(lib["h_m"][0]), float(lib["h_m"][1])]
                entry["base_scale"] = ps.flora_base_scale(float(mh), tuple(entry["h_m"]))
            else:
                entry["spec"] = lib.get("spec")
                entry["spec_raw"] = lib.get("spec_raw", lib.get("spec"))
            entries.append(entry)
        present = {e["key"]: e["id"] for e in entries}
        for label, key in assign.items():
            var_assign[label] = present.get(key) if key is not None else None
        order["variants"][var] = {"ground": gv, "assign": var_assign, "libraries": entries, "missing": missing,
                                  "missing_labels": {lab for lab, key in assign.items()
                                                     if key is not None and key not in present}}
    return order


# ----------------------------------------------------------------------------- run
def _keys(points: list[dict]) -> list[list]:
    return sorted([str(p.get("handle")), str(p.get("label"))] for p in points)


def _ids(rows: list) -> dict:
    return {"count": len(rows), "sha256": hashlib.sha256(json.dumps(rows).encode()).hexdigest()}


def _parity(a: list, b: list) -> dict:
    sa, sb = {h for h, _ in a}, {h for h, _ in b}
    return {"identical": a == b, "only_npm": sorted(sa - sb), "only_vpm": sorted(sb - sa),
            "label_differs": sorted(h for h, lab in a if h in sb and [h, lab] not in b)}


def run(order: dict, out: Path, seed: int, dcc: Callable = blender, *, strict: bool = True,
        inputs: dict | None = None) -> int:
    """Place both versions of one normalized order into the NEW folder ``out``; returns the exit code."""
    out = Path(out)
    if out.exists():
        raise SpecError(f"--out {out} exists: new versioned output dirs only")
    out.mkdir(parents=True)
    exceptions = order["exceptions"]
    pts = order["points"]
    inputs = dict(inputs or {})
    results = {"seed": seed, "inputs": inputs, "status": "running", "variants": {},
               "parity": {"mode": "strict" if strict else "legacy", "identical": None}}
    par = results["parity"]

    def stop(status: str, msg: str, code: int) -> int:
        results["status"] = status
        (out / "results.json").write_text(ps.dumps(results), encoding="utf-8")
        print(msg)
        return code

    try:
        ps.validate_points(pts)
    except ps.PlacementStopped as exc:
        results["stopped"] = exc.reasons
        return stop("stopped", f"STOPPED (input points) {exc.reasons[:5]}", 1)
    # ---- phase A: selection per version (no DCC)
    st: dict[str, dict] = {}
    for var in VARIANTS:
        v = order["variants"][var]
        g = v["ground"]
        gm = json.loads(Path(g["master"]).read_text(encoding="utf-8"))
        gin = {"master": str(g["master"]), "master_sha256": sha(g["master"]), "offset": g["offset"]}
        if "fbx" in g:
            gin.update(fbx=str(g["fbx"]), fbx_sha256=sha(g["fbx"]))
        else:
            gin["mesh_sha256"] = hashlib.sha256(json.dumps(g["mesh"], sort_keys=True).encode()).hexdigest()
        inputs[f"ground_{var}"] = gin
        libs, meta, kind_of = [], {}, {}
        for e in v["libraries"]:
            lib = {"id": e["id"], ("mesh" if "mesh" in e else "fbx"): e.get("mesh", str(e.get("fbx")))}
            hkey = "flora_fbx" if e["kind"] == "flora" else f"maf_fbx_{var}"
            if "fbx" in e:
                inputs.setdefault(hkey, {})[e["id"]] = sha(e["fbx"])
            if e["kind"] == "flora":
                lib["base_scale"] = e["base_scale"]
                meta[e["id"]] = {"kind": "flora", "block": e["block"], "h_m": e["h_m"], "base_scale": e["base_scale"]}
            else:
                meta[e["id"]] = {"kind": "maf", "block": e["block"], "spec": e["spec"], "spec_raw": e["spec_raw"]}
            libs.append(lib)
            kind_of[e["id"]] = e["kind"]
        keep, excl = ps.select_points(pts, v["assign"])
        try:
            keep, gx, stale = ps.apply_ground_exceptions(keep, exceptions, var, gin["master_sha256"], v["assign"])
        except ps.PlacementStopped as exc:
            results["variants"][var] = {"stopped": exc.reasons}
            return stop("stopped", f"{var}: STOPPED {exc.reasons}", 1)
        excl += gx
        assert len(keep) + len(excl) == len(pts)
        for x in excl:
            if x["reason"] == "no_library_model" and x["label"] in v["missing_labels"]:
                x["reason"] = f"no_confirmed_{var}"
        st[var] = {"gm": gm, "gin": gin, "libs": libs, "meta": meta, "kind_of": kind_of, "keep": keep,
                   "excl": excl, "stale": stale}
    sel = {var: _keys(st[var]["keep"]) for var in VARIANTS}
    par["selected"] = {var: _ids(sel[var]) for var in VARIANTS}
    par.update(_parity(sel["npm"], sel["vpm"]))
    if strict and not par["identical"]:
        return stop("parity_failed", f"PARITY: NPM and VPM select different points {par['only_npm'][:5]} "
                                     f"{par['only_vpm'][:5]} {par['label_differs'][:5]}", 4)
    # ---- phase B: facts + engine + plan per version
    for var in VARIANTS:
        s, v = st[var], order["variants"][var]
        vdir = out / var
        vdir.mkdir()
        spec = {"libraries": s["libs"], "ground": ({"fbx": s["gin"]["fbx"]} if "fbx" in s["gin"]
                                                   else {"mesh": v["ground"]["mesh"]})}
        (vdir / "spec.json").write_text(json.dumps(spec, indent=1), encoding="utf-8")
        cmds = [dcc("facts", vdir / "spec.json", vdir / "facts.json")]
        facts = json.loads((vdir / "facts.json").read_text(encoding="utf-8"))
        absent = [lid for lid in s["meta"] if lid not in facts]
        if absent:
            results["variants"][var] = {"stopped": [f"DCC facts have no entry for model {lid!r}" for lid in absent],
                                        "commands": cmds}
            return stop("stopped", f"{var}: STOPPED DCC facts miss {absent}", 1)
        lib = []
        for lid, m in s["meta"].items():
            lib.append(ps.flora_entry(lid, facts[lid], tuple(m["h_m"])) if m["kind"] == "flora"
                       else ps.maf_entry(lid, facts[lid], m["spec"]))
        t = time.time()
        rep = engine.place(s["keep"], s["gm"]["verts"], s["gm"]["faces"], lib, seed, label_map=v["assign"])
        eng_s = round(time.time() - t, 1)
        (vdir / "engine_report.json").write_text(engine.report_json(rep), encoding="utf-8")
        vr = {"engine_status": rep["status"], "engine_seconds": eng_s, "totals": rep["totals"],
              "engine_sinking": rep["sinking"], "findings": Counter(f["code"] for f in rep["findings"]),
              "excluded": s["excl"], "missing_vpm": v["missing"], "facts": facts, "meta": s["meta"],
              "counts": rep["counts"], "commands": cmds, "library_summary": rep["library"],
              "ground_exceptions_stale": s["stale"]}
        results["variants"][var] = vr
        try:
            plan = ps.make_plan(rep, facts, s["gin"]["offset"])
        except ps.PlacementStopped as exc:
            vr["stopped"] = exc.reasons
            return stop("stopped", f"{var}: STOPPED {len(exc.reasons)} reasons, first: {exc.reasons[:5]}", 1)
        (vdir / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
        spec["run_record"] = {"seed": rep["seed"], "engine_schema": rep["schema"],
                              "engine_report_sha256": ps.report_sha256(rep), "input_hashes": rep["input_hashes"],
                              "totals": rep["totals"], "issue": order["issue"], "variant": var}
        (vdir / "spec.json").write_text(json.dumps(spec, indent=1), encoding="utf-8")
        s.update(rep=rep, facts=facts, vr=vr, cmds=cmds, vdir=vdir)
    placed = {var: sorted([str(i["handle"]), str(i["label"])] for i in st[var]["rep"]["instances"]) for var in VARIANTS}
    par["placed"] = {var: _ids(placed[var]) for var in VARIANTS}
    par.update(_parity(placed["npm"], placed["vpm"]))        # the verdict is on the placed points
    if strict and not par["identical"]:
        return stop("parity_failed", f"PARITY: NPM and VPM placed different points {par['only_npm'][:5]} "
                                     f"{par['only_vpm'][:5]} {par['label_differs'][:5]}", 4)
    # ---- phase C: instance + readback + QA per version
    qa_failed = False
    for var in VARIANTS:
        s = st[var]
        rep, facts, vr, vdir, offset = s["rep"], s["facts"], s["vr"], s["vdir"], s["gin"]["offset"]
        blend = vdir / f"{order['job']}_placement_{var}_{order['version']}.blend"
        s["cmds"].append(dcc("instance", vdir / "spec.json", vdir / "plan.json", blend, vdir / "readback.json"))
        rb = json.loads((vdir / "readback.json").read_text(encoding="utf-8"))
        vr["scene_mismatches"] = ps.compare_scene(rep, rb, facts, offset)
        vr["sinking_scene"] = ps.sinking(rb, kind_of=s["kind_of"])
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


def _check_out(out: Path, spec_path: Path) -> None:
    o, sp = Path(out).resolve(), Path(spec_path).resolve()
    if o.exists():
        raise SpecError(f"--out {out} exists (or is an input): new versioned output dirs only")
    if o == sp or sp.parent == o or sp.parent in o.parents:
        raise SpecError(f"--out {out} is inside the spec folder {sp.parent}: outputs never go into the inputs")


def run_file(spec_path: Path, out: Path, seed: int, dcc: Callable = blender, *, strict: bool = True) -> int:
    """Spec file -> run. SpecError (nothing written) on any spec problem or an output that aliases an input."""
    spec_path = Path(spec_path)
    _check_out(out, spec_path)
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SpecError(f"spec {spec_path}: unreadable: {exc}") from exc
    order = normalize(spec, spec_path.parent, strict=strict)
    return run(order, out, seed, dcc, strict=strict,
               inputs={"spec": {"path": str(spec_path), "sha256": sha(spec_path)}})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="dt place site", description="MAF + Flora placement, NPM and VPM at the same "
                                 "points in one run (#1407, D293). Exit 0 pass, 1 stopped, 2 input error, "
                                 "3 scene QA failed, 4 NPM/VPM parity failed.")
    ap.add_argument("spec", type=Path, help=f"placement spec JSON ({SCHEMA}); relative paths from its folder")
    ap.add_argument("--out", type=Path, required=True, help="NEW output folder (never inside the spec folder)")
    ap.add_argument("--seed", type=int, required=True)
    a = ap.parse_args(argv)
    try:
        return run_file(a.spec, a.out, a.seed)
    except SpecError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
