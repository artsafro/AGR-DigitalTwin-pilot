"""OBSERVE #97: rebuild the two scratch practice roots (arm B = base, arm C = base + promoted Revit NPZ adapter).

Pattern: new-case: docs/research/trainer-g22-adapter-r97 - OBSERVE #97 trainer practice series (research only).

uv run --frozen python docs/research/trainer-g22-adapter-r97/make_candidate.py SRC_REPO DST_DIR [BASE_SHA]

Creates DST_DIR/B and DST_DIR/C as `git clone --shared` checkouts of BASE_SHA (default: the frozen base below) and
points their refs/remotes/origin/main at the arm's commit, because `agr trainer run` archives `origin/main` of the
repo that holds trainer.py. Arm C adds ONE commit: floor_from_dump.py + module_build.py copied from the G22 hooks to
tools/methods/body (two path lines in module_build.py fixed for the new depth) and the SKELETONS row 3 adapter name
given as a path. Prints both commits and C's tree hash; the frozen tree hash is CAND_TREE. Never edits SRC_REPO.
"""
import subprocess
import sys
from pathlib import Path

BASE = "e01aafc9c3ad31ad924d230a5d2ed92445ee13a7"
CAND_TREE = "55b2ae49a75f3ec76bc38e91cb3cd40f68ff7adc"  # frozen; built 3x identical before the series
HOOKS = "jobs/garibaldi22/body-training-1619/hooks"
EDITS = {
    "tools/methods/body/module_build.py": [
        ('_CORE_DIR = Path(__file__).resolve().parents[4] / "tools" / "methods" / "body"',
         "_CORE_DIR = Path(__file__).resolve().parent"),
        ("ROOT = Path(__file__).resolve().parents[4]", "ROOT = Path(__file__).resolve().parents[3]"),
    ],
    "docs/agents/SKELETONS.md": [
        ("Revit `floor_from_dump.py`", "Revit NPZ crop `tools/methods/body/floor_from_dump.py`"),
    ],
}


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


def clone(src, dst, base):
    if dst.exists():
        raise SystemExit(f"{dst} exists; the practice roots are NEW folders")
    subprocess.run(["git", "clone", "-q", "--shared", "--no-checkout", str(src), str(dst)], check=True)
    git(dst, "-c", "advice.detachedHead=false", "checkout", "-q", "--detach", base)


def main(src, out, base=BASE):
    out = Path(out)
    b, c = out / "B", out / "C"
    clone(src, b, base)
    git(b, "update-ref", "refs/remotes/origin/main", base)
    clone(src, c, base)
    for name in ("floor_from_dump.py", "module_build.py"):
        (c / "tools/methods/body" / name).write_bytes((c / HOOKS / name).read_bytes())
    for rel, pairs in EDITS.items():
        p = c / rel
        t = p.read_text(encoding="utf-8")
        for old, new in pairs:
            if t.count(old) != 1:
                raise SystemExit(f"{rel}: expected one {old!r}, found {t.count(old)}")
            t = t.replace(old, new)
        p.write_bytes(t.encode("utf-8"))
    git(c, "add", "-A")
    git(c, "-c", "user.name=r97", "-c", "user.email=r97@local", "commit", "-q", "--no-verify", "-m",
        "r97 candidate C: promote floor_from_dump.py + module_build.py to tools/methods/body, SKELETONS row 3 path")
    head = git(c, "rev-parse", "HEAD")
    git(c, "update-ref", "refs/remotes/origin/main", head)
    print("B", base)
    tree = git(c, "rev-parse", "HEAD^{tree}")
    print("C", head, "tree", tree, "OK" if base != BASE or tree == CAND_TREE else "MISMATCH vs CAND_TREE")
    print(git(c, "diff", "--stat", base, head))


if __name__ == "__main__":
    main(*sys.argv[1:4])
