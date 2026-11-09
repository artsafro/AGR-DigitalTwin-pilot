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


# #1027: false positives seen in the 2026-11-04/05 sessions (retro problem 4) must not ask.
@pytest.mark.parametrize("protocol", ["claude", "antigravity"])
@pytest.mark.parametrize("command", [
    "gh pr view 1013 --repo artsafro/AGR-DigitalTwin",
    "gh pr view 1013 --repo=artsafro/AGR-DigitalTwin",
    "gh pr list -R artsafro/AGR-DigitalTwin --state open",
    "gh pr create --head harness/repo-hygiene-code-layout --base main --title x --body-file b.md",
    "gh pr create --repo artsafro/AGR-DigitalTwin-pilot --base main --head improve/repo --title t",
    "gh issue list --search repo",
    "git branch -d feature/x",
    "git branch -d repo-hygiene",
    "git branch --delete feature/x",
])
def test_guard_false_positives_1027_are_allowed(command, protocol):
    assert guard(command, protocol) == "allow"


# #1027: true positives keep asking. `gh --repo o/n repo view` asks: `repo` is the
# subcommand there, and every `gh repo <subcommand>` asks (like `gh repo view` above).
@pytest.mark.parametrize("protocol", ["claude", "antigravity"])
@pytest.mark.parametrize("command", [
    "gh repo delete x",
    "gh repo edit --visibility public",
    "gh --repo o/n repo view",
    "gh -R o/n repo view",
    "gh --repo=o/n repo view",
    "gh repo",
    "gh.exe repo clone o/n",
    "\"C:/Program Files/GitHub CLI/gh.exe\" repo view",
    "git status && gh repo delete x --yes",
    "git branch -D x",
    "git branch --delete --force x",
    "git branch -d -f x",
    "git -C C:/repo branch -D x",
    "GIT branch -D x",
])
def test_guard_true_positives_1027_still_ask(command, protocol):
    assert guard(command, protocol) == "ask"


def _load_guard():
    import importlib.util
    spec = importlib.util.spec_from_file_location("agr_guard_1027", GUARD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_guard_repo_and_branch_rules_generated_probe_1027():
    """Probe: `repo` inside a flag value / branch name never asks; `gh [opts] repo <sub>` always asks;
    `git branch -d` never asks for the force rule, `-D` always does."""
    shell_reason = _load_guard().shell_reason
    names = ["repo", "repo-hygiene", "harness/repo-hygiene-code-layout", "a/repo", "my.repo", "repo_x",
             "REPO", "x-repo-y", "o/repo"]
    owners = ["artsafro/AGR-DigitalTwin", "o/repo", "repo/repo"]
    allowed, asked = [], []
    for name in names:
        for owner in owners:
            for sub in ("pr view 1", "pr create --title t", "pr list", "issue list", "run list"):
                for flag in (f"--repo {owner}", f"--repo={owner}", f"-R {owner}"):
                    allowed.append(f"gh {sub} {flag} --head {name}")
                    allowed.append(f"gh {sub} --head {name} {flag}")
            allowed.append(f"git branch -d {name}")
            allowed.append(f"git branch --delete {name}")
    for owner in owners:
        for sub in ("view", "delete x", "edit --visibility public", "clone o/n", "create n", "rename n",
                    "archive", "fork", "list", "sync"):
            for prefix in ("gh", "gh.exe", f"gh --repo {owner}", f"gh -R {owner}", f"gh --repo={owner}"):
                asked.append(f"{prefix} repo {sub}")
    for name in names:
        asked.append(f"git branch -D {name}")
        asked.append(f"git branch --delete --force {name}")
        asked.append(f"git branch -d -f {name}")
    wrong_allow = [c for c in allowed if shell_reason(c) is not None]
    wrong_ask = [c for c in asked if shell_reason(c) is None]
    assert len(allowed) > 400 and len(asked) > 150
    assert wrong_allow == [] and wrong_ask == []


# #1027 review round 1: force delete in any order/position and short-flag clusters;
# quoted `repo` subcommand tokens. Safe deletes (-d, --delete, -dr) stay allowed.
@pytest.mark.parametrize("protocol", ["claude", "antigravity"])
@pytest.mark.parametrize("command", [
    "git branch -f -d X",
    "git branch -d X -f",
    "git branch -d X --force",
    "git branch --force --delete X",
    "git branch --delete X --force",
    "git branch -df X",
    "git branch -fd X",
    "git branch -qD X",
    "git branch -Dq X",
    "git branch X -D",
    "git branch '-D' X",
    "git branch \"--force\" -d X",
    "git branch --forc --del X",
    "gh 'repo' edit --visibility public",
    "gh \"repo\" archive o/n",
    "gh --repo o/n 'repo' view",
    "gh '--repo' o/n repo view",
    "'gh' repo delete x",
])
def test_guard_round1_force_delete_and_quoted_repo_ask_1027(command, protocol):
    assert guard(command, protocol) == "ask"


@pytest.mark.parametrize("protocol", ["claude", "antigravity"])
@pytest.mark.parametrize("command", [
    "git branch -d x",
    "git branch --delete x",
    "git branch -dr origin/x",
    "git branch -d 'x'",
    "git branch -d feature/fix-x",
    "git branch -d x --format=%(refname)",
    "gh pr view 1 --repo 'o/repo'",
    "gh pr create --title 'repo cleanup' --head harness/repo-x",
])
def test_guard_round1_safe_forms_allowed_1027(command, protocol):
    assert guard(command, protocol) == "allow"


def test_guard_force_delete_any_order_generated_probe_1027():
    """Probe: every permutation of a delete flag and a force flag around the branch name asks;
    a delete flag alone (any cluster without f) never asks for the force rule."""
    import itertools
    shell_reason = _load_guard().shell_reason
    deletes, forces = ["-d", "--delete"], ["-f", "--force"]
    names = ["x", "repo-hygiene", "feature/fix-f", "a-d"]
    asked, allowed = [], []
    for d, f, name in itertools.product(deletes, forces, names):
        for order in itertools.permutations([d, f, name]):
            asked.append("git branch " + " ".join(order))
    for cluster in ("-D", "-df", "-fd", "-qD", "-Dq", "-rD", "-dqf", "-Dr"):
        for name in names:
            asked += [f"git branch {cluster} {name}", f"git branch {name} {cluster}"]
    for d, name in itertools.product(deletes + ["-dr", "-dq", "-qd", "-rd"], names):
        allowed += [f"git branch {d} {name}", f"git branch {name} {d}"]
    wrong_ask = [c for c in asked if shell_reason(c) != "force branch delete"]
    wrong_allow = [c for c in allowed if shell_reason(c) is not None]
    assert len(asked) == 160 and len(allowed) == 48
    assert wrong_ask == [] and wrong_allow == []


def test_guard_shell_reason_fail_closed_inputs_1027():
    shell_reason = _load_guard().shell_reason
    assert shell_reason("") is None
    assert shell_reason("gh repo delete x").startswith("gh")
    assert shell_reason("git branch -D x") == "force branch delete"


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
