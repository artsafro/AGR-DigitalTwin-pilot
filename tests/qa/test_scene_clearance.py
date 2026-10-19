"""V004 co-directional overlap clearance on FBX face geometry (BODY-K, reg p.8 / p.29)."""
import math
import subprocess
import time

import numpy as np
import pytest
from shapely.geometry import Polygon

from test_validator import PROFILES
from twinqa.clearance import (
    AREA_MIN_M2,
    PARALLEL_COS_MIN,
    _normal,
    co_directional_distribution,
    co_directional_pairs,
)
from twinqa.scene import find_blender, readback, scene_findings

from test_scene import mesh, rb, statuses


def y_quad(y, x0=0.0, z0=0.0, size=1.0, reverse=False):
    points = [[x0, y, z0], [x0, y, z0 + size], [x0 + size, y, z0 + size], [x0 + size, y, z0]]
    if reverse:
        points.reverse()
    return points


def faced(name, quads):
    vertices, polygons = [], []
    for quad in quads:
        polygons.append(list(range(len(vertices), len(vertices) + len(quad))))
        vertices.extend(quad)
    item = mesh(name=name, tris=len(quads) * 2, degrees={"4": len(quads)})
    item["face_geometry"] = {"vertices": vertices, "polygons": polygons}
    return item


def clearance(found):
    return next(item for item in found["V004"] if item.name == "co-directional clearance")


def scene(*meshes, kind="vpm", role="oks", profile=None):
    chosen = profile if profile is not None else (PROFILES.npm if kind == "npm" else PROFILES.vpm)
    return scene_findings(rb(*meshes), kind, role, chosen)


def test_overlapping_quads_2mm_apart_fail_below_band():
    found = scene(faced("SM_Test_K_1_Main", [y_quad(0.0), y_quad(0.002)]))
    item = clearance(found)
    assert item.status == "fail"
    assert "1 < 5 mm" in item.observed
    assert item.source_pdf_pages == [8, 29]
    assert item.conflicts == [30]
    assert item.expected == ("co-directional overlapping faces 5-20 mm apart "
                             "(pairs beyond 20 mm: review)")


def test_coplanar_overlapping_quads_fail():
    found = scene(faced("SM_Test_K_1_Main", [y_quad(0.0), y_quad(0.0)]))
    assert clearance(found).status == "fail"


def test_quads_inside_band_pass():
    for gap in (0.010, 0.005, 0.020):
        found = scene(faced("SM_Test_K_1_Main", [y_quad(0.0), y_quad(gap)]))
        item = clearance(found)
        assert item.status == "pass", gap
        assert "1 in band" in item.observed


def _face_records(quads):
    return [{"object": "SM_Test_K_1_Main", "index": index, "points": quad} for index, quad in enumerate(quads)]


def test_quads_above_band_are_review_at_any_distance():
    band = PROFILES.vpm["geometry"]["near_coplanar_spacing_m"]
    assert clearance(scene(faced("SM_Test_K_1_Main", [y_quad(0.0), y_quad(0.030)]))).status == "review"
    item = clearance(scene(faced("SM_Test_K_1_Main", [y_quad(0.0), y_quad(0.150)])))
    assert item.status == "review"
    assert "1 > 20 mm" in item.observed
    distribution = co_directional_distribution(
        co_directional_pairs(_face_records([y_quad(0.0), y_quad(0.150)])), band["min"], band["max"])
    assert distribution["max_mm"] == 150
    assert distribution["histogram_mm"]["100-1000"] == 1
    assert clearance(scene(faced("SM_Test_K_1_Main", [y_quad(0.0), y_quad(3.0)]))).status == "review"
    far = co_directional_distribution(
        co_directional_pairs(_face_records([y_quad(0.0), y_quad(3.0)])), band["min"], band["max"])
    assert far["histogram_mm"]["1000+"] == 1


