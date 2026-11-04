"""Contour-first remeshing must remove only artificial planar seed edges."""
import numpy as np
import pytest
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


def test_bounded_plane_union_does_not_accumulate_pairwise_drift():
    from dt_ai.geometry.ground_planar import planar_patches
    seed = grid(8)
    seed.verts[:, 2] += (seed.verts[:, 0]**2)*1e-6
    patches = planar_patches(seed, allowed_slots={'TileLight'}, plane_tolerance_m=1e-5)
    assert 1 < len(patches) < len(seed.faces)
    for p in patches:
        xyz = seed.verts[seed.faces[list(p.source_faces)]].reshape(-1, 3)
        normal = np.cross(*p.axes)
        assert np.max(np.abs((xyz-p.origin) @ normal)) <= 1e-5


@pytest.mark.parametrize('tolerance', [0., -1., float('nan'), float('inf'), 1.0001e-5, True])
def test_plane_tolerance_is_not_an_acceptance_override(tolerance):
    from dt_ai.geometry.ground_planar import planar_patches
    with pytest.raises(ValueError, match='tolerance'):
        planar_patches(grid(), allowed_slots={'TileLight'}, plane_tolerance_m=tolerance)


def test_unmapped_slot_is_named():
    from dt_ai.geometry.ground_planar import planar_patches
    with pytest.raises(ValueError, match='TileLight'):
        planar_patches(grid(), allowed_slots={'Mulch'})


@pytest.mark.parametrize('slots', [None, [], {' '}, {'TileLight', 4}])
def test_invalid_slot_inventory_is_rejected(slots):
    from dt_ai.geometry.ground_planar import planar_patches
    with pytest.raises(ValueError, match='slots'):
        planar_patches(grid(), allowed_slots=slots)


@pytest.mark.parametrize('level', [0.5, np.nan, np.inf])
def test_nonintegral_or_nonfinite_level_cannot_be_truncated(level):
    from dt_ai.geometry.ground_planar import planar_patches
    seed = grid()
    seed.level = np.full(len(seed.faces), level)
    with pytest.raises(ValueError, match='level'):
        planar_patches(seed, allowed_slots={'TileLight'})


def test_protected_sample_faces_keep_exact_source_membership():
    from dt_ai.geometry.ground_planar import planar_patches
    patches = planar_patches(grid(), allowed_slots={'TileLight'}, protected_faces={0, 1})
    assert (0,) in [p.source_faces for p in patches]
    assert (1,) in [p.source_faces for p in patches]
    assert sorted(i for p in patches for i in p.source_faces) == list(range(8))


@pytest.mark.parametrize('protected', [{-1}, {8}, {True}, {0.5}, [0, 0]])
def test_invalid_protected_faces_fail_closed(protected):
    from dt_ai.geometry.ground_planar import planar_patches
    with pytest.raises(ValueError, match='protected'):
        planar_patches(grid(), allowed_slots={'TileLight'}, protected_faces=protected)


def test_semantic_seam_is_not_dissolved():
    from dt_ai.geometry.ground_planar import planar_patches
    seed = grid()
    seed.slot[:2] = ['Mulch']*2
    patches = planar_patches(seed, allowed_slots={'Mulch', 'TileLight'})
    assert [(p.slot, len(p.source_faces)) for p in patches] == [('Mulch', 2), ('TileLight', 6)]


@pytest.mark.parametrize('seed_id', range(30))
def test_generated_rotations_offsets_keep_union_and_membership(seed_id):
    from dt_ai.geometry.ground_planar import planar_patches
    rng = np.random.default_rng(seed_id)
    seed = grid(4)
    q, _ = np.linalg.qr(rng.normal(size=(3, 3)))
    if np.linalg.det(q) < 0:
        q[:, 0] *= -1
    seed.verts = seed.verts @ q + rng.uniform(-1e6, 1e6, 3)
    patches = planar_patches(seed, allowed_slots={'TileLight'})
    assert len(patches) == 1
    p = patches[0]
    assert p.source_faces == tuple(range(8))
    area = sum(np.linalg.norm(np.cross(*(seed.verts[f][1:]-seed.verts[f][0])))/2
               for f in seed.faces)
    assert p.polygon.area == pytest.approx(area, abs=1e-7)
    boundary = p.to_world(np.array(p.polygon.exterior.coords))
    assert np.max(np.min(np.linalg.norm(boundary[:, None]-seed.verts, axis=2), axis=1)) < 1e-7


@pytest.mark.parametrize('kind', ['empty', 'nan', 'inf', 'duplicate', 'nonmanifold', 'bad_uv', 'blank'])
def test_malformed_source_is_never_a_successful_empty_patch_set(kind):
    from dt_ai.geometry.ground_planar import planar_patches
    seed = grid()
    if kind == 'empty':
        seed.faces = np.empty((0, 3), int)
    elif kind in ('nan', 'inf'):
        seed.verts[0, 0] = float(kind)
    elif kind == 'duplicate':
        seed.faces[1] = seed.faces[0]
    elif kind == 'nonmanifold':
        seed.faces[2] = [0, 6, 4]
    elif kind == 'bad_uv':
        seed.uv[0, 0, 0] = np.nan
    else:
        seed.slot[0] = ' '
    with pytest.raises(ValueError):
        planar_patches(seed, allowed_slots={'TileLight'})


def test_inconsistent_winding_is_not_hidden_as_separate_patch():
    from dt_ai.geometry.ground_planar import planar_patches
    seed = grid()
    seed.faces[0] = seed.faces[0][::-1]
    with pytest.raises(ValueError, match='winding'):
        planar_patches(seed, allowed_slots={'TileLight'})

