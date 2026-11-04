"""new-case: AGR Tools 0.5.0 diagnostics (names, triangle limits per FBX, textures, pivot, GeoJSON).

Each GeoAGR 13.64 defect that applies (D1-D4, D6, D8) is a pair of tests: the same property fails on a
GeoAGR-faithful variant (transcribed from GeoAGR.ms, line cited) and holds on our core.
D5 (texel per system unit) belongs to the 0.3.0 texel readout and D7 (unreachable UI) to no button here.
"""
import importlib.util
import json
import math
import struct
import zlib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'


def _load(name, mod):
    spec = importlib.util.spec_from_file_location(mod, PKG / name)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


core = _load('checks_core.py', 'agr_checks_core_test')
runtime = _load('runtime.py', 'agr_runtime_checks_test')


def png(w, h, depth=8, ctype=2, trns=False, pad=0):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    body = chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, depth, ctype, 0, 0, 0))
    if trns:
        body += chunk(b'tRNS', b'\x00\x00')
    body += chunk(b'IDAT', zlib.compress(b'\x00' * 16 + b'\x00' * pad)) + chunk(b'IEND', b'')
    return b'\x89PNG\r\n\x1a\n' + body


def codes(items):
    return sorted({i[0] for i in items})


# --- thresholds pinned to the locked standards ---------------------------------------------------------
def test_thresholds_match_locked_standards():
    npm = yaml.safe_load((ROOT / 'standards/NPM_STANDARD.yaml').read_text(encoding='utf-8'))
    vpm = yaml.safe_load((ROOT / 'standards/VPM_STANDARD.yaml').read_text(encoding='utf-8'))
    assert core.NPM_OKS_TRI_MAX == npm['geometry']['oks_triangles_per_fbx_max']
    assert core.NPM_GROUND_TRI_MAX == npm['geometry']['ground_triangles_total_max']
    assert core.VPM_OKS_TRI_MAX == vpm['geometry']['oks_triangles_per_fbx_max_excluding_collision']
    table = [(r.get('area_max'), r['triangles_max']) for r in vpm['geometry']['ground_triangles_max_by_area_ha']]
    assert list(core.VPM_GROUND_TRI_BY_AREA) == table
    assert tuple(npm['textures']['allowed_square_sizes_px']) == core.NPM_TEX_SIZES
    assert npm['textures']['max_file_bytes'] == core.NPM_TEX_BYTES_MAX
    assert npm['textures']['island_padding_px_min'] == core.NPM_PADDING_PX
    assert npm['textures']['ground_elements_set_size_px_max'] == core.NPM_GROUND_EL_MAX
    assert npm['textures']['vegetation_set_size_px_max'] == core.NPM_FLORA_MAX
    assert tuple(vpm['textures']['allowed_square_sizes_px']) == core.VPM_TEX_SIZES
    assert vpm['textures']['padding_px_min'] == core.VPM_PADDING_PX
    assert vpm['textures']['bits_per_channel'] == core.VPM_BITS
    assert vpm['textures']['flat_placeholder']['size_px'] == core.VPM_TEX_PLACEHOLDER
    assert vpm['naming']['max_characters'] == core.NAME_MAX == npm['naming']['max_characters'] if 'naming' in npm else True
    assert 2000000 not in (core.VPM_OKS_TRI_MAX, *[t for _, t in core.VPM_GROUND_TRI_BY_AREA])


def test_every_adapted_function_cites_geoagr():
    text = (PKG / 'checks_core.py').read_text(encoding='utf-8')
    for fn in ('mesh_kind', '_symbols', '_address_tokens', 'name_findings', 'triangle_limits',
               'texture_file_findings', 'udim_set_findings', 'padding_findings', 'pivot_findings'):
        doc = getattr(core, fn).__doc__
        assert 'adapted from GeoAGR 13.64 (author Artem), GeoAGR.ms:' in doc and 'changes:' in doc, fn
    assert len(text.splitlines()) < 1000  # only the used logic, not GeoAGR.ms


# --- D2: substring `case` order ------------------------------------------------------------------------
def geoagr_kind(name):
    """GeoAGR.ms:65326-65333 / 65740-65745: first substring branch wins."""
    for token in ('Main', 'MainGlass', 'GroundGlass', 'Ground', 'UCX_'):
        if token in name:
            return token.rstrip('_').replace('UCX', 'UCX')
    return None


@pytest.mark.parametrize('name,kind', [('SM_Addr_001_MainGlass', 'MainGlass'),
                                       ('UCX_SM_Addr_Ground_001', 'UCX'),
                                       ('UCX_SM_Addr_Main_001', 'UCX'),
                                       ('SM_Addr_Ground', 'Ground')])
def test_d2_exact_token_kind(name, kind):
    assert core.mesh_kind(name) == kind


def test_d2_red_on_geoagr_faithful_variant():
    assert geoagr_kind('SM_Addr_001_MainGlass') == 'Main'
    assert geoagr_kind('UCX_SM_Addr_Ground_001') == 'Ground'


# --- D4: SlotNumber 2..7 ---------------------------------------------------------------------------------
def geoagr_slot_error(name):
    """GeoAGR.ms:7103/7111: tt[tt.count] != "1" (M_Glass_ exempt) is an error."""
    return name.split('_')[-1] != '1' and 'M_Glass_' not in name


@pytest.mark.parametrize('name,role', [('M_Addr_001_Main_2', 'M'), ('M_Addr_001_Main_7', 'M'),
                                       ('T_Addr_001_Main_d_2', 'T'), ('T_Addr_001_Main_r_7.png', 'T')])
def test_d4_slot_numbers_2_to_7_are_legal(name, role):
    assert 'name_suffix' not in codes(core.name_findings(name, role, 'npm'))
    assert geoagr_slot_error(name.replace('.png', ''))  # RED on the faithful rule


@pytest.mark.parametrize('name,role', [('M_Addr_001_Main_8', 'M'), ('M_Addr_001_Main_0', 'M'),
                                       ('T_Addr_001_Main_d_8', 'T'), ('M_Addr_001_Main', 'M')])
def test_slot_outside_1_to_7_is_an_error(name, role):
    assert 'name_suffix' in codes(core.name_findings(name, role, 'npm'))


def test_vpm_texture_slot_and_udim():
    assert core.name_findings('T_Tverskaya_12_Diffuse_2.1001.png', 'T', 'vpm') == []
    assert core.name_findings('T_Tverskaya_12_Ground_Normal_1.1100.png', 'T', 'vpm') == []
    assert 'name_suffix' in codes(core.name_findings('T_Tverskaya_12_Diffuse_1.1101.png', 'T', 'vpm'))
    assert 'name_suffix' in codes(core.name_findings('T_Tverskaya_12_Diffuse_1.png', 'T', 'vpm'))
    assert 'name_suffix' in codes(core.name_findings('T_Tverskaya_12_Albedo_1.1001.png', 'T', 'vpm'))
    assert 'name_symbols' in codes(core.name_findings('T_Tverskaya_12_Diffuse_1.1001.png', 'T', 'npm'))


# --- names cross-check with twinqa.naming --------------------------------------------------------------
CROSS = [  # (name, model, fbx role, ours non-pass?, twinqa non-pass?)
    ('SM_Tverskaya_12_001_Main', 'npm', 'oks', False, False),
    ('SM_Tverskaya_12_001_MainGlass', 'npm', 'oks', False, False),
    ('SM_Tverskaya_12_Main', 'npm', 'oks', True, True),
    ('SM_Tverskaya_12_021_Main', 'npm', 'oks', True, True),
    ('SM_Tverskaya_12_001_Main_1', 'npm', 'oks', True, True),
    ('SM_Tverskaya_12_001_Ground', 'npm', 'oks', True, True),
    ('SM_Tverskaya_12_GroundEl', 'npm', 'ground', False, False),
    ('SM_Tverskaya 12_001_Main', 'npm', 'oks', True, True),
    ('SM_Тверская_12_001_Main', 'npm', 'oks', True, True),
    ('UCX_SM_Tverskaya_12_Main_001', 'npm', 'oks', True, True),
    ('SM_Tverskaya_12_Main', 'vpm', 'oks', False, False),
    ('UCX_SM_Tverskaya_12_Main_001', 'vpm', 'oks', False, False),
    ('UCX_SM_Tverskaya_12_Main_01', 'vpm', 'oks', True, True),
    ('UCX_SM_Tverskaya_12_Main_001', 'vpm', 'ground', True, True),
    ('SM_Tverskaya_12_GroundEl', 'vpm', 'ground', True, True),
    ('SM_Tverskaya_12_Ground', 'vpm', 'ground', False, False),
    ('SM_' + 'A' * 252, 'vpm', 'oks', True, True),
    # differences: GeoAGR's capital-letter and digits-apart rules (NPM-1.3-4, NPM-1.3-3.b) are ours only
    ('SM_tverskaya_12_001_Main', 'npm', 'oks', True, False),
    ('SM_Tverskaya12_001_Main', 'npm', 'oks', True, False),
    ('SM_tverskaya_12_Main', 'vpm', 'oks', True, False),
]


