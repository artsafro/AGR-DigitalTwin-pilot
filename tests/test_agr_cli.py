"""new-case: AGR aliases dispatch at the existing CLI subprocess boundary."""
import importlib
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.mark.parametrize("alias,prefix", [
    ("package-vpm", ["derive", "package"]),
    ("ground", ["ground", "v015"]),
    ("validate", None),
])
def test_single_step_aliases(alias, prefix, monkeypatch):
    agr = importlib.import_module("dt_ai.cli.agr")
    run = Mock(return_value=Mock(returncode=2))
    monkeypatch.setattr(agr.subprocess, "run", run)
    args = ["input file", "--option", "NaN", "--option", "inf", "--", "literal"]
    assert agr.main([alias, *args]) == 2
    expected = ([sys.executable, "-m", "dt_ai.cli.main", *prefix] if prefix else
                [sys.executable, str(Path(agr.__file__).resolve().parents[3] / "tools/qa/validate_package.py")])
    run.assert_called_once_with([*expected, *args], check=False)


@pytest.mark.parametrize("statuses,expected,calls", [([0, 0], 0, 2), ([3], 3, 1), ([0, 5], 5, 2)])
def test_npm_chain_forwards_separate_arguments(statuses, expected, calls, monkeypatch):
    agr = importlib.import_module("dt_ai.cli.agr")
    run = Mock(side_effect=[Mock(returncode=s) for s in statuses])
    monkeypatch.setattr(agr.subprocess, "run", run)
    atlas = ["spec.json", "new atlas", "--recipe-dir", "recipes"]
    npm = ["master.fbx", "spec.json", "new atlas", "export", "0000_Test"]
    assert agr.main(["vpm-to-npm", "--blender", "blender.exe", *atlas, "--then-npm", *npm]) == expected
    expected_args = [
        [sys.executable, "-m", "dt_ai.cli.main", "derive", "atlas", *atlas],
        [sys.executable, "-m", "dt_ai.cli.main", "derive", "--blender", "blender.exe", "npm", *npm],
    ]
    assert run.call_count == calls
    assert [c.args[0] for c in run.call_args_list] == expected_args[:calls]


@pytest.mark.parametrize("args", [[], ["a"], ["--then-npm", "n"], ["a", "--then-npm"],
                                      ["a", "--then-npm", "n", "--then-npm", "x"], ["--blender"]])
def test_partial_chain_does_not_start(args, monkeypatch, capsys):
    agr = importlib.import_module("dt_ai.cli.agr")
    run = Mock()
    monkeypatch.setattr(agr.subprocess, "run", run)
    assert agr.main(["vpm-to-npm", *args]) == 2
    run.assert_not_called()
    assert "dt derive" in capsys.readouterr().err


@pytest.mark.parametrize("command,pointer", [
    ("unwrap-atlas", "dt derive atlas"), ("delivery-export", "dt derive npm"),
    ("open-in-max", "routes/npm-oks.md"), ("contact-renders", "routes/npm-oks.md"),
    ("unknown", "agr --help"), ("", "agr --help"), ("NaN", "agr --help"),
])
def test_unsupported_fails_closed_with_pointer(command, pointer, monkeypatch, capsys):
    agr = importlib.import_module("dt_ai.cli.agr")
    run = Mock()
    monkeypatch.setattr(agr.subprocess, "run", run)
    assert agr.main([command, "--help"]) == 2
    assert pointer in capsys.readouterr().err
    run.assert_not_called()


def test_help_lists_all_eleven_commands(capsys):
    agr = importlib.import_module("dt_ai.cli.agr")
    assert agr.main(["--help"]) == 0
    out = capsys.readouterr().out
    for command in ["inspect", "vpm-to-npm", "package-vpm", "validate", "ground", "unwrap-atlas",
                    "delivery-export", "open-in-max", "contact-renders", "brick-seams", "ucx"]:
        assert command in out


def test_empty_invocation_is_an_error(capsys):
    agr = importlib.import_module("dt_ai.cli.agr")
    assert agr.main([]) == 2
    assert "agr --help" in capsys.readouterr().err


def test_launch_error_is_nonzero(monkeypatch, capsys):
    agr = importlib.import_module("dt_ai.cli.agr")
    monkeypatch.setattr(agr.subprocess, "run", Mock(side_effect=OSError("missing executable")))
    assert agr.main(["inspect", "--manifest", "job.json"]) == 2
    assert "missing executable" in capsys.readouterr().err


