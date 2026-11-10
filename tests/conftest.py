import statistics
import time
from pathlib import Path

import pytest

from dt_ai.core.io import read_json
from dt_ai.core.models import BuildJob

from basetemp_default import default_basetemp, is_inside

_BASETEMP_SOURCE = pytest.StashKey[str]()


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    """Use a short basetemp outside the repo unless ``--basetemp`` is given (#1035, [D063]).

    A given basetemp inside the repository (e.g. the shlex-mangled ``C:Users...pytest_tmp`` from a
    backslash ``PYTEST_ADDOPTS``) is replaced by the default, with a warning.
    """
    given = config.option.basetemp
    if given and not is_inside(given, config.rootpath):
        config.stash[_BASETEMP_SOURCE] = "--basetemp"
        return
    path = default_basetemp(config.rootpath)
    path.parent.mkdir(parents=True, exist_ok=True)  # pytest creates only the leaf
    config.option.basetemp = str(path)
    config.stash[_BASETEMP_SOURCE] = "default"
    if given:
        config.issue_config_time_warning(
            pytest.PytestConfigWarning(f"--basetemp {given!r} is inside the repository; using {path} (#1035)"),
            stacklevel=2,
        )


def pytest_report_header(config):
    return f"basetemp: {config.option.basetemp} ({config.stash.get(_BASETEMP_SOURCE, '--basetemp')})"


@pytest.fixture
def root():
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def job(root):
    return BuildJob.model_validate(read_json((root / "jobs/SYNTH-001/project.json").read_bytes()))


@pytest.fixture
def measure_process_time():
    """Return a perf-lane timer: one warm-up run, then the median CPU time of `repeats` runs.

    ``time.process_time()`` (CPU time of this process) is the gate; wall-clock time is
    returned only for reporting. Callers assert on the median CPU time, not on wall time.
    """
    def _measure(fn, warmup=1, repeats=5):
        for _ in range(warmup):
            fn()
        cpu = []
        wall_start = time.perf_counter()
        for _ in range(repeats):
            start = time.process_time()
            fn()
            cpu.append(time.process_time() - start)
        return statistics.median(cpu), time.perf_counter() - wall_start

    return _measure
