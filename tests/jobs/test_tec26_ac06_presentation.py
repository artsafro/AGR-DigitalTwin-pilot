"""new-case: AC06 presentation overrides retain source identity and sandwich coverage."""
import importlib.util
import json
from pathlib import Path

import pytest

JOB = Path(__file__).resolve().parents[2] / 'jobs/TEC26-OKS/AC06'


def adapter():
    s = importlib.util.spec_from_file_location('ac06', JOB / 'build_ac06.py')
    assert s is not None and s.loader is not None
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def test_slide_regions_inside_original_ids():
    m = adapter()
    # Synthetic orthogonal fascia, roof and wall, not production measurements.
    vertices = [[0, 0, 2.5], [1, 0, 2.5], [1, 0, 3.5], [0, 0, 3.5],
                [0, 1, 3.5], [1, 1, 3.5], [0, 0, -1], [1, 0, -1],
                [1, 0, 0], [0, 0, 0]]
    faces = [[0, 1, 2, 3], [3, 2, 5, 4], [0, 1, 2, 3], [6, 7, 8, 9], [0, 1, 2, 3]]
    spec = json.loads((JOB / 'vpm_textures.json').read_text())
    assert m.region_finishes(vertices, faces, [1, 1, 3, 10, 2], spec) == [
        'Sandwich_RAL5015', 'Door_RAL7004', 'Sandwich_RAL7047', 'Panel_RAL7047', 'Sandwich_RAL5015']
    assert faces == [[0, 1, 2, 3], [3, 2, 5, 4], [0, 1, 2, 3], [6, 7, 8, 9], [0, 1, 2, 3]]


def test_canopy_horizontal_faces_also_sandwich():
    s = json.loads((JOB / 'vpm_textures.json').read_text())
    v = [[0,0,2.8], [1,0,2.8], [1,1,2.8], [0,1,2.8]]
    assert adapter().region_finishes(v, [[0,1,2,3]], [2], s) == ['Sandwich_RAL5015']
    assert adapter().region_finishes(v, [[0,1,2,3]], [1], s) == ['Door_RAL7004']


def test_collision_cap_triangulation_without_geometry_change():
    import numpy as np
    dump = json.loads((JOB / 'max-dump-006.json').read_text())
    hull = next(n for n in dump['nodes'] if n['handle'] == 222)
    triangles = adapter().collision_triangles(hull['vertices'], hull['faces'])
    assert len(triangles) == 44
    assert set(k for f in triangles for k in f) == set(range(24))
    v = np.asarray(hull['vertices'])
    for f in triangles:
        p = v[f]
        normal = np.cross(p[1]-p[0], p[2]-p[0])
        normal /= np.linalg.norm(normal)
        assert ((v-p[0]) @ normal).max() <= 1e-5
    # A cap cannot authorize flattening a genuinely concave solid.
    bad = v.copy()
    bad[0] = v.mean(0)
    with pytest.raises(ValueError, match='triangulation'):
        adapter().collision_triangles(bad.tolist(), hull['faces'])


@pytest.mark.parametrize('bad', [float('nan'), float('inf')])
def test_nonfinite_region_refused(bad):
    with pytest.raises(ValueError, match='finite'):
        adapter().region_finishes([[0, 0, bad], [1, 0, 0], [0, 1, 0]], [[0, 1, 2]], [1], {})
