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


def test_export_has_sixteen_pixel_per_side_padding(tmp_path):
    source = synthetic_spec(tmp_path / 'spec.json')
    out = tmp_path / 'v001'
    assert atlas.main([str(source), str(out)]) == 0
    data = json.loads((out / 'npm_atlas.json').read_text())
    assert data['pad'] == 16
    assert data['region'] == 377
    # Derive pixel margins from exported UV coordinates, not the declared pad.
    rectangles = [(v['u0']*2048, (1-v['v0']-v['size'])*2048,
                   v['size']*2048) for v in data['finishes'].values()]
    assert min(min(x, y, 2048-x-s, 2048-y-s) for x, y, s in rectangles) == 16
    assert len(rectangles) == 20
