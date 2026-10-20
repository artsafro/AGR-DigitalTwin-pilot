"""Synthetic guard: the default pytest selection excludes the opt-in `perf` lane.

Pattern: n/a | new-case: issue-361 perf marker excluded from the default addopts.
"""
import pytest


def test_perf_marker_registered(pytestconfig):
    markers = [str(m) for m in pytestconfig.getini("markers")]
    assert any(m.split(":", 1)[0].strip() == "perf" for m in markers)


def test_default_addopts_exclude_perf(pytestconfig):
    addopts = " ".join(pytestconfig.getini("addopts"))
    assert "not perf" in addopts


def test_measure_process_time_warmup_then_five_repeats(measure_process_time):
    """The perf gate runs the warm-up call first, then exactly `repeats` timed calls."""
    calls = []

    def fn():
        calls.append(len(calls))

    median, wall = measure_process_time(fn, warmup=2, repeats=5)
    assert calls == list(range(7))  # 2 warm-up calls, then 5 timed calls, in order
    assert isinstance(median, float) and median >= 0.0
    assert isinstance(wall, float) and wall >= 0.0
