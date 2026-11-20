"""Pattern: n/a | new-case: docs/research/autoresearch-repo-guards-e2e-harness/e2e_bench.py - standing #7 repo_guards.sh wall (OBSERVE)

End-to-end wall time of repo_guards.sh in two scratch worktrees (B unchanged, C with a harness candidate
injected into tools/architecture/duplicate_guard.py on the blank line above the __main__ guard).

  python e2e_bench.py setup --base <sha> --candidate r1_walk_memo,r4_lazy_scopes,r5_lazy_int_names
  python e2e_bench.py parity [--mutant m0_drop_calls]
  python e2e_bench.py run --out C:/x/ar_t_559cc438/r1.json
Contract: docs/research/autoresearch-repo-guards-e2e.md
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import time

WORK = Path("C:/x/ar_t_559cc438")
HARNESS_SRC = Path(__file__).resolve().parents[1] / "autoresearch-repo-guards-harness" / "candidates.py"
GUARDS = "C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh"
DG = "tools/architecture/duplicate_guard.py"
MAIN = 'if __name__ == "__main__":\n'
LIMIT = 75 * 60


def sh(args, cwd, **kw):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def inject(wt, names):
    """Replace the blank line above the __main__ guard with one candidate line (no line shift)."""
    p = wt / DG
    sh(["git", "checkout", "--", DG], wt)
    text = p.read_text(encoding="utf-8")
    old = "\n\n" + MAIN
    if text.count(old) != 1:
        raise SystemExit("injection anchor not unique")
    line = (f"sys.path.insert(0, {str(WORK / 'harness')!r}); "
            f"__import__('candidates').apply(sys.modules[__name__], {names!r})  # AR OBSERVE t_559cc438")
    p.write_text(text.replace(old, "\n" + line + "\n" + MAIN), encoding="utf-8", newline="\n")
    if len(p.read_text(encoding="utf-8").splitlines()) != len(text.splitlines()):
        raise SystemExit("line count changed")


def setup(a):
    (WORK / "harness").mkdir(parents=True, exist_ok=True)
    shutil.copy2(HARNESS_SRC, WORK / "harness" / "candidates.py")
    for name in ("wtB", "wtC"):
        wt = WORK / name
        if not wt.exists():
            r = sh(["git", "worktree", "add", "--detach", str(wt), a.base], Path.cwd())
            if r.returncode:
                raise SystemExit(r.stderr)
    inject(WORK / "wtC", a.candidate.split(","))
    print(json.dumps({"base": a.base, "candidate": a.candidate}))


def scan(wt):
    r = sh(["uv", "run", "python", DG, "--json", "--table"], wt, env={**os.environ, "PYTHONUTF8": "1"})
    return r.returncode, r.stdout


def parity(a):
    rb, ob = scan(WORK / "wtB")
    if a.mutant:
        inject(WORK / "wtC", [a.mutant])
    rc, oc = scan(WORK / "wtC")
    out = dict(rc_b=rb, rc_c=rc, identical=ob == oc, sha_b=hashlib.sha256(ob.encode()).hexdigest(),
               sha_c=hashlib.sha256(oc.encode()).hexdigest(), mutant=a.mutant)
    print(json.dumps(out))
    return 0


def guards(wt):
    start = time.perf_counter()
    r = sh(["bash", GUARDS], wt)
    sec = time.perf_counter() - start
    out = r.stdout + r.stderr
    passed = re.search(r"(\d+) passed", out)
    return dict(seconds=round(sec, 3), rc=r.returncode, green="repo_guards: GREEN" in out,
                passed=int(passed.group(1)) if passed else None,
                problems=[l for l in out.splitlines() if re.match(r"(FAILED|ERROR|NEW COPY|Traceback)", l)][:10])


def run(a):
    if a.out.exists():
        raise SystemExit("--out exists")
    head = {n: sh(["git", "rev-parse", "HEAD"], WORK / n).stdout.strip() for n in ("wtB", "wtC")}
    diff = sh(["git", "diff", "--stat"], WORK / "wtC").stdout.strip()
    start = time.perf_counter()
    warm = {n: guards(WORK / n) for n in ("wtB", "wtC")}
    print("warm-up", warm, flush=True)
    runs, err = [], None
    for pair, order in enumerate(("BC", "CB", "BC"), 1):
        for v in order:
            if time.perf_counter() - start > LIMIT:
                err = "time limit"
                break
            row = dict(pair=pair, variant=v, **guards(WORK / f"wt{v}"))
            runs.append(row)
            print(row, flush=True)
        if err:
            break
    rec: dict[str, object] = dict(head=head, wtC_diff=diff, warmup=warm, runs=runs, error=err)
    if not err and len(runs) == 6:
        med = {v: statistics.median(r["seconds"] for r in runs if r["variant"] == v) for v in "BC"}
        by = {p: {r["variant"]: r["seconds"] for r in runs if r["pair"] == p} for p in (1, 2, 3)}
        ok = all(r["green"] for r in runs) and len({r["passed"] for r in runs}) == 1
        faster = all(by[p]["C"] < by[p]["B"] for p in by)
        rec.update(median=med, ratio=med["C"] / med["B"], all_green_same_count=ok, all_pairs_faster=faster,
                   keep=ok and faster and med["C"] <= 0.80 * med["B"])
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    print({k: rec.get(k) for k in ("median", "ratio", "all_green_same_count", "all_pairs_faster", "keep", "error")})
    return 0


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("setup")
    s.add_argument("--base", required=True)
    s.add_argument("--candidate", required=True)
    q = sub.add_parser("parity")
    q.add_argument("--mutant")
    r = sub.add_parser("run")
    r.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    return {"setup": setup, "parity": parity, "run": run}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
