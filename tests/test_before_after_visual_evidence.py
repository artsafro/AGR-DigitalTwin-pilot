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
       'lens': 50.0, 'ortho_scale': 30.0, 'sensor_width': 36.0, 'sensor_height': 24.0, 'sensor_fit': 'AUTO',
       'projection': [0.0667, 0, 0, 0, 0, 0.1067, 0, 0, 0, 0, -0.002, -1.0002, 0, 0, 0, 1],
       'shift_x': 0.0, 'shift_y': 0.0, 'clip_start': 0.1, 'clip_end': 1000.0,
       'resolution': [1600, 1000], 'pixel_aspect': [1.0, 1.0]}


def test_equal_cameras_pass():
    assert load().compare_cameras(CAM, copy.deepcopy(CAM)) == []


@pytest.mark.parametrize('key,value', [
    ('type', 'PERSP'), ('lens', 50.1), ('ortho_scale', 30.5), ('sensor_fit', 'VERTICAL'),
    ('shift_x', 0.01), ('clip_end', 999.0), ('resolution', [1600, 1001]),
    ('pixel_aspect', [1.0, 2.0]), ('sensor_height', 48.0),
    ('projection', [0.0334, 0, 0, 0, 0, 0.1067, 0, 0, 0, 0, -0.002, -1.0002, 0, 0, 0, 1])])
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


def test_mismatched_projection_every_element():
    """Review r1 P1: any change of the effective projection (calc_matrix_camera) is a mismatch."""
    module = load()
    for index in range(16):
        other = copy.deepcopy(CAM)
        other['projection'][index] += 1e-3
        assert module.compare_cameras(CAM, other) == ['projection'], index


@pytest.mark.parametrize('key', ['sensor_height', 'projection'])
def test_camera_record_without_projection_keys_is_refused(key):
    other = copy.deepcopy(CAM)
    del other[key]
    with pytest.raises(ValueError, match=key):
        load().compare_cameras(CAM, other)


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


RENDER = {'engine': 'BLENDER_WORKBENCH', 'style': 'wire', 'view_transform': 'Standard',
          'look': 'None', 'exposure': 0.0, 'gamma': 1.0, 'display_device': 'sRGB',
          'use_curve_mapping': False, 'use_white_balance': False, 'emulation': 'AUTO',
          'world_color': [0.05, 0.05, 0.05], 'world_use_nodes': False,
          'background_type': 'VIEWPORT', 'background_color': [0.05, 0.05, 0.05],
          'thickness': 0.0012, 'use_border': False, 'use_multiview': False,
          'image_views_format': 'INDIVIDUAL', 'workbench': {}}


def fake_runner(after_camera=None, touch=None, mutate_render=None):
    def run(script, args, *, executable=None, output_json=None, outputs=(), timeout=900, log_path=None):
        cfg = json.loads(Path(args[0]).read_text(encoding='utf-8'))
        out = Path(cfg['output_dir'])
        write_png(out / 'before.png', (200, 50, 50))
        write_png(out / 'after.png', (50, 200, 50))
        if touch:
            touch()
        record = {'before': {'camera': CAM, 'render': copy.deepcopy(RENDER)},
                  'after': {'camera': after_camera or CAM,
                            'render': copy.deepcopy(RENDER)}}
        if mutate_render:
            mutate_render(record['after']['render'])
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
    assert b'\r' not in (output / 'SHA256SUMS.txt').read_bytes(), 'sha256sum -c needs LF lines'
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


@pytest.mark.parametrize('key,value', [
    ('engine', 'CYCLES'), ('style', 'solid'), ('view_transform', 'AgX'),
    ('look', 'AgX - Medium High Contrast'), ('exposure', 2.0), ('gamma', 1.5),
    ('display_device', 'Display P3'), ('world_color', [1.0, 0.0, 0.0]),
    ('world_use_nodes', True), ('use_curve_mapping', True), ('use_white_balance', True),
    ('emulation', 'OFF'), ('background_type', 'WORLD'),
    ('background_color', [0.0, 0.0, 0.0]), ('thickness', 0.0012000001),
    ('use_border', True), ('use_multiview', True), ('image_views_format', 'STEREO_3D'),
    ('workbench', {'show_xray': True})])
