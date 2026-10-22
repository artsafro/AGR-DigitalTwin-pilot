"""from_face in the context of the neighbouring wall (#353, user decision 2026-10-22 variant B). All meshes SYNTHETIC."""
import math

import numpy as np
import pytest

from dt_ai.ops.face import face_on_wall
from dt_ai.ops.invariants import EMBED_MIN_M, Mesh, border_edges, distance_to_surface, winding_number
from tests.ops.test_invariants import box
from tests.ops.test_primitive import join

WALL = box((0, 0, 0), (4, 0.3, 3))                        # closed wall, exterior side y < 0


def panel(x0=1.0, z0=1.0, w=1.0, h=1.0, t=0.02, gap=0.0, side=-1):
    """A thin closed cassette on the wall face; `side=-1` = exterior (y < 0), `+1` = behind the wall (y > 0.3)."""
    if side < 0:
        return box((x0, -gap - t, z0), (x0 + w, -gap, z0 + h))
    return box((x0, 0.3 + gap, z0), (x0 + w, 0.3 + gap + t, z0 + h))


def border_points(mesh: Mesh) -> np.ndarray:
    e = border_edges(mesh)
    return np.concatenate([e[:, 0], (e[:, 0] + e[:, 1]) / 2])


def assert_border_deep(face: Mesh, wall: Mesh, embed=EMBED_MIN_M):
    pts = border_points(face)
    assert len(pts)
    assert (np.abs(winding_number(pts, wall)) > 0.5).all()
    assert distance_to_surface(pts, wall).min() >= embed - 1e-9


def test_single_cassette_becomes_face_with_skirt():
    scene = {"wall": WALL, "cassette": panel()}
    r = face_on_wall(scene, "cassette", "wall", "front")
    assert r.applied, r.question
    face = r.scene["cassette"]
    assert len(face.triangles) == 10                       # 2 cap + 8 skirt, no back cap
    assert r.notes["faces_before"] == 12 and r.notes["faces_after"] == 10
    assert r.notes["inward"] == 1.0 and r.notes["w_out"] == pytest.approx(-0.02)
    assert_border_deep(face, WALL)
    assert r.scene["wall"] is WALL                         # the wall is untouched
    # The exterior cap is the most exterior geometry and faces outwards (-y).
    tri = face.corners()
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    cap = np.isclose(tri[:, :, 1], -0.02).all(axis=1)
    assert cap.sum() == 2 and (n[cap, 1] < 0).all()


def test_air_gap_and_wall_behind_on_the_other_side():
    r = face_on_wall({"wall": WALL, "p": panel(gap=0.05)}, "p", "wall", "front")
    assert r.applied, r.question
    assert_border_deep(r.scene["p"], WALL)
    r = face_on_wall({"wall": WALL, "p": panel(side=+1, gap=0.03)}, "p", "wall", "front")
    assert r.applied, r.question
    assert r.notes["inward"] == -1.0
    assert_border_deep(r.scene["p"], WALL)


def test_two_walls_as_context_each_border_deep_in_one_wall():
    left, right = box((0, 0, 0), (2, 0.3, 3)), box((2, 0, 0), (4, 0.3, 3))
    scene = {"l": left, "r": right, "p": panel(x0=2.4)}
    r = face_on_wall(scene, "p", ("l", "r"), "front")
    assert r.applied, r.question
    assert_border_deep(r.scene["p"], right)
    # A panel over the joint of two walls: its border crosses the joint face, which hides nothing
    # (open_borders_hidden needs every sample deep in ONE neighbour) -> refused, scene unchanged.
    over = {"l": left, "r": right, "p": panel(x0=1.5)}
    r = face_on_wall(over, "p", ("l", "r"), "front")
    assert not r.applied and r.scene is over and r.question


def test_cluster_of_panels_with_joints():
    cluster = join(panel(x0=0.5, w=1.0), panel(x0=1.51, w=1.0))   # 10 mm joint
    scene = {"wall": WALL, "p": cluster}
    split = face_on_wall(scene, "p", "wall", "front")
    assert not split.applied and "splits into 2" in split.question and split.scene is scene
    closed = face_on_wall(scene, "p", "wall", "front", close_gaps_m=0.006)
    assert closed.applied, closed.question
    assert closed.notes["pieces"] == 1 and len(closed.scene["p"].triangles) == 10
    multi = face_on_wall(scene, "p", "wall", "front", allow_multi=True)
    assert multi.applied, multi.question
    assert multi.notes["pieces"] == 2 and len(multi.scene["p"].triangles) == 20


