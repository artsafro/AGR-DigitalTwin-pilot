"""Code graders: evidence paths in, one check row out (`check`, `expected`, `measured`, `passed`, `details`).

A grader raises `EvidenceError` when its evidence is absent or unreadable, and returns `passed: None` with an
`error` when it is incomplete; the runner reports both as not measured (exit 2), never as a pass.

Claude Code transcript shapes relied on (inspected 2026-10-15 over the local transcripts; re-check when the CLI
changes its format, spec "Further Notes"):
- a tool call refused by a PreToolUse hook is a `user` record whose `message.content` holds the `tool_result`
  (`is_error: true`, text `PreToolUse:<tool> hook error: <reason>`) and whose top-level `permissionDecision` is
  `{"decision": "reject", "source": "hook", ...}`;
- a hook that merely failed (`attachment.type == "hook_non_blocking_error"`) or allowed the call
  (`permissionDecision.decision == "accept"`) is not a denial;
- an `assistant` record holds `tool_use` and `text` blocks, a `user` record the `tool_result` of a call
  (joined by `tool_use_id`; `toolUseResult.success` tells a Skill call apart from a failed one), a human prompt,
  or the `<command-name>` text of a /command;
- `isSidechain: true` marks a subagent record: the procedural graders read the main session only;
- `gitBranch` carries the branch of the worktree the record was written in;
- a subagent call is a `tool_use` named `Agent` or `Task` with `input.subagent_type` and `input.prompt`;
- a question put to the user is the turn-ending text of an assistant record or an `AskUserQuestion` call
  (`input.questions[].question`).
"""
import json
import re
from collections import Counter
from pathlib import Path

HOOK_ERROR = re.compile(r"^PreToolUse:(\S+) hook error:\s*")
DENIED = {"reject", "deny"}
CONVERSATION = ("user", "assistant")
COMMAND_TAG = re.compile(r"<command-name>/?([^<\s]+)</command-name>")      # tools/hooks/usage_log.py
SUBAGENT_TOOLS = ("Agent", "Task")


class EvidenceError(Exception):
    """The evidence is missing or unreadable: the check is not measured."""


def _recognized(value):
    """A Claude Code transcript entry: an object with a non-empty string `type`; a `user` / `assistant` entry also
    carries its `message` object. Every record of the local transcripts had this shape (2026-10-15)."""
    if not isinstance(value, dict) or not isinstance(value.get("type"), str) or not value["type"]:
        return False
    if value["type"] not in CONVERSATION:
        return True
    message = value.get("message")              # review 2 of #142: an empty message is no conversation record
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return True
    if not isinstance(content, list):
        return False
    # Review 3 of #142: every block is typed, and a tool_result carries its payload (the denial text may be there).
    return all(isinstance(b, dict) and isinstance(b.get("type"), str)
               and (b["type"] != "tool_result" or isinstance(b.get("content"), (str, list))) for b in content)


def read_jsonl(path):
    """Recognized records of a transcript and the problems that make it incomplete as evidence: lines that are not
    JSON or not a transcript entry (a torn last line included), or no user / assistant record at all.
    Raises EvidenceError when the file is absent or unreadable."""
    path = Path(path)
    if not path.is_file():
        raise EvidenceError(f"{path} does not exist")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise EvidenceError(f"{path}: {type(exc).__name__}: {exc}") from exc
    records, bad = [], 0
    for line in text.split("\n"):  # only \n ends a JSON Lines record; U+2028, 0x1c, 0x85 may sit inside strings
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            value = None
        if _recognized(value):
            records.append(value)
        else:
            bad += 1
    problems = [f"{path}: {bad} line(s) not a transcript record"] if bad else []
    if not any(r["type"] in CONVERSATION for r in records):
        problems.append(f"{path}: no user or assistant record")
    return records, problems


def _text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):          # [{"type": "text", "text": ...}, ...]
        return "".join(c.get("text", "") for c in content if isinstance(c, dict))
    return ""


