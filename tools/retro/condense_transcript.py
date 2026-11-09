"""Condense Claude Code session transcripts for a session retro (docs/agents/WORKFLOW.md, "Session retro").

  py -3 tools/retro/condense_transcript.py --current                 this session (CLAUDE_CODE_SESSION_ID)
  py -3 tools/retro/condense_transcript.py PATH [PATH ...]           given .jsonl transcripts
  py -3 tools/retro/condense_transcript.py --since 2026-11-04 [--until 2026-11-05] [--list]
                                                                     every pilot transcript with activity in the range
  options: --out FILE (default stdout), --tools (also one line per tool call), --width N (assistant text, 400)

A transcript is megabytes of tool output; a retro needs only the conversation. Output, per transcript: a header
(path, cwd, branch, first and last timestamp), then one line per event in order:

  [11-05 07:06] USER ! <text>        user message; `!` = correction signal, `+` = acceptance signal
  [11-05 07:06] AI   <text>          assistant text, cut to --width characters
  [11-05 07:06] ERR  <text>          tool result with is_error, first 200 characters
  [11-05 07:06] INTERRUPT            the user stopped the agent
  [11-05 07:06] TOOL <name>          only with --tools

System reminders, hook output, slash-command wrappers and meta entries are dropped. The signal patterns are
heuristics that point the reader at candidate incidents; the retro still reads the context around them.
Subagent transcripts (`subagents/`) are skipped. Exit 0 ok, 2 no transcript found.
"""
import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ACCEPT = re.compile(r"(?<!не )(?<!не\s)\b(принято|принимаю|вс[её] норм|молодец|круто|отлично|справился|супер|"
                    r"годится|подходит)", re.IGNORECASE)
CORRECT = re.compile(r"\b(не так|неправильн|опять|снова|я же (говорил|сказал|просил|писал)|перемудрил|не вижу|"
                     r"не виду|упал|сломал|зачем ты|почему ты|почему не|хватит|стоп\b|запутал|ошиб|не то\b|"
                     r"не надо|не нужно|верни|откати|сколько можно|ещё раз|еще раз)", re.IGNORECASE)
REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL)
WRAPPER = re.compile(r"^\s*<(command-name|command-message|command-args|local-command-stdout|local-command-stderr|"
                     r"task-notification|user-prompt-submit-hook)\b")
INTERRUPT = "[Request interrupted by user"
PROJECT_GLOB = "*AGR-DigitalTwin-pilot*"


def signal(text):
    """'!' correction, '+' acceptance, ' ' none; a correction wins when both match."""
    if CORRECT.search(text):
        return "!"
    if ACCEPT.search(text):
        return "+"
    return " "


def _projects_dir():
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects"


def _ts(entry):
    raw = entry.get("timestamp")
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")) if raw else None
    except (AttributeError, ValueError):
        return None


def _flat(text, width=None):
    text = " ".join(str(text).split())
    return text if width is None or len(text) <= width else text[: width - 1] + "…"


def _blocks(content):
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b for b in content or [] if isinstance(b, dict)]


def _result_text(block):
    content = block.get("content")
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    return str(content or "")


def events(entries, width=400, tools=False):
    """(timestamp, kind, text) for every event a retro reads, in transcript order."""
    for entry in entries:
        kind, ts = entry.get("type"), _ts(entry)
        queued = entry.get("attachment") if isinstance(entry.get("attachment"), dict) else {}
        if queued.get("type") == "queued_command" and not entry.get("isSidechain"):   # sent while the agent worked
            text = REMINDER.sub("", str(queued.get("prompt") or "")).strip()
            if text and not WRAPPER.match(text):
                yield ts, "USER " + signal(text), _flat(text)
            continue
        if kind not in ("user", "assistant") or entry.get("isMeta") or entry.get("isSidechain"):
            continue
        for block in _blocks((entry.get("message") or {}).get("content")):
            btype = block.get("type")
            if kind == "user" and btype == "text":
                text = REMINDER.sub("", block.get("text", "")).strip()
                if not text or WRAPPER.match(text):
                    continue
                if text.startswith(INTERRUPT):
                    yield ts, "INTERRUPT", ""
                    continue
                yield ts, "USER " + signal(text), _flat(text)
            elif kind == "user" and btype == "tool_result" and block.get("is_error"):
                yield ts, "ERR ", _flat(_result_text(block), 200)
            elif kind == "assistant" and btype == "text" and block.get("text", "").strip():
                yield ts, "AI  ", _flat(block["text"], width)
            elif kind == "assistant" and btype == "tool_use" and tools:
                yield ts, "TOOL", block.get("name", "?")


def read_entries(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if isinstance(entry, dict):
                yield entry


def condense(path, width=400, tools=False, since=None, until=None):
    """The condensed text of one transcript, or '' when no event falls into [since, until)."""
    meta, lines, first, last = {}, [], None, None
    for entry in read_entries(path):
        for key in ("cwd", "gitBranch"):
            if entry.get(key) and key not in meta:
                meta[key] = entry[key]
        for ts, kind, text in events([entry], width, tools):
            if ts and ((since and ts < since) or (until and ts >= until)):
                continue
            first, last = first or ts, ts or last
            stamp = ts.astimezone().strftime("%m-%d %H:%M") if ts else "--:-- --:--"
            lines.append(f"[{stamp}] {kind} {text}".rstrip())
    if not lines:
        return ""
    span = " … ".join(t.astimezone().strftime("%Y-%m-%d %H:%M") for t in (first, last) if t)
    head = [f"## {path}", f"cwd: {meta.get('cwd', '-')}  branch: {meta.get('gitBranch', '-')}  span: {span}"]
    return "\n".join(head + lines) + "\n"


def in_range(since, glob=PROJECT_GLOB):
    """Main-session transcripts of the pilot repo modified since `since` (activity filtered later)."""
    found = []
    for folder in sorted(_projects_dir().glob(glob)):
        for f in sorted(folder.glob("*.jsonl")) if folder.is_dir() else []:
            mtime = datetime.fromtimestamp(f.stat().st_mtime, timezone.utc)
            if mtime >= since:
                found.append(f)
    return found


def current():
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID") or os.environ.get("CLAUDE_SESSION_ID")
    if not sid:
        return []
    return sorted(_projects_dir().glob(f"*/{sid}.jsonl"))


def _day(text):
    return datetime.combine(date.fromisoformat(text), datetime.min.time()).astimezone()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="*", type=Path)
    ap.add_argument("--current", action="store_true")
    ap.add_argument("--since")
    ap.add_argument("--until", help="last day included")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--tools", action="store_true")
    ap.add_argument("--width", type=int, default=400)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)

    since = _day(args.since) if args.since else None
    until = _day(args.until) + timedelta(days=1) if args.until else None
    paths = list(args.paths) + (current() if args.current else []) + (in_range(since) if since and not args.paths
                                                                         and not args.current else [])
    if not paths:
        print("no transcript found", file=sys.stderr)
        return 2
    parts = []
    for path in paths:
        text = condense(path, args.width, args.tools, since, until)
        if not text:
            continue
        if args.list:
            n_user = sum(1 for line in text.splitlines() if "] USER" in line)
            parts.append(f"{text.splitlines()[0][3:]}\n  {text.splitlines()[1]}  user messages: {n_user}\n")
        else:
            parts.append(text)
    out = "\n".join(parts) or "no events in range\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(out, encoding="utf-8")
        print(args.out)
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
