"""new-case: #1024 branch Q - npm.to_vpm (1.0.24) and udim.udims_to_ids (1.0.25) cores, glue loading, stations.

Every named defect is a pair: the source behaviour model (GeoAGR, read from versions/13.64 of GeoAGR-private and cited
by line only) is RED on the requirement, the AGR core is GREEN. Lab L11: docs/experiments/npm.to_vpm.md.
"""
import copy
import importlib.util
import json
import math
import struct
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
AT = ROOT / 'adapters' / 'max' / 'agr_tools'
ST = ROOT / 'test-polygon' / 'stations'


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


C = _load(AT / 'npm2vpm_core.py', 'agr_test_npm2vpm_core')
V = _load(AT / 'udimview_core.py', 'agr_test_udimview_core')
G = _load(AT / 'windowgen_core.py', 'agr_test_windowgen_core_q')
TQ = _load(AT / 'texqa_core.py', 'agr_test_texqa_core_q')
QB = _load(ST / 'Q_build.py', 'agr_test_Q_build')


@pytest.fixture(scope='module')
def lib_types():
    lib = G.load_library(str(ROOT / 'library' / 'windows'))
    offer = sorted(G.offerable(G.library_report(lib['types'], lib['standard'])))
    return [{'id': t, 'width_m': lib['by_id'][t]['width_m'], 'height_m': lib['by_id'][t]['height_m']} for t in offer]


@pytest.fixture(scope='module')
def built():
    return {layout: QB.npm(layout=layout) for layout in ('islands', 'stack')}


# ---- main path: the correspondence table ------------------------------------------------------------------------
@pytest.mark.parametrize('layout', ['islands', 'stack'])
def test_table_returns_vpm_uv_udim_and_separate_meshes(built, layout):
    """Acceptance 1 (lab L11): UV back = VPM UV +-1e-5 (here exact), every triangle in its UDIM, body and glass as
    separate meshes each numbered from 1001 (owner answer V9)."""
    mesh, rows, p = built[layout]
    vpm = QB.vpm()
    plan = C.plan(mesh, {}, C.table_rows(rows))
    assert plan['mode'] == 'table' and not plan['findings'], plan['findings']
    assert set(plan['parts']) == {'body', 'glass'}
    src = p['combined']['src']
    worst = 0.0
    for part, pm in plan['parts'].items():
        for lf, f in enumerate(pm['faces']):
            mi, face = src[f]
            m = vpm[mi]
            assert m['part'] == part
            want = [m['uvs'][i] for i in m['uv_tris'][face]]
            got = [pm['uvs'][i] for i in pm['uv_tris'][lf]]
            for a, b in zip(got, want):
                worst = max(worst, abs(a[0] - b[0]), abs(a[1] - b[1]))
            udim = m['udim_table'][str(m['mat_ids'][face])] if str(m['mat_ids'][face]) in m['udim_table'] else \
                m['udim_table'][m['mat_ids'][face]]
            assert C.in_tile(got, udim)
    assert worst <= 1e-9, worst
    assert plan['summary']['udim'] == {'3': 1001, '7': 1002, '31': 1001}
    assert sorted(set(plan['parts']['glass']['mat_ids'])) == [31]
    mats = C.materials_of(plan, 'body', 'X')
    assert {k: v['name'] for k, v in mats.items()} == {3: 'M_lib_3', 7: 'M_lib_7'}


def test_table_rows_read_the_npm_build_sidecar(built):
    mesh, rows, p = built['islands']
    doc = {'schema': 1, 'tool': 'npm.build', 'table': rows, 'atlas_px': p['atlas']['size']}
    assert C.table_rows(json.loads(json.dumps(doc))) == C.table_rows(rows)
    with pytest.raises(ValueError, match='no rows'):
        C.table_rows({'table': []})
    bad = copy.deepcopy(rows)
    bad[0]['scale'] = [0.0, 1.0]
    with pytest.raises(ValueError, match='scale'):
        C.table_rows(bad)
    both = copy.deepcopy(rows) + [dict(copy.deepcopy(rows[0]), key='x', part='glass')]
    with pytest.raises(ValueError, match='body and glass'):
        C.table_rows(both)