def test_chain_help_is_read_only(monkeypatch, capsys):
    agr = importlib.import_module("dt_ai.cli.agr")
    run = Mock()
    monkeypatch.setattr(agr.subprocess, "run", run)
    assert agr.main(["vpm-to-npm", "--help"]) == 0
    assert "--then-npm" in capsys.readouterr().out
    run.assert_not_called()


@pytest.mark.parametrize("status", range(1, 65))
def test_generated_failure_statuses_stop_chain(status, monkeypatch):
    agr = importlib.import_module("dt_ai.cli.agr")
    run = Mock(return_value=Mock(returncode=status))
    monkeypatch.setattr(agr.subprocess, "run", run)
    assert agr.main(["vpm-to-npm", "s", "a", "--then-npm", "m", "s", "a", "o", "p"]) == status
    assert run.call_count == 1


@pytest.mark.parametrize("command", ["inspect", "package-vpm", "ground", "validate"])
def test_fresh_process_help(command):
    import subprocess
    result = subprocess.run([sys.executable, "-m", "dt_ai.cli.agr", command, "--help"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout


@pytest.mark.parametrize("command", ["unwrap-atlas", "delivery-export", "open-in-max", "contact-renders", "brick-seams", "unknown"])
def test_fresh_process_refusal_writes_nothing(command, tmp_path):
    import subprocess
    source = tmp_path / "input.json"
    source.write_text("immutable synthetic input")
    # Same input/output, predictable partial name, repeated inputs and non-finite tokens:
    # stubs must refuse before any of these can reach a writer.
    partial = tmp_path / "input.json.partial"
    partial.write_text("foreign partial")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    result = subprocess.run([sys.executable, "-m", "dt_ai.cli.agr", command, str(source),
                             str(source), "--out", str(source), "NaN", "inf", "0"],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 2
    if command == 'brick-seams':
        assert 'error:' in result.stderr
    else:
        assert "ERROR:" in result.stderr
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_accepted_route_and_entry_links():
    import json
    import tomllib
    root = Path(__file__).resolve().parents[1]
    config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert config["project"]["scripts"]["agr"] == "dt_ai.cli.agr:main"
    cells = json.loads((root / "docs/scenarios/scenarios.json").read_text(encoding="utf-8"))["cells"]
    cell = next(c for c in cells if c["id"] == "oks-npm")
    assert cell["card"] == "routes/npm-oks.md"
    assert cell["status"] == "ready"
    route = (root / cell["card"]).read_text(encoding="utf-8")
    assert "Accepted" in route and "[D271]" in route
    assert "Headless **Blender first**" not in route
    assert "per step" in route and "Max 2026" in route and "quad" in route
    for entry in ["AGENTS.md", "CLAUDE.md", "GEMINI.md", "docs/agents/codex.md"]:
        text = (root / entry).read_text(encoding="utf-8")
        assert "routes/npm-oks.md" in text and "agr --help" in text
    decisions = (root / "docs/decisions.md").read_text(encoding="utf-8")
    row = next(line for line in decisions.splitlines() if line.startswith("| D271 |"))
    assert all(word in row for word in ["NPM/OKS", "aliases", "microbenchmark", "$10", "#1317"])


def test_inspect_forwards_exact_arguments(monkeypatch):
    agr = importlib.import_module("dt_ai.cli.agr")
    run = Mock(return_value=Mock(returncode=7))
    monkeypatch.setattr(agr.subprocess, "run", run)
    args = ["--manifest", "folder with spaces/job.json"]
    assert agr.main(["inspect", *args]) == 7
    run.assert_called_once_with([sys.executable, "-m", "dt_ai.cli.main", "inspect", *args], check=False)


# --- agr dispatch (RED before #1404: the stub returned 2 with a pointer) ---------------------------------------
def test_agr_ucx_is_a_real_command(capsys):
    agr = importlib.import_module("dt_ai.cli.agr")
    assert "ucx" not in agr.STUBS
    assert agr.main(["ucx", "--help"]) == 0
    out = capsys.readouterr().out
    assert "ucx_build" in out and "ucx10_core" in out and "V010" in out


def test_agr_ucx_dispatches_to_command(monkeypatch):
    agr = importlib.import_module("dt_ai.cli.agr")
    main = Mock(return_value=1)
    monkeypatch.setattr("dt_ai.geometry.ucx_command.main", main)
    assert agr.main(["ucx", "a.fbx", "b.fbx", "Main", "cell=0.5"]) == 1
    main.assert_called_once_with(["a.fbx", "b.fbx", "Main", "cell=0.5"])
