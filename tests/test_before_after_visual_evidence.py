"""new-case: Before/After visual evidence rule [D286] and the same-camera render helper (#1360)."""
import copy
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools/review/before_after.py'
WORKFLOW = ROOT / 'docs/agents/WORKFLOW.md'
TEMPLATE = ROOT / '.github/pull_request_template.md'
CHECKLIST = ROOT / 'docs/agents/REVIEW_CHECKLIST.md'
DECISIONS = ROOT / 'docs/decisions.md'
CAPABILITIES = ROOT / 'docs/agents/CAPABILITIES.md'
ANCHOR = 'WORKFLOW.md#visual-evidence-beforeafter-d286'


def load():
    assert SCRIPT.exists(), 'Before/After helper is missing'
    spec = importlib.util.spec_from_file_location('before_after', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def section(text, heading):
    start = text.index(heading)
    rest = text[start + len(heading):]
    end = re.search(r'\n#{2,3} ', rest)
    return rest[:end.start()] if end else rest


# ---------------------------------------------------------------- the rule (docs)

def test_rule_lives_in_one_canonical_section():
    text = WORKFLOW.read_text(encoding='utf-8')
    body = section(text, '### Visual evidence (Before/After) [D286]')
    for phrase in ('geometry', 'UV', 'materials', 'textures', 'renders', 'Max UI',
                   'Before', 'After', 'same camera', 'After-only', 'mockup', 'not-ready',
                   'G:/Мой диск/AGR-evidence/', 'tools/review/before_after.py'):
        assert phrase in body, phrase
    # one canonical place: the full rule text is not duplicated in other docs
    for other in (TEMPLATE, CHECKLIST, ROOT / 'AGENTS.md'):
        assert 'After-only' not in other.read_text(encoding='utf-8'), other


def test_decision_row_d286():
    rows = [l for l in DECISIONS.read_text(encoding='utf-8').splitlines() if l.startswith('| D286 |')]
    assert len(rows) == 1
    assert 'Before' in rows[0] and 'After' in rows[0] and '#1360' in rows[0]


def test_template_and_checklist_link_the_rule():
    template = TEMPLATE.read_text(encoding='utf-8')
    lines = [l for l in template.splitlines() if l.startswith('- Visual Before/After:')]
    assert len(lines) == 1 and 'docs/agents/' + ANCHOR in lines[0]
    checklist = CHECKLIST.read_text(encoding='utf-8')
    line = [l for l in checklist.splitlines() if 'Before/After' in l]
    assert line and ANCHOR in checklist
    assert any('changes requested' in l for l in line)


def test_capabilities_lists_the_helper():
    assert 'tools/review/before_after.py' in CAPABILITIES.read_text(encoding='utf-8')


# ---------------------------------------------------------------- camera comparison

CAM = {'type': 'ORTHO', 'matrix_world': [1.0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
       'lens': 50.0, 'ortho_scale': 30.0, 'sensor_width': 36.0, 'sensor_fit': 'AUTO',
       'shift_x': 0.0, 'shift_y': 0.0, 'clip_start': 0.1, 'clip_end': 1000.0,
       'resolution': [1600, 1000], 'pixel_aspect': [1.0, 1.0]}


def test_equal_cameras_pass():
    assert load().compare_cameras(CAM, copy.deepcopy(CAM)) == []


@pytest.mark.parametrize('key,value', [
    ('type', 'PERSP'), ('lens', 50.1), ('ortho_scale', 30.5), ('sensor_fit', 'VERTICAL'),
    ('shift_x', 0.01), ('clip_end', 999.0), ('resolution', [1600, 1001]),
    ('pixel_aspect', [1.0, 2.0])])
def test_mismatched_camera_is_named(key, value):
    other = copy.deepcopy(CAM)
    other[key] = value
    assert load().compare_cameras(CAM, other) == [key]


def test_mismatched_matrix_every_element():
    module = load()
    for index in range(16):
        other = copy.deepcopy(CAM)
        other['matrix_world'][index] += 1e-3
        assert module.compare_cameras(CAM, other) == ['matrix_world'], index


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), None, 'x'])
def test_non_finite_camera_is_an_error(bad):
    other = copy.deepcopy(CAM)
    other['lens'] = bad
    with pytest.raises(ValueError, match='lens'):
        load().compare_cameras(CAM, other)


@pytest.mark.parametrize('mutate', [lambda c: c.pop('lens'), lambda c: c.update(extra=1),
                                    lambda c: c.update(matrix_world=[1.0] * 15)])
def test_partial_or_unknown_camera_is_an_error(mutate):
    other = copy.deepcopy(CAM)
    mutate(other)
    with pytest.raises(ValueError):
        load().compare_cameras(CAM, other)


