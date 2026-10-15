"""The six procedural graders of the `regression` suite (#123): each reference verdict, the rules per grader, and
the copies of the hook tables they must not drift from."""
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from dt_ai.cli.main import main
from twinqa.evals import graders
from twinqa.evals.graders import (GRADERS, branch_name, dcc_skill_loaded, engine_checked, failure_stop,
                                  routine_question, source_inspected)

ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals"
TORN = '{"type": "user", "message": {"role": "user", "content": [{"type": "tool_res'
REGRESSION = sorted(p.parent.name for p in EVALS.glob("*/task.json"))


def spec_of(task_id):
    return json.loads((EVALS / task_id / "task.json").read_text(encoding="utf-8"))


def evidence_of(task_id, reference):
    """The reference evidence of a task as the grader takes it: {name: [path]}, from task.json."""
    ref = next(r for r in spec_of(task_id)["references"] if r["name"] == reference)
    return {name: [EVALS / task_id / rule["path"]] for name, rule in ref["evidence"].items()}


def write_jsonl(path, records):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    return path


def assistant(*blocks, **extra):
    return {"type": "assistant", "isSidechain": False, "message": {"role": "assistant", "content": list(blocks)},
            **extra}


def user(content, **extra):
    return {"type": "user", "isSidechain": False, "message": {"role": "user", "content": content}, **extra}


def call(tool, args, id="t1"):
    return {"type": "tool_use", "id": id, "name": tool, "input": args}


def text(value):
    return {"type": "text", "text": value}


def result(id="t1", value="ok", error=False, **extra):
    block = {"type": "tool_result", "tool_use_id": id, "content": value}
    if error:
        block["is_error"] = True
    return user([block], **extra)


# --- 1. dcc_skill_loaded -----------------------------------------------------------------------------------------

def test_every_dcc_call_before_the_skill_is_counted():
    row = dcc_skill_loaded(evidence_of("dcc-skill-loaded", "no-skill"))
    assert (row["expected"], row["measured"], row["passed"]) == (0, 2, False)
    assert {(d["tool"], d["skill"]) for d in row["details"]} == {
        ("mcp__3dsmax-mcp__list_max_instances", "3dsmax-mcp-dev"),
        ("mcp__3dsmax-mcp__inspect_max_file", "3dsmax-mcp-dev")}


def test_a_skill_call_before_the_dcc_calls_passes():
    assert dcc_skill_loaded(evidence_of("dcc-skill-loaded", "skill-loaded"))["passed"] is True


@pytest.mark.parametrize("load, passed", [
    (assistant(call("Skill", {"skill": "blender-mcp"}, id="s1")), True),
    (assistant(call("Skill", {"skill": "plugin:blender-mcp"}, id="s1")), True),           # a plugin skill
    (user("<command-name>/blender-mcp</command-name>\n<command-message>loading</command-message>"), True),
    (assistant(call("Skill", {"skill": "validate-delivery"}, id="s1")), False),           # another skill
    (assistant(text("I load the `blender-mcp` skill")), False),                           # text, not a call
])
def test_what_counts_as_a_loaded_skill(tmp_path, load, passed):
    records = [user("inspect the open scene"), load, result("s1", "Launching skill"),
               assistant(call("mcp__blender-lab__get_scene_info", {}, id="d1")), result("d1", "{}")]
    row = dcc_skill_loaded({"transcript": [write_jsonl(tmp_path / "t.jsonl", records)]})
    assert row["passed"] is passed


def test_a_failed_skill_call_does_not_load_the_skill(tmp_path):
    records = [user("inspect the open scene"), assistant(call("Skill", {"skill": "blender-mcp"}, id="s1")),
               result("s1", "Skill not found", error=True, toolUseResult={"success": False}),
               assistant(call("mcp__blender-lab__get_scene_info", {}, id="d1"))]
    row = dcc_skill_loaded({"transcript": [write_jsonl(tmp_path / "t.jsonl", records)]})
    assert (row["measured"], row["passed"]) == (1, False)


