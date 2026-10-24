"""new-case: UV nudge island partition controls.

Scope: transitive UV-index connectivity for the repeat shift
(docs/domain/uv-textures.md). A bridge face joins same-period faces that share
no UV index with each other; identical coordinates with disjoint indices stay
separate islands. Expected components are the hand-read components of that
literal face graph, not a union-find.
"""
import itertools
import math

import pytest

from dt_ai.geometry.uv import tile_origin
from dt_ai.geometry.uv_nudge import nudge_repeating_islands

# Frozen face graph. UV index sets:
#   A = {0,1,2}  B = {3,2,4}  C = {5,6,4}  D = {7,8,9}
#   A∩B = {2}, B∩C = {4}, A∩C = ∅, D shares nothing.
#   Hand components: {A,B,C} and {D}. Vertex 10 is referenced by no face.
#   D copies A's coordinates on fresh indices.
UV = [
    (2.0, 2.0),
    (2.5, 2.0),
    (2.25, 2.5),
    (2.25, 3.0),
    (2.75, 2.75),
    (3.0, 2.5),
    (3.0, 3.0),
    (2.0, 2.0),
    (2.5, 2.0),
    (2.25, 2.5),
    (4.0, 4.0),
]
FACES = {
    "A": [0, 1, 2],
    "B": [3, 2, 4],
    "C": [5, 6, 4],
    "D": [7, 8, 9],
}
MATS = {"A": "brick", "B": "plaster", "C": "brick", "D": "tile"}
PERIODS = {
    "brick": (0.5, 0.5),
    "plaster": (0.5, 0.5),
    "tile": (0.25, 0.25),
}
TARGET_TILE = 1002
# tile 1002 origin is (1, 0); centre is half a tile in from that corner.
_ORIGIN = tile_origin(TARGET_TILE)
CENTRE = (_ORIGIN[0] + 0.5, _ORIGIN[1] + 0.5)

# {A,B,C} bbox centre (2.5, 2.5), period (0.5, 0.5):
#   floor((1.5-2.5)/0.5 + 0.5) = -2, floor((0.5-2.5)/0.5 + 0.5) = -4
#   -> (-1.0, -2.0)
# {D} bbox centre (2.25, 2.25), period (0.25, 0.25):
#   floor((1.5-2.25)/0.25 + 0.5) = -3, floor((0.5-2.25)/0.25 + 0.5) = -7
#   -> (-0.75, -1.75)
CHAIN = frozenset({"A", "B", "C"})
ISLAND_D = frozenset({"D"})
CHAIN_SHIFT = (-1.0, -2.0)
D_SHIFT = (-0.75, -1.75)
CHAIN_VERTS = frozenset(FACES["A"] + FACES["B"] + FACES["C"])
D_VERTS = frozenset(FACES["D"])

# D is fixed first so the six A-B-C orders include the bridge as the last face.
FACE_ORDERS = [
    ("D", "A", "B", "C"),
    ("D", "A", "C", "B"),
    ("D", "B", "A", "C"),
    ("D", "B", "C", "A"),
    ("D", "C", "A", "B"),
    ("D", "C", "B", "A"),
]


def _literal_components():
    """Face-graph components read off the index sets above. Not a search."""
    assert set(FACES["A"]) & set(FACES["B"]) == {2}
    assert set(FACES["B"]) & set(FACES["C"]) == {4}
    assert set(FACES["A"]).isdisjoint(FACES["C"])
    assert set(FACES["D"]).isdisjoint(CHAIN_VERTS)
    return {CHAIN, ISLAND_D}


def _assemble(order, mats=None, periods=None):
    mats = MATS if mats is None else mats
    periods = PERIODS if periods is None else periods
    uv = list(UV)
    faces = [list(FACES[label]) for label in order]
    materials = [mats[label] for label in order]
    return uv, faces, materials, dict(periods)


def _snap(uv, faces, mats, periods):
    return (
        [tuple(point) for point in uv],
        [list(face) for face in faces],
        list(mats),
        {key: periods[key] for key in periods},
    )


def _same_point(left, right):
    if len(left) != len(right):
        return False
    for a, b in zip(left, right):
        if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
            continue
        if a != b:
            return False
    return True


def _assert_untouched(uv, faces, mats, periods, saved):
    assert len(uv) == len(saved[0])
    assert all(_same_point(a, b) for a, b in zip(uv, saved[0]))
    assert faces == saved[1]
    assert list(mats) == saved[2]
    assert dict(periods) == saved[3]


def _call(uv, faces, mats, periods):
    saved = _snap(uv, faces, mats, periods)
    result = nudge_repeating_islands(
        uv, faces, mats, periods, target_tile=TARGET_TILE)
    _assert_untouched(uv, faces, mats, periods, saved)
    return result


