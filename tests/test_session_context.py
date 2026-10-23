"""Context rotation: tools/hooks/session_context.py, its wiring, the handoff template and the two commands."""
import importlib.util
import json
import os
import random
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
    assert "before merging" in ctx
    report = run("report", {}, repo)
    assert "Branch freshness:" in report and "detached" in report and short in report
    assert "before merging" in report


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


# #529 round 2: count first-parent integrations, and do not define production by those paths.

RELEVANT_SPECS = ("src/", "tools/", "standards/", "docs/domain/", "docs/decisions.md",
                  "docs/procedure/", "docs/agents/CAPABILITIES.md")
PROBE_RELEVANT = (
    "src/synthetic.py", "src/pkg/synthetic.py", "tools/synthetic.py", "standards/synthetic.json",
    "docs/domain/synthetic.md", "docs/decisions.md", "docs/procedure/synthetic.md",
    "docs/agents/CAPABILITIES.md",
)
PROBE_IRRELEVANT = (
    "docs/cases.md", "docs/notes/synthetic.md", "jobs/SYNTH/NOTE.md", "jobs/SYNTH/outputs/mesh.txt",
    "README.md", "docs/decisions.md.bak", "src-extra/synthetic.py", "docs/domain-notes/synthetic.md",
    "docs/procedure-notes/synthetic.md", "toolshed/synthetic.py",
)


def _path_counts_as_relevant(path):
    for spec in RELEVANT_SPECS:
        if spec.endswith("/"):
            if path.startswith(spec):
                return True
        elif path == spec:
            return True
    return False


def commit_paths(repo, paths, title):
    for path in paths:
        dest = repo / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(title + "\n", encoding="utf-8")
        git(repo, "add", "--", path)
    git(repo, "commit", "-q", "-m", title)


def merge_side(repo, branch, paths, side_title, merge_title, resolution_paths=()):
    """Real --no-ff merge. resolution_paths are written only on the merge commit."""
    git(repo, "switch", "-q", "-c", branch)
    commit_paths(repo, paths, side_title)
    git(repo, "switch", "-q", "-")
    if resolution_paths:
        git(repo, "merge", "--no-ff", "--no-commit", "--no-edit", branch)
        for path in resolution_paths:
            dest = repo / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(merge_title + "\n", encoding="utf-8")
            git(repo, "add", "--", path)
        git(repo, "commit", "-q", "-m", merge_title)
    else:
        git(repo, "merge", "--no-ff", "--no-edit", "-m", merge_title, branch)
    git(repo, "branch", "-q", "-D", branch)


def point_origin_main_and_return(repo, base):
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(repo, "reset", "-q", "--hard", base)


def test_no_ff_src_merge_counts_once_with_the_merge_title(repo):
    """(a) two src commits on a side branch are one relevant merge, titled by the merge."""
    base = git_out(repo, "rev-parse", "HEAD")
    git(repo, "switch", "-q", "-c", "side/src")
    commit_paths(repo, ["src/one.py"], "src commit one")
    commit_paths(repo, ["src/two.py"], "src commit two")
    git(repo, "switch", "-q", "-")
    git(repo, "merge", "--no-ff", "--no-edit", "-m", "merge two src commits", "side/src")
    git(repo, "branch", "-q", "-D", "side/src")
    point_origin_main_and_return(repo, base)
    ctx = start(repo, "startup")
    assert "behind origin/main by 1 relevant merge" in ctx
    assert "merge two src commits" in ctx
    assert "src commit one" not in ctx and "src commit two" not in ctx
    assert "behind origin/main by 2" not in ctx
    report = run("report", {}, repo)
    assert "behind origin/main by 1 relevant merge" in report and "merge two src commits" in report


def test_mixed_real_merges_count_only_the_src_integration(repo):
    """(b) one src merge plus a docs-only merge and a jobs-only merge counts as 1."""
    base = git_out(repo, "rev-parse", "HEAD")
    git(repo, "switch", "-q", "-c", "side/src")
    commit_paths(repo, ["src/a.py"], "src side one")
    commit_paths(repo, ["src/b.py"], "src side two")
    git(repo, "switch", "-q", "-")
    git(repo, "merge", "--no-ff", "--no-edit", "-m", "merge src feature", "side/src")
    git(repo, "branch", "-q", "-D", "side/src")
    merge_side(repo, "side/docs", ["docs/cases.md"], "docs side commit", "merge docs only")
    merge_side(repo, "side/jobs", ["jobs/SYNTH/NOTE.md"], "jobs side commit", "merge jobs only")
    point_origin_main_and_return(repo, base)
    ctx = start(repo, "startup")
    assert "behind origin/main by 1 relevant merge" in ctx
    assert "merge src feature" in ctx
    assert "merge docs only" not in ctx and "merge jobs only" not in ctx
    assert "src side one" not in ctx and "src side two" not in ctx
    assert "docs side commit" not in ctx and "jobs side commit" not in ctx
    assert "behind origin/main by 2" not in ctx and "behind origin/main by 3" not in ctx


