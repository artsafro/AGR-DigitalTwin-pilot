"""new-case: AGR Tools 1.0 (#1024) branch H: model.grid_cleanup (gridclean_core) and model.glass_planes (glass_core).

Defects of #1024 «редакция 1» rows 17 and 2 are RED on behaviour models written from the measurements (no team code,
#853; team scripts are named by file + SHA256 only):
* T03 (Max 2026, team audit): Border Loop Cleaner `edge_tool.ms` (eb76545e…d7cb) dissolves loops across UV seams;
  AGR Loop Cleaner v3 `AGR_Loop_Cleaner_v3.ms` (bd82c16c…a866) leaves hidden copies; `IN_tools-detriangulator.mcr`
  (2c41bfdb…2101) sets SG 0 and crashes without map channel 1; thresholds in scene millimetres; `VertexEdgeSplit_UI_v2.ms`
  (d9288242…05f6) splits one T-vertex per edge;
* GeoAGR runtime findings (Max 2026): T08-04 Edges Weld (`GeoAGR.ms:51802`) welds the whole object; T08-05/06
  Detriangulate (`GeoAGR.ms:48104`) silently does nothing without the implicit global `poly`; T08-07 Target Weld hits a
  shifted index on the second weld; T08-16 Corners Weld (`GeoAGR.ms:51542`) without a selection welds all at 1 mm;
* glass: the pilot's own `jobs/vyatskaya-tow02/scripts/clean_glass_blender.py` (dissolve + join_corners only) keeps
  frame faces, both panes of a package and a plane sticking out of the corner.
GREEN on gridclean_core / glass_core. The Max side (copies, one undo, no hidden objects, cm scene) is the native run
tests/max_tools/run_agr_tools_grid_glass_native.py.
"""
import copy
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'
sys.path.insert(0, str(ROOT / 'test-polygon/stations'))
import H_build as hb  # noqa: E402


