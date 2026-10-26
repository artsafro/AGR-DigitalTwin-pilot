"""Session context for a context rotation (/handover -> /clear -> "продолжай" or /takeover; docs/agents/WORKFLOW.md).

  py -3 tools/hooks/session_context.py start       SessionStart (startup / clear / compact): the git state, open PRs
                                                   and docs/HANDOFF.md as additionalContext
  py -3 tools/hooks/session_context.py precompact  PreCompact: a manual /compact with a stale HANDOFF is blocked
                                                   (`/compact force` passes); an auto compaction is logged, never
                                                   blocked - the agent is told after it (SessionStart compact)
  py -3 tools/hooks/session_context.py report      the same text as `start`, plain, for /takeover

A hook cannot write the handoff itself: only the agent knows decisions and the next step. It can tell whether
docs/HANDOFF.md is behind HEAD, belongs to another branch or has an old format, and it says so.
SessionStart stdout and additionalContext both reach the context; either is capped at 10 000 characters
(code.claude.com/docs/en/hooks), so the HANDOFF body is cut to fit and the agent reads the file.
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "git-hooks"))
from branch_names import RENAME_HINT, is_auto  # noqa: E402

HANDOFF = "docs/HANDOFF.md"
LIMIT = 9500                                         # under the 10 000-character hook cap
LINE = 300                                           # one commit subject, PR title or status line
RELEVANT_PATHS = ("src/", "tools/", "standards/", "docs/domain/", "docs/decisions.md",
                  "docs/procedure/", "docs/agents/CAPABILITIES.md")
BRANCH_LINE = re.compile(r"^Branch:\s*`([^`]+)`", re.M)
COMMIT_LINE = re.compile(r"Commit:\s*`([0-9a-f]{7,40})`")
TRANSCRIPT_LINE = re.compile(r"^Transcript:[ \t]*`([^`\n]+)`", re.M)


def _root():
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])


def _git(*args):
    try:
        r = subprocess.run(["git", "-c", "core.quotepath=false", "-c", "color.ui=never",
                            "-c", "log.showSignature=false", *args], cwd=_root(), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.rstrip("\n") if r.returncode == 0 else None


def open_prs():
    """Open PRs of the repo as lines, or a note why there are none (gh missing, offline, not logged in)."""
    if not shutil.which("gh"):
        return ["(gh not found)"]
    try:
        r = subprocess.run(["gh", "pr", "list", "--state", "open", "--limit", "15", "--json",
                            "number,title,headRefName,isDraft"], cwd=_root(), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=15)
        prs = json.loads(r.stdout) if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError):
        prs = None
    if prs is None:
        return ["(gh pr list failed)"]
    branch = _git("branch", "--show-current")
    return [f"#{p['number']} {p['title']} [{p['headRefName']}]" + (" draft" if p.get("isDraft") else "")
            + ("  <- this branch" if p["headRefName"] == branch else "") for p in prs] or ["(none)"]


def handoff_state():
    """(text, warnings) of docs/HANDOFF.md against the current branch, HEAD and the working tree."""
    path = _root() / HANDOFF
    if not path.exists():
        return "", [f"{HANDOFF} does not exist: no handover was made"]
    try:
        text = path.read_bytes().decode("utf-8", errors="replace")
    except OSError as e:
        return "", [f"{HANDOFF} cannot be read ({e}): read it yourself and check every fact against git"]
    if _git("rev-parse", "HEAD") is None:            # no git: nothing below can be verified (review 1 of #107)
        return text, ["git failed in this worktree: the handoff's freshness is not verified"]
    warnings = []
    branch = _git("branch", "--show-current") or "(detached)"
    m = BRANCH_LINE.search(text)
    if not m:
        warnings.append(f"{HANDOFF} has no `Branch:` line (written before docs/HANDOFF.template.md): treat it as "
                        "background, check every fact against git")
    elif m.group(1) != branch:
        warnings.append(f"{HANDOFF} belongs to branch `{m.group(1)}`, this session is on `{branch}`: it is not "
                        "this task's handoff")
    last = _git("log", "-1", "--format=%H", "--", HANDOFF)
    behind = _git("rev-list", "--count", f"{last}..HEAD") if last else None
    if behind and behind != "0":
        warnings.append(f"{behind} commit(s) after the last commit of {HANDOFF}: the handoff is behind HEAD")
    status = _git("status", "--porcelain")
    if status is None:                               # e.g. a broken index (review 2 of #107)
        warnings.append("git status failed: uncommitted work is not verified")
    dirty = (status or "").splitlines()
    if any(line[3:].strip() == HANDOFF for line in dirty):
        warnings.append(f"{HANDOFF} has uncommitted changes")
    others = [line for line in dirty if line[3:].strip() != HANDOFF]
    if others:                                       # work after the handover (review 1 of #107)
        warnings.append(f"{len(others)} uncommitted path(s) in the working tree: the handoff does not cover them")
    return text, warnings


def transcript_line(text):
    """The handoff's saved transcript (tools/hooks/save_transcript.py, #121) as one line, or None without one."""
    m = TRANSCRIPT_LINE.search(text or "")
    if not m or m.group(1).strip() in ("", "-"):
        return None
    try:
        exists = Path(m.group(1)).is_file()
    except (OSError, ValueError):                    # a malformed path never breaks the context
        exists = False
    return f"Transcript: {m.group(1)}" + ("" if exists else " (missing on this machine)")


