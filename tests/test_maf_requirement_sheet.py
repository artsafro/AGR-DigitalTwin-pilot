"""MAF documentation contracts, not geometry checks or delivery acceptance (#180)."""
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHEET = ROOT / "docs/domain/areas/groundel-maf.md"


def sheet_contract(text):
    table = [line for line in text.splitlines() if line.startswith("|")]
    assert len(table) == 26
    rows = [[cell.strip() for cell in line.strip("|").split("|")] for line in table[2:]]
    gaps = text.split("## L2 gaps\n", 1)[1]
    for number, row in enumerate(rows, 1):
        assert len(row) == 7
        assert row[0].startswith(f"MAF-{number:02d} —")
        assert "reg p." in row[1]
        assert all(row)
        assert "](" in row[6]
        assert len(re.findall(rf"^- \*\*MAF-{number:02d}:\*\*", gaps, re.MULTILINE)) == int(row[5] == "none")
    return rows


# Independent transcription of the issue's decisions; these are documentation probes only.
REQUIRED = {
    4: ("[D094]", "overall dimensions", "<= 10 cm", "specification", "not a scale change"),
    20: ("[D096]", "below the Ground surface", "not 'open polygons'", "visible holes remain defects", "C38"),
    23: ("[D095]", "lowest point raised by 10 cm", "projected onto the Ground surface", "sinks 10 cm", "bottom faces are deleted", "not the final shared FBX pivot"),
}


def decision_rows_contract(text):
    rows = sheet_contract(text)
    for number, tokens in REQUIRED.items():
        row = " | ".join(rows[number - 1])
        for token in tokens:
            assert token in row, (number, token)


def test_maf_area_sheet_contract():
    sheet_contract(SHEET.read_text(encoding="utf-8"))


def test_maf_decision_rows():
    decision_rows_contract(SHEET.read_text(encoding="utf-8"))


def test_maf_decision_log_and_conflict():
    log = (ROOT / "docs/decisions.md").read_text(encoding="utf-8")
    for decision, quote in (("D094", "5-10 cm off the specification is fine"),
                            ("D095", "fixed sinking 10 cm"),
                            ("D096", "polygons that go under the ground are not visible")):
        line = next((line for line in log.splitlines() if line.startswith(f"| {decision} |")), "")
        assert "2026-10-15" in line and quote in line and "Artem" in line
    conflicts = (ROOT / "docs/domain/conflicts.md").read_text(encoding="utf-8")
    assert "38. MAF" in conflicts
    assert "Decided 2026-10-15 [D096] (user)" in conflicts


@pytest.mark.parametrize("number", REQUIRED)
def test_maf_generated_decision_probes(number):
    text = SHEET.read_text(encoding="utf-8")
    decision_rows_contract(text)
    row = next(line for line in text.splitlines() if line.startswith(f"| MAF-{number:02d} —"))
    # Exhaust every required clause: dropping attribution, bound, operation or scope must fail.
    for token in REQUIRED[number]:
        with pytest.raises(AssertionError):
            decision_rows_contract(text.replace(row, row.replace(token, "OMITTED")))
    # Exhaust alternative integer centimetre limits around the inclusive 10 cm bound.
    if number == 4:
        for limit in range(0, 21):
            if limit != 10:
                with pytest.raises(AssertionError):
                    decision_rows_contract(text.replace(row, row.replace("<= 10 cm", f"<= {limit} cm")))
        with pytest.raises(AssertionError):
            decision_rows_contract(text.replace(row, row.replace("<= 10 cm", "< 10 cm")))
