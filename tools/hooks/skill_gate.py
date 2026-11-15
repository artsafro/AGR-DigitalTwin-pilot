"""PreToolUse on DCC MCP tools: the matching skill must be loaded in this session first (docs/agents/WORKFLOW.md,
"Triggers").

  py -3 tools/hooks/skill_gate.py      hook input JSON on stdin; denies with the skill to load, or stays silent

A skill counts as loaded when the session's transcript has a Skill call for it or the user ran it as /<skill>, or
when logs/agent-usage.jsonl has it for this session (the transcript is written asynchronously and may lag).
Subagents skip skill-load reminders only; Max mutations always require an in-process PID prefix.
Unreadable transcripts do not waive PID admission. The skill reminder remains fail-open; the PID check
is conservative lexical admission, not a script sandbox or a user-authorization ledger.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import usage_log  # noqa: E402

# MCP server name in the tool name -> project skill (plugin skill for 3ds Max).
SKILLS = [(re.compile(r"^mcp__[^_]*3dsmax", re.I), "3dsmax-mcp-dev"),
          (re.compile(r"^mcp__[^_]*blender", re.I), "blender-mcp"),
          (re.compile(r"^mcp__[^_]*revit", re.I), "revit-mcp")]


def required(tool):
    return next((skill for pattern, skill in SKILLS if pattern.search(tool or "")), None)


def _matches(name, skill):
    return bool(name) and (name == skill or name.endswith(":" + skill))


def loaded(skill, payload):
    """Success evidence only (review 2 of #107): the user ran /<skill> (a genuine command record), or a Skill call
    returned success (`toolUseResult.success` with its `commandName`), or the PostToolUse log has it (PostToolUse
    fires on success only). A tag quoted in a tool result or a failed Skill call does not count."""
    transcript = payload.get("transcript_path")
    try:
        text = Path(transcript).read_text(encoding="utf-8", errors="replace")
    except (OSError, TypeError):
        return True                                  # cannot tell: let it pass (documented)
    for line in text.splitlines():
        if skill not in line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict):
            continue
        if _matches(usage_log.command_of(entry), skill):
            return True
        result = entry.get("toolUseResult")
        if isinstance(result, dict) and result.get("success") is True and _matches(result.get("commandName"), skill):
            return True
    return any(r.get("session_id") == payload.get("session_id") and r.get("kind") in ("skill", "command")
               and _matches(r.get("name"), skill) for r in usage_log.read())


# Stateless admission: selection receipts cannot close the check/dispatch race (#1364).
# Accept only a canonical, unconditional prefix, never a guard found inside arbitrary code.
MAX_GUARD = re.compile(
    r'\s*local\s+pc\s*=\s*dotNetClass\s+"System\.Diagnostics\.Process"\s*;\s*'
    r'if\s*\(pc\.GetCurrentProcess\(\)\)\.Id\s*!=\s*[1-9][0-9]*\s+'
    r'do\s+throw\s+"wrong Max"\s*;\s*', re.I)
PY_GUARD = re.compile(
    r'import os\nif os\.getpid\(\) != [1-9][0-9]*:\n'
    r'    raise RuntimeError\("wrong Max"\)\n')
MAX_QUERIES = {"objects.count", "selection.count", "maxFileName", "maxFilePath", "getSaveRequired()"}
MAX_INSPECTION = {"get_selected_max_instance", "list_max_instances", "get_bridge_status",
                  "get_object_properties", "geometry_qa", "inspect_max_file"}


def max_pid_check(payload):
    """Deny unprovable Max mutations even for subagents or unreadable transcripts.

    This is a lexical accident guard, not an adversarial-code sandbox. It does not
    attest user authorization, that a supplied PID belongs to this task, or Max's
    runtime global bindings. Native mutation tools must use guarded script equivalents.
    """
    tool = payload.get("tool_name", "")
    if not isinstance(tool, str) or not tool.lower().startswith("mcp__3dsmax-mcp__"):
        return {}
    operation = tool.split("__", 2)[-1]
    args = payload.get("tool_input")
    if not isinstance(args, dict):
        args = {}
    # Selection changes routing, not the scene; authorization still applies separately.
    if operation in MAX_INSPECTION or operation == "select_max_instance":
        return {}
    if operation == "inspect_mesh" and args.get("capture", False) is False:
        return {}
    if operation == "query_scene" and args.get("action") in ("overview", "selection"):
        return {}
    code = args.get("code")
    if isinstance(code, str):
        if operation == "execute_maxscript" and code.strip() in MAX_QUERIES:
            return {}
        guard = MAX_GUARD if operation == "execute_maxscript" else PY_GUARD
        if operation in ("execute_maxscript", "execute_python") and guard.match(code):
            return {}
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": (
            "Max PID guard required for this mutation/unknown call. Pin the authorized PID, then use "
            'execute_maxscript code starting with: local pc = dotNetClass "System.Diagnostics.Process"; '
            'if (pc.GetCurrentProcess()).Id != <pid> do throw "wrong Max"; '
            'For execute_python use: import os\\nif os.getpid() != <pid>:\\n'
            '    raise RuntimeError("wrong Max")\\n. '
            "Use a guarded script instead of scene_patch/manage_scene/other native mutations. "
            "A get_selected_max_instance receipt is not atomic with execution and does not waive this guard. "
            "See 3dsmax-mcp-dev; user authorization is still required.")}}


def check(payload):
    pid_decision = max_pid_check(payload)
    if pid_decision:
        return pid_decision
    if payload.get("agent_id"):
        return {}
    skill = required(payload.get("tool_name"))
    if not skill or loaded(skill, payload):
        return {}
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": f"Load the `{skill}` skill first (Skill tool), follow it, "
                                   "then repeat this call (docs/agents/WORKFLOW.md, Triggers)."}}


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        out = check(payload) if isinstance(payload, dict) else {}
    except Exception:
        out = {}
    if out:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
