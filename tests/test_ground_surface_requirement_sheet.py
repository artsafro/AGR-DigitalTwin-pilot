"""Ground surface documentation contracts, not geometry checks or delivery acceptance (#157)."""
from pathlib import Path
import re

import pytest

from test_area_requirement_sheet import contract

ROOT = Path(__file__).resolve().parents[1]
SHEET = ROOT / "docs/domain/areas/ground-surface.md"
CONFLICTS = ROOT / "docs/domain/conflicts.md"

SOURCE_TOKENS = {
    1: ("reg p.1–2 §2", "reg p.21 §2"),
    3: ("reg p.7 §3.4", "reg p.28 §3.7"),
    4: ("reg p.7 §3.6", "[D097]"),
    5: ("[D097]",),
    6: ("reg p.28 §3.10", "reg p.29 §3.10", "[D010]"),
    8: ("reg p.10 §6.1–6.2", "[D097]"),
    10: ("[D098]",),
    12: ("[D018]",),
}

# (1-based row, 0-based column, token). Column 2 is NPM, column 3 is VPM.
NUMBER_TOKENS = (
    (3, 2, "at least 1 m"),
    (3, 3, "at least 1 m"),
    (4, 2, "180 000"),
    (4, 2, "50k"),
    (5, 2, "50 000"),
    (6, 3, "0.05 ha 300 000"),
    (6, 3, "705 000"),
    (6, 3, "1 125 000"),
    (6, 3, "1 650 000"),
    (6, 3, "1 950 000"),
    (6, 3, "2 625 000"),
    (6, 3, "3 150 000"),
    (6, 3, "4 500 000"),
    (6, 3, "excluding collision"),
    (8, 2, "10–40 px per linear metre"),
    (9, 3, "512–1706 px/m"),
    (10, 2, "n/a"),
    (10, 3, "≤ 10 cm"),
    (10, 3, "2 mm – 1 cm"),
)

NONE_ROWS = {1, 2, 3, 5, 6, 7, 8}

PRACTICE_TOKENS = (
    "not regulation",
    "SPOZU",
    "layered cake",
    "6 mm",
    "Flat first",
    "curbs",
    "per linear metre",
    "50k",
    "rejections",
)

ANCHORS = {
    "GND-01": "«если проект относится к отдельному этапу строительства — благоустройство выполняется в пределах границ соответствующего этапа»",
    "GND-03": "«Полигоны по периметру объекта геометрии благоустройства должны быть выдавлены вниз на расстояние не менее 1 метра»",
    "GND-04": "«для благоустройства, его элементов и элементов растительности в сумме – 180 000»",
    "GND-06": "«от 1 Га до 1,5 Га»; «до 3 150 000 треугольных полигонов»; «более 1,5 Га»; «до 4 500 000 треугольных полигонов»",
    "GND-08": "«не меньше 10 пикселей на кв.метр, что при текстуре 2048×2048 соответствует квадрату со сторонами 204 на 204 метров, но не более 40 пикселей на кв.метр»",
}


def sheet_text():
    assert SHEET.is_file(), "Issue #157 requires docs/domain/areas/ground-surface.md"
    return SHEET.read_text(encoding="utf-8")


def _row_line_index(lines, number):
    prefix = f"| GND-{number:02d} —"
    matches = [i for i, line in enumerate(lines) if line.startswith(prefix)]
    assert len(matches) == 1, number
    return matches[0]


def _cells(line):
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def _replace_cell(text, number, column, old, new):
    lines = text.splitlines()
    index = _row_line_index(lines, number)
    cells = _cells(lines[index])
    assert old in cells[column], (number, column, old)
    cells[column] = cells[column].replace(old, new, 1)
    assert old not in cells[column]
    lines[index] = "| " + " | ".join(cells) + " |"
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def sources_contract(text):
    rows = contract(text)
    assert len(rows) == 12
    for number, tokens in SOURCE_TOKENS.items():
        cell = rows[number - 1][1]
        for token in tokens:
            assert token in cell, (number, token)


def numbers_contract(text):
    rows = contract(text)
    for number, column, token in NUMBER_TOKENS:
        cell = rows[number - 1][column]
        if token == "n/a":
            assert cell.startswith("n/a"), cell
        else:
            assert token in cell, (number, column, token)


def coverage_contract(text):
    rows = contract(text)
    assert len(rows) == 12
    for number, row in enumerate(rows, 1):
        if number in NONE_ROWS:
            assert row[5] == "none", number
        else:
            assert row[5] != "none", number
    assert "review" in rows[5][4]
    for token in ("V012", "twinqa/naming.py", "tests/qa/test_mesh_names.py", "partial"):
        assert token in rows[10][5], token
    for token in ("GroundGlass", "254", "Address", "review"):
        assert token in rows[10][4], token