def test_merge_resolution_that_touches_src_counts(repo):
    """(c) docs-only side commits, but the merge resolution itself touches src/."""
    base = git_out(repo, "rev-parse", "HEAD")
    merge_side(repo, "side/docs", ["docs/cases.md"], "docs only side",
               "merge docs side with src resolution", resolution_paths=["src/from_resolution.py"])
    point_origin_main_and_return(repo, base)
    ctx = start(repo, "startup")
    assert "behind origin/main by 1 relevant merge" in ctx
    assert "merge docs side with src resolution" in ctx
    assert "docs only side" not in ctx


def test_up_to_date_real_merge_has_no_freshness_warning(repo):
    """(d) HEAD is the merge that origin/main names."""
    merge_side(repo, "side/src", ["src/one.py"], "src commit one", "merge src already contained")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    ctx = start(repo, "startup")
    assert "Branch freshness:" not in ctx and "relevant merge" not in ctx
    assert "Branch freshness:" not in run("report", {}, repo)


def test_origin_main_root_commit_is_not_verified(repo):
    """(f) a commit with no parent is unsupported: warn, do not report a count."""
    git(repo, "checkout", "-q", "--orphan", "synthetic-main")
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src/root.py").write_text("synthetic root\n", encoding="utf-8")
    git(repo, "add", "--", "src/root.py")
    git(repo, "commit", "-q", "-m", "root on main")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(repo, "switch", "-q", "task/a")
    ctx = start(repo, "startup")
    assert "branch freshness is not verified" in ctx
    assert "relevant merge" not in ctx and "root on main" not in ctx


def test_production_step_includes_dcc_job_outputs_and_branch_before_merge():
    """Production is a DCC/code step, not the relevance-path list. Detached: branch, then merge."""
    texts = [
        (ROOT / "docs/agents/WORKFLOW.md").read_text(encoding="utf-8").split("## Before requesting review")[0],
        (ROOT / ".claude/commands/takeover.md").read_text(encoding="utf-8"),
    ]
    for text in texts:
        assert "jobs/<id>/outputs/" in text
        window = text[max(0, text.index("jobs/<id>/outputs/") - 500): text.index("jobs/<id>/outputs/") + 40]
        folded = window.lower()
        assert "dcc" in folded and "build" in folded and "export" in folded
        assert "git switch -c" in text
        assert text.index("git switch -c") < text.index("git merge --no-edit origin/main")
        assert "detached" in text.lower()


