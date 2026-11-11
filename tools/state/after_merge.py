"""Regenerate docs/PROJECT_STATE.md on main right after a pull request is merged.

AGENTS.md: PROJECT_STATE is regenerated only on `main` after a merge. This script makes that step automatic:

    python tools/state/after_merge.py --pr 1097     # after `gh pr merge 1097` (Codex, manual)
    python tools/state/after_merge.py hook          # Claude Code PostToolUse hook, reads the hook JSON on stdin
    python tools/state/after_merge.py check [--states-json FILE]

`--pr N` checks that #N is MERGED, finds the checkout of `main` (`git worktree list`), refuses when it is dirty,
fast-forwards it to `origin/main`, runs `tools/state/project_state.py` there, then `tools/state/entry_budget.py
--check` (#1222): over the cold-entry budget it restores the file and exits 1 without committing. Otherwise it
commits the regenerated file
(`docs(state): regenerate PROJECT_STATE after #N`). It never pushes: `git push origin main` stays the user's
approval (guard). Then it runs `check` on the new file.

`check` fails (exit 1) when a pull request listed under "Open pull requests:" is MERGED or CLOSED. PR states come
from `gh pr view` or, offline, from a JSON file `{"<number>": "OPEN|MERGED|CLOSED"}` (`--states-json` or the
environment variable DT_PR_STATES_JSON; `tests/test_state_after_merge.py` uses the same injection).

Exit codes: 0 done / nothing to do, 1 stale state or over the cold-entry budget, 2 refused (dirty main, no main
checkout, PR not merged, git/gh failure).
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE = "docs/PROJECT_STATE.md"
GENERATOR = "tools/state/project_state.py"
BUDGET_CHECK = "tools/state/entry_budget.py"
_OPEN_ROW = re.compile(r"^- #([1-9][0-9]*) ")
_MERGE_CMD = re.compile(r"\bgh\s+pr\s+merge\b(?P<rest>[^\n;&|]*)")


class Refused(Exception):
    pass


def listed_open_prs(text):
    """PR numbers under 'Open pull requests:' of a PROJECT_STATE text."""
    numbers = []
    inside = False
    for line in text.splitlines():
        if line.strip() == "Open pull requests:":
            inside = True
            continue
        if inside:
            if line.strip() == "" or line.startswith("## "):
                break
            match = _OPEN_ROW.match(line.strip())
            if match:
                numbers.append(int(match.group(1)))
    return numbers


def stale_open_prs(text, states):
    """Listed-open PRs whose state is MERGED or CLOSED. `states` maps int -> state string."""
    return [n for n in listed_open_prs(text) if str(states.get(n, "")).upper() in ("MERGED", "CLOSED")]


def merged_pr_from_command(command):
    """`gh pr merge 1097 --merge` -> 1097; None when no `gh pr merge` or no number in it."""
    match = _MERGE_CMD.search(command or "")
    if not match:
        return None
    for token in match.group("rest").split():
        token = token.strip("'\"")
        if token.startswith("-"):
            continue
        tail = token.rstrip("/").rsplit("/", 1)[-1].lstrip("#")
        if tail.isdigit():
            return int(tail)
        return None
    return None


def _run(argv, cwd):
    done = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
                          errors="replace", check=False)
    return done.returncode, done.stdout


def _ok(run, argv, cwd, what):
    code, out = run(argv, cwd)
    if code != 0:
        raise Refused(f"{what} failed: {' '.join(argv)}")
    return out


def pr_state(run, number, cwd):
    out = _ok(run, ["gh", "pr", "view", str(number), "--json", "state"], cwd, "gh pr view")
    try:
        return str(json.loads(out)["state"]).upper()
    except (ValueError, KeyError, TypeError) as exc:
        raise Refused(f"gh pr view {number}: unreadable answer") from exc


def main_checkout(run, cwd):
    out = _ok(run, ["git", "worktree", "list", "--porcelain"], cwd, "git worktree list")
    path = None
    for line in out.splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree "):].strip()
        elif line.strip() == "branch refs/heads/main" and path:
            return Path(path)
    raise Refused("no checkout has branch main (git worktree list)")


def live_states(run, numbers, cwd):
    return {n: pr_state(run, n, cwd) for n in numbers}


def file_states(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {int(k): str(v).upper() for k, v in data.items()}


def refresh(number, run=_run, cwd=ROOT, python=sys.executable, commit=True):
    """Regenerate PROJECT_STATE on the main checkout after #number merged. Returns (exit code, message)."""
    try:
        state = pr_state(run, number, cwd)
        if state != "MERGED":
            return 2, f"#{number} is {state}, not MERGED: PROJECT_STATE left alone"
        main = main_checkout(run, cwd)
        if _ok(run, ["git", "status", "--porcelain"], main, "git status").strip():
            return 2, f"main checkout {main} is dirty: PROJECT_STATE not regenerated; clean it, then rerun --pr {number}"
        _ok(run, ["git", "fetch", "origin", "main"], main, "git fetch")
        _ok(run, ["git", "merge", "--ff-only", "origin/main"], main, "git merge --ff-only origin/main")
        _ok(run, [python, GENERATOR, "--repo", "."], main, "project_state.py")
        budget_code, budget_out = run([python, BUDGET_CHECK, "--check"], main)
        if budget_code != 0:
            _ok(run, ["git", "checkout", "--", STATE], main, "git checkout")
            total = (budget_out or "").strip().splitlines()[-1:] or [f"exit {budget_code}"]
            return 1, (f"after_merge: cold-entry budget check failed ({total[0]}): "
                       f"PROJECT_STATE after #{number} not committed, file restored")
        changed = _ok(run, ["git", "status", "--porcelain", "--", STATE], main, "git status").strip()
        note = "unchanged"
        if changed and commit:
            _ok(run, ["git", "add", "--", STATE], main, "git add")
            _ok(run, ["git", "commit", "-m", f"docs(state): regenerate PROJECT_STATE after #{number}", "--", STATE],
                main, "git commit")
            note = "committed on local main; push with `git push origin main` (needs the user's approval)"
        elif changed:
            note = "regenerated, not committed (--no-commit)"
        text = (main / STATE).read_text(encoding="utf-8")
        stale = stale_open_prs(text, live_states(run, listed_open_prs(text), main))
    except Refused as exc:
        return 2, f"after_merge: {exc}"
    if stale:
        return 1, f"PROJECT_STATE still lists merged/closed PRs as open: {stale}"
    return 0, f"PROJECT_STATE after #{number}: {note}"