def test_tilted_narrow_strip_2mm_pair_is_found():
    normal = np.array([0.0009, 0.0, 1.0])
    normal /= np.linalg.norm(normal)
    along = np.array([normal[2], 0.0, -normal[0]])
    across = np.array([0.0, 1.0, 0.0])
    corners = np.stack([np.zeros(3), along, along + across, across])
    shifted = corners + 0.999999 * along + 0.002 * normal
    pairs = co_directional_pairs(_face_records([corners.tolist(), shifted.tolist()]))
    assert len(pairs) == 1
    assert pairs[0]["distance_m"] == pytest.approx(0.002, abs=1e-9)
    assert pairs[0]["projected_area_m2"] > 1e-7
    assert clearance(scene(faced("SM_Test_K_1_Main", [corners.tolist(), shifted.tolist()]))).status == "fail"


def test_combined_controls_one_scene():
    quads = [
        y_quad(0.0, x0=0.0),
        y_quad(0.002, x0=0.0),
        y_quad(0.0, x0=5.0),
        y_quad(0.010, x0=5.0),
        y_quad(0.0, x0=10.0),
        y_quad(0.150, x0=10.0),
        y_quad(0.0, x0=20.0),
        y_quad(0.002, x0=21.0),
        y_quad(0.0, x0=30.0),
        y_quad(0.003, x0=30.0, reverse=True),
    ]
    item = clearance(scene(faced("SM_Test_K_1_Main", quads)))
    assert item.status == "fail"
    assert "3 co-directional overlapping pairs: 1 < 5 mm, 1 in band, 1 > 20 mm" in item.observed


def test_opposite_facing_quads_are_not_co_directional():
    found = scene(faced("SM_Test_K_1_Main", [y_quad(0.0), y_quad(0.002, reverse=True)]))
    assert clearance(found).status == "pass"


def test_side_by_side_touching_quads_pass():
    found = scene(faced("SM_Test_K_1_Main", [y_quad(0.0), y_quad(0.002, x0=1.0)]))
    assert clearance(found).status == "pass"


def test_ucx_overlay_is_excluded():
    found = scene(faced("SM_Test_K_1_Main", [y_quad(0.0)]),
                  faced("UCX_SM_Test_K_1_Main_001", [y_quad(0.002)]))
    assert clearance(found).status == "pass"


def test_pairs_across_meshes_are_detected():
    found = scene(faced("SM_Test_K_1_Main", [y_quad(0.0)]),
                  faced("SM_Test_K_1_MainGlass", [y_quad(0.002)]))
    item = clearance(found)
    assert item.status == "fail"
    assert "SM_Test_K_1_Main#0/SM_Test_K_1_MainGlass#0" in item.observed


def test_missing_face_geometry_is_not_run():
    item = clearance(scene(mesh()))
    assert item.status == "not_run"
    assert item.observed.endswith(": no face geometry in readback")


def test_light_role_skips_co_directional_clearance():
    found = scene(faced("SM_Test_K_1_Main", [y_quad(0.0), y_quad(0.002)]), role="light")
    assert "co-directional clearance" not in statuses(found, "V004")


def test_npm_profile_fails_below_band():
    found = scene(faced("SM_Test_K_1_Main", [y_quad(0.0), y_quad(0.002)]), kind="npm")
    assert clearance(found).status == "fail"
    assert "1 < 5 mm" in clearance(found).observed


def test_co_directional_distribution_histogram():
    band = PROFILES.vpm["geometry"]["near_coplanar_spacing_m"]
    pairs = [{"a": ["A", 0], "b": ["B", 1], "distance_m": gap, "projected_area_m2": 1.0}
             for gap in (0.002, 0.010, 0.030)]
    distribution = co_directional_distribution(pairs, band["min"], band["max"])
    assert distribution["pairs"] == 3
    assert (distribution["below_band"], distribution["in_band"], distribution["above_band"]) == (1, 1, 1)
    assert distribution["histogram_mm"] == {
        "0-1": 0, "1-5": 1, "5-10": 0, "10-20": 1, "20-50": 1, "50-100": 0, "100-1000": 0, "1000+": 0}
    assert distribution["min_mm"] == pytest.approx(2)
    assert distribution["median_mm"] == pytest.approx(10)
    assert distribution["max_mm"] == pytest.approx(30)
    empty = co_directional_distribution([], band["min"], band["max"])
    assert empty["pairs"] == 0
    assert empty["min_mm"] is None and empty["median_mm"] is None and empty["max_mm"] is None


