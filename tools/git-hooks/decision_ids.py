"""Decision id guard: a branch must not allocate a `D<n>` that main or another open PR already uses (#1037).

Pattern: new-case: allocation and collision check of decision ids across parallel branches.

    python tools/git-hooks/decision_ids.py next --fetch       # next free id over main, this branch, open PRs
    python tools/git-hooks/decision_ids.py check [--staged]   # fail on a reused id (pre-commit: --staged --fetch)

"New" ids are the rows of `docs/decisions.md` in the branch that the merge-base with the base ref (default
`origin/main`) does not have. A new id collides when the base ref, or the head of another open pull request
(`gh pr list`), defines the same id with a different row. A row defined twice in the branch is a collision too.
Rows the branch only edits (for example "superseded by") are not new and pass.

Exit codes: 0 no collision, 1 collision (each one named), 2 cannot check (no base ref, no merge-base, no rows,
`gh` or a PR head unreadable). `--no-open-prs` skips the open-PR comparison explicitly and says so.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

LOG = "docs/decisions.md"
ROW = re.compile(r"^\| (D\d{3,}) \|")  # the id format of tests/test_decisions.py; malformed rows fail there


class CheckError(Exception):
    """The check cannot be run; the caller exits 2."""


def rows(text: str | None) -> list[tuple[str, str]]:
    """(id, whitespace-normalised row) for every decision row of a log text, in order."""
    out = []
    for line in (text or "").splitlines():
        m = ROW.match(line)
        if m:
            out.append((m.group(1), " ".join(line.split())))
    return out


def row_map(text: str | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for did, line in rows(text):
        out.setdefault(did, line)
    return out


def number(did: str) -> int:
    return int(did[1:])


def find_collisions(branch: str, base: str | None, main: str, others: dict[str, str | None]) -> list[str]:
    """Problems for the branch log `branch`; `base` is the merge-base log, `others` maps PR label -> head log."""
    problems = []
    seen: dict[str, int] = {}
    for did, _ in rows(branch):
        seen[did] = seen.get(did, 0) + 1
    for did, n in seen.items():
        if n > 1:
            problems.append(f"{did}: defined {n} times in this branch")
    mine, base_ids, on_main = row_map(branch), set(row_map(base)), row_map(main)
    other_maps = {label: row_map(text) for label, text in others.items()}
    for did in sorted((d for d in mine if d not in base_ids), key=number):
        if did in on_main:
            if on_main[did] != mine[did]:
                problems.append(f"{did}: main already uses it for another decision: {on_main[did][:160]}")
            continue
        for label, other in other_maps.items():
            if did in other and other[did] != mine[did]:
                problems.append(f"{did}: also allocated by {label}: {other[did][:160]}")
    return problems


def next_free(*texts: str | None) -> str:
    top = max((number(did) for text in texts for did, _ in rows(text)), default=0)
    return f"D{top + 1:03d}"


def git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


def show(rev: str, cwd: Path) -> str | None:
    """The log at `rev` (`:` = index); None when the revision has no log file."""
    r = git("show", f"{rev}:{LOG}" if rev != ":" else f":{LOG}", cwd=cwd)
    return r.stdout if r.returncode == 0 else None


def commit_of(ref: str, cwd: Path) -> str:
    r = git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", cwd=cwd)
    if r.returncode != 0 or not r.stdout.strip():
        raise CheckError(f"base ref {ref!r} not found (run `git fetch origin`)")
    return r.stdout.strip()


def current_branch(cwd: Path) -> str:
    r = git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd)
    return r.stdout.strip() if r.returncode == 0 else ""


def open_pr_logs(cwd: Path, repo: str | None, remote: str = "origin") -> dict[str, str | None]:
    """PR label -> log at its head, for every open PR except the one of the current branch."""
    cmd = ["gh", "pr", "list", "--state", "open", "--limit", "1000", "--json", "number,headRefName,headRefOid"]
    if repo:
        cmd += ["--repo", repo]
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError as exc:
        raise CheckError(f"cannot run gh: {exc}") from exc
    if r.returncode != 0:
        raise CheckError(f"gh pr list failed: {r.stderr.strip()[:300]}")
    try:
        prs = json.loads(r.stdout)
    except json.JSONDecodeError as exc:
        raise CheckError(f"gh pr list returned no JSON: {exc}") from exc
    mine, out = current_branch(cwd), {}
    for pr in prs:
        if pr.get("headRefName") == mine:
            continue
        oid, label = pr.get("headRefOid"), f"PR #{pr.get('number')} ({pr.get('headRefName')})"
        if not oid:
            raise CheckError(f"{label}: no head commit in gh output")
        if git("cat-file", "-e", f"{oid}^{{commit}}", cwd=cwd).returncode != 0:
            git("fetch", "-q", remote, f"pull/{pr.get('number')}/head", cwd=cwd)
            if git("cat-file", "-e", f"{oid}^{{commit}}", cwd=cwd).returncode != 0:
                raise CheckError(f"{label}: head {oid[:10]} cannot be fetched")
        out[label] = show(oid, cwd)
    return out


def github_repo(base: str, cwd: Path) -> str:
    """owner/name of the remote of `base` (`origin/main` -> origin); gh's own default may be another remote."""
    remote, _, ref = base.partition("/")
    url = git("remote", "get-url", remote, cwd=cwd).stdout.strip() if ref else ""
    m = re.match(r"^(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)([\w.-]+/[\w.-]+?)(?:\.git)?/?$",
                 url)
    if not m:
        raise CheckError(f"cannot tell the GitHub repo of base {base!r} (remote url {url!r}); pass --repo")
    return m.group(1)


