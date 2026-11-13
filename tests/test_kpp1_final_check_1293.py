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


def test_invalid_configs_and_aliases_fail_closed(tmp_path):
    import importlib.util
    import pytest
    spec = importlib.util.spec_from_file_location('final1293', RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fbx = tmp_path / 'a.fbx'
    fbx.write_bytes(b'synthetic path fixture, not real FBX')
    row = {'profile': 'npm', 'fbx': str(fbx), 'geojson': str(tmp_path / 'a.geojson')}
    good = {'inputs': [row], 'output': str(tmp_path / 'result.json'), 'tools': ['Names']}
    for bad in [{}, {'inputs': []}, dict(good, output=float('nan')), dict(good, output=float('inf')),
                dict(good, inputs=[row, row]), dict(good, output=str(tmp_path / '.' / 'a.fbx')),
                dict(good, tools=[]), dict(good, tools=['Names', 'Names']),
                dict(good, tools=['NamesApply']), dict(good, inputs=[dict(row, profile='unknown')])]:
        with pytest.raises(ValueError):
            module.validate_config(bad)
    module.validate_config(good)
    Path(good['output']).write_text('stale receipt')
    with pytest.raises(FileExistsError):
        module.validate_config(good)
    assert fbx.read_bytes() == b'synthetic path fixture, not real FBX'
