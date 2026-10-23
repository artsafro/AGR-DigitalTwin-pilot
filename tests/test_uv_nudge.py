"""Integer-tile UV nudge for repeating materials (issue #549, team GridUVLayout22.ms logic)."""
import math
import random

import pytest

from dt_ai.geometry.uv_nudge import PHASE_TOL, nudge_repeating_islands


def _quad(u0, v0, w=0.5, h=0.5):
    return [(u0, v0), (u0 + w, v0), (u0 + w, v0 + h), (u0, v0 + h)]


def _flat(points):
    return [c for p in points for c in p]


def _phase_kept(old, new, period, tol=1e-9):
    k = (new - old) / period
    return abs(k - round(k)) <= tol


def test_tiled_quad_shifted_by_integer_step_keeps_fractional_uv():
    uv = _quad(3.2, -1.8)
    result = nudge_repeating_islands(uv, [[0, 1, 2, 3]], ["brick"], {"brick": (1.0, 1.0)})
    assert _flat(result.uv) == pytest.approx(_flat(_quad(0.2, 0.2)))
    for (u0, v0), (u1, v1) in zip(uv, result.uv):
        assert u1 - u0 == pytest.approx(round(u1 - u0))
        assert v1 - v0 == pytest.approx(round(v1 - v0))
        assert u1 % 1 == pytest.approx(u0 % 1)
        assert v1 % 1 == pytest.approx(v0 % 1)
    assert result.islands[0]["steps"] == (-3, 2)
    assert result.islands[0]["shift"] == pytest.approx((-3.0, 2.0))


def test_sub_tile_period_moves_by_whole_periods_only():
    uv = _quad(5.13, 2.07, 0.1, 0.1)
    result = nudge_repeating_islands(uv, [[0, 1, 2, 3]], ["tile"], {"tile": (0.25, 1 / 3)})
    for (u0, v0), (u1, v1) in zip(uv, result.uv):
        assert _phase_kept(u0, u1, 0.25) and _phase_kept(v0, v1, 1 / 3)
    cu = sum(p[0] for p in result.uv) / 4
    cv = sum(p[1] for p in result.uv) / 4
    assert abs(cu - 0.5) <= 0.125 + 1e-12 and abs(cv - 0.5) <= 1 / 6 + 1e-12


def test_non_repeating_mesh_unchanged():
    uv = _quad(3.2, -1.8) + _quad(7.0, 7.0)
    faces = [[0, 1, 2, 3], [4, 5, 6, 7]]
    result = nudge_repeating_islands(uv, faces, ["glass", "decal"], {"glass": None, "decal": None})
    assert result.uv == uv
    assert all(i["steps"] == (0, 0) and i["reason"] == "non-repeating" for i in result.islands)


def test_only_repeating_islands_move():
    uv = _quad(3.2, 4.2) + _quad(3.2, 4.2)
    faces = [[0, 1, 2, 3], [4, 5, 6, 7]]
    result = nudge_repeating_islands(uv, faces, ["brick", "glass"], {"brick": (1, 1), "glass": None})
    assert _flat(result.uv[:4]) == pytest.approx(_flat(_quad(0.2, 0.2)))
    assert result.uv[4:] == uv[4:]


def test_udim_tile_offset_option():
    uv = _quad(0.2, 0.2)
    result = nudge_repeating_islands(uv, [[0, 1, 2, 3]], ["brick"], {"brick": (1, 1)}, target_tile=1012)
    assert _flat(result.uv) == pytest.approx(_flat(_quad(1.2, 1.2)))
    assert result.islands[0]["target_tile"] == 1012


def test_islands_are_uv_connected_components_and_move_together():
    # two faces share an edge (UV verts 1, 2) -> one island, one shift
    uv = [(4.1, 4.1), (4.6, 4.1), (4.6, 4.6), (4.1, 4.6), (5.1, 4.1), (5.1, 4.6)]
    faces = [[0, 1, 2, 3], [1, 4, 5, 2]]
    result = nudge_repeating_islands(uv, faces, ["brick", "brick"], {"brick": (1, 1)})
    assert len(result.islands) == 1
    shifts = {(round(a[0] - b[0], 9), round(a[1] - b[1], 9)) for a, b in zip(result.uv, uv)}
    assert len(shifts) == 1


def test_input_not_mutated_and_unreferenced_vertices_kept():
    uv = _quad(3.2, 3.2) + [(9.9, 9.9)]
    snapshot = list(uv)
    result = nudge_repeating_islands(uv, [[0, 1, 2, 3]], ["brick"], {"brick": (1, 1)})
    assert uv == snapshot
    assert result.uv[4] == (9.9, 9.9)


def test_half_period_tie_is_deterministic():
    # centre 1.0 vs target 0.5 -> desired -0.5 steps -> floor(-0.5 + 0.5) = 0 (GridUVLayout rounding)
    uv = _quad(0.75, 0.25)
    result = nudge_repeating_islands(uv, [[0, 1, 2, 3]], ["brick"], {"brick": (1, 1)})
    assert result.islands[0]["steps"] == (0, 0)


