"""new-case: fail-closed, stateless Max MCP mutation PID admission."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "tools/hooks/skill_gate.py"
MUTATION = '(LayerManager.getLayerFromName "revit").on = false'
GUARD = ('local pc = dotNetClass "System.Diagnostics.Process"; '
         'if (pc.GetCurrentProcess()).Id != 563748 do throw "wrong Max"; ')


def decision(code=None, tool="execute_maxscript", **extra):
    payload = {"tool_name": "mcp__3dsmax-mcp__" + tool,
               "tool_input": {"code": code}, **extra}
    result = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout)["hookSpecificOutput"] if result.stdout else {}


def denied(result):
    assert result.get("permissionDecision") == "deny", result
    assert "PID" in result["permissionDecisionReason"]


def test_mutation_requires_guard():
    denied(decision(MUTATION))


def test_guarded_mutation():
    assert decision(GUARD + MUTATION) == {}


@pytest.mark.parametrize("code", ["objects.count", "selection.count", "maxFileName", "getSaveRequired()"])
def test_read_only(code):
    assert decision(code) == {}


def test_two_registrations(monkeypatch):
    # Synthetic registry/PID source only: never imports or contacts a Max bridge.
    import os
    registry = {"selected": 563748, "pinned": 563748}
    script = ('import os\nif os.getpid() != 563748:\n'
              '    raise RuntimeError("wrong Max")\nchanged.append(os.getpid())')
    for selected in [563748, 570920, 570920, 563748]:
        registry["selected"] = selected
        monkeypatch.setattr(os, "getpid", lambda: registry["selected"])
        # A stale or even fresh selection is not an atomic execution identity check.
        denied(decision(MUTATION, selected_pid=registry["selected"], pinned_pid=registry["pinned"]))
        assert decision(GUARD + MUTATION) == {}
        assert decision(script, tool="execute_python") == {}
        changed = []
        if selected == registry["pinned"]:
            exec(script, {"changed": changed})
            assert changed == [563748]
        else:
            with pytest.raises(RuntimeError, match="wrong Max"):
                exec(script, {"changed": changed})
            assert changed == []


@pytest.mark.parametrize("code", [None, "", " ", 123, [], {}, "NaN", "inf", "foo()"])
def test_fail_closed(code):
    denied(decision(code))


@pytest.mark.parametrize("prefix", [
    "-- " + GUARD + "\n", 'format "%" ' + json.dumps(GUARD) + '; ',
    "/* " + GUARD + " */ ", "if false do (" + GUARD + "); ",
    "try (" + GUARD + ") catch(); ", MUTATION + "; " + GUARD,
    GUARD.replace("563748", "0"), GUARD.replace("563748", "-1"),
    GUARD.replace("563748", "563748.0"), GUARD.replace("!=", "=="),
    GUARD.replace("throw", "format"), GUARD.replace("pc.GetCurrentProcess", "other.GetCurrentProcess"),
])
def test_fake_guards(prefix):
    denied(decision(prefix + MUTATION))


def test_subagent():
    denied(decision(MUTATION, agent_id="reader", transcript_path="missing.jsonl"))


@pytest.mark.parametrize("tool", ["scene_patch", "manage_scene", "create_object", "unknown_mutation"])
def test_native_mutations(tool):
    denied(decision(GUARD + MUTATION, tool=tool))


def test_python():
    denied(decision("rt.delete(rt.objects)", tool="execute_python"))
    assert decision('import os\nif os.getpid() != 563748:\n    raise RuntimeError("wrong Max")\n'
                    'rt.delete(rt.objects)', tool="execute_python") == {}


@pytest.mark.parametrize("value", [None, [], "code", {"script": MUTATION}, {"code": None}])
def test_partial_tool_input(value):
    denied(decision(tool_input=value))


@pytest.mark.parametrize("args", [{"action": []}, {"action": {}}, {"action": "class"},
                                 {"action": "property"}, {}, {"action": "overview; delete objects"}])
def test_query_fail_closed(args):
    denied(decision(tool="query_scene", tool_input=args))


@pytest.mark.parametrize("tool,args", [
    ("query_scene", {"action": "overview"}), ("query_scene", {"action": "selection"}),
    ("get_selected_max_instance", {}), ("select_max_instance", {"pid": 563748}),
    ("list_max_instances", {}),
])
def test_routing_and_inspection(tool, args):
    assert decision(tool=tool, tool_input=args) == {}


@pytest.mark.parametrize("prefix", ["# fake\n", "try:\n    ", "if False:\n    ", "print("])
def test_fake_python_guard(prefix):
    denied(decision(prefix + 'import os\nif os.getpid() != 563748:\n'
                    '    raise RuntimeError("wrong Max")\nrt.delete(rt.objects)', tool="execute_python"))


def test_skill_load_still_required(tmp_path):
    transcript = tmp_path / "empty.jsonl"
    transcript.write_text("", encoding="utf-8")
    result = decision(GUARD + MUTATION, transcript_path=str(transcript), session_id="pid-test")
    assert result["permissionDecision"] == "deny"
    assert "Skill tool" in result["permissionDecisionReason"]


def test_pid_docs_and_mirror():
    skill = (ROOT / ".agents/skills/3dsmax-mcp-dev/SKILL.md").read_text(encoding="utf-8")
    assert 'if (pc.GetCurrentProcess()).Id !=' in skill
    assert "guard every mutation" in skill
    assert (ROOT / ".claude/skills/3dsmax-mcp-dev/SKILL.md").read_bytes() == (
        ROOT / ".agents/skills/3dsmax-mcp-dev/SKILL.md").read_bytes()
    capabilities = (ROOT / "docs/agents/CAPABILITIES.md").read_text(encoding="utf-8")
    assert "pinning does not hold; guard every mutation" in capabilities
    assert "Live two-Max re-registration test: NOT DONE" in capabilities


@pytest.mark.parametrize("capture", [True, "false", 1, [], {}])
def test_inspect_mesh_capture_needs_guard(capture):
    denied(decision(tool="inspect_mesh", tool_input={"capture": capture}))


def test_command_alias_is_not_guard_evidence():
    denied(decision(tool_input={"command": MUTATION}))
    denied(decision(tool_input={"command": GUARD + MUTATION}))


def test_generated_pid_probe():
    spec = importlib.util.spec_from_file_location("max_pid_gate_probe", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for pid in range(1, 101):
        for prefix, expected in [(GUARD.replace("563748", str(pid)), False), ("", True)]:
            result = module.check({"tool_name": "mcp__3dsmax-mcp__execute_maxscript",
                                   "tool_input": {"code": prefix + MUTATION}})
            assert bool(result) is expected
