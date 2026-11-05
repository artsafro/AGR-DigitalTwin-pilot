"""Kernel invariants relative to the source [D197] (#968): an op passes when it adds no NEW violator.

Every mesh here is SYNTHETIC. The source of each test already violates an invariant (an open, gnawed box, flipped
normals or a close overlap); the pre-existing violators are the baseline and only new ones fail the op.
"""
import numpy as np
import pytest

from dt_ai.ops.invariants import Context, Mesh, check_operation, no_visible_back_faces
from dt_ai.ops.operations import keep, run_operation
from tests.ops.test_invariants import box


def gnawed_source():
    """'body' is a box without its top: 4 open border edges seen from above and its inside (back faces) visible."""
    return {"body": box((0, 0, 0), (2, 2, 1), drop=("top",)), "decor": box((3, 0, 0), (3.5, 0.5, 0.5))}


def _by_name(report):
    return {r.name: r for r in report.results}


def test_absolute_mode_fails_the_untouched_gnawed_source():
    src = gnawed_source()
    rep = check_operation(src, dict(src), ["body"])
    assert not rep.passed
    assert {r.name for r in rep.broken} == {"open_borders_hidden", "no_visible_back_faces"}


def test_keep_on_a_source_with_preexisting_violators_passes_and_reports_the_baseline():
    src = gnawed_source()
    rep = check_operation(src, dict(src), ["body"], Context(source=src))
    assert rep.passed
    r = _by_name(rep)
    assert r["open_borders_hidden"].baseline == 4 and r["open_borders_hidden"].after == 4
    assert r["open_borders_hidden"].count == 0
    assert r["no_visible_back_faces"].baseline > 0
    assert r["no_visible_back_faces"].after == r["no_visible_back_faces"].baseline
    assert r["no_visible_back_faces"].count == 0
    d = {x["name"]: x for x in rep.to_dict()["results"]}
    assert d["no_visible_back_faces"]["baseline"] == r["no_visible_back_faces"].baseline
    assert d["no_visible_back_faces"]["new"] == 0 and d["open_borders_hidden"]["after"] == 4


def test_run_operation_keep_is_applied_in_relative_mode_and_rolled_back_in_absolute():
    src = gnawed_source()
    assert not run_operation(src, "keep", "body", lambda sc: keep(sc, "body")).applied
    res = run_operation(src, "keep", "body", lambda sc: keep(sc, "body"), Context(source=src))
    assert res.applied and res.report.passed


def test_op_that_adds_a_violator_fails_and_names_the_new_element():
    src = gnawed_source()
    after = {**src, "decor": box((3, 0, 0), (3.5, 0.5, 0.5), drop=("top",))}
    rep = check_operation(src, after, ["decor"], Context(source=src))
    assert not rep.passed
    r = _by_name(rep)
    assert r["open_borders_hidden"].count == 4 and r["open_borders_hidden"].baseline == 4
    assert all(o.startswith("decor: edge") for o in r["open_borders_hidden"].offenders)
    assert r["no_visible_back_faces"].count > 0
    assert all("['decor']" in o for o in r["no_visible_back_faces"].offenders)
    assert r["no_visible_back_faces"].after == r["no_visible_back_faces"].baseline + r["no_visible_back_faces"].count


def test_new_violator_on_the_part_that_already_violates_is_still_new():
    src = gnawed_source()
    after = {**src, "body": box((0, 0, 0), (2, 2, 1), drop=("top", "front"))}
    rep = check_operation(src, after, ["body"], Context(source=src))
    r = _by_name(rep)
    assert not rep.passed
    assert r["open_borders_hidden"].count > 0 and r["open_borders_hidden"].baseline == 4


def test_fixing_a_baseline_violator_passes_with_after_below_baseline():
    src = gnawed_source()
    after = {**src, "body": box((0, 0, 0), (2, 2, 1))}
    rep = check_operation(src, after, ["body"], Context(source=src))
    r = _by_name(rep)
    assert rep.passed
    assert r["open_borders_hidden"].after == 0 and r["open_borders_hidden"].baseline == 4
    assert r["no_visible_back_faces"].after == 0 < r["no_visible_back_faces"].baseline


def test_split_baseline_border_edge_is_not_new():
    """A pre-existing open border cut into two collinear pieces is the same border, not a new violator."""
    v = np.array([(0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0)], float)
    src = {"plate": Mesh(v, np.array([(0, 1, 2), (0, 2, 3)]))}
    v2 = np.vstack([v, [(1, 0, 0)]])
    after = {"plate": Mesh(v2, np.array([(0, 4, 3), (4, 1, 2), (4, 2, 3)]))}
    rep = check_operation(src, after, ["plate"], Context(source=src))
    r = _by_name(rep)
    assert r["open_borders_hidden"].after == 5 and r["open_borders_hidden"].baseline == 4
    assert r["open_borders_hidden"].count == 0


