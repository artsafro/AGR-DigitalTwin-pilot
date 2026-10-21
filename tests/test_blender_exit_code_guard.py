"""Guard: every headless Blender call passes ``--python-exit-code 1`` (#439).

new-case: static scan of tracked command sources that flags any Blender
``--background`` command missing ``--python-exit-code``, so a Python exception
inside Blender can never exit 0 and read as success.

Scope per file type:
- ``.py``: every ``list``/``tuple`` literal (multi-line included) whose string
  constants contain ``--background`` must also contain ``--python-exit-code``;
  and every executable command *string* passed to a subprocess/os execution
  call (``subprocess.run``/``Popen``/``call``/``check_call``/``check_output``,
  ``os.system``/``popen``, ...) that contains ``--background`` must also carry
  the flag. AST-only, never imports or executes the scanned module. Docstrings,
  usage strings and other non-executable prose are not command lines and are
  out of scope.
- ``.sh``/``.ps1``: every logical line (backslash/backtick continuations joined)
  is split into separate commands at shell command boundaries (``;``, ``&``,
  ``&&``, ``|``, ``||``) with ``#`` comments stripped first; a command segment
  containing ``--background`` must also contain ``--python-exit-code``. A flag
  in another command or a comment must not discharge the first command.
- ``.md``: fenced code blocks (`` ``` `` / ``~~~``) and indented code blocks
  (4+ spaces or a tab). Fences tagged ``python``/``py`` are parsed as Python
  with correct line offsets; fences tagged with a shell language (or untagged)
  and indented blocks are scanned as shell. Blocks tagged ``text``/``txt``/
  ``plaintext``/``log``/``output`` are recorded commands or logs, not runnable
  templates; editing a recorded command would falsify evidence, so they are
  skipped. Prose outside code blocks is out of scope.
"""
from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_BACKGROUND = re.compile(r"(?<![-\w])--background(?![-\w])")
_EXIT_CODE = re.compile(r"(?<![-\w])--python-exit-code(?![-\w])")

# Fenced-code languages that are records/logs rather than runnable commands.
_NON_COMMAND_FENCE = {
    "text", "txt", "plaintext", "log", "output", "stdout", "stderr",
    "json", "yaml", "yml", "toml", "ini", "diff", "patch", "md", "markdown",
    "html", "xml", "csv", "nohighlight", "no",
}

# Fenced-code languages parsed with the Python command scanner.
_PY_FENCE_LANGS = {"python", "py", "py3", "python3", "ipython"}

_FENCE = re.compile(r"^\s*(```+|~~~+)\s*(\S*)\s*$")
_INDENTED = re.compile(r"^(?: {4,}|\t)")

# Execution calls whose first positional argument is a command string.
_EXEC_MODULES = {"subprocess", "os"}
_EXEC_ATTRS = {
    "run", "Popen", "call", "check_call", "check_output",
    "getoutput", "getstatusoutput", "system", "popen",
}
_EXEC_BARE_NAMES = {"system", "popen"}


def _string_constants(node: ast.AST) -> list[str]:
    return [c.value for c in ast.walk(node)
            if isinstance(c, ast.Constant) and isinstance(c.value, str)]


def _strip_shell_comment(text: str) -> str:
    """Drop an unquoted ``#`` comment (to end of text) that starts a word."""
    quote: str | None = None
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if quote:
            if ch == quote and (i == 0 or text[i - 1] != "\\"):
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            i += 1
            continue
        if ch == "\\" and i + 1 < n:
            i += 2
            continue
        if ch == "#" and (i == 0 or text[i - 1] in " \t"):
            return text[:i]
        i += 1
    return text


def _split_commands(text: str) -> list[str]:
    """Split a shell/PowerShell logical line into separate command invocations."""
    parts: list[str] = []
    cur: list[str] = []
    quote: str | None = None
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if quote:
            cur.append(ch)
            if ch == quote and (i == 0 or text[i - 1] != "\\"):
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            cur.append(ch)
            i += 1
            continue
        if ch == "\\" and i + 1 < n:
            cur.append(ch)
            cur.append(nxt)
            i += 2
            continue
        if ch == ";":
            parts.append("".join(cur).strip())
            cur = []
            i += 1
            continue
        if ch == "&":
            if nxt == "&":
                parts.append("".join(cur).strip())
                cur = []
                i += 2
                continue
            if nxt == ">":
                cur.append("&>")  # &> redirect
                i += 2
                continue
            if "".join(cur).strip() == "":
                cur.append(ch)  # PowerShell call operator at start
                i += 1
                continue
            parts.append("".join(cur).strip())
            cur = []
            i += 1
            continue
        if ch == "|":
            if nxt in ("|", "&"):
                parts.append("".join(cur).strip())
                cur = []
                i += 2
                continue
            parts.append("".join(cur).strip())
            cur = []
            i += 1
            continue
        if ch == ">" and nxt == "&":
            cur.append(">&")  # fd redirect 2>&1
            i += 2
            continue
        cur.append(ch)
        i += 1
    parts.append("".join(cur).strip())
    return [p for p in parts if p.strip()]


