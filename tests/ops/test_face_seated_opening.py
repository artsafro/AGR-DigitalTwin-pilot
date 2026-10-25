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