def test_band_edges_tolerate_fbx_float_noise():
    band = PROFILES.vpm["geometry"]["near_coplanar_spacing_m"]
    pairs = [{"a": ["A", 0], "b": ["B", k], "distance_m": gap, "projected_area_m2": 1.0}
             for k, gap in enumerate((0.00498, 0.0049999, 0.0200013, 0.020011))]
    distribution = co_directional_distribution(pairs, band["min"], band["max"])
    assert (distribution["below_band"], distribution["in_band"], distribution["above_band"]) == (1, 2, 1)
    assert distribution["histogram_mm"] == {
        "0-1": 0, "1-5": 1, "5-10": 1, "10-20": 1, "20-50": 1, "50-100": 0, "100-1000": 0, "1000+": 0}


def test_worst_lists_below_band_first_then_largest_deviation():
    found = scene(faced("SM_Test_K_1_Main", [y_quad(0.0), y_quad(0.09), y_quad(0.020005, x0=5.0),
                                             y_quad(0.0, x0=5.0), y_quad(0.003, x0=10.0), y_quad(0.0, x0=10.0)]))
    item = clearance(found)
    assert item.status == "fail"
    worst = item.observed.split("worst: ")[1]
    assert worst.index("d=3.0 mm") < worst.index("d=90.0 mm")
    assert "d=20.0 mm" not in worst  # 20.005 mm is inside the band edge tolerance


def _basis(normal):
    axis = int(np.argmin(np.abs(normal)))
    tangent = np.cross(normal, np.eye(3)[axis])
    tangent /= np.linalg.norm(tangent)
    bitangent = np.cross(normal, tangent)
    return tangent, bitangent


def _reference_pairs(faces, window_m=None):
    """Straightforward O(n^2) co-directional overlap, same definitions as the checker.

    `window_m=None` is unlimited: no distance filter.
    """
    prepared = []
    for face in faces:
        points = np.asarray(face["points"], dtype=float)
        normal = _normal(points) if len(points) >= 3 else np.zeros(3)
        if np.linalg.norm(normal) < 0.9:
            prepared.append(None)
            continue
        prepared.append((face, points, normal, points.mean(0)))
    found = []
    for i, left in enumerate(prepared):
        if left is None:
            continue
        _, points_i, normal_i, centroid_i = left
        tangent, bitangent = _basis(normal_i)
        polygon_i = Polygon(np.column_stack((points_i @ tangent, points_i @ bitangent)))
        for j in range(i + 1, len(prepared)):
            right = prepared[j]
            if right is None:
                continue
            face_j, points_j, normal_j, centroid_j = right
            if float(np.dot(normal_i, normal_j)) <= PARALLEL_COS_MIN:
                continue
            distance = abs(float(np.dot(normal_i, centroid_j - centroid_i)))
            if window_m is not None and distance > window_m + 1e-9:
                continue
            polygon_j = Polygon(np.column_stack((points_j @ tangent, points_j @ bitangent)))
            area = float(polygon_i.intersection(polygon_j).area)
            if area < AREA_MIN_M2:
                continue
            found.append({"a": [left[0]["object"], int(left[0]["index"])],
                          "b": [face_j["object"], int(face_j["index"])],
                          "distance_m": distance, "projected_area_m2": area})
    found.sort(key=lambda pair: (pair["distance_m"], pair["a"], pair["b"]))
    return found


