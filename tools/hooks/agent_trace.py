"""Agent trace block for /handover and the PR body (#124; docs/agents/WORKFLOW.md, "Context rotation").

  py -3 tools/hooks/agent_trace.py [--transcript PATH ...] [--usage-log PATH] [--base REF]
                                   [--writer TEXT] [--into FILE]

Prints a Markdown `## Agent trace` block with fixed fields: Sessions, Written by, Subagents, Skills,
Commands, Hook denials, Retries, Context at handover, Duration, Commits. `--into FILE` replaces that
section (through the next `## ` heading) or appends it; the rest of the file stays byte-identical.
A value that cannot be measured is `not measured (<reason>)`; an empty count is `none`.
Exit 0, except an argparse error or a failed `--into` write (exit 2, message on stderr).
"""
import argparse
import datetime
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import context_watch  # noqa: E402
import usage_log  # noqa: E402
from twinqa.evals.graders import EvidenceError, hook_denials, read_jsonl  # noqa: E402

FIELDS = ("Sessions", "Written by", "Subagents", "Skills", "Commands", "Hook denials", "Retries",
          "Context at handover", "Duration", "Commits")
FROM_TRANSCRIPT = " (from the transcript)"


def _root():
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])


def _git(*args):
    try:
        result = subprocess.run(["git", *args], cwd=_root(), capture_output=True, text=True, encoding="utf-8",
                                errors="strict", timeout=10)
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _nm(reason):
    text = " ".join(str(reason).split()) or "unknown"
    if len(text) > 160:
        text = text[:157] + "..."
    return f"not measured ({text})"


def _block(values):
    lines = ["## Agent trace", ""]
    for name, value in zip(FIELDS, values):
        lines.append(f"- {name}: {value}")
    return "\n".join(lines) + "\n"


def _writer(writer):
    text = "" if writer is None else str(writer).replace("\r", " ").replace("\n", " ").strip()
    return text or "-"


def _commits(commits):
    if not commits or len(commits) != 3:
        return _nm("git failed")
    base, head, count = commits
    return f"`{base}..{head}` ({int(count)} commits)"


def _norm(command):
    if not isinstance(command, str):
        return None
    return " ".join(command.split())


def _blocks(record):
    message = record.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return []
    return [block for block in content if isinstance(block, dict)]


def _format_counts(counter):
    if not counter:
        return "none"
    ranked = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return ", ".join(f"{name} {count}" for name, count in ranked)


def _named(rows, kind):
    counter = Counter()
    for row in rows:
        if not isinstance(row, dict) or row.get("kind") != kind:
            continue
        name = row.get("name")
        counter[name if isinstance(name, str) and name else "unknown"] += 1
    return _format_counts(counter)


def _counts_from_rows(rows):
    return _named(rows, "agent"), _named(rows, "skill"), _named(rows, "command")


def _counts_from_transcript(groups):
    agents, skills = Counter(), Counter()
    for records in groups:
        for record in records:
            if not isinstance(record, dict) or record.get("type") != "assistant":
                continue
            for block in _blocks(record):
                if block.get("type") != "tool_use":
                    continue
                raw = block.get("input")
                payload = raw if isinstance(raw, dict) else {}
                if block.get("name") in ("Agent", "Task"):
                    kind = payload.get("subagent_type") or "general-purpose"
                    agents[kind if isinstance(kind, str) and kind else "general-purpose"] += 1
                elif block.get("name") == "Skill":
                    skill = payload.get("skill")
                    skills[skill if isinstance(skill, str) and skill else "unknown"] += 1
    return (_format_counts(agents) + FROM_TRANSCRIPT, _format_counts(skills) + FROM_TRANSCRIPT,
            "none" + FROM_TRANSCRIPT)


