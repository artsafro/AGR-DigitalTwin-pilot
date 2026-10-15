"""Regulatory topology counts (issue #160) on numpy meshes, no Blender."""
import numpy as np
import pytest

from twinqa.geometry.topology import TOL_M, count_defects
from twinqa.scene import _topology_finding

_KEYS = (
    "duplicate_vertices",
    "duplicate_edges",
    "duplicate_polygons",
    "self_intersections",
    "isolated_vertices",
    "isolated_edges",
    "isolated_polygons",
    "zero_length_edges",
    "duplicates_and_self_intersections",
)


def unit_cube(offset=(0.0, 0.0, 0.0)):
    """Closed triangulated unit cube: 8 vertices, 12 triangles."""
    verts = np.array(
        [
            [0, 0, 0],
            [1, 0, 0],
            [1, 1, 0],
            [0, 1, 0],
            [0, 0, 1],
            [1, 0, 1],
            [1, 1, 1],
            [0, 1, 1],
        ],
        dtype=np.float64,
    )
    faces = [
        (0, 1, 2),
        (0, 2, 3),
        (4, 6, 5),
        (4, 7, 6),
        (0, 5, 1),
        (0, 4, 5),
        (3, 2, 6),
        (3, 6, 7),
        (0, 3, 7),
        (0, 7, 4),
        (1, 5, 6),
        (1, 6, 2),
    ]
    return verts + np.asarray(offset, dtype=np.float64), faces


def two_cubes(offset):
    v1, f1 = unit_cube()
    v2, f2 = unit_cube(offset)
    verts = np.vstack([v1, v2])
    faces = f1 + [tuple(i + 8 for i in face) for face in f2]
    return verts, faces


def test_clean_cube_has_no_defects():
    verts, faces = unit_cube()
    counts = count_defects(verts, faces)
    assert counts["tol_m"] == TOL_M
    for key in _KEYS:
        assert counts[key] == 0


def test_vertex_within_tolerance_is_duplicate_and_beyond_is_not():
    verts, faces = unit_cube()
    for shift, expected in ((0.0015, 1), (TOL_M, 1), (0.0025, 0)):
        extra = verts[0] + np.array([shift, 0.0, 0.0])
        far = np.array([[10.0, 0.0, 0.0], [11.0, 0.0, 0.0]])
        mesh = np.vstack([verts, extra, far])
        polys = faces + [(8, 9, 10)]
        assert count_defects(mesh, polys)["duplicate_vertices"] == expected


def test_loose_vertex_is_isolated():
    verts, faces = unit_cube()
    mesh = np.vstack([verts, [[5.0, 5.0, 5.0]]])
    assert count_defects(mesh, faces)["isolated_vertices"] == 1


def test_loose_edge_is_isolated():
    verts, faces = unit_cube()
    mesh = np.vstack([verts, [[4.0, 4.0, 4.0], [5.0, 4.0, 4.0]]])
    edges = [(8, 9)]
    assert count_defects(mesh, faces, edges)["isolated_edges"] == 1


def test_lone_triangle_is_isolated_polygon():
    verts, faces = unit_cube()
    mesh = np.vstack([verts, [[20.0, 20.0, 20.0], [21.0, 20.0, 20.0], [20.0, 21.0, 20.0]]])
    polys = faces + [(8, 9, 10)]
    assert count_defects(mesh, polys)["isolated_polygons"] == 1


def test_coincident_polygon_side_is_zero_length():
    verts, faces = unit_cube()
    mesh = np.vstack([verts, [verts[0]]])
    polys = faces + [(8, 0, 1)]
    assert count_defects(mesh, polys)["zero_length_edges"] >= 1


def test_duplicated_triangle_counts_as_one_duplicate_polygon():
    verts, faces = unit_cube()
    assert count_defects(verts, faces + [faces[0]])["duplicate_polygons"] == 1


def test_overlapping_cubes_self_intersect_and_touching_cubes_do_not():
    overlap = count_defects(*two_cubes((0.5, 0.5, 0.5)))
    touching = count_defects(*two_cubes((1.0, 0.0, 0.0)))
    assert overlap["self_intersections"] > 0
    assert touching["self_intersections"] == 0


def test_candidate_pairs_match_internal_broad_phase():
    verts, faces = two_cubes((0.5, 0.5, 0.5))
    explicit = [(i, j) for i in range(len(faces)) for j in range(i + 1, len(faces))]
    assert count_defects(verts, faces) == count_defects(verts, faces, candidate_pairs=explicit)