def test_cli_refuses_changed_render_state(tmp_path, inputs, monkeypatch, capsys, key, value):
    module = load()
    monkeypatch.setattr(module, 'run_blender', fake_runner(mutate_render=lambda r: r.update({key: value})))
    state = snapshot(tmp_path)
    assert module.main(argv(*inputs, tmp_path / 'ev' / 'out')) == 2
    assert key in capsys.readouterr().err
    assert snapshot(tmp_path) == state


@pytest.mark.parametrize('mutate', [
    lambda r: r.clear(), lambda r: r.pop('exposure'), lambda r: r.update(unknown=1),
    lambda r: r.update(exposure=float('nan')), lambda r: r.update(gamma=float('inf')),
    lambda r: r.update(thickness=0), lambda r: r.update(thickness=-1),
    lambda r: r.update(thickness=None), lambda r: r.update(thickness=True),
    lambda r: r.update(world_color=[0, 0]), lambda r: r.update(background_color=[0, 0, float('nan')]),
    lambda r: r.update(world_use_nodes=1), lambda r: r.update(look=''),
    lambda r: r.update(background_type='unknown'),
    lambda r: r.pop('use_curve_mapping'), lambda r: r.update(use_curve_mapping=1),
    lambda r: r.pop('use_white_balance'), lambda r: r.update(use_white_balance=1),
    lambda r: r.pop('emulation'), lambda r: r.update(emulation=''),
    lambda r: r.update(emulation=1), lambda r: r.update(emulation='unsupported'),
    lambda r: r.update(use_border=1), lambda r: r.update(use_multiview=0),
    lambda r: r.update(image_views_format='unknown'), lambda r: r.update(workbench=None)])
def test_cli_refuses_invalid_render_state(tmp_path, inputs, monkeypatch, mutate):
    module = load()
    monkeypatch.setattr(module, 'run_blender', fake_runner(mutate_render=mutate))
    state = snapshot(tmp_path)
    assert module.main(argv(*inputs, tmp_path / 'ev' / 'out')) == 2
    assert snapshot(tmp_path) == state


def test_render_state_generated_presence_and_numeric_probes():
    """Exhaust all presence subsets, then nonfinite values in every numeric component."""
    module = load()
    keys = list(RENDER)
    for mask in range(1 << len(keys)):
        state = {k: copy.deepcopy(RENDER[k]) for i, k in enumerate(keys) if mask & (1 << i)}
        if len(state) == len(keys):
            assert module.compare_render_state(state, state) == []
        else:
            with pytest.raises(ValueError, match='render keys'):
                module.compare_render_state(state, state)
    for key in ('exposure', 'gamma', 'thickness', 'world_color', 'background_color'):
        for index in range(3 if isinstance(RENDER[key], list) else 1):
            for bad in (float('nan'), float('inf'), -float('inf')):
                state = copy.deepcopy(RENDER)
                if isinstance(state[key], list):
                    state[key][index] = bad
                else:
                    state[key] = bad
                with pytest.raises(ValueError, match=key):
                    module.compare_render_state(state, state)


@pytest.mark.parametrize('value', [None, 0, 1, 'False', '', [], {}, float('nan'), float('inf')])
@pytest.mark.parametrize('key', ['use_curve_mapping', 'use_white_balance'])
def test_render_state_refuses_nonboolean_curve_mapping(value, key):
    module = load()
    state = dict(RENDER, **{key: value})
    with pytest.raises(ValueError, match=key + '.*boolean'):
        module.compare_render_state(state, state)


@pytest.mark.parametrize('value', ['', 'unsupported', None, 1, True, [], float('nan')])
def test_render_state_refuses_unsupported_emulation(value):
    state = dict(RENDER, emulation=value)
    with pytest.raises(ValueError, match='emulation'):
        load().compare_render_state(state, state)


@pytest.mark.parametrize('key', ['use_curve_mapping', 'use_white_balance', 'emulation'])
def test_render_state_missing_curve_mapping_refused(key):
    module = load()
    state = dict(RENDER)
    del state[key]
    with pytest.raises(ValueError, match=key):
        module.compare_render_state(state, state)


