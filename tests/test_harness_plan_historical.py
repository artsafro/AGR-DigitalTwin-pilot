"""docs/HARNESS_PLAN.md is frozen history, not current agent guidance."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

SUPERSEDED_BY = (
    "docs/pipeline.md",
    "docs/decisions.md",
    "docs/agents/WORKFLOW.md",
    "docs/agents/REVIEW_CHECKLIST.md",
    "docs/domain/patterns/INDEX.md",
    "benchmark/README.md",
    "docs/domain/",
    "docs/backlog.md",
    "docs/agents/CAPABILITIES.md",
)

# User-visible strings and the docstrings #920 names. AGENTS.md stays from #810.
LIVE = (
    "AGENTS.md",
    "src/dt_ai/cli/main.py",
    "src/dt_ai/geometry/from_spec.py",
    "src/dt_ai/intake/__init__.py",
    "src/dt_ai/intake/check.py",
    "src/dt_ai/intake/model.py",
    "tools/library/build_window_types.py",
    "tools/qa/check_geometry.py",
    "tools/qa/run_benchmark.py",
    "library/windows/window_types.json",
)

_TOKEN = "HARNESS_PLAN"
# Strict marker only. Bare "historical" is not enough, so "not historical" does not mark.
# "(historical)" and "historical:" are the citation forms; "is historical" is the #810 AGENTS.md form.
_MARKER = re.compile(
    r"\(historical\)|(?<!not )historical:|\bis historical\b",
    re.IGNORECASE,
)


def load_text(path: Path) -> str:
    """Fail closed: a missing or empty live file is a failed check, not a pass."""
    if not path.is_file():
        raise AssertionError(f"missing live file: {path}")
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise AssertionError(f"empty live file: {path}")
    return text


def mention_marks(text: str) -> list[bool]:
    """Each HARNESS_PLAN mention, including one split across two lines.

    A line is joined with the next line before matching, so a token or its marker
    may cross the break. A mention is marked only when that window has a strict marker.
    """
    lines = text.splitlines()
    found: list[bool] = []
    for i, line in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        window = f"{line}{nxt}"
        start = 0
        while True:
            idx = window.find(_TOKEN, start)
            if idx < 0:
                break
            if idx < len(line):
                found.append(_MARKER.search(window) is not None)
            start = idx + len(_TOKEN)
    return found


def test_harness_plan_starts_with_historical_note():
    text = load_text(ROOT / "docs" / "HARNESS_PLAN.md")
    note, _title, _rest = text.partition("\n# ")
    assert note.lstrip().startswith("Historical"), note[:200]
    for doc in SUPERSEDED_BY:
        assert doc in note
        assert (ROOT / doc).exists()


def test_agents_md_does_not_list_harness_plan_as_current():
    agents = load_text(ROOT / "AGENTS.md")
    assert "Harness plan, benchmark etalons, pattern registry: `docs/HARNESS_PLAN.md`" not in agents
    flags = mention_marks(agents)
    assert flags, "AGENTS.md has no HARNESS_PLAN mention"
    assert all(flags)


def test_not_historical_is_rejected_and_split_lines_are_seen():
    assert mention_marks("docs/HARNESS_PLAN.md is not historical\n") == [False]
    assert mention_marks("docs/HARNESS_PLAN.md, not historical:\n") == [False]
    assert mention_marks("see docs/HARNESS_\nPLAN.md §15\n") == [False]
    assert mention_marks("see docs/HARNESS_\nPLAN.md §15 (historical)\n") == [True]
    assert mention_marks("see HARNESS_PLAN §15\nhistorical: docs/pipeline.md\n") == [True]
    assert mention_marks("docs/HARNESS_PLAN.md is historical.\n") == [True]


def test_dt_intake_help_and_window_type_note_carry_the_marker(capsys):
    from dt_ai.cli.main import parser

    p = parser()
    with pytest.raises(SystemExit) as exc_info:
        p.parse_args(["intake", "--help"])
    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    help_marks = mention_marks(help_text)
    assert help_marks, "dt intake --help does not cite HARNESS_PLAN"
    assert all(help_marks), help_text

    note = load_text(ROOT / "library" / "windows" / "window_types.json")
    # The committed note is one JSON string; the builder source is the other user-visible copy.
    import json
    note_text = json.loads(note)["note"]
    note_marks = mention_marks(note_text + "\n")
    assert note_marks and all(note_marks), note_text
    builder = load_text(ROOT / "tools" / "library" / "build_window_types.py")
    builder_marks = mention_marks(builder)
    assert builder_marks and all(builder_marks)


def test_live_set_never_leaves_a_harness_plan_mention_unmarked():
    """Generated probe: every live mention is marked, N/N. Empty or missing files fail closed."""
    total = 0
    marked = 0
    for rel in LIVE:
        flags = mention_marks(load_text(ROOT / rel))
        assert flags, f"{rel} has no HARNESS_PLAN mention"
        total += len(flags)
        marked += sum(flags)
    assert total > 0
    assert marked == total, f"{marked}/{total} HARNESS_PLAN mentions marked"


def test_load_text_fails_closed_on_missing_and_empty(tmp_path):
    missing = tmp_path / "absent.py"
    with pytest.raises(AssertionError, match="missing live file"):
        load_text(missing)
    empty = tmp_path / "empty.py"
    empty.write_text(" \n\t\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="empty live file"):
        load_text(empty)


# Gate messages and live-doc set (#810).
import ast  # noqa: E402
LIVE_ROOTS = (
    ROOT / "AGENTS.md",
    ROOT / "docs" / "agents",
    ROOT / ".agents",
    ROOT / ".claude",
)
CURRENT_RULE = "docs/agents/WORKFLOW.md"
GATE_IMPL = "tools/git-hooks/pipeline_gate.py"


def live_files():
    files = []
    for root in LIVE_ROOTS:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(path for path in root.rglob("*") if path.is_file())
    return files


def _const_strings(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node.value
    for child in ast.iter_child_nodes(node):
        yield from _const_strings(child)


def test_live_docs_mark_harness_plan_historical():
    """Every HARNESS_PLAN line in the live set says historical; an empty set fails closed."""
    files = live_files()
    assert files, "live-doc set is empty (fail closed)"
    unmarked = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(ROOT).as_posix()
        for number, line in enumerate(text.splitlines(), 1):
            if "HARNESS_PLAN" in line and "historical" not in line.lower():
                unmarked.append(f"{rel}:{number}: {line.strip()}")
    assert not unmarked, "unmarked HARNESS_PLAN mention:\n" + "\n".join(unmarked)


def test_benchmark_readme_marks_harness_plan_historical():
    path = ROOT / "benchmark" / "README.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    hits = [(n, line) for n, line in enumerate(lines, 1) if "HARNESS_PLAN" in line]
    assert hits, "benchmark/README.md no longer cites HARNESS_PLAN"
    unmarked = [f"benchmark/README.md:{n}: {line.strip()}"
                for n, line in hits if "historical" not in line.lower()]
    assert not unmarked, "unmarked HARNESS_PLAN mention:\n" + "\n".join(unmarked)


def test_gate_message_strings_omit_harness_plan():
    """ESCALATION, blocked and the deny reason name the current rule and omit HARNESS_PLAN."""
    gate = ast.parse((ROOT / "tools" / "git-hooks" / "pipeline_gate.py").read_text(encoding="utf-8"))
    found_escalation = False
    found_blocked = False
    for node in ast.walk(gate):
        if isinstance(node, ast.Assign):
            names = [target.id for target in node.targets if isinstance(target, ast.Name)]
            if "ESCALATION" in names:
                found_escalation = True
                blob = "".join(_const_strings(node.value))
                assert "HARNESS_PLAN" not in blob, blob
                assert CURRENT_RULE in blob and GATE_IMPL in blob, blob
        if isinstance(node, ast.Call) and _call_name(node) == "print":
            blob = "".join(_const_strings(node))
            if "blocked" in blob:
                found_blocked = True
                assert "HARNESS_PLAN" not in blob, blob
                assert CURRENT_RULE in blob and GATE_IMPL in blob, blob
    assert found_escalation, "ESCALATION message not found"
    assert found_blocked, "blocked message not found"

    hook = ast.parse((ROOT / ".claude" / "hooks" / "pipeline_gate.py").read_text(encoding="utf-8"))
    found_deny = False
    for node in ast.walk(hook):
        if isinstance(node, ast.FunctionDef) and node.name == "deny":
            found_deny = True
            blob = "".join(_const_strings(node))
            assert "HARNESS_PLAN" not in blob, blob
            assert CURRENT_RULE in blob and GATE_IMPL in blob, blob
    assert found_deny, "deny reason not found"


def _call_name(node):
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None
