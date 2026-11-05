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
    "src/dt_ai/spec/compare.py",
    "src/dt_ai/spec/floors.py",
    "src/dt_ai/spec/mesh.py",
    "src/dt_ai/spec/model.py",
    "src/dt_ai/spec/__init__.py",
    "src/twinqa/evals/graders.py",
    "src/twinqa/geometry/checks.py",
    "src/twinqa/geometry/__init__.py",
    "tools/git-hooks/pipeline_gate.py",
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
