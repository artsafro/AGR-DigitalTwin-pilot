"""Synthetic belt-joint witness with the measured crossing geometry simplified to XY."""
from collections import Counter
from pathlib import Path
import runpy
import math

import numpy as np


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
    assert len(xy) >= 7  # at least six chords (sagitta), with every texture division represented
    assert (len(xy)-1) % 5 == 0
    assert arc['steps'] == 5
    assert max(2-np.linalg.norm((xy[1:]+xy[:-1])/2, axis=1)) <= .020