def test_table_fail_closed_no_row_region_udim(built):
    mesh, rows, _p = built['stack']
    m = QB.add_no_row_quad(copy.deepcopy(mesh))
    plan = C.plan(m, {}, C.table_rows(rows))
    codes = {f[0] for f in plan['findings']}
    assert codes == {'table_no_row'} and C.blocking(plan['findings'])
    # a face of id 3 moved out of every cell of id 3
    m2 = copy.deepcopy(mesh)
    f = m2['mat_ids'].index(3)
    for i in m2['uv_tris'][f]:
        m2['uvs'][i] = [0.999, 0.999]
    assert 'table_region' in {x[0] for x in C.plan(m2, {}, C.table_rows(rows))['findings']}
    # a row whose UDIM is not where its UV goes back
    r2 = copy.deepcopy(rows)
    for r in r2:
        if r['library_id'] == 7:
            r['udim'] = 1005
    assert {x[0] for x in C.plan(mesh, {}, C.table_rows(r2))['findings']} == {'udim_mismatch'}
    # mode table without a table
    plan = C.plan(mesh, {'mode': 'table'}, None)
    assert [x[0] for x in plan['findings']] == ['table_invalid']


def test_options_and_empty_input():
    assert C.options({})['window_tol_m'] == 0.05 and C.options({})['mode'] == 'auto'
    for bad in ({'mode': 'x'}, {'window_tol_m': 0}, {'window_ids': [0]}, {'crop_pad_px': -1}, {'foo': 1},
                {'mode': 'regions', 'table': []}, {'window_types': []}):
        with pytest.raises(ValueError):
            C.options(bad)
    with pytest.raises(ValueError, match='no faces'):
        C.plan({'verts': [], 'local': [], 'tris': [], 'mat_ids': [], 'uvs': [], 'uv_tris': []}, {})


# ---- windows ----------------------------------------------------------------------------------------------------
def _with_planes(noise=0.004, scale=1.0):
    m = {'verts': [], 'tris': [], 'mat_ids': [], 'uvs': [], 'uv_tris': []}
    planes = QB.window_planes(noise=noise)
    QB.add_planes(m, planes)
    m['verts'] = [[c * scale for c in v] for v in m['verts']]
    m['local'] = m['verts']
    return m, planes


def test_windows_recognised_100_percent_with_90_deg_and_no_type(lib_types):
    """Acceptance 4: 12 KPP1-W01..03 planes + one turned 90 deg + one without a type, noise 4 mm: 100 %, the turned one
    with its rotation, the untyped one `none`; centre +-5 mm, normal <= 0.5 deg."""
    m, planes = _with_planes()
    wins, findings = C.window_plan(m, list(range(len(m['tris']))), lib_types, 0.05)
    assert len(wins) == len(planes) == 14
    for w, exp in zip(wins, planes):
        assert w['match']['type'] == exp['type'], (exp, w['match'])
        assert w['match']['rotated'] == exp['rotated']
        assert math.dist(w['frame']['origin'], exp['centre']) <= 0.005
        cos = sum(a * b for a, b in zip(w['frame']['z'], exp['normal']))
        assert math.degrees(math.acos(min(1.0, cos))) <= 0.5
    assert [f[0] for f in findings] == ['window_no_type']


def test_window_rows_place_the_type_on_the_plane(lib_types):
    m, planes = _with_planes()
    wins, _ = C.window_plan(m, list(range(len(m['tris']))), lib_types, 0.05)
    wp = _load(AT / 'winplace_core.py', 'agr_test_winplace_core_q')
    for w, exp in zip(wins, planes):
        if not exp['type']:
            continue
        W, H = QB.KPP1[exp['type']]
        size = [W, 0.1, H]
        rows = C.window_rows(w, size)
        c = wp.apply_rows(rows, [W / 2, 0.05, H / 2])
        assert math.dist(c, exp['centre']) <= 1e-6
        assert wp.angle_deg(wp.face_normal_world(rows), exp['normal']) <= 1e-6
        x = rows[0]
        # the type width runs along the plane width, or along its height when turned 90 deg
        along = w['frame']['y'] if exp['rotated'] else w['frame']['x']
        assert abs(abs(sum(a * b for a, b in zip(x, along))) - 1.0) <= 1e-9
        det = (rows[0][0] * (rows[1][1] * rows[2][2] - rows[1][2] * rows[2][1])
               - rows[0][1] * (rows[1][0] * rows[2][2] - rows[1][2] * rows[2][0])
               + rows[0][2] * (rows[1][0] * rows[2][1] - rows[1][1] * rows[2][0]))
        assert abs(det - 1.0) <= 1e-9


