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


TEAM_AUTHORS = {"A101", "AlexYo"}
# In-source attribution that may support a team-ownership claim; a load/fileIn path is not one.
ATTRIBUTION_MARKERS = ("macro category", "author line", "header author")


def _in_house_claim_problems(row: dict) -> list[str]:
    """Why an `in-house-utility` row does not carry genuine team attribution (empty = acceptable)."""
    problems: list[str] = []
    if row.get("author") not in TEAM_AUTHORS:
        problems.append(f"author {row.get('author')!r} is not a team author")
    evidence = row.get("provenance_evidence", "").lower()
    if not any(m in evidence for m in ATTRIBUTION_MARKERS):
        problems.append("evidence cites no in-source attribution (path-only or empty)")
    if row.get("author_inferred") and "inferred" not in evidence:
        problems.append("inferred author but evidence does not say the ownership is inferred")
    return problems


def test_in_house_utility_requires_team_attribution() -> None:
    """Unknown author or a workstation path alone must not establish team ownership (PR #605 round 1)."""
    bad = {
        r["name"]: _in_house_claim_problems(r)
        for r in _rows()
        if r["classification"] == "in-house-utility" and _in_house_claim_problems(r)
    }
    assert not bad, bad


def test_edge_connect_segments_is_unattributed() -> None:
    row = next(r for r in _rows() if r["name"] == "edge_connect_segments.ms")
    assert row["classification"] == "unattributed-utility"
    assert "unresolved" in row["provenance_evidence"]


@pytest.mark.parametrize(
    "row",
    [
        {"author": "unknown", "author_inferred": False, "provenance_evidence": "header fileIn path C:/Users/x/a.ms"},
        {"author": "A101", "author_inferred": True, "provenance_evidence": "header path under C:/Users/artsafro/"},
        {"author": "A101", "author_inferred": True, "provenance_evidence": ""},
        {"author": "", "author_inferred": False, "provenance_evidence": "macro category 'A101'"},
        {"author": "Mathieu Jacquin", "author_inferred": False, "provenance_evidence": "header author line"},
        {"author": "A101", "author_inferred": True, "provenance_evidence": "macro category 'A101'"},
    ],
)
def test_in_house_claim_probe_rejects_unsupported(row: dict) -> None:
    assert _in_house_claim_problems(row)


def test_in_house_claim_probe_accepts_explicit_inference() -> None:
    row = {"author": "A101", "author_inferred": True, "provenance_evidence": "macro category 'A101'; ownership inferred"}
    assert not _in_house_claim_problems(row)


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
