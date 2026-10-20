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
from collections import Counter, defaultdict

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


def _input_boundary_edge_owners(faces):
    """Map each directed boundary edge ``(a, b)`` to the input face index owning it.

    Independent of any output: a boundary edge is one used exactly once across the
    submitted face index cycles; the direction ``a -> b`` follows the submitted
    winding, which is the same convention ``shell_body`` stores in ``source_edge``.
    """
    uses = defaultdict(list)
    for fi, face in enumerate(faces):
        for a, b in zip(face, np.roll(face, -1)):
            uses[tuple(sorted((int(a), int(b))))].append((fi, int(a), int(b)))
    owners = {}
    for entries in uses.values():
        if len(entries) == 1:
            fi, a, b = entries[0]
            owners[(a, b)] = fi
    return owners


def _input_boundary_edges_in_emission_order(faces):
    """Ordered ``(i, j, owner)`` input boundary edges in kernel emission order.

    Matches ``shell_body`` exactly: an edge used once across the submitted index
    cycles is a boundary edge, and the emission order is faces in submitted order,
    then within each face the winding order ``0->1, 1->2, 2->3, 3->0``. Derived
    purely from submitted index adjacency, independent of output coordinates.
    """
    edges = {}
    for fi, face in enumerate(faces):
        for i, j in zip(face, np.roll(face, -1)):
            edges.setdefault(tuple(sorted((int(i), int(j)))), []).append(
                (int(i), int(j), fi))
    return [tuple(uses[0]) for uses in edges.values() if len(uses) == 1]


def assert_shell_provenance(result, submitted_vertices, submitted_faces, submitted_refs):
    """Independent provenance + exact-geometry oracle for ``shell_body`` output.

    Validates against the *submitted* input (vertices, faces, refs) and the emitted
    geometry, never the output's own (potentially swapped/permuted) bookkeeping:

    * Exterior faces are emitted in submitted order with submitted refs, and each
      exterior face's first corner keeps the exact input coordinate (winding not
      reversed).
    * The complete ordered rim ``(source_edge, source_face)`` sequence equals the
      independent input boundary-edge emission order (positional association), and
      each rim record's ``source_ref`` matches its owner face.
    * The emitted vertex coordinates equal, with exact float identity, the retained
      input corners and their exact inward offsets. The kernel stores coordinates
      exactly -- ``np.round(v, 9)`` is only its *identity* key -- so a rounded key
      must never judge whether a retained coordinate survived: it collapses the
      narrow strip's right edge ``X = 0.2*h`` (hex ``0x1.b7cdfd9d7bdbcp-33``) to
      zero and would miss a corruption of exactly that coordinate.

    The exact-geometry half is a frozen witness for the two-strip synthetic fixtures
    (each quad's even corners ``0`` and ``2`` are the first-wins retained corners
    because the strip width lies below the kernel's 9-decimal rounding resolution);
    the provenance half is general.
    """
    v = np.asarray(submitted_vertices, dtype=float)
    sources = result["face_sources"]
    exteriors = [s for s in sources if s["role"] == "exterior"]
    rims = [s for s in sources if s["role"] == "rim"]
    out_f = np.asarray(result["mesh"]["faces"])
    out_v = np.asarray(result["mesh"]["vertices"], dtype=float)
    thickness = result["thickness_m"]

    # Ordered provenance (integer/string comparisons; no rounding).
    assert [s["source_face"] for s in exteriors] == list(range(len(submitted_faces)))
    assert [s["source_ref"] for s in exteriors] == list(submitted_refs)

    expected_edges = _input_boundary_edges_in_emission_order(submitted_faces)
    assert len(rims) == len(expected_edges) == boundary_edge_count(submitted_faces)
    actual_seq = [(int(s["source_edge"][0]), int(s["source_edge"][1]), s["source_face"])
                  for s in rims]
    assert actual_seq == expected_edges, (
        f"rim source sequence {actual_seq} != input boundary emission order "
        f"{expected_edges}")
    for s in rims:
        assert s["source_ref"] == submitted_refs[s["source_face"]]

    # Exact retained geometry (frozen narrow-strip witness; no rounding).
    for k in range(len(exteriors)):
        assert np.array_equal(out_v[out_f[k][0]], v[submitted_faces[k][0]]), (
            f"exterior face {k} first corner lost its exact input coordinate or "
            f"the winding was reversed")

    retained_idx = sorted({int(i) for face in submitted_faces for i in face[0::2]})
    delta = np.array([0.0, thickness, 0.0])
    expected = {tuple(float(x) for x in v[i]) for i in retained_idx}
    expected |= {tuple(float(x) for x in v[i] + delta) for i in retained_idx}
    actual = {tuple(float(x) for x in row) for row in out_v}
    assert actual == expected, (
        f"exact retained coordinates differ: output {sorted(actual)} != "
        f"expected {sorted(expected)}")


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
    assert_shell_provenance(result, v, f, refs)  # independent provenance (not self-referential)
    assert mesh["materials"] == [0] * len(out_f)

    # float.hex identity after JSON round-trip of all output coordinates and indices
    serial = json.loads(json.dumps({"v": out_v.tolist(), "f": out_f.tolist()},
                                   allow_nan=False))
    assert [float(x).hex() for x in out_v.flat] == \
        [float(x).hex() for x in np.array(serial["v"]).flat]
    assert serial["f"] == out_f.tolist()