@pytest.mark.parametrize('name,model,role,ours,theirs', CROSS)
def test_names_cross_check_with_twinqa(name, model, role, ours, theirs):
    from twinqa.naming import mesh_name_violation
    assert bool(core.name_findings(name, 'SM', model, role)) is ours
    assert bool(mesh_name_violation(name, model, role, None, 254)) is theirs


# --- D8: triangle limits per FBX ----------------------------------------------------------------------
def geoagr_tri_errors(rows):
    """GeoAGR.ms:65601-65625: sum over the selection, Main <= 150 000 and Main+Ground <= 180 000."""
    oks = sum(r['triangles'] for r in rows if 'Main' in r['name'])
    gr = sum(r['triangles'] for r in rows if any(t in r['name'] for t in ('Flora', 'Ground', 'GroundEl')))
    return oks > 150000 or oks + gr > 180000


def row(key, name, fbx, tri, area=None):
    return {'key': key, 'name': name, 'fbx': fbx, 'triangles': tri, 'site_area_ha': area}


D8_SCENE = [row(1, 'SM_Tverskaya_12_001_Main', 'C:/o/0001_Tverskaya_12_01.fbx', 100000),
            row(2, 'SM_Tverskaya_12_002_Main', 'C:/o/0001_Tverskaya_12_02.fbx', 100000),
            row(3, 'SM_Tverskaya_12_Ground', 'C:/o/0001_Tverskaya_12_Ground.fbx', 170000)]


def test_d8_limits_are_per_fbx():
    found, table = core.triangle_limits(D8_SCENE)
    assert all(v == [] for v in found.values())
    assert [(t['fbx'].split('/')[-1], t['render_triangles'], t['limit']) for t in table] == [
        ('0001_Tverskaya_12_01.fbx', 100000, 150000), ('0001_Tverskaya_12_02.fbx', 100000, 150000),
        ('0001_Tverskaya_12_Ground.fbx', 170000, 180000)]
    assert geoagr_tri_errors(D8_SCENE)  # RED on the faithful sum over the selection


def test_tri_limits_boundaries_and_fail_closed():
    fbx = 'C:/o/0001_Tverskaya_12_01.fbx'
    assert core.triangle_limits([row(1, 'SM_A_001_Main', fbx, 150000)])[0][1][0][0] == 'tri_at_limit'
    assert core.triangle_limits([row(1, 'SM_A_001_Main', fbx, 150001)])[0][1][0][0] == 'tri_limit'
    assert core.triangle_limits([row(1, 'SM_A_001_Main', fbx, 149999)])[0][1] == []
    two = core.triangle_limits([row(1, 'SM_A_001_Main', fbx, 80000), row(2, 'SM_A_001_MainGlass', fbx, 80000)])[0]
    assert codes(two[1]) == codes(two[2]) == ['tri_limit']
    for bad in (None, -1, 1.5, True, float('nan')):
        assert core.triangle_limits([row(1, 'SM_A_001_Main', fbx, bad)])[0][1][0][0] == 'tri_unmeasurable'
    for path in (None, '', 'C:/o/model.fbx', 'C:/o/SM_A.obj'):
        assert core.triangle_limits([row(1, 'SM_A_001_Main', path, 5)])[0][1][0][0] == 'fbx_unmapped'


def test_vpm_limits_ucx_and_ground_area():
    oks = 'C:/o/SM_Tverskaya_12.fbx'
    assert core.triangle_limits([row(1, 'SM_Tverskaya_12_Main', oks, 1000001)])[0][1][0][0] == 'tri_limit'
    assert core.triangle_limits([row(1, 'SM_Tverskaya_12_Main', oks, 999999)])[0][1] == []
    found, table = core.triangle_limits([row(1, 'SM_Tverskaya_12_Main', oks, 40000),
                                         row(2, 'UCX_SM_Tverskaya_12_Main_001', oks, 15001)])
    assert table[0]['ucx_limit'] == 15000 and found[2][0][0] == 'ucx_tri_limit' and found[1] == []
    assert core.vpm_ucx_limit(60000) == 3000 and core.vpm_ucx_limit(5000000) == 100000
    gr = 'C:/o/SM_Tverskaya_12_Ground.fbx'
    assert core.triangle_limits([row(1, 'SM_Tverskaya_12_Ground', gr, 300001, 0.05)])[0][1][0][0] == 'tri_limit'
    assert core.triangle_limits([row(1, 'SM_Tverskaya_12_Ground', gr, 300001, 0.06)])[0][1] == []
    assert core.triangle_limits([row(1, 'SM_Tverskaya_12_Ground', gr, 10, 9.0)])[1][0]['limit'] == 4500000
    for area in (None, 0.0, -1.0, float('nan'), float('inf'), 'x'):
        assert core.triangle_limits([row(1, 'SM_Tverskaya_12_Ground', gr, 10, area)])[0][1][0][0] == 'tri_unmeasurable'
    mixed = core.triangle_limits([row(1, 'SM_T_Ground', gr, 10, 0.1), row(2, 'SM_T_GroundGlass', gr, 10, 0.2)])[0]
    assert mixed[1][0][0] == mixed[2][0][0] == 'tri_unmeasurable'


# --- textures: D1, D3, sizes, alpha, bits, padding -------------------------------------------------------
def quad(x0, y0, s, base):
    return [(x0, y0), (x0 + s, y0), (x0 + s, y0 + s), (x0, y0 + s)], [(base + 1, [base * 2 + 0, base * 2 + 1, base * 2 + 2]),
                                                                       (base + 2, [base * 2 + 0, base * 2 + 2, base * 2 + 3])]


def two_islands(gap_uv):
    uvs = [(0.1, 0.1), (0.4, 0.1), (0.4, 0.4), (0.1, 0.4),
           (0.4 + gap_uv, 0.1), (0.7 + gap_uv, 0.1), (0.7 + gap_uv, 0.4), (0.4 + gap_uv, 0.4)]
    faces = [(1, [0, 1, 2]), (2, [0, 2, 3]), (3, [4, 5, 6]), (4, [4, 6, 7])]
    return uvs, faces


NPM_FBX = 'C:/o/0001_Tverskaya_12_01.fbx'
VPM_FBX = 'C:/o/SM_Tverskaya_12.fbx'


def tex_row(key, name, maps, fbx=NPM_FBX, gap=20 / 2048):
    return {'key': key, 'name': name, 'fbx': fbx, 'maps': maps, 'uv': lambda: two_islands(gap)}


def geoagr_checked_paths(objects):
    """GeoAGR.ms:65313: `texes_paths = texs` is overwritten per object; only the last list is opened."""
    texes_paths = []
    for maps in objects:
        if maps:
            texes_paths = maps
    return texes_paths


def test_d1_every_object_maps_are_checked():
    bad = ('T_Tverskaya_12_001_Main_d_1.png', png(1000, 1000))
    good = ('T_Tverskaya_12_002_Main_d_1.png', png(1024, 1024))
    found, _ = core.textures_scene([tex_row(1, 'SM_Tverskaya_12_001_Main', [bad]),
                                    tex_row(2, 'SM_Tverskaya_12_002_Main', [good])])
    assert 'tex_size' in codes(found[1]) and found[2] == []
    assert bad not in geoagr_checked_paths([[bad], [good]])  # RED: GeoAGR never opens the first object's map


def test_d3_empty_map_array_is_no_maps():
    found, dropped = core.textures_scene([tex_row(1, 'SM_Tverskaya_12_MainGlass', [], VPM_FBX)])
    assert found[1] == [] and dropped[0]['reason'].startswith('glass without maps')
    assert ([] != None) is True  # noqa: E711 - RED: GeoAGR.ms:65715 `usedMaps != undefined` is always true


