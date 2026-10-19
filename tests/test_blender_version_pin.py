"""Contract tests for Blender version pin between runner and docs.

new-case: AST-only Blender baseline and documentation pin contract.
Ensures BLENDER_VERSION in src/dt_ai/core/blender_runner.py is extracted via AST
(never executing runner code or importing bpy) and matches the Version column of
the exact Tool=Blender row in docs/agents/CAPABILITIES.md, as well as the
identifiable bpy wheel pin rule.
"""
from __future__ import annotations

import ast
from pathlib import Path
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNNER_PATH = ROOT / "src" / "dt_ai" / "core" / "blender_runner.py"
DEFAULT_CAPABILITIES_PATH = ROOT / "docs" / "agents" / "CAPABILITIES.md"


def _read_runner_version(runner_path: Path) -> str:
    tree = ast.parse(runner_path.read_text(encoding="utf-8"), filename=str(runner_path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "BLENDER_VERSION":
                    return str(ast.literal_eval(node.value))
        elif isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "BLENDER_VERSION" and node.value:
            return str(ast.literal_eval(node.value))
    raise AssertionError(f"BLENDER_VERSION constant not found in {runner_path}")


def assert_blender_version_pin(
    runner_path: Path = DEFAULT_RUNNER_PATH,
    capabilities_path: Path = DEFAULT_CAPABILITIES_PATH,
) -> None:
    runner_version = _read_runner_version(runner_path)
    content = capabilities_path.read_text(encoding="utf-8")

    row_version: str | None = None
    for line in content.splitlines():
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cells and cells[0] == "Blender" and len(cells) > 1:
                m = re.match(r"^(\d+\.\d+\.\d+)", cells[1])
                row_version = m.group(1) if m else cells[1]
                break

    if row_version is None:
        raise AssertionError(f"Tool=Blender row not found in smoke table of {capabilities_path}")
    if row_version != runner_version:
        raise AssertionError(
            f"Blender table row version mismatch: runner has {runner_version}, table has {row_version}"
        )

    pin_lines = [l.strip() for l in content.splitlines() if "bpy wheel pin rule" in l.lower()]
    if not pin_lines:
        raise AssertionError(f"missing bpy pin rule: no pin line in {capabilities_path}")
    pin_line = pin_lines[0]

    if "`BLENDER_VERSION` in `src/dt_ai/core/blender_runner.py`" not in pin_line:
        raise AssertionError(f"missing bpy pin rule source reference: {pin_line}")
    if not ("must equal" in pin_line.lower() and "baseline" in pin_line.lower()):
        raise AssertionError(f"missing bpy pin rule 'must equal baseline' phrase: {pin_line}")
    if "re-verified on each blender upgrade" not in pin_line.lower():
        raise AssertionError(f"missing bpy pin rule 're-verified on each Blender upgrade' phrase: {pin_line}")

    m_pin = re.search(r"\b(\d+\.\d+\.\d+)\b", pin_line)
    if not m_pin:
        raise AssertionError(f"missing bpy pin rule version in: {pin_line}")
    pin_version = m_pin.group(1)
    if pin_version != runner_version:
        raise AssertionError(
            f"bpy wheel pin rule version mismatch: runner has {runner_version}, pin has {pin_version}"
        )


def test_matching_blender_version_pin_passes(tmp_path: Path) -> None:
    """Synthetic runner with poison code passes via AST parsing without execution."""
    runner = tmp_path / "blender_runner.py"
    runner.write_text("import bpy\nraise RuntimeError('poison')\nBLENDER_VERSION = '5.1.2'\n", encoding="utf-8")
    cap = tmp_path / "CAPABILITIES.md"
    cap.write_text(
        "| Tool | Version |\n| Blender | 5.1.2 (hash ec6e62d40fa9) |\n\n"
        "- bpy wheel pin rule: a bpy wheel lane, if used, must equal the baseline Blender version "
        "5.1.2 (`BLENDER_VERSION` in `src/dt_ai/core/blender_runner.py`) and is re-verified on each Blender upgrade.\n",
        encoding="utf-8",
    )
    assert_blender_version_pin(runner, cap)
    assert "bpy" not in sys.modules


def test_repository_blender_version_pin() -> None:
    """Repository BLENDER_VERSION matches CAPABILITIES row and pin rule."""
    assert "bpy" not in sys.modules
    assert_blender_version_pin(DEFAULT_RUNNER_PATH, DEFAULT_CAPABILITIES_PATH)


def test_blender_row_version_mismatch(tmp_path: Path) -> None:
    """Changing only the smoke table row to 5.2.2 leaves other 5.1.2 mentions intact and fails."""
    content = DEFAULT_CAPABILITIES_PATH.read_text(encoding="utf-8")
    cap = tmp_path / "CAPABILITIES.md"
    cap.write_text(content.replace("| Blender | 5.1.2", "| Blender | 5.2.2", 1), encoding="utf-8")
    with pytest.raises(AssertionError) as exc_info:
        assert_blender_version_pin(DEFAULT_RUNNER_PATH, cap)
    msg = str(exc_info.value)
    assert "5.1.2" in msg and "5.2.2" in msg


def test_missing_bpy_pin_rule(tmp_path: Path) -> None:
    """Removing the pin rule line triggers missing bpy pin rule assertion."""
    content = DEFAULT_CAPABILITIES_PATH.read_text(encoding="utf-8")
    lines = [l for l in content.splitlines(keepends=True) if "bpy wheel pin rule" not in l.lower()]
    cap = tmp_path / "CAPABILITIES.md"
    cap.write_text("".join(lines), encoding="utf-8")
    with pytest.raises(AssertionError) as exc_info:
        assert_blender_version_pin(DEFAULT_RUNNER_PATH, cap)
    assert "missing bpy pin rule" in str(exc_info.value).lower()


def test_bpy_pin_version_mismatch(tmp_path: Path) -> None:
    """Changing only the pin rule version to 5.2.2 fails naming both versions."""
    content = DEFAULT_CAPABILITIES_PATH.read_text(encoding="utf-8")
    lines = [
        l.replace("5.1.2", "5.2.2", 1) if "bpy wheel pin rule" in l.lower() else l
        for l in content.splitlines(keepends=True)
    ]
    cap = tmp_path / "CAPABILITIES.md"
    cap.write_text("".join(lines), encoding="utf-8")
    with pytest.raises(AssertionError) as exc_info:
        assert_blender_version_pin(DEFAULT_RUNNER_PATH, cap)
    msg = str(exc_info.value)
    assert "5.1.2" in msg and "5.2.2" in msg
