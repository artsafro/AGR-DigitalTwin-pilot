"""new-case: exported NPM region spacing and bleed readback for #1331."""
import importlib.util
import json
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('npm_padding_tool', ROOT / 'tools/derive/npm_atlas.py')
atlas = importlib.util.module_from_spec(spec)
spec.loader.exec_module(atlas)


def synthetic_spec(path, count=20):
    data = {'address': 'Synthetic', 'size_full': 4096, 'zero_m': 0,
            'finishes': {f'F{i}': {'udim': 1001+i, 'kind': 'placeholder',
                                  'rgb': [20+i, 60+i, 100+i]} for i in range(count)},
            'source_ids': {str(i+1): {'finish': f'F{i}'} for i in range(count)}}
    path.write_text(json.dumps(data), encoding='utf-8')
    return path


def synthetic_master(tmp_path):
    """Synthetic master bytes: generation binds npm_atlas.json to the master hash (#1505)."""
    path = tmp_path / 'master.blend'
    path.write_bytes(b'synthetic master revision A')
    return path


def test_export_has_sixteen_pixel_per_side_padding(tmp_path):
    source = synthetic_spec(tmp_path / 'spec.json')
    out = tmp_path / 'v001'
    assert atlas.main([str(source), str(out), '--master', str(synthetic_master(tmp_path))]) == 0
    data = json.loads((out / 'npm_atlas.json').read_text())
    assert data['pad'] == 16
    assert data['region'] == 377
    # Derive pixel margins from exported UV coordinates, not the declared pad.
    rectangles = [(v['u0']*2048, (1-v['v0']-v['size'])*2048,
                   v['size']*2048) for v in data['finishes'].values()]
    assert min(min(x, y, 2048-x-s, 2048-y-s) for x, y, s in rectangles) == 16
    assert len(rectangles) == 20