def test_texture_rules_npm():
    def one(name, data, obj='SM_Tverskaya_12_001_Main', fbx=NPM_FBX):
        # a 0.1 UV gap is 12.8 px even at the 128 px placeholder: padding stays out of the size rules
        return codes(core.textures_scene([tex_row(1, obj, [(name, data)], fbx, gap=0.1)])[0][1])
    assert one('T_A_001_Main_d_1.png', png(2048, 2048)) == []
    assert one('T_A_001_Main_d_1.png', png(4096, 4096)) == ['tex_size']
    assert one('T_A_001_Main_d_1.png', png(1024, 512)) == ['tex_size']
    assert one('T_A_001_Main_d_1.png', png(128, 128)) == ['tex_size']
    assert one('T_A_001_Main_m_1.png', png(128, 128)) == []
    assert one('T_A_001_Main_d_1.png', png(1024, 1024, ctype=6)) == ['tex_alpha']
    assert one('T_A_001_Main_d_1.png', png(1024, 1024, trns=True)) == ['tex_alpha']
    assert one('T_A_001_Main_d_1.jpg', b'x') == ['tex_format']
    assert one('T_A_001_Main_d_1.png', None) == ['tex_missing']
    assert one('T_A_001_Main_d_1.png', b'\x89PNG\r\n\x1a\n\x00') == ['tex_unreadable']
    assert one('T_A_001_Main_d_1.png', b'') == ['tex_unreadable']
    ground = 'C:/o/0001_Tverskaya_12_Ground.fbx'
    assert one('T_A_GroundEl_d_1.png', png(1024, 1024), 'SM_A_GroundEl', ground) == ['tex_size']
    assert one('T_A_GroundEl_d_1.png', png(512, 512), 'SM_A_GroundEl', ground) == []
    big = png(1024, 1024, pad=0)
    heavy = big + b'\x00' * (core.NPM_TEX_BYTES_MAX - len(big))
    assert one('T_A_001_Main_d_1.png', heavy) == ['at_threshold']
    assert one('T_A_001_Main_d_1.png', heavy + b'\x00') == ['tex_file_size']
    assert one('T_A_001_Main_d_1.png', png(1024, 1024), obj='SM_A_001_MainGlass') == ['tex_format']


def vpm_set(size=2048, udims=(1001,), **kw):
    return [(f'T_Tverskaya_12_{m}_1.{u}.png', png(size, size, **(kw if m != 'Diffuse' else {})))
            for u in udims for m in ('Diffuse', 'ERM', 'Normal')]


def test_texture_rules_vpm():
    def one(maps, gap=20 / 2048):
        return codes(core.textures_scene([tex_row(1, 'SM_Tverskaya_12_Main', maps, VPM_FBX, gap)])[0][1])
    assert one(vpm_set()) == []
    assert one(vpm_set(4096), gap=40 / 4096) == []
    assert one(vpm_set(1024)) == ['tex_size']
    assert one(vpm_set(udims=(1001, 1003))) == ['tex_udim']
    assert one(vpm_set(udims=(1002,))) == ['tex_udim']
    assert one(vpm_set()[:2]) == ['tex_set']
    assert one(vpm_set(ctype=6)) == ['tex_alpha']
    diffuse_alpha = [(n, png(2048, 2048, ctype=6) if 'Diffuse' in n else d) for n, d in vpm_set()]
    assert one(diffuse_alpha) == []
    assert one(vpm_set(depth=16)) == ['tex_bit_depth']
    assert one([(n, png(256, 256, ctype=6)) for n, _ in vpm_set()]) == ['tex_alpha']


@pytest.mark.parametrize('gap_px,expected', [(20, []), (16.5, []), (16, ['at_threshold']), (10, ['tex_padding']),
                                             (0, ['tex_padding']), (-30, ['tex_padding'])])
def test_vpm_padding_16_px_at_2048(gap_px, expected):
    uvs, faces = two_islands(gap_px / 2048)
    assert codes(core.padding_findings(uvs, faces, 2048, 16)) == expected


IDENTICAL = -0.3  # two_islands(-0.3): the second square lies exactly on the first (a repeating island)


@pytest.mark.parametrize('gap_px,expected', [(IDENTICAL * 2048, ['tex_overlap_review']), (0, ['tex_overlap_review']),
                                             (-30, ['tex_overlap_review']), (10, ['tex_padding']),
                                             (16, ['at_threshold']), (20, [])])
def test_vpm_overlap_is_review_not_padding(gap_px, expected):
    """VPM 2.5.1.5: padding applies to islands with unique images; repeating islands may overlap
    (VPM_STANDARD uv.repeating_islands_may_overlap, glass.overlap_allowed) -> review, not tex_padding."""
    uvs, faces = two_islands(gap_px / 2048)
    got = core.padding_findings(uvs, faces, 2048, 16, overlap_review=True)
    assert codes(got) == expected
    assert len(got) == len(expected)  # one finding, not one per pair


@pytest.mark.parametrize('gap_px', [IDENTICAL * 2048, 0, -30])
def test_non_vpm_overlap_stays_padding(gap_px):
    uvs, faces = two_islands(gap_px / 2048)
    assert codes(core.padding_findings(uvs, faces, 2048, 16)) == ['tex_padding']
    assert codes(core.padding_findings(uvs, faces, 2048, 8, overlap_review=False)) == ['tex_padding']


def test_vpm_overlap_does_not_hide_a_small_gap_of_the_same_owner():
    """Worst pair per owner: a gap-0 overlap must not mask a 10 px pair of the same object."""
    uvs, faces = two_islands(IDENTICAL)
    uvs = uvs + [(0.4 + 10 / 2048, 0.1), (0.7, 0.1), (0.7, 0.4), (0.4 + 10 / 2048, 0.4)]
    faces = faces + [(5, [8, 9, 10]), (6, [8, 10, 11])]
    got = core.padding_findings(uvs, faces, 2048, 16, overlap_review=True)
    assert codes(got) == ['tex_overlap_review', 'tex_padding'] and len(got) == 2


def test_textures_scene_vpm_overlap_review_npm_overlap_padding():
    vpm = core.textures_scene([tex_row(1, 'SM_Tverskaya_12_Main', vpm_set(), VPM_FBX, IDENTICAL)])[0][1]
    assert codes(vpm) == ['tex_overlap_review']
    assert codes(core.textures_scene([tex_row(1, 'SM_Tverskaya_12_Main', vpm_set(), VPM_FBX, 10 / 2048)])[0][1]) \
        == ['tex_padding']
    npm = core.textures_scene([tex_row(1, 'SM_Tverskaya_12_001_Main', [('T_Tverskaya_12_001_Main_d_1.png',
                                                                       png(1024, 1024))], gap=IDENTICAL)])[0][1]
    assert codes(npm) == ['tex_padding']
    assert 'tex_overlap_review' in core.CODES['textures']


def test_padding_geoagr_live_8px_would_pass_a_12px_gap():
    uvs, faces = two_islands(12 / 2048)
    assert codes(core.padding_findings(uvs, faces, 2048, 16)) == ['tex_padding']
    assert codes(core.padding_findings(uvs, faces, 2048, 8)) == []  # GeoAGR's live 8 px branch (matrix gap 3)


def test_padding_fail_closed_and_tiles():
    assert codes(core.padding_findings([], [], 2048, 16)) == ['tex_unmeasurable']
    uvs, faces = two_islands(0.01)
    uvs[0] = (float('nan'), 0.0)
    assert codes(core.padding_findings(uvs, faces, 2048, 16)) == ['tex_unmeasurable']
    uvs, faces = two_islands(0.0)
    uvs = uvs[:4] + [(u + 1.0, v) for u, v in uvs[4:]]  # other UDIM tile: no shared padding
    assert core.padding_findings(uvs, faces, 2048, 16) == []
    inner = [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9), (0.4, 0.4), (0.5, 0.4), (0.5, 0.5), (0.4, 0.5)]
    faces = [(1, [0, 1, 2]), (2, [0, 2, 3]), (3, [4, 5, 6]), (4, [4, 6, 7])]
    assert codes(core.padding_findings(inner, faces, 2048, 16)) == ['tex_padding']  # contained island


def test_padding_budget_is_unmeasurable(monkeypatch):
    monkeypatch.setattr(core, 'PADDING_PAIR_BUDGET', 3)
    uvs, faces = two_islands(1 / 2048)
    assert codes(core.padding_findings(uvs, faces, 2048, 16)) == ['tex_unmeasurable']


def test_padding_bruteforce_probe():
    """Probe: the reported gap equals a dense brute-force distance between the two squares."""
    import random
    rnd = random.Random(804)
    for _ in range(200):
        gap_px = rnd.uniform(0.0, 40.0)
        uvs, faces = two_islands(gap_px / 2048)
        got = core.padding_findings(uvs, faces, 2048, 16)
        if abs(gap_px - 16) < 1e-6:
            continue
        assert codes(got) == ([] if gap_px > 16 else ['tex_padding']), gap_px