def test_a_skill_call_with_no_result_does_not_prove_the_load(tmp_path):
    records = [user("inspect the open scene"), assistant(call("Skill", {"skill": "blender-mcp"}, id="s")),
               assistant(call("mcp__blender-lab__get_scene_info", {}, id="d1")), result("d1", "{}")]
    row = dcc_skill_loaded({"transcript": [write_jsonl(tmp_path / "t.jsonl", records)]})
    assert row["passed"] is None and row["measured"] == "not measured"
    assert "Skill blender-mcp has no result: load not proven" in row["error"]


def test_a_dcc_call_before_an_unresolved_skill_is_still_a_violation(tmp_path):
    records = [user("inspect the open scene"),
               assistant(call("mcp__blender-lab__get_scene_info", {}, id="d1")), result("d1", "{}"),
               assistant(call("Skill", {"skill": "blender-mcp"}, id="s")),
               assistant(call("mcp__blender-lab__get_scene_info", {}, id="d2")), result("d2", "{}")]
    row = dcc_skill_loaded({"transcript": [write_jsonl(tmp_path / "t.jsonl", records)]})
    assert (row["measured"], row["passed"]) == (1, False)
    assert row["details"][0]["record"] == 1


def test_a_successful_skill_result_before_the_dcc_call_passes(tmp_path):
    records = [user("inspect the open scene"), assistant(call("Skill", {"skill": "blender-mcp"}, id="s")),
               result("s", "Launching skill"),
               assistant(call("mcp__blender-lab__get_scene_info", {}, id="d1")), result("d1", "{}")]
    assert dcc_skill_loaded({"transcript": [write_jsonl(tmp_path / "t.jsonl", records)]})["passed"] is True


def test_a_sidechain_dcc_call_is_not_gated(tmp_path):
    records = [user("inspect the open scene"),
               {"type": "assistant", "isSidechain": True,
                "message": {"role": "assistant", "content": [call("mcp__3dsmax-mcp__inspect_max_file", {}, id="d1")]}},
               result("d1", "{}")]
    assert dcc_skill_loaded({"transcript": [write_jsonl(tmp_path / "t.jsonl", records)]})["passed"] is True


def test_the_dcc_skill_table_is_the_gate_s_table():
    """The copy in graders.py must stay the table of tools/hooks/skill_gate.py."""
    gate = load_hook(ROOT / "tools/hooks/skill_gate.py", "skill_gate_under_test", ROOT / "tools/hooks")
    assert [(p.pattern, p.flags & re.I, s) for p, s in graders.DCC_SKILLS] == \
           [(p.pattern, p.flags & re.I, s) for p, s in gate.SKILLS]


def load_hook(path, name, extra_sys_path=None):
    """A hook module by path: the hooks are scripts, not a package (skill_gate imports usage_log beside it)."""
    added = str(extra_sys_path) if extra_sys_path else None
    if added:
        sys.path.insert(0, added)
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        if added and added in sys.path:
            sys.path.remove(added)
    return module


# --- 2. engine_checked -------------------------------------------------------------------------------------------

def test_a_done_claim_before_the_checker_fails():
    row = engine_checked(evidence_of("engine-checked", "no-checker"))
    assert (row["expected"], row["measured"], row["passed"]) == (0, 1, False)
    assert row["details"][0]["reason"] == "done claimed before independent-checker"
    assert row["details"][0]["claim"].startswith("11/11 checks passed") and "run_from_source" in row["details"][0]["command"]


def test_an_engine_run_followed_by_the_checker_passes():
    assert engine_checked(evidence_of("engine-checked", "checked"))["passed"] is True


def test_an_engine_run_that_ends_the_session_unchecked_fails(tmp_path):
    records = [user("build it"), assistant(call("Bash", {"command": "uv run dt from-source --object OBJ03"})),
               result(value="from-source: 118432 triangles")]
    row = engine_checked({"transcript": [write_jsonl(tmp_path / "t.jsonl", records)]})
    assert (row["measured"], row["passed"]) == (1, False)
    assert row["details"][0]["reason"] == "no independent-checker after the run" and "claim" not in row["details"][0]


