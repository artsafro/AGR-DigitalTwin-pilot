"""Tests for component_signed_volumes diagnostic helper (Card #93).

All test data is SYNTHETIC test data, not a real object.
"""
import copy
import math
from pathlib import Path

import numpy as np
import pytest

from twinqa.geometry import checks
from twinqa.geometry.mesh import from_dump

ROOT = Path(__file__).resolve().parents[2]

_BOX_TRIS = [
    [0, 3, 2], [0, 2, 1], [4, 5, 6], [4, 6, 7],
    [0, 1, 5], [0, 5, 4], [2, 3, 7], [2, 7, 6],
    [1, 2, 6], [1, 6, 5], [0, 4, 7], [0, 7, 3],
]

_UNIT_BOX_VERTS = [
    [0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0],
    [0.0, 0.0, 1.0], [1.0, 0.0, 1.0], [1.0, 1.0, 1.0], [0.0, 1.0, 1.0],
]


def _get_helper():
    from twinqa.geometry.component_volume import component_signed_volumes

    return component_signed_volumes


def _transform_points(pts: np.ndarray, transform_name: str) -> np.ndarray:
    if transform_name == "identity":
        return pts.copy()
    shift = np.array([600000.0, 7500000.0, 150.0], dtype=float)
    if transform_name == "translation":
        return pts + shift
    if transform_name == "Rz37_translation":
        theta = np.radians(37.0)
        c, s = np.cos(theta), np.sin(theta)
        rz = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]], dtype=float)
        return (pts @ rz.T) + shift
    raise ValueError(f"Unknown transform: {transform_name}")


def _build_outer_inner(variant: str, packing: str, transform_name: str) -> list[dict]:
    outer_v = _transform_points(np.asarray(_UNIT_BOX_VERTS, float) * 100.0, transform_name)
    outer_t = [list(t) for t in _BOX_TRIS]
    inner_v = _transform_points(np.asarray(_UNIT_BOX_VERTS, float) * 0.2 + 49.9, transform_name)
    if variant == "outward":
        inner_t = [list(t) for t in _BOX_TRIS]
    elif variant == "inverted":
        inner_t = [[a, c, b] for a, b, c in _BOX_TRIS]
    elif variant == "open":
        inner_t = [list(t) for t in _BOX_TRIS[2:]]
    elif variant == "inconsistent":
        inner_t = [list(t) for t in _BOX_TRIS]
        inner_t[4] = [inner_t[4][0], inner_t[4][2], inner_t[4][1]]
    else:
        raise ValueError(f"Unknown variant: {variant}")

    if packing == "two_meshes":
        return [
            {"name": "outer", "vertices": outer_v.tolist(), "triangles": outer_t},
            {"name": "inner", "vertices": inner_v.tolist(), "triangles": inner_t},
        ]
    if packing == "one_mesh":
        combined_v = np.vstack([outer_v, inner_v]).tolist()
        combined_t = outer_t + [[a + len(outer_v), b + len(outer_v), c + len(outer_v)] for a, b, c in inner_t]
        return [{"name": "combined", "vertices": combined_v, "triangles": combined_t}]
    raise ValueError(f"Unknown packing: {packing}")


