"""new-case: independent synthetic census oracles and no-clobber research output."""
import json
import subprocess
import sys


def test_measure_separates_routes_polls_repeats():
    from tools.research.dcc_code_mode_measure import measure
    calls = [("mcp__3dsmax-mcp__list_max_instances", {}),
             ("mcp__3dsmax-mcp__list_max_instances", {}),
             ("mcp__3dsmax-mcp__select_max_instance", {"pid": 7}),
             ("mcp__blender__execute_blender_code", {"code": "pass"})]
    result = measure(calls)
    assert {k: result["max"][k] for k in ("calls", "polls", "exact_repeats", "repeated_polls")} == {
        "calls": 3, "polls": 2, "exact_repeats": 1, "repeated_polls": 1}
    assert result["blender"]["calls"] == 1
    assert result["revit"]["calls"] == 0


def test_calls_deduplicate_replayed_tool_ids():
    from tools.research.dcc_code_mode_measure import calls_from
    event = {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t",
             "name": "mcp__revit-http-2025__revit_ping", "input": {}}]}}
    assert len(calls_from(json.dumps(event) + "\n" + json.dumps(event))) == 1


def test_output_alias_fresh_cli(tmp_path):
    inventory = tmp_path / "inventory.csv"
    content = b"source,title\n"
    inventory.write_bytes(content)
    run = subprocess.run([sys.executable, "-m", "tools.research.dcc_code_mode_measure", "--out", str(inventory),
                          "--inventory", str(inventory)], capture_output=True, text=True)
    assert run.returncode != 0
    assert inventory.read_bytes() == content
    assert sorted(p.name for p in tmp_path.iterdir()) == ["inventory.csv"]
