"""Contour-first remeshing must remove only artificial planar seed edges."""
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

from dt_ai.geometry.ground_cake import Mesh


def grid(nx=4):
    verts = np.array([(x, y, .2*x+.3*y) for y in (0., 1.) for x in range(nx+1)])
    faces = np.array([f for i in range(nx) for f in ((i, i+1, i+nx+2), (i, i+nx+2, i+nx+1))])
    return Mesh(verts, faces, ['TileLight']*len(faces), np.zeros(len(faces), int),
                verts[faces, :2]/4, 4.)


def test_planar_patch_removes_interior_grid_without_source_loss():
    from dt_ai.geometry.ground_planar import planar_patches
    seed = grid()
    snapshot = seed.verts.copy()
    patches = planar_patches(seed, allowed_slots={'TileLight'})
    assert len(patches) == 1
    patch = patches[0]
    assert patch.source_faces == tuple(range(8))
    assert patch.slot == 'TileLight' and patch.level == 0
    assert patch.polygon.area > 0
    world = patch.to_world(np.array(patch.polygon.exterior.coords))
    assert np.max(np.abs(world[:, 2]-(.2*world[:, 0]+.3*world[:, 1]))) < 1e-12
    actual = Polygon(world[:, :2])
    expected = unary_union([Polygon(seed.verts[f, :2]) for f in seed.faces])
    assert actual.symmetric_difference(expected).area < 1e-12
    assert np.array_equal(seed.verts, snapshot)
