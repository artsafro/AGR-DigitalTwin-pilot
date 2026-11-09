"""Build every ground-terrain variant at each cell setting and append the measured rows (#733).

Pattern: new-case: methods-catalog batch for the ground-terrain class (#733).

    uv run python tools/methods/ground/run_benchmarks.py [--cell 4 --cell 2 ...] [--variant cdt ...] \\
        [--out C:/x/methods/ground-terrain] [--results docs/methods/ground-terrain/results.jsonl] [--reference-row]

Input: the typed adapter v4 copy under C:/x/methods/src/vatutino-ground/ (sha256 ADAPTER_SHA256 checked by the
driver before any build). Per (variant, cell): tools/methods/ground/build_variant.py in a fresh process into
<out>/<variant>-<cell>m/ (must not exist yet), then tools/methods/run_variant.py in a fresh process with the
variant report. Rows are written only by run_variant.py: a failed build appends nothing, is printed with its
error and makes the batch exit 1. `--reference-row` first measures a copy of the benchmark reference FBX (and
its placement sidecar) as variant `reference-v014`: the metric's zero line. Then RESULTS.md is regenerated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))

import results_md  # noqa: E402
from safe_write import Refused, check_target, refuse_aliases  # noqa: E402

CLASS, BENCH = "ground-terrain", "vatutino-ground"
ADAPTER = Path("C:/x/methods/src/vatutino-ground/paving_ground_inputs_v4.json")
ADAPTER_SHA256 = "3b6b433d718c0292f472293849f3363fd2ae90d4892e598efca52be44cd9d502"
FBX_NAME = "SM_Vatutino_Ground.fbx"


def fmt_cell(cell: float) -> str:
    return f"{cell:g}m"


def measure(fbx: Path, variant: str, results: Path, report: Path | None) -> int:
    cmd = [sys.executable, str(HERE.parent / "run_variant.py"), str(fbx), "--bench", BENCH, "--class", CLASS,
           "--variant", variant, "--results", str(results)]
    cmd += ["--variant-report", str(report)] if report else []
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    print((proc.stdout + proc.stderr).strip()[-600:])
    return proc.returncode


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cell", type=float, action="append")
    ap.add_argument("--variant", action="append")
    ap.add_argument("--adapter", type=Path, default=ADAPTER)
    ap.add_argument("--out", type=Path, default=Path("C:/x/methods") / CLASS)
    ap.add_argument("--results", type=Path, default=ROOT / "docs" / "methods" / CLASS / "results.jsonl")
    ap.add_argument("--reference-row", action="store_true")
    a = ap.parse_args(argv)
    cells = a.cell or [4.0, 2.0]
    variants = a.variant or ["builder", "cdt", "bgrid"]
    bench = {o["id"]: o for o in json.loads((ROOT / "benchmark" / "methods" / "benchmarks.json").read_text(
        encoding="utf-8"))["objects"]}[BENCH]
    ref = Path(bench["source"]["local_path"])
    runs = [(v, c, a.out / f"{v}-{fmt_cell(c)}") for c in cells for v in variants]
    try:
        if hashlib.sha256(a.adapter.read_bytes()).hexdigest() != ADAPTER_SHA256:
            raise Refused(f"{a.adapter} sha256 differs from {ADAPTER_SHA256}")
        refuse_aliases([a.results, a.results.with_name("RESULTS.md")],
                       [a.adapter, ref, Path(str(ref) + ".placement.json")])
        check_target(a.results)
        planned = [d for _, _, d in runs] + ([a.out / "reference-v014"] if a.reference_row else [])
        for d in planned:
            if d.exists():
                raise Refused(f"{d} exists: every build goes to a new folder")
    except (Refused, OSError) as exc:
        print(f"RUN_BENCHMARKS refused: {exc}", file=sys.stderr)
        return 4
    codes = []
    if a.reference_row:
        d = a.out / "reference-v014"
        d.mkdir(parents=True)
        shutil.copyfile(ref, d / FBX_NAME)
        shutil.copyfile(Path(str(ref) + ".placement.json"), d / (FBX_NAME + ".placement.json"))
        codes.append(measure(d / FBX_NAME, "reference-v014", a.results, None))
    for variant, cell, d in runs:
        proc = subprocess.run([sys.executable, str(HERE / "build_variant.py"), variant, str(a.adapter), "--cell",
                               repr(cell), "--out", str(d), "--expect-sha256", ADAPTER_SHA256],
                              capture_output=True, text=True, timeout=7200)
        print((proc.stdout + proc.stderr).strip()[-600:])
        if proc.returncode != 0:
            codes.append(1)
            continue
        codes.append(measure(d / FBX_NAME, f"{variant}-{fmt_cell(cell)}", a.results,
                             d / (FBX_NAME + ".variant.json")))
    if a.results.is_file():
        print(results_md.write(a.results))
    return 0 if all(c == 0 for c in codes) else 1


if __name__ == "__main__":
    sys.exit(main())