def _raises(uv, faces, mats, periods, match):
    saved = _snap(uv, faces, mats, periods)
    with pytest.raises(ValueError, match=match) as caught:
        nudge_repeating_islands(
            uv, faces, mats, periods, target_tile=TARGET_TILE)
    _assert_untouched(uv, faces, mats, periods, saved)
    return caught.value


def _components(result, order):
    groups = [frozenset(order[i] for i in island["faces"]) for island in result.islands]
    labels = [label for group in groups for label in group]
    assert sorted(labels) == sorted(order)
    return set(groups)


def _island_for(result, order, labels):
    want = frozenset(labels)
    found = [
        island for island in result.islands
        if frozenset(order[i] for i in island["faces"]) == want
    ]
    assert len(found) == 1
    return found[0]


def _cyclic(old, new, period):
    delta = abs(old % period - new % period)
    return min(delta, period - delta)


def _assert_placed(uv, result, vert_ids, period):
    deltas = {
        (result.uv[i][0] - uv[i][0], result.uv[i][1] - uv[i][1]) for i in vert_ids
    }
    assert len(deltas) == 1
    du, dv = next(iter(deltas))
    pu, pv = period
    assert math.isclose(du / pu, round(du / pu), abs_tol=1e-9)
    assert math.isclose(dv / pv, round(dv / pv), abs_tol=1e-9)
    for i in vert_ids:
        assert _cyclic(uv[i][0], result.uv[i][0], pu) <= 1e-9
        assert _cyclic(uv[i][1], result.uv[i][1], pv) <= 1e-9
    moved = [result.uv[i] for i in vert_ids]
    cu = (min(p[0] for p in moved) + max(p[0] for p in moved)) / 2
    cv = (min(p[1] for p in moved) + max(p[1] for p in moved)) / 2
    assert abs(cu - CENTRE[0]) <= pu / 2 + 1e-9
    assert abs(cv - CENTRE[1]) <= pv / 2 + 1e-9
    return (du, dv)


def _assert_unreferenced(uv, result, faces):
    used = {index for face in faces for index in face}
    for index, point in enumerate(uv):
        if index not in used:
            assert result.uv[index] == point


def _assert_second_call(result, faces, mats, periods):
    saved = _snap(result.uv, faces, mats, periods)
    again = nudge_repeating_islands(
        result.uv, faces, mats, periods, target_tile=TARGET_TILE)
    _assert_untouched(result.uv, faces, mats, periods, saved)
    assert again.uv == result.uv
    assert all(
        island["steps"] == (0, 0) and island["shift"] == (0.0, 0.0)
        for island in again.islands
    )


def _expected_uv():
    moved = []
    for index, (u, v) in enumerate(UV):
        if index in CHAIN_VERTS:
            moved.append((u + CHAIN_SHIFT[0], v + CHAIN_SHIFT[1]))
        elif index in D_VERTS:
            moved.append((u + D_SHIFT[0], v + D_SHIFT[1]))
        else:
            moved.append((u, v))
    return moved


def _named_island(exc):
    text = str(exc)
    assert "island of faces" in text
    bracket = text.split("island of faces", 1)[1]
    body = bracket.split("[", 1)[1].split("]", 1)[0]
    return {int(part.strip()) for part in body.split(",") if part.strip()}


def test_literal_graph_is_a_bridge_plus_one_disjoint_island():
    assert _literal_components() == {CHAIN, ISLAND_D}
    assert [UV[i] for i in FACES["A"]] == [UV[i] for i in FACES["D"]]
    assert len(set(FACES["A"]) & set(FACES["B"])) == 1
    assert PERIODS["brick"] == PERIODS["plaster"] != PERIODS["tile"]
    assert CENTRE == (1.5, 0.5)
    assert len(FACE_ORDERS) == 6
    assert sorted(order[1:] for order in FACE_ORDERS) == sorted(
        itertools.permutations(("A", "B", "C")))
    assert ("D", "A", "C", "B") in FACE_ORDERS
    assert ("D", "C", "A", "B") in FACE_ORDERS


def test_bridge_is_one_component_with_one_translation():
    order = ("A", "B", "C", "D")
    uv, faces, mats, periods = _assemble(order)
    result = _call(uv, faces, mats, periods)
    assert _components(result, order) == _literal_components()
    chain = _island_for(result, order, CHAIN)
    assert set(chain["materials"]) == {"brick", "plaster"}
    assert _assert_placed(uv, result, CHAIN_VERTS, (0.5, 0.5)) == CHAIN_SHIFT
    assert chain["steps"] == (-2, -4)
    assert chain["shift"] == CHAIN_SHIFT
    assert chain["target_tile"] == TARGET_TILE
    disjoint = _island_for(result, order, ISLAND_D)
    assert _assert_placed(uv, result, D_VERTS, (0.25, 0.25)) == D_SHIFT
    assert disjoint["steps"] == (-3, -7)
    assert result.uv == _expected_uv()
    _assert_unreferenced(uv, result, faces)
    _assert_second_call(result, faces, mats, periods)


