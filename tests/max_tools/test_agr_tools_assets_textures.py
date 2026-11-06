"""new-case: textures of placed assets (#1024, assets_textures.py): UDIM occupancy/allocation, VPM plans
(tile per set / packed 4K), VPM names through names_core, NPM routing. Synthetic inputs only."""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name):
    spec = importlib.util.spec_from_file_location('agr_tools_' + name + '_tt', ROOT / 'adapters/max/agr_tools' /
                                                  (name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


T = _load('assets_textures')
N = _load('names_core')


def test_role_of_a101_names():
    assert T.role_of('X/T_Adx_Stol_1_high_Diffuse.png') == 'diffuse'
    assert T.role_of('T_Adx_Stol_1_high_ERM.png') == 'erm'
    assert T.role_of('T_Adx_Stol_1_high_Normal.png') == 'normal'
    assert T.role_of('Mst_K_1_low_o.png') == 'opacity' and T.role_of('Mst_K_1_low_r.png') == 'erm'
    assert T.role_of('G:/TextureFlora/alpha_tree_t1_h500_high.png') == 'diffuse'


def test_used_tiles_and_contiguous_allocation():
    files = ['T_Addr_Diffuse_1.1001.png', 'T_Addr_ERM_1.1002.png', 'T_Addr_Normal_1.1003.png',
             'T_Addr_Diffuse_2.1001.png', 'T_Other_Diffuse_1.1050.png', 'notes.txt']
    used = T.used_tiles(files, 'Addr', N.udim_of)
    assert used == {1: {1001, 1002, 1003}, 2: {1001}}
    assert T.allocate(used, 3) == [(1, 1004), (1, 1005), (1, 1006)]
    assert T.allocate({}, 2, slot=3) == [(3, 1001), (3, 1002)]
    full = {1: set(range(1001, 1099))}
    assert T.allocate(full, 4) == [(1, 1099), (1, 1100), (2, 1001), (2, 1002)]
    with pytest.raises(ValueError, match='no free UDIM'):
        T.allocate({s: {1100} for s in range(1, 8)}, 1)
    assert T.tile_uv(1001) == (0, 0) and T.tile_uv(1023) == (2, 2)


def _sets(n, uv=((0.0, 0.0), (1.0, 1.0))):
    rows = []
    for i in range(n):
        rows.append({'asset': 'maf:A{}'.format(i), 'version': 'high', 'material': 'M_A{}'.format(i),
                     'maps': ['T_A{}_high_Diffuse.png'.format(i), 'T_A{}_high_Normal.png'.format(i)],
                     'uv_bbox': [list(uv[0]), list(uv[1])], 'area3d_m2': 4.0 + i, 'tex_px': [4096, 4096]})
    return T.texture_sets(rows)


def test_tile_per_set_names_offsets_and_placeholders():
    sets = _sets(2)
    plan = T.vpm_plan(sets, {1: {1001, 1002}}, 'Addr', N.texture_stem, 'maf', obj_type='Main')
    assert plan['mode'] == 'tile_per_set' and plan['tiles'] == [(1, 1003), (1, 1004)]
    r = plan['rows'][0]
    assert r['uv_offset'] == [2, 0]
    assert [c['stem'] for c in r['copy']] == ['T_Addr_Diffuse_1.1003', 'T_Addr_Normal_1.1003']
    assert r['placeholders'] == [{'role': 'erm', 'stem': 'T_Addr_ERM_1.1003', 'rgb': [0, 200, 0]}]
    assert all(N.udim_of(c['stem'] + '.png') == 1003 for c in r['copy'])
    assert plan['blocking'] == []


def test_instances_share_one_set_and_flora_alpha_diffuse():
    rows = [{'asset': 'flora:a_t1_h1', 'version': 'high', 'material': 'a_high', 'maps': ['a_t1_h1_high.png'] * 2,
             'uv_bbox': [[0, 0], [1, 1]], 'area3d_m2': 3, 'tex_px': [2048, 2048]}] * 3
    sets = T.texture_sets(rows)
    assert len(sets) == 1 and sets[0]['maps'] == {'diffuse': 'a_t1_h1_high.png'}
    plan = T.vpm_plan(sets, {}, 'Addr', N.texture_stem, 'flora')
    assert [p['role'] for p in plan['rows'][0]['placeholders']] == ['erm', 'normal']


def test_uv_outside_unit_square_blocks():
    plan = T.vpm_plan(_sets(1, uv=((0.0, 0.0), (1.5, 1.0))), {}, 'Addr', N.texture_stem, 'maf')
    assert plan['blocking'] == ['uv_outside_0_1']


def test_more_sets_than_limit_pack_into_4k_tiles_at_one_texel():
    sets = _sets(7, uv=((0.0, 0.0), (0.5, 0.5)))
    plan = T.vpm_plan(sets, {1: {1001}}, 'Addr', N.texture_stem, 'maf', tile_limit=5, texel=None, tile_px=4096)
    assert plan['mode'] == 'packed_4k'
    assert plan['tiles'][0] == (1, 1002)
    assert plan['texel_px_per_m'] == round(min(2048 / (4 + i) ** 0.5 for i in range(7)), 2)
    rects = [(r['udim'], r['x'], r['y'], r['w'], r['h']) for r in plan['rows']]
    assert plan['warnings'] == []
    for i, a in enumerate(rects):
        assert a[1] >= 0 and a[2] >= 0 and a[1] + a[3] <= 4096 and a[2] + a[4] <= 4096
        for b in rects[i + 1:]:
            if a[0] == b[0]:
                assert a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1] or a[2] + a[4] <= b[2] or b[2] + b[4] <= a[2]
    assert 0 < plan['fill'] <= 1


def test_npm_route():
    objs = [{'name': 'a_low', 'kind': 'flora', 'version': 'low'}, {'name': 'a_high', 'kind': 'flora',
                                                                   'version': 'high'},
            {'name': 'M_low', 'kind': 'maf', 'version': 'low'}]
    assert T.npm_route(objs) == {'atlas.flora': ['a_low'], 'atlas.npm': ['M_low']}


def test_assets_go_after_the_ground_tiles_with_ground_names():
    files = ['T_Addr_Diffuse_1.{}.png'.format(u) for u in range(1001, 1007)] + \
            ['T_Addr_Ground_Diffuse_1.{}.png'.format(u) for u in (1001, 1002, 1003)]
    ground = T.used_tiles(files, 'Addr', N.udim_of, ground=True)
    assert ground == {1: {1001, 1002, 1003}}
    assert T.used_tiles(files, 'Addr', N.udim_of, ground=False) == {1: set(range(1001, 1007))}
    plan = T.vpm_plan(_sets(2), ground, 'Addr', N.texture_stem, 'flora')
    assert plan['tiles'] == [(1, 1004), (1, 1005)] and plan['warnings'] == []
    assert plan['rows'][0]['copy'][0]['stem'] == 'T_Addr_Ground_Diffuse_1.1004'
    assert T.vpm_plan(_sets(1), {}, 'Addr', N.texture_stem, 'flora')['warnings'] == ['no_ground_tiles']


def test_packed_defaults_are_the_project_density_and_tile():
    plan = T.vpm_plan(_sets(7, uv=((0.0, 0.0), (0.25, 0.25))), {1: {1001}}, 'Addr', N.texture_stem, 'maf')
    assert plan['mode'] == 'packed_4k' and plan['texel_px_per_m'] == 1000.0
    assert all(r['x'] + r['w'] <= 3600 and r['y'] + r['h'] <= 3600 for r in plan['rows'])

def test_a_set_bigger_than_a_tile_is_fitted_and_reported_not_raised():
    rows = [{'asset': 'flora:big', 'version': 'high', 'material': 'big', 'maps': ['big_high.png'],
             'uv_bbox': [[0, 0], [1, 1]], 'area3d_m2': 25.0, 'tex_px': [4096, 4096]},
            {'asset': 'flora:small', 'version': 'high', 'material': 'small', 'maps': ['small_high.png'],
             'uv_bbox': [[0, 0], [1, 1]], 'area3d_m2': 1.0, 'tex_px': [2048, 2048]}]
    plan = T.vpm_plan(T.texture_sets(rows), {1: {1001}}, 'Addr', N.texture_stem, 'flora', tile_limit=1)
    big = [r for r in plan['rows'] if r['material'] == 'big'][0]
    assert plan['texel_reduced'] == ['big'] and big['w'] <= 3600 - 32 and big['texel_px_per_m'] < 1000
    small = [r for r in plan['rows'] if r['material'] == 'small'][0]
    assert small['texel_px_per_m'] == 1000.0 and 'findings' not in small


def test_default_limits_flora_always_tile_per_species_maf_five():
    many = _sets(12)
    flora = T.vpm_plan(many, {1: {1001}}, 'Addr', N.texture_stem, 'flora')
    assert flora['mode'] == 'tile_per_set' and len(flora['tiles']) == 12 and flora['tiles'][0] == (1, 1002)
    assert T.vpm_plan(_sets(5), {}, 'Addr', N.texture_stem, 'maf')['mode'] == 'tile_per_set'
    assert T.vpm_plan(_sets(6), {}, 'Addr', N.texture_stem, 'maf')['mode'] == 'packed_4k'
