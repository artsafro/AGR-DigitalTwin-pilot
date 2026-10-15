"""Documentation contract tests for all area requirement sheets.

Issue #150 tests-first round 1: defines regression tests and exhaustive probes
against the area requirement contract. Initially imports the existing contract
from test_ucx_requirement_sheet to establish the RED baseline.
"""
from pathlib import Path
import re

import pytest

try:
    from test_ucx_requirement_sheet import contract
except ImportError:
    from tests.test_ucx_requirement_sheet import contract

ROOT = Path(__file__).resolve().parents[1]
AREAS_DIR = ROOT / "docs/domain/areas"
HEADER = ["Requirement", "reg page", "NPM", "VPM", "How it is checked", "L2 coverage", "Detail in"]


def discover_sheets(directory: Path) -> list[Path]:
    """Discover sorted top-level markdown sheets in directory, asserting non-empty."""
    sheets = sorted(p for p in directory.glob("*.md") if p.is_file())
    assert len(sheets) > 0, f"No requirement sheets found in {directory}"
    return sheets


SHEET_PATHS = discover_sheets(AREAS_DIR)

# Synthetic valid sheet with NEW-01 and NEW-02 IDs, first none second check,
# source reg p.4 and [D010], exact seven headers, and L2 gaps first row.
SYNTHETIC_VALID_SHEET = """# NEW Area — requirement sheet

Area: Synthetic test area.

| Requirement | reg page | NPM | VPM | How it is checked | L2 coverage | Detail in |
|---|---|---|---|---|---|---|
| NEW-01 — Synthetic first requirement | reg p.4 §1.1 | NPM scope | VPM scope | Manual review | none | [Detail](../geometry.md) |
| NEW-02 — Synthetic second requirement | [D010] | NPM scope | VPM scope | Automated check | V003 | [Detail](../geometry.md) |

## L2 gaps

- **NEW-01:** First requirement lacks automated coverage.

## Subsequent section

Evidence and notes following gaps.
"""

SYNTHETIC_REORDER_SHEET = """# REORDER Area — requirement sheet

Area: Synthetic reorder area.

| Requirement | reg page | NPM | VPM | How it is checked | L2 coverage | Detail in |
|---|---|---|---|---|---|---|
| NEW-01 — Synthetic first | reg p.4 §1.1 | NPM scope | VPM scope | Manual review | none | [Detail](../geometry.md) |
| NEW-02 — Synthetic second | [D010] | NPM scope | VPM scope | Manual review | none | [Detail](../geometry.md) |

## L2 gaps

- **NEW-01:** First gap description.
- **NEW-02:** Second gap description.

## Subsequent section

Notes after gaps.
"""


def get_table_lines(text: str) -> list[tuple[int, str]]:
    """Return list of (line_index, line_content) for table lines starting with '|'."""
    return [(i, line) for i, line in enumerate(text.splitlines()) if line.startswith("|")]


