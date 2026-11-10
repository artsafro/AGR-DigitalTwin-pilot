"""docs/HARNESS_PLAN.md and docs/prd/agent-ready-harness.md are archived history, not current agent guidance.

Both files left the tree in repo hygiene phase 3 (2026-11-05); they live in git tag `archive/2026-11` and are
cited as `archive/2026-11:<path>` (`docs/ARCHIVE.md`). Every live mention uses that form; the user-visible
strings and docstrings of #920 and the live agent docs of #810 still say "historical".
"""
import ast
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

PLAN = "docs/HARNESS_PLAN.md"
PRD = "docs/prd/agent-ready-harness.md"
ARCHIVE = "archive/2026-11:"

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

# User-visible strings and the docstrings #920 names.
LIVE = (
    "src/dt_ai/cli/main.py",
    "src/dt_ai/geometry/from_spec.py",
    "src/dt_ai/intake/__init__.py",
    "src/dt_ai/intake/check.py",
    "src/dt_ai/intake/model.py",
    "tools/library/build_window_types.py",
    "tools/qa/check_geometry.py",
    "tools/qa/run_benchmark.py",
    "library/windows/window_types.json",
    "src/dt_ai/spec/compare.py",
    "src/dt_ai/spec/floors.py",
    "src/dt_ai/spec/mesh.py",
    "src/dt_ai/spec/model.py",
    "src/dt_ai/spec/__init__.py",
    "src/twinqa/evals/graders.py",
    "src/twinqa/geometry/checks.py",
    "src/twinqa/geometry/__init__.py",
)

# Historical records and frozen inputs keep the old spelling: research and experiment notes, the Russian
# originals, job files, the locked standards, the generated state, the decision log text (only its anchor
# cells are rewritten) and its verbatim detail, the archive index, frozen fixtures and this file.
NOT_LIVE_PREFIX = (
    "docs/research/", "docs/experiments/", "docs/agr/", "docs/archive/", "docs/grill/", "jobs/",
    "technical_library/", "data/", "standards/", "tests/fixtures/",
)
NOT_LIVE_FILE = {
    "docs/PROJECT_STATE.md", "docs/decisions.md", "docs/decisions-detail.md", "docs/ARCHIVE.md",
    "tests/test_harness_plan_historical.py",
}
FROZEN_FIXTURE = re.compile(r"^evals/[^/]+/fixtures/")

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


# Right after the token only: optional ".md", closing quotes, a "§N" citation, then the marker.
_TAIL = re.compile(
    r"""^(?:\.md)?[`'")\]]*[\s,;:]*(?:§\s*[\d.]+(?:\s*[-–]\s*§?\s*[\d.]+)*[\s,;:]*)?(?:"""
    + _MARKER.pattern
    + r")",
    re.IGNORECASE,
)
# Or the citation form "historical: archive/2026-11:docs/HARNESS_PLAN.md" with the marker directly before.
_HEAD = re.compile(r"(?<!not )historical:\s*`?(?:archive/2026-11:)?(?:docs/)?`?$", re.IGNORECASE)


