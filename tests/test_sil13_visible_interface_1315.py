"""Source-bound visible-delivery pilot, not a general Ground repair contract."""
import importlib.util
from pathlib import Path
import numpy as np
import pytest

P = Path(__file__).resolve().parents[1] / 'jobs/SIL13-COLD-1315/hooks/visible_interface.py'

def load():
    spec = importlib.util.spec_from_file_location('sil13_visible', P)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('height,shift,allowed', [
    (.002, .002, True), (.005, .001, True), (.003, .00199, True),
    (.0019999, .001, False), (.0050001, .001, False),
    (.003, .002000001, False), (.003, 0., False), (.003, -.001, False),
    (.003, float('nan'), False), (.003, float('inf'), False),
])
def test_visible_corner_uses_actual_height_and_only_lowers_listed_vertex(height, shift, allowed):
    v = np.array([[0., 0., height], [1., 0., .3], [0., 1., .3]])
    g = np.array([[[-2., -2., -.2], [4., -2., -.2], [-2., 4., -.2]]])
    g = np.concatenate([g, g + [0, 0, .2]])
    g[:, 1, 2] += .02
    v[0, 2] += .02/3
    original = v.copy()
    move = load().lower_visible_corners
    if allowed:
        out, rows = move(v, np.array([[0, 1, 2]]), g, [(0, shift)], 'bench')
        np.testing.assert_array_equal(out[:, :2], v[:, :2])
        np.testing.assert_array_equal(out[1:], v[1:])
        assert len(rows) == 1 and rows[0]['object'] == 'bench' and rows[0]['vertex'] == 0
        assert rows[0]['before_height_m'] == pytest.approx(height)
        assert rows[0]['after_height_m'] == pytest.approx(height-shift)
        assert rows[0]['downshift_m'] == pytest.approx(shift)
    else:
        with pytest.raises(ValueError):
            move(v, np.array([[0, 1, 2]]), g, [(0, shift)], 'bench')
    np.testing.assert_array_equal(v, original)


@pytest.mark.parametrize('moves', [[], [(0, .001), (0, .001)], [(4, .001)], [(True, .001)], [(2, .001)]])
def test_visible_corner_rejects_empty_duplicate_unknown_or_unsupported_vertex(moves):
    v = np.array([[0., 0., .003], [1., 0., .03], [0., 1., .003]])
    g = np.array([[[-1., -1., 0.], [2., -1., 0.], [0., .3, 0.]]])
    with pytest.raises(ValueError):
        load().lower_visible_corners(v, np.array([[0, 1, 2]]), g, moves, 'bench')


def test_vertical_source_wall_is_cut_without_moving_visible_surface():
    # Synthetic control: wall crosses a flat actual-surface analogue at Z=0.
    wall = np.array([[0., 0., -.1], [1., 0., -.1], [0., 0., 1.]])
    ground = np.array([[[-2., -2., 0.], [2., -2., 0.], [0., 2., 0.]]])
    bary, receipt = load().visible_pieces(wall, ground)
    points = np.concatenate(bary) @ wall
    assert points[:, 2].min() >= -1e-10
    assert points[:, 2].max() == pytest.approx(1.)
    assert np.allclose(points[:, 1], 0)
    assert receipt['removed_fraction'] == pytest.approx(21/121)


@pytest.mark.parametrize('kind', ['empty', 'nan', 'inf', 'collinear'])
def test_unsupported_ground_fails_closed(kind):
    t = np.array([[0., 0., -.1], [1., 0., -.1], [0., 0., 1.]])
    g = np.array([[[-2., -2., 0.], [2., -2., 0.], [0., 2., 0.]]])
    if kind == 'empty': g = np.empty((0, 3, 3))
    elif kind == 'collinear': g[:] = 0
    else: g[0, 0, 0] = float(kind)
    with pytest.raises(ValueError): load().visible_pieces(t, g)


def test_layered_ground_uses_upper_surface_not_first_entry():
    t = np.array([[0., 0., -.1], [1., 0., -.1], [0., 0., 1.]])
    g = np.array([[[-2., -2., 0.], [2., -2., 0.], [0., 2., 0.]]])
    g = np.concatenate([g, g + [0, 0, .2]])
    for order in (g, g[::-1], np.concatenate([g, g])):
        pieces, _ = load().visible_pieces(t, order)
        assert (np.concatenate(pieces) @ t)[:, 2].min() == pytest.approx(.2)


def test_above_below_and_exact_surface():
    g = np.array([[[-2., -2., 0.], [2., -2., 0.], [0., 2., 0.]]])
    t = np.array([[0., 0., 0.], [.5, 0., 0.], [0., .5, 0.]])
    for z, count in [(-.1, 0), (0., 1), (.1, 1)]:
        pieces, receipt = load().visible_pieces(t + [0, 0, z], g)
        assert len(pieces) == count
        assert receipt['removed_fraction'] == pytest.approx(1 if z < 0 else 0)


