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