@pytest.mark.parametrize('spec,match', [
    ({}, 'mode'), ({'mode': 'fit', 'azimuth_deg': float('nan')}, 'azimuth'),
    ({'mode': 'fit', 'margin': 0}, 'margin'), ({'mode': 'named'}, 'name'),
    ({'mode': 'fit', 'resolution': [0, 10]}, 'resolution'),
    ({'mode': 'fit', 'style': 'pretty'}, 'style'), ({'mode': 'orbit'}, 'mode'),
    ({'mode': 'fit', 'unknown': 1}, 'unknown')])
def test_camera_request_validation(spec, match):
    with pytest.raises(ValueError, match=match):
        load().validate_request(spec)


# ---------------------------------------------------------------- CLI (fake Blender)

def write_png(path, colour):
    from PIL import Image
    Image.new('RGB', (40, 25), colour).save(path)


def fake_runner(after_camera=None, touch=None):
    def run(script, args, *, executable=None, output_json=None, outputs=(), timeout=900, log_path=None):
        cfg = json.loads(Path(args[0]).read_text(encoding='utf-8'))
        out = Path(cfg['output_dir'])
        write_png(out / 'before.png', (200, 50, 50))
        write_png(out / 'after.png', (50, 200, 50))
        if touch:
            touch()
        record = {'before': {'camera': CAM, 'render': {'engine': 'BLENDER_WORKBENCH', 'style': 'wire'}},
                  'after': {'camera': after_camera or CAM,
                            'render': {'engine': 'BLENDER_WORKBENCH', 'style': 'wire'}}}
        Path(output_json).write_text(json.dumps(record), encoding='utf-8')
        return record
    return run


@pytest.fixture
def inputs(tmp_path):
    before = tmp_path / 'in' / 'welded' / 'model.fbx'
    after = tmp_path / 'in' / 'separate' / 'model.fbx'
    for path, payload in ((before, b'synthetic before'), (after, b'synthetic after')):
        path.parent.mkdir(parents=True)
        path.write_bytes(payload)
    return before, after


def argv(before, after, output, *extra):
    return ['--before', str(before), '--after', str(after), '--output', str(output),
            '--label-before', 'welded', '--label-after', 'separate', *extra]


def snapshot(root):
    return sorted((str(p.relative_to(root)), p.read_bytes() if p.is_file() else b'')
                  for p in root.rglob('*'))


def test_cli_writes_labelled_pair(tmp_path, inputs, monkeypatch):
    module = load()
    monkeypatch.setattr(module, 'run_blender', fake_runner())
    output = tmp_path / 'ev' / '1360-before-after'
    assert module.main(argv(*inputs, output)) == 0
    names = sorted(p.name for p in output.iterdir())
    assert set(names) >= {'SHA256SUMS.txt', 'after.png', 'before.png', 'before-after.png',
                          'before-after.json', 'config.json'}
    manifest = json.loads((output / 'before-after.json').read_text(encoding='utf-8'))
    assert manifest['before']['label'] == 'welded' and manifest['after']['label'] == 'separate'
    assert manifest['before']['sha256'] != manifest['after']['sha256']
    assert manifest['camera'] == CAM and manifest['same_camera'] is True
    assert 'no acceptance' in manifest['scope']
    from PIL import Image
    pair = Image.open(output / 'before-after.png')
    assert pair.width >= 80 and pair.height > 25
    sums = (output / 'SHA256SUMS.txt').read_text(encoding='utf-8')
    assert 'before-after.png' in sums and 'before.png' in sums
    assert not output.with_name(output.name + '.partial').exists()


def test_cli_refuses_mismatched_cameras_and_writes_nothing(tmp_path, inputs, monkeypatch):
    module = load()
    moved = copy.deepcopy(CAM)
    moved['matrix_world'][3] = 5.0
    monkeypatch.setattr(module, 'run_blender', fake_runner(after_camera=moved))
    output = tmp_path / 'ev' / 'out'
    before_state = snapshot(tmp_path / 'in')
    assert module.main(argv(*inputs, output)) == 2
    assert not output.exists() and not output.with_name('out.partial').exists()
    assert snapshot(tmp_path / 'in') == before_state
    assert not (tmp_path / 'ev').exists(), 'created parent directories are removed on refusal'


def test_cli_refuses_input_changed_during_run(tmp_path, inputs, monkeypatch):
    module = load()
    monkeypatch.setattr(module, 'run_blender',
                        fake_runner(touch=lambda: inputs[1].write_bytes(b'changed mid-run')))
    output = tmp_path / 'ev' / 'out'
    assert module.main(argv(*inputs, output)) == 2
    assert not output.exists() and not output.with_name('out.partial').exists()