def hook_denials(records):
    """Every tool call a hook refused, from the record structure only: text quoted in a file or a message never
    counts. One entry per tool_use_id."""
    found = {}
    for n, rec in enumerate(records):
        if rec.get("type") != "user":
            continue
        content = (rec.get("message") or {}).get("content")
        results = [c for c in content if isinstance(c, dict) and c.get("type") == "tool_result"] \
            if isinstance(content, list) else []
        decision = rec.get("permissionDecision")
        by_hook = isinstance(decision, dict) and decision.get("source") == "hook" \
            and decision.get("decision") in DENIED
        if by_hook and not results:                  # review 2 of #142: the decision alone is authoritative
            found.setdefault(f"record-{n}", {"record": n, "tool_use_id": None, "tool": None,
                                             "reason": str(decision.get("reason") or "")[:200],
                                             "sidechain": bool(rec.get("isSidechain"))})
        for res in results:
            text = _text(res.get("content"))
            match = HOOK_ERROR.match(text) if res.get("is_error") is True else None
            # The decision field rules when present; only a record without one (older CLI) falls back to the text.
            if not (by_hook or (match and decision is None)):
                continue
            key = res.get("tool_use_id") or f"record-{n}"
            found.setdefault(key, {
                "record": n,
                "tool_use_id": res.get("tool_use_id"),
                "tool": match.group(1) if match else None,
                "reason": (text[match.end():] if match else text)[:200],
                "sidechain": bool(rec.get("isSidechain")),
            })
    return list(found.values())


def no_hook_denial(evidence):
    """Regression grader: no PreToolUse hook denial in the task's transcripts (`evidence["transcript"]`).

    Strict about partial evidence (review 1 of #142): a line that is not a transcript record - a torn last line of
    a live session too - makes the check not measured, because the lost line may be the denial. A denial found in
    the readable records is a definite failure and wins."""
    details, problems, seen = [], [], set()
    for path in evidence["transcript"]:
        try:                                         # review 2 of #142: one unreadable file never hides a denial
            records, issues = read_jsonl(path)
        except EvidenceError as exc:
            problems.append(str(exc))
            continue
        problems += issues
        for d in hook_denials(records):
            # Copies of one session (a handover before and after the PR) hold the same denial: count it once.
            if d.get("tool_use_id") in seen:
                continue
            if d.get("tool_use_id"):
                seen.add(d["tool_use_id"])
            details.append({"file": str(path), **d})
    row = {"check": "hook denials in the transcript", "expected": 0, "measured": len(details),
           "passed": not details, "details": details}
    if problems and not details:
        row.update(measured="not measured", passed=None, error="incomplete evidence: " + "; ".join(problems))
    elif problems:
        row["evidence_problems"] = problems
    return row


# --- The main session as events: every procedural grader below reads this list, not the records ----------------

def _blocks(rec):
    content = (rec.get("message") or {}).get("content")
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _command_of(rec):
    """The /command of a genuine command record, as `command_of` in tools/hooks/usage_log.py: a user record whose
    content is the command text itself. A `<command-name>` tag quoted in a tool result or a file is not one."""
    content = (rec.get("message") or {}).get("content")
    if not isinstance(content, str) or not content.lstrip().startswith("<command-"):
        return None
    m = COMMAND_TAG.search(content)
    return m.group(1) if m else None


def _results(records):
    """`tool_use_id` -> the outcome of that call: `is_error` of the tool_result block, `success` of the record's
    `toolUseResult` (a Skill call reports it there), the result text, `has_result` (review 1 of #123), and
    `result_record`, the index of the record holding that tool_result (review 2 of #123: completion order)."""
    out = {}
    for n, rec in enumerate(records):
        if rec.get("type") != "user" or rec.get("isSidechain"):
            continue
        outcome = rec.get("toolUseResult")
        for b in _blocks(rec):
            if b.get("type") == "tool_result" and isinstance(b.get("tool_use_id"), str):
                out[b["tool_use_id"]] = {"is_error": b.get("is_error") is True,
                                         "success": outcome.get("success") if isinstance(outcome, dict) else None,
                                         "result_text": _text(b.get("content")), "has_result": True,
                                         "result_record": n}
    return out


