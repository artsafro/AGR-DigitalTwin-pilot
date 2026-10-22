"""AC06 presentation overrides retain source identity and sandwich coverage."""
import importlib.util
import json
from pathlib import Path

import pytest

JOB = Path(__file__).resolve().parents[2] / 'jobs/TEC26-OKS/AC06'


def adapter():
    s = importlib.util.spec_from_file_location('ac06', JOB / 'build_ac06.py')
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def test_slide_regions_inside_original_ids():
    m = adapter()
    # Synthetic orthogonal fascia, roof and wall, not production measurements.
    vertices = [[0, 0, 2.5], [1, 0, 2.5], [1, 0, 3.5], [0, 0, 3.5],
                [0, 1, 3.5], [1, 1, 3.5], [0, 0, -1], [1, 0, -1],
                [1, 0, 0], [0, 0, 0]]
    faces = [[0, 1, 2, 3], [3, 2, 5, 4], [0, 1, 2, 3], [6, 7, 8, 9]]
    spec = json.loads((JOB / 'vpm_textures.json').read_text())
    assert m.region_finishes(vertices, faces, [1, 1, 3, 10], spec) == [
        'Sandwich_RAL5015', 'Door_RAL7004', 'Sandwich_RAL7047', 'Panel_RAL7047']
    assert faces == [[0, 1, 2, 3], [3, 2, 5, 4], [0, 1, 2, 3], [6, 7, 8, 9]]


@pytest.mark.parametrize('bad', [float('nan'), float('inf')])
def test_nonfinite_region_refused(bad):
    with pytest.raises(ValueError, match='finite'):
        adapter().region_finishes([[0, 0, bad], [1, 0, 0], [0, 1, 0]], [[0, 1, 2]], [1], {})
