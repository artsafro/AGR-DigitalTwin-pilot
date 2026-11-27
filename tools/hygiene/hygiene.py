"""Run the pinned repo-hygiene against the pilot (#1950): CLI, agent hooks and CI share this entry.

    py -3 tools/hygiene/hygiene.py check [--base origin/main] [--repo .] [--json]
    py -3 tools/hygiene/hygiene.py hook --agent claude|codex      (PreToolUse; reads the event on stdin)
    py -3 tools/hygiene/hygiene.py session --agent claude|codex   (SessionStart: one-door pointer)
    py -3 tools/hygiene/hygiene.py where                          (print the resolved command)

repo-hygiene is pinned by commit (PIN), never vendored or a submodule. HYGIENE_PROJECT names a local clone; the
pinned commit is checked out there as a detached worktree `.worktrees/pin-<sha12>`. Without it uvx installs
`git+URL@PIN`. The profile is the pilot's own docs/architecture/hygiene-profile.yaml.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

URL = "https://github.com/artsafro/repo-hygiene"
PIN = "095c3dda6006d7dc2e1e1e62a65f3ca4deedcae2"
ROOT = Path(__file__).resolve().parents[2]
PROFILE = "docs/architecture/hygiene-profile.yaml"
SCRIPT_SUFFIXES = (".py", ".pyw", ".ms", ".mcr", ".rb", ".sh", ".mjs", ".js", ".ps1", ".bat", ".cmd")
DOC_SUFFIXES = (".md",)
ONE_DOOR = ("One door: docs/agents/SKELETONS.md -> `uv run python tools/architecture/skeleton_guard.py --show "
            "<cell>` -> its trail -> rule + command at the step. Before a PR: `scripts/hygiene.sh` "
            "(or scripts/hygiene.ps1).")


class Unresolved(RuntimeError):
    pass


def _git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8")


def pinned_checkout(clone: Path) -> Path:
    """Detached worktree of `clone` at PIN (created once); refuse a clone that lacks the pinned commit."""
    if (clone / "pyproject.toml").is_file() and _git("rev-parse", "HEAD", cwd=clone).stdout.strip() == PIN:
        return clone
    target = clone / ".worktrees" / f"pin-{PIN[:12]}"
    if target.is_dir() and _git("rev-parse", "HEAD", cwd=target).stdout.strip() == PIN:
        return target
    if _git("cat-file", "-e", f"{PIN}^{{commit}}", cwd=clone).returncode:
        raise Unresolved(f"HYGIENE_PROJECT={clone} lacks the pinned commit {PIN[:12]}; run `git -C {clone} fetch`")
    made = _git("worktree", "add", "--detach", str(target), PIN, cwd=clone)
    if made.returncode:
        raise Unresolved(f"cannot check out {PIN[:12]} in {clone}: {made.stderr.strip()[:300]}")
    return target


def command(env=os.environ) -> list[str]:
    """argv prefix that runs `hygiene` at PIN."""
    clone = env.get("HYGIENE_PROJECT")
    if clone:
        project = pinned_checkout(Path(clone))
        # The project venv's interpreter skips uv's own start-up (the hook budget is 3 s).
        python = project / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if python.is_file():
            return [str(python), "-m", "repo_hygiene.cli"]
        return ["uv", "run", "-q", "--locked", "--project", str(project), "hygiene"]
    return ["uvx", "-q", "--from", f"git+{URL}@{PIN}", "hygiene"]


def touched(payload: dict) -> list[str]:
    """Repo-relative paths a Write/Edit (Claude) or apply_patch (Codex) event writes."""
    args = payload.get("tool_input") or {}
    name = payload.get("tool_name")
    if name in {"Write", "Edit"} and isinstance(args.get("file_path"), str):
        raw = [args["file_path"]]
    elif name == "apply_patch" and isinstance(args.get("command"), str):
        heads = ("*** Add File: ", "*** Update File: ", "*** Move to: ")
        raw = [line.split(": ", 1)[1].strip() for line in args["command"].splitlines() if line.startswith(heads)]
    else:
        return []
    cwd = Path(payload.get("cwd") or ROOT)
    out = []
    for item in raw:
        path = Path(item) if Path(item).is_absolute() else cwd / item
        try:
            out.append(path.resolve().relative_to(ROOT.resolve()).as_posix())
        except ValueError:
            continue  # outside this checkout
    return out


def new_script_or_doc(rel: str, base: str = "origin/main", root: Path = ROOT) -> bool:
    """A script/doc path that does not exist in `base` (a file this branch adds)."""
    if not rel.lower().endswith(SCRIPT_SUFFIXES + DOC_SUFFIXES):
        return False
    return _git("cat-file", "-e", f"{base}:{rel}", cwd=root).returncode != 0


def hook(agent: str, stdin: str, base: str = "origin/main") -> tuple[int, str]:
    payload = json.loads(stdin or "{}")
    if payload.get("hook_event_name") != "PreToolUse":
        return 0, ""
    if not any(new_script_or_doc(p, base) for p in touched(payload)):
        return 0, ""  # fast path: edits of existing files are the PR check's job
    try:
        argv = [*command(), "hook", "--agent", agent, "--repo", str(ROOT), "--profile", str(ROOT / PROFILE)]
    except Unresolved as exc:
        print(f"repo-hygiene hook skipped: {exc}", file=sys.stderr)
        return 0, ""  # fail open: an unconfigured tool must not block every write
    run = subprocess.run(argv, input=stdin, capture_output=True, text=True, encoding="utf-8")
    if run.returncode:
        print(f"repo-hygiene hook failed ({run.returncode}): {run.stderr.strip()[:300]}", file=sys.stderr)
        return 0, ""
    return 0, run.stdout.strip()


def session(agent: str) -> str:
    return json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ONE_DOOR}})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run the pinned repo-hygiene against the pilot (#1950).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    chk = sub.add_parser("check", help="new findings of the working tree against --base")
    chk.add_argument("--base", default="origin/main")
    chk.add_argument("--repo", default=str(ROOT))
    chk.add_argument("--profile", default=None, help=f"default: <repo-of-this-script>/{PROFILE}")
    chk.add_argument("--json", action="store_true")
    for name in ("hook", "session"):
        sub.add_parser(name).add_argument("--agent", choices=["claude", "codex"], required=True)
    sub.add_parser("where", help="print the resolved repo-hygiene command")
    args = ap.parse_args(argv)
    if args.cmd == "session":
        print(session(args.agent))
        return 0
    if args.cmd == "hook":
        code, out = hook(args.agent, sys.stdin.read())
        if out:
            print(out)
        return code
    try:
        prefix = command()
    except Unresolved as exc:
        print(f"repo-hygiene: {exc}", file=sys.stderr)
        return 2
    if args.cmd == "where":
        print(" ".join(prefix))
        return 0
    argv = [*prefix, "check", "--repo", args.repo, "--profile", args.profile or str(ROOT / PROFILE),
            "--base", args.base, *(["--json"] if args.json else [])]
    return subprocess.run(argv).returncode


if __name__ == "__main__":
    raise SystemExit(main())
