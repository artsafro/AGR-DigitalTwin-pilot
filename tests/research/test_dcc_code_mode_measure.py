"""new-case: independent synthetic census oracles and no-clobber research output."""
import json
import subprocess
import sys
import os

import pytest


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


def test_poll_aliases_exclude_dialog_writes():
    from tools.research.dcc_code_mode_measure import measure
    result = measure([("mcp__3dsmax-mcp__max_dialogs", {"action": "respond"}),
                      ("mcp__max-ultra-mcp__max_list_instances", {}),
                      ("mcp__3dsmax-mcp__get_selected_max_instance", {})])
    assert result["max"]["calls"] == 3
    assert result["max"]["polls"] == 2


def test_calls_deduplicate_replayed_tool_ids():
    from tools.research.dcc_code_mode_measure import calls_from
    event = {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t",
             "name": "mcp__revit-http-2025__revit_ping", "input": {}}]}}
    assert len(calls_from(json.dumps(event) + "\n" + json.dumps(event))) == 1


def test_context_refs_are_not_tool_calls():
    from tools.research.dcc_code_mode_measure import context_refs
    event = {"type": "user", "message": {"content": [{"type": "tool_result", "content": [
        {"type": "tool_reference", "tool_name": "mcp__3dsmax-mcp__query_scene"},
        {"type": "tool_reference", "tool_name": "mcp__3dsmax-mcp__query_scene"},
        {"type": "tool_reference", "tool_name": "mcp__blender__execute_blender_code"}]}]}}
    refs = context_refs(json.dumps(event))
    assert refs == {"max": ["query_scene"], "blender": ["execute_blender_code"], "revit": []}


@pytest.mark.parametrize("alias", ["scene.jsonl", "./scene.jsonl", "hardlink.jsonl",
    pytest.param("SCENE.jsonl", marks=pytest.mark.skipif(os.name != "nt", reason="Windows case alias"))])
def test_duplicate_inventory_alias_rejected(tmp_path, alias):
    source = tmp_path / "scene.jsonl"
    source.write_text('{}\n', encoding="utf-8")
    if alias == "hardlink.jsonl":
        (tmp_path / alias).hardlink_to(source)
    inventory = tmp_path / "inventory.csv"
    inventory.write_text('source,title\nscene.jsonl,one\n' + alias + ',two\n', encoding="utf-8")
    output = tmp_path / "new-output"
    run = subprocess.run([sys.executable, "-m", "tools.research.dcc_code_mode_measure", "--out", str(output),
                          "--root", str(tmp_path), "--inventory", str(inventory)], capture_output=True, text=True)
    assert run.returncode != 0
    assert "duplicate transcript" in run.stderr
    assert not output.exists() and source.read_text(encoding="utf-8") == '{}\n'


def test_output_alias_fresh_cli(tmp_path):
    inventory = tmp_path / "inventory.csv"
    content = b"source,title\n"
    inventory.write_bytes(content)
    run = subprocess.run([sys.executable, "-m", "tools.research.dcc_code_mode_measure", "--out", str(inventory),
                          "--inventory", str(inventory)], capture_output=True, text=True)
    assert run.returncode != 0
    assert inventory.read_bytes() == content
    assert sorted(p.name for p in tmp_path.iterdir()) == ["inventory.csv"]
