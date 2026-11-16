"""Resolve git conflict blocks in docs/decisions.md (#1558): union of D-rows, HEAD wins on the same id, id order.

Pattern: n/a | new-case: conflict-marker resolver for the decision log table (stdlib, in place, fail closed).

`git merge` (or `git merge origin/main` during rework) leaves `<<<<<<< / ======= / >>>>>>>` blocks when two
branches append rows at the end of the table. A `.gitattributes` `merge=union` is not enough: it keeps both rows
in arrival order and silently keeps two rows with the same id. This tool, per conflict block:
  - takes every `| D<n> |` row of both sides (an optional diff3 `|||||||` base section is ignored);
  - same id, same text -> one row; same id, different text -> the HEAD (ours) row stays and the incoming row is
    REPORTED as a collision: the later branch renumbers it (`python tools/git-hooks/decision_ids.py next --fetch`,
    then every `[D<n>]` reference of that branch) and re-adds the row;
  - writes the rows in id order; non-row lines must be equal on both sides, except link-reference definitions
    (`[name]: url`), which are united (same name with a different url is an error).
After resolving, every D-row id in the file must be unique and strictly ascending.

Usage:
  python tools/decisions_merge.py [docs/decisions.md]
Exit codes: 0 resolved (or nothing to resolve), 1 resolved with same-id collisions (file written, rows to
renumber printed), 2 error (unreadable/empty file, no D-row table, malformed or unresolvable block, duplicate or
out-of-order ids): nothing is written.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROW = re.compile(r"^\| D(\d+) \|")
LINK = re.compile(r"^\[([^\]]+)\]:\s*(\S.*)$")
DEFAULT = Path("docs/decisions.md")


class MergeError(ValueError):
    """The file cannot be resolved automatically; nothing is written."""


@dataclass(frozen=True)
class Collision:
    id: int
    kept: str
    incoming: str


def _row_id(line: str) -> int | None:
    m = ROW.match(line)
    return int(m.group(1)) if m else None


def _split_side(lines: list[str], side: str) -> tuple[dict[int, str], list[str]]:
    rows: dict[int, str] = {}
    other: list[str] = []
    for line in lines:
        n = _row_id(line)
        if n is None:
            other.append(line)
            continue
        if any(o.strip() for o in other):
            raise MergeError(f"{side}: row D{n:03d} follows non-row text inside a conflict block; resolve by hand")
        if n in rows and rows[n] != line:
            raise MergeError(f"{side}: id D{n:03d} occurs twice with different text inside one side")
        rows[n] = line
    return rows, other


def _merge_other(ours: list[str], theirs: list[str]) -> list[str]:
    o = [line for line in ours if line.strip()]
    t = [line for line in theirs if line.strip()]
    if o == t:
        return ours
    if not all(LINK.match(line) for line in o + t):
        raise MergeError("non-row text differs between the sides of a conflict block; resolve by hand")
    names = {}
    for line in o:
        m = LINK.match(line)
        names[m.group(1)] = m.group(2).strip()
    extra = []
    for line in t:
        m = LINK.match(line)
        name, url = m.group(1), m.group(2).strip()
        if name in names:
            if names[name] != url:
                raise MergeError(f"link reference [{name}] has different targets on the two sides")
            continue
        names[name] = url
        extra.append(line)
    last = max(i for i, line in enumerate(ours) if line.strip()) if o else len(ours) - 1
    return ours[:last + 1] + extra + ours[last + 1:]


def _resolve_block(ours: list[str], theirs: list[str]) -> tuple[list[str], list[Collision]]:
    o_rows, o_other = _split_side(ours, "HEAD")
    t_rows, t_other = _split_side(theirs, "incoming")
    collisions = []
    merged = dict(t_rows)
    for n, line in t_rows.items():
        if n in o_rows and o_rows[n] != line:
            collisions.append(Collision(n, o_rows[n].rstrip("\r\n"), line.rstrip("\r\n")))
    merged.update(o_rows)
    other = _merge_other(o_other, t_other)
    return [merged[n] for n in sorted(merged)] + other, sorted(collisions, key=lambda c: c.id)


def resolve_text(text: str) -> tuple[str, list[Collision]]:
    """Return (resolved text, collisions). Raises MergeError when the text cannot be resolved safely."""
    if not text.strip():
        raise MergeError("empty file")
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    collisions: list[Collision] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        bare = line.rstrip("\r\n")
        if bare in ("=======", ">>>>>>>", "|||||||") or line.startswith((">>>>>>> ", "||||||| ")):
            raise MergeError(f"line {i + 1}: conflict marker outside a block")
        if not line.startswith("<<<<<<<"):
            out.append(line)
            i += 1
            continue
        start = i
        ours: list[str] = []
        theirs: list[str] = []
        section = ours
        i += 1
        while True:
            if i >= len(lines):
                raise MergeError(f"line {start + 1}: unterminated conflict block")
            cur = lines[i]
            bare = cur.rstrip("\r\n")
            if cur.startswith("<<<<<<<"):
                raise MergeError(f"line {i + 1}: nested conflict block")
            if bare == "|||||||" or cur.startswith("||||||| "):
                if section is not ours:
                    raise MergeError(f"line {i + 1}: base section after =======")
                section = []   # diff3 base: ignored
            elif bare == "=======":
                if section is theirs:
                    raise MergeError(f"line {i + 1}: second ======= in one block")
                section = theirs
            elif bare == ">>>>>>>" or cur.startswith(">>>>>>> "):
                if section is not theirs:
                    raise MergeError(f"line {i + 1}: >>>>>>> before =======")
                break
            else:
                section.append(cur)
            i += 1
        block, found = _resolve_block(ours, theirs)
        out.extend(block)
        collisions.extend(found)
        i += 1
    ids = [n for n in (_row_id(line) for line in out) if n is not None]
    if not ids:
        raise MergeError("no `| D<n> |` rows: not a decision log")
    seen = set()
    for prev, n in zip([0] + ids, ids):
        if n in seen:
            raise MergeError(f"D{n:03d} occurs twice after resolving (outside the conflict block too); resolve by hand")
        seen.add(n)
        if n <= prev:
            raise MergeError(f"D{n:03d} follows D{prev:03d}: rows are not in id order after resolving")
    return "".join(out), collisions


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Resolve docs/decisions.md conflict blocks (#1558)")
    ap.add_argument("path", nargs="?", type=Path, default=DEFAULT)
    args = ap.parse_args(argv)
    path: Path = args.path
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        resolved, collisions = resolve_text(text)
    except (OSError, UnicodeDecodeError, MergeError) as exc:
        print(f"ERROR: {path}: {exc}; nothing written", file=sys.stderr)
        return 2
    if resolved != text:
        tmp = path.with_name(path.name + ".partial")
        if tmp.exists():
            print(f"ERROR: foreign temp file exists: {tmp}; nothing written", file=sys.stderr)
            return 2
        try:
            with open(tmp, "x", encoding="utf-8", newline="") as fh:
                fh.write(resolved)
            if path.read_bytes() != raw:
                raise OSError("file changed while resolving")
            os.replace(tmp, path)
        except OSError as exc:
            print(f"ERROR: {path}: {exc}; nothing written", file=sys.stderr)
            return 2
        finally:
            if tmp.exists():
                tmp.unlink()
        print(f"resolved {path.as_posix()}")
    else:
        print(f"{path.as_posix()}: no conflict blocks")
    for c in collisions:
        print(f"COLLISION D{c.id:03d}: kept HEAD row:\n  {c.kept}\nincoming row needs a new id - renumber it "
              f"(python tools/git-hooks/decision_ids.py next --fetch, then its [D{c.id:03d}] references) "
              f"and re-add it:\n  {c.incoming}")
    return 1 if collisions else 0


if __name__ == "__main__":
    sys.exit(main())
