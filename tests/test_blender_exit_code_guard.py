"""Guard: every headless Blender call passes ``--python-exit-code 1`` (#439).

new-case: static scan of tracked command sources that flags any Blender
``--background`` command missing ``--python-exit-code`` (multi-line Python list
literals included), so a Python exception inside Blender can never exit 0 and
read as success.

Scope per file type:
- ``.py``: every ``list``/``tuple`` literal whose string constants contain the
  ``--background`` flag must also contain ``--python-exit-code`` (AST-only, never
  imports or executes the scanned module). Docstrings and comments are not list
  literals and are therefore out of scope.
- ``.sh``/``.ps1``: every logical line (backslash/backtick continuations joined)
  that contains ``--background`` must also contain ``--python-exit-code``.
- ``.md``: fenced code blocks (`` ``` `` / ``~~~``) tagged with a command language
  (bash/sh/zsh/shell/powershell/ps1/pwsh/cmd/bat/python/py/console, or untagged).
  Blocks tagged ``text``/``txt``/``plaintext``/``log``/``output`` are recorded
  commands or logs, not runnable templates; editing a recorded command would
  falsify evidence, so they are skipped. Indented (non-fenced) blocks and prose
  are out of scope.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
import subprocess

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

_FENCE = re.compile(r"^\s*(```+|~~~+)\s*(\S*)\s*$")


def _string_constants(node: ast.AST) -> list[str]:
    return [c.value for c in ast.walk(node)
            if isinstance(c, ast.Constant) and isinstance(c.value, str)]


def _missing(text: str) -> bool:
    """True when a command region line starts Blender headless but lacks the flag."""
    return bool(_BACKGROUND.search(text)) and not _EXIT_CODE.search(text)


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


def _scan_py(path: Path) -> list[tuple[int, str]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"),
                          filename=str(path))
    except SyntaxError:
        return []  # not parseable Python; no list literal to guard
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.List, ast.Tuple)):
            continue
        strings = _string_constants(node)
        if any(_BACKGROUND.search(s) for s in strings) and \
                not any(_EXIT_CODE.search(s) for s in strings):
            out.append((node.lineno, "list/tuple literal"))
    return out


def _scan_lines(path: Path) -> list[tuple[int, str]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    out: list[tuple[int, str]] = []
    for lineno, text in _logical_lines(lines, 1):
        if _missing(text):
            out.append((lineno, "script line"))
    return out


def _scan_md(path: Path) -> list[tuple[int, str]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    out: list[tuple[int, str]] = []
    in_fence = False
    skip = False
    block: list[str] = []
    block_start = 1
    for i, raw in enumerate(lines, 1):
        m = _FENCE.match(raw)
        if m:
            if not in_fence:
                in_fence = True
                lang = m.group(2).strip().lower()
                skip = lang in _NON_COMMAND_FENCE
                block = []
                block_start = i + 1  # first content line of the block
            else:
                if not skip:
                    for lineno, text in _logical_lines(block, block_start):
                        if _missing(text):
                            out.append((lineno, "markdown command block"))
                in_fence = False
                skip = False
                block = []
            continue
        if in_fence:
            block.append(raw)
    if in_fence and not skip:
        for lineno, text in _logical_lines(block, block_start):
            if _missing(text):
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
        return []
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


def test_empty_file_has_no_violations(tmp_path: Path) -> None:
    src = tmp_path / "empty.sh"
    src.write_text("", encoding="utf-8")
    assert scan_file(src) == []
