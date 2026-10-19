"""Decor L1 documentation regression; no model compliance is asserted (#152)."""
from itertools import product
from pathlib import Path
import re

import pytest

from test_area_requirement_sheet import contract, find_gap_lines

ROOT = Path(__file__).resolve().parents[1]
SHEET = ROOT / "docs/domain/areas/decor.md"

# Issue #152 scope and independently transcribed regulatory budget values.
REQUIRED = {
    "DEC-01": ("[D051]", "simple solids", "Full detail"),
    "DEC-02": ("reg p.7 §3.1", "reg p.28 §3.3", "silhouette"),
    "DEC-03": ("reg p.7 §3.6", "<= 150 000", "per OKS FBX"),
    "DEC-04": ("reg p.28 §3.9", "<= 1 000 000", "excluding UCX"),
    "DEC-05": ("[D010]", "<= 150 000", "project target", "review"),
    "DEC-06": ("reg p.32 §7", "up to 5 cm", "curb"),
    "DEC-07": ("reg p.8 §3.11", "reg p.29 §3.17", "Triangulated"),
}


def sheet_text():
    assert SHEET.is_file(), "Issue #152 requires docs/domain/areas/decor.md"
    return SHEET.read_text(encoding="utf-8")


def decor_contract(text, evidence_paths=()):
    rows = contract(text)
    indexed = {row[0].split()[0]: row for row in rows}
    assert set(indexed) == set(REQUIRED)
    for key, tokens in REQUIRED.items():
        row = " | ".join(indexed[key])
        for token in tokens:
            assert token in row, (key, token)
    for key, column, bound in (("DEC-03", 2, "150 000"),
                               ("DEC-04", 3, "1 000 000"),
                               ("DEC-05", 2, "150 000"),
                               ("DEC-05", 3, "150 000")):
        assert f"<= {bound}" in indexed[key][column], (key, column, bound)
    for target in re.findall(r"\]\(((?:[^()#]|\([^()]*\))+)(?:#[^)]*)?\)", text):
        assert (SHEET.parent / target).is_file(), target
    for key, page in (("DEC-02", 7), ("DEC-03", 7), ("DEC-04", 28),
                      ("DEC-06", 32), ("DEC-07", 29)):
        assert re.search(rf"\*\*{key}, reg p\.{page} .*«.+»", text)
    assert not re.search(r"\]\([^)]*\.png\)", text, re.IGNORECASE)
    assert not any(Path(path).suffix.lower() == ".png" for path in evidence_paths)
    return rows


def test_decor_requirement_sheet():
    decor_contract(sheet_text())


def test_decor_generated_scope_and_limit_probes():
    text = sheet_text()
    decor_contract(text)
    count = 0
    for key, tokens in REQUIRED.items():
        row = next(line for line in text.splitlines() if line.startswith(f"| {key} "))
        for token in tokens:
            with pytest.raises(AssertionError):
                decor_contract(text.replace(row, row.replace(token, "OMITTED")))
            count += 1
        # Brute-force off-by-one and exclusive-bound mutations of each budget.
        for match in re.finditer(r"<= (?:150 000|1 000 000)", row):
            bound = match.group()[3:]
            for replacement in (f"< {bound}", f"<= {int(bound.replace(' ', '')) - 1}",
                                f"<= {int(bound.replace(' ', '')) + 1}"):
                changed = row[:match.start()] + replacement + row[match.end():]
                with pytest.raises(AssertionError):
                    decor_contract(text.replace(row, changed))
                count += 1
    print(f"Decor scope/limit mutations: {count}/{count} rejected")


def test_decor_generated_gap_and_evidence_probes():
    text = sheet_text()
    decor_contract(text)
    gaps = find_gap_lines(text)
    for _, _, line in gaps:
        with pytest.raises(AssertionError):
            decor_contract(text.replace(line, ""))
    suffixes = ["".join(chars) for chars in product("pP", "nN", "gG")]
    for suffix in suffixes:
        with pytest.raises(AssertionError):
            decor_contract(text + f"\n[render](p07.{suffix})\n")
        with pytest.raises(AssertionError):
            decor_contract(text, [f"decor/evidence/p07.{suffix}"])
    print(f"Decor gap omissions: {len(gaps)}/{len(gaps)} rejected; "
          f"PNG links: {len(suffixes)}/{len(suffixes)} rejected; "
          f"PNG artifacts: {len(suffixes)}/{len(suffixes)} rejected")
