"""new-case: literal square-metre oracles for tri_areas and poly_areas.

Acceptance table. Areas are hand square metres. tri_areas is not the oracle
for poly_areas, and poly_areas is not the oracle for tri_areas. Axis-aligned
witnesses match exactly. The oblique rigid motion uses abs 1e-9 + rel 1e-9.

1. right triangle (0,0,0), (3,0,0), (0,4,0)
   -> tri_areas [6.0], poly_areas [6.0]

2. 3-by-4 rectangle (0,0,0), (3,0,0), (3,4,0), (0,4,0)
   with explicit diagonal split [0,1,2], [0,2,3]
   -> tri_areas [6.0, 6.0]; source polygon [0,1,2,3] poly_areas [12.0]

3. planar concave L ring (0,0), (3,0), (3,1), (1,1), (1,3), (0,3)
   -> poly_areas [5.0] (3+3-1)

For each shape: reverse winding and every cyclic shift of each face keep the
same nonnegative area; the same coordinates embedded in the XY, XZ and YZ
planes keep the same values; the fixed proper oblique rotation below plus
translation (1, -2, 3) keeps those areas within the tolerance above; scaling
every coordinate by 2 multiplies areas by 4 (equal to 4*literal, and not
equal to 2*literal). Result order follows face order, result length equals
the face count, and the vertex and face inputs are unchanged.
"""
import copy
import itertools
import sys
from pathlib import Path

import numpy as np

_SCRIPTS = Path(__file__).resolve().parents[2] / "jobs" / "TEC26-OKS" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import qa_packages  # noqa: E402

# Rodrigues formula, stored as independent literals: cos = 3/5, sin = 4/5,
# unit axis (1, 2, 2)/3. Numerators over 45. det = +1 exactly in rationals.
_R_NUM = (
    (29, -20, 28),
    (28, 35, -4),
    (-20, 20, 35),
)
_R_DEN = 45
_TRANSLATION = (1.0, -2.0, 3.0)
_ABS_TOL = 1e-9
_REL_TOL = 1e-9

_SHAPES = (
    {
        "name": "right_triangle",
        "points": [[0.0, 0.0, 0.0], [3.0, 0.0, 0.0], [0.0, 4.0, 0.0]],
        "tri_faces": [[0, 1, 2]],
        "tri_expected": [6.0],
        "poly_faces": [[0, 1, 2]],
        "poly_expected": [6.0],
    },
    {
        "name": "rectangle",
        "points": [[0.0, 0.0, 0.0], [3.0, 0.0, 0.0], [3.0, 4.0, 0.0], [0.0, 4.0, 0.0]],
        "tri_faces": [[0, 1, 2], [0, 2, 3]],
        "tri_expected": [6.0, 6.0],
        "poly_faces": [[0, 1, 2, 3]],
        "poly_expected": [12.0],
    },
    {
        "name": "concave_l",
        "points": [
            [0.0, 0.0, 0.0],
            [3.0, 0.0, 0.0],
            [3.0, 1.0, 0.0],
            [1.0, 1.0, 0.0],
            [1.0, 3.0, 0.0],
            [0.0, 3.0, 0.0],
        ],
        "tri_faces": None,
        "tri_expected": None,
        "poly_faces": [[0, 1, 2, 3, 4, 5]],
        "poly_expected": [5.0],  # 3+3-1
    },
)


def _rotation_matrix():
    """Literal proper rotation. det == 1 and R @ R.T == I within 1e-12."""
    matrix = np.asarray(_R_NUM, dtype=float) / float(_R_DEN)
    det = float(np.linalg.det(matrix))
    assert abs(det - 1.0) <= 1e-12
    gram = matrix @ matrix.T
    assert float(np.max(np.abs(gram - np.eye(3)))) <= 1e-12
    return matrix


def _within(got, expected):
    return abs(float(got) - float(expected)) <= _ABS_TOL + _REL_TOL * abs(float(expected))


def _invoke(fn, verts, faces):
    """Call fn and report whether the objects passed in are unchanged."""
    passed_v = copy.deepcopy(verts)
    passed_f = copy.deepcopy(faces)
    snap_v = copy.deepcopy(passed_v)
    snap_f = copy.deepcopy(passed_f)
    result = list(fn(passed_v, passed_f))
    intact = passed_v == snap_v and passed_f == snap_f
    return result, intact


