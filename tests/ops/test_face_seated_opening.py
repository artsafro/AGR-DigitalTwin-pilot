"""new-case: opaque facade panels supported by real opening frames, not imaginary infill.
Synthetic room: the opposite wall occludes the panel back; no opacity exemption.
"""
import numpy as np
import pytest
import shapely

from dt_ai.ops.contour import extrude_polygon
from dt_ai.ops.face import face_on_wall
from tests.ops.test_invariants import box


def room():
    frame = shapely.box(-1.5, 0, 1.5, 3).difference(shapely.box(-.5, 1, .5, 2))
    return {
        'frame': extrude_polygon(frame, 1, -.15, .3),
        'p': box((-.5, -.1, 1), (.5, -.075, 2)),
        'back': box((-1.5, 2.8, 0), (1.5, 3., 3.)),
        'left': box((-1.5, -.15, 0), (-1.3, 3., 3.)),
        'right': box((1.3, -.15, 0), (1.5, 3., 3.)),
        'floor': box((-1.5, -.15, 0), (1.5, 3., .2)),
        'roof': box((-1.5, -.15, 2.8), (1.5, 3., 3.)),
    }


def test_source_opening_panel_can_seat_in_real_frame_without_solid_behind_centre():
    scene = room()
    result = face_on_wall(scene, 'p', ('frame',), 'front', outward_sign=-1, border_growth_m=.012)
    assert result.applied, result.question
    assert len(result.scene['p'].triangles) == 2
    assert result.report.passed
    for name in scene:
        if name != 'p':
            assert result.scene[name] is scene[name]


@pytest.mark.parametrize('growth', [-.001, .02000001, float('nan'), float('inf'), True])
def test_invalid_growth_refuses_without_mutation(growth):
    scene = room()
    r = face_on_wall(scene, 'p', ('frame',), 'front', outward_sign=-1, border_growth_m=growth)
    assert not r.applied and r.scene is scene
    assert 'border_growth_m' in r.question


@pytest.mark.parametrize('sign', [0, 2, True, -1.0, float('nan'), 'front'])
def test_invalid_orientation_refuses_without_mutation(sign):
    scene = room()
    r = face_on_wall(scene, 'p', ('frame',), 'front', outward_sign=sign, border_growth_m=.012)
    assert not r.applied and r.scene is scene
    assert 'outward_sign' in r.question


def test_growth_does_not_guess_the_orientation_or_waive_embedding():
    scene = room()
    missing = face_on_wall(scene, 'p', ('frame',), 'front', border_growth_m=.012)
    assert not missing.applied and 'outward_sign' in missing.question
    shallow = face_on_wall(scene, 'p', ('frame',), 'front', outward_sign=-1, border_growth_m=.009)
    assert not shallow.applied and shallow.scene is scene
    exact = face_on_wall(scene, 'p', ('frame',), 'front', outward_sign=-1, border_growth_m=.02)
    assert exact.applied, exact.question


def test_border_growth_cannot_silently_merge_source_pieces_or_close_holes():
    from tests.ops.test_primitive import join
    wall=box((-2,-.3,-1),(2,.3,4))
    separated=join(box((-.5,-.1,1),(-.005,-.075,2)),box((.005,-.1,1),(.5,-.075,2)))
    hole=shapely.box(-.5,1,.5,2).difference(shapely.box(-.003,1.497,.003,1.503))
    perforated=extrude_polygon(hole,1,-.1,.025)
    for mesh in (separated,perforated):
        scene={'wall':wall,'p':mesh}
        result=face_on_wall(scene,'p','wall','front',outward_sign=-1,border_growth_m=.012,allow_multi=True)
        assert not result.applied, result.notes
        assert 'source pieces or holes' in result.question
        assert result.scene is scene


def test_wrong_orientation_and_missing_opposite_wall_still_roll_back():
    scene = room()
    wrong = face_on_wall(scene, 'p', ('frame',), 'front', outward_sign=+1, border_growth_m=.012)
    assert not wrong.applied and wrong.scene is scene
    scene.pop('back')
    unsupported = face_on_wall(scene, 'p', ('frame',), 'front', outward_sign=-1, border_growth_m=.012)
    assert not unsupported.applied and unsupported.scene is scene
    assert 'no_visible_back_faces' in unsupported.question


@pytest.mark.parametrize('shift', [0,1,2])
@pytest.mark.parametrize('mirror', [False, True])
def test_generated_room_orientations_remain_opaque_and_preserve_source(shift, mirror):
    from dt_ai.ops.invariants import Mesh, border_edges, distance_to_surface, winding_number
    scene = room()
    if mirror:
        scene = {n:Mesh(m.vertices*np.array([-1,-1,1]),m.triangles) for n,m in scene.items()}
    scene = {n:Mesh(np.roll(m.vertices,shift,axis=1),m.triangles) for n,m in scene.items()}
    original={n:(m.vertices.copy(),m.triangles.copy()) for n,m in scene.items()}
    axis=(1+shift)%3
    r = face_on_wall(scene, 'p', ('frame',), {0:'side',1:'front',2:'top'}[axis],
                     outward_sign=1 if mirror else -1, border_growth_m=.012)
    assert r.applied, r.question
    for n,m in scene.items():
        np.testing.assert_array_equal(m.vertices,original[n][0])
        np.testing.assert_array_equal(m.triangles,original[n][1])
    # Independent dense border witness, beyond the operation's endpoint/midpoint samples.
    edges=border_edges(r.scene['p'])
    points=np.concatenate([a+(b-a)*np.linspace(0,1,201)[:,None] for a,b in edges])
    assert np.min(distance_to_surface(points,scene['frame'])) >= .01-1e-10
    assert (np.abs(winding_number(points,scene['frame']))>.5).all()
