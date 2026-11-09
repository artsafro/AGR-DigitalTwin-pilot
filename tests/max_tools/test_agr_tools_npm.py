"""new-case: #1024 branch P - npm.build (1.0.22) and atlas.facade_strip (1.0.23) cores, without Max.

Every named defect of lab L11 (docs/experiments/npm.build.md) and of the pilot run-strip notes has a regression
test: RED on a model of the source behaviour (GeoAGR Priority atlas, cited as GeoAGR.ms:<line> only, #853) and
GREEN on the AGR implementation (npm_core / facadeatlas_core / atlas_core).
"""
import importlib.util
import json
import math
import os
import random
from pathlib import Path
import types

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / 'adapters' / 'max' / 'agr_tools'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


npm = load(TOOLS / 'npm_core.py', 'p_npm_core')
fac = load(TOOLS / 'facadeatlas_core.py', 'p_facadeatlas_core')
ac = npm.atlas
vpm = load(TOOLS / 'vpm_core.py', 'p_vpm_core')
MB = load(ROOT / 'test-polygon' / 'stations' / 'M_build.py', 'p_m_build')
PB = load(ROOT / 'test-polygon' / 'stations' / 'P_build.py', 'p_p_build')
texqa = load(TOOLS / 'texqa_core.py', 'p_texqa_core')
edit = load(TOOLS / 'edit_core.py', 'p_edit_core')

PANEL, BRICK, GLASS = 3, 7, 31


def coord_map(w, h, seed=None):
    """Map whose pixel encodes its own coordinate: R = x, G = y (w, h <= 256), B = parity checker."""
    rgb = bytearray()
    for y in range(h):
        for x in range(w):
            rgb += bytes((x, y, 255 if (x + y) % 2 else 0))
    return {'w': w, 'h': h, 'rgb': bytes(rgb), 'alpha': None}


def flat_map(w, h, c):
    return {'w': w, 'h': h, 'rgb': bytes(c) * (w * h), 'alpha': None}


def vpm_meshes(maps=None):
    """Body + glass VPM meshes of the L09 small facade through vpm_core (branch M): K6 pieces in UDIM 1001/1002."""
    meshes = PB.vpm_meshes()
    mats = maps or {PANEL: {'name': 'M_Panel', 'map': 'panel.png'}, BRICK: {'name': 'M_Brick', 'map': 'brick.png'},
                    GLASS: {'name': 'M_Glass', 'color': [70, 90, 110]}}
    for m in meshes:
        m['materials'] = {k: v for k, v in mats.items() if k in set(m['mat_ids'])}
    return meshes


HEADERS = {'panel.png': {'w': 64, 'h': 64}, 'brick.png': {'w': 64, 'h': 64}}
OPTS = {'glass_ids': [GLASS], 'udim_table': {'3': 1001, '7': 1002}}


def back_of(p):
    return {'verts': p['combined']['verts'], 'tris': p['combined']['tris'], 'mat_ids': p['combined']['mat_ids'],
            'uvs': p['uvs'], 'uv_tris': p['uv_tris']}


# ---- source behaviour models (GeoAGR Priority atlas, lab L11 measurements) ------------------------------------
def geoagr_priority_tile_px(_map_px):
    """GeoAGR.ms:27440 / :27298-27324: every prepareTile input is a 256 x 256 render, whatever the map."""
    return 256


def geoagr_group_texel(meshes, mid, px=256):
    """GeoAGR.ms:27531-27536: TD from the root of the WHOLE group UV area; stacked K6 pieces count once per
    piece, so the density is too high by the stack height (lab: 358 / 234 / 83 / 36 px/m)."""
    uv_a = geo_a = 0.0
    for m in meshes:
        for f, i in enumerate(m['mat_ids']):
            if i != mid:
                continue
            q = [m['uvs'][t] for t in m['uv_tris'][f]]
            uv_a += npm._tri_area2(*q)
            geo_a += npm._tri_area3(*[m['verts'][v] for v in m['tris'][f]])
    us = [m['uvs'][t][0] for m in meshes for f, i in enumerate(m['mat_ids']) if i == mid for t in m['uv_tris'][f]]
    vs = [m['uvs'][t][1] for m in meshes for f, i in enumerate(m['mat_ids']) if i == mid for t in m['uv_tris'][f]]
    bbox = (max(us) - min(us)) * (max(vs) - min(vs))
    return px * math.sqrt(bbox / geo_a) * math.sqrt(bbox) / max(math.sqrt(uv_a), 1e-12)