def _random_faces(seed):
    rng = np.random.default_rng(seed)
    count = int(rng.integers(20, 41))
    axes = [np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.0, 1.0])]
    faces = []
    for index in range(count):
        kind = int(rng.integers(0, 5))
        axis = axes[int(rng.integers(0, 3))]
        if kind == 0:
            normal = axis.copy()
        elif kind == 1:
            tilt = rng.normal(size=3)
            tilt -= axis * np.dot(tilt, axis)
            length = np.linalg.norm(tilt)
            angle = float(rng.uniform(0.0, 0.0008))
            if length < 1e-9:
                normal = axis.copy()
            else:
                normal = axis * math.cos(angle) + tilt / length * math.sin(angle)
        elif kind == 2:
            normal = -axis
        else:
            normal = rng.normal(size=3)
        normal = normal / np.linalg.norm(normal)
        tangent, bitangent = _basis(normal)
        center = rng.uniform(-0.4, 0.4, size=2)
        origin = float(rng.uniform(0.0, 0.15)) * normal + center[0] * tangent + center[1] * bitangent
        size = float(rng.uniform(0.15, 0.55))
        if rng.random() < 0.5:
            corners = np.array([[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]]) * size
        else:
            corners = np.array([[-0.5, -0.4], [0.5, -0.2], [0.0, 0.5]]) * size
        if rng.random() < 0.3:
            corners = corners[::-1]
        points = [origin + u * tangent + v * bitangent for u, v in corners]
        faces.append({"object": f"M{int(rng.integers(0, 3))}", "index": index,
                      "points": [point.tolist() for point in points]})
    return faces


@pytest.mark.parametrize("window_m", [0.1, None])
@pytest.mark.parametrize("seed", range(30))
def test_co_directional_pairs_match_reference(seed, window_m):
    faces = _random_faces(seed)
    got = co_directional_pairs(faces, window_m)
    expected = _reference_pairs(faces, window_m)
    assert [(pair["a"], pair["b"]) for pair in got] == [(pair["a"], pair["b"]) for pair in expected]
    assert [pair["distance_m"] for pair in got] == pytest.approx(
        [pair["distance_m"] for pair in expected], abs=1e-9)


def _tilt_normal(normal, rng, max_angle):
    angle = float(rng.uniform(0.0, max_angle))
    direction = rng.normal(size=3)
    direction -= normal * np.dot(direction, normal)
    length = np.linalg.norm(direction)
    if angle == 0.0 or length < 1e-12:
        return normal.copy()
    direction /= length
    return normal * math.cos(angle) + direction * math.sin(angle)


def _noisy_plane_faces(seed):
    """150-300 faces on a few shared planes, with noisy normals and a handful of large tilts."""
    rng = np.random.default_rng(seed)
    count = int(rng.integers(150, 301))
    bases = []
    for _ in range(int(rng.integers(3, 5))):
        base = rng.normal(size=3)
        bases.append(base / np.linalg.norm(base))
    n_large = int(rng.integers(3, 7))
    faces = []
    for index in range(count):
        base = bases[int(rng.integers(0, len(bases)))]
        large = index < n_large
        normal = _tilt_normal(base, rng, 8e-4 if large else 5e-4)
        base_u, base_v = _basis(base)
        face_u, face_v = _basis(normal)
        center = rng.uniform(-0.3, 0.3, size=2) if large else rng.uniform(-1.5, 1.5, size=2)
        size = float(rng.uniform(2.0, 5.0) if large else rng.uniform(0.05, 0.4))
        origin = float(rng.uniform(0.0, 0.15)) * base + center[0] * base_u + center[1] * base_v
        if (not large) and rng.random() < 0.5:
            corners = np.array([[-0.5, -0.4], [0.5, -0.2], [0.0, 0.5]]) * size
        else:
            corners = np.array([[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]]) * size
        points = np.array([origin + u * face_u + v * face_v for u, v in corners])
        if rng.random() < 0.25:
            points = points[::-1]
        points += rng.uniform(-1e-6, 1e-6, size=points.shape)
        faces.append({"object": f"M{int(rng.integers(0, 3))}", "index": index,
                      "points": [point.tolist() for point in points]})
    return faces


def _assert_pairs_match(got, expected):
    assert [(pair["a"], pair["b"]) for pair in got] == [(pair["a"], pair["b"]) for pair in expected]
    assert [pair["distance_m"] for pair in got] == pytest.approx(
        [pair["distance_m"] for pair in expected], abs=1e-9)


