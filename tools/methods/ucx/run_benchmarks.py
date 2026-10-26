"""Run every ucx-collisions variant on the benchmark objects and append the measured rows.

Pattern: new-case: methods-catalog batch for the ucx-collisions class (#706).

    uv run python tools/methods/ucx/run_benchmarks.py [--bench kpp1 --bench ac08 ...] [--variant ...] \\
        [--out C:/x/methods/out/ucx-collisions] [--results docs/methods/ucx-collisions/results.jsonl]

Per (benchmark, variant): checks the source sha256 against benchmark/methods/benchmarks.json, builds the
variant in a fresh factory Blender (build_variant_blender.py) into <out>/<bench>/<variant>/<source FBX name>
(`output_name` when the source file is not named SM_<Address>.fbx; the source is never written), packs a ZIP with the source package's textures when the source is a ZIP,
then measures it with tools/methods/run_variant.py in a fresh process. A failed build is appended as a
row with `build_error` and null metrics, never skipped. Then RESULTS.md is regenerated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import results_md  # noqa: E402
import run_variant  # noqa: E402
import ucx_variants as variants  # noqa: E402
from safe_write import check_target, refuse_aliases, same_file  # noqa: E402

CLASS = "ucx-collisions"
DEFAULT_BENCH = ("kpp1", "ac08", "tow02")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_fbx(bench: dict) -> Path:
    src = bench["source"]
    if src["kind"] == "zip":
        path, want = Path(src["fbx_local_path"]), src["fbx_sha256"]
        if sha256(Path(src["local_path"])) != src["sha256"]:
            raise SystemExit(f"{bench['id']}: {src['local_path']} sha256 differs from benchmarks.json")
    else:
        path, want = Path(src["local_path"]), src["sha256"]
    if sha256(path) != want:
        raise SystemExit(f"{bench['id']}: {path} sha256 differs from benchmarks.json")
    return path


def package(bench: dict, fbx: Path) -> Path:
    """Variant FBX + the source package's textures (every non-FBX member of a source ZIP, or the listed
    `textures` of an FBX source, sha256-checked), as a delivery package would carry them."""
    src = bench["source"]
    if src["kind"] != "zip" and not src.get("textures"):
        return fbx
    out = fbx.with_suffix(".zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        zout.write(fbx, fbx.name)
        if src["kind"] == "zip":
            with zipfile.ZipFile(src["local_path"]) as zin:
                for name in zin.namelist():
                    if not name.lower().endswith(".fbx"):
                        zout.writestr(name, zin.read(name))
        for tex in src.get("textures") or []:
            path = Path(tex["local_path"])
            if sha256(path) != tex["sha256"]:
                raise SystemExit(f"{bench['id']}: texture {path} sha256 differs from benchmarks.json")
            zout.write(path, path.name)
    return out


def protected_inputs(manifest: Path, benches: list[dict]) -> list[Path]:
    """Every file the batch reads: the manifest and, for every object in it, source / FBX-in-ZIP / textures /
    reference pictures. No planned destination may be (or alias) one of them."""
    paths = [manifest]
    for b in benches:
        src = b.get("source") or {}
        paths += [Path(src[k]) for k in ("local_path", "fbx_local_path") if src.get(k)]
        paths += [Path(t["local_path"]) for t in src.get("textures") or []]
        paths += [Path(r["local_path"]) for r in (b.get("reference_pictures") or {}).values()]
    return paths


def plan(a, benches: list[dict]) -> list[tuple]:
    """Preflight with no side effect: (bench, source, variant, out, report) per run, every destination (FBX,
    report, ZIP, results.jsonl, RESULTS.md) checked against the protected inputs and against each other."""
    runs, dests = [], [a.results, a.results.with_name("RESULTS.md")]
    for bid in a.bench or DEFAULT_BENCH:
        bench = run_variant.load_benchmark(a.benchmarks, bid, CLASS)
        src = source_fbx(bench)
        for variant in a.variant or variants.VARIANTS:
            if variant not in variants.VARIANTS:
                raise run_variant.Refused(f"unknown variant {variant!r}; known: {list(variants.VARIANTS)}")
            # delivery name SM_<Address>.fbx: V012 derives the Address of the UCX names from the FBX stem
            out = a.out / bid / variant / bench["source"].get("output_name", src.name)
            rep = out.with_name(out.name + ".variant.json")
            runs.append((bench, src, variant, out, rep))
            dests += [out, rep, out.with_suffix(".zip")]
    refuse_aliases(dests, protected_inputs(a.benchmarks, benches))
    for i, d in enumerate(dests):
        for e in dests[i + 1:]:
            if same_file(d, e):
                raise run_variant.Refused(f"two planned destinations are the same file: {d} and {e}")
    for d in dests:
        check_target(d)
    return runs


def failed_row(bench: dict, variant: str, report: dict) -> dict:
    null = {"reason": "build failed"}
    return {"schema": "methods-row/1", "class": CLASS, "variant": variant, "benchmark": bench["id"],
            "benchmark_source_sha256": bench["source"]["sha256"], "output": None, "output_sha256": None,
            "file_size_bytes": None, "wall_time_s": None, "wall_time_reason": "build failed",
            "build_error": report.get("error") or "no report", "triangles": None, "objects": None,
            "xview": null, "ucx": {"status": "build_failed", **null}, "texel": null, "matid": null,
            "render_score": null, "class_metrics": {}, "blender": report.get("blender")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bench", action="append")
    ap.add_argument("--variant", action="append")
    ap.add_argument("--out", type=Path, default=Path("C:/x/methods/out") / CLASS)
    ap.add_argument("--results", type=Path, default=ROOT / "docs" / "methods" / CLASS / "results.jsonl")
    ap.add_argument("--benchmarks", type=Path, default=run_variant.BENCHMARKS)
    a = ap.parse_args(argv)
    try:
        benches = json.loads(a.benchmarks.read_text(encoding="utf-8"))["objects"]
        runs = plan(a, benches)  # every check before the first mkdir / unlink / build
    except (run_variant.Refused, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"RUN_BENCHMARKS refused: {exc}", file=sys.stderr)
        return 4
    from dt_ai.core.blender_runner import blender_executable

    blender = blender_executable()
    by_id = {b["id"]: b for b in benches}
    codes = []
    for bench, src, variant, out, rep in runs:
        bid = bench["id"]
        out.parent.mkdir(parents=True, exist_ok=True)
        for stale in (out, rep, out.with_suffix(".zip")):  # preflight proved none of them is an input
            stale.unlink(missing_ok=True)
        cmd = [blender, "--background", "--factory-startup", "--python-exit-code", "1", "--python",
               str(HERE / "build_variant_blender.py"), "--", str(src), str(out), variant]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        report = json.loads(rep.read_text(encoding="utf-8")) if rep.is_file() else {}
        if proc.returncode != 0 or not report.get("ok") or not out.is_file():
            report.setdefault("error", f"exit {proc.returncode}: {proc.stderr[-300:]}")
            n = run_variant.append_row(a.results, failed_row(by_id[bid], variant, report))
            print(f"{bid} {variant}: build failed -> R{n}: {report['error']}")
            codes.append(2)
            continue
        target = package(bench, out)
        r = subprocess.run([sys.executable, str(HERE.parent / "run_variant.py"), str(target), "--bench", bid,
                            "--class", CLASS, "--variant", variant, "--variant-report", str(rep),
                            "--results", str(a.results), "--benchmarks", str(a.benchmarks)],
                           capture_output=True, text=True, timeout=3600)
        print(f"{bid} {variant}: {(r.stdout + r.stderr).strip()[-300:]}")
        codes.append(r.returncode)
    results_md.write(a.results)
    return 0 if all(c == 0 for c in codes) else 1


if __name__ == "__main__":
    sys.exit(main())
