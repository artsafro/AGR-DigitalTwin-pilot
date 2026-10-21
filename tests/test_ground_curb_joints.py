"""new-case: flat mixed-section curb intersections retain a measured 6 mm joint."""
import numpy as np
from shapely.geometry import box, mapping, LineString
from dt_ai.geometry import ground_cake as gc, ground_details as gd


def test_mixed_curbs_have_no_coplanar_bottom_overlap():
    boundary = box(0, 0, 8, 8)
    sampler = gc.ReliefSampler(gc.build_tin([(-1,-1,0),(9,-1,0),(-1,9,0),(9,9,0)]))
    elements = [dict(ref='drive', role='curb_drive', geometry=mapping(LineString([(1,4),(7,4)]))),
                dict(ref='garden', role='curb_garden', geometry=mapping(LineString([(4,1),(4,7)])))]
    mesh, report, _ = gd.build_details(elements, boundary, sampler, separate_curbs=True)
    assert gc.measure_codirectional(mesh)['pairs_below'] == 0
    assert {r['ref'] for r in report if r['status']=='modeled'} == {'drive','garden'}
    trimmed = [r for r in report if r.get('joint_trim_m2',0)>0]
    assert len(trimmed) == 1 and trimmed[0]['ref'] == 'garden'
    assert trimmed[0]['joint_gap_m'] == .006
    assert set(np.round(mesh.verts[:,2],6)) == {.018,.068,.168}
