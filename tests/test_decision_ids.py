"""Decision ids cannot collide across parallel branches (#1037): tools/git-hooks/decision_ids.py and pre-commit."""

import importlib.util
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/git-hooks/decision_ids.py"
_spec = importlib.util.spec_from_file_location("decision_ids", TOOL)
ids = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ids)

HEAD = "# Decision log\n\n| Id | Date | Decision | Applies to | Source |\n|---|---|---|---|---|\n"


def row(did, text):
    return f"| {did} | 2026-11-09 | {text} | `x.md` | chat |\n"


def log(*pairs):
    return HEAD + "".join(row(d, t) for d, t in pairs)


def git(repo, *args, check=True):
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode != 0:
        raise AssertionError(f"git {args}: {r.stderr}")
    return r


def commit(repo, text, msg="c"):
    (repo / "docs").mkdir(exist_ok=True)
    (repo / "docs/decisions.md").write_text(text, encoding="utf-8", newline="\n")
    git(repo, "add", "docs/decisions.md")
    git(repo, "commit", "-q", "--no-verify", "-m", msg)


@pytest.fixture
def repo(tmp_path):
    """main: D001-D002; branch `feature` forks there; main then adds D003 'work-FBX rule'."""
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    git(r, "config", "user.email", "t@t")
    git(r, "config", "user.name", "t")
    git(r, "config", "core.autocrlf", "false")
    commit(r, log(("D001", "one"), ("D002", "two")))
    git(r, "branch", "feature")
    commit(r, log(("D001", "one"), ("D002", "two"), ("D003", "work-FBX rule")))
    git(r, "checkout", "-q", "feature")
    return r


def cli(repo, *args):
    r = subprocess.run([sys.executable, str(TOOL), *args, "--repo-dir", str(repo)], capture_output=True,
                       text=True, encoding="utf-8")
    return r.returncode, r.stdout + r.stderr


# --- acceptance: collision detected, free id passes -------------------------------------------------------------

def test_reused_main_id_fails(repo):
    commit(repo, log(("D001", "one"), ("D002", "two"), ("D003", "OKS 1 is 290k triangles")))
    code, out = cli(repo, "check", "--base", "main", "--no-open-prs")
    assert code == 1 and "D003: main already uses it" in out and "D004" in out


def test_free_id_passes(repo):
    commit(repo, log(("D001", "one"), ("D002", "two"), ("D004", "OKS 1 is 290k triangles")))
    code, out = cli(repo, "check", "--base", "main", "--no-open-prs")
    assert code == 0, out
    assert "open PRs NOT checked" in out


def test_id_of_another_open_pr_fails(repo):
    git(repo, "branch", "other", "main")
    git(repo, "checkout", "-q", "other")
    commit(repo, log(("D001", "one"), ("D002", "two"), ("D003", "work-FBX rule"), ("D004", "Kasatkino rule")))
    git(repo, "checkout", "-q", "feature")
    commit(repo, log(("D001", "one"), ("D002", "two"), ("D004", "Garibaldi rule")))
    code, out = cli(repo, "check", "--base", "main", "--pr-rev", "PR #9=other")
    assert code == 1 and "D004: also allocated by PR #9" in out


def test_same_row_on_stacked_pr_passes(repo):
    commit(repo, log(("D001", "one"), ("D002", "two"), ("D004", "shared rule")))
    git(repo, "branch", "child", "feature")
    code, out = cli(repo, "check", "--base", "main", "--pr-rev", "PR #10=child")
    assert code == 0, out


def test_duplicate_row_in_branch_fails(repo):
    git(repo, "merge", "-q", "--no-edit", "-s", "ours", "main")
    commit(repo, log(("D001", "one"), ("D002", "two"), ("D003", "work-FBX rule"), ("D003", "branch rule")))
    code, out = cli(repo, "check", "--base", "main", "--no-open-prs")
    assert code == 1 and "D003: defined 2 times" in out


def test_edited_existing_row_passes(repo):
    commit(repo, log(("D001", "one, superseded by D004"), ("D002", "two"), ("D004", "new")))
    code, out = cli(repo, "check", "--base", "main", "--no-open-prs")
    assert code == 0, out


def test_renumbered_after_merging_main_passes(repo):
    commit(repo, log(("D001", "one"), ("D002", "two"), ("D003", "branch rule")))
    assert cli(repo, "check", "--base", "main", "--no-open-prs")[0] == 1
    git(repo, "merge", "-q", "--no-edit", "-s", "ours", "main")
    commit(repo, log(("D001", "one"), ("D002", "two"), ("D003", "work-FBX rule"), ("D004", "branch rule")))
    code, out = cli(repo, "check", "--base", "main", "--no-open-prs")
    assert code == 0, out


def test_staged_reads_index_not_worktree(repo):
    (repo / "docs/decisions.md").write_text(log(("D001", "one"), ("D002", "two"), ("D003", "x")), encoding="utf-8")
    git(repo, "add", "docs/decisions.md")
    (repo / "docs/decisions.md").write_text(log(("D001", "one"), ("D002", "two"), ("D004", "x")), encoding="utf-8")
    assert cli(repo, "check", "--base", "main", "--no-open-prs")[0] == 0
    assert cli(repo, "check", "--base", "main", "--no-open-prs", "--staged")[0] == 1


