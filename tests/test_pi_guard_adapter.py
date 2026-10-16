"""Exercise the Pi adapter's public JSON stdin/stdout boundary."""
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "tools/hooks/pi_guard_adapter.py"


def invoke(tool="bash", tin=None, cwd=ROOT, adapter=ADAPTER):
    result = subprocess.run(
        [sys.executable, str(adapter)],
        input=json.dumps({"tool": tool, "input": tin or {"command": "git status"}, "cwd": str(cwd)}),
        capture_output=True, text=True, encoding="utf-8", cwd=cwd,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_destructive_command_is_blocked():
    result = invoke(tin={"command": "git reset --hard HEAD"})
    assert result["decision"] == "block"
    assert "git reset --hard discards work" in result["reason"]


def test_shim_executes_real_hooks(tmp_path):
    # Node's native TS loader exercises the shipped shim, not a rewritten copy.
    node = os.environ.get("PI_GUARD_TEST_NODE") or shutil.which("node")
    version = subprocess.check_output([node, "--version"], text=True) if node else "v0"
    if not shutil.which("py") or tuple(map(int, re.findall(r"\d+", version)[:2])) < (22, 18):
        pytest.skip("py launcher and Node >=22.18 required for native TypeScript test")
    assert node is not None
    script = tmp_path / "shim.mjs"
    script.write_text('''
import guard from "''' + (ROOT / ".pi/extensions/agr-guard.ts").as_uri() + '''";
let handler;
guard({on: (event, fn) => { if (event === "tool_call") handler = fn; }});
const ctx = {cwd: ''' + json.dumps(str(ROOT)) + '''};
const allowed = await handler({toolName:"bash",input:{command:"git status"}},ctx);
const blocked = await handler({toolName:"bash",input:{command:"git reset --hard HEAD"}},ctx);
if (allowed !== undefined || !blocked.block || !blocked.reason.includes("discards work"))
  throw new Error(JSON.stringify({allowed,blocked}));
console.log("shim: allow status; block reset");
''', encoding="utf-8")
    result = subprocess.run([node, str(script)], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert "shim: allow status; block reset" in result.stdout


@pytest.fixture
def sandbox(tmp_path):
    """Synthetic project; real hooks stay byte-identical to Claude's hooks."""
    for rel in ("tools/hooks/pi_guard_adapter.py", ".claude/hooks/guard.py",
                ".claude/hooks/pipeline_gate.py", "tools/git-hooks/pipeline_gate.py",
                "tools/git-hooks/branch_names.py"):
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, dest)
    return tmp_path


def test_status_is_allowed():
    assert invoke()["decision"] == "allow"


@pytest.mark.parametrize("tool", ["write", "edit"])
@pytest.mark.parametrize("path", [
    "~/outside.txt", "~\\outside.txt", "@C:/outside.txt", "@@outside.txt",
    "file:///C:/outside.txt", "/c/outside.txt", "/mnt/c/outside.txt",
    "/cygdrive/c/outside.txt", "name\u202fspace.txt", "name\u00a0space.txt",
])
def test_pi_special_paths_fail_closed(sandbox, tool, path):
    if os.name != "nt" and path.startswith("/"):
        pytest.skip("Windows shell drive spellings are ordinary absolute paths on POSIX")
    tin = {"path": path, "content": "synthetic", "oldText": "old", "newText": "new"}
    result = invoke(tool, tin, sandbox, sandbox / "tools/hooks/pi_guard_adapter.py")
    assert result["decision"] == "block", (path, result)
    assert "unsupported Pi path syntax" in result["reason"]


@pytest.mark.parametrize("absolute", [False, True])
def test_current_pi_multi_edit_checks_complete_result(sandbox, absolute):
    path = sandbox / "note.txt"
    before = "alpha\nbeta\n"
    after = "beta\ngamma\n"  # matched in ORIGINAL, not sequentially
    path.write_bytes(before.encode("utf-8"))
    check = f'''import json, sys
p = json.load(sys.stdin)
assert p['tool_name'] == 'Edit'
assert p['tool_input']['old_string'] == {before!r}
assert p['tool_input']['new_string'] == {after!r}
assert not p['tool_input'].get('replace_all')
'''
    for name in ("guard.py", "pipeline_gate.py"):
        (sandbox / ".claude/hooks" / name).write_text(check, encoding="utf-8")
    result = invoke("edit", {"path": str(path) if absolute else "note.txt", "edits": [
        {"oldText": "alpha", "newText": "beta"},
        {"oldText": "beta", "newText": "gamma"},
    ]}, sandbox, sandbox / "tools/hooks/pi_guard_adapter.py")
    assert result["decision"] == "allow", result
    assert path.read_text(encoding="utf-8") == before  # preview never writes


@pytest.mark.parametrize("source", [
    "raise RuntimeError('synthetic adapter crash')",
    "print('null')", "print('{}')", "print('not json')",
    "print('{\"decision\":\"unknown\",\"reason\":\"x\"}')",
    "print('{\"decision\":\"allow\"}'); raise RuntimeError('after output')",
])
def test_generated_shim_failures_never_allow(sandbox, source):
    node = os.environ.get("PI_GUARD_TEST_NODE") or shutil.which("node")
    version = subprocess.check_output([node, "--version"], text=True) if node else "v0"
    if not shutil.which("py") or tuple(map(int, re.findall(r"\d+", version)[:2])) < (22, 18):
        pytest.skip("py launcher and Node >=22.18 required")
    assert node is not None
    dest = sandbox / ".pi/extensions/agr-guard.ts"
    dest.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / ".pi/extensions/agr-guard.ts", dest)
    (sandbox / "tools/hooks/pi_guard_adapter.py").write_text(source, encoding="utf-8")
    script = sandbox / "shim.mjs"
    script.write_text('''
import guard from "''' + dest.as_uri() + '''";
let handler;
guard({on: (_event, fn) => { handler = fn; }});
const ctx = {cwd: ''' + json.dumps(str(sandbox)) + '''};
const result = await handler({toolName:"bash",input:{command:"git status"}},ctx);
if (!result?.block || !result.reason) throw new Error(JSON.stringify(result));
const ignored = await handler({toolName:"read",input:{}},ctx);
if (ignored !== undefined) throw new Error("out-of-scope tool intercepted");
''', encoding="utf-8")
    result = subprocess.run([node, str(script)], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("name", ["guard.py", "pipeline_gate.py"])
def test_hook_timeout_blocks(sandbox, name, monkeypatch):
    monkeypatch.setenv("PI_GUARD_HOOK_TIMEOUT_SECONDS", "1")
    (sandbox / ".claude/hooks" / name).write_text("import time; time.sleep(30)", encoding="utf-8")
    result = invoke(cwd=sandbox, adapter=sandbox / "tools/hooks/pi_guard_adapter.py")
    assert result["decision"] == "block"
    assert "TimeoutExpired" in result["reason"]


def test_production_timeout_defaults(monkeypatch):
    monkeypatch.delenv("PI_GUARD_HOOK_TIMEOUT_SECONDS", raising=False)
    import runpy
    import dt_ai.core.run_record
    assert runpy.run_path(str(ADAPTER))["HOOK_TIMEOUT_SECONDS"] == 10
    assert dt_ai.core.run_record.CLEANUP_GRACE_SECONDS == 5


@pytest.mark.parametrize("tool,claude,tin,expected", [
    ("bash", "Bash", {"command": "git status"}, {"command": "git status"}),
    ("powershell", "PowerShell", {"command": "git status"}, {"command": "git status"}),
    ("write", "Write", {"path": "a.txt", "content": "hello"}, {"content": "hello"}),
    ("edit", "Edit", {"path": "a.txt", "oldText": "old", "newText": "new"},
     {"old_string": "old", "new_string": "new"}),
    ("edit", "Edit", {"path": "a.txt", "edits": [{"oldText": "old", "newText": "new"}]},
     {"old_string": "old", "new_string": "new"}),
])
def test_names_fields_cwd_and_project_root_match_claude(sandbox, tool, claude, tin, expected):
    if tool == "edit":
        (sandbox / "a.txt").write_text("old", encoding="utf-8")
    settings = json.loads((ROOT / ".claude/settings.json").read_text())
    entries = settings["hooks"]["PreToolUse"][:2]
    assert all(re.fullmatch(entry["matcher"], claude) for entry in entries)
    check = f'''import json, os, sys
p = json.load(sys.stdin)
assert p['tool_name'] == {claude!r}
assert p['hook_event_name'] == 'PreToolUse'
assert p['cwd'] == {str(sandbox)!r}
assert os.environ['CLAUDE_PROJECT_DIR'] == {str(sandbox)!r}
for k,v in {expected!r}.items(): assert p['tool_input'][k] == v
'''
    if tool in ("write", "edit"):
        check += f"assert p['tool_input']['file_path'] == {str(sandbox / 'a.txt')!r}\n"
    for name in ("guard.py", "pipeline_gate.py"):
        (sandbox / ".claude/hooks" / name).write_text(check, encoding="utf-8")
    assert invoke(tool, tin, sandbox, sandbox / "tools/hooks/pi_guard_adapter.py")["decision"] == "allow"


@pytest.mark.parametrize("path", ["data/note.txt", "data/source.blend"])
def test_data_write_matches_claude_guard(sandbox, path):
    tin = {"file_path": str(sandbox / path), "content": "synthetic"}
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(sandbox)}
    direct = subprocess.run([sys.executable, str(sandbox / ".claude/hooks/guard.py")],
                            input=json.dumps({"tool_name": "Write", "tool_input": tin, "cwd": str(sandbox)}),
                            text=True, capture_output=True, cwd=sandbox, env=env)
    expected = "block" if direct.stdout.strip() else "allow"
    assert invoke("write", {"path": path, "content": "synthetic"}, sandbox,
                  sandbox / "tools/hooks/pi_guard_adapter.py")["decision"] == expected