def geoagr_fill_one_tile(uv_box):
    """prepareTile (GeoAGR.ms:27097-27126, author comment :27096): only the first 0..1 tile is filled; the share of
    an island over 1 UV that stays empty."""
    u0, v0, u1, v1 = uv_box
    area = (u1 - u0) * (v1 - v0)
    filled = min(u1 - u0, 1.0) * min(v1 - v0, 1.0)
    return 1.0 - filled / area


def geoagr_tile_of_bbox_centre(uv_box):
    """Lab L11 prototype / UnAtlas rule: tile of the UV bbox centre (gave 1019 instead of 1007)."""
    return npm.tile_of((uv_box[0] + uv_box[2]) / 2, (uv_box[1] + uv_box[3]) / 2)


# ---- npm.build ----------------------------------------------------------------------------------------------
def test_plan_on_vpm_of_branch_m_passes_and_table_is_complete():
    p = npm.plan(vpm_meshes(), OPTS, HEADERS)
    assert p['findings'] == []
    assert p['summary']['atlas_px'] <= 2048 and p['summary']['texel_px_per_m'] == 39.0
    rows = {r['library_id']: r for r in p['table']}  # one row per island; the last island of each ID
    assert sorted(rows) == [PANEL, BRICK, GLASS]
    assert rows[PANEL]['udim'] == 1001 and rows[BRICK]['udim'] == 1002 and rows[PANEL]['udim_source'] == 'vpm_table'
    assert rows[GLASS]['kind'] == 'glass' and rows[GLASS]['part'] == 'glass' and rows[GLASS]['udim'] == 1001
    for r in rows.values():
        assert set(r) >= {'library_id', 'udim', 'region', 'scale', 'shift', 'material', 'map', 'cell_px',
                          'atlas_px', 'texel_px_per_m'}
        assert r['scale'][0] == pytest.approx(r['scale'][1])


def test_npm_islands_pass_the_npm_padding_rule_stack_does_not():
    """tex.check of an NPM (checks_core.padding_findings, 8 px, overlap is tex_padding outside the VPM): the
    default layout 'islands' gives no finding; the L11 prototype layout 'stack' keeps the K6 pieces stacked in
    one cell and fails it - the conflict lab L11 / acceptance 1.0.22 is a parameter (owner question)."""
    ck = load(TOOLS / 'checks_core.py', 'p_checks_core')
    for layout, want in (('islands', set()), ('stack', {'tex_padding'})):
        p = npm.plan(vpm_meshes(), dict(OPTS, layout=layout), HEADERS)
        faces = [(f + 1, t) for f, t in enumerate(p['uv_tris'])]
        got = ck.padding_findings([tuple(u) for u in p['uvs']], faces, p['atlas']['size'], 8)
        assert {g[0] for g in got} == want, (layout, got[:2])
        _f, m = npm.measure(back_of(p), p)
        assert all(abs(t / 39.0 - 1) <= 0.01 for t in m['texel_px_per_m'].values()) and m['rigid_max_uv'] < 1e-12


def test_defect_texel_by_group_area_red_green():
    """Defect 2: GeoAGR texel by the root of the group area differs between IDs (x10); AGR: one target +-1 %."""
    meshes = vpm_meshes()
    model = [geoagr_group_texel(meshes, mid) for mid in (PANEL, BRICK)]
    assert abs(model[0] / model[1] - 1) > 0.01 or abs(model[0] / 39.0 - 1) > 0.01  # RED: not the target
    p = npm.plan(meshes, OPTS, HEADERS)
    findings, measured = npm.measure(back_of(p), p)
    assert findings == []
    for t in measured['texel_px_per_m'].values():
        assert abs(t / 39.0 - 1) <= 0.01
    p2 = npm.plan(meshes, dict(OPTS, texel_px_per_m=20.0), HEADERS)
    _f, m2 = npm.measure(back_of(p2), p2)
    assert all(abs(t / 20.0 - 1) <= 0.01 for t in m2['texel_px_per_m'].values())