def parse_row_cells(line: str) -> list[str]:
    """Split markdown table line into cell values preserving escaped pipes."""
    return [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def format_row_cells(cells: list[str]) -> str:
    """Format list of cell strings back into a markdown table row."""
    return "| " + " | ".join(cells) + " |"


def replace_line_in_text(text: str, line_index: int, new_line: str) -> str:
    """Replace a single line at line_index in text."""
    lines = text.splitlines()
    lines[line_index] = new_line
    result = "\n".join(lines)
    if text.endswith("\n"):
        result += "\n"
    return result


def delete_line_in_text(text: str, line_index: int) -> str:
    """Delete a single line at line_index in text."""
    lines = text.splitlines()
    del lines[line_index]
    result = "\n".join(lines)
    if text.endswith("\n"):
        result += "\n"
    return result


def extract_requirement_id(cell0: str) -> str:
    """Extract requirement ID token (e.g. 'R01', 'BODY-A', 'MAF-01', 'NEW-01') from first cell."""
    match = re.match(r"^([A-Z0-9]+(?:-[A-Z0-9]+)*)", cell0.strip())
    if match:
        return match.group(1)
    return cell0.split()[0]


def find_gap_lines(text: str) -> list[tuple[int, str, str]]:
    """Return list of (line_index, req_id, line_text) within the '## L2 gaps' section."""
    lines = text.splitlines()
    in_gaps = False
    gaps = []
    for i, line in enumerate(lines):
        if line.startswith("## L2 gaps"):
            in_gaps = True
            continue
        if in_gaps and re.match(r"^#{1,2}\s+", line):
            break
        if in_gaps:
            match = re.match(r"^\s*-\s+(?:\*\*)?([A-Z0-9]+(?:-[A-Z0-9]+)*)(?:\*\*)?(?:[:—\s])", line)
            if match:
                gaps.append((i, match.group(1), line))
    return gaps


@pytest.mark.parametrize("sheet_path", SHEET_PATHS, ids=lambda p: p.name)
def test_area_sheet_contract(sheet_path: Path):
    """Invokes contract on every top-level area sheet; fails BODY and MAF on UCX-only contract."""
    text = sheet_path.read_text(encoding="utf-8")
    contract(text)


@pytest.mark.parametrize("sheet_path", SHEET_PATHS, ids=lambda p: p.name)
def test_columns_negative_probes(sheet_path: Path):
    """Exhaustively drops each of 7 columns and adds an 8th column to header and data rows."""
    text = sheet_path.read_text(encoding="utf-8")
    # Assert valid baseline before mutations so old UCX-only contract fails genuinely
    contract(text)

    table_lines = get_table_lines(text)
    assert len(table_lines) >= 3, f"Sheet {sheet_path.name} missing table rows"

    # Header row mutations
    h_idx, h_line = table_lines[0]
    h_cells = parse_row_cells(h_line)
    assert len(h_cells) == 7, f"Header must have 7 columns, got {len(h_cells)}"

    for col_idx in range(7):
        dropped = h_cells[:col_idx] + h_cells[col_idx + 1:]
        mutated_text = replace_line_in_text(text, h_idx, format_row_cells(dropped))
        with pytest.raises(AssertionError):
            contract(mutated_text)

    extra_h = h_cells + ["ExtraColumn"]
    mutated_text = replace_line_in_text(text, h_idx, format_row_cells(extra_h))
    with pytest.raises(AssertionError):
        contract(mutated_text)

    # Data row mutations
    data_lines = table_lines[2:]
    for r_idx, r_line in data_lines:
        r_cells = parse_row_cells(r_line)
        assert len(r_cells) == 7, f"Row at line {r_idx} must have 7 columns, got {len(r_cells)}"

        for col_idx in range(7):
            dropped = r_cells[:col_idx] + r_cells[col_idx + 1:]
            mutated_text = replace_line_in_text(text, r_idx, format_row_cells(dropped))
            with pytest.raises(AssertionError):
                contract(mutated_text)

        extra_r = r_cells + ["ExtraValue"]
        mutated_text = replace_line_in_text(text, r_idx, format_row_cells(extra_r))
        with pytest.raises(AssertionError):
            contract(mutated_text)


@pytest.mark.parametrize("sheet_path", SHEET_PATHS, ids=lambda p: p.name)
def test_sources_negative_probes(sheet_path: Path):
    """Blanks and invalidates source cell across all data rows."""
    text = sheet_path.read_text(encoding="utf-8")
    # Assert valid baseline before mutations so old UCX-only contract fails genuinely
    contract(text)

    table_lines = get_table_lines(text)
    data_lines = table_lines[2:]
    assert data_lines, f"Sheet {sheet_path.name} has no requirement rows"

    for r_idx, r_line in data_lines:
        r_cells = parse_row_cells(r_line)
        assert len(r_cells) == 7

        blank_cells = list(r_cells)
        blank_cells[1] = ""
        mutated_text = replace_line_in_text(text, r_idx, format_row_cells(blank_cells))
        with pytest.raises(AssertionError):
            contract(mutated_text)

        unsourced_cells = list(r_cells)
        unsourced_cells[1] = "unsourced rule without citation"
        mutated_text = replace_line_in_text(text, r_idx, format_row_cells(unsourced_cells))
        with pytest.raises(AssertionError):
            contract(mutated_text)


@pytest.mark.parametrize("sheet_path", SHEET_PATHS, ids=lambda p: p.name)
def test_gaps_negative_probes(sheet_path: Path):
    """Removes none gaps, duplicates gaps, and adds unknown or covered IDs."""
    text = sheet_path.read_text(encoding="utf-8")
    # Assert valid baseline before mutations so old UCX-only contract fails genuinely
    contract(text)

    table_lines = get_table_lines(text)
    data_lines = table_lines[2:]
    gap_lines = find_gap_lines(text)

    rows_info = []
    for r_idx, r_line in data_lines:
        cells = parse_row_cells(r_line)
        req_id = extract_requirement_id(cells[0])
        coverage = cells[5].strip()
        rows_info.append((req_id, coverage, r_idx))

    # 1. Remove each none-row gap
    none_rows = [info for info in rows_info if info[1] == "none"]
    assert none_rows, f"Sheet {sheet_path.name} has no 'none' coverage rows"

    for req_id, _, _ in none_rows:
        matching_gaps = [g for g in gap_lines if g[1] == req_id]
        assert len(matching_gaps) == 1, f"Expected exactly one gap for {req_id}, found {len(matching_gaps)}"
        g_idx, _, _ = matching_gaps[0]
        mutated_text = delete_line_in_text(text, g_idx)
        with pytest.raises(AssertionError):
            contract(mutated_text)

    # 2. Duplicate each none-row gap
    for req_id, _, _ in none_rows:
        matching_gaps = [g for g in gap_lines if g[1] == req_id]
        g_idx, _, original_gap_line = matching_gaps[0]
        lines = text.splitlines()
        lines.insert(g_idx + 1, original_gap_line)
        mutated_text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
        with pytest.raises(AssertionError):
            contract(mutated_text)

    # 3. Add an unknown ID to gaps section
    lines = text.splitlines()
    g_insert_idx = gap_lines[0][0]
    lines.insert(g_insert_idx, "- **UNKNOWN-99:** Spurious gap entry for nonexistent requirement.")
    mutated_text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    with pytest.raises(AssertionError):
        contract(mutated_text)

    # 4. Add a gap for covered requirements (coverage != "none")
    covered_rows = [info for info in rows_info if info[1] != "none"]
    for req_id, cov, _ in covered_rows:
        lines = text.splitlines()
        lines.insert(g_insert_idx, f"- **{req_id}:** Spurious gap entry for covered requirement ({cov}).")
        mutated_text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
        with pytest.raises(AssertionError):
            contract(mutated_text)


def test_scratch_sheet_negative_probes(tmp_path: Path):
    """Test scratch tmp_path sheet missing column/source/gap and verify recovery on restore."""
    scratch = tmp_path / "scratch_area.md"
    scratch.write_text(SYNTHETIC_VALID_SHEET, encoding="utf-8")

    # Baseline assertion: valid synthetic content must pass
    contract(scratch.read_text(encoding="utf-8"))

    # Case 1: Missing column (drop 7th column from data row)
    table_lines = get_table_lines(SYNTHETIC_VALID_SHEET)
    r_idx, r_line = table_lines[2]
    cells = parse_row_cells(r_line)
    bad_row = format_row_cells(cells[:-1])
    scratch.write_text(replace_line_in_text(SYNTHETIC_VALID_SHEET, r_idx, bad_row), encoding="utf-8")
    with pytest.raises(AssertionError):
        contract(scratch.read_text(encoding="utf-8"))
    # Restore valid content -> must pass
    scratch.write_text(SYNTHETIC_VALID_SHEET, encoding="utf-8")
    contract(scratch.read_text(encoding="utf-8"))

    # Case 2: Missing source in row 1
    bad_source_cells = list(cells)
    bad_source_cells[1] = ""
    scratch.write_text(replace_line_in_text(SYNTHETIC_VALID_SHEET, r_idx, format_row_cells(bad_source_cells)), encoding="utf-8")
    with pytest.raises(AssertionError):
        contract(scratch.read_text(encoding="utf-8"))
    # Restore valid content -> must pass
    scratch.write_text(SYNTHETIC_VALID_SHEET, encoding="utf-8")
    contract(scratch.read_text(encoding="utf-8"))

    # Case 3: Missing gap for none row (remove NEW-01 gap)
    gaps = find_gap_lines(SYNTHETIC_VALID_SHEET)
    assert gaps, "Synthetic sheet must contain gap lines"
    g_idx, _, _ = gaps[0]
    scratch.write_text(delete_line_in_text(SYNTHETIC_VALID_SHEET, g_idx), encoding="utf-8")
    with pytest.raises(AssertionError):
        contract(scratch.read_text(encoding="utf-8"))
    # Restore valid content -> must pass
    scratch.write_text(SYNTHETIC_VALID_SHEET, encoding="utf-8")
    contract(scratch.read_text(encoding="utf-8"))


def test_gap_section_boundaries_and_order():
    """Verify that reordering table rows or gaps is accepted, while out-of-section gaps fail."""
    # Assert valid baseline
    contract(SYNTHETIC_REORDER_SHEET)

    # 1. Reorder requirement rows: swap NEW-01 and NEW-02 rows in table
    table_lines = get_table_lines(SYNTHETIC_REORDER_SHEET)
    r1_idx, r1_line = table_lines[2]
    r2_idx, r2_line = table_lines[3]
    lines = SYNTHETIC_REORDER_SHEET.splitlines()
    lines[r1_idx] = r2_line
    lines[r2_idx] = r1_line
    reordered_rows_text = "\n".join(lines) + "\n"
    contract(reordered_rows_text)

    # 2. Reorder gap entries: swap gap 1 and gap 2 in L2 gaps section
    gaps = find_gap_lines(SYNTHETIC_REORDER_SHEET)
    g1_idx, _, g1_line = gaps[0]
    g2_idx, _, g2_line = gaps[1]
    lines = SYNTHETIC_REORDER_SHEET.splitlines()
    lines[g1_idx] = g2_line
    lines[g2_idx] = g1_line
    reordered_gaps_text = "\n".join(lines) + "\n"
    contract(reordered_gaps_text)

    # 3. Move required gap after next heading: out-of-section gap fails
    lines = SYNTHETIC_REORDER_SHEET.splitlines()
    del lines[g1_idx]
    lines.append("- **NEW-01:** Gap placed after subsequent section heading.")
    out_of_section_text = "\n".join(lines) + "\n"
    with pytest.raises(AssertionError):
        contract(out_of_section_text)


def test_duplicate_table_rejected():
    """Verify that duplicate tables and duplicate IDs are rejected."""
    # 1. Duplicate table in UCX sheet
    ucx_text = (AREAS_DIR / "ucx.md").read_text(encoding="utf-8")
    contract(ucx_text)

    table_lines = [line for line in ucx_text.splitlines() if line.startswith("|")]
    duplicated_ucx = ucx_text + "\n\n" + "\n".join(table_lines) + "\n"
    with pytest.raises(AssertionError):
        contract(duplicated_ucx)

    # 2. Duplicate table in synthetic sheet
    contract(SYNTHETIC_VALID_SHEET)
    synth_table_lines = [line for line in SYNTHETIC_VALID_SHEET.splitlines() if line.startswith("|")]
    duplicated_synth = SYNTHETIC_VALID_SHEET + "\n\n" + "\n".join(synth_table_lines) + "\n"
    with pytest.raises(AssertionError):
        contract(duplicated_synth)

    # 3. Duplicate requirement ID within same table
    table_lines_synth = get_table_lines(SYNTHETIC_VALID_SHEET)
    r1_idx, r1_line = table_lines_synth[2]
    r2_idx, _ = table_lines_synth[3]
    dup_id_text = replace_line_in_text(SYNTHETIC_VALID_SHEET, r2_idx, r1_line)
    with pytest.raises(AssertionError):
        contract(dup_id_text)


def test_empty_or_partial_sheet_rejected():
    """Verify that empty, header-only, partial, or malformed sheets are rejected."""
    with pytest.raises(AssertionError):
        contract("")
    with pytest.raises(AssertionError):
        contract("   \n\n\t   \n")

    header_only = (
        "| Requirement | reg page | NPM | VPM | How it is checked | L2 coverage | Detail in |\n"
        "|---|---|---|---|---|---|---|\n\n"
        "## L2 gaps\n"
    )
    with pytest.raises(AssertionError):
        contract(header_only)

    no_gaps_heading = SYNTHETIC_VALID_SHEET.replace("## L2 gaps", "## Limitations and Notes")
    with pytest.raises(AssertionError):
        contract(no_gaps_heading)

    truncated_row_sheet = SYNTHETIC_VALID_SHEET + "\n| NEW-TRUNC | reg p.4 §1.1 | NPM scope |\n"
    with pytest.raises(AssertionError):
        contract(truncated_row_sheet)

    malformed_width_sheet = (
        SYNTHETIC_VALID_SHEET + "\n| NEW-EXTRA | reg p.4 | A | B | C | none | link | 8th |\n"
    )
    with pytest.raises(AssertionError):
        contract(malformed_width_sheet)


def test_new_sheet_is_discovered(tmp_path: Path):
    """Verify discover_sheets helper behavior and acceptance of synthetic area sheet."""
    areas_test_dir = tmp_path / "areas"
    areas_test_dir.mkdir()

    sheet_z = areas_test_dir / "z-area.md"
    sheet_a = areas_test_dir / "a-area.md"
    sheet_z.write_text(SYNTHETIC_VALID_SHEET, encoding="utf-8")
    sheet_a.write_text(SYNTHETIC_VALID_SHEET, encoding="utf-8")

    nested_dir = areas_test_dir / "area-evidence"
    nested_dir.mkdir()
    nested_md = nested_dir / "review.md"
    nested_md.write_text("# Review evidence\n", encoding="utf-8")

    discovered = discover_sheets(areas_test_dir)
    assert discovered == [sheet_a, sheet_z], "discover_sheets must return sorted top-level sheets only"
    assert nested_md not in discovered, "Nested evidence markdown must be excluded from discovery"

    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    with pytest.raises(AssertionError):
        discover_sheets(empty_dir)

    real_discovered = discover_sheets(AREAS_DIR)
    assert [p.name for p in real_discovered] == ["body.md", "groundel-maf.md", "ucx.md"]
    assert not any(p.name == "review.md" for p in real_discovered)

    contract(SYNTHETIC_VALID_SHEET)
