"""new-case: NPM opacity swaps under the kernel invariants. All meshes are SYNTHETIC."""
import numpy as np
import pytest

from dt_ai.ops import operations
from dt_ai.ops.invariants import Context, Mesh, no_see_through_hole
from dt_ai.ops.silhouette import silhouette, silhouette_deviations
import shapely
from tests.ops.test_invariants import box
from tests.ops.test_primitive import join


def railing(angle=0, depth=0.05, count=16):
    """Posts + rails + evenly spaced balusters; 240 triangles at count=16."""
    y = depth / 2
    pieces = [box((0, -y, 0), (.05, y, 1.2)), box((1.95, -y, 0), (2, y, 1.2)),
              box((.05, -y, 0), (1.95, y, .05)), box((.05, -y, 1.15), (1.95, y, 1.2))]
    pieces += [box((x - .015, -y, .05), (x + .015, y, 1.15)) for x in np.linspace(.12, 1.88, count)]
    mesh = join(*pieces)
    c, s = np.cos(np.deg2rad(angle)), np.sin(np.deg2rad(angle))
    rot = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    return Mesh(mesh.vertices @ rot.T, mesh.triangles)


def snapshot(scene):
    return {p: (m.vertices.copy(), m.triangles.copy()) for p, m in scene.items()}


def assert_unchanged(scene, before):
    assert set(scene) == set(before)
    for p, (v, t) in before.items():
        np.testing.assert_array_equal(scene[p].vertices, v)
        np.testing.assert_array_equal(scene[p].triangles, t)


@pytest.mark.parametrize("angle", [0, 30])
def test_railing_becomes_one_midplane_quad_without_mutating_input(angle):
    scene = {"railing": railing(angle)}
    before = snapshot(scene)
    ctx = Context(opacity_parts=frozenset({"railing"}))
    result = operations.run_operation(scene, "to_opacity_plane", "railing",
                                      lambda s: operations.to_opacity_plane(s, "railing"), ctx)
    assert result.applied, result.question
    assert result.report.passed and result.question is None
    assert result.notes == {"faces_before": 240, "faces_after": 2}
    plane = result.scene["railing"]
    assert plane.vertices.shape == (4, 3) and plane.triangles.shape == (2, 3)
    normal = np.array([-np.sin(np.deg2rad(angle)), np.cos(np.deg2rad(angle)), 0])
    assert plane.vertices @ normal == pytest.approx(np.zeros(4), abs=1e-12)
    tangent = np.array([normal[1], -normal[0], 0])
    assert sorted(plane.vertices @ tangent) == pytest.approx([0, 0, 2, 2], abs=1e-12)
    assert sorted(plane.vertices[:, 2]) == pytest.approx([0, 0, 1.2, 1.2], abs=1e-12)
    assert max(silhouette_deviations(scene["railing"], plane, .07 / 32).values()) <= .07
    assert ctx.opacity_parts == frozenset({"railing"})
    assert_unchanged(scene, before)


def test_planner_selects_largest_savings_only_until_budget_fits():
    scene = {"small": railing(count=4), "large": railing(count=16), "medium": railing(count=10)}
    before = snapshot(scene)
    # 96 + 240 + 168 = 504; save 238 + 166, leaving 100.
    assert operations.plan_opacity_swaps(scene, ["small", "large", "medium"], 100) == [
        ("large", 238), ("medium", 166)]
    assert_unchanged(scene, before)


def test_unreachable_budget_returns_all_swaps_with_a_note():
    scene = {"a": railing(), "b": railing(count=10), "body": box((5, 0, 0), (6, 1, 1))}
    with pytest.warns(UserWarning, match="unreachable.*16.*budget 1"):
        assert operations.plan_opacity_swaps(scene, ["a", "b"], 1) == [("a", 238), ("b", 166)]


@pytest.mark.parametrize("kind,text", [("empty", "empty"), ("one", "2 triangles or fewer"),
                                       ("two", "2 triangles or fewer"), ("thick", "0.200 m thick"),
                                       ("silhouette", "silhouette")])
def test_refusals_ask_a_question_and_leave_the_input_unchanged(kind, text):
    mesh = railing()
    if kind == "empty":
        mesh = Mesh(np.empty((0, 3)), np.empty((0, 3), int))
    elif kind in {"one", "two"}:
        mesh = Mesh(mesh.vertices, mesh.triangles[:1 if kind == "one" else 2])
    elif kind == "thick":
        mesh = railing(depth=.2)
    elif kind == "silhouette":
        mesh = railing(count=1)  # one central baluster leaves huge gaps in the front view
    scene = {"p": mesh}
    before = snapshot(scene)
    with pytest.raises(operations.OperationRefused, match=text) as exc:
        operations.to_opacity_plane(scene, "p")
    assert str(exc.value).endswith("?")
    result = operations.run_operation(scene, "to_opacity_plane", "p", lambda s: operations.to_opacity_plane(s, "p"))
    assert not result.applied and result.report is None and result.scene is scene
    assert text in result.question
    assert_unchanged(scene, before)