def retries(records):
    """Normalised Bash commands that repeat an earlier failed Bash call, in order.

    A later call is a retry when an earlier Bash call in the same transcript, with the same
    whitespace-normalised command, already has a `tool_result` with `is_error: true` (matched by
    `tool_use_id`). Sidechain records are ignored.
    """
    seen_error, calls, found = set(), {}, []
    for record in records:
        if not isinstance(record, dict) or record.get("isSidechain"):
            continue
        if record.get("type") == "assistant":
            for block in _blocks(record):
                if block.get("type") != "tool_use" or block.get("name") != "Bash":
                    continue
                raw = block.get("input")
                command = _norm((raw if isinstance(raw, dict) else {}).get("command"))
                if command is None:
                    continue
                if command in seen_error:
                    found.append(command)
                if block.get("id"):
                    calls[block["id"]] = command
        elif record.get("type") == "user":
            for block in _blocks(record):
                if block.get("type") != "tool_result" or block.get("is_error") is not True:
                    continue
                command = calls.get(block.get("tool_use_id"))
                if command:
                    seen_error.add(command)
    return found


def _format_retries(commands):
    if not commands:
        return "none"
    counts = Counter(commands)
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:5]
    shown = "; ".join(f"`{command[:80]}` x{count}" for command, count in ranked)
    return f"{len(commands)}: {shown}"


def _collect_denials(groups):
    found, seen = [], set()
    for records in groups:
        for denial in hook_denials(records):
            key = denial.get("tool_use_id")
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            found.append(denial)
    return found


def _format_denials(denials):
    if not denials:
        return "none"
    parts = []
    for denial in denials[:5]:
        tool = denial.get("tool") or "unknown"
        reason = " ".join(str(denial.get("reason") or "").split())[:80]
        parts.append(f"{tool} - {reason}")
    return f"{len(denials)}: " + "; ".join(parts)


def _session_id(path, records):
    for record in records:
        if not isinstance(record, dict):
            continue
        session = record.get("sessionId")
        if isinstance(session, str) and session:
            return session
    return Path(path).stem


