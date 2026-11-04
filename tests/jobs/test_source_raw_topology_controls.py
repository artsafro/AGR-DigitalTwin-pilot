"""new-case: characterization of raw face-index handling in Source QA helpers (pilot #658).

Every assertion records CURRENT helper behavior, not approved policy and not a
passed package. Surprising successes (wrapped negative source indices, a
3-corner area of a delivered quad) are witnesses only. main(), DCC, Image/ZIP
and real deliveries are not exercised. Baseline is GREEN; no historical RED.

Acceptance table (unit square (0,0,0),(1,0,0),(1,1,0),(0,1,0); shift 0;
plain finish A; delivery [[0,1,2],[0,2,3]] unless stated). Oracles are literal
numbers (square 1, each half-triangle 0.5), not helper output.

| input | measured legacy observation | test |
| clean source [[0,1,2,3]] | owners [(0,),(0,)], tri [.5,.5], src area [1], ok true, A | test_control |
| source [[-4,-3,-2,-1]] | same as control, assign ['A'] | test_negative_source_wraps |
| source [[True,False,2,3]],[[]],[[0]],[[0,1]],[[0,0,1]] | src area [0], owners empty, ok false, unmatched 2, not_covered 0, ['A'] | test_degenerate_source |
| source index 4 / 0.0 | IndexError / TypeError | test_source_index_errors |
| delivered [[0,1,2,3]] | tri [.5], whole area 1, owners [(0,)], ok false, not_covered 1, mesh passed true | test_lone_quad |
| delivered [[0,1,2,3],[0,2,3]] | tri [.5,.5], whole [1,.5], ok true, mesh passed false, no raise | test_quad_plus_half |
| delivered negative/bool/float/repeated/short | mesh_report ValueError (before finish report) | test_delivered_bad_faces_raise |
"""

import copy
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "jobs" / "TEC26-OKS" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import finish_map  # noqa: E402
import qa_packages  # noqa: E402
from dt_ai.ops import inv_xview  # noqa: E402

SQ = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]]
SHIFT = [0.0, 0.0, 0.0]
SPEC = {"source_ids": {"1": {"finish": "A"}}, "zero_m": 0.0}
TRIS = [[0, 1, 2], [0, 2, 3]]


def _checked(fn, *args):
    """Deep-copy every argument and compare in finally, including when fn raises."""
    saved = copy.deepcopy(args)
    try:
        return fn(*args)
    finally:
        assert args == saved


def _finish(src_f, out_f):
    owners = _checked(qa_packages.match_source_faces, SQ, src_f, SQ, out_f, SHIFT)
    t = _checked(qa_packages.tri_areas, SQ, out_f)
    p = _checked(qa_packages.poly_areas, SQ, src_f)
    expected = ["A"]
    delivered = ["A"] * len(owners)
    rep = _checked(qa_packages.source_finish_report, expected, src_f, owners, delivered, t, p)
    return owners, t, p, rep


def _assign(src_f):
    return _checked(finish_map.assign_finishes, SQ, src_f, [1], SPEC)


def _mesh(vertices, faces):
    return _checked(inv_xview.mesh_report, vertices, faces, "VPM")


def _poly(vertices, faces):
    return _checked(qa_packages._poly_geo, vertices, faces)


def _frozen(fn, src_f, out_f):
    v, s, o = copy.deepcopy(SQ), copy.deepcopy(src_f), copy.deepcopy(out_f)
    shift, spec = copy.deepcopy(SHIFT), copy.deepcopy(SPEC)
    try:
        return fn(src_f, out_f)
    finally:
        assert (SQ, src_f, out_f, SHIFT, SPEC) == (v, s, o, shift, spec)


def test_control():
    owners, t, p, rep = _frozen(_finish, [[0, 1, 2, 3]], TRIS)
    assert owners == [(0,), (0,)]
    assert t == [0.5, 0.5] and p == [1.0]
    assert rep["ok"] is True and rep["source_polygons_not_covered"] == 0
    assert _assign([[0, 1, 2, 3]]) == ["A"]
    assert _mesh(SQ, TRIS)["passed"] is True


