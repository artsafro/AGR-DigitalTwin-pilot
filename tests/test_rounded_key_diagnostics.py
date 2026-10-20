"""Diagnostic-only characterization of rounded coordinate-identity merging in Connect/Shell.

new-case: preserve rounded-key topology diagnostic witnesses (Connect/Shell, Proposal 1
of docs/research/rounded-coordinate-topology-boundary.md).

These tests freeze the exact positive-sign, zero-shift ``.2h`` synthetic fixtures from
the research report as historical witnesses of the *current* identity behavior of
``connect_quads`` and ``shell_body``. The expected ``(V, F, R, Z)`` tuples describe the
present measurement, not an accepted output contract.

Known limitation: the fixtures are sub-nanometre / narrow synthetic strips whose
admissibility here is geometric only (convex, nonzero area, accepted by today's kernel
validation). The measurements do not certify real-model correctness and do not choose
any coordinate-identity policy. Invalid output geometry (repeated indices, exactly
zero-area faces, duplicate exterior index cycles) is reported by the independent
diagnostic helper below, never approved or repaired; the kernels still emit it. Future
behavior fixes may replace these witnesses only after an explicit policy decision.
"""

import json
import sys
from collections import Counter

import numpy as np
import pytest

from dt_ai.geometry.connect import connect_quads
from dt_ai.geometry.shell import shell_body

CONNECT_H = 10.0 ** -8
SHELL_H = 10.0 ** -9


# ---------------------------------------------------------------------------
# Independent diagnostic helper (no np.round oracle)
# ---------------------------------------------------------------------------

def repeated_index_count(faces):
    """Number of faces whose four vertex indices are not all distinct."""
    return sum(len(set(int(i) for i in face)) < 4 for face in faces)


def zero_area_count(vertices, faces):
    """Number of faces with exactly zero area (two triangle cross-product norms)."""
    count = 0
    for face in faces:
        q = np.asarray(vertices)[face]
        area = (np.linalg.norm(np.cross(q[1] - q[0], q[2] - q[0])) +
                np.linalg.norm(np.cross(q[2] - q[0], q[3] - q[0]))) / 2.0
        if area == 0.0:
            count += 1
    return count


def _cycle_signature(face):
    """Canonical rotation of a face index cycle (minimum index first)."""
    idx = [int(i) for i in face]
    start = idx.index(min(idx))
    return tuple(idx[start:] + idx[:start])


def duplicate_cycle_count(faces):
    """Number of distinct index cycles referenced by more than one face."""
    counts = Counter(_cycle_signature(face) for face in faces)
    return sum(1 for n in counts.values() if n > 1)


def boundary_edge_count(faces):
    """Number of edges used exactly once, from input index adjacency only."""
    uses = Counter(tuple(sorted((int(a), int(b))))
                   for face in faces
                   for a, b in zip(face, np.roll(face, -1)))
    return sum(1 for n in uses.values() if n == 1)


def signature(vertices, faces):
    """Return the (V, F, R, Z) measurement tuple."""
    v = np.asarray(vertices)
    f = np.asarray(faces)
    return (len(v), len(f), repeated_index_count(f), zero_area_count(v, f))


# ---------------------------------------------------------------------------
# Frozen synthetic fixtures (positive sign, zero shift, original order)
# ---------------------------------------------------------------------------

def quad(x=0.0, y=0.0, width=1.0):
    """Unit vertical rectangle in the Z=0..1 plane at (x, y)."""
    return np.array([[x, y, 0.0], [x + width, y, 0.0],
                     [x + width, y, 1.0], [x, y, 1.0]])


def narrow_fixture(h, shift=0.0):
    """Two disjoint positive-width vertical rectangles; width = 0.2*h."""
    g = 0.2 * h
    vertices = np.vstack([quad(width=g), quad(x=2.0, width=g)]) + shift * h
    faces = np.array([[0, 1, 2, 3], [4, 5, 6, 7]])
    return vertices, faces


