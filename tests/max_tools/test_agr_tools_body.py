"""new-case: AGR Tools 1.0 (#1024) branch G: body.prepare (1.0.4), model.attach_by_material (1.0.5), model.move_apart (1.0.6).

Plain pytest, no pymxs. Every named defect has a regression: the SOURCE behaviour model (from the lab reports
docs/experiments/model.attach_by_material.md, model.move_apart.md; GeoAGR.ms lines cited there) shows the defect
(RED), the core does not (GREEN). Native Max 2024 behaviour: tests/max_tools/run_agr_tools_body_native.py.
"""
import ast
import importlib.util
import itertools
import math
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'


def _load(name, mod):
    spec = importlib.util.spec_from_file_location(mod, PKG / name)
    m = importlib.util.module_from_spec(spec)
    sys.modules[mod] = m
    spec.loader.exec_module(m)
    return m


cc = _load('contract_core.py', 'agr_tools_contract_core')
m10 = _load('model10_core.py', 'agr_tools_model10_core')
bc = _load('body_core.py', 'agr_tools_body_core')
ec = _load('edit_core.py', 'agr_tools_edit_core_g')


# ---- synthetic data like the lab job 20261106-022928-efe08cb9 ------------------------------------------------------
BOX_AREA = (1.0, 1.0, 1.0, 1.0, 1.0, 1.0)   # 1 m cube: 6 faces of 1 m2 (one face per ID, as quads)
BOX_IDS = (1, 2, 3, 4, 5, 6)                 # a Box primitive carries IDs 1..6 (lab report)


def single(key, name):
    return {'kind': 'single', 'key': key, 'name': name}


def box(h, mat, ids=BOX_IDS, parent=None, children=()):
    return {'handle': h, 'name': 'synthetic_box_{:04d}'.format(h), 'geometry': True, 'material': mat,
            'face_ids': list(ids), 'face_areas': list(BOX_AREA[:len(ids)]), 'parent': parent,
            'children': list(children)}


def plain(n=200):
    mats = [single(1001, 'Mat_A'), single(1002, 'Mat_B'), single(1003, 'Mat_C')]
    return [box(i + 1, mats[i % 3]) for i in range(n)]


def mix():
    """200 boxes: three materials, 10 Multi/Sub (2 slots, own IDs), 5 without material, 4 with another material
    named Mat_A, one child (lab scene `mix`)."""
    a, b, c = single(1001, 'Mat_A'), single(1002, 'Mat_B'), single(1003, 'Mat_C')
    a2 = single(1009, 'Mat_A')
    multi = {'kind': 'multi', 'key': 1100, 'name': 'MS_Two',
             'slots': [{'id': 7, 'key': 1004, 'name': 'Mat_D'}, {'id': 9, 'key': 1002, 'name': 'Mat_B'}]}
    out = []
    for i in range(200):
        h = i + 1
        if i < 10:
            out.append(box(h, multi, ids=(7, 9, 7, 9, 7, 9)))
        elif i < 15:
            out.append(box(h, None))
        elif i < 19:
            out.append(box(h, a2))
        else:
            out.append(box(h, (a, b, c)[i % 3]))
    out[50]['children'] = [51]
    out[51]['parent'] = 51
    return out


# ---- source behaviour models (RED) -------------------------------------------------------------------------------
def src_turbo_one_object(objects):
    """Turbo Attacher «one object» (GeoAGR.ms:55008-55089): the first material of a pair is wrapped into slot 1 of a
    Multi/Sub, every next material is appended; face IDs stay (:55027-55030, :55056-55067); an object without a
    material simply takes the material of its neighbour (:55021-55024)."""
    slots, ids, areas = [], [], []
    prev = None
    for o in objects:
        mat = o['material'] if o['material'] is not None else prev
        prev = mat
        keys = [s['key'] for s in mat['slots']] if mat['kind'] == 'multi' else [mat['key']]
        for k in keys:
            if k not in [s['key'] for s in slots]:
                slots.append({'id': len(slots) + 1, 'key': k, 'name': ''})
        ids += o['face_ids']
        areas += o['face_areas']
    merged = {'handle': 1, 'name': objects[0]['name'], 'geometry': True,
              'material': {'kind': 'multi', 'key': -1, 'name': '', 'slots': slots},
              'face_ids': ids, 'face_areas': areas}
    return merged


