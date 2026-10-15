"""Static producer/consumer contract; no DCC execution or delivery acceptance."""
import ast
from pathlib import Path
import re

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "jobs/KPP1/scripts"
SOURCE = (SCRIPTS / "build_kpp1.py").read_text(encoding="utf-8")
SHELL = (SCRIPTS / "run_all.sh").read_text(encoding="utf-8")
EXPECTED = (
    "KPP1_VPM_v001_body.blend",
    "KPP1_VPM_v002_openings.blend",
    "KPP1_VPM_v003_roof.blend",
    "KPP1_VPM_v004_decor.blend",
    "KPP1_VPM_v005_uv.blend",
    "KPP1_VPM_v006_ucx.blend",
)


def stage_names(source):
    """Evaluate only the literal mapping and the producer's filename f-string."""
    tree = ast.parse(source)
    mappings = [
        node.value for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "STAGES"
                for target in node.targets)
    ]
    assert mappings, "STAGES not found"
    assert len(mappings) == 1, "Ambiguous STAGES assignments"
    stages = ast.literal_eval(mappings[0])
    filenames = [
        arg for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "path"
                for target in node.targets)
        and isinstance(node.value, ast.Call)
        for arg in node.value.args
        if isinstance(arg, ast.JoinedStr)
    ]
    assert filenames, "Stage filename f-string not found"
    assert len(filenames) == 1, "Ambiguous stage filename f-strings"
    filename = filenames[0]
    # Fail closed: calls, attributes and other executable expressions are forbidden.
    allowed = (ast.JoinedStr, ast.Constant, ast.FormattedValue, ast.Name,
               ast.Load, ast.Subscript)
    assert all(isinstance(node, allowed) for node in ast.walk(filename)), "Unsafe filename expression"
    assert {node.id for node in ast.walk(filename) if isinstance(node, ast.Name)} <= {"stage", "STAGES"}
    expression = compile(ast.Expression(filename), "<stage filename>", "eval")
    return {stage: eval(expression, {"__builtins__": {}}, {"stage": stage, "STAGES": stages})
            for stage in range(1, 7)}


def assert_consumer_contract(source, shell=SHELL):
    names = stage_names(source)
    consumers = re.findall(r'"\$B/([^"/]+\.blend)"', shell)
    assert consumers, "No build .blend consumers found in run_all.sh"
    for consumer in consumers:
        assert names[6] == consumer, f"Stage-6 producer/consumer mismatch: {names[6]} != {consumer}"
    return names


@pytest.mark.parametrize("stage, expected", list(enumerate(EXPECTED, start=1)))
def test_real_stage_names(stage, expected):
    assert stage_names(SOURCE)[stage] == expected


def test_real_stage_6_matches_every_shell_consumer():
    assert_consumer_contract(SOURCE)


def test_missing_stages_has_clear_failure():
    tree = ast.parse(SOURCE)
    tree.body = [node for node in tree.body
                 if not (isinstance(node, ast.Assign)
                         and any(isinstance(t, ast.Name) and t.id == "STAGES" for t in node.targets))]
    with pytest.raises(AssertionError, match="^STAGES not found"):
        stage_names(ast.unparse(tree))


def test_stage_6_rename_is_rejected():
    tree = ast.parse(SOURCE)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "STAGES" for t in node.targets
        ):
            for key, value in zip(node.value.keys, node.value.values):
                if ast.literal_eval(key) == 6:
                    value.value = "renamed"
    with pytest.raises(AssertionError, match="Stage-6 producer/consumer mismatch"):
        assert_consumer_contract(ast.unparse(tree))


@pytest.mark.parametrize("position", ["before", "after"])
def test_module_code_is_never_executed(position):
    sentinel = 'raise AssertionError("Module execution is forbidden")\n'
    source = sentinel + SOURCE if position == "before" else SOURCE + "\n" + sentinel
    assert tuple(stage_names(source).values()) == EXPECTED