@pytest.mark.parametrize("periods, match", [
    ({}, "brick"),
    ({"other": (1, 1)}, "brick"),
    ({"brick": (0, 1)}, "period"),
    ({"brick": (-1, 1)}, "period"),
    ({"brick": (math.nan, 1)}, "period"),
    ({"brick": (1, math.inf)}, "period"),
    ({"brick": (1,)}, "period"),
    ({"brick": (True, 1)}, "period"),
    ({"brick": 1.0}, "period"),
])
def test_unmapped_material_or_bad_period_is_an_error(periods, match):
    with pytest.raises(ValueError, match=match):
        nudge_repeating_islands(_quad(0, 0), [[0, 1, 2, 3]], ["brick"], periods)


@pytest.mark.parametrize("uv, faces, mats, match", [
    ([], [], [], "empty"),
    (_quad(0, 0), [], [], "empty"),
    (_quad(0, 0), [[0, 1, 2, 3]], [], "material"),
    (_quad(0, 0), [[0, 1, 2, 3]], ["brick", "brick"], "material"),
    (_quad(0, 0), [[0, 1, 9]], ["brick"], "index"),
    (_quad(0, 0), [[0, 1, -1]], ["brick"], "index"),
    (_quad(0, 0), [[0, 1]], ["brick"], "3"),
    (_quad(0, 0), [[0, 1, 1]], ["brick"], "3"),
    ([(0, 0), (1, math.nan), (1, 1)], [[0, 1, 2]], ["brick"], "finite"),
    ([(0, 0), (1, math.inf), (1, 1)], [[0, 1, 2]], ["brick"], "finite"),
    ([(0, 0), (1,), (1, 1)], [[0, 1, 2]], ["brick"], "partial"),
    ([(0, 0), 5, (1, 1)], [[0, 1, 2]], ["brick"], "partial"),
    ([(0, 0), "ab", (1, 1)], [[0, 1, 2]], ["brick"], "partial"),
    ([(0, 0), (1, 2, 3), (1, 1)], [[0, 1, 2]], ["brick"], "partial"),
    ([(0, 0), (True, 0), (1, 1)], [[0, 1, 2]], ["brick"], "finite"),
    (_quad(0, 0), [[0, 1.0, 2]], ["brick"], "index"),
])
def test_fail_closed_inputs(uv, faces, mats, match):
    with pytest.raises(ValueError, match=match):
        nudge_repeating_islands(uv, faces, mats, {"brick": (1, 1)})


@pytest.mark.parametrize("tile", [1000, 1101, True, 1001.0, "1001"])
def test_bad_target_tile_is_an_error(tile):
    with pytest.raises(ValueError, match="UDIM"):
        nudge_repeating_islands(_quad(0, 0), [[0, 1, 2, 3]], ["brick"], {"brick": (1, 1)}, target_tile=tile)


def test_island_mixing_repeating_and_non_repeating_is_an_error():
    uv = _quad(0, 0) + [(1.0, 0.0)]
    faces = [[0, 1, 2, 3], [1, 4, 2]]
    with pytest.raises(ValueError, match="brick.*glass|glass.*brick"):
        nudge_repeating_islands(uv, faces, ["brick", "glass"], {"brick": (1, 1), "glass": None})


def test_island_with_conflicting_periods_is_an_error():
    uv = _quad(0, 0) + [(1.0, 0.0)]
    faces = [[0, 1, 2, 3], [1, 4, 2]]
    with pytest.raises(ValueError, match="period"):
        nudge_repeating_islands(uv, faces, ["brick", "tile"], {"brick": (1, 1), "tile": (0.5, 1)})


def test_two_materials_with_equal_period_in_one_island_move_together():
    uv = _quad(2.1, 2.1) + [(2.9, 2.1)]
    faces = [[0, 1, 2, 3], [1, 4, 2]]
    result = nudge_repeating_islands(uv, faces, ["brick", "plaster"], {"brick": (1, 1), "plaster": (1, 1)})
    assert result.islands[0]["steps"] == (-2, -2)


@pytest.mark.parametrize("seed", range(200))
def test_probe_random_islands_keep_phase_and_land_nearest_target(seed):
    rng = random.Random(seed)
    uv, faces, mats = [], [], []
    periods = {"r1": (1.0, 1.0), "r2": (0.25, 0.5), "r3": (1 / 3, 2.0), "n": None}
    for _ in range(rng.randint(1, 6)):
        mat = rng.choice(list(periods))
        u0, v0 = rng.uniform(-50, 50), rng.uniform(-50, 50)
        base = len(uv)
        uv += _quad(u0, v0, rng.uniform(0.01, 0.9), rng.uniform(0.01, 0.9))
        faces.append([base, base + 1, base + 2, base + 3])
        mats.append(mat)
    tile = rng.randint(1001, 1100)
    result = nudge_repeating_islands(uv, faces, mats, periods, target_tile=tile)
    tu, tv = (tile - 1001) % 10 + 0.5, (tile - 1001) // 10 + 0.5
    assert len(result.uv) == len(uv)
    assert sorted(f for i in result.islands for f in i["faces"]) == list(range(len(faces)))
    for face, mat in zip(faces, mats):
        old = [uv[i] for i in face]
        new = [result.uv[i] for i in face]
        if periods[mat] is None:
            assert new == old
            continue
        pu, pv = periods[mat]
        assert all(_phase_kept(a[0], b[0], pu, 1e-7) and _phase_kept(a[1], b[1], pv, 1e-7)
                   for a, b in zip(old, new))
        cu = (min(p[0] for p in new) + max(p[0] for p in new)) / 2
        cv = (min(p[1] for p in new) + max(p[1] for p in new)) / 2
        assert abs(cu - tu) <= pu / 2 + 1e-7 and abs(cv - tv) <= pv / 2 + 1e-7


