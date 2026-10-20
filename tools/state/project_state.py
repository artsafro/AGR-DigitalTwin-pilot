"""Generate docs/PROJECT_STATE.md from merged commits and open pull requests.

Regenerate from the repo root:

    python tools/state/project_state.py

The write is refused (exit 1, destination untouched) when the sources are empty,
partial, or unsupported, when a value is NaN or infinite, when the document
would be 80 lines or more, or when the output path resolves to an input.

new-case: deterministic git/GitHub state snapshot and repository context budget.
"""
import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

CHAR_LIMIT = 40_000
LINE_LIMIT = 80
SHA = re.compile(r"[0-9a-fA-F]{7,40}")
ATX = re.compile(r"^ {0,3}#{1,6}(?:[ \t]|$)")
NONFINITE = {
    "nan", "+nan", "-nan", "inf", "+inf", "-inf", "infinity", "+infinity", "-infinity",
}
JSON_NONFINITE = re.compile(r"\bNaN\b|\bInfinity\b|\b-Infinity\b")


class FailClosed(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _nonfinite_token(value):
    return isinstance(value, str) and value.strip().casefold() in NONFINITE


def check_char_total(total):
    """Pass only a positive finite character total strictly under CHAR_LIMIT."""
    if isinstance(total, bool) or total is None:
        raise FailClosed("unsupported")
    if isinstance(total, str):
        token = total.strip()
        if token == "":
            raise FailClosed("empty")
        if _nonfinite_token(token):
            raise FailClosed("non-finite")
        try:
            number = float(token)
        except ValueError as exc:
            raise FailClosed("unsupported") from exc
        total = number
    if isinstance(total, float):
        if not math.isfinite(total):
            raise FailClosed("non-finite")
        if not total.is_integer():
            raise FailClosed("unsupported")
        total = int(total)
    if not isinstance(total, int):
        raise FailClosed("unsupported")
    if total <= 0:
        raise FailClosed("empty")
    if total >= CHAR_LIMIT:
        raise FailClosed("threshold")
    return total


def measure_files(paths):
    total = 0
    for raw in paths:
        path = Path(raw)
        if not path.is_file():
            raise FailClosed("partial")
        with path.open(encoding="utf-8", newline="") as source:
            text = source.read()
        if text.strip() == "":
            raise FailClosed("empty")
        total += len(text)
    return check_char_total(total)


def normalize_merges(lines):
    if isinstance(lines, str):
        lines = lines.splitlines()
    if not isinstance(lines, list):
        raise FailClosed("unsupported")
    rows = []
    for raw in lines:
        if not isinstance(raw, str):
            raise FailClosed("unsupported")
        line = raw.replace("\r", "")
        if line.strip() == "":
            continue
        if "\t" not in line:
            raise FailClosed("partial")
        sha, subject = line.split("\t", 1)
        sha = sha.strip()
        subject = subject.strip()
        if _nonfinite_token(sha) or _nonfinite_token(subject):
            raise FailClosed("non-finite")
        if SHA.fullmatch(sha) is None or subject == "" or "\n" in subject:
            raise FailClosed("partial")
        rows.append((sha.lower(), subject))
    return rows


def normalize_opens(items):
    if not isinstance(items, list):
        raise FailClosed("partial")
    rows = []
    for item in items:
        if not isinstance(item, dict):
            raise FailClosed("partial")
        number = item.get("number", None)
        title = item.get("title", None)
        head = item.get("headRefName", None)
        draft = item.get("isDraft", None)
        if "number" not in item or "title" not in item or "headRefName" not in item or "isDraft" not in item:
            raise FailClosed("partial")
        if isinstance(number, float) and not math.isfinite(number):
            raise FailClosed("non-finite")
        if isinstance(number, str) and _nonfinite_token(number):
            raise FailClosed("non-finite")
        if isinstance(title, str) and _nonfinite_token(title):
            raise FailClosed("non-finite")
        if isinstance(head, str) and _nonfinite_token(head):
            raise FailClosed("non-finite")
        if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
            raise FailClosed("partial")
        if not isinstance(title, str) or title.strip() == "" or "\n" in title or "\r" in title:
            raise FailClosed("partial")
        if not isinstance(head, str) or head.strip() == "" or "\n" in head or "\r" in head:
            raise FailClosed("partial")
        if not isinstance(draft, bool):
            raise FailClosed("partial")
        rows.append({
            "number": number,
            "title": title.strip(),
            "headRefName": head.strip(),
            "isDraft": draft,
        })
    return rows


def require_sources(merges, opens):
    if not merges and not opens:
        raise FailClosed("empty")


def _next_lines(repo):
    path = repo / "docs" / "PROJECT_STATE.next.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    if text.strip() == "":
        raise FailClosed("empty")
    rows = []
    for line in text.splitlines():
        if line.strip() == "":
            continue
        if _nonfinite_token(line.strip()):
            raise FailClosed("non-finite")
        if ATX.match(line):
            raise FailClosed("unsupported")
        rows.append(line.strip())
    if not rows:
        raise FailClosed("empty")
    return rows


def _capability_lines(repo):
    path = repo / 'evals/capability-b01/reference.json'
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if (data.get('schema') != 1 or data.get('agent') not in ('codex', 'claude', 'deepseek')
                or type(data.get('passed')) is not bool):
            raise ValueError('unsupported capability reference')
        parts = []
        for name in ('benchmark', 'procedural'):
            counts = data[name]
            if any(type(counts[k]) is not int or counts[k] < 0
                   for k in ('passed', 'failed', 'not_measured')):
                raise ValueError('invalid capability counts')
            parts.append(f"{name} {counts['passed']} passed / {counts['failed']} failed / "
                         f"{counts['not_measured']} not measured")
        if data['passed'] and any(data[n]['failed'] or data[n]['not_measured']
                                  or not data[n]['passed'] for n in ('benchmark', 'procedural')):
            raise ValueError('inconsistent capability readiness')
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise FailClosed('invalid capability reference') from exc
    status = 'ready' if data['passed'] else 'not ready'
    context = data.get('context', 'unspecified context')
    if context not in ('repository-only', 'repository + user skills', 'unspecified context'):
        raise FailClosed('invalid capability context')
    return [f"Capability A (`capability-b01`, {data['agent']}): {'; '.join(parts)}; {status}; {context}. "
            'Reference: `evals/capability-b01/reference.json`.']


def render(merges, opens, next_lines=None, capability_lines=None):
    require_sources(merges, opens)
    opens = sorted(opens, key=lambda pr: pr["number"])
    next_lines = list(next_lines or [])
    lines = [
        "# Project state",
        "",
        "Generated by `python tools/state/project_state.py`. "
        "Regenerate with `python tools/state/project_state.py`. Do not edit by hand.",
        "",
        "## Goal",
        "",
        "NPM and VPM deliveries for buildings, Ground, MAF, Flora and UCX, plus the Unreal experience. "
        "Sections below are generated from merged and open pull requests.",
        "",
        "## In production",
        "",
        "PR merges do not imply delivery acceptance. Per-object gates stay in `jobs/<ID>/STATE.md`. "
        "Merged pull requests, newest first:",
    ]
    if merges:
        lines.extend(f"- `{sha[:7]}` {subject}" for sha, subject in merges)
    else:
        lines.append("- (none)")
    lines.extend(["", "## Harness", ""])
    if capability_lines:
        lines.extend([*capability_lines, ""])
    lines.append("Open pull requests:")
    if opens:
        for pr in opens:
            draft = " draft" if pr["isDraft"] else ""
            lines.append(f"- #{pr['number']} {pr['title']} [{pr['headRefName']}]{draft}")
    else:
        lines.append("- (none)")
    lines.extend(["", "## Next step", ""])
    if next_lines:
        lines.extend(f"- {line}" for line in next_lines)
    else:
        lines.append("Consult the board and the assigned card for the next action.")
    lines.extend([
        "",
        "## Links",
        "",
        "- Pipeline: `docs/pipeline.md`. Unsolved work: `docs/backlog.md`. Conflicts: `docs/domain/conflicts.md`.",
        "- Decisions: `docs/decisions.md`. Per-object state: `jobs/<ID>/STATE.md`.",
        "- Regenerate: `python tools/state/project_state.py`.",
    ])
    return "\n".join(lines) + "\n"


def finalize(text, limit=LINE_LIMIT):
    if not isinstance(text, str) or text.strip() == "":
        raise FailClosed("empty")
    if len(text.splitlines()) >= limit:
        raise FailClosed("threshold")
    if not text.endswith("\n"):
        text += "\n"
    return text


def _same(left, right):
    try:
        return os.path.normcase(str(left.resolve())) == os.path.normcase(str(right.resolve()))
    except OSError as exc:
        raise FailClosed("unsupported") from exc


def _inputs(repo):
    found = [repo]
    gitdir = repo / ".git"
    if gitdir.exists():
        found.append(gitdir)
        if gitdir.is_file():
            pointer = gitdir.read_text(encoding="utf-8").strip()
            if pointer.startswith("gitdir: "):
                metadata = (repo / pointer[8:]).resolve()
                found.append(metadata)
                common = metadata / "commondir"
                if common.is_file():
                    found.append((metadata / common.read_text(encoding="utf-8").strip()).resolve())
    found.append(repo / "docs" / "PROJECT_STATE.next.md")
    found.append(repo / "evals/capability-b01/reference.json")
    found.append(Path(__file__).resolve())
    return found


def _refuse_output(output, inputs):
    if output.exists() and output.is_dir():
        raise FailClosed("output-is-input")
    for src in inputs:
        if (_same(output, src)
                or (src.is_dir() and src != inputs[0] and output.resolve().is_relative_to(src.resolve()))
                or (output.exists() and src.exists() and os.path.samefile(output, src))):
            raise FailClosed("output-is-input")


def _publish(output, text):
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8", newline="\n")
        os.replace(temporary, output)
    except OSError as exc:
        raise FailClosed("unsupported") from exc
    finally:
        if temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass


def _command(argv):
    """Resolve git/gh on PATH, including a .cmd/.bat stub ahead of a real .exe."""
    found = shutil.which(argv[0])
    if not found:
        raise FailClosed("unsupported")
    if found.lower().endswith((".cmd", ".bat")):
        escaped = [arg.replace("%", "%%") for arg in argv[1:]]
        return ["cmd.exe", "/d", "/c", found, *escaped]
    return [found, *argv[1:]]


def _capture(argv, cwd):
    try:
        completed = subprocess.run(
            _command(argv), cwd=cwd, capture_output=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise FailClosed("unsupported") from exc
    if completed.returncode != 0:
        raise FailClosed("unsupported")
    return completed.stdout.decode("utf-8", errors="replace")


def _load_opens(raw):
    if raw.strip() == "":
        raise FailClosed("partial")
    if JSON_NONFINITE.search(raw):
        raise FailClosed("non-finite")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FailClosed("partial") from exc
    return normalize_opens(payload)


def generate(repo, output, max_merges, max_open):
    repo = Path(repo)
    output = Path(output)
    if not repo.is_dir():
        raise FailClosed("unsupported")
    if max_merges < 1 or max_open < 1:
        raise FailClosed("unsupported")
    inputs = _inputs(repo)
    _refuse_output(output, inputs)
    merges_raw = _capture(
        ["git", "log", "--merges", "--grep=^Merge pull request #",
         "-n", str(max_merges), "--format=%H%x09%s"], repo)
    remote = _capture(["git", "remote", "get-url", "origin"], repo).strip()
    match = re.fullmatch(r"(?:https://github\.com/|git@github\.com:)([\w.-]+/[\w.-]+?)(?:\.git)?/?", remote)
    if match is None:
        raise FailClosed("unsupported origin")
    opens_raw = _capture(
        ["gh", "pr", "list", "--repo", match[1], "--state", "open", "--limit", str(max_open),
         "--json", "number,title,headRefName,isDraft"],
        repo)
    merges = normalize_merges(merges_raw)[:max_merges]
    opens = _load_opens(opens_raw)[:max_open]
    require_sources(merges, opens)
    text = finalize(render(merges, opens, _next_lines(repo), _capability_lines(repo)))
    _publish(output, text)
    return text


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate docs/PROJECT_STATE.md or measure base context.")
    parser.add_argument("--repo", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--max-merges", type=int, default=12)
    parser.add_argument("--max-open", type=int, default=12)
    parser.add_argument("--budget-chars", default=None)
    parser.add_argument("--budget-files", nargs=3, default=None)
    args = parser.parse_args(argv)
    try:
        if args.budget_chars is not None and args.budget_files is not None:
            raise FailClosed("unsupported")
        if args.budget_chars is not None:
            print(check_char_total(args.budget_chars))
            return 0
        if args.budget_files is not None:
            print(measure_files(args.budget_files))
            return 0
        repo = args.repo or Path(__file__).resolve().parents[2]
        output = args.output or (repo / "docs" / "PROJECT_STATE.md")
        generate(repo, output, args.max_merges, args.max_open)
        return 0
    except FailClosed as exc:
        print(f"project_state: {exc.reason}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
