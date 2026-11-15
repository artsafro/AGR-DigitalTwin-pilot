"""new-case: connected 1D cross sections of corner-touching 2D cells."""
from tools.materials.course_grid_native import joint_cross_section


def test_cross_section_merges_touching_intervals_not_shapely_component_count():
    domain=[[-1,0],[1,0],[1,.02],[-1,.02]]
    expected=[[[-.1,0],[.1,0],[.1,.01],[-.1,.01]]]
    # Along x=0 these meet at y=.005, although their 2D interiors do not.
    observed=[[[0,0],[.1,0],[.1,.005],[0,.005]],
              [[-.1,.005],[0,.005],[0,.01],[-.1,.01]]]
    report=joint_cross_section(domain,expected,observed,[0,0],[0,1])
    assert report['observed_intervals_m']==[[0,.01]]
    assert report['passed']
    assert report['false_intervals']==report['missing_intervals']==0


def test_cross_section_retains_real_separated_intervals():
    domain=[[-1,0],[1,0],[1,.02],[-1,.02]]
    expected=[[[-.1,0],[.1,0],[.1,.01],[-.1,.01]]]
    observed=[[[0,0],[.1,0],[.1,.004],[0,.004]],
              [[-.1,.006],[0,.006],[0,.01],[-.1,.01]]]
    report=joint_cross_section(domain,expected,observed,[0,0],[0,1])
    assert len(report['observed_intervals_m'])==2
    assert not report['passed']