@pytest.mark.parametrize("variant", ["outward", "inverted", "open", "inconsistent"])
@pytest.mark.parametrize("packing", ["two_meshes", "one_mesh"])
@pytest.mark.parametrize("transform_name", ["identity", "translation", "Rz37_translation"])
def test_component_matrix(variant, packing, transform_name):
    """24 synthetic cases (4 variants x 2 packings x 3 transforms)."""
    helper = _get_helper()
    meshes = _build_outer_inner(variant, packing, transform_name)
    input_copy = copy.deepcopy(meshes)

    res1, res2, res3 = helper(meshes), helper(meshes), helper(meshes)
    assert res1 == res2 == res3 and meshes == input_copy

    rows = res1
    assert len(rows) == 2
    outer_row = next(r for r in rows if (r["mesh"] == "outer" if packing == "two_meshes" else 0 in r["triangle_ids"]))
    inner_row = next(r for r in rows if (r["mesh"] == "inner" if packing == "two_meshes" else 12 in r["triangle_ids"]))

    assert outer_row["mesh"] == ("outer" if packing == "two_meshes" else "combined")
    assert outer_row["n_triangles"] == 12 and outer_row["triangle_ids"] == list(range(12))
    assert outer_row["eligible"] is True and outer_row["reasons"] == []
    assert outer_row["status"] == "measured" and outer_row["sign"] == 1
    assert math.isclose(outer_row["signed_volume"], 1e6, rel_tol=1e-6)

    exp_tris = 10 if variant == "open" else 12
    exp_ids = list(range(exp_tris)) if packing == "two_meshes" else list(range(12, 12 + exp_tris))
    assert inner_row["mesh"] == ("inner" if packing == "two_meshes" else "combined")
    assert inner_row["n_triangles"] == exp_tris and inner_row["triangle_ids"] == exp_ids

    if variant in ("outward", "inverted"):
        exp_sign = 1 if variant == "outward" else -1
        assert inner_row["eligible"] is True and inner_row["reasons"] == []
        assert inner_row["status"] == "measured" and inner_row["sign"] == exp_sign
        assert math.isclose(inner_row["signed_volume"], exp_sign * 0.008, rel_tol=1e-6)
        assert outer_row["signed_volume"] + inner_row["signed_volume"] > 0
    elif variant == "open":
        assert inner_row["eligible"] is False and inner_row["reasons"] == ["open_or_nonmanifold_edge"]
        assert inner_row["status"] == "not_measured" and inner_row["signed_volume"] is None and inner_row["sign"] is None
    elif variant == "inconsistent":
        assert inner_row["eligible"] is False and "inconsistent_winding" in inner_row["reasons"]
        assert inner_row["status"] == "not_measured" and inner_row["signed_volume"] is None and inner_row["sign"] is None


def test_boundary_primary_reason():
    """Open box must report open_or_nonmanifold_edge only."""
    helper = _get_helper()
    open_box = {
        "name": "open_box",
        "vertices": [list(v) for v in _UNIT_BOX_VERTS],
        "triangles": [list(t) for t in _BOX_TRIS[2:]],
    }
    input_copy = copy.deepcopy(open_box)
    res = helper([open_box])
    assert len(res) == 1
    row = res[0]
    assert row["mesh"] == "open_box" and row["n_triangles"] == 10 and row["triangle_ids"] == list(range(10))
    assert row["eligible"] is False and row["status"] == "not_measured" and row["signed_volume"] is None
    assert row["reasons"] == ["open_or_nonmanifold_edge"] and open_box == input_copy


@pytest.mark.parametrize("packing", ["two_meshes", "one_mesh"])
@pytest.mark.parametrize("transform_name", ["identity", "translation", "Rz37_translation"])
def test_baseline_blind_spot_unchanged(packing, transform_name):
    """Check orientation baseline misses enclosed inverted inner box."""
    helper = _get_helper()
    meshes = _build_outer_inner("inverted", packing, transform_name)
    dump = {"meshes": meshes}
    dump_before = copy.deepcopy(dump)

    base_before = checks.check_orientation(from_dump(dump), {"weld_m": 0.001})
    assert base_before["status"] == "pass" and base_before["value"] == 0
    if packing == "two_meshes":
        inner_mesh_row = next(m for m in base_before["details"]["meshes"] if m["name"] == "inner")
        assert inner_mesh_row["judged_faces"] == 0 and "inner" in base_before["details"]["unjudged_meshes"]

    cand = helper(dump["meshes"])
    assert len(cand) == 2
    inner_cand = next(r for r in cand if (r["mesh"] == "inner" if packing == "two_meshes" else 12 in r["triangle_ids"]))
    assert inner_cand["status"] == "measured" and inner_cand["eligible"] is True and inner_cand["sign"] == -1
    assert math.isclose(inner_cand["signed_volume"], -0.008, rel_tol=1e-6)

    base_after = checks.check_orientation(from_dump(dump), {"weld_m": 0.001})
    assert base_after == base_before and dump == dump_before


