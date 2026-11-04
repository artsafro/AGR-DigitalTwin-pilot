"""Fail-closed file publication for the methods catalog (#706): input protection and atomic text writes.

Pattern: new-case: methods-catalog publish guard (review round 1 of PR #709).

`publish_text` writes through an exclusively created, uniquely named temporary file in the target folder
(`tempfile.mkstemp`, O_EXCL) and `os.replace`s it onto the target, so a pre-existing file with any other
name (e.g. an unrelated `results.jsonl.partial`) is never truncated or removed. A target that is a symlink or
a hard link of another file is refused, never replaced. `refuse_aliases` checks planned destinations against
protected inputs (resolved path or same file) before any side effect.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


class Refused(ValueError):
    pass


def same_file(a: Path, b: Path) -> bool:
    a, b = Path(a), Path(b)
    try:
        if a.resolve() == b.resolve():
            return True
        return a.exists() and b.exists() and os.path.samefile(a, b)
    except OSError:
        return False


def refuse_aliases(destinations, inputs) -> None:
    """Raise Refused when any destination is (or aliases) a protected input; nothing is touched."""
    for dst in destinations:
        for src in inputs:
            if same_file(dst, src):
                raise Refused(f"destination {dst} aliases input {src}; nothing written")


def guard_cli(inputs, outputs) -> None:
    """Standalone writers (#727 review 1): refuse, before any side effect, an output or report that is (or
    aliases: same resolved path, hard link, symlink) an input or another output, and an output that is a
    symlink / hard link / not a regular file. Raises Refused; nothing is written."""
    inputs, outputs = [Path(p) for p in inputs], [Path(p) for p in outputs]
    refuse_aliases(outputs, inputs)
    for i, d in enumerate(outputs):
        for e in outputs[i + 1:]:
            if same_file(d, e):
                raise Refused(f"two outputs are the same file: {d} and {e}; nothing written")
    for d in outputs:
        check_target(d)


def check_target(dst: Path) -> None:
    dst = Path(dst)
    if dst.is_symlink():
        raise Refused(f"{dst} is a symlink; refusing to replace it")
    if dst.exists():
        if not dst.is_file():
            raise Refused(f"{dst} is not a regular file")
        if os.stat(dst).st_nlink > 1:
            raise Refused(f"{dst} is a hard link of another file; refusing to replace it")


def publish_text(dst: Path, text: str) -> Path:
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    check_target(dst)
    fd, tmp = tempfile.mkstemp(prefix=f".{dst.name}.", suffix=".tmp", dir=dst.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, dst)
    except BaseException:
        try:
            os.unlink(tmp)  # only our own exclusively created temp
        except OSError:
            pass
        raise
    return dst
