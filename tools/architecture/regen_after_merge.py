"""Merge without manual resolution of generated maps, then regenerate them (#1558).

Pattern: n/a | new-case: merge helper - keep-one-side driver for generated maps + decision rows + regenerate.

The route/context maps under docs/architecture (*.excalidraw, *.svg, *-owners.md) are generated from the YAML
by route_map.py, and the scheme/owners views carry a revision hash of ALL YAML inputs, so any two PRs that
regenerate conflict on every map. `.gitattributes` marks exactly those outputs `merge=ours` (keep the HEAD copy);
the merged YAML is then the only source and `route_map.py` rewrites the maps. `route_map.py --check` stays the
single guard (tests/test_architecture_map_1359.py): stale maps after a merge fail it until regenerated.
GitHub's mergeability check ignores custom merge drivers: a PR that GitHub shows CONFLICTING is fixed by running
`--merge origin/main` on its branch (rework) and pushing; an integration branch runs `--merge <pr branch>` per PR.

Usage (from the repo or a worktree):
  python tools/architecture/regen_after_merge.py --install            # once per clone: git config merge.ours.driver true
  python tools/architecture/regen_after_merge.py --merge origin/main  # merge + resolve + regenerate + check + commit
  python tools/architecture/regen_after_merge.py                      # after merges done by hand: regenerate + check + commit
Per run: install the driver (idempotent); `git merge --no-edit REF`; unmerged generated maps are taken from HEAD,
an unmerged docs/decisions.md goes through tools/decisions_merge.py; any other unmerged path stops (exit 1, merge
left in progress for a human). Then route_map.py rewrites the maps, `route_map.py --check` must pass (skip only
with --no-check, for synthetic repos without the referenced code), and the result is committed (merge commit, or
"chore(architecture): regenerate route maps after merge" when only the maps changed; --no-commit leaves it staged).
Exit codes: 0 done, 1 conflict left for a human / decision collision / check failed, 2 usage or git error.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import decisions_merge  # noqa: E402
import route_map  # noqa: E402

DRIVER = "ours"
DECISIONS = "docs/decisions.md"


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {(r.stderr or r.stdout).strip()}")
    return r


def install(root: Path) -> None:
    """Configure the keep-HEAD driver named by .gitattributes (`merge=ours`); repo-local, idempotent."""
    git(root, "config", f"merge.{DRIVER}.name", "keep HEAD; generated file, regenerate after merge (#1558)")
    git(root, "config", f"merge.{DRIVER}.driver", "true")


def generated(root: Path) -> set[str]:
    _, _, files = route_map.render_all(root)
    return {rel.as_posix() for rel in files}


def keep_one_side(root: Path, paths: list[str]) -> set[str]:
    """Paths whose .gitattributes merge driver is `ours` (the generated maps; the test pins the set)."""
    if not paths:
        return set()
    out = git(root, "check-attr", "merge", "--", *paths).stdout.splitlines()
    return {line.split(": ")[0] for line in out if line.endswith(f": merge: {DRIVER}")}


def unmerged(root: Path) -> list[str]:
    return sorted(set(git(root, "diff", "--name-only", "--diff-filter=U").stdout.split()))


def merging(root: Path) -> bool:
    return git(root, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False).returncode == 0


def run(root: Path, ref: str | None, check: bool = True, commit: bool = True) -> int:
    install(root)
    if ref:
        r = git(root, "merge", "--no-edit", ref, check=False)
        print((r.stdout + r.stderr).strip())
        if r.returncode != 0 and not merging(root):
            print(f"ERROR: git merge {ref} failed before merging", file=sys.stderr)
            return 2
    left = unmerged(root)
    maps_left = keep_one_side(root, left)
    others = [p for p in left if p not in maps_left and p != DECISIONS]
    if others:
        print("conflicts that need a human (merge left in progress):")
        for p in others:
            print(f"  {p}")
        return 1
    for p in sorted(maps_left):
        git(root, "checkout", "--ours", "--", p)   # stale either way; regenerated below
    if DECISIONS in left:
        rc = decisions_merge.main([str(root / DECISIONS)])
        if rc != 0:
            print(f"{DECISIONS}: decisions_merge exit {rc}; fix the rows, then rerun without --merge")
            return 1
        git(root, "add", "--", DECISIONS)
    if route_map.main(["--root", str(root)]) != 0:
        return 1
    maps = sorted(generated(root))
    git(root, "add", "--", *maps)
    if check and route_map.main(["--root", str(root), "--check"]) != 0:
        print("route_map.py --check failed after regeneration; nothing committed")
        return 1
    if unmerged(root):
        print("unmerged paths remain; nothing committed")
        return 1
    if not commit:
        return 0
    if merging(root):
        git(root, "commit", "--no-edit")
        print("committed the merge")
    elif git(root, "diff", "--cached", "--quiet", "--", *maps, check=False).returncode != 0:
        git(root, "commit", "-m", "chore(architecture): regenerate route maps after merge (#1558)", "--", *maps)
        print("committed regenerated maps")
    else:
        print("maps already match the YAML; nothing to commit")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Merge + regenerate generated route/context maps (#1558)")
    ap.add_argument("--root", type=Path, default=route_map.ROOT)
    ap.add_argument("--install", action="store_true", help="only configure the merge driver")
    ap.add_argument("--merge", metavar="REF", help="git merge REF first")
    ap.add_argument("--no-check", action="store_true", help="skip route_map.py --check (synthetic repos only)")
    ap.add_argument("--no-commit", action="store_true", help="stage, do not commit")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.install:
            install(root)
            print(f"merge.{DRIVER}.driver configured in {root}")
            return 0
        return run(root, args.merge, check=not args.no_check, commit=not args.no_commit)
    except (RuntimeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
