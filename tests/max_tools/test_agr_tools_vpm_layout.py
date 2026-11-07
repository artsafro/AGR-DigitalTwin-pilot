"""new-case: AGR Tools 1.0 (#1024) branch M: vpm.build / udim.rescale / udim.distortion cores, plain pytest.

Every defect of the lab L09 reports (docs/experiments/vpm.build.md, udim.rescale.md, udim.distortion.md; jobs
20261106-020128-4d618c79, -020453-86400856, -020600-4ddad776, -020822-2b518b13, -021049-212901f9) is RED on a
behaviour model of the GeoAGR tool, written from the measurements (no GeoAGR code, #853), and GREEN on the cores
(uvlayout_core, vpm_core, udim10_core). The facade and the plane of the lab are rebuilt by
test-polygon/stations/M_build.py (the same generator feeds the native run and the polygon stations).
"""
import importlib.util
import math
import struct
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'


def _load(path, alias):
    spec = importlib.util.spec_from_file_location(alias, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


lay = _load(PKG / 'uvlayout_core.py', 'agr_tools_uvlayout_core_t')
vc = _load(PKG / 'vpm_core.py', 'agr_tools_vpm_core_t')
u10 = _load(PKG / 'udim10_core.py', 'agr_tools_udim10_core_t')
ec = _load(PKG / 'edit_core.py', 'agr_tools_edit_core_vpm_t')
MB = _load(ROOT / 'test-polygon/stations/M_build.py', 'agr_polygon_M_build_t')
TILE = 3600   # 3.6 m at 1000 px/m (1.0.1 default; was 4096)
STEP = 3.6


def red_green(prop, source, impl):
    assert not prop(source()), 'source model already satisfies the property: not a regression'
    assert prop(impl())


def core_mesh(poly, key=1, name='F'):
    tm, _groups = MB.triangulate(poly)
    return dict(tm, key=key, name=name)


def build(poly, **opts):
    plan = vc.build([core_mesh(poly)], dict({'glass_ids': [MB.GLASS]}, **opts))
    return plan['objects'][0]


def body(obj):
    return next(p for p in obj['parts'] if p['summary']['part'] == 'body')


def frac_seam_px(mesh, pieces, wall_of=None, pairs=None):
    return lay.seam_metric(mesh, pieces, TILE, wall_of, pairs)


# ---- behaviour models of GeoAGR (from the L09 measurements) -------------------------------------------------
def islands_of(uv, faces, mats):
    """Islands = faces of one material on one plane (what Unwrap Tiles treats as an island in mode B)."""
    return {f: (mats[f], tuple(round(c, 3) for c in _plane(uv, f))) for f in faces}


def _plane(uv, f):
    return (0,)


def model_mode_b(mesh, uv):
    """Mode B (`process_and_align_island_universal` GeoAGR.ms:31473-31598): each island (one wall) is moved so its
    UV minimum sits on the tile origin -> a FRACTIONAL shift per island (L09: 945 px seam)."""
    lay_uv, wall_of, _info, pairs = lay.project_k6(mesh, list(range(len(mesh['tris']))), [0, 0, 0], lambda m: STEP)
    groups = {}
    for f, w in wall_of.items():
        groups.setdefault(w, []).append(f)
    out = {}
    for _w, fs in groups.items():
        mu = min(u for f in fs for u, _v in lay_uv[f])
        mv = min(v for f in fs for _u, v in lay_uv[f])
        for f in fs:
            out[f] = [[u - mu, v - mv] for u, v in lay_uv[f]]
    pieces = [{'tri': f, 'w': [[1, 0, 0], [0, 1, 0], [0, 0, 1]], 'uv': out[f], 'mat': mesh['mat_ids'][f]}
              for f in sorted(out)]
    return pieces, wall_of, pairs


def model_rapports(mesh, rapport_m=0.6 * 1.25):
    """Rapports (GeoAGR.ms:32515-32603): each island moved by a whole number of repeats rx (typed by hand) into
    1001: only mod-repeat continuity, by mod UDIM up to 2048 px."""
    uv, wall_of, _info, pairs = lay.project_k6(mesh, list(range(len(mesh['tris']))), [0, 0, 0], lambda m: STEP)
    r = rapport_m / STEP
    groups = {}
    for f, w in wall_of.items():
        groups.setdefault(w, []).append(f)
    out = {}
    for _w, fs in groups.items():
        mu = min(u for f in fs for u, _v in uv[f])
        mv = min(v for f in fs for _u, v in uv[f])
        du, dv = -math.floor(mu / r) * r, -math.floor(mv / r) * r
        for f in fs:
            out[f] = [[u + du, v + dv] for u, v in uv[f]]
    pieces = [{'tri': f, 'w': [[1, 0, 0], [0, 1, 0], [0, 0, 1]], 'uv': out[f], 'mat': mesh['mat_ids'][f]}
              for f in sorted(out)]
    return pieces, wall_of, pairs


def facade_core(**kw):
    return core_mesh(MB.facade(**kw))


# ---- vpm.build: defects of GeoAGR ---------------------------------------------------------------------------
def test_d1_mode_b_fractional_shift_tears_the_seam_ours_is_zero():
    mesh = facade_core(glass=False)

    def ok(res):
        pieces, wall_of, pairs = res
        m = frac_seam_px(mesh, pieces, wall_of, pairs)
        return max(m['internal_max'], m['chain_max']) <= lay.SEAM_TOL_PX

    def impl():
        uv, wall_of, _i, pairs = lay.project_k6(mesh, list(range(len(mesh['tris']))), [0, 0, 0], lambda m: STEP)
        pieces = lay.shift_into_tiles(lay.cut_grid(uv, dict(enumerate(mesh['mat_ids']))), {3: 1001, 7: 1002})
        return pieces, wall_of, pairs
    red_green(ok, lambda: model_mode_b(mesh, None), impl)


def test_d2_rapports_whole_repeats_are_not_whole_udims_ours_is_zero_mod_1():
    mesh = facade_core(glass=False)

    def ok(res):
        pieces, wall_of, pairs = res
        m = frac_seam_px(mesh, pieces, wall_of, pairs)
        return m['chain_max'] <= lay.SEAM_TOL_PX and m['internal_max'] <= lay.SEAM_TOL_PX

    def impl():
        obj = build(MB.facade(glass=False))
        s = body(obj)['summary']
        return s
    pieces, wall_of, pairs = model_rapports(mesh)
    assert not ok((pieces, wall_of, pairs))
    s = impl()
    assert s['seam_internal_max_px'] <= lay.SEAM_TOL_PX and s['seam_chain_max_px'] <= lay.SEAM_TOL_PX


def test_d3_tile_per_material_dense_from_1001():
    poly = MB.facade(glass=False)

    def ok(tiles_by_mat):
        return tiles_by_mat == {3: {1001}, 7: {1002}}

    def source():  # GeoAGR: everything lands in 1001 (and 1002 by the minimum snap)
        return {3: {1001}, 7: {1001}}

    def impl():
        geo = body(build(poly))['geometry']
        out = {}
        for f, t in enumerate(geo['uv_tris']):
            uv = [geo['uvs'][i] for i in t]
            cu, cv = lay._cell(uv)
            out.setdefault(geo['mat_ids'][f], set()).add(lay.udim_of_cell(cu, cv))
        return out
    red_green(ok, source, impl)


def test_d4_islands_across_a_tile_line_are_cut_not_left_sticking_out():
    mesh = facade_core(glass=False)
    uv, _w, _i, _p = lay.project_k6(mesh, list(range(len(mesh['tris']))), [0, 0, 0], lambda m: STEP)

    def ok(pieces):
        return not lay.crossing_pieces(pieces)

    def source():  # whole triangles shifted by the floor of their own minimum (no cut)
        out = []
        for f in sorted(uv):
            mu, mv = min(u for u, _ in uv[f]), min(v for _, v in uv[f])
            out.append({'tri': f, 'uv': [[u - math.floor(mu), v - math.floor(mv)] for u, v in uv[f]],
                        'mat': mesh['mat_ids'][f]})
        return out
    red_green(ok, source, lambda: lay.shift_into_tiles(lay.cut_grid(uv, dict(enumerate(mesh['mat_ids']))),
                                                       {3: 1001, 7: 1002}))


def test_d5_fit_all_to_udim_rescales_the_texel_ours_keeps_it_within_1_percent():
    poly = MB.facade(glass=False)

    def ok(texel):
        return all(abs(lo / (TILE / STEP) - 1) <= 0.01 and abs(hi / (TILE / STEP) - 1) <= 0.01
                   for lo, hi in texel.values())

    def source():  # UVs Grouper `fit_all_to_udim` (:20050): bounding box of each id fitted into 0..1 (x0.21)
        mesh = core_mesh(poly)
        uv, _w, _i, _p = lay.project_k6(mesh, list(range(len(mesh['tris']))), [0, 0, 0], lambda m: STEP)
        out = {}
        for mid in (3, 7):
            fs = [f for f in uv if mesh['mat_ids'][f] == mid]
            us = [u for f in fs for u, _ in uv[f]]
            vs = [v for f in fs for _, v in uv[f]]
            k = 1.0 / max(max(us) - min(us), max(vs) - min(vs))
            out[mid] = (TILE / STEP * k, TILE / STEP * k)
        return out

    def impl():
        s = body(build(poly))['summary']
        return {int(k): tuple(v) for k, v in s['texel_px_per_m'].items()}
    red_green(ok, source, impl)


def test_d6_d7_the_glue_copies_and_never_clears_undo_or_collapses_an_original():
    text = (PKG / 'vpm_max.py').read_text(encoding='utf-8')
    code = '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith(('#', '"', "'")))
    body_ = code.split('"""', 2)[-1]
    assert 'export_copies' in body_
    assert 'clearUndoBuffer(' not in body_ and 'rt.clearUndoBuffer' not in body_
    assert 'convertToPoly' not in body_
    assert 'convertToMesh(c)' in body_ and 'convertToMesh(n)' not in body_


def test_d8_empty_input_is_an_error_not_a_silent_pass():
    with pytest.raises(ValueError, match='nothing to build'):
        vc.build([], {})
    with pytest.raises(ValueError, match='empty mesh'):
        vc.build([{'key': 1, 'name': 'E', 'verts': [], 'tris': [], 'mat_ids': [], 'uvs': None, 'uv_tris': None}],
                 {})


def test_d9_udim_slicer_snaps_uv_to_integers_ours_cuts_without_snapping():
    mesh = facade_core(glass=False)
    uv, _w, _i, _p = lay.project_k6(mesh, list(range(len(mesh['tris']))), [0, 0, 0], lambda m: STEP)

    def ok(pieces):
        a, b, c = mesh['verts'], mesh['tris'], pieces
        for p in c:
            P = [[sum(w[j] * a[b[p['tri']][j]][k] for j in range(3)) for k in range(3)] for w in p['w']]
            for i in range(1, len(P) - 1):
                jac = u10.jacobian([P[0], P[i], P[i + 1]], [p['uv'][0], p['uv'][i], p['uv'][i + 1]])
                if jac and abs(math.sqrt(jac[0] * jac[1]) * TILE / (TILE / STEP) - 1) > 0.01:
                    return False
        return True

    def source():  # snap every UV within 0.05 of an integer onto it (`:5246-5255`)
        out = []
        for p in lay.cut_grid(uv, dict(enumerate(mesh['mat_ids']))):
            out.append(dict(p, uv=[[round(x) if abs(x - round(x)) < 0.05 else x for x in q] for q in p['uv']]))
        return out
    red_green(ok, source, lambda: lay.cut_grid(uv, dict(enumerate(mesh['mat_ids']))))


def test_perimeter_unroll_keeps_corners_axis_projection_tears_them():
    mesh = facade_core(openings=False, glass=False)
    faces = list(range(len(mesh['tris'])))

    def corner(unroll):
        uv, wall_of, _i, pairs = lay.project_k6(mesh, faces, [0, 0, 0], lambda m: STEP, unroll=unroll)
        pieces = lay.shift_into_tiles(lay.cut_grid(uv, dict(enumerate(mesh['mat_ids']))), {3: 1001, 7: 1002})
        allp = {frozenset((a, b)) for a in set(wall_of.values()) for b in set(wall_of.values()) if a != b}
        return lay.seam_metric(mesh, pieces, TILE, wall_of, pairs if unroll else allp)['chain_max']
    assert corner(False) > 100  # L09: 2048 px at a corner by axes
    assert corner(True) <= lay.SEAM_TOL_PX


def test_closed_perimeter_has_one_fold_corner_at_the_root_start_per_material():
    obj = build(MB.facade(openings=False, glass=False))
    s = body(obj)['summary']
    assert s['seam_internal_max_px'] <= lay.SEAM_TOL_PX and s['seam_chain_max_px'] <= lay.SEAM_TOL_PX
    # 7 bad edges = the vertical closing corner of 4 rows x 2 materials, minus the material change at 6 m
    assert 0 < s['fold_edges'] <= 8


# ---- vpm.build acceptance (L09 minimal acceptance) ------------------------------------------------------------
@pytest.mark.parametrize('artist', [False, True])
def test_acceptance_facade_seam_texel_tiles_glass(artist):
    poly = MB.facade()
    if artist:
        poly = MB.artist_uv(poly)
    obj = build(poly)
    assert obj['findings'] == []
    parts = {p['summary']['part']: p['summary'] for p in obj['parts']}
    assert set(parts) == {'body', 'glass'}
    b, g = parts['body'], parts['glass']
    assert b['seam_internal_max_px'] <= 0.01 and b['seam_chain_max_px'] <= 0.01
    assert b['tiles'] == [1001, 1002] and b['udim_table'] == {'3': 1001, '7': 1002}
    assert g['tiles'] == [1001] and g['udim_table'] == {'31': 1001}  # owner answer V9: per mesh from 1001
    assert b['crossing_pieces'] == 0 and g['crossing_pieces'] == 0
    for s in (b, g):
        for lo, hi in s['texel_px_per_m'].values():
            assert abs(lo / (TILE / STEP) - 1) <= 0.01 and abs(hi / (TILE / STEP) - 1) <= 0.01


def _f32(x):
    return struct.unpack('f', struct.pack('f', x))[0]


def test_far_coordinates_and_centimetres_give_the_metre_result():
    """L09 r2: projection by float32 WORLD coordinates at 2 345 678 m gave +2.1 % texel; the glue gives the core
    local + pivot in double, so the far facade equals the near one up to the shift of the zero."""
    far = (2345678.0, 1234567.0, 0.0)
    near = build(MB.facade(glass=False))
    poly = MB.facade(glass=False, offset=far)
    obj = vc.build([core_mesh(poly)], {'grid_zero_m': list(far)})['objects'][0]
    for key in ('seam_internal_max_px', 'seam_chain_max_px', 'tiles', 'pieces', 'texel_px_per_m'):
        assert body(obj)['summary'][key] == body(near)['summary'][key], key

    def ok(texel):
        return all(abs(lo / (TILE / STEP) - 1) <= 0.01 and abs(hi / (TILE / STEP) - 1) <= 0.01
                   for lo, hi in texel.values())

    fine = MB.facade(height=3.0, floor=0.6, col=0.6, glass=False, openings=False, offset=far)

    def true_texel(o):
        """Texel of the built UV on the TRUE geometry (what the renderer sees)."""
        geo = body(o)['geometry']
        verts = [[sum(w * fine['verts'][i][k] for i, w in vw) for k in range(3)] for vw in geo['verts_w']]
        tx = [math.sqrt(s1 * s2) * TILE for f, t in enumerate(geo['tris'])
              for s1, s2, _d in [u10.jacobian([verts[i] for i in t], [geo['uvs'][i] for i in geo['uv_tris'][f]])]]
        return {'3': (min(tx), max(tx))}

    def source():  # UV from world float32 (step 0.25 m at 2 345 678 m)
        p32 = dict(fine, verts=[[_f32(c) for c in v] for v in fine['verts']])
        return true_texel(vc.build([core_mesh(p32)], {'grid_zero_m': list(far)})['objects'][0])

    def impl():
        return true_texel(vc.build([core_mesh(fine)], {'grid_zero_m': list(far)})['objects'][0])
    red_green(ok, source, impl)
    cm = dict(poly, verts=[[c * 100.0 for c in v] for v in poly['verts']])  # the glue scales units to metres
    obj_cm = vc.build([core_mesh(dict(cm, verts=[[c * 0.01 for c in v] for v in cm['verts']]))],
                      {'grid_zero_m': list(far)})['objects'][0]
    assert body(obj_cm)['summary']['seam_chain_max_px'] <= lay.SEAM_TOL_PX


def test_id_out_of_library_range_fails_closed():
    poly = MB.facade(glass=False)
    poly['mat_ids'] = [1005 if i == MB.BRICK else i for i in poly['mat_ids']]
    obj = build(poly)
    assert [c for c, _ids, _d in obj['findings']] == ['id_range'] and obj['parts'] == []


def test_kept_ids_without_uv_fail_closed_and_with_uv_are_rescaled_to_the_texel():
    poly = MB.facade(glass=False)
    obj = build(poly, projected_ids=[MB.PANEL])
    assert [c for c, _i, _d in obj['findings']] == ['no_uv']
    obj = build(MB.artist_uv(poly), projected_ids=[MB.PANEL])
    s = body(obj)['summary']
    assert s['seam_kept_uv_max_px'] > 1  # the artist's random islands: reported, not a K6 finding
    assert obj['findings'] == [] and s['kept_uv_faces'] > 0 and s['rescaled'][0]['id'] == MB.BRICK
    lo, hi = s['texel_px_per_m'][str(MB.BRICK)]
    assert abs(lo / (TILE / STEP) - 1) <= 0.01 and abs(hi / (TILE / STEP) - 1) <= 0.01


def test_options_period_texel_parameter_and_validation():
    o = vc.options({'period_by_id': {'7': 3.9}, 'texel_px_per_m': 1024})
    assert vc.texel_of(o, 3) == pytest.approx(1024.0) and vc.texel_of(o, 7) == pytest.approx(1024 * 3.6 / 3.9)
    assert vc.options({})['step_m'] == 3.6 and vc.options({})['tile_px'] == 3600
    for bad in ({'nope': 1}, {'step_m': 0}, {'glass_ids': 'all'}, {'grid_zero_m': [0, 0]}, {'unroll': 1},
                {'period_by_id': {'x': 3}}, {'texel_px_per_m': -1}):
        with pytest.raises(ValueError):
            vc.options(bad)


def test_body_is_numbered_per_mesh_and_renumber_is_dense_glass_is_1001():
    assert lay.renumber_dense([12, 3, 31, 7]) == {3: 1001, 7: 1002, 12: 1003, 31: 1004}
    with pytest.raises(ValueError):
        lay.renumber_dense([1005])
    seen = []
    obj = vc.build([core_mesh(MB.facade())], {'glass_ids': [MB.GLASS]},
                   lambda ids: seen.append(list(ids)) or lay.renumber_dense(ids))['objects'][0]
    # only the body is renumbered; the glass table is 1001 for every glass id (D221)
    assert seen == [[3, 7]] and obj['findings'] == []
    assert vc.glass_table([40, 31]) == {31: 1001, 40: 1001}
    with pytest.raises(ValueError):
        vc.glass_table([1005])


def test_two_glass_materials_stay_in_udim_1001_and_get_no_maps():
    """D221 (reg p.31 §2.2 / 2.5.2.2.1а): a glass mesh with k glass ids lies in 1001 only (was 1001..1000+k under
    D209, conflict C47), with no udim_gap finding; maps_table gives the glass part no maps (reg 2.4.2)."""
    mesh = core_mesh(MB.facade())
    glass = [f for f, i in enumerate(mesh['mat_ids']) if i == MB.GLASS]
    assert len(glass) >= 2
    second = MB.GLASS + 9
    for f in glass[len(glass) // 2:]:
        mesh['mat_ids'][f] = second
    plan = vc.build([mesh], {'glass_ids': [MB.GLASS, second], 'address': 'Kpp_1'})
    obj = plan['objects'][0]
    assert obj['findings'] == []
    g = next(p['summary'] for p in obj['parts'] if p['summary']['part'] == 'glass')
    assert g['tiles'] == [1001]
    assert g['udim_table'] == {str(MB.GLASS): 1001, str(second): 1001}
    assert g['crossing_pieces'] == 0 and g['seam_internal_max_px'] <= 0.01
    geo = next(p['geometry'] for p in obj['parts'] if p['summary']['part'] == 'glass')
    assert all(-1e-7 <= u <= 1 + 1e-7 and -1e-7 <= v <= 1 + 1e-7 for u, v in geo['uvs'])
    assert set(geo['mat_ids']) == {MB.GLASS, second}   # the glass materials stay apart on the faces
    assert vc.maps_table(plan) == {'SM_Kpp_1_Main': {3: 1001, 7: 1002}}


def test_weld_output_is_closed_where_the_source_is():
    """Cut points of a shared edge are the same vertex on both triangles (no cracks in the copy)."""
    obj = build(MB.facade(openings=False, glass=False))
    geo = body(obj)['geometry']
    count = {}
    for t in geo['tris']:
        for e in range(3):
            k = tuple(sorted((t[e], t[(e + 1) % 3])))
            count[k] = count.get(k, 0) + 1
    assert max(count.values()) <= 2
    # every output triangle names its source triangle (the glue hides fan diagonals by it; native job
    # 20261106-045048-249fe351 found the list overwritten)
    assert len(geo['src_tri']) == len(geo['tris']) and all(isinstance(i, int) for i in geo['src_tri'])
    # boundary edges of the welded copy = boundary of the source (bottom, top and the 4-wall loop has none)
    src = core_mesh(MB.facade(openings=False, glass=False))
    sb = {}
    for t in src['tris']:
        for e in range(3):
            k = tuple(sorted((t[e], t[(e + 1) % 3])))
            sb[k] = sb.get(k, 0) + 1
    src_len = sum(math.dist(src['verts'][a], src['verts'][b]) for (a, b), n in sb.items() if n == 1)

    def pos(v):
        return [sum(w * src['verts'][i][k] for i, w in geo['verts_w'][v]) for k in range(3)]
    out_len = sum(math.dist(pos(a), pos(b)) for (a, b), n in count.items() if n == 1)
    assert out_len == pytest.approx(src_len, rel=1e-9)


def test_20000_faces_within_the_time_budget():
    poly = MB.facade(height=22.0, col=0.6, floor=1.0, margin=0.15)
    mesh = core_mesh(poly)
    assert len(mesh['tris']) >= 19000
    t = time.perf_counter()
    obj = vc.build([mesh], {'glass_ids': [MB.GLASS]})['objects'][0]
    dt = time.perf_counter() - t
    assert obj['findings'] == []
    assert dt < 10.0, dt


# ---- layout_seamless (contract of branch 0, read by branch P) --------------------------------------------------
def test_layout_seamless_whole_shifts_tile_by_centroid_and_cut_flag():
    isl = [{'id': 'a', 'uv': [[2.2, 3.1], [2.8, 3.1], [2.8, 3.9]], 'world': [[0, 0, 0], [1, 0, 0], [1, 0, 1]],
            'library_id': 7},
           {'id': 'b', 'uv': [[-0.4, 0.2], [0.3, 0.2], [0.3, 0.6]], 'world': [[1, 0, 0], [2, 0, 0], [2, 0, 1]],
            'library_id': 3}]
    isl[1]['uv'][0] = [2.8 - 1.0 - 3.0, 3.1 + 2.0]  # shares world (1,0,0) with a: fraction equal mod 1
    r = lay.layout_seamless(isl, [0, 0, 0], 0.6, TILE / STEP, TILE)
    by = {i['id']: i for i in r['islands']}
    assert by['a']['tile'] == 1002 and by['b']['tile'] == 1001
    assert all(isinstance(c, int) for i in r['islands'] for c in i['shift'])
    assert by['a']['shift'] == [1 - 2, 0 - 3] and by['a']['cut'] is False
    assert by['b']['cut'] is True and any(m['id'] == 'b' for m in r['moved'])
    assert r['seam_texels'] <= lay.SEAM_TOL_PX
    with pytest.raises(ValueError):
        lay.layout_seamless([], [0, 0, 0], 0.6, 1137.8, TILE)
    with pytest.raises(ValueError):
        lay.layout_seamless(isl, [0, 0, 0], 0.6, 1137.8, TILE, {'bad': 1})
    r2 = lay.layout_seamless(isl, [0, 0, 0], 0.26, TILE / STEP, TILE)  # brick 0.26 m: 3.6 m is not whole
    assert any(m['id'] is None for m in r2['moved'])


# ---- udim.rescale -----------------------------------------------------------------------------------------------
def plane_mesh(scale=1.0, px_per_m=256.0, size=4.0):
    """4 x 4 m plane as two triangles at `scale` system units per metre, UV at px_per_m (shared UV vertices)."""
    s = size
    k = px_per_m / TILE
    return {'verts': [[0, 0, 0], [s, 0, 0], [s, s, 0], [0, s, 0]], 'tris': [[0, 1, 2], [0, 2, 3]], 'mat_ids': [1, 1],
            'uvs': [[0, 0], [s * k, 0], [s * k, s * k], [0, s * k]], 'uv_tris': [[0, 1, 2], [0, 2, 3]],
            'units': [[c * scale for c in p] for p in [[0, 0, 0], [s, 0, 0], [s, s, 0], [0, s, 0]]]}


def model_rescale_system_units(mesh, target):
    """«ReScale Density» (:43265-43291): density in px per SYSTEM unit -> a centimetre scene is off x100."""
    dens = u10.density(dict(mesh, verts=mesh['units']), [0, 1], TILE)
    sc = target / dens
    return u10.density(dict(mesh, uvs=[[u * sc, v * sc] for u, v in mesh['uvs']]), [0, 1], TILE)


def test_r1_density_is_in_metres_cm_scene_equals_metre_scene():
    def ok(px):
        return abs(px / 512.0 - 1) <= 0.01

    cm = plane_mesh(scale=100.0)
    red_green(ok, lambda: model_rescale_system_units(cm, 512.0),
              lambda: u10.rescale_plan(cm, {'target_px_per_m': 512})['after_px_per_m'])
    assert u10.rescale_plan(plane_mesh(), {'target_px_per_m': 512})['scale'] == pytest.approx(2.0)


def two_walls():
    """Two coplanar quads A | B sharing the edge x = 2 (UV projected from the common zero, separate elements)."""
    k = 256.0 / TILE
    verts = [[0, 0, 0], [2, 0, 0], [2, 2, 0], [0, 2, 0], [4, 0, 0], [4, 2, 0]]
    return {'verts': verts, 'tris': [[0, 1, 2], [0, 2, 3], [1, 4, 5], [1, 5, 2]], 'mat_ids': [1, 1, 1, 1],
            'uvs': [[x * k, y * k] for x, y, _ in verts] + [[2 * k, 0], [2 * k, 2 * k]],
            'uv_tris': [[0, 1, 2], [0, 2, 3], [6, 4, 5], [6, 5, 7]]}


def test_r2_scale_around_the_common_zero_keeps_the_k6_phase_selection_centre_loses_it():
    m = two_walls()

    def ok(uvs):  # the shared edge x = 2 keeps one UV on both elements
        return math.dist(uvs[1], uvs[6]) < 1e-12 and math.dist(uvs[2], uvs[7]) < 1e-12

    def source():  # scale each selection (element) around ITS centre
        uvs = [list(p) for p in m['uvs']]
        for el in ([0, 1, 2, 3], [4, 5, 6, 7]):
            cu = sum(uvs[i][0] for i in el) / 4
            cv = sum(uvs[i][1] for i in el) / 4
            for i in el:
                uvs[i] = [cu + (uvs[i][0] - cu) * 2, cv + (uvs[i][1] - cv) * 2]
        return uvs

    def impl():
        a = u10.rescale_plan(m, {'target_px_per_m': 512, 'faces': [1, 2]})
        return u10.rescale_plan(dict(m, uvs=a['uvs']), {'target_px_per_m': 512, 'faces': [3, 4]})['uvs']
    red_green(ok, source, impl)


def test_r3_no_break_selected_the_element_moves_whole():
    m = plane_mesh()

    def ok(res):
        uvs, uv_tris = res
        return uv_tris[0][0] == uv_tris[1][0] and uv_tris[0][2] == uv_tris[1][1]  # still shared

    def source():  # breakSelected on face 1, then scale only it
        uvs = [list(p) for p in m['uvs']] + [list(m['uvs'][0]), list(m['uvs'][2])]
        return uvs, [[4, 1, 5], [0, 2, 3]]

    def impl():
        r = u10.rescale_plan(m, {'target_px_per_m': 512, 'faces': [1]})
        assert r['faces_scaled'] == 2 and r['notes']
        return r['uvs'], m['uv_tris']
    red_green(ok, source, impl)
    r = u10.rescale_plan(m, {'target_px_per_m': 512, 'faces': [1]})
    assert r['after_px_per_m'] == pytest.approx(512.0)


def test_r4_maps_and_materials_are_never_rewritten():
    text = (PKG / 'udim10_max.py').read_text(encoding='utf-8')
    for bad in ('openBitmap', 'save(', '.filename =', 'copy(n.material', 'material =', 'renderMap'):
        assert bad not in text.split('"""', 2)[-1], bad


def test_r5_empty_scope_and_bad_options_are_errors():
    m = plane_mesh()
    with pytest.raises(ValueError):
        u10.rescale_plan(dict(m, tris=[], uv_tris=[], mat_ids=[]))
    with pytest.raises(ValueError):
        u10.rescale_plan(m, {'faces': []})
    with pytest.raises(ValueError):
        u10.rescale_plan(m, {'faces': [9]})
    with pytest.raises(ValueError):
        u10.rescale_plan(m, {'texel': 1})
    flat = dict(m, uvs=[[0, 0]] * 4)
    with pytest.raises(ValueError, match='zero area'):
        u10.rescale_plan(flat)


def test_rescale_then_k6_layout_keeps_seam_zero():
    """L09 acceptance: rescale around the common zero, then the K6 layout - seam 0 px."""
    square = [(0.0, 0.0), (7.2, 0.0), (7.2, 7.2), (0.0, 7.2)]  # perimeter 4 x 7.2 m: no closing fold
    poly = MB.facade(glass=False, footprint=square)
    tm = core_mesh(poly)
    uv, _w, _i, _p = lay.project_k6(tm, list(range(len(tm['tris']))), [0, 0, 0], lambda m: 2 * STEP)  # half texel
    tm['uvs'] = [c for f in range(len(tm['tris'])) for c in uv[f]]
    tm['uv_tris'] = [[3 * f, 3 * f + 1, 3 * f + 2] for f in range(len(tm['tris']))]
    obj = vc.build([tm], {'projected_ids': [MB.PANEL]})['objects'][0]
    s = body(obj)['summary']
    assert obj['findings'] == [] and s['rescaled'][0]['scale'] == pytest.approx(2.0)
    assert s['seam_internal_max_px'] <= 0.01 and s['seam_kept_uv_max_px'] <= 0.01


# ---- udim.distortion ---------------------------------------------------------------------------------------------
def plane16(scale=1.0, **kw):
    p = MB.plane16(**kw)
    tm, groups = MB.triangulate(p)
    tm = dict(tm, verts=[[c * scale for c in v] for v in tm['verts']])
    return tm, groups


def model_area_normalised(tm, groups):
    """«Texels Distorsions» Area (:16171): (A_uv/A_geom) / object mean; Angle from the first three vertices."""
    ratio = []
    for g in groups:
        a3 = sum(u10._area3(*(tm['verts'][i] for i in tm['tris'][f])) for f in g)
        a2 = sum(u10._area2(*(tm['uvs'][i] for i in tm['uv_tris'][f])) for f in g)
        ratio.append(a2 / a3)
    mean = sum(ratio) / len(ratio)
    return [r / mean for r in ratio]


def test_x1_good_faces_are_not_punished_by_the_object_mean():
    tm, groups = plane16()
    clean = [k for k in range(1, 17) if k not in (1, 6, 9, 12, 14, 3, 8, 15)]

    def ok(flagged):
        return not set(flagged) & set(clean)

    def source():  # GeoAGR flags |area - 1| > 1 %: the clean faces read 0.62
        return [k for k, r in enumerate(model_area_normalised(tm, groups), 1) if abs(r - 1) > 0.01]

    def impl():
        res = u10.distortion_rows(tm, {}, groups)
        return sorted({f for v in res['bad'].values() for f in v})
    red_green(ok, source, impl)


def test_x2_angle_from_three_vertices_misses_the_second_triangle():
    """A quad whose 4th UV corner is pulled: the first three vertices see no distortion."""
    tm, groups = plane16(stretched=(), sheared=())
    q = 5
    i3 = tm['uv_tris'][groups[q][1]][2]
    tm['uvs'][i3] = [tm['uvs'][i3][0] + 0.01, tm['uvs'][i3][1]]

    def ok(flagged):
        return q + 1 in flagged

    def source():
        f = groups[q][0]  # first three vertices = the first fan triangle
        s1, s2, _ = u10.jacobian([tm['verts'][i] for i in tm['tris'][f]], [tm['uvs'][i] for i in tm['uv_tris'][f]])
        return [q + 1] if s1 / s2 > 1.02 else []
    red_green(ok, source, lambda: u10.distortion_rows(tm, {}, groups)['bad'].get('anisotropy', []))


def test_x3_metric_does_not_depend_on_units_or_texel():
    m_tm, groups = plane16()
    cm_tm, _ = plane16(scale=100.0)

    def edge_ratio(tm):  # GeoAGR Edge: UV perimeter / geometry perimeter in system units
        g = groups[0]
        per3 = per2 = 0.0
        for f in g:
            t, u = tm['tris'][f], tm['uv_tris'][f]
            for e in range(3):
                per3 += math.dist(tm['verts'][t[e]], tm['verts'][t[(e + 1) % 3]])
                per2 += math.dist(tm['uvs'][u[e]], tm['uvs'][u[(e + 1) % 3]])
        return per2 / per3
    assert round(edge_ratio(cm_tm), 2) == 0.0 != round(edge_ratio(m_tm), 2) or edge_ratio(m_tm) != edge_ratio(cm_tm)
    a = u10.distortion_rows(m_tm, {}, groups)
    b = u10.distortion_rows(m_tm, {}, groups)
    cm_m = dict(cm_tm, verts=[[c / 100.0 for c in v] for v in cm_tm['verts']])  # the glue gives metres
    c = u10.distortion_rows(cm_m, {}, groups)
    assert a['bad'] == b['bad'] == c['bad']


def test_x6_acceptance_plane16_flags_exactly_the_8_faces():
    tm, groups = plane16()
    res = u10.distortion_rows(tm, {}, groups)
    stretched, sheared = {1, 6, 9, 12, 14}, {3, 8, 15}
    assert set(res['bad']['texel_scale']) == stretched
    assert set(res['bad']['anisotropy']) == stretched | sheared
    assert 'mirrored' not in res['bad'] and res['target_source'] == 'median'
    assert res['target_px_per_m'] == pytest.approx(256.0)
    res = u10.distortion_rows(tm, {'target_px_per_m': 256}, groups)
    assert set(res['bad']['texel_scale']) == stretched and res['target_source'] == 'option'


def test_distortion_of_the_built_facade_is_clean():
    obj = build(MB.facade(glass=False))
    geo = body(obj)['geometry']
    src = core_mesh(MB.facade(glass=False))
    verts = [[sum(w * src['verts'][i][k] for i, w in vw) for k in range(3)] for vw in geo['verts_w']]
    mesh = {'verts': verts, 'tris': geo['tris'], 'mat_ids': geo['mat_ids'], 'uvs': geo['uvs'],
            'uv_tris': geo['uv_tris']}
    res = u10.distortion_rows(mesh, {'target_px_per_m': TILE / STEP})
    assert res['bad'] == {}


def test_mirrored_uv_is_flagged():
    tm, groups = plane16(stretched=(), sheared=())
    tm['uvs'] = [[-u, v] for u, v in tm['uvs']]
    assert len(u10.distortion_rows(tm, {}, groups)['bad']['mirrored']) == 16


def test_distortion_options_are_validated():
    tm, groups = plane16()
    for bad in ({'x': 1}, {'aniso_tol': 0.5}, {'scale_tol': 0}, {'tile_px': 1.5}):
        with pytest.raises(ValueError):
            u10.distortion_rows(tm, bad, groups)


def test_reports_fit_the_edit_contract():
    """The glue builds its reports through edit_core; a sample row of each button validates."""
    r = ec.report('vpm.build', 'preview', [ec.entry(1, 'F', [ec.finding('seam', [1], 'x')])], [], [], (),
                  state_hash='s', extra={'options': vc.options({}), 'issue': '#1024'})
    assert r['status'] == 'fail'
    ec.canonical(vc.options({'period_by_id': {'7': 3.9}}))
