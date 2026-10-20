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
