"""Harness inventory in docs/agents/CAPABILITIES.md (#129, spec docs/prd/agent-ready-harness.md).

Every hook command (in .claude/settings.json and in the subagents' frontmatter), every command, subagent and git
hook has a row: component -> failure prevented -> evidence -> last verified -> covering eval. Eval ids are tasks
under evals/. The rule-layer size and its 200k-token threshold are recorded.
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAPABILITIES = ROOT / "docs" / "agents" / "CAPABILITIES.md"
WORKFLOW = ROOT / "docs" / "agents" / "WORKFLOW.md"
HEADER = ["Component", "Kind", "Failure it prevents", "Evidence it happened", "Last verified", "Eval"]
SCRIPT = re.compile(r"""["']?\$CLAUDE_PROJECT_DIR/((?:\.claude|tools)/[\w./-]+\.py)["']?((?:\s+[\w-]+)*)\s*$""")


def inventory_rows(text=None):
    """The rows of the "Harness inventory" table as {component code span: [cells]}."""
    text = CAPABILITIES.read_text(encoding="utf-8") if text is None else text
    match = re.search(r"^### Harness inventory\n(.*?)(?=^##)", text, re.M | re.S)
    assert match, "CAPABILITIES.md has no '### Harness inventory' section"
    lines = [line for line in match.group(1).splitlines() if line.startswith("|")]
    assert lines, "the Harness inventory has no table"
    header = [c.strip() for c in lines[0].strip("|").split("|")]
    assert header == HEADER, header
    rows = {}
    for line in lines[2:]:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        assert len(cells) == len(HEADER), line
        for name in re.findall(r"`([^`]+)`", cells[0]):
            rows[name] = cells
    return rows


def hook_key(command):
    """`py -3 "$CLAUDE_PROJECT_DIR/tools/hooks/usage_log.py" prompt` -> `tools/hooks/usage_log.py prompt`."""
    match = SCRIPT.search(command)
    assert match, f"hook command names no project script: {command}"
    return " ".join([match.group(1)] + match.group(2).split())


def settings_hooks():
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    return {hook_key(h["command"]) for groups in settings["hooks"].values() for g in groups for h in g["hooks"]}


def agent_hooks():
    keys = set()
    for path in (ROOT / ".claude" / "agents").glob("*.md"):
        for command in re.findall(r"^\s*command:\s*(.+)$", path.read_text(encoding="utf-8"), re.M):
            keys.add(hook_key(command))
    return keys


def test_every_settings_hook_has_a_row():
    hooks = settings_hooks()
    assert len(hooks) >= 8
    missing = sorted(hooks - inventory_rows().keys())
    assert not missing, f"hooks in .claude/settings.json with no inventory row: {missing}"


def test_a_hook_without_a_row_fails():
    text = CAPABILITIES.read_text(encoding="utf-8").replace("`tools/hooks/skill_gate.py`", "`skill gate`")
    assert "tools/hooks/skill_gate.py" in settings_hooks()
    assert "tools/hooks/skill_gate.py" not in inventory_rows(text)


def test_every_subagent_hook_has_a_row():
    missing = sorted(agent_hooks() - inventory_rows().keys())
    assert not missing, f"hooks in .claude/agents/ with no inventory row: {missing}"


def test_every_command_subagent_and_git_hook_has_a_row():
    files = [p for d in (".claude/commands", ".claude/agents") for p in (ROOT / d).glob("*.md")]
    files += [p for p in (ROOT / "tools" / "git-hooks").iterdir() if p.is_file() and p.suffix in ("", ".py")]
    names = {p.relative_to(ROOT).as_posix() for p in files}
    assert len(names) >= 12
    missing = sorted(names - inventory_rows().keys())
    assert not missing, f"components with no inventory row: {missing}"


def test_permission_rule_sets_have_rows():
    rows = inventory_rows()
    for name in ("permissions.allow", "permissions.ask", "permissions.deny"):
        assert name in rows, name


def test_cells_are_filled_and_eval_ids_are_tasks():
    tasks = {p.parent.name for p in (ROOT / "evals").glob("*/task.json")}
    assert tasks
    for name, cells in inventory_rows().items():
        component, kind, failure, evidence, verified, evals = cells
        assert kind and failure and evidence, name
        assert re.match(r"^(\d{4}-\d{2}-\d{2}\b|never\b)", verified), (name, verified)
        if evals == "none":
            continue
        ids = re.findall(r"`([^`]+)`", evals)
        assert ids and re.fullmatch(r"(`[^`]+`(,\s*)?)+", evals), (name, evals)
        unknown = sorted(set(ids) - tasks)
        assert not unknown, f"{name}: eval ids with no evals/<id>/task.json: {unknown}"


@pytest.mark.parametrize("component", [".claude/hooks/guard.py", "ALLOWED_WRITE_ROOTS"])
def test_pr142_is_app_isolation_evidence_not_project_guard_verification(component):
    """PR #142 names the app isolation hook, not the project's guard, as the denier."""
    cells = inventory_rows()[component]
    evidence, verified = cells[3:5]
    assert "PR #142" in evidence
    assert "app isolation hook" in evidence
    assert "not component-specific" in evidence
    assert verified.startswith("never")
    assert "unknown" in verified
    assert "component-specific" in verified


def test_documentation_correction_keeps_all_guard_inventory_rows_and_hook():
    """Exhaustively probe the guard and its three rule-set inventory entries."""
    rows = inventory_rows()
    for component in (".claude/hooks/guard.py", "SHELL_RULES", "PRODUCTION_EXT", "ALLOWED_WRITE_ROOTS"):
        assert component in rows
        assert rows[component][5] == "`no-hook-denial`"
    assert ".claude/hooks/guard.py" in settings_hooks()


def test_rule_layer_size_and_threshold_recorded():
    text = CAPABILITIES.read_text(encoding="utf-8")
    match = re.search(r"^### Rule-layer size\n(.*?)(?=^##)", text, re.M | re.S)
    assert match, "CAPABILITIES.md has no '### Rule-layer size' section"
    body = match.group(1)
    assert re.search(r"\b\d{2,3}k tokens\b", body), "no measured size in tokens"
    assert "200k" in body and "wc -c" in body, "no threshold or no measuring command"


def test_workflow_has_the_inventory_rule():
    text = WORKFLOW.read_text(encoding="utf-8")
    match = re.search(r"^## Harness inventory\b[^\n]*\n(.*?)(?=^##|\Z)", text, re.M | re.S)
    assert match, "WORKFLOW.md has no '## Harness inventory' section"
    body = match.group(1)
    for phrase in ("model change", "component is added", "removal", "200k"):
        assert phrase in body, phrase
