"""new-case: historical release acceptance docs; no Max or installer execution."""
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/agr-tools/release-0.9.0-acceptance.md"


def test_owner_disposition_is_recorded_once_and_reachable():
    log = (ROOT / "docs/decisions.md").read_text(encoding="utf-8")
    rows = [line for line in log.splitlines() if line.startswith("| D331 |")]
    assert len(rows) == 1
    assert "2026-11-16" in rows[0]
    assert "6915458337" in rows[0]
    text = DOC.read_text(encoding="utf-8")
    assert "[D331]" in text
    overview = (ROOT / "docs/agr-tools/OVERVIEW.md").read_text(encoding="utf-8")
    assert "release-0.9.0-acceptance.md" in overview


REQUIRED = (
    "DEFERRED / NOT MEASURED",
    "waived by Artem 2026-11-16, not available for a past release",
    "ACCEPTED EXISTING RUSSIAN NOTES",
    "6672773049",
    "6672179641",
    "6911505408",
    "6915458337",
    "C:/x/release-agr-tools/user-install",
    "Before/after installed-bundle SHA256: unavailable",
    "780/780",
    "-130",
    "night slot",
    "No Max launch or attach",
    "not rerun",
    "Interactive Undo and light-theme",
    "7cdf77f09695916ed92d098c6ee458664d61ccdc0b58cb3825b0ae5f79dbbf3e",
    "33c67eb8ffe7102a9746c5dc355166cbad154a0aabd0351e7937b030385eeb4f",
)


def problems(text):
    """Small document oracle, not a technical release-acceptance validator."""
    missing = [token for token in REQUIRED if token not in text]
    for heading in ("Technical QA", "User acceptance", "Publication"):
        if f"## {heading}" not in text:
            missing.append(heading)
    for gate in ("Max 2026 panel/button smoke", "Installed-bundle backup/restore"):
        row = next((line for line in text.splitlines() if line.startswith(f"| {gate} |")), "")
        if not row or re.search(r"\bPASS\b", row):
            missing.append(gate)
    return missing


def test_receipts_and_acceptance_boundaries():
    assert problems(DOC.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("gate", ["Max 2026 panel/button smoke", "Installed-bundle backup/restore"])
def test_missing_historical_evidence_cannot_be_promoted_to_pass(gate):
    text = DOC.read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if line.startswith(f"| {gate} |"))
    assert gate in problems(text.replace(row, f"| {gate} | PASS |"))


@pytest.mark.parametrize("token", REQUIRED)
def test_each_required_receipt_or_boundary_is_independently_required(token):
    text = DOC.read_text(encoding="utf-8")
    assert token in problems(text.replace(token, "OMITTED"))


@pytest.mark.parametrize("text", ["", "# Acceptance\nPASS", "| Max 2026 panel/button smoke | PASS |"])
def test_empty_and_partial_receipts_are_not_accepted(text):
    assert problems(text)