def test_negative_source_wraps():
    """Current helper behavior: wrapped indices are accepted; not approved policy."""
    owners, t, p, rep = _frozen(_finish, [[-4, -3, -2, -1]], TRIS)
    assert owners == [(0,), (0,)] and t == [0.5, 0.5] and p == [1.0]
    assert rep["ok"] is True
    assert _assign([[-4, -3, -2, -1]]) == ["A"]


@pytest.mark.parametrize("face", [[True, False, 2, 3], [], [0], [0, 1], [0, 0, 1]])
def test_degenerate_source(face):
    owners, t, p, rep = _frozen(_finish, [face], TRIS)
    assert p == [0.0]
    assert owners == [(), ()]
    assert t == [0.5, 0.5]
    assert rep["ok"] is False
    assert rep["unmatched"] == 2
    assert rep["source_polygons_not_covered"] == 0
    assert _assign([face]) == ["A"]


@pytest.mark.parametrize(
    "face,exc", [([0, 1, 2, 4], IndexError), ([0.0, 1.0, 2.0, 3.0], TypeError)]
)
def test_source_index_errors(face, exc):
    with pytest.raises(exc):
        _frozen(_finish, [face], TRIS)


def test_lone_quad():
    """Current helper behavior: tri_areas reads corners 0,1,2 only."""
    out = [[0, 1, 2, 3]]
    owners, t, p, rep = _frozen(_finish, [[0, 1, 2, 3]], out)
    assert t == [0.5] and p == [1.0]
    assert _poly(SQ, out)[0]["area"] == pytest.approx(1.0)
    assert owners == [(0,)]
    assert rep["ok"] is False and rep["source_polygons_not_covered"] == 1
    assert _mesh(SQ, out)["passed"] is True


def test_quad_plus_half():
    """Current helper behavior: finish ok true although mesh_report fails; not a passed package."""
    out = [[0, 1, 2, 3], [0, 2, 3]]
    owners, t, p, rep = _frozen(_finish, [[0, 1, 2, 3]], out)
    assert t == [0.5, 0.5]
    assert owners == [(0,), (0,)]
    assert rep["ok"] is True
    assert _mesh(SQ, out)["passed"] is False


def test_quad_plus_half_whole_face_areas():
    out = [[0, 1, 2, 3], [0, 2, 3]]
    areas = [_poly(SQ, [f])[0]["area"] for f in out]
    assert areas == pytest.approx([1.0, 0.5])


@pytest.mark.parametrize(
    "faces,msg",
    [
        ([[-4, -3, -2], [-4, -2, -1]], "outside"),
        ([[False, True, 2], [0, 2, 3]], "not an integer"),
        ([[0.0, 1.0, 2.0], [0.0, 2.0, 3.0]], "not an integer"),
        ([[0.5, 1.0, 2.0], [0.0, 2.0, 3.0]], "not an integer"),
        ([[0, 0, 1], [0, 2, 3]], "repeated"),
        ([[0], [0, 2, 3]], "fewer than 3"),
        ([[0, 1], [0, 2, 3]], "fewer than 3"),
        ([[], [0, 2, 3]], "fewer than 3"),
    ],
)
def test_delivered_bad_faces_raise(faces, msg):
    with pytest.raises(ValueError, match=msg):
        _mesh(SQ, faces)


def test_spec_mutation_fails_immutability(monkeypatch):
    """A wrapper that writes spec after assign_finishes must fail the input snapshot."""
    original = finish_map.assign_finishes

    def wrapped(vertices, faces, mat_ids, spec):
        result = original(vertices, faces, mat_ids, spec)
        spec["reviewer_unexpected_mutation"] = True
        return result

    monkeypatch.setattr(finish_map, "assign_finishes", wrapped)
    saved = copy.deepcopy(SPEC)
    try:
        with pytest.raises(AssertionError):
            _assign([[0, 1, 2, 3]])
    finally:
        SPEC.clear()
        SPEC.update(saved)