@pytest.mark.parametrize("window_m", [0.1, None])
@pytest.mark.parametrize("seed", range(20))
def test_co_directional_pairs_match_reference_on_noisy_planes(seed, window_m):
    faces = _noisy_plane_faces(seed)
    assert 150 <= len(faces) <= 300
    got = co_directional_pairs(faces, window_m)
    expected = _reference_pairs(faces, window_m)
    _assert_pairs_match(got, expected)


def _two_layer_grid():
    nx, ny, cell = 100, 125, 0.2
    faces = []
    index = 0
    for layer, z in enumerate((0.0, 0.01)):
        name = "SM_Test_K_1_Main" if layer == 0 else "SM_Test_K_1_MainDecor"
        for i in range(nx):
            for j in range(ny):
                x, y = i * cell, j * cell
                p00, p10 = [x, y, z], [x + cell, y, z]
                p11, p01 = [x + cell, y + cell, z], [x, y + cell, z]
                faces.append({"object": name, "index": index, "points": [p00, p10, p11]})
                index += 1
                faces.append({"object": name, "index": index, "points": [p00, p11, p01]})
                index += 1
    return faces


def test_two_layer_grid_scales_to_fifty_thousand_triangles():
    faces = _two_layer_grid()
    assert len(faces) == 50_000
    started = time.perf_counter()
    pairs = co_directional_pairs(faces)
    elapsed = time.perf_counter() - started
    assert elapsed < 60  # catches O(n^2); measured 7-14 s on an idle machine
    assert len(pairs) == 25_000
    assert max(abs(pair["distance_m"] - 0.01) for pair in pairs) < 1e-9


def _welded_grid(z, nx, ny, cell, jitter, index_start, name):
    """One horizontal grid. `jitter` is (ny+1, nx+1, 3) added to each welded vertex."""
    faces = []
    index = index_start
    for i in range(nx):
        for j in range(ny):
            p00 = [i * cell + jitter[j, i, 0], j * cell + jitter[j, i, 1], z + jitter[j, i, 2]]
            p10 = [(i + 1) * cell + jitter[j, i + 1, 0], j * cell + jitter[j, i + 1, 1],
                   z + jitter[j, i + 1, 2]]
            p11 = [(i + 1) * cell + jitter[j + 1, i + 1, 0], (j + 1) * cell + jitter[j + 1, i + 1, 1],
                   z + jitter[j + 1, i + 1, 2]]
            p01 = [i * cell + jitter[j + 1, i, 0], (j + 1) * cell + jitter[j + 1, i, 1],
                   z + jitter[j + 1, i, 2]]
            faces.append({"object": name, "index": index, "points": [p00, p10, p11]})
            index += 1
            faces.append({"object": name, "index": index, "points": [p00, p11, p01]})
            index += 1
    return faces, index


def _jittered_two_layer_grid(seed):
    """Both layers share one welded jitter, so the 10 mm pairs stay the only overlaps."""
    rng = np.random.default_rng(seed)
    nx, ny, cell = 100, 125, 0.2
    jitter = rng.uniform(-1e-6, 1e-6, size=(ny + 1, nx + 1, 3))
    faces = []
    index = 0
    for layer, z in enumerate((0.0, 0.01)):
        name = "SM_Test_K_1_Main" if layer == 0 else "SM_Test_K_1_MainDecor"
        chunk, index = _welded_grid(z, nx, ny, cell, jitter, index, name)
        faces.extend(chunk)
    return faces


def test_jittered_two_layer_grid_scales_to_fifty_thousand_triangles():
    faces = _jittered_two_layer_grid(161)
    assert len(faces) == 50_000
    started = time.perf_counter()
    pairs = co_directional_pairs(faces)
    elapsed = time.perf_counter() - started
    assert elapsed < 60, elapsed  # catches O(n^2); measured 7-14 s idle
    assert len(pairs) == 25_000
    assert max(abs(pair["distance_m"] - 0.01) for pair in pairs) < 1e-5