def test_diagnostic_documentation():
    """Documentation must define helper and scope boundaries."""
    doc_path = ROOT / "docs" / "qa" / "component-volume.md"
    assert doc_path.is_file()
    text = doc_path.read_text(encoding="utf-8")
    lower = text.lower()

    assert "component_signed_volumes" in text
    assert "open_or_nonmanifold_edge" in text
    assert "optional" in lower
    assert "report-only" in lower or "report only" in lower
    assert "negative" in lower
    assert "defect" in lower
    assert "self-intersection" in lower
    assert "not proved" in lower or "no certification" in lower or "does not prove" in lower
    assert "delivery_passed=false" in text or "delivery_passed" in text


def test_empty_input():
    """Empty list and meshes with no triangles return empty list."""
    helper = _get_helper()
    assert helper([]) == []
    assert helper([{"name": "empty", "vertices": [], "triangles": []}]) == []
    assert helper([{"name": "no_tris", "vertices": [[0.0, 0.0, 0.0]], "triangles": []}]) == []
    assert helper([
        {"name": "m1", "vertices": [], "triangles": []},
        {"name": "m2", "vertices": [[1.0, 2.0, 3.0]], "triangles": []},
    ]) == []


def test_ineligible_topology():
    """Topology defects report not_measured and specific reason codes."""
    helper = _get_helper()

    # Degenerate triangle: collapsed indices [0, 0, 1]
    degen_tris = [list(t) for t in _BOX_TRIS]
    degen_tris[0] = [0, 0, 1]
    res_degen = helper([{"name": "degen", "vertices": [list(v) for v in _UNIT_BOX_VERTS], "triangles": degen_tris}])
    assert len(res_degen) == 1 and res_degen[0]["status"] == "not_measured"
    assert res_degen[0]["eligible"] is False and res_degen[0]["signed_volume"] is None
    assert "degenerate_triangle" in res_degen[0]["reasons"]

    # Nonmanifold edge: edge [0, 1] shared by 3 triangles
    nonman_tris = [list(t) for t in _BOX_TRIS] + [[0, 1, 6]]
    res_nonman = helper([{"name": "nonman_edge", "vertices": [list(v) for v in _UNIT_BOX_VERTS], "triangles": nonman_tris}])
    assert len(res_nonman) == 1 and res_nonman[0]["status"] == "not_measured"
    assert res_nonman[0]["eligible"] is False and res_nonman[0]["signed_volume"] is None
    assert "open_or_nonmanifold_edge" in res_nonman[0]["reasons"]

    # Vertex-touching boxes control: touching at vertex 0 form 2 edge-separated components
    neg_cube_verts = (np.asarray(_UNIT_BOX_VERTS, float) - 1.0).tolist()
    remap = {6: 0, **{old: new for new, old in enumerate([0, 1, 2, 3, 4, 5, 7], start=8)}}
    fan_verts = [list(v) for v in _UNIT_BOX_VERTS] + [neg_cube_verts[i] for i in [0, 1, 2, 3, 4, 5, 7]]
    fan_tris = [list(t) for t in _BOX_TRIS] + [[remap[a], remap[b], remap[c]] for a, b, c in _BOX_TRIS]
    res_touch = helper([{"name": "vertex_touching_boxes", "vertices": fan_verts, "triangles": fan_tris}])
    assert len(res_touch) == 2
    for r in res_touch:
        assert r["eligible"] is True and r["status"] == "measured" and r["sign"] == 1
        assert math.isclose(r["signed_volume"], 1.0, rel_tol=1e-6) and r["reasons"] == []

    # Single-component disconnected-fan fixture: two cones meeting at vertex 0 connected by prism
    hourglass_verts = [
        [0.0, 0.0, 0.0], [-1.0, -1.0, 1.0], [1.0, -1.0, 1.0], [0.0, 1.0, 1.0],
        [-1.0, -1.0, 2.0], [1.0, -1.0, 2.0], [0.0, 1.0, 2.0],
    ]
    hourglass_tris = [
        [0, 2, 1], [0, 3, 2], [0, 1, 3], [1, 2, 5], [1, 5, 4],
        [2, 3, 6], [2, 6, 5], [3, 1, 4], [3, 4, 6], [0, 4, 5], [0, 5, 6], [0, 6, 4],
    ]
    res_hg = helper([{"name": "hourglass", "vertices": hourglass_verts, "triangles": hourglass_tris}])
    assert len(res_hg) == 1 and res_hg[0]["status"] == "not_measured"
    assert res_hg[0]["eligible"] is False and res_hg[0]["signed_volume"] is None
    assert res_hg[0]["reasons"] == ["vertex_not_single_fan"]


