"""Synthetic #298 v015 site rules: MAF atlas slot remap and «Верона» insert -> placement point."""
import importlib.util
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rules = _load('site_assembly_rules_v015', 'jobs/VATUTINO-SITE/assembly_rules.py')
gen = _load('maf_gen_bench_t', 'tools/library/maf_gen_bench.py')
CFG = json.loads((ROOT / 'jobs/VATUTINO-SITE/maf/verona-gen.config.json').read_text(encoding='utf-8'))


def test_remap_rect_maps_corners_and_centre():
    src, dst = [0.0, 0.5, 0.25, 0.75], [0.5, 0.0, 1.0, 0.5]
    assert rules.remap_rect([0.0, 0.5], src, dst) == pytest.approx([0.5, 0.0])
    assert rules.remap_rect([0.25, 0.75], src, dst) == pytest.approx([1.0, 0.5])
    assert rules.remap_rect([0.125, 0.625], src, dst) == pytest.approx([0.75, 0.25])


def test_remap_rect_refuses_uv_outside_its_reviewed_slot():
    with pytest.raises(ValueError, match='outside'):
        rules.remap_rect([0.3, 0.6], [0.0, 0.5, 0.25, 0.75], [0.5, 0.0, 1.0, 0.5])


def _rot(p, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


@pytest.mark.parametrize('path,insert_rot', [
    ([[0.0, 0.0], [3.0, 1.0]], 30.0),
    ([[0.0, 0.0], [-1.5, -1.2], [0.5, -4.0]], 0.0),       # L-shape, longest segment second
    ([[0.0, 0.0], [0.0, -2.0], [2.5, -2.0]], 354.6),
])
def test_verona_point_puts_the_generated_mesh_on_the_dwg_strip(path, insert_rot):
    insert = [-7600.0, -15300.0]
    spec = dict(CFG['params'], path=path, materials={r: i + 1 for i, r in enumerate(CFG['materials'])}, name='T')
    mesh = gen.build_clad_box(spec)
    shape = {'centreline_block_m': path, 'inserts_in_568BF': [
        {'handle': 'H1', 'insert_m': insert, 'rotation_deg': insert_rot}]}
    pt = rules.verona_point(shape, mesh['plan_rotation_deg'], CFG['params']['depth'], 'VAT_MAF_T3508_99')
    assert pt['label'] == 'VAT_MAF_T3508_99' and pt['handle'] == 'H1' and pt['inside'] is True
    # engine: world = T(point) . Rz(rotation) . v_local (bbox centre anchor = local origin)
    world = [(pt['x'] + q[0], pt['y'] + q[1]) for q in (_rot(v, pt['rotation']) for v in mesh['verts'])]
    # expected: the strip of the block centreline, block -> world by the DWG insert
    lp, _, _ = gen._offsets([tuple(p) for p in path], CFG['params']['depth'] / 2)
    _, rp, _ = gen._offsets([tuple(p) for p in path], CFG['params']['depth'] / 2)
    strip = [(insert[0] + q[0], insert[1] + q[1]) for q in (_rot(p, insert_rot) for p in lp + rp)]
    for axis in (0, 1):
        assert min(w[axis] for w in world) == pytest.approx(min(s[axis] for s in strip), abs=1e-6)
        assert max(w[axis] for w in world) == pytest.approx(max(s[axis] for s in strip), abs=1e-6)


def test_verona_points_relabel_adapter_inserts_and_add_missing_ones():
    shapes = {'rows': {
        '1': {'status': 'found', 'block': 'B1', 'centreline_block_m': [[0, 0], [2, 0]],
              'inserts_in_568BF': [{'handle': 'A', 'insert_m': [1.0, 2.0], 'rotation_deg': 0}]},
        '2': {'status': 'found', 'block': 'B2', 'centreline_block_m': [[0, 0], [2, 0]],
              'inserts_in_568BF': [{'handle': 'B', 'insert_m': [5.0, 6.0], 'rotation_deg': 90}]}}}
    report = {'rows': [{'row': 1, 'set_id': 'S1', 'plan_rotation_deg': 0.0},
                       {'row': 2, 'set_id': 'S2', 'plan_rotation_deg': 0.0}]}
    adapter = [{'handle': 'A', 'label': 'B1', 'x': 1.0, 'y': 2.0, 'z': 7.5, 'rotation': 0, 'inside': True},
               {'handle': 'Z', 'label': 'Other', 'x': 0, 'y': 0, 'z': 0, 'rotation': 0, 'inside': True}]
    pts, log = rules.verona_points(shapes, report, adapter, 0.6)
    by = {p['handle']: p for p in pts}
    assert set(by) == {'A', 'B', 'Z'} and len(pts) == 3
    assert by['A']['label'] == 'S1' and by['A']['z'] == 7.5 and by['A']['x'] == pytest.approx(2.0)
    assert by['B']['label'] == 'S2' and by['B']['z'] == 0.0 and by['B']['y'] == pytest.approx(7.0)
    assert by['Z']['label'] == 'Other'
    assert {r['handle']: r['source'] for r in log} == {'A': 'adapter insert relabelled', 'B': 'plan-shapes insert added'}


def test_flora_tile_remap_equals_the_reviewed_217_remap_uv():
    # Blender's Python has no Pillow, so the assembly cannot import tools/library/flora_atlas_from_scene.py.
    from tools.library.flora_atlas_from_scene import remap_uv
    tile = [0.25, 0.5, 0.5, 0.75]
    for uv in ([0.0, 0.0], [1.0, 1.0], [0.3, 0.9], [0.5, 0.125]):
        assert rules.flora_tile_uv(uv, tile) == pytest.approx(list(remap_uv(uv, tile)), abs=1e-12)
    with pytest.raises(ValueError):
        rules.flora_tile_uv([1.2, 0.5], tile)


npm_code = _load('site_npm_code', 'jobs/VATUTINO-SITE/npm_code.py')


def _zip(path, entries):
    import zipfile
    with zipfile.ZipFile(path, 'w') as z:
        for name, data in entries.items():
            z.writestr(name, data)


def test_npm_code_rename_keeps_bytes_and_renames_every_part(tmp_path):
    import zipfile
    src = tmp_path / '0000_Vatutino.zip'
    _zip(src, {'0000_Vatutino_Ground.fbx': b'ground', '0000_Vatutino_01.fbx': b'oks'})
    dest, names, sha = npm_code.rename_npm_zip(src, '1234', tmp_path / 'out')
    assert dest.name == '1234_Vatutino.zip' and len(sha) == 64
    with zipfile.ZipFile(dest) as z:
        assert {n: z.read(n) for n in z.namelist()} == {'1234_Vatutino_Ground.fbx': b'ground', '1234_Vatutino_01.fbx': b'oks'}
    with pytest.raises(FileExistsError):
        npm_code.rename_npm_zip(src, '1234', tmp_path / 'out')


@pytest.mark.parametrize('code,entries', [('12a4', {'0000_Vatutino_Ground.fbx': b''}),
                                          ('1234', {'Other_Ground.fbx': b''}),
                                          ('1234', {'0000_Vatutino_Ground.fbx': b'', 'T_x.png': b''})])
def test_npm_code_rename_refuses_bad_code_or_foreign_entries(tmp_path, code, entries):
    src = tmp_path / '0000_Vatutino.zip'
    _zip(src, entries)
    with pytest.raises(ValueError):
        npm_code.rename_npm_zip(src, code, tmp_path / 'out')
    assert not (tmp_path / 'out' / f'{code}_Vatutino.zip').exists()


@pytest.mark.parametrize('count', [1, 2, 20])
def test_npm_code_receipt_binds_both_zip_files(tmp_path, count):
    import hashlib
    import json
    import zipfile

    src = tmp_path / '0000_Vatutino.zip'
    entries = {f'0000_Vatutino_{i:02}.fbx': bytes(range(i)) for i in range(1, count + 1)}
    entries['0000_Vatutino_Ground.fbx'] = b'ground'
    _zip(src, entries)
    original = src.read_bytes()
    dest, _, sha = npm_code.rename_npm_zip(src, '1234', tmp_path / 'out')
    receipt = json.loads(dest.with_suffix('.zip.delivery.json').read_text(encoding='utf-8'))
    assert receipt['source'] == {'path': str(src.resolve()), 'sha256': hashlib.sha256(original).hexdigest()}
    assert receipt['delivered'] == {'file': dest.name, 'size': dest.stat().st_size,
                                   'sha256': hashlib.sha256(dest.read_bytes()).hexdigest()}
    assert sha == receipt['delivered']['sha256'] != receipt['source']['sha256']
    assert src.read_bytes() == original
    with zipfile.ZipFile(dest) as archive:
        assert {n: archive.read(n) for n in archive.namelist()} == {
            '1234' + key[4:]: value for key, value in entries.items()}


@pytest.mark.parametrize('kind', ['empty_file', 'empty_zip', 'truncated', 'duplicate', 'not_zip', 'address', 'unicode_code'])
def test_npm_code_rejects_invalid_inputs_before_publication(tmp_path, kind):
    import zipfile

    src = tmp_path / ('0000_Vatutino.bin' if kind == 'not_zip' else '0000_Vatutino.zip')
    name = '0000_Vatutino_Ground.fbx'
    if kind == 'empty_file':
        src.touch()
    else:
        _zip(src, {} if kind == 'empty_zip' else {name: b'ground'})
        if kind == 'truncated':
            src.write_bytes(src.read_bytes()[:-10])
        if kind == 'duplicate':
            with zipfile.ZipFile(src, 'a') as archive, pytest.warns(UserWarning, match='Duplicate name'):
                archive.writestr(name, b'duplicate')
    out = tmp_path / 'out'
    before = src.read_bytes()
    with pytest.raises((ValueError, zipfile.BadZipFile)):
        npm_code.rename_npm_zip(src, '１２３４' if kind == 'unicode_code' else '1234', out,
                                '../elsewhere' if kind == 'address' else 'Vatutino')
    assert src.read_bytes() == before
    assert set(tmp_path.iterdir()) <= {src, out}
    assert not out.exists() or not list(out.iterdir())


@pytest.mark.parametrize('which', ['archive', 'sidecar', 'report'])
def test_npm_code_cli_does_not_clobber_input_hardlinks(tmp_path, which):
    import os
    import subprocess
    import sys

    src = tmp_path / '0000_Vatutino.zip'
    _zip(src, {'0000_Vatutino_Ground.fbx': b'ground'})
    before = src.read_bytes()
    out = tmp_path / 'out'
    out.mkdir()
    alias = out / {'archive': '1234_Vatutino.zip', 'sidecar': '1234_Vatutino.zip.delivery.json',
                   'report': 'validate-1234_Vatutino.json'}[which]
    os.link(src, alias)
    run = subprocess.run([sys.executable, '-I', str(npm_code.__file__), src, '1234', out], cwd=tmp_path,
                         capture_output=True, encoding='utf-8')
    assert run.returncode != 0
    assert list(out.iterdir()) == [alias]
    assert src.read_bytes() == alias.read_bytes() == before


def test_npm_code_cli_reports_failing_validator_and_attests_final_zip(tmp_path):
    import json
    import subprocess
    import sys

    src = tmp_path / '0000_Vatutino.zip'
    _zip(src, {'0000_Vatutino_Ground.fbx': b'not an FBX'})
    out = tmp_path / 'out'
    run = subprocess.run([sys.executable, '-I', str(npm_code.__file__), src, '1234', out], cwd=tmp_path,
                         capture_output=True, encoding='utf-8')
    assert run.returncode == 1, (run.stdout, run.stderr)
    report = json.loads((out / 'validate-1234_Vatutino.json').read_text(encoding='utf-8'))
    assert any('delivered: 1234_Vatutino.zip sha256=' in note for note in report['notes'])


def test_npm_code_refuses_source_drift_during_copy(tmp_path, monkeypatch):
    import zipfile

    src = tmp_path / '0000_Vatutino.zip'
    _zip(src, {'0000_Vatutino_Ground.fbx': b'ground'})
    read = zipfile.ZipFile.read

    def read_and_append(archive, *args, **kwargs):
        result = read(archive, *args, **kwargs)
        with src.open('ab') as stream:
            stream.write(b'concurrent edit')
        return result

    monkeypatch.setattr(zipfile.ZipFile, 'read', read_and_append)
    out = tmp_path / 'out'
    with pytest.raises(ValueError, match='differs|changed'):
        npm_code.rename_npm_zip(src, '1234', out)
    assert src.read_bytes().endswith(b'concurrent edit')
    assert not out.exists() or not list(out.iterdir())


def test_npm_code_competing_archive_leaves_no_stale_receipt(tmp_path, monkeypatch):
    import os

    src = tmp_path / '0000_Vatutino.zip'
    _zip(src, {'0000_Vatutino_Ground.fbx': b'ground'})
    out = tmp_path / 'out'
    dest = out / '1234_Vatutino.zip'
    link = os.link

    def competing_link(source, target):
        if target == dest:
            dest.write_bytes(b'foreign publisher')
        link(source, target)

    monkeypatch.setattr(os, 'link', competing_link)
    with pytest.raises(FileExistsError):
        npm_code.rename_npm_zip(src, '1234', out)
    assert {p.name: p.read_bytes() for p in out.iterdir()} == {dest.name: b'foreign publisher'}
