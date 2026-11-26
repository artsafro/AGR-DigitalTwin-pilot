"""R109 controls: the layer-evidence detector fires on synthetic layers and not on a painted face."""
import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[2] / 'docs/research/trainer_layer_r109/replay.py'


@pytest.fixture(scope='module')
def r109():
    spec = importlib.util.spec_from_file_location('r109_replay', PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def box(o):
    """6 quads of a cube whose 8 vertex indices start at o (x, y, z bits)."""
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return [[o + i for i in q] for q in f]


def layered():
    """Two boxes stacked on x: box A = 0..7, box B shares A's +x face (vertices 1,3,5,7) as its -x face."""
    a = box(0)
    m = {0: 1, 2: 3, 4: 5, 6: 7, 1: 8, 3: 9, 5: 10, 7: 11}
    b = [[m[i] for i in q] for q in box(0)]
    return a + b


def test_shared_interface_fires_nonmanifold(r109):
    ev = r109.evidence(layered(), [0] * 12)
    assert ev['b_nonmanifold'] and ev['any'] and not ev['a_components']


def test_disjoint_layers_fire_components(r109):
    ev = r109.evidence(box(0) + box(8), [0] * 12)
    assert ev['a_components'] and ev['any']


def test_layer_material_partition_fires_closed(r109):
    ev = r109.evidence(layered(), [0] * 6 + [1] * 6)
    assert ev['c_closed_partition'] and ev['any']


def test_painted_face_is_not_layer(r109):
    ev = r109.evidence(box(0), [1, 0, 0, 0, 0, 0])
    assert ev == {'a_components': False, 'b_nonmanifold': False, 'c_closed_partition': False, 'any': False}


def test_duplicated_outer_face_fires_raw_b_only_and_clean_cube_is_clean(r109):
    """r1 P1.2: a single closed cube with one duplicated outer face has no second solid or interface, yet raw (b) fires.
    (b) is therefore marked unvalidated and no verdict claims selector reachability."""
    cube = box(0)
    assert r109.evidence(cube, [0] * 6)['any'] is False
    dup = r109.evidence(cube + [list(cube[0])], [0] * 7)
    assert dup == {'a_components': False, 'b_nonmanifold': True, 'c_closed_partition': False, 'any': True}
    assert r109.CRITERIA['b_nonmanifold'].startswith('unvalidated')
    assert all(c['pass'] for c in r109.run_controls().values())


def census_row(n, m=0):
    return {r'Базовая стена Вентфасад 250 250': {'geometries': n, 'any': m}}


class Clock:
    def __init__(self, end_wall):
        self.calls, self.end_wall = 0, end_wall

    def monotonic(self):  # t0 = 0, every later call returns the end-to-end wall
        self.calls += 1
        return 0.0 if self.calls == 1 else self.end_wall


# input -> expected (hypothesis, status): r1 P1.1 rows a/b/c plus the in-budget control.
CASES = {
    'control_N907_ok_100s': (907, 907, 100.0, False, ('confirmed', 'complete')),
    'a_N906_parity907': (906, 907, 100.0, False, ('inconclusive', 'invalid')),
    'b_N907_601s': (907, 907, 601.0, False, ('inconclusive', 'budget_stop')),
    'c_N907_witness_crash': (907, 907, 100.0, True, ('inconclusive', 'invalid')),
    'parity_906': (907, 906, 100.0, False, ('inconclusive', 'invalid')),
}


@pytest.mark.parametrize('case', sorted(CASES))
def test_main_verdict_table(r109, tmp_path, monkeypatch, case):
    n, rows63b, wall, crash, want = CASES[case]
    monkeypatch.setattr(r109, 'ROOT', tmp_path)
    monkeypatch.setattr(r109, 'check_frozen', lambda commit, work: None)
    monkeypatch.setattr(r109, 'pinned_inputs', lambda: {})
    monkeypatch.setattr(r109, 'read_source', lambda pins: b'')
    monkeypatch.setattr(r109, 'verify_pins', lambda pins, msg='': None)
    monkeypatch.setattr(r109, 'census', lambda data: census_row(n))
    monkeypatch.setattr(r109, 'blender_secondary',
                        lambda work, pins, t: ({'63B': {'family_rows': rows63b}}, 50.0, 'x'))
    monkeypatch.setattr(r109, 'time', Clock(wall))
    if crash:
        def boom(polys, mats):
            raise RuntimeError('witness crash')
        monkeypatch.setattr(r109, 'evidence', boom)
    monkeypatch.setattr('sys.argv', ['replay.py', str(tmp_path / 'out'), 'f' * 40])
    rec = r109.main()
    assert (rec['hypothesis'], rec['status']) == want
    assert rec['selector_reachable'] == 'not_measured'
    assert (tmp_path / 'out' / 'receipt.json').exists()


def test_main_blender_timeout_is_budget_stop(r109, tmp_path, monkeypatch):
    monkeypatch.setattr(r109, 'check_frozen', lambda commit, work: None)
    monkeypatch.setattr(r109, 'pinned_inputs', lambda: {})
    monkeypatch.setattr(r109, 'read_source', lambda pins: b'')
    monkeypatch.setattr(r109, 'verify_pins', lambda pins, msg='': None)
    monkeypatch.setattr(r109, 'census', lambda data: census_row(1210))
    monkeypatch.setattr(r109, 'blender_secondary', lambda work, pins, t: (None, None, None))
    monkeypatch.setattr('sys.argv', ['replay.py', str(tmp_path / 'out'), 'f' * 40])
    rec = r109.main()
    assert (rec['hypothesis'], rec['status']) == ('inconclusive', 'budget_stop')


def test_replay_refuses_unfrozen_commit(r109, tmp_path, monkeypatch):
    monkeypatch.setattr('sys.argv', ['replay.py', str(tmp_path / 'x'), 'deadbeef'])
    with pytest.raises(ValueError, match='frozen variant commit'):
        r109.main()
