"""Permission contract at the guard's JSON stdin/stdout seam (no live gh calls)."""
import json
import ast
import os
import re
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / ".claude/hooks/guard.py"


def guard(command, protocol="claude"):
    if protocol == "antigravity":
        payload = {"toolCall": {"name": "run_command", "args": {"CommandLine": command}}}
    else:
        payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    result = subprocess.run([sys.executable, str(GUARD)], input=json.dumps(payload),
                            capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
                            env=os.environ.copy(), check=True)
    output = json.loads(result.stdout) if result.stdout.strip() else {}
    return output.get("decision", output.get("hookSpecificOutput", {}).get("permissionDecision", "allow"))


@pytest.mark.parametrize("protocol", ["claude", "antigravity"])
@pytest.mark.parametrize("command", [
    "gh pr merge 127 --squash",
    "gh issue delete 127 --yes",
    "gh repo delete owner/repo --yes",
    "gh release delete v1 --yes",
    "gh repo view owner/repo",
    "gh --repo owner/repo pr merge 127",
    "gh -R owner/repo issue delete 127 --yes",
    "gh extension delete example",
    "git status && gh pr merge 127",
    "gh pr view 127\ngh issue delete 127 --yes",
])
def test_sensitive_github_commands_ask(command, protocol):
    assert guard(command, protocol) == "ask"


@pytest.mark.parametrize("protocol", ["claude", "antigravity"])
@pytest.mark.parametrize("command", ["gh pr view 127", "gh issue list", "gh pr list --state open"])
def test_readonly_github_queries_are_allowed(command, protocol):
    assert guard(command, protocol) == "allow"


def test_dcc_risks_and_skills_reference_single_register():
    capabilities = (ROOT / "docs/agents/CAPABILITIES.md").read_text(encoding="utf-8")
    assert "### DCC tool risk classes" in capabilities
    section = capabilities.split("### DCC tool risk classes\n", 1)[1].split("\n## ", 1)[0]
    rows = [line for line in section.splitlines() if line.startswith("|")][2:]
    assert rows
    routes = set()
    for row in rows:
        route, operation, risk = [cell.strip() for cell in row.strip("|").split("|")]
        assert operation
        assert risk in {"read-only", "versioned-write", "destructive"}, row
        routes.add(route)
    assert {"3dsmax-mcp", "revit-bridge", "revit-http-2025", "revit-twin", "multiCAD",
            "blender", "speedtree", "rizomuv", "SketchUp"} <= routes
    for name in ["blender-mcp", "3dsmax-mcp-dev", "revit-mcp", "autocad-mcp",
                 "rizomuv-mcp", "speedtree-mcp"]:
        skill = (ROOT / ".agents/skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert "CAPABILITIES.md#dcc-tool-risk-classes" in skill, name
        assert "Before any write" in skill, name
        assert "versioned-write" in skill and "destructive" in skill, name


def matrix_rows(text):
    assert "## Permission matrix" in text, "missing permission matrix"
    section = text.split("## Permission matrix\n", 1)[1].split("\n## ", 1)[0]
    lines = [line for line in section.splitlines() if line.startswith("|")]
    assert lines and [c.strip() for c in lines[0].strip("|").split("|")] == [
        "Action class", "Claude Code", "Codex", "Antigravity", "Enforcement"]
    rows = [[c.strip() for c in line.strip("|").split("|")] for line in lines[2:]]
    assert rows, "empty permission matrix"
    return rows


def check_matrix(text):
    for row in matrix_rows(text):
        assert len(row) == 5, row
        action, *permissions, enforcement = row
        assert all(p in {"free", "versioned write", "ask", "never"} for p in permissions), row
        if not {"ask", "never"}.intersection(permissions):
            continue
        commands = re.findall(r"guard: `([^`]+)`", enforcement)
        gates = re.findall(r"gate: \[[^]]+\]\(([^)#]+)#([^)]+)\)", enforcement)
        assert commands or gates, f"{action}: ask/never requires a named guard rule or gate"
        for command in commands:
            assert guard(command) == "ask", (action, command)
        for path, anchor in gates:
            target = (ROOT / "docs/agents" / path).resolve()
            assert target.is_relative_to(ROOT) and target.is_file(), (action, target)
            source = target.read_text(encoding="utf-8")
            if target.suffix == ".py":
                anchors = {n.name for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef)}
            else:
                anchors = {re.sub(r"[^\w -]", "", h.lower()).replace(" ", "-")
                           for h in re.findall(r"^#+ (.+)$", source, re.M)}
            assert anchor in anchors, (action, target, anchor)


def test_permission_matrix_maps_restricted_rows_to_guard_or_gate():
    check_matrix((ROOT / "docs/agents/WORKFLOW.md").read_text(encoding="utf-8"))


@pytest.mark.parametrize("enforcement", ["", "TBD", "gate: [missing](WORKFLOW.md#missing)",
                                         "guard: `gh issue list`"])
def test_permission_contract_rejects_uncovered_restrictions(enforcement):
    text = ("## Permission matrix\n"
            "| Action class | Claude Code | Codex | Antigravity | Enforcement |\n"
            "|---|---|---|---|---|\n"
            f"| Uncovered action | never | ask | never | {enforcement} |\n")
    with pytest.raises(AssertionError):
        check_matrix(text)
