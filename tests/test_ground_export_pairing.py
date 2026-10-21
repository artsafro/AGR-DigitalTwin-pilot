"""Export-diagonal repair retains source identity, never changes source geometry."""
from collections import Counter
import numpy as np
import pytest
from dt_ai.geometry.ground_quads import pair_triangles
from dt_ai.geometry.ground_cake import Mesh


def seed():
    v = np.array([(0,0,0), (4,0,0), (4,4,.02), (0,4,0)], float)
    f = np.array([(0,1,2), (0,2,3)])
    return Mesh(v, f, ['TileLight']*2, np.zeros(2,int), v[f,:2]/4, 4.)


def test_export_unsafe_pair_remains_exact_source_triangles():
    m = seed()
    # Opposite diagonal crosses at z=0 rather than z=.01. A proven unsafe
    # pair must remain two triangles even though its dihedral is below D129.
    q = pair_triangles(m, excluded_pairs=[(0,1)])
    assert q.faces == tuple(map(tuple,m.faces))
    assert q.source_faces == ((0,), (1,))
    np.testing.assert_array_equal(q.verts,m.verts)
    np.testing.assert_array_equal(q.uv,m.uv)
    assert len(pair_triangles(m).faces) == 1  # reset/compatibility control


@pytest.mark.parametrize('pairs', [[(0,0)], [(0,2)], [(-1,1)], [(0,1,2)],
    [(False,1)], [(0.,1)], [(np.nan,1)], [(0,1),(1,0)], [None]])
def test_exclusions_reject_malformed_or_duplicated_identity(pairs):
    with pytest.raises(ValueError, match='excluded pair'):
        pair_triangles(seed(), excluded_pairs=pairs)


@pytest.mark.parametrize('shift', [0., 10000., -15000.])
def test_exclusion_permutation_and_source_coverage(shift):
    m = seed();m.verts += shift
    before = [a.copy() for a in (m.verts,m.faces,m.uv)]
    q = pair_triangles(m, excluded_pairs=[(1,0)])
    assert Counter(i for ids in q.source_faces for i in ids) == Counter(range(2))
    for old,new in zip(before,(m.verts,m.faces,m.uv)):
        np.testing.assert_array_equal(old,new)