def exported_fixture(tmp_path, pad=16):
    # Synthetic coloured cells with edge extrusion; geometry comes from the exported UVs.
    import numpy as np
    side, cell = 2048, 409
    image = np.zeros((side, side, 3), dtype=np.uint8)
    finishes = {}
    for k in range(20):
        x, y = (k % 5)*cell, (k // 5)*cell
        image[y:y+cell, x:x+cell] = [30+k, 70+k, 120+k]
        finishes[f'F{k}'] = {'udim': 1001+k, 'u0': (x+pad)/side,
                            'v0': 1-(y+cell-pad)/side, 'size': (cell-2*pad)/side,
                            'px_per_m': None}
    layout = tmp_path / 'npm_atlas.json'
    layout.write_text(json.dumps({'atlas': side, 'cell': cell, 'pad': 16,
                                  'region': cell-2*pad, 'finishes': finishes}))
    d, o = tmp_path / 'd.png', tmp_path / 'o.png'
    Image.fromarray(image).save(d)
    Image.fromarray(np.full_like(image, 255)).save(o)
    return layout, d, o


@pytest.mark.parametrize('pad', [6, 8, 15])
def test_readback_rejects_short_padding(tmp_path, pad):
    paths = exported_fixture(tmp_path, pad)
    assert hasattr(atlas, 'validate_export'), 'missing exported atlas measurement'
    with pytest.raises(ValueError, match='16 px.*8 px regulatory floor'):
        atlas.validate_export(*paths)


@pytest.mark.parametrize('pad', [16, 17])
def test_readback_threshold(tmp_path, pad):
    paths = exported_fixture(tmp_path, pad)
    assert hasattr(atlas, 'validate_export'), 'missing exported atlas measurement'
    result = atlas.validate_export(*paths)
    assert result['edge_margin_px'] == pad
    assert result['region_gap_px'] == 2*pad
    assert result['per_side_padding_px'] == pad
    assert result['regions'] == 20


@pytest.mark.parametrize('case', ['empty', 'partial', 'nan', 'inf', 'bool', 'outside', 'zero',
                                  'duplicate', 'overlap', 'rgba', 'dimensions', 'bleed', 'truncated',
                                  'unsupported', 'fractional', 'overflow'])
def test_invalid_readback(tmp_path, case):
    paths = exported_fixture(tmp_path)
    data = json.loads(paths[0].read_text())
    r = data['finishes']['F0']
    if case == 'empty':
        data['finishes'] = {}
    elif case == 'partial':
        del r['size']
    elif case in ('nan', 'inf', 'bool', 'overflow'):
        r['u0'] = {'nan': float('nan'), 'inf': float('inf'), 'bool': True, 'overflow': 1e308}[case]
    elif case == 'outside':
        r['u0'] = -1
    elif case == 'zero':
        r['size'] = 0
    elif case == 'fractional':
        r['u0'] += .1/2048
    elif case == 'duplicate':
        data['finishes']['F1']['udim'] = r['udim']
    elif case == 'overlap':
        data['finishes']['F1'] = dict(r, udim=1002)
    elif case == 'unsupported':
        data['atlas'] = 1024
    elif case == 'truncated':
        paths[1].write_bytes(b'PNG')
    elif case in ('rgba', 'dimensions'):
        Image.new('RGBA' if case == 'rgba' else 'RGB',
                  (2048, 2048) if case == 'rgba' else (1024, 1024)).save(paths[1])
    elif case == 'bleed':
        with Image.open(paths[1]) as im:
            im.putpixel((0, 0), (0, 0, 0))
            im.save(paths[1])
    paths[0].write_text(json.dumps(data))
    before = [p.read_bytes() for p in paths]
    with pytest.raises((ValueError, OSError)):
        atlas.validate_export(*paths)
    assert [p.read_bytes() for p in paths] == before


def test_fresh_check_cli(tmp_path):
    import subprocess
    import sys
    paths = exported_fixture(tmp_path)
    cmd = [sys.executable, str(ROOT / 'tools/derive/npm_atlas.py'), '--check', *map(str, paths)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['region_gap_px'] == 32
    paths[0].write_text('{}')
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode != 0
    assert 'refused' in result.stderr


def test_readback_rejects_alias(tmp_path):
    paths = exported_fixture(tmp_path)
    alias = tmp_path / 'alias.png'
    alias.hardlink_to(paths[1])
    with pytest.raises(ValueError, match='distinct'):
        atlas.validate_export(paths[0], paths[1], alias)


def test_readback_detects_changed_input(tmp_path, monkeypatch):
    paths = exported_fixture(tmp_path)
    original = Path.read_bytes
    reads = 0
    def changing_read(path):
        nonlocal reads
        reads += 1
        if reads == 4:
            return b'changed after decode'
        return original(path)
    monkeypatch.setattr(Path, 'read_bytes', changing_read)
    with pytest.raises(ValueError, match='changed during readback'):
        atlas.validate_export(*paths)


@pytest.mark.parametrize('target', ['T_Synthetic_001_Main_d_1.png',
                                    'T_Synthetic_001_Main_o_1.png', 'npm_atlas.json'])
def test_generator_rejects_racing_output_hardlink(tmp_path, monkeypatch, target):
    import sys
    sys.path.insert(0, atlas.RECIPE)
    import finish_map
    original = finish_map.fresh_out_dir
    source = synthetic_spec(tmp_path / 'spec.json', 1)
    before = source.read_bytes()
    def race(out, inputs):
        original(out, inputs)
        (Path(out) / target).hardlink_to(source)
    monkeypatch.setattr(finish_map, 'fresh_out_dir', race)
    with pytest.raises(FileExistsError):
        atlas.main([str(source), str(tmp_path / 'v001'), '--master', str(synthetic_master(tmp_path))])
    assert source.read_bytes() == before


@pytest.mark.parametrize('pad', range(33))
def test_generated_padding_matrix(tmp_path, pad):
    paths = exported_fixture(tmp_path, pad)
    if pad < 16:
        with pytest.raises(ValueError):
            atlas.validate_export(*paths)
    else:
        result = atlas.validate_export(*paths)
        assert result['per_side_padding_px'] == pad
        assert result['region_gap_px'] == 2*pad


def test_cli_no_clobber(tmp_path):
    import subprocess
    import sys
    source = synthetic_spec(tmp_path / 'spec.json', 1)
    before = source.read_bytes()
    command = [sys.executable, str(ROOT / 'tools/derive/npm_atlas.py'), str(source)]
    result = subprocess.run([*command, str(source.parent / './spec.json')], capture_output=True)
    assert result.returncode != 0
    assert source.read_bytes() == before
