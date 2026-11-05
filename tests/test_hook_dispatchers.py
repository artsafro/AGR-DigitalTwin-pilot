"""One-process hook dispatchers: .claude/hooks/pretool.py (guard + pipeline gate) and tools/hooks/prompt_hooks.py
(context_watch + usage_log prompt). Each must give the output its parts gave as separate hooks."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PRETOOL = ROOT / ".claude/hooks/pretool.py"
GUARD = ROOT / ".claude/hooks/guard.py"
GATE = ROOT / ".claude/hooks/pipeline_gate.py"
PROMPT = ROOT / "tools/hooks/prompt_hooks.py"
STATE_BUILT = "# J\n\n**Pipeline status:** built\n"


def call(script, payload, env=None, cwd=ROOT):
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"} | (env or {})
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run([sys.executable, str(script)], input=raw, capture_output=True, text=True,
                          encoding="utf-8", env=env, cwd=cwd)


def decision(result):
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["hookSpecificOutput"] if result.stdout.strip() else None


def test_guard_asks_gate_silent_gives_guard_output():
    payload = {"tool_name": "Bash", "tool_input": {"command": "git push origin main"}, "cwd": str(ROOT)}
    got = call(PRETOOL, payload)
    assert decision(got)["permissionDecision"] == "ask"
    assert got.stdout == call(GUARD, payload).stdout                     # exact shape and reason text
    assert call(GATE, payload).stdout == ""


def _job(tmp_path):
    (tmp_path / ".git").mkdir()
    return tmp_path / "jobs/J/STATE.md"


def test_gate_denies_gives_gate_output(tmp_path):
    target = _job(tmp_path)
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(target), "content": STATE_BUILT},
               "cwd": str(tmp_path)}
    got = call(PRETOOL, payload, cwd=tmp_path)
    assert decision(got)["permissionDecision"] == "deny"
    assert got.stdout == call(GATE, payload, cwd=tmp_path).stdout
    assert call(GUARD, payload, cwd=tmp_path).stdout == ""               # inside the session cwd


def test_gate_deny_beats_guard_ask(tmp_path):
    target = _job(tmp_path)
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(target), "content": STATE_BUILT}}
    env = {"TEMP": str(ROOT / "nonexistent-temp")}                       # tmp_path is outside every allowed root
    assert decision(call(GUARD, payload, env))["permissionDecision"] == "ask"
    got = call(PRETOOL, payload, env)
    assert decision(got)["permissionDecision"] == "deny"
    assert got.stdout == call(GATE, payload, env).stdout


def test_both_silent_gives_no_output():
    got = call(PRETOOL, {"tool_name": "Bash", "tool_input": {"command": "git status"}, "cwd": str(ROOT)})
    assert got.returncode == 0 and got.stdout == "" and got.stderr == ""


def _load_pretool():
    spec = importlib.util.spec_from_file_location("pretool_under_test", PRETOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_notebook_edit_skips_the_gate(monkeypatch):
    pretool = _load_pretool()
    ran = []
    monkeypatch.setattr(pretool, "run_part", lambda name, raw: (ran.append(name), ("", None))[1])
    pretool.dispatch(json.dumps({"tool_name": "NotebookEdit", "tool_input": {"notebook_path": "x.ipynb"}}))
    assert ran == ["guard.py"]
    ran.clear()
    pretool.dispatch(json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "x.md"}}))
    assert ran == ["guard.py", "pipeline_gate.py"]


def test_notebook_edit_on_a_production_asset_asks():
    payload = {"tool_name": "NotebookEdit", "tool_input": {"notebook_path": str(ROOT / "model.fbx")},
               "cwd": str(ROOT)}
    assert decision(call(PRETOOL, payload))["permissionDecision"] == "ask"


def test_an_error_in_one_part_keeps_the_other_decision(monkeypatch):
    pretool = _load_pretool()
    deny = json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                              "permissionDecisionReason": "x"}})
    parts = {"guard.py": ("", "Traceback: boom\n"), "pipeline_gate.py": (deny, None)}
    monkeypatch.setattr(pretool, "run_part", lambda name, raw: parts[name])
    assert pretool.dispatch(json.dumps({"tool_name": "Write", "tool_input": {}})) == (deny, "", 0)
    parts["pipeline_gate.py"] = ("", None)                               # no decision: the error is reported
    out, err, code = pretool.dispatch(json.dumps({"tool_name": "Write", "tool_input": {}}))
    assert (out, code) == ("", 1) and "boom" in err


@pytest.mark.parametrize("raw", ["not json", "", "{}"])
def test_bad_input_mirrors_the_parts(raw):
    got = call(PRETOOL, raw)
    assert got.returncode == 0 and got.stdout == ""


def test_non_dict_input_errors_like_the_guard():
    """guard.py raises on a JSON list (exit 1, a non-blocking hook error); the dispatcher reports it the same way."""
    assert call(GUARD, "[]").returncode == 1
    got = call(PRETOOL, "[]")
    assert got.returncode == 1 and got.stdout == "" and "AttributeError" in got.stderr


# --- UserPromptSubmit ---------------------------------------------------------------------------------------

def _response(tokens):
    return {"type": "assistant", "message": {"id": "m", "model": "claude-opus-4-6",
            "content": [{"type": "text", "text": "ok"}],
            "usage": {"input_tokens": 2, "cache_creation_input_tokens": 1000,
                      "cache_read_input_tokens": tokens - 1002, "output_tokens": 50}}}


def _prompt_env(log):
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE_CODE_")}
    return env | {"AGR_USAGE_LOG": str(log), "CLAUDE_PROJECT_DIR": str(ROOT)}


def test_prompt_dispatcher_logs_and_warns(tmp_path):
    t = tmp_path / "s.jsonl"
    t.write_text(json.dumps(_response(150_000)) + "\n", encoding="utf-8")
    log = tmp_path / "logs/u.jsonl"
    payload = {"session_id": "s1", "transcript_path": str(t), "hook_event_name": "UserPromptSubmit",
               "prompt": "/handover"}
    r = subprocess.run([sys.executable, str(PROMPT)], input=json.dumps(payload), capture_output=True, text=True,
                       encoding="utf-8", env=_prompt_env(log))
    assert r.returncode == 0, r.stderr
    assert "strongly urge" in json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
    rows = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
    assert [(x["kind"], x["name"], x["session_id"]) for x in rows] == [("command", "handover", "s1")]


def test_prompt_dispatcher_plain_prompt_is_silent(tmp_path):
    log = tmp_path / "u.jsonl"
    payload = {"session_id": "s1", "hook_event_name": "UserPromptSubmit", "prompt": "go on"}
    r = subprocess.run([sys.executable, str(PROMPT)], input=json.dumps(payload), capture_output=True, text=True,
                       encoding="utf-8", env=_prompt_env(log))
    assert r.returncode == 0 and r.stdout == "" and not log.exists()


@pytest.mark.parametrize("raw", ["not json", "[]", "{}", ""])
def test_prompt_dispatcher_bad_input_is_silent(raw, tmp_path):
    r = subprocess.run([sys.executable, str(PROMPT)], input=raw, capture_output=True, text=True,
                       env=_prompt_env(tmp_path / "u.jsonl"))
    assert r.returncode == 0 and r.stdout == ""