def test_duplicated_face_is_one_island_moved_once():
    uv = _quad(3.2, 3.2)
    result = nudge_repeating_islands(uv, [[0, 1, 2, 3], [0, 1, 2, 3]], ["brick"] * 2, {"brick": (1, 1)})
    assert len(result.islands) == 1 and result.islands[0]["faces"] == [0, 1]
    assert _flat(result.uv) == pytest.approx(_flat(_quad(0.2, 0.2)))


def test_repeat_call_is_idempotent():
    first = nudge_repeating_islands(_quad(3.2, 3.2), [[0, 1, 2, 3]], ["brick"], {"brick": (1, 1)})
    second = nudge_repeating_islands(first.uv, [[0, 1, 2, 3]], ["brick"], {"brick": (1, 1)})
    assert second.uv == first.uv and second.islands[0]["steps"] == (0, 0)


def _cyclic_phase_error(old, new, period):
    d = abs(old % period - new % period)
    return min(d, period - d)


def _assert_invariants(uv, result, period, tile=1001):
    pu, pv = period
    tu, tv = (tile - 1001) % 10 + 0.5, (tile - 1001) // 10 + 0.5
    for (u0, v0), (u1, v1) in zip(uv, result.uv):
        assert _cyclic_phase_error(u0, u1, pu) <= PHASE_TOL
        assert _cyclic_phase_error(v0, v1, pv) <= PHASE_TOL
    us, vs = [p[0] for p in result.uv], [p[1] for p in result.uv]
    assert abs((min(us) + max(us)) / 2 - tu) <= pu / 2 + PHASE_TOL
    assert abs((min(vs) + max(vs)) / 2 - tv) <= pv / 2 + PHASE_TOL


HUGE_QUAD = [(1e16, 0.0), (1e16 + 4, 0.0), (1e16 + 4, 4.0), (1e16, 4.0)]


@pytest.mark.parametrize("period", [(0.3, 0.3), (0.25, 0.25)])
def test_precision_unsafe_shift_is_rejected_not_silently_wrong(period):
    # review round 1 P1: phase error 0.07 for (.3,.3); centre 0.0 outside .5 +- .125 for (.25,.25)
    with pytest.raises(ValueError, match="precision"):
        nudge_repeating_islands(HUGE_QUAD, [[0, 1, 2, 3]], ["brick"], {"brick": period})


@pytest.mark.parametrize("period", [(0.3, 0.3), (0.25, 0.25), (1.0, 1.0)])
def test_ordinary_offset_control_keeps_phase_centre_and_is_idempotent(period):
    uv = _quad(3.2, 3.2)
    first = nudge_repeating_islands(uv, [[0, 1, 2, 3]], ["brick"], {"brick": period})
    _assert_invariants(uv, first, period)
    second = nudge_repeating_islands(first.uv, [[0, 1, 2, 3]], ["brick"], {"brick": period})
    assert second.uv == first.uv and second.islands[0]["steps"] == (0, 0)


def test_one_unsafe_island_fails_whole_call_and_input_is_kept():
    uv = _quad(3.2, 3.2) + HUGE_QUAD
    before = list(uv)
    with pytest.raises(ValueError, match="precision"):
        nudge_repeating_islands(uv, [[0, 1, 2, 3], [4, 5, 6, 7]], ["a", "b"],
                                {"a": (0.3, 0.3), "b": (0.3, 0.3)})
    assert uv == before


@pytest.mark.parametrize("exp", range(0, 18))
@pytest.mark.parametrize("period", [(0.3, 0.3), (0.25, 0.25), (1 / 3, 0.7), (1.0, 1.0)])
def test_probe_magnitude_sweep_holds_invariants_or_raises(exp, period):
    rng = random.Random(exp)
    sign = rng.choice((-1, 1))
    uv = _quad(sign * 10.0 ** exp + rng.random(), -sign * 10.0 ** exp + rng.random(), 0.4, 0.4)
    try:
        result = nudge_repeating_islands(uv, [[0, 1, 2, 3]], ["brick"], {"brick": period})
    except ValueError as exc:
        assert "precision" in str(exc)
        return
    _assert_invariants(uv, result, period)
    again = nudge_repeating_islands(result.uv, [[0, 1, 2, 3]], ["brick"], {"brick": period})
    assert again.uv == result.uv
