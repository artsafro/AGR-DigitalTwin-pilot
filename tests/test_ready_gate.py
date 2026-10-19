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


# Round 1 review (PR #13): the gate must follow Markdown structure, not a global heading map.

MISPLACED = FILLED.replace("## Specification", "## Specification\n\n## Context\n\nRead WORKFLOW.")


def fenced(body, fence):
    return f"{fence}markdown\n{body}\n{fence}\n"


def test_fields_outside_specification_do_not_count():
    """An empty Specification is not filled by field headings that sit under Context."""
    problems = load_gate().gate_problems(MISPLACED)
    for field in load_gate().SPEC_FIELDS:
        assert any(field in p for p in problems), (field, problems)


def test_fenced_contract_does_not_pass():
    gate = load_gate()
    for fence in ("```", "~~~", "````"):
        problems = gate.gate_problems(fenced(FILLED, fence))
        for name in gate.SECTIONS:
            assert any(name in p and "missing" in p for p in problems), (fence, name, problems)


def test_fenced_checkbox_is_not_an_acceptance_item():
    gate = load_gate()
    for fence in ("```", "~~~"):
        body = replace_field(FILLED, "Acceptance", fenced("- [ ] example only", fence))
        assert any("Acceptance" in p for p in gate.gate_problems(body)), fence


def test_fenced_heading_does_not_split_a_field():
    """A heading inside a fenced example is text of the field it sits in, not a new section."""
    gate = load_gate()
    body = replace_field(FILLED, "Requirement", "> quote\n\n~~~\n## Specification\n### Acceptance\n~~~")
    assert gate.gate_problems(body) == []
    body = replace_field(FILLED, "Context", "```\n## Context\n```")
    assert gate.gate_problems(body) == []  # fenced text still fills the field


def test_cli_exit_code_for_malformed_bodies(tmp_path, capsys):
    gate = load_gate()
    good = tmp_path / "good.md"
    good.write_text(FILLED, encoding="utf-8")
    assert gate.main(["--file", str(good)]) == 0
    for name, body in (("misplaced", MISPLACED), ("backtick", fenced(FILLED, "```")),
                       ("tilde", fenced(FILLED, "~~~"))):
        path = tmp_path / f"{name}.md"
        path.write_text(body, encoding="utf-8")
        assert gate.main(["--file", str(path)]) == 1, name
        assert "FAIL" in capsys.readouterr().out, name


# Round 2 review (PR #13): a field's answer is its own text, and indented code is not a checklist.

BORROWED = (FILLED.replace("`main` at `abc1234`.\n", "")
            .replace("### Out of scope", "#### Out of scope")
            .replace("### Evidence the PR must bring", "#### Evidence the PR must bring"))
INDENTED = {
    "spaces": replace_field(FILLED, "Acceptance", "\n    - [ ] example only\n"),
    "tab": replace_field(FILLED, "Acceptance", "\n\t- [ ] example only\n"),
}


def test_empty_field_does_not_borrow_a_nested_field():
    problems = load_gate().gate_problems(BORROWED)
    assert any("Inputs and versions" in p for p in problems), problems


def test_descriptive_subheading_still_fills_a_field():
    """A non-contract subheading under a field is that field's own text."""
    body = replace_field(FILLED, "Inputs and versions", "\n#### Source\n\n`main` at `abc1234`.\n")
    assert load_gate().gate_problems(body) == []


def test_indented_code_checkbox_is_not_an_acceptance_item():
    gate = load_gate()
    for name, body in INDENTED.items():
        assert any("Acceptance" in p for p in gate.gate_problems(body)), name


def test_nested_checklist_items_still_count():
    """An indented checkbox inside a list is a nested item, not code."""
    gate = load_gate()
    body = replace_field(FILLED, "Acceptance", "\n- [ ] parent\n    - [ ] child\n\t- [ ] tab child\n")
    assert gate.gate_problems(body) == []
    body = replace_field(FILLED, "Acceptance", "\n- Items:\n\n    - [ ] nested only\n")
    assert gate.gate_problems(body) == []


def test_cli_exit_code_for_round_two_bodies(tmp_path, capsys):
    gate = load_gate()
    for name, body in (("borrowed", BORROWED), *INDENTED.items()):
        path = tmp_path / f"{name}.md"
        path.write_text(body, encoding="utf-8")
        assert gate.main(["--file", str(path)]) == 1, name
        out = capsys.readouterr().out
        assert "FAIL" in out and ("Inputs and versions" in out or "Acceptance" in out), (name, out)