def events(records):
    """One transcript's main session as an ordered list of events, each with its `record` index:

    - `tool_use`: `name`, `input`, `id`, and from the result joined by `tool_use_id` `is_error`, `success`
      (None when the transcript holds no result), `result_text`, `has_result` (review 1 of #123: True only
      when a tool_result was joined, otherwise False), and `result_record` (review 2 of #123: the index of
      the record holding the tool_result, otherwise None);
    - `text`: one text block of an assistant record;
    - `prompt`: a user record that is not only tool results - a human turn - with the `command` it ran.

    `isSidechain: true` records are subagent records and are left out: every procedural grader reads the main
    session only. Records of other types (`summary`, `attachment`, ...) hold no event.
    """
    results, out = _results(records), []
    for n, rec in enumerate(records):
        if rec.get("type") not in CONVERSATION or rec.get("isSidechain"):
            continue
        if rec["type"] == "assistant":
            for b in _blocks(rec):
                if b.get("type") == "tool_use":
                    out.append({"kind": "tool_use", "record": n, "id": b.get("id"), "name": b.get("name") or "",
                                "input": b["input"] if isinstance(b.get("input"), dict) else {},
                                "is_error": None, "success": None, "result_text": "", "has_result": False,
                                "result_record": None, **results.get(b.get("id"), {})})
                elif b.get("type") == "text":
                    out.append({"kind": "text", "record": n, "text": b.get("text") or ""})
            continue
        blocks = _blocks(rec)
        if blocks and all(b.get("type") == "tool_result" for b in blocks):
            continue                                   # the result of a call, not a turn of the user
        out.append({"kind": "prompt", "record": n, "command": _command_of(rec),
                    "text": _text((rec.get("message") or {}).get("content"))})
    return out


def _sessions(paths):
    """(path, records) per readable transcript, plus the problems that make the evidence incomplete. One file is
    one session: a grader that judges "within a session" works per pair."""
    sessions, problems = [], []
    for path in paths:
        try:
            records, issues = read_jsonl(path)
        except EvidenceError as exc:                  # one unreadable file never hides a violation elsewhere
            problems.append(str(exc))
            continue
        problems += issues
        sessions.append((path, records))
    return sessions, problems


def _row(check, details, problems):
    """The common grader row: `expected` 0 violations, `measured` their number. Incomplete evidence without a
    violation is not measured; a violation found in the readable part stays a failure and keeps the problems."""
    row = {"check": check, "expected": 0, "measured": len(details), "passed": not details, "details": details}
    if problems and not details:
        row.update(measured="not measured", passed=None, error="incomplete evidence: " + "; ".join(problems))
    elif problems:
        row["evidence_problems"] = problems
    return row


# --- 1. dcc_skill_loaded -----------------------------------------------------------------------------------------

# MCP server name in the tool name -> the skill to load first; the table of tools/hooks/skill_gate.py SKILLS
# (docs/agents/WORKFLOW.md, "Triggers"), copied so that a grader never imports a hook. A test asserts they match.
DCC_SKILLS = [(re.compile(r"^mcp__[^_]*3dsmax", re.I), "3dsmax-mcp-dev"),
              (re.compile(r"^mcp__[^_]*blender", re.I), "blender-mcp"),
              (re.compile(r"^mcp__[^_]*revit", re.I), "revit-mcp")]


def dcc_skill(tool):
    """The skill a DCC MCP tool needs (None for any other tool), as `required` in skill_gate.py."""
    return next((skill for pattern, skill in DCC_SKILLS if pattern.search(tool or "")), None)


def _names_skill(name, skill):
    return bool(name) and (name == skill or name.endswith(":" + skill))


def dcc_skill_loaded(evidence):
    """Regression grader: every DCC MCP call of the main session had its skill loaded earlier in that session
    (docs/agents/WORKFLOW.md, "Triggers"; the gate is tools/hooks/skill_gate.py).

    A load is a `Skill` call whose result succeeded (`has_result`, not an error, `success` is not False; review 1
    of #123) with its `result_record` strictly before the DCC call (review 2 of #123: completion order), or the
    user's `/<skill>` command at its own record. A Skill call with no result does not load: a later DCC call for
    that skill is not measured. A successful result that arrives after the DCC call is a violation. Subagents
    preload their skills and are not gated, so sidechain records are ignored."""
    sessions, problems = _sessions(evidence["transcript"])
    details = []
    for path, records in sessions:
        loads, pending = [], {}                    # (skill, record the load completed)
        for ev in events(records):
            if ev["kind"] == "prompt":
                named = {s for _, s in DCC_SKILLS if _names_skill(ev["command"], s)}
                loads.extend((skill, ev["record"]) for skill in named)
                for skill in named:
                    pending.pop(skill, None)
                continue
            if ev["kind"] != "tool_use":
                continue
            if ev["name"] == "Skill":
                named = {s for _, s in DCC_SKILLS if _names_skill(ev["input"].get("skill"), s)}
                # review 1 of #123: no tool_result means the load is not proven
                if ev["has_result"] and ev["is_error"] is not True and ev["success"] is not False:
                    loads.extend((skill, ev["result_record"]) for skill in named)
                    for skill in named:
                        pending.pop(skill, None)
                elif not ev["has_result"]:
                    for skill in named:
                        pending.setdefault(skill, ev["record"])
                continue
            skill = dcc_skill(ev["name"])
            if not skill or any(name == skill and seen is not None and seen < ev["record"]
                                for name, seen in loads):
                continue
            # a result that lands after the call does not prove the load; no result at all is not measured
            if skill in pending and not any(name == skill for name, _ in loads):
                problems.append(f"{path}: record {pending[skill]}: Skill {skill} has no result: load not proven")
            else:
                details.append({"file": str(path), "record": ev["record"], "tool": ev["name"], "skill": skill})
    return _row("DCC calls before their skill", details, problems)


