"""Usage log of subagents, skills and slash commands: logs/agent-usage.jsonl (docs/agents/WORKFLOW.md, "Triggers").

  py -3 tools/hooks/usage_log.py post            PostToolUse on Agent / Task / Skill: one line per call
  py -3 tools/hooks/usage_log.py prompt          UserPromptSubmit: one line when the prompt is a /command
  py -3 tools/hooks/usage_log.py stats [--days N]   counts per subagent, project skill and command (zeros too)
  py -3 tools/hooks/usage_log.py backfill [--days N]   past usage from ~/.claude/projects transcripts of this
                                                  repository and its registered worktrees (#109); safe to run again

A line: time (UTC), session_id, branch, kind (agent | skill | command), name, command (the last /command of the
session before the call, or null). The log lives in the main checkout (`git rev-parse --git-common-dir`/..), so
every worktree writes one file; it is local and git-ignored. Logging never blocks or fails a call.
"""
import datetime
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

COMMAND_TAG = re.compile(r"<command-name>/?([^<\s]+)</command-name>")


def _root():
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])


def _git(*args):
    try:
        r = subprocess.run(["git", *args], cwd=_root(), capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def log_path():
    if os.environ.get("AGR_USAGE_LOG"):              # tests and dry runs
        return Path(os.environ["AGR_USAGE_LOG"])
    common = _git("rev-parse", "--path-format=absolute", "--git-common-dir")
    base = Path(common).parent if common else _root()
    return base / "logs" / "agent-usage.jsonl"


def command_of(entry):
    """The /command of a genuine command record (a user entry whose content is the command text itself), else None.
    A tag quoted inside a tool result or a file is not a command (review 2 of #107)."""
    content = (entry.get("message") or {}).get("content") if isinstance(entry, dict) else None
    if entry.get("type") != "user" or not isinstance(content, str) or not content.lstrip().startswith("<command-"):
        return None
    m = COMMAND_TAG.search(content)
    return m.group(1) if m else None


def last_command(transcript):
    """The last /command the user ran in this session, from the transcript (None without one)."""
    found = None
    try:
        for line in Path(transcript).read_text(encoding="utf-8", errors="replace").splitlines():
            if "<command-name>" in line:
                try:
                    found = command_of(json.loads(line)) or found
                except ValueError:
                    continue
    except (OSError, TypeError):
        return None
    return found


def entry(payload):
    tool, args = payload.get("tool_name"), payload.get("tool_input") or {}
    if payload.get("hook_event_name") == "UserPromptSubmit":
        m = re.match(r"\s*/([\w:.-]+)", payload.get("prompt") or "")
        if not m:
            return None
        kind, name = "command", m.group(1)
    elif tool in ("Agent", "Task"):
        kind, name = "agent", args.get("subagent_type") or "general-purpose"
    elif tool == "Skill":
        kind, name = "skill", args.get("skill")
    else:
        return None
    return {"time": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "session_id": payload.get("session_id"), "branch": _git("branch", "--show-current"), "kind": kind,
            "name": name, "command": None if kind == "command" else last_command(payload.get("transcript_path"))}


def write(payload):
    line = entry(payload)
    if not line:
        return
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def read(days=None):
    path = log_path()
    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days) if days else None
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
            if since is None or datetime.datetime.fromisoformat(row["time"]) >= since:
                rows.append(row)
        except (ValueError, KeyError, TypeError):
            continue
    return rows


def known():
    """{kind: names} the project defines: subagents, project skills (not vendored), commands."""
    root = _root()
    lock = root / "skills-lock.json"
    vendored = set(json.loads(lock.read_text(encoding="utf-8"))["skills"]) if lock.exists() else set()
    return {"agent": sorted(p.stem for p in (root / ".claude/agents").glob("*.md")),
            "skill": sorted(p.name for p in (root / ".agents/skills").iterdir() if p.is_dir() and p.name not in vendored),
            "command": sorted(p.stem for p in (root / ".claude/commands").glob("*.md"))}


def stats(days):
    rows = read(days)
    counts = Counter((r.get("kind"), r.get("name")) for r in rows)
    out = [f"Usage, last {days} days ({log_path()}; {len(rows)} entries):"]
    if not log_path().exists():
        out.append("  (no log yet: the hooks write it from the first call on)")
    for kind, names in known().items():
        cells = [f"{n} {counts.get((kind, n), 0)}" for n in names]
        out.append(f"  {kind}s: " + ", ".join(cells))
        zero = [n for n in names if not counts.get((kind, n))]
        if zero:
            out.append(f"    never called: {', '.join(zero)}")
    other = sorted({(k, n) for k, n in counts if n not in known().get(k, [])})
    if other:
        out.append("  other: " + ", ".join(f"{n} ({k}) {counts[(k, n)]}" for k, n in other))
    return "\n".join(out)


def _slug(path):
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def worktrees():
    """Paths of this repository's checkouts: the main checkout and every registered Git worktree, wherever it lives
    (`git worktree list --porcelain`); without Git, the project dir alone."""
    common = _git("rev-parse", "--path-format=absolute", "--git-common-dir")
    paths = [Path(common).parent if common else _root()]
    listed = _git("worktree", "list", "--porcelain") or ""
    paths += [Path(x[len("worktree "):]) for x in listed.splitlines() if x.startswith("worktree ")]
    return list(dict.fromkeys(paths))


