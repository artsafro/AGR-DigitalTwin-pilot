"""Pull-request graders (#125). Evidence is a recorded `gh` result, never a live call.

`pr_agent_trace` — the PR body has an `## Agent trace` span (the same span as
`tools/hooks/agent_trace.py`) with all ten fields filled. A value `not measured (...)` counts;
a placeholder that starts with `<` does not.

`pr_numeric_literals` — an added numeric literal in `src/dt_ai/` (the engine) or `src/twinqa/`
(the delivery checker) must be 0, 1 or 2, a move of a value removed in the same file, or referenced.
`src/twinqa/evals/` is the harness, not the delivery checker, and is not scanned. A reference is a
decision-log id (`D<n>`, as in `[D073]`) or the word `tolerances` on the added line, on a PR-body
line or another added line that also contains the same numeric value, or an added line of a file
whose path contains `tolerances`. The scanner walks each hunk's new side (context and added lines)
so a string can continue; a hunk starts outside a string, and f-string expressions are skipped with
the string. Comments and string literals are not code.

`pr_review_rounds` — the highest review-round marker on the first non-empty line of a PR comment
is at most 3 (`docs/agents/REVIEW_CHECKLIST.md` [D073]). A quote further down is not a marker.
"""
import json
import re
from collections import Counter
from pathlib import Path

TRACE_FIELDS = ("Sessions", "Written by", "Subagents", "Skills", "Commands", "Hook denials", "Retries",
                "Context at handover", "Duration", "Commits")
CEILING = 3  # docs/agents/REVIEW_CHECKLIST.md [D073]: the ceiling stays 3 rounds

_DECISION = re.compile(r"\bD\d{1,4}\b")
_TOLERANCES = re.compile(r"\btolerances\b")
_FIELD = re.compile(r"^- ([^:]+): (.*)$")
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
_ROUND_REVIEW = re.compile(r"^(?:codex\s+)?review,?\s+round\s+(\d+)\b", re.IGNORECASE)
_ROUND_VERDICT = re.compile(r"^round\s+(\d+)\s+verdict\b", re.IGNORECASE)
_NUMBER = re.compile(
    r"(?<![\w.])(?:"
    r"0[xX][0-9A-Fa-f](?:_?[0-9A-Fa-f])*"
    r"|0[oO][0-7](?:_?[0-7])*"
    r"|0[bB][01](?:_?[01])*"
    r"|(?:\d(?:_?\d)*\.\d(?:_?\d)*|\.\d(?:_?\d)*)(?:[eE][+-]?\d(?:_?\d)*)?[jJ]?"
    r"|\d(?:_?\d)*\.(?:[eE][+-]?\d(?:_?\d)*)?[jJ]?"
    r"|\d(?:_?\d)*(?:[eE][+-]?\d(?:_?\d)*)[jJ]?"
    r"|\d(?:_?\d)*[jJ]"
    r"|\d(?:_?\d)*"
    r")(?![\w.])"
)
_PREFIX = set("rRuUbBfF")
_MARKDOWN = set("#*_> \t")


def _raise(message):
    from twinqa.evals.graders import EvidenceError
    raise EvidenceError(message)


def read_view(path):
    """One `gh pr view --json body,comments` file. Raises EvidenceError when it is not a JSON object."""
    path = Path(path)
    if not path.is_file():
        _raise(f"{path} does not exist")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        _raise(f"{path}: {type(exc).__name__}: {exc}")
    if not isinstance(value, dict):
        _raise(f"{path}: not a gh pr view")
    return value


def _bare_path(spec):
    """`b/foo`, `"b/foo bar"` or `/dev/null` from a `---` / `+++` / `diff --git` path."""
    spec = spec.strip()
    if len(spec) >= 2 and spec[0] == '"' and spec[-1] == '"':
        spec = spec[1:-1].replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"').replace("\\\\", "\\")
    if spec == "/dev/null":
        return None
    if spec.startswith("a/") or spec.startswith("b/"):
        return spec[2:]
    return spec


def _header_paths(line):
    rest = line[len("diff --git "):]
    if rest.startswith('"'):
        parts, cur, quoted = [], [], False
        for index, char in enumerate(rest):
            if char == '"' and (index == 0 or rest[index - 1] != "\\"):
                quoted = not quoted
                cur.append(char)
                if not quoted:
                    parts.append("".join(cur))
                    cur = []
            elif char == " " and not quoted:
                if cur:
                    parts.append("".join(cur))
                    cur = []
            else:
                cur.append(char)
        if cur:
            parts.append("".join(cur))
        if len(parts) >= 2:
            return _bare_path(parts[0]), _bare_path(parts[1])
    split = rest.find(" b/")
    if split < 0:
        return None, None
    return _bare_path(rest[:split]), _bare_path(rest[split + 1:])


