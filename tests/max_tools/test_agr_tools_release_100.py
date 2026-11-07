"""new-case: release branch R of AGR Tools 1.0.0 (#1024): the 33 stage buttons of plan 1.0 ship.

RED on main 5cb7d37d: every 1.0 action was wip; a 1.0 row of a shipped version was always «done» on the path page
(roadmap.state looked at `version` only), the plan had no way to say «not in this release» for a branch that misses
the release (SPLIT.md «Порядок слияния» 3), a step row (no own button) was labelled «в версии 1.0» even inside 1.0.0,
and roadmap.load accepted any `deferred` value. Branch Q merged before R (#1085), so nothing is deferred in 1.0.0;
the `deferred` path stays tested on a copy of the plan.
"""
import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'
SUITE = ROOT / 'docs/plans/agr-tools-suite.json'


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


rm = _load(PKG / 'roadmap.py', 'agr_tools_roadmap_r100')
m = _load(PKG / 'ui_model.py', 'agr_tools_ui_model_r100')
TEXT = SUITE.read_text(encoding='utf-8')
suite = rm.load(TEXT)
ROWS = {r['id']: r for r in suite['rows']}
Q = ('npm.to_vpm', 'udim.udims_to_ids')


def test_version_is_100_and_every_stage_button_ships():
    assert m.VERSION == '1.1.0'
    assert set(m.WIP_100) == set() and len(m.ACTIONS_100) == 33 + 4  # 33 buttons of 1.0 + 4 handoff buttons of 1.1
    assert [a.tool for a in m.ACTIONS_100][33:] == ['handoff.export', 'handoff.import', 'handoff.verify',
                                                    'handoff.restore_materials']
    for a in m.ACTIONS_100:
        assert not a.wip and a.tip == m.stage_tip(a.tool), a.tool
        # 1.1: the buttons with a parameter form (FORM_100) press into form_ui, the others straight into edit_ui
        entry = 'form_ui' if a.tool in m.FORM_100 else 'edit_ui'
        assert m.macro_100(a)[1].startswith('(on execute do python.Execute "agr_tools_runtime.{}('.format(entry)), a.tool
        assert m.macro_100(a._replace(wip=True))[1] == '('  # a wip button would be a disabled block


def test_stage_tip_names_the_stage():
    assert m.stage_tip('vpm.build') == '1.0, этап 6 «ВПМ»'
    assert m.stage_tip('pack.deliver') == '1.0, этап 9 «Сдача»'
    assert m.stage_tip('agent.request') == '1.0, этап «Агент»'
    with pytest.raises(KeyError):
        m.stage_tip('qa.xview')


def _deferred_suite(to='1.1'):
    """The plan as it would be if branch Q had missed the release: its rows and step deferred to 1.1 (or later)."""
    d = json.loads(TEXT)
    for r in d['rows']:
        if r['id'] in Q + ('atlas.unatlas',):
            r['deferred'] = to
    return rm.load(json.dumps(d, ensure_ascii=False))


def test_nothing_is_deferred_in_100_and_a_deferred_row_is_not_shipped():
    assert not any(r.get('deferred') for r in suite['rows'])
    v10 = next(v for v in suite['versions'] if v['version'] == '1.0')
    assert v10['status'] == 'done' and 'deferred' not in v10
    for rid in Q + ('atlas.unatlas',):
        assert rm.state(ROWS[rid], '1.0.0') == 'done'
    rows = {r['id']: r for r in _deferred_suite()['rows']}
    for rid in Q + ('atlas.unatlas',):
        r = rows[rid]
        assert r['version'] == '1.0' and r['stage'] == 8
        assert rm.state(r, '1.0.0') == 'planned' and rm.state(r, '1.1.0') == 'done'
        assert rm.planned_label(r) == 'в версии 1.1 (#1024)'
    assert rm.state(ROWS['vpm.build'], '1.0.0') == 'done' and rm.state(ROWS['vpm.build'], '0.9.0') == 'planned'


def test_step_rows_name_their_big_button():
    assert rm.planned_label(ROWS['tex.vpm_sets']) == 'в кнопке vpm.build'
    assert rm.planned_label(ROWS['model.window_placer']) == 'в кнопке ' + ROWS['model.window_placer']['step_of']
    assert rm.planned_label(ROWS['tex.browser']) == 'в версии 1.x'


@pytest.mark.parametrize('rid,value', [
    ('vpm.build', '1.0'),       # not later than its version
    ('vpm.build', '0.9'),       # earlier
    ('vpm.build', 1.1),         # not a string
    ('qa.xview', '1.1'),        # not a stage row
])
def test_roadmap_rejects_a_bad_deferred(rid, value):
    broken = json.loads(TEXT)
    next(r for r in broken['rows'] if r['id'] == rid)['deferred'] = value
    with pytest.raises(ValueError, match='deferred'):
        rm.load(json.dumps(broken, ensure_ascii=False))


def test_rail_shows_released_old_rows_and_a_deferred_row_greyed():
    rail = m.rail(suite['blocks'], suite['rows'])
    done = {m.row_of(a.id) for _, d, _ in rail for a in d}
    assert {'udim.rescale', 'light.export', 'udim.udims_to_ids'} <= done
    state = {x['id']: x['state'] for n in rm.flow(copy.deepcopy(suite), m.VERSION) for s in n['steps']
             for x in s['buttons']}
    assert state['udim.udims_to_ids'] == 'done' and state['udim.rescale'] == 'done'
    # the package is 1.1.0 now: a row deferred to 1.1 ships with it, so the greyed row is deferred past 1.1
    state = {x['id']: x['state'] for n in rm.flow(_deferred_suite('1.2'), m.VERSION) for s in n['steps']
             for x in s['buttons']}
    assert state['udim.udims_to_ids'] == 'planned' and state['udim.rescale'] == 'done'


@pytest.mark.parametrize('bump,verdict', [(0.05, 'border_nonplanar'), (0.02, 'border_nonplanar'), (0.003, None)])
def test_capsules_on_the_real_openings_core_name_a_nonplanar_border(bump, verdict):
    """K x J integration (polygon 1.0.12 BODY_KCapsBump_001 in the full release run b/c): branch K was tested on its
    stand-in recogniser, which gave a non-planar border a frame. The real openings_core (J) returns it as kind
    `nonplanar` without a frame, and capsule_core said `frame_missing` (RED on main) instead of `border_nonplanar`."""
    kb = _load(ROOT / 'test-polygon/stations/K_build.py', 'agr_tools_k_build_r100')
    oc = _load(PKG / 'openings_core.py', 'agr_tools_openings_core_r100')
    cc = _load(PKG / 'capsule_core.py', 'agr_tools_capsule_core_r100')
    b = kb.badik_mesh(8.0, 6.0, 7.0, 0.25, [{'wall': 0, 's': [1.5, 2.7], 'z': [0.9, 2.4], 'bump': bump}])
    ops = oc.find_openings(b)
    assert len(ops) == 1 and (ops[0]['kind'] == 'nonplanar') == bool(verdict), ops[0]['kind']
    p = cc.plan([{'handle': 1, 'name': 'B', 'openings': ops}])
    if verdict:
        assert not p['rows'] and p['findings'][1][0][0] == verdict and p['ambiguous'], p['findings']
    else:
        assert len(p['rows']) == 1 and not p['ambiguous'], p['findings']
