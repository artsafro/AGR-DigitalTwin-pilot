"""Report kanban card worktrees and remove only the ones that are safe.

new-case: kanban worktree hygiene tool

The default run is a report and exits 0. ``--apply`` removes a worktree only
when classify() returns ``removable``, and the git command never includes
``--force``. A ``removable`` worktree with gitignored content is kept with the
reason ``ignored files`` unless ``--include-ignored`` is given. Any failed
removal makes the exit code 1. A missing board database exits nonzero and
removes nothing.
"""
import argparse
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path


DEFAULT_BOARD = "agr-pilot"
DEFAULT_REPO = "C:/Users/artsafro/agr-pilot/AGR-DigitalTwin"
FINISHED = ("done", "archived")
_BOUNDARY = r"[\s`'\"(),:;]"


class GitError(RuntimeError):
    """A git call failed in a way that must keep the worktree."""


def classify(status, dirty, unpushed):
    if status is None:
        return "keep: unknown card"
    if status not in FINISHED:
        return f"keep: card {status}"
    if dirty:
        return "keep: dirty"
    if unpushed == "no-upstream":
        return "keep: no-upstream"
    if isinstance(unpushed, int) and not isinstance(unpushed, bool) and unpushed > 0:
        return f"keep: unpushed {unpushed}"
    return "removable"


def wanted_by(branch, own_id, cards):
    if not branch:
        return []
    pattern = re.compile(
        r"(?:^|" + _BOUNDARY + r")" + re.escape(branch) + r"(?:$|" + _BOUNDARY + r")"
    )
    found = []
    for card in cards:
        card_id = card.get("id")
        if card_id == own_id:
            continue
        if card.get("status") in FINISHED:
            continue
        body = card.get("body") or ""
        if isinstance(body, bytes):
            body = body.decode("utf-8", "replace")
        else:
            body = str(body)
        if pattern.search(body):
            found.append(card_id)
    return found


def apply_argv(repo, wt):
    return ["git", "-C", repo, "worktree", "remove", wt]


def default_db(board):
    return Path(f"C:/Users/artsafro/.hermes/kanban/boards/{board}/kanban.db")


def board_uri(path):
    return f"file:{Path(path).as_posix()}?mode=ro"


def open_board(path):
    db_path = Path(path)
    if not db_path.is_file():
        raise FileNotFoundError(f"missing db: {db_path}")
    return sqlite3.connect(board_uri(db_path), uri=True)


def load_cards(conn):
    rows = conn.execute(
        "SELECT id, status, body, branch_name FROM tasks"
    ).fetchall()
    return [
        {"id": row[0], "status": row[1], "body": row[2], "branch_name": row[3]}
        for row in rows
    ]


def normalise_path(path):
    return str(path).replace("\\", "/").rstrip("/")


def card_id_for_worktree(repo, wt_path):
    repo_n = normalise_path(repo)
    wt_n = normalise_path(wt_path)
    prefix = repo_n + "/.worktrees/"
    if os.name == "nt":
        if not wt_n.casefold().startswith(prefix.casefold()):
            return None
    elif not wt_n.startswith(prefix):
        return None
    name = wt_n[len(prefix):].split("/", 1)[0]
    folded = name.casefold() if os.name == "nt" else name
    if not folded.startswith("t_"):
        return None
    return name


def parse_worktree_porcelain(text):
    entries = []
    current = None
    for line in text.splitlines():
        if line.startswith("worktree "):
            if current is not None:
                entries.append(current)
            current = {"path": line[len("worktree "):], "branch": None}
        elif current is None:
            continue
        elif line.startswith("branch "):
            ref = line[len("branch "):]
            heads = "refs/heads/"
            current["branch"] = ref[len(heads):] if ref.startswith(heads) else ref
        elif line == "detached":
            current["branch"] = None
    if current is not None:
        entries.append(current)
    return entries


def _one_line(text):
    return " ".join((text or "").split())


def run_git(argv):
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _git_failure(proc, fallback):
    detail = _one_line(proc.stderr) or _one_line(proc.stdout) or fallback
    raise GitError(detail)


def list_card_worktrees(repo):
    proc = run_git(["git", "-C", str(repo), "worktree", "list", "--porcelain"])
    if proc.returncode != 0:
        _git_failure(proc, "git worktree list failed")
    selected = []
    for entry in parse_worktree_porcelain(proc.stdout):
        card_id = card_id_for_worktree(repo, entry["path"])
        if card_id is None:
            continue
        selected.append({
            "id": card_id,
            "path": entry["path"],
            "branch": entry["branch"],
        })
    return selected


def worktree_dirty(wt):
    proc = run_git(["git", "-C", wt, "status", "--porcelain"])
    if proc.returncode != 0:
        _git_failure(proc, "git status failed")
    return bool(proc.stdout.strip())