def test_index_edges_only():
    """Separation strictly by index edges without coordinate welding or cross-mesh merging."""
    helper = _get_helper()

    # Coincident index-disjoint boxes in a single mesh
    v_coincident = [list(v) for v in _UNIT_BOX_VERTS] * 2
    t_coincident = [list(t) for t in _BOX_TRIS] + [[a + 8, b + 8, c + 8] for a, b, c in _BOX_TRIS]
    res_coinc = helper([{"name": "coincident", "vertices": v_coincident, "triangles": t_coincident}])
    assert len(res_coinc) == 2 and res_coinc[0]["triangle_ids"] == list(range(12)) and res_coinc[1]["triangle_ids"] == list(range(12, 24))
    assert res_coinc[0]["eligible"] is True and res_coinc[1]["eligible"] is True
    assert math.isclose(res_coinc[0]["signed_volume"], 1.0, rel_tol=1e-6) and math.isclose(res_coinc[1]["signed_volume"], 1.0, rel_tol=1e-6)

    # Vertex-touching boxes with disjoint indices in a single mesh
    box2_touch_verts = (np.asarray(_UNIT_BOX_VERTS, float) + [1.0, 0.0, 0.0]).tolist()
    res_touch = helper([{"name": "touching", "vertices": [list(v) for v in _UNIT_BOX_VERTS] + box2_touch_verts, "triangles": t_coincident}])
    assert len(res_touch) == 2 and res_touch[0]["triangle_ids"] == list(range(12)) and res_touch[1]["triangle_ids"] == list(range(12, 24))
    assert res_touch[0]["eligible"] is True and res_touch[1]["eligible"] is True
    assert math.isclose(res_touch[0]["signed_volume"], 1.0, rel_tol=1e-6) and math.isclose(res_touch[1]["signed_volume"], 1.0, rel_tol=1e-6)

    # Per-mesh isolation
    m_a = {"name": "mesh_a", "vertices": [list(v) for v in _UNIT_BOX_VERTS], "triangles": [list(t) for t in _BOX_TRIS]}
    m_b = {"name": "mesh_b", "vertices": [list(v) for v in _UNIT_BOX_VERTS], "triangles": [list(t) for t in _BOX_TRIS]}
    res_iso = helper([m_a, m_b])
    assert len(res_iso) == 2 and res_iso[0]["mesh"] == "mesh_a" and res_iso[1]["mesh"] == "mesh_b"
    assert res_iso[0]["eligible"] is True and res_iso[1]["eligible"] is True
    assert math.isclose(res_iso[0]["signed_volume"], 1.0, rel_tol=1e-6) and math.isclose(res_iso[1]["signed_volume"], 1.0, rel_tol=1e-6)


def test_malformed_input_validation():
    """Malformed input preconditions raise ValueError."""
    helper = _get_helper()
    cases = [
        ("invalid_not_a_list", "list"),
        (["not_a_dict"], "dictionary"),
        ([{"name": "missing_triangles", "vertices": []}], "must contain"),
        ([{"name": 42, "vertices": [], "triangles": []}], "string"),
        ([{"name": "m_nan", "vertices": [[np.nan, 0.0, 0.0]], "triangles": []}], "non-finite"),
        ([{"name": "m_inf", "vertices": [[0.0, float("inf"), 0.0]], "triangles": []}], "non-finite"),
        ([{"name": "m_float_idx", "vertices": [[0.0, 0.0, 0.0]], "triangles": [[0.5, 0.0, 0.0]]}], "integer"),
        ([{"name": "m_neg_idx", "vertices": [[0.0, 0.0, 0.0]], "triangles": [[-1, 0, 0]]}], "negative"),
        ([{"name": "m_oob", "vertices": [[0.0, 0.0, 0.0]], "triangles": [[0, 0, 5]]}], "out of bounds"),
    ]
    for arg, pattern in cases:
        with pytest.raises(ValueError, match=pattern):
            helper(arg)


