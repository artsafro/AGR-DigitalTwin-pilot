"""Atomic publication of a reader output; standard library only (Blender loads it by path) [D111] (#339).

The bytes go to an exclusive, uniquely named temporary file next to the target (`tempfile.mkstemp`, `O_EXCL`), which
then replaces the target. No predictable side name is used, so an input that happens to be called `<output>.partial`
and any unrelated sentinel files are never overwritten or removed; on failure the temporary file is deleted.
Pattern: n/a | new-case: alias-safe output publication for the structure readers (#339 review 1).
"""
import os
import tempfile
from pathlib import Path


def publish(path, data: bytes) -> None:
    """Write `data` to `path` atomically through a fresh exclusive temporary file in the same directory."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise
