"""PROJECT_STATE regeneration after a merge (tools/state/after_merge.py), offline.

All PR states are injected (a dict, a fake runner or a JSON file); no test calls git or gh on the network.
The checked-in-file test runs only when DT_PR_STATES_JSON names a states file, e.g.

    gh pr list --state all --limit 400 --json number,state \
      --jq 'map({(.number|tostring): .state}) | add' > states.json
    DT_PR_STATES_JSON=states.json uv run pytest tests/test_state_after_merge.py
"""
import json
import os
from pathlib import Path

import pytest

import tools.state.after_merge as am

ROOT = Path(__file__).resolve().parents[1]

SNAPSHOT = """# Project state

## In production

- `82feaa8` Merge pull request #1025 from artsafro/improve/x

## Harness

Open pull requests:
- #1006 Relative invariants (#968) [improve/issue-968-relative] draft
- #1048 Improve: agr_tools sibling modules [improve/agr-tools-sibling]
- #1099 docs: decision D220 [docs/decision-d220-delivery-external-data]

## Next step
"""


def test_listed_open_prs_reads_only_the_open_section():
    assert am.listed_open_prs(SNAPSHOT) == [1006, 1048, 1099]


def test_a_merged_pr_listed_as_open_is_stale():
    states = {1006: "MERGED", 1048: "OPEN", 1099: "OPEN"}
    assert am.stale_open_prs(SNAPSHOT, states) == [1006]


def test_closed_counts_as_stale_and_open_does_not():
    assert am.stale_open_prs(SNAPSHOT, {1006: "OPEN", 1048: "CLOSED", 1099: "open"}) == [1048]
    assert am.stale_open_prs(SNAPSHOT, {1006: "OPEN", 1048: "OPEN", 1099: "OPEN"}) == []


def test_check_cli_fails_on_injected_merged_state(tmp_path, capsys):
    state = tmp_path / "PROJECT_STATE.md"
    state.write_text(SNAPSHOT, encoding="utf-8")
    states = tmp_path / "states.json"
    states.write_text(json.dumps({"1006": "MERGED", "1048": "OPEN", "1099": "OPEN"}), encoding="utf-8")
    assert am.main(["check", "--file", str(state), "--states-json", str(states)]) == 1
    assert "[1006]" in capsys.readouterr().out
    states.write_text(json.dumps({"1006": "OPEN", "1048": "OPEN", "1099": "OPEN"}), encoding="utf-8")
    assert am.main(["check", "--file", str(state), "--states-json", str(states)]) == 0


@pytest.mark.skipif(not os.environ.get("DT_PR_STATES_JSON"), reason="needs injected PR states (DT_PR_STATES_JSON)")
def test_checked_in_project_state_lists_no_merged_pr_as_open():
    text = (ROOT / "docs" / "PROJECT_STATE.md").read_text(encoding="utf-8")
    stale = am.stale_open_prs(text, am.file_states(os.environ["DT_PR_STATES_JSON"]))
    assert not stale, f"docs/PROJECT_STATE.md lists merged/closed PRs as open: {stale}"


@pytest.mark.parametrize("command, number", [
    ("gh pr merge 1097 --merge", 1097),
    ("gh pr merge --squash 1097", 1097),
    ("cd x && gh pr merge https://github.com/o/r/pull/42 --merge", 42),
    ("gh pr merge '#7'", 7),
    ("gh pr merge --merge", None),
    ("gh pr merge feature/branch", None),
    ("gh pr view 1097", None),
])
def test_merged_pr_from_command(command, number):
    assert am.merged_pr_from_command(command) == number


class FakeRepo:
    """Answers the argv sequences refresh() sends; records them. `after` is the regenerated PROJECT_STATE."""

    def __init__(self, tmp_path, states, dirty=False, changed=True, after=SNAPSHOT, has_main=True):
        self.main = tmp_path / "main"
        (self.main / "docs").mkdir(parents=True)
        self.states, self.dirty, self.changed, self.after, self.has_main = states, dirty, changed, after, has_main
        self.calls = []

    def __call__(self, argv, cwd):
        self.calls.append((list(argv), Path(cwd)))
        if argv[:3] == ["gh", "pr", "view"]:
            return 0, json.dumps({"state": self.states[int(argv[3])]})
        if argv[:3] == ["git", "worktree", "list"]:
            branch = "branch refs/heads/main" if self.has_main else "branch refs/heads/other"
            return 0, f"worktree {self.main}\nHEAD abc\n{branch}\n\nworktree /w\nHEAD def\nbranch refs/heads/x\n"
        if argv[:3] == ["git", "status", "--porcelain"]:
            if len(argv) == 3:
                return 0, " M x\n" if self.dirty else ""
            return 0, " M docs/PROJECT_STATE.md\n" if self.changed else ""
        if len(argv) > 1 and argv[1] == am.GENERATOR:
            (self.main / am.STATE).write_text(self.after, encoding="utf-8")
            return 0, ""
        return 0, ""

    def argvs(self):
        return [c[0] for c in self.calls]


