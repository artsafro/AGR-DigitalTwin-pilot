"""new-case: repository-wide job STATE start-here header contract (#1208)."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LABELS = ("Current run:", "Source:", "Next gate:")
STATE_FILES = sorted((ROOT / "jobs").glob("*/STATE.md"))


def assert_header(text: str) -> None:
    lines = text.splitlines()
    assert len(lines) >= 3, "Missing three-line STATE header"
    for label, line in zip(LABELS, lines[:3], strict=True):
        assert line.startswith(label), f"Expected {label!r}, got {line!r}"
        value = line[len(label):].strip()
        assert value, f"Empty {label}"
        if value.lower().startswith("unknown"):
            assert value.startswith("unknown — ") and value[10:].strip(), (
                f"{label} needs unknown — <why>"
            )


@pytest.mark.parametrize("path", STATE_FILES, ids=lambda path: path.parent.name)
def test_job_state_starts_with_header(path):
    assert_header(path.read_text(encoding="utf-8"))


def test_job_state_inventory_is_not_empty():
    assert STATE_FILES, "No jobs/*/STATE.md found; check repository root"