@pytest.mark.parametrize("tool,tin", [
    ("bash", {"command": "uv run dt build --job jobs/J"}),
    ("powershell", {"command": "uv run dt build --job jobs/J"}),
    ("write", {"path": "jobs/J/STATE.md", "content": "Pipeline status: built\n"}),
    ("edit", {"path": "jobs/J/STATE.md", "oldText": "draft", "newText": "built"}),
])
def test_pipeline_blocks_locked_job(sandbox, tool, tin):
    pipeline = sandbox / "jobs/J/pipeline"
    pipeline.mkdir(parents=True)
    (pipeline.parent / "STATE.md").write_text("Pipeline status: draft\n")
    failure = {"item": "module:M01", "kind": "checker", "cause": "code", "detail": "bbox off"}
    (pipeline / "state.json").write_text(json.dumps({"failures": [failure, failure], "stops": []}))
    result = invoke(tool, tin, sandbox, sandbox / "tools/hooks/pi_guard_adapter.py")
    assert result["decision"] == "block"
    assert "pipeline_gate:" in result["reason"]


@pytest.mark.parametrize("name", ["guard.py", "pipeline_gate.py"])
@pytest.mark.parametrize("source", [
    "raise RuntimeError('synthetic crash')",
    "print('not json')",
    "print('{}')",
    "print('[]')",
    "print('{\"hookSpecificOutput\":{\"permissionDecision\":\"unexpected\"}}')",
    "print('{\"hookSpecificOutput\":{\"permissionDecision\":\"allow\"}}'); raise RuntimeError('after allow')",
    "import sys; sys.exit(2)",
    None,
])
def test_generated_hook_failures_never_allow(sandbox, name, source):
    hook = sandbox / ".claude/hooks" / name
    if source is None:
        hook.unlink()
    else:
        hook.write_text(source, encoding="utf-8")
    result = invoke(cwd=sandbox, adapter=sandbox / "tools/hooks/pi_guard_adapter.py")
    assert result["decision"] == "block"
    assert result["reason"]


