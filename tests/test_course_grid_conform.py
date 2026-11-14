"""new-case: source-proven cut mesh endpoint identity and conforming boundaries."""
import pytest
from tools.materials.course_grid_native import conform_source_mesh


def test_source_endpoint_identity_and_t_junction_are_repaired_without_blind_weld():
    source=[[0.,0.,0.],[1.,0.,0.],[1.,1.,0.],[0.,1.,0.],[2.,0.,0.],[2.,1.,0.]]
    # Left face was split halfway along the shared edge; right still spans it.
    vertices=source+[[1.000004,0.,0.],[1.,.5,0.],[0.,.5,0.]]
    faces=[[0,6,7,8],[8,7,2,3],[1,4,5,2]]
    uv=[[[0,0],[1,0],[1,.5],[0,.5]],[[0,.5],[1,.5],[1,1],[0,1]],[[0,0],[1,0],[1,1],[0,1]]]
    out=conform_source_mesh(vertices,faces,[10,10,11],uv,source,{10:[0,1,2,3],11:[1,4,5,2]})
    assert out['vertices'][:len(source)]==source
    assert out['faces']==[[0,1,7,8],[8,7,2,3],[1,4,5,2,7]]
    assert out['uv'][2][-1]==pytest.approx([0,.5])
    assert out['remap'][6]==1
    assert out['insertions']==[{'face':2,'edge':[2,1],'vertex':7}]


def test_close_disconnected_surface_is_not_welded():
    source=[[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[0.,0.,.00001],[1.,0.,.00001],[0.,1.,.00001]]
    faces=[[0,1,2],[3,4,5]];uv=[[[0,0],[1,0],[0,1]]]*2
    out=conform_source_mesh(source,faces,[10,11],uv,source,{10:faces[0],11:faces[1]})
    assert out['faces']==faces and out['insertions']==[]


@pytest.mark.parametrize('bad',[[],[[float('nan'),0,0]],[[float('inf'),0,0]]])
def test_invalid_conform_input_fails_closed(bad):
    with pytest.raises(ValueError):
        conform_source_mesh(bad,[[0,1,2]],[0],[[[0,0],[1,0],[0,1]]],bad,{0:[0,1,2]})
