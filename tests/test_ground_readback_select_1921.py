"""#1921: Ground FBX readback selects one Ground surface independently of UCX/import order; placement and strict UDIM.

Pure-Python tests of tools/blender/ground_readback_match.py (no bpy). The native Blender cases are in
tests/test_ground_readback_quad_1837.py.
"""
import importlib.util
import itertools
import json
import random
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    'ground_readback_match_1921', Path(__file__).resolve().parents[1] / 'tools/blender/ground_readback_match.py')
match = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(match)

ADDR = 'Synthetic_Ground'  # export_meta address = <Address>_Ground; the object is SM_<that>
GROUND = ('SM_Synthetic_Ground', 'MESH')


def _ucx(n):
    return [(f'UCX_SM_Synthetic_Ground_{i:03d}', 'MESH') for i in range(1, n + 1)]


@pytest.mark.parametrize('address', [ADDR, None])
@pytest.mark.parametrize('n_ucx', [0, 1, 3])
def test_ground_selected_with_ucx_before_and_after(address, n_ucx):
    for objects in itertools.permutations([GROUND, *_ucx(n_ucx)]):
        sel = match.select_ground(list(objects), address)
        assert (sel['status'], sel['selected']) == ('selected', 'SM_Synthetic_Ground'), objects
        assert sel['unexpected_surface_meshes'] == []
        assert sorted(e['name'] for e in sel['excluded']) == sorted(n for n, _ in _ucx(n_ucx))
        assert {e['reason'] for e in sel['excluded']} <= {'UCX collision mesh'}


@pytest.mark.parametrize('address', [ADDR, None])
def test_missing_ground_is_not_a_measurement(address):
    for objects in ([], _ucx(2), [('SM_Synthetic_GroundGlass', 'MESH'), ('Camera', 'CAMERA')],
                    [('SM_Synthetic_Ground', 'EMPTY')]):
        sel = match.select_ground(objects, address)
        assert sel['status'] == 'missing' and sel['selected'] is None, objects
        assert len(sel['excluded']) == len(objects)  # every input object is accounted for with a reason


def test_ambiguous_ground_is_not_a_measurement():
    two = [('SM_A_Ground', 'MESH'), ('SM_B_Ground', 'MESH'), *_ucx(1)]
    for objects in itertools.permutations(two):
        sel = match.select_ground(list(objects), None)
        assert sel['status'] == 'ambiguous' and sel['selected'] is None
        assert sorted(sel['candidates']) == ['SM_A_Ground', 'SM_B_Ground']
    # with a recorded address, only the exact SM_<Address>_Ground counts; the other is an unexpected mesh
    sel = match.select_ground([('SM_Other_Ground', 'MESH'), GROUND], ADDR)
    assert (sel['status'], sel['selected']) == ('selected', 'SM_Synthetic_Ground')
    assert sel['unexpected_surface_meshes'] == ['SM_Other_Ground']


def test_excluded_objects_keep_reasons():
    objects = [('UCX_SM_Synthetic_Ground_001', 'MESH'), ('ucx_lower', 'MESH'), ('SM_Synthetic_GroundGlass', 'MESH'),
               ('Cube', 'MESH'), ('SM_Synthetic_Ground.001', 'MESH'), ('Light', 'LIGHT'), GROUND]
    sel = match.select_ground(objects, ADDR)
    assert sel['selected'] == 'SM_Synthetic_Ground'
    why = {e['name']: e['reason'] for e in sel['excluded']}
    assert why == {'UCX_SM_Synthetic_Ground_001': 'UCX collision mesh', 'ucx_lower': 'UCX collision mesh',
                   'SM_Synthetic_GroundGlass': 'GroundGlass, not the Ground surface',
                   'Cube': 'name is not SM_Synthetic_Ground', 'SM_Synthetic_Ground.001': 'name is not SM_Synthetic_Ground',
                   'Light': 'not a mesh (LIGHT)'}
    assert sel['unexpected_surface_meshes'] == ['Cube', 'SM_Synthetic_Ground.001']


