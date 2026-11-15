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


def fake_runner(after_camera=None, touch=None):
    def run(script, args, *, executable=None, output_json=None, outputs=(), timeout=900, log_path=None):
        cfg = json.loads(Path(args[0]).read_text(encoding='utf-8'))
        out = Path(cfg['output_dir'])
        write_png(out / 'before.png', (200, 50, 50))
        write_png(out / 'after.png', (50, 200, 50))
        if touch:
            touch()
        state = {'engine': 'BLENDER_WORKBENCH', 'style': 'wire',
                 'color_management': 'FOLLOW_SCENE', 'use_sequencer': False,
                 'use_compositing': False, 'use_border': False, 'use_multiview': False,
                 'image_views_format': 'INDIVIDUAL'}
        record = {'before': {'camera': CAM, 'render': dict(state)},
                  'after': {'camera': after_camera or CAM, 'render': dict(state)}}
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


@pytest.mark.parametrize('key,bad', [('color_management', 'OVERRIDE'),
                                   ('use_sequencer', True), ('use_compositing', True)])
@pytest.mark.parametrize('missing', [False, True])
def test_output_pipeline_evidence_fails_closed(tmp_path, inputs, monkeypatch, key, bad, missing):
    module = load()
    runner = fake_runner()

    def changed(*args, **kwargs):
        records = runner(*args, **kwargs)
        for role in ('before', 'after'):
            records[role]['render'].update(color_management='FOLLOW_SCENE',
                                           use_sequencer=False, use_compositing=False)
        if missing:
            del records['after']['render'][key]
        else:
            records['after']['render'][key] = bad
        return records

    monkeypatch.setattr(module, 'run_blender', changed)
    output = tmp_path / 'ev' / 'out'
    original = snapshot(tmp_path)
    assert module.main(argv(*inputs, output)) == 2
    assert snapshot(tmp_path) == original


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


MAKE_OUTPUT_SCENES = r'''
import bpy, sys
paths = sys.argv[sys.argv.index('--') + 1:]
mask = int(paths[2])
for index, path in enumerate(paths[:2]):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add()
    scene = bpy.context.scene
    # Isolate pipeline settings from the independently owned stamp-metadata issue.
    for prop in scene.render.bl_rna.properties:
        if prop.identifier.startswith('use_stamp') and prop.type == 'BOOLEAN':
            setattr(scene.render, prop.identifier, False)
    if index == 1:
        scene['synthetic_variant'] = mask  # distinct input bytes even for the reset control
        if mask & 1:
            image = scene.render.image_settings
            image.color_management = 'OVERRIDE'
            image.view_settings.view_transform = 'AgX'
            image.view_settings.exposure = 2.0
        if mask & 2:
            editor = scene.sequence_editor_create()
            strip = editor.strips.new_effect('SyntheticRed', 'COLOR', channel=1,
                                             frame_start=1, length=9)
            strip.color = (1, 0, 0)
            scene.render.use_sequencer = True
            assert len(editor.strips) == 1
        if mask & 4:
            group = bpy.data.node_groups.new('SyntheticRed', 'CompositorNodeTree')
            group.interface.new_socket(name='Image', in_out='OUTPUT', socket_type='NodeSocketColor')
            rgb = group.nodes.new('CompositorNodeRGB')
            rgb.outputs[0].default_value = (1, 0, 0, 1)
            output = group.nodes.new('NodeGroupOutput')
            group.links.new(rgb.outputs[0], output.inputs['Image'])
            scene.compositing_node_group = group
            scene.render.use_compositing = True
            assert scene.compositing_node_group == group
    bpy.ops.wm.save_as_mainfile(filepath=path)
'''


@pytest.mark.skipif(blender() is None or os.environ.get('RUN_BLENDER_SMOKE') != '1',
                    reason='opt in with RUN_BLENDER_SMOKE=1 (real Blender render)')
@pytest.mark.parametrize('mask', range(8))
def test_real_blender_output_pipeline_is_normalized(tmp_path, mask):
    """Synthetic native rows: single settings, all subsets and clean reset control."""
    module = load()
    maker = tmp_path / 'make-output.py'
    maker.write_text(MAKE_OUTPUT_SCENES, encoding='utf-8')
    a, b = tmp_path / 'a.blend', tmp_path / 'b.blend'
    module.run_blender(maker, [a, b, str(mask)], outputs=[a, b])
    original = (a.read_bytes(), b.read_bytes())
    output = tmp_path / 'evidence'
    assert module.main(argv(a, b, output, '--resolution', '64x40', '--style', 'solid')) == 0
    assert (output / 'before.png').read_bytes() == (output / 'after.png').read_bytes()
    evidence = json.loads((output / 'render-evidence.json').read_text(encoding='utf-8'))
    assert evidence['before']['render'] == evidence['after']['render']
    expected = {'color_management': 'FOLLOW_SCENE', 'use_sequencer': False,
                'use_compositing': False}
    for key, value in expected.items():
        assert evidence['before']['render'][key] == value
    manifest = json.loads((output / 'before-after.json').read_text(encoding='utf-8'))
    assert manifest['render'] == evidence['before']['render']
    assert (a.read_bytes(), b.read_bytes()) == original


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