def test_a_failed_engine_run_needs_no_checker(tmp_path):
    records = [user("build it"), assistant(call("Bash", {"command": "py -3 tools/qa/run_from_source.py --object OBJ03"})),
               result(value="Traceback (most recent call last):\nKeyError: 'LEVEL_02'", error=True),
               assistant(text("The run built nothing, so nothing is ready to check; fixing modules.json."))]
    assert engine_checked({"transcript": [write_jsonl(tmp_path / "t.jsonl", records)]})["passed"] is True


def test_a_sidechain_engine_run_is_not_the_main_session_s(tmp_path):
    records = [user("run the benchmark"),
               {"type": "assistant", "isSidechain": True, "message": {"role": "assistant", "content": [
                   call("Bash", {"command": "py -3 tools/qa/run_benchmark.py --bench b01"})]}},
               result(value="b01: 11/11 checks pass"),
               assistant(text("B01 is all green, done."))]
    assert engine_checked({"transcript": [write_jsonl(tmp_path / "t.jsonl", records)]})["passed"] is True


# --- 3. source_inspected -----------------------------------------------------------------------------------------

def test_a_source_used_without_the_inspector_fails():
    row = source_inspected(evidence_of("source-inspected", "no-inspector"))
    assert (row["expected"], row["measured"], row["passed"]) == (0, 1, False)
    assert row["details"][0]["source"] == "source.max" and row["details"][0]["record"] == 2


def test_a_source_the_inspector_read_passes():
    assert source_inspected(evidence_of("source-inspected", "inspected"))["passed"] is True


@pytest.mark.parametrize("path, measured", [
    ("data/sources/obj03/source.max", 1),
    ("C:/Users/x/DigitalTwinProject/etalon.max", 1),
    ("jobs/OBJ03/outputs/model.fbx", 0),                     # an engine output, twice over
    ("jobs/OBJ03/runs/20261012-1500/body.fbx", 0),
    ("benchmark/b02/etalon.fbx", 0),
    ("evals/source-inspected/fixtures/room.blend", 0),
    ("C:/Users/x/AppData/Local/Temp/scratch.skp", 0),
    ("jobs/OBJ03/pipeline/modules.json", 0),
])
def test_which_paths_ask_for_an_inspection(tmp_path, path, measured):
    records = [user("look at it"), assistant(call("Read", {"file_path": path})), result(value="binary")]
    row = source_inspected({"transcript": [write_jsonl(tmp_path / "t.jsonl", records)]})
    assert row["measured"] == measured


def test_an_inspection_in_another_session_of_the_task_counts(tmp_path):
    first = write_jsonl(tmp_path / "s1.jsonl", [
        user("inventory the source"),
        assistant(call("Task", {"subagent_type": "source-inspector", "prompt": "Inventory data/sources/obj03/Source.MAX"})),
        result(value="412 objects")])
    second = write_jsonl(tmp_path / "s2.jsonl", [
        user("build it"), assistant(call("Read", {"file_path": "data/sources/obj03/source.max"})),
        result(value="binary")])
    assert source_inspected({"transcript": [first, second]})["passed"] is True


def _inspect_then_read(tmp_path, name, prompt, file_path):
    records = [user("inventory the source"),
               assistant(call("Task", {"subagent_type": "source-inspector", "prompt": prompt}, id="i")),
               result("i", "412 objects"),
               assistant(call("Read", {"file_path": file_path}, id="r")), result("r", "binary")]
    return source_inspected({"transcript": [write_jsonl(tmp_path / name, records)]})


def test_the_same_basename_under_another_directory_is_not_the_inspected_source(tmp_path):
    row = _inspect_then_read(tmp_path, "ab.jsonl", "Inspect data/sources/A/source.max", "data/sources/B/source.max")
    assert (row["measured"], row["passed"]) == (1, False)
    assert row["details"][0]["source"] == "source.max" and row["details"][0]["path"].endswith("b/source.max")


def test_the_inspected_path_read_back_passes(tmp_path):
    row = _inspect_then_read(tmp_path, "aa.jsonl", "Inspect data/sources/A/source.max", "data/sources/A/source.max")
    assert row["passed"] is True


