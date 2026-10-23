"""Pattern: attached-decor | new-case: source-bound decor placement and rigid repair."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from dt_ai.ops.inv_quads import PolyMesh

FIXTURE = json.loads((Path(__file__).parents[1] / 'fixtures/attached_decor/contacts.json').read_text())


def api():
    assert importlib.util.find_spec('dt_ai.ops.attached_decor'), 'attached-decor operation is missing'
    from dt_ai.ops import attached_decor
    return attached_decor


def patch(z=0.0):
    return PolyMesh(np.array([[0, 0, z], [1, 0, z], [1, 1, z], [0, 1, z]], float), ((0, 1, 2, 3),))


def scene_case(name):
    return {k: PolyMesh(np.array(p['vertices']), (tuple(range(len(p['vertices']))),))
            for k, p in FIXTURE['cases'][name]['parts'].items()}


def test_railing_on_coping():
    op = api()
    # Synthetic arithmetic witness: independent 0.7300 / 0.73 levels coincide.
    assert op.clearance_pairs({'coping': patch(.73), 'glass': patch(.7300)})
    assert not op.clearance_pairs({'coping': patch(.73), 'glass': patch(.86)})
    # Actual tilted face, not its centroid: the near end fails in both versions.
    for tag in ('v013', 'v027', 'v028'):
        assert op.clearance_pairs(scene_case('railing_' + tag))


@pytest.mark.parametrize('unit', [2, 3, 5, 6])
def test_ac_glass_clearance(unit):
    op = api()
    scene = scene_case('ac_unit_' + str(unit))
    assert op.clearance_pairs(scene)
    # Positive control derived from the host face, not a second simplified envelope.
    basket = scene['basket']
    p = basket.vertices
    normal = np.cross(p[1] - p[0], p[2] - p[0])
    normal /= np.linalg.norm(normal)
    glass = np.concatenate([p - .025 * normal, p - .033 * normal])
    nf = len(p)
    corrected = PolyMesh(glass, (tuple(range(nf)), tuple(range(nf, 2 * nf))))
    assert not op.clearance_pairs({'basket': basket, 'glass': corrected})


@pytest.mark.parametrize('stub', [224, 242])
def test_ac_glass_clearance_v028_stubs(stub):
    assert api().clearance_pairs(scene_case(f'stub_v028_{stub}'))


def test_stub_move_rigid():
    op = api()
    assert hasattr(op, 'move_rigid'), 'rigid repair is missing'
    scene = scene_case('stub_v027_224')
    scene['unrelated'] = patch(100)
    before = {k: m.vertices.copy() for k, m in scene.items()}
    vector = np.array([.003, 0, 0])
    result = op.move_rigid(scene, ['glass'], vector, fixed=['unrelated'])
    assert result.moved == ('coping', 'glass')
    assert not result.contacts
    for name in ('glass', 'coping'):
        np.testing.assert_allclose(result.scene[name].vertices, before[name] + vector, atol=1e-14)
        np.testing.assert_array_equal(scene[name].vertices, before[name])
    np.testing.assert_array_equal(result.scene['unrelated'].vertices, before['unrelated'])
    # Rigid repair is not a construction-clearance waiver: the old 7 mm stays reported.
    assert result.clearance


@pytest.mark.parametrize('dz,contact', [(0, True), (.003, True), (.005, True), (.006, False), (.032, False)])
def test_louvre_rail_threshold_from_unit_fixture(dz, contact):
    # rootcause/louvre_top/unit_cases.py rail_soffit: synthetic, copied verbatim.
    from dt_ai.ops import inv_xview as ix
    v = np.array([(0, 0, 0), (0, 2, 0), (2, 2, 0), (2, 0, 0),
                  (-3.37 + .012, .5, dz), (-3.37 + .012, .565, dz),
                  (.012, .565, dz), (.012, .5, dz)])
    r = ix.mesh_report(v, [(0, 1, 2, 3), (4, 5, 6, 7)])
    assert bool(r['xview_faces']) == contact


@pytest.mark.parametrize('case', [k for k in FIXTURE['cases'] if k.startswith('louvre_')])
def test_real_louvre_fix(case):
    op = api()
    scene = scene_case(case)
    rail = next(k for k in scene if 'louvre' in k.lower())
    fixed = [k for k in scene if k != rail]
    assert op.clearance_pairs(scene)
    result = op.move_rigid(scene, [rail], [0, 0, .032], fixed=fixed)
    assert not result.contacts and not result.clearance
    np.testing.assert_allclose(result.scene[rail].vertices, scene[rail].vertices + [0, 0, .032])


@pytest.mark.parametrize('seed,fixed', [(['a', 'a'], []), (['a'], ['b', 'b']), ('a', ['b']), (['a'], 'b')])
def test_duplicate_or_string_selection_is_error(seed, fixed):
    with pytest.raises(ValueError, match='selection'):
        api().move_rigid({'a': patch(), 'b': patch(.1)}, seed, [0, 0, .02], fixed=fixed)


@pytest.mark.parametrize('gap', [0, .003, .005, .006, .009, .010, .010001, .13])
def test_generated_clearance_boundary(gap):
    assert bool(api().clearance_pairs({'a': patch(), 'b': patch(gap)})) == (gap <= .010)


@pytest.mark.parametrize('count', range(2, 12))
def test_generated_neighbour_closure_and_rigidity(count):
    scene = {str(i): patch(i * .008) for i in range(count)}
    result = api().move_rigid(scene, ['0'], [.1, -.2, .03], fixed=[])
    assert set(result.moved) == set(scene)
    assert set(result.scene) == set(scene)  # no dropped elements
    for name, mesh in scene.items():
        np.testing.assert_allclose(result.scene[name].vertices - mesh.vertices,
                                   np.tile([.1, -.2, .03], (4, 1)), atol=1e-14)
        assert result.scene[name].faces == mesh.faces
        assert not np.shares_memory(result.scene[name].vertices, mesh.vertices)


@pytest.mark.parametrize('vector', [[0, 0, 0], [1, 2], [np.nan, 0, 0], [0, np.inf, 0]])
def test_bad_translation_is_error(vector):
    with pytest.raises(ValueError, match='vector'):
        api().move_rigid({'a': patch()}, ['a'], vector, fixed=[])


@pytest.mark.parametrize('scene', [{}, {'a': PolyMesh(np.empty((0, 3)), ())}, {'a': object()},
                                    {'a': PolyMesh(np.zeros((3, 3)), ((0, 1, 2),))}])
def test_empty_partial_unsupported_scene_is_error(scene):
    with pytest.raises(ValueError):
        api().clearance_pairs(scene)


@pytest.mark.parametrize('bad', [np.nan, np.inf])
def test_changed_input_nonfinite_is_error(bad):
    mesh = patch()
    mesh.vertices[0, 0] = bad
    with pytest.raises(ValueError, match='finite'):
        api().move_rigid({'a': mesh}, ['a'], [0, 0, .1], fixed=[])


@pytest.mark.parametrize('seeds,fixed', [([], []), (['missing'], []), (['a'], ['missing']), (['a'], ['a'])])
def test_unknown_empty_conflicting_selection_is_error(seeds, fixed):
    with pytest.raises(ValueError):
        api().move_rigid({'a': patch()}, seeds, [0, 0, .1], fixed=fixed)


def test_postcondition_refuses_new_obstacle_and_retained_contacts():
    op = api()
    scene = {'a': patch(), 'host': patch(.1)}
    before = scene['a'].vertices.copy()
    with pytest.raises(ValueError, match='contacts'):
        op.move_rigid(scene, ['a'], [0, 0, .1], fixed=['host'])
    np.testing.assert_array_equal(scene['a'].vertices, before)
    # No stale success receipt/cache after an input is edited.
    assert not op.move_rigid(scene, ['a'], [0, 0, -.1], fixed=['host']).contacts
    scene['host'].vertices[:, 2] = -.1
    with pytest.raises(ValueError, match='contacts'):
        op.move_rigid(scene, ['a'], [0, 0, -.1], fixed=['host'])
    # Moving a whole v028 defective pair cannot fix its internal 4 mm gap.
    with pytest.raises(ValueError, match='contacts'):
        op.move_rigid(scene_case('stub_v028_224'), ['glass'], [.003, 0, 0], fixed=[])


def test_perpendicular_embed_is_not_parallel_contact():
    vertical = PolyMesh(np.array([[0, 0, 0], [0, 1, 0], [0, 1, 1], [0, 0, 1]], float), ((0, 1, 2, 3),))
    assert not api().clearance_pairs({'a': patch(), 'b': vertical})


def test_generated_tilted_ends_cannot_hide_behind_centroid():
    for length in (.5, 1, 3, 10):
        # Near-parallel face: mean gap 12 mm, endpoint gap 4 mm.
        a = patch()
        a.vertices[:, 0] *= length
        b = PolyMesh(a.vertices + np.array([[0, 0, .004], [0, 0, .020],
                                            [0, 0, .020], [0, 0, .004]]), a.faces)
        if length >= 3:  # inside xView's 0.810 degree parallel limit
            assert api().clearance_pairs({'a': a, 'b': b})
        # A parallel >=20 mm translation is an independent clean control.
        c = PolyMesh(a.vertices + [0, 0, .020], a.faces)
        assert not api().clearance_pairs({'a': a, 'c': c})


def test_snapshot_survives_caller_mutation_during_check(monkeypatch):
    from dt_ai.ops import inv_xview as ix
    scene = {'a': patch(), 'b': patch(.1)}
    original = ix.face_pairs
    def checking(mesh, tol):
        scene['a'].vertices[:] = 900
        return original(mesh, tol)
    monkeypatch.setattr(ix, 'face_pairs', checking)
    result = api().move_rigid(scene, ['a'], [0, 0, .02], fixed=['b'])
    np.testing.assert_array_equal(result.scene['a'].vertices, patch(.02).vertices)


def test_fresh_process_api():
    import subprocess
    import sys
    code = ('import numpy as n; from dt_ai.ops.attached_decor import move_rigid; '
            'from dt_ai.ops.inv_quads import PolyMesh; '
            'm=PolyMesh(n.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0.]]),((0,1,2,3),)); '
            'r=move_rigid({"a":m},["a"],[0,0,.032],fixed=[]); '
            'assert not r.contacts and not r.clearance; print("fresh-process OK")')
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == 'fresh-process OK'

