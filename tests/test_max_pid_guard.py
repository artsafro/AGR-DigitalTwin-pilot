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


def test_two_registrations():
    # Synthetic registry/PID source only: never imports or contacts a Max bridge.
    registry = {"selected": 563748, "pinned": 563748}
    for selected in [563748, 570920, 570920, 563748]:
        registry["selected"] = selected
        # A stale or even fresh selection is not an atomic execution identity check.
        denied(decision(MUTATION, selected_pid=registry["selected"], pinned_pid=registry["pinned"]))
        assert decision(GUARD + MUTATION) == {}
        # Simulated execution of the embedded guard prevents the wrong PID's mutation.
        changed = registry["selected"] == registry["pinned"]
        assert changed == (selected == 563748)


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


def test_generated_pid_probe():
    spec = importlib.util.spec_from_file_location("max_pid_gate_probe", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for pid in range(1, 101):
        for prefix, expected in [(GUARD.replace("563748", str(pid)), False), ("", True)]:
            result = module.check({"tool_name": "mcp__3dsmax-mcp__execute_maxscript",
                                   "tool_input": {"code": prefix + MUTATION}})
            assert bool(result) is expected
