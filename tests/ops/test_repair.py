"""new-case: repair.flip_close kernel op controls and probes (#1144)."""
import numpy as np
import pytest

from dt_ai.ops.inv_quads import PolyMesh
from dt_ai.ops.repair import flip_close

V = [(x, y, z) for z in (0, 1) for y in (0, 1) for x in (0, 1)]
BOX = ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5))   # outward, bottom first


def _directed(faces):
    return [(f[k], f[(k + 1) % len(f)]) for f in faces for k in range(len(f))]


def _volume(v, faces):
    v = np.asarray(v, float)
    return sum(np.dot(v[f[0]], np.cross(v[f[k]], v[f[k + 1]])) for f in faces for k in range(1, len(f) - 1)) / 6


def _closed_consistent(faces):
    d = _directed(faces)
    return len(d) == len(set(d)) and all((b, a) in set(d) for a, b in d)


def test_open_bottom_is_capped_outward_and_every_face_is_kept():
    r = flip_close(PolyMesh(V, BOX[1:]))
    assert r.flipped == () and len(r.caps) == 1 and r.skipped == ()
    assert sorted(i for i in r.face_sources if i is not None) == list(range(5)) and r.face_sources[-1] is None
    assert _closed_consistent(r.mesh.faces) and _volume(V, r.mesh.faces) == pytest.approx(1.0)
    assert sorted(r.caps[0][1]) == [0, 1, 2, 3]


def test_reversed_face_is_flipped_back_and_named():
    faces = list(BOX)
    faces[3] = faces[3][::-1]
    r = flip_close(PolyMesh(V, tuple(faces)))
    assert r.flipped == (3,) and r.caps == () and _closed_consistent(r.mesh.faces)
    assert set(r.mesh.faces[3]) == set(BOX[3])


def test_closed_inside_out_majority_is_oriented_by_signed_volume():
    faces = [f[::-1] for f in BOX]
    faces[0] = BOX[0]          # 5 inverted + 1 right: closed, so the volume sign wins, not the majority (#1152)
    r = flip_close(PolyMesh(V, tuple(faces)))
    assert r.flipped == (1, 2, 3, 4, 5) and _closed_consistent(r.mesh.faces)
    assert _volume(V, r.mesh.faces) == pytest.approx(1.0)


def test_closed_cube_four_of_six_inward_gets_positive_volume():
    faces = [f[::-1] if i in (0, 1, 2, 3) else f for i, f in enumerate(BOX)]
    r = flip_close(PolyMesh(V, tuple(faces)), close=None)
    assert r.flipped == (0, 1, 2, 3) and r.caps == () and _closed_consistent(r.mesh.faces)
    assert _volume(V, r.mesh.faces) == pytest.approx(1.0)
    assert all(set(r.mesh.faces[i]) == set(BOX[i]) and _volume(V, [r.mesh.faces[i]]) == pytest.approx(
        _volume(V, [BOX[i]])) for i in range(6))     # every face wound as the outward reference


def test_closed_cube_all_inward_is_flipped_whole():
    r = flip_close(PolyMesh(V, tuple(f[::-1] for f in BOX)))
    assert r.flipped == tuple(range(6)) and _volume(V, r.mesh.faces) == pytest.approx(1.0)


def test_correct_cube_is_unchanged():
    r = flip_close(PolyMesh(V, BOX))
    assert r.flipped == () and r.caps == () and r.skipped == () and r.mesh.faces == BOX


@pytest.mark.parametrize("faces", [((0, 1, 3, 2),), ((0, 1, 5, 4), (1, 3, 7, 5))])
def test_single_open_sheet_is_not_capped_with_a_duplicate(faces):
    r = flip_close(PolyMesh(V, faces), close=None)
    assert r.mesh.faces == faces and r.caps == () and r.flipped == ()
    assert len(r.skipped) == 1 and r.skipped[0][1] == "loop bounds the whole open sheet"


def _volume_rel(v, faces):
    v = np.asarray(v, float)
    return _volume(v - v.mean(0), faces)     # translation-invariant for a closed mesh, exact far from the origin


@pytest.mark.parametrize("off", [0.0, 1e5, 1e6])     # 0.0 = origin control (#1158 review P1-1)
@pytest.mark.parametrize("s", [0.1, 1.0])
def test_closed_cube_far_from_origin_gets_positive_volume(off, s):
    v = [tuple(s * c + off for c in p) for p in V]
    faces = [f[::-1] if i in (0, 1, 2, 3) else f for i, f in enumerate(BOX)]
    r = flip_close(PolyMesh(v, tuple(faces)), close=None)
    assert r.flipped == (0, 1, 2, 3) and r.caps == () and _closed_consistent(r.mesh.faces)
    assert _volume_rel(v, r.mesh.faces) == pytest.approx(s ** 3, rel=1e-6)


GV = [(x, y, 0) for y in range(3) for x in range(3)]        # 3x3 planar grid, vertex 4 interior
GRID = ((0, 1, 4, 3), (1, 2, 5, 4), (3, 4, 7, 6), (4, 5, 8, 7))


def test_planar_grid_sheet_with_interior_vertex_is_not_capped():
    r = flip_close(PolyMesh(GV, GRID), close=None)
    assert r.mesh.faces == GRID and r.caps == () and r.flipped == ()
    assert len(r.skipped) == 1 and r.skipped[0][1] == "loop bounds the whole open sheet"


