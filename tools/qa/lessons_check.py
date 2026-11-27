"""Job LESSONS.md evidence check [D415] (#1924, Harness2 arXiv 2610.14224). Warn-only by default.

Pattern: n/a | new-case: warn on a new job lesson without situation / lesson / evidence.

    python tools/qa/lessons_check.py FILE...            # every form lesson in the files
    python tools/qa/lessons_check.py --staged           # staged jobs/*/LESSONS.md vs HEAD (pre-commit)
    python tools/qa/lessons_check.py --base origin/main # jobs/*/LESSONS.md changed since the merge-base
    add --strict to exit 1 on any warning.

The form (template `jobs/_template/LESSONS.md`): one `## L<n> <title>` block per lesson with three fields,
`- Situation:`, `- Lesson:`, `- Evidence:`; the evidence is the contrast or before/after that proves the lesson
(an `agr trainer ab` report, two readbacks, numbers). Lessons stay job-local: no D-row promotion here.
A lesson is NEW when its `L<n>` id is not in the base version; only new lessons are checked in diff mode, and an
added bullet or table row outside any `## L<n>` block (the older free form) warns too. Fenced code is ignored.
Exit codes: 0 checked (warnings printed as `WARN ...`), 1 warnings with --strict, 2 unreadable input / git error.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

FIELDS = ("situation", "lesson", "evidence")
HEAD_RE = re.compile(r"^##\s+(L\d+)\b\s*(.*)$")
FIELD_RE = re.compile(r"^\s*[-*]?\s*\**\s*(situation|lesson|evidence)\s*\**\s*:\s*\**\s*(.*)$", re.I)
PLACEHOLDER_RE = re.compile(r"^(todo|tbd|n/?a|none|-+|—|\?+|\.\.\.|<[^>]*>)\.?$", re.I)
LEGACY_RE = re.compile(r"^\s*([-*]\s+\S|\|)")
TABLE_SEP_RE = re.compile(r"^\s*\|[\s:|-]+\|?\s*$")
GLOB = "jobs/*/LESSONS.md"


class CheckError(Exception):
    """Unreadable input or git failure: exit 2."""


def _lines(text):
    """(line, in_fence) pairs."""
    fence = False
    for ln in text.splitlines():
        if ln.lstrip().startswith("```"):
            fence = not fence
            yield ln, True
            continue
        yield ln, fence


def parse_lessons(text):
    """-> [{id, title, line, fields{situation, lesson, evidence}}] of `## L<n>` blocks outside fenced code."""
    out, cur, last = [], None, None
    for i, (ln, fenced) in enumerate(_lines(text), 1):
        if fenced:
            continue
        m = HEAD_RE.match(ln)
        if m:
            cur = {"id": m.group(1), "title": m.group(2).strip(), "line": i, "fields": {}}
            out.append(cur)
            last = None
            continue
        if re.match(r"^#{1,2}\s", ln):
            cur = last = None
            continue
        if cur is None:
            continue
        f = FIELD_RE.match(ln)
        if f:
            last = f.group(1).lower()
            cur["fields"][last] = f.group(2).strip()
        elif last and ln.strip() and ln.startswith((" ", "\t")):
            cur["fields"][last] = (cur["fields"][last] + " " + ln.strip()).strip()
    return out


def _empty(value):
    v = (value or "").strip().strip("*").strip()
    return not v or bool(PLACEHOLDER_RE.match(v))


def _block_lines(text):
    """Set of line texts that belong to `## L<n>` blocks or fenced code (not legacy candidates)."""
    inside, keep = False, set()
    for ln, fenced in _lines(text):
        if fenced:
            keep.add(ln)
            continue
        if HEAD_RE.match(ln):
            inside = True
        elif re.match(r"^#{1,2}\s", ln):
            inside = False
        if inside:
            keep.add(ln)
    return keep


def warnings_for(text, base=None, path="LESSONS.md"):
    """Warnings for the lessons of `text`; with `base`, only lessons and legacy lines new against it."""
    lessons = parse_lessons(text)
    old_ids = {x["id"] for x in parse_lessons(base)} if base is not None else set()
    out = []
    for lid, n in Counter(x["id"] for x in lessons).items():
        if n > 1:
            out.append(f"WARN {path}: duplicate lesson id {lid} ({n} blocks)")
    for x in lessons:
        if x["id"] in old_ids:
            continue
        missing = [f for f in FIELDS if _empty(x["fields"].get(f))]
        if missing:
            out.append(f"WARN {path}:{x['line']}: {x['id']} \"{x['title']}\" has no {' / '.join(missing)} "
                       f"(situation / lesson / evidence form [D415])")
    if base is not None:
        before = Counter(ln for ln, fenced in _lines(base) if not fenced)
        inside = _block_lines(text)
        for i, (ln, fenced) in enumerate(_lines(text), 1):
            if fenced:
                continue
            if before[ln] > 0:
                before[ln] -= 1
                continue
            if ln in inside or not LEGACY_RE.match(ln) or TABLE_SEP_RE.match(ln):
                continue
            out.append(f"WARN {path}:{i}: new lesson not in situation / lesson / evidence form [D415]: "
                       f"{ln.strip()[:80]}")
    return out


def _git(args, cwd):
    p = subprocess.run(["git", *args], capture_output=True, cwd=cwd)
    if p.returncode != 0:
        raise CheckError(f"git {' '.join(args)}: {p.stderr.decode('utf-8', 'replace').strip()}")
    return p.stdout.decode("utf-8", "replace")


def _show(ref_path, cwd):
    p = subprocess.run(["git", "show", ref_path], capture_output=True, cwd=cwd)
    return p.stdout.decode("utf-8", "replace") if p.returncode == 0 else ""


def _skip(rel):
    return rel.startswith("jobs/_template/")


def run(argv=None):
    ap = argparse.ArgumentParser(prog="lessons_check", description=__doc__.split("\n\n")[0])
    ap.add_argument("files", nargs="*")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--staged", action="store_true")
    g.add_argument("--base")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args(argv)
    cwd = Path.cwd()
    warns = []
    if a.staged or a.base:
        top = _git(["rev-parse", "--show-toplevel"], cwd).strip()
        if a.staged:
            rels = _git(["diff", "--cached", "--name-only", "--diff-filter=AM", "--", GLOB], top).split()
            pairs = [(r, _show(f":{r}", top), _show(f"HEAD:{r}", top)) for r in rels]
        else:
            mb = _git(["merge-base", a.base, "HEAD"], top).strip()
            rels = _git(["diff", "--name-only", "--diff-filter=AM", mb, "--", GLOB], top).split()
            pairs = []
            for r in rels:
                try:
                    pairs.append((r, (Path(top) / r).read_text(encoding="utf-8"), _show(f"{mb}:{r}", top)))
                except OSError as exc:
                    raise CheckError(f"cannot read {r}: {exc}") from exc
        for rel, cur, base in pairs:
            if not _skip(rel):
                warns += warnings_for(cur, base=base, path=rel)
    for f in a.files:
        try:
            text = Path(f).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise CheckError(f"cannot read {f}: {exc}") from exc
        warns += warnings_for(text, path=Path(f).as_posix())
    for w in warns:
        print(w)
    return 1 if a.strict and warns else 0


def main(argv=None):
    try:
        return run(argv)
    except CheckError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