# --- 2. engine_checked -------------------------------------------------------------------------------------------

ENGINE_RUN = re.compile(r"run_benchmark\.py|run_from_source\.py|\bdt\s+from-source\b|dt_ai\.geometry\.from_(?:spec|source)")
DONE = re.compile(r"\b(?:done|complete[d]?|ready|all green|passed)\b|готов|собран|\b\d+\s*/\s*\d+\s+(?:checks?|pass)", re.I)


def engine_checked(evidence):
    """Regression grader: after every engine run the main agent called the `independent-checker` subagent before
    it claimed the model was done (docs/agents/WORKFLOW.md, "Subagents" and step 6: a report, an exit 0 or a
    child agent's summary is not evidence).

    A failed run (`is_error`) built nothing and needs no checker."""
    sessions, problems = _sessions(evidence["transcript"])
    details = []
    for path, records in sessions:
        evs = events(records)
        runs = [i for i, ev in enumerate(evs)
                if ev["kind"] == "tool_use" and ev["name"] == "Bash" and ev["is_error"] is not True
                and ENGINE_RUN.search(str(ev["input"].get("command") or ""))]
        for i in runs:
            checked, claim = False, None
            for ev in evs[i + 1:]:
                if ev["kind"] == "tool_use" and ev["name"] in SUBAGENT_TOOLS \
                        and ev["input"].get("subagent_type") == "independent-checker":
                    checked = True
                    break
                if ev["kind"] == "text" and DONE.search(ev["text"]):
                    claim = ev["text"].strip()[:120]
                    break
            if checked:
                continue
            detail = {"file": str(path), "record": evs[i]["record"],
                      "command": str(evs[i]["input"].get("command") or "")[:160],
                      "reason": "done claimed before independent-checker" if claim
                                else "no independent-checker after the run"}
            if claim:
                detail["claim"] = claim
            details.append(detail)
    return _row("engine runs without an independent-checker", details, problems)


# --- 3. source_inspected -----------------------------------------------------------------------------------------

SOURCE = re.compile(r"[^\s\"'*?<>|/\\:]+\.(?:max|rvt|fbx|blend|skp|dwg|ifc)\b", re.I)
# Folder segments of what the pipeline produced; a file under them is not an incoming source.
OUTPUT_FOLDERS = {"outputs", "runs", "benchmark", "logs", "fixtures", "temp", "tmp"}


def _source_path(token):
    """One path token, normalized (review 1 of #123): lowercase, `\\` to `/`, repeated slashes collapsed,
    a leading `./` dropped."""
    text = re.sub(r"/+", "/", token.replace("\\", "/")).lower()
    while text.startswith("./"):
        text = text[2:]
    return text


def _source_names(text):
    """The source paths a string names, normalized. The whole whitespace- or quote-delimited token is the path
    (review 1 of #123), not only its basename: a token under an output folder, and an engine output (`model.*`),
    is not a source."""
    found = []
    for token in re.split(r"[\s\"']+", text or ""):
        if not token or {p.lower() for p in re.split(r"[\\/]+", token)} & OUTPUT_FOLDERS:
            continue
        if any(not m.group(0).lower().startswith("model.") for m in SOURCE.finditer(token)):
            found.append(_source_path(token))
    return found


def _segments(path):
    return [part for part in path.split("/") if part]


def _same_source(referenced, inspected):
    """Trailing path segments match (review 1 of #123). A referenced path that has a directory is covered only
    when the inspected path has the basename and a parent; a basename-only reference matches any inspection of
    that basename. A basename-only inspection does not cover a longer path."""
    ref, ins = _segments(referenced), _segments(inspected)
    if not ref or not ins:
        return False
    shorter, longer = (ref, ins) if len(ref) <= len(ins) else (ins, ref)
    if longer[-len(shorter):] != shorter:
        return False
    return not (len(ref) > 1 and len(ins) < 2)


