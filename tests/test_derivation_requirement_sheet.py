"""Derivation L1 documentation regression; no model compliance is asserted (#155)."""
from pathlib import Path
import re

import pytest

from test_area_requirement_sheet import contract, find_gap_lines

ROOT = Path(__file__).resolve().parents[1]
SHEET = ROOT / "docs/domain/areas/derivation.md"

REQUIRED = {
    "DER-01": ("[D010]", "reg p.7 §3.6", "reg p.28 §3.9", "<= 150 000", "<= 1 000 000", "excluding UCX", "review"),
    "DER-02": ("reg p.4 §1.3", "reg p.24 §1.3", "All OKS and Ground", "identically"),
    "DER-03": ("reg p.8 §3.11", "reg p.29 §3.17", "quad", "triangulated"),
    "DER-04": ("[D030]", "1001"),
    "DER-05": ("LEVEL_", "[D045]", "reg p.28 §3.1"),
    "DER-06": ("reg p.4 §4", "[D017]", "_Light.fbx", "001-250"),
    "DER-07": ("reg p.10 §8.1", "rotation 0"),
    "DER-08": ("reg p.10 §8.2", "Moscow"),
    "DER-09": ("reg p.32 §9.2-9.4", "reg p.33 §9.4-9.5", "[D018]", "0,0,0", "Z = project zero", "<= 1 mm"),
    "DER-10": ("reg p.9 §5.1-5.3", "reg p.30 §4.2", "embedded", "External PNG", "<= 3 MB", "2048 or 4096"),
    "DER-11": (">= 8 px", ">= 16 px", ">= 32 px", "1001"),
    "DER-12": ("reg p.9 §4.5-4.6, §5.11", "100", "7"),
    "DER-13": ("[D014]", "DirectX"),
    "DER-14": ("[D020]", "0.003-0.01 m"),
    "DER-15": ("reg p.36 §13.3", "001-999", "Not part of the NPM package"),
    "DER-16": ("reg p.26 §1.2", "[D011]", "[D016]", "FBX files only"),
    "DER-17": ("reg p.11 §10.3.1-3.2", "reg p.33 §10.4.1", "_01.fbx", "_20.fbx"),
    "DER-18": ("001-020", "[D019]", "SM_Address_Main"),
    "DER-19": ("T_Address_Diffuse_1.1001.png", "M_Glass_07"),
    "DER-20": ("<= 254",),
    "DER-21": ("reg p.7 §2.1-2.4", "reg p.26 §1.3", "Up to 20 FBX"),
}

# Each inclusive bound is asserted in its profile cell so one mutated copy is rejected.
PROFILE_BOUNDS = {
    "DER-01": ((2, "<= 150 000"), (3, "<= 150 000"), (3, "<= 1 000 000")),
    "DER-10": ((2, "<= 3 MB"),),
    "DER-11": ((2, ">= 8 px"), (3, ">= 16 px"), (3, ">= 32 px")),
    "DER-20": ((2, "<= 254"),),
}

QUOTE_ANCHORS = ((1, 7), (3, 29), (6, 4), (9, 33), (10, 30), (15, 36), (18, 12))
GAP_IDS = {"DER-02", "DER-08", "DER-12", "DER-18", "DER-20"}
BOUND_ROWS = {"DER-01", "DER-10", "DER-11", "DER-20"}


def sheet_text():
    assert SHEET.is_file(), "Issue #155 requires docs/domain/areas/derivation.md"
    return SHEET.read_text(encoding="utf-8")


def derivation_contract(text, evidence_paths=()):
    rows = contract(text)
    indexed = {row[0].split()[0]: row for row in rows}
    assert len(rows) == 21
    assert set(indexed) == set(REQUIRED)
    for key, tokens in REQUIRED.items():
        row = " | ".join(indexed[key])
        for token in tokens:
            assert token in row, (key, token)
    for key, checks in PROFILE_BOUNDS.items():
        for column, bound in checks:
            assert bound in indexed[key][column], (key, column, bound)
    for target in re.findall(r"\]\(((?:[^()#]|\([^()]*\))+)(?:#[^)]*)?\)", text):
        assert (SHEET.parent / target).is_file(), target
    for number, page in QUOTE_ANCHORS:
        assert re.search(rf"\*\*DER-{number:02d}, reg p\.{page} .*«.+»", text)
    assert {gid for _, gid, _ in find_gap_lines(text)} == GAP_IDS
    assert not re.search(r"\]\([^)]*\.png\)", text, re.IGNORECASE)
    assert not any(Path(path).suffix.lower() == ".png" for path in evidence_paths)
    assert "uv run --extra pdf-review python -c" in text and "get_pixmap" in text
    return rows


def test_derivation_requirement_sheet():
    derivation_contract(sheet_text())


def test_derivation_generated_token_probes():
    text = sheet_text()
    derivation_contract(text)
    count = 0
    for key, tokens in REQUIRED.items():
        row = next(line for line in text.splitlines() if line.startswith(f"| {key} "))
        for token in tokens:
            with pytest.raises(AssertionError):
                derivation_contract(text.replace(row, row.replace(token, "OMITTED")))
            count += 1
        if key not in BOUND_ROWS:
            continue
        for match in re.finditer(r"(<=|>=) (\d+(?: \d+)*)", row):
            operator, number = match.group(1), match.group(2)
            value = int(number.replace(" ", ""))
            for replacement in (f"< {number}", f"{operator} {value - 1}", f"{operator} {value + 1}"):
                changed = row[:match.start()] + replacement + row[match.end():]
                with pytest.raises(AssertionError):
                    derivation_contract(text.replace(row, changed))
                count += 1
    print(f"{count}/{count} rejected")


def test_derivation_generated_gap_and_evidence_probes():
    text = sheet_text()
    derivation_contract(text)
    gaps = find_gap_lines(text)
    for _, _, line in gaps:
        with pytest.raises(AssertionError):
            derivation_contract(text.replace(line, ""))
    quote_lines = [
        line for line in text.splitlines()
        if re.search(r"\*\*DER-\d{2}, reg p\.\d+ .*«.+»", line)
    ]
    assert len(quote_lines) == 7
    for line in quote_lines:
        with pytest.raises(AssertionError):
            derivation_contract(text.replace(line, ""))
    suffixes = ("png", "PNG", "Png", "pNg")
    for suffix in suffixes:
        with pytest.raises(AssertionError):
            derivation_contract(text + f"\n[render](evidence/p32.{suffix})\n")
        with pytest.raises(AssertionError):
            derivation_contract(text, [f"p32.{suffix}"])
    print(f"Derivation gap omissions: {len(gaps)}/{len(gaps)} rejected; "
          f"quote omissions: {len(quote_lines)}/{len(quote_lines)} rejected; "
          f"PNG links: {len(suffixes)}/{len(suffixes)} rejected; "
          f"PNG artifacts: {len(suffixes)}/{len(suffixes)} rejected")