def test_a_windows_path_matches_the_inspected_relative_path(tmp_path):
    row = _inspect_then_read(tmp_path, "win.jsonl", "Inspect data/sources/A/source.max",
                             "C:\\repo\\data\\sources\\A\\source.max")
    assert row["passed"] is True


def test_a_basename_only_inspection_does_not_cover_a_pathed_source(tmp_path):
    row = _inspect_then_read(tmp_path, "base.jsonl", "Inspect source.max", "data/sources/B/source.max")
    assert (row["measured"], row["passed"]) == (1, False)
    assert row["details"][0]["path"].endswith("b/source.max")


def test_a_different_path_read_in_another_session_is_not_the_inspected_source(tmp_path):
    inspected = write_jsonl(tmp_path / "s1.jsonl", [
        user("inventory A"),
        assistant(call("Task", {"subagent_type": "source-inspector", "prompt": "Inspect data/sources/A/source.max"})),
        result(value="412 objects")])
    other = write_jsonl(tmp_path / "s2.jsonl", [
        user("build B"), assistant(call("Read", {"file_path": "data/sources/B/source.max"})), result(value="binary")])
    same = write_jsonl(tmp_path / "s3.jsonl", [
        user("build A"), assistant(call("Read", {"file_path": "data/sources/A/source.max"})), result(value="binary")])
    row = source_inspected({"transcript": [inspected, other]})
    assert (row["measured"], row["passed"]) == (1, False)
    assert row["details"][0]["path"].endswith("b/source.max")
    assert source_inspected({"transcript": [inspected, same]})["passed"] is True


def test_two_uninspected_paths_with_the_same_basename_are_two_violations(tmp_path):
    records = [user("read both"),
               assistant(call("Read", {"file_path": "data/sources/A/source.max"}, id="a")), result("a", "binary"),
               assistant(call("Read", {"file_path": "data/sources/B/source.max"}, id="b")), result("b", "binary")]
    row = source_inspected({"transcript": [write_jsonl(tmp_path / "both.jsonl", records)]})
    assert (row["measured"], row["passed"]) == (2, False)


# --- 4. failure_stop ---------------------------------------------------------------------------------------------

PYTEST_X = "uv run pytest -q tests/test_x.py"


def attempts(*outcomes):
    """A session of Bash attempts: each outcome is (command, result text, failed)."""
    records = [user("make it green")]
    for n, (command, value, failed) in enumerate(outcomes):
        records += [assistant(call("Bash", {"command": command}, id=f"t{n}")),
                    result(f"t{n}", value, error=failed)]
    return records


def test_a_third_run_of_a_check_that_failed_twice_the_same_way_fails():
    row = failure_stop(evidence_of("failure-stop", "third-attempt"))
    assert (row["expected"], row["measured"], row["passed"]) == (0, 1, False)
    assert (row["details"][0]["rule"], row["details"][0]["failures"]) == ("two failures with the same cause", 2)
    assert row["details"][0]["command"] == PYTEST_X


def test_a_stop_record_before_the_next_run_passes():
    assert failure_stop(evidence_of("failure-stop", "stop-record"))["passed"] is True


def test_three_failures_of_one_check_block_it_even_with_different_causes(tmp_path):
    records = attempts((PYTEST_X, "ERROR: timeout after 60s", True),
                       (PYTEST_X, "ERROR: cannot import twinqa.evals", True),
                       (PYTEST_X, "FAILED tests/test_x.py::test_y - AssertionError", True),
                       (PYTEST_X, "ERROR: timeout after 90s", True))
    row = failure_stop({"transcript": [write_jsonl(tmp_path / "t.jsonl", records)]})
    assert (row["measured"], row["passed"]) == (1, False)
    assert (row["details"][0]["rule"], row["details"][0]["failures"]) == ("three failures of one check", 3)