@pytest.mark.parametrize("name", ["guard.py", "pipeline_gate.py"])
@pytest.mark.parametrize("decision", ["allow", "deny", "ask"])
def test_explicit_decisions(sandbox, name, decision):
    output = {"hookSpecificOutput": {"permissionDecision": decision, "permissionDecisionReason": "synthetic reason"}}
    (sandbox / ".claude/hooks" / name).write_text(f"print({json.dumps(output)!r})", encoding="utf-8")
    result = invoke(cwd=sandbox, adapter=sandbox / "tools/hooks/pi_guard_adapter.py")
    assert result["decision"] == ("allow" if decision == "allow" else "block")
    if decision != "allow":
        assert result["reason"] == "synthetic reason"


@pytest.mark.parametrize("raw", ["", "null", "[]", "{}", "not json",
    '{"tool":"read","input":{},"cwd":"."}',
    '{"tool":"bash","input":{"command":null},"cwd":"."}',
    '{"tool":"edit","input":{"path":"x","oldText":null,"newText":""},"cwd":"."}',
])
def test_generated_malformed_calls_never_allow(raw):
    result = subprocess.run([sys.executable, str(ADAPTER)], input=raw,
                            capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    assert result.returncode == 0
    assert json.loads(result.stdout)["decision"] == "block"
