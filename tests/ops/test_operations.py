"""Operations under the invariants (cloud card C4: keep, embed into neighbour). All meshes are SYNTHETIC."""
import numpy as np
import pytest

from dt_ai.ops.invariants import Context
from dt_ai.ops.operations import OperationRefused, embed_into_neighbour, keep, run_operation
from tests.ops.test_invariants import box

WALL = box((0, 0, 0), (4, 0.3, 3))                       # front surface at y = 0, 300 mm thick
INTO_WALL = (0, 1, 0)


def decor_on_wall():
    """A 100 mm decor box standing on the wall's front surface (its back face touches y = 0)."""
    return {"wall": WALL, "decor": box((1, -0.1, 1), (2, 0.0, 2))}


def embed(depth, scene=None, direction=INTO_WALL, ctx=Context(embed_min_m=0.010)):
    scene = scene or decor_on_wall()
    return scene, run_operation(scene, "embed_into_neighbour", "decor",
                                lambda s: embed_into_neighbour(s, "decor", "wall", direction, depth), ctx,
                                {"neighbour": "wall", "depth_m": depth})


@pytest.mark.parametrize("depth", [0.010, 0.015, 0.020])
def test_embed_sinks_the_part_and_deletes_the_hidden_face(depth):
    scene, r = embed(depth)
    assert r.applied and r.report.passed and r.question is None
    assert r.notes == {"faces_before": 12, "faces_after": 10}          # the two triangles of the back face
    assert r.scene["decor"].vertices[:, 1].max() == pytest.approx(depth)    # back outline sits `depth` inside
    assert r.scene["wall"] is scene["wall"]                              # the neighbour is untouched


@pytest.mark.parametrize("direction", [(0, 3, 0), (0, 0.001, 0), (0, 5, 0.0)])
def test_embed_direction_is_a_direction_not_a_length(direction):
    _, r = embed(0.015, direction=direction)
    assert r.applied and r.scene["decor"].vertices[:, 1].max() == pytest.approx(0.015)


def test_the_input_scene_is_never_modified():
    scene = decor_on_wall()
    before = {k: (m.vertices.copy(), m.triangles.copy()) for k, m in scene.items()}
    embed(0.015, scene)
    for k, (v, t) in before.items():
        assert np.array_equal(scene[k].vertices, v) and np.array_equal(scene[k].triangles, t)


@pytest.mark.parametrize("depth", [0.005, 0.0099, 0.0201, 0.05, 0.0, -0.015])
def test_embed_depth_outside_10_to_20_mm_is_refused_with_a_question(depth):
    scene, r = embed(depth)
    assert not r.applied and r.report is None and r.scene is scene
    assert "mm is outside 10-20 mm" in r.question


def test_embed_that_hides_nothing_is_refused():
    far = {"wall": WALL, "decor": box((1, -1.1, 1), (2, -1.0, 2))}      # 1 m in front of the wall
    scene, r = embed(0.015, far)
    assert not r.applied and "they do not touch" in r.question and r.scene is far
    scene, r = embed(0.015, direction=(0, -1, 0))                       # sunk out of the wall, not into it
    assert not r.applied and "points out of the neighbour" in r.question


@pytest.mark.parametrize("kwargs,text", [({"neighbour": "nobody"}, "not another part"),
                                         ({"neighbour": "decor"}, "not another part"),
                                         ({"direction": (0, 0, 0)}, "non-zero")])
def test_embed_bad_arguments_are_refused(kwargs, text):
    args = {"neighbour": "wall", "direction": INTO_WALL, **kwargs}
    r = run_operation(decor_on_wall(), "embed_into_neighbour", "decor",
                      lambda s: embed_into_neighbour(s, "decor", args["neighbour"], args["direction"], 0.015))
    assert not r.applied and text in r.question


def test_embed_that_breaks_an_invariant_is_rolled_back():
    """A 20 mm thin neighbour: the sunk face sits 5 mm from its other side, less than the 10 mm embed minimum."""
    thin = {"wall": box((0, 0, 0), (4, 0.02, 3)), "decor": box((1, -0.1, 1), (2, 0.0, 2))}
    scene, r = embed(0.015, thin)
    assert not r.applied and r.scene is thin
    assert [b.name for b in r.report.broken] == ["open_borders_hidden"]
    assert "rolled back" in r.question and "open_borders_hidden" in r.question


def test_keep_passes_a_clean_part_and_stops_on_a_gnawed_one():
    clean = {"p": box((0, 0, 0), (1, 1, 1))}
    r = run_operation(clean, "keep", "p", lambda s: keep(s, "p"))
    assert r.applied and r.report.passed
    gnawed = {"p": box((0, 0, 0), (1, 1, 1), drop=("top",))}
    r = run_operation(gnawed, "keep", "p", lambda s: keep(s, "p"))
    assert not r.applied and r.scene is gnawed and "keep on p broke the invariants" in r.question


def test_unknown_part_is_an_error_not_a_question():
    with pytest.raises(ValueError, match="unknown part"):
        run_operation({"p": box((0, 0, 0), (1, 1, 1))}, "keep", "q", lambda s: s)
