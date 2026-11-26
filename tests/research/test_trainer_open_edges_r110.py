from runpy import run_path
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[2] / 'docs/research/trainer_open_edges_r110/replay.py'
measure = run_path(str(MODULE))['measure']

VERTS = ((0., 0., 0.), (1., 0., 0.), (0., 1., 0.), (0., 0., 1.))
FACES = ((0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3))
SPLIT = ((4, 6, 5), *FACES[1:])


@pytest.mark.parametrize(('vertices', 'faces', 'expected'), [
    (VERTS, FACES, (0, 0, 0)),
    (VERTS + VERTS[:3], SPLIT, (6, 0, 3)),
    (VERTS + VERTS[:3], SPLIT[:-1], (7, 3, 3)),
    (VERTS + ((1/1024, 0., 0.),) + VERTS[1:3], SPLIT, (6, 4, 2)),
])
def test_exact_reindex_only_reconciles_coincident_seams(vertices, faces, expected):
    row = measure(vertices, faces)
    assert (row['raw_open'], row['exact_open'], row['changed_corners']) == expected
    assert row['collapsed'] == row['extra_nonmanifold'] == 0


def test_degenerate_edge_is_counted_not_erased():
    row = measure(VERTS + VERTS[:1], ((0, 4, 1),))
    assert row['collapsed'] == 1


def test_invalid_negative_index_refused():
    with pytest.raises(ValueError):
        measure(VERTS, ((-1, 0, 1),))