def test_defect_256px_render_tiles_red_green():
    """Defect 1: GeoAGR Priority cells come from 256 px renders; AGR cells sample the full-resolution map."""
    assert geoagr_priority_tile_px(1024) != 1024  # RED
    groups = [{'key': '3', 'kind': 'texture', 'uv_box': [0.0, 0.0, 1.0, 1.0], 'm_per_uv': [3.6, 3.6]}]
    lay = ac.rigid_plan(groups, 39.0)
    img = ac.rigid_raster(lay, groups, {'3': coord_map(200, 180)})
    assert img['sources'] == {'3': [200, 180]}  # GREEN: input size = source size


def test_defect_island_over_one_uv_empty_red_green():
    """Defect 3: an island 3 x 2.5 UV - GeoAGR leaves 87 % empty (or stretches the edges); AGR repeats the map over
    the real extent, every pixel of the cell is texture (no background)."""
    box = [0.0, 0.0, 3.0, 2.5]
    assert geoagr_fill_one_tile(box) > 0.8  # RED
    groups = [{'key': '7', 'kind': 'texture', 'uv_box': box, 'm_per_uv': [1.0, 1.0]}]
    lay = ac.rigid_plan(groups, 40.0)
    img = ac.rigid_raster(lay, groups, {'7': flat_map(32, 32, (10, 200, 30))})
    x, y, w, h = lay['cells']['7']['outer']
    size = img['size']
    for yy in range(y, y + h):
        row = img['rgb'][(yy * size + x) * 3:(yy * size + x + w) * 3]
        assert row == bytes((10, 200, 30)) * w
    assert lay['cells']['7']['inner'][2:] == [120, 100]  # 3 x 2.5 UV at 40 px per UV, not squeezed into 1 UV


def test_texture_follows_uv_within_quarter_pixel():
    """Acceptance 3: the jumps of a coordinate-encoded map land where the UV says (<= 0.25 px). Integer scale 2:
    every atlas pixel is one source pixel of the periodic map shifted by the group's fractional start."""
    w = h = 16
    groups = [{'key': '2', 'kind': 'texture', 'uv_box': [0.375, -0.5, 2.125, 0.75], 'm_per_uv': [1.0, 1.0]}]
    lay = ac.rigid_plan(groups, 2.0 * w)  # 32 px per UV = 2 atlas px per source px
    cell = lay['cells']['2']
    img = ac.rigid_raster(lay, groups, {'2': coord_map(w, h)})
    size = img['size']
    worst = 0.0
    for X in range(cell['outer'][2]):
        for Y in range(cell['outer'][3]):
            ax, ay = cell['outer'][0] + X + 0.5, cell['outer'][1] + Y + 0.5
            u = (ax / size - cell['shift'][0]) / cell['scale'][0]
            v = ((1 - ay / size) - cell['shift'][1]) / cell['scale'][1]
            sx, sy = (u * w) % w, (-v * h) % h
            got = img['rgb'][(int(ay) * size + int(ax)) * 3:(int(ay) * size + int(ax)) * 3 + 2]
            worst = max(worst, min(abs(got[0] - sx + 0.5), w - abs(got[0] - sx + 0.5)))
            worst = max(worst, min(abs(got[1] - sy + 0.5), h - abs(got[1] - sy + 0.5)))
    assert worst <= 0.25 + 1e-9


def test_defect_colours_change_red_green():
    """Defect 7: GeoAGR Priority changes colours (128 -> 102, 120 -> 182); AGR keeps flat maps and plugs exact."""
    model = {128: 102, 120: 182}
    assert any(k != v for k, v in model.items())  # RED (measured in Max 2026, lab L11)
    groups = [{'key': '1', 'kind': 'texture', 'uv_box': [0.2, 0.1, 1.7, 1.3], 'm_per_uv': [2.0, 2.0]},
              {'key': '4', 'kind': 'plug', 'uv_box': [0.0, 0.0, 0.5, 0.5], 'color': [120, 128, 7]}]
    lay = ac.rigid_plan(groups, 37.3)
    img = ac.rigid_raster(lay, groups, {'1': flat_map(48, 40, (128, 120, 255))})
    for key, c in (('1', (128, 120, 255)), ('4', (120, 128, 7))):
        x, y, w, h = lay['cells'][key]['outer']
        for yy in range(y, y + h):
            assert img['rgb'][(yy * img['size'] + x) * 3:(yy * img['size'] + x + w) * 3] == bytes(c) * w