def source_inspected(evidence):
    """Regression grader: every architectural source the task touched was read by the `source-inspector` subagent
    (docs/agents/WORKFLOW.md, "Triggers": a new or updated source makes it mandatory).

    The inspection may happen in any session of the task, so every transcript of the evidence counts as one
    inspection history; a source referenced in no inspector prompt is a violation. Identity is the normalized
    path (review 1 of #123): the same basename in two directories is two sources."""
    sessions, problems = _sessions(evidence["transcript"])
    referenced, inspected = {}, []
    for path, records in sessions:
        for ev in events(records):
            if ev["kind"] != "tool_use":
                continue
            if ev["name"] in SUBAGENT_TOOLS and ev["input"].get("subagent_type") == "source-inspector":
                inspected += _source_names(str(ev["input"].get("prompt") or ""))
                continue
            if ev["name"] == "Bash":
                values = [ev["input"].get("command")]
            elif ev["name"] == "Read":
                values = [ev["input"].get("file_path")]
            elif dcc_skill(ev["name"]):
                values = list(ev["input"].values())
            else:
                continue
            for value in values:
                for name in _source_names(value) if isinstance(value, str) else []:
                    referenced.setdefault(name, {"file": str(path), "record": ev["record"],
                                                 "source": name.split("/")[-1], "path": name})
    details = [d for name, d in referenced.items() if not any(_same_source(name, seen) for seen in inspected)]
    return _row("sources used without source-inspector", details, problems)


# --- 4. failure_stop ---------------------------------------------------------------------------------------------

CD_PREFIX = re.compile(r"^\s*cd\s+(?:\"[^\"]*\"|'[^']*'|\S+)\s*(?:&&|;)\s*")
RUN_VALUE = re.compile(r"(--output|--basetemp|--run|-o)(?:\s+|=)(?:\"[^\"]*\"|'[^']*'|\S+)")
DIGITS = re.compile(r"\d+")
STOP_TEXT = re.compile(r"stop record|запись остановки", re.I)
STATE_FILE = re.compile(r"pipeline[\\/]state\.json$", re.I)
EDIT_TOOLS = ("Edit", "Write", "MultiEdit")


def _attempt_key(command):
    """One check, however it was invoked: without a leading `cd <dir> &&`, without the values of the run folder
    flags, with every digit run as N and whitespace collapsed."""
    text = RUN_VALUE.sub(r"\1", CD_PREFIX.sub("", command or ""))
    return re.sub(r"\s+", " ", DIGITS.sub("N", text)).strip()


def _cause(text):
    """The cause of a failure as the result shows it: its last non-empty line, digit runs as N, lowercased."""
    lines = [line for line in (text or "").split("\n") if line.strip()]
    return DIGITS.sub("N", lines[-1]).strip().lower()[:200] if lines else ""


def _blocked(causes):
    """The rule that closes this path (docs/agents/WORKFLOW.md step 6), or None while it is open."""
    if any(n >= 2 for n in Counter(causes).values()):
        return "two failures with the same cause"
    return "three failures of one check" if len(causes) >= 3 else None


def _stop_record(ev):
    """A saved stop: `pipeline/state.json` written with its `stops` (HARNESS_PLAN §12)."""
    if ev["name"] not in EDIT_TOOLS or not STATE_FILE.search(str(ev["input"].get("file_path") or "")):
        return False
    edits = ev["input"].get("edits") if isinstance(ev["input"].get("edits"), list) else []
    written = [ev["input"].get("new_string"), ev["input"].get("content"),
               *(e.get("new_string") for e in edits if isinstance(e, dict))]
    return any("stops" in s for s in written if isinstance(s, str))


