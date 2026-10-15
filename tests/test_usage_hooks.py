"""Triggers: tools/hooks/usage_log.py, tools/hooks/skill_gate.py, their wiring, /reuse-scan and agent descriptions."""
import datetime
import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
LOG_HOOK = ROOT / "tools/hooks/usage_log.py"
GATE = ROOT / "tools/hooks/skill_gate.py"


def run(script, args, payload, log):
    env = {**os.environ, "AGR_USAGE_LOG": str(log), "CLAUDE_PROJECT_DIR": str(ROOT)}
    r = subprocess.run([sys.executable, str(script), *args], input=json.dumps(payload), capture_output=True,
                       text=True, encoding="utf-8", env=env)
    assert r.returncode == 0, r.stderr
    return r.stdout


def lines(log):
    return [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []


def transcript(tmp_path, *entries):
    t = tmp_path / "s.jsonl"
    t.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")
    return t


def command(name):
    return {"type": "user", "message": {"content": f"<command-message>{name}</command-message>\n"
                                                   f"<command-name>/{name}</command-name>\n<command-args></command-args>"}}


def skill_call(name, success=True):
    """The tool result of a Skill call, as Claude Code records it (toolUseResult.success, commandName)."""
    return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1",
                                                     "content": f"Launching skill: {name}"}]},
            "toolUseResult": {"success": success, "commandName": name}}


def quoted(text):
    """A tool result that only quotes a command tag (a file read, a grep)."""
    return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t2", "content": text}]}}


def test_hooks_are_wired():
    hooks = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))["hooks"]
    post = hooks["PostToolUse"][0]
    assert all(re.search(post["matcher"], t) for t in ("Agent", "Task", "Skill")) and not re.search(post["matcher"], "Bash")
    assert post["hooks"][0]["command"].endswith('usage_log.py" post')
    assert any(h["command"].endswith('usage_log.py" prompt') for h in hooks["UserPromptSubmit"][0]["hooks"])
    gate = next(e for e in hooks["PreToolUse"] if "skill_gate.py" in e["hooks"][0]["command"])
    for tool in ("mcp__3dsmax-mcp__inspect_mesh", "mcp__blender__get_objects_summary", "mcp__revit-http-2025__revit_ping",
                 "mcp__revit-twin__x"):
        assert re.search(gate["matcher"], tool)
    assert not re.search(gate["matcher"], "Bash") and not re.search(gate["matcher"], "mcp__github__get_me")


def test_usage_log_records_agents_skills_and_commands(tmp_path):
    log, t = tmp_path / "logs/u.jsonl", transcript(tmp_path, command("takeover"))
    base = {"session_id": "s1", "transcript_path": str(t)}
    run(LOG_HOOK, ["post"], {**base, "tool_name": "Agent", "tool_input": {"subagent_type": "bench-runner"}}, log)
    run(LOG_HOOK, ["post"], {**base, "tool_name": "Task", "tool_input": {}}, log)
    run(LOG_HOOK, ["post"], {**base, "tool_name": "Skill", "tool_input": {"skill": "blender-mcp"}}, log)
    run(LOG_HOOK, ["post"], {**base, "tool_name": "Bash", "tool_input": {"command": "ls"}}, log)
    run(LOG_HOOK, ["prompt"], {**base, "hook_event_name": "UserPromptSubmit", "prompt": "/handover"}, log)
    run(LOG_HOOK, ["prompt"], {**base, "hook_event_name": "UserPromptSubmit", "prompt": "продолжай"}, log)
    got = [(r["kind"], r["name"], r["command"]) for r in lines(log)]
    assert got == [("agent", "bench-runner", "takeover"), ("agent", "general-purpose", "takeover"),
                   ("skill", "blender-mcp", "takeover"), ("command", "handover", None)]
    assert all(r["session_id"] == "s1" and r["time"] for r in lines(log))


def test_command_attribution_ignores_quoted_tags(tmp_path):        # review 2 of #107
    log = tmp_path / "u.jsonl"
    t = transcript(tmp_path, command("handover"), quoted("example: <command-name>/takeover</command-name>"))
    run(LOG_HOOK, ["post"], {"session_id": "s", "transcript_path": str(t), "tool_name": "Agent",
                             "tool_input": {"subagent_type": "bench-runner"}}, log)
    assert lines(log)[0]["command"] == "handover"


def test_reuse_candidates_fails_loudly_when_git_fails(tmp_path):  # review 2 of #107; git runs but exits non-zero
    r = subprocess.run([sys.executable, str(ROOT / "tools/reuse_candidates.py")], capture_output=True, text=True,
                       env={**os.environ, "GIT_DIR": str(tmp_path / "no-repo")})       # review 3: not a missing git
    assert r.returncode != 0 and "Job scripts" not in r.stdout and "failed" in r.stderr


