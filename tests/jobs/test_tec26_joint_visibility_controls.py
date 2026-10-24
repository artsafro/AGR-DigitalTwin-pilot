"""new-case: joint_count visibility and finite-sample boundary controls.

Characterization is baseline GREEN, not historical RED: the checks below describe the
current count_joints contract on synthetic 1-D profiles. A joint is visible only where a
finite panel sample falls inside the closed window abs(s - e) <= max(tol, 0.006). Fewer
than 10 finite luminance samples refuse the row. No assets and no DCC.
"""
import importlib.util
import types
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
JOINT_COUNT_PATH = ROOT / "jobs" / "TEC26-OKS" / "scripts" / "joint_count.py"
FIELD_LO, FIELD_HI, RIBS = -1.0, 1.0, 2
VISIBLE_FLOOR = 0.006
REFUSAL = "no panel samples on this row"
VISIBILITY_OLD = "<= max(tol, 0.006)"
VISIBILITY_NEW = "< max(tol, 0.006)"
COUNT_OLD = "ok.sum() < 10"
COUNT_NEW = "ok.sum() <= 10"


def load_joint_count():
    spec = importlib.util.spec_from_file_location("joint_count_visibility_controls", JOINT_COUNT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def module_from_source(source, name):
    module = types.ModuleType(name)
    exec(compile(source, str(JOINT_COUNT_PATH), "exec"), module.__dict__)
    return module


def replace_once(source, old, new):
    assert source.count(old) == 1
    assert source.count(new) == 0
    mutated = source.replace(old, new, 1)
    assert mutated.count(old) == 0
    assert mutated.count(new) == 1
    return mutated


def _wings(n_each_side=5):
    left = np.linspace(-0.9, -0.1, n_each_side)
    right = np.linspace(0.1, 0.9, n_each_side)
    wings = np.concatenate([left, right])
    assert np.all(np.abs(wings) >= 0.1)
    assert np.all(np.diff(wings) > 0)
    return wings


def bright_profile(probe, tol):
    """Sorted bright finite samples. Wings stay outside the visibility window; probe may sit on it."""
    wings = _wings()
    window = max(float(tol), VISIBLE_FLOOR)
    assert np.all(np.abs(wings) > window)
    parts = [wings] if probe is None else [wings, np.asarray([probe], dtype=float)]
    s = np.sort(np.concatenate(parts))
    assert np.all(np.diff(s) > 0)
    lum = np.ones(s.shape, dtype=float)
    assert np.isfinite(lum).all() and lum.min() == 1.0
    return s, lum


def report(mod, s, lum, tol):
    return mod.count_joints(s, lum, FIELD_LO, FIELD_HI, RIBS, tol)


def assert_hidden_joint(mod, s, lum, tol):
    got = report(mod, s, lum, tol)
    assert got["hidden_by_other_finish"] == [0.0]
    assert got["missing"] == []
    assert got["extra"] == []
    assert got["found_m"] == []
    assert got["joints_found"] == 0
    assert got["joints_expected"] == 1
    assert got["ribs_expected"] == RIBS
    assert got["pitch_m"] == 1.0
    assert got["ok"] is True
    assert "reason" not in got


def assert_boundary_sample_is_missing(mod, s, lum, tol):
    got = report(mod, s, lum, tol)
    assert got["missing"] == [0.0]
    assert got["hidden_by_other_finish"] == []
    assert got["extra"] == []
    assert got["found_m"] == []
    assert got["joints_found"] == 0
    assert got["joints_expected"] == 1
    assert got["ok"] is False
    assert "reason" not in got


def clean_dark_profile(n_each_side):
    """Bright wings plus one dark run whose sample positions are symmetric about 0."""
    half = np.float64(1 / 256)  # exact dyadic, strictly inside the 6 mm floor
    dark = np.array([-half, half])
    assert float(dark.mean()) == 0.0
    assert abs(float(half)) < VISIBLE_FLOOR
    wings = _wings(n_each_side)
    s = np.concatenate([wings[:n_each_side], dark, wings[n_each_side:]])
    assert np.all(np.diff(s) > 0)
    lum = np.ones(s.shape, dtype=float)
    lum[(s == -half) | (s == half)] = 0.0
    assert int(np.isfinite(lum).sum()) == s.size
    assert int((lum == 0.0).sum()) == 2
    return s, lum


def assert_clean_joint(mod, s, lum, tol=0.003):
    got = report(mod, s, lum, tol)
    assert "reason" not in got
    assert got["ok"] is True
    assert got["joints_found"] == 1
    assert got["joints_expected"] == 1
    assert got["found_m"] == [0.0]
    assert got["missing"] == []
    assert got["hidden_by_other_finish"] == []
    assert got["extra"] == []
    assert got["pitch_m"] == 1.0
    assert got["first_joint_from_field_m"] == 1.0
    assert got["last_joint_to_field_m"] == 1.0
    assert got["max_position_error_m"] == 0.0


def assert_row_refused(mod, s, lum):
    got = report(mod, s, lum, 0.003)
    assert got["ok"] is False
    assert got["reason"] == REFUSAL
    assert got["found"] == []
    assert got["expected"] == 1


def test_no_sample_inside_window_is_hidden():
    """tol=0.003, samples only at |s|>=0.1: the joint at 0 is hidden, not missing."""
    mod = load_joint_count()
    tol = 0.003
    s, lum = bright_profile(None, tol)
    window = max(tol, VISIBLE_FLOOR)
    assert s.size >= 10
    assert np.all(np.abs(s) >= 0.1)
    assert not np.any(np.abs(s - 0.0) <= window)
    assert_hidden_joint(mod, s, lum, tol)


def test_sample_on_the_closed_window_is_missing():
    """A bright sample at exactly max(tol, 0.006) makes the joint visible and missing."""
    mod = load_joint_count()
    cases = ((0.003, np.float64(0.006), 0.006), (0.012, np.float64(0.012), 0.012))
    for tol, probe, literal in cases:
        s, lum = bright_profile(probe, tol)
        window = max(tol, VISIBLE_FLOOR)
        inside = np.abs(s - 0.0) <= window
        assert int(inside.sum()) == 1
        distance = abs(float(s[inside][0]) - 0.0)
        assert distance == literal
        assert distance == window
        assert_boundary_sample_is_missing(mod, s, lum, tol)


def test_next_float_outside_the_window_is_hidden():
    """np.nextafter of the closed edge is strictly outside, so the joint stays hidden."""
    mod = load_joint_count()
    cases = ((0.003, np.float64(0.006)), (0.012, np.float64(0.012)))
    for tol, edge in cases:
        probe = np.nextafter(edge, np.inf)
        window = max(tol, VISIBLE_FLOOR)
        distance = abs(float(probe) - 0.0)
        assert probe > edge
        assert distance > edge
        assert distance > window
        s, lum = bright_profile(probe, tol)
        assert not np.any(np.abs(s - 0.0) <= window)
        nearest = float(s[np.argmin(np.abs(s - 0.0))])
        assert abs(nearest - 0.0) == distance
        assert abs(nearest - 0.0) > window
        assert_hidden_joint(mod, s, lum, tol)


def test_clean_dark_run_centred_at_zero_is_found():
    mod = load_joint_count()
    s, lum = clean_dark_profile(n_each_side=5)
    assert s.size >= 10 and int(np.isfinite(lum).sum()) >= 10
    assert_clean_joint(mod, s, lum)


def test_finite_sample_count_boundary():
    """Nine finite samples refuse the row. Ten finite samples with a dark run at 0 report the joint."""
    mod = load_joint_count()
    s9 = np.linspace(-0.9, 0.9, 12)
    lum9 = np.ones(s9.shape, dtype=float)
    lum9[-3:] = np.nan
    assert int(np.isfinite(lum9).sum()) == 9
    assert_row_refused(mod, s9, lum9)

    s10, lum10 = clean_dark_profile(n_each_side=4)
    assert s10.size == 10 and int(np.isfinite(lum10).sum()) == 10
    assert_clean_joint(mod, s10, lum10)

    assert bool(np.isfinite(np.inf)) is False
    for bad in (np.inf, np.nan):
        s = np.linspace(-0.9, 0.9, 10)
        lum = np.ones(s.shape, dtype=float)
        lum[-1] = bad
        assert int(np.isfinite(lum).sum()) == 9
        assert_row_refused(mod, s, lum)


def test_mutants_flip_only_the_probed_boundary():
    """Process-local mutants: one operator each, exec'd in a fresh module, production file untouched."""
    source = JOINT_COUNT_PATH.read_text(encoding="utf-8")
    real = load_joint_count()
    visibility = module_from_source(replace_once(source, VISIBILITY_OLD, VISIBILITY_NEW), "joint_count_vis_mutant")
    counted = module_from_source(replace_once(source, COUNT_OLD, COUNT_NEW), "joint_count_count_mutant")

    for tol, probe in ((0.003, np.float64(0.006)), (0.012, np.float64(0.012))):
        s, lum = bright_profile(probe, tol)
        window = max(tol, VISIBLE_FLOOR)
        inside = np.abs(s - 0.0) <= window
        assert int(inside.sum()) == 1
        assert abs(float(s[inside][0]) - 0.0) == window
        assert_boundary_sample_is_missing(real, s, lum, tol)
        with pytest.raises(AssertionError):
            assert_boundary_sample_is_missing(visibility, s, lum, tol)
        flipped = report(visibility, s, lum, tol)
        assert flipped["hidden_by_other_finish"] == [0.0]
        assert flipped["missing"] == []
        assert flipped["joints_found"] == 0
        assert flipped["found_m"] == []
        assert flipped["ok"] is True

    s10, lum10 = clean_dark_profile(n_each_side=4)
    assert int(np.isfinite(lum10).sum()) == 10
    assert_clean_joint(real, s10, lum10)
    with pytest.raises(AssertionError):
        assert_clean_joint(counted, s10, lum10)
    refused = report(counted, s10, lum10, 0.003)
    assert refused["ok"] is False
    assert refused["reason"] == REFUSAL
    assert refused["found"] == []
    assert refused["expected"] == 1
