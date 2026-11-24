"""Offline guard for the three audited Max merge owners (no Max import)."""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ASSETS = "adapters/max/agr_tools/assets_max.py"
EXPORT = "tools/export/batch_export_max.py"
FLORA = "tools/flora/build_flora_library_max.py"
MTL = {"renamemtldups", "usescenemtldups", "usemergedmtldups"}
PARENT = {"neverreparent", "alwaysreparent"}
PROMPT = {"promptmtldups", "promptreparent"}


def _name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _literal_names(node):
    if not isinstance(node, ast.Call) or _name(node.func) != "Name" or len(node.args) != 1:
        return set()
    arg = node.args[0]
    choices = (arg.body, arg.orelse) if isinstance(arg, ast.IfExp) else (arg,)
    names = {c.value.lower() for c in choices if isinstance(c, ast.Constant) and isinstance(c.value, str)}
    return names if all(isinstance(c, ast.Constant) and isinstance(c.value, str) for c in choices) else set()


def _merge_problems(flags):
    return [rule for rule, bad in (
        ("explicit non-prompt material policy", not flags & MTL),
        ("explicit non-prompt reparent policy", not flags & PARENT),
        ("dialog flag forbidden", flags & PROMPT),
    ) if bad]


def _python_output_problems(tree):
    aliases = {a.asname: a.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
               and node.module in {"logging", "builtins"} for a in node.names if a.asname}
    for call in (n for n in ast.walk(tree) if isinstance(n, ast.Call)):
        name = aliases.get(_name(call.func), _name(call.func))
        kwargs = {kw.arg: kw.value for kw in call.keywords}
        if name == "StreamHandler":
            yield call.lineno, "use FileHandler instead of StreamHandler"
        if name == "basicConfig" and ("filename" not in kwargs or {"stream", "handlers"} & kwargs.keys()):
            yield call.lineno, "configure logging with a filename"
        if name == "print" and ("file" not in kwargs or
                                isinstance(kwargs["file"], (ast.Attribute, ast.Constant))):
            yield call.lineno, "write diagnostics to an explicit file"
        if (name in {"write", "writelines"} and isinstance(call.func, ast.Attribute)
                and _name(call.func.value) in {"stdout", "__stdout__", "stderr", "__stderr__"}):
            yield call.lineno, "write diagnostics to an explicit file"


@pytest.mark.parametrize("source", [ASSETS, EXPORT, FLORA])
def test_max_merge_owners_keep_python_diagnostics_off_stdout(source):
    tree = ast.parse((ROOT / source).read_text(encoding="utf-8"))
    assert not [f"{source}:{line}: {msg}" for line, msg in _python_output_problems(tree)]


@pytest.mark.parametrize("source", [ASSETS, FLORA])
def test_pymxs_merge_passes_non_prompt_policies(source):
    tree = ast.parse((ROOT / source).read_text(encoding="utf-8"))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and _name(n.func).lower() == "mergemaxfile"]
    assert calls, f"{source}: re-audit relocated merge"
    # Assets forwards this value through _bring; keep its two allowed branches explicit.
    material_options = set()
    if source == ASSETS:
        assignments = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                       and any(_name(t) == "flag_mtl" for t in n.targets)]
        assert len(assignments) == 1
        material_options = _literal_names(assignments[0].value)
        assert material_options == {"renamemtldups", "usescenemtldups"}
    for call in calls:
        assert all(not isinstance(arg, ast.Starred) for arg in call.args), "audit dynamic merge flags"
        flags = set().union(*(_literal_names(arg) for arg in call.args))
        if source == ASSETS and any(isinstance(arg, ast.Name) and arg.id == "flag_mtl" for arg in call.args):
            flags |= material_options
        assert not _merge_problems(flags), f"{source}:{call.lineno}: {_merge_problems(flags)}"


def test_export_maxscript_merge_passes_non_prompt_policies():
    tree = ast.parse((ROOT / EXPORT).read_text(encoding="utf-8"))
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for line in node.value.splitlines():
                code = line.partition("--")[0]
                match = re.search(r"\bmergeMAXFile\s+(.+)", code, flags=re.I)
                if match:
                    calls.append(set(re.findall(r"#(\w+)", match[1].lower())))
    assert calls, "re-audit relocated MAXScript merge"
    for flags in calls:
        assert not _merge_problems(flags), _merge_problems(flags)


@pytest.mark.parametrize(("snippet", "count"), [
    ("import logging as log\nlog.StreamHandler(sys.stdout)", 1),
    ("from logging import StreamHandler as SH\nSH()", 1),
    ("logging.basicConfig(stream=sys.stdout)", 1),
    ("logging.basicConfig(handlers=[logging.StreamHandler()])", 2),
    ("print('diagnostic', file=sys.stdout)\nsys.__stdout__.write('diagnostic')", 2),
    ("logging.basicConfig(filename='job.log', encoding='utf-8')", 0),
    ("logging.FileHandler('job.log')\nprint('diagnostic', file=log_file)", 0),
])
def test_diagnostic_sink_examples(snippet, count):
    assert len(list(_python_output_problems(ast.parse(snippet)))) == count


@pytest.mark.parametrize("flags", [
    {"renamemtldups"}, {"neverreparent"}, {"promptmtldups", "promptreparent"},
    {"renamemtldups", "neverreparent", "promptreparent"},
])
def test_merge_rule_rejects_implicit_or_explicit_prompts(flags):
    assert _merge_problems(flags)