def _shell_violates(text: str) -> bool:
    """True when any command segment starts Blender headless but lacks the flag."""
    for command in _split_commands(_strip_shell_comment(text)):
        if _BACKGROUND.search(command) and not _EXIT_CODE.search(command):
            return True
    return False


def _logical_lines(lines: list[str], start_line: int) -> list[tuple[int, str]]:
    """Join trailing-backslash/backtick continuations, tracking the start line."""
    logical: list[tuple[int, str]] = []
    buf = ""
    start = start_line
    for i, raw in enumerate(lines, start_line):
        stripped = raw.rstrip("\n")
        if buf == "":
            start = i
        if stripped.endswith("\\") or stripped.endswith("`"):
            buf += stripped[:-1] + " "
            continue
        buf += stripped
        logical.append((start, buf))
        buf = ""
    if buf.strip():
        logical.append((start, buf))
    return logical


def _is_exec_call(node: ast.Call) -> bool:
    fn = node.func
    if isinstance(fn, ast.Attribute):
        return (isinstance(fn.value, ast.Name)
                and fn.value.id in _EXEC_MODULES
                and fn.attr in _EXEC_ATTRS)
    if isinstance(fn, ast.Name):
        return fn.id in _EXEC_BARE_NAMES
    return False


def _command_string_arg(node: ast.Call) -> str | None:
    if not node.args:
        return None
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None


