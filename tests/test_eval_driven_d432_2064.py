"""#2064: the eval-driven development principle is a real D-row and every place agents read it cites it.

new-case: tests/test_eval_driven_d432_2064.py - D432 citation guard (decisions.md, AGENTS.md, trainer, merge policy)
"""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DID = "D432"


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def _row(did):
    rows = [line for line in _read("docs/decisions.md").splitlines() if line.startswith(f"| {did} |")]
    assert len(rows) == 1, f"{did} must be exactly one row in docs/decisions.md, found {len(rows)}"
    return rows[0]


def test_d432_row_exists_and_carries_the_approved_rules():
    row = _row(DID)
    for phrase in (
        "Не агент ради архитектуры, а архитектура ради эффективности агента",
        "baseline on the trainer",
        "development set (~75 %",
        "holdout (~25 %",
        "3 repeats per arm are a preliminary measurement",
        "regression test",
        "MERGE_POLICY bucket `artem`",
        "Artem's product and architecture decisions stay his",
        "User Proxy and the Evaluator are separate",
        "UNRESOLVED",
        "harness problem",
        "context problem",
        "#2064",
    ):
        assert phrase in row, phrase


def test_every_reader_cites_d432_and_the_id_resolves():
    for rel in ("AGENTS.md", "docs/agents/MERGE_POLICY.md", "docs/agents/MERGE_POLICY.yaml", "docs/trainer/ETALONS.md"):
        assert DID in _read(rel), rel
    agents = [line for line in _read("AGENTS.md").splitlines() if DID in line]
    assert len(agents) == 1, "AGENTS.md cites D432 in exactly one line"
    for did in set(re.findall(r"\bD\d{3}\b", "\n".join(agents))):
        _row(did)


def test_merge_policy_keeps_unmeasured_process_changes_in_the_artem_bucket():
    policy = yaml.safe_load(_read("docs/agents/MERGE_POLICY.yaml"))
    rule = next(r for r in policy["rules"] if r["id"] == "agent_working_order")
    assert rule["bucket"] == "artem" and DID in rule["why"]
    artem_row = next(line for line in _read("docs/agents/MERGE_POLICY.md").splitlines() if line.startswith("| `artem`"))
    assert f"[{DID}]" in artem_row and "тренажёре" in artem_row
