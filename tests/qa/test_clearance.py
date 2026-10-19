# Boundary cases ported from AGR tests/test_glb_clearance.py (sha256 b11dd4371c83) on 2026-10-06; changes: call the
# function directly, tolerance from the VPM profile, plus an FBX roundtrip through Blender.
"""Near-parallel overlap: 0 / 4 / 6 mm, both orientations, split borders, FBX input."""
import json
import random
import subprocess
import time

import numpy as np
import pytest
import shapely.errors
from shapely.geometry import Polygon

import check_clearance
from test_validator import PROFILES
from twinqa.clearance import AREA_MIN_M2, PARALLEL_COS_MIN, _normal, near_parallel_overlaps
from twinqa.scene import find_blender

TOL = PROFILES.vpm["geometry"]["near_coplanar_spacing_m"]["min"]


def test_tolerance_comes_from_profile():
    assert TOL == 0.005  # reg p.29: 5 mm - 2 cm spacing


@pytest.mark.parametrize("distance, reverse, shift, expected", [
    (0.0, False, 0.25, 1), (0.004, True, 0.25, 1), (0.006, True, 0.25, 0), (0.0, True, 1.0, 0)])
@pytest.mark.parametrize("split_border", [False, True])
def test_partial_area_clearance_both_orientations(distance, reverse, shift, expected, split_border):
    a = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]
    if split_border:
        a.insert(1, [0.5, 0, 0])
    b = [[x + shift, y, distance] for x, y, _ in a]
    if reverse:
        b.reverse()
    pairs = near_parallel_overlaps([{"object": "a", "index": 0, "points": a},
                                    {"object": "b", "index": 0, "points": b}], TOL)
    assert len(pairs) == expected
    if expected:
        assert pairs[0]["same_direction"] == (not reverse)


BLENDER = find_blender()
TWO_PLANES = """
import bpy, sys
out = sys.argv[sys.argv.index('--') + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
for z in (0.0, 0.003):  # 3 mm apart, overlapping
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, z))
bpy.ops.export_scene.fbx(filepath=out)
"""


@pytest.mark.blender
@pytest.mark.skipif(BLENDER is None, reason="Blender not installed")
def test_fbx_planes_3mm_apart_are_reported(tmp_path):
    fbx = tmp_path / "planes.fbx"
    subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                    "--python-expr", TWO_PLANES, "--", str(fbx)], check=True, capture_output=True, timeout=300)
    report = tmp_path / "report.json"
    assert check_clearance.main([str(fbx), str(report)]) == 1
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["pair_count"] == 1 and abs(data["pairs"][0]["distance_m"] - 0.003) < 1e-6


def _reference_near_parallel_overlaps(faces, tolerance_m):
    pts = [np.asarray(f["points"], dtype=float) for f in faces]
    if not pts:
        return []
    normals = np.array([_normal(p) for p in pts])
    centers = np.array([p.mean(0) for p in pts])
    lows, highs = np.array([p.min(0) for p in pts]), np.array([p.max(0) for p in pts])
    pairs = []
    for i, face in enumerate(faces):
        n = normals[i]
        if np.linalg.norm(n) < 0.9:
            continue
        dot = normals @ n
        cand = np.where((np.abs(dot) > PARALLEL_COS_MIN) & (np.abs((centers - pts[i][0]) @ n) < tolerance_m + 1e-5))[0]
        axes = [k for k in range(3) if k != int(np.argmax(np.abs(n)))]  # project on the dominant plane
        cand = cand[np.all(np.minimum(highs[cand][:, axes], highs[i, axes]) > np.maximum(lows[cand][:, axes], lows[i, axes]), axis=1)]
        a = Polygon(pts[i][:, axes])
        for j in cand:
            if j <= i:
                continue
            area = a.intersection(Polygon(pts[j][:, axes])).area
            if area < AREA_MIN_M2:
                continue
            dist = abs(float((centers[j] - pts[i][0]) @ n))
            if dist >= tolerance_m - 1e-7:
                continue
            pairs.append({"a": [face["object"], face["index"]], "b": [faces[j]["object"], faces[j]["index"]],
                          "distance_m": dist, "same_direction": bool(dot[j] > 0), "projected_area_m2": float(area)})
    return pairs