def test_material_id_mutation_fails_immutability(monkeypatch):
    original = finish_map.assign_finishes

    def wrapped(vertices, faces, mat_ids, spec):
        result = original(vertices, faces, mat_ids, spec)
        mat_ids.append(9)
        return result

    monkeypatch.setattr(finish_map, "assign_finishes", wrapped)
    with pytest.raises(AssertionError):
        _assign([[0, 1, 2, 3]])


def test_vertex_mutation_fails_immutability(monkeypatch):
    original = inv_xview.mesh_report

    def wrapped(vertices, faces, profile="NPM", tol=None, part="mesh"):
        result = original(vertices, faces, profile, tol, part)
        vertices[0][0] = 99.0
        return result

    monkeypatch.setattr(inv_xview, "mesh_report", wrapped)
    saved = copy.deepcopy(SQ)
    try:
        with pytest.raises(AssertionError):
            _mesh(SQ, TRIS)
    finally:
        SQ[:] = saved


def test_shift_mutation_fails_immutability(monkeypatch):
    original = qa_packages.match_source_faces

    def wrapped(src_v, src_faces, out_v, out_faces, shift, tol=2e-4):
        result = original(src_v, src_faces, out_v, out_faces, shift, tol)
        shift[0] = 1.0
        return result

    monkeypatch.setattr(qa_packages, "match_source_faces", wrapped)
    saved = copy.deepcopy(SHIFT)
    try:
        with pytest.raises(AssertionError):
            _finish([[0, 1, 2, 3]], TRIS)
    finally:
        SHIFT[:] = saved


def test_report_input_mutation_fails_immutability(monkeypatch):
    original = qa_packages.source_finish_report

    def wrapped(expected, src_faces, owners, delivered, t_areas=None, p_areas=None):
        result = original(expected, src_faces, owners, delivered, t_areas, p_areas)
        expected.append("mutated")
        return result

    monkeypatch.setattr(qa_packages, "source_finish_report", wrapped)
    with pytest.raises(AssertionError):
        _finish([[0, 1, 2, 3]], TRIS)


def test_mutation_before_exception_fails_immutability(monkeypatch):
    """A helper that mutates its input and then raises must surface the immutability failure."""
    def wrapped(vertices, faces, mat_ids, spec):
        spec["reviewer_unexpected_mutation"] = True
        raise ValueError("boom")

    monkeypatch.setattr(finish_map, "assign_finishes", wrapped)
    saved = copy.deepcopy(SPEC)
    try:
        with pytest.raises(AssertionError):
            _assign([[0, 1, 2, 3]])
    finally:
        SPEC.clear()
        SPEC.update(saved)


def test_clean_exception_propagates_unchanged(monkeypatch):
    def wrapped(vertices, faces, mat_ids, spec):
        raise ValueError("boom")

    monkeypatch.setattr(finish_map, "assign_finishes", wrapped)
    with pytest.raises(ValueError, match="boom"):
        _assign([[0, 1, 2, 3]])


def test_repeat_and_reset_after_mutation(monkeypatch):
    """After a rejected mutation is reset, unmodified helpers pass again, repeatedly."""
    first = _assign([[0, 1, 2, 3]])
    original = finish_map.assign_finishes

    def wrapped(vertices, faces, mat_ids, spec):
        spec["x"] = 1
        return original(vertices, faces, mat_ids, spec)

    saved = copy.deepcopy(SPEC)
    with monkeypatch.context() as m:
        m.setattr(finish_map, "assign_finishes", wrapped)
        with pytest.raises(AssertionError):
            _assign([[0, 1, 2, 3]])
    SPEC.clear()
    SPEC.update(saved)
    assert _assign([[0, 1, 2, 3]]) == first
    assert _assign([[0, 1, 2, 3]]) == first
