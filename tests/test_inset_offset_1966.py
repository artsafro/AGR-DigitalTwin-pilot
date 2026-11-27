"""#1966 (Refs #1784) [D419]: NPM delivery - inset elements offset off the body so the joined *_Main passes xView.

Pattern: n/a | new-case: tests of tools/derive/inset_offset.py (pure numpy over the shared xView kernel, no DCC).
Synthetic: every mesh below is a made-up box / plane, not Sokolniki data.
"""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

from dt_ai.ops import inv_xview as X
from dt_ai.ops.inv_quads import PolyMesh

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('inset_offset_1966', ROOT / 'tools/derive/inset_offset.py')
io = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(io)


def _box(x0, y0, z0, x1, y1, z1, base=0):
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return v, [tuple(i + base for i in q) for q in f]


def _scene(*parts):
    V, F = [], []
    for p in parts:
        v, f = p(len(V))
        V += v
        F += f
    return np.array(V, float), F


def _wall(base):        # body: a 10 x 1 x 6 m block, front face y = 0 facing -y
    return _box(0, 0, 0, 10, 1, 6, base)


def _relief(base):      # inset: a relief box whose back lies 1 mm in front of the wall face (inside face_m)
    return _box(2, -0.301, 1, 3, -0.001, 2, base)


def _sill(base):        # body: an opening sill 0.1 m deep at z = 0 (front edge y = 0)
    v = [(5, 0, 0), (6, 0, 0), (6, 0.1, 0), (5, 0.1, 0)]
    return v, [tuple(i + base for i in (0, 3, 2, 1))]


def _window(base):      # inset: a window plane at the back of the sill, its two bottom corners ON the sill corners
    v = [(5, 0.1, 0), (6, 0.1, 0), (6, 0.1, 1), (5, 0.1, 1)]
    return v, [tuple(i + base for i in (0, 1, 2, 3))]


def _pairs(V, F):
    tol = X.tolerance_for('NPM')
    return len(X.face_pairs(PolyMesh(V, tuple(F)), tol)), len(X.vertex_pairs(V, tol.vertex_m)[0])


def test_components_by_shared_vertices():
    V, F = _scene(_wall, _relief)
    comp = io.components(F, len(V))
    assert comp[:6] == [0] * 6 and comp[6:] == [1] * 6


def test_relief_on_the_wall_fails_xview_before_and_passes_after():
    V, F = _scene(_wall, _relief)
    assert _pairs(V, F)[0] > 0
    comp = io.components(F, len(V))
    plan = io.plan_offsets(V, F, comp, anchor={0}, target_m=0.006)
    move = np.array(plan['moves'][1])
    assert move == pytest.approx([0.0, -0.005, 0.0], abs=1e-6)       # off the wall along its outward normal
    V2 = io.apply_moves(V, F, comp, plan['moves'])
    assert _pairs(V2, F) == (0, 0)
    assert plan['residual']['face_pairs'] == 0 and plan['residual']['vertex_pairs'] == 0
    assert np.allclose(V2[:8], V[:8])                                  # the anchor (body) never moves


def test_two_mm_is_not_enough_for_the_npm_face_threshold():
    V, F = _scene(_wall, _relief)
    plan = io.plan_offsets(V, F, io.components(F, len(V)), anchor={0}, target_m=0.002, rounds=1)
    assert plan['residual']['face_pairs'] > 0                         # xView NPM face_m = 5 mm


def test_window_sharing_corner_points_moves_along_its_own_normal():
    V, F = _scene(_sill, _window)
    assert _pairs(V, F) == (0, 2)
    comp = io.components(F, len(V))
    plan = io.plan_offsets(V, F, comp, anchor={0}, target_m=0.006)
    m = np.array(plan['moves'][1])
    assert abs(m[1]) == pytest.approx(0.006) and m[0] == 0 and m[2] == 0
    assert _pairs(io.apply_moves(V, F, comp, plan['moves']), F) == (0, 0)


def test_anchor_pairs_are_reported_unresolved_not_moved():
    V, F = _scene(_wall, lambda b: _box(10, 0, 0, 12, 1, 6, b))      # two body volumes touching at x = 10
    comp = io.components(F, len(V))
    plan = io.plan_offsets(V, F, comp, anchor={0, 1}, target_m=0.006)
    assert plan['moves'] == {}
    assert plan['residual']['vertex_pairs'] > 0 and plan['residual']['by_class']


def test_weld_targets_join_coincident_anchor_vertices_only():
    V, F = _scene(_wall, lambda b: _box(10, 0, 0, 12, 1, 6, b), _window)
    comp = io.components(F, len(V))
    tm = io.weld_targets(V, F, comp, anchor={0, 1})
    assert len(tm) == 4                                                  # the 4 seam corners at x = 10
    assert all(comp_v in range(16) for kv in tm.items() for comp_v in kv)


def test_a_component_pushed_both_ways_moves_its_touching_faces_only():
    V, F = _scene(lambda b: _box(0, 0, 0, 1, 1, 1, b), lambda b: _box(1.001, 0, 0, 2, 1, 1, b),
                  lambda b: _box(2.001, 0, 0, 3, 1, 1, b))
    comp = io.components(F, len(V))
    plan = io.plan_offsets(V, F, comp, anchor={0, 2}, target_m=0.006)
    assert 1 in plan['local'] and 1 not in plan['moves'] and not plan['stuck_vertices']
    V2 = io.apply_moves(V, F, comp, plan['moves'], plan['vertex_moves'])
    assert _pairs(V2, F) == (0, 0)
    assert V2[8:16, 0].min() >= 1.006 - 1e-9 and V2[8:16, 0].max() <= 1.995 + 1e-9    # >= 6 mm off both
    assert V2[8:16, 0].max() - V2[8:16, 0].min() > 0.98                                   # shortened, not lost


def test_a_post_between_two_beams_is_thinned_not_moved_back_and_forth():
    # beam | post | beam: 3 mm left, 7 mm right; moving off the left beam brings the right one within 5 mm
    V, F = _scene(lambda b: _box(-3, 0, 0, 1, 0.1, 0.1, b), lambda b: _box(1.003, 0, -1, 1.05, 0.1, 1, b),
                  lambda b: _box(1.057, 0, 0, 5, 0.1, 0.1, b))
    comp = io.components(F, len(V))
    plan = io.plan_offsets(V, F, comp, anchor=set(), target_m=0.006)
    assert 1 in plan['local'] and plan['residual']['face_pairs'] == 0 and plan['residual']['vertex_pairs'] == 0


def test_a_welded_away_vertex_is_not_counted():
    V, F = _scene(_wall, lambda b: _box(10, 0, 0, 12, 1, 6, b))
    comp = io.components(F, len(V))
    tm = io.weld_targets(V, F, comp, anchor={0, 1})
    F2 = [tuple(tm.get(v, v) for v in f) for f in F]
    fp, vp = io._pairs(V, F2, X.tolerance_for('NPM'))
    assert vp == []


def test_volumes_meeting_at_one_corner_are_not_welded_into_a_bow_tie():
    V, F = _scene(_wall, lambda b: _box(10, 1, 6, 12, 2, 8, b))               # touch at the point (10, 1, 6) only
    comp = io.components(F, len(V))
    assert io.weld_targets(V, F, comp, anchor={0, 1}) == {}
