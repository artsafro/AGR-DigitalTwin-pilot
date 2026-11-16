"""new-case: shared headless window command, same OBJ as AGR Tools win.generate."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'adapters/max/agr_tools'))
import windowgen_core as wg
import pytest
from tools.windows import generate as command


def test_glass_ownership_is_three_dimensional_and_unique():
    bay = {'id': 'b', 'min': [0, 0, 0], 'max': [2, 1, 2]}
    glass = {'id': 'g', 'min': [.1, .1, .1], 'max': [1.9, .2, 1.9]}
    assert command.assign_glass([bay], [glass])['assigned'] == {'g': 'b'}
    behind = dict(glass, min=[.1, 2, .1], max=[1.9, 2.1, 1.9])
    zero = command.assign_glass([bay], [behind])
    assert zero['status'] == 'fail' and zero['drops'][0]['reason'] == 'no bay in 3D'
    many = command.assign_glass([bay, dict(bay, id='b2')], [glass])
    assert many['status'] == 'fail' and many['drops'][0]['candidates'] == ['b', 'b2']


@pytest.mark.parametrize('objects', [[], [{'id': 'g'}],
    [{'id': 'g', 'min': [0, 0, 0], 'max': [float('nan'), 1, 1]}],
    [{'id': 'g', 'min': [0, 0, 0], 'max': [float('inf'), 1, 1]}],
    [{'id': 'g', 'min': [0, 0, 0], 'max': [0, 1, 1]}],
    [{'id': 'g', 'min': [0, 0, 0], 'max': [1, 1, 1]}] * 2])
def test_ownership_rejects_invalid_inventory(objects):
    with pytest.raises(ValueError):
        command.assign_glass([{'id': 'b', 'min': [0, 0, 0], 'max': [2, 1, 2]}], objects)


def test_explicit_generator_fallback():
    lib = wg.load_library(str(ROOT / 'library/windows'))
    entry = dict(lib['by_id']['KPP1-W01'], id='SOURCE-DRAFT', width_m=1.317,
                 panes_m=[[.057, .057, 1.26, 1.743]])
    opening = {'id': 'one', 'w': 1.317, 'h': 1.8, 'inset_m': .2, 'generator': entry}
    plan, drafts = command.plan_openings([opening], lib)
    assert plan[0]['route'] == 'generator' and plan[0]['type'] == 'SOURCE-DRAFT'
    assert drafts == [entry]
    matched, drafts = command.plan_openings([dict(opening, w=1.18)], lib)
    assert matched[0]['route'] == 'library' and matched[0]['type'] == 'KPP1-W01'
    assert drafts == []


@pytest.mark.parametrize('width', [1.18, 1.317])
def test_generator_unknown_key_is_named(width):
    lib = wg.load_library(str(ROOT / 'library/windows'))
    entry = dict(lib['by_id']['KPP1-W01'], id='SOURCE-DRAFT', width_m=1.317,
                 panes_m=[[.057,.057,1.26,1.743]], unknown_material='no-default')
    with pytest.raises(ValueError, match='unknown_material'):
        command.plan_openings([{'id':'x','w':width,'h':1.8,'inset_m':.2,'generator':entry}], lib)


def test_command_refuses_existing_output(tmp_path):
    target = tmp_path / 'input.json'
    target.write_bytes(b'original')
    for out in (target, tmp_path):
        with pytest.raises((ValueError, OSError)):
            command.generate(['KPP1-W01'], ROOT / 'library/windows', out)
    assert target.read_bytes() == b'original'


def test_max_button_adapter_bundle_parity(tmp_path, monkeypatch):
    import importlib.util
    from types import SimpleNamespace
    def load(name):
        spec = importlib.util.spec_from_file_location(name, ROOT / 'adapters/max/agr_tools' / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    adapter, edit = load('windowgen_max'), load('edit_core')
    monkeypatch.setattr(adapter, '_rt', lambda: SimpleNamespace(selection=[]))
    ids = ['KPP1-W01', 'KPP1-W02', 'KPP1-W03']
    ctx = SimpleNamespace(edit=edit, core=wg, options={'ids': ids, 'out': str(tmp_path / 'max')})
    preview = adapter.win_generate(ctx, 'preview', [], None)
    adapter.win_generate(ctx, 'apply', [], preview)
    command.generate(ids, ROOT / 'library/windows', tmp_path / 'agent')
    for source in (tmp_path / 'max').iterdir():
        assert source.read_bytes() == (tmp_path / 'agent' / source.name).read_bytes(), source.name


def test_kpp1_opening_plan():
    spec = {f: {'surrounds': [], 'features': []} for f in 'SNWE'}
    spec['S']['surrounds'] = [{'bays': [
        {'id': str(i), 'rect': [0, w, 0, h]} for i, (w, h) in enumerate([(1.18, 1.8), (1.18, 5.45), (2, 1.8)])]}]
    lib = wg.load_library(str(ROOT / 'library/windows'))
    plan, drafts = command.plan_openings(command.kpp1_openings(spec, .2), lib)
    assert [p['type'] for p in plan] == ['KPP1-W01', 'KPP1-W02', 'KPP1-W03']
    assert all(p['inset_m'] == .2 and p['route'] == 'library' for p in plan)
    assert not drafts


@pytest.mark.parametrize('opening', [None, {}, {'id': 'x', 'w': 1.18, 'h': 1.8},
    {'id': 'x', 'w': 1.18, 'h': 1.8, 'inset_m': 0},
    {'id': 'x', 'w': float('nan'), 'h': 1.8, 'inset_m': .2},
    {'id': 'x', 'w': float('inf'), 'h': 1.8, 'inset_m': .2},
    {'id': 'x', 'w': 1.18, 'h': 1.8, 'inset_m': .2, 'type': 'UNKNOWN'},
    {'id': 'x', 'w': 1.18, 'h': 1.8, 'inset_m': .2, 'surprise': 1},
    {'id': 'x', 'w': 1.177, 'h': 1.8, 'inset_m': .2},
    {'id': 'x', 'w': 1.317, 'h': 1.8, 'inset_m': .2}])
def test_invalid_opening_is_not_a_success(opening):
    lib = wg.load_library(str(ROOT / 'library/windows'))
    with pytest.raises((ValueError, TypeError)):
        command.plan_openings([opening], lib)


def test_generated_ownership_matrix():
    # Independent integer-box oracle over 125 translated glass witnesses, including exact tolerance.
    bay = {'id': 'b', 'min': [0, 0, 0], 'max': [2, 2, 2]}
    from itertools import product
    for x, y, z in product((-1, 0, 1, 2, 3), repeat=3):
        obj = {'id': 'g', 'min': [x, y, z], 'max': [x+.5, y+.5, z+.5]}
        report = command.assign_glass([bay], [obj])
        assert (report['status'] == 'pass') == (x in (0,1) and y in (0,1) and z in (0,1))
        assert len(report['assigned']) + len(report['drops']) == 1
    edge = {'id': 'g', 'min': [-.012, .1, .1], 'max': [.5, .5, .5]}
    assert command.assign_glass([bay], [edge])['status'] == 'fail'


def test_publish_race_retains_foreign_output(tmp_path, monkeypatch):
    real_rename = command.os.rename
    out = tmp_path / 'output'
    def race(src, dst):
        Path(dst).mkdir()
        (Path(dst) / 'foreign').write_bytes(b'keep')
        return real_rename(src, dst)
    monkeypatch.setattr(command.os, 'rename', race)
    with pytest.raises(OSError):
        command.generate(['KPP1-W01'], ROOT / 'library/windows', out)
    assert [p.name for p in out.iterdir()] == ['foreign']
    assert (out / 'foreign').read_bytes() == b'keep'
    assert not list(tmp_path.glob('.window-*'))


def test_input_change_refuses_publication(tmp_path, monkeypatch):
    source = tmp_path / 'input'
    source.write_bytes(b'before')
    original = command.core.sheet_png
    def mutate(*args):
        source.write_bytes(b'changed')
        return original(*args)
    monkeypatch.setattr(command.core, 'sheet_png', mutate)
    with pytest.raises(ValueError, match='changed during'):
        command.generate(['KPP1-W01'], ROOT / 'library/windows', tmp_path / 'out', inputs=[source])
    assert not (tmp_path / 'out').exists()
    assert not list(tmp_path.glob('.window-*'))


def test_request_cli_fails_closed_then_resets(tmp_path):
    request, out = tmp_path / 'request.json', tmp_path / 'run'
    valid = {'schema': 'window-request/1', 'openings': [{'id':'one', 'w':1.18, 'h':1.8, 'inset_m':.2}]}
    args = [sys.executable, '-m', 'dt_ai.cli.agr', 'window-generate', '--request', str(request), '--out', str(out)]
    for bad in ({}, dict(valid, openings=[]), dict(valid, openings=valid['openings'] * 2),
                dict(valid, openings=[dict(valid['openings'][0], type='unmapped')])):
        request.write_text(json.dumps(bad), encoding='utf-8')
        result = subprocess.run(args, capture_output=True)
        assert result.returncode != 0 and not out.exists()
    request.write_text(json.dumps(valid), encoding='utf-8')
    assert subprocess.run(args, capture_output=True).returncode == 0
    receipt = (out / 'run.json').read_bytes()
    assert json.loads(receipt)['openings'][0]['inset_m'] == .2
    request.write_text('{}', encoding='utf-8')
    assert subprocess.run(args, capture_output=True).returncode != 0
    assert (out / 'run.json').read_bytes() == receipt


def test_hardlinked_and_resolved_output_aliases(tmp_path):
    request = tmp_path / 'request.json'
    request.write_text(json.dumps({'schema':'window-request/1', 'openings':[{'id':'x','w':1.18,'h':1.8,'inset_m':.2}]}))
    hard = tmp_path / 'hard.json'
    hard.hardlink_to(request)
    before = request.read_bytes()
    for target in (request, hard, tmp_path / 'missing' / '..' / 'request.json'):
        result = command.main(['--request', str(request), '--out', str(target)])
        assert result != 0 and request.read_bytes() == before and hard.read_bytes() == before


def test_duplicate_json_keys_are_refused(tmp_path):
    request = tmp_path / 'request.json'
    request.write_text('{"schema":"wrong","schema":"window-request/1","openings":[{"id":"x","w":1.18,"h":1.8,"inset_m":0.2}]}')
    assert command.main(['--request', str(request), '--out', str(tmp_path/'out')]) != 0
    assert not (tmp_path / 'out').exists()


def test_duplicate_guard_refuses_window_implementations_not_calls():
    from tools.architecture import duplicate_guard as guard
    for name in ('build_type', 'assign_glass'):
        text = 'def ' + name + '(*args):\n    return {}\n'
        hits = guard.scan_text(text, 'jobs/new/window.py')
        assert [f.rule for f in hits] == ['window-generator']
        assert not guard.scan_text(text, 'adapters/max/agr_tools/windowgen_core.py')
    assert not guard.scan_text('from windowgen_core import build_type\nx = build_type(a, b)', 'jobs/new/wrapper.py')


def test_fresh_agent_command_matches_max_builder(tmp_path):
    out = tmp_path / 'generated'
    result = subprocess.run([sys.executable, '-m', 'dt_ai.cli.agr', 'window-generate',
                             '--ids', 'KPP1-W01', 'KPP1-W02', 'KPP1-W03', '--out', str(out)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    lib = wg.load_library(str(ROOT / 'library/windows'))
    for tid in ('KPP1-W01', 'KPP1-W02', 'KPP1-W03'):
        expected = wg.to_obj(wg.build_type(lib['by_id'][tid], lib['standard'], {'variant': 'vpm'}), tid)
        assert (out / (tid + '.obj')).read_text(encoding='utf-8') == expected
    assert json.loads((out / 'quality.json').read_text())['counts']['pass'] == 3