# ---------------------------------------------------------------------------
# Independent provenance oracle (review P1: source-order alignment)
# ---------------------------------------------------------------------------

def _swap_source_provenance(result, refs):
    """Review P1 mutation: swap each ``source_face`` 0<->1 and re-point ``source_ref``
    to the swapped face's ref, leaving geometry/source_edge/role/materials intact."""
    mutated = {
        "mesh": result["mesh"],
        "face_sources": [dict(s) for s in result["face_sources"]],
        "thickness_m": result["thickness_m"],
        "inner_faces": result["inner_faces"],
    }
    for s in mutated["face_sources"]:
        new = 1 - s["source_face"]
        s["source_face"] = new
        s["source_ref"] = refs[new]
    return mutated


def test_shell_exterior_provenance_normal_order_distinct_refs():
    v, f = narrow_fixture(SHELL_H)
    refs = ["front", "back"]
    result = shell_run(v, f, thickness_m=0.4, refs=refs)
    # exterior source_face order [0, 1] with the submitted refs
    assert_shell_provenance(result, v, f, refs)


def test_shell_exterior_provenance_reversed_order_distinct_refs():
    v, f = narrow_fixture(SHELL_H)
    refs = ["front", "back"]
    # submit faces and their refs in reverse order: refs follow their faces
    result = shell_run(v, f[::-1], thickness_m=0.4, refs=refs[::-1])
    assert_shell_provenance(result, v, f[::-1], refs[::-1])


def test_shell_provenance_rejects_source_face_swap_mutation():
    v, f = narrow_fixture(SHELL_H)
    refs = ["front", "back"]
    result = shell_run(v, f, thickness_m=0.4, refs=refs)
    assert_shell_provenance(result, v, f, refs)  # intact provenance passes

    out_v = np.array(result["mesh"]["vertices"])
    out_f = np.array(result["mesh"]["faces"])
    assert signature(out_v, out_f) == (8, 10, 6, 6)  # frozen geometry retained

    mutated = _swap_source_provenance(result, refs)
    # the internal consistency tautology survives, but the independent oracle fails
    assert all(s["source_ref"] == refs[s["source_face"]]
               for s in mutated["face_sources"])
    with pytest.raises(AssertionError):
        assert_shell_provenance(mutated, v, f, refs)


def _rotate_rim_source_records(result):
    """Review round-2 mutation: rotate only rim ``face_sources`` records one
    position, preserving all mesh vertices/faces/materials, exterior records and
    every individual source record (each triple stays internally consistent)."""
    mutated = {
        "mesh": result["mesh"],
        "face_sources": [dict(s) for s in result["face_sources"]],
        "thickness_m": result["thickness_m"],
        "inner_faces": result["inner_faces"],
    }
    positions = [i for i, s in enumerate(mutated["face_sources"]) if s["role"] == "rim"]
    rows = [mutated["face_sources"][i] for i in positions]
    for i, s in zip(positions, rows[1:] + rows[:1]):
        mutated["face_sources"][i] = s
    return mutated


def test_shell_rim_source_sequence_matches_input_boundary_order():
    v, f = narrow_fixture(SHELL_H)
    refs = ["front", "back"]
    result = shell_run(v, f, thickness_m=0.4, refs=refs)
    rims = [s for s in result["face_sources"] if s["role"] == "rim"]
    # concrete acceptance row: the complete ordered rim source sequence, derived
    # purely from submitted index adjacency, equals the kernel emission order exactly
    expected = [(0, 1, 0), (1, 2, 0), (2, 3, 0), (3, 0, 0),
                (4, 5, 1), (5, 6, 1), (6, 7, 1), (7, 4, 1)]
    assert _input_boundary_edges_in_emission_order(f) == expected
    assert [(int(s["source_edge"][0]), int(s["source_edge"][1]), s["source_face"])
            for s in rims] == expected


