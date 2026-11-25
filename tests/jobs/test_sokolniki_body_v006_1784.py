"""Sokolniki #1784 body v006 [D408], accepted with assembly v009 [D409]: openings for the Revit fill the accepted body had none for.

Pattern: n/a | new-case: tests of jobs/sokolniki-uvk1000/hooks/body_openings.py against the shared lattice core
tools/methods/body/volume_body.py (synthetic inputs, no Revit FBX, no DCC). Synthetic: all geometry below is made up.
"""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / 'jobs/sokolniki-uvk1000'


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


bo = _load(D / 'hooks' / 'body_openings.py', 'body_openings_1784b6')
vb = _load(ROOT / 'tools/methods/body/volume_body.py', 'volume_body_1784b6')

LEVELS = [0.0, 0.6, 3.84, 4.5, 5.1, 8.04, 8.7]


def _vl(rects=()):
    ring = [[0, 0], [20, 0], [20, 30], [0, 30], [0, 0]]
    edges = {}
    for i, k in enumerate(('A1', 'A2', 'A3', 'A4')):
        a, b = ring[i], ring[i + 1]
        edges[k] = {'volume': 'A', 'xy': [a, b], 'facade': 'F9%d' % i, 'visible_from': 0}
    return {'volumes': {'A': {'ring': ring, 'levels': LEVELS}}, 'edges': edges, 'rectangles': list(rects)}


def _plan(glass=(), doors=(), stem=()):
    return {'rows': [{'layer': '04_ВИТРАЖИ', 'family': 'Системная панель ADSK_Cтеклопак', 'representation': 'inset',
                      'objects': list(glass)},
                     {'layer': '04_ВИТРАЖИ', 'family': 'Системная панель ADSK_Cтемалит_25', 'representation': 'texture',
                      'objects': list(stem)},
                     {'layer': '03_ДВЕРИ', 'family': 'AC_ДверьВитражная_Двупольная_А', 'representation': 'inset',
                      'objects': list(doors)}]}


def _panel(name, x0, x1, z0, z1, depth=0.12, t=0.04):
    """A panel on edge A1 (y = 0 face, inside is +y) whose centre stands `depth` behind the face."""
    y0, y1 = depth - t / 2, depth + t / 2
    return {'name': name, 'z': [z0, z1], 'hull': [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]}


def _door_rect(s0, s1):
    return {'name': 'door', 'facade': 'F90', 'edge': 'A1', 'projected_rect': [s0, s1, 0.0, 2.175],
            'state': 'level_conflict'}


def test_blind_facade_panels_become_one_opening_built_by_the_lattice_core():
    objs = [_panel('g1', 2.0, 3.0, 0.65, 3.74), _panel('g2', 3.05, 4.0, 0.65, 3.74)]
    rects, rev, rep = bo.derive(objs, _plan(glass=['g1', 'g2']), _vl(), {})
    assert len(rects) == 1 and rects[0]['state'] == 'contour_cut' and rects[0]['edge'] == 'A1'
    assert rects[0]['projected_rect'] == [2.0, 4.0, 0.6, 3.7]
    assert rev[rects[0]['name']] == 0.12  # reveal = the Revit glass depth
    assert rep['by_status']['glass'] == {'new_opening': 2}
    plans = vb.plans_from_volume_lines(_vl(), {'extra_rectangles': rects, 'reveal_m_by_name': rev})
    assert len(plans['A']['plan']['windows']) == 1


def test_covered_panel_is_not_cut_twice():
    cut = {'name': 'w', 'facade': 'F90', 'edge': 'A1', 'projected_rect': [2.0, 4.0, 0.6, 3.84], 'state': 'cut'}
    rects, _, rep = bo.derive([_panel('g1', 2.5, 3.5, 0.65, 3.74)], _plan(glass=['g1']), _vl([cut]), {})
    assert rects == [] and rep['objects']['g1']['status'] == 'in_body_opening'