def test_selection_independent_of_order_random_probe():
    rng = random.Random(1921)
    pool = [*_ucx(4), ('SM_Synthetic_GroundGlass', 'MESH'), ('Cam', 'CAMERA'), ('Cube', 'MESH')]
    for _ in range(300):
        objects = rng.sample(pool, rng.randint(0, len(pool)))
        with_ground = objects + [GROUND]
        rng.shuffle(with_ground)
        a, b = match.select_ground(with_ground, ADDR), match.select_ground(list(reversed(with_ground)), ADDR)
        assert a['selected'] == b['selected'] == 'SM_Synthetic_Ground'
        assert sorted(map(str, a['excluded'])) == sorted(map(str, b['excluded']))
        assert match.select_ground(objects, ADDR)['status'] == 'missing'


def test_placement_missing_is_not_recorded_zero(tmp_path):
    p = tmp_path / 'g.fbx.placement.json'
    missing = match.load_placement(str(p))
    assert missing['status'] == 'missing' and missing['offset'] is None
    p.write_text(json.dumps({'origin_msk77_xyz': [0.0, 0.0, 0.0]}))
    assert match.load_placement(str(p)) == {'status': 'recorded', 'path': str(p), 'offset': [0.0, 0.0, 0.0],
                                            'reason': None}
    p.write_text(json.dumps({'origin_msk77_xyz': [1002.5, 2001.25, 0]}))
    assert match.load_placement(str(p))['offset'] == [1002.5, 2001.25, 0.0]


@pytest.mark.parametrize('body', ['', '{', '[]', '{}', '{"origin_msk77_xyz": [1, 2]}',
                                  '{"origin_msk77_xyz": [1, 2, NaN]}', '{"origin_msk77_xyz": [1, 2, Infinity]}',
                                  '{"origin_msk77_xyz": [1, "2", 3]}', '{"origin_msk77_xyz": [1, true, 3]}',
                                  '{"origin_msk77_xyz": null}'])
def test_placement_invalid_fails_closed(tmp_path, body):
    p = tmp_path / 'g.fbx.placement.json'
    p.write_text(body)
    got = match.load_placement(str(p))
    assert got['status'] == 'invalid' and got['offset'] is None and got['reason']


def _report(selection='selected', status=None, uv=True):
    rep = {'ground_selection': {'status': selection}}
    if uv:
        rep['uv_tiles'] = {} if status is None else {'udim_assignment': {'status': status, 'reason': 'r'}}
    return rep


@pytest.mark.parametrize('rep,result,code', [
    (_report(status='pass'), 'measured_pass', 0),
    (_report(status='fail'), 'measured_fail', 1),
    (_report(status='not_measured'), 'insufficient_evidence', 2),
    (_report(status=None), 'insufficient_evidence', 2),           # NPM: no UDIM assignment
    (_report(uv=False), 'insufficient_evidence', 2),
    (_report(selection='missing', status='not_measured'), 'insufficient_evidence', 2),
    (_report(selection='ambiguous', status='pass'), 'insufficient_evidence', 2),
    (_report(status='PASS'), 'insufficient_evidence', 2),          # alternate form is not a pass
    (_report(status=''), 'insufficient_evidence', 2),
    (_report(status=True), 'insufficient_evidence', 2),
    ({}, 'insufficient_evidence', 2),
])
def test_strict_udim_result(rep, result, code):
    got = match.strict_udim_result(rep)
    assert (got['result'], got['exit']) == (result, code)
    assert got['reason']


def test_strict_udim_ignores_informational_fields():
    base = _report(status='pass')
    for noise in ({'density': {'faces_below': 99, 'faces_above': 99}}, {'material_mismatch_by_order': 5},
                  {'open_edges': 1000, 'placement': {'status': 'missing'}}):
        assert match.strict_udim_result({**base, **noise})['exit'] == 0


def test_naming_mirror_matches_the_twinqa_owner():
    from twinqa.naming import address_from_fbx, is_ucx
    names = ['UCX_SM_A_Ground_001', 'ucx_x', 'Ucx_y', 'UCXSM_A', 'SM_A_Ground', 'SM_A_B_Ground', 'SM_A_GroundGlass',
             'SM__Ground', 'SM_A_Ground.001', 'SM_Ä_Ground', 'sm_A_Ground', 'SM_A_Ground_', 'Cube', '', 'SM_Ground']
    for name in names:
        assert match.is_ucx(name) == is_ucx(name), name
        assert match.is_generic_ground(name) == (address_from_fbx('vpm', 'ground', name) is not None), name