# --- padding per atlas (review r1 P1): face matID -> slot maps; atlases shared across objects of one FBX --
def full_square_islands(mat_ids, x0=0.0, s=1.0):
    """One island per entry, each covering the same UV square, with the given face matID."""
    uvs, faces = [], []
    for k, mid in enumerate(mat_ids):
        b = len(uvs)
        uvs += [(x0, 0.0), (x0 + s, 0.0), (x0 + s, s), (x0, s)]
        faces += [(2 * k + 1, [b, b + 1, b + 2], mid), (2 * k + 2, [b, b + 2, b + 3], mid)]
    return uvs, faces


def slot_row(key, name, slots, fbx, uv):
    maps, seen = [], set()
    for paths in slots.values():
        for p, d in paths or []:
            if p not in seen:
                seen.add(p)
                maps.append((p, d))
    return {'key': key, 'name': name, 'fbx': fbx, 'maps': maps,
            'slots': {mid: None if paths is None else [p for p, _ in paths]
                                         for mid, paths in slots.items()}, 'uv': lambda: uv}


def geoagr_pooled_padding(uvs, faces, size, need):
    """r1 variant: every UV face of the object in one pool, whatever its matID (the fixed defect)."""
    return core.padding_findings(uvs, [(f, idx) for f, idx, *_ in faces], size, need)


def test_two_slot_npm_islands_of_different_atlases_are_not_compared():
    d1 = ('T_Tverskaya_12_001_Main_d_1.png', png(1024, 1024))
    d2 = ('T_Tverskaya_12_001_Main_d_2.png', png(1024, 1024))
    uv = full_square_islands([1, 2])
    found, dropped = core.textures_scene([slot_row(1, 'SM_Tverskaya_12_001_Main', {1: [d1], 2: [d2]}, NPM_FBX, uv)])
    assert found[1] == [] and dropped == []
    assert codes(geoagr_pooled_padding(*uv, 1024, 8)) == ['tex_padding']  # RED: r1 pooled both slots


def test_two_slot_vpm_on_udim_1001_is_clean():
    s1 = [(f'T_Tverskaya_12_{m}_1.1001.png', png(2048, 2048)) for m in ('Diffuse', 'ERM', 'Normal')]
    s2 = [(f'T_Tverskaya_12_{m}_2.1001.png', png(2048, 2048)) for m in ('Diffuse', 'ERM', 'Normal')]
    uv = full_square_islands([1, 2])
    found, dropped = core.textures_scene([slot_row(1, 'SM_Tverskaya_12_Main', {1: s1, 2: s2}, VPM_FBX, uv)])
    assert found[1] == [] and dropped == []
    assert codes(geoagr_pooled_padding(*uv, 2048, 16)) == ['tex_padding']  # RED: r1 pooled both slots


def shared_atlas_rows(fbx_b=NPM_FBX, gap=0.0):
    d = ('T_Tverskaya_12_Main_d_1.png', png(1024, 1024))
    a = full_square_islands([1], 0.1, 0.3)
    b = full_square_islands([1], 0.4 + gap, 0.3)
    return [slot_row(1, 'SM_Tverskaya_12_001_Main', {1: [d]}, NPM_FBX, a),
            slot_row(2, 'SM_Tverskaya_12_002_Main', {1: [d]}, fbx_b, b)]


def test_shared_atlas_touching_islands_of_two_objects_fail():
    found, dropped = core.textures_scene(shared_atlas_rows())
    assert codes(found[1]) == ['tex_padding'] and codes(found[2]) == ['tex_padding'] and dropped == []
    assert found[1][0][2] == [1, 2] and found[2][0][2] == [1, 2]  # each object gets ITS face ids
    # RED: r1 measured each object alone -> both [] with no dropped entry (silent skip)
    assert all(geoagr_pooled_padding(*r['uv'](), 1024, 8) == [] for r in shared_atlas_rows())


def test_shared_atlas_in_other_fbx_is_not_compared_and_wide_gap_passes():
    found, _ = core.textures_scene(shared_atlas_rows(fbx_b='C:/o/0001_Tverskaya_12_02.fbx'))
    assert found == {1: [], 2: []}
    found, _ = core.textures_scene(shared_atlas_rows(gap=20 / 1024))
    assert found == {1: [], 2: []}


def test_shared_atlas_padding_combined_with_d1_and_single_material_rows():
    """Regression combined with the earlier fixes: a bad map on the FIRST object (D1) and a row
    without slots (single material) sharing the atlas still pools its faces."""
    rows = shared_atlas_rows()
    rows[0]['maps'].append(('T_Tverskaya_12_001_Main_n_1.png', png(1000, 1000)))
    rows[0]['slots'][1].append('T_Tverskaya_12_001_Main_n_1.png')
    del rows[1]['slots']
    rows[1]['uv'] = (lambda uv: lambda: (uv[0], [(f, idx) for f, idx, _ in uv[1]]))(rows[1]['uv']())
    found, _ = core.textures_scene(rows)
    assert codes(found[1]) == ['tex_padding', 'tex_size'] and codes(found[2]) == ['tex_padding']


def test_unmapped_face_matid_is_an_error_naming_it():
    """matID 5 on #(1, 3) wraps to ID 2 (highest ID 3), which has no sub-material: the 3ds Max 2026 FBX
    export writes an empty placeholder slot there (measured, PR #827 body), so it stays unmeasurable."""
    d1 = ('T_Tverskaya_12_001_Main_d_1.png', png(1024, 1024))
    uv = full_square_islands([1, 5])
    found, _ = core.textures_scene([slot_row(1, 'SM_Tverskaya_12_001_Main', {1: [d1], 3: [d1]}, NPM_FBX, uv)])
    assert codes(found[1]) == ['tex_unmeasurable'] and 'matID 5' in found[1][0][1]


# Measured in 3ds Max 2026.3 (3dsmaxbatch, FBX export + re-import, card t_8fc3cd5f / #827):
# face matID -> materialIDList entry the exported polygon gets; None = empty placeholder "Slot #k".
MAX_FBX_MATID = {
    (1, 2): {1: 1, 2: 2, 3: 1, 4: 2, 5: 1, 6: 2},
    (1, 5): {1: 1, 2: None, 3: None, 4: None, 5: 5, 6: 1, 7: None, 10: 5, 11: 1},
    (2, 3): {1: None, 2: 2, 3: 3, 4: None, 5: 2, 6: 3},
}


@pytest.mark.parametrize('ids', sorted(MAX_FBX_MATID))
def test_max_submaterial_index_matches_the_max_fbx_measurement(ids):
    for mid, want in MAX_FBX_MATID[ids].items():
        got = core.max_submaterial_index(mid, list(ids))
        assert (None if got is None else ids[got]) == want, (ids, mid)


def test_max_submaterial_index_fails_closed():
    assert core.max_submaterial_index(1, []) is None  # 0 sub-materials
    assert core.max_submaterial_index(3, [1, 1]) is None  # duplicated ID: ambiguous, never the first
    assert core.max_submaterial_index(1, [1, 1]) is None
    assert core.max_submaterial_index(0, [1, 2]) is None and core.max_submaterial_index(-1, [1, 2]) is None
    assert core.max_submaterial_index(None, [1, 2]) is None and core.max_submaterial_index(2.0, [1, 2]) is None


def test_runtime_lookups_share_the_max_resolver():
    """matid / _material_names / _slot_gaps resolve a Multimaterial slot through one helper.
    RED: r2 runtime looked IDs up strictly, so matID 3 on #(1, 2) was an empty slot."""
    import types
    a, b = types.SimpleNamespace(name='A'), types.SimpleNamespace(name='B')
    mm = types.SimpleNamespace(materialIDList=[1, 2], materialList=[a, None])
    assert runtime._max_submaterial(mm, 3) is a and runtime._max_submaterial(mm, 1) is a
    assert runtime._max_submaterial(mm, 4) is None and runtime._max_submaterial(mm, 2) is None
    mm = types.SimpleNamespace(materialIDList=[1, 5], materialList=[a, b])
    assert [runtime._max_submaterial(mm, m) for m in (6, 10, 3)] == [a, b, None]
    src = (PKG / 'runtime.py').read_text(encoding='utf-8')
    assert src.count('_max_submaterial(') == 4 and 'materialIDList[i]) ==' not in src


def two_slot_rows(mat_ids):
    d1 = ('T_Tverskaya_12_001_Main_d_1.png', png(1024, 1024))
    d2 = ('T_Tverskaya_12_001_Main_d_2.png', png(1024, 1024))
    return [slot_row(1, 'SM_Tverskaya_12_001_Main', {1: [d1], 2: [d2]}, NPM_FBX, full_square_islands(mat_ids))]