def parallel_fixture(h, shift=0.0):
    """Two unit vertical rectangles separated by a Y gap of 0.2*h."""
    g = 0.2 * h
    vertices = np.vstack([quad(), quad(y=g)]) + shift * h
    faces = np.array([[0, 1, 2, 3], [4, 5, 6, 7]])
    return vertices, faces


def depth_fixture(h, shift=0.0):
    """Two unit vertical rectangles; Shell thickness = 0.2*h (depth)."""
    vertices = np.vstack([quad(), quad(x=2.0)]) + shift * h
    faces = np.array([[0, 1, 2, 3], [4, 5, 6, 7]])
    return vertices, faces


def shared_fixture(h):
    """Indexed exact common edge: 6 unique vertices, one shared (1, 2) edge."""
    v = np.vstack([quad(), quad(x=1.0)])
    return v[[0, 1, 2, 3, 5, 6]], np.array([[0, 1, 2, 3], [1, 4, 5, 2]])


def coincident_fixture(h):
    """Duplicate coordinates with separate indices (split-index coincident)."""
    v = np.vstack([quad(), quad(x=1.0)])
    return v, np.array([[0, 1, 2, 3], [4, 5, 6, 7]])


def shell_run(vertices, faces, thickness_m, refs=None):
    """Call public shell_body with vertical outward normals and explicit metres."""
    if refs is None:
        refs = [f"synthetic:{i}" for i in range(len(faces))]
    normals = np.tile([0.0, -1.0, 0.0], (len(faces), 1))
    return shell_body(vertices, faces, normals, thickness_m=thickness_m,
                      name="synthetic", source_refs=refs, units="m")


def shell_exterior_faces(result):
    """Exterior faces only (role == 'exterior'), in emitted face order."""
    of = np.array(result["mesh"]["faces"])
    return np.array([of[i] for i, s in enumerate(result["face_sources"])
                     if s["role"] == "exterior"])


# ---------------------------------------------------------------------------
# Concrete legacy-defect witnesses
# ---------------------------------------------------------------------------

def test_connect_narrow_point2_witness():
    v, f = narrow_fixture(CONNECT_H)
    out_v, out_f, parents = connect_quads(v, f, max_side_m=3.9)
    assert signature(out_v, out_f) == (4, 2, 2, 2)
    assert out_f.tolist() == [[0, 0, 1, 1], [2, 2, 3, 3]]


def test_connect_narrow_point2_45h_unmerged_witness():
    v, f = narrow_fixture(CONNECT_H, shift=0.45)
    out_v, out_f, _ = connect_quads(v, f, max_side_m=3.9)
    assert signature(out_v, out_f) == (8, 2, 0, 0)


def test_shell_narrow_point2_witness():
    v, f = narrow_fixture(SHELL_H)
    result = shell_run(v, f, thickness_m=0.4)
    out_v = np.array(result["mesh"]["vertices"])
    out_f = np.array(result["mesh"]["faces"])
    assert signature(out_v, out_f) == (8, 10, 6, 6)


def test_shell_depth_point2_witness():
    v, f = depth_fixture(SHELL_H)
    result = shell_run(v, f, thickness_m=0.2 * SHELL_H)
    out_v = np.array(result["mesh"]["vertices"])
    out_f = np.array(result["mesh"]["faces"])
    assert signature(out_v, out_f) == (8, 10, 8, 8)


def test_shell_narrow_point2_45h_unmerged_witness():
    v, f = narrow_fixture(SHELL_H, shift=0.45)
    result = shell_run(v, f, thickness_m=0.4)
    out_v = np.array(result["mesh"]["vertices"])
    out_f = np.array(result["mesh"]["faces"])
    assert signature(out_v, out_f) == (16, 10, 0, 0)