def worktree_unpushed(wt):
    proc = run_git(["git", "-C", wt, "rev-list", "@{u}..HEAD", "--count"])
    if proc.returncode != 0:
        return "no-upstream"
    text = proc.stdout.strip()
    try:
        return int(text)
    except ValueError as exc:
        raise GitError(f"unpushed count: {text}") from exc


def worktree_ignored_count(wt):
    proc = run_git(["git", "-C", wt, "status", "--porcelain", "--ignored"])
    if proc.returncode != 0:
        _git_failure(proc, "git status --ignored failed")
    return sum(1 for line in proc.stdout.splitlines() if line.startswith("!!"))


def inspect_worktree(entry, cards):
    by_id = {card.get("id"): card for card in cards}
    card = by_id.get(entry["id"])
    status = None if card is None else card.get("status")
    branch = entry.get("branch")
    try:
        dirty = worktree_dirty(entry["path"])
        unpushed = worktree_unpushed(entry["path"])
        ignored = worktree_ignored_count(entry["path"])
    except GitError as exc:
        return {
            "id": entry["id"],
            "status": status,
            "branch": branch,
            "dirty": None,
            "unpushed": None,
            "ignored": None,
            "wanted_by": [],
            "verdict": f"keep: {exc}",
        }
    return {
        "id": entry["id"],
        "status": status,
        "branch": branch,
        "dirty": dirty,
        "unpushed": unpushed,
        "ignored": ignored,
        "wanted_by": wanted_by(branch, entry["id"], cards),
        "verdict": classify(status, dirty, unpushed),
    }


def remove_worktree(repo, wt):
    argv = apply_argv(str(repo), wt)
    if any(arg == "--force" or arg.startswith("--force=") for arg in argv):
        raise GitError("refusing --force")
    proc = run_git(argv)
    if proc.returncode != 0:
        _git_failure(proc, "git worktree remove failed")


def format_row(row):
    if row["dirty"] is True:
        cleanliness = "dirty"
    elif row["dirty"] is False:
        cleanliness = "clean"
    else:
        cleanliness = "unknown"
    status = row["status"] if row["status"] is not None else "none"
    branch = row["branch"] or "-"
    unpushed = "-" if row["unpushed"] is None else row["unpushed"]
    ignored = "-" if row.get("ignored") is None else row["ignored"]
    text = (
        f"{row['id']} status={status} branch={branch} "
        f"{cleanliness} unpushed={unpushed} ignored={ignored} {row['verdict']}"
    )
    if row["wanted_by"]:
        text += " WANTED-BY " + " ".join(row["wanted_by"])
    return text


def format_totals(rows):
    total = len(rows)
    removable = sum(1 for row in rows if row["verdict"] == "removable")
    reasons = {}
    for row in rows:
        verdict = row["verdict"]
        if verdict == "removable":
            continue
        reason = verdict[len("keep: "):] if verdict.startswith("keep: ") else verdict
        reasons[reason] = reasons.get(reason, 0) + 1
    if reasons:
        breakdown = ", ".join(
            f"{reason}={reasons[reason]}" for reason in sorted(reasons)
        )
    else:
        breakdown = "none"
    return f"total={total} / removable={removable} / kept by reason: {breakdown}"


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", default=DEFAULT_BOARD)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--db")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--include-ignored", action="store_true")
    return parser.parse_args(argv)


def _kept_row(entry, reason):
    return {
        "id": entry.get("id"),
        "status": None,
        "branch": entry.get("branch"),
        "dirty": None,
        "unpushed": None,
        "ignored": None,
        "wanted_by": [],
        "verdict": f"keep: {reason}",
    }


def main(argv=None):
    args = parse_args(argv)
    db_path = Path(args.db) if args.db else default_db(args.board)
    if not db_path.is_file():
        print(f"missing db: {db_path}", file=sys.stderr)
        return 1
    try:
        conn = open_board(db_path)
        try:
            cards = load_cards(conn)
        finally:
            conn.close()
    except (sqlite3.Error, OSError, FileNotFoundError) as exc:
        print(f"db error: {exc}", file=sys.stderr)
        return 1
    try:
        entries = list_card_worktrees(args.repo)
    except GitError as exc:
        print(f"git error: {exc}", file=sys.stderr)
        return 1

    rows = []
    failed = False
    for entry in entries:
        try:
            row = inspect_worktree(entry, cards)
        except (OSError, sqlite3.Error, GitError, ValueError) as exc:
            row = _kept_row(entry, exc)
        if args.apply and row["verdict"] == "removable":
            if row.get("ignored") and not args.include_ignored:
                row["verdict"] = "keep: ignored files"
            else:
                try:
                    remove_worktree(args.repo, entry["path"])
                except GitError as exc:
                    row = _kept_row(entry, exc)
                    row["status"] = None
                    failed = True
        rows.append(row)
        print(format_row(row))
    print(format_totals(rows))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