def test_planar_annulus_hole_is_capped_outer_border_is_not():
    v = [(x, y, 0) for y in range(4) for x in range(4)]      # 4x4 grid without the centre quad (5, 6, 10, 9)
    q = tuple((y * 4 + x, y * 4 + x + 1, y * 4 + x + 5, y * 4 + x + 4)
              for y in range(3) for x in range(3) if (x, y) != (1, 1))
    r = flip_close(PolyMesh(v, q), close=None)
    assert len(r.caps) == 1 and sorted(r.caps[0][1]) == [5, 6, 9, 10]
    assert [w for _, w in r.skipped] == ["loop bounds the whole open sheet"]


def test_open_box_control_keeps_its_cap():
    r = flip_close(PolyMesh(V, BOX[1:]), close=None)
    assert len(r.caps) == 1 and r.skipped == ()


@pytest.mark.parametrize("dz,capped", [(0.04, False), (0.0079, True), (0.0081, False)])
def test_nonplanar_loop_is_skipped_at_threshold(dz, capped):
    v = [list(p) for p in V]
    v[0][2] -= dz      # one of 4 bottom corners pulled down: every corner is dz/4 off the best-fit plane
    r = flip_close(PolyMesh(v, BOX[1:]))      # plane_m 0.002 = dz/4 at dz 0.008
    if capped:
        assert len(r.caps) == 1
    else:
        assert r.caps == () and "nonplanar" in r.skipped[0][1]


def test_non_convex_loop_is_skipped():
    v = [(0, 0, 0), (2, 0, 0), (2, 1, 0), (1, 1, 0), (1, 2, 0), (0, 2, 0)]
    v += [(x, y, 1) for x, y, _ in v]
    n = 6
    walls = tuple((i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n))
    top = tuple(range(n, 2 * n))
    r = flip_close(PolyMesh(v, walls + (top,)))
    assert r.caps == () and r.skipped and r.skipped[0][1] == "not a convex loop"


def test_close_selection_skips_unselected_loops():
    r = flip_close(PolyMesh(V, BOX[1:]), close=set())
    assert r.caps == () and r.skipped[0][1] == "not selected"
    sel = {frozenset(e) for e in ((0, 1), (1, 3), (3, 2), (2, 0))}
    assert len(flip_close(PolyMesh(V, BOX[1:]), close=sel).caps) == 1


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf"), True, 0.0021])
def test_plane_tolerance_fail_closed(bad):
    with pytest.raises(ValueError, match="plane_m"):
        flip_close(PolyMesh(V, BOX), plane_m=bad)


def test_empty_and_unsupported_fail_closed():
    with pytest.raises(ValueError, match="empty"):
        flip_close(PolyMesh(V, ()))
    with pytest.raises(ValueError, match="unsupported"):
        flip_close({"v": V})


def test_input_is_not_mutated():
    m = PolyMesh(V, BOX[1:])
    before = (m.vertices.copy(), m.faces)
    flip_close(m)
    assert np.array_equal(m.vertices, before[0]) and m.faces == before[1]


def test_probe_random_rigid_open_boxes_with_random_flips():
    """Probe: 300 random rotations/translations, random flipped minority, random removed face -> closed,
    consistently wound, positive volume, every input face exactly once, flipped == the flipped set."""
    rng = np.random.default_rng(1144)
    ok = 0
    for _ in range(300):
        q, _ = np.linalg.qr(rng.normal(size=(3, 3)))
        q *= np.sign(np.linalg.det(q))
        v = (np.asarray(V, float) - 0.5) @ q.T * rng.uniform(0.1, 30) + rng.uniform(-50, 50, 3)
        drop = int(rng.integers(6))
        faces = [f for i, f in enumerate(BOX) if i != drop]
        flipped = set(rng.choice(5, size=int(rng.integers(0, 3)), replace=False).tolist())
        faces = [f[::-1] if i in flipped else f for i, f in enumerate(faces)]
        r = flip_close(PolyMesh(v, tuple(faces)))
        assert set(r.flipped) == flipped
        assert sorted(i for i in r.face_sources if i is not None) == list(range(5))
        assert len(r.caps) == 1 and _closed_consistent(r.mesh.faces)
        assert _volume(v, r.mesh.faces) > 0
        ok += 1
    assert ok == 300


def test_probe_random_rigid_closed_boxes_with_any_flips_get_positive_volume():
    """Probe (#1152): 300 random rigid transforms, random flipped subset of all 6 faces (majority allowed) ->
    closed, consistently wound, volume == +scale^3, no caps, flipped == the flipped set."""
    rng = np.random.default_rng(1152)
    ok = 0
    for _ in range(300):
        q, _ = np.linalg.qr(rng.normal(size=(3, 3)))
        q *= np.sign(np.linalg.det(q))
        s = rng.uniform(0.1, 30)
        v = (np.asarray(V, float) - 0.5) @ q.T * s + rng.uniform(-50, 50, 3)
        flipped = set(rng.choice(6, size=int(rng.integers(0, 7)), replace=False).tolist())
        r = flip_close(PolyMesh(v, tuple(f[::-1] if i in flipped else f for i, f in enumerate(BOX))))
        assert set(r.flipped) == flipped and r.caps == () and _closed_consistent(r.mesh.faces)
        assert _volume(v, r.mesh.faces) == pytest.approx(s ** 3, rel=1e-6)
        ok += 1
    assert ok == 300