def failure_stop(evidence):
    """Regression grader: the main agent stopped a path instead of repeating it (docs/agents/WORKFLOW.md step 6,
    `docs/agents/COMMANDS.md`: "Три попытки -> стоп").

    Per session, per check (the normalized command): two failures with the same cause, or three failures, block
    the check; the next attempt of a blocked check is a violation. A saved stop record (`pipeline/state.json`
    with its `stops`, or a "Stop record" text) reopens every check, a success reopens its own. A stop write
    reopens only when it has a result and did not fail (review 1 of #123), and only from its `result_record`
    (review 2 of #123: completion order); a write with no result leaves that attempt not measured.
    Bash failures, successes and stop saves change state at their result records, while retry violations
    are checked at invocation (review 3 of #123)."""
    sessions, problems = _sessions(evidence["transcript"])
    details = []
    for path, records in sessions:
        failures = {}                                  # attempt key -> (cause, seq) still open
        unknown, seq = None, 0                         # latest stop write whose result never arrived
        result_positions = {(n, block.get("tool_use_id")): i
                            for n, rec in enumerate(records) for i, block in enumerate(_blocks(rec))
                            if block.get("type") == "tool_result"}
        timeline = [(ev["record"], False, i, ev) for i, ev in enumerate(events(records))]
        timeline += [(ev["result_record"], True, result_positions[(ev["result_record"], ev["id"])], ev)
                     for _, _, _, ev in timeline
                     if ev["kind"] == "tool_use" and ev["has_result"]
                     and ev["result_record"] is not None
                     and (ev["name"] == "Bash" or _stop_record(ev))]
        # Preserve result block order too; a completion never authorizes a call in that same record.
        for _, completed, _, ev in sorted(timeline, key=lambda item: item[:3]):
            if completed:
                if _stop_record(ev):
                    if ev["is_error"] is not True:
                        failures.clear()
                        unknown = None
                else:
                    key = _attempt_key(str(ev["input"].get("command") or ""))
                    if ev["is_error"] is True:
                        failures.setdefault(key, []).append((_cause(ev["result_text"]), seq))
                        seq += 1
                    else:
                        failures.pop(key, None)
                continue
            if ev["kind"] == "text" and STOP_TEXT.search(ev["text"]):
                failures.clear()
                unknown = None
                continue
            if ev["kind"] != "tool_use":
                continue
            if _stop_record(ev):
                # A failed write changes nothing; a missing result is not a saved stop.
                if not ev["has_result"]:
                    unknown = (ev["record"], seq)
                continue
            if ev["name"] != "Bash":
                continue
            command = str(ev["input"].get("command") or "")
            key = _attempt_key(command)
            causes = failures.get(key, [])
            open_causes = [cause for cause, seen in causes if unknown is None or seen >= unknown[1]]
            rule = _blocked([cause for cause, _ in causes])
            if rule and _blocked(open_causes):
                details.append({"file": str(path), "record": ev["record"], "command": command[:160],
                                "failures": len(causes), "rule": rule})
            elif rule and unknown is not None:
                problems.append(f"{path}: record {unknown[0]}: stop record saved with no result: outcome unknown")
    return _row("attempts after a blocked check", details, problems)


# --- 5. branch_name ----------------------------------------------------------------------------------------------

# tools/git-hooks/branch_names.py AUTO_BRANCH and TYPES, copied (a test asserts they match); the named form is
# docs/agents/NAMING.md, "Branches" (user 2026-10-14 [D078]).
AUTO_BRANCH = re.compile(r"^(?:claude/|codex/)?[a-z0-9]+(?:-[a-z0-9]+)*-[0-9a-f]{6}$")
BRANCH_TYPES = ("feature", "fix", "experiment", "research", "harness", "job")
NAMED = re.compile(r"^(?:(?:feature|fix|experiment|research|harness)/[a-z0-9]+(?:-[a-z0-9]+)+"
                   r"|job/[a-z0-9]+-[a-z0-9]+-[a-z0-9]+(?:-[a-z0-9]+)*)$")
COMMIT = re.compile(r"\bgit\b[^|;&\n]*\bcommit\b|\bgit\b[^|;&\n]*\bpush\b|\bgh\s+pr\s+create\b")


def branch_name(evidence):
    """Regression grader: the work was committed on a branch named by docs/agents/NAMING.md - `<type>/<area>-<what>`
    or `job/<object-id>-<stage>`, never the auto-generated worktree name ([D078]); `main` passes, as a state
    update after a merge happens there.

    Graded branches: the `gitBranch` of every record that holds a commit, push or `gh pr create`, plus the last
    `gitBranch` of the file (the branch the session ended on). A file with neither is not measured."""
    sessions, problems = _sessions(evidence["transcript"])
    details = []
    for path, records in sessions:
        committing = {ev["record"] for ev in events(records)
                      if ev["kind"] == "tool_use" and ev["name"] == "Bash"
                      and COMMIT.search(str(ev["input"].get("command") or ""))}
        branches, last = {}, None
        for n, rec in enumerate(records):
            branch = rec.get("gitBranch")
            if not isinstance(branch, str) or not branch:
                continue
            last = (branch, n)
            if n in committing:
                branches.setdefault(branch, n)
        if last:
            branches.setdefault(*last)
        if not branches:
            problems.append(f"{path}: no commit record and no gitBranch")
            continue
        for branch, n in branches.items():
            if branch == "main" or (NAMED.match(branch) and not AUTO_BRANCH.match(branch)):
                continue
            reason = "auto-generated worktree branch" if AUTO_BRANCH.match(branch) \
                else "not <type>/<area>-<what> (docs/agents/NAMING.md)"
            details.append({"file": str(path), "record": n, "branch": branch, "reason": reason})
    return _row("branch names off NAMING.md", details, problems)


