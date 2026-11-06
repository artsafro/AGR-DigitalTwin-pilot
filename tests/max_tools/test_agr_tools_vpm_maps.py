"""AGR Tools 1.0 (#1024) branch N: tex.dilate (1.0.20), udim.plugs (1.0.21), vpmmaps (D+ERM+N of vpm.build), bitmap enumerator.

Every named defect is a regression test run against two implementations:
* `source` - a behaviour model of the GeoAGR chain / GridUVLayout22 AS MEASURED (plan-row verdicts, lab L15, team-script
  audit T02; no GeoAGR code, #853): it must FAIL (strict xfail = RED);
* `agr` - dilate_core / udimplug_core / vpmmaps_core / tex_core of this branch: it must PASS (GREEN).
"""
import hashlib
import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'


def _load(path, name):
    mod = sys.modules.get(name)
    if mod is None:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return mod


ec = _load(PKG / 'edit_core.py', 'agr_tools_edit_core')
tc = _load(PKG / 'tex_core.py', 'agr_tools_tex_core')
dc = _load(PKG / 'dilate_core.py', 'agr_tools_dilate_core')
pc = _load(PKG / 'udimplug_core.py', 'agr_tools_udimplug_core')
vc = _load(PKG / 'vpmmaps_core.py', 'agr_tools_vpmmaps_core')


def img_rgb(w, h, fn):
    px = bytearray()
    for y in range(h):
        for x in range(w):
            px += bytes(fn(x, y))
    return tc.Image(w, h, 3, px)


def img_rgba(w, h, fn):
    px = bytearray()
    for y in range(h):
        for x in range(w):
            px += bytes(fn(x, y))
    return tc.Image(w, h, 4, px)


# ---- behaviour model of the source (as measured; plan row verdict + L15) --------------------------------
class SourceDilate:
    """GeoAGR chain `-transparent <colour>` + uvdilate + `-alpha remove` as the plan row measured it: only a real
    alpha channel is padded, a map without alpha comes back unpadded, the output never has alpha, the padded file is
    written over the output path without a question, the number of padded pixels is not limited."""

    @staticmethod
    def run(img, files=None, target='out.png'):
        if img.n != 4:
            return img, 0, False                      # white background without alpha: no padding
        mask = [1 if a else 0 for a in img.px[3::4]]
        out, n = dc.dilate_masked(img, mask, max(img.w, img.h))     # unlimited, to the canvas edge
        return out, n, False                          # alpha removed

    @staticmethod
    def write(files, target, data):
        files[target] = data                          # silent overwrite
        return True


# ======================= tex.dilate ======================================================================
def island_rgba(w=32, h=32):
    return img_rgba(w, h, lambda x, y: (200, 40, 40, 255) if 12 <= x < 20 and 12 <= y < 20 else (0, 0, 0, 0))


def island_white(w=32, h=32):
    return img_rgb(w, h, lambda x, y: (200, 40, 40) if 12 <= x < 20 and 12 <= y < 20 else (255, 255, 255))


def test_dilate_no_padding_on_white_background_without_alpha_red_green():
    img = island_white()
    src, _, _ = SourceDilate.run(img)
    assert src.px == img.px                                   # the source leaves it unpadded
    mask = dc.mask_from_background(img, (255, 255, 255))
    out, n = dc.dilate_masked(img, mask, 4)
    assert n > 0 and tuple(out.px[3 * (11 * 32 + 15):3 * (11 * 32 + 15) + 3]) == (200, 40, 40)   # ring next to the island


@pytest.mark.xfail(strict=True, reason='RED: the source gives no padding for a map on a white background without alpha')
def test_dilate_source_white_background_is_padded():
    img = island_white()
    out, n, _ = SourceDilate.run(img)
    assert n > 0


def test_dilate_white_background_agr_pads():
    img = island_white()
    out, n = dc.dilate_masked(img, dc.mask_from_background(img, (255, 255, 255)), 4)
    assert n > 0


def test_dilate_keeps_alpha_agr():
    img = island_rgba()
    out, n = dc.dilate_masked(img, dc.mask_from_alpha(img), 3, keep_alpha=True)
    assert out.n == 4 and n > 0
    assert out.px[4 * (12 * 32 + 12) + 3] == 255              # island alpha kept
    assert out.px[4 * (12 * 32 + 11) + 3] == 0                # padded pixel: colour only, alpha 0 (analysis C6)


