"""Pattern: attached-decor | new-case: source-bound decor placement and rigid repair."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from dt_ai.ops.inv_quads import PolyMesh

FIXTURE = json.loads((Path(__file__).parents[1] / 'fixtures/attached_decor/contacts.json').read_text())


def api():
    assert importlib.util.find_spec('dt_ai.ops.attached_decor'), 'attached-decor operation is missing'
    from dt_ai.ops import attached_decor
    return attached_decor


def patch(z=0.0):
    return PolyMesh(np.array([[0, 0, z], [1, 0, z], [1, 1, z], [0, 1, z]], float), ((0, 1, 2, 3),))


def scene_case(name):
    return {k: PolyMesh(np.array(p['vertices']), (tuple(range(len(p['vertices']))),))
            for k, p in FIXTURE['cases'][name]['parts'].items()}


def test_railing_on_coping():
    op = api()
    # Synthetic arithmetic witness: independent 0.7300 / 0.73 levels coincide.
    assert op.clearance_pairs({'coping': patch(.73), 'glass': patch(.7300)})
    assert not op.clearance_pairs({'coping': patch(.73), 'glass': patch(.86)})
    # Actual tilted face, not its centroid: the near end fails in both versions.
    for tag in ('v013', 'v027', 'v028'):
        assert op.clearance_pairs(scene_case('railing_' + tag))