def _stamp(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


def _duration(records):
    stamps = [stamp for stamp in (_stamp(record.get("timestamp")) for record in records if isinstance(record, dict))
              if stamp]
    if not stamps:
        return _nm("no timestamps")
    first, last = min(stamps), max(stamps)
    seconds = max(0, int((last - first).total_seconds()))
    hours, remainder = divmod(seconds, 3600)
    return (f"{hours} h {remainder // 60} min ({first.strftime('%Y-%m-%dT%H:%M:%SZ')} - "
            f"{last.strftime('%Y-%m-%dT%H:%M:%SZ')}, UTC)")


def _context(path):
    try:
        used, model = context_watch.used_tokens(path)
        size = context_watch.window(model)
    except (OSError, UnicodeError, ValueError) as exc:
        return _nm(exc)
    if not size:
        return _nm("unknown window")
    return f"{round(100 * used / size)} % ({round(used / 1000)}k of {round(size / 1000)}k tokens)"


def _read_all(paths):
    groups, sessions, errors = [], [], []
    for path in paths:
        try:
            records, _problems = read_jsonl(path)
        except EvidenceError as exc:
            errors.append(str(exc))
            continue
        groups.append(records)
        sessions.append(_session_id(path, records))
    if errors:
        return [], [], "; ".join(errors)
    return groups, sessions, None


def trace(transcripts, usage_rows, commits, writer):
    """Markdown `## Agent trace` block.

    `transcripts` is a sequence of transcript paths, or none. `usage_rows` is the usage-log rows
    (already limited to the current branch when no transcript is given), or None when there is no
    log; a string is a reason the counts could not be measured. `commits` is `(base, head, count)`
    or None. `writer` is the Written by text.
    """
    written, commit_line = _writer(writer), _commits(commits)
    paths = list(transcripts or [])
    if isinstance(usage_rows, str) and not paths:
        missing = _nm("no transcript")
        counts = _nm(usage_rows)
        return _block((missing, written, counts, counts, counts, missing, missing, missing, missing, commit_line))
    if not paths:
        missing = _nm("no transcript")
        sub, skill, command = ((_nm("no usage log, no transcript"),) * 3 if usage_rows is None
                               else _counts_from_rows(usage_rows))
        return _block((missing, written, sub, skill, command, missing, missing, missing, missing, commit_line))
    groups, sessions, error = _read_all(paths)
    if error:
        missing = _nm(error)
        return _block((missing, written, missing, missing, missing, missing, missing, missing, missing, commit_line))
    matched = [row for row in (usage_rows or []) if isinstance(row, dict) and row.get("session_id") in set(sessions)]
    sub, skill, command = _counts_from_rows(matched) if matched else _counts_from_transcript(groups)
    records = [record for group in groups for record in group]
    retry_commands = [command for group in groups for command in retries(group)]
    return _block((
        ", ".join(f"`{session}`" for session in sessions), written, sub, skill, command,
        _format_denials(_collect_denials(groups)), _format_retries(retry_commands),
        _context(paths[-1]), _duration(records), commit_line))


def replace_section(text, block):
    """Replace the `## Agent trace` section, or append `block` when the text has none.

    The parts outside that section are unchanged, including their newlines.
    """
    if not block.endswith("\n"):
        block += "\n"
    lines = text.splitlines(keepends=True)
    start = next((index for index, line in enumerate(lines) if line.rstrip("\r\n") == "## Agent trace"), None)
    if start is None:
        if text and not text.endswith(("\n", "\r")):
            text += "\n"
        return text + block
    end = next((index for index in range(start + 1, len(lines))
                if lines[index].rstrip("\r\n").startswith("## ")), len(lines))
    head, tail = "".join(lines[:start]), "".join(lines[end:])
    if tail and not block.endswith("\n\n"):
        block += "\n"
    return head + block + tail


def _load_usage(path):
    chosen = Path(path) if path else usage_log.log_path()
    if not chosen.is_file():
        return None
    previous = os.environ.get("AGR_USAGE_LOG")
    os.environ["AGR_USAGE_LOG"] = str(chosen)
    try:
        return usage_log.read()
    except OSError:
        return None
    finally:
        if previous is None:
            os.environ.pop("AGR_USAGE_LOG", None)
        else:
            os.environ["AGR_USAGE_LOG"] = previous


def _commit_range(base):
    merge = _git("merge-base", base, "HEAD")
    if not merge:
        return None
    short_base, short_head = _git("rev-parse", "--short", merge), _git("rev-parse", "--short", "HEAD")
    count = _git("rev-list", "--count", f"{merge}..HEAD")
    if not short_base or not short_head or count is None or not count.isdigit():
        return None
    return short_base, short_head, int(count)


def _build(args):
    transcripts = args.transcript or None
    usage = _load_usage(args.usage_log)
    if not transcripts and usage is not None:
        branch = _git("branch", "--show-current")
        usage = "branch unknown" if branch is None else [row for row in usage if row.get("branch") == branch]
    return trace(transcripts, usage, _commit_range(args.base), args.writer)


def _write_into(path, block):
    dest = Path(path)
    if not dest.is_file():
        raise OSError(f"{dest} is not a file")
    with open(dest, encoding="utf-8", newline="") as handle:
        text = handle.read()
    updated = replace_section(text, block)
    with open(dest, "w", encoding="utf-8", newline="") as handle:
        handle.write(updated)


def main(argv):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--transcript", action="append")
    parser.add_argument("--usage-log")
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--writer", default="-")
    parser.add_argument("--into")
    args = parser.parse_args(argv)
    try:
        block = _build(args)
    except Exception as exc:                         # a trace is never a reason to fail the handover
        print(f"agent_trace failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 0
    if not args.into:
        print(block, end="")
        return 0
    try:
        _write_into(args.into, block)
    except OSError as exc:
        print(f"agent_trace: cannot write {args.into}: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:
        print(f"agent_trace failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(0)