def _load(name, alias):
    spec = importlib.util.spec_from_file_location(alias, PKG / name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


gc = _load('gridclean_core.py', 'agr_tools_gridclean_core_h')
gl = _load('glass_core.py', 'agr_tools_glass_core_h')
OPTS = gc.options({})
GOPTS = gl.options({})


def red_green(prop, source, impl):
    assert not prop(source()), 'source model already satisfies the property: not a regression'
    assert prop(impl())


def digest(mesh):
    return hashlib.sha256(json.dumps(mesh, sort_keys=True).encode()).hexdigest()


def corner_ids(mesh, pts):
    out = []
    for p in pts:
        hit = [i for i, q in enumerate(mesh['verts']) if math.dist(p, q) < 1e-9]
        out.append(hit[0] if hit else None)
    return out


def corners_in_place(mesh, pts):
    return all(any(math.dist(p, q) < 1e-9 for q in mesh['verts']) for p in pts)


# ---- source behaviour models -----------------------------------------------------------------------------------
def blc_source(mesh):
    """Border Loop Cleaner as measured (T03): dissolves an edge loop whatever the UV seam on it."""
    m = gc.copy_mesh(mesh)
    for loop in gc._edge_loops(gc.copy_mesh(mesh)):
        for (a, b) in loop:
            uses = gc.edges(m).get((a, b), ())
            if len(uses) != 2:
                continue
            f1, f2 = uses[0][0], uses[1][0]
            got = gc._merge_rings(m['faces'][f1], m['faces'][f2], a, b)
            if got is None:
                continue
            m['faces'][f1] = dict(m['faces'][f1], v=got[0], uv=got[1])
            del m['faces'][f2]
    return m


def detri_source(mesh, poly_global=True):
    """IN_tools-detriangulator / GeoAGR Detriangulate as measured: needs map channel 1 (crash), sets SG 0; GeoAGR
    reads the implicit global `poly` (T08-05/06): without it nothing happens and nothing is said."""
    if not poly_global:
        return gc.copy_mesh(mesh)
    if not mesh['uv']:
        raise RuntimeError('-- Unknown property: "getMapFace" in undefined')
    m = gc.copy_mesh(mesh)
    gc.detriangulate(m, dict(OPTS, coplanar_deg=180.0))
    for f in m['faces']:
        f['sg'] = 0
    return m


def ves_source(mesh, tol):
    """VertexEdgeSplit as measured (T03): one T-vertex per edge."""
    m = gc.copy_mesh(mesh)
    found = gc.t_vertices(m, tol)
    first = {}
    for fi, ci, v, t in found:
        first.setdefault((fi, ci), (fi, ci, v, t))
    keep = set(first.values())
    by_edge = {}
    for fi, ci, v, t in keep:
        by_edge.setdefault((fi, ci), []).append((t, v))
    for (fi, ci), items in by_edge.items():
        f = m['faces'][fi]
        t, v = items[0]
        f['v'].insert(ci + 1, v)
        if f['uv'] is not None:
            p, q = f['uv'][ci], f['uv'][(ci + 1) % (len(f['uv']))]
            f['uv'].insert(ci + 1, [p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t])
    return m


def weld_source_whole(mesh, thr):
    """GeoAGR Edges Weld LMB (T08-04) / Corners Weld without a selection (T08-16): weld every vertex of the object."""
    m = gc.copy_mesh(mesh)
    gl.weld_all(m, thr)
    return m


def target_weld_source(mesh, pairs):
    """GeoAGR Target Weld (T08-07): pairs of 1-based indices welded one after another; each weld deletes a vertex and
    shifts the higher indices, the second pair then names a different vertex."""
    m = gc.copy_mesh(mesh)
    verts = m['verts']
    alive = list(range(len(verts)))  # current index -> original id
    for a, b in pairs:
        src, dst = alive[a - 1], alive[b - 1]
        for f in m['faces']:
            f['v'] = [dst if v == src else v for v in f['v']]
        alive.pop(a - 1)
    return m


def scene_units_source(mesh_scene, thr_mm):
    """T03: thresholds read in scene units while the dialog says mm; in a cm scene 1 «mm» is 1 cm."""
    m = gc.copy_mesh(mesh_scene)
    gl.weld_all(m, thr_mm)
    return m


def glass_source(mesh):
    """clean_glass_blender.py as written: weld 1 mm, dissolve coplanar, drop line points, join corners."""
    m = gc.copy_mesh(mesh)
    gl.weld_all(m, 0.001)
    gl.drop_degenerate(m)
    gl.dissolve_coplanar(m, GOPTS)
    gc.remove_line_vertices(m, set(), {'line_m': 0.002, 'uv_tol': float('inf')})
    gl.join_corners(m, GOPTS)
    gc.remove_line_vertices(m, set(), {'line_m': 0.002, 'uv_tol': float('inf')})
    m, _ = gc.compact(m)
    return m


# ---- options ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('bad', [{'nope': 1}, {'modes': []}, {'modes': ['x']}, {'t_mode': 'glue'}, {'tol_m': 0},
                                 {'tol_m': float('nan')}, {'weld_m': True}, {'line_m': -1}])
def test_grid_options_reject_bad_values(bad):
    with pytest.raises(ValueError):
        gc.options(bad)


@pytest.mark.parametrize('bad', [{'nope': 1}, {'place': 'middle'}, {'from_frame_m': 0}, {'thin_m': 'x'}])
def test_glass_options_reject_bad_values(bad):
    with pytest.raises(ValueError):
        gl.options(bad)


# ---- model.grid_cleanup: acceptance of #1024 row 17 ------------------------------------------------------------
def test_facade_acceptance_zero_t_same_islands_sg_matid_corners_in_place():
    src = hb.facade()
    before = gc.stats(src)
    assert before['t_vertices'] == 2 and before['tris'] > 80 and before['uv_islands'] == 2
    keep = digest(src)
    res = gc.clean(src, OPTS)
    assert digest(src) == keep, 'the core changed its input (the original must stay byte-identical)'
    after = gc.stats(res['mesh'])
    assert res['skipped'] is None and res['findings'] == []
    assert after['t_vertices'] == 0 and after['tris'] == 0 and after['ngons'] == 0
    assert (after['uv_islands'], after['sgs'], after['mat_ids']) == (2, [1, 2], [1, 2])
    assert corners_in_place(res['mesh'], hb.opening_corners())
    assert res['counts']['quads_made'] > 40 and res['counts']['loops'] >= 1
    assert after['faces'] < before['faces'] // 2