def test_empty_mesh():
    empty = count_defects(np.zeros((0, 3)), [])
    for key in _KEYS:
        assert empty[key] == 0
    loose = count_defects(np.zeros((0, 3)), [], edges=np.zeros((0, 2)))
    assert loose["isolated_edges"] == 0


def _plane_and_shallow_pierce(depth):
    """Horizontal triangle and a separate vertical triangle piercing its interior.

    The vertical triangle's lowest vertex sits at z = -depth; its other two
    vertices are at z = +0.5. The piercing edge passes through the horizontal
    centroid, so the hit is interior, not on an edge.
    """
    horizontal = np.array(
        [[-1.0, -1.0, 0.0], [1.0, -1.0, 0.0], [0.0, 1.0, 0.0]],
        dtype=np.float64,
    )
    y = -1.0 / 3.0
    vertical = np.array(
        [[0.0, y, -depth], [0.0, y + 0.2, 0.5], [0.0, y - 0.2, 0.5]],
        dtype=np.float64,
    )
    return np.vstack([horizontal, vertical]), [(0, 1, 2), (3, 4, 5)]


@pytest.mark.parametrize(
    ("depth", "expected"),
    [(0.0015, 0), (0.0025, 1), (TOL_M, 0)],
)
def test_shallow_penetration_is_not_a_self_intersection(depth, expected):
    counts = count_defects(*_plane_and_shallow_pierce(depth))
    assert counts["self_intersections"] == expected


@pytest.mark.parametrize("seed", range(50))
def test_separated_and_overlapping_random_cubes(seed):
    rng = np.random.default_rng(seed)
    direction = rng.normal(size=3)
    direction = direction / np.linalg.norm(direction)
    far = count_defects(*two_cubes(direction * rng.uniform(3.0, 8.0)))
    assert far["self_intersections"] == 0
    assert far["duplicate_vertices"] == 0
    assert far["duplicate_edges"] == 0
    assert far["duplicate_polygons"] == 0
    near = rng.uniform(0.05, 0.9, size=3) * rng.choice(np.array([-1.0, 1.0]), size=3)
    assert count_defects(*two_cubes(near))["self_intersections"] > 0


def _copies(base, faces, n=101, step=4.0):
    base = np.asarray(base, dtype=np.float64)
    nv = len(base)
    shift = np.array([step, 0.0, 0.0])
    verts = np.concatenate([base + shift * k for k in range(n)])
    polys = [tuple(int(i) + nv * k for i in face) for k in range(n) for face in faces]
    return verts, polys


def _crossing_vertices(depth):
    return np.array(
        [
            [-1.0, -1.0, 0.0],
            [1.0, -1.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, -0.3, -depth],
            [0.0, -0.1, 0.5],
            [0.0, -0.5, 0.5],
            [0.0, -0.2, 0.0],
            [0.0, -0.4, 0.0],
        ],
        dtype=np.float64,
    )


def _rigid(points, rng):
    axis = rng.normal(size=3)
    axis = axis / np.linalg.norm(axis)
    angle = float(rng.uniform(0.0, 2.0 * np.pi))
    x, y, z = axis
    c, s = np.cos(angle), np.sin(angle)
    cross = 1.0 - c
    rotation = np.array(
        [
            [c + x * x * cross, x * y * cross - z * s, x * z * cross + y * s],
            [y * x * cross + z * s, c + y * y * cross, y * z * cross - x * s],
            [z * x * cross - y * s, z * y * cross + x * s, c + z * z * cross],
        ]
    )
    return points @ rotation.T + rng.normal(size=3)


def test_shared_vertex_proper_crossing_counts():
    verts = [(0, 0, 0), (2, 0, 0), (0, 2, 0), (1, 1, 1), (1, 1, -1)]
    faces = [(0, 1, 2), (0, 3, 4)]
    assert count_defects(verts, faces)["self_intersections"] == 1
    copies, polys = _copies(verts, faces)
    assert count_defects(copies, polys)["self_intersections"] == 101