def _line(text):
    return text if len(text) <= LINE else text[:LINE] + " [...]"


class FreshnessIncomplete(Exception):
    """Empty, partial or unsupported integration input. Callers warn and do not report a count."""


_SHA = re.compile(r"^[0-9a-f]{40}$")
_SHORT = re.compile(r"^[0-9a-f]{7,40}$")
_NOT_VERIFIED = "branch freshness is not verified"


def _supported_diff_path(path):
    if not path or path[:1] in ("'", '"') or path.startswith("/") or (len(path) >= 2 and path[1] == ":"):
        return False
    return all(part not in ("", ".", "..") for part in path.split("/"))


def _path_is_relevant(path):
    for spec in RELEVANT_PATHS:
        if spec.endswith("/"):
            if path.startswith(spec):
                return True
        elif path == spec:
            return True
    return False


def classify_integration_log(text):
    """Titles of relevant first-parent integrations in one `git log` blob.

    The blob is `git log --first-parent --diff-merges=first-parent --name-only
    --format=%x1e%H%x09%h%x09%s%x09%P`. Each record's paths are that commit's diff
    against its first parent (a merge resolution counts; a root commit has no parent).
    Empty text, a partial header, a missing parent or an unsupported path raises
    FreshnessIncomplete. An empty path list is a real empty diff and is not relevant.
    """
    if not isinstance(text, str):
        raise FreshnessIncomplete("empty or partial log")
    text = text.lstrip("\r\n")
    if text == "" or not text.startswith("\x1e"):
        raise FreshnessIncomplete("empty or partial log")
    titles = []
    for part in text.split("\x1e")[1:]:
        lines = part.splitlines()
        if not lines or not lines[0].strip():
            raise FreshnessIncomplete("empty record")
        sha, sep1, rest = lines[0].partition("\t")
        short, sep2, rest = rest.partition("\t")
        subject, sep3, parents = rest.partition("\t")
        if not (sep1 and sep2 and sep3) or not _SHA.fullmatch(sha) or not _SHORT.fullmatch(short):
            raise FreshnessIncomplete("partial header")
        subject = subject.strip()
        if not subject:
            raise FreshnessIncomplete("empty subject")
        parent_list = parents.split()
        if not parent_list or any(_SHA.fullmatch(p) is None for p in parent_list):
            raise FreshnessIncomplete("unsupported parents")
        paths = []
        for raw in lines[1:]:
            if not raw.strip():
                continue
            path = raw.strip().replace("\\", "/")
            if not _supported_diff_path(path):
                raise FreshnessIncomplete("unsupported path")
            paths.append(path)
        if any(_path_is_relevant(path) for path in paths):
            titles.append(f"{short} {subject}")
    return titles


def branch_freshness():
    """Warnings for a detached HEAD or for origin/main integrations that touch the report paths.

    An integration is one first-parent commit on origin/main that is not in HEAD (a merge or a
    plain commit). Relevance is that commit's own diff against its first parent, so a no-ff merge
    counts once, under the merge title, and a merge-resolution change counts. Read-only and
    offline: no fetch. A missing origin/main ref skips the behind check and does not claim the
    branch is current. Empty, partial or unsupported git output is a warning, never a clean result.
    """
    branch = _git("branch", "--show-current")
    head = _git("rev-parse", "--short", "HEAD")
    if branch is None or head is None:
        return [f"git failed: {_NOT_VERIFIED}"]
    warnings = []
    if branch == "":
        warnings.append(f"HEAD is detached at `{head}`: no production work may happen on a detached HEAD "
                        "(create or switch to a task branch before merging, for example `git switch -c job/<id>`)")
    if _git("rev-parse", "--verify", "origin/main") is None:
        return warnings
    behind = _git("rev-list", "--count", "HEAD..origin/main")
    if behind is None or not behind.strip().isdigit():
        warnings.append(f"git failed counting commits behind origin/main: {_NOT_VERIFIED}")
        return warnings
    if int(behind) == 0:
        return warnings
    log = _git("log", "--first-parent", "--diff-merges=first-parent", "--name-only", "--no-renames",
               "--format=%x1e%H%x09%h%x09%s%x09%P", "HEAD..origin/main")
    if log:
        log = log.lstrip("\r\n")
    if not log or not log.startswith("\x1e"):
        warnings.append(f"git failed listing commits behind origin/main: {_NOT_VERIFIED}")
        return warnings
    try:
        titles = classify_integration_log(log)
    except FreshnessIncomplete:
        warnings.append(f"git failed reading origin/main integrations: {_NOT_VERIFIED}")
        return warnings
    if not titles:
        return warnings
    noun = "merge" if len(titles) == 1 else "merges"
    warnings.append(f"behind origin/main by {len(titles)} relevant {noun}")
    warnings.extend(titles)
    return warnings