def _practice_bounds(lines):
    practice = lines.index("## Project practice")
    gaps = lines.index("## L2 gaps")
    end = next(i for i in range(practice + 1, len(lines)) if lines[i].startswith("## "))
    return practice, gaps, end


def practice_contract(text):
    lines = text.splitlines()
    table_last = max(i for i, line in enumerate(lines) if line.lstrip().startswith("|"))
    practice, gaps, end = _practice_bounds(lines)
    assert table_last < practice < gaps
    section = "\n".join(lines[practice + 1:end])
    for token in PRACTICE_TOKENS:
        assert token in section, token


def anchors_contract(text):
    for key, quote in ANCHORS.items():
        assert re.search(rf"\*\*{re.escape(key)} — reg p\.", text), key
        assert "«" in quote and quote in text, key
    assert not re.search(r"\]\([^)]*\.png\)", text, re.IGNORECASE)
    assert not list((ROOT / "docs/domain/areas").rglob("*.png"))


def test_ground_sheet_contract():
    rows = contract(sheet_text())
    assert len(rows) == 12
    for number, row in enumerate(rows, 1):
        assert row[0].startswith(f"GND-{number:02d} —")


def test_ground_sources():
    sources_contract(sheet_text())


def test_ground_numbers():
    numbers_contract(sheet_text())


def test_ground_coverage():
    coverage_contract(sheet_text())


def test_ground_name_coverage_negative_probes():
    text = sheet_text()
    coverage_contract(text)
    count = 0
    for column, tokens in ((5, ("V012", "twinqa/naming.py", "tests/qa/test_mesh_names.py", "partial")),
                           (4, ("GroundGlass", "254", "Address", "review"))):
        for token in tokens:
            with pytest.raises(AssertionError):
                coverage_contract(_replace_cell(text, 11, column, token, "UNVERIFIED"))
            count += 1
    assert count == 8


def test_ground_project_practice():
    practice_contract(sheet_text())


def test_ground_anchors():
    anchors_contract(sheet_text())


def test_ground_conflict_c36():
    lines = CONFLICTS.read_text(encoding="utf-8").splitlines()
    matches = [i for i, line in enumerate(lines) if line.startswith("37. Ground small level differences")]
    assert len(matches) == 1
    index = matches[0]
    section_c = next(i for i, line in enumerate(lines) if line.startswith("## C."))
    section_d = next(i for i, line in enumerate(lines) if line.startswith("## D."))
    assert section_c < index < section_d
    assert "Open" in lines[index]


def test_ground_sources_negative_probes():
    text = sheet_text()
    sources_contract(text)
    count = 0
    for number, tokens in SOURCE_TOKENS.items():
        for token in tokens:
            with pytest.raises(AssertionError):
                sources_contract(_replace_cell(text, number, 1, token, ""))
            count += 1
    assert count == sum(len(tokens) for tokens in SOURCE_TOKENS.values())


def test_ground_numbers_negative_probes():
    text = sheet_text()
    numbers_contract(text)
    count = 0
    for number, column, token in NUMBER_TOKENS:
        with pytest.raises(AssertionError):
            numbers_contract(_replace_cell(text, number, column, token, "UNVERIFIED"))
        count += 1
    assert count == len(NUMBER_TOKENS)


def test_ground_gaps_negative_probes():
    text = sheet_text()
    contract(text)
    count = 0
    for number in sorted(NONE_ROWS):
        needle = f"- **GND-{number:02d}:**"
        lines = [line for line in text.splitlines() if not line.startswith(needle)]
        assert len(lines) == len(text.splitlines()) - 1
        mutated = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
        with pytest.raises(AssertionError):
            contract(mutated)
        count += 1
    assert count == 7


def test_ground_practice_negative_probes():
    text = sheet_text()
    practice_contract(text)
    count = 0
    lines = text.splitlines()
    practice, _, end = _practice_bounds(lines)
    section = "\n".join(lines[practice:end])
    for token in PRACTICE_TOKENS:
        assert token in section
        mutated_section = section.replace(token, "")
        assert token not in mutated_section
        mutated_lines = lines[:practice] + mutated_section.split("\n") + lines[end:]
        mutated = "\n".join(mutated_lines) + ("\n" if text.endswith("\n") else "")
        with pytest.raises(AssertionError):
            practice_contract(mutated)
        count += 1

    moved = lines.copy()
    heading = moved.pop(practice)
    gap_at = moved.index("## L2 gaps")
    moved.insert(gap_at + 1, heading)
    mutated = "\n".join(moved) + ("\n" if text.endswith("\n") else "")
    with pytest.raises(AssertionError):
        practice_contract(mutated)
    count += 1
    assert count == len(PRACTICE_TOKENS) + 1