@pytest.mark.xfail(strict=True, reason='RED: the source output has no alpha channel (uvdilate + -alpha remove)')
def test_dilate_source_keeps_alpha():
    out, n, _ = SourceDilate.run(island_rgba())
    assert out.n == 4


def test_dilate_padding_is_limited_agr():
    img = island_rgba(64, 64)
    mask = dc.mask_from_alpha(img)
    out, n = dc.dilate_masked(img, mask, 2)
    filled = [i for i in range(64 * 64) if not mask[i] and tuple(out.px[3 * i:3 * i + 3]) != (0, 0, 0)]
    assert filled and all(abs(i % 64 - 15.5) <= 3.5 + 2 and abs(i // 64 - 15.5) <= 3.5 + 2 for i in filled)
    far = 3 * (0 * 64 + 0)
    assert tuple(out.px[far:far + 3]) == (0, 0, 0)            # corner beyond the padding stays untouched
    assert n == sum(1 for i in range(64 * 64) if not mask[i] and tuple(out.px[3 * i:3 * i + 3]) != (0, 0, 0))


@pytest.mark.xfail(strict=True, reason='RED: the source expands without a pixel limit to the canvas edge')
def test_dilate_source_padding_limited():
    img = island_rgba(64, 64)
    out, n, _ = SourceDilate.run(img)
    assert tuple(out.px[0:3]) == (0, 0, 0)


def test_dilate_covered_pixels_identical_agr():
    img = island_rgba()
    mask = dc.mask_from_alpha(img)
    out, _ = dc.dilate_masked(img, mask, 6)
    assert dc.covered_identical(img, out, mask)


def test_padding_px_by_profile_agr():
    assert dc.padding_px('vpm', 2048) == 16 and dc.padding_px('vpm', 4096) == 32 and dc.padding_px('npm', 2048) == 8


def test_dilate_empty_mask_is_error_agr():
    img = island_rgba()
    with pytest.raises(ValueError):
        dc.dilate_masked(img, bytearray(32 * 32), 4)
    with pytest.raises(ValueError):
        dc.dilate_options({})


def test_coverage_mask_uv_agr():
    mask = dc.coverage_mask(16, 16, [[(0.25, 0.25), (0.75, 0.25), (0.75, 0.75), (0.25, 0.75)]])
    assert mask[8 * 16 + 8] == 1 and mask[0] == 0 and sum(mask) >= 8 * 8


def _opts(tmp, **kw):
    f = tmp / 'in'
    f.mkdir(exist_ok=True)
    p = f / 'T_A_Diffuse_1.1001.png'
    p.write_bytes(tc.encode_png(kw.pop('img', island_rgba())))
    return dc.dilate_options(dict({'files': [str(p)], 'out': str(tmp / 'out'), 'padding': 4}, **kw)), p


def test_dilate_plan_apply_never_overwrites_agr(tmp_path):
    opts, p = _opts(tmp_path)
    rows = dc.dilate_plan(opts, dc._sibling('agr_tools_tex_core', 'tex_core.py') and (lambda q: Path(q).read_bytes() if os.path.exists(q) else None))
    assert 'code' not in rows[0] and rows[0]['filled'] > 0
    written = dc.write_padded(ec, rows)
    assert Path(written[0]).exists() and Path(written[0]).name == p.name
    again = dc.dilate_plan(opts, lambda q: Path(q).read_bytes() if os.path.exists(q) else None)
    assert again[0]['code'] == 'dilate_exists'                # second run: refused, not overwritten
    assert hashlib.sha256(p.read_bytes()).hexdigest() == hashlib.sha256(tc.encode_png(island_rgba())).hexdigest()


@pytest.mark.xfail(strict=True, reason='RED: the source writes over an existing output silently (L15)')
def test_dilate_source_refuses_existing():
    files = {'out.png': b'old'}
    SourceDilate.write(files, 'out.png', b'new')
    assert files['out.png'] == b'old'


def test_dilate_no_mask_is_a_row_not_a_guess_agr(tmp_path):
    opts, _ = _opts(tmp_path, img=island_white(), mask='auto')
    rows = dc.dilate_plan(opts, lambda q: Path(q).read_bytes())
    assert rows[0]['code'] == 'dilate_no_mask' and 'data' not in rows[0]


def test_dilate_report_valid_agr(tmp_path):
    opts, _ = _opts(tmp_path)
    rows = dc.dilate_plan(opts, lambda q: Path(q).read_bytes())
    rep = dc.dilate_report(ec, 'preview', opts, rows, ec.fingerprint(dc.dilate_state(rows, opts)))
    assert rep['status'] == 'pass' and rep['plan']['done'] and ec.validate_report(rep)
    bad = dc.dilate_plan(dc.dilate_options({'files': [str(tmp_path / 'nope.png')], 'out': str(tmp_path)}), lambda q: None)
    rep2 = dc.dilate_report(ec, 'preview', {}, bad, 'x')
    assert rep2['status'] == 'fail' and rep2['plan']['skipped']


# ======================= udim.plugs ======================================================================
SQUARE = [(0, 0, 0), (2, 0, 0), (2, 0, 3), (0, 0, 3)]      # a wall face 2 x 3 m in XZ


class SourcePlugs:
    """GridUVLayout22 layoutPlugs/runPlugs as measured (T02): square 0.05 at the tile centre, UDIM 1000+matID without a
    range check, and a `classOf node` check that refuses the second run (the node is a PolyMeshObject after the first)."""
    runs = 0

    @classmethod
    def run(cls, faces, node_class='Editable_Poly'):
        if node_class != 'Editable_Poly':
            raise RuntimeError('runPlugs: object is not an Editable_Poly')
        cls.runs += 1
        return [{'udim': 1000 + f['matid']} for f in faces], 'PolyMeshObject'


def test_plug_island_square_and_centre_agr():
    uv = pc.plug_uv(SQUARE, 1003)
    assert pc.plug_check([uv], 1003)
    us = [p[0] for p in uv]
    assert abs((max(us) - min(us)) - 0.05) < 1e-9 or abs((max(p[1] for p in uv) - min(p[1] for p in uv)) - 0.05) < 1e-9


def test_plug_tile_offset_agr():
    assert pc.tile_offset(1001) == (0, 0) and pc.tile_offset(1011) == (0, 1) and pc.tile_offset(1012) == (1, 1)
    uv = pc.plug_uv(SQUARE, 1012)
    assert 1.4 < sum(p[0] for p in uv) / 4 < 1.6 and 1.4 < sum(p[1] for p in uv) / 4 < 1.6


def test_plug_second_run_works_agr():
    faces = [{'face': 1, 'matid': 3, 'verts': SQUARE}]
    o = pc.plug_options({})
    assert pc.plug_plan(faces, o) == pc.plug_plan(faces, o)         # idempotent, no class gate


@pytest.mark.xfail(strict=True, reason='RED: runPlugs refuses its own second run (classOf node is PolyMeshObject)')
def test_plug_source_second_run():
    faces = [{'face': 1, 'matid': 3, 'verts': SQUARE}]
    _, cls = SourcePlugs.run(faces)
    SourcePlugs.run(faces, cls)


def test_plug_work_id_refused_agr():
    o = pc.plug_options({})
    plan = pc.plug_plan([{'face': 1, 'matid': 1005, 'verts': SQUARE}, {'face': 2, 'matid': 2, 'verts': SQUARE}], o)
    assert [f['face'] for f in plan['faces']] == [2] and plan['skipped'][0]['code'] == 'plug_matid'


@pytest.mark.xfail(strict=True, reason='RED: the source takes UDIM = 1000 + matID for a work ID 1005 without a range check')
def test_plug_source_range_check():
    out, _ = SourcePlugs.run([{'face': 1, 'matid': 1005}])
    assert out[0]['udim'] <= 1100


def test_plug_degenerate_and_empty_agr():
    o = pc.plug_options({})
    plan = pc.plug_plan([{'face': 1, 'matid': 1, 'verts': [(0, 0, 0), (1, 0, 0), (2, 0, 0)]}], o)
    assert plan['faces'] == [] and plan['skipped'][0]['code'] == 'plug_degenerate'
    with pytest.raises(ValueError):
        pc.plug_plan([], o)


def test_plug_fixed_tile_and_occupied_agr():
    o = pc.plug_options({'fixed_udim': 1003, 'occupied': {1003: True}})
    plan = pc.plug_plan([{'face': 1, 'matid': 9, 'verts': SQUARE}, {'face': 2, 'matid': 4, 'verts': SQUARE}], o)
    assert {f['udim'] for f in plan['faces']} == {1003} and plan['ambiguous']


# ======================= vpmmaps =========================================================================
LIB = {3: {'library_id': 3, 'key': 'ral_9003', 'rgb_srgb': [240, 240, 240], 'roughness': 0.5, 'metallic': 0.0,
           'emissive': 0.0, 'recipe': 'solid'},
       7: {'library_id': 7, 'key': 'metal_grey', 'rgb_srgb': [120, 125, 130], 'roughness': 0.3, 'metallic': 1.0,
           'emissive': 0.0, 'recipe': 'solid'},
       12: {'library_id': 12, 'key': 'ral_7016', 'rgb_srgb': [56, 62, 66], 'roughness': 0.7, 'metallic': 0.0,
            'emissive': 0.1, 'recipe': 'solid'},
       31: {'library_id': 31, 'key': 'glass', 'rgb_srgb': [90, 110, 120], 'roughness': 0.05, 'metallic': 0.2,
            'emissive': 0.0, 'recipe': 'solid'}}
TABLE = {'SM_Addr_Main': {3: 1001, 7: 1002, 12: 1003, 31: 1004}}


class SourceMaps:
    """GeoAGR Render Material as measured in L15: UDIM = ID + 1000, slot `_1`, ERM from separate maps, silent overwrite,
    a ready ERM that is not 256 gives no ERM file, flat normal 127/127/255 at 512."""

    @staticmethod
    def udim(mat_id):
        return mat_id + 1000

    @staticmethod
    def erm_for_ready(size):
        return size == 256

    @staticmethod
    def flat_normal(size):
        return (127, 127, 255) if size == 512 else (128, 128, 255)


def test_udim_dense_per_mesh_agr(tmp_path):
    r = vc.build_maps(TABLE, LIB, str(tmp_path))
    assert sorted({m['udim'] for m in r['maps']}) == [1001, 1002, 1003, 1004]
    assert len(r['maps']) == 12 and not r['skipped']
    assert sorted(os.listdir(tmp_path))[0] == 'T_Addr_Diffuse_1.1001.png'


@pytest.mark.xfail(strict=True, reason='RED: the source numbers UDIM = library ID + 1000 (ID 31 -> 1031, with gaps)')
def test_source_udim_dense():
    assert sorted(SourceMaps.udim(i) for i in (3, 7, 12, 31)) == [1001, 1002, 1003, 1004]


def test_udim_per_mesh_starts_1001_both_meshes_agr(tmp_path):
    table = {'SM_Addr_Main': {3: 1001, 7: 1002}, 'SM_Addr_MainGlass': {31: 1001}}
    r = vc.plan_maps(table, LIB, str(tmp_path), {'slot': {'SM_Addr_MainGlass': 2}})
    names = sorted(m['name'] for m in r['maps'])
    assert 'T_Addr_Diffuse_1.1001.png' in names and 'T_Addr_Diffuse_2.1001.png' in names and not r['skipped']
    clash = vc.plan_maps(table, LIB, str(tmp_path))
    assert any('requested twice' in s['reason'] for s in clash['skipped'])   # no silent overwrite of 1001


def test_erm_channels_from_record_agr(tmp_path):
    r = vc.build_maps(TABLE, LIB, str(tmp_path))
    erm = next(m for m in r['maps'] if m['kind'] == 'ERM' and m['udim'] == 1002)
    img = tc.decode_png(Path(erm['path']).read_bytes())[0]
    assert tuple(img.px[0:3]) == (0, 77, 255)                 # emissive 0, roughness 0.3, metallic 1: metal not lost
    assert abs(img.px[0] - 0) <= 1 and abs(img.px[1] - 0.3 * 255) <= 1 and abs(img.px[2] - 255) <= 1


def test_diffuse_is_record_colour_agr(tmp_path):
    r = vc.build_maps(TABLE, LIB, str(tmp_path))
    d = next(m for m in r['maps'] if m['kind'] == 'D' and m['udim'] == 1001)
    assert tuple(tc.decode_png(Path(d['path']).read_bytes())[0].px[0:3]) == (240, 240, 240)


def test_normal_flat_at_any_size_agr(tmp_path):
    for size in (256, 512):
        out = tmp_path / str(size)
        r = vc.build_maps({'SM_Addr_Main': {3: 1001}}, LIB, str(out), {'size': size})
        n = next(m for m in r['maps'] if m['kind'] == 'N')
        assert tuple(tc.decode_png(Path(n['path']).read_bytes())[0].px[0:3]) == (128, 128, 255)


@pytest.mark.xfail(strict=True, reason='RED: the source normal is 127/127/255 at 512 (L15)')
def test_source_flat_normal_512():
    assert SourceMaps.flat_normal(512) == (128, 128, 255)


def test_ready_erm_any_size_passes_agr(tmp_path):
    ready = tmp_path / 'ready_erm_512.png'
    data = tc.solid_png(512, (0, 90, 200))
    ready.write_bytes(data)
    r = vc.build_maps({'SM_Addr_Main': {3: 1001}}, LIB, str(tmp_path / 'o'), {'ready_erm': {3: str(ready)}})
    erm = next(m for m in r['maps'] if m['kind'] == 'ERM')
    assert Path(erm['path']).read_bytes() == data and erm['sha256'] == hashlib.sha256(data).hexdigest()


@pytest.mark.xfail(strict=True, reason='RED: a ready ERM of 512 gives no ERM file in the source (L15)')
def test_source_ready_erm_512():
    assert SourceMaps.erm_for_ready(512)


def test_supplied_normal_passes_unchanged_agr(tmp_path):
    nm = tmp_path / 'n.png'
    data = tc.encode_png(img_rgb(16, 16, lambda x, y: (x * 15, y * 15, 200)))
    nm.write_bytes(data)
    r = vc.build_maps({'SM_Addr_Main': {3: 1001}}, LIB, str(tmp_path / 'o'), {'ready_normal': {3: str(nm)}})
    n = next(m for m in r['maps'] if m['kind'] == 'N')
    assert Path(n['path']).read_bytes() == data


def test_deterministic_and_no_overwrite_agr(tmp_path):
    a = vc.plan_maps(TABLE, LIB, str(tmp_path / 'a'))
    b = vc.plan_maps(TABLE, LIB, str(tmp_path / 'b'))
    assert [m['sha256'] for m in a['maps']] == [m['sha256'] for m in b['maps']]
    vc.build_maps(TABLE, LIB, str(tmp_path / 'a'))
    again = vc.build_maps(TABLE, LIB, str(tmp_path / 'a'))
    assert again['maps'] == [] and len(again['skipped']) == 12 and all('exists' in s['reason'] for s in again['skipped'])
    v = vc.build_maps(TABLE, LIB, str(tmp_path / 'a'), {'on_exists': 'version'})
    assert len(v['maps']) == 12 and all('_v002' in m['path'] for m in v['maps'])


def test_missing_base_map_is_skipped_not_empty_agr(tmp_path):
    lib = {5: {'library_id': 5, 'key': 'panel_grey', 'rgb_srgb': [200, 200, 200], 'roughness': 0.6, 'metallic': 0.0,
               'emissive': 0.0, 'recipe': 'greyscale_mask', 'base_map': 'panels.png'}}
    r = vc.build_maps({'SM_Addr_Main': {5: 1001}}, lib, str(tmp_path / 'o'), {'map_dir': str(tmp_path / 'none')})
    assert {s['kind'] for s in r['skipped']} == {'D', 'N'} and [m['kind'] for m in r['maps']] == ['ERM']
    assert all('nothing guessed' in s['reason'] for s in r['skipped'])


def test_mask_recipe_builds_relief_normal_agr(tmp_path):
    mask = tc.encode_png(img_rgb(8, 8, lambda x, y: (255, 255, 255) if x >= 4 else (0, 0, 0)))
    (tmp_path / 'm').mkdir()
    (tmp_path / 'm' / 'panels.png').write_bytes(mask)
    lib = {5: {'library_id': 5, 'key': 'panel_grey', 'rgb_srgb': [200, 200, 200], 'roughness': 0.6, 'metallic': 0.0,
               'emissive': 0.0, 'recipe': 'greyscale_mask', 'base_map': 'panels.png'}}
    r = vc.build_maps({'SM_Addr_Main': {5: 1001}}, lib, str(tmp_path / 'o'), {'map_dir': str(tmp_path / 'm'), 'size': 256})
    n = next(m for m in r['maps'] if m['kind'] == 'N')
    img = tc.decode_png(Path(n['path']).read_bytes())[0]
    assert tuple(img.px[3:6]) == (128, 128, 255)             # flat region (x=1)
    assert img.px[3 * 3] != 128                              # the edge column of the mask tilts the normal
    d = next(m for m in r['maps'] if m['kind'] == 'D')
    assert tc.decode_png(Path(d['path']).read_bytes())[0].px[3 * 7:3 * 7 + 3] == bytes([200, 200, 200])


def test_bad_inputs_agr(tmp_path):
    with pytest.raises(ValueError):
        vc.build_maps({}, LIB, str(tmp_path))
    with pytest.raises(ValueError):
        vc.build_maps({'SM_Addr_Main': {3: 1001, 7: 1003}}, LIB, str(tmp_path))      # gap
    r = vc.plan_maps({'SM_Addr_Main': {99: 1001}}, LIB, str(tmp_path))
    assert r['skipped'][0]['reason'].startswith('library id 99')


# ======================= bitmap enumerator ===============================================================
TREE = {'name': 'M_Addr', 'subs': [
    {'id': 1, 'material': {'name': 'M_Addr_1', 'subs': [], 'maps': [
        {'slot': 'Diffuse Color', 'name': 'd', 'file': 'C:/m/T_A_Diffuse_1.1001.png', 'children': []},
        {'slot': 'Bump', 'name': 'b', 'file': None, 'children': [
            {'name': 'mix', 'subs': [], 'maps': [{'slot': 'Color #1', 'name': 'n', 'file': 'C:/m/T_A_Normal_1.1001.png',
                                                   'children': []}]}]}]}},
    {'id': 2, 'material': {'name': 'M_Addr_2', 'subs': [], 'maps': []}}], 'maps': []}


def test_enumerator_ids_slots_udim_agr():
    rows = tc.material_bitmaps(TREE)
    assert [(r['matid'], r['udim'], r['path'].rsplit('/', 1)[1]) for r in rows] == [
        (1, 1001, 'T_A_Diffuse_1.1001.png'), (1, 1001, 'T_A_Normal_1.1001.png')]
    assert rows[1]['slot'] == 'Bump' and rows[0]['material'] == 'M_Addr'      # nested map keeps the outer slot
    assert set(tc.bitmaps_by_id(rows)) == {1}


def test_dilate_report_names_owner_nodes_agr(tmp_path):
    opts, p = _opts(tmp_path, owners={'T_A_Diffuse_1.1001.png': [[11, 'SM_A_Main'], [12, 'SM_A_Glass']]})
    rows = dc.dilate_plan(opts, lambda q: Path(q).read_bytes())
    rep = dc.dilate_report(ec, 'preview', opts, rows, 'h')
    assert [o['name'] for o in rep['objects']] == ['SM_A_Main', 'SM_A_Glass'] and rep['status'] == 'pass'
    opts2, _ = _opts(tmp_path, img=island_white(), mask='alpha', owners={'T_A_Diffuse_1.1001.png': [[11, 'SM_A_Main']]})
    rep2 = dc.dilate_report(ec, 'preview', opts2, dc.dilate_plan(opts2, lambda q: Path(q).read_bytes()), 'h')
    assert rep2['status'] == 'fail' and rep2['objects'][0]['findings'][0]['code'] == 'dilate_no_mask'


# ======================= polygon fragment / native script (a syntax error cost one runner job) ===============
def test_station_builder_and_native_script_compile_agr():
    import ast
    for rel in ('test-polygon/stations/N_build.py', 'tests/max_tools/run_agr_tools_vpm_maps_native.py'):
        ast.parse((ROOT / rel).read_text(encoding='utf-8'), rel)
    nb = _load(ROOT / 'test-polygon/stations/N_build.py', 'n_build_t')
    ok, white = tc.decode_png(nb.png('rgba_island'))[0], tc.decode_png(nb.png('rgb_white_island'))[0]
    assert ok.n == 4 and white.n == 3 and dc.mask_from_alpha(ok).count(1) == 64
    assert dc.mask_from_background(white, (255, 255, 255)).count(1) == 64


def test_station_fragment_has_pass_and_fail_per_button_agr():
    import json
    frag = json.loads((ROOT / 'test-polygon/stations/N.json').read_text(encoding='utf-8'))
    assert [s['button'] for s in frag['stations']] == ['tex.dilate', 'udim.plugs']
    for st in frag['stations']:
        assert {e['expect'] for e in st['expected']} == {'pass', 'fail'}


def test_bitarray_items_shapes_agr():
    um = _load(PKG / 'udimplug_max.py', 'agr_tools_udimplug_max_t')
    assert um._selected([0, 0, 0, 0, 0, 0], 6) == set()                   # per-element 0/1: empty stays empty
    assert um._selected([False, True, False, True, False, False], 6) == {2, 4}
    assert um._selected([2, 4], 6) == {2, 4}                              # indices of the set bits
