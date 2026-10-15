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


def _rigid_motion(rng):
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
    return rotation, rng.normal(size=3)


def _rigid(points, rng):
    rotation, translation = _rigid_motion(rng)
    return np.asarray(points, dtype=np.float64) @ rotation.T + translation


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


def _aabb(x0, x1, y0, y1, z0, z1):
    verts = np.array(
        [
            [x0, y0, z0],
            [x1, y0, z0],
            [x1, y1, z0],
            [x0, y1, z0],
            [x0, y0, z1],
            [x1, y0, z1],
            [x1, y1, z1],
            [x0, y1, z1],
        ],
        dtype=np.float64,
    )
    _, faces = unit_cube()
    return verts, faces


def _cat(va, fa, vb, fb):
    va = np.asarray(va, dtype=np.float64)
    vb = np.asarray(vb, dtype=np.float64)
    shift = len(va)
    faces = list(fa) + [tuple(int(i) + shift for i in face) for face in fb]
    return np.vstack([va, vb]), faces


def test_box_resting_on_box_is_clean():
    base = _aabb(0.0, 1.0, 0.0, 1.0, 0.0, 1.0)
    resting = _cat(*base, *_aabb(0.1, 0.4, 0.1, 0.4, 1.0, 1.5))
    assert count_defects(*resting)["self_intersections"] == 0
    flush = _cat(*base, *_aabb(0.0, 0.3, 0.0, 0.3, 1.0, 1.5))
    assert count_defects(*flush)["self_intersections"] == 0
    sunk = _cat(*base, *_aabb(0.1, 0.4, 0.1, 0.4, 0.7, 1.2))
    assert count_defects(*sunk)["self_intersections"] > 0


def test_needle_through_flat_vertex_counts():
    """Flat floor around the origin, and a vertical triangle whose z=0 section passes through it."""
    verts = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, -1.0, 0.0],
            [1.0, 1.0, 0.0],
            [-1.0, 1.0, 0.0],
            [-1.0, -1.0, 0.0],
            [0.0, 0.0, -0.5],
            [0.3, 0.0, 0.5],
            [-0.3, 0.0, 0.5],
        ],
        dtype=np.float64,
    )
    faces = [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1), (5, 6, 7)]
    assert count_defects(verts, faces)["self_intersections"] > 0


def _axis_cuts(rng):
    count = int(rng.integers(1, 4))
    for _ in range(50):
        cuts = np.sort(rng.uniform(0.15, 0.85, size=count))
        if count == 1 or np.all(np.diff(cuts) >= 0.05):
            return [float(value) for value in cuts]
    return [float(value) for value in np.linspace(0.15, 0.85, count)]


def _grid_box(x0, x1, y0, y1, z0, z1, x_cuts, y_cuts, z_cuts):
    """Closed box. Each face is a grid of quads split into two triangles; vertices are welded."""
    xs = [x0, *sorted(x_cuts), x1]
    ys = [y0, *sorted(y_cuts), y1]
    zs = [z0, *sorted(z_cuts), z1]
    verts: list[tuple[float, float, float]] = []
    index: dict[tuple[int, int, int], int] = {}

    def vid(ix, iy, iz):
        key = (ix, iy, iz)
        if key not in index:
            index[key] = len(verts)
            verts.append((xs[ix], ys[iy], zs[iz]))
        return index[key]

    faces: list[tuple[int, int, int]] = []

    def quad(a, b, c, d):
        faces.append((a, b, c))
        faces.append((a, c, d))

    nx, ny, nz = len(xs), len(ys), len(zs)
    for iy in range(ny - 1):
        for iz in range(nz - 1):
            quad(vid(0, iy, iz), vid(0, iy, iz + 1), vid(0, iy + 1, iz + 1), vid(0, iy + 1, iz))
    ix = nx - 1
    for iy in range(ny - 1):
        for iz in range(nz - 1):
            quad(vid(ix, iy, iz), vid(ix, iy + 1, iz), vid(ix, iy + 1, iz + 1), vid(ix, iy, iz + 1))
    for ix in range(nx - 1):
        for iz in range(nz - 1):
            quad(vid(ix, 0, iz), vid(ix + 1, 0, iz), vid(ix + 1, 0, iz + 1), vid(ix, 0, iz + 1))
    iy = ny - 1
    for ix in range(nx - 1):
        for iz in range(nz - 1):
            quad(vid(ix, iy, iz), vid(ix, iy, iz + 1), vid(ix + 1, iy, iz + 1), vid(ix + 1, iy, iz))
    for ix in range(nx - 1):
        for iy in range(ny - 1):
            quad(vid(ix, iy, 0), vid(ix, iy + 1, 0), vid(ix + 1, iy + 1, 0), vid(ix + 1, iy, 0))
    iz = nz - 1
    for ix in range(nx - 1):
        for iy in range(ny - 1):
            quad(vid(ix, iy, iz), vid(ix + 1, iy, iz), vid(ix + 1, iy + 1, iz), vid(ix, iy + 1, iz))
    return np.array(verts, dtype=np.float64), faces


@pytest.mark.parametrize("seed", range(30))
def test_random_grid_boxes(seed):
    rng = np.random.default_rng(seed)
    cuts = [_axis_cuts(rng) for _ in range(3)]
    verts, faces = _grid_box(0.0, 1.0, 0.0, 1.0, 0.0, 1.0, *cuts)
    rotation, translation = _rigid_motion(rng)
    alone = verts @ rotation.T + translation
    assert count_defects(alone, faces)["duplicates_and_self_intersections"] == 0

    rest_v, rest_f = _grid_box(0.1, 0.9, 0.1, 0.9, 1.0, 1.5, [], [], [])
    merged_v, merged_f = _cat(verts, faces, rest_v, rest_f)
    assert count_defects(merged_v @ rotation.T + translation, merged_f)["self_intersections"] == 0

    depth = float(rng.uniform(0.1, 0.4))
    z0 = 1.0 - depth
    sunk_v, sunk_f = _grid_box(0.1, 0.9, 0.1, 0.9, z0, z0 + 0.5, [], [], [1.0])
    sunk_v, sunk_f = _cat(verts, faces, sunk_v, sunk_f)
    assert count_defects(sunk_v @ rotation.T + translation, sunk_f)["self_intersections"] > 0
