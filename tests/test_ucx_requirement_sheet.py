"""Documentation contract for the UCX calibration sheet, not a geometry validator."""
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHEET = ROOT / "docs/domain/areas/ucx.md"
HEADER = ["Requirement", "reg page", "NPM", "VPM", "How it is checked", "L2 coverage", "Detail in"]


def sheet_text():
    assert SHEET.is_file(), "Required UCX requirement sheet is missing"
    return SHEET.read_text(encoding="utf-8")


def contract(text):
    lines = [line for line in text.splitlines() if line.startswith("|")]
    cells = [[c.strip() for c in re.split(r"(?<!\\)\|", line.strip("|"))] for line in lines]
    assert cells[0] == HEADER
    assert len(cells) == 20  # header, separator, 18 requirements; exactly one table
    rows = cells[2:]
    gaps = text.split("## L2 gaps\n", 1)[1]
    for i, row in enumerate(rows, 1):
        assert len(row) == 7
        assert row[0].startswith(f"R{i:02d} ")
        assert re.search(r"reg p\.\d+(?:-\d+)? §[\d.]+|\[D\d+\]", row[1])
        assert row[2] == "n/a"
        assert row[3] and row[4] and row[5]
        assert "](" in row[6]
        assert len(re.findall(rf"^- R{i:02d}:", gaps, re.MULTILINE)) == int(row[5] == "none")
    for target in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", text):
        assert (SHEET.parent / target).is_file(), target
    return rows


def quote_evidence_contract(text, filenames):
    assert not any(name.endswith(".png") for name in filenames), "Keep rendered PNGs local-only"
    assert not re.search(r"\]\([^)]*\.png\)", text), "Evidence must not depend on PNG links"
    for row, page in (("R04", 36), ("R08", 34), ("R11", 36), ("R12", 36), ("R15", 36)):
        assert re.search(rf"\*\*{row} — reg p\.?p?\.{page}.*[«“]", text)
    assert "uv run --extra pdf-review python -c" in text
    assert "get_pixmap" in text


def test_ucx_quote_evidence_is_binary_independent():
    evidence = SHEET.parent / "ucx-evidence"
    text = (evidence / "review.md").read_text(encoding="utf-8")
    quote_evidence_contract(text, [path.name for path in evidence.iterdir()])
    # Brute-force all five page renders: reintroducing any binary must fail.
    for page in (29, 33, 34, 36, 37):
        with pytest.raises(AssertionError):
            quote_evidence_contract(text, [f"reg-p{page}.png"])


def test_ucx_sheet_contract():
    contract(sheet_text())


def numeric_contract(rows):
    # Independently transcribed from rendered pages 34, 36, 37; D012 resolves C3.
    expected = {
        4: "<= 5 cm", 8: "001..999", 10: "0.02-1 cm",
        11: "<= 10 cm", 12: "<= 30 cm", 13: "<= 1 m",
        15: "n < 50,000: 15,000; otherwise min(ceil(n * 0.05), 100,000)",
    }
    for number, value in expected.items():
        assert value in rows[number - 1][3]
    return expected


def test_ucx_sheet_numeric_and_profile_index():
    rows = contract(sheet_text())
    expected = numeric_contract(rows)
    # Perturb every indexed numeric constraint: the documentation probe must reject it.
    for number, value in expected.items():
        changed = [row.copy() for row in rows]
        changed[number - 1][3] = changed[number - 1][3].replace(value, "UNVERIFIED_LIMIT")
        with pytest.raises(AssertionError):
            numeric_contract(changed)
    assert "Ground" in rows[1][3]
    assert all(word in rows[2][3] for word in ("MAF", "lighting", "vegetation", "none"))
    assert "recommendation" in rows[9][3]
    assert "[D012]" in rows[14][1]


def test_ucx_sheet_generated_negative_probes():
    text = sheet_text()
    rows = contract(text)
    # Brute-force every row: no unsourced row, no UCX rule transferred to NPM,
    # and every uncovered requirement has exactly its corresponding gap entry.
    for row in rows:
        original = "| " + " | ".join(row) + " |"
        for column, replacement in ((1, "unsourced"), (2, "required")):
            changed = row.copy()
            changed[column] = replacement
            with pytest.raises(AssertionError):
                contract(text.replace(original, "| " + " | ".join(changed) + " |"))
        if row[5] == "none":
            with pytest.raises(AssertionError):
                contract(text.replace(f"- {row[0][:3]}:", "- OMITTED:"))
    # Each uncovered row must appear exactly once, not merely be present.
    for row in rows:
        if row[5] == "none":
            with pytest.raises(AssertionError):
                contract(text + f"\n- {row[0][:3]}: duplicate gap\n")
    # At most one requirement table: any duplicated table fails the contract.
    with pytest.raises(AssertionError):
        contract(text + "\n" + "\n".join(line for line in text.splitlines() if line.startswith("|")))