def _record(failures, tag, result, intact, expected, tol):
    if not intact:
        failures.append(f"{tag}:inputs")
    if len(result) != len(expected):
        failures.append(f"{tag}:length:{len(result)}!={len(expected)}")
        return
    if any(area < 0 for area in result):
        failures.append(f"{tag}:sign:{result}")
    for index, (got, exp) in enumerate(zip(result, expected)):
        ok = _within(got, exp) if tol else got == exp
        if not ok:
            failures.append(f"{tag}:face{index}:{got}!={exp}")


def _check(failures, tag, fn, verts, faces, expected, tol=False):
    result, intact = _invoke(fn, verts, faces)
    _record(failures, tag, result, intact, expected, tol)


def _reembed(points, plane):
    """Place the XY coordinates of a shape into XY, XZ or YZ."""
    out = []
    for x, y, _z in points:
        if plane == "xy":
            out.append([x, y, 0.0])
        elif plane == "xz":
            out.append([x, 0.0, y])
        elif plane == "yz":
            out.append([0.0, x, y])
        else:
            raise AssertionError(plane)
    return out


def _rotate(points):
    matrix = _rotation_matrix()
    shift = np.asarray(_TRANSLATION, dtype=float)
    out = []
    for point in points:
        moved = matrix @ np.asarray(point, dtype=float) + shift
        out.append([float(moved[0]), float(moved[1]), float(moved[2])])
    return out


def _scale(points, factor=2.0):
    return [[coord * factor for coord in point] for point in points]


def _windings(face):
    """Forward and reversed cyclic shifts, every start vertex."""
    variants = []
    forward = list(face)
    backward = list(reversed(face))
    for base in (forward, backward):
        count = len(base)
        for start in range(count):
            variants.append(base[start:] + base[:start])
    return variants


def _face_variants(faces):
    return list(itertools.product(*(_windings(face) for face in faces)))


def _channels(shape):
    if shape["tri_faces"] is not None:
        yield "tri", shape["tri_faces"], shape["tri_expected"]
    yield "poly", shape["poly_faces"], shape["poly_expected"]


def _check_scale(failures, tag, fn, verts, faces, expected):
    result, intact = _invoke(fn, _scale(verts), faces)
    quadrupled = [4.0 * area for area in expected]
    doubled = [2.0 * area for area in expected]
    if not intact:
        failures.append(f"{tag}:inputs")
    if len(result) != len(expected):
        failures.append(f"{tag}:length:{len(result)}!={len(expected)}")
        return
    if result != quadrupled:
        failures.append(f"{tag}:face:{result}!={quadrupled}")
    if result == doubled:
        failures.append(f"{tag}:linear:{result}")


def _check_shifts(failures, tag, fn, verts, faces, expected):
    for variant in _face_variants(faces):
        result, intact = _invoke(fn, verts, list(variant))
        if (
            not intact
            or len(result) != len(expected)
            or any(area < 0 for area in result)
            or result != list(expected)
        ):
            failures.append(f"{tag}:value:{list(variant)}:{result}")
            return


def witness_failures():
    """Literal and invariant failures of the current tri_areas and poly_areas.

    Empty for the real producers. Non-empty when a mutated producer misses a witness.
    """
    _rotation_matrix()
    tri_fn = qa_packages.tri_areas
    poly_fn = qa_packages.poly_areas
    failures = []
    for shape in _SHAPES:
        points = shape["points"]
        for kind, faces, expected in _channels(shape):
            fn = tri_fn if kind == "tri" else poly_fn
            _check(failures, f"literal:{shape['name']}:{kind}", fn, points, faces, expected)
            _check_shifts(failures, f"shift:{shape['name']}:{kind}", fn, points, faces, expected)
            for plane in ("xy", "xz", "yz"):
                _check(
                    failures,
                    f"plane:{plane}:{shape['name']}:{kind}",
                    fn,
                    _reembed(points, plane),
                    faces,
                    expected,
                )
            _check(
                failures,
                f"oblique:{shape['name']}:{kind}",
                fn,
                _rotate(points),
                faces,
                expected,
                tol=True,
            )
            _check_scale(failures, f"scale:{shape['name']}:{kind}", fn, points, faces, expected)

    tri_verts = [
        [0.0, 0.0, 0.0],
        [3.0, 0.0, 0.0],
        [0.0, 4.0, 0.0],
        [6.0, 0.0, 0.0],
    ]
    _check(failures, "order:tri:6-then-12", tri_fn, tri_verts, [[0, 1, 2], [0, 3, 2]], [6.0, 12.0])
    _check(failures, "order:tri:12-then-6", tri_fn, tri_verts, [[0, 3, 2], [0, 1, 2]], [12.0, 6.0])

    poly_verts = [
        [0.0, 0.0, 0.0],
        [3.0, 0.0, 0.0],
        [0.0, 4.0, 0.0],
        [3.0, 4.0, 0.0],
    ]
    _check(
        failures,
        "order:poly:6-then-12",
        poly_fn,
        poly_verts,
        [[0, 1, 2], [0, 1, 3, 2]],
        [6.0, 12.0],
    )
    _check(
        failures,
        "order:poly:12-then-6",
        poly_fn,
        poly_verts,
        [[0, 1, 3, 2], [0, 1, 2]],
        [12.0, 6.0],
    )
    return failures


