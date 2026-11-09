"""new-case: #1043 release-vs-reclaim unlink gap; at most one holder.

The owner's release and a POSIX reclaimer never both unlink by name -> at most one holder.

A reclaimer X inside `_unlink_named_if` has checked bytes + inode of a stale lock (owner O alive,
past `until`). If O releases and a new holder H O_EXCLs a fresh lock between X's checks and X's
`os.remove`, X used to remove H's lock and a third caller K acquired too. POSIX consume is forced
(fcntl is absent on Windows: `locks._flock` falls back to msvcrt.locking, and is the injectable seam).
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import pytest

from agr_mcp import locks

# Every os call of `_unlink_named_if` between the reclaimer's first open and its unlink.
POINTS = ["open", "read", "fstat", "stat", "lstat", "remove"]


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("AGR_MCP_LOCK_DIR", str(tmp_path / "locks"))


def _lock_file() -> Path:
    path = locks.lock_path("blender-batch")
    assert path is not None
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _o_excl(path, name, holders, now):
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return
    os.write(fd, json.dumps({"pid": os.getpid(), "until": now + 600, "token": name}).encode())
    os.close(fd)
    holders.append(name)


def _interleave(monkeypatch, point, *, via_reclaim=True, flock_works=True):
    """X reclaims O's stale lock; at `point` O releases and H O_EXCLs; then K O_EXCLs.

    Returns (fired, reclaimed, holders, files left in the lock dir).
    """
    path = _lock_file()
    now = time.time()
    # O: alive (our pid), past `until` -> stale; its release is still legitimate.
    path.write_text(json.dumps({"card": "o", "pid": os.getpid(), "until": now - 1, "token": "O"}),
                    encoding="utf-8")
    monkeypatch.setattr(locks, "_drop_stale_inode", locks._drop_stale_inode_posix)
    if not flock_works:
        monkeypatch.setattr(locks, "_flock", lambda fd, op: None)
    main = threading.get_ident()
    state = {"armed": False, "fired": False}
    holders: list[str] = []
    racer = threading.Thread(target=lambda: (locks._release(path, "O"), _o_excl(path, "H", holders, now)))

    def fire():
        if state["armed"] and not state["fired"] and threading.get_ident() == main:
            state["fired"] = True
            racer.start()
            racer.join(0.5)  # fixed: O's release waits for X's critical section

    real = {name: getattr(os, name) for name in POINTS}

    def hooked(name):
        def call(*args, **kwargs):
            if name == "remove":
                fire()
                return real[name](*args, **kwargs)
            result = real[name](*args, **kwargs)
            fire()
            return result
        return call

    real_unlink = locks._unlink_named_if

    def unlink_named_if(target, pred):
        arm = threading.get_ident() == main and target == path
        if arm:
            state["armed"] = True
        try:
            return real_unlink(target, pred)
        finally:
            if arm:
                state["armed"] = False

    monkeypatch.setattr(locks, "_unlink_named_if", unlink_named_if)
    monkeypatch.setattr(os, point, hooked(point))
    try:
        if via_reclaim:
            reclaimed = locks._reclaim(path, "X")
        else:
            mutex = locks._mutex_path(path)
            mutex.write_text(json.dumps({"pid": os.getpid(), "until": now + 30, "token": "X"}),
                             encoding="utf-8")
            reclaimed = locks._drop_stale_inode_posix(path, "X")
            mutex.unlink()
    finally:
        monkeypatch.setattr(os, point, real[point])
    if state["fired"]:
        racer.join(10)
        assert not racer.is_alive(), "O's release never returned"
    _o_excl(path, "K", holders, now)
    left = sorted(p.name for p in path.parent.iterdir())
    return state["fired"], reclaimed, holders, left


def test_reviewer_interleaving_lstat_gap_gives_one_holder(monkeypatch):
    """Issue witness: hook after X's final lstat -> holders == ['H'] (was ['H', 'K'])."""
    fired, reclaimed, holders, _left = _interleave(monkeypatch, "lstat")
    assert fired and reclaimed
    assert holders == ["H"]


