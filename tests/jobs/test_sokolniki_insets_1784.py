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
