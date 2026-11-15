"""PreToolUse dispatcher for Claude Code: guard.py and pipeline_gate.py in one process.

  py -3 .claude/hooks/pretool.py      hook input JSON on stdin (registered in .claude/settings.json)

Reads stdin once and runs each part's own main() in-process on that input (stdin and stdout swapped, SystemExit
caught), so guard.py and pipeline_gate.py stay the standalone scripts Codex and Antigravity call. pipeline_gate runs
only for the tools it was registered for (Bash, PowerShell, Write, Edit; not NotebookEdit).

One output: the part with the strongest permissionDecision wins (deny > ask > allow > nothing), printed verbatim.
"allow" comes only from guard.py's one-shot merge token [D234] and is forwarded only when no part failed. A part
that raises does not hide the other's deny/ask; with no such decision, an error is reported as the part would report it
standalone (traceback on stderr, exit 1: a non-blocking hook error).

Bare python advisory (#1034): a Bash/PowerShell command that runs a bare `python`/`python3` as a command name (at
the start, after `;`, `&&`, `|`, `&`, `(`, `$(`, a backtick or a newline, after env assignments or `time`/`env`/
`then`/`do`) gets an advisory to use `py -3`, because on this host the bare name can be the Microsoft Store stub
(exit 49). It is never a decision: it goes to `additionalContext` (for the agent) and `systemMessage` (for the user),
and is added to a winning ask/deny. Only here, not in guard.py: Codex and the Pi adapter read guard.py's stdout as a
strict decision. Lexical check, not a shell parser: quoted text, comments and here-doc bodies are not commands.
"""
import importlib.util
import io
import json
import re
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
# (module file, tool names it runs for; None = every tool the settings matcher sends)
PARTS = [
    ("guard.py", None),
    ("pipeline_gate.py", {"Bash", "PowerShell", "Write", "Edit"}),
]
RANK = {"deny": 3, "ask": 2, "allow": 1}   # deny > ask > allow > nothing; allow only from guard's merge token [D234]
SHELLS = {"Bash", "PowerShell"}
BARE_PYTHON = {"python", "python3", "python.exe", "python3.exe"}
# Words that may precede the command name of one simple command (shell keywords and transparent wrappers).
PREFIX_WORDS = {"time", "env", "exec", "command", "nohup", "if", "then", "elif", "else", "while", "until", "do", "!", "{"}
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
HEREDOC = re.compile(r"""<<-?[ \t]*(['"]?)([^\s'";|&<>()]+)\1""")
PLAIN = re.compile(r"""[^\s'";|&()`$<\\]+""")                         # a run of ordinary word characters
ADVISORY = ("pretool.py: bare `python`/`python3` can start the Microsoft Store stub on this host (exit 49; edits made "
            "through it silently do not apply). Use `py -3` (Python 3.13, docs/agents/CAPABILITIES.md), "
            "`uv run python` or an explicit interpreter path such as `.venv/Scripts/python.exe`.")


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


def _input(raw):
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _words(command, escape):
    """Words of a shell command with None at each command boundary; quotes removed, comments and here-docs dropped."""
    out, word, heredocs, i, n = [], None, [], 0, len(command)

    def add(text):
        nonlocal word
        if word is None:
            word = []
        word.append(text)

    def end():
        nonlocal word
        if word is not None:
            out.append("".join(word))
            word = None

    while i < n:
        c = command[i]
        if c == escape and i + 1 < n:                                   # escaped char (or line continuation)
            if command[i + 1] != "\n":
                add(command[i + 1])
            i += 2
        elif c in " \t\r":
            end()
            i += 1
        elif c == "\n":
            end()
            out.append(None)
            i += 1
            for delim in heredocs:                                      # here-doc bodies follow this line in turn
                while i < n:
                    j = command.find("\n", i)
                    line, i = (command[i:], n) if j < 0 else (command[i:j], j + 1)
                    if line.strip() == delim:
                        break
            heredocs = []
        elif c == "#" and word is None:                                 # comment up to the newline
            j = command.find("\n", i)
            i = n if j < 0 else j
        elif c in "'\"":
            j = i + 1
            while j < n and command[j] != c:
                j += 2 if c == '"' and command[j] == escape else 1
            add(command[i + 1:j])
            i = j + 1
        elif c in ";|&()" or (c == "`" and escape != "`") or command.startswith("$(", i):
            end()
            out.append(None)
            i += 2 if c == "$" else 1
        elif escape == "\\" and command.startswith("<<", i) and not command.startswith("<<<", i):
            end()
            m = HEREDOC.match(command, i)
            if m:
                heredocs.append(m.group(2))
                i = m.end()
            else:
                i += 2
        else:
            m = PLAIN.match(command, i)
            j = m.end() if m else i + 1
            add(command[i:j])
            i = j
    end()
    return out


def bare_python(command, tool):
    """True when a Bash/PowerShell command runs a bare `python`/`python3` (no path) as a command name."""
    if not isinstance(command, str) or tool not in SHELLS:
        return False
    first = True
    for word in _words(command, "`" if tool == "PowerShell" else "\\"):
        if word is None:
            first = True
        elif not first:
            continue
        elif word.lower() in BARE_PYTHON:
            return True
        elif word not in PREFIX_WORDS and not ASSIGNMENT.match(word):
            first = False
    return False


def _advisory(data):
    tin = data.get("tool_input")
    return ADVISORY if isinstance(tin, dict) and bare_python(tin.get("command"), data.get("tool_name")) else ""


def _with_advisory(out, note):
    """The winning output with the advisory added (or the advisory alone); the output unchanged without one."""
    if not note:
        return out
    try:
        data = json.loads(out) if out.strip() else {}
        specific = data.setdefault("hookSpecificOutput", {"hookEventName": "PreToolUse"})
    except (ValueError, AttributeError):
        return out
    if not isinstance(specific, dict):
        return out
    specific["additionalContext"] = "\n".join(x for x in (specific.get("additionalContext"), note) if x)
    data["systemMessage"] = "\n".join(x for x in (data.get("systemMessage"), note) if x)
    return json.dumps(data) + "\n"


def dispatch(raw):
    """(stdout, stderr, exit code) of the combined hook."""
    data = _input(raw)
    tool = data.get("tool_name")
    best, errors, notes = ("", 0), [], []
    for name, tools in PARTS:
        if tools is not None and tool not in tools:
            continue
        out, error = run_part(name, raw)
        part = _input(out).get("hookSpecificOutput", {})
        if isinstance(part, dict) and part.get("additionalContext"):
            notes.append(part["additionalContext"])
        if error:
            errors.append(error)
        rank = _rank(out)
        if rank > best[1]:
            best = (out, rank)
    note = "\n".join(dict.fromkeys(notes + ([_advisory(data)] if _advisory(data) else [])))
    # deny/ask win over a failed part; an explicit allow does not (a part that crashed may have denied).
    if best[1] > RANK["allow"] or (best[1] and not errors):
        return _with_advisory(best[0], note), "", 0
    if errors:
        return "", "".join(errors), 1
    return _with_advisory("", note), "", 0


def main():
    out, err, code = dispatch(sys.stdin.read())
    if out:
        sys.stdout.write(out)
    if err:
        sys.stderr.write(err)
    return code


if __name__ == "__main__":
    sys.exit(main())