@pytest.mark.parametrize("via_reclaim", [True, False])
@pytest.mark.parametrize("point", POINTS)
def test_probe_release_at_every_reclaimer_os_call_at_most_one_holder(point, via_reclaim, monkeypatch):
    """Brute force: O releases at every os call of X's `_unlink_named_if` -> exactly one holder, H."""
    fired, reclaimed, holders, left = _interleave(monkeypatch, point, via_reclaim=via_reclaim)
    assert fired, f"X never reached {point}"
    assert reclaimed
    assert holders == ["H"]
    lock = _lock_file()
    assert left == sorted([lock.name, f".{lock.name}.reclaim"]), left  # no mutex, no aside file
    assert json.loads(lock.read_text(encoding="utf-8"))["token"] == "H"


def test_witness_without_sentinel_exclusion_gives_two_holders(monkeypatch):
    """Non-vacuous: with `_flock` a no-op the same lstat schedule gives two holders."""
    _fired, _reclaimed, holders, _left = _interleave(monkeypatch, "lstat", flock_works=False)
    assert holders == ["H", "K"]


def test_release_waits_bounded_for_a_wedged_sentinel_then_reports(monkeypatch, capsys):
    """A sentinel held past the wait: release gives up in bounded time, reports, deletes nothing."""
    path = _lock_file()
    body = json.dumps({"pid": os.getpid(), "until": time.time() + 600, "token": "O"})
    path.write_text(body, encoding="utf-8")
    monkeypatch.setattr(locks, "_RELEASE_WAIT_S", 0.3)
    with locks._reclaim_exclusion(path) as held:
        assert held
        start = time.monotonic()
        locks._release(path, "O")
        spent = time.monotonic() - start
    assert 0.3 <= spent < 5
    assert path.read_text(encoding="utf-8") == body
    err = capsys.readouterr().err
    assert "release failed" in err.lower() and path.name in err


@pytest.mark.parametrize("body", ["", "{", "[]", "null", '{"token": "other"}', '{"token": null}'])
def test_release_never_deletes_a_lock_it_cannot_prove_ours(body):
    """Fail closed: empty, partial, odd or foreign body stays; nothing is reported as our lock."""
    path = _lock_file()
    path.write_text(body, encoding="utf-8")
    locks._release(path, "O")
    assert path.read_text(encoding="utf-8") == body


def test_release_of_our_lock_deletes_it_and_takes_the_sentinel(monkeypatch):
    path = _lock_file()
    path.write_text(json.dumps({"pid": os.getpid(), "token": "O"}), encoding="utf-8")
    ops = []
    real_flock = locks._flock
    monkeypatch.setattr(locks, "_flock", lambda fd, op: (ops.append(op), real_flock(fd, op))[1])
    locks._release(path, "O")
    assert not path.exists()
    assert ops and ops[0] & locks._LOCK_EX, ops


@pytest.mark.skipif(os.name != "nt", reason="Windows handle-delete path only (#1117)")
def test_windows_release_deletes_by_handle_not_name(monkeypatch):
    """#1117: O releasing by name after X handle-deletes O's stale inode drops H's fresh lock.

    X's Windows reclaim (`_drop_stale_inode_win` -> `_consume_handle`) deletes through a handle with
    POSIX semantics (frees the name) and never takes the `.<lock>.reclaim` sentinel, so the by-name
    `os.remove` at the tail of `_unlink_named_if` is not excluded: O's release deletes H's fresh lock
    and a third caller K acquires (`holders == ['H', 'K']` on the #1116 head). Deleting through a
    handle on the inode whose own bytes still carry O's token leaves H's file alone (`holders == ['H']`).
    """
    path = _lock_file()
    now = time.time()
    path.write_text(json.dumps({"card": "o", "pid": os.getpid(), "until": now - 1, "token": "O"}),
                    encoding="utf-8")
    holders: list[str] = []
    fired = {"value": False}
    real_consume = locks._consume_handle

    def consume_handle(target, pred):
        if target == path and not fired["value"]:
            fired["value"] = True
            assert locks._reclaim(path, "X")  # X handle-deletes O's stale inode (frees the name)
            _o_excl(path, "H", holders, now)  # H O_EXCLs a fresh lock
        return real_consume(target, pred)

    monkeypatch.setattr(locks, "_consume_handle", consume_handle)
    locks._release(path, "O")
    _o_excl(path, "K", holders, now)
    assert fired["value"], "O's release never reached the handle delete"
    assert holders == ["H"]
    assert json.loads(path.read_text(encoding="utf-8"))["token"] == "H"