def test_defect_glass_diffuse_cell_red_green():
    """Defect 6: GeoAGR glass is a diffuse-colour cell (transparency lost); AGR: a white cell, faces in the NPM."""
    p = npm.plan(vpm_meshes(), OPTS, HEADERS)
    glass = [g for g in p['groups'] if g['library_id'] == GLASS][0]
    assert glass['color'] == [70, 90, 110]  # RED: the source colour GeoAGR would paint
    img = ac.rigid_raster(p['atlas'], p['groups'], {'3': coord_map(64, 64), '7': coord_map(64, 64)})
    gf = p['combined']['mat_ids'].index(GLASS)
    x, y, w, h = p['atlas']['cells'][p['face_key'][gf]]['outer']
    o = (y * img['size'] + x) * 3
    assert img['rgb'][o:o + 3] == bytes(ac.GLASS_RGB)  # GREEN
    assert p['summary']['kinds']['glass'] == 1
    assert sum(1 for part in p['combined']['part'] if part == 'glass') == sum(
        1 for i in p['combined']['mat_ids'] if i == GLASS)


def test_defect_missing_map_black_atlas_red_green():
    """Defect 9: GeoAGR never checks exit codes - a missing EXE / map gives a black 128 px atlas; AGR refuses."""
    p = npm.plan(vpm_meshes(), OPTS, {'panel.png': {'w': 64, 'h': 64}, 'brick.png': {'error': 'not found'}})
    assert [c for c, _f, _d in p['findings']] == ['map_missing']
    assert p['atlas'] is None and p['uvs'] is None and p['table'] is None


def test_defect_plug_path_red_green():
    """Defect 8: GeoAGR checks plugs at `Tile_C:\\...` (:27638) and fails; AGR plugs need no file at all."""
    assert 'Tile_' + 'C:\\x.png' != 'C:\\x.png'  # RED: the path the source builds is not a file name
    meshes = vpm_meshes({PANEL: {'name': 'P', 'color': [1, 2, 3]}, BRICK: {'name': 'B', 'color': [4, 5, 6]},
                         GLASS: {'name': 'G', 'color': [0, 0, 0]}})
    p = npm.plan(meshes, OPTS, {})
    assert p['findings'] == [] and p['summary']['kinds'] == {'texture': 0, 'plug': 2, 'glass': 1}
    img = ac.rigid_raster(p['atlas'], p['groups'], {})
    x, y, _w, _h = p['atlas']['cells'][p['face_key'][p['combined']['mat_ids'].index(PANEL)]]['outer']
    assert img['rgb'][(y * img['size'] + x) * 3:(y * img['size'] + x) * 3 + 3] == bytes((1, 2, 3))


def test_source_udim_from_table_not_uv_centre():
    """L11: the source UDIM comes from the VPM table / passport; the bbox centre of an island across tiles gave
    1019 instead of 1007. Without a table: the tile holding most of the area (reported as such)."""
    box = [6.2, 0.1, 9.9, 1.9]  # crosses tiles 1007..1010 and 1017..1020
    assert geoagr_tile_of_bbox_centre(box) != 1007  # RED
    verts = [[0, 0, 0], [3.7, 0, 0], [3.7, 0, 1.8], [0, 0, 1.8], [3.7, 0, 0.05], [0.05, 0, 0.05]]
    uvs = [[6.2, 0.1], [9.9, 0.1], [9.9, 1.9], [6.2, 1.9], [6.95, 0.15], [6.25, 0.15]]
    m = {'key': 1, 'name': 'SM_X_Main', 'part': 'body', 'verts': verts, 'tris': [[0, 1, 2], [0, 2, 3]],
         'mat_ids': [5, 5], 'uvs': uvs, 'uv_tris': [[0, 1, 2], [0, 2, 3]], 'materials': {5: {'map': 'a.png'}}}
    with_table = npm.plan([m], {'udim_table': {'5': 1007}}, {'a.png': {'w': 32, 'h': 32}})
    assert with_table['table'][0]['udim'] == 1007 and with_table['table'][0]['udim_source'] == 'vpm_table'
    without = npm.plan([m], {}, {'a.png': {'w': 32, 'h': 32}})
    assert without['table'][0]['udim_source'] == 'uv_area_majority'


