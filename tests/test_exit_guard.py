"""A hard exit inside the pytest process must turn the run red, never end it green (#red-main 9905d723).

Pattern: n/a | new-case: merge suites on main 9905d723 ended mid-run with exit 0 and no summary line.

`os._exit(0)` from test code skips pytest's summary and returns 0, so a suite runner reads "green".
The guard in `tests/exit_guard.py` (registered by `tests/conftest.py`) reports the call with the test id
and its stack and exits non-zero instead. On Windows `os.kill(pid, 0)` is not a liveness probe (it sends
CTRL_C_EVENT / TerminateProcess), so the guard refuses it inside the pytest process.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent

HARD_EXIT_MODULE = """\
import os


def test_before():
    pass


def test_hard_exit():
    os._exit(0)


def test_after():
    pass
"""


def _run_inner(tmp_path: Path, *plugin_args: str, module: str = HARD_EXIT_MODULE,
               conftest: str | None = None) -> subprocess.CompletedProcess:
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (tmp_path / "test_inner.py").write_text(module, encoding="utf-8")
    if conftest is not None:
        (tmp_path / "conftest.py").write_text(conftest, encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(TESTS), os.environ.get("PYTHONPATH", "")]))
    env.pop("PYTEST_ADDOPTS", None)
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "no:randomly", *plugin_args,
         "-c", str(tmp_path / "pytest.ini"), "--rootdir", str(tmp_path), str(tmp_path / "test_inner.py")],
        cwd=tmp_path, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )


def test_unguarded_hard_exit_reads_green_without_summary(tmp_path):
    """Control: the symptom of the red main - exit 0, no `passed` line, later tests never ran."""
    proc = _run_inner(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "passed" not in proc.stdout


def test_guard_turns_hard_exit_red_and_names_the_test(tmp_path):
    proc = _run_inner(tmp_path, "-p", "exit_guard")
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "os._exit(0)" in out, out
    assert "test_inner.py::test_hard_exit" in out, out
    assert "test_hard_exit" in out and "os._exit(0)" in proc.stderr, out


def test_suite_runs_under_the_guard():
    """The shared conftest registers the guard, so the full suite cannot end green on a hard exit."""
    assert getattr(os._exit, "__module__", None) == "exit_guard", os._exit


@pytest.mark.skipif(os.name != "nt", reason="os.kill(pid, 0) is a liveness probe on POSIX")
def test_guard_refuses_windows_kill_zero():
    with pytest.raises(RuntimeError, match="os.kill"):
        os.kill(os.getpid(), 0)


TEARDOWN_EXIT_MODULE = """\
import os

import pytest


@pytest.fixture
def exits_on_teardown():
    yield
    os._exit(0)


def test_teardown_exit(exits_on_teardown):
    pass


def test_after():
    pass
"""

NONZERO_EXIT_MODULE = """\
import os


def test_exit_five():
    os._exit(5)
"""

THREAD_EXIT_MODULE = """\
import os
import threading


def test_thread_exit():
    t = threading.Thread(target=os._exit, args=(0,))
    t.start()
    t.join(30)
"""

CHILD_EXIT_MODULE = """\
import multiprocessing
import os
import subprocess
import sys


def _child():
    os._exit(0)


def test_children_exit_zero():
    ctx = multiprocessing.get_context("spawn")
    p = ctx.Process(target=_child)
    p.start()
    p.join(60)
    assert p.exitcode == 0
    # a process that loads the guard but is not the guarded pytest process keeps its own exit code
    code = "import exit_guard, os; exit_guard._state['pid'] = -1; exit_guard._exit(0)"
    assert subprocess.run([sys.executable, "-c", code], timeout=60).returncode == 0
"""

SESSIONFINISH_CONFTEST = """\
import os


def pytest_sessionfinish(session, exitstatus):
    os._exit(0)
"""

PASSING_MODULE = """\
def test_ok():
    pass
"""


def test_guard_catches_exit_in_fixture_teardown(tmp_path):
    proc = _run_inner(tmp_path, "-p", "exit_guard", module=TEARDOWN_EXIT_MODULE)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 3, out
    assert "test_inner.py::test_teardown_exit" in proc.stderr, out


def test_guard_keeps_a_nonzero_exit_code(tmp_path):
    proc = _run_inner(tmp_path, "-p", "exit_guard", module=NONZERO_EXIT_MODULE)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 5, out
    assert "os._exit(5)" in proc.stderr, out


def test_guard_catches_exit_from_a_worker_thread(tmp_path):
    proc = _run_inner(tmp_path, "-p", "exit_guard", module=THREAD_EXIT_MODULE)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 3, out
    assert "test_inner.py::test_thread_exit" in proc.stderr, out


def test_guard_leaves_child_processes_alone(tmp_path):
    proc = _run_inner(tmp_path, "-p", "exit_guard", module=CHILD_EXIT_MODULE)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert "1 passed" in proc.stdout, out
    assert "exit_guard:" not in out, out


def test_guard_catches_exit_in_sessionfinish(tmp_path):
    proc = _run_inner(tmp_path, "-p", "exit_guard", module=PASSING_MODULE, conftest=SESSIONFINISH_CONFTEST)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 3, out
    assert "<no test running>" in proc.stderr, out