@pytest.mark.parametrize(
    ("raw_v", "raw_t"),
    [
        (np.empty((0, 4), dtype=float), np.empty((0, 3), dtype=int)),
        (np.empty((0,), dtype=float), np.empty((0, 3), dtype=int)),
        (np.empty((0, 2), dtype=float), np.empty((0, 3), dtype=int)),
        (np.empty((0, 3, 1), dtype=float), np.empty((0, 3), dtype=int)),
        (np.empty((0, 3), dtype=np.complex128), np.empty((0, 3), dtype=int)),
        (np.array([[1.0 + 1.0j, 0.0, 0.0]]), np.empty((0, 3), dtype=int)),
        (np.empty((0, 3), dtype=float), np.empty((0, 4), dtype=int)),
        (np.empty((0, 3), dtype=float), np.empty((0,), dtype=int)),
        (np.empty((0, 3), dtype=float), np.empty((0, 2), dtype=int)),
        (np.empty((0, 3), dtype=float), np.empty((0, 3, 1), dtype=int)),
        (np.empty((0, 3), dtype=float), np.empty((0, 3), dtype=float)),
    ],
)
def test_malformed_ndarray_regressions(raw_v, raw_t):
    """Parametrized ndarray validation: invalid shapes and non-real dtypes raise ValueError."""
    helper = _get_helper()
    with pytest.raises(ValueError):
        helper([{"name": "m", "vertices": raw_v, "triangles": raw_t}])


def test_ndarray_inputs_success():
    """Exercise valid ndarray vertex and triangle inputs."""
    helper = _get_helper()
    verts = np.asarray(_UNIT_BOX_VERTS, dtype=float)
    tris = np.asarray(_BOX_TRIS, dtype=np.int64)
    res = helper([{"name": "box", "vertices": verts, "triangles": tris}])
    assert len(res) == 1 and res[0]["eligible"] is True
    assert res[0]["status"] == "measured" and res[0]["sign"] == 1
    assert math.isclose(res[0]["signed_volume"], 1.0, rel_tol=1e-6)


# ---------------------------------------------------------------------------
# Task #110: Single-vertex fan performance and incidence tests (synthetic data)
# ---------------------------------------------------------------------------


class SyntheticAccessCountingArray(np.ndarray):
    """Synthetic ndarray subclass tracking integer-row __getitem__ accesses."""

    row_read_count: int

    def __new__(cls, input_array):
        obj = np.asarray(input_array).view(cls)
        obj.row_read_count = 0
        return obj

    def __array_finalize__(self, obj):
        if obj is None:
            return
        self.row_read_count = getattr(obj, "row_read_count", 0)

    def __getitem__(self, item):
        if isinstance(item, (int, np.integer)):
            self.row_read_count += 1
        elif isinstance(item, tuple) and len(item) > 0 and isinstance(item[0], (int, np.integer)):
            self.row_read_count += 1
        return super().__getitem__(item)


def _build_synthetic_bipyramid(
    n: int, radius: float = 1.0, height: float = 1.0
) -> tuple[np.ndarray, np.ndarray]:
    """Generate synthetic closed bipyramid mesh with n equatorial vertices and 2*n triangles."""
    theta = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False)
    v_eq = np.column_stack([radius * np.cos(theta), radius * np.sin(theta), np.zeros(n, dtype=float)])
    v_top = np.array([[0.0, 0.0, height]], dtype=float)
    v_bot = np.array([[0.0, 0.0, -height]], dtype=float)
    vertices = np.vstack([v_eq, v_top, v_bot])

    top = n
    bot = n + 1
    tris = []
    for i in range(n):
        nxt = (i + 1) % n
        tris.append([i, nxt, top])
        tris.append([nxt, i, bot])
    triangles = np.array(tris, dtype=np.int64)
    return vertices, triangles


