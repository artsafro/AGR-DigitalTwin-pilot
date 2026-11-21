"""new-case: explicitly bounded cut-node coalescing, never a global weld."""
import pytest
from tools.materials.course_grid_native import coalesce_cut_nodes


def test_coalescing_reports_collapsed_cells_and_preserves_source_accounting():
    vertices=[[0.,0.,0.],[1.,0.,0.],[1.,1.,0.],[0.,1.,0.],[.5,0.,0.],[.5005,0.,0.]]
    faces=[[0,4,3],[4,5,3],[5,2,3],[5,1,2]]
    result=coalesce_cut_nodes(vertices,faces,[10]*4,original_vertex_count=4,groups=[{'vertices':[4,5],'position':[.50025,0.,0.]}])
    assert result['vertices'][:4]==vertices[:4]
    assert result['faces']==[[0,4,3],[4,2,3],[4,1,2]]
    assert result['lineage']==[10,10,10]
    assert result['dropped']==[{'face':1,'source':10,'reason':'explicit cut-node coalescence; collapsed connectivity cell'}]
    assert result['max_displacement_m']==pytest.approx(.00025)


@pytest.mark.parametrize('groups',[
    [{'vertices':[0,3],'position':[0,0,0]}],
    [{'vertices':[3,4],'position':[.01,0,0]}],
    [{'vertices':[3,4],'position':[float('nan'),0,0]}],
    [{'vertices':[3,4],'position':[0,0,0]},{'vertices':[4,5],'position':[0,0,0]}],
])
def test_original_vertices_excess_motion_nonfinite_and_duplicate_groups_refuse(groups):
    with pytest.raises(ValueError):
        coalesce_cut_nodes([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[.0001,0,0],[.0002,0,0],[.0003,0,0]],[[0,1,2],[3,4,2]],[10,10],original_vertex_count=3,groups=groups)
