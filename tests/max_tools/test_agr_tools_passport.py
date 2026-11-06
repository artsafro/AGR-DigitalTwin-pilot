"""new-case: AGR Tools 1.0 (#1024) branch F: project.passport, source.intake, scene.source_class, scene.small_parts,
journal_core (copy into the project), ProjectPassport schema, tools/project/new_project.py.

Plain pytest, no pymxs: cores directly; glue functions with a HostAdapter fake (contract_core.HostAdapter) and the
pymxs touch points patched. Named defects are RED on a behaviour model of the source, GREEN on this branch:
* TOW02 (job-retro-vyatskaya-tow02-pr392.md): no pre-check, a panel source goes to the shell engine;
* D066 threshold: a share at PANEL_HINT_SHARE must be `ambiguous`, never a class nor a crash of the report;
* T08 small parts (GeoAGR-private work/team-scripts-audit/T08/notes/optimizer.md:39): substring keys hit Studio,
  Minute, Шпиль, М120, Стеклопакет; nodes already on `optimize` are counted again; a group member leaves its group.
Native Max 2024 behaviour (fileProperties, layers, one undo, copies): run_agr_tools_passport_native.py.
"""
import contextlib
import copy
import importlib.util
import json
import math
import os
import random
import sys
import time
import types
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'


