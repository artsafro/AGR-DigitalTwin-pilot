"""Documentation contract tests for all area requirement sheets.

Issue #150: Generalized documentation contract for area requirement sheets.
Validates table headers, column counts, sources, coverage, markdown links,
and L2 gap entries, while retaining all UCX-specific profile and numeric checks.
"""
from pathlib import Path
import re
import pytest

ROOT = Path(__file__).resolve().parents[1]
AREAS_DIR = ROOT / "docs/domain/areas"
HEADER = ["Requirement", "reg page", "NPM", "VPM", "How it is checked", "L2 coverage", "Detail in"]


def discover_sheets(directory: Path) -> list[Path]:
    """Discover sorted top-level markdown sheets in directory, asserting non-empty."""
    sheets = sorted(p for p in directory.glob("*.md") if p.is_file())
    assert len(sheets) > 0, f"No requirement sheets found in {directory}"
    return sheets


SHEET_PATHS = discover_sheets(AREAS_DIR)

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

SYNTHETIC_REORDER_SHEET = SYNTHETIC_VALID_SHEET.replace(
    "Automated check | V003 |", "Manual review | none |"
).replace("## Subsequent section", "- **NEW-02:** Second gap.\n\n## Subsequent section")


def parse_cells(line: str) -> list[str]:
    return [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def row_str(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def table_line_indices(lines: list[str] | str) -> list[int]:
    """Return line indices for markdown table rows, tolerating leading whitespace."""
    raw = lines.splitlines() if isinstance(lines, str) else lines
    return [i for i, line in enumerate(raw) if line.lstrip().startswith("|")]


def mutate_line(text: str, line_idx: int, new_line: str | None) -> str:
    lines = text.splitlines()
    if new_line is None:
        del lines[line_idx]
    else:
        lines[line_idx] = new_line
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def find_gap_lines(text: str) -> list[tuple[int, str, str]]:
    lines, in_gaps, gaps = text.splitlines(), False, []
    for i, line in enumerate(lines):
        if re.match(r"^##\s+L2 gaps\s*$", line):
            in_gaps = True
        elif in_gaps and re.match(r"^#{1,2}\s+", line):
            break
        elif in_gaps:
            m = re.match(r"^\s*[-*]\s+(.+)$", line)
            if m:
                tokens = re.split(r"[\s:]+", re.sub(r"[*`]+", "", m.group(1)).strip(), maxsplit=1)
                if tokens and tokens[0]:
                    gaps.append((i, tokens[0], line))
    return gaps


def assert_rejected(text: str, context: str):
    try:
        contract(text)
    except AssertionError:
        return
    pytest.fail(f"Mutation was not rejected: {context}")


def contract(text: str) -> list[list[str]]:
    """Generalized documentation contract for area requirement sheets."""
    assert text and text.strip(), "Requirement sheet text must not be empty"
    lines = text.splitlines()
    t_indices = table_line_indices(lines)
    assert len(t_indices) >= 3, "Requirement sheet must contain a table with header, separator, and data rows"
    assert t_indices[-1] - t_indices[0] + 1 == len(t_indices), "Requirement sheet must contain exactly one contiguous markdown table"

    cells = [parse_cells(lines[i]) for i in t_indices]
    assert cells[0] == HEADER, f"Header row must match {HEADER}, got {cells[0]}"
    assert not any(row == HEADER for row in cells[1:]), "Duplicate table header found"
    assert len(cells[1]) == 7 and all(re.fullmatch(r":?-+:?", c) for c in cells[1]), f"Invalid table separator row: {cells[1]}"

    rows = cells[2:]
    assert rows, "Table must have at least one requirement data row"

    all_ids, seen_ids, expected_gaps, covered_ids = set(), set(), [], set()
    for i, row in enumerate(rows, 1):
        assert len(row) == 7, f"Row {i} must have exactly 7 columns, got {len(row)}"
        token = row[0].strip().split()[0] if row[0].strip() else ""
        assert token, f"Row {i} requirement cell must not be empty"
        req_id = re.sub(r"^[*`]+|[*`:]+$", "", token)
        assert req_id, f"Row {i} invalid requirement ID: {row[0]}"
        assert req_id not in seen_ids, f"Duplicate requirement ID: {req_id}"
        seen_ids.add(req_id)
        all_ids.add(req_id)

        assert re.search(r"reg p\.\d+|\[D\d+\]", row[1]), f"Row {req_id} missing valid source (reg p.N or [D...]): {row[1]}"
        assert row[2], f"Row {req_id} NPM scope must not be empty"
        assert row[3], f"Row {req_id} VPM scope must not be empty"
        assert row[4], f"Row {req_id} check method must not be empty"
        assert row[5], f"Row {req_id} L2 coverage must not be empty"
        assert "](" in row[6], f"Row {req_id} Detail in must contain markdown link: {row[6]}"
        expected_gaps.append(req_id) if row[5] == "none" else covered_ids.add(req_id)

    gap_headings = [i for i, line in enumerate(lines) if re.match(r"^##\s+L2 gaps\s*$", line)]
    assert len(gap_headings) == 1, f"Expected exactly one '## L2 gaps' section, found {len(gap_headings)}"

    gap_ids = [gid for _, gid, _ in find_gap_lines(text)]
    dup = [gid for gid in gap_ids if gap_ids.count(gid) > 1]
    assert not dup, f"Duplicate gap entries in L2 gaps: {set(dup)}"
    unknown = set(gap_ids) - all_ids
    assert not unknown, f"Unknown requirement IDs in L2 gaps: {sorted(unknown)}"
    covered = set(gap_ids) & covered_ids
    assert not covered, f"Covered requirements cannot be in L2 gaps: {sorted(covered)}"
    missing = set(expected_gaps) - set(gap_ids)
    assert not missing, f"Missing L2 gaps for none-coverage requirements: {sorted(missing)}"

    return rows


def quote_evidence_contract(text: str, filenames: list[str]):
    assert not any(name.endswith(".png") for name in filenames), "Keep rendered PNGs local-only"
    assert not re.search(r"\]\([^)]*\.png\)", text), "Evidence must not depend on PNG links"
    for row, page in (("R04", 36), ("R08", 34), ("R11", 36), ("R12", 36), ("R15", 36)):
        assert re.search(rf"\*\*{row} — reg p\.?p?\.{page}.*[«“]", text)
    assert "uv run --extra pdf-review python -c" in text and "get_pixmap" in text


def numeric_contract(rows: list[list[str]]):
    expected = {
        4: "<= 5 cm", 8: "001..999", 10: "0.02-1 cm", 11: "<= 10 cm", 12: "<= 30 cm", 13: "<= 1 m",
        15: "n < 50,000: 15,000; otherwise min(ceil(n * 0.05), 100,000)",
    }
    for number, value in expected.items():
        assert value in rows[number - 1][3]
    return expected


def ucx_contract(text: str) -> list[list[str]]:
    rows = contract(text)
    assert len(rows) == 18, f"Expected 18 UCX rows, got {len(rows)}"
    for i, row in enumerate(rows, 1):
        assert row[0].startswith(f"R{i:02d} "), f"Row {i} ID must start with R{i:02d}"
        assert row[2] == "n/a", f"UCX row {i} NPM must be 'n/a', got {row[2]!r}"
    for target in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", text):
        assert ((AREAS_DIR / "ucx.md").parent / target).is_file(), target
    return rows


@pytest.mark.parametrize("sheet_path", SHEET_PATHS, ids=lambda p: p.name)
def test_area_sheet_contract(sheet_path: Path):
    """Invokes contract on every top-level area sheet."""
    rows = contract(sheet_path.read_text(encoding="utf-8"))
    print(f"{sheet_path.name}: {len(rows)} rows validated across {len(SHEET_PATHS)} discovered sheets")


@pytest.mark.parametrize("sheet_path", SHEET_PATHS, ids=lambda p: p.name)
def test_columns_negative_probes(sheet_path: Path):
    """Exhaustively drops each of 7 columns and adds an 8th column to header and data rows."""
    text = sheet_path.read_text(encoding="utf-8")
    contract(text)
    lines = text.splitlines()
    t_indices = table_line_indices(lines)
    tested = 0
    for idx in [t_indices[0]] + t_indices[2:]:
        cells = parse_cells(lines[idx])
        for col in range(7):
            assert_rejected(mutate_line(text, idx, row_str(cells[:col] + cells[col + 1:])), f"{sheet_path.name}: drop col {col}")
            tested += 1
        assert_rejected(mutate_line(text, idx, row_str(cells + ["Extra"])), f"{sheet_path.name}: extra col")
        tested += 1
    total = 8 + 8 * (len(t_indices) - 2)
    print(f"{sheet_path.name} columns: {tested}/{total} rejected")


@pytest.mark.parametrize("sheet_path", SHEET_PATHS, ids=lambda p: p.name)
def test_sources_negative_probes(sheet_path: Path):
    """Blanks and invalidates source cell across all data rows."""
    text = sheet_path.read_text(encoding="utf-8")
    contract(text)
    lines = text.splitlines()
    data_indices = table_line_indices(lines)[2:]
    tested = 0
    for r_idx in data_indices:
        r_cells = parse_cells(lines[r_idx])
        for repl in ("", "unsourced rule without citation"):
            changed = list(r_cells)
            changed[1] = repl
            assert_rejected(mutate_line(text, r_idx, row_str(changed)), f"{sheet_path.name}: row {r_idx} src {repl}")
            tested += 1
    total = len(data_indices) * 2
    print(f"{sheet_path.name} sources: {tested}/{total} rejected")


@pytest.mark.parametrize("sheet_path", SHEET_PATHS, ids=lambda p: p.name)
def test_gaps_negative_probes(sheet_path: Path):
    """Removes none gaps, duplicates gaps, and adds unknown or covered IDs."""
    text = sheet_path.read_text(encoding="utf-8")
    contract(text)
    lines = text.splitlines()
    data_indices = table_line_indices(lines)[2:]
    gap_entries = find_gap_lines(text)
    tested = 0

    rows_info = [(re.sub(r"^[*`]+|[*`:]+$", "", parse_cells(lines[i])[0].split()[0]), parse_cells(lines[i])[5].strip()) for i in data_indices]
    none_rows = [info for info in rows_info if info[1] == "none"]
    for req_id, _ in none_rows:
        matching = [g for g in gap_entries if g[1] == req_id]
        assert len(matching) == 1, f"Expected exactly one gap for {req_id}, found {len(matching)}"
        g_idx, _, orig_line = matching[0]
        assert_rejected(mutate_line(text, g_idx, None), f"{sheet_path.name}: drop none-gap {req_id}")
        l = text.splitlines()
        l.insert(g_idx + 1, orig_line)
        assert_rejected("\n".join(l) + ("\n" if text.endswith("\n") else ""), f"{sheet_path.name}: duplicate none-gap {req_id}")
        tested += 2

    gap_heading_indices = [i for i, line in enumerate(lines) if re.match(r"^##\s+L2 gaps\s*$", line)]
    g_insert_idx = gap_entries[0][0] if gap_entries else (gap_heading_indices[0] + 1)
    l = text.splitlines()
    l.insert(g_insert_idx, "- **UNKNOWN-99:** Spurious gap entry for nonexistent requirement.")
    assert_rejected("\n".join(l) + ("\n" if text.endswith("\n") else ""), f"{sheet_path.name}: add unknown gap")
    tested += 1

    covered_rows = [info for info in rows_info if info[1] != "none"]
    for req_id, cov in covered_rows:
        l = text.splitlines()
        l.insert(g_insert_idx, f"- **{req_id}:** Spurious gap entry for covered requirement ({cov}).")
        assert_rejected("\n".join(l) + ("\n" if text.endswith("\n") else ""), f"{sheet_path.name}: add covered gap {req_id}")
        tested += 1

    total = len(none_rows) * 2 + 1 + len(covered_rows)
    print(f"{sheet_path.name} gaps: {tested}/{total} rejected")


@pytest.mark.parametrize("case, mutation_fn, expected_diagnostic", [
    ("missing_column", lambda t: t.replace(" | [Detail](../geometry.md) |", " |"), "7 columns"),
    ("missing_source", lambda t: t.replace("reg p.4 §1.1", ""), "missing valid source"),
    ("missing_gap", lambda t: t.replace("- **NEW-01:** First requirement lacks automated coverage.\n", ""), "Missing L2 gaps"),
], ids=["missing_column", "missing_source", "missing_gap"])
def test_scratch_sheet_negative_probes(tmp_path: Path, case: str, mutation_fn, expected_diagnostic: str):
    """Test scratch tmp_path sheet missing column/source/gap and verify recovery on restore."""
    scratch = tmp_path / f"scratch_{case}.md"
    scratch.write_text(SYNTHETIC_VALID_SHEET, encoding="utf-8")
    contract(scratch.read_text(encoding="utf-8"))
    scratch.write_text(mutation_fn(SYNTHETIC_VALID_SHEET), encoding="utf-8")
    with pytest.raises(AssertionError, match=expected_diagnostic):
        contract(scratch.read_text(encoding="utf-8"))
    scratch.write_text(SYNTHETIC_VALID_SHEET, encoding="utf-8")
    contract(scratch.read_text(encoding="utf-8"))


def test_gap_section_boundaries_and_order():
    """Verify that reordering table rows or gaps is accepted, while out-of-section gaps fail."""
    contract(SYNTHETIC_REORDER_SHEET)
    lines = SYNTHETIC_REORDER_SHEET.splitlines()
    t_idx = table_line_indices(lines)
    lines[t_idx[2]], lines[t_idx[3]] = lines[t_idx[3]], lines[t_idx[2]]
    contract("\n".join(lines) + "\n")

    gaps = find_gap_lines(SYNTHETIC_REORDER_SHEET)
    g1, g2 = gaps[0][0], gaps[1][0]
    lines = SYNTHETIC_REORDER_SHEET.splitlines()
    lines[g1], lines[g2] = lines[g2], lines[g1]
    contract("\n".join(lines) + "\n")

    lines = SYNTHETIC_REORDER_SHEET.splitlines()
    del lines[g1]
    lines.append("- **NEW-01:** Gap placed after subsequent section heading.")
    with pytest.raises(AssertionError):
        contract("\n".join(lines) + "\n")


def test_duplicate_table_rejected():
    """Verify that duplicate tables and duplicate IDs are rejected."""
    for text in ((AREAS_DIR / "ucx.md").read_text(encoding="utf-8"), SYNTHETIC_VALID_SHEET):
        contract(text)
        lines = text.splitlines()
        tbl = "\n".join(lines[i] for i in table_line_indices(lines))
        with pytest.raises(AssertionError):
            contract(text + "\n\n" + tbl + "\n")

    lines = SYNTHETIC_VALID_SHEET.splitlines()
    t_synth = table_line_indices(lines)
    with pytest.raises(AssertionError):
        contract(mutate_line(SYNTHETIC_VALID_SHEET, t_synth[3], lines[t_synth[2]]))


def test_empty_or_partial_sheet_rejected():
    """Verify that empty, header-only, partial, or malformed sheets are rejected."""
    bad_sheets = [
        "", "   \n\n\t   \n",
        "| Requirement | reg page | NPM | VPM | How it is checked | L2 coverage | Detail in |\n|---|---|---|---|---|---|---|\n\n## L2 gaps\n",
        SYNTHETIC_VALID_SHEET.replace("## L2 gaps", "## Limitations and Notes"),
        SYNTHETIC_VALID_SHEET.replace("## L2 gaps", "## L2 gaps-other"),
        SYNTHETIC_VALID_SHEET + "\n| NEW-TRUNC | reg p.4 §1.1 | NPM scope |\n",
        SYNTHETIC_VALID_SHEET + "\n| NEW-EXTRA | reg p.4 | A | B | C | none | link | 8th |\n",
    ]
    for bad in bad_sheets:
        with pytest.raises(AssertionError):
            contract(bad)


def test_new_sheet_is_discovered(tmp_path: Path):
    """Verify discover_sheets helper behavior and acceptance of synthetic area sheet."""
    areas_test_dir = tmp_path / "areas"
    areas_test_dir.mkdir()
    sheet_z, sheet_a = areas_test_dir / "z-area.md", areas_test_dir / "a-area.md"
    sheet_z.write_text(SYNTHETIC_VALID_SHEET, encoding="utf-8")
    sheet_a.write_text(SYNTHETIC_VALID_SHEET, encoding="utf-8")
    nested_dir = areas_test_dir / "area-evidence"
    nested_dir.mkdir()
    (nested_dir / "review.md").write_text("# Review evidence\n", encoding="utf-8")

    discovered = discover_sheets(areas_test_dir)
    assert discovered == [sheet_a, sheet_z], "discover_sheets must return sorted top-level sheets only"
    assert (nested_dir / "review.md") not in discovered
    for sheet in discovered:
        contract(sheet.read_text(encoding="utf-8"))

    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    with pytest.raises(AssertionError):
        discover_sheets(empty_dir)

    real_discovered = discover_sheets(AREAS_DIR)
    assert real_discovered == sorted(real_discovered) and len(real_discovered) >= 1
    assert not any(p.name == "review.md" for p in real_discovered)


def test_all_covered_sheet_contract():
    """Verify synthetic all-covered sheet passes contract and rejects added gaps for covered IDs."""
    covered_sheet = SYNTHETIC_VALID_SHEET.replace(" | none | ", " | V003 | ").replace(
        "- **NEW-01:** First requirement lacks automated coverage.\n", ""
    )
    rows = contract(covered_sheet)
    assert len(rows) == 2
    gap_heading_idx = [i for i, line in enumerate(covered_sheet.splitlines()) if re.match(r"^##\s+L2 gaps\s*$", line)][0]
    for req_id in ("NEW-01", "NEW-02"):
        lines = covered_sheet.splitlines()
        lines.insert(gap_heading_idx + 1, f"- **{req_id}:** Spurious gap entry.")
        with pytest.raises(AssertionError, match="Covered requirements cannot be in L2 gaps"):
            contract("\n".join(lines) + "\n")


def test_gap_id_parsing_and_masquerade():
    """Verify gap parsing handles formats, rejects unknown lowercase and suffixed IDs without masquerade."""
    sample = "## L2 gaps\n\n- **MAF-01:** First\n- **BODY-A** Second\n- R01: Third\n- `R02`: Fourth\n- *R03*: Fifth\n"
    assert [gid for _, gid, _ in find_gap_lines(sample)] == ["MAF-01", "BODY-A", "R01", "R02", "R03"]

    ucx_text = (AREAS_DIR / "ucx.md").read_text(encoding="utf-8")
    for bad_id in ("r01", "R01suffix", "R01foo"):
        with pytest.raises(AssertionError, match=r"Unknown requirement IDs in L2 gaps|Missing L2 gaps"):
            contract(ucx_text.replace("- R01:", f"- {bad_id}:"))

    for bad_gap in ("- new-01: Lowercase", "- **new-01:** Bold lowercase", "- NEW-01suffix: Suffix", "- NEW-01foo: Foo"):
        synth = SYNTHETIC_VALID_SHEET.replace("- **NEW-01:** First requirement lacks automated coverage.", bad_gap)
        with pytest.raises(AssertionError, match=r"Unknown requirement IDs in L2 gaps|Missing L2 gaps"):
            contract(synth)


def test_ucx_sheet_contract():
    """UCX-specific contract assertions: sequential R01..R18, NPM n/a, link resolution, and NPM mutation rejection."""
    ucx_text = (AREAS_DIR / "ucx.md").read_text(encoding="utf-8")
    rows = ucx_contract(ucx_text)
    tested = 0
    lines = ucx_text.splitlines()
    data_indices = table_line_indices(lines)[2:]
    for r_idx, row in zip(data_indices, rows):
        changed = row.copy()
        changed[2] = "required"
        with pytest.raises(AssertionError):
            ucx_contract(mutate_line(ucx_text, r_idx, row_str(changed)))
        tested += 1
    print(f"ucx.md npm: {tested}/{len(rows)} rejected")


def test_ucx_sheet_numeric_and_profile_index():
    """Transcribed numeric limits and profile assertions for UCX."""
    rows = contract((AREAS_DIR / "ucx.md").read_text(encoding="utf-8"))
    for number, value in numeric_contract(rows).items():
        changed = [row.copy() for row in rows]
        changed[number - 1][3] = changed[number - 1][3].replace(value, "UNVERIFIED_LIMIT")
        with pytest.raises(AssertionError):
            numeric_contract(changed)
    assert "Ground" in rows[1][3]
    assert all(word in rows[2][3] for word in ("MAF", "lighting", "vegetation", "none"))
    assert "recommendation" in rows[9][3]
    assert "[D012]" in rows[14][1]


def test_ucx_quote_evidence_is_binary_independent():
    """Transcribed evidence quotes and binary PNG rejection."""
    evidence = (AREAS_DIR / "ucx.md").parent / "ucx-evidence"
    text = (evidence / "review.md").read_text(encoding="utf-8")
    quote_evidence_contract(text, [path.name for path in evidence.iterdir()])
    for page in (29, 33, 34, 36, 37):
        with pytest.raises(AssertionError):
            quote_evidence_contract(text, [f"reg-p{page}.png"])


# --- Issue #150 review round 1: regression tests for indented rows (R1-R5) ---

SYNTHETIC_ROW_01 = (
    "| NEW-01 — Synthetic first requirement | reg p.4 §1.1 | NPM scope | VPM scope | Manual review | none | [Detail](../geometry.md) |"
)
SYNTHETIC_ROW_02 = (
    "| NEW-02 — Synthetic second requirement | [D010] | NPM scope | VPM scope | Automated check | V003 | [Detail](../geometry.md) |"
)


@pytest.mark.parametrize("indent", [0, 1, 2, 3])
def test_indented_rows_are_validated(indent: int):
    """Verify indented trailing synthetic row (NEW-02) is parsed and returned rather than omitted (R1)."""
    spaces = " " * indent
    sheet = SYNTHETIC_VALID_SHEET.replace(SYNTHETIC_ROW_02, f"{spaces}{SYNTHETIC_ROW_02}")
    rows = contract(sheet)
    assert len(rows) == 2, f"Expected 2 rows returned for indent {indent}, got {len(rows)}"
    assert rows[0][0].startswith("NEW-01")
    assert rows[1][0].startswith("NEW-02")
    assert rows[1][1] == "[D010]"
    assert rows[1][5] == "V003"


@pytest.mark.parametrize("indent", [0, 1, 2, 3])
@pytest.mark.parametrize("case, mutate_new_02_fn, expected_diagnostic", [
    (
        "missing_source",
        lambda r: r.replace("[D010]", ""),
        "missing valid source",
    ),
    (
        "missing_npm_column",
        lambda r: r.replace(" | NPM scope", ""),
        "exactly 7 columns",
    ),
    (
        "missing_gap_when_none",
        lambda r: r.replace(" | V003 | ", " | none | "),
        "Missing L2 gaps",
    ),
], ids=["missing_source", "missing_npm_column", "missing_gap_when_none"])
def test_indented_rows_reject_invalid_cells(indent: int, case: str, mutate_new_02_fn, expected_diagnostic: str):
    """Verify that invalid cells in indented trailing synthetic row (NEW-02) trigger proper diagnostics (R2, R3, R4)."""
    spaces = " " * indent
    mutated_new_02 = f"{spaces}{mutate_new_02_fn(SYNTHETIC_ROW_02)}"
    sheet = SYNTHETIC_VALID_SHEET.replace(SYNTHETIC_ROW_02, mutated_new_02)
    with pytest.raises(AssertionError, match=expected_diagnostic):
        contract(sheet)


@pytest.mark.parametrize("indent", [0, 1, 2, 3])
def test_indented_mutation_probes(tmp_path: Path, capsys: pytest.CaptureFixture, indent: int):
    """Verify mutation probes exercise both data rows when indented (R5)."""
    spaces = " " * indent
    sheet = SYNTHETIC_VALID_SHEET.replace(
        SYNTHETIC_ROW_01, f"{spaces}{SYNTHETIC_ROW_01}"
    ).replace(
        SYNTHETIC_ROW_02, f"{spaces}{SYNTHETIC_ROW_02}"
    )
    scratch_path = tmp_path / f"synthetic_indented_{indent}.md"
    scratch_path.write_text(sheet, encoding="utf-8")

    test_columns_negative_probes(scratch_path)
    out_col = capsys.readouterr().out
    assert "columns: 24/24 rejected" in out_col, f"Expected 24 rejected columns, got: {out_col!r}"

    test_sources_negative_probes(scratch_path)
    out_src = capsys.readouterr().out
    assert "sources: 4/4 rejected" in out_src, f"Expected 4 rejected sources, got: {out_src!r}"

    test_gaps_negative_probes(scratch_path)
    out_gap = capsys.readouterr().out
    assert "gaps: 4/4 rejected" in out_gap, f"Expected 4 rejected gaps, got: {out_gap!r}"