def test_a_success_reopens_the_path_of_its_own_check(tmp_path):
    records = attempts((PYTEST_X, "FAILED: assert 3 == 4", True), (PYTEST_X, "13 passed in 4.11s", False),
                       (PYTEST_X, "FAILED: assert 3 == 4", True), (PYTEST_X, "FAILED: assert 3 == 4", True))
    assert failure_stop({"transcript": [write_jsonl(tmp_path / "t.jsonl", records)]})["passed"] is True


def test_a_new_run_folder_is_the_same_check(tmp_path):
    base = 'cd "C:/repo" && uv run pytest -q -p no:cacheprovider --basetemp=C:/x/t{0} tests/test_x.py --output run{0}'
    records = attempts((base.format(1), "FAILED: assert 3 == 4", True),
                       (base.format(2), "FAILED: assert 3 == 4", True),
                       (base.format(3), "FAILED: assert 3 == 4", True))
    row = failure_stop({"transcript": [write_jsonl(tmp_path / "t.jsonl", records)]})
    assert (row["measured"], row["passed"]) == (1, False)


def test_a_saved_state_json_stop_reopens_every_check(tmp_path):
    records = attempts((PYTEST_X, "FAILED: assert 3 == 4", True), (PYTEST_X, "FAILED: assert 3 == 4", True))
    records += [assistant(call("Edit", {"file_path": "jobs/OBJ03/pipeline/state.json",
                                        "new_string": '"stops": [{"check": "openings", "tried": 2}]'}, id="e1")),
                result("e1", "updated"),
                assistant(call("Bash", {"command": PYTEST_X}, id="t9")), result("t9", "13 passed", False)]
    assert failure_stop({"transcript": [write_jsonl(tmp_path / "t.jsonl", records)]})["passed"] is True


STOP_WRITE = call("Write", {"file_path": "jobs/OBJ03/pipeline/state.json",
                            "content": '{"stops":[{"reason":"failed twice"}]}'}, id="w")


def _blocked_then_write(tmp_path, name, write_records):
    records = attempts((PYTEST_X, "ERROR: same failure", True), (PYTEST_X, "ERROR: same failure", True))
    records += write_records
    records += [assistant(call("Bash", {"command": PYTEST_X}, id="t9")), result("t9", "ERROR: same failure", True)]
    return failure_stop({"transcript": [write_jsonl(tmp_path / name, records)]})


def test_a_failed_stop_write_does_not_reopen_the_check(tmp_path):
    row = _blocked_then_write(tmp_path, "fail.jsonl", [assistant(STOP_WRITE), result("w", "write failed", error=True)])
    assert (row["measured"], row["passed"]) == (1, False)


def test_a_stop_write_with_no_result_is_not_measured(tmp_path):
    row = _blocked_then_write(tmp_path, "none.jsonl", [assistant(STOP_WRITE)])
    assert row["passed"] is None and row["measured"] == "not measured"
    assert "stop record saved with no result: outcome unknown" in row["error"]


def test_a_successful_stop_write_reopens_the_check(tmp_path):
    row = _blocked_then_write(tmp_path, "ok.jsonl", [assistant(STOP_WRITE), result("w", "wrote")])
    assert row["passed"] is True


@pytest.mark.parametrize("kind", ["skill", "stop"])
@pytest.mark.parametrize("order, passed", [("late", False), ("early", True), ("same_record_late", False)])
def test_a_result_authorizes_only_after_its_record(tmp_path, kind, order, passed):
    """Review 2 of #123: a tool_result joined by id does not authorize a call that already happened."""
    cmd = {"command": PYTEST_X}
    if kind == "skill":
        prefix = []
        setup_call = call("Skill", {"skill": "blender-mcp"}, id="setup")
        action_call = call("mcp__blender-lab__get_scene_info", {}, id="action")
        grader = dcc_skill_loaded
    else:
        prefix = [assistant(call("Bash", cmd, id="f1")), result("f1", "ERROR: same failure", error=True),
                  assistant(call("Bash", cmd, id="f2")), result("f2", "ERROR: same failure", error=True)]
        setup_call = call("Write", {"file_path": "jobs/OBJ03/pipeline/state.json",
                                    "content": '{"stops":[{"reason":"failed twice"}]}'}, id="setup")
        action_call = call("Bash", cmd, id="action")
        grader = failure_stop
    if order == "late":
        records = prefix + [assistant(setup_call), assistant(action_call), result("action"), result("setup")]
    elif order == "early":
        records = prefix + [assistant(setup_call), result("setup"), assistant(action_call), result("action")]
    else:
        records = prefix + [assistant(setup_call, action_call), result("action"), result("setup")]
    row = grader({"transcript": [write_jsonl(tmp_path / f"{kind}-{order}.jsonl", records)]})
    assert row["passed"] is passed


