"""Bench for the Blender exit-code guard full-repo scan (standing #11, t_95ce9e1f).

Usage (from any directory; ``--root`` is the scratch worktree at the frozen base):
  python bench.py parity --root C:/x/ar_t_95ce9e1f/wtB --candidate r1_one_walk [--mutant m0_direct_children_only]
  python bench.py run    --root C:/x/ar_t_95ce9e1f/wtB --candidate r1_one_walk --out <new json path>

B = the guard module loaded from ``git show <HEAD of root>:tests/test_blender_exit_code_guard.py``;
C = a second instance of the same module with ``_scan_py_source`` replaced by the candidate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
import subprocess
import sys
import time
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import candidates  # noqa: E402

REL = "tests/test_blender_exit_code_guard.py"


def load(root: Path, name: str):
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    src = subprocess.run(["git", "show", f"{head}:{REL}"], cwd=root, capture_output=True, check=True).stdout
    if src != (root / REL).read_bytes():
        raise SystemExit(f"{REL} in {root} differs from HEAD {head}: refuse")
    mod = types.ModuleType(name)
    mod.__file__ = str(root / REL)
    exec(compile(src, str(root / REL), "exec"), mod.__dict__)
    return mod, head, hashlib.sha256(src).hexdigest()


def pair(root: Path, candidate: str):
    b, head, sha = load(root, "guard_b")
    c, _h, _s = load(root, "guard_c")
    setattr(c, "_scan_py_source", candidates.CANDIDATES[candidate](c))
    return b, c, head, sha


# ---------------------------------------------------------------- generated corpus
_STR = ['"--background"', '"--python-exit-code"', '"1"', '"blender"', '"-b"', '"--back" "ground"',
        '"--python-exit" "-code"', '"x --background y"', '"--background --python-exit-code 1"',
        "'--background;--python-exit-code'", '"--backgrounds"', '"x-background"', 'f"{a}--background"',
        'f"--python-exit-code {b}"', '"""--background\n"""', 'r"--background"', '"\\x2d-background"', "b'--background'"]
_IMPORTS = ["import subprocess", "import subprocess as sp", "from subprocess import run", "from subprocess import run as r",
            "from os import *", "import os", "from subprocess import *", "import os as sp", "from subprocess import Popen as r",
            "import shutil as sp", "from os import system"]
_FUNCS = ["subprocess.run", "sp.run", "run", "r", "os.system", "system", "Popen", "subprocess.check_output", "sp.popen",
          "foo.run", "print"]
_CMDS = ['"blender --background a.blend --python s.py"', '"blender --background --python-exit-code 1 x"',
         '"blender --background x # --python-exit-code 1"', '"blender --background x; echo --python-exit-code"',
         '"echo hi && blender --background y"', '"blender -b x"', '"blender --background x\\n--python-exit-code 1"']


def _expr(rng: random.Random, depth: int) -> str:
    k = rng.random()
    if depth <= 0 or k < 0.3:
        return rng.choice(_STR + ["a", "1", "None"])
    if k < 0.45:
        return "[" + ", ".join(_expr(rng, depth - 1) for _ in range(rng.randint(0, 4))) + "]"
    if k < 0.6:
        items = [_expr(rng, depth - 1) for _ in range(rng.randint(0, 4))]
        return "(" + ", ".join(items) + ("," if len(items) == 1 else "") + ")"
    if k < 0.67:
        return "{" + ", ".join(_expr(rng, depth - 1) for _ in range(rng.randint(1, 3))) + "}"
    if k < 0.74:
        return "{" + ", ".join(f"{_expr(rng, 0)}: {_expr(rng, depth - 1)}" for _ in range(rng.randint(1, 3))) + "}"
    fn = rng.choice(_FUNCS)
    if rng.random() < 0.5:
        arg = rng.choice(_CMDS)
    else:
        arg = _expr(rng, depth - 1)
    kw = rng.choice(["", "args=", "cmd=", "command=", "shell="])
    extra = f", check={_expr(rng, depth - 1)}" if rng.random() < 0.3 else ""
    return f"{fn}({kw}{arg}{extra})"


def gen_program(rng: random.Random) -> str:
    lines = [rng.choice(_IMPORTS) for _ in range(rng.randint(0, 3))]
    for n in range(rng.randint(1, 6)):
        kind = rng.random()
        if kind < 0.6:
            lines.append(f"v{n} = {_expr(rng, rng.randint(1, 5))}")
        elif kind < 0.8:
            lines.append(f"def f{n}():\n    {rng.choice(_IMPORTS)}\n    return {_expr(rng, rng.randint(1, 4))}")
        else:
            lines.append(f"class C{n}:\n    x = {_expr(rng, rng.randint(1, 4))}\n    def m(self):\n"
                         f"        {rng.choice(_IMPORTS)}\n        return {_expr(rng, 3)}")
    return "\n".join(lines) + "\n"


def corpus(seed: int, n: int) -> list[str]:
    rng = random.Random(seed)
    return [gen_program(rng) for _ in range(n)]


# ---------------------------------------------------------------- commands
def cmd_parity(a) -> int:
    root = Path(a.root)
    b, c, head, sha = pair(root, a.mutant or a.candidate)
    report = {"head": head, "guard_sha256": sha, "candidate": a.mutant or a.candidate}
    vb, vc = b.repository_violations(), c.repository_violations()
    report["p1_repo_equal"] = vb == vc
    report["p1_violations"] = len(vb)
    files = b.tracked_sources()
    diff_files = []
    n_py = n_md = 0
    for rel in files:
        p = root / rel
        if not p.is_file():
            continue
        if rel.endswith(".py"):
            n_py += 1
            src = p.read_text(encoding="utf-8", errors="replace")
            if b._scan_py_source(src) != c._scan_py_source(src):
                diff_files.append(rel)
        elif rel.endswith(".md"):
            n_md += 1
            if b.scan_file(p) != c.scan_file(p):
                diff_files.append(rel)
    report.update(p2_py_files=n_py, p2_md_files=n_md, p2_diff_files=diff_files[:20], p2_equal=not diff_files)
    progs = corpus(a.seed, a.n)
    diffs = [i for i, s in enumerate(progs) if b._scan_py_source(s) != c._scan_py_source(s)]
    hits = sum(1 for s in progs if b._scan_py_source(s))
    report.update(p3_programs=len(progs), p3_with_violations=hits, p3_diff=len(diffs), p3_equal=not diffs,
                  p3_first_diff=progs[diffs[0]] if diffs else None)
    report["parity"] = report["p1_repo_equal"] and report["p2_equal"] and report["p3_equal"]
    print(json.dumps(report, indent=1, ensure_ascii=False))
    return 0 if report["parity"] else 1


def cmd_run(a) -> int:
    root = Path(a.root)
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f"--out {out} exists: refuse to overwrite")
    b, c, head, sha = pair(root, a.candidate)
    ref = b.repository_violations()
    if c.repository_violations() != ref:
        raise SystemExit("parity failure on warm-up: refuse to time")
    order = ["B", "C", "C", "B", "B", "C", "C", "B", "B", "C"][: 2 * a.pairs]
    times: dict[str, list[float]] = {"B": [], "C": []}
    seq = []
    for v in order:
        mod = b if v == "B" else c
        t = time.perf_counter()
        res = mod.repository_violations()
        dt = time.perf_counter() - t
        if res != ref:
            raise SystemExit(f"parity failure in timed run {v}")
        times[v].append(dt)
        seq.append([v, round(dt, 3)])
        print(v, round(dt, 3), flush=True)
    mb, mc = statistics.median(times["B"]), statistics.median(times["C"])
    faster = sum(1 for x, y in zip(times["B"], times["C"]) if y < x)
    rec = {"head": head, "guard_sha256": sha, "candidate": a.candidate,
           "candidates_sha256": hashlib.sha256((HERE / "candidates.py").read_bytes()).hexdigest(),
           "sequence": seq, "median_B": round(mb, 3), "median_C": round(mc, 3), "ratio": round(mc / mb, 4),
           "pairs_faster": faster, "pairs": a.pairs, "violations": len(ref)}
    out.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    print(json.dumps({k: rec[k] for k in ("median_B", "median_C", "ratio", "pairs_faster")}))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("parity", "run"):
        s = sub.add_parser(name)
        s.add_argument("--root", required=True)
        s.add_argument("--candidate", required=True, choices=sorted(candidates.CANDIDATES))
    sp = sub.choices["parity"]
    sp.add_argument("--mutant", choices=sorted(candidates.CANDIDATES))
    sp.add_argument("--seed", type=int, default=1111)
    sp.add_argument("--n", type=int, default=3000)
    sr = sub.choices["run"]
    sr.add_argument("--out", required=True)
    sr.add_argument("--pairs", type=int, default=5)
    a = ap.parse_args()
    return cmd_parity(a) if a.cmd == "parity" else cmd_run(a)


if __name__ == "__main__":
    raise SystemExit(main())