def test_common_vertex_only_contact_is_clean():
    verts = [(0, 0, 0), (2, 0, 0), (0, 2, 0), (-1, -1, 1), (-1, -1, -1)]
    assert count_defects(verts, [(0, 1, 2), (0, 3, 4)])["self_intersections"] == 0
    right_angle = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
    assert count_defects(right_angle, [(0, 1, 2), (0, 1, 3)])["self_intersections"] == 0


def test_subdivided_crossing_counts():
    verts = _crossing_vertices(0.5)
    assert count_defects(verts, [(0, 1, 2), (3, 4, 5)])["self_intersections"] == 1
    split = [(0, 1, 2), (3, 6, 7), (6, 4, 5), (6, 5, 7)]
    assert count_defects(verts, split)["self_intersections"] == 1


def test_subdivided_crossing_101_copies():
    base = [
        (-1, -1, 0),
        (1, -1, 0),
        (0, 1, 0),
        (0, -0.3, -0.5),
        (0, -0.1, 0.5),
        (0, -0.5, 0.5),
        (0, -0.2, 0),
        (0, -0.4, 0),
        (-2, -1, 0),
        (-1, -2, 0),
    ]
    faces = [(0, 1, 2), (3, 6, 7), (6, 4, 5), (6, 5, 7), (0, 8, 9)]
    verts, polys = _copies(base, faces)
    counts = count_defects(verts, polys)
    assert counts["self_intersections"] >= 101
    assert counts["duplicates_and_self_intersections"] > 100
    assert counts["isolated_polygons"] == 0
    finding = _topology_finding(
        [{"name": "SM_Test_K_1_Main", "topology": counts}],
        {"geometry": {}},
        "synthetic.fbx",
    )
    assert finding.status == "fail"


def test_wall_on_floor_touch_is_clean():
    floor = [(-1.0, -1.0, 0.0), (1.0, -1.0, 0.0), (0.0, 1.0, 0.0)]
    wall = [(0.0, -0.2, 0.0), (0.0, -0.5, 0.0), (0.0, -0.35, 1.0)]
    single = np.array(floor + wall, dtype=np.float64)
    assert count_defects(single, [(0, 1, 2), (3, 4, 5)])["self_intersections"] == 0
    midpoint = [(0.0, -0.35, 0.0)]
    split = np.array(floor + wall + midpoint, dtype=np.float64)
    assert count_defects(split, [(0, 1, 2), (3, 6, 5), (6, 4, 5)])["self_intersections"] == 0


@pytest.mark.parametrize(("depth", "expected"), [(0.0015, 0), (0.002, 0), (0.0025, 1)])
def test_subdivided_shallow_penetration_boundary(depth, expected):
    split = [(0, 1, 2), (3, 6, 7), (6, 4, 5), (6, 5, 7)]
    assert count_defects(_crossing_vertices(depth), split)["self_intersections"] == expected


def test_welded_cross_junction_is_not_a_self_intersection():
    verts = np.array(
        [
            [-1.0, -1.0, 0.0],
            [1.0, -1.0, 0.0],
            [1.0, 1.0, 0.0],
            [-1.0, 1.0, 0.0],
            [0.0, -0.5, 0.0],
            [0.0, 0.5, 0.0],
            [0.0, -0.5, -1.0],
            [0.0, 0.5, -1.0],
            [0.0, 0.5, 1.0],
            [0.0, -0.5, 1.0],
        ],
        dtype=np.float64,
    )
    faces = [
        (0, 4, 5),
        (0, 5, 3),
        (1, 5, 4),
        (1, 2, 5),
        (4, 5, 7),
        (4, 7, 6),
        (4, 9, 5),
        (5, 9, 8),
    ]
    assert count_defects(verts, faces)["self_intersections"] == 0


@pytest.mark.parametrize("seed", range(50))
def test_random_subdivided_crossings(seed):
    rng = np.random.default_rng(seed)
    split = [(0, 1, 2), (3, 6, 7), (6, 4, 5), (6, 5, 7)]
    moved = _rigid(_crossing_vertices(0.5), rng)
    assert count_defects(moved, split)["self_intersections"] == 1
    floor = np.array(
        [[-1.0, -1.0, 0.0], [1.0, -1.0, 0.0], [0.0, 1.0, 0.0],
         [0.0, -0.2, 0.0], [0.0, -0.5, 0.0], [0.0, -0.35, 1.0]],
        dtype=np.float64,
    )
    assert count_defects(_rigid(floor, rng), [(0, 1, 2), (3, 4, 5)])["self_intersections"] == 0