def test_rev_mode(repo):
    commit(repo, log(("D001", "one"), ("D002", "two"), ("D003", "x")))
    git(repo, "checkout", "-q", "main")
    code, out = cli(repo, "check", "--base", "main", "--no-open-prs", "--rev", "feature")
    assert code == 1 and "D003" in out


def test_next_is_max_over_main_branch_and_prs(repo):
    git(repo, "branch", "other", "main")
    git(repo, "checkout", "-q", "other")
    commit(repo, log(("D001", "one"), ("D002", "two"), ("D003", "work-FBX rule"), ("D007", "far")))
    git(repo, "checkout", "-q", "feature")
    code, out = cli(repo, "next", "--base", "main", "--no-open-prs")
    assert code == 0 and out.splitlines()[0] == "D004"
    code, out = cli(repo, "next", "--base", "main", "--pr-rev", "PR #9=other")
    assert code == 0 and out.splitlines()[0] == "D008"


# --- fail closed --------------------------------------------------------------------------------------------------

def test_missing_base_ref_errors(repo):
    code, out = cli(repo, "check", "--base", "origin/nope", "--no-open-prs")
    assert code == 2 and "base ref 'origin/nope' not found" in out


@pytest.mark.parametrize("text", ["", HEAD, "| D1 | not a row"])
def test_branch_log_without_rows_errors(repo, text):
    (repo / "docs/decisions.md").write_text(text, encoding="utf-8")
    code, out = cli(repo, "check", "--base", "main", "--no-open-prs")
    assert code == 2 and "no decision rows" in out


def test_missing_branch_log_errors(repo):
    (repo / "docs/decisions.md").unlink()
    assert cli(repo, "check", "--base", "main", "--no-open-prs")[0] == 2


def test_base_without_log_errors(repo):
    git(repo, "checkout", "-q", "--orphan", "empty")
    git(repo, "rm", "-q", "-rf", ".")
    (repo / "f").write_text("x")
    git(repo, "add", "f")
    git(repo, "commit", "-q", "-m", "e")
    git(repo, "checkout", "-q", "feature")
    code, out = cli(repo, "check", "--base", "empty", "--no-open-prs")
    assert code == 2 and "no decision rows" in out


def test_no_merge_base_errors(repo):
    git(repo, "checkout", "-q", "--orphan", "lone")
    commit(repo, log(("D001", "lone")))
    code, out = cli(repo, "check", "--base", "main", "--no-open-prs")
    assert code == 2 and "no merge-base" in out


@pytest.mark.parametrize("item", ["noequals", "=main", "x="])
def test_bad_pr_rev_errors(repo, item):
    assert cli(repo, "check", "--base", "main", "--pr-rev", item)[0] == 2


def test_unknown_pr_rev_errors(repo):
    code, out = cli(repo, "check", "--base", "main", "--pr-rev", "PR #1=nope")
    assert code == 2 and "'nope' not found" in out


def test_gh_failure_errors(repo, monkeypatch):
    def boom(*a, **k):
        raise OSError("gh missing")
    monkeypatch.setattr(ids.subprocess, "run", boom)
    with pytest.raises(ids.CheckError, match="cannot run gh"):
        ids.open_pr_logs(repo, None)


def test_fetch_failure_errors(repo):
    code, out = cli(repo, "check", "--base", "origin/main", "--no-open-prs", "--fetch")
    assert code == 2 and "cannot fetch origin/main" in out


@pytest.mark.parametrize("url,expected", [
    ("https://github.com/artsafro/AGR-DigitalTwin-pilot.git", "artsafro/AGR-DigitalTwin-pilot"),
    ("https://github.com/artsafro/AGR-DigitalTwin-pilot", "artsafro/AGR-DigitalTwin-pilot"),
    ("git@github.com:artsafro/x.y.git", "artsafro/x.y"),
    ("ssh://git@github.com/artsafro/x/", "artsafro/x"),
    ("C:/some/bare.git", None),
    ("https://gitlab.com/a/b.git", None),
])
def test_github_repo_comes_from_the_base_remote(repo, url, expected):
    git(repo, "remote", "add", "origin", url)
    git(repo, "remote", "add", "upstream", "https://github.com/someone/else.git")
    if expected:
        assert ids.github_repo("origin/main", repo) == expected
    else:
        with pytest.raises(ids.CheckError, match="pass --repo"):
            ids.github_repo("origin/main", repo)


