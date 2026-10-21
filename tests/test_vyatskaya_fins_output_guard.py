"""Synthetic checks of the build_fins.py output-version guard (PR #392 P1).

The default output ``outputs/build-v003-fins`` must never be overwritten on a re-run:
an existing, non-empty output version is refused with an error that names the next free
version; a fresh or empty directory keeps the existing behaviour. These tests use
synthetic sentinel files under ``tmp_path`` only, never under ``jobs/*/outputs``.
"""
import importlib.util
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "jobs" / "vyatskaya-tow02" / "scripts"
_spec = importlib.util.spec_from_file_location("build_fins", SCRIPTS / "build_fins.py")
build_fins = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_fins)


def test_fresh_output_dir_is_created(tmp_path):
    out = tmp_path / "outputs" / "build-v014-fins"
    build_fins.ensure_output_available(out)
    assert out.is_dir()


def test_empty_existing_output_dir_is_reused(tmp_path):
    out = tmp_path / "outputs" / "build-v014-fins"
    out.mkdir(parents=True)
    build_fins.ensure_output_available(out)
    assert out.is_dir()
    assert list(out.iterdir()) == []


def test_nonempty_output_dir_is_refused_and_preserved(tmp_path):
    outputs = tmp_path / "outputs"
    prior = outputs / "build-v003-fins"
    prior.mkdir(parents=True)
    sentinel = prior / "fins.obj"
    sentinel.write_text("original accepted export", encoding="utf-8")
    with pytest.raises(FileExistsError) as exc_info:
        build_fins.ensure_output_available(prior)
    assert sentinel.read_text(encoding="utf-8") == "original accepted export"
    assert list(outputs.iterdir()) == [prior]


def test_refusal_names_next_free_version_skipping_master(tmp_path):
    outputs = tmp_path / "outputs"
    prior = outputs / "build-v003-fins"
    prior.mkdir(parents=True)
    (prior / "fins.obj").write_text("original", encoding="utf-8")
    (outputs / "build-v013").mkdir(parents=True)  # master build, not a fins output
    with pytest.raises(FileExistsError, match="build-v014-fins"):
        build_fins.ensure_output_available(prior)


def test_next_free_version_empty_outputs(tmp_path):
    assert build_fins.next_free_fins_version(tmp_path / "outputs") == "build-v001-fins"


def test_next_free_version_skips_master_build(tmp_path):
    outputs = tmp_path / "outputs"
    for name in ("build-v003-fins", "build-v012-fins", "build-v013"):
        (outputs / name).mkdir(parents=True)
    assert build_fins.next_free_fins_version(outputs) == "build-v014-fins"


def test_output_path_that_is_a_file_is_refused(tmp_path):
    out = tmp_path / "outputs" / "build-v003-fins"
    out.parent.mkdir(parents=True)
    out.write_text("not a directory", encoding="utf-8")
    with pytest.raises(FileExistsError):
        build_fins.ensure_output_available(out)


# ------------------------------------------------------------------------------------------- main() guard
# The helpers above only prove the guard API works. PR #392 P2: the publication entry point must
# call it. These tests invoke the real ``main()`` with OUT/MEAS pointed at synthetic paths so a
# reviewer mutation that removes the guard call from ``main()`` (while keeping the helpers) fails.
def _point_paths(monkeypatch, tmp_path):
    """Point ``build_fins.OUT``/``MEAS`` at synthetic paths under ``tmp_path`` (never real job outputs)."""
    out = tmp_path / "outputs" / "build-v003-fins"
    meas = tmp_path / "outputs" / "measure-v001"
    monkeypatch.setattr(build_fins, "OUT", out)
    monkeypatch.setattr(build_fins, "MEAS", meas)
    return out, meas


def test_main_refuses_occupied_output_before_measurement(monkeypatch, tmp_path):
    out, _ = _point_paths(monkeypatch, tmp_path)
    out.mkdir(parents=True)
    sentinels = {
        "fins.obj": b"OBJ original accepted export\n",
        "fins.mtl": b"MTL original accepted export\n",
        "fins_summary.json": b'{"original": "accepted export"}\n',
        "fins_elevation.png": b"PNG original accepted export\n",
    }
    for name, data in sentinels.items():
        (out / name).write_bytes(data)
    # MEAS is left non-existent: if main() read any measurement before the guard, the missing
    # fins.json would raise FileNotFoundError first. A FileExistsError therefore proves the guard
    # refuses BEFORE any measurement access; the sentinels must survive byte-for-byte.
    # The guard must be idempotent: every repeated re-run on the occupied output (E3) refuses the
    # same way and never touches the sentinels, so invoke the publication entry point 3 times and
    # re-check the bytes after each refusal (matches the independent reviewer's 3/3 probe).
    for _ in range(3):
        with pytest.raises(FileExistsError):
            build_fins.main()
        for name, data in sentinels.items():
            assert (out / name).read_bytes() == data
        assert sorted(p.name for p in out.iterdir()) == sorted(sentinels)


def test_main_reaches_measurement_for_fresh_output(monkeypatch, tmp_path):
    out, _ = _point_paths(monkeypatch, tmp_path)
    # A fresh (missing) output is created by the guard, then main() proceeds to the measurement
    # read; the synthetic MEAS is absent, so the first measurement read raises FileNotFoundError.
    with pytest.raises(FileNotFoundError):
        build_fins.main()
    assert out.is_dir()
    assert list(out.iterdir()) == []


def test_main_reaches_measurement_for_empty_output(monkeypatch, tmp_path):
    out, _ = _point_paths(monkeypatch, tmp_path)
    out.mkdir(parents=True)
    # An existing-but-empty output is reused (not refused), then main() reaches the measurement read.
    with pytest.raises(FileNotFoundError):
        build_fins.main()
    assert out.is_dir()
    assert list(out.iterdir()) == []
