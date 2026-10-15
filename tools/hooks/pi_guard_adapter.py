"""Translate one Pi tool call to the existing Claude PreToolUse hooks.

Empty hook stdout with exit zero is Claude's implicit allow. All adapter,
process and protocol errors fail closed; no shell or model input is executed.
"""
import json
import os
import re
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
TOOLS = {"bash": "Bash", "powershell": "PowerShell", "edit": "Edit", "write": "Write"}
HOOKS = ("guard.py", "pipeline_gate.py")


def evaluate(call):
    tool = TOOLS[call["tool"]]
    tin = dict(call["input"])
    cwd = Path(call["cwd"]).resolve(strict=True)
    if not cwd.is_dir():
        raise ValueError("cwd is not a directory")
    if tool in ("Bash", "PowerShell"):
        if not isinstance(tin.get("command"), str) or not tin["command"]:
            raise ValueError("command must be a nonempty string")
    else:
        path = tin.get("path", tin.get("file_path"))
        if not isinstance(path, str) or not path:
            raise ValueError("path must be a nonempty string")
        # Pi expands @, tilde, file URLs, Unicode spaces and Windows shell
        # paths before writing. Reject those spellings rather than check a
        # different target. Use ordinary relative or native absolute paths.
        if (path.startswith(("@", "~", "file://"))
                or re.search(r"[\u00a0\u2000-\u200a\u202f\u205f\u3000]", path)
                or (os.name == "nt" and (
                    path.startswith(("/", "\\"))
                    or (Path(path).drive and not Path(path).is_absolute())))):
            raise ValueError("unsupported Pi path syntax; use a relative or native absolute path")
        tin["file_path"] = str((cwd / path).resolve())
        fields = ("content",) if tool == "Write" else ("old_string", "new_string")
        if tool == "Edit":
            tin["old_string"] = tin.get("oldText", tin.get("old_string"))
            tin["new_string"] = tin.get("newText", tin.get("new_string"))
        if any(not isinstance(tin.get(field), str) for field in fields):
            raise ValueError("file content/edit fields must be strings")
    payload = json.dumps({"tool_name": tool, "tool_input": tin,
                          "hook_event_name": "PreToolUse", "cwd": str(cwd)})
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(ROOT), "PYTHONIOENCODING": "utf-8"}
    for name in HOOKS:
        result = subprocess.run([sys.executable, str(ROOT / ".claude/hooks" / name)],
                                input=payload, text=True, encoding="utf-8", capture_output=True,
                                cwd=cwd, env=env, timeout=10)
        if result.returncode:
            return {"decision": "block", "reason": f"{name} failed (exit {result.returncode}): {result.stderr.strip()}"}
        if not result.stdout.strip():
            continue
        output = json.loads(result.stdout)
        specific = output["hookSpecificOutput"]
        decision = specific["permissionDecision"]
        if decision in ("ask", "deny"):
            return {"decision": "block", "reason": specific.get("permissionDecisionReason") or f"{name}: {decision}"}
        if decision != "allow":
            raise ValueError(f"{name}: unknown permission decision")
    return {"decision": "allow", "reason": "Both PreToolUse hooks allowed the call"}


def main():
    try:
        result = evaluate(json.load(sys.stdin))
    except Exception as exc:
        result = {"decision": "block", "reason": f"Pi guard adapter failed: {type(exc).__name__}: {exc}"}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