# --- 6. routine_question -----------------------------------------------------------------------------------------

# docs/agents/COMMANDS.md, "Что агент спрашивает, а что решает сам": the agent asks about the model and the
# object's data, and decides the implementation itself. Keywords are lowercase English and Russian stems,
# matched at a word start (review 1 of #123). ASCII keywords of 3 letters or fewer (`adr`, `mid`, `npm`, `vpm`)
# also end at a word end; longer keywords and every Cyrillic keyword stay prefix stems. The first list that
# matches wins.
ALLOWED_QUESTIONS = {
    "architecture": ("architecture", "архитектур", "adr"),
    "acceptance": ("accept", "approve", "принимаешь", "принять", "утверд", "приёмк", "приемк"),
    "destructive": ("delete", "remove", "overwrite", "reset", "drop", "удал", "перезапис", "снести"),
    "publication": ("push", "merge", "publish", "release", "pull request", "пуш", "смерж", "мерж", "опубликов"),
    "branch_rename": ("rename", "переимен", "branch -m"),
    "model": ("модел", "model", "врезк", "inset", "глубин", "depth", "level of detail", "профил", "npm", "vpm", "mid"),
    "data": ("отметк", "высот", "elevation", "object id", "данные объекта", "object data", "source file",
             "исходник", "размер", "dimension"),
}
IMPLEMENTATION_WORDS = ("algorithm", "алгоритм", "cache", "кэш", "кеш", "pr structure", "структур pr",
                        "split the pr", "разбить pr", "hint threshold", "порог подсказ", "report format",
                        "формат отчёт", "формат отчет")


def _keyword_re(word):
    """A keyword at a word start. ASCII keywords of 3 letters or fewer also end at a word end (review 1 of #123);
    longer keywords and Cyrillic stems stay prefixes (`accept` matches `accepted`, `модел` matches `модели`)."""
    end = r"(?![a-zа-яё0-9])" if len(word) <= 3 and word.isascii() else ""
    return re.compile(rf"(?<![a-zа-яё0-9]){re.escape(word)}{end}")


ALLOWED_RE = {category: tuple(_keyword_re(word) for word in words) for category, words in ALLOWED_QUESTIONS.items()}
IMPLEMENTATION_RE = tuple(_keyword_re(word) for word in IMPLEMENTATION_WORDS)
WORD = re.compile(r"[a-zа-яё0-9]{4,}")
STOPWORDS = {"this", "that", "with", "from", "what", "which", "should", "будет", "нужно", "этот", "какой",
             "какие", "можно", "или"}
OVERLAP = 0.5                                          # share of the question's words a rule row must share
SENTENCE = re.compile(r"[^.!?\n]*\?")


def _tokens(text):
    return set(WORD.findall((text or "").lower())) - STOPWORDS


def _last_question(text):
    """The question inside a turn-ending text: the last sentence of its last line that ends with `?`."""
    line = [part for part in text.strip().split("\n") if part.strip()][-1]
    found = SENTENCE.findall(line)
    return (found[-1] if found else line).strip()


def _questions(records):
    """(record index, question) for every question the main session put to the user: the turn-ending text of an
    assistant record when it ends with `?`, and each question of an `AskUserQuestion` call."""
    evs, out = events(records), []
    for i, ev in enumerate(evs):
        if ev["kind"] == "tool_use" and ev["name"] == "AskUserQuestion":
            asked = ev["input"].get("questions")
            for item in asked if isinstance(asked, list) else []:
                text = item.get("question") if isinstance(item, dict) else None
                if isinstance(text, str) and text.strip():
                    out.append((ev["record"], text.strip()))
            continue
        if ev["kind"] != "text":
            continue
        nxt = evs[i + 1] if i + 1 < len(evs) else None
        if nxt and (nxt["record"] == ev["record"] or nxt["kind"] != "prompt"):
            continue                                   # the turn goes on: the text asked the user nothing
        if ev["text"].strip().endswith("?"):
            out.append((ev["record"], _last_question(ev["text"])))
    return out