def test_connect_parallel_point2_duplicate_exterior_cycles():
    v, f = parallel_fixture(CONNECT_H)
    out_v, out_f, _ = connect_quads(v, f, max_side_m=3.9)
    assert signature(out_v, out_f) == (4, 2, 0, 0)
    assert duplicate_cycle_count(out_f) == 1
    # two identical exterior index cycles despite distinct original Y planes
    assert out_f[0].tolist() == out_f[1].tolist() == [0, 1, 3, 2]


def test_shell_parallel_point2_duplicate_exterior_cycles():
    v, f = parallel_fixture(SHELL_H)
    result = shell_run(v, f, thickness_m=0.4)
    out_v = np.array(result["mesh"]["vertices"])
    out_f = np.array(result["mesh"]["faces"])
    assert signature(out_v, out_f) == (8, 10, 0, 0)
    exteriors = shell_exterior_faces(result)
    assert duplicate_cycle_count(exteriors) == 1
    assert exteriors[0].tolist() == exteriors[1].tolist() == [0, 1, 2, 3]


def test_connect_parallel_reversed_order_retains_original_y():
    v, f = parallel_fixture(CONNECT_H)
    out_v, out_f, _ = connect_quads(v, f[::-1], max_side_m=3.9)
    assert signature(out_v, out_f) == (4, 2, 0, 0)
    # representative is the *other* plane's original Y (0.2*h), not the rounded key 0.0
    assert np.all(out_v[:, 1] == 0.2 * CONNECT_H)


def test_shell_parallel_reversed_order_retains_original_y():
    v, f = parallel_fixture(SHELL_H)
    result = shell_run(v, f[::-1], thickness_m=0.4)
    out_v = np.array(result["mesh"]["vertices"])
    out_f = np.array(result["mesh"]["faces"])
    assert signature(out_v, out_f) == (8, 10, 0, 0)
    exteriors = shell_exterior_faces(result)
    exterior_verts = out_v[exteriors]
    assert np.all(exterior_verts[..., 1] == 0.2 * SHELL_H)


def test_shell_shared_exact_indexed_control():
    v, f = shared_fixture(SHELL_H)
    result = shell_run(v, f, thickness_m=0.4)
    out_v = np.array(result["mesh"]["vertices"])
    out_f = np.array(result["mesh"]["faces"])
    assert signature(out_v, out_f) == (12, 8, 0, 0)
    rims = sum(1 for s in result["face_sources"] if s["role"] == "rim")
    # 6 boundary rims derived from input index adjacency, not output coordinate keys
    assert boundary_edge_count(f) == 6
    assert rims == 6


def test_shell_coincident_split_index_control():
    v, f = coincident_fixture(SHELL_H)
    result = shell_run(v, f, thickness_m=0.4)
    out_v = np.array(result["mesh"]["vertices"])
    out_f = np.array(result["mesh"]["faces"])
    assert signature(out_v, out_f) == (12, 10, 0, 0)
    rims = sum(1 for s in result["face_sources"] if s["role"] == "rim")
    assert boundary_edge_count(f) == 8
    assert rims == 8


# ---------------------------------------------------------------------------
# Admissibility, preservation, alignment, JSON round-trip
# ---------------------------------------------------------------------------

def test_fixtures_are_admissible():
    fixtures = [narrow_fixture(CONNECT_H), narrow_fixture(SHELL_H),
                parallel_fixture(CONNECT_H), parallel_fixture(SHELL_H),
                depth_fixture(SHELL_H), shared_fixture(SHELL_H),
                coincident_fixture(SHELL_H)]
    for v, f in fixtures:
        assert np.isfinite(v).all()
        assert all(len(set(int(i) for i in face)) == 4 for face in f)
        for face in f:
            q = v[face]
            area = (np.linalg.norm(np.cross(q[1] - q[0], q[2] - q[0])) +
                    np.linalg.norm(np.cross(q[2] - q[0], q[3] - q[0]))) / 2.0
            assert area > 0.0