@pytest.mark.parametrize('key', ['use_curve_mapping', 'use_white_balance', 'emulation'])
def test_render_state_curve_mapping_mismatch_and_reset(key):
    module = load()
    changed = dict(RENDER, **{key: 'OFF' if key == 'emulation' else True})
    for _ in range(3):
        assert module.compare_render_state(RENDER, changed) == [key]
        assert module.compare_render_state(changed, RENDER) == [key]
        assert module.compare_render_state(RENDER, dict(RENDER)) == []


def test_render_state_repeated_failure_and_reset():
    module = load()
    for _ in range(3):
        bad = dict(RENDER, exposure=3.0)
        assert module.compare_render_state(RENDER, bad) == ['exposure']
        assert module.compare_render_state(bad, RENDER) == ['exposure']
        assert module.compare_render_state(RENDER, copy.deepcopy(RENDER)) == []


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


@pytest.mark.parametrize('key,value', [
    ('use_border', True), ('use_multiview', True), ('image_views_format', 'STEREO_3D'),
    ('use_border', None), ('use_multiview', None), ('image_views_format', None)])
def test_cli_refuses_changed_output_setting(tmp_path, inputs, monkeypatch, capsys, key, value):
    module = load()
    original = fake_runner()

    def runner(*args, **kwargs):
        record = original(*args, **kwargs)
        for role in ('before', 'after'):
            record[role]['render'].update(use_border=False, use_multiview=False,
                                          image_views_format='INDIVIDUAL')
        if value is None:
            del record['after']['render'][key]
        else:
            record['after']['render'][key] = value
        return record

    monkeypatch.setattr(module, 'run_blender', runner)
    output = tmp_path / 'ev' / 'changed'
    assert module.main(argv(*inputs, output)) == 2
    assert key in capsys.readouterr().err
    assert not output.exists() and not output.with_name('changed.partial').exists()


def blender():
    sys.path.insert(0, str(ROOT / 'src'))
    from dt_ai.core.blender_runner import blender_executable
    exe = blender_executable()
    return exe if Path(exe).is_file() else None


OUTPUT_SCENES = r'''
import bpy, sys
root, mutation = sys.argv[sys.argv.index('--') + 1:]
assert bpy.app.version[:3] == (5, 1, 2), bpy.app.version_string
for role in ('before', 'after'):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.ops.mesh.primitive_cube_add()
    scene = bpy.context.scene
    # Make distinct source bytes without changing geometry or visible content.
    scene['synthetic_role'] = role
    r = scene.render
    if role == 'after':
        if mutation in ('border', 'crop', 'combined'):
            r.use_border = True
            r.use_crop_to_border = mutation != 'border'
            r.border_max_x = 0.5
        if mutation in ('multiview', 'combined'):
            r.use_multiview = True
            r.views_format = 'STEREO_3D'
        if mutation in ('image_views_format', 'multiview', 'combined'):
            r.image_settings.views_format = 'STEREO_3D'
        if mutation == 'combined':
            scene.display.shading.show_xray = True
            scene.display.shading.show_object_outline = True
        if mutation == 'reset':
            r.use_border = r.use_multiview = True
            r.use_border = r.use_multiview = False
    bpy.ops.wm.save_as_mainfile(filepath=root + '/' + role + '.blend')
'''


@pytest.mark.skipif(blender() is None or os.environ.get('RUN_BLENDER_SMOKE') != '1',
                    reason='opt in with RUN_BLENDER_SMOKE=1 (real Blender render)')
@pytest.mark.parametrize('mutation', ['border', 'crop', 'multiview', 'image_views_format',
                                      'combined', 'reset'])
