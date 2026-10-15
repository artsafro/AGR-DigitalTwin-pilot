"""The ready-for-agent gate: a ticket is ready only when its contract is filled (#130)."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / ".github" / "ISSUE_TEMPLATE" / "task.md"


def load_gate():
    path = ROOT / "tools" / "check_ready_gate.py"
    spec = importlib.util.spec_from_file_location("check_ready_gate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FILLED = """\
## Requirement

> Сделай шаблон задачи. (user, 2026-10-14)

## Specification

### Acceptance

- [ ] `.github/ISSUE_TEMPLATE/task.md` with the three sections
- [ ] `uv run pytest -q` green

### Inputs and versions

`main` at `abc1234`.

### Out of scope

None.

### Evidence the PR must bring

The pytest numbers and the gate output over the open issues.

## Context

`docs/agents/WORKFLOW.md`, `docs/agents/issue-tracker.md`.
"""


def replace_field(body, heading, text):
    """Replace the content under one heading (up to the next heading) with text."""
    lines, out, skipping = body.splitlines(), [], False
    for line in lines:
        if line.startswith("#"):
            skipping = line.lstrip("#").strip() == heading
            out.append(line)
            if skipping:
                out.append(text)
            continue
        if not skipping:
            out.append(line)
    return "\n".join(out)


def test_filled_ticket_passes():
    assert load_gate().gate_problems(FILLED) == []


def test_empty_template_fails_on_every_field():
    gate = load_gate()
    problems = gate.gate_problems(TEMPLATE.read_text(encoding="utf-8"))
    for field in gate.FIELDS:
        assert any(field in p for p in problems), (field, problems)


def test_template_has_the_three_sections_and_every_field():
    gate = load_gate()
    text = TEMPLATE.read_text(encoding="utf-8")
    assert text.startswith("---\n") and "\nname:" in text.split("---")[1]
    found = [h for _, h in gate.headings(text)]
    for name in ("Requirement", "Specification", "Context", *gate.SPEC_FIELDS):
        assert name in found, name


def test_each_empty_field_fails_alone():
    gate = load_gate()
    for field in gate.FIELDS:
        problems = gate.gate_problems(replace_field(FILLED, field, "<!-- fill me -->"))
        assert problems and all(field in p for p in problems), (field, problems)


def test_missing_section_fails():
    gate = load_gate()
    body = FILLED.replace("## Context", "## Notes")
    assert any("Context" in p and "missing" in p for p in gate.gate_problems(body))


def test_acceptance_needs_a_checkable_item():
    gate = load_gate()
    prose = replace_field(FILLED, "Acceptance", "It works.")
    assert any("Acceptance" in p for p in gate.gate_problems(prose))
    blank_box = replace_field(FILLED, "Acceptance", "- [ ] ")
    assert any("Acceptance" in p for p in gate.gate_problems(blank_box))


def test_legacy_ticket_without_specification_fails():
    """The old to-tickets body (What to build / Acceptance criteria) does not pass the gate."""
    legacy = ("## What to build\n\nA thing.\n\n## Acceptance criteria\n\n- [ ] it works\n\n"
              "## Blocked by\n\n- None\n")
    problems = load_gate().gate_problems(legacy)
    assert any("Specification" in p for p in problems)


def test_docs_name_the_gate_recitation_and_contract():
    tracker = (ROOT / "docs/agents/issue-tracker.md").read_text(encoding="utf-8")
    assert "tools/check_ready_gate.py" in tracker and "needs-info" in tracker
    workflow = (ROOT / "docs/agents/WORKFLOW.md").read_text(encoding="utf-8")
    assert "Recitation" in workflow
    for line in ("## Requirement", "Context:"):
        assert line in workflow, line
    handover = (ROOT / ".claude/commands/handover.md").read_text(encoding="utf-8")
    assert "Requirement" in handover
    commands = (ROOT / "docs/agents/COMMANDS.md").read_text(encoding="utf-8")
    assert ".github/ISSUE_TEMPLATE/task.md" in commands
