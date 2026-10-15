"""Tests for branch_name grader ignoring isSidechain records (#140 / card blind spots).

Every acceptance table row from tmp/branch-name-pr-body.md is implemented here:
- A1: test_sidechain_last_branch_does_not_fail_main
- A2: test_sidechain_last_branch_does_not_hide_main_failure
- A3: test_sidechain_commit_does_not_fail_main
- A4: test_only_sidechain_branches_are_not_measured
- A5: test_existing_fixture_verdicts
- E1: test_sidechain_position_is_irrelevant
- E2: test_main_commit_failure_survives_rename
- E3: test_repeated_sidechains_are_ignored
- E4: test_empty_transcript_is_not_measured
- E5: test_partial_transcript_is_not_measured
- E6: test_missing_branch_does_not_erase_main_branch
"""
import json
from pathlib import Path

import pytest
from twinqa.evals.graders import branch_name

ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = ROOT / "evals" / "branch-name" / "fixtures"

FIXTURE_EXPECTATIONS = {
    "auto-branch-commit.real-excerpt.jsonl": False,
    "renamed.corrected.synthetic.jsonl": True,
}


def write_jsonl(path, records):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    return path


def assistant(*blocks, **extra):
    return {"type": "assistant", "isSidechain": False, "message": {"role": "assistant", "content": list(blocks)},
            **extra}


def user(content, **extra):
    return {"type": "user", "isSidechain": False, "message": {"role": "user", "content": content}, **extra}


def call(tool, args, id="t1"):
    return {"type": "tool_use", "id": id, "name": tool, "input": args}


def text(value):
    return {"type": "text", "text": value}


def result(id="t1", value="ok", error=False, **extra):
    block = {"type": "tool_result", "tool_use_id": id, "content": value}
    if error:
        block["is_error"] = True
    return user([block], **extra)


# --- Acceptance table rows (A1 - A5) -----------------------------------------------------------------------------

def test_sidechain_last_branch_does_not_fail_main(tmp_path):
    """A1: Main fix/qa-orientation; trailing sidechain worktree-agent-ab12cd -> passed=True, 0 details."""
    records = [
        user("start", gitBranch="fix/qa-orientation"),
        assistant(text("done"), gitBranch="fix/qa-orientation"),
        assistant(text("sidechain"), isSidechain=True, gitBranch="worktree-agent-ab12cd"),
    ]
    row = branch_name({"transcript": [write_jsonl(tmp_path / "t.jsonl", records)]})
    assert row["passed"] is True
    assert row["details"] == []


def test_sidechain_last_branch_does_not_hide_main_failure(tmp_path):
    """A2: Main worktree-agent-ab12cd; trailing sidechain fix/qa-orientation -> passed=False, 1 detail."""
    records = [
        user("start", gitBranch="worktree-agent-ab12cd"),
        assistant(text("done"), gitBranch="worktree-agent-ab12cd"),
        assistant(text("sidechain"), isSidechain=True, gitBranch="fix/qa-orientation"),
    ]
    row = branch_name({"transcript": [write_jsonl(tmp_path / "t.jsonl", records)]})
    assert row["passed"] is False
    assert len(row["details"]) == 1
    assert row["details"][0]["branch"] == "worktree-agent-ab12cd"
    assert row["details"][0]["reason"] == "auto-generated worktree branch"


@pytest.mark.parametrize("scenario, trailing", [
    ("sidechain_ending", []),
    ("main_after_sidechain", [assistant(text("continue on main"), gitBranch="main")]),
])
def test_sidechain_commit_does_not_fail_main(tmp_path, scenario, trailing):
    """A3: Sidechain git commit on worktree-agent-ab12cd; main main -> passed=True, 0 details."""
    records = [
        user("work on main", gitBranch="main"),
        assistant(
            call("Bash", {"command": "git commit -q -m 'subagent commit'"}, id="c1"),
            isSidechain=True,
            gitBranch="worktree-agent-ab12cd",
        ),
        result("c1", "committed", isSidechain=True, gitBranch="worktree-agent-ab12cd"),
        *trailing,
    ]
    row = branch_name({"transcript": [write_jsonl(tmp_path / f"t_{scenario}.jsonl", records)]})
    assert row["passed"] is True
    assert row["details"] == []


@pytest.mark.parametrize("scenario, leading", [
    ("unrelated_main_without_branch", [user("look around")]),
    ("truly_sidechain_only", []),
])
def test_only_sidechain_branches_are_not_measured(tmp_path, scenario, leading):
    """A4: Sidechain fix/qa-orientation only with commit -> passed=None, 'no commit record and no gitBranch'."""
    records = [
        *leading,
        assistant(
            call("Bash", {"command": "git commit -q -m 'sidechain commit'"}, id="c1"),
            isSidechain=True,
            gitBranch="fix/qa-orientation",
        ),
        result("c1", "committed", isSidechain=True, gitBranch="fix/qa-orientation"),
    ]
    row = branch_name({"transcript": [write_jsonl(tmp_path / f"t_{scenario}.jsonl", records)]})
    assert row["passed"] is None
    assert row["measured"] == "not measured"
    assert "no commit record and no gitBranch" in row.get("error", "")


