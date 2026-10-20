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