def src_turbo_by_name(objects):
    """cb_byName (lab): materials grouped by NAME; a second material «Mat_A» takes the first's slot -> lost."""
    first_of = {}
    for o in objects:
        m = o['material']
        if m is not None and m['kind'] == 'single':
            first_of.setdefault(m['name'], m['key'])
    out = []
    for o in objects:
        m = o['material']
        if m is not None and m['kind'] == 'single':
            m = single(first_of[m['name']], m['name'])
        out.append(dict(o, material=m))
    return out


def src_move_faces(gap_su, lo, hi, to):
    """Move Faces ЛКМ (GeoAGR.ms:49657, test :49812 `d >= min and d <= min`): only d == min moves; each side moves
    To from the middle -> final gap 2*To. Everything in system units (lab: the cm scene finds only gap 0)."""
    if gap_su >= lo and gap_su <= lo:
        return 2 * to
    return gap_su


def src_move_verts(gap_su, lo, hi, to, kind):
    """Move Verts ЛКМ (GeoAGR.ms:50241): bi pair in range -> 2*To; co-directional pair: both planes move together,
    the gap stays (lab table)."""
    if lo <= gap_su <= hi and kind == 'bi':
        return 2 * to
    return gap_su


# ---- model.attach_by_material ----------------------------------------------------------------------------------
def test_attach_default_is_keep_split_by_instance():
    plan = m10.attach_plan(plain(), None)
    assert plan['mode'] == 'split'
    assert [g['name'] for g in plan['groups']] == ['BODY_MatA_001', 'BODY_MatB_001', 'BODY_MatC_001']
    assert [len(g['members']) for g in plan['groups']] == [67, 67, 66]


@pytest.mark.parametrize('scene', ['plain', 'mix'])
def test_red_green_one_object_recolours_faces(scene):
    """Defect L14-1 (Mat_B 402 -> 201 m2): the source's «one object» changes the material faces show."""
    objs = plain() if scene == 'plain' else mix()
    before = m10.material_areas(objs)
    src = m10.material_areas([src_turbo_one_object(objs)])
    assert m10.compare_areas(before, src), 'source model should recolour (RED)'
    plan = m10.attach_plan(objs, {'mode': 'one'})
    g, = plan['groups']
    after = m10.material_areas([m10.merged_object(plan, g, objs)])
    assert not m10.compare_areas(before, after)
    assert [s['id'] for s in g['slots']] == list(range(1, len(g['slots']) + 1))


@pytest.mark.parametrize('scene', ['plain', 'mix'])
def test_keep_split_keeps_every_face_material(scene):
    objs = plain() if scene == 'plain' else mix()
    before = m10.material_areas(objs)
    plan = m10.attach_plan(objs, {})
    after = m10.material_areas([m10.merged_object(plan, g, objs) for g in plan['groups']])
    assert not m10.compare_areas(before, after)


def test_red_green_no_material_takes_neighbour():
    """Defect L14-2: 30 m2 without a material got a foreign material; here -> slot No_Material."""
    objs = mix()
    src = m10.material_areas([src_turbo_one_object(objs)])
    assert None not in src  # RED: the faces without material are gone into a neighbour's material
    plan = m10.attach_plan(objs, {'mode': 'one'})
    g, = plan['groups']
    nm = [s for s in g['slots'] if s['key'] is None]
    assert nm and nm[0]['name'] == 'No_Material'
    after = m10.material_areas([m10.merged_object(plan, g, objs)])
    assert after[None] == pytest.approx(30.0)
    split = m10.attach_plan(objs, {})
    assert any(g['kind'] == 'none' and g['name'] == 'BODY_NoMaterial_001' for g in split['groups'])
    assert all(any(c == 'no_material' for c, _ in split['findings'][h]) for h in range(11, 16))


