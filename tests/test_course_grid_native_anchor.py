"""new-case: protected cyclic anchors without adding any diagonal."""
import numpy as np
from dt_ai.ops.inv_quads import PolyMesh
from dt_ai.ops.inv_xview import face_pairs,tolerance_for
from tools.materials import course_grid_native as native
from test_course_grid_protected_tessellation import POINTS,OTHER


def test_native_cyclic_anchor_preserves_exact_protected_polygon():
    indices=native.canonical_native_boundary(POINTS)
    assert len(indices)==6
    assert sorted(indices)==list(range(6))
    assert all(indices[(k+1)%6]==(indices[k]+1)%6 for k in range(6))
    mesh=PolyMesh(np.array(POINTS+[OTHER]),(tuple(indices),(6,2,1)))
    assert face_pairs(mesh,tolerance_for('VPM'))==[]
    # No source/protected vertex, UV association, boundary edge or face is added.
    assert {(indices[i],indices[(i+1)%6]) for i in range(6)}=={(i,(i+1)%6) for i in range(6)}