def hook(stdin_text, run=_run, cwd=ROOT):
    """PostToolUse hook: after a `gh pr merge N` shell command, run refresh(N). Never blocks the tool."""
    try:
        data = json.loads(stdin_text or "{}")
    except ValueError:
        return None
    command = (data.get("tool_input") or {}).get("command", "")
    if not re.search(r"\bgh\s+pr\s+merge\b", command or ""):
        return None
    number = merged_pr_from_command(command)
    if number is None:
        message = "gh pr merge without a PR number: run `python tools/state/after_merge.py --pr <N>` yourself"
    else:
        _code, message = refresh(number, run=run, cwd=cwd)
    return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": message}}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Regenerate PROJECT_STATE on main after a merge.")
    parser.add_argument("mode", nargs="?", choices=("hook", "check"), default=None)
    parser.add_argument("--pr", type=int, default=None)
    parser.add_argument("--no-commit", action="store_true")
    parser.add_argument("--states-json", default=os.environ.get("DT_PR_STATES_JSON"))
    parser.add_argument("--file", default=str(ROOT / STATE))
    args = parser.parse_args(argv)
    if args.mode == "hook":
        out = hook(sys.stdin.read())
        if out:
            sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        return 0
    if args.mode == "check":
        text = Path(args.file).read_text(encoding="utf-8")
        try:
            states = (file_states(args.states_json) if args.states_json
                      else live_states(_run, listed_open_prs(text), ROOT))
        except Refused as exc:
            print(f"after_merge: {exc}", file=sys.stderr)
            return 2
        stale = stale_open_prs(text, states)
        if stale:
            print(f"PROJECT_STATE lists merged/closed PRs as open: {stale}")
            return 1
        print("PROJECT_STATE open list: no merged or closed PR")
        return 0
    if args.pr is None:
        parser.error("--pr N, hook or check is required")
    code, message = refresh(args.pr, commit=not args.no_commit)
    print(message, file=sys.stderr if code else sys.stdout)
    return code


if __name__ == "__main__":
    sys.exit(main())
