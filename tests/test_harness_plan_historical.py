"""docs/HARNESS_PLAN.md is frozen history, not current agent guidance."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SUPERSEDED_BY = (
    "docs/pipeline.md",
    "docs/decisions.md",
    "docs/agents/WORKFLOW.md",
    "docs/agents/REVIEW_CHECKLIST.md",
    "docs/domain/patterns/INDEX.md",
    "benchmark/README.md",
    "docs/domain/",
    "docs/backlog.md",
    "docs/agents/CAPABILITIES.md",
)


def test_harness_plan_starts_with_historical_note():
    text = (ROOT / "docs" / "HARNESS_PLAN.md").read_text(encoding="utf-8")
    note, _title, _rest = text.partition("\n# ")
    assert note.lstrip().startswith("Historical"), note[:200]
    for doc in SUPERSEDED_BY:
        assert doc in note
        assert (ROOT / doc).exists()


def test_agents_md_does_not_list_harness_plan_as_current():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Harness plan, benchmark etalons, pattern registry: `docs/HARNESS_PLAN.md`" not in agents
    for line in agents.splitlines():
        if "HARNESS_PLAN" in line:
            assert "historical" in line.lower(), line
