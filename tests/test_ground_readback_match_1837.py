"""#1837: pure-Python probes of the Ground readback centre matcher (tools/blender/ground_readback_match.py).

No Blender and no mocked Blender API: the matcher takes plain (key, slot, normal_z) tuples.
"""
import importlib.util
import math
import random
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    'ground_readback_match', Path(__file__).resolve().parents[1] / 'tools/blender/ground_readback_match.py')
assert _spec is not None and _spec.loader is not None
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)

X0, Y0 = 1000.5, 2000.25
VERTS = [[X0, Y0, 150.0], [X0 + 2, Y0, 150.2], [X0 + 2, Y0 + 2, 150.2], [X0, Y0 + 2, 150.0], [X0 + 4, Y0 + 1, 150.4]]


def src(faces=([0, 1, 2, 3], [1, 4, 2]), mat=(0, 1), level=(0, 0)):
    return dict(verts=VERTS, faces=[list(f) for f in faces], slots=['Tile', 'Lawn'], mat=list(mat),
                level=list(level))


def mean(face):
    return tuple(round(sum(VERTS[i][k] for i in face) / len(face), 3) for k in range(3))


def imp(*rows):
    return [(mean(f), slot, nz) for f, slot, nz in rows]


def test_key_uses_face_degree():
    assert M.face_centre_key(VERTS, [0, 1, 2, 3]) == (X0 + 1, Y0 + 1, 150.1)
    assert M.face_centre_key(VERTS, [1, 4, 2]) == mean([1, 4, 2])  # triangle behaviour unchanged (/3)
    legacy = tuple(round(sum(VERTS[i][k] for i in [0, 1, 2, 3]) / 3, 3) for k in range(3))
    assert M.face_centre_key(VERTS, [0, 1, 2, 3]) != legacy


def test_full_coverage_pass_any_order():
    r = M.match_by_centre(src(), imp(([1, 4, 2], 'Lawn', 1.0), ([0, 1, 2, 3], 'Tile', 1.0)))
    assert r['centre_match']['complete'] and r['faces_matched_by_centre'] == 2
    assert (r['material_by_centre'], r['surface_normals_by_centre']) == ('pass', 'pass')
    assert r['surface_faces_checked_by_centre'] == 2


def test_wrong_quad_material_and_reversed_quad_normal_fail():
    r = M.match_by_centre(src(), imp(([0, 1, 2, 3], 'Lawn', -1.0), ([1, 4, 2], 'Lawn', 1.0)))
    assert (r['material_mismatch'], r['material_by_centre']) == (1, 'fail')
    assert (r['surface_faces_normal_down'], r['surface_normals_by_centre']) == (1, 'fail')


def test_skirt_face_normal_not_checked():
    r = M.match_by_centre(src(level=(-1, 0)), imp(([0, 1, 2, 3], 'Tile', -1.0), ([1, 4, 2], 'Lawn', 1.0)))
    assert r['surface_faces_normal_down'] == 0 and r['surface_faces_checked_by_centre'] == 1
    assert r['surface_normals_by_centre'] == 'pass'


@pytest.mark.parametrize('rows, field, value', [
    ([], 'unmatched_source_faces', [0, 1]),                                              # empty import
    ([([1, 4, 2], 'Lawn', 1.0)], 'unmatched_source_faces', [0]),                         # partial
    ([([1, 4, 2], 'Lawn', 1.0), ([0, 1, 2], 'Tile', 1.0)], 'unmatched_imported_faces', [1]),  # stray polygon
    ([([1, 4, 2], 'Lawn', 1.0), ([1, 4, 2], 'Lawn', 1.0), ([0, 1, 2, 3], 'Tile', 1.0)],
     'duplicate_imported_faces', [1]),                                                   # duplicated polygon
])
def test_incomplete_coverage_is_never_pass(rows, field, value):
    r = M.match_by_centre(src(), imp(*rows))
    assert r['centre_match'][field] == value and r['centre_match']['complete'] is False
    assert r['material_mismatch'] == 0 and r['material_by_centre'] == 'incomplete'
    assert r['surface_normals_by_centre'] == 'incomplete'


def test_ambiguous_source_centres_reported():
    # quad 0-1-2-3 and the reversed copy share a centre: neither may be silently picked
    r = M.match_by_centre(src(faces=([0, 1, 2, 3], [3, 2, 1, 0])), imp(([0, 1, 2, 3], 'Tile', 1.0)) * 2)
    cm = r['centre_match']
    assert cm['ambiguous_source_faces'] == [0, 1] and cm['ambiguous_imported_faces'] == [0, 1]
    assert cm['matched'] == 0 and r['material_by_centre'] == 'incomplete'


def test_nonfinite_source_and_imported_never_match():
    s = src()
    s['verts'] = [list(v) for v in VERTS]
    s['verts'][0][2] = math.nan
    r = M.match_by_centre(s, [((math.nan, Y0 + 1, 150.1), 'Tile', 1.0), (mean([1, 4, 2]), 'Lawn', math.nan)])
    cm = r['centre_match']
    assert cm['nonfinite_source_faces'] == [0] and cm['unmatched_imported_faces'] == [0]
    assert r['surface_faces_normal_down'] == 1  # NaN normal is never "up"
    assert r['material_by_centre'] == 'incomplete' and r['surface_normals_by_centre'] == 'fail'
    r = M.match_by_centre(src(), [((math.inf, 0.0, 0.0), 'Tile', 1.0), (mean([1, 4, 2]), 'Lawn', 1.0)])
    assert r['centre_match']['unmatched_imported_faces'] == [0] and r['material_by_centre'] == 'incomplete'


@pytest.mark.parametrize('bad, msg', [
    (src(faces=([0, 1],), mat=(0,), level=(0,)), 'at least 3'),
    (src(mat=(0, 2)), 'material index 2'),
    (src(level=(0,)), 'lengths differ'),
])
def test_malformed_source_is_an_error(bad, msg):
    with pytest.raises(ValueError, match=msg):
        M.match_by_centre(bad, [])


def test_generated_ngons_off_origin_all_matched():
    """Probe: random 3..8-gons, translated far off origin, shuffled order -> every face matched once."""
    rng = random.Random(1837)
    for _ in range(200):
        verts, faces, rows = [], [], []
        ox, oy = rng.uniform(-1e5, 1e5), rng.uniform(-1e5, 1e5)
        for fi in range(rng.randint(1, 12)):
            n = rng.randint(3, 8)
            cx, cy = ox + fi * 10, oy
            base = len(verts)
            verts += [[cx + math.cos(2 * math.pi * k / n), cy + math.sin(2 * math.pi * k / n), rng.uniform(100, 200)]
                      for k in range(n)]
            faces.append(list(range(base, base + n)))
        s = dict(verts=verts, faces=faces, slots=['Tile'], mat=[0] * len(faces), level=[0] * len(faces))
        rows = [(tuple(sum(verts[i][k] for i in f) / len(f) for k in range(3)), 'Tile', 1.0) for f in faces]
        rows = [(tuple(round(c, 3) for c in key), sl, nz) for key, sl, nz in rows]
        rng.shuffle(rows)
        r = M.match_by_centre(s, rows)
        assert r['centre_match']['complete'] and r['faces_matched_by_centre'] == len(faces)
