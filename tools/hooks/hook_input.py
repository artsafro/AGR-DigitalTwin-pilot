"""new-case: UTF-8 hook transport, independent of the Windows console code page.

Dispatchers may supply already-decoded StringIO; real stdin must be read as
bytes so its locale-dependent TextIOWrapper cannot corrupt JSON string values.
JSON validation and each hook's existing error policy remain with the caller.
"""
import sys


def read_stdin():
    """Read UTF-8 transport bytes, or preserve an already-decoded text stream."""
    buffer = getattr(sys.stdin, "buffer", None)
    if buffer is not None:
        return buffer.read().decode("utf-8")
    return sys.stdin.read()