@pytest.mark.parametrize("seed", range(40))
def test_generated_panels_keep_border_deep_and_cost_10_tris(seed):
    """Invariant probe: every applied face has its whole open border >= embed inside the wall, 10 tris a rectangle."""
    rng = np.random.default_rng(seed)
    w, h = rng.uniform(0.2, 2.0, 2)
    x0, z0 = rng.uniform(0.05, 4 - w - 0.05), rng.uniform(0.05, 3 - h - 0.05)
    t, gap = rng.uniform(0.002, 0.06), rng.uniform(0.0, 0.1)
    side = int(rng.choice([-1, 1]))
    r = face_on_wall({"wall": WALL, "p": panel(x0, z0, w, h, t, gap, side)}, "p", "wall", "front")
    assert r.applied, r.question
    assert len(r.scene["p"].triangles) == 10
    assert_border_deep(r.scene["p"], WALL)


EMPTY = Mesh(np.zeros((0, 3)), np.zeros((0, 3), int))


@pytest.mark.parametrize("case, scene, walls, view, kw, needle", [
    ("unknown view", {"wall": WALL, "p": panel()}, "wall", "back", {}, "unknown view"),
    ("no wall", {"wall": WALL, "p": panel()}, (), "front", {}, "no wall"),
    ("wall missing", {"wall": WALL, "p": panel()}, "nope", "front", {}, "not another part"),
    ("wall is part", {"wall": WALL, "p": panel()}, "p", "front", {}, "not another part"),
    ("empty part", {"wall": WALL, "p": EMPTY}, "wall", "front", {}, "no faces"),
    ("empty wall", {"wall": EMPTY, "p": panel()}, "wall", "front", {}, "has no faces"),
    ("open wall", {"wall": box((0, 0, 0), (4, 0.3, 3), drop=("front",)), "p": panel()}, "wall", "front", {},
     "not a closed"),
    ("wall far away", {"wall": box((0, 5, 0), (4, 5.3, 3)), "p": panel()}, "wall", "front", {}, "neither side"),
    ("wall on both sides", {"a": box((0, -0.5, 0), (4, -0.1, 3)), "b": box((0, 0, 0), (4, 0.3, 3)),
                            "p": panel(gap=0.05)}, ("a", "b"), "front", {}, "both sides"),
    ("panel overhangs", {"wall": WALL, "p": panel(x0=2.0, w=2.3)}, "wall", "front", {}, "does not reach"),
    ("wrong view", {"wall": WALL, "p": panel()}, "wall", "top", {}, ""),
    ("embed below min", {"wall": WALL, "p": panel()}, "wall", "front", {"embed_m": 0.001}, "embed_m"),
    ("embed nan", {"wall": WALL, "p": panel()}, "wall", "front", {"embed_m": math.nan}, "embed_m"),
    ("embed bool", {"wall": WALL, "p": panel()}, "wall", "front", {"embed_m": True}, "embed_m"),
    ("reach inf", {"wall": WALL, "p": panel()}, "wall", "front", {"max_reach_m": math.inf}, "max_reach_m"),
    ("gaps too wide", {"wall": WALL, "p": panel()}, "wall", "front", {"close_gaps_m": 0.05}, "close_gaps_m"),
    ("reach too short", {"wall": WALL, "p": panel(gap=0.1)}, "wall", "front", {"max_reach_m": 0.1},
     ""),
])
def test_refusals_leave_scene_unchanged(case, scene, walls, view, kw, needle):
    r = face_on_wall(scene, "p", walls, view, **kw)
    assert not r.applied, case
    assert r.scene is scene and r.question
    assert needle in r.question, (case, r.question)


def test_nan_geometry_cannot_enter():
    with pytest.raises(ValueError, match="finite"):
        Mesh(np.array([[math.nan, 0, 0], [1, 0, 0], [0, 0, 1]]), np.array([[0, 1, 2]]))


def test_unknown_part_is_an_error():
    with pytest.raises(ValueError, match="unknown part"):
        face_on_wall({"wall": WALL}, "p", "wall", "front")


def test_embed_exactly_at_threshold_is_kept_and_border_meets_it():
    r = face_on_wall({"wall": WALL, "p": panel()}, "p", "wall", "front", embed_m=EMBED_MIN_M)
    assert r.applied, r.question
    assert_border_deep(r.scene["p"], WALL, EMBED_MIN_M)
