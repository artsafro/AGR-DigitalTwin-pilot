"""Check the ready-for-agent gate (#130): an issue body is ready only when its contract is filled.

The contract is `.github/ISSUE_TEMPLATE/task.md`: Requirement, Specification (Acceptance, Inputs and
versions, Out of scope, Evidence the PR must bring) and Context. Every field must hold text after the
template's HTML comments are removed; Acceptance needs at least one non-empty checkbox item. "None" is a
valid answer and counts as filled. The four fields count only as subheadings of the Specification section;
headings and checkboxes inside fenced code (``` or ~~~) are example text, never contract structure.
A field's answer is its own text: a nested heading that names another contract field or section ends it,
so an empty field never borrows a neighbour's answer. A checkbox indented four or more columns (tab = 4)
counts only as a nested list item; outside a list it is an indented code block, not a criterion.

    py -3 tools/check_ready_gate.py --issue 130 [--repo OWNER/NAME]
    py -3 tools/check_ready_gate.py --label ready-for-agent [--repo OWNER/NAME]
    py -3 tools/check_ready_gate.py --file body.md        (or "-" for stdin)

Exit 0: every checked issue passes; 1: at least one fails; 2: no input or a gh failure.
"""
import argparse
import json
import re
import subprocess
import sys

SECTIONS = ("Requirement", "Specification", "Context")
SPEC_FIELDS = ("Acceptance", "Inputs and versions", "Out of scope", "Evidence the PR must bring")
FIELDS = ("Requirement", *SPEC_FIELDS, "Context")

HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
COMMENT = re.compile(r"<!--.*?-->", re.S)
CHECKBOX = re.compile(r"^[-*+][ \t]+\[[ xX]\][ \t]*(.*)$")
LIST_ITEM = re.compile(r"^(?:[-*+]|\d{1,9}[.)])(?:[ \t]|$)")
CONTRACT = {name.lower() for name in FIELDS} | {"specification"}


def lines_with_fences(text):
    """Yield (line, fenced) pairs; fenced is True for fence delimiters and every line between them.

    CommonMark fences: three or more backticks or tildes, up to three spaces of indent; the closing
    fence uses the same character, is at least as long and carries no info string. An unclosed fence
    runs to the end of the text.
    """
    fence = None
    for line in text.splitlines():
        match = FENCE.match(line)
        if fence is None:
            if match and not (match.group(1)[0] == "`" and "`" in match.group(2)):
                fence = match.group(1)
                yield line, True
            else:
                yield line, False
        else:
            if (match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence)
                    and not match.group(2).strip()):
                fence = None
            yield line, True


def parse(text):
    """Headings outside fenced code as dicts: level, name (lower case), and body lines up to the next
    heading of any level, each body line as (line, fenced). HTML comments are removed first."""
    blocks = []
    for line, is_fenced in lines_with_fences(COMMENT.sub("", (text or "").replace("\r\n", "\n"))):
        match = None if is_fenced else HEADING.match(line)
        if match:
            blocks.append({"level": len(match.group(1)), "name": match.group(2).strip().lower(),
                           "lines": []})
        elif blocks:
            blocks[-1]["lines"].append((line, is_fenced))
    return blocks


def headings(text):
    """Every ATX heading outside fenced code as (level, text)."""
    return [(len(m.group(1)), m.group(2).strip())
            for line, is_fenced in lines_with_fences(text)
            if not is_fenced and (m := HEADING.match(line))]


def span(blocks, index):
    """The block at index and every deeper block after it, up to the next heading of the same or a
    higher level: the whole section."""
    level, end = blocks[index]["level"], index + 1
    while end < len(blocks) and blocks[end]["level"] > level:
        end += 1
    return blocks[index:end]


def own_span(blocks, index):
    """Like span, but a nested heading that names a contract field or section ends the answer:
    a required field never supplies another one's content (malformed nesting stays empty)."""
    section = span(blocks, index)
    for end, block in enumerate(section[1:], 1):
        if block["name"] in CONTRACT:
            return section[:end]
    return section


