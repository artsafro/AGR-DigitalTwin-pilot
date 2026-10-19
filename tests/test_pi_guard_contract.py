"""Review regressions: current Pi schema, full-result gates and path policy.

Installed-Pi checks are read-only or use in-memory operations (never write
outside the synthetic project). No dependency on Pi is needed for core tests.
"""
import itertools
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from test_pi_guard_adapter import ROOT, invoke, sandbox  # noqa: F401 (shared fixture)


@pytest.mark.parametrize("absolute,reverse,kind", list(itertools.product(
    [False, True], [False, True], ["status", "locked-status", "locked-check"])))
def test_current_multi_edit_combines_paths_and_pipeline(sandbox, absolute, reverse, kind):
    pipeline = sandbox / "jobs/J/pipeline"
    pipeline.mkdir(parents=True)
    if kind != "status":
        failure = {"item": "module:M01", "kind": "checker", "cause": "code", "detail": "bbox off"}
        (pipeline / "state.json").write_text(json.dumps({"failures": [failure, failure], "stops": []}))
    if kind == "locked-check":
        target = pipeline / "check.json"
        before = '{"passed": false, "note": "alpha"}'
        edits = [{"oldText": "false", "newText": "true"}, {"oldText": "alpha", "newText": "beta"}]
    else:
        target = pipeline.parent / "STATE.md"
        before = "Pipeline marker: draft\nNote: alpha\n"
        edits = [{"oldText": "marker", "newText": "status"}, {"oldText": "draft", "newText": "built"}]
    target.write_bytes(before.encode())
    if reverse:
        edits.reverse()
    rel = target.relative_to(sandbox).as_posix()
    adapter = sandbox / "tools/hooks/pi_guard_adapter.py"
    result = invoke("edit", {"path": str(target) if absolute else rel, "edits": edits}, sandbox, adapter)
    assert result["decision"] == "block", result
    assert "pipeline_gate:" in result["reason"]
    assert target.read_bytes() == before.encode()
    # Safe real-schema control, even while another job is locked.
    note = sandbox / "note.txt"
    note.write_bytes(b"alpha beta")
    assert invoke("edit", {"path": str(note) if absolute else "note.txt", "edits": [
        {"oldText": "alpha", "newText": "gamma"}, {"oldText": "beta", "newText": "delta"},
    ]}, sandbox, adapter)["decision"] == "allow"
    assert invoke("bash", {"command": "git status"}, sandbox, adapter)["decision"] == "allow"
    assert invoke("bash", {"command": "git reset --hard HEAD"}, sandbox, adapter)["decision"] == "block"
    # Same dangerous current-schema edit cannot bypass by using Pi path syntax.
    for raw in ("@" + str(target), target.as_uri(), "@" + rel):
        decision = invoke("edit", {"path": raw, "edits": edits}, sandbox, adapter)
        assert decision["decision"] == "block", (raw, decision)


def test_claude_aliases_cannot_hide_current_pi_status_edit(sandbox):
    path = sandbox / "jobs/J/STATE.md"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"Pipeline status: draft\n")
    result = invoke("edit", {"path": "jobs/J/STATE.md", "edits": [
        {"oldText": "draft", "newText": "built"}],
        "old_string": "Pipeline status", "new_string": "Ignored label",
    }, sandbox, sandbox / "tools/hooks/pi_guard_adapter.py")
    assert result["decision"] == "block", result


@pytest.mark.parametrize("edits", [
    [], None, 2, "not-json", [None], [{"oldText": "", "newText": "x"}],
    [{"oldText": "alpha", "newText": None}],
    [{"oldText": "missing", "newText": "x"}],
    [{"oldText": "alpha", "newText": "alpha"}],
    [{"oldText": "alpha", "newText": "x"}, {"oldText": "lph", "newText": "y"}],
])
def test_malformed_or_unpreviewable_edits_block(sandbox, edits):
    (sandbox / "note.txt").write_bytes(b"alpha beta")
    result = invoke("edit", {"path": "note.txt", "edits": edits}, sandbox,
                    sandbox / "tools/hooks/pi_guard_adapter.py")
    assert result["decision"] == "block", result


def test_fuzzy_only_edit_is_explicitly_blocked(sandbox):
    (sandbox / "note.txt").write_bytes("smart ‘quote’\n".encode("utf-8"))
    result = invoke("edit", {"path": "note.txt", "edits": [
        {"oldText": "smart 'quote'", "newText": "replacement"},
    ]}, sandbox, sandbox / "tools/hooks/pi_guard_adapter.py")
    assert result["decision"] == "block"
    assert "fuzzy-only edits are unsupported" in result["reason"]


@pytest.mark.parametrize("tool", ["edit", "write"])
def test_generated_unicode_path_spellings_block(sandbox, tool):
    # Entire space class normalized by installed Pi, not just the two examples.
    spaces = [0xA0, *range(0x2000, 0x200B), 0x202F, 0x205F, 0x3000]
    for char in spaces:
        result = invoke(tool, {"path": "a" + chr(char) + "b.txt", "content": "x",
                              "edits": [{"oldText": "a", "newText": "b"}]}, sandbox,
                        sandbox / "tools/hooks/pi_guard_adapter.py")
        assert result["decision"] == "block", (char, result)
        assert "unsupported Pi path syntax" in result["reason"]


@pytest.fixture
def installed_pi():
    node = os.environ.get("PI_GUARD_TEST_NODE") or shutil.which("node")
    pi = shutil.which("pi")
    configured = os.environ.get("PI_GUARD_TEST_PI_TOOLS")
    tools = Path(configured) if configured else (Path(pi).parent / "node_modules/@earendil-works/pi-coding-agent/dist/core/tools" if pi else Path("missing"))
    if not node or not (tools / "edit.js").is_file():
        pytest.skip("installed Pi and Node required for independent protocol oracle")
    return node, tools


