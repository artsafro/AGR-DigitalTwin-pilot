"""Tests for the v005 MAF atlas layouts (VPM 4K / NPM 2K / 512 site set) of issue #524."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools' / 'library'))
sys.path.insert(0, str(ROOT / 'tests'))

import maf_atlas_ids as ids_mod  # noqa: E402
import maf_atlas_layout as lay  # noqa: E402
from test_maf_atlas_ids import _outs, _setup, _write  # noqa: E402

SPEC = {'version': 'v005', 'library': {'size': 1024, 'padding_px': 16, 'slot_px': {'L': 512, 'M': 256, 'S': 128},
                                      'decal_reserve_px': 256,
                                      'profiles': {'vpm': {'size': 1024, 'file': 'vpm.png', 'udim': 1001},
                                                   'npm': {'size': 512, 'file': 'npm.png'}}},
        'site_sets': {'s': {'file': 'site.png', 'material_to_id': {'steel_red': 'paint_red', 'oak': 'wood_medium'},
                            'proof_positions': ['P1']}}}
POS = {'positions': [{'set_id': 'P1', 'catalogue_id': 'MAF_0001', 'material_map': {'1': 'oak', '2': 'steel_red'}},
                     {'set_id': 'P2', 'catalogue_id': 'MAF_0002', 'material_map': {'*': 'steel_red'}}]}


def _rects_disjoint(cells, size):
    occ = np.zeros((size, size), np.uint8)
    for c in cells:
        x, y, w, h = c['slot_px']
        assert 0 <= x and 0 <= y and x + w <= size and y + h <= size
        occ[y:y + h, x:x + w] += 1
    return occ.max() <= 1


def test_id_corner_is_bottom_right_inside_the_content():
    for content in ([8, 8, 240, 240], [4, 4, 56, 56], [100, 50, 1008, 1008]):
        x, y, w, h = content
        zx, zy, zs, _ = lay.id_corner(content)
        assert zx + zs == x + w and zy + zs == y + h and zs >= lay.CORNER_MIN_PX and zx >= x and zy >= y


def _ids_run(tmp_path, **kw):
    ev = tmp_path / 'ev'
    assert ids_mod.main(_setup(tmp_path, **kw) + _outs(tmp_path) + ['--evidence-dir', str(ev)]) == 0
    return tmp_path / 'out.json', ev


def _layout_args(tmp_path, ids_json, ev, spec=None, pos=None):
    return ['--ids', str(ids_json), '--spec', _write(tmp_path / 'spec.json', spec or SPEC),
            '--tiles-dir', str(ev), '--site-set', 's=' + _write(tmp_path / 'set.json', pos or POS),
            '--out-json', str(tmp_path / 'layout.json')]


def test_end_to_end_layouts_read_back(tmp_path):
    ids_json, ev = _ids_run(tmp_path)
    out = tmp_path / 'png'
    assert lay.main(_layout_args(tmp_path, ids_json, ev) + ['--evidence-dir', str(out)]) == 0
    r = json.loads((tmp_path / 'layout.json').read_text(encoding='utf-8'))
    ids = json.loads(ids_json.read_text(encoding='utf-8'))
    tiles = {t['key']: ev / t['file'] for t in ids['evidence']['tiles']}
    vpm, npm = r['profiles']['vpm'], r['profiles']['npm']
    assert sorted(c['id'] for c in vpm['cells']) == [e['id'] for e in ids['ids']]  # every id exactly once
    assert _rects_disjoint(vpm['cells'] + [{'slot_px': vpm['decal_reserve_px']}], 1024)
    assert {c['size_class']: c['slot_px'][2] for c in vpm['cells']} == {'S': 128, 'M': 256}
    assert npm['padding_px'] == 8 and all(b['slot_px'] == [v // 2 for v in a['slot_px']]
                                          for a, b in zip(vpm['cells'], npm['cells']))
    for name, L in (('vpm', vpm), ('npm', npm), ('s', r['site_sets']['s'])):
        im = np.asarray(Image.open(L['png']['path']).convert('RGB')).astype(int)
        for c in L['cells']:
            x, y, w, h = c['content_px']
            tile = np.asarray(Image.open(tiles[c['key']]).convert('RGB').resize((w, h))).astype(int)
            cy, cx = y + h // 3, x + w // 3  # away from the ID corner
            assert np.abs(im[cy, cx] - tile[h // 3, w // 3]).max() <= 40, (name, c['key'])
            zx, zy, zs, _ = c['id_corner_px']
            assert (im[zy + zs - 1, zx + zs - 1] == 0).all(), (name, c['key'])  # number box in the corner
            assert not (im[y:zy - 1, x:x + w] == 0).all(-1).all(-1).any()  # no number box above the corner
    site = r['site_sets']['s']
    assert {c['key'] for c in site['cells']} == {'paint_red', 'wood_medium'}  # only the ids the site uses
    assert [(p['slot'], p['key']) for p in site['proof']] == [('1', 'wood_medium'), ('2', 'paint_red')]
    assert len(site['positions']) == 3


def test_stale_tile_fails_and_writes_nothing(tmp_path, capsys):
    ids_json, ev = _ids_run(tmp_path)
    t = json.loads(ids_json.read_text(encoding='utf-8'))['evidence']['tiles'][0]
    Image.new('RGB', (512, 512), (1, 2, 3)).save(ev / t['file'])
    assert lay.main(_layout_args(tmp_path, ids_json, ev)) == 2
    assert 'stale tile' in capsys.readouterr().err and not (tmp_path / 'layout.json').exists()


@pytest.mark.parametrize('pos, msg', [
    ({'positions': [{'set_id': 'P1', 'material_map': {'1': 'teak'}}]}, "material 'teak' has no id mapping"),
    ({'positions': []}, 'no position materials'),
    ({'positions': [{'set_id': 'P9', 'material_map': {'1': 'oak'}}]}, "proof positions not in the set: ['P1']"),
])
def test_site_set_fails_closed(tmp_path, capsys, pos, msg):
    ids_json, ev = _ids_run(tmp_path)
    assert lay.main(_layout_args(tmp_path, ids_json, ev, pos=pos)) == 2
    assert msg in capsys.readouterr().err and not (tmp_path / 'layout.json').exists()


@pytest.mark.parametrize('patch, msg', [
    ({'size': 256}, 'does not fit'),
    ({'slot_px': {'L': 512, 'M': 256, 'S': 100}}, 'not a power of two'),
    ({'profiles': {'npm': {'size': 256, 'file': 'n.png'}}}, 'padding 4 px < 8 px'),
    ({'profiles': {'big': {'size': 2048, 'file': 'b.png'}}}, 'must be a power of two <= 1024'),
])
def test_library_layout_fails_closed(tmp_path, capsys, patch, msg):
    ids_json, ev = _ids_run(tmp_path)
    spec = json.loads(json.dumps(SPEC))
    spec['library'].update(patch)
    assert lay.main(_layout_args(tmp_path, ids_json, ev, spec=spec)) == 2
    assert msg in capsys.readouterr().err and not (tmp_path / 'layout.json').exists()


def test_output_on_an_input_fails(tmp_path):
    ids_json, ev = _ids_run(tmp_path)
    before = ids_json.read_bytes()
    args = _layout_args(tmp_path, ids_json, ev)
    args[args.index('--out-json') + 1] = str(ids_json.parent / '.' / ids_json.name)
    assert lay.main(args) == 2 and ids_json.read_bytes() == before


def test_version_mismatch_fails(tmp_path, capsys):
    ids_json, ev = _ids_run(tmp_path)
    assert lay.main(_layout_args(tmp_path, ids_json, ev, spec=dict(SPEC, version='v004'))) == 2
    assert 'version' in capsys.readouterr().err


def test_every_id_number_fits_its_corner_at_512_for_two_digits():
    cells = [{'id': i, 'key': 'k', 'id_corner_px': lay.id_corner([0, 0, 56, 56])} for i in (9, 29, 31)]
    assert lay.corner_fits({'cells': cells}) == []
    assert lay.corner_fits({'cells': [{'id': 123456, 'key': 'k', 'id_corner_px': [0, 0, 16, 16]}]}) == ['123456 k']


def test_real_v005_layout_artifact_is_consistent():
    r = json.loads((ROOT / 'library' / 'maf' / 'atlas_layout_v005.json').read_text(encoding='utf-8'))
    ids = json.loads((ROOT / 'library' / 'maf' / 'material_ids_v005.json').read_text(encoding='utf-8'))
    want = sorted(e['id'] for e in ids['ids'] if e.get('atlas', True))
    assert r['status'] == 'proposed' and r['version'] == ids['version'] == 'v005'
    for name, L in r['profiles'].items():
        assert sorted(c['id'] for c in L['cells']) == want, name
        assert _rects_disjoint(L['cells'] + [{'slot_px': L['decal_reserve_px']}], L['size']), name
        assert L['padding_px'] >= 8
    site = r['site_sets']['vatutino']
    assert site['size'] == 512 and {p['set_id'] for p in site['proof']} == {
        'VAT_MAF_T3510_01', 'VAT_MAF_T3510_26', 'VAT_MAF_T3510_28'}
    assert {c['key'] for c in site['cells']} == {p['key'] for p in site['positions']}


def test_json_and_md_on_one_file_or_evidence_on_tiles_fail(tmp_path):
    ids_json, ev = _ids_run(tmp_path)
    args = _layout_args(tmp_path, ids_json, ev)
    assert lay.main(args + ['--out-md', str(tmp_path / 'LAYOUT.json')]) == 2
    assert lay.main(args + ['--evidence-dir', str(ev)]) == 2
    assert not (tmp_path / 'layout.json').exists()