def _box(n, size=10.0):  # closed box, n x n quads per side -> 12 n^2 triangles (docs/research/mesh-audit-scaling-real-sizes.md, appendix A)
    verts, index, tris = [], {}, []
    def vid(p):
        key = tuple(round(c, 9) for c in p)
        if key not in index:
            index[key] = len(verts); verts.append(key)
        return index[key]
    g = np.linspace(0.0, size, n + 1)
    for axis in range(3):
        for side in (0.0, size):
            u, w = [k for k in range(3) if k != axis]
            for i in range(n):
                for j in range(n):
                    q = []
                    for a, b in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)):
                        p = [0.0, 0.0, 0.0]; p[axis], p[u], p[w] = side, g[a], g[b]; q.append(vid(p))
                    t1, t2 = (q[0], q[1], q[2]), (q[0], q[2], q[3])
                    if (side == 0.0) == ((u - axis) % 3 == 1):
                        t1, t2 = t1[::-1], t2[::-1]
                    tris += [t1, t2]
    return np.array(verts, float), np.array(tris, int)


def _bipyramid(faces):  # ring of faces/2 vertices + 2 apexes: slivers
    m = max(faces // 2, 3)
    a = np.linspace(0, 2 * np.pi, m, endpoint=False)
    v = np.vstack([np.stack([10 * np.cos(a), 10 * np.sin(a), np.zeros(m)], 1), [[0, 0, 10.0]], [[0, 0, -10.0]]])
    t = [(i, (i + 1) % m, m) for i in range(m)] + [((i + 1) % m, i, m + 1) for i in range(m)]
    return v, np.array(t, int)


def _mesh_faces(verts, tris, index_base=0):
    return [{"object": "model", "index": index_base + i, "points": verts[tri].tolist()} for i, tri in enumerate(tris)]


def _corpus(seed):
    """~150-400 faces: parallel pairs, insets, contacts, threshold cases, clutter."""
    rng = np.random.default_rng(seed)
    py = random.Random(seed)
    tol = (0.003, 0.005, 0.02)[seed % 3]
    faces = []

    def add(points, obj="part"):
        faces.append({"object": obj, "index": len(faces), "points": np.asarray(points, float).tolist()})

    def basis(normal):
        n = np.asarray(normal, float)
        n = n / np.linalg.norm(n)
        tmp = np.array([1.0, 0.0, 0.0]) if abs(n[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        u = np.cross(n, tmp)
        u /= np.linalg.norm(u)
        return n, u, np.cross(n, u)

    def place(origin, normal, xy):
        n, u, v = basis(normal)
        o = np.asarray(origin, float)
        return [o + x * u + y * v for x, y in xy]

    def emit(origin, normal, xy, dist, reverse, inset=0.0, slide=(0.0, 0.0)):
        a = place(origin, normal, xy)
        cx = sum(x for x, _ in xy) / len(xy)
        cy = sum(y for _, y in xy) / len(xy)
        shrunk = [(cx + (x - cx) * (1 - inset) + slide[0], cy + (y - cy) * (1 - inset) + slide[1]) for x, y in xy]
        n = np.asarray(normal, float)
        n = n / np.linalg.norm(n)
        b = place(np.asarray(origin, float) + n * dist, normal, shrunk)
        add(a)
        add(b[::-1] if reverse else b)

    def rot_matrix():
        q, r = np.linalg.qr(rng.normal(size=(3, 3)))
        q = q * np.sign(np.diag(r))
        if np.linalg.det(q) < 0:
            q[:, 0] *= -1
        return q

    quad = [(0, 0), (1, 0), (1, 1), (0, 1)]
    tri = [(0, 0), (1, 0), (0.2, 1)]
    pent = [(0, 0), (0.5, 0), (1, 0), (1, 1), (0, 1)]  # collinear split-border vertex
    n45 = np.array([1.0, 1.0, 0.0])
    n_rand = rot_matrix()[:, 2]

    def slot(i):
        return np.array([(i % 6) * 4.0, (i // 6) * 4.0, (i % 3) * 0.5])

    emit(slot(0), [0, 0, 1], quad, tol * 0.4, False, inset=0.1)  # same direction
    emit(slot(1), [0, 1, 0], tri, tol * 0.3, True, inset=0.05)  # opposite
    emit(slot(2), n45, pent, min(tol * 0.5, 0.01), False, slide=(0.15, 0.1))
    emit(slot(3), n_rand, quad, 0.005, True, inset=0.2, slide=(0.05, -0.02))  # 5 mm inset
    emit(slot(4), [0, 0, 1], quad, 0.0, False, slide=(0.3, 0.2))  # coplanar overlap
    add(place(slot(5), [0, 0, 1], quad))  # coplanar edge contact, zero area
    add(place(slot(5), [0, 0, 1], [(1, 0), (2, 0), (2, 1), (1, 1)]))
    for k, delta in enumerate((1e-6, -1e-6, 1e-8, -1e-8)):
        emit(slot(6 + k), [1, 0, 0], quad, tol + delta, k % 2 == 1)
    for k, delta in enumerate((1e-9, -1e-9)):
        emit(slot(10 + k), [0, 1, 0], tri, tol - 1e-7 + delta, True)
    theta = float(np.arccos(PARALLEL_COS_MIN))
    base = np.array([0.0, 0.0, 1.0])
    for k, factor in enumerate((0.5, 0.99, 1.01, 2.0)):
        tilted = np.array([np.sin(theta * factor), 0.0, np.cos(theta * factor)])
        origin = slot(12 + k)
        add(place(origin, base, quad))
        add(place(origin + base * (tol * 0.25), tilted, [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)]))
    # Same-direction pair split across a normal-cell boundary (h = 0.005).
    z0 = 0.05
    for k, z in enumerate((z0 - 1e-4, z0 + 1e-4)):
        xy = float(np.sqrt(max(0.0, 1.0 - z * z)))
        normal = [xy, 0.0, z]
        origin = slot(16) + np.array([0.0, 0.0, k * tol * 0.2])
        add(place(origin, normal, [(0.05, 0.05), (0.85, 0.05), (0.85, 0.85), (0.05, 0.85)]))
    ang = np.pi / 4
    c, s = float(np.cos(ang)), float(np.sin(ang))
    rot45 = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    pivot = slot(18)
    for pts in (place(pivot, [0, 0, 1], quad), place(pivot + np.array([0, 0, tol * 0.2]), [0, 0, 1], quad)):
        add((np.asarray(pts, float) - pivot) @ rot45.T + pivot)
    add([[0, 0, 0], [1, 0, 0], [2, 0, 0]])  # collinear
    add([[3, 3, 3], [3, 3, 3], [3, 3, 3]])  # zero normal
    add([[4, 0, 0], [4, 1, 0], [4, 2, 0], [4, 3, 0]])
    for _ in range(140 + py.randrange(200)):
        center = rng.uniform(-30.0, 30.0, size=3)
        add(center + rng.normal(scale=0.35, size=(py.choice((3, 4, 5)), 3)), "clutter")
    if seed % 4 == 0:
        offset = np.array([1.0e4, -1.1e4, 8.0e3])
        for face in faces:
            face["points"] = (np.asarray(face["points"], float) + offset).tolist()
    return faces, tol


@pytest.mark.parametrize("seed", range(40))
def test_equivalence_with_reference_on_seeded_corpus(seed):
    faces, tol = _corpus(seed)
    assert near_parallel_overlaps(faces, tol) == _reference_near_parallel_overlaps(faces, tol)


def test_seeded_corpus_is_not_vacuous():
    total, directions = 0, set()
    for seed in range(40):
        faces, tol = _corpus(seed)
        for pair in near_parallel_overlaps(faces, tol):
            total += 1
            directions.add(pair["same_direction"])
    assert total >= 50 and directions == {True, False}


def test_equivalence_on_scaled_box_and_bipyramid():
    for verts, tris in (_box(6), _bipyramid(400)):
        faces = _mesh_faces(verts, tris)
        assert near_parallel_overlaps(faces, 0.003) == _reference_near_parallel_overlaps(faces, 0.003)
    verts, tris = _box(6)
    shifted = verts + np.array([0.0, 0.0, 0.004])
    both = _mesh_faces(verts, tris) + _mesh_faces(shifted, tris, len(tris))
    assert near_parallel_overlaps(both, 0.003) == _reference_near_parallel_overlaps(both, 0.003)


def test_50k_box_is_subquadratic():
    verts, tris = _box(65)
    faces = _mesh_faces(verts, tris)
    assert len(faces) == 12 * 65 * 65
    started = time.perf_counter()
    result = near_parallel_overlaps(faces, 0.003)
    elapsed = time.perf_counter() - started
    print(elapsed)
    assert result == [] and elapsed < 30.0


def test_edge_cases_match_reference():
    quad = [{"object": "a", "index": 0, "points": [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]}]
    degenerate = [
        {"object": "d", "index": 0, "points": [[0, 0, 0], [1, 0, 0], [2, 0, 0]]},
        {"object": "d", "index": 1, "points": [[1, 1, 1], [1, 1, 1], [1, 1, 1]]},
        {"object": "d", "index": 2, "points": [[0, 0, 0], [0, 1, 0], [0, 2, 0]]},
    ]
    touching = [
        {"object": "a", "index": 0, "points": [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]},
        {"object": "b", "index": 0, "points": [[0.2, 0.2, 0], [1.2, 0.2, 0], [1.2, 1.2, 0], [0.2, 1.2, 0]]},
    ]
    nan_faces = [
        {"object": "a", "index": 0, "points": [[0, 0, 0], [1, 0, 0], [1, 1, np.nan], [0, 1, 0]]},
        {"object": "b", "index": 0, "points": [[0, 0, 0.001], [1, 0, 0.001], [1, 1, 0.001], [0, 1, 0.001]]},
        {"object": "c", "index": 0, "points": [[0, 0, np.nan], [1, 0, 0], [0, 1, 0]]},
    ]
    small, _ = _corpus(0)
    cases = [
        ([], 0.005),
        (quad, 0.005),
        (degenerate, 0.005),
        (touching, 0.0),
        (small, float("inf")),
        (nan_faces, 0.005),
    ]
    for faces, tol in cases:
        assert near_parallel_overlaps(faces, tol) == _reference_near_parallel_overlaps(faces, tol)


def test_vectorized_setup_matches_per_face_setup():
    from twinqa.clearance import _face_arrays

    rng = np.random.default_rng(202)
    pts = []
    for _ in range(6):
        for vertices in (3, 4, 5, 8):
            pts.append(rng.normal(size=(vertices, 3)))
    nan_face = rng.normal(size=(4, 3))
    nan_face[1, 2] = np.nan
    pts.append(nan_face)
    pts.append(np.full((6, 3), 2.5))
    pts.append(np.column_stack((np.linspace(0.0, 5.0, 4), np.zeros(4), np.zeros(4))))
    normals, centers, lows, highs, first = _face_arrays(pts)
    assert np.array_equal(normals, np.array([_normal(p) for p in pts]), equal_nan=True)
    assert np.array_equal(centers, np.array([p.mean(0) for p in pts]), equal_nan=True)
    assert np.array_equal(lows, np.array([p.min(0) for p in pts]), equal_nan=True)
    assert np.array_equal(highs, np.array([p.max(0) for p in pts]), equal_nan=True)
    assert np.array_equal(first, np.array([p[0] for p in pts]), equal_nan=True)


def _faces_at_separation(xy, separation, shift=0.0):
    return [{"object": "synthetic", "index": i,
             "points": [[x + shift, y, z] for x, y in xy]}
            for i, z in enumerate((0.0, separation))]


_BOWTIE = [(0, 0), (2, 2), (0, 2), (1, 0)]
_SQUARE = [(0, 0), (2, 0), (2, 2), (0, 2)]
_SEPARATIONS = [0.001, 0.0029998, 0.003, 0.003005, 0.00302]


@pytest.mark.parametrize("separation", [0.001, 0.0029998, 0.003, 0.003005])
def test_invalid_polygon_raises_like_reference(separation):
    faces = _faces_at_separation(_BOWTIE, separation)
    with pytest.raises(shapely.errors.GEOSException):
        near_parallel_overlaps(faces, 0.003)
    with pytest.raises(shapely.errors.GEOSException):
        _reference_near_parallel_overlaps(faces, 0.003)


def test_invalid_polygon_outside_window_matches_reference():
    faces = _faces_at_separation(_BOWTIE, 0.00302)
    got = near_parallel_overlaps(faces, 0.003)
    ref = _reference_near_parallel_overlaps(faces, 0.003)
    assert got == [] and got == ref


@pytest.mark.parametrize("separation", _SEPARATIONS)
def test_valid_square_matches_reference_at_boundaries(separation):
    faces = _faces_at_separation(_SQUARE, separation)
    got = near_parallel_overlaps(faces, 0.003)
    assert got == _reference_near_parallel_overlaps(faces, 0.003)
    if separation == 0.001:
        assert got


def test_invalid_polygon_in_large_mesh_raises():
    faces = _mesh_faces(*_box(6))
    faces.extend(_faces_at_separation(_BOWTIE, 0.003005, shift=100.0))
    with pytest.raises(shapely.errors.GEOSException):
        near_parallel_overlaps(faces, 0.003)
    with pytest.raises(shapely.errors.GEOSException):
        _reference_near_parallel_overlaps(faces, 0.003)