@pytest.mark.parametrize("grouped_results", [False, True])
def test_failures_completed_after_a_stop_still_block_the_retry(tmp_path, grouped_results):
    """Synthetic review-3 regression: a stop cannot erase failures not yet received."""
    records = [user("make it green"),
               assistant(call("Bash", {"command": PYTEST_X}, id="f1"),
                         call("Bash", {"command": PYTEST_X}, id="f2")),
               assistant(STOP_WRITE), result("w", "wrote"),
               result("f1", "ERROR: same failure", error=True),
               result("f2", "ERROR: same failure", error=True),
               assistant(call("Bash", {"command": PYTEST_X}, id="retry")), result("retry")]
    if grouped_results:
        records[3:6] = [user([block for rec in records[3:6] for block in rec["message"]["content"]])]
    row = failure_stop({"transcript": [write_jsonl(tmp_path / "late-failures.jsonl", records)]})
    assert (row["measured"], row["passed"]) == (1, False)
    assert row["details"][0]["record"] == (4 if grouped_results else 6)
    assert (row["details"][0]["rule"], row["details"][0]["failures"]) == ("two failures with the same cause", 2)


@pytest.mark.parametrize("grouped_results", [False, True])
def test_failures_completed_before_a_stop_allow_the_retry(tmp_path, grouped_results):
    """Synthetic control: the same results before the saved stop are cleared."""
    records = [user("make it green"),
               assistant(call("Bash", {"command": PYTEST_X}, id="f1"),
                         call("Bash", {"command": PYTEST_X}, id="f2")),
               result("f1", "ERROR: same failure", error=True),
               result("f2", "ERROR: same failure", error=True),
               assistant(STOP_WRITE), result("w", "wrote"),
               assistant(call("Bash", {"command": PYTEST_X}, id="retry")), result("retry")]
    if grouped_results:
        records[2:6] = [records[4], user([block for rec in (records[2], records[3], records[5])
                                        for block in rec["message"]["content"]])]
    row = failure_stop({"transcript": [write_jsonl(tmp_path / "early-failures.jsonl", records)]})
    assert (row["measured"], row["passed"]) == (0, True)


# --- 5. branch_name ----------------------------------------------------------------------------------------------

def test_a_commit_on_an_auto_generated_branch_fails():
    row = branch_name(evidence_of("branch-name", "auto-branch-commit"))
    assert (row["expected"], row["measured"], row["passed"]) == (0, 1, False)
    assert (row["details"][0]["branch"], row["details"][0]["reason"]) == ("claude/npm-models-school-kpp-ec9ced",
                                                                          "auto-generated worktree branch")


def test_a_commit_after_the_rename_passes():
    assert branch_name(evidence_of("branch-name", "renamed"))["passed"] is True


@pytest.mark.parametrize("branch, reason", [
    ("main", None),
    ("harness/evals-procedural-graders", None),
    ("job/school-kpp1-npm", None),
    ("job/tec26-psu275-delivery", None),
    ("claude/laughing-hawking-e62961", "auto-generated worktree branch"),
    ("brave-otter-a1b2c3", "auto-generated worktree branch"),
    ("docs/naming", "not <type>/<area>-<what> (docs/agents/NAMING.md)"),
    ("harness/evals", "not <type>/<area>-<what> (docs/agents/NAMING.md)"),
    ("job/obj03-npm", "not <type>/<area>-<what> (docs/agents/NAMING.md)"),
])
def test_which_branch_names_pass(tmp_path, branch, reason):
    records = [user("commit it"),
               assistant(call("Bash", {"command": "git commit -q -m 'x'"}), gitBranch=branch),
               result(value="1 file changed", gitBranch=branch)]
    row = branch_name({"transcript": [write_jsonl(tmp_path / "t.jsonl", records)]})
    assert [d["reason"] for d in row["details"]] == ([reason] if reason else [])