def test_transom_over_a_door_is_trimmed_so_the_core_accepts_it():
    """Regression: a curtain field sharing the door's cell with other levels makes the core refuse the whole body."""
    vl = _vl([_door_rect(5.0, 7.0)])
    objs = [_panel('g1', 5.0, 7.0, 2.25, 3.74), _panel('g2', 5.0, 7.0, 5.15, 7.94),
            _panel('g3', 5.0, 7.0, 3.79, 5.1)]
    raw = [{'name': 'raw', 'facade': 'F90', 'edge': 'A1', 'projected_rect': [5.0, 7.0, 2.2, 7.9],
            'state': 'contour_cut'}]
    with pytest.raises(ValueError, match='overlap or touch with different levels'):
        vb.plans_from_volume_lines(vl, {'extra_rectangles': raw})
    rects, rev, rep = bo.derive(objs, _plan(glass=['g1', 'g2', 'g3']), vl, {})
    assert len(rects) == 1 and rects[0]['projected_rect'][2:] == [3.84, 7.9]  # sill lifted to the door cell head
    vb.plans_from_volume_lines(vl, {'extra_rectangles': rects, 'reveal_m_by_name': rev})
    assert rep['objects']['g1']['status'] == 'trimmed_out' and rep['objects']['g2']['status'] == 'new_opening'


def test_corner_pier_top_band_and_sliver():
    objs = [_panel('g1', 0.05, 3.0, 5.15, 8.69), _panel('g2', 10.0, 10.1, 0.65, 3.74)]
    rects, _, rep = bo.derive(objs, _plan(glass=['g1', 'g2']), _vl(), {})
    assert len(rects) == 1
    s0, s1, z0, z1 = rects[0]['projected_rect']
    assert s0 == 0.3 and z1 <= LEVELS[-1] - 0.25  # a corner pier stays, the top band stays closed
    assert rep['not_cut'][0]['reason'].startswith('sliver')


def test_entrance_niche_capped_and_interior_glass_left_out():
    objs = [_panel('d1', 8.0, 10.0, 0.0, 2.2, depth=1.9), _panel('g9', 12.0, 13.0, 0.65, 3.74, depth=9.0),
            _panel('g8', 15.0, 16.0, 5.15, 7.94, depth=1.6)]
    rects, rev, rep = bo.derive(objs, _plan(glass=['g9', 'g8'], doors=['d1']), _vl(), {})
    assert [r['kind'] for r in rects] == ['door'] and rev[rects[0]['name']] == 0.95
    assert rep['objects']['g9']['status'] == 'interior' and rep['objects']['g8']['status'] == 'recessed'


def test_head_above_a_roof_well_deck_is_capped_when_the_reveal_reaches_the_parapet():
    wells = {'roof_wells': {'A': {'deck_z': 8.3, 'parapet_m': 0.15}}}
    objs = [_panel('g1', 2.0, 4.0, 5.15, 8.69, depth=0.5)]
    rects, rev, _ = bo.derive(objs, _plan(glass=['g1']), _vl(), wells)
    assert rects[0]['projected_rect'][3] == 8.3
    vb.plans_from_volume_lines(_vl(), dict(wells, extra_rectangles=rects, reveal_m_by_name=rev))


def test_stemalit_joins_its_curtain_field_but_never_opens_alone():
    objs = [_panel('g1', 2.0, 3.0, 0.65, 3.74), _panel('s1', 3.05, 4.0, 0.65, 3.74), _panel('s2', 9.0, 10.0, 0.65, 3.74)]
    rects, _, rep = bo.derive(objs, _plan(glass=['g1'], stem=['s1', 's2']), _vl(), {})
    assert len(rects) == 1 and rects[0]['projected_rect'][:2] == [2.0, 4.0]
    assert rep['objects']['s2']['status'] == 'stemalit_alone'


def test_committed_config_is_the_v007_config_plus_generated_rects():
    c7 = json.loads((D / 'body_config_v007.json').read_text(encoding='utf-8'))
    c6 = json.loads((D / 'body_config_body_v006.json').read_text(encoding='utf-8'))
    assert c6['extra_rectangles'][:len(c7['extra_rectangles'])] == c7['extra_rectangles']
    new = c6['extra_rectangles'][len(c7['extra_rectangles']):]
    assert new and all(r['name'].startswith('B006-') and r['state'] == 'contour_cut' for r in new)
    assert all(0 < c6['reveal_m_by_name'][r['name']] < 1 for r in new)
    for k in ('roof_wells', 'base_by_volume', 'agreed_edge_clamps'):
        assert c6[k] == c7[k]


def test_body_v006_hook_wired_and_acceptance_recorded():
    """The job runs body_openings.py at body/before and README records Artem's acceptance [D409]."""
    hooks = json.loads((D / 'skeleton.json').read_text(encoding='utf-8'))['hooks']
    assert {'script': 'hooks/body_openings.py', 'stage': 'body', 'point': 'before'} in hooks
    readme = (D / 'README.md').read_text(encoding='utf-8')
    assert '**Accepted** by Artem 2026-11-25' in readme and '[D409]' in readme
    assert '| D409 |' in (ROOT / 'docs/decisions.md').read_text(encoding='utf-8')
