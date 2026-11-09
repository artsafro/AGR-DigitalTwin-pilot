"""One-shot merge token in the PreToolUse guard (#1028, [D234]).

An explicit chat merge command naming PR N authorises exactly one `gh pr merge N`: the agent
quotes the command into a token for N (TTL 10 min) bound to the repository of its checkout's
`origin`; the guard allows only that N in that repository, once. pretool.py (the hook Claude Code
runs) forwards that allow unless another part asks, denies or fails.
"""
import importlib.util
import json
import math
import os
import random
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / ".claude/hooks/guard.py"
PRETOOL = ROOT / ".claude/hooks/pretool.py"
TTL = 600
ORIGIN = "https://github.com/artsafro/AGR-DigitalTwin-pilot.git"
REPO = "github.com/artsafro/agr-digitaltwin-pilot"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_guard():
    return load(GUARD, "guard_under_test")


def make_repo(path, *remotes):
    """A git checkout at path with the given (name, url) remotes; no remote when remotes is empty."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    for name, url in remotes:
        subprocess.run(["git", "-C", str(path), "remote", "add", name, url], check=True)
    return path


@pytest.fixture
def ctx(tmp_path):
    return SimpleNamespace(tokens=tmp_path / "tokens", repo=make_repo(tmp_path / "repo", ("origin", ORIGIN)),
                           root=tmp_path)


def env_for(token_dir, **extra):
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PROJECT_DIR", "GH_REPO")}
    env["AGR_MERGE_TOKEN_DIR"] = str(token_dir)
    env.update(extra)
    return env


def run_hook(script, command, token_dir, cwd, protocol="claude", hook_cwd=None, **extra_env):
    if protocol == "antigravity":
        payload = {"toolCall": {"name": "run_command", "args": {"CommandLine": command}}}
    else:
        payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(hook_cwd or cwd)}
    result = subprocess.run([sys.executable, str(script)], input=json.dumps(payload), capture_output=True,
                            text=True, encoding="utf-8", env=env_for(token_dir, **extra_env), cwd=cwd)
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout) if result.stdout.strip() else {}
    if protocol == "antigravity":
        return out.get("decision"), out.get("reason", "")
    hso = out.get("hookSpecificOutput", {})
    return hso.get("permissionDecision", "none"), hso.get("permissionDecisionReason", "")


def run_guard(command, c, **kw):
    return run_hook(GUARD, command, c.tokens, kw.pop("cwd", c.repo), **kw)


def run_pretool(command, c, **kw):
    return run_hook(PRETOOL, command, c.tokens, kw.pop("cwd", c.repo), **kw)


def put_token(token_dir, pr, command=None, created_at=None, raw=None, name=None, repo=REPO):
    token_dir.mkdir(parents=True, exist_ok=True)
    path = token_dir / (name or f"pr-{pr}.json")
    if raw is not None:
        path.write_text(raw, encoding="utf-8")
        return path
    body = {"pr": pr, "repo": repo, "command": command if command is not None else f"Мерджи #{pr}",
            "created_at": time.time() if created_at is None else created_at}
    path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    return path


def tokens_left(token_dir):
    return sorted(p.name for p in token_dir.glob("*")) if token_dir.exists() else []


# --- acceptance rows -------------------------------------------------------------------------

def test_token_for_n_allows_gh_pr_merge_n_once(ctx):
    put_token(ctx.tokens, 1028)
    decision, reason = run_guard("gh pr merge 1028 --merge", ctx)
    assert decision == "allow"
    assert "1028" in reason and "D234" in reason and "Мерджи #1028" in reason and REPO in reason
    assert tokens_left(ctx.tokens) == []


def test_second_call_with_the_same_token_asks(ctx):
    put_token(ctx.tokens, 1028)
    assert run_guard("gh pr merge 1028", ctx)[0] == "allow"
    decision, reason = run_guard("gh pr merge 1028", ctx)
    assert decision == "ask"
    assert "merge command" in reason


def test_token_for_n_does_not_allow_other_pr_and_is_kept(ctx):
    put_token(ctx.tokens, 1028)
    assert run_guard("gh pr merge 1029", ctx)[0] == "ask"
    assert tokens_left(ctx.tokens) == ["pr-1028.json"]
    assert run_guard("gh pr merge 1028", ctx)[0] == "allow"


@pytest.mark.parametrize("age", [TTL, TTL + 1, 10 * TTL])
def test_expired_or_exactly_at_ttl_token_asks(ctx, age):
    put_token(ctx.tokens, 1028, created_at=time.time() - age)
    assert run_guard("gh pr merge 1028", ctx)[0] == "ask"


def test_no_token_asks(ctx):
    assert run_guard("gh pr merge 1028", ctx)[0] == "ask"
    ctx.tokens = ctx.root / "missing-dir"
    assert run_guard("gh pr merge 1028", ctx)[0] == "ask"


def test_antigravity_protocol_allows_once_then_asks(ctx):
    put_token(ctx.tokens, 7)
    assert run_guard("gh pr merge 7", ctx, protocol="antigravity")[0] == "allow"
    assert run_guard("gh pr merge 7", ctx, protocol="antigravity")[0] == "ask"


# --- P1 round 1: pretool.py (the hook Claude Code runs) forwards the allow ---------------------

def test_pretool_forwards_allow_once_then_asks(ctx):
    put_token(ctx.tokens, 1149)
    decision, reason = run_pretool("gh pr merge 1149 --merge", ctx)
    assert decision == "allow" and "D234" in reason
    assert tokens_left(ctx.tokens) == []
    assert run_pretool("gh pr merge 1149 --merge", ctx)[0] == "ask"


def test_pretool_without_token_asks(ctx):
    assert run_pretool("gh pr merge 1149", ctx)[0] == "ask"


GUARD_ALLOW = json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                                 "permissionDecisionReason": "guard.py: token"}})


def _part(decision):
    return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision,
                                              "permissionDecisionReason": f"pipeline_gate: {decision}"}})


@pytest.mark.parametrize("gate, expected", [
    ((_part("deny"), None), ("deny", 0)),
    ((_part("ask"), None), ("ask", 0)),
    (("", None), ("allow", 0)),
    (("", "Traceback: boom\n"), (None, 1)),          # a failed part: the allow is not forwarded
    ((_part("allow"), None), ("allow", 0)),
])
def test_pretool_rank_deny_over_ask_over_allow(monkeypatch, gate, expected):
    pretool = load(PRETOOL, "pretool_under_test")
    monkeypatch.setattr(pretool, "run_part", lambda name, raw: (GUARD_ALLOW, None) if name == "guard.py" else gate)
    out, err, code = pretool.dispatch(json.dumps({"tool_name": "Bash", "tool_input": {"command": "gh pr merge 1"}}))
    decision = json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out.strip() else None
    assert (decision, code) == expected
    assert bool(err) == (code == 1)


def test_pretool_guard_ask_beats_gate_allow(monkeypatch):
    pretool = load(PRETOOL, "pretool_under_test")
    monkeypatch.setattr(pretool, "run_part",
                        lambda name, raw: (_part("ask"), None) if name == "guard.py" else (_part("allow"), None))
    out, _, _ = pretool.dispatch(json.dumps({"tool_name": "Bash", "tool_input": {"command": "gh pr merge 1"}}))
    assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "ask"


# --- P1 round 1: the token is bound to one repository -----------------------------------------

@pytest.mark.parametrize("command", [
    "gh pr merge 1149 -R artsafro/AGR-DigitalTwin --merge",
    "gh pr merge 1149 --repo=artsafro/AGR-DigitalTwin-pilot2",
    "gh -R other/AGR-DigitalTwin-pilot pr merge 1149",
    "gh pr merge 1149 -R ghe.example.com/artsafro/AGR-DigitalTwin-pilot",
    "gh pr merge 1149 -R artsafro/AGR-DigitalTwin-pilot -R artsafro/AGR-DigitalTwin",
    "gh pr merge 1149 -R not-a-repo",
])
def test_other_repo_flag_asks_and_keeps_token(ctx, command):
    put_token(ctx.tokens, 1149)
    assert run_guard(command, ctx)[0] == "ask"
    assert run_pretool(command, ctx)[0] == "ask"
    assert tokens_left(ctx.tokens) == ["pr-1149.json"]


@pytest.mark.parametrize("remotes", [
    (),                                                                           # no remote
    (("origin", "https://github.com/artsafro/AGR-DigitalTwin.git"),),             # other repo
    (("origin", ORIGIN), ("upstream", "https://github.com/other/AGR-DigitalTwin-pilot.git")),  # gh may pick upstream
    None,                                                                         # not a git checkout
])
def test_cwd_of_another_repo_asks_and_keeps_token(ctx, remotes):
    cwd = ctx.root / "elsewhere"
    if remotes is None:
        cwd.mkdir()
    else:
        make_repo(cwd, *remotes)
    put_token(ctx.tokens, 1149)
    assert run_guard("gh pr merge 1149 --merge", ctx, cwd=cwd)[0] == "ask"
    assert tokens_left(ctx.tokens) == ["pr-1149.json"]


def test_hook_cwd_wins_over_process_cwd(ctx):
    """Claude Code sends the session cwd in the payload; the guard checks that one."""
    foreign = make_repo(ctx.root / "foreign", ("origin", "https://github.com/other/x.git"))
    put_token(ctx.tokens, 1149)
    assert run_guard("gh pr merge 1149", ctx, hook_cwd=foreign)[0] == "ask"
    assert tokens_left(ctx.tokens) == ["pr-1149.json"]


def test_matching_repo_flag_allows_from_any_cwd(ctx):
    cwd = ctx.root / "nogit"
    cwd.mkdir()
    put_token(ctx.tokens, 1149)
    assert run_guard("gh pr merge 1149 -R artsafro/AGR-DigitalTwin-pilot --merge", ctx, cwd=cwd)[0] == "allow"


def test_gh_repo_env_names_the_target(ctx):
    put_token(ctx.tokens, 1149)
    assert run_guard("gh pr merge 1149", ctx, GH_REPO="artsafro/AGR-DigitalTwin")[0] == "ask"
    assert tokens_left(ctx.tokens) == ["pr-1149.json"]
    assert run_guard("gh pr merge 1149", ctx, GH_REPO="artsafro/AGR-DigitalTwin-pilot")[0] == "allow"


@pytest.mark.parametrize("repo", [None, "", "artsafro/AGR-DigitalTwin", 7, "github.com/artsafro"])
def test_token_without_matching_repo_asks(ctx, repo):
    put_token(ctx.tokens, 1149, repo=repo)
    assert run_guard("gh pr merge 1149", ctx)[0] == "ask"


# --- fail-closed token contents ----------------------------------------------------------------

def _raw(**body):
    return json.dumps({"repo": REPO, **body})


@pytest.mark.parametrize("token", [
    {"raw": ""},
    {"raw": "{not json"},
    {"raw": "[]"},
    {"raw": _raw(pr=1028, command="Мерджи #1028")},                       # no created_at
    {"raw": _raw(pr=1028, created_at=time.time())},                       # no command
    {"raw": _raw(command="Мерджи #1028", created_at=time.time())},        # no pr
    {"command": "вперед"},                       # incident 7: no PR number in the command
    {"command": "Мерджи"},
    {"command": "Мерджи #10280"},                # names another PR
    {"command": "Мерджи #11028"},
    {"command": ""},
    {"command": 1028},
    {"created_at": time.time() + 120},           # from the future
    {"created_at": "now"},
    {"created_at": True},
    {"raw": '{"pr": 1028, "repo": "%s", "command": "Мерджи #1028", "created_at": NaN}' % REPO},
    {"raw": '{"pr": 1028, "repo": "%s", "command": "Мерджи #1028", "created_at": Infinity}' % REPO},
    {"raw": '{"pr": 1028, "repo": "%s", "command": "Мерджи #1028", "created_at": -Infinity}' % REPO},
    {"raw": _raw(pr=1029, command="Мерджи #1028", created_at=time.time())},  # pr mismatch
    {"raw": _raw(pr="1028", command="Мерджи #1028", created_at=time.time())},
    {"raw": _raw(pr=True, command="Мерджи #1", created_at=time.time()), "pr": 1},
])
def test_invalid_token_asks(ctx, token):
    pr = token.pop("pr", 1028)
    put_token(ctx.tokens, pr, **token)
    assert run_guard(f"gh pr merge {pr}", ctx)[0] == "ask"


# --- fail-closed command shapes: the token covers one plain merge, nothing else ---------------

@pytest.mark.parametrize("command", [
    "gh pr merge",                                   # current branch, no number
    "gh pr merge 1028 && git push origin main",
    "gh pr merge 1028; rm -rf x",
    "gh pr merge 1028 | tee log",
    "gh pr merge 1028\ngh pr merge 1028",
    "gh pr merge 1028 --delete-branch",
    "gh pr merge 1028 -d",
    "gh pr merge 1028 --admin",
    "gh pr merge 1028 --body $(cat x)",
    "gh pr merge 1028 1029",
    "gh pr merge 1028 --subject 'x y'",
    "echo gh pr merge 1028",
    "gh pr merge https://github.com/o/n/pull/1028",
    "gh pr merge feature-1028",
    "gh pr merge 1028 --unknown-flag",
])
def test_command_outside_the_plain_merge_shape_asks_and_keeps_token(ctx, command):
    put_token(ctx.tokens, 1028)
    assert run_guard(command, ctx)[0] == "ask"
    assert tokens_left(ctx.tokens) == ["pr-1028.json"]


@pytest.mark.parametrize("command", [
    "gh pr merge 1028",
    "gh pr merge #1028 --squash",
    "gh.exe pr merge 1028 --merge",
    "gh pr merge 1028 --repo artsafro/AGR-DigitalTwin-pilot --merge",
    "gh -R artsafro/AGR-DigitalTwin-pilot pr merge 1028 -m",
    "gh pr merge 1028 -R github.com/artsafro/agr-digitaltwin-pilot",
    "  gh pr merge 1028 --rebase --auto  ",
])
def test_plain_merge_shapes_are_allowed_with_a_token(ctx, command):
    put_token(ctx.tokens, 1028)
    assert run_guard(command, ctx)[0] == "allow"


# --- token writer CLI ---------------------------------------------------------------------------

def run_writer(token_dir, cwd, *args):
    return subprocess.run([sys.executable, str(GUARD), "merge-token", *args], capture_output=True, text=True,
                          encoding="utf-8", env=env_for(token_dir), cwd=cwd)


def test_writer_then_guard_dry_run(ctx):
    result = run_writer(ctx.tokens, ctx.repo, "1028", "Мерджи #1028")
    assert result.returncode == 0, result.stderr
    data = json.loads((ctx.tokens / "pr-1028.json").read_text(encoding="utf-8"))
    assert data["pr"] == 1028 and data["command"] == "Мерджи #1028" and data["repo"] == REPO
    assert math.isfinite(data["created_at"])
    assert run_pretool("gh pr merge 1028", ctx)[0] == "allow"
    assert run_pretool("gh pr merge 1028", ctx)[0] == "ask"


@pytest.mark.parametrize("args", [
    ("1028", "вперед"),
    ("1028", "Мерджи"),
    ("1028", "Мерджи #10280"),
    ("1028", ""),
    ("abc", "Мерджи #abc"),
    ("0", "Мерджи #0"),
    ("-5", "Мерджи #-5"),
    ("1028",),
])
def test_writer_refuses_command_not_naming_the_pr(ctx, args):
    result = run_writer(ctx.tokens, ctx.repo, *args)
    assert result.returncode != 0
    assert tokens_left(ctx.tokens) == []


@pytest.mark.parametrize("remotes", [None, (), (("upstream", ORIGIN),), (("origin", "not a url"),)])
def test_writer_refuses_without_origin(ctx, remotes):
    cwd = ctx.root / "w"
    if remotes is None:
        cwd.mkdir()
    else:
        make_repo(cwd, *remotes)
    result = run_writer(ctx.tokens, cwd, "1028", "Мерджи #1028")
    assert result.returncode != 0 and "origin" in result.stderr
    assert tokens_left(ctx.tokens) == []


# --- generated probes: "once", "only that N", "only that repository" ---------------------------

def test_probe_each_token_allows_exactly_one_matching_merge(ctx, monkeypatch):
    guard = load_guard()
    monkeypatch.setenv("AGR_MERGE_TOKEN_DIR", str(ctx.tokens))
    monkeypatch.delenv("GH_REPO", raising=False)
    rng = random.Random(1028)
    numbers = rng.sample(range(1, 100000), 200)
    issued, others = numbers[:100], numbers[100:]
    for n in issued:
        put_token(ctx.tokens, n, command=f"Мерджи #{n}")
    allows = {n: 0 for n in issued}
    for n in others:
        assert guard.merge_token_allows(f"gh pr merge {n}", str(ctx.repo)) is None
    for _ in range(3):
        for n in issued:
            if guard.merge_token_allows(f"gh pr merge {n}", str(ctx.repo)):
                allows[n] += 1
    assert set(allows.values()) == {1}
    assert tokens_left(ctx.tokens) == []


SAME = ["artsafro/AGR-DigitalTwin-pilot", "ARTSAFRO/agr-digitaltwin-PILOT", "github.com/artsafro/AGR-DigitalTwin-pilot",
        "https://github.com/artsafro/AGR-DigitalTwin-pilot", "https://github.com/artsafro/AGR-DigitalTwin-pilot.git",
        "https://github.com/artsafro/AGR-DigitalTwin-pilot/", "git@github.com:artsafro/AGR-DigitalTwin-pilot.git",
        "ssh://git@github.com/artsafro/AGR-DigitalTwin-pilot.git", "ssh://git@github.com:22/artsafro/AGR-DigitalTwin-pilot"]
OTHER = ["artsafro/AGR-DigitalTwin", "artsafro/AGR-DigitalTwin-pilot2", "artsafro/xAGR-DigitalTwin-pilot",
         "other/AGR-DigitalTwin-pilot", "gitlab.com/artsafro/AGR-DigitalTwin-pilot",
         "git@gitlab.com:artsafro/AGR-DigitalTwin-pilot.git", "https://github.com/artsafro/AGR-DigitalTwin-pilot/x"]
BAD = ["", "  ", "artsafro", "a/b/c/d", "../x", "./.", "https://github.com/artsafro", "o/n?x", None, 5]


def test_probe_repo_normalization():
    guard = load_guard()
    assert {guard.normalize_repo(s) for s in SAME} == {REPO}
    assert REPO not in {guard.normalize_repo(s) for s in OTHER}
    assert [s for s in BAD if guard.normalize_repo(s) is not None] == []


def test_probe_repo_binding_by_flag(ctx, monkeypatch):
    """Every spelling of the token's repo allows (once); every other or bad repo asks and keeps the token."""
    guard = load_guard()
    monkeypatch.setenv("AGR_MERGE_TOKEN_DIR", str(ctx.tokens))
    monkeypatch.delenv("GH_REPO", raising=False)
    nogit = ctx.root / "nogit"
    nogit.mkdir()
    checked = 0
    for spec in OTHER + [s for s in BAD if isinstance(s, str) and s.strip()]:
        put_token(ctx.tokens, 5)
        assert guard.merge_token_allows(f"gh pr merge 5 -R {spec}", str(ctx.repo)) is None, spec
        assert tokens_left(ctx.tokens) == ["pr-5.json"], spec
        checked += 1
    for spec in SAME:
        put_token(ctx.tokens, 5)
        assert guard.merge_token_allows(f"gh pr merge 5 --repo {spec}", str(nogit)), spec
        assert guard.merge_token_allows(f"gh pr merge 5 --repo {spec}", str(nogit)) is None, spec
        checked += 1
    assert checked == len(OTHER) + len(SAME) + 6