def other_logs(args, cwd: Path) -> tuple[dict[str, str | None], str]:
    if args.pr_rev:
        out = {}
        for item in args.pr_rev:
            label, _, rev = item.partition("=")
            if not label or not rev:
                raise CheckError(f"--pr-rev needs LABEL=REV, got {item!r}")
            commit_of(rev, cwd)
            out[label] = show(rev, cwd)
        return out, f"{len(out)} given PR heads"
    if args.no_open_prs:
        return {}, "open PRs NOT checked (--no-open-prs)"
    repo = args.repo or github_repo(args.base, cwd)
    out = open_pr_logs(cwd, repo, args.base.partition("/")[0] if "/" in args.base else "origin")
    return out, f"{len(out)} open PR heads of {repo}"


def branch_log(args, cwd: Path) -> str:
    if args.staged:
        text = show(":", cwd)
    elif args.rev:
        commit_of(args.rev, cwd)
        text = show(args.rev, cwd)
    else:
        path = cwd / LOG
        text = path.read_text(encoding="utf-8") if path.is_file() else None
    if text is None or not rows(text):
        raise CheckError(f"no decision rows read from {LOG} of this branch")
    return text


def run(args) -> int:
    cwd = Path(args.repo_dir).resolve()
    if args.fetch:
        remote, _, ref = args.base.partition("/")
        if not ref or git("fetch", "-q", remote, ref, cwd=cwd).returncode != 0:
            raise CheckError(f"cannot fetch {args.base}")
    base_commit = commit_of(args.base, cwd)
    main = show(base_commit, cwd) or ""
    if not rows(main):
        raise CheckError(f"no decision rows in {LOG} at {args.base}")
    branch = branch_log(args, cwd)
    others, scope = other_logs(args, cwd)
    if args.command == "next":
        print(next_free(main, branch, *others.values()))
        print(f"decision_ids: next free id over {args.base}, this branch and {scope}", file=sys.stderr)
        return 0
    head = args.rev or "HEAD"
    mb = git("merge-base", head, base_commit, cwd=cwd)
    if mb.returncode != 0 or not mb.stdout.strip():
        raise CheckError(f"no merge-base between {head} and {args.base}")
    problems = find_collisions(branch, show(mb.stdout.strip(), cwd), main, others)
    for p in problems:
        print(f"decision_ids: collision {p}", file=sys.stderr)
    if problems:
        print(f"decision_ids: renumber to `{next_free(main, branch, *others.values())}` or later "
              f"(`python tools/git-hooks/decision_ids.py next`), and every [D<n>] reference with it", file=sys.stderr)
        return 1
    print(f"decision_ids: ok, no new id reused ({args.base}, {scope})")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("command", choices=("check", "next"))
    ap.add_argument("--base", default="origin/main", help="base ref (default origin/main)")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--staged", action="store_true", help="read the branch log from the index")
    src.add_argument("--rev", help="read the branch log from this revision (default: work tree)")
    prs = ap.add_mutually_exclusive_group()
    prs.add_argument("--no-open-prs", action="store_true", help="compare with the base ref only")
    prs.add_argument("--pr-rev", action="append", metavar="LABEL=REV", help="compare with these revisions "
                     "instead of the open PRs from gh")
    ap.add_argument("--fetch", action="store_true", help="fetch the base ref (<remote>/<branch>) first")
    ap.add_argument("--repo", help="GitHub owner/name for gh (default: the url of the base ref's remote)")
    ap.add_argument("--repo-dir", default=".", help="git work tree (default: current directory)")
    args = ap.parse_args(argv)
    try:
        return run(args)
    except CheckError as exc:
        print(f"decision_ids: cannot check: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