def test_clean_facade_is_a_pass_in_preview():
    res = gc.clean(hb.facade(triangulate=False, tjunctions=False, noise=False, loop=False), OPTS)
    assert gc.preview_findings(res['before'], OPTS) == []
    dirty = gc.clean(hb.facade(), OPTS)
    assert [c for c, _ in gc.preview_findings(dirty['before'], OPTS)] == ['t_junction', 'triangles']


def test_blc_merges_uv_islands_ours_keeps_them():
    m = hb.facade(triangulate=False, tjunctions=False, noise=False)
    red_green(lambda r: gc.uv_islands(r) == 2, lambda: blc_source(m), lambda: gc.clean(m, OPTS)['mesh'])


def test_detriangulator_sg0_red_ours_keeps_sg():
    m = hb.facade(tjunctions=False, noise=False)
    red_green(lambda r: gc.stats(r)['sgs'] == [1, 2], lambda: detri_source(m),
              lambda: gc.clean(m, gc.options({'modes': ['detriangulate']}))['mesh'])


def test_detriangulator_without_channel_1_crashes_ours_skips():
    m = hb.facade(uv=False)
    with pytest.raises(RuntimeError):
        detri_source(m)  # RED: the source dies
    res = gc.clean(m, OPTS)
    assert res['skipped'] and 'channel 1' in res['skipped'] and digest(res['mesh']) == digest(gc.copy_mesh(m))


def test_geoagr_detriangulate_without_global_poly_is_silent_ours_merges():
    m = hb.facade(tjunctions=False, noise=False)
    red_green(lambda r: gc.stats(r)['tris'] == 0, lambda: detri_source(m, poly_global=False),
              lambda: gc.clean(m, gc.options({'modes': ['detriangulate']}))['mesh'])


def test_ves_one_t_per_edge_ours_cuts_all():
    # two T-vertices on one long edge: a bottom quad 0..2 and two top quads 0..0.7, 0.7..1.3, 1.3..2
    m = {'verts': [[0, 0, 0], [2, 0, 0], [2, 0, 1], [0, 0, 1], [0.7, 0, 1], [1.3, 0, 1], [0, 0, 2], [0.7, 0, 2],
                   [1.3, 0, 2], [2, 0, 2]],
         'faces': [{'v': [0, 1, 2, 3], 'uv': None, 'mat': 1, 'sg': 1},
                   {'v': [3, 4, 7, 6], 'uv': None, 'mat': 1, 'sg': 1},
                   {'v': [4, 5, 8, 7], 'uv': None, 'mat': 1, 'sg': 1},
                   {'v': [5, 2, 9, 8], 'uv': None, 'mat': 1, 'sg': 1}], 'uv': False}
    o = gc.options({'modes': ['tjunctions']})
    red_green(lambda r: not gc.t_vertices(r, o['tol_m']), lambda: ves_source(m, o['tol_m']),
              lambda: gc.clean(m, o)['mesh'])


def test_weld_only_in_selection_geoagr_welds_whole_object():
    m = hb.facade_weld()
    sel = [i for i, p in enumerate(m['verts']) if p[0] > 11.9 and p[2] < 1.01]
    outside = {i: list(p) for i, p in enumerate(m['verts']) if i not in sel}
    # an unselected 0.5 mm pair elsewhere: a duplicate point of the left border, must stay apart
    m['verts'].append([0.0, 0.0, 0.0005])
    m['faces'].append({'v': [len(m['verts']) - 1, 1, 2], 'uv': [[0, 0], [0, 0], [0, 0]], 'mat': 1, 'sg': 1})
    o = gc.options({'modes': ['tjunctions'], 't_mode': 'weld', 'weld_m': 0.001})

    outside[len(m['verts']) - 1] = m['verts'][-1]

    def untouched(r):  # every unselected point still there, at its place (the core compacts: compare positions)
        pts = [r['verts'][i] for i in gc.used_verts(r)]
        return all(any(math.dist(q, p) < 1e-12 for q in pts) for p in outside.values())
    red_green(untouched, lambda: weld_source_whole(m, 0.001), lambda: gc.clean(m, o, sel)['mesh'])
    res = gc.clean(m, o, sel)
    assert res['counts']['welded'] == 2


