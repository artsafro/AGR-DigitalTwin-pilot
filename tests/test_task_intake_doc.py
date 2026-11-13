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


def test_guard_prompt_metric_names_denial_source_and_marks_asks_unmeasured():
    # The 'guard prompts per session' metric names a real source for denials and says asks are unmeasured:
    # hook denials -> `tools/hooks/agent_trace.py --transcript <session.jsonl>` (the `Hook denials` field);
    # guard asks -> "not measured today". `usage_log.py stats` stays next to subagent/skill/command counts
    # only, never next to the guard metric. The doc wraps "guard prompts per session" across a line break,
    # so assert on a whitespace-collapsed checklist, never on the raw text (a bare `"... not in ..."` on the
    # raw text would pass for the wrong reason).
    checklist = _text()[_text().index("## Checklist"):]
    collapsed = " ".join(checklist.split()).lower()
    guard_metric = collapsed[collapsed.index("guard prompts per session"):
                             collapsed.index("say how and when it is measured")]
    # Denials have a real source; asks are not measured today.
    assert "agent_trace.py --transcript <session.jsonl>" in guard_metric
    assert "hook denials" in guard_metric
    assert "guard asks are not measured today" in guard_metric
    # `usage_log.py stats` is not paired with the guard metric.
    assert "usage_log.py stats" not in guard_metric
    # Every `usage_log.py stats` mention sits next to subagent / skill / command counts.
    for m in re.finditer(r"usage_log\.py stats", collapsed):
        window = collapsed[max(0, m.start() - 40):m.start() + 80]
        assert any(w in window for w in ("subagent", "skill", "command")), window


def test_pr_template_asks_for_the_before_after_numbers():
    template = (ROOT / ".github" / "pull_request_template.md").read_text(encoding="utf-8")
    assert "before/after metric" in template.lower()
    assert "not measured" in template


def test_check_level_intake_contract():
    for path in (".github/ISSUE_TEMPLATE/task.md", "docs/agents/task-intake.md"):
        text = " ".join((ROOT / path).read_text(encoding="utf-8").split())
        for clause in (
            "level: fast | standard | full",
            "orchestrator/agent sets",
            "at intake",
            "Artem overrides with one word",
            "[D271]",
            "TASK_TO_MODEL.md#check-levels",
        ):
            assert clause in text, (path, clause)
    intake = " ".join(_text().split())
    assert "first message" in intake
    assert "up a level" in intake and "never down" in intake
    assert "Check level is separate from" in intake


def _level_policy() -> str:
    text = (ROOT / "docs/procedure/TASK_TO_MODEL.md").read_text(encoding="utf-8")
    assert "## Check levels" in text
    return text.split("## Check levels", 1)[1].split("## GATES", 1)[0]


def test_check_level_worker_policy():
    policy = " ".join(_level_policy().split())
    for clause in (
        "[D271]",
        "When Artem is online, open the scene in his DCC version and give the absolute path instead of renders",
        "Render only for board cards without him",
        "`fast`: 1 image",
        "`standard`: 1 image per item + 1 overview",
        "Extra angles only for a defect Artem named",
        "one machine readback (IDs/UV/count, 1-2 calls)",
        "one dt-reviewer round on committed job scripts",
        "one PR per job",
        "Artem accepts the picture or opened scene",
        "second correction on the same point",
        "does not waive mandatory gates",
    ):
        assert clause in policy, clause


def test_check_level_table():
    policy = _level_policy()
    rows = [line for line in policy.splitlines() if line.startswith("| `")]
    assert len(rows) == 3
    expected = {
        "fast": ("colouring", "re-export", "no pytest", "no code review"),
        "standard": ("new node", "jobs/", "exported file", "dt-reviewer"),
        "full": ("validators", "standards/", "schemas", "shared src/", "passed=true",
                 "affected tests", "one full suite per PR", "probes", "receipts"),
    }
    for level, clauses in expected.items():
        row = next(line for line in rows if line.startswith(f"| `{level}` |"))
        for clause in clauses:
            assert clause in row, (level, clause)


def test_check_level_decision_is_recorded_and_linked():
    log = (ROOT / "docs/decisions.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| D271 \|.*$", log, re.M)
    assert len(rows) == 1
    assert rows[0].split("|")[-2].strip().startswith("backfill")
    # Renumbering during a main merge must also update the generated heading anchor.
    intake = (ROOT / "docs/agents/task-intake.md").read_text(encoding="utf-8")
    procedure = (ROOT / "docs/procedure/TASK_TO_MODEL.md").read_text(encoding="utf-8")
    decision = rows[0].split("|")[1].strip()
    assert f"## Check level [{decision}]" in intake
    assert f"task-intake.md#check-level-{decision.lower()}" in procedure
    for clause in ("2026-11-12", "#1273", "#1277", "canopy", "separate cards", "1-2 calls"):
        assert clause in rows[0], clause
    for path in ("docs/agents/task-intake.md", ".github/ISSUE_TEMPLATE/task.md",
                 "docs/procedure/TASK_TO_MODEL.md", "docs/domain/validation.md"):
        assert "[D271]" in (ROOT / path).read_text(encoding="utf-8"), path