def checklist_items(section):
    """Checkbox texts outside code. Indent of four or more columns (tab = 4) is a nested list item only
    while a list is open; otherwise CommonMark reads it as an indented code block."""
    items = []
    for block in section:
        in_list = False
        for line, is_fenced in block["lines"]:
            if is_fenced:
                in_list = False
                continue
            expanded = line.expandtabs(4)
            stripped = expanded.lstrip(" ")
            if not stripped:
                continue
            indent = len(expanded) - len(stripped)
            if indent < 4:
                in_list = bool(LIST_ITEM.match(stripped)) or (in_list and indent > 0)
            elif not in_list:
                continue
            match = CHECKBOX.match(stripped)
            if match:
                items.append(match.group(1).strip())
    return items


def section_text(section):
    return "\n".join(line for block in section for line, _ in block["lines"]).strip()


def gate_problems(body):
    """Problems that keep a body from ready-for-agent; an empty list means it passes.

    Requirement and Context are the first headings of that name outside the Specification section;
    the four Specification fields count only as subheadings inside the Specification section.
    Headings and checkboxes inside fenced code are text, never contract structure.
    """
    blocks = parse(body)
    problems = []
    spec_at = next((i for i, b in enumerate(blocks) if b["name"] == "specification"), None)
    spec = span(blocks, spec_at) if spec_at is not None else []
    inside = {id(b) for b in spec}
    for name in SECTIONS:
        if name == "Specification":
            if spec_at is None:
                problems.append("Specification: section missing")
            continue
        at = next((i for i, b in enumerate(blocks)
                   if b["name"] == name.lower() and id(b) not in inside), None)
        if at is None:
            problems.append(f"{name}: section missing")
        elif not section_text(own_span(blocks, at)):
            problems.append(f"{name}: empty")
    if spec_at is None:
        return problems
    for name in SPEC_FIELDS:
        at = next((i for i, b in enumerate(spec)
                   if i > 0 and b["name"] == name.lower()), None)
        if at is None:
            problems.append(f"{name}: field missing under Specification")
            continue
        field = own_span(spec, at)
        if name == "Acceptance":
            if not any(checklist_items(field)):
                problems.append("Acceptance: no checkable item (`- [ ] ...`)")
        elif not section_text(field):
            problems.append(f"{name}: empty")
    return problems


def gh_json(args):
    done = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8")
    if done.returncode:
        raise RuntimeError(done.stderr.strip() or f"gh {' '.join(args)} failed")
    return json.loads(done.stdout)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--issue", type=int, help="issue number")
    source.add_argument("--label", help="check every open issue with this label")
    source.add_argument("--file", help="a body file, '-' for stdin")
    parser.add_argument("--repo", help="OWNER/NAME; default: the repo of the current clone")
    args = parser.parse_args(argv)
    repo = ["--repo", args.repo] if args.repo else []
    try:
        if args.file:
            text = sys.stdin.read() if args.file == "-" else open(args.file, encoding="utf-8").read()
            issues = [{"number": None, "title": args.file, "body": text}]
        elif args.issue:
            issues = [gh_json(["issue", "view", str(args.issue), *repo, "--json", "number,title,body"])]
        else:
            issues = gh_json(["issue", "list", "--state", "open", "--label", args.label, "--limit", "500",
                              *repo, "--json", "number,title,body"])
    except (OSError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    failed = 0
    for issue in sorted(issues, key=lambda i: i["number"] or 0):
        problems = gate_problems(issue["body"])
        failed += bool(problems)
        name = f"#{issue['number']}" if issue["number"] else issue["title"]
        print(f"{'FAIL' if problems else 'PASS'} {name} {issue['title'] if issue['number'] else ''}".rstrip())
        for problem in problems:
            print(f"  - {problem}")
    print(f"{len(issues) - failed} pass, {failed} fail")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