def test_weld_without_selection_is_skipped_geoagr_welds_all():
    m = hb.facade_weld()
    o = gc.options({'modes': ['tjunctions'], 't_mode': 'weld'})
    whole = weld_source_whole(m, 0.001)
    assert len(gc.used_verts(whole)) < len(gc.used_verts(m))  # RED: Corners Weld without selection welds all
    res = gc.clean(m, o, [])
    assert res['skipped'] and 'selection' in res['skipped']
    assert res['counts']['welded'] == 0


def test_target_weld_index_shift_red_ours_one_pass():
    # four points on a line, pairs (1->2) and (3->4) meant on the ORIGINAL ids
    m = {'verts': [[0, 0, 0], [0.0004, 0, 0], [1, 0, 0], [1.0004, 0, 0], [0.5, 0, 1]],
         'faces': [{'v': [0, 2, 4], 'uv': None, 'mat': 1, 'sg': 1}, {'v': [1, 3, 4], 'uv': None, 'mat': 1, 'sg': 1}],
         'uv': False}
    want = {1: 0, 3: 2}

    def right(r):
        return all(v not in gc.used_verts(r) for v in want) and {0, 2, 4} <= set(gc.used_verts(r))
    src = target_weld_source(m, [(2, 1), (4, 3)])
    assert not right(src)  # RED: the second pair hits the shifted index
    mm = gc.copy_mesh(m)
    pairs = gc.weld_selected(mm, [0, 1, 2, 3], 0.001, set())
    assert dict(pairs) == want and right(mm)


def test_thresholds_in_metres_cm_scene_gives_the_metre_result():
    m_m = hb.facade_weld()
    sel = [i for i, p in enumerate(m_m['verts']) if p[0] > 11.9]
    o = gc.options({'modes': ['tjunctions'], 't_mode': 'weld', 'weld_m': 0.001})
    ref = gc.clean(m_m, o, sel)['counts']
    # a cm scene: the glue reads coordinates * units.SystemScale (0.01 m per unit) -> the same metres
    m_cm = hb.facade_weld(scale=100.0)
    back = copy.deepcopy(m_cm)
    back['verts'] = [[c * 0.01 for c in p] for p in back['verts']]
    assert gc.clean(back, o, sel)['counts'] == ref
    # RED: the source reads «1 mm» as 1 scene unit = 1 cm and welds a 5 mm gap that must stay
    gap = {'verts': [[0, 0, 0], [0.5, 0, 0], [0, 0, 100], [100, 0, 0], [100.5, 0, 0]],
           'faces': [{'v': [0, 3, 2], 'uv': None, 'mat': 1, 'sg': 1}, {'v': [1, 4, 2], 'uv': None, 'mat': 1, 'sg': 1}],
           'uv': False}
    assert len(gc.used_verts(scene_units_source(gap, 1.0))) < 5
    gap_m = dict(gap, verts=[[c * 0.01 for c in p] for p in gap['verts']])
    assert gc.clean(gap_m, o, [0, 1, 2, 3, 4])['counts']['welded'] == 0


def test_no_hidden_copies_core_returns_data_only():
    """LC3 left 40 hidden copies (T03). The core never creates objects: one mesh in, one mesh out; the glue makes one
    export copy per node (native run counts hidden objects before/after)."""
    res = gc.clean(hb.facade(), OPTS)
    assert set(res) == {'mesh', 'counts', 'before', 'after', 'protected', 'findings', 'skipped'}
    src = (PKG / 'gridclean_max.py').read_text(encoding='utf-8')
    assert src.count('export_copies(') == 1 and 'isHidden' not in src and 'hide ' not in src


