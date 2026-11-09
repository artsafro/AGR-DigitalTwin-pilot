"""One-shot merge token in the PreToolUse guard (#1028, [D223]).

An explicit chat merge command naming PR N authorises exactly one `gh pr merge N`: the agent
quotes the command into a token for N (TTL 10 min); the guard allows only that N, once.
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

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / ".claude/hooks/guard.py"
TTL = 600


def load_guard():
    spec = importlib.util.spec_from_file_location("guard_under_test", GUARD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def env_for(token_dir):
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    env["AGR_MERGE_TOKEN_DIR"] = str(token_dir)
    return env


def run_guard(command, token_dir, protocol="claude"):
    if protocol == "antigravity":
        payload = {"toolCall": {"name": "run_command", "args": {"CommandLine": command}}}
    else:
        payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    result = subprocess.run([sys.executable, str(GUARD)], input=json.dumps(payload), capture_output=True,
                            text=True, encoding="utf-8", env=env_for(token_dir), cwd=ROOT)
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout) if result.stdout.strip() else {}
    if protocol == "antigravity":
        return out.get("decision"), out.get("reason", "")
    hso = out.get("hookSpecificOutput", {})
    return hso.get("permissionDecision", "none"), hso.get("permissionDecisionReason", "")


def put_token(token_dir, pr, command=None, created_at=None, raw=None, name=None):
    token_dir.mkdir(parents=True, exist_ok=True)
    path = token_dir / (name or f"pr-{pr}.json")
    if raw is not None:
        path.write_text(raw, encoding="utf-8")
        return path
    body = {"pr": pr, "command": command if command is not None else f"Мерджи #{pr}",
            "created_at": time.time() if created_at is None else created_at}
    path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    return path


def tokens_left(token_dir):
    return sorted(p.name for p in token_dir.glob("*")) if token_dir.exists() else []


# --- acceptance rows -------------------------------------------------------------------------

def test_token_for_n_allows_gh_pr_merge_n_once(tmp_path):
    put_token(tmp_path, 1028)
    decision, reason = run_guard("gh pr merge 1028 --merge", tmp_path)
    assert decision == "allow"
    assert "1028" in reason and "D223" in reason and "Мерджи #1028" in reason
    assert tokens_left(tmp_path) == []


def test_second_call_with_the_same_token_asks(tmp_path):
    put_token(tmp_path, 1028)
    assert run_guard("gh pr merge 1028", tmp_path)[0] == "allow"
    decision, reason = run_guard("gh pr merge 1028", tmp_path)
    assert decision == "ask"
    assert "merge command" in reason


def test_token_for_n_does_not_allow_other_pr_and_is_kept(tmp_path):
    put_token(tmp_path, 1028)
    assert run_guard("gh pr merge 1029", tmp_path)[0] == "ask"
    assert tokens_left(tmp_path) == ["pr-1028.json"]
    assert run_guard("gh pr merge 1028", tmp_path)[0] == "allow"


@pytest.mark.parametrize("age", [TTL, TTL + 1, 10 * TTL])
def test_expired_or_exactly_at_ttl_token_asks(tmp_path, age):
    put_token(tmp_path, 1028, created_at=time.time() - age)
    assert run_guard("gh pr merge 1028", tmp_path)[0] == "ask"


def test_no_token_asks(tmp_path):
    assert run_guard("gh pr merge 1028", tmp_path)[0] == "ask"
    assert run_guard("gh pr merge 1028", tmp_path / "missing-dir")[0] == "ask"


def test_antigravity_protocol_allows_once_then_asks(tmp_path):
    put_token(tmp_path, 7)
    assert run_guard("gh pr merge 7", tmp_path, "antigravity")[0] == "allow"
    assert run_guard("gh pr merge 7", tmp_path, "antigravity")[0] == "ask"


# --- fail-closed token contents ----------------------------------------------------------------

@pytest.mark.parametrize("token", [
    {"raw": ""},
    {"raw": "{not json"},
    {"raw": "[]"},
    {"raw": json.dumps({"pr": 1028, "command": "Мерджи #1028"})},              # no created_at
    {"raw": json.dumps({"pr": 1028, "created_at": time.time()})},                # no command
    {"raw": json.dumps({"command": "Мерджи #1028", "created_at": time.time()})},  # no pr
    {"command": "вперед"},                       # incident 7: no PR number in the command
    {"command": "Мерджи"},
    {"command": "Мерджи #10280"},                # names another PR
    {"command": "Мерджи #11028"},
    {"command": ""},
    {"command": 1028},
    {"created_at": time.time() + 120},           # from the future
    {"created_at": "now"},
    {"created_at": True},
    {"raw": '{"pr": 1028, "command": "Мерджи #1028", "created_at": NaN}'},
    {"raw": '{"pr": 1028, "command": "Мерджи #1028", "created_at": Infinity}'},
    {"raw": '{"pr": 1028, "command": "Мерджи #1028", "created_at": -Infinity}'},
    {"raw": json.dumps({"pr": 1029, "command": "Мерджи #1028", "created_at": time.time()})},  # pr mismatch
    {"raw": json.dumps({"pr": "1028", "command": "Мерджи #1028", "created_at": time.time()})},
    {"raw": json.dumps({"pr": True, "command": "Мерджи #1", "created_at": time.time()}), "pr": 1},
])
def test_invalid_token_asks(tmp_path, token):
    pr = token.pop("pr", 1028)
    put_token(tmp_path, pr, **token)
    assert run_guard(f"gh pr merge {pr}", tmp_path)[0] == "ask"


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
def test_command_outside_the_plain_merge_shape_asks_and_keeps_token(tmp_path, command):
    put_token(tmp_path, 1028)
    assert run_guard(command, tmp_path)[0] == "ask"
    assert tokens_left(tmp_path) == ["pr-1028.json"]


@pytest.mark.parametrize("command", [
    "gh pr merge 1028",
    "gh pr merge #1028 --squash",
    "gh.exe pr merge 1028 --merge",
    "gh pr merge 1028 --repo artsafro/AGR-DigitalTwin-pilot --merge",
    "gh -R artsafro/AGR-DigitalTwin-pilot pr merge 1028 -m",
    "  gh pr merge 1028 --rebase --auto  ",
])
def test_plain_merge_shapes_are_allowed_with_a_token(tmp_path, command):
    put_token(tmp_path, 1028)
    assert run_guard(command, tmp_path)[0] == "allow"


# --- token writer CLI ---------------------------------------------------------------------------

def run_writer(token_dir, *args):
    return subprocess.run([sys.executable, str(GUARD), "merge-token", *args], capture_output=True, text=True,
                          encoding="utf-8", env=env_for(token_dir), cwd=ROOT)


def test_writer_then_guard_dry_run(tmp_path):
    result = run_writer(tmp_path, "1028", "Мерджи #1028")
    assert result.returncode == 0, result.stderr
    data = json.loads((tmp_path / "pr-1028.json").read_text(encoding="utf-8"))
    assert data["pr"] == 1028 and data["command"] == "Мерджи #1028"
    assert math.isfinite(data["created_at"])
    assert run_guard("gh pr merge 1028", tmp_path)[0] == "allow"
    assert run_guard("gh pr merge 1028", tmp_path)[0] == "ask"


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
def test_writer_refuses_command_not_naming_the_pr(tmp_path, args):
    result = run_writer(tmp_path, *args)
    assert result.returncode != 0
    assert tokens_left(tmp_path) == []


# --- generated probe: "once" and "only that N" ---------------------------------------------------

def test_probe_each_token_allows_exactly_one_matching_merge(tmp_path, monkeypatch):
    guard = load_guard()
    monkeypatch.setenv("AGR_MERGE_TOKEN_DIR", str(tmp_path))
    rng = random.Random(1028)
    numbers = rng.sample(range(1, 100000), 200)
    issued, others = numbers[:100], numbers[100:]
    for n in issued:
        put_token(tmp_path, n, command=f"Мерджи #{n}")
    allows = {n: 0 for n in issued}
    for n in others:
        assert guard.merge_token_allows(f"gh pr merge {n}") is None
    for _ in range(3):
        for n in issued:
            if guard.merge_token_allows(f"gh pr merge {n}"):
                allows[n] += 1
    assert set(allows.values()) == {1}
    assert tokens_left(tmp_path) == []
