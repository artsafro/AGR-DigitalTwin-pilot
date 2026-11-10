"""Pytest plugin: a hard exit inside the pytest process turns the run red instead of ending it green.

`os._exit(0)` skips pytest's summary and returns 0, so a suite runner reads a cut run as green (red main
9905d723: merge suites stopped at 19 % / 38 % with exit 0). Inside the pytest process this guard writes the
running test id and the caller's stack to stderr and exits with `HARD_EXIT_CODE` for code 0.
On Windows `os.kill(pid, 0)` is not a liveness probe (CTRL_C_EVENT / TerminateProcess), so it is refused.
Registered by `tests/conftest.py`; usable alone as `-p exit_guard`. Child processes are not affected.
"""
from __future__ import annotations

import os
import sys
import traceback
from typing import Any

HARD_EXIT_CODE = 3  # pytest's INTERNAL_ERROR: never 0
_REAL_EXIT = os._exit
_REAL_KILL = os.kill
_WINDOWS = os.name == "nt"
_state: dict[str, Any] = {"pid": None, "nodeid": None}


def _exit(code):
    if os.getpid() == _state["pid"]:
        stack = "".join(traceback.format_stack()[:-1])
        msg = (f"\nexit_guard: os._exit({code!r}) called inside the pytest process during "
               f"{_state['nodeid'] or '<no test running>'}; the run is red, not green.\n{stack}")
        capman = _state.get("capman")
        try:  # fd capture still owns fd 1/2 during a test: give them back so the message reaches the log
            if capman is not None:
                capman.stop_global_capturing()
        except Exception:
            pass
        try:
            os.write(2, msg.encode("utf-8", errors="replace"))
        except OSError:
            pass
        _REAL_EXIT(code if code else HARD_EXIT_CODE)
    _REAL_EXIT(code)


def _kill(pid, sig):
    if _WINDOWS and sig == 0 and os.getpid() == _state["pid"]:
        raise RuntimeError(f"exit_guard: os.kill({pid}, 0) on Windows sends CTRL_C_EVENT / TerminateProcess; "
                           "probe liveness with OpenProcess + GetExitCodeProcess instead")
    return _REAL_KILL(pid, sig)


_exit.__module__ = _kill.__module__ = "exit_guard"


def pytest_configure(config):
    _state["pid"] = os.getpid()
    _state["capman"] = config.pluginmanager.getplugin("capturemanager")
    os._exit = _exit
    os.kill = _kill


def pytest_runtest_logstart(nodeid, location):
    _state["nodeid"] = nodeid


def pytest_runtest_logfinish(nodeid, location):
    _state["nodeid"] = None


def pytest_unconfigure(config):
    os._exit = _REAL_EXIT
    os.kill = _REAL_KILL
    _state["pid"] = _state["capman"] = None


if __name__ == "__main__":  # pragma: no cover
    sys.exit("exit_guard is a pytest plugin: -p exit_guard")
