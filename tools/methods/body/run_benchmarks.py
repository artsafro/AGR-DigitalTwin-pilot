"""Run every building-body variant on the benchmark objects and append the measured rows (#727).

Pattern: new-case: methods-catalog batch for the building-body class (#727).

    uv run python tools/methods/body/run_benchmarks.py [--bench kpp1 ...] [--variant ...] \\
        [--out C:/x/methods/building-body] [--results docs/methods/building-body/results.jsonl] \\
        [--logs docs/evidence/727-building-body]

Per benchmark: the source sha256 is checked against benchmark/methods/benchmarks.json, the source is read back
once (Blender) and its level contours are measured (contours.py, the shared "drawing" input, marked synthetic).
Per variant the output goes to <out>/<bench>/<variant>/<FBX name> (never the source):
- source-as-is: a copy of the source FBX (reference row, no build, no wall time);
- kernel-prisms: kernel_prisms.py (dt_ai.ops.contour.extrude_polygon) + body_blender.py export-mesh;
- blender-gn-union: body_blender.py gn-union (Geometry Nodes extrude per band + Mesh Boolean union);
- max-pymxs-cleanup: max_cleanup_pymxs.py in 3dsmaxbatch through ~/hermes_kanban/scripts/dcc_batch.py on a
  copy of the source.
Every DCC run leaves a text log (status, product version, seconds, report) in <logs>/<bench>-<variant>.log.txt.
Rows are written only by run_variant.py in a fresh process; a failed build appends nothing and the batch exits 1.
Then RESULTS.md is regenerated.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import contours as body_contours  # noqa: E402
import results_md  # noqa: E402
import run_variant  # noqa: E402
from safe_write import check_target, refuse_aliases, same_file  # noqa: E402

_spec = importlib.util.spec_from_file_location("methods_ucx_batch", HERE.parent / "ucx" / "run_benchmarks.py")
ucx_batch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ucx_batch)

CLASS = "building-body"
BASELINE = "source-as-is"
VARIANTS = ("kernel-prisms", "blender-gn-union", "max-pymxs-cleanup")
DEFAULT_BENCH = ("kpp1", "ac08", "tow02")
DCC_BATCH = Path.home() / "hermes_kanban" / "scripts" / "dcc_batch.py"


def main_name(out: Path) -> str:
    return f"{out.stem}_Main"


def plan(a, benches: list[dict]) -> list[tuple]:
    runs, dests = [], [a.results, a.results.with_name("RESULTS.md")]
    for bid in a.bench or DEFAULT_BENCH:
        bench = run_variant.load_benchmark(a.benchmarks, bid, CLASS)
        src = ucx_batch.source_fbx(bench)
        work = a.out / bid
        dests += [work / "source.readback.json", work / "contours.json"]
        for variant in a.variant or (BASELINE,) + VARIANTS:
            if variant not in (BASELINE,) + VARIANTS:
                raise run_variant.Refused(f"unknown variant {variant!r}; known: {[BASELINE, *VARIANTS]}")
            out = work / variant / bench["source"].get("output_name", src.name)
            rep = out.with_name(out.name + ".variant.json")
            extra = [out.with_name("kernel_mesh.json"), out.with_name("source_copy.fbx"), out.with_name("job.py"),
                     a.logs / f"{bid}-{variant}.log.txt"]
            runs.append((bench, src, variant, out, rep))
            dests += [out, rep] + extra
    refuse_aliases(dests, ucx_batch.protected_inputs(a.benchmarks, benches))
    for i, d in enumerate(dests):
        for e in dests[i + 1:]:
            if same_file(d, e):
                raise run_variant.Refused(f"two planned destinations are the same file: {d} and {e}")
    for d in dests:
        check_target(d)
    return runs


def _blender(blender: str, mode: str, src: Path, out: Path) -> tuple[int, str, float]:
    t0 = time.perf_counter()
    proc = subprocess.run([blender, "--background", "--factory-startup", "--python-exit-code", "1", "--python",
                           str(HERE / "body_blender.py"), "--", mode, str(src), str(out), main_name(out)],
                          capture_output=True, text=True, timeout=3600)
    tail = "\n".join(ln for ln in (proc.stdout + proc.stderr).splitlines()
                     if ln.startswith(("BODY_BLENDER", "Blender ", "Traceback", "  File", "Error", "RuntimeError")))
    return proc.returncode, tail, round(time.perf_counter() - t0, 2)


def _max(src: Path, out: Path, rep: Path) -> tuple[int, str, float]:
    copy = out.with_name("source_copy.fbx")
    shutil.copyfile(src, copy)  # Max reads a copy, never the benchmark source
    job = out.with_name("job.py")
    cfg = {"src": str(copy), "out": str(out), "report": str(rep)}
    job.write_text(f"CONFIG = {json.dumps(cfg)}\nexec(open({str(HERE / 'max_cleanup_pymxs.py')!r}, "
                   f"encoding='utf-8').read())\n", encoding="utf-8")
    t0 = time.perf_counter()
    proc = subprocess.run([sys.executable, str(DCC_BATCH), "max", "--file", str(job), "--timeout", "1800"],
                          capture_output=True, text=True, timeout=3600)
    line = (proc.stdout.strip().splitlines() or ["{}"])[-1]
    try:
        res = json.loads(line)
    except json.JSONDecodeError:
        res = {"status": "unparsed", "raw": line[-300:]}
    log = res.get("log") or ""
    version = re.search(r"Product version: ([^\r\n]+)", log)
    body = [ln for ln in log.splitlines() if ln.startswith("BODY_MAX")]
    text = (f"dcc_batch status={res.get('status')} exit_code={res.get('exit_code')} seconds={res.get('seconds')}\n"
            f"product: {version.group(1).strip() if version else 'not in log'}\n" + "\n".join(body))
    return (0 if res.get("status") == "ok" else 1), text, round(time.perf_counter() - t0, 2)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bench", action="append")
    ap.add_argument("--variant", action="append")
    ap.add_argument("--out", type=Path, default=Path("C:/x/methods") / CLASS)
    ap.add_argument("--results", type=Path, default=ROOT / "docs" / "methods" / CLASS / "results.jsonl")
    ap.add_argument("--logs", type=Path, default=ROOT / "docs" / "evidence" / "727-building-body")
    ap.add_argument("--benchmarks", type=Path, default=run_variant.BENCHMARKS)
    a = ap.parse_args(argv)
    try:
        benches = json.loads(a.benchmarks.read_text(encoding="utf-8"))["objects"]
        runs = plan(a, benches)  # every check before the first mkdir / unlink / build
    except (run_variant.Refused, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"RUN_BENCHMARKS refused: {exc}", file=sys.stderr)
        return 4
    from dt_ai.core.blender_runner import blender_executable
    from twinqa.scene import readback

    blender = blender_executable()
    a.logs.mkdir(parents=True, exist_ok=True)
    codes, prepared = [], {}
    for bench, src, variant, out, rep in runs:
        bid = bench["id"]
        work = a.out / bid
        if bid not in prepared:
            work.mkdir(parents=True, exist_ok=True)
            rb = readback(src)
            (work / "source.readback.json").write_text(json.dumps(rb), encoding="utf-8")
            (work / "contours.json").write_text(json.dumps(body_contours.contours(rb)), encoding="utf-8")
            prepared[bid] = work / "contours.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        for stale in (out, rep, out.with_name("kernel_mesh.json"), out.with_name("source_copy.fbx")):
            stale.unlink(missing_ok=True)  # planned destinations only; preflight proved none is an input
        args = [sys.executable, str(HERE.parent / "run_variant.py"), str(out), "--bench", bid, "--class", CLASS,
                "--variant", variant, "--results", str(a.results), "--benchmarks", str(a.benchmarks)]
        if variant == BASELINE:
            shutil.copyfile(src, out)
            r = subprocess.run(args, capture_output=True, text=True, timeout=3600)
            print(f"{bid} {variant}: {(r.stdout + r.stderr).strip()[-300:]}")
            codes.append(r.returncode)
            continue
        if variant == "kernel-prisms":
            mesh_json = out.with_name("kernel_mesh.json")
            k = subprocess.run([sys.executable, str(HERE / "kernel_prisms.py"), str(prepared[bid]), str(mesh_json)],
                               capture_output=True, text=True, timeout=3600)
            code, text, secs = (k.returncode, k.stderr[-400:], 0.0) if k.returncode else \
                _blender(blender, "export-mesh", mesh_json, out)
        elif variant == "blender-gn-union":
            code, text, secs = _blender(blender, "gn-union", prepared[bid], out)
        else:
            code, text, secs = _max(src, out, rep)
        report = json.loads(rep.read_text(encoding="utf-8")) if rep.is_file() else {}
        log = a.logs / f"{bid}-{variant}.log.txt"
        log.write_text(f"{bid} {variant} driver_seconds={secs} exit={code}\n{text}\nreport: "
                       f"{json.dumps({k: v for k, v in report.items() if k != 'objects'})}\n", encoding="utf-8")
        if code != 0 or not report.get("ok") or not out.is_file():
            print(f"{bid} {variant}: build failed, no row: {report.get('error') or text[-300:]}")
            codes.append(2)
            continue
        r = subprocess.run(args + ["--variant-report", str(rep)], capture_output=True, text=True, timeout=3600)
        print(f"{bid} {variant}: {(r.stdout + r.stderr).strip()[-300:]}")
        codes.append(r.returncode)
    results_md.write(a.results)
    return 0 if all(c == 0 for c in codes) else 1


if __name__ == "__main__":
    sys.exit(main())