def test_missing_ground_coverage_is_an_error_not_a_drop():
    t = np.array([[20., 0., -.1], [21., 0., -.1], [20., 0., 1.]])
    g = np.array([[[-2., -2., 0.], [2., -2., 0.], [0., 2., 0.]]])
    with pytest.raises(ValueError, match='coverage'): load().visible_pieces(t, g)


@pytest.mark.parametrize('kind', ['empty', 'partial', 'nan', 'inf', 'zero', 'threshold'])
def test_source_invalidity_fails_closed(kind):
    g = np.array([[[-2., -2., 0.], [2., -2., 0.], [0., 2., 0.]]])
    t = np.array([[0., 0., -.1], [1., 0., -.1], [0., 0., 1.]])
    if kind == 'empty': t = np.empty((0, 3))
    elif kind == 'partial': t = t[:2]
    elif kind == 'zero': t[:] = 0
    elif kind == 'threshold': t = np.array([[0., 0., 0.], [1., 0., 0.], [0., 1e-14, 0.]])
    else: t[0, 0] = float(kind)
    with pytest.raises(ValueError): load().visible_pieces(t, g)


def test_pure_cut_never_mutates_its_source_or_ground():
    g = np.array([[[-2., -2., 0.], [2., -2., 0.], [0., 2., 0.]]])
    t = np.array([[0., 0., -.1], [1., 0., -.1], [0., 0., 1.]])
    originals = [a.copy() for a in (t, g)]
    t.flags.writeable = g.flags.writeable = False
    load().visible_pieces(t, g)
    assert np.array_equal(t, originals[0]) and np.array_equal(g, originals[1])


@pytest.mark.parametrize('scale', [.01, 1., 100.])
@pytest.mark.parametrize('reverse', [False, True])
def test_generated_sloped_ground_preserves_source_plane_and_winding(scale, reverse):
    # Independent affine plane z=.2*x+.1*y through literal triangle corners.
    g = np.array([[[-2., -2., -.6], [2., -2., .2], [0., 2., .2]]])*scale
    t = np.array([[0., 0., -.1], [.5, 0., -.1], [0., .5, 1.]])*scale
    if reverse: t = t[::-1]
    pieces, receipt = load().visible_pieces(t, g)
    original_normal = np.cross(t[1]-t[0], t[2]-t[0])
    for b in pieces:
        points = b @ t
        assert (points[:, 2]-.2*points[:, 0]-.1*points[:, 1]).min() >= -1e-9
        assert np.abs(b.sum(axis=1)-1).max() < 1e-12
        assert b.min() >= -1e-12
        assert np.cross(points[1]-points[0], points[2]-points[0]) @ original_normal > 0
    assert 0 < receipt['removed_fraction'] < 1


def test_actual_SIL13_frame_face_crosses_ground_before_but_not_after():
    from twinqa.geometry.topology import count_defects
    # Real source witness249640/Ground816, metres; not synthetic site data.
    t = np.array([[-33.707542419433594, -10.022300720214844, -.08728155493736267],
                  [-33.74269104003906, -10.028857231140137, .16019296646118164],
                  [-33.74532699584961, -10.027812957763672, -.08528155833482742]])
    g = np.array([[[-34.00199890136719, -10.533002853393555, -.05362486094236374],
                   [-33.20100021362305, -9.459002494812012, -.06624692678451538],
                   [-34.125, -9.00000286102295, -.06089106947183609]]])
    def defects(tris):
        vertices = np.concatenate([np.asarray(tris).reshape(-1, 3), g.reshape(-1, 3)])
        faces = np.arange(len(vertices)).reshape(-1, 3)
        return count_defects(vertices, list(faces))['duplicates_and_self_intersections']
    assert defects([t]) == 1
    pieces, _ = load().visible_pieces(t, g)
    assert defects([b @ t for b in pieces]) == 0


@pytest.mark.parametrize('missing_width', [1e-4, 1e-3, .1])
def test_partial_projected_coverage_is_never_accepted(missing_width):
    t = np.array([[0., 0., -.1], [1., 0., -.1], [0., 0., 1.]])
    # A rectangular site whose right edge stops short of the wall.
    x = 1-missing_width
    g = np.array([[[-2., -2., 0.], [x, -2., 0.], [x, 2., 0.]],
                  [[-2., -2., 0.], [x, 2., 0.], [-2., 2., 0.]]])
    with pytest.raises(ValueError, match='coverage'): load().visible_pieces(t, g)