def test_real_blender_output_settings_normalized(tmp_path, mutation):
    from dt_ai.core.blender_runner import run_blender
    module = load()
    maker = tmp_path / 'make-output.py'
    maker.write_text(OUTPUT_SCENES, encoding='utf-8')
    a, b = tmp_path / 'before.blend', tmp_path / 'after.blend'
    run_blender(maker, [tmp_path, mutation], outputs=[a, b],
                log_path=tmp_path / 'maker.log')
    hashes = [module.sha256(p) for p in (a, b)]
    output = tmp_path / 'ev' / mutation
    child = subprocess.run([sys.executable, str(SCRIPT), *argv(a, b, output,
                            '--resolution', '64x40', '--style', 'solid')],
                            capture_output=True, text=True)
    assert child.returncode == 0, child.stdout + child.stderr
    evidence = json.loads((output / 'render-evidence.json').read_text(encoding='utf-8'))
    assert evidence['before']['render'] == evidence['after']['render']
    assert (output / 'before.png').read_bytes() == (output / 'after.png').read_bytes()
    for key, expected in (('use_border', False), ('use_multiview', False),
                          ('image_views_format', 'INDIVIDUAL')):
        assert evidence['before']['render'][key] == expected
    assert [module.sha256(p) for p in (a, b)] == hashes


