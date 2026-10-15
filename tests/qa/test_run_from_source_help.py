"""Tests for tools/qa/run_from_source.py CLI parser and --blender help."""
import argparse
import importlib.util
from pathlib import Path
import sys

import pytest

TARGET = Path(__file__).resolve().parents[2] / "tools" / "qa" / "run_from_source.py"


@pytest.fixture
def run_from_source(monkeypatch):
    monkeypatch.setattr(sys, "path", list(sys.path))
    spec = importlib.util.spec_from_file_location("tools.qa.run_from_source", TARGET)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_from_source_help_advertises_blender_policy(run_from_source, capsys):
    with pytest.raises(SystemExit) as exc_info:
        run_from_source.main(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    help_text = captured.out + captured.err
    assert "TWINQA_BLENDER" in help_text
    assert "5.1.2" in help_text
    assert "PATH" not in help_text
    assert "newest" not in help_text


def test_argparse_parser_preserves_explicit_blender(run_from_source, monkeypatch):
    original_parse_args = argparse.ArgumentParser.parse_args
    captured = []

    def wrapped_parse_args(self, *args, **kwargs):
        parsed = original_parse_args(self, *args, **kwargs)
        captured.append(parsed)
        raise SystemExit(0)

    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", wrapped_parse_args)

    argv = [
        "--dump", "synthetic-dump.json",
        "--modules", "synthetic-modules.json",
        "--object", "synthetic-object.json",
        "--tolerances", "synthetic-tolerances.json",
        "--output", "synthetic-output",
        "--blender", "X",
    ]

    with pytest.raises(SystemExit) as exc_info:
        run_from_source.main(argv)

    assert exc_info.value.code == 0
    assert len(captured) == 1
    assert captured[0].blender == "X"
