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


def test_replay_refuses_unfrozen_commit(r109, tmp_path, monkeypatch):
    monkeypatch.setattr('sys.argv', ['replay.py', str(tmp_path / 'x'), 'deadbeef'])
    with pytest.raises(ValueError, match='frozen variant commit'):
        r109.main()
