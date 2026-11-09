"""new-case: object-local clearance witnesses persist across face permutations and translations.

Extends `test_geometry_mutation.py::test_clearance_evidence_provenance` (which covers the two
unchanged forward/reverse mesh orders) with the review's 32 combinations: an independent local
face permutation for `contact_a` and `contact_b`, forward/reverse mesh order and panel translations
0 / 0.375 / -250 / 10000 m. Every expected object-local index is derived from the frozen old-to-new
face permutation, never parsed out of the returned pair; each reported endpoint is resolved back to
its source triangle and its vertex set compared against the geometric ground truth. A task-local
in-memory mutation restores the pre-fix flattened/global face identity and is shown to defeat these
assertions, characterising (not fabricating) the regression the assertions guard against.
"""
import copy
import importlib.util
from pathlib import Path

import numpy as np
import pytest


def evaluator():
    path = Path(__file__).resolve().parents[2] / "tools/evals_geometry_mutation.py"
    assert path.is_file(), "geometry mutation evaluator must exist"
    spec = importlib.util.spec_from_file_location("geometry_mutation", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def ev():
    return evaluator()


@pytest.fixture(scope="module")
def corpus(ev):
    return ev.corpus()


def _mesh(scene, name):
    return next(m for m in scene["meshes"] if m["name"] == name)


def _permute(triangles, reverse):
    """Frozen old-to-new face index permutation for a triangle list (reverse flips the order)."""
    n = len(triangles)
    old_to_new = {i: (n - 1 - i) if reverse else i for i in range(n)}
    new_triangles = list(reversed(triangles)) if reverse else list(triangles)
    return old_to_new, new_triangles


def _translate_along_x(mesh, delta):
    mesh["vertices"] = [[x + delta, y, z] for x, y, z in mesh["vertices"]]


def _permute_and_translate(scene, reverse_a, reverse_b, translation, mesh_reverse):
    """Deep-copied scene with both contact panels permuted and translated; returns (scene, mappings)."""
    scene = copy.deepcopy(scene)
    mappings = {}
    for name, reverse in (("contact_a", reverse_a), ("contact_b", reverse_b)):
        mesh = _mesh(scene, name)
        old_to_new, mesh["triangles"] = _permute(mesh["triangles"], reverse)
        mappings[name] = old_to_new
        _translate_along_x(mesh, translation)
    if mesh_reverse:
        scene["meshes"].reverse()
    return scene, mappings


def _vertex_set(scene, name, index):
    mesh = _mesh(scene, name)
    return frozenset(tuple(mesh["vertices"][i]) for i in mesh["triangles"][index])


def _contact_half_vertex_sets(translation):
    """Ground-truth unit-quad halves in the XY plane at z=0, x in [50+t, 51+t], y in [0, 1].

    Independent of the scene's triangle ordering: old index 0 = lower-right half, old index 1 =
    upper-left half (the corpus `quad()` builds triangles [0,1,2] then [0,2,3]).
    """
    x0 = 50.0 + translation
    lower_right = frozenset(((x0, 0.0, 0.0), (x0 + 1.0, 0.0, 0.0), (x0 + 1.0, 1.0, 0.0)))
    upper_left = frozenset(((x0, 0.0, 0.0), (x0 + 1.0, 1.0, 0.0), (x0, 1.0, 0.0)))
    return {0: lower_right, 1: upper_left}


def _assert_object_local_identity(pairs, scene, expected_pairs):
    """Every reported pair must be an object-local witness matching the permutation-derived set."""
    inventory = {m["name"]: len(m["triangles"]) for m in scene["meshes"]}
    reported = {frozenset((tuple(p["a"]), tuple(p["b"]))) for p in pairs}
    assert reported == expected_pairs, (reported, expected_pairs)
    for pair in pairs:
        for endpoint in (pair["a"], pair["b"]):
            name, index = endpoint
            assert name in inventory, endpoint
            assert 0 <= index < inventory[name], endpoint


TRANSLATIONS = [0.0, 0.375, -250.0, 10000.0]


@pytest.mark.parametrize("mesh_reverse", [False, True])
@pytest.mark.parametrize("reverse_b", [False, True])
@pytest.mark.parametrize("reverse_a", [False, True])
@pytest.mark.parametrize("translation", TRANSLATIONS)
def test_false_contact_clearance_identity(ev, corpus, reverse_a, reverse_b, mesh_reverse, translation):
    base, mutants = corpus
    scene, mappings = _permute_and_translate(
        mutants["false_contact"]["scene"], reverse_a, reverse_b, translation, mesh_reverse)
    before = copy.deepcopy(scene)
    result = ev.run_checker("clearance", scene)
    # The checker must not mutate its input scene.
    assert scene == before
    assert result["status"] == "fail"
    assert result["value"] == 2
    pairs = result["details"]["pairs"]
    assert len(pairs) == 2
    assert all(p["distance_m"] == 0 for p in pairs)
    assert all(p["projected_area_m2"] == 0.5 for p in pairs)
    assert all(p["same_direction"] is True for p in pairs)
    # Expected object-local indices from the frozen old-to-new permutation, never from the pairs.
    perm_a, perm_b = mappings["contact_a"], mappings["contact_b"]
    expected = {
        frozenset((("contact_a", perm_a[0]), ("contact_b", perm_b[0]))),
        frozenset((("contact_a", perm_a[1]), ("contact_b", perm_b[1]))),
    }
    _assert_object_local_identity(pairs, scene, expected)
    # Resolve reported endpoints into source triangles and independently compare vertex sets.
    halves = _contact_half_vertex_sets(translation)
    for pair in pairs:
        a_verts = _vertex_set(scene, pair["a"][0], pair["a"][1])
        b_verts = _vertex_set(scene, pair["b"][0], pair["b"][1])
        assert a_verts == b_verts
        assert a_verts in set(halves.values())


@pytest.mark.parametrize("mesh_reverse", [False, True])
@pytest.mark.parametrize("reverse_b", [False, True])
@pytest.mark.parametrize("reverse_a", [False, True])
@pytest.mark.parametrize("translation", TRANSLATIONS)
def test_clean_separated_panels_remain_clean(ev, corpus, reverse_a, reverse_b, mesh_reverse, translation):
    base, mutants = corpus
    scene, _ = _permute_and_translate(base, reverse_a, reverse_b, translation, mesh_reverse)
    before = copy.deepcopy(scene)
    result = ev.run_checker("clearance", scene)
    assert scene == before
    assert result["status"] == "pass"
    assert result["value"] == 0
    assert result["details"]["pairs"] == []


def test_reset_to_original_restores_full_result(ev, corpus):
    base, mutants = corpus
    original = copy.deepcopy(mutants["false_contact"]["scene"])
    expected = ev.run_checker("clearance", copy.deepcopy(original))
    # Perturb a copy (reverse both panels, translate far, reverse mesh order), then reset.
    scene, _ = _permute_and_translate(original, True, True, 10000.0, True)
    assert ev.run_checker("clearance", scene)["status"] == "fail"
    assert ev.run_checker("clearance", copy.deepcopy(original)) == expected
    assert {frozenset((tuple(p["a"]), tuple(p["b"]))) for p in expected["details"]["pairs"]} == {
        frozenset((("contact_a", 0), ("contact_b", 0))),
        frozenset((("contact_a", 1), ("contact_b", 1))),
    }


def test_duplicate_faces_reversed_triangle_order_remaps_ids(ev, corpus):
    base, mutants = corpus
    scene = copy.deepcopy(mutants["duplicate_faces"]["scene"])
    mesh = _mesh(scene, "normal_target")
    n = len(mesh["triangles"])
    assert n == 13
    old_top, old_dup = 11, 12  # original top face and its +0.001 m duplicate, before the reversal
    remap = {i: n - 1 - i for i in range(n)}  # frozen reversal: old index i -> n-1-i
    mesh["triangles"] = list(reversed(mesh["triangles"]))
    before = copy.deepcopy(scene)
    result = ev.run_checker("clearance_target", scene)
    assert scene == before
    assert result["status"] == "fail"
    assert result["value"] == 1
    pair, = result["details"]["pairs"]
    assert {tuple(pair["a"]), tuple(pair["b"])} == {
        ("normal_target", remap[old_top]), ("normal_target", remap[old_dup])}
    assert pair["distance_m"] == pytest.approx(0.001)
    assert pair["projected_area_m2"] == 0.5
    # Geometry unchanged: the remapped faces still point at the same vertices (duplicate +0.001 m).
    top_verts = _vertex_set(scene, "normal_target", remap[old_top])
    dup_verts = _vertex_set(scene, "normal_target", remap[old_dup])
    assert np.allclose(np.asarray(sorted(top_verts)), np.asarray(sorted(dup_verts)) - [0, 0, 0.001])


def test_flattened_global_ids_defeat_identity_assertions(ev, corpus, monkeypatch):
    base, mutants = corpus
    scene = copy.deepcopy(mutants["false_contact"]["scene"])
    expected = {
        frozenset((("contact_a", 0), ("contact_b", 0))),
        frozenset((("contact_a", 1), ("contact_b", 1))),
    }
    # Unchanged source -> the identity assertions hold (green).
    real = ev.run_checker("clearance", copy.deepcopy(scene))
    _assert_object_local_identity(real["details"]["pairs"], scene, expected)

    # Task-local in-memory mutation restoring the pre-fix flattened/global face identity
    # (every face labelled with scope[0] and a global Soup index; commit e88ad59).
    def flattened(name, scene):
        scope = ["contact_a", "contact_b"] if name == "clearance" else ["normal_target"]
        soup = ev.scoped(scene, scope)
        faces = [{"object": scope[0], "index": i, "points": t.tolist()} for i, t in enumerate(soup.corners())]
        hits = ev.near_parallel_overlaps(faces, 0.005)
        return ev.checks.result(name, not hits, len(hits), 0, {"pairs": hits})

    monkeypatch.setattr(ev, "run_checker", flattened)
    flattened_result = ev.run_checker("clearance", copy.deepcopy(scene))
    with pytest.raises(AssertionError):
        _assert_object_local_identity(flattened_result["details"]["pairs"], scene, expected)