def _geoagr_window_match(w_su, h_su, types_su, thr=0.2):
    """Source model, principle of Geo Window Placer (GeoAGR.ms:57117-57124): |dw| + |dh| < 0.2 in SYSTEM units, no
    90 deg variant."""
    best = None
    for tid, (W, H) in types_su.items():
        d = abs(w_su - W) + abs(h_su - H)
        if d < thr and (best is None or d < best[0]):
            best = (d, tid)
    return best[1] if best else None


@pytest.mark.parametrize('unit', [1.0, 100.0])
def test_window_threshold_in_metres_red_green(lib_types, unit):
    """Defect (lab L11): the GeoAGR principle (threshold 0.2 system units, no 90 deg) finds 13/14 in metres and 1/14
    in cm (RED); the AGR core matches in metres per axis with the 90 deg variant: 14/14 in both (GREEN)."""
    _m, planes = _with_planes()
    types_su = {t: (W * unit, H * unit) for t, (W, H) in QB.KPP1.items()}
    src = [_geoagr_window_match(p['w'] * unit, p['h'] * unit, types_su) == p['type'] for p in planes]
    assert sum(src) < len(planes)  # RED: the 90 deg plane is never found
    if unit == 100.0:  # in cm 0.2 cm is below the 4 mm noise: most typed planes are lost
        assert sum(ok for ok, p in zip(src, planes) if p['type']) <= 4
    # GREEN: the glue gives the core metres (units.SystemScale), so the cm scene is the metre scene
    got = [C.match_type(p['w'], p['h'], [t for t in lib_types if t['id'] in QB.KPP1], 0.05) for p in planes]
    assert all((g['type'] if g['status'] == 'ok' else None) == p['type'] and g['rotated'] == p['rotated']
               for g, p in zip(got, planes))


def test_window_ambiguous_same_size_types():
    types = [{'id': 'WT-07', 'width_m': 2.514, 'height_m': 2.614}, {'id': 'WT-10', 'width_m': 2.514,
                                                                    'height_m': 2.614}]
    m = C.match_type(2.515, 2.613, types, 0.05)
    assert m['status'] == 'ambiguous' and m['others'] == ['WT-07', 'WT-10']
    sq = C.match_type(1.5, 1.5, [{'id': 'SQ', 'width_m': 1.5, 'height_m': 1.5}], 0.05)
    assert sq['status'] == 'ok' and not sq['rotated']


def test_window_frame_refuses_horizontal_and_nonplanar(lib_types):
    m = {'verts': [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], 'tris': [[0, 1, 2], [0, 2, 3]], 'mat_ids': [50, 50]}
    wins, f = C.window_plan(m, [0, 1], lib_types, 0.05)
    assert [x[0] for x in f] == ['window_frame'] and 'horizontal' in f[0][2]
    m['verts'] = [[0, 0, 0], [1, 0, 0], [1, 0.05, 1], [0, 0, 1]]
    _w, f = C.window_plan(m, [0, 1], lib_types, 0.05)
    assert [x[0] for x in f] == ['window_frame'] and 'planar' in f[0][2]


