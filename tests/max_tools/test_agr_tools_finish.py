"""new-case: AGR Tools 0.9 (#979) branch B: tex.finish_map core (finish_core.py), plain pytest.

#979 §2: the source (pilot jobs/TEC26-OKS/scripts/finish_map.py, retro job-retro-tec26-oks-pr574.md) is modelled as
measured in the retro: job-wired parameters and a render before the check against the sheet. RED on the model,
GREEN on finish_core. Acceptance: a synthetic OKS with 4 IDs and a legend of 5 finishes.
"""
import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'


def _load(name, alias):
    spec = importlib.util.spec_from_file_location(alias, PKG / name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


fc = _load('finish_core.py', 'agr_tools_finish_core_t')

LEGEND = {
    'finishes': [{'name': 'Plaster_White', 'ral': 'RAL 9010', 'color': '#F1ECE1'},
                 {'name': 'Plaster_Grey', 'ral': 'RAL 7044', 'color': [183, 179, 168]},
                 {'name': 'Brick_Red', 'color': '#8E402A', 'texture': 'C:/tex/brick.png'},
                 {'name': 'Metal_Graphite', 'ral': 'RAL 7024', 'color': '#474A51'},
                 {'name': 'Glass_Dark', 'color': '#20262B'}],
    'ids': [{'id': 1, 'finish': 'Plaster_White'}, {'id': 2, 'finish': 'Plaster_Grey'},
            {'id': 3, 'finish': 'Brick_Red'}, {'id': 4, 'finish': 'Metal_Graphite'}],
    'seams_m': [3.0, 6.0],
}


def oks(ids=(1, 2, 3, 4), height=9.0):
    """A 10 x 8 m block, 4 walls (ID per wall) + roof; base at z = 0."""
    v = [(0, 0, 0), (10, 0, 0), (10, 8, 0), (0, 8, 0), (0, 0, height), (10, 0, height), (10, 8, height), (0, 8, height)]
    faces = [[0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7], [4, 5, 6, 7]]
    return {'vertices': v, 'faces': faces, 'ids': list(ids) + [ids[0]]}


def red_green(prop, source, impl):
    assert not prop(source()), 'source model already satisfies the property: not a regression'
    assert prop(impl())


def source_model(mesh, legend):
    """finish_map.py as in the retro: the job's legend is built in, the picture is rendered, then the legend is
    checked; an ID without a row takes the first finish."""
    rendered = {mid: legend['ids'][0]['finish'] for mid in set(mesh['ids'])}
    for row in legend['ids']:
        rendered[row['id']] = row['finish']
    return {'rendered': True, 'ids': rendered}


@pytest.mark.parametrize('mutate', [
    lambda d: d.pop('finishes'),
    lambda d: d.update(finishes=[]),
    lambda d: d['finishes'].append(dict(d['finishes'][0])),                  # duplicate finish
    lambda d: d['finishes'][0].update(ral='9010X'),                           # bad RAL
    lambda d: d['finishes'][1].update(color='#12345'),                       # bad colour
    lambda d: d['finishes'][4].pop('color'),                                  # neither colour nor texture
    lambda d: d['ids'].append({'id': 1, 'finish': 'Plaster_Grey'}),         # duplicate ID
    lambda d: d['ids'].append({'id': 5, 'finish': 'Wood'}),                  # unknown finish
    lambda d: d['ids'][0].update(id='1'),                                     # ID not an integer
    lambda d: d.update(seams_m=[6.0, 3.0]),                                   # seams not ascending
    lambda d: d.update(sheet='A-101'),                                        # job-wired key
    lambda d: d['finishes'][0].update(name='Штукатурка'),                     # name outside Latin
])
def test_legend_mutations_are_value_errors(mutate):
    doc = copy.deepcopy(LEGEND)
    mutate(doc)
    with pytest.raises(ValueError):
        fc.validate_legend(doc)


def test_id_without_legend_row_fails_before_anything_is_built():
    legend = fc.validate_legend(LEGEND)
    mesh = oks(ids=(1, 2, 3, 7))
    red_green(lambda r: not r['rendered'] and 7 not in r['ids'],
              lambda: source_model(mesh, LEGEND),
              lambda: {'rendered': False, 'ids': {row['id']: row['finish'] for row in
                                                  fc.plan_object('SM_A_001_Main', mesh, legend)['ids']}})
    p = fc.plan([(1, 'SM_A_001_Main', mesh)], legend)['plans'][0]
    assert sorted({c for c, _, _ in p['findings']}) == ['finish_id_absent', 'finish_id_unmapped']


def test_correct_legend_4_ids_5_finishes_passes_and_lists_the_unused_finish():
    legend = fc.validate_legend(LEGEND)
    res = fc.plan([(1, 'SM_A_001_Main', oks())], legend)
    p = res['plans'][0]
    assert p['findings'] == []
    assert [(r['id'], r['finish']) for r in p['ids']] == [(1, 'Plaster_White'), (2, 'Plaster_Grey'),
                                                           (3, 'Brick_Red'), (4, 'Metal_Graphite')]
    assert res['unused_finishes'] == ['Glass_Dark']
    assert p['cuts_z_m'] == [3.0, 6.0]
    assert p['seams_per_facade'] == {'E': 2, 'N': 2, 'S': 2, 'W': 2}


def test_seam_outside_the_object_refuses_the_cut():
    legend = fc.validate_legend(dict(LEGEND, seams_m=[3.0, 12.0]))
    p = fc.plan_object('SM_A_001_Main', oks(), legend)
    assert [c for c, _, _ in p['findings']] == ['seam_outside'] and p['cuts_z_m'] == [3.0]


def test_centimetre_scene_seams_in_metres():
    legend = fc.validate_legend(LEGEND)
    mesh = oks()
    mesh = dict(mesh, vertices=[tuple(c * 100 for c in p) for p in mesh['vertices']])
    p = fc.plan_object('SM_A_001_Main', mesh, legend, unit=0.01)
    assert p['cuts_z_m'] == [3.0, 6.0] and p['findings'] == []


def test_seam_readback_within_1_mm():
    rows = fc.seam_readback([0.0, 2.9995, 6.002, 9.0], [3.0, 6.0])
    assert [r['ok'] for r in rows] == [True, False]


def test_csv_legend():
    text = 'id,finish,ral,color,texture\n1,Plaster_White,RAL 9010,#F1ECE1,\n2,Plaster_Grey,,#B7B3A8,\n,Glass_Dark,,#20262B,\n'
    legend = fc.parse_legend(text, 'csv')
    assert legend['ids'] == {1: 'Plaster_White', 2: 'Plaster_Grey'} and 'Glass_Dark' in legend['finishes']
    with pytest.raises(ValueError):
        fc.parse_legend('id,finish,colour\n1,A,#000000\n', 'csv')
    assert fc.parse_legend(json.dumps(LEGEND), 'json')['seams_m'] == [3.0, 6.0]
    with pytest.raises(ValueError):
        fc.parse_legend('{"finishes": [], "finishes": []}', 'json')


def test_facades():
    assert fc.facade_of((0, -1, 0)) == 'S' and fc.facade_of((1, 0, 0)) == 'E' and fc.facade_of((0, 0, 1)) is None