def _rename_prompt(branch):
    """Lines (each under LINE) telling the agent to get the auto-generated branch renamed (user 2026-10-14 [D078])."""
    return [f"BRANCH NAME: `{branch}` is an auto-generated worktree name (docs/agents/NAMING.md).",
            "In your first reply, in one line, propose a branch name for this task by NAMING.md: " + RENAME_HINT
            + ".",
            "Wait for the user's confirmation, then run `git branch -m <name>` before the first commit "
            "(tools/git-hooks/pipeline_gate.py blocks commits on such a branch)."]


def context(source):
    branch = _git("branch", "--show-current") or "(detached)"
    status = _git("status", "--short")
    lines = (status or "").splitlines()
    head = [f"# Session context ({source}; tools/hooks/session_context.py)",
            f"Branch: {branch}  Worktree: {_root()}",
            *(_rename_prompt(branch) if is_auto(branch) else []),
            "Last 5 commits:", *(("  " + c) for c in (_git("log", "-5", "--oneline") or "(git log failed)").splitlines()),
            "git status --short: " + ("FAILED (git unavailable here)" if status is None
                                      else "clean" if not lines else f"{len(lines)} path(s)"),
            *(("  " + s) for s in lines[:25]), *(["  ..."] if len(lines) > 25 else []),
            "Open PRs (gh):", *(("  " + p) for p in open_prs())]
    text, warnings = handoff_state()
    if source == "compact" and warnings:
        warnings.insert(0, "the context was just compacted and the handoff is not current: before any other work "
                           "run the /handover procedure (.claude/commands/handover.md) while the summary is "
                           "fresh, or tell the user why you cannot")
    head += ["Handoff warnings:", *(("  - " + w) for w in warnings)] if warnings else ["Handoff: current"]
    fresh = branch_freshness()
    if fresh:
        head += ["Branch freshness:", *(("  - " + w) for w in fresh)]
    head += [t for t in [transcript_line(text)] if t]
    if source in ("startup", "clear", "compact"):
        head += ["If the user says «продолжай»: first name the branch, the HEAD commit and the next step from the "
                 "handoff (and any warning above), then do that step. /takeover is the full reconciliation."]
    body = "\n".join(_line(h) for h in head)[:LIMIT - 1000]   # metadata never crowds the handoff out (review 1)
    room = LIMIT - len(body) - 200
    if text:
        cut = text if len(text) <= room else text[:max(room, 0)] + f"\n[... cut at {room} characters: read {HANDOFF}]"
        body += f"\n\n--- {HANDOFF} ---\n{cut}"
    return body[:LIMIT]


def _log_compaction(payload):
    git_dir = _git("rev-parse", "--absolute-git-dir")
    if not git_dir:
        return
    _, warnings = handoff_state()
    line = json.dumps({"time": datetime.datetime.now().isoformat(timespec="seconds"),
                       "trigger": payload.get("trigger"), "head": _git("rev-parse", "--short", "HEAD"),
                       "handoff_warnings": warnings}, ensure_ascii=False)
    try:
        with open(Path(git_dir) / "agr-compactions.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def precompact(payload):
    _log_compaction(payload)
    if payload.get("trigger") != "manual":           # blocking an auto compaction can fail the request
        return {}
    if str(payload.get("custom_instructions") or "").strip().lower().split()[:1] == ["force"]:   # the word, first
        return {}
    _, warnings = handoff_state()
    if not warnings:
        return {}
    return {"decision": "block", "reason": "docs/HANDOFF.md is not current (" + "; ".join(warnings) + "). Run "
            "/handover first (then /clear rather than /compact), or `/compact force` to compact anyway."}


def main(mode):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        payload = json.loads(sys.stdin.read() or "{}") if mode != "report" else {}
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    if mode == "start":
        try:
            text = context(payload.get("source") or "startup")
        except Exception as e:                       # the session still learns that it has no context
            text = f"# Session context FAILED ({type(e).__name__}: {e}): read {HANDOFF} and check git yourself"
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}))
    elif mode == "precompact":
        try:
            out = precompact(payload)
        except Exception:                            # a broken gate never blocks compaction
            out = {}
        if out:
            print(json.dumps(out))
    elif mode == "report":
        print(context("report"))
    else:
        print(f"unknown mode {mode!r}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ""))