def test_no_maxscript_globals_in_the_glue():
    for name in ('gridclean_max.py', 'glass_max.py'):
        src = (PKG / name).read_text(encoding='utf-8')
        assert 'global ' not in src.replace('global _GRID', '').replace('globals', ''), name
        assert 'clearUndoBuffer' not in src and 'collapseStack' not in src and 'decodeValue' not in src


def test_opening_corners_never_move_in_weld_mode():
    m = hb.facade(triangulate=False, tjunctions=False, noise=False)
    sel = list(range(len(m['verts'])))  # everything selected, 1 m weld radius would collapse corners
    res = gc.clean(m, gc.options({'modes': ['tjunctions'], 't_mode': 'weld', 'weld_m': 0.0001}), sel)
    assert corners_in_place(res['mesh'], hb.opening_corners())


# ---- model.glass_planes: acceptance of #1024 row 2 -------------------------------------------------------------
def quads(m):
    return [f for f in m['faces'] if len(f['v']) == 4]


@pytest.mark.parametrize('kind,faces', [('flat_12', 1), ('bend_30', 2), ('corner_sliver', 2), ('corner_stick', 2),
                                        ('frame_5cm', 1), ('double_film', 1), ('package_f100', 1), ('single', 1)])
def test_glass_acceptance_quads(kind, faces):
    src = hb.glass(kind)
    keep = digest(src)
    res = gl.planes(src, GOPTS)
    assert digest(src) == keep
    m = res['mesh']
    assert len(m['faces']) == faces and len(quads(m)) == faces and res['ambiguous'] == []


def test_corner_90_two_quads_share_the_corner_edge_6_points():
    for kind in ('corner_sliver', 'corner_stick'):
        m = gl.planes(hb.glass(kind), GOPTS)['mesh']
        a, b = m['faces']
        shared = set(a['v']) & set(b['v'])
        assert len(shared) == 2 and len(m['verts']) == 6, kind
        for v in shared:
            assert math.dist(m['verts'][v][:2], [2.0, 0.0]) < 1e-9


def test_glass_source_keeps_frames_packages_and_stick_out():
    for kind in ('frame_5cm', 'package_f100', 'corner_stick'):
        want = 1 if kind != 'corner_stick' else 2
        red_green(lambda r: len(r['faces']) == want and (kind != 'corner_stick' or len(r['verts']) == 6),
                  lambda: glass_source(hb.glass(kind)), lambda: gl.planes(hb.glass(kind), GOPTS)['mesh'])


def test_frame_5cm_only_the_glass_plane_stays():
    res = gl.planes(hb.glass('frame_5cm'), GOPTS)
    m = res['mesh']
    assert all(abs(p[1]) < 1e-9 for p in m['verts'])
    assert {f['mat'] for f in m['faces']} == {1}
    assert res['counts']['frame_faces'] > 0 and res['glass_from_frame_m'] == [0.025]


def test_double_film_1mm_removed():
    res = gl.planes(hb.glass('double_film'), GOPTS)
    assert len(res['mesh']['faces']) == 1 and 'glass_double' in [c for c, _ in res['findings']]


def test_package_one_plane_at_80mm_from_the_frame_face():
    keep = gl.planes(hb.glass('package_f100'), GOPTS)
    ys = {round(p[1], 6) for p in keep['mesh']['verts']}
    assert ys == {0.0804} and keep['glass_from_frame_m'] == [0.0804]  # middle of the package (source 80.4 mm)
    frame = gl.planes(hb.glass('package_f100'), gl.options({'place': 'frame'}))
    assert {round(p[1], 6) for p in frame['mesh']['verts']} == {0.08} and frame['glass_from_frame_m'] == [0.08]


def test_bend_30_keeps_the_bend():
    m = gl.planes(hb.glass('bend_30'), GOPTS)['mesh']
    n1, n2 = (gc.normal(m['verts'], f['v']) for f in m['faces'])
    assert abs(gc._angle_deg(n1, n2) - 30.0) < 1e-6


