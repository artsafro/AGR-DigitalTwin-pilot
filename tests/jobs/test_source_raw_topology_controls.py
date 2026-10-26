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
from dt_ai.ops.inv_xview import mesh_report  # noqa: E402

SQ = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]]
SHIFT = [0.0, 0.0, 0.0]
SPEC = {"source_ids": {"1": {"finish": "A"}}, "zero_m": 0.0}
TRIS = [[0, 1, 2], [0, 2, 3]]


def _finish(src_f, out_f):
    owners = qa_packages.match_source_faces(SQ, src_f, SQ, out_f, SHIFT)
    t = qa_packages.tri_areas(SQ, out_f)
    p = qa_packages.poly_areas(SQ, src_f)
    rep = qa_packages.source_finish_report(["A"], src_f, owners, ["A"] * len(owners), t, p)
    return owners, t, p, rep


def _assign(src_f):
    return finish_map.assign_finishes(SQ, src_f, [1], SPEC)


def _frozen(fn, src_f, out_f):
    v, s, o = copy.deepcopy(SQ), copy.deepcopy(src_f), copy.deepcopy(out_f)
    try:
        return fn(src_f, out_f)
    finally:
        assert (SQ, src_f, out_f) == (v, s, o)


def test_control():
    owners, t, p, rep = _frozen(_finish, [[0, 1, 2, 3]], TRIS)
    assert owners == [(0,), (0,)]
    assert t == [0.5, 0.5] and p == [1.0]
    assert rep["ok"] is True and rep["source_polygons_not_covered"] == 0
    assert _assign([[0, 1, 2, 3]]) == ["A"]
    assert mesh_report(SQ, TRIS, profile="VPM")["passed"] is True


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
    assert qa_packages._poly_geo(SQ, out)[0]["area"] == pytest.approx(1.0)
    assert owners == [(0,)]
    assert rep["ok"] is False and rep["source_polygons_not_covered"] == 1
    assert mesh_report(SQ, out, profile="VPM")["passed"] is True


def test_quad_plus_half():
    """Current helper behavior: finish ok true although mesh_report fails; not a passed package."""
    out = [[0, 1, 2, 3], [0, 2, 3]]
    owners, t, p, rep = _frozen(_finish, [[0, 1, 2, 3]], out)
    assert t == [0.5, 0.5]
    assert owners == [(0,), (0,)]
    assert rep["ok"] is True
    assert mesh_report(SQ, out, profile="VPM")["passed"] is False


def test_quad_plus_half_whole_face_areas():
    out = [[0, 1, 2, 3], [0, 2, 3]]
    areas = [qa_packages._poly_geo(SQ, [f])[0]["area"] for f in out]
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
    before = copy.deepcopy(faces)
    with pytest.raises(ValueError, match=msg):
        mesh_report(SQ, faces, profile="VPM")
    assert faces == before
