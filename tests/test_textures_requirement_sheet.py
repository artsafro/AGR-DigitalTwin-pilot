"""Issue #154: Textures L1 index, not texture-production compliance tests."""
import re

import pytest

from test_area_requirement_sheet import (
    AREAS_DIR, contract, assert_rejected, find_gap_lines, mutate_line,
    row_str, table_line_indices, parse_cells,
)

SHEET = AREAS_DIR / "textures.md"


def sheet_text():
    assert SHEET.is_file(), "Textures L1 requirement sheet is missing"
    return SHEET.read_text(encoding="utf-8")


def test_textures_requirement_sheet():
    text = sheet_text()
    rows = contract(text)
    assert len(rows) == 20
    assert [r[0].split()[0] for r in rows] == [f"TEX-{n:02}" for n in range(1, 21)]
    for target in re.findall(r"\]\(((?:[^()#]|\([^()]*\))+)(?:#[^)]*)?\)", text):
        assert (SHEET.parent / target).is_file(), target
    for req, page in (("TEX-01", 11), ("TEX-02", 12), ("TEX-04", 26), ("TEX-09", 3), ("TEX-19", 18)):
        assert re.search(rf"\*\*{req}, reg p\.{page} .*“", text), req
    assert not re.search(r"\]\([^)]*\.png\)", text)
    assert "[D013]" in rows[8][1] and "[D020]" in rows[6][1]
    assert "[D097]" in rows[16][1] and "[D097]" in rows[17][1]


def test_textures_exhaustive_document_invariants():
    """Mutate each row source and each none-gap; production checks stay out of scope."""
    text = sheet_text()
    rows = contract(text)
    lines = text.splitlines()
    for idx in table_line_indices(lines)[2:]:
        cells = parse_cells(lines[idx])
        cells[1] = ""
        assert_rejected(mutate_line(text, idx, row_str(cells)), "missing source")
    gaps = find_gap_lines(text)
    for idx, req, _ in gaps:
        assert_rejected(mutate_line(text, idx, None), f"missing gap {req}")
    assert len(gaps) == sum(r[5] == "none" for r in rows)
    print(f"Textures sources: {len(rows)}/{len(rows)}; gaps: {len(gaps)}/{len(gaps)} rejected")


LIMIT_ANCHORS = [
    (1, 2, "_d"), (1, 2, "_n"), (1, 2, "_o"), (1, 2, "_m"), (1, 2, "_r"),
    (4, 3, "3-2100"), (6, 2, "2048"), (6, 2, "3 MiB"),
    (7, 2, "no alpha"), (8, 2, "only as a pair"),
    (9, 2, "128×128"), (10, 3, "4096×4096"),
    (12, 3, "256×256"), (13, 2, "≥ 8 px"), (13, 3, "≥ 32 px"),
    (14, 3, "≥ 1 polygon"), (15, 2, "≤ 20 sets"), (15, 2, "≤ 22"),
    (16, 2, "≤ 512×512"), (16, 2, "≤ 2048×2048"),
    (17, 2, "10-40 px/m"), (18, 3, "520-1706 px/m"),
    (19, 2, "baking"),
]


@pytest.mark.parametrize("number,column,token", LIMIT_ANCHORS)
def test_textures_scope_and_limit_anchors(number, column, token):
    """Literal anchors independently transcribed from page images or cited decisions."""
    rows = contract(sheet_text())
    assert token in rows[number - 1][column]


def limit_anchor_contract(text):
    rows = contract(text)
    for number, column, token in LIMIT_ANCHORS:
        assert token in rows[number - 1][column], (number, token)


def test_textures_limit_anchor_omission_probes():
    """Every documented limit anchor must detect its own omission, not enforce L2."""
    text = sheet_text()
    limit_anchor_contract(text)
    lines = text.splitlines()
    indices = table_line_indices(lines)[2:]
    for number, column, token in LIMIT_ANCHORS:
        idx = indices[number - 1]
        cells = parse_cells(lines[idx])
        cells[column] = cells[column].replace(token, "")
        with pytest.raises(AssertionError):
            limit_anchor_contract(mutate_line(text, idx, row_str(cells)))
    print(f"Textures limit omissions: {len(LIMIT_ANCHORS)}/{len(LIMIT_ANCHORS)} rejected")