def test_connect_parents_alignment_and_input_immutability():
    v, f = narrow_fixture(CONNECT_H)
    v_before, f_before = v.copy(), f.copy()
    out_v, out_f, parents = connect_quads(v, f, max_side_m=3.9)
    assert np.array_equal(v, v_before)
    assert np.array_equal(f, f_before)
    assert len(parents) == len(out_f) == 2
    assert parents == [0, 1]


def test_shell_alignment_materials_and_json_roundtrip():
    v, f = narrow_fixture(SHELL_H)
    refs = [f"synthetic:{i}" for i in range(len(f))]
    normals = np.tile([0.0, -1.0, 0.0], (len(f), 1))
    v_before, f_before = v.copy(), f.copy()
    normals_before = normals.copy()
    refs_before = list(refs)

    result = shell_body(v, f, normals, thickness_m=0.4, name="synthetic",
                        source_refs=refs, units="m")
    mesh = result["mesh"]
    out_v = np.array(mesh["vertices"])
    out_f = np.array(mesh["faces"])

    assert np.array_equal(v, v_before)
    assert np.array_equal(f, f_before)
    assert np.array_equal(normals, normals_before)
    assert refs == refs_before

    sources = result["face_sources"]
    assert len(sources) == len(out_f) == len(mesh["materials"])
    assert all(s["source_ref"] == refs[s["source_face"]] for s in sources)
    assert mesh["materials"] == [0] * len(out_f)

    # float.hex identity after JSON round-trip of all output coordinates and indices
    serial = json.loads(json.dumps({"v": out_v.tolist(), "f": out_f.tolist()},
                                   allow_nan=False))
    assert [float(x).hex() for x in out_v.flat] == \
        [float(x).hex() for x in np.array(serial["v"]).flat]
    assert serial["f"] == out_f.tolist()


# ---------------------------------------------------------------------------
# Diagnostic helper oracle sensitivity controls (not a production gate)
# ---------------------------------------------------------------------------

def test_helper_reports_repeated_index_and_zero_area():
    faces = np.array([[0, 0, 1, 1]])
    vertices = np.array([[0.0, 0.0, 0.0], [0.0, 0.1, 0.0]])
    assert repeated_index_count(faces) == 1
    assert zero_area_count(vertices, faces) == 1


def test_helper_reports_duplicate_cycles_without_repeated_indices():
    # two distinct-index coincident cycles: R == 0 but duplicate cycles detected
    faces = np.array([[0, 1, 2, 3], [0, 1, 2, 3]])
    assert repeated_index_count(faces) == 0
    assert duplicate_cycle_count(faces) == 1


def test_mutated_repeated_index_diagnostic_is_caught_by_witness(monkeypatch):
    v, f = narrow_fixture(CONNECT_H)
    out_v, out_f, _ = connect_quads(v, f, max_side_m=3.9)
    assert repeated_index_count(out_f) == 2  # intact diagnostic sees the defect

    monkeypatch.setattr(sys.modules[__name__], "repeated_index_count",
                        lambda faces: 0)
    # disabling the R diagnostic breaks the frozen (4, 2, 2, 2) witness -> caught
    assert signature(out_v, out_f) != (4, 2, 2, 2)


def test_mutated_duplicate_cycle_diagnostic_is_caught_by_witness(monkeypatch):
    v, f = parallel_fixture(CONNECT_H)
    out_v, out_f, _ = connect_quads(v, f, max_side_m=3.9)
    assert duplicate_cycle_count(out_f) == 1  # intact diagnostic sees the duplicate

    monkeypatch.setattr(sys.modules[__name__], "duplicate_cycle_count",
                        lambda faces: 0)
    # disabling the duplicate-cycle diagnostic breaks the witness -> caught
    assert duplicate_cycle_count(out_f) == 0


def test_invalid_geometry_is_reported_not_repaired():
    v, f = narrow_fixture(CONNECT_H)
    out_v, out_f, _ = connect_quads(v, f, max_side_m=3.9)
    # the kernel still emits the degenerate faces; the diagnostic only reports them
    assert repeated_index_count(out_f) == 2
    assert zero_area_count(out_v, out_f) == 2
