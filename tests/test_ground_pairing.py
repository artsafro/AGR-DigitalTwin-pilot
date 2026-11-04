"""Source-preserving option-(a) controls for #371 (synthetic meshes)."""
from collections import Counter
import numpy as np
import pytest
from dt_ai.geometry.ground_cake import Mesh
from dt_ai.geometry import ground_quads as gq


def seed(z=0.):
    v = np.array([(0,0,0), (4,0,0), (4,4,z), (0,4,0)], float)
    f = np.array([(0,1,2), (0,2,3)])
    return Mesh(v, f, ['TileLight']*2, np.zeros(2,int), v[f,:2]/4, 4.)


def test_pair_keeps_original_diagonal_and_every_source_face():
    m = seed(.02)  # < 1 degree but not strictly planar: no Steiner remesh
    q = gq.pair_triangles(m)
    assert len(q.faces) == 1
    assert q.source_faces == ((0,1),)
    ring = q.faces[0]
    assert set((ring[0],ring[2])) == {0,2}
    assert Counter(tuple(sorted(t)) for t in [(ring[0],ring[1],ring[2]),(ring[0],ring[2],ring[3])]) == Counter(tuple(sorted(t)) for t in m.faces)
    np.testing.assert_array_equal(q.verts,m.verts)
    np.testing.assert_allclose(q.uv[0],m.verts[list(ring),:2]/4)


@pytest.mark.parametrize('change',['slot','level','uv','steep'])
def test_discontinuity_is_not_paired(change):
    m = seed()
    if change == 'slot': m.slot[1] = 'LawnRolled'
    elif change == 'level': m.level[1] = 1
    elif change == 'uv': m.uv[1,0,0] += .1
    else: m.verts[2,2] = 1
    q = gq.pair_triangles(m)
    assert q.faces == tuple(map(tuple,m.faces))
    assert q.source_faces == ((0,), (1,))


@pytest.mark.parametrize('change',['empty','nan','duplicate','slot','uv','level','cell'])
def test_pairing_rejects_invalid_seed(change):
    m=seed()
    if change=='empty': m.faces=np.empty((0,3),int)
    elif change=='nan': m.verts[0,0]=np.nan
    elif change=='duplicate': m.faces[1]=m.faces[0]
    elif change=='slot': m.slot[1]=''
    elif change=='uv': m.uv[0,0,0]=np.inf
    elif change=='level': m.level=np.array([0,np.inf])
    else: m.cell=np.nan
    with pytest.raises(ValueError): gq.pair_triangles(m)


@pytest.mark.parametrize('seed_id',range(12))
def test_generated_grids_have_exact_triangle_inventory_and_immutable_inputs(seed_id):
    rng=np.random.default_rng(seed_id)
    nx,ny=rng.integers(2,8,size=2)
    verts=np.array([(x,y,.01*x+.005*y) for y in range(ny) for x in range(nx)])
    faces=[]
    for y in range(ny-1):
        for x in range(nx-1):
            a=y*nx+x; b=a+1; c=b+nx; d=a+nx
            faces.extend([(a,b,c),(a,c,d)])
    faces=np.array(faces)
    m=Mesh(verts,faces,['TileLight']*len(faces),np.zeros(len(faces),int),verts[faces,:2]/4,4.)
    before=tuple(a.copy() for a in (m.verts,m.faces,m.uv,m.level))
    q=gq.pair_triangles(m)
    assert all(len(f)==4 for f in q.faces)
    assert sorted(i for ids in q.source_faces for i in ids)==list(range(len(faces)))
    triangles=[(f[0],f[i],f[i+1]) for f in q.faces for i in range(1,len(f)-1)]
    assert Counter(tuple(sorted(t)) for t in triangles)==Counter(tuple(sorted(t)) for t in faces)
    for old,now in zip(before,(m.verts,m.faces,m.uv,m.level)): np.testing.assert_array_equal(old,now)
