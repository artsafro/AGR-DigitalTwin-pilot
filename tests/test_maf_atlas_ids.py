"""Tests for the v004/v005 MAF material ID list from atlas cells (issue #524)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools' / 'library'))

import maf_atlas_cells as cells_mod  # noqa: E402
import maf_atlas_ids as ids_mod  # noqa: E402

RED, BLUE, BLACK, GREY = (200, 30, 30), (40, 160, 210), (5, 5, 5), (208, 208, 208)


def _atlas(path: Path, size=512, seed=1) -> Path:
    """Synthetic atlas: 4 flat cells in the top row (128 px each), wood-like noise below."""
    rng = np.random.default_rng(seed)
    a = np.zeros((size, size, 3), np.uint8)
    for k, col in enumerate((RED, BLUE, BLACK, GREY)):
        a[:size // 4, k * size // 4:(k + 1) * size // 4] = col
    wood = np.array([150, 115, 86]) + rng.normal(0, 18, (size - size // 4, size, 3))
    a[size // 4:] = np.clip(wood, 0, 255).astype(np.uint8)
    Image.fromarray(a).save(path)
    return path


def test_segment_finds_flat_cells_and_wood(tmp_path):
    r = cells_mod.segment(str(_atlas(tmp_path / 'a.png')))
    solid = [c for c in r['cells'] if c['kind'] == 'solid']
    pat = [c for c in r['cells'] if c['kind'] == 'patterned']
    assert [(c['x'], c['w'], c['h']) for c in solid] == [(0, 128, 128), (128, 128, 128), (256, 128, 128),
                                                         (384, 128, 128)]
    assert [c['color'] for c in solid] == ['#C81E1E', '#28A0D2', '#050505', '#D0D0D0']
    assert len(pat) == 1 and (pat[0]['y'], pat[0]['w'], pat[0]['h']) == (128, 512, 384)


def test_segment_reports_source_pixels_for_large_images(tmp_path):
    p = tmp_path / 'big.png'
    Image.open(_atlas(tmp_path / 's.png')).resize((2048, 2048), Image.NEAREST).save(p)
    r = cells_mod.segment(str(p))
    assert r['size'] == [2048, 2048] and r['work_scale'] == 4.0
    assert {(c['x'], c['w']) for c in r['cells'] if c['kind'] == 'solid'} == {(0, 512), (512, 512), (1024, 512),
                                                                              (1536, 512)}


def test_flat_blocks_inside_a_non_guillotine_region_and_mixed_remainder(tmp_path):
    # low-contrast noise (0..20): few neighbour jumps above the edge threshold -> no full-length cut line,
    # too varied to be solid, almost no flat pixels -> the red block is found only by the flat-block pass
    a = (110 + np.random.default_rng(3).integers(0, 21, (256, 256, 1)) + np.zeros((256, 256, 3))).astype(np.uint8)
    a[20:100, 30:120] = RED  # flat block not separated by a full-length line
    p = tmp_path / 'm.png'
    Image.fromarray(a).save(p)
    r = cells_mod.segment(str(p))
    kinds = sorted(c['kind'] for c in r['cells'])
    assert kinds == ['mixed', 'solid']
    s = [c for c in r['cells'] if c['kind'] == 'solid'][0]
    assert (s['x'], s['y'], s['w'], s['h'], s['color']) == (30, 20, 90, 80, '#C81E1E')


@pytest.mark.parametrize('kw', [{'work': 0}, {'min_cell': -1}, {'edge_t': float('nan')}, {'mat_diff': float('inf')},
                                {'solid_share': 0}])
def test_segment_rejects_bad_parameters(tmp_path, kw):
    with pytest.raises(ValueError):
        cells_mod.segment(str(_atlas(tmp_path / 'a.png')), **kw)


def test_segment_rejects_too_small_image(tmp_path):
    p = tmp_path / 't.png'
    Image.new('RGB', (10, 10), RED).save(p)
    with pytest.raises(ValueError, match='too small'):
        cells_mod.segment(str(p))


def test_id_number_is_drawn_in_the_bottom_right_corner():
    im = Image.new('RGB', (200, 200), (255, 255, 255))
    d = ImageDraw.Draw(im)
    ids_mod.draw_id(d, (0, 0, 199, 199), '17', ids_mod._font(14))
    a = np.asarray(im)
    assert (a[199, 199] == 0).all()  # corner box is filled
    assert (a[:150, :] == 255).all() and (a[:, :150] == 255).all()  # nothing outside the corner zone


# ---------------------------------------------------------------- end to end (synthetic library)

def _write(p: Path, obj) -> str:
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')
    return str(p)


def _seed(ids=None, **kw):
    return {'version': 'v005', **kw, 'ids': ids if ids is not None else [
        {'id': 1, 'key': 'paint_red', 'name_ru': 'красная', 'kind': 'paint', 'hex': '#C81E1E', 'spec': 'красн',
         'library': '^Red$'},
        {'id': 2, 'key': 'paint_blue', 'name_ru': 'голубая', 'kind': 'paint', 'hex': '#28A0D2', 'spec': None,
         'library': None},
        {'id': 3, 'key': 'wood_medium', 'name_ru': 'дерево', 'kind': 'wood', 'hex': '#967356', 'spec': 'дерев',
         'library': None},
        {'id': 4, 'key': 'concrete', 'name_ru': 'бетон', 'kind': 'mineral', 'hex': '#A0A0A0', 'spec': 'бетон',
         'library': None},
    ]}


def _setup(tmp_path, seed=None, faces=None):
    maps = tmp_path / 'maps'
    maps.mkdir()
    _atlas(maps / 'T_Atlas.png')
    tex = [{'name': 'Map #1', 'filepath': 'G:\\far\\maps\\T_Atlas.png'}]
    materials = {'files': [
        {'fbx': 'MAF_0001_A.fbx', 'materials': [{'name': 'Red', 'hex': '#CC0000', 'textures': tex},
                                                {'name': 'Material #12', 'hex': '#CCCCCC', 'textures': []},
                                                {'name': 'Kolpak_x', 'hex': '#000000', 'textures': []}]},
        {'fbx': 'MAF_0002_B.fbx', 'materials': [{'name': 'Wood', 'hex': '#808080', 'textures': tex},
                                                {'name': 'Gone', 'hex': '#808080', 'textures': [
                                                    {'name': 'Map #2', 'filepath': 'E:\\x\\missing.png'}]},
                                                {'name': 'Empty', 'hex': '#808080', 'textures': [
                                                    {'name': 'Map #3', 'filepath': 'C:\\lib\\..'}]}]}]}
    # UV: face 1 on the red cell; face 2 on wood touching v=0 (bottom edge) - must not be 'uncovered'
    faces = faces if faces is not None else [[0.05, 0.80, 0.20, 0.80, 0.20, 0.95], [0.4, 0.0, 0.6, 0.0, 0.5, 0.0]]
    uv = {'files': [
        {'fbx': 'MAF_0001_A.fbx', 'materials': {'Red': {'images': tex, 'uv_layer': 'UVMap', 'faces': faces[:1]}}},
        {'fbx': 'MAF_0002_B.fbx', 'materials': {'Wood': {'images': tex, 'uv_layer': 'UVMap', 'faces': faces[1:]}}}]}
    schedule = {'rows': [{'table': 'T1', 'row': 1, 'name': 'Скамья', 'material': 'сталь красная, дерево'},
                         {'table': 'T1', 'row': 2, 'name': 'Урна', 'material': 'бетон'},
                         {'table': 'T1', 'row': 3, 'name': 'Знак', 'material': 'стекло'}]}
    args = ['--materials', _write(tmp_path / 'fbx_materials.json', materials),
            '--uv-dump', _write(tmp_path / 'uv.json', uv),
            '--max-maps', _write(tmp_path / 'max.json', {'materials': [{'name': 'Empty', 'maps': [
                {'name': 'Map #3', 'class': 'Bitmaptexture', 'file': None, 'path': ''}]}]}),
            '--schedule', _write(tmp_path / 'schedule.json', schedule),
            '--seed', _write(tmp_path / 'seed.json', seed if seed is not None else _seed()),
            '--ral', _write(tmp_path / 'ral.json', {'colors': {'3020': '#CC0605'}}),
            '--maps-dir', str(maps)]
    return args


def _outs(tmp_path):
    return ['--out-json', str(tmp_path / 'out.json'), '--out-md', str(tmp_path / 'out.md')]


def test_end_to_end_every_input_element_is_accounted_for(tmp_path):
    args = _setup(tmp_path) + _outs(tmp_path) + ['--evidence-dir', str(tmp_path / 'ev')]
    assert ids_mod.main(args) == 0
    r = json.loads((tmp_path / 'out.json').read_text(encoding='utf-8'))
    by = {e['key']: e for e in r['ids']}
    assert r['status'] == 'proposed' and all(e['status'].startswith('proposed') for e in r['ids'])
    # atlas cells -> ids by colour, with the MAFs whose UV faces land on them
    assert [c['uv_mafs'] for c in by['paint_red']['cells']] == [['MAF_0001']]
    assert [c['uv_mafs'] for c in by['wood_medium']['cells']] == [['MAF_0002']]
    at = r['atlases'][0]
    assert at['uv']['uncovered']['faces'] == 0
    assert all(c.get('id') or c.get('reason') for c in at['cells'])  # every cell: id or reason
    # texture refs: found / missing / empty bitmap, never guessed
    inv = r['inventory']
    assert [x['name'] for x in inv['found']] == ['T_Atlas.png']
    assert [(m['name'], m['referenced_path']) for m in inv['missing']] == [('missing.png', 'E:\\x\\missing.png')]
    assert inv['empty_bitmap'] == [{'material': 'Empty', 'mafs': 1}]
    # library material names: id / excluded (junk) / unmapped (named, never defaulted)
    lib = r['library_materials']
    assert by['paint_red']['library_materials'] == [{'material': 'Red', 'mafs': 1}]
    assert {m['material'] for m in lib['excluded']} == {'Material #12'}
    assert {m['material'] for m in lib['unmapped']} == {'Empty', 'Gone', 'Kolpak_x', 'Wood'}
    # spec rows: ids or gap
    reqs = {q['row']: q for q in r['spec_requirements']}
    assert reqs[1]['ids'] == [1, 3] and reqs[2]['ids'] == [4] and reqs[3]['gap'] is True
    assert by['concrete']['status'] == 'proposed, gap: no atlas cell (spec asks for it)'
    # evidence: contact sheet with the ID number corner, one overlay
    ev = r['evidence']
    assert Path(ev['contact_sheet']['path']).is_file() and 'overlay T_Atlas.png' in ev
    md = (tmp_path / 'out.md').read_text(encoding='utf-8')
    assert '| 1 | - | `paint_red`' in md and 'missing.png' in md and 'T1#3' in md


def test_contact_sheet_uses_the_real_crop_not_a_placeholder(tmp_path):
    assert ids_mod.main(_setup(tmp_path) + _outs(tmp_path) + ['--evidence-dir', str(tmp_path / 'ev')]) == 0
    r = json.loads((tmp_path / 'out.json').read_text(encoding='utf-8'))
    sheet = np.asarray(Image.open(r['evidence']['contact_sheet']['path']).convert('RGB')).astype(int)
    # tile 1 (paint_red) centre = crop of the red cell; tile 4 (concrete, gap) = target swatch, no cross
    assert np.abs(sheet[110, 110] - np.array(RED)).max() <= 2
    wood = sheet[60:160, 60 + 2 * 220:160 + 2 * 220].reshape(-1, 3)
    assert wood.std(0).mean() > 5  # textured crop, not a flat placeholder


def test_gap_tile_is_the_target_colour_without_a_diagonal_and_tiles_carry_no_number(tmp_path):
    assert ids_mod.main(_setup(tmp_path) + _outs(tmp_path) + ['--evidence-dir', str(tmp_path / 'ev')]) == 0
    r = json.loads((tmp_path / 'out.json').read_text(encoding='utf-8'))
    sheet = np.asarray(Image.open(r['evidence']['contact_sheet']['path']).convert('RGB')).astype(int)
    x0 = 3 * 220 + 6  # tile 4 = concrete (gap): whole box except the bottom-right ID corner = #A0A0A0
    box = sheet[6:6 + 150, x0:x0 + 150].reshape(-1, 3)
    assert (np.abs(box - 160) <= 1).all(), 'gap tile must be the plain target colour (no red diagonal)'
    tiles = {t['key']: t for t in r['evidence']['tiles']}
    assert set(tiles) == {e['key'] for e in r['ids']} and tiles['concrete']['source'].startswith('GAP')
    red = np.asarray(Image.open(tmp_path / 'ev' / tiles['paint_red']['file']).convert('RGB')).astype(int)
    assert (np.abs(red - np.array(RED)) <= 2).all()  # clean tile: no number baked into it


def test_layout_example_is_never_a_colour_or_texture_source(tmp_path):
    ex = tmp_path / 'example_id_layout.png'
    a = np.zeros((256, 256, 3), np.uint8)
    a[:, :128] = (160, 160, 160)  # would match concrete and blue-ish if it were a source
    a[:, 128:] = (40, 160, 210)
    Image.fromarray(a).save(ex)
    args = _setup(tmp_path) + _outs(tmp_path) + ['--layout-example', str(ex), '--evidence-dir', str(tmp_path / 'ev')]
    assert ids_mod.main(args) == 0
    r = json.loads((tmp_path / 'out.json').read_text(encoding='utf-8'))
    at = [a for a in r['atlases'] if a['name'] == 'example_id_layout.png'][0]
    assert at['role'] == 'layout example' and all(c['id'] is None and 'layout example' in c['reason']
                                                   for c in at['cells'])
    assert all(c['atlas'] != 'example_id_layout.png' for e in r['ids'] for c in e['cells'])
    by = {e['key']: e for e in r['ids']}
    assert by['concrete']['cells'] == [] and by['concrete']['status'].startswith('proposed, gap')
    assert all('example_id' not in t['source'] for t in r['evidence']['tiles'])


@pytest.mark.parametrize('merges, prev, msg', [
    ([], ['paint_red', 'paint_blue', 'wood_medium', 'concrete', 'paint_wine'], "neither kept nor merged: ['paint_wine']"),
    ([{'from_key': 'paint_wine', 'into': 'paint_rose', 'reason': 'x'}], None, "into 'paint_rose' is not an id"),
    ([{'from_key': 'paint_blue', 'into': 'paint_red', 'reason': 'x'}], None, 'still an id'),
    ([{'from_key': 'paint_wine', 'into': 'paint_red'}], None, 'no reason'),
    ([{'from_key': 'paint_wine', 'into': 'paint_red', 'reason': 'x'}] * 2, None, 'duplicated'),
    ([{'from_key': 'paint_gold', 'into': 'paint_red', 'reason': 'x'}], ['paint_red', 'paint_blue', 'wood_medium',
                                                                        'concrete'], 'not in the previous seed'),
    ([], [], 'prev seed has no ids'),
])
def test_merges_fail_closed_and_no_previous_id_is_lost(tmp_path, capsys, merges, prev, msg):
    args = _setup(tmp_path, seed=_seed(merges=merges)) + _outs(tmp_path)
    if prev is not None:
        args += ['--prev-seed', _write(tmp_path / 'prev.json', {'ids': [{'key': k} for k in prev]})]
    assert ids_mod.main(args) == 2
    assert msg in capsys.readouterr().err
    assert not (tmp_path / 'out.json').exists()


def test_merge_rows_reach_the_report(tmp_path):
    m = [{'from_key': 'paint_wine', 'from_v004_id': 11, 'into': 'paint_red', 'reason': 'one red'}]
    args = _setup(tmp_path, seed=_seed(merges=m)) + _outs(tmp_path) + [
        '--prev-seed', _write(tmp_path / 'prev.json', {'ids': [{'key': k} for k in (
            'paint_red', 'paint_blue', 'wood_medium', 'concrete', 'paint_wine')]})]
    assert ids_mod.main(args) == 0
    md = (tmp_path / 'out.md').read_text(encoding='utf-8')
    assert '| 11 `paint_wine` | 1 `paint_red` | one red |' in md


def test_pick_patch_takes_a_clean_matching_patch_or_nothing(tmp_path):
    p = tmp_path / 'c.png'
    a = np.full((512, 512, 3), 30, np.uint8)
    rng = np.random.default_rng(5)
    a[:, 256:] = np.clip(160 + rng.normal(0, 10, (512, 256, 3)), 0, 255).astype(np.uint8)  # concrete-like noise
    Image.fromarray(a).save(p)
    at = {'name': 'c.png', 'path': str(p), 'role': 'atlas',
          'cells': [{'x': 256, 'y': 0, 'w': 256, 'h': 512, 'kind': 'patterned', 'id': None}]}
    concrete = ids_mod.load_seed(_seed([{'id': 4, 'key': 'concrete', 'name_ru': 'b', 'kind': 'mineral',
                                         'hex': '#A0A0A0'}]), {})[0]
    got = ids_mod.pick_patch([at], concrete)
    assert got and got['atlas'] == 'c.png' and got['x'] >= 256 + 32 and got['dist'] <= ids_mod.PATCH_TOL
    wood = dict(concrete, targets=['#967356'])
    assert ids_mod.pick_patch([at], wood) is None  # nothing near the target -> no patch, never a default
    assert ids_mod.pick_patch([dict(at, role='layout example')], concrete) is None


@pytest.mark.parametrize('bad_seed, msg', [
    ({'ids': []}, 'no ids'),
    (_seed([{'id': 1, 'key': 'a', 'name_ru': 'a', 'kind': 'paint', 'hex': '#000000'},
            {'id': 1, 'key': 'b', 'name_ru': 'b', 'kind': 'paint', 'hex': '#000000'}]), 'unique'),
    (_seed([{'id': 1, 'key': 'a', 'name_ru': 'a', 'kind': 'glitter', 'hex': '#000000'}]), 'unknown kind'),
    (_seed([{'id': 1, 'key': 'a', 'name_ru': 'a', 'kind': 'paint', 'ral': '9999'}]), 'RAL 9999'),
    (_seed([{'id': 1, 'key': 'a', 'name_ru': 'a', 'kind': 'paint', 'hex': 'red'}]), 'bad colour'),
])
def test_bad_seed_fails_closed_and_writes_nothing(tmp_path, capsys, bad_seed, msg):
    assert ids_mod.main(_setup(tmp_path, seed=bad_seed) + _outs(tmp_path)) == 2
    assert msg in capsys.readouterr().err
    assert not (tmp_path / 'out.json').exists() and not (tmp_path / 'out.md').exists()


@pytest.mark.parametrize('face', [[0.1, float('nan'), 0.2, 0.8, 0.2, 0.9], [0.1, 0.8, 0.2], [0.1, 0.8, 0.2, 0.9]])
def test_bad_uv_face_fails_closed(tmp_path, face):
    args = _setup(tmp_path, faces=[face, [0.4, 0.1, 0.6, 0.1, 0.5, 0.2]]) + _outs(tmp_path)
    assert ids_mod.main(args) == 2
    assert not (tmp_path / 'out.json').exists()


def test_output_resolving_to_an_input_fails_and_input_is_untouched(tmp_path):
    args = _setup(tmp_path)
    seed_path = Path(args[args.index('--seed') + 1])
    before = seed_path.read_bytes()
    alias = str(seed_path.parent / '.' / seed_path.name)
    assert ids_mod.main(args + ['--out-json', alias, '--out-md', str(tmp_path / 'o.md')]) == 2
    assert seed_path.read_bytes() == before and not (tmp_path / 'o.md').exists()


def test_two_outputs_on_one_file_fail(tmp_path):
    args = _setup(tmp_path) + ['--out-json', str(tmp_path / 'o.x'), '--out-md', str(tmp_path / 'O.X')]
    assert ids_mod.main(args) == 2


def test_missing_maps_dir_fails(tmp_path):
    args = _setup(tmp_path) + _outs(tmp_path) + ['--maps-dir', str(tmp_path / 'nope')]
    assert ids_mod.main(args) == 2


def test_cell_to_id_tolerance_is_inclusive_at_the_threshold_and_exclusive_above():
    seed = ids_mod.load_seed(_seed([{'id': 1, 'key': 'g', 'name_ru': 'g', 'kind': 'paint', 'hex': '#646464'}]), {})
    def one(hexc):
        at = {'size': [100, 100], 'role': 'atlas',
              'cells': [{'x': 0, 'y': 0, 'w': 50, 'h': 50, 'kind': 'solid', 'color': hexc, 'mean': hexc}]}
        ids_mod.match_cells([at], seed)
        return at['cells'][0]['id']
    assert one('#767676') == 1  # |dRGB| = 18 = tolerance
    assert one('#777777') is None  # 19 > tolerance -> unmapped with a reason, never the nearest anyway


def test_real_v005_artifact_keeps_or_merges_every_v004_id_and_never_uses_the_example():
    lib = ROOT / 'library' / 'maf'
    r = json.loads((lib / 'material_ids_v005.json').read_text(encoding='utf-8'))
    v4 = json.loads((lib / 'material_ids_v004_seed.json').read_text(encoding='utf-8'))
    assert r['status'] == 'proposed' and [e['id'] for e in r['ids']] == list(range(1, len(r['ids']) + 1))
    kept = {e['key'] for e in r['ids']}
    merged = {m['from_key']: m['into'] for m in r['merges']}
    assert {e['key'] for e in v4['ids']} == kept | set(merged) and not kept & set(merged)
    assert set(merged.values()) <= kept
    assert all(c['atlas'] != 'example_id_layout.png' for e in r['ids'] for c in e['cells'])
    ex = [a for a in r['atlases'] if a['name'] == 'example_id_layout.png']
    assert ex and all(c['id'] is None for c in ex[0]['cells'])
    assert {t['key'] for t in r['evidence']['tiles']} == kept
    assert not any('example_id' in t['source'] for t in r['evidence']['tiles'])


def test_real_v004_artifact_is_consistent():
    p = ROOT / 'library' / 'maf' / 'material_ids_v004.json'
    r = json.loads(p.read_text(encoding='utf-8'))
    seed = json.loads((ROOT / 'library' / 'maf' / 'material_ids_v004_seed.json').read_text(encoding='utf-8'))
    assert r['status'] == 'proposed' and [e['id'] for e in r['ids']] == [e['id'] for e in seed['ids']]
    assert len({e['key'] for e in r['ids']}) == len(r['ids'])
    for at in r['atlases']:
        assert all(c.get('id') or c.get('reason') for c in at['cells']), at['name']
    assert all(not q['gap'] or q['ids'] == [] for q in r['spec_requirements'])
