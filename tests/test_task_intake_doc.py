"""Task intake procedure (D186): the agent-facing doc keeps its four steps, its decision anchor and its AGENTS.md link.

Pattern: n/a | new-case: presence/coverage guard for an agent procedure doc (PR #576 review round 1, P1).
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "agents" / "task-intake.md"


def _text() -> str:
    return DOC.read_text(encoding="utf-8")


def test_heading_carries_d186():
    first = _text().splitlines()[0]
    assert first.startswith("# Task intake") and "[D186]" in first


def test_four_steps_in_order():
    t = _text()
    full = t[t.index("## Full intake"):t.index("## Preflight")]
    steps = re.findall(r"^(\d)\. (.+)$", full, re.M)
    assert [n for n, _ in steps[:4]] == ["1", "2", "3", "4"]
    body = " ".join(s for _, s in steps[:4]).lower()
    for needle in ("read the sources", "at most 5 questions", "his words verbatim", "first piece"):
        assert needle in body, needle


def test_worker_preflight_section_present():
    assert "## Preflight (card worker)" in _text()


def test_agents_md_links_the_doc_with_d186():
    line = next(l for l in (ROOT / "AGENTS.md").read_text(encoding="utf-8").splitlines() if "task-intake.md" in l)
    assert "docs/agents/task-intake.md" in line and "[D186]" in line


def test_d186_is_a_single_decision_row():
    rows = re.findall(r"^\| D186 \|", (ROOT / "docs" / "decisions.md").read_text(encoding="utf-8"), re.M)
    assert len(rows) == 1


def test_harness_tasks_require_a_before_after_metric():
    checklist = _text()[_text().index("## Checklist"):]
    assert "before/after metric" in checklist.lower()
    assert "how and when it is measured" in checklist
    # Reuse the existing measures, never add tooling for the metric.
    for needle in ("tools/hooks/usage_log.py stats", "context-diet", "entry_budget.py", "kpi/readiness"):
        assert needle in checklist, needle


def test_guard_prompt_metric_not_paired_with_usage_log():
    # The 'guard prompts per session' metric names no counting command: guard asks/denials are not recorded
    # (guard.py prints an ask/allow decision to the hook stdout and nothing logs it). It must say so, and
    # `usage_log.py stats` must stay next to subagent/skill/command counts only.
    checklist = _text()[_text().index("## Checklist"):]
    assert "guard" in checklist.lower()
    assert "not measured today" in checklist.lower()
    assert "guard prompts per session" not in checklist


def test_pr_template_asks_for_the_before_after_numbers():
    template = (ROOT / ".github" / "pull_request_template.md").read_text(encoding="utf-8")
    assert "before/after metric" in template.lower()
    assert "not measured" in template
