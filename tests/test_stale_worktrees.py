import importlib.util
import sqlite3
import subprocess
from pathlib import Path

import pytest


def load_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "stale_worktrees.py"
    spec = importlib.util.spec_from_file_location("stale_worktrees", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_done_clean_zero_unpushed_is_removable():
    module = load_module()
    assert module.classify("done", False, 0) == "removable"


def test_done_dirty_is_kept():
    module = load_module()
    assert module.classify("done", True, 0) == "keep: dirty"


def test_done_clean_unpushed_commits_are_kept():
    module = load_module()
    assert module.classify("done", False, 2) == "keep: unpushed 2"


def test_active_card_statuses_are_kept():
    module = load_module()
    for status in ("running", "blocked", "review"):
        assert module.classify(status, False, 0) == f"keep: card {status}"


def test_missing_card_is_unknown():
    module = load_module()
    assert module.classify(None, False, 0) == "keep: unknown card"


def test_branch_named_by_ready_card_stays_removable_and_lists_wanted_by():
    module = load_module()
    cards = [
        {"id": "t_self", "status": "done", "body": "topic/stale", "branch_name": "topic/stale"},
        {"id": "t_old", "status": "archived", "body": "mentions topic/stale", "branch_name": "other"},
        {"id": "t_x", "status": "ready", "body": "continues topic/stale tomorrow", "branch_name": "topic/next"},
        {"id": "t_done_other", "status": "done", "body": "topic/stale too", "branch_name": "topic/stale"},
    ]
    assert module.classify("done", False, 0) == "removable"
    assert module.wanted_by("topic/stale", "t_self", cards) == ["t_x"]


def test_apply_argv_removes_without_force():
    module = load_module()
    repo = "C:/Users/artsafro/agr-pilot/AGR-DigitalTwin"
    wt = repo + "/.worktrees/t_aa62f98d"
    argv = module.apply_argv(repo, wt)
    assert argv == ["git", "-C", repo, "worktree", "remove", wt]
    assert "--force" not in argv
    assert not any("--force" in arg for arg in argv)


def test_probe_removable_only_for_finished_clean_pushed():
    module = load_module()
    statuses = ("done", "archived", "running", "blocked", "review", "ready", None)
    dirty_values = (False, True)
    unpushed_values = (0, 1, 5, "no-upstream")
    seen = 0
    held = 0
    for status in statuses:
        for dirty in dirty_values:
            for unpushed in unpushed_values:
                seen += 1
                result = module.classify(status, dirty, unpushed)
                removable = status in ("done", "archived") and dirty is False and unpushed == 0
                if removable:
                    assert result == "removable"
                else:
                    assert result != "removable"
                    assert result.startswith("keep:")
                held += 1
    assert seen == held
    assert seen == len(statuses) * len(dirty_values) * len(unpushed_values)


def test_board_db_opens_read_only(tmp_path):
    module = load_module()
    db = tmp_path / "kanban.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE tasks (id TEXT, status TEXT, body TEXT, branch_name TEXT)"
    )
    conn.execute(
        "INSERT INTO tasks (id, status, body, branch_name) VALUES (?, ?, ?, ?)",
        ("t_a", "done", "", "topic/a"),
    )
    conn.commit()
    conn.close()

    readonly = module.open_board(db)
    try:
        row = readonly.execute("SELECT id, status FROM tasks").fetchone()
        assert row == ("t_a", "done")
        with pytest.raises(sqlite3.OperationalError):
            readonly.execute(
                "INSERT INTO tasks (id, status, body, branch_name) VALUES (?, ?, ?, ?)",
                ("t_b", "done", "", "topic/b"),
            )
    finally:
        readonly.close()


def test_missing_db_exits_nonzero(tmp_path, capsys):
    module = load_module()
    missing = tmp_path / "no-such-kanban.db"
    code = module.main(["--db", str(missing), "--repo", str(tmp_path)])
    captured = capsys.readouterr()
    assert code != 0
    assert "missing" in (captured.out + captured.err).lower()


def _git(*args, cwd, check=True):
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and proc.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {proc.stderr}")
    return proc


def make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-b", "main", str(repo), cwd=tmp_path)
    _git("config", "user.email", "test@example.com", cwd=repo)
    _git("config", "user.name", "Test", cwd=repo)
    _git("config", "commit.gpgsign", "false", cwd=repo)
    (repo / ".gitignore").write_text("tmp/\n")
    (repo / "f.txt").write_text("base\n")
    _git("add", ".gitignore", "f.txt", cwd=repo)
    _git("commit", "-m", "init", cwd=repo)
    remote = tmp_path / "remote.git"
    _git("init", "--bare", str(remote), cwd=tmp_path)
    _git("remote", "add", "origin", str(remote), cwd=repo)
    _git("push", "-u", "origin", "main", cwd=repo)
    return repo