def test_refresh_regenerates_and_commits_on_main_without_push(tmp_path):
    repo = FakeRepo(tmp_path, {1097: "MERGED", 1006: "OPEN", 1048: "OPEN", 1099: "OPEN"})
    code, message = am.refresh(1097, run=repo, cwd=tmp_path, python="py")
    assert code == 0, message
    argvs = repo.argvs()
    assert ["git", "merge", "--ff-only", "origin/main"] in argvs
    assert ["py", am.GENERATOR, "--repo", "."] in argvs
    commits = [a for a in argvs if a[:2] == ["git", "commit"]]
    assert commits and "after #1097" in commits[0][3]
    assert not any(a[:2] == ["git", "push"] for a in argvs)
    assert all(cwd == repo.main for argv, cwd in repo.calls if argv[0] == "git" and argv[1] != "worktree")
    assert "push" in message


def test_refresh_fails_when_the_new_state_still_lists_a_merged_pr(tmp_path):
    repo = FakeRepo(tmp_path, {1097: "MERGED", 1006: "MERGED", 1048: "OPEN", 1099: "OPEN"})
    code, message = am.refresh(1097, run=repo, cwd=tmp_path, python="py")
    assert code == 1 and "[1006]" in message


def test_refresh_refuses_an_unmerged_pr_and_touches_nothing(tmp_path):
    repo = FakeRepo(tmp_path, {1097: "OPEN"})
    code, _message = am.refresh(1097, run=repo, cwd=tmp_path, python="py")
    assert code == 2
    assert repo.argvs() == [["gh", "pr", "view", "1097", "--json", "state"]]


def test_refresh_refuses_a_dirty_main_checkout(tmp_path):
    repo = FakeRepo(tmp_path, {1097: "MERGED"}, dirty=True)
    code, message = am.refresh(1097, run=repo, cwd=tmp_path, python="py")
    assert code == 2 and "dirty" in message
    assert not any(a[:2] in (["git", "fetch"], ["git", "commit"]) for a in repo.argvs())


def test_refresh_refuses_without_a_main_checkout(tmp_path):
    repo = FakeRepo(tmp_path, {1097: "MERGED"}, has_main=False)
    code, message = am.refresh(1097, run=repo, cwd=tmp_path, python="py")
    assert code == 2 and "main" in message


def test_refresh_unchanged_state_makes_no_commit(tmp_path):
    repo = FakeRepo(tmp_path, {1097: "MERGED", 1006: "OPEN", 1048: "OPEN", 1099: "OPEN"}, changed=False)
    code, message = am.refresh(1097, run=repo, cwd=tmp_path, python="py")
    assert code == 0 and "unchanged" in message
    assert not any(a[:2] == ["git", "commit"] for a in repo.argvs())


def test_hook_runs_refresh_only_for_gh_pr_merge(tmp_path):
    repo = FakeRepo(tmp_path, {1097: "MERGED", 1006: "OPEN", 1048: "OPEN", 1099: "OPEN"})
    assert am.hook(json.dumps({"tool_input": {"command": "gh pr view 1097"}}), run=repo, cwd=tmp_path) is None
    assert repo.calls == []
    out = am.hook(json.dumps({"tool_input": {"command": "gh pr merge 1097 --merge"}}), run=repo, cwd=tmp_path)
    assert out["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert "after #1097" in out["hookSpecificOutput"]["additionalContext"]


def test_hook_without_a_number_asks_for_the_manual_run(tmp_path):
    repo = FakeRepo(tmp_path, {})
    out = am.hook(json.dumps({"tool_input": {"command": "gh pr merge --merge"}}), run=repo, cwd=tmp_path)
    assert "--pr <N>" in out["hookSpecificOutput"]["additionalContext"]
    assert repo.calls == []


def test_settings_wire_the_hook_after_shell_tools():
    hooks = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))["hooks"]["PostToolUse"]
    wired = [g for g in hooks for h in g["hooks"] if "tools/state/after_merge.py\" hook" in h["command"]]
    assert wired and "Bash" in wired[0]["matcher"] and "PowerShell" in wired[0]["matcher"]
