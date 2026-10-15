"""Synthetic bpy 5.1.2 wheel vs headless blender.exe parity harness (hypothesis #89).

Optional experiment. blender.exe stays the default lane. A passing run does not approve a
wheel lane and is not a delivery: delivery_passed is false. Dumps are synthetic proxies.
"""
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS = {"B01": "bench-b01-box", "B02": "bench-b02-corner-niche", "B02t": "bench-b02t-terrace"}
EXPORT = ROOT / "tools/export/export_mesh_blender.py"
READBACK = ROOT / "tools/blender/fbx_readback.py"
MEASURE = ROOT / "tools/source/measure_spec_blender.py"
UV_FIXTURE = Path(__file__).resolve().with_name("make_uv_fixture.py")
DEFAULT_BLENDER = "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe"

# Four quads, polygon order 1001, 1002, 1011, 1012. measure_spec_blender emits one UDIM
# tile per loop triangle (UV centre). Both triangles of a quad that spans [i+0.1, i+0.9]
# stay in that quad's tile, so each tile is repeated twice.
UV_EXPECTED_TILES = [1001, 1001, 1002, 1002, 1011, 1011, 1012, 1012]

EXCLUDE = {"source", "sha256"}
LIMIT = {"geom": 1e-5, "locscale": 1e-6, "rot": 1e-4, "other": 0.0}
CAT = {"vertices": "geom", "bounds_m": "geom", "location": "locscale", "scale": "locscale",
       "rotation_euler_deg": "rot"}
LANES = ("exe", "whl")
DELIVERY_PASSED = False


def resolve_lanes(blender=None, wheel=None):
    """Arguments win. Otherwise DT_BLENDER (default DEFAULT_BLENDER) and DT_BPY_PYTHON (no default)."""
    if blender is None:
        blender = os.environ.get("DT_BLENDER", DEFAULT_BLENDER)
    if wheel is None:
        wheel = os.environ.get("DT_BPY_PYTHON")
    return blender, wheel


def lane_cmd(lane, blender, wheel, script, args) -> list[str]:
    script = str(script)
    tail = [str(a) for a in args]
    if lane == "exe":
        return [str(blender), "--background", "--factory-startup", "--disable-autoexec",
                "--python-exit-code", "1", "--python", script, "--", *tail]
    if lane == "whl":
        return [str(wheel), script, "--", *tail]
    raise ValueError(f"unknown lane {lane!r}")


