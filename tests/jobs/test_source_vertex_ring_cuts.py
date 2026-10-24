"""new-case: independent missing-vertex and allowed-edge-cut controls for qa_packages.geometry_report.

Pattern: new-case (characterization on the current code; GREEN at baseline, not a historical RED).

NOT CERTIFIED HERE: vertex preservation does not certify triangle containment, coverage or source-corner face
incidence. geometry_report looks at the vertex set only; the known concave false pass is deliberately not pinned.

Source: literal square (0,0,0),(4,0,0),(4,4,0),(0,4,0), one quad [0,1,2,3]. Tolerance 2e-4 (unchanged).
Table (unique counts; cuts False / True):
  unchanged                 -> ok True/True,  missing 0, new 0, off 0
  omit one corner           -> ok False/False, missing 1
  + edge midpoint (2,0,0)   -> new 1, off 0, ok False / True
  + interior (2,2,0)        -> new 1, off 1, ok False / False
  + exterior (5,2,0)        -> new 1, off 1, ok False / False
  duplicated / permuted     -> same unique counts
  omit corner + midpoint    -> missing 1, new 1, ok False / False
Repeated in XY, XZ, YZ and with output = source - shift.
"""
import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "jobs/TEC26-OKS/scripts"))
import qa_packages  # noqa: E402

SQ = [(0, 0, 0), (4, 0, 0), (4, 4, 0), (0, 4, 0)]
FACES = [[0, 1, 2, 3]]
MID, INT, EXT = (2, 0, 0), (2, 2, 0), (5, 2, 0)
PLANES = {"XY": (0, 1, 2), "XZ": (0, 2, 1), "YZ": (2, 0, 1)}
SHIFTS = [(0, 0, 0), (100.0, -50.0, 25.0)]


def _p(pt, plane):
    a, b, c = PLANES[plane]
    out = [0, 0, 0]
    out[a], out[b], out[c] = pt
    return tuple(out)


def _run(out_pts, cuts, plane, shift):
    src = [_p(p, plane) for p in SQ]
    out = [[p[i] - shift[i] for i in range(3)] for p in (_p(q, plane) for q in out_pts)]
    return qa_packages.geometry_report(src, FACES, out, shift, cuts)


# name, output points, (missing, new, off), ok without cuts, ok with cuts
CASES = [
    ("unchanged", SQ, (0, 0, 0), True, True),
    ("omit_corner", SQ[1:], (1, 0, 0), False, False),
    ("midpoint", SQ + [MID], (0, 1, 0), False, True),
    ("interior", SQ + [INT], (0, 1, 1), False, False),
    ("exterior", SQ + [EXT], (0, 1, 1), False, False),
    ("dup_permuted", [SQ[2], SQ[0], SQ[0], SQ[3], SQ[1], SQ[2]], (0, 0, 0), True, True),
    ("dup_permuted_mid", [MID, SQ[3], SQ[1], MID, SQ[0], SQ[2], SQ[0]], (0, 1, 0), False, True),
    ("omit_corner_plus_mid", SQ[1:] + [MID], (1, 1, 0), False, False),
]


@pytest.mark.parametrize("shift", SHIFTS)
@pytest.mark.parametrize("plane", PLANES)
@pytest.mark.parametrize("name,pts,counts,ok_no,ok_cut", CASES, ids=[c[0] for c in CASES])
def test_table(name, pts, counts, ok_no, ok_cut, plane, shift):
    missing, new, off = counts
    for cuts, ok in ((False, ok_no), (True, ok_cut)):
        r = _run(pts, cuts, plane, shift)
        assert (r["missing_source_vertices"], r["new_vertices"], r["new_off_source_edges"]) == counts
        assert r["ok"] is ok and r["cuts_allowed"] is cuts
        assert len(r["off_examples"]) == off


@pytest.mark.parametrize("plane", PLANES)
def test_off_examples_normalized(plane):
    r = _run(SQ + [INT], True, plane, (0, 0, 0))
    assert r["off_examples"] == [[float(v) for v in _p(INT, plane)]]
    r = _run(SQ + [EXT], True, plane, (100.0, -50.0, 25.0))
    assert r["off_examples"] == [[float(v) for v in _p(EXT, plane)]]


def test_inputs_not_mutated():
    src = [list(map(float, p)) for p in SQ]
    out = [list(map(float, p)) for p in SQ + [MID, INT]]
    faces, shift = copy.deepcopy(FACES), [1.0, 2.0, 3.0]
    snap = copy.deepcopy((src, out, faces, shift))
    qa_packages.geometry_report(src, faces, out, shift, True)
    assert (src, out, faces, shift) == snap


def test_controls_are_independent(monkeypatch):
    """Mutations: ignoring missing vertices, or ignoring cuts_allowed, must be caught by the table."""
    orig = qa_packages._new_vertices
    monkeypatch.setattr(qa_packages, "_new_vertices", lambda *a, **k: (lambda n, m: (n, 0))(*orig(*a, **k)))
    assert _run(SQ[1:], True, "XY", (0, 0, 0))["ok"] is True  # mutated: corner loss now passes
    monkeypatch.setattr(qa_packages, "_new_vertices", orig)
    assert _run(SQ[1:], True, "XY", (0, 0, 0))["ok"] is False
    # cuts_allowed ignored == always True: the midpoint with cuts False must differ from it
    assert _run(SQ + [MID], False, "XY", (0, 0, 0))["ok"] != _run(SQ + [MID], True, "XY", (0, 0, 0))["ok"]