def mention_marks(text: str) -> list[bool]:
    """Each HARNESS_PLAN mention, including one split across two lines.

    The marker must follow the token directly (same citation, same line). A split
    token may cross the break; a marker on another line or after other text does not count.
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
            end = idx + len(_TOKEN)
            if idx < len(line):
                tail = line[end:] if end <= len(line) else window[end:]
                head = line[:idx]
                found.append(_TAIL.search(tail) is not None or _HEAD.search(head) is not None)
            start = end
    return found


def unarchived_mentions(text: str) -> list[int]:
    """1-based line numbers where HARNESS_PLAN or the PRD is cited without the archive form."""
    bad = []
    for number, line in enumerate(text.splitlines(), 1):
        for match in re.finditer(r"HARNESS_PLAN|agent-ready-harness", line):
            path = PLAN if match.group() == _TOKEN else PRD
            # The token must sit inside "archive/2026-11:<path>".
            start = match.start() - (len(path) - len(path.split("/")[-1]))
            if line[max(0, start - len(ARCHIVE)):start + len(path)] != ARCHIVE + path:
                bad.append(number)
                break
    return bad


def live_tree_files():
    """Tracked text files that are live guidance or code; an empty set fails closed."""
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    files = []
    for rel in out.split():
        if rel.startswith(NOT_LIVE_PREFIX) or rel in NOT_LIVE_FILE or FROZEN_FIXTURE.match(rel):
            continue
        if not (ROOT / rel).is_file():
            continue
        files.append(rel)
    assert files, "live tree is empty (fail closed)"
    return files


def test_archived_plans_left_the_tree_and_are_indexed():
    for rel in (PLAN, PRD):
        assert not (ROOT / rel).exists(), f"{rel} is back in the tree; cite {ARCHIVE}{rel} instead"
    index = load_text(ROOT / "docs" / "ARCHIVE.md")
    assert "archive/2026-11" in index
    for rel in (PLAN, PRD):
        assert f"`{rel}`" in index, rel
    for doc in SUPERSEDED_BY:
        assert (ROOT / doc).exists(), doc


def test_every_live_mention_uses_the_archive_form():
    """Generated probe over every tracked live file: N/N mentions carry archive/2026-11:<path>."""
    bad = []
    seen = 0
    for rel in live_tree_files():
        try:
            text = (ROOT / rel).read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue
        if "HARNESS_PLAN" not in text and "agent-ready-harness" not in text:
            continue
        seen += 1
        bad += [f"{rel}:{n}" for n in unarchived_mentions(text)]
    assert seen > 0, "no live file cites the archived plans (the probe found nothing to check)"
    assert not bad, "mention without archive/2026-11:<path>:\n" + "\n".join(bad)


def test_decision_anchor_cells_use_the_archive_form():
    """Decision rows keep their text; only the anchor cell (Applies to) is rewritten."""
    rows = [line for line in load_text(ROOT / "docs" / "decisions.md").splitlines() if line.startswith("| D")]
    hits = 0
    for row in rows:
        anchor = [cell.strip() for cell in row.strip().strip("|").split("|")][3]
        if "HARNESS_PLAN" in anchor or "agent-ready-harness" in anchor:
            hits += 1
            assert unarchived_mentions(anchor) == [], row[:80]
    assert hits > 0


def test_unarchived_mentions_detector():
    assert unarchived_mentions("see `docs/HARNESS_PLAN.md` §4\n") == [1]
    assert unarchived_mentions("see HARNESS_PLAN §4\n") == [1]
    assert unarchived_mentions("spec `docs/prd/agent-ready-harness.md`\n") == [1]
    assert unarchived_mentions("ok `archive/2026-11:docs/HARNESS_PLAN.md` §4\n") == []
    assert unarchived_mentions("ok archive/2026-11:docs/prd/agent-ready-harness.md\n") == []
    assert unarchived_mentions("archive/2026-10:docs/HARNESS_PLAN.md\n") == [1]
    assert unarchived_mentions("a\narchive/2026-11:docs/HARNESS_PLAN.md and HARNESS_PLAN §5\n") == [2]


def test_agents_md_does_not_list_harness_plan_as_current():
    agents = load_text(ROOT / "AGENTS.md")
    assert "Harness plan, benchmark etalons, pattern registry: `docs/HARNESS_PLAN.md`" not in agents
    assert "docs/ARCHIVE.md" in agents
    assert all(mention_marks(agents)), "AGENTS.md cites HARNESS_PLAN without the historical marker"


def test_not_historical_is_rejected_and_split_lines_are_seen():
    assert mention_marks("docs/HARNESS_PLAN.md is not historical\n") == [False]
    assert mention_marks("docs/HARNESS_PLAN.md, not historical:\n") == [False]
    assert mention_marks("see docs/HARNESS_\nPLAN.md §15\n") == [False]
    assert mention_marks("see docs/HARNESS_\nPLAN.md §15 (historical)\n") == [True]
    assert mention_marks("see HARNESS_PLAN §15\nhistorical: docs/pipeline.md\n") == [False]
    assert mention_marks("HARNESS_PLAN §5 is the current rule; old notes (historical)\n") == [False]
    assert mention_marks("see HARNESS_PLAN §4\nfloors (historical) see pipeline\n") == [False]
    assert mention_marks("HARNESS_PLAN §4 and HARNESS_PLAN §5 (historical)\n") == [False, True]
    assert mention_marks("`docs/HARNESS_PLAN.md` (historical)\n") == [True]
    assert mention_marks("(historical: docs/HARNESS_PLAN.md §9)\n") == [True]
    assert mention_marks("(historical: archive/2026-11:docs/HARNESS_PLAN.md §9)\n") == [True]
    assert mention_marks("(not historical: archive/2026-11:docs/HARNESS_PLAN.md §9)\n") == [False]
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


def unmarked_lines(text: str) -> list[int]:
    """1-based line numbers whose HARNESS_PLAN mention has no strict marker."""
    lines = text.splitlines()
    out: list[int] = []
    for i, line in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        window = f"{line}{nxt}"
        if _TOKEN in line and _MARKER.search(window) is None:
            out.append(i + 1)
    return out


def test_no_unmarked_mention_anywhere_in_src_and_tools():
    """Acceptance row 1: the grep over src and tools finds 0 unmarked mentions."""
    bad: list[str] = []
    for top in ("src", "tools"):
        for path in sorted((ROOT / top).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            if _TOKEN not in text:
                continue
            bad += [f"{path.relative_to(ROOT)}:{n}" for n in unmarked_lines(text)]
    assert not bad, bad


@pytest.mark.parametrize("rel", [r for r in LIVE if r.endswith(".py")])
def test_removing_the_marker_fails_naming_file_and_line(rel):
    """Acceptance row 2: strip every marker from a LIVE file; each mention is reported."""
    text = load_text(ROOT / rel)
    assert unmarked_lines(text) == []
    stripped = re.sub(r"\(historical\)|historical:|\bis historical\b", "", text, flags=re.IGNORECASE)
    hit = unmarked_lines(stripped)
    assert hit, f"{rel}: stripping markers was not detected"
    msg = f"{rel}:{hit[0]}"
    assert rel in msg and str(hit[0]) in msg


def test_mesh_frame_error_string_carries_the_marker():
    """Acceptance row 3: the user-visible 'every spec needs a frame' error is marked."""
    lines = load_text(ROOT / "src" / "dt_ai" / "spec" / "mesh.py").splitlines()
    idx = next(i for i, ln in enumerate(lines) if "every spec needs a frame" in ln)
    window = "".join(lines[idx : idx + 2])
    assert _TOKEN in window and _MARKER.search(window), lines[idx]
    text = "\n".join(lines)
    assert unmarked_lines(text) == []
    stripped = "\n".join(
        _MARKER.sub("", ln) if idx <= i < idx + 2 else ln for i, ln in enumerate(lines)
    )
    hits = unmarked_lines(stripped)
    mention = next(i for i in (idx, idx + 1) if _TOKEN in lines[i])
    assert hits == [mention + 1], hits


def test_missing_live_file_fails_never_skips(monkeypatch):
    """Acceptance row 4: a LIVE entry that does not exist is an error, not a skip."""
    import sys

    mod = sys.modules[__name__]
    monkeypatch.setattr(mod, "LIVE", LIVE + ("src/dt_ai/spec/does_not_exist.py",))
    with pytest.raises(AssertionError, match="missing live file"):
        test_live_set_never_leaves_a_harness_plan_mention_unmarked()

# Gate messages and live-doc set (#810).
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