def build_dumps(out: Path) -> dict:
    """Copy tracked benchmark inputs, hash the originals, write synthetic <key>-dump.json files."""
    from dt_ai.geometry.from_spec import BuildInputs, build
    from dt_ai.spec.model import Spec

    out = Path(out)
    (out / "inputs").mkdir(parents=True, exist_ok=False)
    hashes, triangles = {}, {}
    for key, bench in MODELS.items():
        for name in ("spec.json", "object.json"):
            src = ROOT / "benchmark" / bench / name
            shutil.copyfile(src, out / "inputs" / f"{key}-{name}")
            hashes[f"{bench}/{name}"] = hashlib.sha256(src.read_bytes()).hexdigest()
        spec = json.loads((out / "inputs" / f"{key}-spec.json").read_text(encoding="utf-8"))
        obj = json.loads((out / "inputs" / f"{key}-object.json").read_text(encoding="utf-8"))
        dump = build(Spec.model_validate(spec), BuildInputs.from_object(obj))
        (out / f"{key}-dump.json").write_text(json.dumps(dump, indent=2), encoding="utf-8")
        triangles[key] = sum(len(m["triangles"]) for m in dump["meshes"])
        print(key, "meshes", len(dump["meshes"]), "helpers", len(dump.get("helpers", [])),
              "tris", triangles[key], "synthetic delivery_passed=false")
    (out / "input-hashes.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    return {"hashes": hashes, "triangles": triangles}


def run_matrix(work, blender, wheel, reps=2, models=tuple(MODELS), timeout=300,
               runner=subprocess.run) -> list[dict]:
    """Export/readback matrix plus the synthetic UV fixture. Writes <work>/runs.json.

    Dumps are read from <work>/common. A missing wheel interpreter raises ValueError.
    """
    if not wheel:
        raise ValueError("wheel interpreter is required (pass --wheel or set DT_BPY_PYTHON)")
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    runs = []

    def call(lane, script, args, log):
        cmd = lane_cmd(lane, blender, wheel, script, args)
        started = time.perf_counter()
        try:
            completed = runner(cmd, capture_output=True, text=True, timeout=timeout,
                               encoding="utf-8", errors="replace")
            code = completed.returncode
            text = (completed.stdout or "") + (completed.stderr or "")
        except subprocess.TimeoutExpired as exc:
            code, text = "timeout", str(exc)
        elapsed = time.perf_counter() - started
        log = Path(log)
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(text, encoding="utf-8")
        runs.append({"lane": lane, "script": Path(script).name, "args": [str(a) for a in args],
                     "exit": code, "seconds": round(elapsed, 3), "log": str(log),
                     "tail": text.strip().splitlines()[-2:]})
        print(f"{lane} {Path(script).name:26s} exit={code} {elapsed:6.2f}s "
              f"{Path(args[-1]).relative_to(work)}", flush=True)

    for rep in range(1, reps + 1):
        base = work / f"rep{rep}"
        base.mkdir(exist_ok=False)
        for model in models:
            dump = work / "common" / f"{model}-dump.json"
            for exporter in LANES:
                slot = base / model / exporter
                call(exporter, EXPORT, [dump, slot / "model.blend", slot / "model.fbx"], slot / "export.log")
                call(exporter, MEASURE, [slot / "model.blend", slot / "ms-blend.json"], slot / "ms-blend.log")
                for reader in LANES:
                    call(reader, READBACK, [slot / "model.fbx", slot / f"rb-{reader}.json"],
                         slot / f"rb-{reader}.log")
                    call(reader, MEASURE, [slot / "model.fbx", slot / f"ms-fbx-{reader}.json"],
                         slot / f"ms-fbx-{reader}.log")
        for exporter in LANES:
            slot = base / "UV" / exporter
            call(exporter, UV_FIXTURE, [slot / "model.blend", slot / "model.fbx"], slot / "export.log")
            call(exporter, MEASURE, [slot / "model.blend", slot / "ms-blend.json"], slot / "ms-blend.log")
            for reader in LANES:
                call(reader, READBACK, [slot / "model.fbx", slot / f"rb-{reader}.json"],
                     slot / f"rb-{reader}.log")
                call(reader, MEASURE, [slot / "model.fbx", slot / f"ms-fbx-{reader}.json"],
                     slot / f"ms-fbx-{reader}.log")
    (work / "runs.json").write_text(json.dumps(runs, indent=1), encoding="utf-8")
    return runs


def norm(x):
    if isinstance(x, dict):
        return {k: norm(v) for k, v in x.items() if k not in EXCLUDE}
    if isinstance(x, list):
        x = [norm(v) for v in x]
        if x and all(isinstance(v, dict) and "name" in v for v in x):
            x = sorted(x, key=lambda v: v["name"])
        return x
    return x


def diff(a, b, path="", cat="other", acc=None):
    """acc = {'max': {cat: float}, 'discrete': [paths]}"""
    acc = acc if acc is not None else {"max": {}, "discrete": []}
    if isinstance(a, bool) or isinstance(b, bool) or isinstance(a, str) or a is None or b is None:
        if a != b:
            acc["discrete"].append(f"{path}: {str(a)[:60]} != {str(b)[:60]}")
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if isinstance(a, int) and isinstance(b, int):
            if a != b:
                acc["discrete"].append(f"{path}: {a} != {b}")
        else:
            delta = abs(a - b)
            acc["max"][cat] = max(acc["max"].get(cat, 0.0), delta)
    elif isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            acc["discrete"].append(f"{path}: keys {sorted(set(a) ^ set(b))}")
        for key in set(a) & set(b):
            diff(a[key], b[key], f"{path}.{key}", CAT.get(key, cat), acc)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            acc["discrete"].append(f"{path}: len {len(a)} != {len(b)}")
        else:
            for i, (left, right) in enumerate(zip(a, b)):
                diff(left, right, f"{path}[{i}]", cat, acc)
    else:
        acc["discrete"].append(f"{path}: type {type(a).__name__} != {type(b).__name__}")
    return acc


def verdict(acc):
    bad = [f"{c} {m:.3g}>{LIMIT[c]:g}" for c, m in acc["max"].items() if m > LIMIT[c]]
    return {"ok": not bad and not acc["discrete"], "max": {c: m for c, m in acc["max"].items()},
            "over": bad, "discrete": acc["discrete"][:5], "n_discrete": len(acc["discrete"])}


def engine_view(dump):
    """The common dump reduced to the fields measure_spec_blender emits (helpers, meshes)."""
    return {"meshes": [{k: m[k] for k in ("name", "vertices", "triangles", "material_ids", "polygon_sizes")}
                       for m in dump["meshes"]], "helpers": dump.get("helpers", [])}


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _without_udim(measured):
    return norm({"meshes": [{k: v for k, v in mesh.items() if k != "udim_tiles"}
                            for mesh in measured["meshes"]],
                 "helpers": measured["helpers"]})


def _tile_view(measured):
    meshes = measured.get("meshes") or []
    if len(meshes) != 1 or "udim_tiles" not in meshes[0]:
        return {"udim_tiles": None, "meshes": len(meshes)}
    return {"udim_tiles": meshes[0]["udim_tiles"]}


def _rep_numbers(work, reps):
    if reps is None:
        found = sorted(int(path.name[3:]) for path in work.iterdir()
                       if path.is_dir() and path.name.startswith("rep") and path.name[3:].isdigit())
        if not found:
            raise FileNotFoundError(f"no rep<N> directories in {work}")
        return tuple(found)
    if isinstance(reps, int):
        return tuple(range(1, reps + 1))
    return tuple(reps)


def compare(work, reps=None, models=tuple(MODELS)) -> dict:
    """Compare a matrix. reps=None detects rep<N> folders. rep>1 is compared with rep1.

    UV fixture rows keep udim_tiles. Writes <work>/compare.json.
    Synthetic comparison only; delivery_passed is false.
    """
    work = Path(work)
    reps = _rep_numbers(work, reps)
    runs = _load(work / "runs.json")
    completion_fail = [row for row in runs if row["exit"] != 0]
    rows = []
    expected_tiles = {"udim_tiles": list(UV_EXPECTED_TILES)}

    def add(rep, model, exporter, reader, check, acc):
        rows.append({"rep": rep, "model": model, "exporter": exporter, "reader": reader,
                     "check": check, **verdict(acc)})

    def require_outputs(directory):
        for name in ("model.blend", "model.fbx"):
            path = directory / name
            if not path.is_file() or path.stat().st_size == 0:
                completion_fail.append({"missing": str(path)})

    for rep in reps:
        for model in models:
            common = norm(engine_view(_load(work / "common" / f"{model}-dump.json")))
            base = work / f"rep{rep}" / model
            ref_rb = norm(_load(base / "exe" / "rb-exe.json"))
            ref_ms = norm(_load(base / "exe" / "ms-fbx-exe.json"))
            for exporter in LANES:
                require_outputs(base / exporter)
                blend = norm(_load(base / exporter / "ms-blend.json"))
                add(rep, model, exporter, "-", "blend vs engine dump", diff(common, _without_udim(blend)))
                add(rep, model, exporter, "-", "blend vs exe blend",
                    diff(norm(_load(base / "exe" / "ms-blend.json")), blend))
                for reader in LANES:
                    rb_path = base / exporter / f"rb-{reader}.json"
                    readback = norm(_load(rb_path))
                    if not readback.get("readback_ok") or not readback.get("meshes"):
                        completion_fail.append({"readback": str(rb_path)})
                    measured = norm(_load(base / exporter / f"ms-fbx-{reader}.json"))
                    add(rep, model, exporter, reader, "readback vs exe/exe", diff(ref_rb, readback))
                    add(rep, model, exporter, reader, "fbx measure vs exe/exe", diff(ref_ms, measured))
                    add(rep, model, exporter, reader, "fbx measure vs engine dump",
                        diff(common, _without_udim(measured)))
                    if rep > 1:
                        previous = work / "rep1" / model / exporter
                        add(rep, model, exporter, reader, f"readback rep{rep} vs rep1",
                            diff(norm(_load(previous / f"rb-{reader}.json")), readback))
                        add(rep, model, exporter, reader, f"fbx measure rep{rep} vs rep1",
                            diff(norm(_load(previous / f"ms-fbx-{reader}.json")), measured))
        uv_root = work / f"rep{rep}" / "UV"
        ref_blend = norm(_load(uv_root / "exe" / "ms-blend.json"))
        ref_rb = norm(_load(uv_root / "exe" / "rb-exe.json"))
        ref_ms = norm(_load(uv_root / "exe" / "ms-fbx-exe.json"))
        for exporter in LANES:
            require_outputs(uv_root / exporter)
            blend = norm(_load(uv_root / exporter / "ms-blend.json"))
            add(rep, "UV", exporter, "-", "uv blend vs exe blend", diff(ref_blend, blend))
            add(rep, "UV", exporter, "-", "uv udim_tiles expected", diff(expected_tiles, _tile_view(blend)))
            for reader in LANES:
                rb_path = uv_root / exporter / f"rb-{reader}.json"
                readback = norm(_load(rb_path))
                if not readback.get("readback_ok") or not readback.get("meshes"):
                    completion_fail.append({"readback": str(rb_path)})
                measured = norm(_load(uv_root / exporter / f"ms-fbx-{reader}.json"))
                add(rep, "UV", exporter, reader, "uv readback vs exe/exe", diff(ref_rb, readback))
                add(rep, "UV", exporter, reader, "uv fbx measure vs exe/exe", diff(ref_ms, measured))
                add(rep, "UV", exporter, reader, "uv udim_tiles expected",
                    diff(expected_tiles, _tile_view(measured)))

    summary = {}
    for row in rows:
        bucket = summary.setdefault(row["check"], {"n": 0, "fail": 0, "max": {}})
        bucket["n"] += 1
        bucket["fail"] += not row["ok"]
        for cat, magnitude in row["max"].items():
            bucket["max"][cat] = max(bucket["max"].get(cat, 0.0), magnitude)
    result = {"completion_fail": completion_fail, "rows": rows, "summary": summary,
              "ok": not completion_fail and all(row["ok"] for row in rows)}
    if result["ok"] and DELIVERY_PASSED:
        raise RuntimeError("delivery_passed must stay false")
    (work / "compare.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result
