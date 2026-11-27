"""Sokolniki #1784 step 3: inset elements on the accepted body v005 [D378].

Pattern: n/a | new-case: tests of jobs/sokolniki-uvk1000/hooks/inset_build.py and inset_sheet.py (synthetic inputs,
no Revit FBX, no DCC). Synthetic: all geometry below is made up for the tests.
"""
import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / 'jobs/sokolniki-uvk1000'


def _load(name):
    spec = importlib.util.spec_from_file_location(name + '_1784s3', D / 'hooks' / (name + '.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ib = _load('inset_build')
sh = _load('inset_sheet')
CFG = json.loads((D / 'insets_config.json').read_text(encoding='utf-8'))


def _normal(pts):
    n = [0.0, 0.0, 0.0]
    for i in range(len(pts)):
        p, q = pts[i], pts[(i + 1) % len(pts)]
        n[0] += (p[1] - q[1]) * (p[2] + q[2])
        n[1] += (p[2] - q[2]) * (p[0] + q[0])
        n[2] += (p[0] - q[0]) * (p[1] + q[1])
    return n


def _faces(mesh):
    return [[mesh.verts[i] for i in f['v']] for f in mesh.faces]


def test_box_is_closed_with_outward_quads():
    m = ib.Mesh()
    c = [1.0, 2.0, 3.0]
    ib.box(m, c, [[0.6, 0.8, 0], [-0.8, 0.6, 0], [0, 0, 1]], [2.0, 0.1, 0.05], 'X')
    assert len(m.faces) == 6 and all(len(f['v']) == 4 for f in m.faces)
    for pts in _faces(m):
        mid = [sum(p[j] for p in pts) / 4 for j in range(3)]
        assert sum(_normal(pts)[j] * (mid[j] - c[j]) for j in range(3)) > 0
    edges = {}
    for f in m.faces:
        for a, b in zip(f['v'], f['v'][1:] + f['v'][:1]):
            edges[frozenset((a, b))] = edges.get(frozenset((a, b)), 0) + 1
    assert set(edges.values()) == {2}  # closed, manifold


def test_column_embed_lowers_only_the_bottom():
    m = ib.Mesh()
    ib.box(m, [0, 0, 5], [[0, 0, 1], [1, 0, 0], [0, 1, 0]], [1.0, 0.05, 0.05], 'X', embed_down=0.02)
    zs = sorted({round(v[2], 4) for v in m.verts})
    assert zs == [3.98, 6.0]


def test_merge_runs_joins_stacked_and_drops_duplicates():
    ax = [[0, 0, 1], [1, 0, 0], [0, 1, 0]]
    a = {'center': [0, 0, 1], 'axes': ax, 'half': [1, 0.03, 0.03]}
    b = {'center': [0, 0, 3], 'axes': ax, 'half': [1, 0.03, 0.03]}  # stacked, touching at z=2
    dup = {'center': [0, 0, 1], 'axes': ax, 'half': [1, 0.03, 0.03]}
    apart = {'center': [0, 0, 6], 'axes': ax, 'half': [1, 0.03, 0.03]}  # gap 2 m: stays
    out, d = ib.merge_runs([a, dup, b, apart], 0.005)
    assert d == 1 and len(out) == 2
    run = min(out, key=lambda o: o['center'][2])
    assert math.isclose(run['center'][2], 2.0) and math.isclose(run['half'][0], 2.0)


def test_merge_columns_joins_touching_posts_world_aligned():
    ax = [[0, 0, 1], [0.6, 0.8, 0], [-0.8, 0.6, 0]]
    a = {'center': [0, 0, 1], 'axes': ax, 'half': [1, 0.05, 0.05]}
    b = {'center': [0.1, 0, 1], 'axes': ax, 'half': [1, 0.05, 0.05]}  # side by side, faces touch
    c = {'center': [5, 0, 1], 'axes': ax, 'half': [1, 0.05, 0.05]}
    out, joined = ib.merge_columns([a, b, c], 0.005)
    assert joined == 1 and len(out) == 2
    big = max(out, key=lambda o: o['half'][1])
    assert big['axes'][1] == [1.0, 0.0, 0.0] and math.isclose(big['half'][1], 0.1)


def _cage_obb():
    col = lambda x, y: {'family': 'cage_column', 'center': [x, y, 11.5], 'axes': [[0, 0, 1], [1, 0, 0], [0, 1, 0]],
                        'half': [1.5, 0.05, 0.05], 'tris': 100}
    beam = {'family': 'cage_beam', 'center': [2.0, 0.0, 13.03], 'axes': [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            'half': [1.95, 0.03, 0.03], 'tris': 100}  # rests on both column tops (13.0), ends at their faces
    return [col(0, 0), col(4, 0), beam]


def test_cage_beam_ends_never_flush_with_a_column_face():
    report = {}
    cols, beams = ib.prepare_cage(_cage_obb(), CFG['cage'], report)
    assert len(cols) == 2 and len(beams) == 1
    b = beams[0]
    for sg in (-1, 1):
        e = b['c'][0] + sg * b['hl']
        for c in cols:
            for face in (c['center'][0] - c['half'][1], c['center'][0] + c['half'][1]):
                assert abs(e - face) >= CFG['cage']['parallel_gap_m']
    # both column tops ran up into the beam they carry
    assert report['merged_runs']['cage_column']['tops_raised_into_beam'] == 2
    assert all(math.isclose(c['center'][2] + c['half'][0], 13.03) for c in cols)


def _f05_inputs():
    """Synthetic face line along +y (x=0) on a CCW ring; outward = -x; glass 0.5..1.0 m outside, one step."""
    vl = {'volumes': {'V': {'ring': [[0, 0], [10, 0], [10, 20], [0, 20], [0, 0]]}},
          'edges': {'E1': {'volume': 'V', 'xy': [[0, 20], [0, 0]]}}}
    objs = []
    for s0, s1, o0, o1 in ((0.0, 5.0, 0.5, 0.6), (5.05, 10.0, 0.2, 0.3)):  # two facets, a 0.4 m step
        for z in (1.0, 3.0):
            sc, oc = (s0 + s1) / 2, (o0 + o1) / 2
            ang = math.atan2(o1 - o0, s1 - s0)
            # s runs along -y from (0, 20); out runs along +x? outward of a CCW ring at this edge is -x
            t, n = (0.0, -1.0), (-1.0, 0.0)
            c = [t[0] * sc + n[0] * oc, 20 + t[1] * sc + n[1] * oc, z]
            run = [t[0] * math.cos(ang) + n[0] * math.sin(ang), t[1] * math.cos(ang) + n[1] * math.sin(ang), 0]
            nrm = [-run[1], run[0], 0]
            objs.append({'family': 'curtain_glass', 'center': c, 'axes': [run, [0, 0, 1], nrm],
                         'half': [math.hypot(s1 - s0, o1 - o0) / 2, 1.0, 0.01], 'zmin': z - 1.0, 'zmax': z + 1.0})
    return vl, objs


def test_f05_glazing_closes_the_gap_with_quads_only():
    vl, objs = _f05_inputs()
    a, t, n, _ = ib.f05_frame(vl, ['E1'])
    assert math.isclose(n[0], -1.0, abs_tol=1e-9)  # outward of the CCW ring
    cfg = dict(CFG['f05'])
    pts, k = ib.glass_polyline(objs, a, t, n, 10.0, 0.0, cfg)
    assert k == 4
    rets = [(p, q) for p, q in zip(pts, pts[1:]) if abs(q[1] - p[1]) > q[0] - p[0]]
    assert len(rets) == 1 and rets[0][1][0] > rets[0][0][0]  # the return spans the gap, never a zero-width wall
    m = ib.Mesh()
    bands = [(0.0, 6.0, 0.0, 2.0), (0.0, 10.0, 2.0, 4.0)]
    ib.f05_glazing(m, pts, a, t, n, bands, {'glass': 'G', 'end': 'E'})
    assert all(len(f['v']) == 4 for f in m.faces)
    edges = {}
    for f in m.faces:
        for i, j in zip(f['v'], f['v'][1:] + f['v'][:1]):
            edges.setdefault(frozenset((i, j)), []).append(1)
    open_edges = [e for e, u in edges.items() if len(u) == 1]
    assert all(len(u) <= 2 for u in edges.values())
    for e in open_edges:  # the only boundary is the mouth outline on the face plane (x = 0)
        assert all(abs(m.verts[i][0]) < 1e-6 for i in e)
    xs = [v[0] for v in m.verts]
    assert min(xs) < -0.15 and max(xs) <= 1e-6  # everything is outside the face, nothing inside the body


def test_decor_lists_unmatched_family_and_strips_ids():
    assert sh.family('Ограждение ADSK_МГН_h 900 [2272786]_[16826].004') == 'Ограждение ADSK_МГН_h 900'
    assert sh.family('ADSK_КолоннаНесущая_Труба_ГОСТ 3_3e2a45b') == 'ADSK_КолоннаНесущая_Труба_ГОСТ 3'
    dump = {'objects': [{'name': 'ADSK_КолоннаНесущая_Труба_ГОСТ 3_3e2a45b', 'tris': 10},
                        {'name': 'Неизвестное семейство_abcdef1', 'tris': 5}]}
    d = sh.decor(dump, CFG)
    rows = {r['family']: r['decision'] for r in d['rows']}
    assert rows['ADSK_КолоннаНесущая_Труба_ГОСТ 3'] == 'вставка'
    assert rows['Неизвестное семейство'] == 'не классифицировано'


def test_views_outward_normal_and_joined_edges():
    vl = {'volumes': {'V': {'ring': [[0, 0], [10, 0], [10, 5], [0, 5], [0, 0]]}},
          'edges': {'E1': {'volume': 'V', 'facade': 'F01', 'xy': [[0, 0], [6, 0]]},
                    'E2': {'volume': 'V', 'facade': 'F01', 'xy': [[6, 0], [10, 0]]},
                    'E3': {'volume': 'V', 'facade': 'F02', 'xy': [[10, 0], [10, 5]]}}}
    v = sh.views(vl)
    f1 = next(f for f in v['facades'] if f['id'] == 'F01')
    assert f1['edges'] == ['E1', 'E2'] and f1['s'] == [0.0, 10.0]
    assert math.isclose(f1['n'][1], -1.0)  # south face of a CCW ring looks to -y


# ---- v007 [D410] -----------------------------------------------------------------------------------------------
def _closed(mesh):
    cnt = {}
    for f in mesh.faces:
        v = f['v']
        for a, b in zip(v, v[1:] + v[:1]):
            k = (min(a, b), max(a, b))
            cnt[k] = cnt.get(k, 0) + 1
    return all(c == 2 for c in cnt.values())


def _planar(pts, tol=1e-6):
    n = _normal(pts)
    L = math.sqrt(sum(c * c for c in n))
    n = [c / L for c in n]
    d0 = sum(a * b for a, b in zip(pts[0], n))
    return all(abs(sum(a * b for a, b in zip(p, n)) - d0) < tol for p in pts)


def _relief(origin, N, v=(-0.5, 0.5), z=(0.0, 3.0), apex=(0.0, 1.5)):
    return {'origin': list(origin), 'N': list(N), 'V': [-N[1], N[0], 0.0], 'v': list(v), 'z': list(z),
            't_back': 0.03, 't_front': 0.3, 't_apex': 0.5, 'apex_v': apex[0], 'apex_z': apex[1]}


def test_relief_panel_is_a_closed_planar_quad_pyramid():
    m = ib.Mesh()
    lost = ib.relief_panel(m, _relief((0, 0, 0), (1.0, 0.0, 0.0), apex=(0.1, 1.2)), 'M', 0.05, 0.02, 0.02)
    faces = _faces(m)
    assert len(faces) == 10 and all(len(f) == 4 for f in faces)
    assert all(_planar(f) for f in faces) and _closed(m)
    xs = [p[0] for p in m.verts]
    assert min(xs) == 0.03 and math.isclose(max(xs), 0.5 - lost, abs_tol=1e-4) and 0 < lost < 0.02
    c = [sum(p[i] for p in m.verts) / len(m.verts) for i in range(3)]
    for f in faces:  # outward normals
        fc = [sum(p[i] for p in f) / 4 for i in range(3)]
        assert sum(a * (b - cc) for a, b, cc in zip(_normal(f), fc, c)) > 0
    ys = [p[1] for p in m.verts]
    assert math.isclose(min(ys), -0.49) and math.isclose(max(ys), 0.49)  # half the 0.02 joint per side


def test_relief_apex_outside_the_rim_is_refused():
    try:
        ib.relief_panel(ib.Mesh(), _relief((0, 0, 0), (1.0, 0.0, 0.0), apex=(0.49, 1.5)), 'M')
    except ValueError as e:
        assert 'apex' in str(e)
    else:
        raise AssertionError('apex on the rim must be refused')


def test_mitre_ends_keep_corner_panels_apart():
    a = _relief((9.5, 0.0, 1.5), (0.0, -1.0, 0.0))   # face y = 0, looks to -y, runs x 9..10
    b = _relief((10.0, 0.5, 1.5), (1.0, 0.0, 0.0))   # face x = 10, looks to +x, runs y 0..1
    ends, n = ib.mitre_ends([a, b], 0.02)
    assert n == 1
    assert math.isclose(ends[0]['vb'][1], 0.53 - 0.01) and math.isclose(ends[0]['vf'][1], 0.8 - 0.01)
    assert math.isclose(ends[1]['vb'][0], -0.53 + 0.01) and math.isclose(ends[1]['vf'][0], -0.8 + 0.01)
    ma, mb = ib.Mesh(), ib.Mesh()
    ib.relief_panel(ma, a, 'M', joint=0.02, ends=ends[0])
    ib.relief_panel(mb, b, 'M', joint=0.02, ends=ends[1])
    # the two mitred end faces are parallel and > 5 mm apart (xView face threshold)
    pa = [p for p in ma.verts if p[0] - (-p[1]) > 9.9]
    gap = min(abs((p[0] + p[1]) - (q[0] + q[1])) / math.sqrt(2) for p in pa for q in mb.verts)
    assert gap > 0.007 and _closed(ma) and _closed(mb)


def _vl_d01():
    ring = [[0, 0], [20, 0], [20, 10], [0, 10]]
    return {'volumes': {'D': {'ring': ring + [ring[0]]}},
            'edges': {'D01': {'volume': 'D', 'xy': [[0, 0], [20, 0]]}}}


def _obb(fam, c, half3, name):
    hx, hy, hz = half3
    return {'family': fam, 'name': name, 'center': list(c), 'axes': [[0, 0, 1], [1, 0, 0], [0, 1, 0]],
            'half': [hz, hx, hy], 'zmin': c[2] - hz, 'zmax': c[2] + hz}


def test_f05_ground_piers_in_front_and_glass_bays_between():
    g = dict(CFG['f05_ground'], edge='D01')
    objs = [_obb('pier', (5.0, -0.5, 3.75), (0.45, 0.45, 3.75), 'p1'),        # pier in front of the face (-y)
            _obb('pier', (5.0, 5.0, 3.75), (0.2, 6.0, 3.75), 'wall'),         # a long wall: not a pier piece
            _obb('curtain_glass', (2.0, 2.0, 1.0), (0.9, 0.03, 0.95), 'g1'),  # glass 2 m behind the face
            _obb('curtain_glass', (8.0, 2.0, 1.0), (0.9, 0.03, 0.95), 'g2')]
    pm, gm, rep = ib.f05_ground(objs, _vl_d01(), g, 7.525)
    assert len(rep['piers']) == 1 and len(pm.faces) == 6 and _closed(pm)
    ys = [p[1] for p in pm.verts]
    assert math.isclose(max(ys), 0.05) and math.isclose(min(ys), -0.95)  # 0.05 into the body, Revit front
    assert rep['bays'] == [[1.1, 4.55], [5.45, 8.9]]
    for f in _faces(gm):
        assert all(math.isclose(p[1], -0.02) for p in f) and _normal(f)[1] < 0  # in front, facing out
        assert max(p[2] for p in f) == 7.525 and min(p[2] for p in f) == 0.0


def test_well_diff_passes_wells_and_flags_a_facade_change():
    import sys
    sys.path.insert(0, str(ROOT / 'tools' / 'methods' / 'body'))
    import volume_body as vb
    core = vb.load_core(str(ROOT / 'tools' / 'methods' / 'body'))
    ring = [[0, 0], [12, 0], [12, 8], [0, 8]]
    vl = {'volumes': {'A': {'ring': ring + [ring[0]], 'levels': [0.0, 3.0, 6.0, 7.2]}}, 'edges': {}, 'rectangles': []}
    for i in range(4):
        vl['edges']['A%02d' % (i + 1)] = {'volume': 'A', 'xy': [ring[i], ring[(i + 1) % 4]], 'facade': 'F',
                                          'seam': None, 'visible_from': 0}
    cfg = {'roof_wells': {'A': {'deck_z': 6.5, 'parapet_m': 0.2}}}
    m5 = {'A': {'body': vb.build_volume(core, vb.plans_from_volume_lines(vl, {})['A'])['body']}}
    m7 = {'A': {'body': vb.build_volume(core, vb.plans_from_volume_lines(vl, cfg)['A'])['body']}}
    rep = sh.well_diff(m5, m7, cfg, vl)
    assert rep['pass'] and rep['volumes']['A']['removed'] == 1
    vv = [list(p) for p in m7['A']['body']['verts']]
    k = next(i for i, p in enumerate(vv) if p == [0.0, 0.0, 3.0])
    vv[k][1] -= 0.05  # a facade vertex moved: outside the well
    m7['A']['body']['verts'] = vv
    bad = sh.well_diff(m5, m7, cfg, vl)
    assert not bad['pass'] and bad['outside_diff'] > 0


def test_census_rows_count_every_object_and_keep_unclassified():
    dec = {'rows': [{'family': 'Люк выхода на кровлю с лестнич', 'count': 3, 'decision': 'вставка', 'target': 'x',
                     'why': 'y', 'tris': 9},
                    {'family': 'Неизвестное', 'count': 2, 'decision': 'не классифицировано', 'target': '',
                     'why': 'нет правила', 'tris': 1}]}
    rows = sh.census_rows(dec, CFG, {'families': {'hatch': {'faces': 18}}})
    by = {r['family']: r for r in rows}
    assert by['Люк выхода на кровлю']['v007'] == '3' and by['Неизвестное']['decision'] == 'не классифицировано'
    assert sum(r['count'] for r in rows) == 5


# v008 (plan #1896): build strictly by the accepted modelling plan sokolniki-v002 (synthetic plan / body / dump below).
PLAN = {'rows': [
    {'layer': '05_ДЕКОР', 'family': 'Панель фасадная 2 Фигурная', 'representation': 'inset', 'objects': ['P1', 'P2']},
    {'layer': '09_ВНУТРЕННЕЕ_НЕ_В_МОДЕЛЬ', 'family': 'Панель фасадная 2 Фигурная', 'representation': 'not_shown',
     'objects': ['P3']},
    {'layer': '04_ВИТРАЖИ', 'family': 'Системная панель ADSK_Cтемалит_25', 'representation': 'texture',
     'objects': ['G9']},
    {'layer': '02_ОКНА', 'family': 'WB_Окно_1Створка', 'representation': 'inset', 'objects': ['W1']},
    {'layer': '03_ДВЕРИ', 'family': 'AC_ДверьВитражная', 'representation': 'inset', 'objects': ['DR1']},
    {'layer': '04_ВИТРАЖИ', 'family': 'Системная панель ADSK_Cтеклопак', 'representation': 'inset',
     'objects': ['G1']}]}


def test_plan_filter_drops_texture_and_not_shown_objects():
    objs = [{'name': n, 'family': f} for n, f in (('P1', 'decor_panel'), ('P2', 'decor_panel'), ('P3', 'decor_panel'),
                                                   ('G9', 'curtain_glass'), ('X', 'mesh'))]
    kept, dropped = ib.plan_filter(objs, ib.plan_verdicts(PLAN))
    assert [o['name'] for o in kept] == ['P1', 'P2', 'X']
    assert dropped['decor_panel'] == {'not_shown': 1} and dropped['curtain_glass'] == {'texture': 1}
    assert dropped['_unplanned'] == ['X']


def _body():
    # one volume: a 10 x 10 x 3 box-ish strip: 2 wall quads, 1 window quad and 1 door quad in the y=0 face, 1 roof
    v = [[0, 0, 0], [4, 0, 0], [4, 0, 3], [0, 0, 3], [6, 0, 0], [6, 0, 3], [8, 0, 0], [8, 0, 3], [10, 0, 0], [10, 0, 3],
         [0, 10, 3], [10, 10, 3]]
    f = [([0, 1, 2, 3], 'WALL'), ([1, 4, 5, 2], 'WINDOW'), ([4, 6, 7, 5], 'WALL'), ([6, 8, 9, 7], 'WINDOW'),
         ([3, 2, 5, 7, 9, 11, 10], 'ROOF')]
    return {'A': {'body': {'verts': v, 'faces': [{'v': ids, 'mat': m, 'uv': [[0, 0]] * len(ids)} for ids, m in f]}}}


DUMP = [{'name': 'W1', 'hull': [[4.1, -0.2], [5.9, -0.2], [5.9, 0.2], [4.1, 0.2]], 'z': [0.5, 2.5]},
        {'name': 'DR1', 'hull': [[8.1, -0.2], [9.9, -0.2], [9.9, 0.2], [8.1, 0.2]], 'z': [0.0, 2.4]},
        {'name': 'G1', 'hull': [[30, 30], [31, 30], [31, 31]], 'z': [0, 3]},
        {'name': 'P1', 'hull': [[4.5, -0.3], [5.5, -0.3], [5.5, 0.0]], 'z': [0, 3]}]


def test_partition_moves_window_and_roof_faces_out_of_the_body_unwelded():
    pcfg = CFG['partition']
    body, insets, rep = ib.partition_body(_body(), DUMP, ib.plan_verdicts(PLAN), pcfg)
    assert {f['mat'] for f in body['A']['body']['faces']} == {'WALL'}
    assert rep['multiset_equal'] and rep['faces_moved'] == 3 and rep['unmatched'] == 0
    win, door = pcfg['classes'][0], pcfg['classes'][1]
    assert win['layer'] == '02' and door['layer'] == '03'
    assert len(insets[win['object']]['faces']) == 1 and len(insets[door['object']]['faces']) == 1
    assert insets[win['object']]['faces'][0]['mat'] == win['material']
    roof = insets[pcfg['ROOF']['object']]
    assert len(roof['faces']) == 1 and len(roof['faces'][0]['v']) == 7
    # own vertices: the body keeps only wall vertices, the inset objects get their own copies
    assert len(body['A']['body']['verts']) == 8


def test_partition_counts_revit_openings_with_a_body_face():
    dump = DUMP + [{'name': 'W2', 'hull': [[50, 50], [51, 50], [51, 51]], 'z': [0, 3]}]
    plan = {'rows': PLAN['rows'] + [{'layer': '02_ОКНА', 'family': 'WB_Окно_1Створка', 'representation': 'inset',
                                     'objects': ['W2']}]}
    _, _, rep = ib.partition_body(_body(), dump, ib.plan_verdicts(plan), CFG['partition'])
    assert rep['revit_with_opening']['02'] == {'matched': 1, 'planned': 2}  # W2 has no opening in the body


def test_plan_rows_follow_every_plan_row_and_flag_railings():
    plan = {'rows': PLAN['rows'] + [{'layer': '06_ОГРАЖДЕНИЯ', 'family': 'Ограждение', 'representation': 'geometry',
                                     'objects': ['R1']}]}
    rep = {'families': {'decor_panel': {'faces': 20}, 'f05_glazing': {'revit_panels': 5, 'faces': 3},
                        'f05_ground': {'glass_panels': 2, 'bays': [[0, 1]]}}, 'objects': {}, 'merged_runs': {},
           'partition': {'by_class': {'17_window_glass': 3}, 'revit_with_opening': {'02': {'matched': 1, 'planned': 2}}}}
    rows = sh.plan_rows(plan, rep)
    assert len(rows) == len(plan['rows'])
    by = {(r['layer'][:2], r['plan']): r for r in rows}
    assert by[('05', 'вставка')]['v008'].endswith('2 тел рельефа') and by[('09', 'не показывать')]['ok']
    assert not by[('06', 'геометрия')]['ok']
    assert '1 из 2' in by[('02', 'вставка')]['v008']
