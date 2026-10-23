"""new-case: join and atomic seam simplification regression controls (#530)."""
import numpy as np

from dt_ai.ops.inv_quads import PolyMesh
from dt_ai.ops.inv_xview import XviewTolerance, face_pairs


def band(cols=30, sag=0.002):
    v = [(0, 0, 0), (10, 0, 0), (10, 0, 3.5), (0, 0, 3.5)]
    xs = np.linspace(0, 10, cols + 1)
    bottom = [3] + list(range(4, 4 + cols - 1)) + [2]
    v += [(x, sag * np.sin(np.pi * x / 10), 3.5) for x in xs[1:-1]]
    top = list(range(len(v), len(v) + cols + 1))
    v += [(x, sag * np.sin(np.pi * x / 10), 4.05) for x in xs]
    return PolyMesh(v, ((0, 1, 2, 3),)), PolyMesh(v, tuple(
        (bottom[i], bottom[i+1], top[i+1], top[i]) for i in range(cols)))


def contacts(mesh):
    return [p for p in face_pairs(mesh, XviewTolerance()) if 'contact' in p[2]]


def test_join_conforms_sagged_band_to_glass_boundary_without_separating():
    from dt_ai.ops.seams import join_parts
    glass, strip = band()
    before = PolyMesh(glass.vertices, glass.faces + strip.faces)
    assert len(contacts(before)) == 30
    result = join_parts({'glass': glass, 'band': strip})
    assert contacts(result.mesh) == []
    assert len(result.mesh.faces) == 31
    assert len(result.face_sources) == 31
    assert result.max_weld_m <= 0.002000001
    assert result.displacements == {}
    assert len(result.mesh.faces[0]) == 33
    assert np.array_equal(glass.vertices, strip.vertices)
