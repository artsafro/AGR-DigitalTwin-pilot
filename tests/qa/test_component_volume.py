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
