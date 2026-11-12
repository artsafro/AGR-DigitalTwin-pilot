"""new-case: frozen #149 audit completeness, not capability or delivery certification."""
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/research/roadmap-149-audit.md"
# Direct sub-issues returned by GitHub on 2026-11-12, not all descendants.
CHILDREN = {
    150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164,
    165, 166, 175, 176, 180, 181, 182, 183, 184, 185, 187, 188, 189, 190, 191,
    194, 195, 216, 217, 292, 294, 295, 296, 298, 313, 316, 317, 318, 319, 332,
    333, 337, 338, 339, 340, 345, 346, 347, 348, 349, 350, 351, 352, 353,
}


@pytest.mark.parametrize("kind", ["candidate", "story", "child"])
def test_audit_accounts_for_frozen_inputs(kind):
    assert REPORT.is_file(), "#1260 audit report is missing"
    text = REPORT.read_text(encoding="utf-8")
    source = (ROOT / "docs/research/capability-roadmap.md").read_text(encoding="utf-8")
    if kind == "candidate":
        expected = set(re.findall(r"\*\*(T-[A-Z]+-\d+) ", source))
        prefix = r"T-[A-Z]+-\d+"
    elif kind == "story":
        expected = {f"US-{i:02d}" for i in range(1, 22)}
        prefix = r"US-\d+"
    else:
        expected = {f"CH-{i}" for i in CHILDREN}
        prefix = r"CH-\d+"
    rows = [line.split("|")[1:-1] for line in text.splitlines()
            if re.match(rf"^\| ({prefix}) \|", line)]
    actual = [row[0].strip() for row in rows]
    assert set(actual) == expected
    assert len(actual) == len(expected), "duplicate audit rows"
    for row in rows:
        assert len(row) == 5, row
        assert all(cell.strip() for cell in row), row
        assert row[2].strip() in {"done", "partly", "not started", "obsolete"}, row
        assert "#" in row[3] or "No implementation" in row[3], row


def test_audit_local_links_resolve():
    assert REPORT.is_file(), "#1260 audit report is missing"
    links = re.findall(r"\]\(([^)]+)\)", REPORT.read_text(encoding="utf-8"))
    local = [link.split("#")[0] for link in links
             if not link.startswith(("https:", "http:", "#"))]
    assert local, "no repository evidence links"
    for link in local:
        assert (REPORT.parent / link).resolve().exists(), link


def test_audit_proposes_three_to_five_priorities():
    assert REPORT.is_file(), "#1260 audit report is missing"
    rows = [line.split("|")[1:-1] for line in REPORT.read_text(encoding="utf-8").splitlines()
            if re.match(r"^\| NEXT-\d+ \|", line)]
    assert 3 <= len(rows) <= 5
    assert len({row[0].strip() for row in rows}) == len(rows)
    assert all(len(row) == 5 and all(cell.strip() for cell in row) for row in rows)
    assert all(row[2].strip() in {"simple", "medium", "hard"} for row in rows)