def test_flipped_source_part_is_baseline_a_second_flipped_part_is_new():
    src = {"a": box((0, 0, 0), (1, 1, 1), flip=True), "b": box((2, 0, 0), (3, 1, 1))}
    ctx = Context(source=src)
    assert check_operation(src, dict(src), ["b"], ctx).passed
    after = {**src, "b": box((2, 0, 0), (3, 1, 1), flip=True)}
    rep = check_operation(src, after, ["b"], ctx)
    bf = _by_name(rep)["no_visible_back_faces"]
    assert not bf.passed and bf.count > 0
    assert all("['b']" in o for o in bf.offenders)


def test_moving_a_clean_part_keeps_the_baseline_and_passes():
    src = gnawed_source()
    after = {**src, "decor": box((3, 1, 0), (3.5, 1.5, 0.5))}
    rep = check_operation(None, after, ["decor"], Context(source=src))   # the vacated spot is the hole check's job
    assert rep.passed, rep.to_dict()


def test_close_overlap_in_the_source_is_baseline_a_new_pair_fails():
    # two co-directional plates 2 mm apart (z-fighting); registered as opacity parts so only the overlap counts
    a = Mesh(np.array([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], float), np.array([(0, 1, 2), (0, 2, 3)]))
    b = Mesh(a.vertices + [0, 0, 0.002], a.triangles)
    src = {"a": a, "b": b}
    ctx = Context(source=src, opacity_parts=frozenset({"a", "b", "c"}))
    keep_rep = check_operation(src, dict(src), ["a"], ctx)
    ov = _by_name(keep_rep)["no_close_overlap"]
    assert ov.baseline > 0 and ov.count == 0 and ov.passed
    c = Mesh(a.vertices + [5, 0, 0], a.triangles)
    d = Mesh(a.vertices + [5, 0, 0.003], a.triangles)
    after = {**src, "c": c, "d": d}
    ctx2 = Context(source=src, opacity_parts=frozenset({"a", "b", "c", "d"}))
    rep = check_operation(src, after, ["c"], ctx2)
    ov = _by_name(rep)["no_close_overlap"]
    assert not ov.passed and ov.count > 0
    assert all("c#" in o for o in ov.offenders)


def test_empty_source_baseline_is_absolute():
    src = gnawed_source()
    rep = check_operation(src, dict(src), ["body"], Context(source={}))
    assert not rep.passed
    r = _by_name(rep)
    assert r["open_borders_hidden"].baseline == 0 and r["open_borders_hidden"].count == 4


def test_source_must_be_a_scene_of_meshes():
    src = gnawed_source()
    with pytest.raises(TypeError, match="source"):
        check_operation(src, dict(src), ["body"], Context(source={"body": "not a mesh"}))


def test_absolute_mode_report_has_no_baseline_fields():
    src = {"x": box((0, 0, 0), (1, 1, 1))}
    d = check_operation(src, dict(src), ["x"]).to_dict()
    assert all("baseline" not in r for r in d["results"])


def test_back_face_pixels_use_one_frame_for_source_and_after():
    """Growing the scene changes the probe frame; the baseline must be re-measured on the common frame."""
    src = gnawed_source()
    after = {**src, "far": box((30, 0, 0), (31, 1, 1))}
    rep = check_operation(src, after, ["far"], Context(source=src))
    assert rep.passed, rep.to_dict()
    assert _by_name(rep)["no_visible_back_faces"].baseline != no_visible_back_faces(src).count


@pytest.mark.parametrize("seed", range(12))
def test_probe_random_extra_drop_fails_iff_it_adds_violators(seed):
    """Brute-force probe: source = closed box A with random faces dropped + clean box B; after = the same plus
    random extra drops on B. Zero extra drops -> pass; any extra drop on the clean B -> fail naming B."""
    rng = np.random.default_rng(seed)
    names = ["bottom", "top", "front", "back", "left", "right"]
    drop_a = tuple(rng.choice(names, size=rng.integers(1, 4), replace=False))
    drop_b = tuple(rng.choice(names, size=rng.integers(0, 3), replace=False))
    src = {"A": box((0, 0, 0), (1, 1, 1), drop=drop_a), "B": box((2, 0, 0), (3, 1, 1))}
    after = {**src, "B": box((2, 0, 0), (3, 1, 1), drop=drop_b)}
    rep = check_operation(src, after, ["B"], Context(source=src))
    assert rep.passed == (len(drop_b) == 0), (drop_a, drop_b, rep.to_dict())
    if drop_b:
        ob = _by_name(rep)["open_borders_hidden"]
        assert ob.count > 0 and all(o.startswith("B: edge") for o in ob.offenders)