def _reference_fan_oracle(
    triangles: np.ndarray, comp_tri_ids: list[int], unique_verts: list[int]
) -> bool:
    """Synthetic brute-force reference fan oracle matching current semantics.

    Checks vertex fans per component subset, handling repeated triangle indices
    once per vertex. Does not mutate inputs.
    """
    from collections import defaultdict, deque

    for v_idx in unique_verts:
        incident_tris = [t for t in comp_tri_ids if v_idx in triangles[t]]
        if len(incident_tris) <= 1:
            continue

        adj: dict[int, list[int]] = defaultdict(list)
        edge_neighbor_to_tris: dict[int, list[int]] = defaultdict(list)
        for t in incident_tris:
            for other in {x for x in triangles[t] if x != v_idx}:
                edge_neighbor_to_tris[other].append(t)

        for tris in edge_neighbor_to_tris.values():
            if len(tris) > 1:
                first = tris[0]
                for other in tris[1:]:
                    adj[first].append(other)
                    adj[other].append(first)

        visited: set[int] = set()
        fan_count = 0
        for t in incident_tris:
            if t not in visited:
                fan_count += 1
                if fan_count > 1:
                    return False
                q = deque([t])
                visited.add(t)
                while q:
                    curr = q.popleft()
                    for nbr in adj[curr]:
                        if nbr not in visited:
                            visited.add(nbr)
                            q.append(nbr)
    return True


@pytest.mark.parametrize("n", [40, 80])
def test_check_single_vertex_fans_linear_row_access_regression(n: int):
    """Regression test: _check_single_vertex_fans must perform linear row accesses.

    With O(V*F) face scanning per vertex, reads grow quadratically and exceed 12*F.
    Building incidence once per component keeps reads <= 12*number_faces.
    """
    from twinqa.geometry.component_volume import _check_single_vertex_fans

    _, triangles_raw = _build_synthetic_bipyramid(n)
    counting_triangles = SyntheticAccessCountingArray(triangles_raw)
    number_faces = len(counting_triangles)
    comp_tri_ids = list(range(number_faces))
    unique_verts = list(range(n + 2))

    is_single_fan = _check_single_vertex_fans(counting_triangles, comp_tri_ids, unique_verts)
    assert is_single_fan is True
    assert counting_triangles.row_read_count <= 12 * number_faces


def test_check_single_vertex_fans_oracle_random_cases():
    """Verify _check_single_vertex_fans against seeded brute-force oracle across 100 cases."""
    import random
    from twinqa.geometry.component_volume import _check_single_vertex_fans

    rng = random.Random(110)
    for i in range(100):
        if i == 0:
            # Empty triangles, empty comp_tri_ids, empty unique_verts
            triangles = np.empty((0, 3), dtype=np.int64)
            comp_tri_ids = []
            unique_verts = []
        elif i == 1:
            # Empty comp_tri_ids with non-empty triangles
            triangles = np.array([[0, 1, 2], [2, 3, 0]], dtype=np.int64)
            comp_tri_ids = []
            unique_verts = [0, 1, 2, 3]
        elif i == 2:
            # Repeated triangle indices in comp_tri_ids
            triangles = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64)
            comp_tri_ids = [0, 0, 1, 1, 0]
            unique_verts = [0, 1, 2, 3]
        elif i == 3:
            # Empty unique_verts
            triangles = np.array([[0, 1, 2]], dtype=np.int64)
            comp_tri_ids = [0]
            unique_verts = []
        else:
            n_v = rng.randint(1, 8)
            n_t = rng.randint(0, 12)
            if n_t == 0:
                triangles = np.empty((0, 3), dtype=np.int64)
                comp_tri_ids = []
                unique_verts = list(range(n_v)) if rng.random() > 0.5 else []
            else:
                raw_tris = [[rng.randint(0, n_v - 1) for _ in range(3)] for _ in range(n_t)]
                triangles = np.array(raw_tris, dtype=np.int64)
                subset_size = rng.randint(0, 15)
                comp_tri_ids = [rng.randint(0, n_t - 1) for _ in range(subset_size)]
                if rng.random() < 0.2:
                    unique_verts = sorted(list(set(rng.randint(0, n_v - 1) for _ in range(rng.randint(0, n_v)))))
                else:
                    unique_verts = list(range(n_v))

        tri_before = triangles.copy()
        comp_before = list(comp_tri_ids)
        verts_before = list(unique_verts)

        actual = _check_single_vertex_fans(triangles, comp_tri_ids, unique_verts)
        expected = _reference_fan_oracle(triangles, comp_tri_ids, unique_verts)

        assert actual == expected
        assert np.array_equal(triangles, tri_before)
        assert comp_tri_ids == comp_before
        assert unique_verts == verts_before