def test_windows_are_left_out_of_the_vpm_parts(built, lib_types):
    mesh, rows, _p = built['stack']
    m = QB.add_planes(copy.deepcopy(mesh), QB.window_planes(untyped=False))
    plan = C.plan(m, {'window_ids': [QB.WINDOW_ID]}, C.table_rows(rows), None, lib_types)
    assert {x[0] for x in plan['findings']} == set()
    assert all(QB.WINDOW_ID not in pm['mat_ids'] for pm in plan['parts'].values())
    assert plan['summary']['windows']['by_status'] == {'ok': 13}
    with pytest.raises(ValueError, match='window library'):
        C.plan(m, {'window_ids': [QB.WINDOW_ID]}, C.table_rows(rows), None, [])


# ---- without a table: regions (atlas.unatlas) -------------------------------------------------------------------
def _atlas_npm():
    return QB.atlas_npm(), QB.ATLAS_CELLS


def _geoagr_unatlas(mesh, w, h, padding=0.05):
    """Source model of GeoAGR UnAtlas for a multi-ID object (GeoAGR.ms:29639-29664 stacks by ID, :29806-29837 crop,
    :29864-29882 UV, :29888 outside the first UDIM). Per stack (ID order): {'id', 'udim', 'out_px', 'err_px',
    'skipped'}; err_px = atlas-pixel distance between the crop pixel and the new UV of the same atlas points."""
    out = []
    for i, mid in enumerate(sorted(set(mesh['mat_ids'])), 1):
        pts = [mesh['uvs'][t] for f, x in enumerate(mesh['mat_ids']) if x == mid for t in mesh['uv_tris'][f]]
        mnu, mxu = min(p[0] for p in pts), max(p[0] for p in pts)
        mnv, mxv = min(p[1] for p in pts), max(p[1] for p in pts)
        if mnu < 0 or mxu > 1 or mnv < 0 or mxv > 1:
            out.append({'id': mid, 'udim': None, 'skipped': True, 'finding': None})  # Listener line only
            continue
        wu, hv = mxu - mnu, mxv - mnv
        ox, oy, ow, oh = mnu * w, (1 - mxv) * h, wu * w, hv * h
        px, py = ow * padding, oh * padding
        x1, y1 = int(ox - px), int(oy - py)
        cw, ch = int(ow + 2 * px), int(oh + 2 * py)
        x1, y1 = max(x1, 0), max(y1, 0)
        cw, ch = min(cw, int(w - x1)), min(ch, int(h - y1))
        sq = max(cw, ch)
        ts = (1.0 / max(wu, hv)) * (1 - 2 * padding)
        offx = padding + ((1 - 2 * padding) - wu * ts) * 0.5
        offy = padding + ((1 - 2 * padding) - hv * ts) * 0.5
        err = 0.0
        for u, v in pts:
            nu, nv = (u - mnu) * ts + offx, (v - mnv) * ts + offy
            ex = (u * w - x1) + (sq - cw) / 2.0  # gravity center extent
            ey = ((1 - v) * h - y1) + (sq - ch) / 2.0
            err = max(err, abs(ex - nu * sq), abs(ey - (1 - nv) * sq))
        out.append({'id': mid, 'udim': 1001 + (i - 1) % 10 + 10 * ((i - 1) // 10), 'out_px': 2048,
                    'err_px': err, 'skipped': False})
    return out


def test_regions_id_kept_native_size_one_formula_red_green():
    """Acceptance 2 + plan defects: GeoAGR gives UDIM by stack number (1001..1004 for ids 2, 5, 9, 12), stretches every
    crop to 2048, its crop and UV disagree by > 1 px and the stack outside the first UDIM is skipped without a
    finding (RED). AGR: UDIM = 1000 + ID, crop = region size, error <= 1 px (0 by construction), the stack in atlas
    tile (1, 0) shifted back (GREEN)."""
    m, cells = _atlas_npm()
    src = _geoagr_unatlas(m, 2048, 2048)
    assert [s['udim'] for s in src if not s['skipped']] != [1000 + s['id'] for s in src if not s['skipped']]
    assert all(s['out_px'] == 2048 for s in src if not s['skipped'])
    assert max(s['err_px'] for s in src if not s['skipped']) > 1.0
    assert [s['id'] for s in src if s['skipped']] == [5]
    plan = C.plan(m, {'mode': 'regions'}, None, {'w': 2048, 'h': 2048})
    assert not plan['findings'], plan['findings']
    regs = plan['regions']
    assert {k: r['udim'] for k, r in regs.items()} == {2: 1002, 5: 1005, 9: 1009, 12: 1012}
    for mid, (u0, v0, u1, v1) in cells.items():
        du = int(math.floor(u0))
        x0, x1 = math.floor((u0 - du) * 2048 + 1e-7), math.ceil((u1 - du) * 2048 - 1e-7)
        assert regs[mid]['size_px'][0] == x1 - x0 < 2048
    assert regs[5]['shift_tiles'] == [1, 0]
    assert regs[12]['box_px'][2] == 2048  # at the atlas edge, no clamp mismatch
    assert plan['summary']['crop_error_px'] <= 1e-6
    pm = plan['parts']['body']
    for lf, mid in enumerate(pm['mat_ids']):
        assert C.in_tile([pm['uvs'][i] for i in pm['uv_tris'][lf]], 1000 + mid)
    assert set(pm['mat_ids']) == {2, 5, 9, 12}  # ids stay on their faces


def test_regions_straddle_and_id_range_are_explicit():
    m, _ = _atlas_npm()
    f = m['mat_ids'].index(9)
    m['uvs'][m['uv_tris'][f][1]] = [1.2, 0.5]  # id 9 now crosses u = 1
    m['mat_ids'] += [150, 150]
    m['tris'] += [[0, 1, 2], [0, 2, 3]]
    m['uv_tris'] += [[0, 1, 2], [0, 2, 3]]
    plan = C.plan(m, {'mode': 'regions'}, None, {'w': 1024, 'h': 1024})
    codes = sorted(x[0] for x in plan['findings'])
    assert codes == ['id_range', 'region_straddle'] and C.blocking(plan['findings'])
    miss = C.plan(m, {'mode': 'regions'}, None, None)
    assert [x[0] for x in miss['findings']] == ['atlas_missing']


def test_region_uv_and_crop_are_the_same_pixels():
    w, h = 1000, 600
    pts = [(0.1234, 0.5678), (0.3456, 0.789), (0.2, 0.7)]
    for pad in (0, 3):
        box = C.region_box(pts, w, h, pad)
        for p in pts:
            assert C.crop_error_px(p, box, w, h, 1007) <= 1e-9
            u, v = C.region_uv(p, box, w, h, 1007)
            assert 6 <= u <= 7 and 0 <= v <= 1


def _png(w, h, depth, ctype, rows):
    raw = b''.join(b'\x00' + r for r in rows)
    def ck(k, b):
        return struct.pack('>I', len(b)) + k + b + struct.pack('>I', zlib.crc32(k + b) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + ck(b'IHDR', struct.pack('>IIBBBBB', w, h, depth, ctype, 0, 0, 0)) +
            ck(b'IDAT', zlib.compress(raw)) + ck(b'IEND', b''))


def test_crop_png_keeps_16_bit_pixels():
    """The lab atlas carries a 16-bit coordinate: the crop must keep the source depth and pixels exactly."""
    w, h = 40, 30
    rows = [b''.join(struct.pack('>HHH', x * 1000 + 7, y * 1000 + 3, x * y) for x in range(w)) for y in range(h)]
    data = _png(w, h, 16, 2, rows)
    out = C.crop_png(data, (5, 4, 17, 12))
    assert C.png_size(out) == (12, 8, 16, 2)
    ch = C._chunks(out)
    raw = zlib.decompress(b''.join(b for k, b in ch if k == b'IDAT'))
    stride = 12 * 6
    for y in range(8):
        line = raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)]
        assert line == rows[y + 4][5 * 6:17 * 6]
    # the 16-bit coordinate atlas of the lab: every UV corner of every region reads its own atlas pixel back
    W = 256
    atlas = QB.coord16_png(W, W)
    m = QB.atlas_npm()
    plan = C.plan(m, {'mode': 'regions'}, None, {'w': W, 'h': W})
    worst = 0.0
    pm = plan['parts']['body']
    for mid, reg in plan['regions'].items():
        crop = C.crop_png(atlas, reg['box_px'])
        cw, chh, depth, _ct = C.png_size(crop)
        assert depth == 16 and [cw, chh] == reg['size_px']
        raw = zlib.decompress(b''.join(b for k, b in C._chunks(crop) if k == b'IDAT'))
        tu, tv = C.tile_origin(reg['udim'])
        for lf, fm in enumerate(pm['mat_ids']):
            if fm != mid:
                continue
            for i in pm['uv_tris'][lf]:
                u, v = pm['uvs'][i]
                x = min(cw - 1, int((u - tu) * cw))
                y = min(chh - 1, int((1 - (v - tv)) * chh))
                off = y * (cw * 6 + 1) + 1 + x * 6
                ax, ay = (struct.unpack('>H', raw[off:off + 2])[0] - 16) / 32.0, \
                    (struct.unpack('>H', raw[off + 2:off + 4])[0] - 16) / 32.0
                want_x = (u - tu) * cw + reg['box_px'][0]
                want_y = (1 - (v - tv)) * chh + reg['box_px'][1]
                worst = max(worst, abs(ax + 0.5 - want_x), abs(ay + 0.5 - want_y))
    assert worst <= 1.0, worst
    rgb = TQ.write_png(8, 8, bytes(range(192)), 3)
    small = TQ.read_png(C.crop_png(rgb, (2, 1, 5, 4)))
    assert (small.w, small.h, small.depth) == (3, 3, 8)
    assert small.px[:3] == bytes(range(192))[(1 * 8 + 2) * 3:(1 * 8 + 2) * 3 + 3]
    with pytest.raises(ValueError):
        C.crop_png(rgb, (0, 0, 9, 9))