@pytest.mark.parametrize("before,edits", [
    ("alpha\nbeta\n", [{"oldText": "alpha", "newText": "beta"}, {"oldText": "beta", "newText": "gamma"}]),
    ("\ufeffalpha\r\nbeta\r\n", [{"oldText": "alpha\nbeta", "newText": "gamma\ndelta"}]),
    ("alpha\rbeta\n", [{"oldText": "alpha", "newText": "gamma"}]),
    ("alpha 😀 beta", [{"oldText": "beta", "newText": "omega"}, {"oldText": "😀", "newText": "😎"}]),
    ("alpha beta", {"oldText": "alpha", "newText": "gamma"}),
    ("alpha beta", '[{"oldText":"alpha","newText":"gamma"}]'),
])
def test_preview_equals_actual_installed_pi(sandbox, installed_pi, before, edits):
    node, tools = installed_pi
    # Actual Pi executes against an in-memory filesystem. Capture the resulting
    # text, then require BOTH unchanged hook entrypoints to see exactly that text.
    script = '''import {createEditToolDefinition} from EDIT;
let saved;
const tool = createEditToolDefinition(process.cwd(), {operations:{
 access:async()=>{},readFile:async()=>Buffer.from(BEFORE),writeFile:async(p,c)=>{saved=c}
}});
let args={path:"note.txt",edits:EDITS};
args=tool.prepareArguments(args);
await tool.execute("synthetic",args);
console.log(JSON.stringify(saved));'''.replace("EDIT", json.dumps((tools / "edit.js").as_uri()), 1)
    script = script.replace("BEFORE", json.dumps(before)).replace("EDITS", json.dumps(edits))
    actual = json.loads(subprocess.check_output([node, "--input-type=module", "-e", script], text=True, encoding="utf-8"))
    (sandbox / "note.txt").write_bytes(before.encode("utf-8"))
    check = f'''import json, sys
p=json.load(sys.stdin)
assert p['tool_name']=='Edit'
assert p['tool_input']['new_string']=={actual!r}
'''
    for name in ("guard.py", "pipeline_gate.py"):
        (sandbox / ".claude/hooks" / name).write_text(check, encoding="utf-8")
    result = invoke("edit", {"path": "note.txt", "edits": edits}, sandbox, sandbox / "tools/hooks/pi_guard_adapter.py")
    assert result["decision"] == "allow", result
    assert (sandbox / "note.txt").read_bytes() == before.encode("utf-8")


@pytest.mark.parametrize("tool", ["write", "edit"])
def test_special_outside_paths_match_installed_pi_policy(sandbox, installed_pi, tool):
    node, tools = installed_pi
    outside = Path.home() / "agr-pi-synthetic-outside.txt"
    spellings = ["~/agr-pi-synthetic-outside.txt", "@" + outside.as_posix(), outside.as_uri()]
    if os.name == "nt":
        suffix = outside.as_posix()[2:]
        spellings += [prefix + outside.drive[0].lower() + suffix for prefix in ("/", "/mnt/", "/cygdrive/")]
    for raw in spellings:
        script = 'import {resolveToCwd} from ' + json.dumps((tools / "path-utils.js").as_uri()) + '; console.log(JSON.stringify(resolveToCwd(' + json.dumps(raw) + ',' + json.dumps(str(sandbox)) + ')));'
        actual = json.loads(subprocess.check_output([node, "--input-type=module", "-e", script], text=True))
        assert Path(actual) == outside
        payload = {"tool_name": "Write" if tool == "write" else "Edit", "cwd": str(sandbox),
                   "tool_input": {"file_path": actual, "content": "synthetic", "old_string": "a", "new_string": "b"}}
        direct = json.loads(subprocess.check_output(
            [sys.executable, str(sandbox / ".claude/hooks/guard.py")],
            input=json.dumps(payload), text=True, cwd=sandbox,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(sandbox)}))
        assert direct["hookSpecificOutput"]["permissionDecision"] == "ask"
        result = invoke(tool, {"path": raw, "content": "synthetic", "edits": [
            {"oldText": "a", "newText": "b"}]}, sandbox, sandbox / "tools/hooks/pi_guard_adapter.py")
        assert result["decision"] == "block", (raw, result)
        assert "unsupported Pi path syntax" in result["reason"]


@pytest.mark.parametrize("tool", ["write", "edit"])
def test_supported_paths_equal_installed_pi_targets(sandbox, installed_pi, tool):
    node, tools = installed_pi
    target = sandbox / "note.txt"
    target.write_bytes(b"alpha beta")
    for raw in ("note.txt", "./note.txt", "sub/../note.txt", str(target), target.as_posix()):
        script = 'import {resolveToCwd} from ' + json.dumps((tools / "path-utils.js").as_uri()) + '; console.log(JSON.stringify(resolveToCwd(' + json.dumps(raw) + ',' + json.dumps(str(sandbox)) + ')));'
        actual = json.loads(subprocess.check_output([node, "--input-type=module", "-e", script], text=True))
        check = f'''import json, sys
p=json.load(sys.stdin)
assert p['tool_input']['file_path']=={str(Path(actual).resolve())!r}
'''
        for name in ("guard.py", "pipeline_gate.py"):
            (sandbox / ".claude/hooks" / name).write_text(check, encoding="utf-8")
        result = invoke(tool, {"path": raw, "content": "gamma", "edits": [
            {"oldText": "alpha", "newText": "gamma"}]}, sandbox, sandbox / "tools/hooks/pi_guard_adapter.py")
        assert result["decision"] == "allow", (raw, result)
