"""new-case: explicit fixed-node finalization plans, never implicit welds."""
import copy
import pytest
from tools.materials import course_grid_native as native


def row():
    return dict(object='synthetic',face=2,source_face=7,material_id=4,
      local_xyz=[[0,0,0],[1,0,0],[1,1,0],[0,1,0]],
      vertices=[0,1,2,3],uv=[[0,0],[1,0],[1,1],[0,1]])


def test_explicit_boundary_plan_preserves_corner_associations_and_input():
    r=row();before=copy.deepcopy(r)
    result=native.plan_boundary_finalization([r],[dict(object='synthetic',source_face=7,material_id=4)])
    assert len(result)==1 and len(result[0]['triangles'])==2
    assert result[0]['local_xyz']==r['local_xyz']
    assert result[0]['uv']==r['uv']
    assert r==before


@pytest.mark.parametrize('targets', [[],[dict(object='synthetic',source_face=8,material_id=4)],
 [dict(object='synthetic',source_face=7,material_id=1)],
 [dict(object='synthetic',source_face=7,material_id=4)]*2,
 [dict(object='synthetic',source_face=True,material_id=4)]])
def test_boundary_plan_refuses_missing_duplicate_or_stale_targets(targets):
    with pytest.raises(ValueError):native.plan_boundary_finalization([row()],targets)
