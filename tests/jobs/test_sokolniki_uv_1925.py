"""Sokolniki #1925 step 4: finish zones, UV report table and the uv_config.json spec.

Pattern: n/a | new-case: tests of jobs/sokolniki-uvk1000/hooks/inset_build.py (body_finish, ring_relation),
inset_sheet.py (uv_rows) and uv_config.json against the shared atlas spec validator (no DCC).
Synthetic: all geometry and report numbers below are made up for the tests.
"""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / 'jobs/sokolniki-uvk1000'


def _load(name):
    spec = importlib.util.spec_from_file_location(name + '_1925', D / 'hooks' / (name + '.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ib = _load('inset_build')
sh = _load('inset_sheet')
CFG = json.loads((D / 'uv_config.json').read_text(encoding='utf-8'))
Z = CFG['zoning']
RING = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [0.0, 0.0]]


def test_ring_relation_facade_and_jamb():
    d, cos = ib.ring_relation((5.0, 0.0), (0.0, -1.0), RING)   # on the south line, facing out
    assert d == pytest.approx(0.0) and cos == pytest.approx(1.0)
    d, cos = ib.ring_relation((5.0, 0.2), (1.0, 0.0), RING)    # jamb across the south line, 0.2 m deep
    assert d == pytest.approx(0.2) and cos == pytest.approx(0.0)


@pytest.mark.parametrize('vol,z,finish', [
    ('N', (0.0, 0.3, 0.6), '02_porcelain_600_RAL7012'),
    ('N', (4.5, 6.0, 8.04), '01_brick_F301-80'),
    ('D', (0.6, 2.0, 3.84), '02_porcelain_600_RAL7012'),
    ('D', (4.5, 6.0, 8.04), '03_cassette_RAL9003'),
    ('S', (0.6, 1.8, 3.04), '01_brick_F301-80'),
    ('S', (3.6, 5.0, 6.64), '03_cassette_RAL9003'),
    ('H', (17.42, 20.0, 22.7), '03_cassette_RAL9003'),
])
def test_body_finish_dark_light_bands(vol, z, finish):
    assert ib.body_finish(vol, (0.0, -1.0, 0.0), z, 0.0, 1.0, 5.0, Z)[0] == finish


def test_body_finish_reveals_parapets_and_roof():
    up, down, side = (0.0, 0.0, 1.0), (0.0, 0.0, -1.0), (1.0, 0.0, 0.0)
    assert ib.body_finish('D', up, (18.97, 18.97, 18.97), 0.1, 0.0, 1.0, Z) == ('14_flashing_RAL7016', 'parapet_top')
    assert ib.body_finish('D', up, (0.9, 0.9, 0.9), 0.1, 0.0, 0.5, Z) == ('11_reveal_RAL9003', 'sill_head_soffit')
    assert ib.body_finish('D', down, (3.0, 3.0, 3.0), 0.1, 0.0, 9.0, Z) == ('11_reveal_RAL9003', 'sill_head_soffit')
    assert ib.body_finish('D', up, (7.5, 7.5, 7.5), 0.3, 0.0, 12.0, Z) == ('21_roof_membrane', 'ledge_roof')
    assert ib.body_finish('S', side, (11.12, 12.0, 13.5), 0.15, 1.0, 3.0, Z) == ('14_flashing_RAL7016', 'parapet_inner')
    assert ib.body_finish('S', side, (4.2, 5.0, 6.64), 0.1, 0.0, 1.0, Z) == ('11_reveal_RAL9003', 'jamb')
    # the outer parapet face stays cladding (on the ring line)
    assert ib.body_finish('S', (0.0, -1.0, 0.0), (11.12, 12.0, 13.5), 0.0, 1.0, 3.0, Z)[0] == '03_cassette_RAL9003'


def test_body_finish_refuses_a_face_across_a_finish_level():
    with pytest.raises(ValueError, match='crosses the finish level 3.84'):
        ib.body_finish('D', (0.0, -1.0, 0.0), (3.0, 4.0, 5.0), 0.0, 1.0, 5.0, Z)


def test_uv_config_is_a_valid_shared_atlas_spec():
    import sys
    sys.path.insert(0, str(ROOT))
    from tools.derive import finish_map
    finish_map.validate_spec(CFG)
    udims = sorted(t['udim'] for t in CFG['finishes'].values())
    assert udims == list(range(1001, 1001 + len(udims)))
    used = set(CFG['material_map'].values()) | {Z['reveal'], Z['parapet_top'], Z['parapet_inner'], Z['ledge_roof']}
    used |= {f for v in Z['volumes'].values() for _, f in v['bands']}
    assert used <= set(CFG['finishes'])
    for t in CFG['finishes'].values():   # tools/blender/vpm_uv.lmax contract for textured finishes
        if t['kind'] == 'full':
            assert len(t['P']) == 2 and all(type(s) is bool for s in t['shift'])
            assert t['S'] - 2 * CFG['pad_m'] - max(t['P']) > 1.5


def test_uv_rows_scales_texel_to_the_atlas_region():
    rep = {'objects': {
        'A': {'tris_before': 10, 'tris_after': 14, 'overflow_ngons_split': 1,
              'edges_before': {'open': 4, 'open_len_m': 8.0, 'nonmanifold': 0},
              'edges_after': {'open': 6, 'open_len_m': 8.0, 'nonmanifold': 0},
              'uv_qa': {'01_brick_F301-80': {'faces': 5, 'overflow': 0}},
              'density_px_per_m': {'01_brick_F301-80': [913, 1024]}},
        'B': {'tris_before': 4, 'tris_after': 4,
              'edges_before': {'open': 4, 'open_len_m': 4.0, 'nonmanifold': 0},
              'edges_after': {'open': 4, 'open_len_m': 4.5, 'nonmanifold': 0},
              'uv_qa': {'12_frame_RAL9003': {'faces': 2, 'overflow': 1}}, 'density_px_per_m': {}}}}
    rows, tot = sh.uv_rows(rep, CFG, {'region': 377})
    brick = next(r for r in rows if r['finish'] == '01_brick_F301-80')
    assert brick['faces'] == 5 and brick['npm_px_per_m'] == [84.0, 94.2]
    assert next(r for r in rows if r['finish'] == '12_frame_RAL9003')['npm_px_per_m'] is None
    assert tot == {'tris_before': 14, 'tris_after': 18, 'overflow': 1, 'ngons_split': 1,
                   'open_len_changed': ['B'], 'nonmanifold_after': 0}