def test_existing_fixture_verdicts():
    """A5: Every evals/branch-name/fixtures/*.jsonl produces its unchanged expected verdict."""
    fixture_files = list(FIXTURES_DIR.glob("*.jsonl"))
    assert fixture_files, f"No fixtures found in {FIXTURES_DIR}"
    assert {p.name for p in fixture_files} == set(FIXTURE_EXPECTATIONS.keys()), (
        f"Fixture mismatch: found {[p.name for p in fixture_files]}, "
        f"expected {list(FIXTURE_EXPECTATIONS.keys())}"
    )
    for path in sorted(fixture_files):
        expected = FIXTURE_EXPECTATIONS[path.name]
        row = branch_name({"transcript": [path]})
        assert row["passed"] is expected, (
            f"Fixture {path.name}: expected passed={expected}, got {row['passed']}"
        )


# --- Edge cases (E1 - E6) ----------------------------------------------------------------------------------------

def test_sidechain_position_is_irrelevant(tmp_path):
    """E1: Bad sidechain before, between, after valid main records -> passed=True, 0 details."""
    records = [
        assistant(text("sub before"), isSidechain=True, gitBranch="worktree-agent-ab12cd"),
        user("main 1", gitBranch="fix/qa-orientation"),
        assistant(text("sub between"), isSidechain=True, gitBranch="claude/auto-branch-123456"),
        assistant(text("main 2"), gitBranch="fix/qa-orientation"),
        assistant(text("sub after"), isSidechain=True, gitBranch="worktree-agent-ab12cd"),
    ]
    row = branch_name({"transcript": [write_jsonl(tmp_path / "t.jsonl", records)]})
    assert row["passed"] is True
    assert row["details"] == []


def test_main_commit_failure_survives_rename(tmp_path):
    """E2: Main bad-branch commit, main fix/qa-orientation, sidechain main -> passed=False, 1 detail at record index."""
    bad_branch = "claude/auto-branch-123456"
    records = [
        user("start"),
        assistant(
            call("Bash", {"command": "git commit -q -m 'bad commit'"}, id="c1"),
            gitBranch=bad_branch,
        ),
        result("c1", "committed", gitBranch=bad_branch),
        assistant(text("renamed branch"), gitBranch="fix/qa-orientation"),
        assistant(text("subagent"), isSidechain=True, gitBranch="main"),
    ]
    row = branch_name({"transcript": [write_jsonl(tmp_path / "t.jsonl", records)]})
    assert row["passed"] is False
    assert len(row["details"]) == 1
    assert row["details"][0]["record"] == 1
    assert row["details"][0]["branch"] == bad_branch
    assert row["details"][0]["reason"] == "auto-generated worktree branch"


def test_repeated_sidechains_are_ignored(tmp_path):
    """E3: Three bad-branch sidechain records after main fix/qa-orientation -> passed=True, 0 details."""
    records = [
        user("main work", gitBranch="fix/qa-orientation"),
        assistant(text("main done"), gitBranch="fix/qa-orientation"),
        assistant(text("sub1"), isSidechain=True, gitBranch="worktree-agent-ab12cd"),
        user("sub2", isSidechain=True, gitBranch="claude/auto-branch-123456"),
        assistant(text("sub3"), isSidechain=True, gitBranch="worktree-agent-fe98dc"),
    ]
    row = branch_name({"transcript": [write_jsonl(tmp_path / "t.jsonl", records)]})
    assert row["passed"] is True
    assert row["details"] == []


def test_empty_transcript_is_not_measured(tmp_path):
    """E4: Empty JSONL -> passed=None, not measured."""
    empty_file = tmp_path / "empty.jsonl"
    empty_file.write_text("", encoding="utf-8")
    row = branch_name({"transcript": [empty_file]})
    assert row["passed"] is None
    assert row["measured"] == "not measured"
    assert "incomplete evidence" in row.get("error", "")


def test_partial_transcript_is_not_measured(tmp_path):
    """E5: Main fix/qa-orientation plus torn final JSON line -> passed=None, not measured."""
    records = [
        user("start", gitBranch="fix/qa-orientation"),
        assistant(text("done"), gitBranch="fix/qa-orientation"),
    ]
    path = write_jsonl(tmp_path / "partial.jsonl", records)
    with path.open("a", encoding="utf-8") as f:
        f.write('{"type": "user", "message": {"role": "user", "content": [{"type": "tool_res\n')
    row = branch_name({"transcript": [path]})
    assert row["passed"] is None
    assert row["measured"] == "not measured"
    assert "incomplete evidence" in row.get("error", "")


def test_missing_branch_does_not_erase_main_branch(tmp_path):
    """E6: Main fix/qa-orientation followed by main record without gitBranch -> passed=True, 0 details."""
    records = [
        user("start", gitBranch="fix/qa-orientation"),
        assistant(text("working"), gitBranch="fix/qa-orientation"),
        assistant(text("turn without branch")),
    ]
    row = branch_name({"transcript": [write_jsonl(tmp_path / "t.jsonl", records)]})
    assert row["passed"] is True
    assert row["details"] == []