def refusal_cases(tmp_path, before, after):
    same_content = tmp_path / 'in' / 'copy.fbx'
    same_content.write_bytes(before.read_bytes())
    unsupported = tmp_path / 'in' / 'model.obj'
    unsupported.write_bytes(b'x')
    empty = tmp_path / 'in' / 'empty.fbx'
    empty.write_bytes(b'')
    existing = tmp_path / 'ev' / 'exists'
    existing.mkdir(parents=True)
    occupied = tmp_path / 'ev' / 'occ'
    (tmp_path / 'ev' / 'occ.partial').mkdir()
    return {
        'missing before': argv(tmp_path / 'nope.fbx', after, tmp_path / 'ev' / 'a'),
        'same file': argv(before, before, tmp_path / 'ev' / 'b'),
        'alias': argv(before, before.parent / '..' / 'welded' / 'model.fbx', tmp_path / 'ev' / 'c'),
        'identical content': argv(before, same_content, tmp_path / 'ev' / 'd'),
        'unsupported': argv(unsupported, after, tmp_path / 'ev' / 'e'),
        'empty': argv(empty, after, tmp_path / 'ev' / 'f'),
        'output exists': argv(before, after, existing),
        'partial exists': argv(before, after, occupied),
        'output is input': argv(before, after, before),
        'output inside repo': argv(before, after, ROOT / 'tmp' / 'ba-1360-probe'),
        'output under input dir alias': argv(before, after, before.parent / '..' / 'welded'),
        'named without name': argv(before, after, tmp_path / 'ev' / 'g', '--camera-mode', 'named'),
        'nan azimuth': argv(before, after, tmp_path / 'ev' / 'h', '--azimuth', 'nan'),
        'inf elevation': argv(before, after, tmp_path / 'ev' / 'i', '--elevation', 'inf'),
        'elevation at 90': argv(before, after, tmp_path / 'ev' / 'j', '--elevation', '90'),
        'empty label': ['--before', str(before), '--after', str(after), '--output',
                        str(tmp_path / 'ev' / 'k'), '--label-before', ' ', '--label-after', 'x'],
    }


def test_cli_fail_closed_cases(tmp_path, inputs, monkeypatch):
    module = load()
    calls = []
    monkeypatch.setattr(module, 'run_blender', lambda *a, **k: calls.append(a))
    before, after = inputs
    cases = refusal_cases(tmp_path, before, after)
    state = snapshot(tmp_path)
    results = {name: module.main(args) for name, args in cases.items()}
    assert results == {name: 2 for name in cases}
    assert calls == []
    assert snapshot(tmp_path) == state
    assert not (ROOT / 'tmp' / 'ba-1360-probe').exists()


def test_fresh_process_cli_help_and_refusal(tmp_path, inputs):
    before, _ = inputs
    help_run = subprocess.run([sys.executable, str(SCRIPT), '--help'], capture_output=True, text=True)
    assert help_run.returncode == 0 and '--camera-mode' in help_run.stdout
    bad = subprocess.run([sys.executable, str(SCRIPT), *argv(before, before, tmp_path / 'ev' / 'z')],
                         capture_output=True, text=True)
    assert bad.returncode == 2 and 'ERROR' in bad.stderr
    assert not (tmp_path / 'ev' / 'z').exists()


# ---------------------------------------------------------------- real Blender (optional)

def blender():
    sys.path.insert(0, str(ROOT / 'src'))
    from dt_ai.core.blender_runner import blender_executable
    exe = blender_executable()
    return exe if Path(exe).is_file() else None


MAKE_SCENES = r'''
import bpy, sys
out = sys.argv[sys.argv.index('--') + 1:]
for path, x, cam_x in ((out[0], 0.0, 10.0), (out[1], 0.5, 11.0)):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add(location=(x, 0, 0))
    data = bpy.data.cameras.new('Shot')
    cam = bpy.data.objects.new('Shot', data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = (cam_x, -10, 6)
    bpy.ops.wm.save_as_mainfile(filepath=path)
'''


@pytest.mark.skipif(blender() is None or os.environ.get('RUN_BLENDER_SMOKE') != '1',
                    reason='opt in with RUN_BLENDER_SMOKE=1 (real Blender render)')
def test_real_blender_named_mismatch_refused_and_fit_matches(tmp_path):
    module = load()
    maker = tmp_path / 'make.py'
    maker.write_text(MAKE_SCENES, encoding='utf-8')
    a, b = tmp_path / 'a.blend', tmp_path / 'b.blend'
    subprocess.run([blender(), '--background', '--factory-startup', '--python', str(maker), '--',
                    str(a), str(b)], check=True, capture_output=True)
    bad = tmp_path / 'ev' / 'named'
    assert module.main(argv(a, b, bad, '--camera-mode', 'named', '--camera-name', 'Shot',
                            '--resolution', '64x40')) == 2
    assert not bad.exists() and not bad.with_name('named.partial').exists()
    good = tmp_path / 'ev' / 'fit'
    assert module.main(argv(a, b, good, '--resolution', '64x40')) == 0
    manifest = json.loads((good / 'before-after.json').read_text(encoding='utf-8'))
    assert manifest['same_camera'] is True and manifest['camera']['type'] == 'ORTHO'
    assert all(math.isfinite(v) for v in manifest['camera']['matrix_world'])