def test_rigid_transfer_keeps_k6_seam_and_table_returns_vpm_uv():
    """K6 seam 0: one scale + one shift per ID, so every UV difference inside a group scales uniformly; the
    table returns the VPM UV exactly (npm.to_vpm, lab L11: <= 3e-6)."""
    p = npm.plan(vpm_meshes(), OPTS, HEADERS)
    rows = {r['key']: r for r in p['table']}
    cm = p['combined']
    worst = 0.0
    for f, mid in enumerate(cm['mat_ids']):
        for a, s in zip(p['uv_tris'][f], cm['uv_tris'][f]):
            back = ac.from_atlas(rows[p['face_key'][f]], p['uvs'][a])
            worst = max(worst, abs(back[0] - cm['uvs'][s][0]), abs(back[1] - cm['uvs'][s][1]))
    assert worst <= 1e-9
    _f, measured = npm.measure(back_of(p), p)
    assert measured['rigid_max_uv'] <= 1e-12 and measured['outside_cell'] == 0


def test_atlas_size_by_content_and_overflow_refuses():
    """L11: the atlas size follows the content (0.6 % of a 2048 at 39 px/m); a layout that does not fit at the
    target texel is refused with the numbers, the texel is never lowered to fit."""
    p = npm.plan(vpm_meshes(), OPTS, HEADERS)
    assert p['summary']['atlas_px'] < 2048
    big = npm.plan(vpm_meshes(), dict(OPTS, texel_px_per_m=900.0), HEADERS)
    assert [c for c, _f, _d in big['findings']] == ['atlas_overflow'] and big['atlas'] is None


def test_padding_is_continued_texture_and_at_least_8px():
    groups = [{'key': '3', 'kind': 'texture', 'uv_box': [0.0, 0.0, 1.0, 1.0], 'm_per_uv': [1.0, 1.0]},
              {'key': '7', 'kind': 'texture', 'uv_box': [0.0, 0.0, 1.0, 1.0], 'm_per_uv': [1.0, 1.0]}]
    lay = ac.rigid_plan(groups, 32.0)
    for c in lay['cells'].values():
        assert c['inner'][0] - c['outer'][0] >= 8 and c['inner'][1] - c['outer'][1] >= 8
    with pytest.raises(ac.AtlasError):
        ac.rigid_plan(groups, 32.0, pad=4)


def test_options_and_empty_input():
    with pytest.raises(ValueError):
        npm.options({'texel': 39})
    with pytest.raises(ValueError):
        npm.options({'max_size': 4096})
    with pytest.raises(ValueError):
        npm.plan([], {}, {})


def test_no_uv_fails_closed():
    m = vpm_meshes()[0]
    m = dict(m, uvs=None, uv_tris=None)
    p = npm.plan([m], OPTS, HEADERS)
    assert 'no_uv' in [c for c, _f, _d in p['findings']] and p['atlas'] is None


def test_atlas_png_is_24_bit_and_new_file_only(tmp_path):
    """Defects 4/5: GeoAGR overwrites atlases and reuses %TEMP%\\Tile_* (stale tile in the atlas, :27588); AGR
    writes NEW files only (write_new refuses an existing file) and keeps no fixed temp names."""
    groups = [{'key': '3', 'kind': 'texture', 'uv_box': [0.0, 0.0, 1.0, 1.0], 'm_per_uv': [1.0, 1.0]}]
    lay = ac.rigid_plan(groups, 32.0)
    img = ac.rigid_raster(lay, groups, {'3': coord_map(16, 16)})
    data = texqa.write_png(img['size'], img['size'], img['rgb'], 3)
    pic = texqa.read_png(data)
    assert (pic.w, pic.n) == (img['size'], 3) and pic.rgb() == img['rgb']
    target = tmp_path / 'T_X_d_1.png'
    target.write_bytes(b'stale')
    with pytest.raises(FileExistsError):
        edit.write_new(str(target), data)
    assert target.read_bytes() == b'stale'
    assert edit.new_path(str(tmp_path / 'T_X_d_1.png'), version=True).endswith('T_X_d_1_v002.png')