def _load_session_context():
    spec = importlib.util.spec_from_file_location("session_context_under_test", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _record(subject, parents, paths, n=1):
    sha = f"{n:040x}"
    parent_field = " ".join(parents)
    body = "\n".join(paths)
    extra = f"\n{body}\n" if paths else "\n"
    return f"\x1e{sha}\t{sha[:7]}\t{subject}\t{parent_field}{extra}"


def test_classifier_fail_closed_on_empty_partial_and_unsupported():
    """Empty, partial and unsupported integration records are not a clean 'nothing relevant'."""
    mod = _load_session_context()
    classify = mod.classify_integration_log
    parent = f"{2:040x}"
    with pytest.raises(mod.FreshnessIncomplete):
        classify("")
    with pytest.raises(mod.FreshnessIncomplete):
        classify("\x1e")
    with pytest.raises(mod.FreshnessIncomplete):
        classify("not a record")
    with pytest.raises(mod.FreshnessIncomplete):
        classify(f"\x1e{'abcd'}\t{'abcd'}\tmerge synthetic\t{parent}\n")
    with pytest.raises(mod.FreshnessIncomplete):
        classify(f"\x1e{f'{1:040x}'}\t{f'{1:07x}'}\t\t{parent}\n")
    with pytest.raises(mod.FreshnessIncomplete):
        classify(_record("root synthetic", [], ["src/synthetic.py"]))
    with pytest.raises(mod.FreshnessIncomplete):
        classify(_record("partial parent", ["zzzz"], ["src/synthetic.py"]))
    with pytest.raises(mod.FreshnessIncomplete):
        classify(_record("escape path", [parent], ["../src/synthetic.py"]))
    with pytest.raises(mod.FreshnessIncomplete):
        classify(_record("dot path", [parent], ["."]))
    assert classify(_record("empty diff", [parent], [])) == []
    assert classify(_record("docs only", [parent], ["docs/cases.md", "jobs/SYNTH/NOTE.md"])) == []
    src = classify(_record("merge synthetic", [parent, f"{3:040x}"], ["docs/cases.md", "src/synthetic.py"]))
    assert src == [f"{f'{1:040x}'[:7]} merge synthetic"]


def test_docs_or_job_only_merges_never_warn_probe(repo):
    """Synthetic probe: reported relevant merges equal merges whose first-parent diff is relevant.

    Seed 529, N=12 no-ff merges. Path sets are a shuffled mix of docs-only, jobs-only, relevant,
    near-miss traps and mixed sides, sometimes plus a path that exists only on the merge commit.
    """
    rng = random.Random(529)
    n = 12
    kinds = ["docs", "jobs", "relevant", "mixed", "trap"]
    deck = kinds * 2 + [rng.choice(kinds) for _ in range(n - 10)]
    rng.shuffle(deck)
    base = git_out(repo, "rev-parse", "HEAD")
    rows = []
    for i, kind in enumerate(deck):
        if kind == "docs":
            paths = [rng.choice(("docs/cases.md", "docs/notes/synthetic.md"))]
        elif kind == "jobs":
            paths = [rng.choice(("jobs/SYNTH/NOTE.md", "jobs/SYNTH/outputs/mesh.txt"))]
        elif kind == "relevant":
            paths = [rng.choice(PROBE_RELEVANT)]
        elif kind == "trap":
            paths = [rng.choice(("docs/decisions.md.bak", "src-extra/synthetic.py",
                                 "docs/domain-notes/synthetic.md", "docs/procedure-notes/synthetic.md",
                                 "toolshed/synthetic.py"))]
        else:
            paths = [rng.choice(PROBE_RELEVANT), rng.choice(PROBE_IRRELEVANT)]
        resolution = [rng.choice(PROBE_RELEVANT + PROBE_IRRELEVANT)] if rng.random() < 0.35 else []
        merge_title = f"synthetic-merge-{i:02d}"
        side_title = f"synthetic-side-{i:02d}"
        merge_side(repo, f"syn-side-{i}", list(dict.fromkeys(paths)), side_title, merge_title,
                   resolution_paths=resolution)
        touched = list(dict.fromkeys([*paths, *resolution]))
        rows.append((merge_title, side_title, any(_path_counts_as_relevant(p) for p in touched)))
    point_origin_main_and_return(repo, base)
    ctx = start(repo, "startup")
    expected = sum(1 for _title, _side, relevant in rows if relevant)
    assert expected not in (0, n)                                  # the mix actually contains both kinds
    noun = "merge" if expected == 1 else "merges"
    assert f"behind origin/main by {expected} relevant {noun}" in ctx
    for title, side, relevant in rows:
        assert (title in ctx) is relevant
        assert side not in ctx
    assert "Branch freshness:" in ctx


def _rename_merge(repo, old, new, merge_title, extra_side=2):
    """Real --no-ff merge whose side branch renames old -> new plus extra docs commits."""
    commit_paths(repo, [old], "add file to rename")
    base = git_out(repo, "rev-parse", "HEAD")
    git(repo, "switch", "-q", "-c", "side/rename")
    for i in range(extra_side):
        commit_paths(repo, [f"docs/side_{i}.md"], f"rename side commit {i}")
    (repo / new).parent.mkdir(parents=True, exist_ok=True)
    git(repo, "mv", old, new)
    git(repo, "commit", "-q", "-m", "rename commit")
    git(repo, "switch", "-q", "-")
    git(repo, "merge", "--no-ff", "--no-edit", "-m", merge_title, "side/rename")
    git(repo, "branch", "-q", "-D", "side/rename")
    point_origin_main_and_return(repo, base)


def test_outward_rename_src_to_docs_counts_once_with_merge_title(repo):
    """Rename src/check.py -> docs/check.py (+2 side commits) = 1 relevant merge."""
    _rename_merge(repo, "src/check.py", "docs/check.py", "merge outward rename")
    ctx = start(repo, "startup")
    assert "behind origin/main by 1 relevant merge" in ctx
    assert "merge outward rename" in ctx
    assert "rename side commit" not in ctx


def test_inward_rename_docs_to_src_counts(repo):
    _rename_merge(repo, "docs/check.py", "src/check.py", "merge inward rename")
    ctx = start(repo, "startup")
    assert "behind origin/main by 1 relevant merge" in ctx
    assert "merge inward rename" in ctx


def test_irrelevant_only_rename_does_not_warn(repo):
    _rename_merge(repo, "docs/a.md", "jobs/SYNTH/a.md", "merge irrelevant rename")
    ctx = start(repo, "startup")
    assert "merge irrelevant rename" not in ctx
    assert "behind origin/main by" not in ctx