def projects_dirs():
    """Claude Code transcript folders of this repository. Claude Code names a folder by the session cwd with every
    non-alphanumeric character replaced by '-'. A folder belongs here when it is the slug of a checkout from
    worktrees() (external worktrees included) or `<slug>--...`, a cwd inside one (`<main>/.claude/worktrees/x`, kept
    after the worktree is removed). `<slug>-other` is another repository and is not read."""
    base = Path(os.environ.get("AGR_CLAUDE_PROJECTS") or Path.home() / ".claude" / "projects")
    if not base.is_dir():
        return []
    slugs = {_slug(p) for p in worktrees()}
    return sorted(d for d in base.iterdir()
                  if d.is_dir() and any(d.name == s or d.name.startswith(s + "--") for s in slugs))


def _time(stamp):
    """A transcript or log time as an aware UTC datetime; fractions of a second are kept."""
    t = datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return (t if t.tzinfo else t.replace(tzinfo=datetime.timezone.utc)).astimezone(datetime.timezone.utc)


def transcript_entries(path, since):
    """Usage events of one past transcript, in order: a genuine /command, an Agent/Task call of the main session,
    a successful Skill load (toolUseResult.success + commandName). Each is (row, start, end): the row has the hook's
    fields plus source=backfill and the transcript time with its fractions; start..end spans the call (an Agent call
    ends at its tool_result, where the live PostToolUse hook would have logged it)."""
    events, current, calls = [], None, {}
    for raw in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(raw)
            when = _time(e["timestamp"])
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
        if not isinstance(e, dict) or e.get("isSidechain"):
            continue
        content = (e.get("message") or {}).get("content")
        if isinstance(content, list):                 # the end of an Agent call logged below
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in calls:
                    events[calls.pop(b["tool_use_id"])][2] = when
        found = []
        cmd = command_of(e)
        if cmd:
            current = cmd
            found.append(("command", cmd, None))
        if e.get("type") == "assistant" and isinstance(content, list):
            found += [("agent", (b.get("input") or {}).get("subagent_type") or "general-purpose", b.get("id"))
                      for b in content
                      if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in ("Agent", "Task")]
        result = e.get("toolUseResult")
        if isinstance(result, dict) and result.get("success") is True and result.get("commandName"):
            found.append(("skill", result["commandName"], None))
        if when < since:
            continue
        for kind, name, call_id in found:
            if call_id:
                calls[call_id] = len(events)
            events.append([{"time": when.isoformat(), "session_id": e.get("sessionId") or Path(path).stem,
                            "branch": e.get("gitBranch") or None, "kind": kind, "name": name,
                            "command": None if kind == "command" else current, "source": "backfill"}, when, when])
    return [tuple(x) for x in events]


LIVE_SLACK = datetime.timedelta(seconds=60)          # live hook time vs the transcript span of the same call


def backfill(days):
    """Append past usage from this repository's transcripts. Idempotent and without double counts, per event:
    a backfill line with the same session_id+time+name is skipped; so is an event the live hooks already logged,
    i.e. a live line of the same session, kind and name inside the call's span (+-LIVE_SLACK), each live line
    matched once. Other events of a session the hooks logged in part are added."""
    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    seen, live = set(), {}
    for r in read():
        try:
            t = _time(r["time"])
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
        if r.get("source") == "backfill":
            seen.add((r.get("session_id"), t, r.get("name")))
        else:
            live.setdefault((r.get("session_id"), r.get("kind"), r.get("name")), []).append(t)
    for times in live.values():
        times.sort()
    files = [f for d in projects_dirs() for f in d.glob("*.jsonl") if f.stat().st_mtime >= since.timestamp()]
    events = sorted((ev for f in files for ev in transcript_entries(f, since)), key=lambda ev: ev[1])
    new, skipped = [], 0
    for row, start, end in events:
        key = (row["session_id"], start, row["name"])
        times = live.get((row["session_id"], row["kind"], row["name"]), [])
        hit = next((t for t in times if start - LIVE_SLACK <= t <= end + LIVE_SLACK), None)
        if key in seen:
            skipped += 1
            continue
        if hit is not None:
            times.remove(hit)
            skipped += 1
            continue
        seen.add(key)
        new.append(row)
    if new:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in new)
    return f"backfill, last {days} days: {len(new)} new, {skipped} already logged, {len(files)} transcripts ({log_path()})"


def main(argv):
    mode = argv[0] if argv else ""
    if mode in ("stats", "backfill"):
        days = int(argv[argv.index("--days") + 1]) if "--days" in argv else 7
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(stats(days) if mode == "stats" else backfill(days))
        return 0
    if mode not in ("post", "prompt"):
        print(f"unknown mode {mode!r}", file=sys.stderr)
        return 2
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if isinstance(payload, dict):
            write(payload)
    except Exception:                                # logging is never a reason to fail a call
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