def test_open_prs_use_base_remote_repo_not_gh_default(repo, monkeypatch):
    """Witness: in the main checkout gh's default was `upstream` and returned 0 PRs, a silent pass."""
    git(repo, "remote", "add", "origin", "https://github.com/artsafro/AGR-DigitalTwin-pilot.git")
    git(repo, "update-ref", "refs/remotes/origin/main", "main")
    seen = []
    real = subprocess.run

    def fake(cmd, *a, **k):
        if cmd[0] == "gh":
            seen.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, "[]", "")
        return real(cmd, *a, **k)
    monkeypatch.setattr(ids.subprocess, "run", fake)
    commit(repo, log(("D001", "one"), ("D002", "two"), ("D004", "x")))
    assert ids.main(["check", "--repo-dir", str(repo)]) == 0
    assert seen and seen[0][-2:] == ["--repo", "artsafro/AGR-DigitalTwin-pilot"]


def test_open_prs_without_known_repo_errors(repo):
    code, out = cli(repo, "check", "--base", "main")
    assert code == 2 and "pass --repo" in out


def test_open_pr_logs_skips_own_branch_and_reads_heads(repo, monkeypatch):
    git(repo, "branch", "other", "main")
    oid = git(repo, "rev-parse", "other").stdout.strip()
    own = git(repo, "rev-parse", "feature").stdout.strip()
    payload = (f'[{{"number": 9, "headRefName": "other", "headRefOid": "{oid}"}},'
               f' {{"number": 8, "headRefName": "feature", "headRefOid": "{own}"}}]')
    real = subprocess.run

    def fake(cmd, *a, **k):
        if cmd[0] == "gh":
            return subprocess.CompletedProcess(cmd, 0, payload, "")
        return real(cmd, *a, **k)
    monkeypatch.setattr(ids.subprocess, "run", fake)
    out = ids.open_pr_logs(repo, None)
    assert list(out) == ["PR #9 (other)"] and "work-FBX rule" in out["PR #9 (other)"]


def test_open_pr_unfetchable_head_errors(repo, monkeypatch):
    payload = '[{"number": 9, "headRefName": "x", "headRefOid": "' + "1" * 40 + '"}]'
    real = subprocess.run

    def fake(cmd, *a, **k):
        if cmd[0] == "gh":
            return subprocess.CompletedProcess(cmd, 0, payload, "")
        return real(cmd, *a, **k)
    monkeypatch.setattr(ids.subprocess, "run", fake)
    with pytest.raises(ids.CheckError, match="cannot be fetched"):
        ids.open_pr_logs(repo, None)


# --- invariant probe: after any set of passing branches merge, every id names one decision ----------------------

def test_probe_passing_branches_never_collide_on_merge():
    rng = random.Random(1037)
    trials = 0
    for _ in range(400):
        main_n = rng.randint(1, 30)
        main = [(f"D{i:03d}", f"main {i}") for i in range(1, main_n + 1)]
        fork = rng.randint(1, main_n)
        branches = {}
        for b in range(rng.randint(2, 4)):
            new = [(f"D{rng.randint(1, main_n + 6):03d}", f"b{b} {k}") for k in range(rng.randint(1, 3))]
            branches[f"b{b}"] = (main[:fork], main[:fork] + new)
        main_text = log(*main)
        passed = []
        for name, (base, mine) in branches.items():
            others = {o: log(*m) for o, (_, m) in branches.items() if o != name}
            if not ids.find_collisions(log(*mine), log(*base), main_text, others):
                passed.append(mine)
        merged = {}
        for d, t in main + [r for mine in passed for r in mine]:
            merged.setdefault(d, set()).add(t)
        assert all(len(v) == 1 for v in merged.values()), merged
        trials += 1
    assert trials == 400


# --- pre-commit wiring --------------------------------------------------------------------------------------------

@pytest.mark.skipif(shutil.which("py") is None, reason="pre-commit calls `py -3` (Windows launcher)")
def test_pre_commit_blocks_reused_id_and_passes_free_id(repo, tmp_path):
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", str(origin))
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "push", "-q", "origin", "main")
    hooks = repo / "tools/git-hooks"
    shutil.copytree(ROOT / "tools/git-hooks", hooks, ignore=shutil.ignore_patterns("__pycache__"))
    git(repo, "add", "tools")
    git(repo, "commit", "-q", "--no-verify", "-m", "hooks")
    git(repo, "config", "core.hooksPath", "tools/git-hooks")
    git(repo, "config", "twin.decisionIds", "main-only")
    (repo / "docs/decisions.md").write_text(log(("D001", "one"), ("D002", "two"), ("D003", "branch")),
                                            encoding="utf-8", newline="\n")
    git(repo, "add", "docs/decisions.md")
    r = git(repo, "commit", "-q", "-m", "reuse", check=False)
    assert r.returncode != 0 and "D003: main already uses it" in r.stderr
    (repo / "docs/decisions.md").write_text(log(("D001", "one"), ("D002", "two"), ("D004", "branch")),
                                            encoding="utf-8", newline="\n")
    git(repo, "add", "docs/decisions.md")
    r = git(repo, "commit", "-q", "-m", "free", check=False)
    assert r.returncode == 0, r.stderr


def test_pre_commit_runs_check_only_when_log_staged():
    text = (ROOT / "tools/git-hooks/pre-commit").read_text(encoding="utf-8")
    assert "decision_ids.py" in text and "--staged --fetch" in text and "-- docs/decisions.md" in text
