"""Translate one Pi tool call to the existing Claude PreToolUse hooks.

Empty hook stdout with exit zero is Claude's implicit allow. All adapter,
process and protocol errors fail closed; no shell or model input is executed.
PreToolUse hook execution timeout defaults to HOOK_TIMEOUT_SECONDS (10 seconds),
overridable via the PI_GUARD_HOOK_TIMEOUT_SECONDS environment variable.
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
HOOK_TIMEOUT_SECONDS = 10


def preview_edit(tin, path):
    """Exact Pi edits: match disjoint ranges in the original LF-normalized file.

    Fuzzy-only matches are deliberately blocked: guessing Pi's fuzzy output could
    validate different content. No file is changed by this preview.
    """
    edits = tin.get("edits", [])
    if isinstance(edits, str):
        edits = json.loads(edits)
    if isinstance(edits, dict):
        edits = [edits]
    if not isinstance(edits, list):
        raise ValueError("edits must be an array")
    edits = list(edits)
    if "oldText" in tin or "newText" in tin:
        edits.append({"oldText": tin.get("oldText"), "newText": tin.get("newText")})
    if not edits:
        raise ValueError("edits must contain at least one replacement")
    raw = path.read_bytes().decode("utf-8")
    bom = "\ufeff" if raw.startswith("\ufeff") else ""
    content = raw[len(bom):]
    ending = "\r\n" if content.find("\n") > 0 and content[content.find("\n") - 1] == "\r" else "\n"

    def lf(text):
        return text.replace("\r\n", "\n").replace("\r", "\n")

    base = lf(content)
    replacements = []
    for edit in edits:
        if (not isinstance(edit, dict)
                or not isinstance(edit.get("oldText"), str)
                or not isinstance(edit.get("newText"), str)):
            raise ValueError("each edit requires oldText and newText strings")
        old, new = lf(edit["oldText"]), lf(edit["newText"])
        if not old or base.count(old) != 1:
            raise ValueError("edit needs a unique exact match; fuzzy-only edits are unsupported")
        start = base.index(old)
        replacements.append((start, start + len(old), new))
    replacements.sort()
    if any(a[1] > b[0] for a, b in zip(replacements, replacements[1:])):
        raise ValueError("edits overlap")
    result = base
    for start, end, new in reversed(replacements):
        result = result[:start] + new + result[end:]
    if result == base:
        raise ValueError("edits produce no change")
    # Claude Edit reconstructs from read_text() (universal newlines). Replacing
    # that entire text lets pipeline_gate inspect the full Pi result, not just
    # one replacement; also retains Edit-specific hook rules/matchers.
    return raw.replace("\r\n", "\n").replace("\r", "\n"), bom + result.replace("\n", ending)


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
        if tool == "Edit":
            tin["old_string"], tin["new_string"] = preview_edit(tin, Path(tin["file_path"]))
            tin["replace_all"] = False
        elif not isinstance(tin.get("content"), str):
            raise ValueError("file content must be a string")
    payload = json.dumps({"tool_name": tool, "tool_input": tin,
                          "hook_event_name": "PreToolUse", "cwd": str(cwd)})
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(ROOT), "PYTHONIOENCODING": "utf-8"}
    raw_timeout = os.environ.get("PI_GUARD_HOOK_TIMEOUT_SECONDS")
    timeout = float(raw_timeout) if raw_timeout is not None else HOOK_TIMEOUT_SECONDS
    for name in HOOKS:
        result = subprocess.run([sys.executable, str(ROOT / ".claude/hooks" / name)],
                                input=payload, text=True, encoding="utf-8", capture_output=True,
                                cwd=cwd, env=env, timeout=timeout)
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
