"""Documentation contract for #131; these checks do not grade agent behavior."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def section(text, heading):
    marker = f"## {heading}\n"
    assert marker in text, f"Missing documented contract: {heading}"
    return text.split(marker, 1)[1].split("\n## ", 1)[0]


def test_quoted_rule_escalation_contract():
    workflow = read("docs/agents/WORKFLOW.md")
    escalation = section(workflow, "Escalation (#131)")
    assert "rule, quote and decision id" in escalation
    assert "without asking the user again" in escalation
    assert "PR" in escalation and "source path" in escalation
    assert "no rule" in escalation and "conflict" in escalation
    assert "mandatory confirmations" in escalation
    assert "Worked example: quoted rule" in escalation
    assert "D048" in escalation and "depth by default" in escalation
    questions = section(workflow, "Questions-only")
    assert "Escalation" in questions
    assert "architecture, acceptance, destructive actions and publication" in questions
    row = next(line for line in questions.splitlines() if line.startswith("| Question to the user |"))
    assert row.count("ask if unresolved") == 3
    assert "#escalation-131" in row
    assert "Merges stay on the user's command only" in escalation


def test_librarian_has_exactly_two_answer_shapes():
    librarian = read(".claude/agents/pattern-librarian.md")
    answer = section(librarian, "Answer format")
    blocks = answer.split("```text\n")[1:]
    assert len(blocks) == 2
    assert blocks[0].split("```", 1)[0].splitlines() == [
        "rule: <applicable rule; source path#section>",
        "quote: <verbatim quote, at most 3 lines>",
        "decision id: D<n>",
    ]
    assert blocks[1].split("```", 1)[0].strip() == "no rule"
    assert "missing decision id" in answer
    assert "open conflict" in answer
    assert "Never invent" in answer
    assert "Optional diagnostic" in answer


def test_p2_issue_routing_contract():
    escalation = section(read("docs/agents/WORKFLOW.md"), "Escalation (#131)")
    p2 = escalation.split("### (b) P2 findings to issues", 1)
    assert len(p2) == 2, "Missing P2 routing procedure"
    assert "without asking the user" in p2[1]
    assert "duplicate" in p2[1] and "review round" in p2[1]
    assert "Worked example: P2 finding" in p2[1]
    assert "does not authorize a merge" in p2[1]
    checklist = read("docs/agents/REVIEW_CHECKLIST.md")
    assert "WORKFLOW.md#escalation-131" in checklist
    assert "without asking the user" in checklist


def test_worked_rule_quote_matches_source_and_decision():
    escalation = section(read("docs/agents/WORKFLOW.md"), "Escalation (#131)")
    quotes = [line[2:] for line in escalation.splitlines() if line.startswith("> ")]
    assert quotes, "Worked example must quote a real rule"
    source = read("docs/domain/conflicts.md")
    assert all(quote in source for quote in quotes)
    decision = next(line for line in read("docs/decisions.md").splitlines() if "| D048 |" in line)
    assert "0.4" in decision and "depth" in decision
