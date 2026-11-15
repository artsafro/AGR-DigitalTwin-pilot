"""new-case: retain both lobes of an exactly pinched native boundary."""
from tools.materials.course_grid_native import split_native_loop


def test_exact_pinched_boundary_keeps_both_lobes_and_all_edges():
    ids=[0,1,2,3,4,2,5,6]
    result=split_native_loop(ids)
    assert len(result['loops'])==2 and not result['collapsed']
    expected={(ids[i],ids[(i+1)%len(ids)]) for i in range(len(ids))}
    actual={(ids[loop[i]],ids[loop[(i+1)%len(loop)]]) for loop in result['loops'] for i in range(len(loop))}
    assert actual==expected
    assert all(len({ids[i] for i in loop})==len(loop) for loop in result['loops'])


def test_exact_zero_length_edge_reported_not_silently_removed():
    result=split_native_loop([0,1,1,2,3])
    assert len(result['loops'])==1 and result['collapsed']
