"""new-case: AGR Tools 1.0 (#1024) branch L - materials: mat.table (K3), mat.tiles (K3 + owner answer V12), tex.plug_colour
(lab L14). Plain pytest, no pymxs: cores + library; the Max glue runs in run_agr_tools_materials_native.py.

Every named defect has a RED test on a model of the source behaviour and a GREEN test on this implementation:
* tex.multimat (GeoAGR Multimat HP GeoAGR.ms:42706): ID = UDIM - 1000 keeps the gaps -> renumber_dense is dense;
* #1024 literal 4096 px @ 1024 px/m (= 4.0 m) facade map: 600 mm module does not divide -> seam; 3.6 m period: none;
* Ground recipe pitch 105 x 305 (joint outside the module): not periodic on 3.6 m -> joint inside the module;
* GeoAGR Colors Tex (GeoAGR.ms:39668-39965, lab L14 jobs 20261106-023826-7907def9): first colour found, row 0 not
  read, alpha ignored, gamma 2.2 darkening -> mode of the full alpha-weighted histogram of file bytes.
"""
import hashlib
import importlib.util
import inspect
import json
import struct
import sys
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'
LIB = ROOT / 'library/materials/materials.json'


def _load(filename, name):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, PKG / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ec = _load('edit_core.py', 'agr_tools_edit_core')
ml = _load('matlib_core.py', 'agr_tools_matlib_core')
tc = _load('tiles_core.py', 'agr_tools_tiles_core')
pc = _load('plugcolour_core.py', 'agr_tools_plugcolour_core')
tex = _load('tex_core.py', 'agr_tools_tex_core')
RALS3 = [{'code': c, 'rgb': ml.hex_rgb(h)} for c, h in (('7024', '#474A51'), ('7040', '#989EA1'),
                                                         ('5015', '#2271B3'))]


@pytest.fixture(scope='module')
def lib():
    return ml.load_library(LIB)


# ==== library (K3) ===============================================================================================
def test_library_pointer_schema_and_ral(lib):
    ptr = json.loads(LIB.read_text(encoding='utf-8'))
    assert ptr['current'] == 'materials_v002.json' and lib['version'] == 'v002' == ptr['version']
    assert lib['sha256'] == ptr['sha256'] and lib['ral_checked']
    assert 30 <= len(lib['materials']) <= 40
    ids = [r['library_id'] for r in lib['materials']]
    assert len(ids) == len(set(ids)) and {3, 7, 12, 31} <= set(ids)
    ral = json.loads((ROOT / 'tools/materials/ral_classic.json').read_text(encoding='utf-8'))['colors']
    for r in lib['materials']:
        if r['ral']:
            assert r['ral'] in ral and r['rgb_srgb'] == ml.hex_rgb(ral[r['ral']]), r['key']
    classes = {r['class'] for r in lib['materials']}
    assert {'glass', 'interior', 'roof', 'metal', 'paint', 'tile', 'panel', 'paving'} <= classes
    # interior/roof/metal plugs: colour + roughness/metal, no texture
    for k in ('interior', 'roof_logicroof', 'steel_stainless'):
        rec = next(r for r in lib['materials'] if r['key'] == k)
        assert rec['recipe'] == {'kind': 'solid'} and rec['base_map'] is None
    glass = [r for r in lib['materials'] if r['class'] == 'glass']
    assert len(glass) == 1 and 0 < glass[0]['opacity'] < 1


def test_library_base_maps_and_maf_cross_reference(lib):
    assert set(ml.BASE_MAPS) == set(tc.BASE_MAPS)
    used = {r['base_map'] for r in lib['materials'] if r['base_map']}
    assert {'facade_600x1200', 'ground_100x300', 'crumb_1x1'} <= used  # the three K3 maps
    assert len(used) >= 6  # owner answer V12: the audit set, not only panels/paving/crumb
    maf = json.loads((ROOT / 'library/maf/material_ids_v005.json').read_text(encoding='utf-8'))
    maf_ids = {int(m['id']) for m in maf['ids']}
    for r in lib['materials']:
        if r['maf_v005_id'] is not None:
            assert r['maf_v005_id'] in maf_ids, r['key']