def test_unregistered_opacity_plane_rolls_back_open_borders_and_back_faces():
    scene = {"p": railing()}
    before = snapshot(scene)
    result = operations.run_operation(scene, "to_opacity_plane", "p", lambda s: operations.to_opacity_plane(s, "p"))
    assert not result.applied and result.scene is scene and "rolled back" in result.question
    assert {"open_borders_hidden", "no_visible_back_faces"} <= {r.name for r in result.report.broken}
    assert_unchanged(scene, before)


def test_old_railing_gap_now_covered_by_opacity_is_not_a_lost_pixel():
    scene = {"p": railing(), "behind": box((0, .3, 0), (2, .5, 1.2))}
    after = operations.to_opacity_plane(scene, "p")
    assert not shapely.covers(silhouette(scene["p"], 1), shapely.Point(.18, .6))
    assert shapely.covers(silhouette(after["p"], 1), shapely.Point(.18, .6))
    ctx = Context(opacity_parts=frozenset({"p"}))
    check = no_see_through_hole(scene, after, ctx)
    assert check.passed and check.count == 0 and ctx.lost_pixels_max == 0
    result = operations.run_operation(scene, "to_opacity_plane", "p", lambda s: operations.to_opacity_plane(s, "p"), ctx)
    assert result.applied and result.report.passed
    assert result.scene["behind"] is scene["behind"]


def test_new_hole_elsewhere_in_same_swap_is_still_rolled_back():
    scene = {"p": railing(), "wall": box((4, -.1, 0), (5, .1, 1.2))}
    before = snapshot(scene)
    def swap_and_break(s):
        after = operations.to_opacity_plane(s, "p")
        after["wall"] = box((4, -.1, 0), (5, .1, 1.2), drop=("front", "back"))
        return after
    # A second registered part must not acquire a blanket exemption.
    ctx = Context(opacity_parts=frozenset({"p", "wall"}))
    result = operations.run_operation(scene, "to_opacity_plane", "p", swap_and_break, ctx)
    assert not result.applied and result.scene is scene
    holes = [r for r in result.report.broken if r.name == "no_see_through_hole"]
    assert len(holes) == 1 and holes[0].count > 0
    assert_unchanged(scene, before)


@pytest.mark.parametrize("mode", ["removed", "empty", "one_triangle", "unchanged"])
def test_registration_does_not_exempt_non_replacement_holes(mode):
    source = railing()
    scene = {"p": source, "other": box((4, -.1, 0), (5, .1, 1.2))}
    after = dict(scene)
    if mode == "removed":
        del after["p"]
    elif mode == "empty":
        after["p"] = Mesh(source.vertices, np.empty((0, 3), int))
    elif mode == "one_triangle":
        plane = operations.to_opacity_plane(scene, "p")["p"]
        after["p"] = Mesh(plane.vertices, plane.triangles[:1])
    else:
        del after["other"]
    check = no_see_through_hole(scene, after, Context(opacity_parts=frozenset({"p"})))
    assert not check.passed and check.count > 0


@pytest.mark.parametrize("budget", [504, 505, 1000])
def test_budget_already_met_leaves_all_candidates_geometry(budget):
    scene = {"small": railing(count=4), "large": railing(count=16), "medium": railing(count=10)}
    assert operations.plan_opacity_swaps(scene, scene, budget) == []


def test_planning_deduplicates_candidates_and_does_not_claim_nonpositive_savings():
    scene = {"p": railing(), "plane": Mesh(np.zeros((4, 3)), np.array([[0, 1, 2], [0, 2, 3]]))}
    assert operations.plan_opacity_swaps(scene, ["p", "p", "plane"], 4) == [("p", 238)]
    assert operations.plan_opacity_swaps({}, [], 0) == []
    with pytest.warns(UserWarning, match="unreachable"):
        assert operations.plan_opacity_swaps(scene, [], 0) == []
    with pytest.raises(ValueError, match="non-negative"):
        operations.plan_opacity_swaps(scene, scene, -1)