def _scan_py_source(source: str) -> list[tuple[int, str]]:
    """Return (line_number, kind) violations for Python source text (1-based)."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []  # not parseable Python; no literal/command to guard
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.List, ast.Tuple)):
            strings = _string_constants(node)
            if (any(_BACKGROUND.search(s) for s in strings)
                    and not any(_EXIT_CODE.search(s) for s in strings)):
                out.append((node.lineno, "python argv literal"))
        elif isinstance(node, ast.Call) and _is_exec_call(node):
            command = _command_string_arg(node)
            if (command is not None
                    and _BACKGROUND.search(command)
                    and not _EXIT_CODE.search(command)):
                out.append((node.lineno, "python command string"))
    return out


def _scan_py(path: Path) -> list[tuple[int, str]]:
    return _scan_py_source(path.read_text(encoding="utf-8", errors="replace"))


def _scan_lines(path: Path) -> list[tuple[int, str]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    out: list[tuple[int, str]] = []
    for lineno, text in _logical_lines(lines, 1):
        if _shell_violates(text):
            out.append((lineno, "script line"))
    return out


def _scan_md(path: Path) -> list[tuple[int, str]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    out: list[tuple[int, str]] = []

    in_fence = False
    fence_lang = ""
    fence_skip = False
    fence_block: list[str] = []
    fence_start = 1

    indent_block: list[str] = []
    indent_start = 1

    def flush_indent() -> None:
        nonlocal indent_block
        if indent_block:
            for lineno, text in _logical_lines(indent_block, indent_start):
                if _shell_violates(text):
                    out.append((lineno, "markdown indented command block"))
        indent_block = []

    for i, raw in enumerate(lines, 1):
        m = _FENCE.match(raw)
        if m:
            if not in_fence:
                flush_indent()
                in_fence = True
                fence_lang = m.group(2).strip().lower()
                fence_skip = fence_lang in _NON_COMMAND_FENCE
                fence_block = []
                fence_start = i + 1
            else:
                if not fence_skip:
                    if fence_lang in _PY_FENCE_LANGS:
                        for lineno, kind in _scan_py_source("\n".join(fence_block)):
                            out.append((fence_start - 1 + lineno, "markdown python block"))
                    else:
                        for lineno, text in _logical_lines(fence_block, fence_start):
                            if _shell_violates(text):
                                out.append((lineno, "markdown command block"))
                in_fence = False
                fence_block = []
            continue
        if in_fence:
            fence_block.append(raw)
            continue
        if _INDENTED.match(raw):
            if not indent_block:
                indent_start = i
            indent_block.append(raw)
        else:
            flush_indent()
    flush_indent()
    if in_fence and not fence_skip:
        if fence_lang in _PY_FENCE_LANGS:
            for lineno, kind in _scan_py_source("\n".join(fence_block)):
                out.append((fence_start - 1 + lineno, "markdown python block"))
        else:
            for lineno, text in _logical_lines(fence_block, fence_start):
                if _shell_violates(text):
                    out.append((lineno, "markdown command block"))
    return out


def scan_file(path: Path) -> list[tuple[int, str]]:
    """Return (line_number, kind) violations for one file."""
    suffix = path.suffix.lower()
    if suffix == ".py":
        return _scan_py(path)
    if suffix in (".sh", ".ps1"):
        return _scan_lines(path)
    if suffix == ".md":
        return _scan_md(path)
    return []


def tracked_sources() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.py", "*.ps1", "*.sh", "*.md"],
        cwd=ROOT, capture_output=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(
            f"git ls-files inventory failed (exit {result.returncode}): {stderr}"
        )
    return [f for f in result.stdout.decode("utf-8", errors="replace").split("\0") if f]


def repository_violations() -> list[tuple[str, int, str]]:
    out: list[tuple[str, int, str]] = []
    for rel in tracked_sources():
        path = ROOT / rel
        if not path.is_file():
            continue
        for lineno, kind in scan_file(path):
            out.append((rel, lineno, kind))
    return out


# --- repository guard -------------------------------------------------------

def test_repository_headless_blender_calls_pass_exit_code() -> None:
    violations = repository_violations()
    assert not violations, (
        "headless Blender --background commands missing --python-exit-code:\n"
        + "\n".join(f"  {rel}:{lineno} ({kind})" for rel, lineno, kind in violations)
    )


# --- synthetic fixtures -----------------------------------------------------

def test_py_multiline_list_literal_missing_flag_is_flagged(tmp_path: Path) -> None:
    src = tmp_path / "run.py"
    src.write_text(
        "command = [blender, '--background', '--factory-startup',\n"
        "           '--disable-autoexec', '--python', 'script.py', '--', 'out']\n",
        encoding="utf-8",
    )
    violations = scan_file(src)
    assert violations, "multi-line list literal missing the flag must be flagged"
    assert violations[0][0] == 1


def test_py_multiline_list_literal_with_flag_passes(tmp_path: Path) -> None:
    src = tmp_path / "run.py"
    src.write_text(
        "command = [blender, '--background', '--factory-startup',\n"
        "           '--disable-autoexec', '--python-exit-code', '1',\n"
        "           '--python', 'script.py', '--', 'out']\n",
        encoding="utf-8",
    )
    assert scan_file(src) == []


def test_py_subprocess_run_string_command_missing_flag_is_flagged(tmp_path: Path) -> None:
    src = tmp_path / "run.py"
    src.write_text(
        "import subprocess\n"
        "subprocess.run(\"blender --background --python job.py\", shell=True)\n",
        encoding="utf-8",
    )
    violations = scan_file(src)
    assert violations, "executable command string missing the flag must be flagged"
    assert violations[0][0] == 2


def test_py_subprocess_run_string_command_with_flag_passes(tmp_path: Path) -> None:
    src = tmp_path / "run.py"
    src.write_text(
        "import subprocess\n"
        "subprocess.run(\n"
        "    \"blender --background --python-exit-code 1 --python job.py\",\n"
        "    shell=True)\n",
        encoding="utf-8",
    )
    assert scan_file(src) == []


def test_py_docstring_usage_without_flag_is_not_flagged(tmp_path: Path) -> None:
    """Prose/docstring command templates are not executable and stay unflagged."""
    src = tmp_path / "run.py"
    src.write_text(
        '"""Usage: blender --background --factory-startup --python job.py -- <out>"""\n'
        "def run() -> None:\n"
        "    pass\n",
        encoding="utf-8",
    )
    assert scan_file(src) == []


def test_sh_line_missing_flag_is_flagged(tmp_path: Path) -> None:
    src = tmp_path / "run.sh"
    src.write_text('"$BL" --background --factory-startup --python script.py -- out\n',
                   encoding="utf-8")
    violations = scan_file(src)
    assert violations and violations[0][0] == 1


def test_sh_line_with_flag_passes(tmp_path: Path) -> None:
    src = tmp_path / "run.sh"
    src.write_text(
        '"$BL" --background --factory-startup --python-exit-code 1 '
        '--python script.py -- out\n',
        encoding="utf-8",
    )
    assert scan_file(src) == []


def test_sh_two_commands_semicolon_first_missing_is_flagged(tmp_path: Path) -> None:
    src = tmp_path / "run.sh"
    src.write_text(
        "blender --background --python a.py; "
        "blender --background --python-exit-code 1 --python b.py\n",
        encoding="utf-8",
    )
    violations = scan_file(src)
    assert violations and violations[0][0] == 1, (
        "a flag in the second command must not discharge the first"
    )


def test_sh_two_commands_semicolon_both_with_flag_passes(tmp_path: Path) -> None:
    src = tmp_path / "run.sh"
    src.write_text(
        "blender --background --python-exit-code 1 --python a.py; "
        "blender --background --python-exit-code 1 --python b.py\n",
        encoding="utf-8",
    )
    assert scan_file(src) == []


def test_sh_comment_flag_does_not_discharge_missing(tmp_path: Path) -> None:
    src = tmp_path / "run.sh"
    src.write_text(
        "blender --background --python a.py # remember --python-exit-code 1\n",
        encoding="utf-8",
    )
    violations = scan_file(src)
    assert violations and violations[0][0] == 1, (
        "a flag in a comment must not discharge the command"
    )


def test_md_bash_block_missing_flag_is_flagged(tmp_path: Path) -> None:
    src = tmp_path / "run.md"
    src.write_text(
        "```bash\n"
        "blender --background --factory-startup \\\n"
        "  --python script.py -- out\n"
        "```\n",
        encoding="utf-8",
    )
    violations = scan_file(src)
    assert violations and violations[0][0] == 2


def test_md_bash_block_with_flag_passes(tmp_path: Path) -> None:
    src = tmp_path / "run.md"
    src.write_text(
        "```bash\n"
        "blender --background --factory-startup --python-exit-code 1 \\\n"
        "  --python script.py -- out\n"
        "```\n",
        encoding="utf-8",
    )
    assert scan_file(src) == []


def test_md_indented_command_block_missing_flag_is_flagged(tmp_path: Path) -> None:
    src = tmp_path / "run.md"
    src.write_text(
        "Command:\n\n"
        "    blender --background --python a.py\n",
        encoding="utf-8",
    )
    violations = scan_file(src)
    assert violations, "indented command block missing the flag must be flagged"
    assert violations[0][0] == 3


def test_md_python_fence_multiline_list_with_flag_passes(tmp_path: Path) -> None:
    src = tmp_path / "run.md"
    src.write_text(
        "```python\n"
        "subprocess.run([\n"
        "    'blender', '--background',\n"
        "    '--python-exit-code', '1', '--python', 'job.py'\n"
        "])\n"
        "```\n",
        encoding="utf-8",
    )
    assert scan_file(src) == []


def test_md_python_fence_multiline_list_missing_flag_is_flagged(tmp_path: Path) -> None:
    src = tmp_path / "run.md"
    src.write_text(
        "```python\n"
        "subprocess.run([\n"
        "    'blender', '--background',\n"
        "    '--python', 'job.py'\n"
        "])\n"
        "```\n",
        encoding="utf-8",
    )
    violations = scan_file(src)
    assert violations and violations[0][0] == 2, (
        "multiline list in a python fence must be flagged at its opening line"
    )


def test_md_text_block_is_recorded_not_runnable(tmp_path: Path) -> None:
    """A text-fenced block is a recorded command/log, not a runnable template."""
    src = tmp_path / "run.md"
    src.write_text(
        "```text\n"
        "blender --background --factory-startup --python script.py -- out\n"
        "```\n",
        encoding="utf-8",
    )
    assert scan_file(src) == []


def test_tracked_sources_raises_on_git_failure(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=["git", "ls-files"], returncode=128,
            stdout=b"", stderr=b"fatal: inventory failed",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="inventory failed"):
        tracked_sources()


def test_tracked_sources_returns_paths_on_success(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=["git", "ls-files"], returncode=0,
            stdout=b"a.py\0b.sh\0", stderr=b"",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert tracked_sources() == ["a.py", "b.sh"]


def test_empty_file_has_no_violations(tmp_path: Path) -> None:
    src = tmp_path / "empty.sh"
    src.write_text("", encoding="utf-8")
    assert scan_file(src) == []