@pytest.mark.parametrize('mutate,match', [
    (lambda d: d['materials'].append(dict(d['materials'][0], key='dup_id')), 'duplicate library_id'),
    (lambda d: d['materials'][0].update(ral='8099'), 'not in ral_classic'),
    (lambda d: d['materials'][0].update(rgb_srgb=[1, 2, 3]), 'differs from ral_classic'),
    (lambda d: d['materials'][13].update(base_map='crumb_1x1'), 'greyscale_mask needs base_map'),
    (lambda d: d['materials'][0].update(library_id=1001), 'library_id must be an integer 1..1000'),
    (lambda d: d['materials'][0].update(roughness=0.5), 'byte 0..255'),
])
def test_library_rejects(mutate, match):
    doc = json.loads((ROOT / 'library/materials/materials_v002.json').read_text(encoding='utf-8'))
    ral = ml.ral_table(ROOT / 'tools/materials/ral_classic.json')
    mutate(doc)
    with pytest.raises(ValueError, match=match):
        ml.validate_library(doc, ral)


def test_library_pointer_hash_mismatch(tmp_path):
    src = ROOT / 'library/materials/materials_v002.json'
    (tmp_path / 'materials_v002.json').write_bytes(src.read_bytes().replace(b'"v002"', b'"v002" ', 1))
    (tmp_path / 'materials.json').write_text(LIB.read_text(encoding='utf-8'), encoding='utf-8')
    with pytest.raises(ValueError, match='sha256'):
        ml.load_library(tmp_path / 'materials.json')


def test_load_library_signature_is_branch0():
    assert list(inspect.signature(ml.load_library).parameters) == ['path']
    assert list(inspect.signature(ml.renumber_dense).parameters) == ['used_ids', 'start']


# ==== renumbering (K3, V9) ======================================================================================
def _source_multimat_ids(udims):
    """Model of GeoAGR Multimat HP / tex.multimat (#1024 «редакция 1» row 22): ID = UDIM - 1000."""
    return sorted(u - 1000 for u in udims)


def test_red_multimat_keeps_udim_gaps_green_dense():
    src = _source_multimat_ids([1001, 1002, 1005])
    assert src == [1, 2, 5] and src != list(range(1, len(src) + 1))  # RED: gaps survive
    got = ml.renumber_dense([5, 1, 2])
    assert sorted(got.values()) == [1001, 1002, 1003]  # GREEN: dense


def test_renumber_dense_midpoly_and_per_mesh_glass():
    assert ml.renumber_dense([31, 3, 12, 7]) == {3: 1001, 7: 1002, 12: 1003, 31: 1004}
    assert ml.renumber_dense([39]) == {39: 1001}  # glass mesh starts at 1001 too (V9)
    assert ml.renumber_dense([10, 20], start=1001) == {10: 1001, 20: 1002}
    for bad in ([0], [1005], [True], [1.5], []):
        with pytest.raises(ValueError):
            ml.renumber_dense(bad)
    with pytest.raises(ValueError):
        ml.renumber_dense(range(1, 102))


# ==== mat.table plan ============================================================================================
def _items(*specs):
    return [{'handle': i + 1, 'name': n, 'role': role, 'ids': {k: 2 for k in ids}}
            for i, (n, role, ids) in enumerate(specs)]