def _cells(line):
    """The cells of a Markdown table row (a separator row has none)."""
    line = line.strip()
    if not line.startswith("|"):
        return []
    cells = [c.strip() for c in line.strip("|").split("|")]
    return [] if all(set(c) <= set("-: ") for c in cells) else cells


def _read_doc(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise EvidenceError(f"{path}: {type(exc).__name__}: {exc}") from exc


def _rule_rows(evidence):
    """(category, row id, text) of every rule a question may already be answered by: the decision rows of
    `decisions` (`| D<n> | date | decision | ...`) and the pattern rows of `patterns` (name, slug, what it does)."""
    rows = []
    for path in evidence["decisions"]:
        for line in _read_doc(path).split("\n"):
            cells = _cells(line)
            if len(cells) >= 3 and re.fullmatch(r"D\d+", cells[0]):
                rows.append(("decision_log", cells[0], cells[2]))
    for path in evidence["patterns"]:
        for line in _read_doc(path).split("\n"):
            cells = _cells(line)
            if len(cells) >= 3 and cells[1].startswith("`"):
                rows.append(("pattern", cells[1].strip("`"), f"{cells[0]} {cells[2]}"))
    return rows


def _classify(question, rows):
    """(category, matched row) of one question: an allowed category by keyword, a violation by keyword
    (`implementation`) or by word overlap with a rule row (`decision_log` / `pattern`), else (None, None)."""
    low = question.lower()
    for category, patterns in ALLOWED_RE.items():
        if any(pattern.search(low) for pattern in patterns):
            return category, None
    if any(pattern.search(low) for pattern in IMPLEMENTATION_RE):
        return "implementation", None
    q = _tokens(question)
    best = (0.0, None, None)
    for category, row_id, text in rows:
        shared = len(q & _tokens(text))
        score = shared / len(q) if q else 0.0
        if shared >= 3 and score > best[0]:
            best = (score, category, row_id)
    return (best[1], best[2]) if best[0] >= OVERLAP else (None, None)


def routine_question(evidence):
    """Regression grader: the agent asked the user about the model and the object's data only, never about its
    own implementation or about something the decision log and the pattern registry already answer
    (docs/agents/COMMANDS.md, "Что агент спрашивает, а что решает сам").

    Deterministic: keyword lists (`ALLOWED_QUESTIONS`, `IMPLEMENTATION_WORDS`) and word overlap with the rule
    rows (`OVERLAP`), no model call. A question no list recognizes is not measured, never a silent pass."""
    rows = _rule_rows(evidence)                        # EvidenceError: a rule file is missing or unreadable
    sessions, problems = _sessions(evidence["transcript"])
    details, allowed, unclassified = [], [], []
    for path, records in sessions:
        for record, question in _questions(records):
            category, match = _classify(question, rows)
            if category is None:
                unclassified.append(question[:200])
            elif category in ALLOWED_QUESTIONS:
                allowed.append({"question": question[:200], "category": category})
            else:
                details.append({"file": str(path), "record": record, "question": question[:200],
                                "category": category, **({"match": match} if match else {})})
    row = _row("routine questions to the user", details, problems)
    row["allowed"], row["unclassified"] = allowed, unclassified
    if row["passed"] is True and unclassified:
        row.update(measured="not measured", passed=None,
                   error="unclassified question(s): " + "; ".join(unclassified))
    return row


# grader name -> (function, the evidence names it reads); task.json is checked against the names.
GRADERS = {"no_hook_denial": (no_hook_denial, ("transcript",)),
           "dcc_skill_loaded": (dcc_skill_loaded, ("transcript",)),
           "engine_checked": (engine_checked, ("transcript",)),
           "source_inspected": (source_inspected, ("transcript",)),
           "failure_stop": (failure_stop, ("transcript",)),
           "branch_name": (branch_name, ("transcript",)),
           "routine_question": (routine_question, ("transcript", "decisions", "patterns"))}

from twinqa.evals.pr_graders import PR_GRADERS  # noqa: E402  (#125; pr_graders imports EvidenceError from here)
GRADERS.update(PR_GRADERS)