def test_files_of_npm_names():
    d, o, m = npm.files_of('SM_Vyatskaya_1_001_Main', 512, False)
    assert d.startswith('T_') and d.endswith('_d_1.png') and o is None and m.startswith('M_')
    d2, o2, _ = npm.files_of('not a name!', 512, True)
    assert d2 == 'T_not a name!_d_1.png' and o2.endswith('_o_1.png')


def test_glue_modules_load_without_max():
    for name in ('npm_max.py', 'facadeatlas_max.py'):
        mod = load(TOOLS / name, 'p_' + name[:-3])
        assert callable(getattr(mod, 'npm_build', None) or getattr(mod, 'atlas_facade_strip', None))
    nm = load(TOOLS / 'npm_max.py', 'p_npm_max2')
    p = npm.plan(vpm_meshes(), OPTS, HEADERS)
    total = 0
    for mi in range(2):
        uvs, tris = nm.split_uv(p, mi)
        total += len(tris)
        assert all(0 <= i < len(uvs) for t in tris for i in t)
    assert total == len(p['combined']['tris'])
    e = nm.entries_of(edit, vpm_meshes(), [('map_missing', [0, 1], 'x')])
    assert e[0]['findings'][0]['ids'] == [1, 2] and e[1]['findings'] == []


def test_write_files_in_a_new_folder(tmp_path):
    nm = load(TOOLS / 'npm_max.py', 'p_npm_max3')
    agr = types.SimpleNamespace(_load_core=lambda f, a: load(TOOLS / f, a))
    ctx = types.SimpleNamespace(agr=agr, edit=edit, host=types.SimpleNamespace(doc=lambda: 'untitled'))
    p = npm.plan(vpm_meshes(), OPTS, HEADERS)
    img = ac.rigid_raster(p['atlas'], p['groups'], {'3': coord_map(64, 64), '7': coord_map(64, 64)})
    folder = tmp_path / 'X_NPM'
    files, mname = nm.write_files(ctx, p, img, str(folder), 'SM_Test_Main', npm)
    assert [f['kind'] for f in files] == ['diffuse', 'table'] and mname == 'M_SM_Test_Main_1'
    table = json.loads(Path(files[1]['path']).read_text(encoding='ascii'))
    assert table['atlas_px'] == p['atlas']['size'] and len(table['table']) == len(p['groups'])
    with pytest.raises(FileExistsError):
        nm.write_files(ctx, p, img, str(folder), 'SM_Test_Main', npm)


def test_correspondence_table_signature_of_branch_0():
    rep = {'size': 512, 'texel': 39.0, 'cells': {'3': {'region': [0, 0, .5, .5], 'scale': [.1, .1],
                                                       'shift': [.2, .3], 'inner': [8, 8, 10, 10]}},
           'groups': [{'key': '3', 'library_id': 3, 'udim': 1001, 'kind': 'texture'}]}
    row, = ac.correspondence_table(rep)
    assert {k: row[k] for k in ('library_id', 'udim', 'region', 'scale', 'shift')} == {
        'library_id': 3, 'udim': 1001, 'region': [0, 0, .5, .5], 'scale': [.1, .1], 'shift': [.2, .3]}


