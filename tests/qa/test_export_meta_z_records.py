"""new-case: VPM exporters emit per-FBX world bounds + FBX SHA-256 that V013 consumes (#1342)."""
import copy
import hashlib
import importlib.util
import json
import random
import subprocess
from pathlib import Path

import pytest

import validate_package as vp
from test_scene import PROFILES, mesh, rb

ROOT = Path(__file__).resolve().parents[2]
BOUNDS = [[-1.0, -1.0, -0.3], [1.0, 1.0, 8.35]]
NAME = 'SM_Test_K_1.fbx'
EXPORTERS = ['jobs/KPP1/scripts/export_vpm.py', 'jobs/TEC26-OKS/scripts/export_vpm.py',
             'jobs/PSU275/scripts/export_vpm_psu275.py']


def owner():
    spec = importlib.util.spec_from_file_location('export_meta_1342', ROOT / 'adapters/max/agr_tools/export_meta.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exporter_meta(fbx: Path, bounds=BOUNDS):
    """The shape the three VPM exporters write next to the package (export_meta.json)."""
    return {'address': 'Test_K_1', 'fbx': str(fbx), 'h_otn_model_max_z_m': round(bounds[1][2], 2),
            'thumbnail': 'thumbnail_256.jpg', 'fbx_records': {fbx.name: owner().fbx_record(fbx, bounds)}}


def run_cli(tmp_path, monkeypatch, meta, capsys, readback_bounds=BOUNDS):
    fbx = tmp_path / NAME
    m = mesh()
    m['bounds_m'] = readback_bounds
    monkeypatch.setattr(vp, 'readback', lambda p: rb(m))
    path = tmp_path / 'export_meta.json'
    path.write_text(json.dumps(meta) if not isinstance(meta, str) else meta, encoding='utf-8')
    code = vp.main([str(fbx), '--profile', 'vpm', '--scene', '--json', '--export-meta', str(path)])
    out = capsys.readouterr()
    return code, out


def v013(out_text):
    report = json.loads(out_text)
    return [f['status'] for s in report['stages'] for f in s['findings'] if f['name'] == 'Z bounds vs export_meta']


@pytest.fixture
def fbx(tmp_path):
    path = tmp_path / NAME
    path.write_bytes(b'synthetic FBX bytes (#1342 test, not a real object)')
    return path


def test_fbx_record_hashes_exported_bytes(fbx):
    record = owner().fbx_record(fbx, BOUNDS)
    assert record == {'bounds_m': BOUNDS, 'fbx_sha256': hashlib.sha256(fbx.read_bytes()).hexdigest()}


def test_exporter_meta_validates(fbx):
    meta = exporter_meta(fbx)
    assert owner().validate_meta(copy.deepcopy(meta)) == meta
    assert owner().z_meta_mapping(meta) == meta['fbx_records']


@pytest.mark.parametrize('shift,status', [(0.0, 'pass'), (1.40, 'fail'), (-1.40, 'fail')])
def test_cli_consumes_exporter_meta(tmp_path, monkeypatch, capsys, fbx, shift, status):
    meta = exporter_meta(fbx)
    meta['fbx_records'][NAME]['bounds_m'][1][2] += shift
    meta['fbx_records'][NAME]['bounds_m'][0][2] += shift
    _, out = run_cli(tmp_path, monkeypatch, meta, capsys)
    assert v013(out.out) == [status]


def test_cli_stale_fbx_after_export_fails(tmp_path, monkeypatch, capsys, fbx):
    meta = exporter_meta(fbx)
    fbx.write_bytes(b'changed after export')
    _, out = run_cli(tmp_path, monkeypatch, meta, capsys)
    assert v013(out.out) == ['fail']


@pytest.mark.parametrize('payload', ['legacy', 'duplicate_key', 'nan', 'not_json'])
def test_cli_refuses_unusable_exporter_meta(tmp_path, monkeypatch, capsys, fbx, payload):
    meta = exporter_meta(fbx)
    if payload == 'legacy':
        del meta['fbx_records']
    text = json.dumps(meta)
    if payload == 'duplicate_key':
        text = text.replace('"address": "Test_K_1",', '"address": "Test_K_1", "address": "Other",')
    elif payload == 'nan':
        text = text.replace('8.35]', 'NaN]')
    elif payload == 'not_json':
        text = text[:-3]
    code, out = run_cli(tmp_path, monkeypatch, text, capsys)
    assert code != 0 and 'export_meta' in out.err and not out.out
    if payload == 'legacy':
        assert 'fbx_records' in out.err


def test_cli_bare_mapping_still_accepted(tmp_path, monkeypatch, capsys, fbx):
    _, out = run_cli(tmp_path, monkeypatch, exporter_meta(fbx)['fbx_records'], capsys)
    assert v013(out.out) == ['pass']


def _bad_records(fbx, rng):
    """Generated malformed fbx_records: every one must be refused by validate_meta, never passed."""
    good = owner().fbx_record(fbx, BOUNDS)
    mutations = [
        lambda r: {},
        lambda r: [],
        lambda r: {NAME: None},
        lambda r: {'SM Test.fbx': r[NAME]},
        lambda r: {'../SM_Test_K_1.fbx': r[NAME]},
        lambda r: {NAME.replace('.fbx', '.FBX'): r[NAME]},
        lambda r: {NAME: {**r[NAME], 'extra': 1}},
        lambda r: {NAME: {'bounds_m': r[NAME]['bounds_m']}},
        lambda r: {NAME: {**r[NAME], 'fbx_sha256': 'x' * 64}},
        lambda r: {NAME: {**r[NAME], 'fbx_sha256': r[NAME]['fbx_sha256'].upper()}},
        lambda r: {NAME: {**r[NAME], 'fbx_sha256': r[NAME]['fbx_sha256'][:-1]}},
        lambda r: {NAME: {**r[NAME], 'bounds_m': []}},
        lambda r: {NAME: {**r[NAME], 'bounds_m': [[0, 0, 0]]}},
        lambda r: {NAME: {**r[NAME], 'bounds_m': [[0, 0, 0], [1, 1]]}},
        lambda r: {NAME: {**r[NAME], 'bounds_m': [[0, 0, float('nan')], [1, 1, 1]]}},
        lambda r: {NAME: {**r[NAME], 'bounds_m': [[0, 0, 0], [1, 1, float('inf')]]}},
        lambda r: {NAME: {**r[NAME], 'bounds_m': [[0, 0, True], [1, 1, 1]]}},
        lambda r: {NAME: {**r[NAME], 'bounds_m': [[0, 0, '0'], [1, 1, 1]]}},
        lambda r: {NAME: {**r[NAME], 'bounds_m': [[0, 0, 2], [1, 1, 1]]}},
        lambda r: {'Other.fbx': r[NAME]},  # does not name the exported fbx
        lambda r: {NAME: r[NAME], 'SM_Test_k_1.fbx': r[NAME]},  # casefold duplicate
    ]
    for _ in range(200):
        yield rng.choice(mutations)({NAME: copy.deepcopy(good)})


def test_generated_malformed_records_refused(fbx):
    """Probe: 200 seeded malformed fbx_records -> 200/200 ValueError (never accepted)."""
    module = owner()
    refused = 0
    for records in _bad_records(fbx, random.Random(1342)):
        meta = exporter_meta(fbx)
        meta['fbx_records'] = records
        with pytest.raises(ValueError, match='export_meta'):
            module.validate_meta(meta)
        refused += 1
    assert refused == 200


def test_fbx_record_refuses_missing_or_bad_bounds(tmp_path):
    module = owner()
    with pytest.raises(ValueError, match='missing'):
        module.fbx_record(tmp_path / 'SM_None.fbx', BOUNDS)
    target = tmp_path / NAME
    target.write_bytes(b'x')
    with pytest.raises(ValueError, match='export_meta'):
        module.fbx_record(target, [[0, 0, float('nan')], [1, 1, 1]])


@pytest.mark.parametrize('script', EXPORTERS)
def test_exporters_emit_fbx_records(script):
    text = (ROOT / script).read_text(encoding='utf-8')
    assert 'fbx_record(' in text and '"fbx_records"' in text


MASTER = r'''
import bpy, sys
out, dz = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True)
def box(name, lo, hi):
    me = bpy.data.meshes.new(name)
    xs, ys, zs = (lo[0], hi[0]), (lo[1], hi[1]), (lo[2], hi[2])
    v = [(x, y, z) for x in xs for y in ys for z in zs]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me.from_pydata(v, [], f)
    me.uv_layers.new(name="UVMap")
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    return o
dz = float(dz)
for name, lo, hi in (("SM_Synth_1_Main", (100, 200, dz), (110, 206, 8.35 + dz)),
                     ("SM_Synth_1_MainGlass", (101, 199.9, 1 + dz), (109, 200, 7 + dz)),
                     ("UCX_SM_Synth_1_Main_001", (100, 199.9, dz), (110, 206, 8.35 + dz))):
    o = box(name, lo, hi)
    if not name.startswith("UCX_"):
        m = bpy.data.materials.new("M_" + name)
        m.use_nodes = True
        o.data.materials.append(m)
bpy.ops.wm.save_as_mainfile(filepath=out)
'''


@pytest.mark.blender
@pytest.mark.parametrize('script', EXPORTERS)
def test_real_export_feeds_v013(tmp_path, capsys, script):
    """Synthetic master (not a real object) -> real exporter -> validate_package with the produced meta."""
    from twinqa.scene import find_blender
    blender = find_blender()
    if blender is None:
        pytest.skip('Blender unavailable')
    builder = tmp_path / 'make_master.py'
    builder.write_text(MASTER, encoding='utf-8')
    master = tmp_path / 'master.blend'
    subprocess.run([blender, '--background', '--factory-startup', '--python-exit-code', '1', '--python',
                    str(builder), '--', str(master), '0'], check=True, capture_output=True, timeout=600)
    pkg = tmp_path / 'out' / 'pkg'
    proc = subprocess.run([blender, '--background', '--factory-startup', '--python-exit-code', '1', '--python',
                           str(ROOT / script), '--', str(master), str(pkg)], capture_output=True, text=True,
                          encoding='utf-8', errors='replace', timeout=900)
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    meta_path = tmp_path / 'out' / 'export_meta.json'
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    fbx = pkg / 'SM_Synth_1.fbx'
    records = owner().z_meta_mapping(meta)
    assert set(records) == {fbx.name}
    assert records[fbx.name]['fbx_sha256'] == hashlib.sha256(fbx.read_bytes()).hexdigest()
    assert records[fbx.name]['bounds_m'][1][2] == pytest.approx(8.35, abs=1e-5)
    vp.main([str(fbx), '--profile', 'vpm', '--scene', '--json', '--export-meta', str(meta_path)])
    assert v013(capsys.readouterr().out) == ['pass']
    for z in (0, 1):
        meta['fbx_records'][fbx.name]['bounds_m'][z][2] += 1.40
    shifted = tmp_path / 'out' / 'export_meta_shifted.json'
    shifted.write_text(json.dumps(meta), encoding='utf-8')
    vp.main([str(fbx), '--profile', 'vpm', '--scene', '--json', '--export-meta', str(shifted)])
    assert v013(capsys.readouterr().out) == ['fail']
