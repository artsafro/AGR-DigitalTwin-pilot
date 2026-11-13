"""new-case: check-only native campaign safety and completeness guards for #1293."""
import ast
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[1] / 'jobs/KPP1/final-check-1293/run_max.py'


def test_each_macro_restores_complete_scope():
    tree = ast.parse(RUNNER.read_text(encoding='utf-8'))
    loop = next(n for n in ast.walk(tree) if isinstance(n, ast.For) and ast.unparse(n.target) == 'tool')
    calls = [ast.unparse(n) for n in ast.walk(loop) if isinstance(n, ast.Call)]
    assert 'rt.select(nodes)' in calls, 'xView selects offenders; later macros must not inherit its selection'


def test_no_apply_or_export_commit_or_save_calls():
    tree = ast.parse(RUNNER.read_text(encoding='utf-8'))
    calls = [ast.unparse(n.func).lower() for n in ast.walk(tree) if isinstance(n, ast.Call)]
    assert not any('apply' in c or 'commit' in c or 'savemax' in c for c in calls)
    scope = {}
    exec(compile(tree, str(RUNNER), 'exec'), {'__name__': 'not_main'}, scope)
    assert len(scope['TOOLS']) == 11
    assert not any('Apply' in t for t in scope['TOOLS'])


def test_exclusive_output_and_input_hashes():
    text = RUNNER.read_text(encoding='utf-8')
    assert "output.open('x'" in text
    assert "result['inputs_after'] != hashes" in text
    assert 'aliased input/output' in text
    assert "entry['scene_unchanged']" in text