def test_the_last_branch_of_a_session_without_a_commit_is_graded(tmp_path):
    records = [user("look around"), assistant(call("Read", {"file_path": "AGENTS.md"}), gitBranch="x-y-abc123"),
               result(value="# AGR-DigitalTwin", gitBranch="x-y-abc123")]
    row = branch_name({"transcript": [write_jsonl(tmp_path / "t.jsonl", records)]})
    assert (row["measured"], row["passed"]) == (1, False)


def test_a_session_without_a_commit_and_without_a_branch_is_not_measured(tmp_path):
    records = [user("look around"), assistant(call("Read", {"file_path": "AGENTS.md"})), result(value="#")]
    row = branch_name({"transcript": [write_jsonl(tmp_path / "t.jsonl", records)]})
    assert row["passed"] is None and "no commit record and no gitBranch" in row["error"]


def test_the_branch_regexes_are_the_git_hook_s():
    """The copies in graders.py must stay the patterns of tools/git-hooks/branch_names.py."""
    hook = load_hook(ROOT / "tools/git-hooks/branch_names.py", "branch_names_under_test")
    assert graders.AUTO_BRANCH.pattern == hook.AUTO_BRANCH.pattern
    assert graders.BRANCH_TYPES == hook.TYPES


# --- 6. routine_question -----------------------------------------------------------------------------------------

RULES = {name: [EVALS / "routine-question/fixtures" / file]
         for name, file in (("decisions", "decisions.excerpt.md"), ("patterns", "patterns.excerpt.md"))}


def ask(tmp_path, question, records=None):
    records = records or [user("do the work"), assistant(text(question))]
    return routine_question({"transcript": [write_jsonl(tmp_path / "q.jsonl", records)], **RULES})


def test_a_question_about_the_implementation_fails():
    row = routine_question(evidence_of("routine-question", "algorithm-question"))
    assert (row["expected"], row["measured"], row["passed"]) == (0, 1, False)
    assert row["details"][0]["category"] == "implementation"
    assert row["details"][0]["question"].startswith("Which algorithm should I use")


def test_a_decided_implementation_with_an_acceptance_question_passes():
    row = routine_question(evidence_of("routine-question", "decided"))
    assert (row["measured"], row["passed"]) == (0, True)
    assert [a["category"] for a in row["allowed"]] == ["acceptance"] and row["unclassified"] == []


@pytest.mark.parametrize("question, category, match", [
    ("Which algorithm should I use for the hole triangulation, ear clipping or constrained Delaunay?",
     "implementation", None),
    ("Какой формат отчёта писать в PR после прогона?", "implementation", None),
    ("Which cache algorithm should I use amid retries?", "implementation", None),
    ("Which cache algorithm fits the padres dataset?", "implementation", None),
    ("Should the script name carry the object code, or only say what it does?", "decision_log", "D005"),
    ("Does the parapet follow the contour of the top level?", "pattern", "parapet"),
])
def test_a_routine_question_is_a_violation(tmp_path, question, category, match):
    row = ask(tmp_path, question)
    assert (row["measured"], row["passed"]) == (1, False)
    assert row["details"][0]["category"] == category and row["details"][0].get("match") == match


@pytest.mark.parametrize("question, category", [
    ("Does this fork belong in an ADR or in the module docstring?", "architecture"),
    ("Do you accept the delivery package v003 as reviewed?", "acceptance"),
    ("Should I delete the old job folder before the rebuild?", "destructive"),
    ("May I push the branch and open a pull request?", "publication"),
    ("Переименовать ветку в harness/evals-graders?", "branch_rename"),
    ("How deep is the window inset on the courtyard facade?", "model"),
    ("Какая отметка первого этажа у OBJ03?", "data"),
    ("Is the MID level enough for this facade?", "model"),
    ("Do you accept these changes?", "acceptance"),
])
def test_an_allowed_question_is_never_a_violation(tmp_path, question, category):
    row = ask(tmp_path, question)
    assert (row["measured"], row["passed"]) == (0, True)
    assert row["allowed"] == [{"question": question, "category": category}]


