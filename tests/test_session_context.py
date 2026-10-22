"""Context rotation: tools/hooks/session_context.py, its wiring, the handoff template and the two commands."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "tools/hooks/session_context.py"
SECTIONS = ["Where we are", "In progress", "User decisions not in the code", "Waiting for the user", "Next step",
            "Rules broken", "Open PRs and issues for this task"]


def git(repo, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=repo, check=True,
                   capture_output=True)


def git_out(repo, *args):
    r = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True, encoding="utf-8")
    return r.stdout.strip()


def leave_origin_main_ahead(repo, path, title):
    """Point refs/remotes/origin/main at a new commit, and leave the branch on the previous HEAD."""
    base = git_out(repo, "rev-parse", "HEAD")
    dest = repo / path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("x\n", encoding="utf-8")
    git(repo, "add", "--", path)
    git(repo, "commit", "-q", "-m", title)
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(repo, "reset", "-q", "--hard", base)


def handoff(branch, extra=""):
    return f"# Handoff — 2026-10-14\n\nBranch: `{branch}` · Commit: `abc1234` · Job: `-`\n\n## Next step\n\nDo X.\n{extra}"


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "task/a")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/HANDOFF.md").write_text(handoff("task/a"), encoding="utf-8")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "Handoff: do X")
    return tmp_path


def run(mode, payload, repo):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(repo),
           "PATH": os.path.dirname(shutil.which("git"))}          # no gh: the test stays offline
    r = subprocess.run([sys.executable, str(HOOK), mode], input=json.dumps(payload), capture_output=True,
                       text=True, encoding="utf-8", env=env)
    assert r.returncode == 0, r.stderr
    return r.stdout


def start(repo, source):
    raw = run("start", {"source": source}, repo)
    assert raw.isascii()                                          # survives any console code page
    out = json.loads(raw)["hookSpecificOutput"]
    assert out["hookEventName"] == "SessionStart"
    return out["additionalContext"]


def test_hooks_are_wired():
    hooks = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))["hooks"]
    entry = hooks["SessionStart"][0]
    assert all(re.search(entry["matcher"], s) for s in ("startup", "clear", "compact"))
    assert not re.search(entry["matcher"], "resume")              # a resumed session has its own context
    assert entry["hooks"][0]["command"].endswith('session_context.py" start')
    pre = hooks["PreCompact"][0]
    assert all(re.search(pre["matcher"], s) for s in ("manual", "auto"))
    assert pre["hooks"][0]["command"].endswith('session_context.py" precompact')


def test_current_handoff(repo):
    ctx = start(repo, "clear")
    assert "Branch: task/a" in ctx
    assert "Handoff: current" in ctx and "--- docs/HANDOFF.md ---" in ctx and "Do X." in ctx
    assert "Handoff: do X" in ctx                                 # the last commits
    assert "(gh not found)" in ctx and "продолжай" in ctx


def test_stale_foreign_and_old_handoffs_are_flagged(repo):
    (repo / "x.txt").write_text("x", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "work")
    ctx = start(repo, "startup")
    assert "1 commit(s) after the last commit" in ctx and "?? " not in ctx
    git(repo, "switch", "-q", "-c", "task/b")
    assert "belongs to branch `task/a`" in start(repo, "startup")
    (repo / "docs/HANDOFF.md").write_text("# Handoff\n\nold format\n", encoding="utf-8")
    ctx = start(repo, "startup")
    assert "no `Branch:` line" in ctx and "uncommitted changes" in ctx and "?? " not in ctx


def test_compact_with_a_stale_handoff_asks_for_a_checkpoint(repo):
    assert "handover procedure" not in start(repo, "compact")
    (repo / "x.txt").write_text("x", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "work")
    assert "run the /handover procedure" in start(repo, "compact")
    assert "handover procedure" not in start(repo, "startup")


def test_long_handoff_is_cut_under_the_hook_cap(repo):
    (repo / "docs/HANDOFF.md").write_text(handoff("task/a", "line of text\n" * 2000), encoding="utf-8")
    ctx = start(repo, "startup")
    assert len(ctx) < 10_000 and "cut at" in ctx


def test_precompact(repo):
    log = repo / ".git/agr-compactions.log"
    assert run("precompact", {"trigger": "manual", "custom_instructions": None}, repo) == ""   # current: passes
    (repo / "x.txt").write_text("x", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "work")
    out = json.loads(run("precompact", {"trigger": "manual", "custom_instructions": None}, repo))
    assert out["decision"] == "block" and "/handover" in out["reason"]
    assert run("precompact", {"trigger": "manual", "custom_instructions": "force"}, repo) == ""
    assert run("precompact", {"trigger": "auto", "custom_instructions": None}, repo) == ""   # never blocks auto
    lines = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
    assert [x["trigger"] for x in lines] == ["manual", "manual", "manual", "auto"]
    assert lines[-1]["handoff_warnings"]


def test_unreadable_input_does_not_break_the_session(repo):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(repo), "PATH": os.path.dirname(shutil.which("git"))}
    r = subprocess.run([sys.executable, str(HOOK), "start"], input="not json", capture_output=True, text=True, env=env)
    assert r.returncode == 0 and "Session context (startup" in json.loads(r.stdout)["hookSpecificOutput"][
        "additionalContext"]


def test_template_has_every_section_and_a_parsable_branch_line():
    text = (ROOT / "docs/HANDOFF.template.md").read_text(encoding="utf-8")
    assert re.search(r"^Branch:\s*`[^`]+`.*Commit:\s*`", text, re.M)
    assert [s for s in SECTIONS if f"\n## {s}\n" not in text] == []


@pytest.mark.parametrize("name", ["handover", "takeover"])
def test_commands(name):
    text = (ROOT / f".claude/commands/{name}.md").read_text(encoding="utf-8")
    meta = yaml.safe_load(text.split("---\n")[1])
    assert meta["disable-model-invocation"] is True and meta["description"]
    assert "!`py -3 tools/hooks/session_context.py report`" in text
    if name == "handover":
        assert "HANDOFF.template.md" in text and "Чекпоинт готов, можно /clear" in text
    else:
        assert "Wait for the user's «да»" in text


# Review 1 of #107: each test failed before the fix.

@pytest.mark.parametrize("instructions, blocked", [
    ("force", False), ("Force keep the API notes", False),
    ("reinforce the API constraints", True), ("do not force; preserve recent decisions", True)])
def test_force_is_the_first_word_only(repo, instructions, blocked):
    (repo / "x.txt").write_text("x", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "work")
    out = run("precompact", {"trigger": "manual", "custom_instructions": instructions}, repo)
    assert (out != "") is blocked


def test_failed_git_is_not_reported_clean(repo, tmp_path):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(repo), "PATH": str(tmp_path)}          # no git at all
    r = subprocess.run([sys.executable, str(HOOK), "start"], input="{}", capture_output=True, text=True, env=env)
    ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "FAILED" in ctx and "clean" not in ctx and "Handoff: current" not in ctx and "not verified" in ctx
    r = subprocess.run([sys.executable, str(HOOK), "precompact"], input=json.dumps({"trigger": "manual"}),
                       capture_output=True, text=True, env=env)
    assert json.loads(r.stdout)["decision"] == "block"


def test_work_after_the_handover_makes_it_stale(repo):
    (repo / "docs/task.py").write_text("x = 1\n", encoding="utf-8")
    assert "1 uncommitted path(s)" in start(repo, "compact") and "run the /handover procedure" in start(repo, "compact")
    assert json.loads(run("precompact", {"trigger": "manual"}, repo))["decision"] == "block"


def test_a_huge_commit_subject_does_not_break_the_cap(repo):
    git(repo, "commit", "--allow-empty", "-q", "-m", "generated summary " + "x" * 10_500)
    ctx = start(repo, "startup")
    assert len(ctx) < 10_000 and "--- docs/HANDOFF.md ---" in ctx and "Do X." in ctx


def test_an_unreadable_handoff_still_gives_context(repo):
    (repo / "docs/HANDOFF.md").write_bytes(b"# Handoff\n\nBranch: `task/a`\n\xff\xfe broken\n")
    ctx = start(repo, "startup")
    assert "broken" in ctx and "uncommitted changes" in ctx
    assert run("precompact", {"trigger": "auto"}, repo) == ""


def test_failed_git_status_is_a_warning(repo):                       # review 2 of #107
    (repo / ".git/index").write_bytes(b"broken index")
    ctx = start(repo, "startup")
    assert "git status failed" in ctx and "Handoff: current" not in ctx
    assert json.loads(run("precompact", {"trigger": "manual"}, repo))["decision"] == "block"


# #529: branch freshness. Warn cases fail until branch_freshness() is wired into context().

def test_detached_head_is_a_freshness_warning(repo):
    git(repo, "checkout", "-q", "--detach", "HEAD")
    short = git_out(repo, "rev-parse", "--short", "HEAD")
    ctx = start(repo, "startup")
    assert "Branch freshness:" in ctx
    assert "detached" in ctx and short in ctx and "no production work" in ctx
    report = run("report", {}, repo)
    assert "Branch freshness:" in report and "detached" in report and short in report


@pytest.mark.parametrize("path,title", [
    ("src/x.py", "add src helper"),
    ("tools/h.py", "add a tool helper"),
    ("standards/rule.json", "add a standard"),
    ("docs/decisions.md", "record a decision"),
    ("docs/agents/CAPABILITIES.md", "note a capability"),
    ("docs/domain/node.md", "add a domain rule"),
])
def test_relevant_main_merges_are_listed(repo, path, title):
    leave_origin_main_ahead(repo, path, title)
    ctx = start(repo, "startup")
    assert "Branch freshness:" in ctx and "1 relevant merge" in ctx and title in ctx
    report = run("report", {}, repo)
    assert "1 relevant merge" in report and title in report


def test_irrelevant_commits_do_not_add_to_the_relevant_count(repo):
    base = git_out(repo, "rev-parse", "HEAD")
    (repo / "docs/cases.md").write_text("c\n", encoding="utf-8")
    git(repo, "add", "--", "docs/cases.md")
    git(repo, "commit", "-q", "-m", "docs only case")
    (repo / "src").mkdir()
    (repo / "src/x.py").write_text("x\n", encoding="utf-8")
    git(repo, "add", "--", "src/x.py")
    git(repo, "commit", "-q", "-m", "add src helper")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(repo, "reset", "-q", "--hard", base)
    ctx = start(repo, "startup")
    assert "1 relevant merge" in ctx and "add src helper" in ctx
    assert "2 relevant" not in ctx and "docs only case" not in ctx


@pytest.mark.parametrize("path,title", [
    ("docs/cases.md", "docs only case"),
    ("jobs/NOTE.md", "job only note"),
])
def test_docs_only_or_job_only_main_merges_do_not_warn(repo, path, title):
    leave_origin_main_ahead(repo, path, title)
    ctx = start(repo, "startup")
    assert "Branch freshness:" not in ctx and title not in ctx
    assert "relevant merge" not in run("report", {}, repo)


def test_branch_even_with_origin_main_has_no_freshness_warning(repo):
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    ctx = start(repo, "startup")
    assert "Branch freshness:" not in ctx and "up to date" not in ctx.lower()
    assert "Branch freshness:" not in run("report", {}, repo)


def test_missing_origin_main_does_not_claim_the_branch_current(repo):
    ctx = start(repo, "startup")
    assert "up to date" not in ctx.lower() and "Branch freshness: current" not in ctx


def test_git_unavailable_does_not_call_branch_freshness_current(repo, tmp_path):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(repo), "PATH": str(tmp_path)}
    r = subprocess.run([sys.executable, str(HOOK), "report"], capture_output=True, text=True,
                       encoding="utf-8", env=env)
    assert r.returncode == 0, r.stderr
    assert "branch freshness is not verified" in r.stdout
    assert "up to date" not in r.stdout.lower() and "clean" not in r.stdout


def test_takeover_lists_freshness_and_proposes_merge():
    text = (ROOT / ".claude/commands/takeover.md").read_text(encoding="utf-8")
    assert "HEAD detached" in text
    assert "relevant merge" in text
    assert "explicit skip" in text
    assert "does not merge" in text


def test_loop_merges_main_before_the_first_production_step():
    loop = (ROOT / "docs/agents/WORKFLOW.md").read_text(encoding="utf-8").split("## Before requesting review")[0]
    assert "git fetch origin" in loop
    assert "git merge --no-edit origin/main" in loop
    assert "never rebase" in loop
    assert "detached HEAD" in loop
    for path in ("src/", "tools/", "standards/", "docs/domain/", "docs/decisions.md",
                 "docs/procedure/", "docs/agents/CAPABILITIES.md"):
        assert path in loop