def test_table_midpoly_ids_dense_and_report(lib):
    items = _items(('BODY_Mid_001', 'body', [3, 7, 12, 31]), ('GLASS_Mid_001', 'glass', [39]))
    entries, table, multisub, skipped = ml.table_plan(ec, items, lib)
    assert all(not e['findings'] for e in entries) and not skipped
    body = [(r['library_id'], r['udim'], r['delivery_id']) for r in table if r['mesh'] == 'BODY_Mid_001']
    assert body == [(3, 1001, 1), (7, 1002, 2), (12, 1003, 3), (31, 1004, 4)]
    assert [(r['library_id'], r['udim']) for r in table if r['mesh'] == 'GLASS_Mid_001'] == [(39, 1001)]
    assert [m['id'] for m in multisub] == [3, 7, 12, 31, 39]
    glass = next(m for m in multisub if m['id'] == 39)
    assert glass['opacity'] == 0.5 and glass['name'] == 'L039_glass_01'
    rep = ml.report(ec, 'preview', entries, table, multisub, skipped, lib, state_hash='s')
    assert rep['status'] == 'pass' and rep['plan']['multisub']['name'] == 'AGR_Library_v002'
    assert ec.check_preview('mat.table', rep) is rep
    assert ml.udim_tables(table) == {'BODY_Mid_001': {3: 1001, 7: 1002, 12: 1003, 31: 1004}, 'GLASS_Mid_001': {39: 1001}}
    # passport schema rows
    schema = json.loads((ROOT / 'schemas/ProjectPassport.schema.json').read_text(encoding='utf-8'))
    import jsonschema
    jsonschema.validate(table, schema['properties']['materials'])


@pytest.mark.parametrize('spec,code,ids', [
    (('BODY_Udim_001', 'body', [3, 1005]), 'udim_id_on_geometry', [1005]),
    (('BODY_Unknown_001', 'body', [3, 999]), 'id_not_in_library', [999]),
    (('BODY_Glass_001', 'body', [3, 39]), 'glass_not_on_glass', [39]),
    (('GLASS_Wrong_001', 'glass', [39, 3]), 'non_glass_on_glass', [3]),
])
def test_table_fail_codes(lib, spec, code, ids):
    entries, table, multisub, _ = ml.table_plan(ec, _items(spec), lib)
    assert [(f['code'], f['ids']) for f in entries[0]['findings']] == [(code, ids)]
    assert table == [] and multisub == []
    rep = ml.report(ec, 'preview', entries, table, multisub, [], lib, state_hash='s')
    assert rep['status'] == 'fail'


def test_table_empty_input_and_no_faces(lib):
    with pytest.raises(ValueError, match='empty input'):
        ml.table_plan(ec, [], lib)
    entries, table, _, skipped = ml.table_plan(ec, _items(('BODY_Empty_001', 'body', [])), lib)
    assert entries == [] and skipped[0]['item'] == 'BODY_Empty_001'


# ==== mat.tiles (K3) ============================================================================================
def test_tile_defaults_are_parameters():
    s, f = tc.spec('facade_600x1200')
    assert (s['px_per_m'], s['period_m'], s['size_px'], s['counts']) == (1000.0, 3.6, 3600, [6, 3]) and not f
    s, _ = tc.spec('facade_600x1200', {'px_per_m': 1000})
    assert s['size_px'] == 3600  # audit Q1: 1000 px/m -> 3600 px, every module integer
    s, _ = tc.spec('ground_100x300')
    assert s['counts'] == [12, 36] and s['bond'] == 0.5
    s, _ = tc.spec('crumb_1x1')
    assert (s['size_px'], s['cells']) == (1000, 250)   # 1 m at 1000 px/m
    with pytest.raises(ValueError):
        tc.spec('nope')
    with pytest.raises(ValueError):
        tc.spec('facade_600x1200', {'colour': 1})


@pytest.mark.parametrize('base', sorted(tc.BASE_MAPS))
def test_every_base_map_is_seamless_and_recolours_within_delta_e(base):
    s, grey, result, findings = tc.check_base(base, None, RALS3)
    assert findings == [] and result['seam_levels'] <= 1.0
    assert all(r['delta_e2000'] <= 2.0 for r in result['recolour'])