def test_matid_outside_list_is_measured_on_the_max_slot_with_an_advisory():
    """(a) matID 3 on #(1, 2): 3ds Max exports it with sub 1 (matID 1). RED: r2 said tex_unmeasurable."""
    found, dropped = core.textures_scene(two_slot_rows([2, 3]))
    assert codes(found[1]) == ['tex_matid_wrapped'] and len(found[1]) == 1 and dropped == []
    assert 'matID 3 -> sub 1 (matID 1)' in found[1][0][1]
    assert 'tex_matid_wrapped' in core.CODES['textures']
    # witness: the matID 3 island is pooled with the matID 1 island (same atlas d_1), not with matID 2
    found, _ = core.textures_scene(two_slot_rows([1, 3]))
    assert codes(found[1]) == ['tex_matid_wrapped', 'tex_padding']
    assert [i[2] for i in found[1] if i[0] == 'tex_padding'] == [[1, 2, 3, 4]]


def test_listed_matids_only_are_unchanged():
    """(b) no face outside the list: no advisory, same findings as before."""
    assert core.textures_scene(two_slot_rows([1, 2])) == ({1: []}, [])
    found, _ = core.textures_scene(two_slot_rows([1, 1]))
    assert codes(found[1]) == ['tex_padding']


def test_multimaterial_without_submaterials_is_unmeasurable():
    """(c) 0 sub-materials: no slot to wrap to. RED: r2 returned no finding at all (silent pass)."""
    d1 = ('T_Tverskaya_12_001_Main_d_1.png', png(1024, 1024))
    row = slot_row(1, 'SM_Tverskaya_12_001_Main', {}, NPM_FBX, full_square_islands([1]))
    row['maps'] = [d1]
    found, _ = core.textures_scene([row])
    assert codes(found[1]) == ['tex_unmeasurable'] and 'no sub-materials' in found[1][0][1]


def test_slot_without_maps_is_missing_and_dropped_by_name():
    d1 = ('T_Tverskaya_12_001_Main_d_1.png', png(1024, 1024))
    uv = full_square_islands([1, 2])
    found, dropped = core.textures_scene([slot_row(1, 'SM_Tverskaya_12_001_Main', {1: [d1], 2: []}, NPM_FBX, uv)])
    assert codes(found[1]) == ['tex_missing'] and 'matID 2' in found[1][0][1]  # a sub-material without maps
    assert [d['name'] for d in dropped] == ['SM_Tverskaya_12_001_Main'] and 'matID 2' in dropped[0]['reason']


# --- pivot ----------------------------------------------------------------------------------------------
def piv(key, name, p, fbx=VPM_FBX):
    return {'key': key, 'name': name, 'fbx': fbx, 'pivot': p}


def test_pivot_rules():
    found, dropped = core.pivot_findings([piv(1, 'SM_T_Main', (0, 0, 0)), piv(2, 'SM_T_MainGlass', (0, 0, 0)),
                                          piv(3, 'UCX_SM_T_Main_001', (5, 5, 5))])
    assert found == {1: [], 2: [], 3: []} and dropped[0]['name'] == 'UCX_SM_T_Main_001'
    found, _ = core.pivot_findings([piv(1, 'SM_T_Main', (0, 0, 0.5)), piv(2, 'SM_T_MainGlass', (3, 0, 0.5))])
    assert codes(found[1]) == ['pivot_z'] and codes(found[2]) == ['pivot_mismatch', 'pivot_z']
    found, _ = core.pivot_findings([piv(1, 'SM_T_Main', (0, 0, 0.001)), piv(2, 'SM_T_MainGlass', (0.001, 0, 0.001))])
    assert codes(found[1]) == ['at_threshold'] and codes(found[2]) == ['at_threshold']
    for bad in (None, (0, 0), (0, 0, float('nan')), (0, 0, float('inf')), (0, True, 0)):
        assert codes(core.pivot_findings([piv(1, 'SM_T_Main', bad)])[0][1]) == ['pivot_unmeasurable']
    _, dropped = core.pivot_findings([piv(1, 'SM_T_001_Main', (0, 0, 9), NPM_FBX)])
    assert dropped[0]['reason'].startswith('NPM FBX')
    assert codes(core.pivot_findings([piv(1, 'SM_T_Main', (0, 0, 0), 'x.fbx')])[0][1]) == ['fbx_unmapped']


def test_pivot_probe_per_fbx_groups():
    """Probe: pivots in different FBX never compare with each other; 0.9 mm passes, 1.1 mm fails."""
    import random
    rnd = random.Random(5)
    for _ in range(100):
        off = rnd.choice((0.0009, 0.0011))
        rows = [piv(1, 'SM_A_Main', (0, 0, 0), 'C:/o/SM_A.fbx'), piv(2, 'SM_B_Main', (50, 50, 0), 'C:/o/SM_B.fbx'),
                piv(3, 'SM_A_MainGlass', (off, 0, 0), 'C:/o/SM_A.fbx')]
        found, _ = core.pivot_findings(rows)
        assert found[2] == [] and codes(found[3]) == ([] if off < 0.001 else ['pivot_mismatch'])


def _flagged(rows):
    found, _ = core.pivot_findings(rows)
    return {r['name'] for r in rows if any(c[0] == 'pivot_mismatch' for c in found[r['key']])}


def test_pivot_verdict_is_order_independent():
    """#821: the reference is the Main/Ground object, never the first member; reversal gives the same set."""
    import itertools
    cases = [
        ([('Main', 0), ('A', 0), ('B', 0)], set()),
        ([('Odd', 0.5), ('Main', 0), ('A', 0)], {'Odd'}),
        ([('Main', 0), ('A', 0.0005)], set()),
        ([('SM_T_Ground', 0), ('A', 2)], {'A'}),
    ]
    for spec, want in cases:
        for perm in itertools.permutations(spec):
            rows = [piv(i, n, (x, 0, 0)) for i, (n, x) in enumerate(perm)]
            assert _flagged(rows) == want, (perm, want)
    # no Main/Ground: pairs more than 1 mm apart are reported, C is named, A/B pair is not
    for perm in itertools.permutations([('A', 0), ('B', 0), ('C', 1)]):
        rows = [piv(i, n, (x, 0, 0)) for i, (n, x) in enumerate(perm)]
        found, _ = core.pivot_findings(rows)
        by = {r['name']: found[r['key']] for r in rows}
        assert _flagged(rows) == {'A', 'B', 'C'}
        assert 'C (' in by['A'][0][1] and 'B (' not in by['A'][0][1] and 'A (' not in by['B'][0][1]


