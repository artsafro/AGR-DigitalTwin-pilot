"""PreToolUse dispatcher for Claude Code: guard.py and pipeline_gate.py in one process.

  py -3 .claude/hooks/pretool.py      hook input JSON on stdin (registered in .claude/settings.json)

Reads stdin once and runs each part's own main() in-process on that input (stdin and stdout swapped, SystemExit
caught), so guard.py and pipeline_gate.py stay the standalone scripts Codex and Antigravity call. pipeline_gate runs
only for the tools it was registered for (Bash, PowerShell, Write, Edit; not NotebookEdit).

One output: the part with the strongest permissionDecision wins (deny > ask > nothing), printed verbatim. A part
that raises does not hide the other's decision; with no decision, an error is reported as the part would report it
standalone (traceback on stderr, exit 1: a non-blocking hook error).
"""
import importlib.util
import io
import json
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
# (module file, tool names it runs for; None = every tool the settings matcher sends)
PARTS = [
    ("guard.py", None),
    ("pipeline_gate.py", {"Bash", "PowerShell", "Write", "Edit"}),
]
RANK = {"deny": 2, "ask": 1}


def _load(name):
    spec = importlib.util.spec_from_file_location(f"pretool_{Path(name).stem}", HERE / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_part(name, raw):
    """(stdout, error) of the part's main() on the raw input; error is a traceback string or None."""
    stdin, stdout = sys.stdin, sys.stdout
    sys.stdin, sys.stdout = io.StringIO(raw), io.StringIO()
    error = None
    try:
        _load(name).main()
    except SystemExit as e:
        if e.code not in (None, 0):
            error = f"{name}: exit {e.code}\n"
    except Exception:
        error = traceback.format_exc()
    finally:
        out = sys.stdout.getvalue()
        sys.stdin, sys.stdout = stdin, stdout
    return out, error


def _rank(out):
    try:
        decision = json.loads(out)["hookSpecificOutput"]["permissionDecision"]
    except (ValueError, KeyError, TypeError):
        return 0
    return RANK.get(decision, 0)


def _tool(raw):
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data.get("tool_name") if isinstance(data, dict) else None


def dispatch(raw):
    """(stdout, stderr, exit code) of the combined hook."""
    tool = _tool(raw)
    best, errors = ("", 0), []
    for name, tools in PARTS:
        if tools is not None and tool not in tools:
            continue
        out, error = run_part(name, raw)
        if error:
            errors.append(error)
        rank = _rank(out)
        if rank > best[1]:
            best = (out, rank)
    if best[1]:
        return best[0], "", 0
    if errors:
        return "", "".join(errors), 1
    return "", "", 0


def main():
    out, err, code = dispatch(sys.stdin.read())
    if out:
        sys.stdout.write(out)
    if err:
        sys.stderr.write(err)
    return code


if __name__ == "__main__":
    sys.exit(main())