def read_diff(path):
    """One `gh pr diff` file: per file the new path, added `(line, text)`, removed texts and hunks.

    A hunk is `(kind, text)` with kind `+`, `-` or ` `. An empty file is no diff. A non-empty file
    without a `diff --git` header is not a gh pr diff. `\\ No newline at end of file` is not a line.
    """
    path = Path(path)
    if not path.is_file():
        _raise(f"{path} does not exist")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        _raise(f"{path}: {type(exc).__name__}: {exc}")
    if not text.strip():
        return []
    lines = text.splitlines()
    if not any(line.startswith("diff --git ") for line in lines):
        _raise(f"{path}: not a gh pr diff")
    files, current, hunk, new_line = [], None, None, 1

    def close_hunk():
        nonlocal hunk
        if current is not None and hunk is not None:
            current["hunks"].append(hunk)
        hunk = None

    for line in lines:
        if line.startswith("diff --git "):
            close_hunk()
            old, new = _header_paths(line)
            current = {"path": new or old or "", "added": [], "removed": [], "hunks": [], "_old": old}
            files.append(current)
            continue
        if current is None:
            continue
        if line.startswith("--- "):
            current["_old"] = _bare_path(line[4:])
            continue
        if line.startswith("+++ "):
            new = _bare_path(line[4:])
            current["path"] = new or current.get("_old") or current["path"]
            continue
        if line.startswith("@@"):
            close_hunk()
            match = _HUNK.match(line)
            new_line = int(match.group(1)) if match else 1
            hunk = []
            continue
        if hunk is None:
            continue
        if line.startswith("\\"):
            continue
        if line == "":
            kind, body = " ", ""
        elif line[0] not in "+- ":
            close_hunk()
            continue
        else:
            kind, body = line[0], line[1:]
        hunk.append((kind, body))
        if kind == "+":
            current["added"].append((new_line, body))
            new_line += 1
        elif kind == " ":
            new_line += 1
        else:
            current["removed"].append(body)
    close_hunk()
    for item in files:
        item.pop("_old", None)
    return files


def _span_line(line):
    """Same span as tools/hooks/agent_trace.py: blank, a field line, a lone `-`, or a `<` placeholder."""
    body = line.rstrip("\r\n")
    if body.strip() == "" or body.strip() == "-":
        return True
    return body.startswith("- ") or body.startswith("<")


def _trace_of(view):
    body = view.get("body") if isinstance(view, dict) else None
    if not isinstance(body, str):
        return None
    lines = body.splitlines()
    start = next((i for i, line in enumerate(lines) if line.replace("\r", "").rstrip(" ") == "## Agent trace"), None)
    if start is None:
        return "absent", list(TRACE_FIELDS)
    found = {}
    index = start + 1
    while index < len(lines) and _span_line(lines[index]):
        match = _FIELD.match(lines[index].replace("\r", "").rstrip(" "))
        index += 1
        if not match or match.group(1) not in TRACE_FIELDS:
            continue
        name, value = match.group(1), match.group(2).strip()
        if value and not value.startswith("<"):
            found[name] = "ok"
        elif found.get(name) != "ok":
            found[name] = "placeholder" if value.startswith("<") else "missing"
    missing = [name for name in TRACE_FIELDS if found.get(name) != "ok"]
    if missing:
        return "incomplete", missing
    return "ok", []


def pr_agent_trace(evidence):
    """The PR body carries `## Agent trace` with every field filled (`evidence["pr"]`, every file)."""
    check, expected = "Agent trace block in the PR body", "present, 10 fields"
    from twinqa.evals.graders import EvidenceError  # graders.py imports this module at its end
    problems, states = [], []
    for path in evidence.get("pr") or []:
        try:
            view = read_view(path)
        except EvidenceError as exc:
            problems.append(str(exc))
            continue
        state = _trace_of(view)
        if state is None:
            problems.append(f"{path}: no body (fetch with gh pr view --json body,comments)")
            continue
        states.append(state)
    failures = [state for state in states if state[0] != "ok"]
    if not failures and (problems or not states):
        return {"check": check, "expected": expected, "measured": "not measured", "passed": None, "details": [],
                "error": "incomplete evidence: " + "; ".join(problems or ["no pr view"])}
    if not failures:
        return {"check": check, "expected": expected, "measured": "present, 10 fields", "passed": True, "details": []}
    missing = []
    for _status, fields in failures:
        for name in fields:
            if name not in missing:
                missing.append(name)
    if any(status == "incomplete" for status, _fields in failures):
        measured = "incomplete: missing [" + ", ".join(missing) + "]"
    else:
        measured = "absent"
    row = {"check": check, "expected": expected, "measured": measured, "passed": False, "details": missing}
    if problems:
        row["evidence_problems"] = problems
    return row