def test_shell_provenance_rejects_rim_record_rotation_mutation():
    v, f = narrow_fixture(SHELL_H)
    refs = ["front", "back"]
    result = shell_run(v, f, thickness_m=0.4, refs=refs)
    assert_shell_provenance(result, v, f, refs)  # intact provenance passes

    out_v = np.array(result["mesh"]["vertices"])
    out_f = np.array(result["mesh"]["faces"])
    assert signature(out_v, out_f) == (8, 10, 6, 6)  # frozen geometry retained

    mutated = _rotate_rim_source_records(result)
    assert mutated["mesh"] == result["mesh"]  # geometry untouched

    # per-record internal consistency (owner/ref) survives the rotation, so the
    # round-1 oracle would still pass; the positional+geometry oracle must not
    owners = _input_boundary_edge_owners(f)
    for s in mutated["face_sources"]:
        if s["role"] == "rim":
            edge = (int(s["source_edge"][0]), int(s["source_edge"][1]))
            assert owners[edge] == s["source_face"]
            assert s["source_ref"] == refs[s["source_face"]]

    with pytest.raises(AssertionError):
        assert_shell_provenance(mutated, v, f, refs)


def test_shell_provenance_rejects_rim_rotation_via_process_local_wrapper(monkeypatch):
    import dt_ai.geometry.shell as shell_mod

    v, f = narrow_fixture(SHELL_H)
    refs = ["front", "back"]

    def wrapped_shell_body(*args, **kwargs):
        return _rotate_rim_source_records(shell_mod.shell_body(*args, **kwargs))

    # process-local wrapper: shell_run resolves the module-global shell_body, so the
    # rotated result flows into the oracle exactly as the reviewer's reproducer does
    monkeypatch.setattr(sys.modules[__name__], "shell_body", wrapped_shell_body)
    result = shell_run(v, f, thickness_m=0.4, refs=refs)

    with pytest.raises(AssertionError):
        assert_shell_provenance(result, v, f, refs)


def _corrupt_retained_x(result, h):
    """Review round-3 mutation: zero any emitted X strictly between 0 and ``h``.

    The narrow strip's retained right edge has ``X = 0.2*h`` (hex
    ``0x1.b7cdfd9d7bdbcp-33``), which lies strictly below ``h``. A rounded-key oracle
    collapses that X to zero and therefore cannot distinguish the corruption; the
    exact-geometry oracle must reject it. Only the ``mesh`` coordinates are changed;
    provenance, faces and materials are left intact.
    """
    mesh = dict(result["mesh"])
    out_v = np.array(mesh["vertices"], dtype=float)
    mask = (out_v[:, 0] > 0.0) & (out_v[:, 0] < h)
    out_v[mask, 0] = 0.0
    mesh["vertices"] = out_v.tolist()
    return {"mesh": mesh, "face_sources": result["face_sources"],
            "thickness_m": result["thickness_m"], "inner_faces": result["inner_faces"]}


def test_shell_provenance_rejects_retained_x_corruption_mutation():
    v, f = narrow_fixture(SHELL_H)
    refs = ["front", "back"]
    result = shell_run(v, f, thickness_m=0.4, refs=refs)
    assert_shell_provenance(result, v, f, refs)  # intact provenance passes

    out_v = np.array(result["mesh"]["vertices"])
    out_f = np.array(result["mesh"]["faces"])
    assert signature(out_v, out_f) == (8, 10, 6, 6)  # frozen geometry retained

    # the retained right-edge corners keep their exact X = 0.2*h before corruption
    g = 0.2 * SHELL_H
    exact = {tuple(map(float, row)) for row in out_v}
    assert (g, 0.0, 1.0) in exact
    assert (g, 0.4, 1.0) in exact

    mutated = _corrupt_retained_x(result, SHELL_H)
    with pytest.raises(AssertionError):
        assert_shell_provenance(mutated, v, f, refs)


def test_shell_provenance_rejects_retained_x_corruption_via_process_local_wrapper(
        monkeypatch):
    import dt_ai.geometry.shell as shell_mod

    v, f = narrow_fixture(SHELL_H)
    refs = ["front", "back"]

    def wrapped_shell_body(*args, **kwargs):
        return _corrupt_retained_x(shell_mod.shell_body(*args, **kwargs), SHELL_H)

    # process-local wrapper: shell_run resolves the module-global shell_body, so the
    # corrupted result flows into the oracle exactly as the reviewer's reproducer does
    monkeypatch.setattr(sys.modules[__name__], "shell_body", wrapped_shell_body)
    result = shell_run(v, f, thickness_m=0.4, refs=refs)

    with pytest.raises(AssertionError):
        assert_shell_provenance(result, v, f, refs)


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
