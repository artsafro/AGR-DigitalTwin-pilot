"""Failure-atomicity controls for tools/methods/safe_write.py:publish_text.

Pattern: new-case: methods-catalog publish failure atomicity (exclusive temp, os.replace,
owned-temp removal on BaseException). Synthetic bytes only; not a delivery package.

Acceptance (input -> expected output):

| # | input | expected |
|---|---|---|
| 1 | existing `results.jsonl` = `b"OLD TARGET\\r\\nkeep"`; text `привет\\nмир\\n`; `results.jsonl.partial` = `b"UNRELATED PARTIAL\\r\\n"`; `.unrelated.tmp` = `b"UNRELATED DOT TEMP\\r\\n"` | returns that target Path; target bytes == `"привет\\nмир\\n".encode("utf-8")` (two LF 0x0A, no CR); both sentinels byte-identical; no owned `.{results.jsonl}.*.tmp` remains; that temp name can be recreated and renamed |
| 2 | same files; real temp holds the full UTF-8 payload and the target is still `b"OLD TARGET\\r\\nkeep"` when `os.replace` raises the same `PermissionError(13, "Access is denied")` | that PermissionError propagates; directory inventory unchanged; owned temp removed and its name reusable |
| 3 | target path absent; same two sentinels; same PermissionError at replace after a complete temp | that PermissionError; target still absent; sentinels unchanged; owned temp removed |
| 4 | existing target as in row 1; text `привет\\nмир\\n`; real temp write flushes a one-character prefix then raises the same `OSError(28, "No space left on device")` | that OSError propagates; `os.replace` is not called; target still `b"OLD TARGET\\r\\nkeep"`; sentinels unchanged; owned temp removed |
| 5 | existing target as in row 1; `os.replace` raises the same `KeyboardInterrupt` after the intact target and the complete temp were observed | that KeyboardInterrupt propagates; target and sentinels unchanged; owned temp removed |
| 6 | existing target and both sentinels; `tempfile.mkstemp` raises the same `OSError(17, "File exists")` before returning an fd | that OSError propagates; inventory byte-identical; no file created or removed |
| probe | synthetic texts ``, `\\n`, `\\n\\n`, `a\\nb\\n`, `юникод\\nё`, `a\\r\\nb`, `\\r\\n`, `mixed\\r\\nkeep\\n` (8), each published onto the previous target bytes with the same sentinels | each target becomes exactly `text.encode("utf-8")` (`\\n` and `\\r` counts preserved; `newline="\\n"` does not translate); at each replace the previous target is still intact and the temp is complete; sentinels unchanged; no owned temp remains |

Out of scope: a failing `os.unlink` of the owned temp. These tests do not claim the helper removes an unremovable file or hides the original exception.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools" / "methods"

OLD = b"OLD TARGET\r\nkeep"
PARTIAL = b"UNRELATED PARTIAL\r\n"
DOT = b"UNRELATED DOT TEMP\r\n"
PARTIAL_NAME = "results.jsonl.partial"
DOT_NAME = ".unrelated.tmp"
TARGET_NAME = "results.jsonl"
TEXT = "привет\nмир\n"
PROBE = (
    "",
    "\n",
    "\n\n",
    "a\nb\n",
    "юникод\nё",
    "a\r\nb",
    "\r\n",
    "mixed\r\nkeep\n",
)


def _load(name, path):
    if name in sys.modules:
        return sys.modules[name]
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


sw = _load("safe_write", TOOLS / "safe_write.py")


class _Proxy:
    """Attribute overlay for one call. The real os/tempfile modules stay unchanged."""

    def __init__(self, real, overrides):
        object.__setattr__(self, "_real", real)
        object.__setattr__(self, "_overrides", dict(overrides))

    def __getattr__(self, name):
        overrides = object.__getattribute__(self, "_overrides")
        if name in overrides:
            return overrides[name]
        return getattr(object.__getattribute__(self, "_real"), name)


@contextmanager
def _bound(module, name, value):
    previous = getattr(module, name)
    setattr(module, name, value)
    try:
        yield previous
    finally:
        setattr(module, name, previous)


def _stage(tmp_path, *, present):
    folder = tmp_path / "pub"
    folder.mkdir()
    target = folder / TARGET_NAME
    if present:
        target.write_bytes(OLD)
    (folder / PARTIAL_NAME).write_bytes(PARTIAL)
    (folder / DOT_NAME).write_bytes(DOT)
    return target


def _inventory(folder):
    return {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()}


def _expect_inventory(folder, target_bytes):
    expect = {PARTIAL_NAME: PARTIAL, DOT_NAME: DOT}
    if target_bytes is not None:
        expect[TARGET_NAME] = target_bytes
    assert _inventory(folder) == expect


def _owned(folder):
    prefix = f".{TARGET_NAME}."
    return [p for p in folder.iterdir() if p.name.startswith(prefix) and p.name.endswith(".tmp")]


def _assert_replace_boundary(src, dst, *, old, payload):
    src_p, dst_p = Path(src), Path(dst)
    assert src_p.name.startswith(f".{TARGET_NAME}.") and src_p.name.endswith(".tmp"), src_p.name
    assert src_p.parent == dst_p.parent and src_p.is_file()
    assert src_p.read_bytes() == payload
    if old is None:
        assert not dst_p.exists()
    else:
        assert dst_p.is_file() and dst_p.read_bytes() == old
    assert (dst_p.parent / PARTIAL_NAME).read_bytes() == PARTIAL
    assert (dst_p.parent / DOT_NAME).read_bytes() == DOT


def _assert_reusable(path):
    """A deleted owned name must accept a new file that can be renamed and reopened."""
    assert not path.exists()
    path.write_bytes(b"reopen")
    moved = path.with_name(path.name + ".moved")
    path.rename(moved)
    assert moved.read_bytes() == b"reopen"
    moved.rename(path)
    with path.open("rb") as handle:
        assert handle.read() == b"reopen"
    path.unlink()
    assert not path.exists()


def _assert_reopenable(folder):
    for path in list(folder.iterdir()):
        if not path.is_file():
            continue
        held = path.read_bytes()
        moved = path.with_name(path.name + ".reopen")
        path.rename(moved)
        assert moved.read_bytes() == held
        moved.rename(path)
        with path.open("rb") as handle:
            assert handle.read() == held


def _replace_spy(src, dst, *, old, payload, seen):
    _assert_replace_boundary(src, dst, old=old, payload=payload)
    seen.append(Path(src))
    return os.replace(src, dst)


def test_publish_unicode_lf_keeps_sentinels_and_drops_owned_temp(tmp_path):
    target = _stage(tmp_path, present=True)
    payload = TEXT.encode("utf-8")
    seen = []

    def spy(src, dst):
        return _replace_spy(src, dst, old=OLD, payload=payload, seen=seen)

    with _bound(sw, "os", _Proxy(os, {"replace": spy})):
        got = sw.publish_text(target, TEXT)
    assert got == target and isinstance(got, Path)
    assert target.read_bytes() == payload
    assert payload.count(b"\n") == 2 and b"\r" not in payload
    assert seen and _owned(target.parent) == []
    _expect_inventory(target.parent, payload)
    _assert_reusable(seen[0])
    _assert_reopenable(target.parent)


def _failing_replace(tmp_path, *, present, exc):
    target = _stage(tmp_path, present=present)
    payload = TEXT.encode("utf-8")
    old = OLD if present else None
    seen = []

    def boom(src, dst):
        _assert_replace_boundary(src, dst, old=old, payload=payload)
        seen.append(Path(src))
        raise exc

    with _bound(sw, "os", _Proxy(os, {"replace": boom})):
        with pytest.raises(type(exc)) as caught:
            sw.publish_text(target, TEXT)
    assert caught.value is exc
    assert seen and _owned(target.parent) == []
    _expect_inventory(target.parent, old)
    _assert_reusable(seen[0])
    _assert_reopenable(target.parent)


def test_permissionerror_at_replace_keeps_existing_target(tmp_path):
    _failing_replace(tmp_path, present=True, exc=PermissionError(13, "Access is denied"))


def test_permissionerror_at_replace_leaves_absent_target_absent(tmp_path):
    _failing_replace(tmp_path, present=False, exc=PermissionError(13, "Access is denied"))


def test_partial_write_oserror_preserves_target_and_removes_owned_temp(tmp_path):
    target = _stage(tmp_path, present=True)
    payload = TEXT.encode("utf-8")
    err = OSError(28, "No space left on device")
    acquired = []
    seen = {"replace": 0, "partial": 0}

    def recording(*args, **kwargs):
        fd, tmp = tempfile.mkstemp(*args, **kwargs)
        acquired.append(Path(tmp))
        return fd, tmp

    def wrapping(fd, mode="r", *args, **kwargs):
        handle = os.fdopen(fd, mode, *args, **kwargs)
        real_write = handle.write

        def write(data):
            if seen["partial"]:
                return real_write(data)
            piece = data[:1]
            assert piece and len(TEXT) > 1
            real_write(piece)
            handle.flush()
            os.fsync(handle.fileno())
            size = acquired[-1].stat().st_size
            assert 0 < size < len(payload)
            seen["partial"] = size
            raise err

        handle.write = write
        return handle

    def forbid(src, dst):
        seen["replace"] += 1
        raise AssertionError("os.replace must not run after a partial temp write")

    with _bound(sw, "tempfile", _Proxy(tempfile, {"mkstemp": recording})), _bound(
        sw, "os", _Proxy(os, {"fdopen": wrapping, "replace": forbid})
    ):
        with pytest.raises(OSError) as caught:
            sw.publish_text(target, TEXT)
    assert caught.value is err
    assert seen["replace"] == 0 and seen["partial"] > 0
    assert acquired and _owned(target.parent) == []
    _expect_inventory(target.parent, OLD)
    _assert_reusable(acquired[0])
    _assert_reopenable(target.parent)


def test_keyboardinterrupt_at_replace_preserves_target_and_removes_owned_temp(tmp_path):
    _failing_replace(tmp_path, present=True, exc=KeyboardInterrupt())


def test_mkstemp_failure_before_acquisition_removes_nothing(tmp_path):
    target = _stage(tmp_path, present=True)
    err = OSError(17, "File exists")
    seen = {}

    def fail(*args, **kwargs):
        seen["prefix"] = kwargs.get("prefix")
        seen["suffix"] = kwargs.get("suffix")
        seen["dir"] = kwargs.get("dir")
        raise err

    before = _inventory(target.parent)
    with _bound(sw, "tempfile", _Proxy(tempfile, {"mkstemp": fail})):
        with pytest.raises(OSError) as caught:
            sw.publish_text(target, "не должно записаться\n")
    assert caught.value is err
    assert seen == {"prefix": f".{TARGET_NAME}.", "suffix": ".tmp", "dir": target.parent}
    assert _inventory(target.parent) == before
    assert _owned(target.parent) == []
    _assert_reopenable(target.parent)


def test_byte_exact_probe_over_text_inputs(tmp_path):
    assert len(PROBE) == 8
    target = _stage(tmp_path, present=True)
    previous = OLD
    for text in PROBE:
        payload = text.encode("utf-8")
        seen = []

        def spy(src, dst, previous=previous, payload=payload, seen=seen):
            return _replace_spy(src, dst, old=previous, payload=payload, seen=seen)

        with _bound(sw, "os", _Proxy(os, {"replace": spy})):
            got = sw.publish_text(target, text)
        assert got == target
        assert target.read_bytes() == payload
        assert payload.count(b"\n") == text.count("\n")
        assert payload.count(b"\r") == text.count("\r")
        assert _owned(target.parent) == []
        _expect_inventory(target.parent, payload)
        _assert_reusable(seen[0])
        previous = payload
    _assert_reopenable(target.parent)
