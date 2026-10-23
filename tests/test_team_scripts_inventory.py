"""Consistency of the Telegram script inventory (issue #540).

Pattern: n/a | new-case: provenance and totals of docs/research/team-scripts-inventory.json.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs" / "research" / "team-scripts-inventory.json"
REPORT = ROOT / "docs" / "research" / "team-scripts-audit.md"

ALLOWED = {"in-house", "in-house-utility", "unattributed-utility", "third-party", "export-artifact"}
UTILITY = {"in-house-utility", "unattributed-utility"}
# Files whose header names an external author or product (audit #540).
EXTERNAL_HEADER = {
    "zOffTy Tools-Copitor_v3.mcr": "Mathieu Jacquin",
    "uniconnector_v4.23.3_0.ms": "Nikolay Litvinov",
    "dragNDropReferences11.ms": "Christoph Buelter",
    "imagecomphelper.ms": "Christoph Buelter",
}


def _rows() -> list[dict]:
    return json.loads(INVENTORY.read_text(encoding="utf-8"))["files"]


def _report_totals(text: str) -> dict[str, int]:
    line = next(ln for ln in text.splitlines() if ln.startswith("Classification field in the JSON:"))
    totals = {name: int(n) for name, n in re.findall(r"`([a-z-]+)` (\d+)", line)}
    if not totals:
        raise ValueError(f"no totals parsed from: {line!r}")
    return totals


def test_classifications_are_known() -> None:
    unknown = {r["name"]: r["classification"] for r in _rows() if r["classification"] not in ALLOWED}
    assert not unknown, unknown


@pytest.mark.parametrize("name,author", sorted(EXTERNAL_HEADER.items()))
def test_external_header_is_third_party(name: str, author: str) -> None:
    row = next(r for r in _rows() if r["name"] == name)
    assert row["classification"] == "third-party"
    assert row["author"] == author
    assert row["author_inferred"] is False


def test_utility_rows_carry_provenance_evidence() -> None:
    missing = [r["name"] for r in _rows() if r["classification"] in UTILITY and not r.get("provenance_evidence", "").strip()]
    assert not missing, missing


def test_named_non_inferred_author_is_not_team_utility() -> None:
    """A signed external author must not sit in a utility bucket that implies team ownership."""
    team = {"unknown", "A101", "AlexYo"}
    bad = [
        r["name"]
        for r in _rows()
        if r["classification"] in UTILITY and not r["author_inferred"] and r["author"] not in team
    ]
    assert not bad, bad


def test_report_totals_match_json() -> None:
    rows = _rows()
    counts = Counter(r["classification"] for r in rows)
    totals = _report_totals(REPORT.read_text(encoding="utf-8"))
    assert totals == dict(counts)
    assert sum(totals.values()) == len(rows)


def test_report_totals_parser_fails_closed() -> None:
    with pytest.raises(StopIteration):
        _report_totals("no totals here")
    with pytest.raises(ValueError):
        _report_totals("Classification field in the JSON: nothing")