def _flat_grid(z, index_start, name, nx=50, ny=25, cell=0.2):
    faces = []
    index = index_start
    for i in range(nx):
        for j in range(ny):
            x, y = i * cell, j * cell
            p00, p10 = [x, y, z], [x + cell, y, z]
            p11, p01 = [x + cell, y + cell, z], [x, y + cell, z]
            faces.append({"object": name, "index": index, "points": [p00, p10, p11]})
            index += 1
            faces.append({"object": name, "index": index, "points": [p00, p11, p01]})
            index += 1
    return faces, index


def test_stacked_layers_report_every_pair():
    faces = []
    index = 0
    for layer in range(10):  # 11 identical footprints per column: every pair is reported, no cutoff
        chunk, index = _flat_grid(layer * 3.0, index, f"SM_Test_K_1_L{layer}")
        faces.extend(chunk)
    chunk, index = _flat_grid(0.002, index, "SM_Test_K_1_Near")
    faces.extend(chunk)
    assert len(faces) == 11 * 2_500
    started = time.perf_counter()
    pairs = co_directional_pairs(faces)
    elapsed = time.perf_counter() - started
    assert elapsed < 90, elapsed  # 525k pairs at 21 layers measured 97-102 s; 10 layers keeps headroom
    assert len(pairs) == 2_500 * 55
    band = PROFILES.vpm["geometry"]["near_coplanar_spacing_m"]
    distribution = co_directional_distribution(pairs, band["min"], band["max"])
    assert distribution["below_band"] == 2_500
    assert sum(abs(pair["distance_m"] - 0.002) < 1e-9 for pair in pairs) == 2_500


def test_large_tilted_quads_match_reference():
    half = 20.0
    base = [[-half, -half, 0.0], [half, -half, 0.0], [half, half, 0.0], [-half, half, 0.0]]
    angle = 1e-3
    cosine, sine = math.cos(angle), math.sin(angle)
    tilted = []
    for x, y, _z in base:
        y0, z0 = y, 0.0
        tilted.append([x, y0 * cosine - z0 * sine, y0 * sine + z0 * cosine + 0.008])
    faces = [{"object": "A", "index": 0, "points": base},
             {"object": "B", "index": 1, "points": tilted}]
    got = co_directional_pairs(faces, 0.1)
    expected = _reference_pairs(faces, 0.1)
    assert len(got) == 1
    _assert_pairs_match(got, expected)
    assert got[0]["distance_m"] == pytest.approx(0.008, abs=1e-6)


def _proper_rotation(rng):
    orthogonal, _triangular = np.linalg.qr(rng.normal(size=(3, 3)))
    if np.linalg.det(orthogonal) < 0:
        orthogonal[:, 0] *= -1
    return orthogonal


def _boundary_normal(rng):
    axis = int(rng.integers(0, 3))
    normal = np.zeros(3)
    normal[axis] = 1.0 if rng.random() < 0.5 else -1.0
    for component in range(3):
        if component == axis:
            continue
        odd = float(rng.choice((-3, -1, 1, 3))) * 0.001
        normal[component] = odd + float(rng.uniform(-5e-6, 5e-6))
    normal /= np.linalg.norm(normal)
    return _tilt_normal(normal, rng, math.nextafter(0.0007, 0.0))


def _strip_corners(triangle, width):
    edge = 1.0
    if triangle:
        corners = np.array([[0.0, 0.0], [edge, 0.0], [0.0, edge]])
    else:
        corners = np.array([[0.0, 0.0], [edge, 0.0], [edge, edge], [0.0, edge]])
    moved = corners + np.array([edge - width, 0.0])
    area = float(Polygon(corners).intersection(Polygon(moved)).area)
    return corners, moved, area