def test_red_green_same_name_material_kept_apart():
    """Defect L14-3: by name the second «Mat_A» vanished; here by instance + warning same_name_material."""
    objs = mix()
    before = m10.material_areas(objs)
    assert m10.compare_areas(before, m10.material_areas(src_turbo_by_name(objs)))  # RED
    plan = m10.attach_plan(objs, {})
    names = [g['name'] for g in plan['groups']]
    assert 'BODY_MatA_001' in names and 'BODY_MatA_002' in names
    assert plan['warnings'] and 'Mat_A' in plan['warnings'][0]
    assert any(c == 'same_name_material' for c, _ in plan['findings'][16])


def test_red_green_children_reparented_or_refused():
    """Defect L14-4: children were attached silently, the hierarchy lost. A child outside the selection is
    re-parented to the result (default) or the parent is refused with a reason."""
    objs = plain(6)
    objs[0]['children'] = [99]
    plan = m10.attach_plan(objs, {})
    g = next(g for g in plan['groups'] if 1 in g['members'])
    assert g['reparent'] == [[99, 1]]
    plan = m10.attach_plan(objs, {'children': 'refuse'})
    assert plan['skipped'][0][0] == 1 and 'child' in plan['skipped'][0][2]
    assert all(1 not in g['members'] for g in plan['groups'])


def test_red_green_result_name_is_k1():
    """Defect L14-5: the result took the first object's name (synthetic_box_0064_nomat); here BODY_<material>_NNN,
    unique against the scene (redaction 1: QuickAttach duplicates ATT_<mat>_part)."""
    objs = plain(6)
    plan = m10.attach_plan(objs, {}, taken={'BODY_MatA_001'})
    assert [g['name'] for g in plan['groups']] == ['BODY_MatA_002', 'BODY_MatB_001', 'BODY_MatC_001']
    for g in plan['groups']:
        assert cc.BODY_RE.match(g['name'])
    one = m10.attach_plan(objs, {'mode': 'one'})
    assert one['groups'][0]['name'] == 'BODY_Attached_001'


def test_attach_tokens_and_errors():
    assert m10.material_token('Кирпич_красный 2') == 'Kirpichkrasnyy2'
    assert m10.material_token(None) == 'NoMaterial'
    assert m10.material_token('___') == 'Mat'
    with pytest.raises(ValueError, match='empty selection'):
        m10.attach_plan([], {})
    with pytest.raises(ValueError, match='unknown'):
        m10.attach_plan(plain(3), {'by_name': True})
    with pytest.raises(ValueError, match='mode'):
        m10.attach_plan(plain(3), {'mode': 'binary'})
    helper = {'handle': 7, 'name': 'Point001', 'geometry': False, 'material': None, 'face_ids': [], 'face_areas': [],
              'parent': None, 'children': []}
    with pytest.raises(ValueError, match='nothing to attach'):
        m10.attach_plan([helper], {})
    plan = m10.attach_plan(plain(3) + [helper], {})
    assert plan['skipped'][0][1] == 'Point001'


def test_shown_multi_wraps_and_empty_slot():
    mat = {'kind': 'multi', 'key': 5, 'name': 'M', 'slots': [{'id': 2, 'key': 10, 'name': 'a'},
                                                             {'id': 4, 'key': None, 'name': None}]}
    assert m10.shown(mat, 2) == (10, 'a')
    assert m10.shown(mat, 4) is None
    assert m10.shown(mat, 3) == (10, 'a')       # outside the ID list: wraps by index ((3-1) mod 2 = 0)
    assert m10.shown(mat, 6) is None


def test_attach_plan_2000_is_fast():
    objs = plain(2000)
    t = time.perf_counter()
    plan = m10.attach_plan(objs, {'mode': 'one'})
    assert time.perf_counter() - t < 2.0
    assert len(plan['groups'][0]['members']) == 2000


# ---- model.move_apart ------------------------------------------------------------------------------------------
def quad(z, flip=False, size=1.0, shift=(0.0, 0.0)):
    x0, y0 = shift
    pts = [[x0, y0, z], [x0 + size, y0, z], [x0 + size, y0 + size, z], [x0, y0 + size, z]]
    face = [0, 1, 2, 3] if not flip else [3, 2, 1, 0]
    return {'verts': pts, 'faces': [face]}