def test_matid_and_uv_kept():
    src = hb.glass('flat_12')
    m = gl.planes(src, GOPTS)['mesh']
    f, = m['faces']
    assert f['mat'] == 1 and f['uv'] is not None
    src_uv = {(round(u, 9), round(v, 9)) for g in src['faces'] for u, v in g['uv']}
    assert {(round(u, 9), round(v, 9)) for u, v in f['uv']} <= src_uv
    assert sorted({(round(u, 9), round(v, 9)) for u, v in f['uv']}) == [(0, 0), (0, 1), (1, 0), (1, 1)]
    assert gl.udim_tiles(m) == [1001]


def test_not_a_quad_is_ambiguous():
    res = gl.planes(hb.glass('triangle'), GOPTS)
    assert res['ambiguous'] and '3' in res['ambiguous'][0]


def test_single_quad_glass_has_no_findings():
    res = gl.planes(hb.glass('single'), GOPTS)
    assert res['findings'] == [] and res['ambiguous'] == []


def test_glass_cm_scene_same_result():
    a = gl.planes(hb.glass('corner_sliver'), GOPTS)
    cm = hb.glass('corner_sliver', scale=100.0)
    cm['verts'] = [[c * 0.01 for c in p] for p in cm['verts']]
    b = gl.planes(cm, GOPTS)
    assert a['counts'] == b['counts']


# ---- glue wiring (no pymxs) ------------------------------------------------------------------------------------
def test_glue_functions_present_and_registered():
    rt = _load('runtime.py', 'agr_runtime_h')
    for tool, fn in (('model.grid_cleanup', 'model_grid_cleanup'), ('model.glass_planes', 'model_glass_planes')):
        core, name = rt.EDITS_100[tool]
        assert name == fn and tool not in rt.READ_100
        glue = _load(rt.glue_file(core, rt.GLUE_100), 'agr_h_glue_' + fn)
        assert callable(getattr(glue, fn))


def test_parse_dump_roundtrip():
    gm = _load('gridclean_max.py', 'agr_tools_gridclean_max_h')
    text = '3 1 1\n0 0 0\n1 0 0\n0 0 1\n1 2|1 2 3 |0 0 1 0 0 1 \n2 \n\n'
    mesh, sel, hidden = gm.parse_dump(text)
    assert mesh['faces'] == [{'v': [0, 1, 2], 'uv': [[0, 0], [1, 0], [0, 1]], 'mat': 1, 'sg': 2}]
    assert sel == [1] and hidden == [] and mesh['uv'] is True
    tm = [[0, 1, 0], [-1, 0, 0], [0, 0, 2], [5, 6, 7]]
    inv = gm.inverse_rows(tm)
    for p in ([1, 2, 3], [-4, 0.5, 9]):
        w = gm.to_world(p, tm, 0.01)
        back = gm.to_object(w, tm, inv, 0.01)
        assert all(abs(back[i] - p[i]) < 1e-12 for i in range(3))


def test_rebuild_script_fan_and_visibility():
    gm = _load('gridclean_max.py', 'agr_tools_gridclean_max_h2')
    assert gm.fan(3) == [((0, 1, 2), (True, True, True))]
    assert gm.fan(4) == [((0, 1, 2), (True, True, False)), ((0, 2, 3), (False, True, True))]
    # pentagon with a collinear (T) point at index 2: the fan starts there, no zero-area triangle
    v = [[0, 0, 0], [2, 0, 0], [2, 0, 1], [2, 0, 2], [0, 0, 2]]
    ring = [1, 2, 3, 4, 0]  # a fan from corner 1 would give the zero-area triangle 1-2-3
    s0 = gm.best_start(v, ring)
    r = ring[s0:] + ring[:s0]
    assert s0 != 0 and min(gm._tri_area(v[r[0]], v[r[i]], v[r[i + 1]]) for i in range(1, 4)) > 0
    m = {'verts': v, 'faces': [{'v': [0, 1, 2, 3, 4], 'uv': [[0, 0], [1, 0], [1, .5], [1, 1], [0, 1]], 'mat': 3,
                                'sg': 4}], 'uv': True}
    s = gm.mesh_script(7, v, m)
    assert 'getNodeByHandle 7' in s and 'global' not in s
    assert '#(3, 3, 3)' in s and '#(4, 4, 4)' in s and 'convertTo o Editable_Poly' in s
