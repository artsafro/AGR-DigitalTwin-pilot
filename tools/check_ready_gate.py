"""Check the ready-for-agent gate (#130): an issue body is ready only when its contract is filled.

The contract is `.github/ISSUE_TEMPLATE/task.md`: Requirement, Specification (Acceptance, Inputs and
versions, Out of scope, Evidence the PR must bring) and Context. Every field must hold text after the
template's HTML comments are removed; Acceptance needs at least one non-empty checkbox item. "None" is a
valid answer and counts as filled.

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
COMMENT = re.compile(r"<!--.*?-->", re.S)
CHECKBOX = re.compile(r"^\s*[-*+]\s+\[[ xX]\]\s*(.*)$")


def headings(text):
    """Every ATX heading as (level, text)."""
    found = []
    for line in text.splitlines():
        match = HEADING.match(line)
        if match:
            found.append((len(match.group(1)), match.group(2).strip()))
    return found


def field_texts(text):
    """Map each heading to its own text, up to the next heading of any level, comments removed."""
    fields, current, buffer = {}, None, []
    for line in COMMENT.sub("", text.replace("\r\n", "\n")).splitlines():
        match = HEADING.match(line)
        if match:
            if current is not None:
                fields.setdefault(current, "\n".join(buffer).strip())
            current, buffer = match.group(2).strip().lower(), []
        else:
            buffer.append(line)
    if current is not None:
        fields.setdefault(current, "\n".join(buffer).strip())
    return fields


def gate_problems(body):
    """Problems that keep a body from ready-for-agent; an empty list means it passes."""
    fields = field_texts(body or "")
    problems = []
    for name in SECTIONS:
        if name.lower() not in fields:
            problems.append(f"{name}: section missing")
    for name in FIELDS:
        key = name.lower()
        if key not in fields:
            if name in SPEC_FIELDS and "specification" in fields:
                problems.append(f"{name}: field missing under Specification")
            continue
        content = fields[key]
        if name == "Acceptance":
            items = [m.group(1).strip() for m in map(CHECKBOX.match, content.splitlines()) if m]
            if not any(items):
                problems.append("Acceptance: no checkable item (`- [ ] ...`)")
        elif not content:
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