def test_a_failed_skill_attempt_is_no_load(tmp_path):              # review 3 of #107: the call and its failure
    attempt = {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": "t1", "name": "Skill", "input": {"skill": "blender-mcp"}}]}}
    t = transcript(tmp_path, attempt, skill_call("blender-mcp", success=False))
    out = run(GATE, [], {"session_id": "s", "transcript_path": str(t), "tool_name": "mcp__blender__get_objects_summary"},
              tmp_path / "u.jsonl")
    assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_usage_log_never_fails(tmp_path):
    for raw in ("not json", "[]", "{}"):
        r = subprocess.run([sys.executable, str(LOG_HOOK), "post"], input=raw, capture_output=True, text=True,
                           env={**os.environ, "AGR_USAGE_LOG": str(tmp_path / "u.jsonl")})
        assert r.returncode == 0 and r.stdout == ""


def test_stats_counts_and_names_the_unused(tmp_path):
    log = tmp_path / "u.jsonl"
    old = {"time": "2020-01-01T00:00:00+00:00", "kind": "agent", "name": "mesh-reader"}
    log.write_text(json.dumps(old) + "\n", encoding="utf-8")
    run(LOG_HOOK, ["post"], {"tool_name": "Agent", "tool_input": {"subagent_type": "bench-runner"}}, log)
    run(LOG_HOOK, ["post"], {"tool_name": "Agent", "tool_input": {"subagent_type": "Explore"}}, log)
    env = {**os.environ, "AGR_USAGE_LOG": str(log)}
    out = subprocess.run([sys.executable, str(LOG_HOOK), "stats", "--days", "7"], capture_output=True, text=True,
                         encoding="utf-8", env=env).stdout
    assert "bench-runner 1" in out and "mesh-reader 0" in out                 # the 2020 line is outside 7 days
    assert re.search(r"never called: .*mesh-reader", out) and "Explore (agent) 1" in out
    assert "handover 0" in out and "validate-delivery 0" in out


def _slug(path):
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def _at(e, t, sid="s1", **kw):
    return {**e, "timestamp": t, "sessionId": sid, "gitBranch": "harness/x", **kw}


def _agent(sub, call_id="a"):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": call_id, "name": "Agent", "input": {"subagent_type": sub} if sub else {}}]}}


def _agent_done(call_id):
    return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": call_id, "content": "ok"}]}}


def _write(path, *entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")


def _backfill(env):
    r = subprocess.run([sys.executable, str(LOG_HOOK), "backfill", "--days", "3"], capture_output=True, text=True,
                       encoding="utf-8", env=env)
    assert r.returncode == 0, r.stderr
    return r.stdout


def _stamp(t):
    return t.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _env(tmp_path, repo, projects, log, git=False):
    env = {**os.environ, "AGR_USAGE_LOG": str(log), "AGR_CLAUDE_PROJECTS": str(projects), "CLAUDE_PROJECT_DIR": str(repo)}
    if not git:
        env["GIT_DIR"] = str(tmp_path / "no-repo")
    return env


def test_backfill_from_past_transcripts(tmp_path):                # #109
    repo, projects, log = tmp_path / "repo", tmp_path / "projects", tmp_path / "logs/u.jsonl"
    repo.mkdir()
    now = datetime.datetime.now(datetime.timezone.utc)
    ts = [(now - datetime.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%S.123Z") for h in (5, 4, 3, 2, 1)]
    old = "2020-01-01T00:00:00.000Z"
    main = projects / _slug(repo)
    wt = projects / (_slug(repo) + "--claude-worktrees-wt-1")
    other = projects / (_slug(repo) + "-other")                         # another repo with the same prefix
    _write(main / "s1.jsonl",
           _at(command("takeover"), ts[0]),
           _at(_agent("bench-runner"), ts[1]),
           _at(quoted("<command-name>/handover</command-name>"), ts[1]),      # quoted: not a command
           _at(skill_call("blender-mcp"), ts[2]),
           _at(skill_call("revit-mcp", success=False), ts[2]),               # failed load: not logged
           _at(_agent("source-inspector"), ts[3], isSidechain=True),          # a subagent's own call
           _at(_agent("mesh-reader"), old))                                   # outside --days
    with open(main / "s1.jsonl", "a", encoding="utf-8") as f:
        f.write("not json\n")
    _write(wt / "s2.jsonl", _at(_agent(None), ts[4], sid="s2"))
    _write(other / "s3.jsonl", _at(_agent("bench-runner"), ts[4], sid="s3"))
    env = _env(tmp_path, repo, projects, log)

    out = _backfill(env)
    got = [(r["session_id"], r["kind"], r["name"], r["command"], r["branch"]) for r in lines(log)]
    assert got == [("s1", "command", "takeover", None, "harness/x"),
                   ("s1", "agent", "bench-runner", "takeover", "harness/x"),
                   ("s1", "skill", "blender-mcp", "takeover", "harness/x"),
                   ("s2", "agent", "general-purpose", None, "harness/x")]
    assert lines(log)[1]["time"] == ts[1][:19] + ".123000+00:00" and all(r["source"] == "backfill" for r in lines(log))
    assert "4 new" in out
    assert "0 new" in _backfill(env) and len(lines(log)) == 4               # idempotent


def test_backfill_keeps_same_second_calls_apart(tmp_path):          # #109 review 1: time keeps its fractions
    repo, projects, log = tmp_path / "repo", tmp_path / "projects", tmp_path / "u.jsonl"
    repo.mkdir()
    t = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)).replace(microsecond=0)
    _write(projects / _slug(repo) / "s.jsonl",
           _at(_agent("bench-runner", "a1"), _stamp(t.replace(microsecond=123000)), sid="s"),
           _at(_agent("bench-runner", "a2"), _stamp(t.replace(microsecond=789000)), sid="s"))
    env = _env(tmp_path, repo, projects, log)
    assert "2 new" in _backfill(env)
    assert sorted(r["time"][-13:] for r in lines(log)) == [".123000+00:00", ".789000+00:00"]
    assert "0 new" in _backfill(env) and len(lines(log)) == 2


def test_backfill_reconciles_live_lines_per_call(tmp_path):         # #109 review 1: no session-wide skip
    repo, projects, log = tmp_path / "repo", tmp_path / "projects", tmp_path / "u.jsonl"
    repo.mkdir()
    now = datetime.datetime.now(datetime.timezone.utc)
    h = [now - datetime.timedelta(hours=x) for x in (3, 2, 1)]
    done = h[1] + datetime.timedelta(minutes=20)                       # a long subagent run
    # before the hooks: a historical agent call; then the hooks log a /takeover and a bench-runner call live
    _write(projects / _slug(repo) / "s.jsonl",
           _at(_agent("historical-agent", "a0"), _stamp(h[0]), sid="s"),
           _at(_agent_done("a0"), _stamp(h[0] + datetime.timedelta(minutes=1)), sid="s"),
           _at(command("takeover"), _stamp(h[1]), sid="s"),
           _at(_agent("bench-runner", "a1"), _stamp(h[1] + datetime.timedelta(seconds=5)), sid="s"),
           _at(_agent_done("a1"), _stamp(done), sid="s"),
           _at(_agent("bench-runner", "a2"), _stamp(h[2]), sid="s"))   # a second call the hook missed
    live = [{"time": h[1].isoformat(timespec="seconds"), "session_id": "s", "kind": "command", "name": "takeover"},
            {"time": (done + datetime.timedelta(seconds=1)).isoformat(timespec="seconds"), "session_id": "s",
             "kind": "agent", "name": "bench-runner", "command": "takeover"}]
    _write(log, *live)
    env = _env(tmp_path, repo, projects, log)
    assert "2 new, 2 already logged" in _backfill(env)
    added = [(r["name"], r["command"]) for r in lines(log)[2:]]
    assert added == [("historical-agent", None), ("bench-runner", "takeover")]
    assert all(r["source"] == "backfill" for r in lines(log)[2:])
    assert "0 new" in _backfill(env) and len(lines(log)) == 4


def test_backfill_reads_registered_external_worktrees(tmp_path):    # #109 review 1: worktrees outside the checkout
    repo, projects, log = tmp_path / "repo", tmp_path / "projects", tmp_path / "u.jsonl"
    external, stranger = tmp_path / "elsewhere" / "wt1", tmp_path / "elsewhere" / "other-repo"
    repo.mkdir()
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "init.defaultBranch=main"]
    subprocess.run([*git, "init", "-q", str(repo)], check=True)
    subprocess.run([*git, "-C", str(repo), "commit", "-q", "--allow-empty", "-m", "x"], check=True)
    subprocess.run([*git, "-C", str(repo), "worktree", "add", "-q", "-b", "wt1", str(external)], check=True)
    t = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
    _write(projects / _slug(external) / "e.jsonl", _at(_agent("source-inspector"), _stamp(t), sid="e"))
    _write(projects / _slug(stranger) / "x.jsonl", _at(_agent("bench-runner"), _stamp(t), sid="x"))
    env = {k: v for k, v in _env(tmp_path, repo, projects, log, git=True).items() if not k.startswith("GIT_")}
    out = _backfill(env)
    assert [(r["session_id"], r["name"]) for r in lines(log)] == [("e", "source-inspector")], out
    assert "1 transcripts" in out
    assert "0 new" in _backfill(env)


@pytest.mark.parametrize("tool, loaded_by, denied", [
    ("mcp__blender__get_objects_summary", None, True),
    ("mcp__blender__get_objects_summary", skill_call("blender-mcp"), False),
    ("mcp__blender__get_objects_summary", command("blender-mcp"), False),
    ("mcp__blender__get_objects_summary", skill_call("revit-mcp"), True),
    ("mcp__3dsmax-mcp__inspect_mesh", skill_call("3dsmax-mcp-dev"), False),
    ("mcp__3dsmax-mcp__inspect_mesh", skill_call("3dsmax-mcp:3dsmax-mcp-dev"), False),
    ("mcp__revit-http-2025__revit_ping", skill_call("blender-mcp"), True),
    ("mcp__github__get_me", None, False),
    # review 2 of #107: a failed Skill call or a quoted tag is no load
    ("mcp__blender__get_objects_summary", skill_call("blender-mcp", success=False), True),
    ("mcp__blender__get_objects_summary", quoted("<command-name>/blender-mcp</command-name>"), True),
])
def test_skill_gate(tmp_path, tool, loaded_by, denied):
    t = transcript(tmp_path, *([loaded_by] if loaded_by else []), {"type": "user", "message": {"content": "hi"}})
    out = run(GATE, [], {"session_id": "s", "transcript_path": str(t), "tool_name": tool}, tmp_path / "u.jsonl")
    if denied:
        decision = json.loads(out)["hookSpecificOutput"]
        assert decision["permissionDecision"] == "deny" and "Skill tool" in decision["permissionDecisionReason"]
    else:
        assert out == ""


def test_skill_gate_trusts_the_usage_log_and_skips_subagents(tmp_path):
    t = transcript(tmp_path, {"type": "user", "message": {"content": "hi"}})
    log = tmp_path / "u.jsonl"
    payload = {"session_id": "s", "transcript_path": str(t), "tool_name": "mcp__revit-http-2025__revit_ping"}
    assert run(GATE, [], {**payload, "agent_id": "a1"}, log) == ""            # subagent: not gated
    assert run(GATE, [], payload, log) != ""
    run(LOG_HOOK, ["post"], {"session_id": "s", "tool_name": "Skill", "tool_input": {"skill": "revit-mcp"}}, log)
    assert run(GATE, [], payload, log) == ""
    assert run(GATE, [], {**payload, "session_id": "other"}, log) != ""       # another session's load does not count
    assert run(GATE, [], {**payload, "transcript_path": str(tmp_path / "missing.jsonl")}, log) == ""


def test_reuse_scan_command_and_helper():
    text = (ROOT / ".claude/commands/reuse-scan.md").read_text(encoding="utf-8")
    meta = yaml.safe_load(text.split("---\n")[1])
    assert meta["disable-model-invocation"] is True
    assert "!`py -3 tools/reuse_candidates.py --days 7`" in text and "usage_log.py stats --days 7" in text
    r = subprocess.run([sys.executable, str(ROOT / "tools/reuse_candidates.py"), "--days", "7"], capture_output=True,
                       text=True, encoding="utf-8")
    assert r.returncode == 0 and r.stdout.startswith("Job scripts: ")
    takeover = (ROOT / ".claude/commands/takeover.md").read_text(encoding="utf-8")
    assert "!`py -3 tools/hooks/usage_log.py stats --days 7`" in takeover
    assert "Repeats" in (ROOT / ".claude/commands/handover.md").read_text(encoding="utf-8")


def test_logs_are_ignored():
    r = subprocess.run(["git", "check-ignore", "-q", "logs/agent-usage.jsonl"], cwd=ROOT)
    assert r.returncode == 0


@pytest.mark.parametrize("path", sorted(glob.glob(str(ROOT / ".claude/agents/*.md")) + [
    p for p in glob.glob(str(ROOT / ".agents/skills/*/SKILL.md"))
    if Path(p).parent.name not in json.loads((ROOT / "skills-lock.json").read_text(encoding="utf-8"))["skills"]]))
def test_descriptions_have_use_when_examples(path):
    meta = yaml.safe_load(Path(path).read_text(encoding="utf-8").split("---\n")[1])
    tail = meta["description"].split("Use when:")[-1]
    assert "Use when:" in meta["description"] and 2 <= tail.count("«") <= 3, meta["description"]