# ---------------------------------------------------------------- real Blender (optional)


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
    subprocess.run([blender(), '--background', '--factory-startup', '--python-exit-code', '1',
                    '--python', str(maker), '--',
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
    assert all(math.isfinite(v) for v in manifest['camera']['projection'])
    wire = tmp_path / 'ev' / 'wire'
    assert module.main(argv(a, b, wire, '--resolution', '64x40', '--style', 'wire')) == 0
    evidence = json.loads((wire / 'render-evidence.json').read_text(encoding='utf-8'))
    assert [evidence[r]['mesh_objects'] for r in ('before', 'after')] == [1, 1]  # r1 P3: no wire copies


MAKE_RENDER_SCENES = r'''
import bpy, sys
out = sys.argv[sys.argv.index('--') + 1:]
for index, path in enumerate(out[:2]):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add(size=8 if index and out[2] in ('extent', 'combined') else 2)
    scene = bpy.context.scene
    data = bpy.data.cameras.new('Shot')
    cam = bpy.data.objects.new('Shot', data)
    scene.collection.objects.link(cam)
    cam.location = (0, -20, 0)
    cam.rotation_euler = (1.5707963, 0, 0)
    if index:
        if out[2] in ('exposure', 'combined'):
            scene.view_settings.exposure = 2
        if out[2] in ('curve', 'combined'):
            scene.view_settings.use_curve_mapping = True
            scene.view_settings.curve_mapping.curves[3].points[1].location = (1.0, 0.4)
            scene.view_settings.curve_mapping.update()
        if out[2] in ('whitebalance', 'combined'):
            scene.view_settings.use_white_balance = True
            scene.view_settings.white_balance_temperature = 2500
            scene.view_settings.white_balance_tint = -20
        if out[2] in ('gamma', 'combined'):
            scene.view_settings.gamma = 1.8
        if out[2] in ('look', 'combined'):
            scene.view_settings.look = 'AgX - Medium High Contrast'
        if out[2] in ('display', 'combined'):
            scene.display_settings.display_device = 'Display P3'
        if out[2] in ('emulation', 'combined'):
            scene.display_settings.emulation = 'OFF'
        if out[2] in ('world', 'combined'):
            scene.world = bpy.data.worlds.new('SyntheticWorld')
            scene.world.color = (1, 0, 0)
            scene.world.node_tree.nodes.get('Background').inputs['Color'].default_value = (0, 1, 0, 1)
        if out[2] in ('background', 'combined'):
            scene.display.shading.background_type = 'WORLD'
            scene.display.shading.background_color = (0.8, 0.1, 0.2)
        if out[2] == 'combined':
            scene.render.use_border = True
            scene.render.border_max_x = 0.5
            scene.render.use_multiview = True
            scene.render.image_settings.views_format = 'STEREO_3D'
            scene.display.shading.show_xray = True
            scene.display.shading.show_object_outline = True
            scene.display.shading.show_specular_highlight = False
    bpy.ops.wm.save_as_mainfile(filepath=path)
'''


@pytest.mark.skipif(blender() is None or os.environ.get('RUN_BLENDER_SMOKE') != '1',
                    reason='opt in with RUN_BLENDER_SMOKE=1 (real Blender render)')
@pytest.mark.parametrize('change,style,mode', [
    ('exposure', 'wire', 'fit'), ('exposure', 'solid', 'fit'), ('extent', 'wire', 'fit'),
    ('whitebalance', 'solid', 'fit'), ('whitebalance', 'wire', 'fit'), ('whitebalance', 'solid', 'named'),
    ('emulation', 'solid', 'fit'), ('emulation', 'wire', 'fit'),
    ('curve', 'solid', 'fit'), ('curve', 'wire', 'fit'), ('curve', 'solid', 'named'),
    ('gamma', 'wire', 'fit'), ('look', 'wire', 'fit'), ('display', 'wire', 'fit'),
    ('world', 'material', 'fit'), ('background', 'texture', 'fit'),
    ('combined', 'wire', 'fit'), ('combined', 'wire', 'named')])
def test_real_blender_normalizes_saved_render_state(tmp_path, change, style, mode):
    """Synthetic saved scenes: source exposure and size must not change render settings."""
    module = load()
    maker = tmp_path / 'make.py'
    maker.write_text(MAKE_RENDER_SCENES, encoding='utf-8')
    a, b = tmp_path / 'a.blend', tmp_path / 'b.blend'
    from dt_ai.core.blender_runner import run_blender
    run_blender(maker, [a, b, change], outputs=[a, b], log_path=tmp_path / 'make.log')
    output = tmp_path / 'ev' / change
    assert module.main(argv(a, b, output, '--resolution', '64x40', '--style', style,
                            '--camera-mode', mode, '--camera-name', 'Shot')) == 0
    evidence = json.loads((output / 'render-evidence.json').read_text(encoding='utf-8'))
    left, right = (evidence[r]['render'] for r in ('before', 'after'))
    assert left == right
    assert left['exposure'] == 0.0 and left['gamma'] == 1.0
    assert left['look'] == 'None' and left['view_transform'] == 'Standard'
    assert left['use_curve_mapping'] is False
    assert left['use_white_balance'] is False
    assert left['emulation'] == 'AUTO'
    assert left['use_border'] is False and left['use_multiview'] is False
    assert left['image_views_format'] == 'INDIVIDUAL'
    assert left['workbench']['show_xray'] is False
    assert left['workbench']['show_object_outline'] is False
    assert left['workbench']['show_specular_highlight'] is True
    assert left['display_device'] == 'sRGB' and left['background_type'] == 'VIEWPORT'
    assert left['background_color'] == pytest.approx([0.05] * 3)
    assert left['world_color'] == pytest.approx([0.05] * 3)
    assert left['thickness'] == right['thickness']
    if style == 'wire':
        assert left['thickness'] == pytest.approx(0.0048 if change in ('extent', 'combined') else 0.0012)
    else:
        assert left['thickness'] is None
    if change not in ('extent', 'combined'):
        from PIL import Image
        assert Image.open(output / 'before.png').tobytes() == Image.open(output / 'after.png').tobytes()
        if change in ('curve', 'whitebalance'):
            assert (output / 'before.png').read_bytes() == (output / 'after.png').read_bytes()


CHECK_COLOUR_RNA = r'''
import ast, bpy, json, sys
from pathlib import Path
source = ast.parse(Path(sys.argv[sys.argv.index('--') + 1]).read_text(encoding='utf-8'))
setup = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == 'setup')
assignments = {ast.unparse(target): node.value for node in ast.walk(setup)
               if isinstance(node, ast.Assign) for target in node.targets}
# Dependent values cannot affect output with their master switches disabled.
# curve_mapping is a read-only pointer to mutable curves; also prove its switch off.
gated = {'view_settings': {'white_balance_temperature', 'white_balance_tint',
                           'white_balance_whitepoint'}, 'display_settings': set()}
for switch in ('use_curve_mapping', 'use_white_balance'):
    assert ast.literal_eval(assignments['scene.view_settings.' + switch]) is False, switch
inventory = {}
for owner in ('view_settings', 'display_settings'):
    writable = {p.identifier for p in getattr(bpy.context.scene, owner).bl_rna.properties
                if not p.is_readonly}
    handled = {key.removeprefix('scene.' + owner + '.') for key in assignments
               if key.startswith('scene.' + owner + '.')}
    unknown = writable - handled - gated[owner]
    assert not unknown, f'unhandled writable {owner}: {sorted(unknown)}'
    inventory[owner] = sorted(writable)
    print(owner, 'writable:', sorted(writable), 'gated:', sorted(gated[owner]))
Path(sys.argv[sys.argv.index('--') + 2]).write_text(json.dumps(inventory), encoding='utf-8')
'''


@pytest.mark.skipif(blender() is None or os.environ.get('RUN_BLENDER_SMOKE') != '1',
                    reason='opt in with RUN_BLENDER_SMOKE=1 (real Blender RNA)')
def test_real_blender_colour_rna_has_no_unhandled_writable_properties(tmp_path):
    """Blender upgrades must not silently add inherited colour state to this helper."""
    script = tmp_path / 'colour_rna.py'
    script.write_text(CHECK_COLOUR_RNA, encoding='utf-8')
    from dt_ai.core.blender_runner import run_blender
    report = tmp_path / 'rna.json'
    inventory = run_blender(script, [load().BLENDER_SCRIPT, report], output_json=report,
                           log_path=tmp_path / 'rna.log')
    assert 'use_white_balance' in inventory['view_settings']
    assert 'emulation' in inventory['display_settings']


MAKE_SENSOR_SCENES = r'''
import bpy, sys
out = sys.argv[sys.argv.index('--') + 1:]
for path, sensor_height in ((out[0], 24.0), (out[1], 48.0)):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
    data = bpy.data.cameras.new('Shot')
    data.type = 'PERSP'
    data.sensor_fit = 'VERTICAL'
    data.sensor_height = sensor_height
    cam = bpy.data.objects.new('Shot', data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = (0, -10, 0)
    cam.rotation_euler = (1.5707963, 0, 0)
    bpy.ops.wm.save_as_mainfile(filepath=path)
'''


@pytest.mark.skipif(blender() is None or os.environ.get('RUN_BLENDER_SMOKE') != '1',
                    reason='opt in with RUN_BLENDER_SMOKE=1 (real Blender render)')
def test_real_blender_named_sensor_height_mismatch_refused(tmp_path, capsys):
    """Review r1 P1: same transform, sensor_fit VERTICAL, sensor_height 24 vs 48 = 2x FOV -> exit 2."""
    module = load()
    maker = tmp_path / 'make.py'
    maker.write_text(MAKE_SENSOR_SCENES, encoding='utf-8')
    a, b = tmp_path / 'a.blend', tmp_path / 'b.blend'
    subprocess.run([blender(), '--background', '--factory-startup', '--python-exit-code', '1',
                    '--python', str(maker), '--', str(a), str(b)], check=True, capture_output=True)
    bad = tmp_path / 'ev' / 'sensor'
    assert module.main(argv(a, b, bad, '--camera-mode', 'named', '--camera-name', 'Shot',
                            '--resolution', '320x200', '--style', 'solid')) == 2
    err = capsys.readouterr().err
    assert 'sensor_height' in err and 'projection' in err
    assert not bad.exists() and not bad.with_name('sensor.partial').exists()


# #1468: synthetic native inputs, not customer model/acceptance evidence.
WORKBENCH_MUTATIONS = {
    'show_object_outline': True,
    'object_outline_color': [1.0, 0.0, 0.0],
    'show_xray': True,
    'show_specular_highlight': False,
    'studio_light': 'paint.sl',
    'studiolight_rotate_z': 1.5,
    'xray_alpha': 0.1,
    'show_backface_culling': True,
    'render_aa': 'OFF',
    'light_direction': [0.0, 0.0, -1.0],
    'use_dof': True,
}
WORKBENCH_EXPECTED = {
    'show_object_outline': False,
    'object_outline_color': [0.0, 0.0, 0.0],
    'show_xray': False,
    'show_specular_highlight': True,
    'studio_light': 'Default',
    'studiolight_rotate_z': 0.0,
    'xray_alpha': 0.5,
    'show_backface_culling': False,
    'render_aa': '8',
    'light_direction': [1 / math.sqrt(3)] * 3,
    'use_dof': False,
}
MAKE_WORKBENCH_SCENES = r'''
import bpy, json, sys
from pathlib import Path
root = Path(sys.argv[sys.argv.index('--') + 1])
mutations = json.loads((root / 'mutations.json').read_text())
readback = {}
for label in ['baseline', *mutations, 'combined']:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    assert bpy.app.background and bpy.app.version[:2] == (5, 1)
    assert bpy.data.filepath == '' and scene.unit_settings.system == 'METRIC'
    bpy.ops.mesh.primitive_cube_add()
    changes = mutations if label == 'combined' else ({label: mutations[label]} if label != 'baseline' else {})
    for key, value in changes.items():
        owner = scene.display if key in ('render_aa', 'light_direction') else scene.display.shading
        setattr(owner, key, value)
    # Red outline makes the review witness unmistakable; separately test colour too.
    if label in ('show_object_outline', 'combined'):
        scene.display.shading.object_outline_color = (1, 0, 0)
    if label == 'combined':
        # Combine new flags with earlier setup invariants and hostile PNG stamps.
        scene.display.shading.light = 'MATCAP'
        scene.display.shading.show_cavity = True
        scene.display.shading.show_shadows = True
        scene.display.shading.color_type = 'RANDOM'
        scene.display.shading.single_color = (0.1, 0.2, 0.3)
        scene.render.use_stamp = True
        scene.render.use_stamp_note = True
        scene.render.stamp_note_text = 'synthetic inherited note'
    path = root / (label + '.blend')
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False)
    scene = bpy.context.scene
    values = {}
    for key in mutations:
        owner = scene.display if key in ('render_aa', 'light_direction') else scene.display.shading
        value = getattr(owner, key)
        values[key] = value if isinstance(value, (str, bool, float)) else list(value)
    readback[label] = values
(root / 'saved-state.json').write_text(json.dumps(readback))
'''


@pytest.fixture(scope='module')
def workbench_scenes(tmp_path_factory):
    from dt_ai.core.blender_runner import run_blender
    root = tmp_path_factory.mktemp('synthetic-workbench')
    maker = root / 'make.py'
    maker.write_text(MAKE_WORKBENCH_SCENES, encoding='utf-8')
    (root / 'mutations.json').write_text(json.dumps(WORKBENCH_MUTATIONS), encoding='utf-8')
    saved = run_blender(maker, [root], output_json=root / 'saved-state.json',
                        outputs=[root / (name + '.blend') for name in ['baseline', *WORKBENCH_MUTATIONS, 'combined']],
                        log_path=root / 'make.log')
    for key in WORKBENCH_MUTATIONS:
        assert saved[key][key] != saved['baseline'][key], key
    return root


@pytest.mark.skipif(blender() is None or os.environ.get('RUN_BLENDER_SMOKE') != '1',
                    reason='opt in with RUN_BLENDER_SMOKE=1 (real Blender render)')
@pytest.mark.parametrize('flag,style,reverse',
    [(key, 'solid', False) for key in WORKBENCH_MUTATIONS]
    + [('combined', style, False) for style in ('solid', 'wire', 'material', 'texture')]
    + [('combined', 'solid', True)])
def test_real_blender_workbench_flags_normalized(workbench_scenes, tmp_path, flag, style, reverse):
    module = load()
    a, b = workbench_scenes / 'baseline.blend', workbench_scenes / (flag + '.blend')
    if reverse:
        a, b = b, a
    hashes = module.sha256(a), module.sha256(b)
    output = tmp_path / 'ev' / 'normalized'
    assert module.main(argv(a, b, output, '--resolution', '64x40', '--style', style)) == 0
    evidence = json.loads((output / 'render-evidence.json').read_text(encoding='utf-8'))
    assert evidence['before']['render'] == evidence['after']['render']
    assert (output / 'before.png').read_bytes() == (output / 'after.png').read_bytes(), flag
    state = evidence['before']['render']['workbench']
    assert set(state) == set(WORKBENCH_EXPECTED)
    for key, expected in WORKBENCH_EXPECTED.items():
        if isinstance(expected, (float, list)):
            assert state[key] == pytest.approx(expected), key
        else:
            assert state[key] == expected, key
    assert (module.sha256(a), module.sha256(b)) == hashes