def _near_edge_faces(seed):
    """Narrow in-plane overlaps on normals near a quantised-cell boundary, then a rigid move."""
    rng = np.random.default_rng(seed)
    faces = []
    index = 0
    for pair in range(int(rng.integers(5, 16))):
        normal = _boundary_normal(rng)
        tangent, bitangent = _basis(normal)
        triangle = pair > 0 and rng.random() < 0.5
        corners = moved = None
        area = 0.0
        for _attempt in range(40):
            width = float(rng.uniform(1e-6, 1e-2))
            corners, moved, area = _strip_corners(triangle, width)
            if not (5e-8 < area < 2e-7):
                break
        if 5e-8 < area < 2e-7:
            corners, moved, area = _strip_corners(False, 1e-3)
        offset = float(rng.uniform(0.2, 30.0) if rng.random() < 0.25 else rng.uniform(0.0, 0.2))
        origin = np.array([pair * 25.0, (pair % 4) * 25.0, (pair % 3) * 25.0])

        def embed(uv, shift):
            return origin + shift + uv[:, 0:1] * tangent + uv[:, 1:2] * bitangent

        for points in (embed(corners, np.zeros(3)), embed(moved, offset * normal)):
            faces.append({"object": "M0", "index": index, "points": [point.tolist() for point in points]})
            index += 1
    rotation = _proper_rotation(rng)
    translation = rng.uniform(-1000.0, 1000.0, size=3)
    for face in faces:
        points = np.asarray(face["points"], dtype=float) @ rotation.T + translation
        face["points"] = [point.tolist() for point in points]
    return faces


@pytest.mark.parametrize("seed", range(40))
def test_rotated_translated_near_edge_pairs_match_reference(seed):
    faces = _near_edge_faces(seed)
    assert 10 <= len(faces) <= 30
    got = co_directional_pairs(faces)
    expected = _reference_pairs(faces)
    assert len(got) >= 1
    assert [(pair["a"], pair["b"]) for pair in got] == [(pair["a"], pair["b"]) for pair in expected]
    assert [pair["distance_m"] for pair in got] == pytest.approx(
        [pair["distance_m"] for pair in expected], rel=1e-9, abs=1e-6)


BLENDER = find_blender()
CUBE_LAYERS = r"""
import bpy, sys
out, variant = sys.argv[sys.argv.index('--') + 1], sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)

def triangulate(obj):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.modifier_add(type='TRIANGULATE')
    bpy.ops.object.modifier_apply(modifier='Triangulate')
    obj.select_set(False)

def world_normal(obj, poly):
    return (obj.matrix_world.to_3x3() @ poly.normal).normalized()

def world_center(obj, poly):
    total = None
    for vertex in poly.vertices:
        point = obj.matrix_world @ obj.data.vertices[vertex].co
        total = point if total is None else total + point
    return total / len(poly.vertices)

bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))
cube = bpy.context.object
cube.name = 'SM_Test_K_1_Main'
triangulate(cube)
if variant == 'red':
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 2.002))
    plane = bpy.context.object
    plane.name = 'SM_Test_K_1_MainDecor'
    triangulate(plane)
    top = max(cube.data.polygons, key=lambda poly: world_center(cube, poly).z)
    if world_normal(cube, top).dot(world_normal(plane, plane.data.polygons[0])) <= 0:
        bpy.context.view_layer.objects.active = plane
        plane.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.flip_normals()
        bpy.ops.object.mode_set(mode='OBJECT')
        plane.select_set(False)
    aligned = world_normal(cube, top).dot(world_normal(plane, plane.data.polygons[0]))
    if aligned <= 0.5:
        raise RuntimeError('plane normal does not match the cube face: %s' % aligned)
bpy.ops.export_scene.fbx(filepath=out)
"""


@pytest.mark.blender
@pytest.mark.skipif(BLENDER is None, reason="Blender not installed")
@pytest.mark.parametrize("variant", ["green", "red"])
def test_blender_cube_clearance_roundtrip(tmp_path, variant):
    fbx = tmp_path / f"cube_{variant}.fbx"
    subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                    "--python-expr", CUBE_LAYERS, "--", str(fbx), variant],
                   check=True, capture_output=True, timeout=300)
    report = readback(fbx)
    assert report["readback_ok"]
    assert all("face_geometry" in mesh for mesh in report["meshes"])
    found = scene_findings(report, "vpm", "oks", PROFILES.vpm)
    assert clearance(found).status == ("pass" if variant == "green" else "fail")
