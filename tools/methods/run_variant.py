"""Measure one methods-catalog variant output and append one JSON row (docs/methods/README.md, #706).

Pattern: new-case: methods catalog metric runner (one comparable row per variant x benchmark).

    uv run python tools/methods/run_variant.py <variant output .fbx|.zip> --bench <id> --class <class> \\
        --variant <name> [--variant-report <out>.variant.json | --wall-time-s S] [--render view=png ...] \\
        [--results docs/methods/<class>/results.jsonl] [--benchmarks benchmark/methods/benchmarks.json]

Row fields: wall time, triangles, objects, xView overlaps (shared 2 mm / 5 mm / 0.81 deg), UCX check (V010 +
V012 names), texel (min / median px/m), file size, MatID (slot integrity), render-vs-reference SSIM (null
without a reference picture or render), and the class metrics (ucx-collisions: model -> UCX fit).
A metric that cannot be measured is null with a reason, never a made-up number.
Exit 0 row appended; 2 measurement error (nothing appended); 4 refused (bad arguments, unknown benchmark or
class, results path aliasing an input).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import methods_metrics as metrics  # noqa: E402
from safe_write import Refused, check_target, publish_text, refuse_aliases, same_file  # noqa: E402,F401

BENCHMARKS = ROOT / "benchmark" / "methods" / "benchmarks.json"
EXTRA = Path(__file__).resolve().parent / "extra_readback_blender.py"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_benchmark(path: Path, bench_id: str, cls: str) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    objs = {o["id"]: o for o in data["objects"]}
    if bench_id not in objs:
        raise Refused(f"unknown benchmark {bench_id!r}; known: {sorted(objs)}")
    if cls not in metrics.CLASSES:
        raise Refused(f"unknown class {cls!r}; known: {list(metrics.CLASSES)}")
    if cls not in objs[bench_id]["classes"]:
        raise Refused(f"class {cls!r} does not apply to benchmark {bench_id!r} ({objs[bench_id]['classes']})")
    return objs[bench_id]


def wall_time(report: Path | None, seconds: float | None) -> tuple[float | None, str | None]:
    if report is not None and seconds is not None:
        raise Refused("give --variant-report or --wall-time-s, not both")
    if report is not None:
        rep = json.loads(report.read_text(encoding="utf-8"))
        if rep.get("ok") is not True:
            raise Refused(f"variant report {report.name} is not ok: {rep.get('error')}")
        seconds = rep.get("wall_time_s")
        if seconds is None:
            raise Refused(f"variant report {report.name} has no wall_time_s")
    if seconds is None:
        return None, "no variant wall time given"
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds < 0:
        raise Refused(f"wall time must be a finite number >= 0, got {seconds!r}")
    return float(seconds), None


def fbx_from(path: Path, tmp: Path) -> Path:
    if path.suffix.lower() == ".fbx":
        return path
    if path.suffix.lower() != ".zip":
        raise Refused(f"unsupported output {path.name}: expected .fbx or .zip")
    with zipfile.ZipFile(path) as z:
        fbx = [n for n in z.namelist() if n.lower().endswith(".fbx")]
        if len(fbx) != 1:
            raise metrics.MetricError(f"{path.name} holds {len(fbx)} FBX files; expected exactly 1")
        for name in z.namelist():  # textures next to the FBX so the readback sees their size
            target = (tmp / name).resolve()
            if tmp.resolve() not in target.parents:
                raise metrics.MetricError(f"zip member {name!r} escapes the extract folder")
        z.extractall(tmp)
    return tmp / fbx[0]


def run_extra(fbx: Path, tmp: Path, timeout: int = 900) -> dict:
    from dt_ai.core.blender_runner import blender_executable

    out = tmp / "extra.json"
    cmd = [blender_executable(), "--background", "--factory-startup", "--python-exit-code", "1",
           "--python", str(EXTRA), "--", str(fbx), str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if not out.is_file():
        raise metrics.MetricError(f"extra readback wrote nothing (exit {proc.returncode}): {proc.stderr[-400:]}")
    return json.loads(out.read_text(encoding="utf-8"))


def parse_renders(items) -> dict:
    out = {}
    for item in items or []:
        view, sep, path = item.partition("=")
        if not sep or not view or not path:
            raise Refused(f"--render needs view=path, got {item!r}")
        if view in out:
            raise Refused(f"--render view {view!r} given twice")
        if not Path(path).is_file():
            raise Refused(f"render {path} does not exist")
        out[view] = Path(path)
    return out


def references(bench: dict) -> dict:
    refs = {}
    for view, ref in (bench.get("reference_pictures") or {}).items():
        p = Path(ref["local_path"])
        if not p.is_file():
            raise metrics.MetricError(f"reference picture {view} missing at {p}")
        if sha256(p) != ref["sha256"]:
            raise metrics.MetricError(f"reference picture {view} sha256 differs from benchmarks.json")
        refs[view] = p
    return refs


def git_head() -> str | None:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True,
                              timeout=30).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def build_row(*, rb: dict, extra: dict | None, output: Path, bench: dict, cls: str, variant: str,
              wall: tuple, renders: dict, refs: dict, measure_s: float | None = None,
              tile_sides: dict | None = None) -> dict:
    from twinqa.profiles import load_profiles

    if not rb.get("readback_ok"):
        raise metrics.MetricError(f"readback failed: {rb.get('error')}")
    triangles, objects = metrics.counts(rb)
    row = {
        "schema": metrics.SCHEMA, "class": cls, "variant": variant, "benchmark": bench["id"],
        "benchmark_source_sha256": bench["source"]["sha256"], "output": output.name,
        "output_sha256": sha256(output), "file_size_bytes": output.stat().st_size,
        "wall_time_s": wall[0], "wall_time_reason": wall[1],
        "triangles": triangles, "objects": objects,
        "xview": metrics.xview(rb, "VPM"),
        "ucx": metrics.ucx_check(rb, load_profiles().profile("vpm")) if objects["ucx"] else
        {"status": "fail", "checks": {"UCX present": "fail"}, "pieces": 0, "reason": "no UCX mesh"},
        "texel": metrics.texel(rb, tile_sides),
        "matid": metrics.matid(rb, extra),
        "render_score": metrics.render_score(refs, renders),
        "class_metrics": {},
        "blender": rb.get("blender"),
    }
    if cls == "ucx-collisions":
        row["class_metrics"]["ucx_fit"] = metrics.ucx_fit(rb, extra)
    row["measure_time_s"] = measure_s
    return row


def append_row(results: Path, row: dict) -> int:
    """Append by publishing old + row through an exclusive unique temp (safe_write.publish_text); returns the
    1-based row number (= RESULTS.md row id). A pre-existing file of any other name is never touched."""
    check_target(results)
    old = results.read_text(encoding="utf-8") if results.exists() else ""
    if old and not old.endswith("\n"):
        raise metrics.MetricError(f"{results} does not end with a newline (partial write?)")
    lines = [ln for ln in old.splitlines() if ln.strip()]
    row = {"row": f"R{len(lines) + 1}", **row}
    publish_text(results, old + json.dumps(row, ensure_ascii=False, sort_keys=False) + "\n")
    return len(lines) + 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("output", type=Path)
    ap.add_argument("--bench", required=True)
    ap.add_argument("--class", dest="cls", required=True)
    ap.add_argument("--variant", required=True)
    ap.add_argument("--variant-report", type=Path)
    ap.add_argument("--wall-time-s", type=float)
    ap.add_argument("--render", action="append")
    ap.add_argument("--results", type=Path)
    ap.add_argument("--benchmarks", type=Path, default=BENCHMARKS)
    ap.add_argument("--readback", type=Path, help="reuse a fbx_readback.py JSON of this output (tests)")
    ap.add_argument("--extra", type=Path, help="reuse an extra_readback_blender.py JSON of this output (tests)")
    a = ap.parse_args(argv)
    try:
        if not a.output.is_file():
            raise Refused(f"no output file {a.output}")
        bench = load_benchmark(a.benchmarks, a.bench, a.cls)
        results = a.results or ROOT / "docs" / "methods" / a.cls / "results.jsonl"
        inputs = [a.output, a.benchmarks] + [p for p in (a.variant_report, a.readback, a.extra) if p]
        renders = parse_renders(a.render)
        inputs += list(renders.values())
        inputs += [Path(r["local_path"]) for r in (bench.get("reference_pictures") or {}).values()]
        refuse_aliases([results], inputs)
        check_target(results)
        wall = wall_time(a.variant_report, a.wall_time_s)
    except (Refused, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"RUN_VARIANT refused: {exc}", file=sys.stderr)
        return 4
    try:
        t0 = time.perf_counter()
        refs = references(bench)
        with tempfile.TemporaryDirectory(prefix="methods_") as tmp:
            fbx = fbx_from(a.output, Path(tmp))
            if a.readback:
                rb = json.loads(a.readback.read_text(encoding="utf-8"))
            else:
                from twinqa.scene import readback

                rb = readback(fbx)
            extra = json.loads(a.extra.read_text(encoding="utf-8")) if a.extra else (
                None if a.readback else run_extra(fbx, Path(tmp)))
            sides = metrics.package_tile_sides(tmp) if a.output.suffix.lower() == ".zip" else None
            row = build_row(rb=rb, extra=extra, output=a.output, bench=bench, cls=a.cls, variant=a.variant,
                            wall=wall, renders=renders, refs=refs, tile_sides=sides)
        row["measure_time_s"] = round(time.perf_counter() - t0, 3)
        row["measured_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        row["git_commit"] = git_head()
        n = append_row(results, row)
    except (metrics.MetricError, OSError, RuntimeError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        print(f"RUN_VARIANT error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(f"RUN_VARIANT R{n} {a.cls} {a.variant} {a.bench} -> {results}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