def pair(gap_m, kind, scale=1.0):
    """Two 1x1 m quads (lab): `bi` back to back (lower faces down, upper faces up), `co` both facing up.
    scale: metres per system unit is applied by the HOST; the core always receives metres."""
    lower = quad(0.0, flip=True)
    upper = quad(gap_m, flip=(kind == 'co'))
    if kind == 'co':
        lower = quad(0.0)
        upper = quad(gap_m)
    return [lower, upper]


GAPS_MM = (0, 1, 2, 5, 10, 15, 20, 25)
RANGES_MM = {'main': (0, 2, 3), 'coplanar': (5, 20, 10), 'wide': (0, 20, 10)}


def _gap_after(objs, plan):
    after = m10.apply_moves(objs, plan['moves'])
    return abs(after[1]['verts'][0][2] - after[0]['verts'][0][2]), after


@pytest.mark.parametrize('kind', ['bi', 'co'])
@pytest.mark.parametrize('rng', sorted(RANGES_MM))
@pytest.mark.parametrize('units', ['m', 'cm'])
def test_move_apart_grid(kind, rng, units):
    """Lab grid: 8 gaps x 3 ranges x bi/co x m/cm. In range -> gap after = To +- 0.01 mm; outside -> unchanged;
    lateral shift <= 0.01 mm. The cm scene gives the same table (metres via units.SystemScale in the host)."""
    lo, hi, to = RANGES_MM[rng]
    k = 0.01 if units == 'cm' else 1.0
    for g in GAPS_MM:
        objs = pair(g / 1000.0, kind)
        # the host converts system units to metres: round-trip through the scene units like host_max.mesh
        objs = [{'verts': [[c / k * k for c in p] for p in o['verts']], 'faces': o['faces']} for o in objs]
        plan = m10.move_plan(objs, {'min_mm': lo, 'max_mm': hi, 'to_mm': to})
        got, after = _gap_after(objs, plan)
        if lo <= g <= hi:
            assert len(plan['pairs']) == 1 and plan['pairs'][0]['kind'] == kind, (g, plan['pairs'])
            assert got == pytest.approx(to / 1000.0, abs=1e-5), (kind, rng, g, got)
        else:
            assert not plan['pairs'] and got == pytest.approx(g / 1000.0, abs=1e-12)
        for o, a in zip(objs, after):
            for p, q in zip(o['verts'], a['verts']):
                assert math.hypot(q[0] - p[0], q[1] - p[1]) <= 1e-8  # lateral shift


def test_red_green_t08_02_move_faces_range():
    """Defect T08-01/02 (GeoAGR.ms:49812): 10 mm in [5, 20] is never moved by Move Faces; here moved to To."""
    assert src_move_faces(10, 5, 20, 3) == 10  # RED: unchanged
    objs = pair(0.010, 'bi')
    plan = m10.move_plan(objs, {'min_mm': 5, 'max_mm': 20, 'to_mm': 25})
    got, _ = _gap_after(objs, plan)
    assert got == pytest.approx(0.025, abs=1e-5)


def test_red_green_to_is_final_gap():
    """Defect L14 «2*To»: each side moved To, final gap 2*To (owner 06.11.2026: To = the final gap)."""
    assert src_move_verts(0, 0, 0.002, 0.003, 'bi') == pytest.approx(0.006)  # RED
    objs = pair(0.0, 'bi')
    plan = m10.move_plan(objs, {'range': 'main', 'to_mm': 3})
    got, after = _gap_after(objs, plan)
    assert got == pytest.approx(0.003, abs=1e-9)
    # both faces of a double plane move, each along its own normal by To/2
    assert after[0]['verts'][0][2] == pytest.approx(-0.0015) and after[1]['verts'][0][2] == pytest.approx(0.0015)


def test_red_green_cm_scene_range_in_metres():
    """Defect L14: in a cm scene the source reads ranges/To in system units -> only gap 0 is found."""
    gap_cm = 1.0  # 10 mm in a cm scene
    assert src_move_verts(gap_cm, 0.005, 0.02, 0.01, 'bi') == gap_cm  # RED: 1.0 su is outside [0.005, 0.02] su
    k = 0.01
    lower, upper = quad(0.0, flip=True), quad(gap_cm, flip=False)
    objs = [{'verts': [[c * k for c in p] for p in o['verts']], 'faces': o['faces']} for o in (lower, upper)]
    plan = m10.move_plan(objs, {'range': 'coplanar'})
    got, _ = _gap_after(objs, plan)
    assert got == pytest.approx(0.020, abs=1e-5)


