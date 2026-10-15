"""PreToolUse pipeline gate for Claude Code (docs/HARNESS_PLAN.md §16; rules in tools/git-hooks/pipeline_gate.py).

Blocks (permission "deny", unlike guard.py's "ask": it checks the pipeline state, not a danger):
- a Write/Edit of `jobs/<JOB>/STATE.md` that leaves a `Pipeline status` above draft without the job's
  `pipeline/spec.json`, `spec.report.json` and `check.json` on disk (checked: also no failed check);
- a Write of a new `jobs/<JOB>/scripts/*` file that does not name a listed engine gap (`Engine gap: EG<n>`);
- a Write/Edit of `jobs/<JOB>/STATE.md`, `pipeline/state.json` or `pipeline/check.json` that runs or sets the
  status of an item over the attempts limit without a stop record, or leaves a malformed state.json (#128).
Every other call passes. The git pre-commit runs the same rules for every agent.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path


def _gate():
    path = Path(__file__).resolve().parents[2] / "tools" / "git-hooks" / "pipeline_gate.py"
    spec = importlib.util.spec_from_file_location("pipeline_gate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def deny(reasons):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": "pipeline_gate: " + "; ".join(reasons) + " (docs/HARNESS_PLAN.md §16)",
    }}))
    sys.exit(0)


def new_text(tool, tin, path):
    """The file's text after the call; None for a malformed call (review 2 of PR #73)."""
    if tool == "Write":
        content = tin.get("content", "")
        return content if isinstance(content, str) else None
    old = path.read_text(encoding="utf-8") if path.is_file() else ""
    a, b = tin.get("old_string", ""), tin.get("new_string", "")
    if not isinstance(a, str) or not isinstance(b, str):
        return None
    return old.replace(a, b) if tin.get("replace_all") else old.replace(a, b, 1)


def _root(target, data):
    """The repository the target lies in: the project folder or the session's cwd when they hold it, else the
    nearest folder above it with .git (review 3 of PR #73: never a `jobs` folder deeper in the path)."""
    for c in (os.environ.get("CLAUDE_PROJECT_DIR"), data.get("cwd")):
        if isinstance(c, str) and c:
            base = os.path.normcase(os.path.abspath(c))
            if os.path.normcase(str(target)).startswith(base.rstrip("\\/") + os.sep):
                return Path(os.path.abspath(c))
    return next((a for a in target.parents if (a / ".git").exists()), None)


def main():
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        sys.exit(0)
    if not isinstance(data, dict) or not isinstance(data.get("tool_input"), dict):
        sys.exit(0)
    tool = data.get("tool_name", "")
    tin = data["tool_input"]
    target = tin.get("file_path", "")
    if tool not in ("Write", "Edit") or not isinstance(target, str) or not target:
        sys.exit(0)
    path = Path(os.path.abspath(target))              # `..` resolved (review 3 of PR #73)
    root = _root(path, data)
    if root is None:
        sys.exit(0)
    parts = Path(os.path.relpath(path, root)).parts   # case-blind on Windows
    if len(parts) < 3 or parts[0].lower() != "jobs":
        sys.exit(0)
    job, rest = parts[1], parts[2:]
    gate = _gate()
    rel = "/".join(("jobs", job) + tuple(rest))
    lower = tuple(r.lower() for r in rest)            # Windows names are case-blind (review 1 of PR #73)
    if lower in (("state.md",), ("pipeline", "state.json"), ("pipeline", "check.json")):
        rel = f"jobs/{job}/STATE.md" if lower == ("state.md",) else f"jobs/{job}/{'/'.join(lower)}"
        text = new_text(tool, tin, path)
        if text is None:                              # a malformed call is the tool's to reject
            sys.exit(0)

        def disk_read(p):
            f = root / p
            return f.read_bytes() if f.is_file() else None

        def new_read(p):
            return text if p == rel else disk_read(p)

        errors = gate.job_errors(job, new_read, require_line=False) if lower == ("state.md",) else []
        errors += gate.attempt_errors(job, disk_read, new_read)    # #128
        if errors:
            deny(errors)
    elif tool == "Write" and not path.exists() and gate.is_job_script(rel):
        backlog = root / "docs" / "backlog.md"
        content = tin.get("content", "")
        if not isinstance(content, str):              # a malformed call is the tool's to reject
            sys.exit(0)
        errors = gate.script_errors(rel, content,
                                    backlog.read_text(encoding="utf-8") if backlog.is_file() else None)
        if errors:
            deny(errors)
    sys.exit(0)


if __name__ == "__main__":
    main()
