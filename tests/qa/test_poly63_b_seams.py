"""Synthetic belt-joint witness with the measured crossing geometry simplified to XY."""
from collections import Counter
from pathlib import Path
import runpy
import math

import numpy as np
import pytest


hook = runpy.run_path(str(Path(__file__).parents[2] / 'jobs/POLY63-B/hooks/body_grid.py'))
build = hook['build']


def test_near_crossing_belt_is_sewn():
    design = {'modules': {
        'A': {'ring': [(0, 0), (4, 0), (4, 4), (0, 4)], 'zone': [0]*4},
        'B': {'ring': [(0, -.004), (4, .001), (4, 3), (0, 3)], 'zone': [2]*4},
    }, 'floors': [{'type': key, 'bottom': i, 'top': i+1, 'openings': []}
                  for i, key in enumerate('AB')]}
    mesh = build(design)
    edges = Counter(tuple(sorted((a, b))) for f in mesh['faces']
                    for a, b in zip(f, f[1:] + f[:1]))
    assert not [(a, b, n) for (a, b), n in edges.items()
                if mesh['vertices'][a][2] == mesh['vertices'][b][2] == 1 and n != 2]


def test_corner_uses_tangent_anchored_full_steps_and_sagitta():
    points = np.array([(2*math.cos(a), 2*math.sin(a)) for a in np.linspace(0, math.pi/2, 23)])
    arc, xy = hook['resample_arc'](points, .6)
    assert np.allclose(xy[[0,-1]], points[[0,-1]])
    lengths = np.linalg.norm(np.diff(xy, axis=0), axis=1)
    stations = np.r_[0., lengths.cumsum()]
    for target in .6*np.arange(1,6):
        assert min(abs(stations-target)) < 1e-9
    assert 0 < stations[-1]-3 < .6
    assert max(2-np.linalg.norm((xy[1:]+xy[:-1])/2, axis=1)) <= .020


@pytest.mark.parametrize('stretched, jump', [(False, False), (True, False), (False, True), (True, True)])
def test_native_registration_rejects_stretched_repeat_and_same_id_jump(stretched, jump):
    checker = runpy.run_path(str(Path(__file__).parents[2] / 'jobs/POLY63-B/hooks/check_readback.py'))
    # Independent circular fixture. Each full repeat requires two .30 m chords.
    angle = 2*math.asin((.26 if stretched else .30)/4)
    angles = [0., angle, 2*angle, 2*angle+.09]
    xy = np.array([(2*math.cos(t), 2*math.sin(t)) for t in angles])
    residual = float(np.linalg.norm(xy[-1]-xy[-2]))
    u = [0., .5, 1., 2. if stretched else 1.+residual/.6]
    samples = [(xy[i:i+2], u[i:i+2]) for i in range(3)]
    arc = checker['measure_arc'](xy, [0, 2], [0.,0.], 2., samples, .6)
    assert (arc['max_step_error_m'] > .0002) == stretched
    assert (arc['max_uv_metric_error_m'] > .0002) == stretched
    assert arc['terminal_remainder_m'] == pytest.approx(residual)
    assert arc['max_sagitta_m'] <= .02
    edge = checker['phase_delta']([(1.,.5), (1.,1.5)], [(2.15 if jump else 2.,.5), (2.15 if jump else 2.,1.5)])
    assert checker['registration_failures']({'corner': arc}, edge, .6) == (
        (['corner'] if stretched else []) + (['same-ID facade edge phase'] if jump else []))