def test_pivot_reference_agreement_is_permutation_independent():
    """#832: a Main/Ground reference is never mismatched against a non-reference; disagreeing
    references produce one pivot_reference_ambiguous on the alphabetically first name; agreeing
    references judge only the other meshes. Every permutation yields the same (name, code) set,
    and the verdict is fail exactly when any finding exists."""
    import itertools
    import random

    counted = [0]

    def drive(spec):
        seen = []
        for perm in itertools.permutations(spec):
            counted[0] += 1
            rows = []
            for i, item in enumerate(perm):
                fbx = item[2] if len(item) > 2 else VPM_FBX
                rows.append(piv(i + 1, item[0], item[1], fbx))
            found, _ = core.pivot_findings(rows)
            full = tuple(sorted((r['name'], item[0], item[1]) for r in rows for item in found[r['key']]))
            verdict = 'fail' if any(found[r['key']] for r in rows) else 'pass'
            assert verdict == ('fail' if full else 'pass')
            seen.append(full)
        assert len(set(seen)) == 1, (spec, seen[:2])
        return seen[0]

    def codes_of(full):
        return tuple(sorted({(name, code) for name, code, _ in full}))

    assert 'pivot_reference_ambiguous' in core.CODES['pivot']
    runtime.parse_report(json.dumps(scene_report(
        'pivot', [{'code': 'pivot_reference_ambiguous', 'ids': [], 'detail': 'refs disagree'}])))

    # 1. Agreeing references: only the odd mesh is a pivot_mismatch.
    full = drive([('SM_A_Main', (0, 0, 0)), ('SM_B_Main', (0, 0, 0)), ('Odd', (0.5, 0, 0))])
    assert full == ((
        'Odd', 'pivot_mismatch',
        f'pivot differs from SM_A_Main (0.500000 m), SM_B_Main (0.500000 m) in {VPM_FBX} (VPM-2.9-5)'),)
    # 2. Disagreeing references: one ambiguous finding, nothing else, verdict fail.
    full = drive([('SM_A_Main', (0, 0, 0)), ('SM_B_Main', (1, 0, 0)), ('A', (0, 0, 0))])
    assert full == ((
        'SM_A_Main', 'pivot_reference_ambiguous',
        f'Main/Ground references disagree in {VPM_FBX}: '
        'SM_A_Main (0,0,0), SM_B_Main (1,0,0) (VPM-2.9-5)'),)
    # 3. One reference, everyone on it: no findings.
    assert drive([('SM_A_Main', (0, 0, 0)), ('A', (0, 0, 0)), ('B', (0, 0, 0))]) == ()
    # 4. One reference and one offset mesh: the same single mismatch as before.
    full = drive([('SM_A_Main', (0, 0, 0)), ('A', (0.5, 0, 0))])
    assert full == ((
        'A', 'pivot_mismatch',
        f'pivot differs from SM_A_Main (0.500000 m) in {VPM_FBX} (VPM-2.9-5)'),)

    # Probe: a reference never takes pivot_mismatch from a generated non-reference offset.
    for dx in (0.0, 0.0004, 0.05, 0.5, 1.0, 2.5):
        full = drive([('SM_A_Main', (0, 0, 0)), ('SM_B_Main', (0, 0, 0)), ('Odd', (dx, 0, 0))])
        assert not any(code == 'pivot_mismatch' and name in ('SM_A_Main', 'SM_B_Main')
                       for name, code, _ in full)
        far = dx > core.PIVOT_TOL_M and not math.isclose(dx, core.PIVOT_TOL_M, rel_tol=1e-9, abs_tol=0.0)
        assert codes_of(full) == ((('Odd', 'pivot_mismatch'),) if far else ())
        if far:
            detail = full[0][2]
            assert detail.startswith('pivot differs from SM_A_Main (') and 'SM_B_Main (' in detail
            assert 'Odd (' not in detail

    # Probe: any reference pair beyond 1 mm -> one ambiguous finding, zero mismatches.
    for dx, shown in ((0.0011, '(0.0011,0,0)'), (0.01, '(0.01,0,0)'), (0.2, '(0.2,0,0)'),
                      (1.0, '(1,0,0)'), (4.0, '(4,0,0)')):
        full = drive([('SM_A_Main', (0, 0, 0)), ('SM_B_Main', (dx, 0, 0)), ('A', (0, 0, 0))])
        assert codes_of(full) == (('SM_A_Main', 'pivot_reference_ambiguous'),)
        assert full[0][2] == (
            f'Main/Ground references disagree in {VPM_FBX}: SM_A_Main (0,0,0), SM_B_Main {shown} (VPM-2.9-5)')
    full = drive([('SM_A_Main', (0, 0, 0)), ('SM_B_Ground', (0, 0, 0)),
                  ('SM_C_Main', (2, 0, 0)), ('A', (5, 0, 0))])
    assert codes_of(full) == (('SM_A_Main', 'pivot_reference_ambiguous'),)
    assert full[0][2] == (
        f'Main/Ground references disagree in {VPM_FBX}: '
        'SM_A_Main (0,0,0), SM_B_Ground (0,0,0), SM_C_Main (2,0,0) (VPM-2.9-5)')

    # Probe: references within 1 mm; each non-reference is judged against every reference.
    near = (('SM_A_Main', (0, 0, 0)), ('SM_B_Main', (0.0003, 0, 0)))
    for pos in ((0, 0, 0), (0.0005, 0, 0), (0.02, 0, 0), (0.5, 0.5, 0), (-1, 0.2, 0)):
        full = drive([*near, ('Odd', pos)])
        distances = [math.dist(pos, ref[1]) for ref in near]
        bad = [ref for ref, dist in zip(near, distances)
               if dist > core.PIVOT_TOL_M and not math.isclose(dist, core.PIVOT_TOL_M, rel_tol=1e-9, abs_tol=0.0)]
        edge = [ref for ref, dist in zip(near, distances)
                if math.isclose(dist, core.PIVOT_TOL_M, rel_tol=1e-9, abs_tol=0.0)]
        expect = []
        if edge:
            expect.append(('Odd', 'at_threshold'))
        if bad:
            expect.append(('Odd', 'pivot_mismatch'))
        assert codes_of(full) == tuple(sorted(expect))
        assert not any(name.startswith('SM_') for name, _, _ in full)
        if bad:
            detail = next(text for _, code, text in full if code == 'pivot_mismatch')
            named = [ref[0] for ref in bad]
            assert all(ref in detail for ref in named)
            assert all(ref not in detail for ref, _ in near if ref not in named)
    full = drive([('SM_A_Main', (0, 0, 0)), ('SM_B_Main', (0.0008, 0, 0)), ('Odd', (0.0015, 0, 0))])
    assert codes_of(full) == (('Odd', 'pivot_mismatch'),)
    assert 'SM_A_Main (' in full[0][2] and 'SM_B_Main (' not in full[0][2]
    full = drive([('SM_A_Main', (0, 0, 0)), ('SM_B_Main', (0, 0, 0)), ('A', (0, 0, 0)), ('B', (0.4, 0, 0))])
    assert full == ((
        'B', 'pivot_mismatch',
        f'pivot differs from SM_A_Main (0.400000 m), SM_B_Main (0.400000 m) in {VPM_FBX} (VPM-2.9-5)'),)

    # Probe: with no Main/Ground reference, every pair is judged (MainGlass is not a reference).
    rnd = random.Random(832)
    for _ in range(8):
        spec = [(name, (rnd.uniform(-2, 2), rnd.uniform(-2, 2), 0.0)) for name in ('A', 'B', 'C')]
        full = drive(spec)
        expect = set()
        pts = dict(spec)
        for i, left in enumerate(('A', 'B', 'C')):
            for right in ('A', 'B', 'C')[i + 1:]:
                dist = math.dist(pts[left], pts[right])
                if math.isclose(dist, core.PIVOT_TOL_M, rel_tol=1e-9, abs_tol=0.0):
                    expect.update({(left, 'at_threshold'), (right, 'at_threshold')})
                elif not math.isfinite(dist) or dist > core.PIVOT_TOL_M:
                    expect.update({(left, 'pivot_mismatch'), (right, 'pivot_mismatch')})
        assert codes_of(full) == tuple(sorted(expect))
    full = drive([('SM_A_MainGlass', (0, 0, 0)), ('SM_B_MainGlass', (1, 0, 0))])
    assert codes_of(full) == (('SM_A_MainGlass', 'pivot_mismatch'), ('SM_B_MainGlass', 'pivot_mismatch'))
    assert 'pivot_reference_ambiguous' not in {code for _, code, _ in full}

    # Probe: exactly 1 mm is at_threshold (a fail), never a pass and never an ambiguous reference.
    full = drive([('SM_A_Main', (0, 0, 0)), ('SM_B_Main', (0.001, 0, 0))])
    assert full == (
        ('SM_A_Main', 'at_threshold', 'pivot 0.001000 m from SM_B_Main: == 0.001 m'),
        ('SM_B_Main', 'at_threshold', 'pivot 0.001000 m from SM_A_Main: == 0.001 m'))
    full = drive([('SM_A_Main', (0, 0, 0)), ('A', (0.001, 0, 0))])
    assert full == (('A', 'at_threshold', 'pivot 0.001000 m from SM_A_Main: == 0.001 m'),)
    full = drive([('SM_A_Main', (0, 0, 0)), ('SM_B_Main', (0.001, 0, 0)), ('SM_C_Main', (1, 0, 0))])
    assert full == (
        ('SM_A_Main', 'at_threshold', 'pivot 0.001000 m from SM_B_Main: == 0.001 m'),
        ('SM_A_Main', 'pivot_reference_ambiguous',
         f'Main/Ground references disagree in {VPM_FBX}: '
         'SM_A_Main (0,0,0), SM_B_Main (0.001,0,0), SM_C_Main (1,0,0) (VPM-2.9-5)'),
        ('SM_B_Main', 'at_threshold', 'pivot 0.001000 m from SM_A_Main: == 0.001 m'))

    # Fail closed: NaN, inf and an empty pivot are errors, never a shared-pivot pass.
    for bad in (float('nan'), float('inf'), float('-inf')):
        full = drive([('SM_A_Main', (0, 0, bad)), ('SM_B_Main', (0, 0, 0)), ('A', (0, 0, 0))])
        assert ('SM_A_Main', 'pivot_unmeasurable') in codes_of(full)
        assert 'pivot_mismatch' not in {code for _, code, _ in full}
    for empty in ((), [], None, (0, 0)):
        full = drive([('SM_A_Main', empty), ('A', (0, 0, 0))])
        assert full == (('SM_A_Main', 'pivot_unmeasurable', f'pivot {empty!r}'),)

    # One finding per FBX group: a far reference in another file is not this group's reference.
    one, two = 'C:/o/SM_One.fbx', 'C:/o/SM_Two.fbx'
    assert drive([('SM_A_Main', (0, 0, 0), one), ('SM_B_Main', (5, 0, 0), two)]) == ()
    full = drive([('SM_A_Main', (0, 0, 0), one), ('SM_B_Main', (1, 0, 0), one),
                  ('SM_C_Main', (0, 0, 0), two), ('SM_D_Main', (2, 0, 0), two)])
    assert full == (
        ('SM_A_Main', 'pivot_reference_ambiguous',
         f'Main/Ground references disagree in {one}: SM_A_Main (0,0,0), SM_B_Main (1,0,0) (VPM-2.9-5)'),
        ('SM_C_Main', 'pivot_reference_ambiguous',
         f'Main/Ground references disagree in {two}: SM_C_Main (0,0,0), SM_D_Main (2,0,0) (VPM-2.9-5)'))

    assert counted[0] == 282, counted[0]
    print('PIVOT_PERMUTATIONS', counted[0])