def test_red_4096_at_1024_ppm_facade_not_seamless_green_3_6m():
    # RED: the literal #1024 numbers (4096 px at 1024 px/m = 4.0 m) cut the 600 mm module at the tile edge
    _, _, red, found = tc.check_base('facade_600x1200', {'period_m': 4.0, 'fit': False}, RALS3)
    assert red['seam_levels'] > 1.0 and {'module_not_dividing', 'not_seamless'} <= {f['code'] for f in found}
    _, _, red_fit, found_fit = tc.check_base('facade_600x1200', {'period_m': 4.0}, RALS3)
    assert {f['code'] for f in found_fit} == {'module_stretched'}  # fitting would distort the module by 4.8 %
    # GREEN: 3.6 m UDIM step (owner 06.11) holds 6 x 3 modules
    _, _, green, ok = tc.check_base('facade_600x1200', None, RALS3)
    assert green['seam_levels'] == 0.0 and not ok


def test_red_ground_pitch_105x305_not_periodic_green_joint_inside():
    _, _, red, found = tc.check_base('ground_100x300', {'module': [0.305, 0.105], 'fit': False})
    assert red['seam_levels'] > 1.0 and 'not_seamless' in {f['code'] for f in found}
    _, _, green, ok = tc.check_base('ground_100x300')
    assert green['seam_levels'] == 0.0 and not ok


def test_brick_fitted_to_period_reports_stretch():
    s, f = tc.spec('brick_250x65')
    assert s['counts'] == [14, 48] and s['stretch_pct'][0] == pytest.approx(-1.0989, abs=1e-3) and not f
    _, f = tc.spec('brick_250x65', {'max_stretch_pct': 1.0})
    assert [c for c, _ in f] == ['module_stretched']  # the threshold is a parameter (brick tolerance 1.5 %, Q3)


def test_bond_with_odd_course_count_is_a_finding():
    _, f = tc.spec('ground_100x300', {'period_m': 0.3})
    assert [c for c, _ in f] == ['bond_odd_courses']


def test_recolour_mask_channels():
    s, _ = tc.spec('facade_600x1200')
    grey = tc.Grey(s)
    hist = tc.body_histogram(grey)
    ref = tc.grey_ref(hist)
    rgb = [71, 74, 81]
    luts, joint = tc.recolour_luts(rgb, ref)
    mean = tc.mean_body_colour(hist, luts)
    assert all(abs(m - c) < 0.6 for m, c in zip(mean, rgb))
    assert joint == [round(c * 0.55 + (c - c * 0.55) * 0.35) for c in rgb]
    key, r, g = grey.row(0)  # row 0 sits on the half joint of the tile edge
    row = tc.recolour_row(r, g, luts, joint)
    full = [i for i, v in enumerate(g) if v == 255]
    assert full and list(row[full[0] * 3:full[0] * 3 + 3]) == joint
    mid = grey.h // 6
    _, r, g = grey.row(mid)
    body = [i for i, v in enumerate(g) if v == 0][0]
    assert list(tc.recolour_row(r, g, luts, joint)[body * 3:body * 3 + 3]) == [luts[c][r[body]] for c in range(3)]