def _exempt(value):
    """0, 1 and 2 are structure, not thresholds: identities, halves (`/ 2`), xy slices (`[:, :2]`), digits."""
    return value in (0, 1, 2)


def _number_value(token):
    try:
        if token[-1] in "jJ":
            return float(abs(complex(token.replace("_", ""))))
        if len(token) > 2 and token[0] == "0" and token[1] in "xXoObB":
            return float(int(token, 0))
        return float(token)
    except ValueError:
        return None


def _escaped(text, index):
    slashes = 0
    while index > 0 and text[index - 1] == "\\":
        slashes += 1
        index -= 1
    return slashes % 2 == 1


def _open_string(text, i):
    """If a string literal starts at i, return (index after it, unclosed triple or None). Else None."""
    if text[i] not in _PREFIX and text[i] not in "'\"":
        return None
    end = i
    limit = len(text)
    while end < limit and text[end] in _PREFIX:
        end += 1
    if end >= limit or text[end] not in "'\"":
        return None
    if i > 0 and (text[i - 1].isalnum() or text[i - 1] == "_"):
        return None
    raw = "r" in text[i:end].lower()
    quote = text[end]
    triple = text[end:end + 3] == quote * 3
    cursor = end + (3 if triple else 1)
    if triple:
        close = text.find(quote * 3, cursor)
        while close >= 0 and not raw and _escaped(text, close):
            close = text.find(quote * 3, close + 1)
        if close < 0:
            return limit, (quote, raw)
        return close + 3, None
    while cursor < limit:
        if text[cursor] == "\\" and not raw:
            cursor += 2
            continue
        if text[cursor] == quote:
            return cursor + 1, None
        cursor += 1
    return limit, None


def _scan(items):
    """`(include, text, extra...)` in order. Yields code numbers on included lines. Starts outside a string."""
    triple = None
    for item in items:
        include, text, extra = item[0], item[1], item[2:]
        index, limit = 0, len(text)
        while index < limit:
            if triple:
                quote, raw = triple
                close = text.find(quote * 3, index)
                while close >= 0 and not raw and _escaped(text, close):
                    close = text.find(quote * 3, close + 1)
                if close < 0:
                    break
                index = close + 3
                triple = None
                continue
            if text[index] == "#":
                break
            opened = _open_string(text, index)
            if opened is not None:
                index, triple = opened
                continue
            match = _NUMBER.match(text, index)
            if match:
                if include:
                    value = _number_value(match.group(0))
                    if value is not None:
                        yield (text, match.group(0), value, *extra)
                index = match.end()
                continue
            index += 1


def _line_has_reference(text):
    return _DECISION.search(text) is not None or _TOLERANCES.search(text) is not None


def _plain_values(text):
    values = []
    for match in _NUMBER.finditer(text):
        value = _number_value(match.group(0))
        if value is not None:
            values.append(value)
    return values


def _in_scope(path):
    name = path.replace("\\", "/")
    if not name.endswith(".py"):
        return False
    if name.startswith("src/twinqa/evals/"):
        return False
    return name.startswith("src/dt_ai/") or name.startswith("src/twinqa/")


def _literals(files):
    """Added in-scope literals that are not exempt and not a move of a removed value in the same file."""
    scanned, pending = [], []
    for entry in files:
        path = entry["path"]
        if not _in_scope(path):
            continue
        if path not in scanned:
            scanned.append(path)
        removed = Counter()
        for hunk in entry["hunks"]:
            for _text, _token, value in _scan((True, text) for kind, text in hunk if kind == "-"):
                if not _exempt(value):
                    removed[value] += 1
        added_lines = iter(entry["added"])  # one iterator: `+` lines follow the hunks
        for hunk in entry["hunks"]:
            side = []
            for kind, text in hunk:
                if kind == "-":
                    continue
                if kind == "+":
                    line_no, _body = next(added_lines)
                    side.append((True, text, line_no))
                else:
                    side.append((False, text, None))
            for text, token, value, line_no in _scan(side):
                if _exempt(value):
                    continue
                if removed[value]:
                    removed[value] -= 1
                    continue
                pending.append({"file": path, "line": line_no, "literal": token, "value": value, "text": text})
    return scanned, pending