def _load(name, key):
    spec = importlib.util.spec_from_file_location(key, PKG / name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


pc = _load('passport_core.py', 'agr_tools_passport_core_f')
sc = _load('scene10_core.py', 'agr_tools_scene10_core_f')
ic = _load('intake_core.py', 'agr_tools_intake_core_f')
jc = _load('journal_core.py', 'agr_tools_journal_core_f')
ec = _load('edit_core.py', 'agr_tools_edit_core_f')
cc = _load('contract_core.py', 'agr_tools_contract_core_f')


# ---- meshes -----------------------------------------------------------------------------------------------
def box(x0=0.0, y0=0.0, z0=0.0, sx=1.0, sy=1.0, sz=1.0):
    v = [[x0 + dx * sx, y0 + dy * sy, z0 + dz * sz] for dz in (0, 1) for dy in (0, 1) for dx in (0, 1)]
    f = [[0, 2, 1], [1, 2, 3], [4, 5, 6], [5, 7, 6], [0, 1, 4], [1, 5, 4], [2, 6, 3], [3, 6, 7], [0, 4, 2],
         [2, 4, 6], [1, 3, 5], [3, 7, 5]]
    return v, f


def quad(x0, y0, z0, w, h):
    v = [[x0, y0, z0], [x0 + w, y0, z0], [x0 + w, y0, z0 + h], [x0, y0, z0 + h]]
    return v, [[0, 1, 2], [0, 2, 3]]


def merge(*meshes):
    verts, tris = [], []
    for v, f in meshes:
        base = len(verts)
        verts += [list(p) for p in v]
        tris += [[base + i for i in t] for t in f]
    return verts, tris


def panels(n, w=1.0, gap=0.5):
    return merge(*[quad(i * (w + gap), 0.0, 0.0, w, 3.0) for i in range(n)])


# ---- scene.source_class: D066 port ------------------------------------------------------------------------
def test_closed_box_is_monolithic_and_40_panels_are_panelised():
    f = sc.source_facts(*box(sx=10, sy=8, sz=30))
    assert (f['class'], f['shell'], f['parts'], f['level'], f['route']) == ('monolithic', True, 1, 'A',
                                                                             'dt spec extract')
    f = sc.source_facts(*panels(40))
    assert f['class'] == 'panelised' and f['parts'] == 40 and abs(f['largest_share'] - 1 / 40) < 1e-12
    assert f['level'] == 'B' and f['route'] == 'measurement+direct-build'


def test_grid_of_5000_parts_is_panelised_within_10_seconds():
    grid = merge(*[quad((i % 100) * 1.5, 0.0, (i // 100) * 3.5, 1.0, 3.0) for i in range(5000)])
    t0 = time.perf_counter()
    f = sc.source_facts(*grid)
    took = time.perf_counter() - t0
    assert f['class'] == 'panelised' and f['parts'] == 5000
    assert took <= 10.0, took


def test_share_exactly_at_the_threshold_is_ambiguous_RED_GREEN():
    # two equal quads: largest share 0.5 == PANEL_HINT_SHARE
    mesh = merge(quad(0, 0, 0, 1, 1), quad(5, 0, 0, 1, 1))
    pilot = pytest.importorskip('dt_ai.spec.source_class')
    with pytest.raises(pilot.SourceClassError):  # RED: the pilot rule raises, there is no report to show
        pilot.classify_source(*mesh)
    f = sc.source_facts(*mesh)  # GREEN: a report with `ambiguous`, never a class
    assert f['class'] == 'ambiguous' and f['level'] == 'C'
    edit = ec
    r = _load('scene10_max.py', 'agr_tools_scene10_max_f').source_class_report(
        edit, sc, [({'handle': 7, 'name': 'SM_Half_Main'}, f)], [{'verts': mesh[0], 'faces': mesh[1]}], [], None)
    assert r['status'] == 'fail' and r['plan']['ambiguous'][0]['item'] == 'SM_Half_Main'
    assert [x['code'] for x in r['objects'][0]['findings']] == ['ambiguous_share']


def test_tow02_panel_source_never_routes_to_the_shell_engine_RED_GREEN():
    source = panels(40)

    def source_route_without_precheck(verts, tris):  # behaviour before scene.source_class: always the extractor
        return 'dt spec extract'
    assert source_route_without_precheck(*source) == 'dt spec extract'  # RED: 5 561 parts went to the shell engine
    assert sc.source_facts(*source)['route'] == 'measurement+direct-build'  # GREEN


@pytest.mark.parametrize('bad,word', [
    (([], []), 'empty'), (([[0, 0, float('nan')], [1, 0, 0], [0, 1, 0]], [[0, 1, 2]]), 'non-finite'),
    (([[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[0, 1, 5]]), 'out of range'),
    (([[0, 0, 0], [1, 0, 0], [2, 0, 0]], [[0, 1, 2]]), 'total area'),
    (([[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[0, 1.5, 2]]), 'fractional'),
])
def test_unusable_meshes_raise(bad, word):
    with pytest.raises(sc.SourceClassError, match=word):
        sc.source_facts(*bad)


def test_port_matches_the_pilot_rule_on_the_same_meshes():
    pilot = pytest.importorskip('dt_ai.spec.source_class')
    rng = random.Random(1024)
    cases = [box(), panels(3), merge(box(), panels(5)), merge(box(sx=0.2, sy=0.2, sz=0.2), quad(3, 0, 0, 9, 9)),
             merge(*[box(x0=i * 3.0) for i in range(4)])]
    for _ in range(25):
        parts = [quad(rng.uniform(0, 50), rng.uniform(0, 5), 0, rng.uniform(0.5, 4), rng.uniform(0.5, 4))
                 for _ in range(rng.randint(1, 8))]
        if rng.random() < 0.3:
            parts.append(box(x0=rng.uniform(60, 70), sx=rng.uniform(0.5, 3)))
        cases.append(merge(*parts))
    for verts, tris in cases:
        mine = sc.source_facts(verts, tris)
        try:
            theirs = pilot.source_facts(verts, tris)
        except pilot.SourceClassError:
            assert mine['class'] == 'ambiguous'
            continue
        assert (mine['parts'], mine['shell'], mine['class']) == (theirs.connected_parts, theirs.shell,
                                                                 theirs.source_class)
        assert abs(mine['largest_share'] - theirs.largest_share) < 1e-12


def test_weld_joins_vertices_within_the_pilot_tolerance():
    v, f = merge(quad(0, 0, 0, 1, 1), quad(1.00004, 0, 0, 1, 1))  # 0.04 mm apart: one part
    v[5][0] = 1.0 + 4e-5
    assert sc.source_facts(v, f)['parts'] == 1
    v2, f2 = merge(quad(0, 0, 0, 1, 1), quad(1.01, 0, 0, 1, 1))  # 1 cm apart: two parts
    assert sc.source_facts(v2, f2)['parts'] == 2


# ---- scene.small_parts --------------------------------------------------------------------------------------
NAMES = ['Bolt_M12', 'Studio_Main', 'Minute_Hand', 'Шпиль', 'М120_Panel', 'Стеклопакет_01', 'Уголок_50']


def _items(names, layer='0', extent=2.0, **kw):
    return [dict({'ref': {'handle': i + 1, 'name': n}, 'name': n, 'layer': layer, 'extent_m': extent,
                  'faces': 120}, **kw) for i, n in enumerate(names)]


def test_small_parts_whole_words_RED_GREEN():
    def zavod_substring_model(name):  # T08 measured hits: stud, nut, шпил, м12, пакет_ (substring, no word border)
        low = name.lower()
        return any(k in low for k in ('bolt', 'уголок', 'stud', 'nut', 'шпил', 'м12', 'пакет_'))
    assert [n for n in NAMES if zavod_substring_model(n)] == NAMES  # RED: all seven, five of them false
    opts = sc.small_options({})
    found, done, skipped = sc.small_parts_plan(_items(NAMES), opts)
    assert done == ['Bolt_M12', 'Уголок_50'] and not skipped  # GREEN: only the two real ones
    assert found['Bolt_M12'] == [('keyword', 'whole word bolt')]
    assert sc.words('Bolt_M12') == ['bolt', 'm'] and sc.words('Стеклопакет_01') == ['стеклопакет']


def test_small_parts_by_size_in_metres_and_options():
    opts = sc.small_options({'max_extent_m': 0.1})
    found, done, _ = sc.small_parts_plan(_items(['Plate_A'], extent=0.08) + _items(['Plate_B'], extent=0.2), opts)
    assert done == ['Plate_A'] and found['Plate_A'][0][0] == 'small_size' and found['Plate_B'] == []
    opts = sc.small_options({'max_extent_m': 0.1, 'max_faces': 50})
    _, done, _ = sc.small_parts_plan(_items(['Plate_A'], extent=0.08), opts)  # 120 faces > 50
    assert done == []
    for bad in ({'max_extent_m': 0}, {'max_extent_m': float('nan')}, {'max_faces': 0}, {'keywords': ['two words']},
                {'nope': 1}, {'layer': ''}):
        with pytest.raises(ValueError):
            sc.small_options(bad)
    _, done, _ = sc.small_parts_plan(_items(['Studio_Main', 'Bolt_X']), sc.small_options({'keywords': ['studio']}))
    assert done == ['Studio_Main']


def test_small_parts_already_on_optimize_are_not_counted_again_RED_GREEN():
    first = _items(['Bolt_M12', 'Уголок_50'], layer='optimize')

    def zavod_counts(items):  # the measured source counted nodes already on optimize again
        return sum(1 for it in items if 'bolt' in it['name'].lower() or 'уголок' in it['name'].lower())
    assert zavod_counts(first) == 2  # RED
    found, done, skipped = sc.small_parts_plan(first, sc.small_options({}))
    assert done == [] and [s[0] for s in skipped] == ['Bolt_M12', 'Уголок_50']  # GREEN: second run, 0 new
    assert all(not v for v in found.values())


def test_small_parts_group_member_is_skipped_RED_GREEN():
    items = _items(['Bolt_M12'], group_member=True)

    def zavod_moves(it):  # T08: a member left its group head's layer
        return True
    assert zavod_moves(items[0])  # RED
    _, done, skipped = sc.small_parts_plan(items, sc.small_options({}))
    assert done == [] and 'group' in skipped[0][1]  # GREEN


def test_small_parts_report_rows_pass_and_fail():
    sm = _load('scene10_max.py', 'agr_tools_scene10_max_f2')
    opts = sc.small_options({})
    items = _items(NAMES)
    r = sm.small_report(ec, sc, 'preview', items, opts, {'x': 1}, raw={})
    codes = {o['name']: [f['code'] for f in o['findings']] for o in r['objects']}
    assert codes['Bolt_M12'] == ['keyword'] and codes['Studio_Main'] == [] and r['status'] == 'fail'
    assert r['plan']['done'] == ['Bolt_M12', 'Уголок_50'] and r['plan']['options_raw'] == {}
    ec.check_preview('scene.small_parts', r)


# ---- source.intake ------------------------------------------------------------------------------------------
def _yup_cm_far():
    """A 20 x 30 x 15 m building whose numbers are in cm, Y up, at 2 345 678 m east (cm read 1:1 as metres)."""
    v, f = box(sx=2000.0, sy=3000.0, sz=1500.0)  # Y is the height (30 m)
    v = [[x + 234567800.0, y, z + 50000.0] for x, y, z in v]
    return v, f


def test_intake_acceptance_cm_yup_far_core():
    v, f = _yup_cm_far()
    opts = ic.options({'source_up_axis': 'Y'})
    plan = ic.normalization([{'name': 'SRC', 'verts': v}], 1.0, opts)
    assert plan['source_units'] == 'cm' and abs(plan['factor'] - 0.01) < 1e-15
    assert plan['origin_m'] == [2345678.0, -515.0, 0.0] or plan['origin_m'][0] == 2345678.0
    out = [ic.apply_matrix(p, plan['matrix_units']) for p in v]
    lo = [min(p[i] for p in out) for i in range(3)]
    hi = [max(p[i] for p in out) for i in range(3)]
    size = [round(h - l, 6) for h, l in zip(hi, lo)]
    assert size == [20.0, 15.0, 30.0]  # metres, Z up: the 30 m height is on Z now
    assert all(-1.0 < c <= 1e-6 or abs(c) < 1.0 for c in lo) and max(abs(c) for c in hi) < 100
    found = ic.findings(plan, opts)['SRC']
    assert [c for c, _ in found] == ['units_scale', 'up_axis', 'far_coordinates']
    norm = ic.passport_normalization(plan)
    assert norm['source_units'] == 'cm' and norm['source_up_axis'] == 'Y' and norm['scale'] == 0.01
    assert norm['origin_m'][0] == 2345678.0


def test_intake_metric_near_source_has_no_findings_and_identity():
    v, f = box(x0=3, y0=4, sx=20, sy=15, sz=30)
    plan = ic.normalization([{'name': 'OK', 'verts': v}], 1.0, ic.options({}))
    assert plan['source_units'] == 'm' and plan['factor'] == 1.0 and plan['origin_m'] == [3.0, 4.0, 0.0]
    assert ic.findings(plan, ic.options({}))['OK'] == []


def test_intake_units_follow_the_scene_unit_and_ambiguous_size_is_an_error():
    v, f = box(sx=2000, sy=1500, sz=3000)  # a cm scene reads 20 x 15 x 30 m: already right
    plan = ic.normalization([{'name': 'A', 'verts': [[c * 0.01 for c in p] for p in v]}], 0.01, ic.options({}))
    assert plan['source_units'] == 'cm' and plan['factor'] == 1.0 and plan['scene_units'] == 'cm'
    tiny = box(sx=0.3, sy=0.3, sz=0.3)[0]
    with pytest.raises(ic.IntakeError, match='ambiguous'):
        ic.normalization([{'name': 'T', 'verts': tiny}], 1.0, ic.options({}))
    plan = ic.normalization([{'name': 'T', 'verts': tiny}], 1.0, ic.options({'source_units': 'm'}))
    assert plan['factor'] == 1.0
    for bad in ({'source_units': 'parsec'}, {'source_up_axis': 'W'}, {'far_m': 0}, {'plausible_m': [5, 1]},
                {'x': 1}):
        with pytest.raises(ic.IntakeError):
            ic.options(bad)
    with pytest.raises(ic.IntakeError, match='empty'):
        ic.normalization([], 1.0, ic.options({}))


def test_intake_axes_rotation_keeps_handedness():
    for axis in 'XYZ':
        r = ic._ROT[axis]
        det = (r[0][0] * (r[1][1] * r[2][2] - r[1][2] * r[2][1]) - r[0][1] * (r[1][0] * r[2][2] - r[1][2] * r[2][0])
               + r[0][2] * (r[1][0] * r[2][1] - r[1][1] * r[2][0]))
        assert det == 1, axis
        up = {'X': [1, 0, 0], 'Y': [0, 1, 0], 'Z': [0, 0, 1]}[axis]
        assert ic.rotate(up, axis) == [0, 0, 1]


class FakeHost(cc.HostAdapter):
    host = 'offline'

    def __init__(self, objs, doc='untitled', m=1.0):
        self.objs, self._doc, self._m, self.undos = objs, doc, m, 0

    def doc(self):
        return self._doc

    def m_per_unit(self):
        return self._m

    def refs(self, nodes):
        return [cc.obj_ref('offline', self._doc, self.objs[n]['handle'], n) for n in nodes]

    def resolve(self, refs):
        return [r['name'] for r in refs]

    def selection(self):
        return self.refs(list(self.objs))

    def mesh(self, ref):
        o = self.objs[ref['name']]
        return {'verts': [[c * self._m for c in p] for p in o['verts']], 'faces': o['faces'],
                'mat_ids': o.get('mat_ids', [1] * len(o['faces'])), 'ref': ref}

    def get_prop(self, ref, key):
        return self.objs[ref['name']].get('props', {}).get(key)

    def set_prop(self, ref, key, value):
        self.objs[ref['name']].setdefault('props', {})[key] = str(value)

    @contextlib.contextmanager
    def undo(self, label):
        self.undos += 1
        yield


def test_intake_glue_plan_and_class_for_the_passport():
    im = _load('intake_max.py', 'agr_tools_intake_max_f')
    v, f = _yup_cm_far()
    host = FakeHost({'SRC_Main': {'handle': 11, 'verts': v, 'faces': f, 'mat_ids': [3] * 6 + [7] * 6}})
    ctx = types.SimpleNamespace(core=ic, edit=ec, host=host)
    meshes = [host.mesh(r) for r in host.refs(['SRC_Main'])]
    opts = ic.options({'source_up_axis': 'Y'})
    plan, found, facts, mats = im.plan_of(ctx, meshes, 1.0, opts, sc)
    assert facts['class'] == 'monolithic' and facts['level'] == 'A' and mats == [3, 7]
    r = im.build_report(ctx, 'preview', meshes, plan, found, facts, mats, {'s': 1}, ['SRC_Main_AGR_intake_01'],
                        [ec.skipped('material split', 'branch G')], {'options_raw': {'source_up_axis': 'Y'}})
    assert r['status'] == 'fail' and r['plan']['class']['class'] == 'monolithic'
    assert sorted(x['code'] for x in r['objects'][0]['findings']) == ['far_coordinates', 'units_scale', 'up_axis']
    src = ic.passport_source('C:/src/KPP1.fbx', facts)
    p = pc.with_source(pc.new_passport('KPP1'), src, ic.passport_normalization(plan))
    assert p['source']['class'] == 'monolithic' and p['source']['level'] == 'A'
    assert p['normalization']['origin_m'][0] == 2345678.0 and p['normalization']['up_axis'] == 'Z'
    jsonschema.validate(p, json.loads((ROOT / 'schemas/ProjectPassport.schema.json').read_text(encoding='utf-8')))


# ---- passport core + schema ----------------------------------------------------------------------------------
def _schema_file():
    return json.loads((ROOT / 'schemas/ProjectPassport.schema.json').read_text(encoding='utf-8'))


def test_schema_file_is_the_core_schema_and_valid_draft_2020_12():
    assert _schema_file() == json.loads(json.dumps(pc.SCHEMA))
    jsonschema.Draft202012Validator.check_schema(pc.SCHEMA)
    assert tuple(pc.SCHEMA['properties']['parts']['items']['properties']['role']['enum']) == cc.ROLES == pc.ROLES


def test_new_project_on_an_empty_scene_is_valid_by_the_schema():
    p = pc.new_passport('KPP1', title='КПП-1', ts='2026-11-06T10:00:00+03:00')
    jsonschema.validate(p, _schema_file())
    assert [s['id'] for s in p['stages']] == list(range(10)) + ['agent']
    assert all(s['status'] == 'todo' for s in p['stages']) and p['source']['level'] == 'C'
    assert pc.loads(pc.dumps(p)) == p and pc.dumps(p).endswith(b'\n')
    md = pc.markdown(p)
    assert '# Паспорт проекта KPP1' in md and '| agent | todo |' in md


MUTATIONS = [
    lambda p: p.pop('stages'), lambda p: p['stages'].pop(), lambda p: p['source'].update(level='D'),
    lambda p: p['normalization'].update(units='cm'), lambda p: p['parts'].append({'name': 'X', 'role': 'wall'}),
    lambda p: p['openings'].append({'marker': 'OPEN_1', 'window_type': 'WT-07'}),
    lambda p: p['materials'].append({'library_id': 1005}), lambda p: p.update(extra=1),
    lambda p: p.update(schema=True), lambda p: p['normalization'].update(scale=0),
    lambda p: p['stages'][0].update(status='ok'), lambda p: p['stages'][1].update(id=10),
    lambda p: p.update(project_id='bad id'), lambda p: p['journal'].update(tail=[{}] * 51),
    lambda p: p['normalization'].update(origin_m=[0, 0]), lambda p: p['stages'][2].update(started='yesterday'),
    lambda p: p['agent_requests'].append({'id': 'r1', 'stage': 'x', 'status': 'open'}),
    lambda p: p.update(questions=['']), lambda p: p['source'].update(sha256='ABC'),
]


@pytest.mark.parametrize('i', range(len(MUTATIONS)))
def test_broken_passport_is_an_error_like_jsonschema(i):
    bad = copy.deepcopy(pc.new_passport('KPP1'))
    MUTATIONS[i](bad)
    if 'started' not in json.dumps(bad):  # date-time needs the optional rfc3339 validator in jsonschema
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, _schema_file())
    with pytest.raises(pc.PassportError):
        pc.validate(bad)
    with pytest.raises(pc.PassportError):
        pc.loads(json.dumps(bad))


def test_duplicate_stage_and_strict_json_are_errors():
    p = pc.new_passport('KPP1')
    p['stages'][10] = {'id': 0, 'status': 'todo'}
    with pytest.raises(pc.PassportError, match='once each'):
        pc.validate(p)
    with pytest.raises(pc.PassportError, match='duplicate'):
        pc.loads('{"schema": 1, "schema": 1}')
    with pytest.raises(pc.PassportError, match='non-finite'):
        pc.loads('{"x": NaN}')
    with pytest.raises(pc.PassportError, match='not JSON'):
        pc.loads('{')


def test_stage_moves_and_roles_read_back():
    p = pc.set_stage(pc.new_passport('KPP1'), 0, 'work', ts='2026-11-06T10:00:00+03:00')
    p = pc.set_stage(p, 0, 'done', ts='2026-11-06T10:05:30+03:00')
    s = pc.stage(p, 0)
    assert s['seconds'] == 330.0 and s['status'] == 'done'
    p = pc.set_stage(p, 'agent', 'blocked', blockers=['no answer'])
    assert pc.stage(p, 'agent')['blockers'] == ['no answer']
    with pytest.raises(pc.PassportError):
        pc.set_stage(p, 3, 'finished')
    parts, problems = pc.parts_from_roles([
        {'name': 'BODY_Brick_001', 'prop': 'body', 'layer': '0'},
        {'name': 'Glass_1', 'prop': None, 'layer': 'GLASS_main'},
        {'name': 'Wall_1', 'prop': 'wall', 'layer': '0'},
        {'name': 'Roof_1', 'prop': 'roof', 'layer': 'BODY_x'},
        {'name': 'Thing', 'prop': '', 'layer': '0'}])
    assert parts == [{'name': 'BODY_Brick_001', 'role': 'body'}, {'name': 'Glass_1', 'role': 'glass'},
                     {'name': 'Roof_1', 'role': 'roof'}]
    assert {k: v[0] for k, v in problems.items()} == {'Wall_1': 'role_unknown', 'Roof_1': 'role_conflict',
                                                      'Thing': 'role_missing'}
    p = pc.with_parts(pc.new_passport('KPP1'), [{'name': 'BODY_Brick_001', 'role': 'body', 'levels': ['LEVEL_1']}])
    assert pc.with_parts(p, parts)['parts'][0]['levels'] == ['LEVEL_1']  # body.prepare's levels survive a refresh


def test_link_value_round_trip_and_broken_link():
    sha = 'a' * 64
    text = pc.link_value('C:\\proj\\jobs\\KPP1\\passport.json', sha)
    assert pc.parse_link(text) == {'path': 'C:/proj/jobs/KPP1/passport.json', 'sha256': sha}
    assert pc.parse_link(None) is None and pc.parse_link('') is None
    for bad in ('{', '{"path": "x"}', json.dumps({'path': '', 'sha256': sha}), json.dumps({'path': 'x',
                                                                                          'sha256': 'zz'})):
        with pytest.raises(pc.PassportError):
            pc.parse_link(bad)


def test_project_id_from_scene_names():
    assert pc.project_id_from('C:/x/KPP1 v2.max') == 'KPP1_v2'
    assert pc.project_id_from('C:/x/Касаткино.max') is None
    assert pc.project_id_from('untitled') == 'untitled'


# ---- journal copy -----------------------------------------------------------------------------------------
def test_journal_copy_only_grows_and_feeds_the_tail(tmp_path):
    scene = str(tmp_path / 'KPP1.max')
    folder = str(tmp_path / 'journal')
    for i in range(3):
        jc.append(jc.record('scene.source_class', 'preview', 'pass', {'objects': 1}, actor='panel', doc=scene,
                            ts='2026-11-06T10:0{}:00+0300'.format(i)), scene, folder)
    dest = str(tmp_path / 'jobs/KPP1/journal.jsonl')
    got = jc.copy_to(scene, dest, folder)
    assert got['lines'] == 3 and got['added'] == 3 and len(got['tail']) == 3
    other = str(tmp_path / 'KPP1_renamed.max')  # the scene saved under a new name: a new panel journal
    jc.append(jc.record('project.passport', 'apply', 'pass', actor='panel', doc=other), other, folder)
    got = jc.copy_to(other, dest, folder)
    assert got['lines'] == 4 and got['added'] == 1
    got = jc.copy_to(scene, dest, folder)  # nothing new: nothing lost, nothing doubled
    assert got['lines'] == 4 and got['added'] == 0
    lines, bad = jc.read_lines(dest)
    assert [x['tool'] for x in lines] == ['scene.source_class'] * 3 + ['project.passport'] and bad == []
    p = pc.with_journal(pc.new_passport('KPP1'), got['lines'], got['tail'])
    assert p['journal']['lines'] == 4 and len(p['journal']['tail']) == 4


# ---- project.passport glue with a fake host -----------------------------------------------------------------
def _passport_glue(monkeypatch, tmp_path, objs, options=None):
    rt = _load('runtime.py', 'agr_runtime_f')
    pm = _load('passport_max.py', 'agr_tools_passport_max_f')
    store = {}
    monkeypatch.setattr(pm, 'read_link', lambda: store.get('agr_passport'))
    monkeypatch.setattr(pm, 'write_link', lambda text: store.__setitem__('agr_passport', text))
    monkeypatch.setattr(pm, '_nodes', lambda nodes: list(nodes or objs))
    host = FakeHost(objs, doc=str(tmp_path / 'scenes' / 'KPP1.max'))

    def items(ctx, nodes):
        return [{'ref': r, 'name': r['name'], 'prop': host.get_prop(r, 'agr_role'), 'layer': objs[r['name']]['layer']}
                for r in host.refs(nodes)]
    monkeypatch.setattr(pm, 'role_items', items)
    monkeypatch.setenv('AGR_JOURNAL_DIR', str(tmp_path / 'journal'))
    ctx = types.SimpleNamespace(agr=rt, core=pc, edit=ec, emax=None, host=host, options=dict(options or {}))
    return pm, ctx, store, host


def _objs():
    v, f = box()
    return {'BODY_Brick_001': {'handle': 3, 'verts': v, 'faces': f, 'layer': '0', 'props': {'agr_role': 'body'}},
            'GLASS_01': {'handle': 4, 'verts': v, 'faces': f, 'layer': 'GLASS_main'},
            'Thing': {'handle': 5, 'verts': v, 'faces': f, 'layer': '0'}}


def test_passport_create_open_and_never_overwrite(monkeypatch, tmp_path):
    root = tmp_path / 'proj'
    pm, ctx, store, host = _passport_glue(monkeypatch, tmp_path, _objs(), {'root': str(root), 'project_id': 'KPP1'})
    prev = pm.project_passport(ctx, 'preview', None, None)
    assert prev['plan']['action'] == 'create' and not (root / 'jobs').exists()  # preview writes nothing
    codes = {o['name']: [f['code'] for f in o['findings']] for o in prev['objects']}
    assert codes == {'BODY_Brick_001': [], 'GLASS_01': [], 'Thing': ['role_missing']}
    ec.check_preview('project.passport', prev)
    ctx.options = {}
    done = pm.project_passport(ctx, 'apply', None, prev)
    path = root / 'jobs/KPP1/passport.json'
    passport, sha = pc.read(str(path))
    jsonschema.validate(passport, _schema_file())
    assert passport['parts'] == [{'name': 'BODY_Brick_001', 'role': 'body'}, {'name': 'GLASS_01', 'role': 'glass'}]
    assert (root / 'jobs/KPP1/PASSPORT.md').is_file() and (root / 'jobs/KPP1/journal.jsonl').is_file()
    assert pc.parse_link(store['agr_passport'])['sha256'] == sha == done['plan']['sha256']
    # second press: the link opens it; a role change refreshes parts; the old passport goes to history/
    ctx.options = {}
    host.objs['Thing']['props'] = {'agr_role': 'decor'}
    prev2 = pm.project_passport(ctx, 'preview', None, None)
    assert prev2['plan']['action'] == 'open' and prev2['status'] == 'pass'
    pm.project_passport(ctx, 'apply', None, prev2)
    passport2, sha2 = pc.read(str(path))
    assert {'name': 'Thing', 'role': 'decor'} in passport2['parts'] and sha2 != sha
    assert (root / 'jobs/KPP1/history/passport_v001.json').read_bytes() == pc.dumps(passport)


def test_passport_apply_refuses_a_stale_preview_and_a_file_changed_meanwhile(monkeypatch, tmp_path):
    root = tmp_path / 'proj'
    pm, ctx, store, host = _passport_glue(monkeypatch, tmp_path, _objs(), {'root': str(root), 'project_id': 'KPP1'})
    prev = pm.project_passport(ctx, 'preview', None, None)
    host.objs['Thing']['props'] = {'agr_role': 'decor'}  # the scene changed after the preview
    ctx.options = {}
    with pytest.raises(ec.StalePreview):
        pm.project_passport(ctx, 'apply', None, prev)
    assert not (root / 'jobs').exists()
    ctx.options = {'root': str(root), 'project_id': 'KPP1'}
    pm.project_passport(ctx, 'apply', None, pm.project_passport(ctx, 'preview', None, None))
    prev = pm.project_passport(ctx, 'preview', None, None)
    path = root / 'jobs/KPP1/passport.json'
    p = pc.read(str(path))[0]
    p['questions'].append('edited by hand')
    path.write_bytes(pc.dumps(p))  # someone edits the passport between preview and apply
    with pytest.raises(ec.StalePreview):
        pm.project_passport(ctx, 'apply', None, prev)


def test_passport_with_a_broken_schema_is_an_error_and_not_replaced(monkeypatch, tmp_path):
    root = tmp_path / 'proj'
    folder = root / 'jobs/KPP1'
    folder.mkdir(parents=True)
    broken = pc.new_passport('KPP1')
    broken['source']['level'] = 'D'
    (folder / 'passport.json').write_text(json.dumps(broken), encoding='utf-8')
    pm, ctx, store, host = _passport_glue(monkeypatch, tmp_path, _objs(), {'root': str(root), 'project_id': 'KPP1'})
    with pytest.raises(pc.PassportError, match='level'):
        pm.project_passport(ctx, 'preview', None, None)
    assert json.loads((folder / 'passport.json').read_text(encoding='utf-8')) == broken
    store['agr_passport'] = '{"path": 1}'
    with pytest.raises(pc.PassportError, match='broken'):
        pm.project_passport(ctx, 'preview', None, None)


def test_passport_on_an_empty_untitled_scene_needs_only_a_project_id(monkeypatch, tmp_path):
    pm, ctx, store, host = _passport_glue(monkeypatch, tmp_path, {})
    host._doc = 'untitled'
    with pytest.raises(ValueError, match='project id'):
        pm.project_passport(ctx, 'preview', None, None)
    monkeypatch.setenv('AGR_PROJECTS_ROOT', str(tmp_path / 'projects'))
    ctx.options = {'project_id': 'NEW1'}
    prev = pm.project_passport(ctx, 'preview', None, None)
    assert prev['plan']['passport'] == str(tmp_path / 'projects/jobs/NEW1/passport.json')
    assert prev['objects'] == [] and prev['status'] == 'pass'
    ctx.options = {}
    pm.project_passport(ctx, 'apply', None, prev)
    jsonschema.validate(pc.read(prev['plan']['passport'])[0], _schema_file())
    ctx.options = {'nope': 1}
    with pytest.raises(ValueError, match='unknown option'):
        pm.project_passport(ctx, 'preview', None, None)


def test_three_presses_give_three_journal_lines_through_the_dispatcher(monkeypatch, tmp_path):
    rt = _load('runtime.py', 'agr_runtime_f3')
    pm, ctx, store, host = _passport_glue(monkeypatch, tmp_path, _objs(), {'root': str(tmp_path / 'p'),
                                                                          'project_id': 'KPP1'})
    real = rt._load_core

    def fake(name, key):
        if name == 'passport_max.py':
            return pm
        if name == 'host_max.py':
            return types.SimpleNamespace(MaxHost=lambda: host)
        return real(name, key)
    monkeypatch.setattr(rt, '_load_core', fake)
    monkeypatch.setattr(rt, '_scene_doc', lambda: host.doc())
    for _ in range(3):
        r = rt.edits_100('project.passport', 'preview', options={'root': str(tmp_path / 'p'), 'project_id': 'KPP1'})
        assert r['plan']['action'] == 'create'
    lines = jc.tail(host.doc(), 10, str(tmp_path / 'journal'))
    assert [(x['tool'], x['mode'], x['actor']) for x in lines] == [('project.passport', 'preview', 'panel')] * 3
    assert all(x['preview_sha'] for x in lines)
    with pytest.raises(ValueError, match='needs_human'):
        rt.edits_100('project.passport', 'apply', r, actor='mcp')
    assert len(jc.tail(host.doc(), 10, str(tmp_path / 'journal'))) == 4


# ---- new_project CLI, AGENTS.md -----------------------------------------------------------------------------
def test_new_project_cli_creates_checks_and_refuses(tmp_path, capsys):
    spec = importlib.util.spec_from_file_location('agr_new_project_f', ROOT / 'tools/project/new_project.py')
    npj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(npj)
    assert npj.main(['KPP1', '--root', str(tmp_path), '--title', 'КПП-1']) == 0
    path = tmp_path / 'jobs/KPP1/passport.json'
    jsonschema.validate(json.loads(path.read_text(encoding='utf-8')), _schema_file())
    assert npj.main(['--check', str(path)]) == 0 and 'OK KPP1' in capsys.readouterr().out
    assert npj.main(['KPP1', '--root', str(tmp_path)]) == 1  # never overwrites
    p = json.loads(path.read_text(encoding='utf-8'))
    p['stages'] = p['stages'][:5]
    bad = tmp_path / 'bad.json'
    bad.write_text(json.dumps(p), encoding='utf-8')
    assert npj.main(['--check', str(bad)]) == 1 and 'stages' in capsys.readouterr().err
    assert npj.main(['bad id', '--root', str(tmp_path)]) == 1


def test_agents_md_holds_the_passport_rule():
    text = (ROOT / 'AGENTS.md').read_text(encoding='utf-8')
    assert 'passport.json' in text and 'ProjectPassport.schema.json' in text


def test_cores_are_stdlib_only():
    import ast
    for name in ('passport_core.py', 'scene10_core.py', 'intake_core.py', 'journal_core.py'):
        tree = ast.parse((PKG / name).read_text(encoding='utf-8'))
        mods = {a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | \
            {n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        assert mods <= set(sys.stdlib_module_names), (name, mods - set(sys.stdlib_module_names))
    for name in ('passport_max.py', 'scene10_max.py', 'intake_max.py'):
        code = (PKG / name).read_text(encoding='utf-8')
        assert 'decodeValue' not in code and 'clearUndoBuffer' not in code and 'collapseStack' not in code
        assert math.isfinite(1.0)