def _hits(failures, tags):
    """Tags whose witness recorded at least one failure."""
    return [tag for tag in tags if any(item.startswith(tag + ":") for item in failures)]


def _literal_tags():
    tags = []
    for shape in _SHAPES:
        for kind, _faces, _expected in _channels(shape):
            tags.append(f"literal:{shape['name']}:{kind}")
    return tags


def _xz_yz_oblique_tags():
    tags = []
    for prefix in ("plane:xz", "plane:yz", "oblique"):
        for shape in _SHAPES:
            for kind, _faces, _expected in _channels(shape):
                tags.append(f"{prefix}:{shape['name']}:{kind}")
    return tags


def _tri_areas_no_half(out_v, out_faces):
    """Mutated copy of tri_areas with the factor 1/2 removed."""
    verts = np.asarray(out_v, float)
    return [
        float(np.linalg.norm(np.cross(verts[face[1]] - verts[face[0]], verts[face[2]] - verts[face[0]])))
        for face in out_faces
    ]


def _poly_areas_no_half(src_v, src_faces):
    """Mutated copy of the Newell area with the factor 1/2 removed."""
    areas = []
    for face in src_faces:
        polygon = np.asarray([src_v[index] for index in face], float)
        normal = np.zeros(3)
        for index in range(len(polygon)):
            start = polygon[index]
            end = polygon[(index + 1) % len(polygon)]
            normal += [
                (start[1] - end[1]) * (start[2] + end[2]),
                (start[2] - end[2]) * (start[0] + end[0]),
                (start[0] - end[0]) * (start[1] + end[1]),
            ]
        areas.append(float(np.linalg.norm(normal)))
    return areas


def _tri_areas_xy(out_v, out_faces):
    """Mutated copy that returns the area of the XY projection only."""
    verts = np.asarray(out_v, float)
    areas = []
    for face in out_faces:
        edge_a = verts[face[1]] - verts[face[0]]
        edge_b = verts[face[2]] - verts[face[0]]
        areas.append(float(abs(edge_a[0] * edge_b[1] - edge_a[1] * edge_b[0]) / 2.0))
    return areas


def _poly_areas_xy(src_v, src_faces):
    """Mutated copy of Newell that keeps only the XY (z) component."""
    areas = []
    for face in src_faces:
        polygon = np.asarray([src_v[index] for index in face], float)
        nz = 0.0
        for index in range(len(polygon)):
            start = polygon[index]
            end = polygon[(index + 1) % len(polygon)]
            nz += (start[0] - end[0]) * (start[1] + end[1])
        areas.append(abs(nz) / 2.0)
    return areas


def test_real_producer_matches_literal_area_oracles():
    assert witness_failures() == []


def test_dropped_half_is_caught_by_literal_witnesses(monkeypatch):
    monkeypatch.setattr(qa_packages, "tri_areas", _tri_areas_no_half)
    monkeypatch.setattr(qa_packages, "poly_areas", _poly_areas_no_half)
    failures = witness_failures()
    tags = _literal_tags()
    caught = _hits(failures, tags)
    assert failures
    assert caught == tags


def test_xy_projection_is_caught_by_xz_yz_and_oblique_witnesses(monkeypatch):
    monkeypatch.setattr(qa_packages, "tri_areas", _tri_areas_xy)
    monkeypatch.setattr(qa_packages, "poly_areas", _poly_areas_xy)
    failures = witness_failures()
    tags = _xz_yz_oblique_tags()
    caught = _hits(failures, tags)
    assert failures
    assert caught == tags
    assert _hits(failures, _literal_tags()) == []