@pytest.mark.parametrize("seed", range(12))
def test_generated_pca_quad_purity_and_context_probe(seed):
    rng = np.random.default_rng(seed)
    rotation, _ = np.linalg.qr(rng.normal(size=(3, 3)))
    shift = rng.uniform(-10, 10, size=3)
    source = railing()
    moved = Mesh(source.vertices @ rotation.T + shift, source.triangles)
    scene = {"p": moved}
    before = snapshot(scene)
    try:
        plane = operations.to_opacity_plane(scene, "p")["p"]
    except operations.OperationRefused as exc:
        # Existing polygon fallback conservatively refuses sub-grid slivers; preserve that policy.
        assert "silhouette" in str(exc) and str(exc).endswith("?")
        result = operations.run_operation(scene, "to_opacity_plane", "p", lambda s: operations.to_opacity_plane(s, "p"))
        assert not result.applied and result.scene is scene and result.report is None
        assert_unchanged(scene, before)
        return
    local = (plane.vertices - shift) @ rotation
    assert local[:, 1] == pytest.approx(np.zeros(4), abs=1e-12)
    assert sorted(local[:, 0]) == pytest.approx([0, 0, 2, 2], abs=1e-12)
    assert sorted(local[:, 2]) == pytest.approx([0, 0, 1.2, 1.2], abs=1e-12)
    assert len(plane.triangles) == 2 and len(plane.vertices) == 4
    ctx = Context(opacity_parts=frozenset({"p"}), resolution=12)
    accepted = operations.run_operation(scene, "to_opacity_plane", "p", lambda s: operations.to_opacity_plane(s, "p"), ctx)
    assert accepted.applied, accepted.question
    rejected = operations.run_operation(scene, "to_opacity_plane", "p", lambda s: operations.to_opacity_plane(s, "p"),
                                        Context(resolution=12))
    assert not rejected.applied and rejected.scene is scene
    assert_unchanged(scene, before)


@pytest.mark.parametrize("seed", range(12))
def test_generated_other_first_hit_hole_is_not_exempt(seed):
    rng = np.random.default_rng(seed)
    angle = float(rng.uniform(0, 360))
    source = railing(angle=angle)
    wall_x = float(rng.uniform(4, 6))
    scene = {"p": source, "other": box((wall_x, 0, 0), (wall_x + 1, 1, 1))}
    before = snapshot(scene)
    after = operations.to_opacity_plane(scene, "p")
    normal = np.array([-np.sin(np.deg2rad(angle)), np.cos(np.deg2rad(angle)), 0])
    assert after["p"].vertices @ normal == pytest.approx(np.zeros(4), abs=1e-12)
    assert len(after["p"].triangles) == 2 and len(after["p"].vertices) == 4
    assert after["other"] is scene["other"]
    assert_unchanged(scene, before)
    # Remove an unrelated closed part, even if it is also registered for opacity later.
    del after["other"]
    ctx = Context(opacity_parts=frozenset(scene), resolution=12)
    result = no_see_through_hole(scene, after, ctx)
    assert not result.passed and result.count > 0


@pytest.mark.parametrize("angle", [0, 30])
@pytest.mark.parametrize("combined", [False, True])
@pytest.mark.parametrize("kind", ["half_quad", "translated_quad", "tiny_quad"])
def test_invalid_opacity_replacement_cannot_waive_lost_pixels(kind, combined, angle):
    """Review P1: invalid swaps never inherit the valid swap's thickness exemption."""
    scene = {"p": railing(angle)}
    if combined:
        control = railing(30)
        scene["control"] = Mesh(control.vertices + [4, 0, 0], control.triangles)
    before = snapshot(scene)
    after = operations.to_opacity_plane(scene, "p")
    q = after["p"]
    if kind == "half_quad":
        invalid = Mesh(q.vertices, np.array([[0, 1, 2], [2, 1, 0]]))
    elif kind == "translated_quad":
        invalid = Mesh(q.vertices + [0, 0, 10], q.triangles)
    else:
        invalid = Mesh(q.vertices.mean(0) + (q.vertices - q.vertices.mean(0)) * .01, q.triangles)
    after["p"] = invalid
    if combined:
        after = operations.to_opacity_plane(after, "control")
    ctx = Context(opacity_parts=frozenset(scene), resolution=24)
    check = no_see_through_hole(scene, after, ctx)
    assert not check.passed and check.count > 0
    result = operations.run_operation(scene, "probe_invalid_swap", "p", lambda _: after, ctx)
    assert not result.applied and result.scene is scene and "rolled back" in result.question
    assert "no_see_through_hole" in {r.name for r in result.report.broken}
    assert_unchanged(scene, before)


def test_generated_greedy_prefix_probe():
    """Exhaustive independent prefix oracle: 27 candidate-count triples x 8 budgets = 216 plans."""
    import itertools
    import warnings
    for counts in itertools.product((2, 5, 11), repeat=3):
        scene = {str(i): Mesh(np.zeros((3, 3)), np.tile([[0, 1, 2]], (n, 1))) for i, n in enumerate(counts)}
        before = snapshot(scene)
        for budget in (0, 2, 4, 6, 10, 16, 24, 34):
            total = sum(counts)
            ordered = sorted(range(3), key=lambda i: -counts[i])
            expected = []
            for i in ordered:
                if total <= budget:
                    break
                if counts[i] > 2:
                    expected.append((str(i), counts[i] - 2))
                    total -= counts[i] - 2
            with warnings.catch_warnings(record=True) as notes:
                warnings.simplefilter("always")
                actual = operations.plan_opacity_swaps(scene, ["0", "1", "2", "0"], budget)
            assert actual == expected
            assert bool(notes) == (total > budget)
            assert_unchanged(scene, before)
