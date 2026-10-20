import statistics
import time
from pathlib import Path

import pytest

from dt_ai.core.io import read_json
from dt_ai.core.models import BuildJob


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
