"""new-case: hostile ambiguous identifiers may not alias a real native source."""
import pytest
from tools.materials.course_grid_native import plan_boundary_finalization


def test_boolean_source_id_cannot_alias_source_one():
    row=dict(object='synthetic',face=0,source_face=1,material_id=4,
      local_xyz=[[0,0,0],[1,0,0],[0,1,0]],vertices=[0,1,2],uv=[[0,0],[1,0],[0,1]])
    with pytest.raises(ValueError):
        plan_boundary_finalization([row],[dict(object='synthetic',source_face=True,material_id=4)])