@pytest.mark.parametrize("order", FACE_ORDERS)
def test_face_order_keeps_vertex_uv_and_membership(order):
    uv, faces, mats, periods = _assemble(order)
    result = _call(uv, faces, mats, periods)
    assert result.uv == _expected_uv()
    assert _components(result, order) == _literal_components()
    assert _assert_placed(uv, result, CHAIN_VERTS, (0.5, 0.5)) == CHAIN_SHIFT
    assert _assert_placed(uv, result, D_VERTS, (0.25, 0.25)) == D_SHIFT
    _assert_unreferenced(uv, result, faces)
    _assert_second_call(result, faces, mats, periods)


def test_one_shared_uv_index_is_one_component():
    # A∩B = {2} only. Separate centres would take different shifts.
    order = ("A", "B")
    uv, faces, mats, periods = _assemble(order)
    result = _call(uv, faces, mats, periods)
    assert _components(result, order) == {frozenset({"A", "B"})}
    verts = set(FACES["A"]) | set(FACES["B"])
    # bbox centre (2.375, 2.5) -> steps (-2, -4) -> shift (-1, -2)
    assert _assert_placed(uv, result, verts, (0.5, 0.5)) == (-1.0, -2.0)
    _assert_unreferenced(uv, result, faces)
    _assert_second_call(result, faces, mats, periods)


def test_equal_coordinates_and_disjoint_indices_keep_different_periods():
    order = ("A", "D")
    uv, faces, mats, periods = _assemble(order)
    result = _call(uv, faces, mats, periods)
    assert _components(result, order) == {frozenset({"A"}), frozenset({"D"})}
    # A alone, centre (2.25, 2.25), period 0.5 -> steps (-1, -3) -> (-0.5, -1.5)
    shift_a = _assert_placed(uv, result, set(FACES["A"]), (0.5, 0.5))
    shift_d = _assert_placed(uv, result, set(FACES["D"]), (0.25, 0.25))
    assert shift_a == (-0.5, -1.5)
    assert shift_d == D_SHIFT
    assert shift_a != shift_d
    _assert_unreferenced(uv, result, faces)
    _assert_second_call(result, faces, mats, periods)


def test_conflicting_period_only_at_the_far_end_names_the_island():
    mats = {"A": "brick", "B": "plaster", "C": "other", "D": "tile"}
    periods = {"brick": (0.5, 0.5), "plaster": (0.5, 0.5), "other": (0.25, 0.25), "tile": (0.25, 0.25)}
    # No bridge: A and C share no index, so the two periods are legal.
    uv, faces, materials, period_map = _assemble(("A", "C"), mats, periods)
    apart = _call(uv, faces, materials, period_map)
    assert _components(apart, ("A", "C")) == {frozenset({"A"}), frozenset({"C"})}
    # B (same period as A) is the only link. The clash sits on C.
    uv, faces, materials, period_map = _assemble(("A", "B", "C", "D"), mats, periods)
    exc = _raises(uv, faces, materials, period_map, "period")
    assert _named_island(exc) == {0, 1, 2}
    assert "different periods" in str(exc)


def test_nonrepeating_only_at_the_far_end_names_the_island():
    mats = {"A": "brick", "B": "plaster", "C": "glass", "D": "tile"}
    periods = {"brick": (0.5, 0.5), "plaster": (0.5, 0.5), "glass": None, "tile": (0.25, 0.25)}
    uv, faces, materials, period_map = _assemble(("A", "C"), mats, periods)
    apart = _call(uv, faces, materials, period_map)
    assert _components(apart, ("A", "C")) == {frozenset({"A"}), frozenset({"C"})}
    for index in FACES["C"]:
        assert apart.uv[index] == uv[index]
    uv, faces, materials, period_map = _assemble(("A", "B", "C", "D"), mats, periods)
    exc = _raises(uv, faces, materials, period_map, "repeating")
    assert _named_island(exc) == {0, 1, 2}
    assert "non-repeating" in str(exc)


@pytest.mark.parametrize("kind", ["empty", "nan", "inf", "partial"])
def test_bad_input_errors_and_leaves_the_caller_unchanged(kind):
    uv, faces, mats, periods = _assemble(("A", "B", "C", "D"))
    if kind == "empty":
        uv, faces, mats = [], [], []
        match = "empty"
    elif kind == "nan":
        uv[0] = (math.nan, 2.0)
        match = "finite"
    elif kind == "inf":
        uv[2] = (2.25, math.inf)
        match = "finite"
    else:
        uv[4] = (2.75,)
        match = "partial"
    saved = _snap(uv, faces, mats, periods)
    with pytest.raises(ValueError, match=match):
        nudge_repeating_islands(uv, faces, mats, periods, target_tile=TARGET_TILE)
    _assert_untouched(uv, faces, mats, periods, saved)
