"""Pattern: n/a | new-case: docs/research/autoresearch-repo-guards-harness/adopt_parity.py - standing #9 adoption parity (OBSERVE)

Old duplicate_guard (git show <base>) vs the working-tree one, in ONE process:
  - main(["--root", ROOT, "--json", "--table"]): rc + stdout;
  - scan_text of EVERY tracked *.py (sorted findings, or exception type + text).
With --mutant the new module is broken on purpose first; the comparison must then DIFFER.
Usage: uv run python docs/research/autoresearch-repo-guards-harness/adopt_parity.py --base 69cf3a7c
       [--mutant scope_module|walk_drop_calls] --out C:/x/ar_t_a334c185/parity.json
Contract: docs/research/autoresearch-repo-guards-adopt.md
"""
import argparse
import ast
import contextlib
import hashlib
import io
import json
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DG = "tools/architecture/duplicate_guard.py"
sys.path.insert(0, str(ROOT / "tools/architecture"))


def load(name, source):
    mod = types.ModuleType(name)
    mod.__file__ = str(ROOT / DG)
    sys.modules[name] = mod
    exec(compile(source, str(ROOT / DG), "exec"), mod.__dict__)
    return mod


def mutate(dg, name):
    if name == "scope_module":
        dg._scopes = lambda tree: {id(n): dg.MODULE for n in ast.walk(tree)}
    elif name == "walk_drop_calls":
        dg._walk = lambda node: tuple(n for n in ast.walk(node) if not isinstance(n, ast.Call))
    else:
        raise SystemExit(f"unknown mutant {name}")


def run_main(dg):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            rc = dg.main(["--root", str(ROOT), "--json", "--table"])
        except SystemExit as e:
            rc = e.code
    return rc, buf.getvalue()


def scan_all(dg, files):
    out = {}
    for rel in files:
        text = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
        try:
            out[rel] = [list(f) for f in dg.scan_text(text, rel)]
        except Exception as e:   # noqa: BLE001 - the exception itself is part of the parity
            out[rel] = f"{type(e).__name__}: {e}"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--mutant")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit("--out exists")
    old_src = subprocess.run(["git", "show", f"{a.base}:{DG}"], cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8", check=True).stdout
    new_src = (ROOT / DG).read_text(encoding="utf-8")
    if old_src == new_src:
        raise SystemExit("old == new: nothing to compare")
    old, new = load("dg_old", old_src), load("dg_new", new_src)
    if a.mutant:
        mutate(new, a.mutant)
    files = sorted(subprocess.run(["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True, text=True,
                                  encoding="utf-8", check=True).stdout.split())
    mo, mn = run_main(old), run_main(new)
    so, sn = scan_all(old, files), scan_all(new, files)
    diff = [f for f in files if so[f] != sn[f]]
    rec = dict(base=a.base, mutant=a.mutant, files=len(files),
               files_with_findings=sum(1 for f in files if isinstance(so[f], list) and so[f]),
               files_raising=sum(1 for f in files if isinstance(so[f], str)),
               findings=sum(len(v) for v in so.values() if isinstance(v, list)),
               main_rc=[mo[0], mn[0]], main_identical=mo == mn,
               main_sha=[hashlib.sha256(mo[1].encode()).hexdigest(), hashlib.sha256(mn[1].encode()).hexdigest()],
               scan_text_diff_files=len(diff), scan_text_diff_sample=diff[:10])
    rec["identical"] = rec["main_identical"] and not diff
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    print(json.dumps(rec))
    return 0


if __name__ == "__main__":
    sys.exit(main())
