"""new-case: shared stdlib helpers of AGR Tools (one copy instead of one per module).

No pymxs and no runtime/ctx: export_core.py also runs standalone as a CLI, and the tests load every module by path.
Users load this file by sibling path (`Path(__file__).with_name('session_core.py')`).
"""
import os
from pathlib import Path


def in_session(emax, label, fn):
    """Run fn() inside emax.session (one undo record, selection restored) and RE-RAISE its error afterwards.

    Measured (job 20261105-011438-a488a8fd, Max 2024 batch): an exception inside `pymxs.undo(True, ...)` does not
    leave the `with` block, so a failed apply would carry on as if it had worked. The error is kept and raised
    after the context exits; fn() cleans up its own copies/files before it fails."""
    box = {}
    with emax.session(label):
        try:
            box['value'] = fn()
        except BaseException as exc:  # noqa: BLE001 - re-raised below, outside the undo context
            box['error'] = exc
    if 'error' in box:
        raise box['error']
    return box['value']


def same(a, b):
    """True when two paths name the same file (normalised resolved path, else os.path.samefile)."""
    a, b = Path(a), Path(b)
    try:
        if os.path.normcase(str(a.resolve())) == os.path.normcase(str(b.resolve())):
            return True
    except OSError as exc:
        raise ValueError(f'cannot resolve paths: {exc}') from exc
    if a.exists() and b.exists():
        try:
            return os.path.samefile(a, b)
        except OSError as exc:
            raise ValueError(f'cannot compare input and output identity: {exc}') from exc
    return False