# --- GeoJSON --------------------------------------------------------------------------------------------
def test_geojson_report_never_raises():
    def boom(_):
        raise RuntimeError('checker crashed')
    for path, runner in ((None, boom), ('', boom), ('a.json', boom), ('C:/x/a.geojson', boom),
                         ('C:/x/a.geojson', lambda p: []), ('C:/x/a.geojson', lambda p: [{'name': 'x'}])):
        r = core.geojson_report(path, runner)
        assert r['status'] == 'fail' and r['objects'] == [] and r['plan']['findings'][0]['status'] == 'fail'
        runtime.parse_report(json.dumps(r))
    ok = core.geojson_report('a.geojson', lambda p: [{'name': 'schema', 'status': 'pass', 'observed': '', 'expected': ''}])
    assert ok['status'] == 'pass'
    review = core.geojson_report('a.geojson', lambda p: [{'name': 's', 'status': 'review', 'observed': '', 'expected': ''}])
    assert review['status'] == 'fail'


def test_geojson_subprocess_code_runs_twinqa(tmp_path):
    import subprocess
    import sys
    broken = tmp_path / 'SM_Tverskaya_12.geojson'
    broken.write_bytes(b'{"type": ')
    proc = subprocess.run([sys.executable, '-c', core.GEOJSON_CODE, str(ROOT), str(broken)], capture_output=True)
    assert proc.returncode == 0, proc.stderr
    got = json.loads(proc.stdout)
    assert got[0]['status'] == 'fail' and got[0]['name'] == 'JSON'
    report = core.geojson_report(str(broken), lambda p: got)
    assert report['status'] == 'fail'


# --- report contract and read-only glue -----------------------------------------------------------------
def scene_report(tool, findings):
    return {'schema': 1, 'tool': tool, 'status': 'fail' if findings else 'pass',
            'objects': [{'handle': 7, 'name': 'SM_A_Main', 'findings': findings}],
            'plan': {'fbx': [{'fbx': VPM_FBX, 'model': 'vpm', 'role': 'oks', 'objects': 1, 'render_triangles': None,
                              'ucx_triangles': None, 'limit': None, 'ucx_limit': None}], 'dropped': []}}


@pytest.mark.parametrize('tool,code', [('names', 'name_suffix'), ('tris', 'tri_limit'), ('textures', 'tex_padding'),
                                       ('pivot', 'pivot_z')])
def test_parse_report_accepts_new_tools(tool, code):
    runtime.parse_report(json.dumps(scene_report(tool, [{'code': code, 'ids': [], 'detail': 'x'}])))
    runtime.parse_report(json.dumps(scene_report(tool, [])))


@pytest.mark.parametrize('mutate', [
    lambda r: r.update(status='pass'),
    lambda r: r['objects'][0]['findings'][0].update(code='xview_overlap'),
    lambda r: r.pop('plan'),
    lambda r: r['plan']['fbx'][0].update(model='ipm'),
    lambda r: r['plan']['dropped'].append({'name': 'a', 'reason': ''}),
    lambda r: r.update(objects=[]),
])
def test_parse_report_rejects_broken_new_reports(mutate):
    r = scene_report('names', [{'code': 'name_suffix', 'ids': [], 'detail': 'x'}])
    mutate(r)
    with pytest.raises(ValueError):
        runtime.parse_report(json.dumps(r))


