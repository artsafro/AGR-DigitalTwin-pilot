"""Bounded alternating paths improve pairing, never compatibility constraints."""
from itertools import combinations
import numpy as np
import pytest
from dt_ai.geometry import ground_quads as gq
from dt_ai.geometry.ground_cake import Mesh


def test_short_and_seven_edge_augmenting_paths_keep_all_vertices_unique():
    for n in (4,8):
        adj=[set() for _ in range(n)]
        for i in range(n-1):adj[i].add(i+1);adj[i+1].add(i)
        old={}
        for i in range(1,n-1,2):old[i]=i+1;old[i+1]=i
        before=dict(old);result=gq._augment_matching(adj,old)
        assert len(result)==n and old==before
        assert all(result.get(b)==a and b in adj[a] for a,b in result.items())


def test_exhaustive_four_node_graphs_match_independent_cardinality_oracle():
    edges=list(combinations(range(4),2))
    for mask in range(1<<len(edges)):
        available=[e for i,e in enumerate(edges) if mask&(1<<i)]
        matchings=[]
        for selection in range(1<<len(available)):
            chosen=[e for i,e in enumerate(available) if selection&(1<<i)]
            flat=[v for e in chosen for v in e]
            if len(set(flat))==len(flat):matchings.append(chosen)
        best=max(map(len,matchings))
        adj=[set() for _ in range(4)]
        for a,b in available:adj[a].add(b);adj[b].add(a)
        for chosen in matchings:
            old={a:b for e in chosen for a,b in (e,e[::-1])}
            result=gq._augment_matching(adj,old)
            assert len(result)==2*best
            assert all(result.get(b)==a and b in adj[a] for a,b in result.items())


def test_improved_pairing_still_respects_excluded_source_pairs():
    v=np.array([(0,0,0),(1,0,0),(1,1,0),(0,1,0)],float);f=np.array([(0,1,2),(0,2,3)])
    m=Mesh(v,f,['TileLight']*2,np.zeros(2,int),v[f,:2],4.)
    q=gq.pair_triangles(m,excluded_pairs=[(0,1)],improve_matching=True)
    assert q.source_faces==((0,),(1,))
    with pytest.raises(ValueError,match='improve_matching'):gq.pair_triangles(m,improve_matching='yes')
