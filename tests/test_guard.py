"""The PreToolUse guard (.claude/hooks/guard.py): write boundary for file tools."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude/hooks/guard.py"


def run(payload, cwd):
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    result = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True,
                            text=True, env=env, cwd=cwd)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout) if result.stdout.strip() else {}


def write(path, cwd):
    return run({"tool_name": "Write", "tool_input": {"file_path": str(path), "content": "x"}, "cwd": str(cwd)}, cwd)


def decision(out):
    return out.get("hookSpecificOutput", {}).get("permissionDecision", "allow")


def test_plan_mode_file_in_home_claude_plans_is_allowed(tmp_path):
    # Claude Code writes its plan to ~/.claude/plans/<name>.md in plan mode (#111).
    plan = Path.home() / ".claude" / "plans" / "some-plan-name.md"
    assert decision(write(plan, tmp_path)) == "allow"


def test_write_outside_project_and_allowed_roots_asks(tmp_path):
    outside = Path.home() / ".claude" / "settings.json"
    out = write(outside, tmp_path)
    assert decision(out) == "ask"
    assert "write outside project/allowed folders" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_write_inside_cwd_is_allowed(tmp_path):
    assert decision(write(tmp_path / "notes.md", tmp_path)) == "allow"