def add_worktree(repo, branch, wt_name):
    wt = repo / ".worktrees" / wt_name
    _git("worktree", "add", "-b", branch, str(wt), cwd=repo)
    _git("push", "-u", "origin", branch, cwd=wt)
    return wt


def make_board_db(tmp_path, cards):
    db = tmp_path / "kanban.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE tasks (id TEXT, status TEXT, body TEXT, branch_name TEXT)"
    )
    for card in cards:
        conn.execute(
            "INSERT INTO tasks (id, status, body, branch_name) VALUES (?, ?, ?, ?)",
            (card["id"], card["status"], card.get("body", ""), card.get("branch_name")),
        )
    conn.commit()
    conn.close()
    return db


def test_wanted_by_does_not_match_substring():
    module = load_module()
    cards = [
        {"id": "t_2", "status": "ready", "body": "names fix/ab only", "branch_name": "fix/ab"},
    ]
    assert module.wanted_by("fix/a", "t_1", cards) == []


def test_wanted_by_matches_whole_token():
    module = load_module()
    cards = [
        {"id": "t_2", "status": "ready", "body": "merge `fix/a` first", "branch_name": "other"},
    ]
    assert module.wanted_by("fix/a", "t_1", cards) == ["t_2"]


def test_inspect_worktree_counts_ignored(tmp_path):
    module = load_module()
    repo = make_repo(tmp_path)
    wt = add_worktree(repo, "fix/a", "t_1")
    (wt / "tmp" / "evals").mkdir(parents=True)
    (wt / "tmp" / "evals" / "x").write_text("receipt")
    cards = [{"id": "t_1", "status": "done", "body": "", "branch_name": "fix/a"}]
    entry = {"id": "t_1", "path": str(wt), "branch": "fix/a"}
    row = module.inspect_worktree(entry, cards)
    assert row["ignored"] == 1
    assert row["dirty"] is False
    assert row["unpushed"] == 0
    assert row["verdict"] == "removable"


def test_remove_worktree_removes(tmp_path):
    module = load_module()
    repo = make_repo(tmp_path)
    wt = add_worktree(repo, "fix/a", "t_1")
    module.remove_worktree(str(repo), str(wt))
    assert not wt.exists()


def test_remove_worktree_locked_raises(tmp_path):
    module = load_module()
    repo = make_repo(tmp_path)
    wt = add_worktree(repo, "fix/a", "t_1")
    _git("worktree", "lock", str(wt), cwd=repo)
    with pytest.raises(module.GitError):
        module.remove_worktree(str(repo), str(wt))
    assert wt.exists()


def test_apply_keeps_worktree_with_ignored_files(tmp_path, capsys):
    module = load_module()
    repo = make_repo(tmp_path)
    wt = add_worktree(repo, "fix/a", "t_1")
    (wt / "tmp" / "evals").mkdir(parents=True)
    (wt / "tmp" / "evals" / "x").write_text("receipt")
    db = make_board_db(
        tmp_path, [{"id": "t_1", "status": "done", "body": "", "branch_name": "fix/a"}]
    )
    code = module.main(["--db", str(db), "--repo", str(repo), "--apply"])
    captured = capsys.readouterr()
    assert code == 0
    assert wt.exists()
    assert "ignored files" in captured.out


def test_apply_with_include_ignored_removes_worktree(tmp_path, capsys):
    module = load_module()
    repo = make_repo(tmp_path)
    wt = add_worktree(repo, "fix/a", "t_1")
    (wt / "tmp" / "evals").mkdir(parents=True)
    (wt / "tmp" / "evals" / "x").write_text("receipt")
    db = make_board_db(
        tmp_path, [{"id": "t_1", "status": "done", "body": "", "branch_name": "fix/a"}]
    )
    code = module.main(
        ["--db", str(db), "--repo", str(repo), "--apply", "--include-ignored"]
    )
    assert code == 0
    assert not wt.exists()


def test_apply_remove_failure_exits_nonzero(tmp_path, capsys):
    module = load_module()
    repo = make_repo(tmp_path)
    wt = add_worktree(repo, "fix/a", "t_1")
    db = make_board_db(
        tmp_path, [{"id": "t_1", "status": "done", "body": "", "branch_name": "fix/a"}]
    )
    _git("worktree", "lock", str(wt), cwd=repo)
    code = module.main(
        ["--db", str(db), "--repo", str(repo), "--apply", "--include-ignored"]
    )
    captured = capsys.readouterr()
    assert code == 1
    assert "keep:" in captured.out
    assert wt.exists()


def test_report_only_does_not_remove(tmp_path, capsys):
    module = load_module()
    repo = make_repo(tmp_path)
    wt = add_worktree(repo, "fix/a", "t_1")
    db = make_board_db(
        tmp_path, [{"id": "t_1", "status": "done", "body": "", "branch_name": "fix/a"}]
    )
    code = module.main(["--db", str(db), "--repo", str(repo)])
    captured = capsys.readouterr()
    assert code == 0
    assert wt.exists()
    assert "removable" in captured.out