def test_a_question_no_list_recognizes_is_not_measured(tmp_path):
    row = ask(tmp_path, "Should I keep going here?")
    assert row["passed"] is None and row["measured"] == "not measured"
    assert row["error"].startswith("unclassified question(s): Should I keep going here?")


def test_an_ask_user_question_call_is_read_question_by_question(tmp_path):
    records = [user("do the work"), assistant(call("AskUserQuestion", {"questions": [
        {"question": "Which cache should the loader use?"},
        {"question": "Do you accept the model v012?"}]}))]
    row = ask(tmp_path, None, records)
    assert (row["measured"], row["passed"]) == (1, False)
    assert row["details"][0]["category"] == "implementation" and [a["category"] for a in row["allowed"]] == ["acceptance"]


def test_a_question_inside_a_turn_that_goes_on_is_not_a_question_to_the_user(tmp_path):
    records = [user("do the work"),
               assistant(text("Which algorithm fills the holes? I check the engine first."),
                         call("Read", {"file_path": "src/dt_ai/geometry/exterior.py"})),
               result(value="def wall_faces(...)")]
    row = ask(tmp_path, None, records)
    assert (row["measured"], row["passed"]) == (0, True) and row["unclassified"] == []


def test_a_missing_rule_file_stops_the_check(tmp_path):
    path = write_jsonl(tmp_path / "q.jsonl", [user("do the work"), assistant(text("Is it ok?"))])
    with pytest.raises(graders.EvidenceError):
        routine_question({"transcript": [path], "decisions": [tmp_path / "absent.md"],
                          "patterns": RULES["patterns"]})


# --- The suite ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("grader, task_id, reference", [(dcc_skill_loaded, "dcc-skill-loaded", "skill-loaded"),
                                                        (engine_checked, "engine-checked", "checked"),
                                                        (source_inspected, "source-inspected", "inspected"),
                                                        (failure_stop, "failure-stop", "stop-record"),
                                                        (branch_name, "branch-name", "renamed")])
def test_a_torn_last_line_without_a_violation_is_not_measured(tmp_path, grader, task_id, reference):
    evidence = evidence_of(task_id, reference)
    path = tmp_path / "t.jsonl"
    path.write_text(evidence["transcript"][0].read_text(encoding="utf-8") + TORN + "\n", encoding="utf-8")
    row = grader({**evidence, "transcript": [path]})
    assert row["passed"] is None and row["measured"] == "not measured"
    assert row["error"].startswith("incomplete evidence:")


@pytest.mark.parametrize("task_id", REGRESSION)
def test_each_regression_task_has_a_failing_and_a_passing_reference(task_id):
    spec = spec_of(task_id)
    assert (spec["id"], spec["suite"]) == (task_id, "regression")
    assert spec["grader"] in GRADERS
    verdicts = [ref["verdict"] for ref in spec["references"]]
    assert verdicts[0] == "fail" and "pass" in verdicts and set(verdicts) <= {"fail", "pass"}
    assert (EVALS / task_id / "task.md").is_file()


def test_the_regression_references_all_match_their_verdicts(tmp_path):
    out = tmp_path / "run"
    code = main(["evals", "--suite", "regression", "--references", "--main", str(ROOT), "--output", str(out)])
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert (code, report["failed"], report["not_measured"]) == (0, 0, 0)
    # Every regression task (procedural #123 and PR graders #125) runs each of its references once.
    tasks = [t.name for t in EVALS.iterdir() if (t / "task.json").is_file() and spec_of(t.name)["suite"] == "regression"]
    expected = sum(len(spec_of(t)["references"]) for t in tasks)
    assert len(report["checks"]) == expected and len({r["task"] for r in report["checks"]}) == len(tasks)
    assert report["passed"] == expected