# ---- udim.udims_to_ids ------------------------------------------------------------------------------------------
def test_udims_to_ids_acceptance():
    """#1024 «редакция 1» 26: faces in 1001, 1002, 1011, U = -0.5 and U = 10.2 -> IDs 1, 2, 11 and two faces (four
    triangles) ambiguous; the mesh (IDs) is not changed."""
    m = QB.udim_plane(bad=True)
    before = copy.deepcopy(m)
    v = V.view(m)
    assert [(t, r['id']) for t, r in v['tiles'].items()] == [(1001, 1), (1002, 2), (1011, 11)]
    assert sorted(f for f, _ in v['ambiguous']) == [6, 7, 8, 9]
    assert [f[0] for f in V.findings_of(v)] == ['udim_ambiguous']
    assert m == before
    ok = V.view(QB.udim_plane())
    assert not V.findings_of(ok) and ok['mismatch'] == [2, 3, 4, 5]  # ids are 1 now: 1002/1011 differ (shown)


def _geoagr_mesh_rule(pts):
    """Source model GeoAGR.ms:41484-41498 (Editable_Mesh): the FIRST UV vertex, floor, ID < 1 clamped to 1."""
    u, v = pts[0]
    tid = (math.floor(u) + 1) + math.floor(v) * 10
    return max(1, tid)


