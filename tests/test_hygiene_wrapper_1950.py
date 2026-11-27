"""new-case: pinned repo-hygiene wired into the pilot - wrapper, hooks, CI (#1950).

The three v0 cases on a fixture PR diff (new duplicate script, stale route pointer, archive of a live file) must
fail the wrapper; a clean diff passes. The end-to-end cases need the pinned tool (HYGIENE_PROJECT = a local
repo-hygiene clone) and skip without it; the hook filter, the pin and the wiring are checked offline.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

from tools.architecture import duplicate_guard

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pilot_hygiene", ROOT / "tools/hygiene/hygiene.py")
hygiene = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hygiene)

needs_tool = pytest.mark.skipif(not os.environ.get("HYGIENE_PROJECT"),
                                reason="HYGIENE_PROJECT (local repo-hygiene clone) not set")


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                           *args], check=True, capture_output=True, text=True).stdout


def put(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def pr(tmp_path):
    """A pilot-shaped base commit; the test writes its PR diff into the working tree."""
    root = tmp_path / "pilot"
    root.mkdir()
    git(root, "init", "-q")
    put(root, "AGENTS.md", "# Start\nRead [the site trail](routes/site.md).\n")
    put(root, "routes/site.md", "# Site\nUse [the recipe](../docs/recipe.md).\n")
    put(root, "docs/recipe.md", "# Recipe\n")
    put(root, "docs/old-recipe.md", "# Old recipe\nStatus: superseded by docs/recipe.md\n")
    put(root, "adapters/max/agr_tools/udimtile_core.py", "def udim_tile(u, v):\n    return 1001 + u + v * 10\n")
    put(root, "tools/live.py", "VALUE = 1\n")
    put(root, "tools/run.py", "from tools import live\n")
    put(root, "docs/ARCHIVE.md", "# Archive\n\n## Hidden from search (still in the tree)\n\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "base")
    return root


def wrapper(root):
    return subprocess.run([sys.executable, str(ROOT / "tools/hygiene/hygiene.py"), "check", "--repo", str(root),
                           "--base", "HEAD", "--json"], capture_output=True, text=True, encoding="utf-8")


def rules(run):
    assert run.returncode in (0, 1), run.stderr
    return run.returncode, sorted((f["rule"], f["file"]) for f in json.loads(run.stdout)["findings"])


@needs_tool
@pytest.mark.parametrize("rel,text,expected", [
    ("tools/x1950/udim.py", "def udim_tile(u, v):\n    return 1001 + int(u) + int(v) * 10\n",
     [("duplicate-operation", "tools/x1950/udim.py")] * 2),
    ("routes/site.md", "# Site\nUse [the recipe](../docs/old-recipe.md).\n", [("stale-pointer", "routes/site.md")]),
    ("docs/ARCHIVE.md", "# Archive\n\n## Hidden from search (still in the tree)\n\n- `tools/live.py` — retired\n",
     [("live-consumer", "docs/ARCHIVE.md")]),
], ids=["duplicate-script", "stale-route-pointer", "archive-live-file"])
def test_fixture_pr_diff_fails_the_wrapper(pr, rel, text, expected):
    assert rules(wrapper(pr)) == (0, [])
    put(pr, rel, text)
    assert rules(wrapper(pr)) == (1, expected)


@needs_tool
def test_clean_fixture_pr_diff_passes(pr):
    put(pr, "tools/x1950/area.py", "def area(w, h):\n    return w * h\n")
    put(pr, "routes/site.md", "# Site\nUse [the recipe](../docs/recipe.md) first.\n")
    assert rules(wrapper(pr)) == (0, [])


def event(path, content="x = 1\n", tool="Write"):
    return {"hook_event_name": "PreToolUse", "tool_name": tool, "cwd": str(ROOT),
            "tool_input": {"file_path": str(ROOT / path), "content": content}}


def test_hook_only_checks_new_scripts_and_docs(monkeypatch):
    monkeypatch.setattr(hygiene, "command", lambda: pytest.fail("existing/non-script path must not run the tool"))
    for rel in ("tools/architecture/search_noise.py", "AGENTS.md", "tools/x1950/data.json"):
        assert hygiene.hook("claude", json.dumps(event(rel))) == (0, "")
    assert hygiene.touched(event("tools/x1950/new.py")) == ["tools/x1950/new.py"]
    assert hygiene.new_script_or_doc("tools/x1950/new.py") and hygiene.new_script_or_doc("docs/x1950-new.md")
    patch = {"hook_event_name": "PreToolUse", "tool_name": "apply_patch", "cwd": str(ROOT),
             "tool_input": {"command": "*** Begin Patch\n*** Add File: tools/x1950/a.py\n+x = 1\n"
                                       "*** Update File: AGENTS.md\n@@\n-a\n+b\n*** End Patch\n"}}
    assert hygiene.touched(patch) == ["tools/x1950/a.py", "AGENTS.md"]


def test_hook_fails_open_without_the_tool(monkeypatch, capsys):
    monkeypatch.setattr(hygiene, "command", lambda: (_ for _ in ()).throw(hygiene.Unresolved("no clone")))
    assert hygiene.hook("claude", json.dumps(event("tools/x1950/new.py"))) == (0, "")
    assert "skipped: no clone" in capsys.readouterr().err


@needs_tool
def test_hook_denies_a_new_duplicate_script_under_three_seconds():
    body = "def udim_tile(u, v):\n    return 1001 + int(u) + int(v) * 10\n"
    argv = [sys.executable, str(ROOT / "tools/hygiene/hygiene.py"), "hook", "--agent", "claude"]
    started = time.perf_counter()
    run = subprocess.run(argv, input=json.dumps(event("tools/x1950/udim.py", body)), capture_output=True,
                         text=True, encoding="utf-8")
    elapsed = time.perf_counter() - started
    out = json.loads(run.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny" and "duplicate-operation" in out["permissionDecisionReason"]
    assert elapsed < 3.0, f"hook took {elapsed:.2f} s"


def test_a_moved_clone_runs_the_pin_from_a_detached_worktree(tmp_path, monkeypatch):
    clone = tmp_path / "repo-hygiene"
    clone.mkdir()
    git(clone, "init", "-q")
    put(clone, "pyproject.toml", "[project]\nname = 'x'\n")
    git(clone, "add", ".")
    git(clone, "commit", "-qm", "pinned")
    pin = git(clone, "rev-parse", "HEAD").strip()
    put(clone, "later.txt", "moved on\n")
    git(clone, "add", ".")
    git(clone, "commit", "-qm", "later")
    monkeypatch.setattr(hygiene, "PIN", pin)
    target = hygiene.pinned_checkout(clone)
    assert target == clone / ".worktrees" / f"pin-{pin[:12]}" and not (target / "later.txt").exists()
    assert hygiene.pinned_checkout(clone) == target  # reused, not re-created
    assert hygiene.command({"HYGIENE_PROJECT": str(clone)})[-2:] == [str(target), "hygiene"]
    monkeypatch.setattr(hygiene, "PIN", "0" * 40)
    with pytest.raises(hygiene.Unresolved, match="lacks the pinned commit"):
        hygiene.pinned_checkout(clone)


def test_pin_is_a_full_commit_and_the_wiring_names_one_entry():
    assert len(hygiene.PIN) == 40 and int(hygiene.PIN, 16) >= 0
    assert hygiene.command({})[-2:] == [f"git+{hygiene.URL}@{hygiene.PIN}", "hygiene"]
    entry = "tools/hygiene/hygiene.py"
    claude = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))["hooks"]
    codex = json.loads((ROOT / ".codex/hooks.json").read_text(encoding="utf-8"))["hooks"]
    for hooks, agent, matcher in ((claude, "claude", "Write|Edit"), (codex, "codex", "^apply_patch$")):
        pre = [h["command"] for g in hooks["PreToolUse"] if g.get("matcher") == matcher for h in g["hooks"]]
        start = [h["command"] for g in hooks["SessionStart"] for h in g["hooks"]]
        assert any(entry in c and f"hook --agent {agent}" in c for c in pre)
        assert any(entry in c and f"session --agent {agent}" in c for c in start)
    assert "One door" in json.loads(hygiene.session("claude"))["hookSpecificOutput"]["additionalContext"]
    # The worker token cannot push .github/workflows/ (no `workflow` scope): staged for Artem to move.
    staged = [p for p in (ROOT / ".github/workflows/hygiene.yml", ROOT / "tools/hygiene/hygiene.workflow.yml")
              if p.is_file()]
    assert len(staged) == 1
    ci = staged[0].read_text(encoding="utf-8")
    assert entry in ci and "check --base" in ci
    assert "scripts/hygiene" in (ROOT / "AGENTS.md").read_text(encoding="utf-8")


def assert_profile_contract(profile: str) -> None:
    assert not any(line.startswith("extends:") for line in profile.splitlines())
    operations = yaml.safe_load(profile).get("operations", {})
    expected = duplicate_guard.RULES.keys()
    assert operations.keys() == expected, (
        f"operation IDs differ: missing {sorted(expected - operations.keys())}; "
        f"extra {sorted(operations.keys() - expected)}"
    )
    assert duplicate_guard.GUARDED.keys() == expected, "duplicate_guard RULES and GUARDED must cover the same rules"
    for rule, owner in duplicate_guard.RULES.items():
        operation = operations[rule]
        assert operation["owner"] == owner, f"{rule}: owner must match duplicate_guard RULES"
        # duplicate_guard scopes by top-level folder; the hook uses recursive globs.
        globs = {f"{top}/**" for top in duplicate_guard.GUARDED[rule]}
        assert set(operation["scope"]) == globs, f"{rule}: scope must match duplicate_guard GUARDED"


def test_pilot_profile_contract():
    assert_profile_contract((ROOT / hygiene.PROFILE).read_text(encoding="utf-8"))


@pytest.mark.parametrize(("drift", "diagnostic"), [
    ("missing-rule", r"operation IDs.*missing.*poly63-window-match"),
    ("extra-rule", r"operation IDs.*extra.*synthetic-extra"),
    ("moved-owner", r"poly63-window-match: owner"),
    ("narrowed-scope", r"poly63-window-match: scope"),
    ("widened-scope", r"poly63-window-match: scope"),
])
def test_pilot_profile_contract_rejects_operation_drift(drift, diagnostic):
    """Mutate a synthetic copy of the actual profile, never the tracked file."""
    profile = yaml.safe_load((ROOT / hygiene.PROFILE).read_text(encoding="utf-8"))
    operations = profile["operations"]
    rule = "poly63-window-match"
    operation = operations[rule]
    if drift == "missing-rule":
        del operations[rule]
    elif drift == "extra-rule":
        operations["synthetic-extra"] = dict(operation)
    elif drift == "moved-owner":
        operation["owner"] = "tools/windows/stage2.py"
    elif drift == "narrowed-scope":
        operation["scope"] = [glob for glob in operation["scope"] if glob != "src/**"]
    elif drift == "widened-scope":
        operation["scope"] = [*operation["scope"], "adapters/**"]
    with pytest.raises(AssertionError, match=diagnostic):
        assert_profile_contract(yaml.safe_dump(profile))