def test_red_green_codirectional_pair_opens():
    """Defect L14: Move Verts moves both co-directional planes together, the gap stays; here one side moves."""
    assert src_move_verts(0.001, 0, 0.002, 0.003, 'co') == 0.001  # RED
    objs = pair(0.001, 'co')
    plan = m10.move_plan(objs, {'range': 'main'})
    got, after = _gap_after(objs, plan)
    assert got == pytest.approx(0.003, abs=1e-9)
    assert after[0]['verts'] == objs[0]['verts']  # the back face stays


def test_move_apart_facing_pair_and_tilt():
    lower, upper = quad(0.0), quad(0.004, flip=True)  # facing each other (a slit)
    plan = m10.move_plan([lower, upper], {'min_mm': 0, 'max_mm': 5, 'to_mm': 10})
    got, after = _gap_after([lower, upper], plan)
    assert got == pytest.approx(0.010, abs=1e-9)
    assert after[0]['verts'][0][2] == pytest.approx(-0.003)
    tilted = {'verts': [[0, 0, 0.001], [1, 0, 0.001 + math.tan(math.radians(0.5))],
                        [1, 1, 0.001 + math.tan(math.radians(0.5))], [0, 1, 0.001]], 'faces': [[0, 1, 2, 3]]}
    assert m10.move_plan([quad(0.0, flip=True), tilted], {'range': 'all', 'angle_deg': 1.0})['pairs']
    assert not m10.move_plan([quad(0.0, flip=True), tilted], {'range': 'all', 'angle_deg': 0.1})['pairs']


def test_move_apart_far_from_zero_and_no_overlap():
    far = 2345678.0
    a = quad(10.0, flip=True, shift=(far, far))
    b = quad(10.0005, shift=(far, far))
    plan = m10.move_plan([a, b], {'range': 'main'})
    assert len(plan['pairs']) == 1
    side = quad(0.001, shift=(1.0, 0.0))  # touching along an edge, no overlap in projection
    assert not m10.move_plan([quad(0.0, flip=True), side], {'range': 'main'})['pairs']