def _geoagr_unwrap_rule(pts):
    """Source model GeoAGR.ms:41449-41452 (Unwrap path): abs(centre as integer) - truncation toward zero."""
    cu = sum(p[0] for p in pts) / len(pts)
    cv = sum(p[1] for p in pts) / len(pts)
    return abs(int(cu)) + 1 + 10 * abs(int(cv))


def test_udims_to_ids_source_defects_red_green():
    neg = [(-0.9, 0.1), (-0.1, 0.1), (-0.1, 0.9)]
    over = [(10.0, 0.1), (10.4, 0.1), (10.4, 0.9)]
    first_on_border = [(1.0, 0.1), (0.2, 0.1), (0.2, 0.9)]  # centroid u 0.47 -> tile 1001, first vertex on u = 1
    # U2 clamp / wrap: RED
    assert _geoagr_mesh_rule(neg) == 1 and _geoagr_unwrap_rule(neg) == 1
    assert _geoagr_mesh_rule(over) == 11
    # U1 first vertex: RED
    assert _geoagr_mesh_rule(first_on_border) == 2
    # GREEN
    assert V.face_tile(neg)[0] is None and V.face_tile(over)[0] is None
    assert V.face_tile(first_on_border) == (1001, None)
    assert V.face_tile([(0.5, 10.5)] * 3)[0] is None  # tile 1101: ID > 100
    with pytest.raises(ValueError):
        V.view({'tris': [[0, 1, 2]], 'mat_ids': [1], 'uvs': None, 'uv_tris': None})
    assert V.options({'faces': [3, 1]}) == {'faces': [1, 3]}
    with pytest.raises(ValueError):
        V.options({'faces': [0]})