def pr_numeric_literals(evidence):
    """New numeric literals in the engine / checker without a decision-log or tolerances reference.

    `evidence["pr"]` is the view (the body is part of the reference rule) and `evidence["diff"]` the diff.
    A failure found in a readable diff wins over a missing body.
    """
    check = "new numeric literals in the engine / checker without a reference"
    from twinqa.evals.graders import EvidenceError
    problems, parsed, bodies = [], [], []
    for path in evidence.get("diff") or []:
        try:
            parsed.append(read_diff(path))
        except EvidenceError as exc:
            problems.append(str(exc))
    for path in evidence.get("pr") or []:
        try:
            view = read_view(path)
        except EvidenceError as exc:
            problems.append(str(exc))
            continue
        body = view.get("body") if isinstance(view, dict) else None
        if not isinstance(body, str):
            problems.append(f"{path}: no body (fetch with gh pr view --json body,comments)")
        else:
            bodies.append(body)
    files = [entry for diff in parsed for entry in diff]
    scanned, pending = _literals(files) if parsed else ([], [])
    referenced = set()
    for body in bodies:
        for line in body.splitlines():
            if _line_has_reference(line):
                referenced.update(_plain_values(line))
    for entry in files:
        for _line_no, text in entry["added"]:
            if _line_has_reference(text):
                referenced.update(_plain_values(text))
        if "tolerances" in entry["path"].replace("\\", "/"):
            for _line_no, text in entry["added"]:
                referenced.update(_plain_values(text))
    details = []
    for item in pending:
        if _line_has_reference(item["text"]) or item["value"] in referenced:
            continue
        details.append({"file": item["file"], "line": item["line"], "literal": item["literal"],
                        "text": item["text"].strip()[:200]})
    row = {"check": check, "expected": 0, "measured": len(details), "passed": not details,
           "details": details, "scanned_files": scanned}
    if problems and not details:
        row.update(measured="not measured", passed=None, error="incomplete evidence: " + "; ".join(problems))
    elif problems:
        row["evidence_problems"] = problems
    elif not parsed:
        row.update(measured="not measured", passed=None, error="incomplete evidence: no diff")
    return row


def _strip_markdown(line):
    text = line.replace("\r", "")
    while text[:1] in _MARKDOWN:
        text = text[1:]
    return text


def _comment_marker(comment):
    """A round marker on the first non-empty line, an unrecognized review heading, or nothing."""
    if not isinstance(comment, dict) or not isinstance(comment.get("body"), str):
        return None
    first = next((line for line in comment["body"].splitlines() if line.replace("\r", "").strip()), "")
    stripped = _strip_markdown(first)
    match = _ROUND_REVIEW.match(stripped) or _ROUND_VERDICT.match(stripped)
    if match:
        return {"kind": "round", "round": int(match.group(1)), "url": comment.get("url") or "", "line": first}
    folded = stripped.casefold()
    if folded.startswith("codex review") or folded.startswith("review"):
        return {"kind": "unrecognized", "url": comment.get("url") or "", "line": first}
    return None


def pr_review_rounds(evidence):
    """Review rounds marked on PR comments, ceiling 3 (`evidence["pr"]`, every file)."""
    check, expected = "review rounds", "<= 3"
    from twinqa.evals.graders import EvidenceError
    problems, markers, unrecognized = [], [], []
    readable = False
    for path in evidence.get("pr") or []:
        try:
            view = read_view(path)
        except EvidenceError as exc:
            problems.append(str(exc))
            continue
        comments = view.get("comments") if isinstance(view, dict) else None
        if not isinstance(comments, list):
            problems.append(f"{path}: no comments (fetch with gh pr view --json body,comments)")
            continue
        readable = True
        for comment in comments:
            found = _comment_marker(comment)
            if found is None:
                continue
            if found["kind"] == "round":
                markers.append({key: found[key] for key in ("round", "url", "line")})
            else:
                unrecognized.append(found)
    highest = max((item["round"] for item in markers), default=0)
    over = highest > CEILING
    row = {"check": check, "expected": expected, "measured": highest, "passed": highest <= CEILING,
           "details": markers}
    if over:
        if problems:
            row["evidence_problems"] = problems
        return row
    if problems or unrecognized or not readable:
        bits = list(problems)
        bits += [f"unrecognized review heading: {item['url']} {item['line']}" for item in unrecognized]
        row.update(measured="not measured", passed=None, error="incomplete evidence: " + "; ".join(bits))
    return row


PR_GRADERS = {
    "pr_agent_trace": (pr_agent_trace, ("pr",)),
    "pr_numeric_literals": (pr_numeric_literals, ("pr", "diff")),
    "pr_review_rounds": (pr_review_rounds, ("pr",)),
}