def test_move_apart_duplicate_box_corners_sum():
    """A duplicated box (every face co-planar with its twin): the twin grows by To on every side (orthogonal shifts
    sum at the corners), every pair reaches To."""
    pts = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]]
    faces = [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
    objs = [{'verts': pts, 'faces': faces}, {'verts': [list(p) for p in pts], 'faces': faces}]
    plan = m10.move_plan(objs, {'range': 'main'})
    assert len(plan['pairs']) == 6 and not plan['skipped']
    after = m10.apply_moves(objs, plan['moves'])
    for p in plan['pairs']:
        assert m10.gap_after(after, p) == pytest.approx(0.003, abs=1e-9)
    assert after[0]['verts'] == objs[0]['verts']


def test_move_apart_report_rows_and_options():
    objs = pair(0.001, 'bi')
    plan = m10.move_plan(objs, {})
    row = m10.pair_row(plan['pairs'][0], ['Lower', 'Upper'])
    assert row == {'a': ['Lower', 1], 'b': ['Upper', 1], 'kind': 'bi', 'gap_mm': 1.0, 'overlap_m2': 1.0}
    assert plan['faces'] == {0: [1], 1: [1]}
    for bad in ({'to_mm': 0}, {'min_mm': 5, 'max_mm': 1}, {'range': 'x'}, {'dist': 1}, {'to_mm': float('nan')}):
        with pytest.raises(ValueError):
            m10.move_options(bad)
    with pytest.raises(ValueError, match='empty'):
        m10.move_plan([], {})


def test_no_maxscript_globals_in_glue():
    """Defect S-09 / T08-20 (GeoAGR.ms:50282): `::dist` leaked as a global. The glue never declares a MAXScript
    global: every rt.execute string is a block expression `( ... )` without `global`."""
    for name in ('model10_max.py', 'body_max.py'):
        tree = ast.parse((PKG / name).read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, 'attr', None) == 'execute':
                text = ''.join(c.value for c in ast.walk(node.args[0]) if isinstance(c, ast.Constant)
                               and isinstance(c.value, str))
                assert text.startswith('(') and 'global' not in text and '::' not in text, (name, text)


# ---- body.prepare ----------------------------------------------------------------------------------------------
def body5():
    mats = ['Кирпич', 'Brick', 'Brick', None, 'Glass_01']
    return [{'handle': i + 1, 'name': 'Box{:03d}'.format(i + 1), 'kind': 'geometry', 'role': None,
             'material': mats[i], 'layer': '0', 'z_m': None} for i in range(5)]


def test_body_prepare_acceptance_5_objects_3_heights():
    """#1024 1.0.4: body of 5 objects + 3 clicks -> roles, two storeys and the roof (names: see deviation)."""
    plan = bc.prepare_plan(body5(), [], {'levels': [0.0, 3.3, 9.9]})
    assert sorted(r for _h, r in plan['roles']) == ['body'] * 5
    assert [lv['name'] for lv in plan['levels']] == ['LEVEL_L1', 'LEVEL_L2', 'LEVEL_roof']
    assert [n for _h, _o, n in plan['renames']] == ['BODY_Kirpich_001', 'BODY_Brick_001', 'BODY_Brick_002',
                                                    'BODY_NoMaterial_001', 'BODY_Glass01_001']
    assert all(lay == 'BODY_main' for _h, lay in plan['layers'])
    assert not plan['ambiguous'] and not plan['findings']
    assert plan['passport']['roles'] == {'body': 5}
    assert [x['name'] for x in plan['passport']['levels']] == ['LEVEL_L1', 'LEVEL_L2', 'LEVEL_roof']


def test_body_prepare_repeated_height_refused():
    plan = bc.prepare_plan(body5(), [], {'levels': [3.0, 3.0005, 6.0]})
    assert plan['ambiguous'] and '1 mm' in plan['ambiguous'][0]
    scene = [{'handle': 50, 'name': 'LEVEL_L1', 'z_m': 6.0}]
    plan = bc.prepare_plan(body5(), scene, {'levels': [6.0004], 'level_names': ['L2']})
    assert plan['ambiguous'] and 'LEVEL_L1' in plan['ambiguous'][0] and not plan['levels']


def test_body_prepare_level_names_by_extractor_rule():
    """Deviation: the acceptance's LEVEL_1 breaks mesh.py:27 (a letter after LEVEL_); the core refuses it."""
    assert bc.level_name_problem('LEVEL_1')
    assert bc.level_name_problem('LEVEL_roof001')
    assert bc.level_name_problem('LEVEL_L1.001')
    assert bc.level_name_problem('LEVEL_L1') is None and bc.level_name_problem('LEVEL_roof') is None
    plan = bc.prepare_plan(body5(), [], {'levels': [0.0, 3.0], 'level_names': ['1', 'roof']})
    assert plan['ambiguous'] and 'LEVEL_1' in plan['ambiguous'][0]


def test_body_prepare_selected_helpers_and_roles():
    objs = body5()[:2] + [
        {'handle': 10, 'name': 'LEVEL_roof001', 'kind': 'helper', 'role': None, 'material': None, 'layer': '0',
         'z_m': 9.0},
        {'handle': 11, 'name': 'LEVEL_L1', 'kind': 'helper', 'role': 'helper', 'material': None,
         'layer': 'HELPER_main', 'z_m': 0.0},
        {'handle': 12, 'name': 'LEVEL_L0', 'kind': 'helper', 'role': None, 'material': None, 'layer': '0',
         'z_m': 0.0005},
        {'handle': 13, 'name': 'Wall', 'kind': 'geometry', 'role': 'wall', 'material': 'B', 'layer': '0',
         'z_m': None},
        {'handle': 14, 'name': 'BODY_Brick_001', 'kind': 'geometry', 'role': 'body', 'material': 'Brick',
         'layer': 'BODY_x', 'z_m': None},
        {'handle': 15, 'name': 'Cam', 'kind': 'other', 'role': None, 'material': None, 'layer': '0', 'z_m': None}]
    scene = [{'handle': o['handle'], 'name': o['name'], 'z_m': o['z_m']} for o in objs if o['kind'] == 'helper']
    plan = bc.prepare_plan(objs, scene, {'roles': {'Box002': 'decor'}})
    codes = {h: [c for c, _ in fs] for h, fs in plan['findings'].items()}
    assert codes[10] == ['level_name']
    assert codes[11] == ['level_duplicate'] and codes[12] == ['level_duplicate']
    assert codes[13] == ['role_unknown']
    roles = dict(plan['roles'])
    assert roles[1] == 'body' and roles[2] == 'decor' and roles[10] == 'helper' and 11 not in roles
    assert 14 not in roles and all(h != 14 for h, _o, _n in plan['renames'])
    assert all(h != 14 for h, _l in plan['layers'])
    assert ('Cam', ) == tuple(i for i, _r in plan['skipped'] if i != 'passport')
    assert all(h != 2 for h, _o, _n in plan['renames'])  # decor keeps its name


def test_body_prepare_options_and_errors():
    with pytest.raises(ValueError, match='empty'):
        bc.prepare_plan([], [], {})
    with pytest.raises(ValueError, match='unknown'):
        bc.options({'levelz': []})
    with pytest.raises(ValueError, match='finite'):
        bc.options({'levels': [float('inf')]})
    with pytest.raises(ValueError):
        bc.options({'roles': {'Box001': 'wall'}})
    with pytest.raises(ValueError, match='level_names'):
        bc.prepare_plan(body5(), [], {'levels': [1.0, 2.0], 'level_names': ['L1']})
    plan = bc.prepare_plan([], [], {'levels': [{'name': 'L0', 'z_m': 0.0}, 3.0]})
    assert [x['name'] for x in plan['levels']] == ['LEVEL_L0', 'LEVEL_roof']
    assert bc.default_level_names(1) == ['roof']
    assert bc.check_after([{'handle': 1, 'name': 'x', 'role': None}], {}) == [(1, 'role_missing',
                                                                                "agr_role None after apply")]


def test_reports_are_valid_edit_reports():
    """The plan lists map onto edit_core reports (preview hash, skipped with reasons)."""
    plan = bc.prepare_plan(body5(), [], {'levels': [0.0, 3.0, 6.0]})
    r = ec.report('body.prepare', 'preview', objects=[ec.entry(o['handle'], o['name']) for o in body5()],
                  done=['x'], skipped_=[ec.skipped(i, why) for i, why in plan['skipped']],
                  ambiguous=plan['ambiguous'], state_hash=ec.fingerprint([1]),
                  extra={'passport': plan['passport'], 'levels': plan['levels']})
    assert ec.check_preview('body.prepare', r) is r


def test_glue_functions_exist_for_dispatcher():
    """EDITS_100 rows of branch G resolve to glue functions (the stub answer not_implemented is gone)."""
    for name, fns in (('body_max.py', ['body_prepare']),
                      ('model10_max.py', ['model_attach_by_material', 'model_move_apart'])):
        tree = ast.parse((PKG / name).read_text(encoding='utf-8'))
        have = {n.name: [a.arg for a in n.args.args] for n in tree.body if isinstance(n, ast.FunctionDef)}
        for fn in fns:
            assert have[fn] == ['ctx', 'mode', 'nodes', 'preview'], (name, fn)
        assert not any(isinstance(n, (ast.Import, ast.ImportFrom)) and 'pymxs' in ast.dump(n) for n in tree.body)


def test_pairs_each_face_once():
    objs = [quad(z / 1000.0, flip=(i % 2 == 0)) for i, z in enumerate((0, 1, 10, 11))]
    plan = m10.move_plan(objs, {'range': 'main'})
    assert sorted((p['a'][0], p['b'][0]) for p in plan['pairs']) == [(0, 1), (2, 3)]
    assert list(itertools.chain.from_iterable(plan['faces'].values())) == [1, 1, 1, 1]