# ---- glue, stations, expected -----------------------------------------------------------------------------------
def test_glue_modules_load_and_export_the_functions():
    n = _load(AT / 'npm2vpm_max.py', 'agr_test_npm2vpm_max')
    u = _load(AT / 'udimview_max.py', 'agr_test_udimview_max')
    assert callable(n.npm_to_vpm) and callable(u.udim_udims_to_ids)
    rt = _load(AT / 'runtime.py', 'agr_test_runtime_q')
    assert rt.EDITS_100['npm.to_vpm'] == ('npm2vpm_core.py', 'npm_to_vpm')
    assert 'udim.udims_to_ids' in rt.READ_100 and 'npm.to_vpm' not in rt.READ_100


def test_udims_to_ids_glue_refuses_apply():
    u = _load(AT / 'udimview_max.py', 'agr_test_udimview_max2')
    with pytest.raises(ValueError, match='read-only'):
        u.udim_udims_to_ids(None, 'apply', None, {})


def test_station_fragment_and_options_match_the_builder():
    frag = json.loads((ST / 'Q.json').read_text(encoding='utf-8'))
    assert frag['branch'] == 'Q'
    by = {s['button']: s for s in frag['stations']}
    assert set(by) == {'npm.to_vpm', 'udim.udims_to_ids'}
    for s in by.values():
        assert {e['expect'] for e in s['expected']} == {'pass', 'fail'}
    assert by['npm.to_vpm']['options'] == json.loads(json.dumps(QB.station_options()))


@pytest.mark.parametrize('button', ['npm.to_vpm', 'udim.udims_to_ids'])
def test_station_rows_by_the_cores(button, lib_types):
    frag = json.loads((ST / 'Q.json').read_text(encoding='utf-8'))
    st = [s for s in frag['stations'] if s['button'] == button][0]
    kinds = {o['name']: o['extra']['kind'] for o in st['objects']}
    for exp in st['expected']:
        kind = kinds[exp['name']]
        if button == 'npm.to_vpm':
            o = st['options']
            mesh = QB.station_npm(exp['name'], 'fail' if kind == 'n2v_fail' else 'ok')
            types = [t for t in lib_types if t['id'] in o['window_types']]
            p = C.plan(mesh, o, C.table_rows(o['table']), None, types)
            codes = sorted({f[0] for f in p['findings']})
        else:
            v = V.view(QB.udim_plane(exp['name'], bad=(kind == 'udim_bad')))
            codes = sorted({f[0] for f in V.findings_of(v)})
        assert codes == sorted(exp['codes']) and (exp['expect'] == 'fail') == bool(codes), (exp, codes)


@pytest.mark.parametrize('button', ['npm.to_vpm', 'udim.udims_to_ids'])
def test_expected_json_follows_the_fragment(button):
    frag = json.loads((ST / 'Q.json').read_text(encoding='utf-8'))
    st = [s for s in frag['stations'] if s['button'] == button][0]
    doc = json.loads((ROOT / 'test-polygon' / 'expected' / (button + '.json')).read_text(encoding='utf-8'))
    assert doc['shipped'] is True and doc['tool'] == button and doc['reason'] == ''
    assert doc['objects'] == [{k: e[k] for k in ('name', 'scene', 'expect', 'codes')} for e in st['expected']]
    assert doc['station'] == {'npm.to_vpm': '1.0.24', 'udim.udims_to_ids': '1.0.25'}[button]
