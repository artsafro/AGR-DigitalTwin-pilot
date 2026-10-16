"""Boundary regression tests: root Unreal/ directory removal and project log scoping (#2)."""
import glob
import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AGENT_FEED_PATH = ROOT / "tools" / "herdr" / "agent_feed.py"

PROBE_LOG_FILES = [
    "logs/a.log",
    "logs/nested/b.log",
    "tools/nested/c.log",
    "Unreal/Game/Saved/Logs/old.log",
]


def load_agent_feed():
    spec = importlib.util.spec_from_file_location("agent_feed", AGENT_FEED_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_unreal_repository_boundary():
    assert not (ROOT / "Unreal").exists(), "Root Unreal/ directory must be absent"
    module = load_agent_feed()
    assert module.PROJECT_LOGS == [
        "logs/**/*.log",
        "tools/**/*.log",
    ], "PROJECT_LOGS must only contain logs/**/*.log and tools/**/*.log"


@pytest.mark.parametrize(
    ("rel_path", "expected_match"),
    [
        ("logs/a.log", True),
        ("logs/nested/b.log", True),
        ("tools/nested/c.log", True),
        ("Unreal/Game/Saved/Logs/old.log", False),
    ],
)
def test_project_logs_filesystem_probe(tmp_path, rel_path, expected_match):
    for path_str in PROBE_LOG_FILES:
        target = tmp_path / path_str
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"log data for {path_str}\n", encoding="utf-8")

    module = load_agent_feed()
    matched = {
        Path(f).resolve().relative_to(tmp_path.resolve()).as_posix()
        for pat in module.PROJECT_LOGS
        for f in glob.glob(os.path.join(str(tmp_path), pat), recursive=True)
    }
    assert (
        (rel_path in matched) is expected_match
    ), f"Expected {rel_path} matched={expected_match}, but found matched={sorted(matched)}"
