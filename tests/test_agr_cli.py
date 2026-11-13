"""new-case: AGR aliases dispatch at the existing CLI subprocess boundary."""
import importlib
import sys
from unittest.mock import Mock


def test_inspect_forwards_exact_arguments(monkeypatch):
    agr = importlib.import_module("dt_ai.cli.agr")
    run = Mock(return_value=Mock(returncode=7))
    monkeypatch.setattr(agr.subprocess, "run", run)
    args = ["--manifest", "folder with spaces/job.json"]
    assert agr.main(["inspect", *args]) == 7
    run.assert_called_once_with([sys.executable, "-m", "dt_ai.cli.main", "inspect", *args], check=False)
