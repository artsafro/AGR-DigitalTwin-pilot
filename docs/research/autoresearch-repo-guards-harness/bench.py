"""Frozen bench for docs/research/autoresearch-repo-guards.md (t_e730ebd2, OBSERVE).

Alternates baseline (B) and candidate (C) runs of duplicate_guard.main(["--json", "--table"]) in ONE process,
asserts parity on every run (exit code + stdout) and on scan_text of every tests/*.py, writes a JSON receipt.
Usage: uv run python docs/research/autoresearch-repo-guards-harness/bench.py --rounds 3 --candidate r1_walk_memo
       --out C:/x/ar_t_e730ebd2/r1.json
"""
import argparse
import contextlib
import io
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools/architecture"))
sys.path.insert(0, str(HERE))
import duplicate_guard as dg  # noqa: E402
import candidates  # noqa: E402

ARGV = ["--root", str(ROOT), "--json", "--table"]


def run_main():
    buf = io.StringIO()
    t0 = time.perf_counter()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        rc = dg.main(ARGV)
    return time.perf_counter() - t0, rc, buf.getvalue()


def scan_text_corpus():
    """scan_text findings (or the error text) of every tests/*.py: the synthetic copies the guard tests feed."""
    out = {}
    for p in sorted((ROOT / "tests").rglob("*.py")):
        rel = p.relative_to(ROOT).as_posix()
        try:
            out[rel] = [list(f) for f in dg.scan_text(p.read_text(encoding="utf-8"), rel)]
        except (SyntaxError, ValueError, UnicodeDecodeError) as exc:
            out[rel] = f"{type(exc).__name__}: {exc}"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--candidate", required=True, help="comma-separated names from candidates.CANDIDATES")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    names = [n for n in a.candidate.split(",") if n]
    if a.out.resolve().is_relative_to(ROOT):
        sys.exit("--out must be outside the repo (no receipts in git, rule 57)")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--", "tools", "src", "jobs", "docs/architecture"],
                           capture_output=True, text=True).stdout.strip()
    base_corpus = scan_text_corpus()
    undo = candidates.apply(dg, names)
    try:
        cand_corpus = scan_text_corpus()
    finally:
        undo()
    corpus_parity = base_corpus == cand_corpus
    runs, ref = [], None
    for i in range(a.rounds):
        for variant in ("B", "C"):
            undo = candidates.apply(dg, names) if variant == "C" else (lambda: None)
            try:
                sec, rc, text = run_main()
            finally:
                undo()
            if ref is None:
                ref = (rc, text)
            parity = (rc, text) == ref
            runs.append({"round": i + 1, "variant": variant, "sec": round(sec, 3), "rc": rc, "parity": parity,
                         "stdout_lines": text.count("\n")})
            print(f"round {i + 1} {variant}: {sec:.2f} s rc={rc} parity={parity}", flush=True)
    med = {v: statistics.median(r["sec"] for r in runs if r["variant"] == v) for v in "BC"}
    ok = corpus_parity and all(r["parity"] for r in runs)
    receipt = {"head": head, "dirty_scanned_dirs": dirty, "candidate": names, "pid": os.getpid(),
               "python": sys.version.split()[0], "runs": runs, "median_B": med["B"], "median_C": med["C"],
               "ratio": round(med["C"] / med["B"], 4), "corpus_files": len(base_corpus),
               "corpus_parity": corpus_parity, "parity": ok, "keep": ok and med["C"] <= 0.80 * med["B"]}
    a.out.write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    print(json.dumps({k: receipt[k] for k in ("median_B", "median_C", "ratio", "parity", "keep", "corpus_files")}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
