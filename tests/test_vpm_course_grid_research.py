"""new-case: #1314 research packet completeness, not a UV production validator."""

from pathlib import Path
import re

import pytest


REPORT = Path(__file__).resolve().parents[1] / "docs/research/vpm-course-grid-1314.md"


@pytest.mark.parametrize("heading", [
    "## 1. Evidence and 4BK session",
    "## 2. Techniques and tools",
    "## 3. Gaps against current code",
    "## 4. Proposed procedure",
    "## 5. Acceptance metrics",
    "## 6. Candidate CLI contract",
    "## 7. Questions for Artem",
])
def test_research_acceptance_sections(heading):
    assert heading in REPORT.read_text(encoding="utf-8")


def test_research_local_citations_resolve():
    text = REPORT.read_text(encoding="utf-8")
    targets = re.findall(r"\]\(([^)]+)\)", text)
    local = [target.split("#", 1)[0] for target in targets if "://" not in target]
    assert local, "The research must cite its domain and implementation sources"
    for target in local:
        assert (REPORT.parent / target).is_file(), target