def test_png_stream_readback_and_normal_erm(lib):
    s, _ = tc.spec('tile_300x300', {'px_per_m': 40})
    grey = tc.Grey(s)
    data, raw = tc.png_stream(grey.w, grey.h, tc.mask_rows(grey))
    assert tc.png_readback(data) == (grey.w, grey.h, raw)
    img, info = tex.decode_png(data)
    assert (img.w, img.h, img.n) == (grey.w, grey.h, 3)
    bad = bytearray(data)
    bad[40] ^= 0xff
    with pytest.raises(ValueError):
        tc.png_readback(bytes(bad))
    rows = list(tc.normal_rows(grey))
    mid = rows[grey.h // 24]
    assert mid[3 * (grey.w // 24):3 * (grey.w // 24) + 3] == b'\x80\x80\xff'  # flat body
    assert any(rows[0][i:i + 3] != b'\x80\x80\xff' for i in range(0, len(rows[0]), 3))  # joint relief
    rec = lib['by_id'][36]
    assert tc.erm_rgb(rec) == [0, 60, 255]
    with pytest.raises(ValueError):
        tc.png_stream(2, 2, [b'\x00' * 6])


def test_texture_tiles_cli_greyscale_mask_recipe(tmp_path):
    cli = importlib.util.spec_from_file_location('tt_cli', ROOT / 'technical_library/texture_tiles/cli.py')
    mod = importlib.util.module_from_spec(cli)
    cli.loader.exec_module(mod)
    size = tc.spec('ground_100x300', {'px_per_m': 50})[0]['size_px']
    cfg = {'tiles': [{'id': 18, 'udim': 1001, 'rgb': [118, 116, 114], 'size': [size, size], 'kind': 'greyscale_mask',
                      'base_map': 'ground_100x300', 'overrides': {'px_per_m': 50}}]}
    rep = mod.build(cfg, tmp_path / 'out')
    assert rep['tiles'][0]['size'] == [size, size] and rep['archive_readback_equal']
    with pytest.raises(ValueError, match='size must be'):
        mod.validate({'tiles': [dict(cfg['tiles'][0], size=[4096, 4096])]})
    with pytest.raises(ValueError, match='module_not_dividing'):
        mod.validate({'tiles': [dict(cfg['tiles'][0], overrides={'px_per_m': 50, 'period_m': 4.0, 'fit': False})]})


# ==== tex.plug_colour (lab L14) =================================================================================
def _source_colors_tex(w, h, n, px):
    """Model of GeoAGR «Colors Tex» (GeoAGR.ms:39725-39957) as measured by lab L14: rows from 1 (row 0 not read),
    alpha dropped, the FIRST colour met is written, through the Max bitmap slot gamma 2.2 (darkens)."""
    first = None
    for y in range(1, h):
        for x in range(w):
            o = (y * w + x) * n
            first = first or tuple(px[o:o + 3])
    return [int(255 * (c / 255.0) ** 2.2) for c in first]  # truncated, as the lab measured


def _img(w, h, colour_at, n=3):
    px = bytearray()
    for y in range(h):
        for x in range(w):
            px += bytes(colour_at(x, y))[:n]
    return w, h, n, bytes(px)


def test_red_gamma_darkening_green_exact_colour():
    w, h, n, px = _img(64, 64, lambda x, y: (200, 100, 50))
    assert _source_colors_tex(w, h, n, px) == [149, 32, 7]  # RED (lab L14: 149 32 7)
    row = pc.analyse('solid.png', w, h, n, px)
    assert row['chosen'] == [200, 100, 50] and row['decision'] == 'pass' and row['rmse'] == 0.0  # GREEN
    w, h, n, px = _img(64, 64, lambda x, y: (128, 128, 128))
    assert _source_colors_tex(w, h, n, px) == [55, 55, 55] and pc.analyse('g', w, h, n, px)['chosen'] == [128] * 3


def test_red_first_found_green_mode_and_spread_fail():
    # 9.4 % blue first in the scan, 90.6 % main
    w, h = 64, 64
    blue = int(w * h * 0.094)
    n_px = [0]

    def at(x, y):
        i = y * w + x
        return (0, 0, 255) if w <= i < w + blue else (200, 100, 50)
    w, h, n, px = _img(w, h, at)
    src = _source_colors_tex(w, h, n, px)
    assert src == [0, 0, 255]  # RED: the first colour found wins (blue, after gamma still blue)
    row = pc.analyse('mix.png', w, h, n, px)
    assert row['chosen'] == [200, 100, 50] and row['decision'] == 'spread'  # GREEN: mode, fail by spread
    assert row['top'][1]['rgb'] == [0, 0, 255] and row['top'][1]['share'] == pytest.approx(blue / (w * h), abs=1e-6)
    assert pc.finding_of(row)[0] == 'plug_spread'


def test_red_row0_not_read_green_row0_counted():
    w, h, n, px = _img(32, 32, lambda x, y: (0, 0, 255) if y == 0 else (200, 100, 50))
    src_first = _source_colors_tex(w, h, n, px)
    assert src_first != [0, 0, 255]  # RED: row 0 never read
    row = pc.analyse('r0.png', w, h, n, px)
    assert {'rgb': [0, 0, 255], 'share': round(32 / 1024, 6)} in row['top']  # GREEN


def test_red_alpha_ignored_green_alpha_weighted():
    w, h = 32, 32
    w, h, n, px = _img(w, h, lambda x, y: (0, 0, 0, 0) if y * 32 + x < 640 else (0, 255, 0, 255), n=4)
    assert _source_colors_tex(w, h, n, px) == [0, 0, 0]  # RED: transparent black written as opaque
    row = pc.analyse('a.png', w, h, n, px)
    assert row['chosen'] == [0, 255, 0] and row['transparent_share'] == 0.625 and row['decision'] == 'pass'
    w, h, n, px = _img(4, 4, lambda x, y: (9, 9, 9, 0), n=4)
    assert pc.analyse('t', w, h, n, px)['decision'] == 'no_visible'


def test_tie_is_reported_not_guessed():
    w, h, n, px = _img(4, 4, lambda x, y: (255, 0, 0) if x < 2 else (0, 255, 0))
    row = pc.analyse('tie', w, h, n, px)
    assert row['decision'] == 'tie' and pc.finding_of(row)[0] == 'plug_tie'


def _tga(w, h, pixels, bpp=24, rle=False, top=True):
    k = bpp // 8
    data = bytearray()
    rows = [pixels[y * w:(y + 1) * w] for y in range(h)]
    if not top:
        rows = rows[::-1]
    for r in rows:
        for p in r:
            data += bytes((p[2], p[1], p[0]) + ((p[3],) if k == 4 else ()))
    if rle:
        body = bytearray()
        for i in range(0, len(data), k):
            body += bytes((0x80,)) + data[i:i + k]  # one-pixel runs
        data = body
    head = struct.pack('<BBBHHBHHHHBB', 0, 0, 10 if rle else 2, 0, 0, 0, 0, 0, w, h, bpp, 0x20 if top else 0)
    return bytes(head) + bytes(data)


def test_formats_png_rgba_palette_tga_jpg_and_sizes(tmp_path):
    img = tex.Image(4, 2, 4, bytes([10, 20, 30, 255] * 6 + [0, 0, 0, 0] * 2))
    files = {'rgba.png': tex.encode_png(img),
             'rgb.png': tex.encode_png(tex.Image(4, 2, 3, bytes([10, 20, 30] * 8))),
             'pal.png': tex.encode_palette_png(10, 1, [(1, 2, 3), (9, 8, 7)], [0, 0, 0, 1, 1, 1, 1, 1, 1, 1]),
             'a.tga': _tga(2, 2, [(10, 20, 30)] * 4),
             'b.tga': _tga(2, 2, [(10, 20, 30, 255)] * 3 + [(0, 0, 0, 0)], bpp=32, rle=True, top=False)}
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.iterdir()}

    def read(p):
        return Path(p).read_bytes()
    rows = {name: pc.analyse_file(str(tmp_path / name), read) for name in files}
    assert rows['rgba.png']['chosen'] == [10, 20, 30] and rows['rgba.png']['transparent_share'] == 0.25
    assert rows['rgb.png']['decision'] == 'pass'
    assert rows['pal.png']['chosen'] == [9, 8, 7]  # palette 30/70: the 70 % colour (lab: first 30 % was written)
    assert rows['a.tga']['chosen'] == [10, 20, 30] and rows['a.tga']['decoder'] == 'tga'
    assert rows['b.tga']['chosen'] == [10, 20, 30] and rows['b.tga']['transparent_share'] == 0.25
    for r in rows.values():
        assert {'file', 'size', 'colours', 'top', 'transparent_share', 'chosen', 'mean', 'rmse', 'max_delta_e',
                'decision', 'sha256'} <= set(r)
    # JPG: decoded by the glue (.NET); without it the file is unreadable, never skipped silently
    (tmp_path / 'c.jpg').write_bytes(b'\xff\xd8\xff')
    assert pc.analyse_file(str(tmp_path / 'c.jpg'), read)['decision'] == 'unreadable'
    got = pc.analyse_file(str(tmp_path / 'c.jpg'), read, other=lambda p: tex.Image(2, 2, 3, bytes([5, 6, 7] * 4)))
    assert got['chosen'] == [5, 6, 7] and got['decoder'] == 'dotnet'
    assert pc.analyse_file(str(tmp_path / 'missing.png'), read)['decision'] == 'unreadable'
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.iterdir() if p.name in before}
    assert after == before  # sources untouched
    for w, h in ((512, 512), (256, 1024)):  # lab: these sizes were skipped with a modal dialog
        r = pc.analyse('big', w, h, 3, bytes([1, 2, 3]) * (w * h))
        assert r['chosen'] == [1, 2, 3] and r['stride'] == 1


def test_large_map_is_sampled_including_row0():
    w, h = 2048, 1024
    px = bytearray(bytes([200, 100, 50]) * (w * h))
    px[0:3] = bytes([1, 1, 1])
    r = pc.analyse('huge', w, h, 3, bytes(px), {'max_samples': 1 << 16})
    assert r['stride'] > 1 and r['samples'] <= 1 << 16
    assert any(t['rgb'] == [1, 1, 1] for t in r['top'])  # (0, 0) is on the sample grid


def test_plug_png_exact_and_report_shape():
    data = pc.plug_png([200, 100, 50], 16)
    img, _ = tex.decode_png(data)
    assert img.px == bytes([200, 100, 50]) * 256
    row = pc.analyse('p', img.w, img.h, img.n, img.px)
    rep = pc.report(ec, [ec.entry(5, 'Plane_Plug', [])], [row], [], 'state', pc.options({}))
    assert rep['status'] == 'pass' and rep['plan']['files'][0]['decision'] == 'pass'
    rep = pc.report(ec, [ec.entry(5, 'Plane_Plug', [ec.finding('plug_spread', [], 'x')])], [row], [], 's', {})
    assert rep['status'] == 'fail'


# ==== glue modules and rules ====================================================================================
@pytest.mark.parametrize('glue,fn', [('matlib_max.py', 'mat_table'), ('tiles_max.py', 'mat_tiles'),
                                     ('plugcolour_max.py', 'tex_plug_colour')])
def test_glue_functions_exist_without_pymxs(glue, fn):
    mod = _load(glue, 'agr_tools_' + glue[:-3])
    assert list(inspect.signature(getattr(mod, fn)).parameters) == ['ctx', 'mode', 'nodes', 'preview']


@pytest.mark.parametrize('name', ['matlib_core.py', 'matlib_max.py', 'tiles_core.py', 'tiles_max.py',
                                  'plugcolour_core.py', 'plugcolour_max.py'])
def test_no_forbidden_calls(name):
    import ast
    src = (PKG / name).read_text(encoding='utf-8')
    doc = ast.get_docstring(ast.parse(src), clean=False) or ''
    text = src.replace(doc, '')  # the docstring may name what the code avoids
    for bad in ('clearUndoBuffer', 'decodeValue', 'collapseStack', 'maxOps.CollapseNode'):
        assert bad not in text
    if name.endswith('_core.py'):
        assert 'pymxs' not in text.replace('no pymxs', '')