def test_d6_glue_never_edits_the_scene():
    """D6: GeoAGR Prepare LowPoly/HighPoly (GeoAGR.ms:65533-65547) DeleteIso, ResetXForm and collapse."""
    import ast
    tree = ast.parse((PKG / 'checks_max.py').read_text(encoding='utf-8'))
    for node in ast.walk(tree):  # drop docstrings: they name the forbidden calls on purpose
        body = getattr(node, 'body', None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            node.body = body[1:] or [ast.Pass()]
    code = ast.unparse(tree)
    for call in ('ResetXForm', 'resetXForm', 'collapseStack', 'convertTo', 'convertToPoly', 'DeleteIso',
                 'rt.copy', 'addModifier', '.pivot =', 'setUserProp', 'saveMaxFile', 'ConnectVertices'):
        assert call not in code, call


def test_buttons_registered_in_rollout_and_package():
    mcr = (PKG / 'agr_tools.mcr').read_text(encoding='utf-8')
    for label, tool in (('Names check NPM/VPM', 'names'), ('Triangle limits per FBX', 'tris'),
                        ('Textures check (all objects)', 'textures'), ('Pivot check', 'pivot'),
                        ('GeoJSON check', 'geojson')):
        assert f'"{label}"' in mcr and f"ui('{tool}')" in mcr
    assert 'VERSION = "0.5.0"' in (PKG / 'runtime.py').read_text(encoding='utf-8')
    assert 'version=0.5.0' in (PKG / 'startup.ms').read_text(encoding='utf-8')
    install = (PKG / 'install.ms').read_text(encoding='utf-8')
    assert 'AGRTools-0.5.0' in install and '"checks_core.py", "checks_max.py"' in install
    assert (PKG / 'mzp.run').read_text(encoding='utf-8').splitlines()[1] == 'version 0.5'


def test_mzp_ships_the_new_cores(tmp_path):
    import zipfile
    builder = _load('../../../tools/max/build_agr_tools.py', 'agr_builder_checks')
    out = tmp_path / 'AGR-Tools-0.5.0.mzp'
    builder.build(out)
    with zipfile.ZipFile(out) as z:
        names = set(z.namelist())
    assert {'agr_tools/checks_core.py', 'agr_tools/checks_max.py', 'agr_tools/CHANGELOG.md'} <= names


def test_math_is_finite_guard():
    assert math.isfinite(core.vpm_ucx_limit(10 ** 9))


def test_tri_limits_probe_per_fbx_invariant():
    """Probe: for random scenes over 4 FBX, every render object's finding is exactly the comparison of
    ITS FBX sum with ITS FBX limit; no object is missing from the output; UCX never adds to render."""
    import random
    rnd = random.Random(804)
    fbxs = {'C:/o/0001_A_01.fbx': 150000, 'C:/o/0001_A_02.fbx': 150000, 'C:/o/0001_A_Ground.fbx': 180000,
            'C:/o/SM_A.fbx': 1000000}
    checked = 0
    for _ in range(300):
        rows = []
        for k in range(rnd.randint(1, 8)):
            fbx = rnd.choice(sorted(fbxs))
            ucx = fbx.endswith('SM_A.fbx') and rnd.random() < 0.3
            name = 'UCX_SM_A_Main_%03d' % (k + 1) if ucx else 'SM_A_%d_Main' % k
            rows.append(row(k + 1, name, fbx, rnd.choice((0, 1, 74999, 75000, 75001, 150000, 600000))))
        found, table = core.triangle_limits(rows)
        assert set(found) == {r['key'] for r in rows}
        for r in rows:
            if r['name'].startswith('UCX_'):
                continue
            total = sum(x['triangles'] for x in rows if x['fbx'] == r['fbx'] and not x['name'].startswith('UCX_'))
            lim = fbxs[r['fbx']]
            want = ['tri_limit'] if total > lim else ['tri_at_limit'] if total == lim else []
            assert codes(found[r['key']]) == want, (rows, r)
            checked += 1
        assert sum(t['objects'] for t in table) == len(rows)
    assert checked > 500


def test_slot_number_probe():
    """Probe: every M/T SlotNumber 1..7 is legal and every other last token is `name_suffix`."""
    for tok in [str(i) for i in range(0, 12)] + ['01', '07', 'a', '1a', '']:
        for name, role in ((f'M_Addr_001_Main_{tok}', 'M'), (f'T_Addr_001_Main_d_{tok}', 'T')):
            got = codes(core.name_findings(name, role, 'npm'))
            if tok in core.SLOTS:
                assert 'name_suffix' not in got, name
            else:
                assert got and ('name_suffix' in got or 'name_separator' in got), (name, got)


def test_checks_050_works_when_loaded_like_bootstrap():
    """Native Max 2024 r1: the macro path raised KeyError 'agr_tools_runtime' because bootstrap.py
    loads runtime.py with module_from_spec and never registers it in sys.modules."""
    import sys
    spec = importlib.util.spec_from_file_location('agr_tools_runtime_unregistered', PKG / 'runtime.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert 'agr_tools_runtime_unregistered' not in sys.modules
    seen = {}

    class Glue:
        @staticmethod
        def run(agr, checks, tool, nodes, path):
            seen['agr'] = agr
            return {'tool': tool}

    mod._load_core = lambda name, module: Glue if name == 'checks_max.py' else core
    assert mod.checks_050('pivot', ['n'], None) == {'tool': 'pivot'}
    assert seen['agr']._prop is mod._prop and seen['agr']._report is mod._report


def test_padding_per_atlas_bruteforce_probe():
    """Probe (review r1 invariant): an object fails padding iff one of its squares is closer than
    8 px (NPM, 1024) to another square OF THE SAME ATLAS AND FBX, whatever object or slot holds it."""
    import random
    rnd = random.Random(8040)
    atlas = {a: (f'T_P_Main_d_{a}.png', png(1024, 1024)) for a in (1, 2)}
    fbxs = (NPM_FBX, 'C:/o/0001_Tverskaya_12_02.fbx')
    for _ in range(300):
        rows, squares = [], []  # squares: (key, fbx, atlas, x0)
        for key in range(1, rnd.randint(2, 4)):
            fbx = rnd.choice(fbxs)
            slots = {mid: [atlas[a]] for mid, a in enumerate(rnd.sample((1, 2), rnd.randint(1, 2)), start=1)}
            uvs, faces = [], []
            for k in range(rnd.randint(1, 2)):
                mid = rnd.choice(list(slots))
                x0 = rnd.choice((0.0, 0.25, 0.5, 0.75)) + rnd.choice((0.0, 4, 9)) / 1024
                b = len(uvs)
                uvs += [(x0, 0.0), (x0 + 0.2, 0.0), (x0 + 0.2, 0.2), (x0, 0.2)]
                faces += [(2 * k + 1, [b, b + 1, b + 2], mid), (2 * k + 2, [b, b + 2, b + 3], mid)]
                squares.append((key, fbx, int(slots[mid][0][0][-5]), x0))
            rows.append(slot_row(key, f'SM_P_{key:03d}_Main', slots, fbx, (uvs, faces)))
        found, _ = core.textures_scene(rows)
        for key in {r['key'] for r in rows}:
            mine = [s for s in squares if s[0] == key]
            bad = any(s is not t and s[1:3] == t[1:3] and max(abs(s[3] - t[3]) - 0.2, 0.0) * 1024 < 8
                      for s in mine for t in squares)
            assert codes(found[key]) == (['tex_padding'] if bad else []), (key, squares)


class _Seq(list):
    @property
    def count(self):
        return len(self)


def _fake_mm(ids, maps_per_sub):
    import types
    rt = types.SimpleNamespace(undefined=object(), Multimaterial=object())
    rt.classOf = lambda m: rt.Multimaterial
    subs = [types.SimpleNamespace(maps=_Seq(p)) for p in maps_per_sub]
    rt.usedMaps = lambda s: s.maps
    mm = types.SimpleNamespace(materialIDList=_Seq(ids), materialList=_Seq(subs))
    return rt, types.SimpleNamespace(material=mm)


def _slots_to_findings(ids, maps_per_sub):
    cm = _load('checks_max.py', 'agr_checks_max_dup_test')
    rt, node = _fake_mm(ids, maps_per_sub)
    cm._rt = lambda: rt
    slots = cm._slots(node)
    d1 = ('T_Tverskaya_12_001_Main_d_1.png', png(1024, 1024))
    d2 = ('T_Tverskaya_12_001_Main_d_2.png', png(1024, 1024))
    row = slot_row(1, 'SM_Tverskaya_12_001_Main', {}, NPM_FBX, full_square_islands([2]))
    row['slots'], row['maps'] = slots, [d1, d2]
    return slots, core.textures_scene([row])


def test_duplicate_matid_in_list_is_one_named_finding():
    """RED: last-wins kept only the second sub-material's maps and reported nothing."""
    slots, (found, _) = _slots_to_findings([1, 1], [['T_Tverskaya_12_001_Main_d_1.png'],
                                                    ['T_Tverskaya_12_001_Main_d_2.png']])
    assert slots == {1: None}
    assert codes(found[1]) == ['tex_unmeasurable'] and 'matID 1' in found[1][0][1]


def test_distinct_matids_keep_both_slots_without_ambiguity():
    slots, (found, _) = _slots_to_findings([1, 2], [['T_Tverskaya_12_001_Main_d_1.png'],
                                                    ['T_Tverskaya_12_001_Main_d_2.png']])
    assert slots == {1: ['T_Tverskaya_12_001_Main_d_1.png'], 2: ['T_Tverskaya_12_001_Main_d_2.png']}
    assert 'tex_unmeasurable' not in codes(found[1])


def test_duplicate_matid_does_not_hide_the_other_slot():
    m = ['T_Tverskaya_12_001_Main_d_1.png']
    slots, (found, _) = _slots_to_findings([1, 1, 2], [m, m, ['T_Tverskaya_12_001_Main_d_2.png']])
    assert slots[1] is None and slots[2] == ['T_Tverskaya_12_001_Main_d_2.png']
    unm = [x for x in found[1] if x[0] == 'tex_unmeasurable']
    assert len(unm) == 1 and 'matID 1' in unm[0][1]


def _wrap_row(id_list, mat_ids, slots, gapped=False):
    uv = full_square_islands(mat_ids)
    if gapped:  # two islands of the same slot 0.001 apart: a padding finding with a value
        u, f = full_square_islands(mat_ids * 2, s=0.4)
        u = [(x + (0.401 if i >= 4 else 0.0), y) for i, (x, y) in enumerate(u)]
        uv = (u, f)
    row = slot_row(1, 'SM_Tverskaya_12_001_Main', slots, NPM_FBX, uv)
    row['id_list'] = id_list
    return row


_D1 = ('T_Tverskaya_12_001_Main_d_1.png', png(1024, 1024))
_D2 = ('T_Tverskaya_12_001_Main_d_2.png', png(1024, 1024))


def test_wrap_to_duplicated_matid_is_unmeasurable_not_wrapped():
    """RED: matID 3 wrapped to the unique key set {1, 2} (-> sub 1) and was measured."""
    found, _ = core.textures_scene([_wrap_row([1, 1, 2], [3], {1: None, 2: [_D2]})])
    assert 'tex_matid_wrapped' not in codes(found[1])
    unm = [x[1] for x in found[1] if x[0] == 'tex_unmeasurable' and 'face matID 3' in x[1]]
    assert len(unm) == 1


def test_wrap_without_duplicate_unchanged():
    found, _ = core.textures_scene([_wrap_row([1, 2], [3], {1: [_D1], 2: [_D2]})])
    w = [x[1] for x in found[1] if x[0] == 'tex_matid_wrapped']
    assert len(w) == 1 and '-> sub 1 (matID 1)' in w[0] and 'materialIDList [1, 2]' in w[0]


def test_unique_matid_next_to_duplicate_is_measured():
    """P3 of #848: slot 2 of [1, 1, 2] is measured (its padding is reported)."""
    found, _ = core.textures_scene([_wrap_row([1, 1, 2], [2], {1: None, 2: [_D2]}, gapped=True)])
    pad = [x for x in found[1] if x[0] == 'tex_padding']
    assert pad and any(ch.isdigit() for ch in pad[0][1])


def test_wrapped_message_prints_list_as_given():
    found, _ = core.textures_scene([_wrap_row([2, 1, 2, 5], [6], {2: None, 1: [_D1], 5: [_D2]})])
    w = [x[1] for x in found[1] if x[0] == 'tex_matid_wrapped']
    assert w and 'materialIDList [2, 1, 2, 5]' in w[0] and '[1, 2, 5]' not in w[0]