# ---- atlas.facade_strip ----------------------------------------------------------------------------------------
def test_facade_four_strips_two_unique_panels_acceptance():
    """1.0.23 acceptance: 4 repeating strips + 2 unique panels: atlas <= NPM limit, padding >= 8 px, strip texel =
    target +-1 %, UV of the copy in its cells, phase kept (fold by whole periods)."""
    mesh = PB.strip_facade()
    maps = {'s%d.png' % i: {'w': 48, 'h': 32} for i in range(4)}
    maps.update({'u1.png': {'w': 64, 'h': 64}, 'u2.png': {'w': 64, 'h': 64}})
    p = fac.plan([mesh], {'period_by_id': PB.PERIODS}, maps)
    assert p['findings'] == []
    s = p['summary']
    assert s['atlas_px'] <= 2048 and s['strip_ids'] == sorted(int(k) for k in PB.PERIODS) and len(s['unique_ids']) == 2
    findings, measured = fac.measure(back_of(p), p)
    assert findings == [] and measured['outside_cell'] == 0
    for t in measured['texel_px_per_m'].values():
        assert abs(t / 39.0 - 1) <= 0.01
    for c in p['atlas']['cells'].values():
        assert c['inner'][0] - c['outer'][0] >= 8
    # phase: folded pattern UV minus the raw projection is a whole number of periods
    for key, recs in p['strips'].items():
        assert all(float(x).is_integer() for r in recs for x in r['shift_periods'])
    assert max(len(v) for v in p['strips'].values()) >= 2  # several wall regions share one strip


def test_facade_phase_continuous_across_neighbour_walls():
    """Two coplanar wall pieces side by side (not connected): the pattern UV of the shared line differs by a whole
    number of periods only - the strip shows the same texture phase on both sides."""
    mesh = PB.strip_facade()
    p = fac.plan([mesh], {'period_by_id': PB.PERIODS}, {**{'s%d.png' % i: {'w': 48, 'h': 32} for i in range(4)},
                                                       'u1.png': {'w': 64, 'h': 64}, 'u2.png': {'w': 64, 'h': 64}})
    cm = p['combined']
    pos = {}
    for f, mid in enumerate(cm['mat_ids']):
        if str(mid) not in PB.PERIODS:
            continue
        for c, vi in enumerate(cm['tris'][f]):
            x, y, z = cm['verts'][vi]
            if abs(x - 4.5) < 1e-9 and abs(y) < 1e-9:  # the cut line of the front wall (both pieces on y = 0)
                pos.setdefault((mid, round(z, 6)), []).append(p['pattern_uv'][f][c])
    assert len(pos) == 8 and all(len(v) >= 2 for v in pos.values())
    for vals in pos.values():
        for a in vals[1:]:
            assert abs((a[0] - vals[0][0]) - round(a[0] - vals[0][0])) < 1e-9
            assert abs((a[1] - vals[0][1]) - round(a[1] - vals[0][1])) < 1e-9


def test_facade_stack_parameter_and_npm_padding_rule():
    """D156 stacks every region of a strip ID into one strip: tex.check of an NPM reports the overlap
    (`tex_padding`); stack=False gives every planar region / island its own cell, no finding, same texel."""
    ck = load(TOOLS / 'checks_core.py', 'p_checks_core_f')
    maps = {**{'s%d.png' % i: {'w': 48, 'h': 32} for i in range(4)}, 'u1.png': {'w': 64, 'h': 64},
            'u2.png': {'w': 64, 'h': 64}}
    for stack, want in ((True, {'tex_padding'}), (False, set())):
        p = fac.plan([PB.strip_facade()], {'period_by_id': PB.PERIODS, 'stack': stack}, maps)
        got = ck.padding_findings([tuple(u) for u in p['uvs']], [(f + 1, t) for f, t in enumerate(p['uv_tris'])],
                                  p['atlas']['size'], 8)
        assert {g[0] for g in got} == want, (stack, got[:2])
        findings, m = fac.measure(back_of(p), p)
        assert findings == [] and all(abs(t / 39.0 - 1) <= 0.01 for t in m['texel_px_per_m'].values())
    nm = load(TOOLS / 'npm_max.py', 'p_npm_max_slice')
    two = fac.plan([PB.strip_facade('SM_A_Main'), PB.strip_facade('SM_B_Main')],
                   {'period_by_id': PB.PERIODS, 'stack': False}, maps)
    n = len(two['combined']['tris']) // 2
    sub = nm._slice(two, n, n)
    back = {'verts': two['combined']['verts'], 'tris': two['combined']['tris'][n:], 'mat_ids': two['combined']['mat_ids'][n:],
            'uvs': two['uvs'], 'uv_tris': two['uv_tris'][n:]}
    assert fac.measure(back, sub)[0] == []  # the per-copy readback of the 2nd object uses its own cells


