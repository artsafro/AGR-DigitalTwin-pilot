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


# --- Bare python / python3 advisory (#1034) ------------------------------------------------------------------

BLENDER_PY = '"C:/Program Files/Blender Foundation/Blender 4.4/4.4/python/bin/python.exe" x.py'
BARE = ["python x.py", 'python3 -c "print(1)"', "cd a && python b.py", "ls; python3 b.py", "echo x | python -",
        "FOO=1 python x.py", "python.exe x.py", "Python x.py", "(python x.py)", "echo $(python -c 1)",
        "echo `python -c 1`", "time python x.py", "a || python3 b.py", "git status\npython b.py",
        "if true; then python x.py; fi", "for f in a; do python3 $f; done", "  python", "x & python y.py",
        "env python x.py", "PYTHONPATH=src python3 -m pytest", r'echo \"; python x.py']
NOT_BARE = ["py -3 x.py", "uv run python x.py", ".venv/Scripts/python.exe -m pytest", BLENDER_PY,
            "rg python", 'echo "python x.py"', "git commit -m 'python x.py'", "ls python_tools/", "cat python.txt",
            "./python x.py", "pythonw x.py", "python3.13 x.py", "pytest -q", "mypython x.py", "",
            'py -3 -c "import os; python = 1"', "cat <<EOF\npython x.py\nEOF", "cat <<'END' >f\npython3 b\nEND",
            "# python x.py", "echo a # ; python x", r"echo \; python x", "uv run --with x python -m y",
            "grep -n 'a;python' f", "sed -n '1,2p' python3"]


@pytest.mark.parametrize("command", BARE)
def test_bare_python_is_flagged(command):
    assert _load_pretool().bare_python(command, "Bash")


@pytest.mark.parametrize("command", NOT_BARE)
def test_not_bare_python_is_not_flagged(command):
    assert not _load_pretool().bare_python(command, "Bash")


@pytest.mark.parametrize("command,flagged", [("& python x.py", True), ("python x.py; Get-Date", True),
                                             ("& 'C:/Python313/python.exe' x.py", False),
                                             ("Write-Host `\"python x`\"", False), ("py -3 x.py", False)])
def test_powershell_spellings(command, flagged):
    assert _load_pretool().bare_python(command, "PowerShell") is flagged


@pytest.mark.parametrize("value", [None, 7, ["python"], {"a": 1}])
def test_non_string_command_is_not_flagged(value):
    assert not _load_pretool().bare_python(value, "Bash")


def test_bare_python_gets_an_advisory_not_a_decision():
    got = call(PRETOOL, {"tool_name": "Bash", "tool_input": {"command": "python x.py"}, "cwd": str(ROOT)})
    out = decision(got)
    assert "permissionDecision" not in out                                # advisory only: never blocks or asks
    assert out["hookEventName"] == "PreToolUse"
    assert "py -3" in out["additionalContext"] and "docs/agents/CAPABILITIES.md" in out["additionalContext"]
    assert "py -3" in json.loads(got.stdout)["systemMessage"]


def test_powershell_bare_python_gets_the_advisory():
    got = call(PRETOOL, {"tool_name": "PowerShell", "tool_input": {"command": "python x.py"}, "cwd": str(ROOT)})
    assert "py -3" in decision(got)["additionalContext"]


def test_bare_python_with_a_guard_ask_keeps_the_ask_and_adds_the_advisory():
    payload = {"tool_name": "Bash", "tool_input": {"command": "python x.py && git push origin main"}, "cwd": str(ROOT)}
    out = decision(call(PRETOOL, payload))
    guard_out = decision(call(GUARD, payload))
    assert out["permissionDecision"] == "ask"
    assert out["permissionDecisionReason"] == guard_out["permissionDecisionReason"]
    assert "py -3" in out["additionalContext"]


@pytest.mark.parametrize("tool,tin", [("Bash", {"command": "py -3 x.py"}), ("Bash", {"command": "rg python"}),
                                      ("Write", {"file_path": str(ROOT / "a.md"), "content": "python x.py"}),
                                      ("Bash", {})])
def test_no_advisory_for_other_calls(tool, tin):
    got = call(PRETOOL, {"tool_name": tool, "tool_input": tin, "cwd": str(ROOT)})
    assert got.returncode == 0 and got.stdout == "", got.stdout


def test_repeated_bare_python_calls_warn_every_time():
    payload = {"tool_name": "Bash", "tool_input": {"command": "python x.py"}, "cwd": str(ROOT)}
    first, second = (call(PRETOOL, payload).stdout for _ in range(2))
    assert first and first == second


def test_shared_guard_stays_silent_on_bare_python():
    """Codex and the Pi adapter call guard.py directly and parse its decision strictly: it must not change."""
    got = call(GUARD, {"tool_name": "Bash", "tool_input": {"command": "python x.py"}, "cwd": str(ROOT)})
    assert got.returncode == 0 and got.stdout == ""


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


def test_prompt_dispatcher_acceptance_nudges_experience_transfer(tmp_path):
    payload = {"session_id": "s1", "hook_event_name": "UserPromptSubmit", "prompt": "Видны, принято"}
    r = subprocess.run([sys.executable, str(PROMPT)], input=json.dumps(payload), capture_output=True, text=True,
                       encoding="utf-8", env=_prompt_env(tmp_path / "u.jsonl"))
    assert r.returncode == 0, r.stderr
    assert "experience-transfer" in json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]


def test_prompt_dispatcher_acceptance_joins_context_warning(tmp_path):
    t = tmp_path / "s.jsonl"
    t.write_text(json.dumps(_response(150_000)) + "\n", encoding="utf-8")
    payload = {"session_id": "s1", "transcript_path": str(t), "hook_event_name": "UserPromptSubmit",
               "prompt": "все норм, спасибо"}
    r = subprocess.run([sys.executable, str(PROMPT)], input=json.dumps(payload), capture_output=True, text=True,
                       encoding="utf-8", env=_prompt_env(tmp_path / "u.jsonl"))
    text = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "strongly urge" in text and "experience-transfer" in text


@pytest.mark.parametrize("prompt", ["не принято, переделай", "ты перемудрил, отлично было бы проще"])
def test_prompt_dispatcher_rejection_does_not_nudge(prompt, tmp_path):
    payload = {"session_id": "s1", "hook_event_name": "UserPromptSubmit", "prompt": prompt}
    r = subprocess.run([sys.executable, str(PROMPT)], input=json.dumps(payload), capture_output=True, text=True,
                       encoding="utf-8", env=_prompt_env(tmp_path / "u.jsonl"))
    assert r.returncode == 0 and r.stdout == ""


@pytest.mark.parametrize("raw", ["not json", "[]", "{}", ""])
def test_prompt_dispatcher_bad_input_is_silent(raw, tmp_path):
    r = subprocess.run([sys.executable, str(PROMPT)], input=raw, capture_output=True, text=True,
                       env=_prompt_env(tmp_path / "u.jsonl"))
    assert r.returncode == 0 and r.stdout == ""
