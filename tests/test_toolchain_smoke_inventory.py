"""Document contract tests for the Headless toolchain smoke check in docs/agents/CAPABILITIES.md.

Task #139: Headless toolchain smoke inventory contract.
Verifies the existence and structure of the 'Headless toolchain smoke check' section,
its required table columns, coverage of required tools, the explicit autocad-mcp note,
and the 'Not used, by decision' exclusions.
Tests are strictly independent of live installed tools, host OS, and run dates.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPABILITIES = ROOT / "docs" / "agents" / "CAPABILITIES.md"

SECTION_TITLE = "Headless toolchain smoke check"
REQUIRED_COLUMNS = [
    "Tool",
    "Version",
    "Command used",
    "Result (works / fails + error line)",
    "Date checked",
]

REQUIRED_TOOLS = [
    "PyMuPDF",
    "ezdxf",
    "CheckToolBox",
    "speedtree-mcp",
    "AutoCAD core console",
    "3ds Max batch",
    "Blender",
    "autocad-mcp",
]


def smoke_check_section(text: str | None = None) -> str:
    """Extract the 'Headless toolchain smoke check' section from CAPABILITIES.md."""
    content = CAPABILITIES.read_text(encoding="utf-8") if text is None else text
    pattern = rf"^#{{2,3}}\s+{re.escape(SECTION_TITLE)}\b(.*?)(?=^#{{2,3}}\s|\Z)"
    match = re.search(pattern, content, re.M | re.S)
    assert match, f"CAPABILITIES.md has no '{SECTION_TITLE}' section heading"
    return match.group(1)


def smoke_check_table(text: str | None = None) -> tuple[list[str], dict[str, dict[str, str]]]:
    """Parse the markdown table from the smoke check section into columns and tool-keyed rows."""
    section = smoke_check_section(text)
    table_lines = [line.strip() for line in section.splitlines() if line.strip().startswith("|")]
    assert len(table_lines) >= 3, f"The '{SECTION_TITLE}' section has no markdown table"

    headers = [c.strip() for c in table_lines[0].strip("|").split("|")]
    assert headers == REQUIRED_COLUMNS, (
        f"Smoke check table column mismatch.\nExpected: {REQUIRED_COLUMNS}\nGot: {headers}"
    )

    rows: dict[str, dict[str, str]] = {}
    for line in table_lines[2:]:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        assert len(cells) == len(REQUIRED_COLUMNS), f"Row column count mismatch: {line}"
        row_dict = dict(zip(headers, cells))
        tool_name = cells[0].replace("`", "").strip()
        rows[tool_name] = row_dict

    return headers, rows


def find_tool_row(rows: dict[str, dict[str, str]], tool_name: str) -> dict[str, str] | None:
    """Find a row matching the tool name (exact or contained/case-insensitive)."""
    norm = tool_name.strip().lower()
    for key, row in rows.items():
        k_norm = key.strip().lower()
        if k_norm == norm or norm in k_norm:
            return row
    return None


def test_smoke_check_section_heading_exists() -> None:
    """Test 1: Section heading 'Headless toolchain smoke check' exists in CAPABILITIES.md."""
    section = smoke_check_section()
    assert section.strip(), f"'{SECTION_TITLE}' section in CAPABILITIES.md is empty"


def test_smoke_check_table_columns_contract() -> None:
    """Test 2: Table has exact required columns: Tool | Version | Command used | Result (works / fails + error line) | Date checked."""
    headers, rows = smoke_check_table()
    assert headers == REQUIRED_COLUMNS
    assert len(rows) >= len(REQUIRED_TOOLS), (
        f"Table must have at least {len(REQUIRED_TOOLS)} rows, found {len(rows)}"
    )


def test_smoke_check_rows_cover_required_tools() -> None:
    """Test 3: Rows cover PyMuPDF, ezdxf, CheckToolBox, speedtree-mcp, AutoCAD core console, 3ds Max batch, Blender, autocad-mcp."""
    _, rows = smoke_check_table()
    missing: list[str] = []
    for tool in REQUIRED_TOOLS:
        if find_tool_row(rows, tool) is None:
            missing.append(tool)
    assert not missing, f"Smoke check table missing required tool rows: {missing}"


def test_smoke_check_rows_have_populated_cells() -> None:
    """Test 4: Each required tool row has populated, non-empty cells across all columns."""
    _, rows = smoke_check_table()
    for tool in REQUIRED_TOOLS:
        row = find_tool_row(rows, tool)
        assert row is not None, f"Missing row for {tool}"
        for col in REQUIRED_COLUMNS:
            val = row.get(col, "").strip()
            assert val, f"Row for '{tool}' has empty cell for column '{col}'"


def test_autocad_mcp_not_checked_needs_autocad_open() -> None:
    """Test 5: Explicit autocad-mcp row notes: 'not checked: needs AutoCAD open (user)'."""
    _, rows = smoke_check_table()
    row = find_tool_row(rows, "autocad-mcp")
    assert row is not None, "autocad-mcp row not found in smoke check table"
    result_cell = row.get("Result (works / fails + error line)", "")
    full_row_str = " | ".join(row.values())
    expected_phrase = "not checked: needs AutoCAD open (user)"
    assert expected_phrase in result_cell or expected_phrase in full_row_str, (
        f"autocad-mcp row must contain '{expected_phrase}', got result: '{result_cell}'"
    )


def test_not_used_by_decision_mentions_excluded_tools() -> None:
    """Test 6: 'Not used, by decision' section/note contains trimesh, CADCraft, ODA File Converter, MTree/Sapling, and transient IfcOpenShell uv --with."""
    section = smoke_check_section()
    assert "not used, by decision" in section.lower(), (
        f"'{SECTION_TITLE}' section must contain 'Not used, by decision'"
    )
    assert "trimesh" in section, "Excluded tools must mention 'trimesh'"
    assert "CADCraft" in section or "cadcraft" in section.lower(), "Excluded tools must mention 'CADCraft'"
    assert "ODA File Converter" in section, "Excluded tools must mention 'ODA File Converter'"
    assert "MTree/Sapling" in section or ("MTree" in section and "Sapling" in section), (
        "Excluded tools must mention 'MTree/Sapling'"
    )
    assert "transient IfcOpenShell uv --with" in section or (
        "IfcOpenShell" in section and "uv --with" in section
    ), "Excluded tools must mention 'transient IfcOpenShell uv --with'"