def test_facade_float32_vertices_fold_like_exact_ones():
    """Native job 20261106-062347-9524f5c1: in metres Max stores 3.6 as 3.5999999 (float32); folding with a 1e-9
    tolerance moved such a piece by one period (strip one period taller, fill 0.507 in m vs 0.441 in cm)."""
    import struct
    mesh = PB.strip_facade()
    f32 = dict(mesh, verts=[[struct.unpack('f', struct.pack('f', c))[0] for c in v] for v in mesh['verts']])
    maps = {**{'s%d.png' % i: {'w': 48, 'h': 32} for i in range(4)}, 'u1.png': {'w': 64, 'h': 64},
            'u2.png': {'w': 64, 'h': 64}}
    exact = fac.plan([mesh], {'period_by_id': PB.PERIODS}, maps)
    noisy = fac.plan([f32], {'period_by_id': PB.PERIODS}, maps)
    lo = [math.floor(3.5999999 / 1.2 + 1e-9), math.floor(3.5999999 / 1.2 + fac.FOLD_EPS)]
    assert lo == [2, 3]  # RED with the old tolerance, GREEN with FOLD_EPS
    assert {k: c['inner'][2:] for k, c in noisy['atlas']['cells'].items()} == {
        k: c['inner'][2:] for k, c in exact['atlas']['cells'].items()}


def test_facade_options_labels_off_and_period_required():
    with pytest.raises(ValueError):
        fac.options({'period_by_id': {'101': 1.2}, 'labels': True})
    with pytest.raises(ValueError):
        fac.options({})
    o = fac.options({'period_by_id': {'101': 1.2}})
    assert o['labels'] is False and o['period_by_id']['101'] == [1.2, 1.2]


def test_facade_missing_map_refuses():
    mesh = PB.strip_facade()
    p = fac.plan([mesh], {'period_by_id': PB.PERIODS}, {})
    assert {c for c, _f, _d in p['findings']} == {'map_missing'} and p['atlas'] is None


def test_facade_pilot_padding_note_red_green():
    """Pilot note (docs/backlog.md:158): own-colour padding below 8 px; the pilot also fixed one 2048 atlas and
    hand-placed bands. AGR: padding >= 8 px of the continued texture, size from the content."""
    pilot_pad, pilot_size = 16, 2048
    assert pilot_size == 2048  # RED-ish: fixed size regardless of content
    mesh = PB.strip_facade()
    p = fac.plan([mesh], {'period_by_id': PB.PERIODS}, {**{'s%d.png' % i: {'w': 48, 'h': 32} for i in range(4)},
                                                       'u1.png': {'w': 64, 'h': 64}, 'u2.png': {'w': 64, 'h': 64}})
    assert p['atlas']['size'] < pilot_size and p['atlas']['pad'] >= 8 and pilot_pad >= 8


def test_periodic_cell_matches_bruteforce():
    rnd = random.Random(3)
    w, h = 7, 5
    src = bytes(rnd.randrange(256) for _ in range(w * h))
    x0, y0, kx, ky, dw, dh = -3.3, 11.6, 0.7, 1.9, 9, 6
    got = ac.periodic_cell(src, w, h, 1, x0, y0, kx, ky, dw, dh)

    def area(xa, xb, ya, yb):
        acc, n = 0.0, 400
        for i in range(n):
            for j in range(n // 4):
                x = xa + (xb - xa) * (i + 0.5) / n
                y = ya + (yb - ya) * (j + 0.5) / (n // 4)
                acc += src[(int(math.floor(y)) % h) * w + int(math.floor(x)) % w]
        return acc / (n * (n // 4))
    for Y in range(dh):
        for X in range(dw):
            want = area(x0 + X / kx, x0 + (X + 1) / kx, y0 + Y / ky, y0 + (Y + 1) / ky)
            assert abs(got[Y * dw + X] - want) <= 1.5