def test_reordered_triangle_and_inverted_box_controls():
    """Synthetic controls for deterministic triangle order invariance and inverted orientation."""
    helper = _get_helper()

    # 1. Inverted box control: reversed winding must still be recognized as closed single-fan manifold
    inv_tris = [[a, c, b] for a, b, c in _BOX_TRIS]
    res_inv = helper([{"name": "synthetic_inverted_box", "vertices": _UNIT_BOX_VERTS, "triangles": inv_tris}])
    assert len(res_inv) == 1
    assert res_inv[0]["eligible"] is True
    assert res_inv[0]["status"] == "measured"
    assert res_inv[0]["sign"] == -1
    assert math.isclose(res_inv[0]["signed_volume"], -1.0, rel_tol=1e-6)
    assert res_inv[0]["reasons"] == []

    # 2. Deterministic reordered triangles on valid closed box: output must remain identical
    perm = [5, 2, 11, 0, 7, 1, 9, 3, 8, 4, 10, 6]
    reord_box_tris = [_BOX_TRIS[i] for i in perm]
    res_reord_box = helper([{"name": "synthetic_reordered_box", "vertices": _UNIT_BOX_VERTS, "triangles": reord_box_tris}])
    assert len(res_reord_box) == 1
    assert res_reord_box[0]["eligible"] is True
    assert res_reord_box[0]["status"] == "measured"
    assert res_reord_box[0]["sign"] == 1
    assert math.isclose(res_reord_box[0]["signed_volume"], 1.0, rel_tol=1e-6)
    assert res_reord_box[0]["reasons"] == []

    # 3. Deterministic reordered triangles on disconnected-fan hourglass: must preserve ineligible defect
    hourglass_verts = [
        [0.0, 0.0, 0.0], [-1.0, -1.0, 1.0], [1.0, -1.0, 1.0], [0.0, 1.0, 1.0],
        [-1.0, -1.0, 2.0], [1.0, -1.0, 2.0], [0.0, 1.0, 2.0],
    ]
    hourglass_tris = [
        [0, 2, 1], [0, 3, 2], [0, 1, 3], [1, 2, 5], [1, 5, 4],
        [2, 3, 6], [2, 6, 5], [3, 1, 4], [3, 4, 6], [0, 4, 5], [0, 5, 6], [0, 6, 4],
    ]
    reord_hg_tris = hourglass_tris[::-1]
    res_reord_hg = helper([{"name": "synthetic_reordered_hourglass", "vertices": hourglass_verts, "triangles": reord_hg_tris}])
    assert len(res_reord_hg) == 1
    assert res_reord_hg[0]["eligible"] is False
    assert res_reord_hg[0]["status"] == "not_measured"
    assert res_reord_hg[0]["signed_volume"] is None
    assert res_reord_hg[0]["reasons"] == ["vertex_not_single_fan"]


@pytest.mark.parametrize("n", [250, 500, 1000])
def test_benchmark_synthetic_bipyramid_component_signed_volumes(n: int):
    """Descriptive performance benchmark for synthetic closed bipyramid components.

    Produces synthetic bipyramid with n equatorial vertices and 2*n triangles (500, 1000, 2000).
    Times component_signed_volumes with time.perf_counter, prints elapsed seconds without timing assertions.
    Asserts one eligible positive measured component and matches analytical volume.
    """
    import time

    helper = _get_helper()
    vertices, triangles = _build_synthetic_bipyramid(n)
    number_faces = len(triangles)
    assert number_faces == 2 * n

    start_time = time.perf_counter()
    results = helper([{"name": f"synthetic_bipyramid_n{n}", "vertices": vertices, "triangles": triangles}])
    elapsed_seconds = time.perf_counter() - start_time
    print(f"\n[benchmark] synthetic bipyramid n={n} ({number_faces} triangles): elapsed = {elapsed_seconds:.6f} s")

    assert len(results) == 1
    row = results[0]
    assert row["eligible"] is True
    assert row["status"] == "measured"
    assert row["sign"] == 1
    assert row["reasons"] == []
    assert row["n_triangles"] == number_faces

    analytical_volume = (n / 3.0) * math.sin(2.0 * math.pi / n)
    assert math.isclose(row["signed_volume"], analytical_volume, rel_tol=1e-7)

