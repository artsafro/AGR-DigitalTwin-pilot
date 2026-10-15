"""End-to-end regression tests for facade corner matching in check_facades_max_roundtrip.py.

Round 3 test suite for Task #83 adoption:
- Exercises tools/check_facades_max_roundtrip.py via runpy in an offline fake-bpy environment.
- Fakes bpy.data.objects, mesh matrix_world, vertices, loops, uv_layers, polygons, and mathutils.kdtree.
- Evaluates test_frozen_verdict across 8 synthetic fixtures x 3 independent orders (24 cases).
- Characterizes baseline reusable-neighbor false acceptance flaw on 12 malformed permutations.
"""

from __future__ import annotations

from collections import Counter
import itertools
import json
import math
from pathlib import Path
import runpy
import sys
import types
from typing import Any

import numpy as np
import pytest

from technical_library.uv.corner_match import match_corners, maximum_matching


# ---------------------------------------------------------------------------
# Offline Mock Environment for Blender (bpy) & mathutils.kdtree
# ---------------------------------------------------------------------------

class FakeKDTree:
    """Brute-force KDTree mimicking mathutils.kdtree.KDTree for baseline check."""

    def __init__(self, size: int) -> None:
        self.points: list[tuple[tuple[float, float, float], int]] = []

    def insert(self, co: Any, index: int) -> None:
        self.points.append((tuple(float(v) for v in co[:3]), int(index)))

    def balance(self) -> None:
        pass

    def find_range(
        self, co: Any, radius: float
    ) -> list[tuple[tuple[float, float, float], int, float]]:
        target = tuple(float(v) for v in co[:3])
        return [
            (pt, idx, math.dist(target, pt))
            for pt, idx in self.points
            if math.dist(target, pt) <= radius
        ]


class FakeMatrix:
    """Identity-like transform supporting matrix-vector multiplication (@)."""

    def __matmul__(self, other: Any) -> Any:
        return other


def build_fake_mesh_object(corners: list[list[float]]) -> types.SimpleNamespace:
    """Build a fake Blender object containing 4 triangles (12 corners)."""
    assert len(corners) == 12, f"Expected 12 corners, got {len(corners)}"
    vertices = [types.SimpleNamespace(co=tuple(float(v) for v in c[:3])) for c in corners]
    loops = [types.SimpleNamespace(vertex_index=i) for i in range(12)]
    uv_data = [types.SimpleNamespace(uv=tuple(float(v) for v in c[3:5])) for c in corners]
    polygons = [
        types.SimpleNamespace(
            loop_indices=list(range(f * 3, f * 3 + 3)),
            vertices=list(range(f * 3, f * 3 + 3)),
        )
        for f in range(4)
    ]
    mesh = types.SimpleNamespace(
        vertices=vertices, loops=loops, uv_layers=[types.SimpleNamespace(data=uv_data)], polygons=polygons
    )
    return types.SimpleNamespace(data=mesh, matrix_world=FakeMatrix())


def run_roundtrip_script(
    tmp_path: Path, fake_objects: dict[str, types.SimpleNamespace], reference_dict: dict[str, Any]
) -> None:
    """Test helper to execute tools/check_facades_max_roundtrip.py via runpy."""
    (tmp_path / "blender-reference.json").write_text(json.dumps(reference_dict), encoding="utf-8")
    script_path = Path(__file__).resolve().parent.parent / "tools" / "check_facades_max_roundtrip.py"

    saved_sys_path = list(sys.path)
    saved_argv = list(sys.argv)
    saved_modules = {k: sys.modules.get(k) for k in ("bpy", "mathutils", "mathutils.kdtree")}

    bpy = types.ModuleType("bpy")
    bpy.ops = types.SimpleNamespace(import_scene=types.SimpleNamespace(fbx=lambda filepath=None: None))
    bpy.data = types.SimpleNamespace(objects=fake_objects)
    mathutils = types.ModuleType("mathutils")
    mathutils.kdtree = types.SimpleNamespace(KDTree=FakeKDTree)

    sys.modules["bpy"] = bpy
    sys.modules["mathutils"] = mathutils
    sys.modules["mathutils.kdtree"] = mathutils.kdtree
    sys.argv = ["check_facades_max_roundtrip.py", "--", str(tmp_path)]

    try:
        runpy.run_path(str(script_path), run_name="__main__")
    finally:
        sys.path[:] = saved_sys_path
        sys.argv = saved_argv
        for k, v in saved_modules.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


# ---------------------------------------------------------------------------
# Synthetic Fixtures: 12 corners, 4 triangles each
# ---------------------------------------------------------------------------

BASE_REF: list[list[float]] = [
    [0.0, 0.0, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.1, 0.0], [0.0, 1.0, 0.0, 0.2, 0.0],
    [0.0, 0.0, 0.0, 0.0, 0.1], [1.0, 0.0, 0.0, 0.1, 0.1], [0.0, 1.0, 0.0, 0.2, 0.1],
    [0.0, 0.0, 0.0, 0.0, 0.2], [-1.0, 0.0, 0.0, 0.1, 0.2], [0.0, -1.0, 0.0, 0.2, 0.2],
    [0.0, 0.0, 0.0, 0.0, 0.3], [0.0, 0.0, 1.0, 0.1, 0.3], [0.0, 0.0, -1.0, 0.2, 0.3],
]


def get_synthetic_fixtures() -> dict[str, tuple[list[list[float]], list[list[float]]]]:
    """Return the 8 synthetic fixture pairs: (reference_corners, observed_corners)."""
    base = [list(c) for c in BASE_REF]
    clean_id_ref = [[i * 1.5, i * 2.0, i * 0.5, BASE_REF[i][3], BASE_REF[i][4]] for i in range(12)]
    legit_ref = [list(c) for c in base]
    legit_ref[6] = list(legit_ref[0])

    m1 = [list(c) for c in base]
    m1[0][3:] = base[3][3:]
    m2 = [list(c) for c in base]
    m2[0][3:] = base[3][3:]
    m2[1][3:] = base[4][3:]
    m3 = [list(c) for c in base]
    m3[3][3:] = base[0][3:]
    m3[6][3:] = base[0][3:]
    m4 = [list(c) for c in base]
    m4[9][3:] = base[0][3:]

    return {
        "identical": (clean_id_ref, [list(c) for c in clean_id_ref]),
        "face_corner_reorder": (base, [list(base[i]) for i in (3, 4, 5, 1, 2, 0, 9, 10, 11, 7, 8, 6)]),
        "legitimate_repeats": (legit_ref, [list(c) for c in legit_ref]),
        "distinct_seam_uv": ([list(c) for c in base], [list(c) for c in base]),
        "replace_one_seam": ([list(c) for c in base], m1),
        "duplicate_two_tuples": ([list(c) for c in base], m2),
        "collapse_vertex_uvs": ([list(c) for c in base], m3),
        "replace_island_corner": ([list(c) for c in base], m4),
    }


def reorder_mesh(
    corners_12: list[list[float]], tri_order: list[int], corner_order: list[int]
) -> list[list[float]]:
    """Reorder a 12-corner list by triangle order and corner permutation."""
    tris = [corners_12[i * 3 : (i + 1) * 3] for i in range(4)]
    result: list[list[float]] = []
    for t_idx in tri_order:
        tri = tris[t_idx]
        result.extend([list(tri[c_idx]) for c_idx in corner_order])
    return result


ORDERS: dict[str, tuple[list[int], list[int], list[int], list[int]]] = {
    "identity": ([0, 1, 2, 3], [0, 1, 2], [0, 1, 2, 3], [0, 1, 2]),
    "permuted_cyclic": ([1, 0, 3, 2], [2, 0, 1], [2, 3, 0, 1], [1, 2, 0]),
    "reverse": ([3, 2, 1, 0], [2, 1, 0], [3, 2, 1, 0], [2, 1, 0]),
}

CLEAN_FIXTURES = {"identical", "face_corner_reorder", "legitimate_repeats", "distinct_seam_uv"}
MALFORMED_FIXTURES = {"replace_one_seam", "duplicate_two_tuples", "collapse_vertex_uvs", "replace_island_corner"}
ALL_FIXTURE_NAMES = [
    "identical", "face_corner_reorder", "legitimate_repeats", "distinct_seam_uv",
    "replace_one_seam", "duplicate_two_tuples", "collapse_vertex_uvs", "replace_island_corner",
]
ORDER_NAMES = ["identity", "permuted_cyclic", "reverse"]


# ---------------------------------------------------------------------------
# Baseline Characterization Helper
# ---------------------------------------------------------------------------

def baseline_reusable_neighbor_match(
    observed_corners: list[list[float]],
    expected_corners: list[list[float]],
    radius: float = 0.002,
    uv_tol: float = 2e-6,
) -> tuple[bool, float]:
    """Reproduce baseline reusable-neighbor comparator semantics."""
    expected = np.array(expected_corners)
    tree = FakeKDTree(len(expected))
    for i, c in enumerate(expected):
        tree.insert(c[:3], i)
    tree.balance()

    max_uv = 0.0
    for c_raw in observed_corners:
        c = np.array(c_raw)
        candidates = tree.find_range(c[:3], radius)
        if not candidates:
            return False, float("inf")
        best = min(candidates, key=lambda item: np.max(abs(expected[item[1], 3:] - c[3:])))
        max_uv = max(max_uv, float(np.max(abs(expected[best[1], 3:] - c[3:]))))

    return max_uv < uv_tol, max_uv


def test_baseline_characterization_false_accepts() -> None:
    """Verify baseline reusable-neighbor semantics falsely accepts all 12 malformed cases."""
    fixtures = get_synthetic_fixtures()
    malformed_keys = ["replace_one_seam", "duplicate_two_tuples", "collapse_vertex_uvs", "replace_island_corner"]
    count = 0
    for key in malformed_keys:
        raw_ref, raw_obs = fixtures[key]
        for ref_tri, ref_cor, obs_tri, obs_cor in ORDERS.values():
            ref = reorder_mesh(raw_ref, ref_tri, ref_cor)
            obs = reorder_mesh(raw_obs, obs_tri, obs_cor)
            passed, max_uv = baseline_reusable_neighbor_match(obs, ref)
            assert passed is True
            assert max_uv < 2e-6
            count += 1
    assert count == 12


# ---------------------------------------------------------------------------
# Test Frozen Verdict: 8 synthetic fixtures x 3 independent orders
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture_name", ALL_FIXTURE_NAMES)
@pytest.mark.parametrize("order_name", ORDER_NAMES)
def test_frozen_verdict(tmp_path: Path, fixture_name: str, order_name: str) -> None:
    """End-to-end regression across 8 fixtures x 3 orders against check_facades_max_roundtrip.py."""
    fixtures = get_synthetic_fixtures()
    raw_ref, raw_obs = fixtures[fixture_name]
    ref_tri, ref_cor, obs_tri, obs_cor = ORDERS[order_name]

    ref_corners = reorder_mesh(raw_ref, ref_tri, ref_cor)
    obs_corners = reorder_mesh(raw_obs, obs_tri, obs_cor)

    fake_obj = build_fake_mesh_object(obs_corners)
    ref_data = {"mesh": {"corners": ref_corners, "faces": 4, "degrees": {"3": 4}}}
    fake_objects = {"mesh": fake_obj}

    if fixture_name in CLEAN_FIXTURES:
        run_roundtrip_script(tmp_path, fake_objects, ref_data)
        report_file = tmp_path / "max-roundtrip-qa.json"
        assert report_file.exists()
        report = json.loads(report_file.read_text(encoding="utf-8"))
        assert report["mesh"]["polygon_degrees_preserved"] is True
        assert report["mesh"]["corners_checked"] == 12
    else:
        with pytest.raises(AssertionError):
            run_roundtrip_script(tmp_path, fake_objects, ref_data)


# ---------------------------------------------------------------------------
# Acceptance Tests
# ---------------------------------------------------------------------------

def test_graph_oracle() -> None:
    """Exhaust all square bipartite graphs n=0..3; compare exhaustive oracle and unique eligible edges."""
    for n in range(4):
        for bits in range(1 << (n * n)):
            adj = [[v for v in range(n) if (bits >> (u * n + v)) & 1] for u in range(n)]
            assignment = maximum_matching(adj, n)
            assert len(assignment) == n
            matched_v = [v for v in assignment if v != -1]
            assert len(matched_v) == len(set(matched_v))
            for u, v in enumerate(assignment):
                if v != -1:
                    assert v in adj[u]
            max_oracle = 0
            for p in itertools.product(range(-1, n), repeat=n):
                used = [v for v in p if v != -1]
                if len(used) == len(set(used)) and all(v == -1 or v in adj[u] for u, v in enumerate(p)):
                    max_oracle = max(max_oracle, len(used))
            assert len(matched_v) == max_oracle


def test_threshold_boundaries() -> None:
    """Nextafter below/equal/above XYZ (0.002, inclusive <=) and UV (2e-6, strict <)."""
    ref = [[0.0, 0.0, 0.0, 0.0, 0.0]]
    for axis in range(3):
        for sign in (1.0, -1.0):
            p_below, p_eq, p_above = [0.0] * 3, [0.0] * 3, [0.0] * 3
            p_below[axis] = sign * math.nextafter(0.002, 0.0)
            p_eq[axis] = sign * 0.002
            p_above[axis] = sign * math.nextafter(0.002, 1.0)
            assert match_corners(ref, [[*p_below, 0.0, 0.0]]).perfect is True
            assert match_corners(ref, [[*p_eq, 0.0, 0.0]]).perfect is True
            assert match_corners(ref, [[*p_above, 0.0, 0.0]]).perfect is False

    for uv_idx in (3, 4):
        for sign in (1.0, -1.0):
            o_below, o_eq, o_above = [0.0] * 5, [0.0] * 5, [0.0] * 5
            o_below[uv_idx] = sign * math.nextafter(2e-6, 0.0)
            o_eq[uv_idx] = sign * 2e-6
            o_above[uv_idx] = sign * math.nextafter(2e-6, 1.0)
            assert match_corners(ref, [o_below]).perfect is True
            assert match_corners(ref, [o_eq]).perfect is False
            assert match_corners(ref, [o_above]).perfect is False


def test_spatial_bucket_boundaries() -> None:
    """Verify conservative spatial discovery across bucket boundaries with cell_size=2*xyz_tol."""
    # 1. Literal boundary bug from driver
    ref_lit = [[math.nextafter(0.0, -math.inf), 0.0, 0.0, 0.0, 0.0]]
    obs_lit = [[0.002, 0.0, 0.0, 0.0, 0.0]]
    assert math.dist(ref_lit[0][:3], obs_lit[0][:3]) <= 0.002
    assert match_corners(ref_lit, obs_lit).perfect is True
    assert match_corners(obs_lit, ref_lit).perfect is True

    # 2. All XYZ axes, both signs (+/-), and swapped sides
    for axis in range(3):
        for sign in (1.0, -1.0):
            p1, p2 = [0.0] * 5, [0.0] * 5
            p1[axis] = math.nextafter(0.0, -sign * math.inf)
            p2[axis] = sign * 0.002
            assert math.dist(p1[:3], p2[:3]) <= 0.002
            assert match_corners([p1], [p2]).perfect is True
            assert match_corners([p2], [p1]).perfect is True

    # 3. Translated coordinates (negative edges, normal project magnitudes)
    translations = [
        (-0.004, -0.002, 0.0),
        (-1234.567, 8901.234, -567.89),
        (50000.0, 100000.0, -25000.0),
    ]
    for tx, ty, tz in translations:
        p1 = [tx, ty, tz, 0.0, 0.0]
        p2 = [tx + 0.00195, ty, tz, 0.0, 0.0]
        assert math.dist(p1[:3], p2[:3]) <= 0.002
        assert match_corners([p1], [p2]).perfect is True
        assert match_corners([p2], [p1]).perfect is True


def test_invalid_tolerances() -> None:
    """Optional tolerances must reject invalid nonfinite/nonpositive values with ValueError."""
    c = [[0.0, 0.0, 0.0, 0.0, 0.0]]
    for val in (0.0, -0.002, float("nan"), float("inf"), float("-inf"), "invalid"):
        with pytest.raises(ValueError):
            match_corners(c, c, xyz_tol=val)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            match_corners(c, c, uv_tol=val)  # type: ignore[arg-type]


def test_diagnostic_errors() -> None:
    """Verify nonzero position & UV perturbation errors are derived from assignments."""
    ref = [[0.0, 0.0, 0.0, 0.1, 0.1], [1.0, 0.0, 0.0, 0.2, 0.2]]
    obs = [[1.0 + 0.0012, 0.0, 0.0, 0.2 + 1.2e-6, 0.2], [0.0, 0.0008, 0.0, 0.1, 0.1 + 1.8e-6]]
    res = match_corners(ref, obs)
    assert res.perfect is True
    assert res.cardinality == 2
    assert res.max_position_error_m == pytest.approx(0.0012, abs=1e-9)
    assert res.max_uv_error == pytest.approx(1.8e-6, abs=1e-9)
    assert res.max_position_error_m > 0.0
    assert res.max_uv_error > 0.0
    derived_pos = max(math.dist(obs[u][:3], ref[v][:3]) for u, v in enumerate(res.assignment))
    derived_uv = max(max(abs(obs[u][3] - ref[v][3]), abs(obs[u][4] - ref[v][4])) for u, v in enumerate(res.assignment))
    assert res.max_position_error_m == derived_pos
    assert res.max_uv_error == derived_uv


def test_roundtrip_integration(tmp_path: Path) -> None:
    """Integration check: clean emits report with new keys; corrupted is rejected."""
    fixtures = get_synthetic_fixtures()
    clean_ref, clean_obs = fixtures["distinct_seam_uv"]
    fake_obj = build_fake_mesh_object(clean_obs)
    ref_data = {"mesh": {"corners": clean_ref, "faces": 4, "degrees": {"3": 4}}}
    run_roundtrip_script(tmp_path, {"mesh": fake_obj}, ref_data)
    report_file = tmp_path / "max-roundtrip-qa.json"
    assert report_file.exists()
    report = json.loads(report_file.read_text(encoding="utf-8"))
    assert report["mesh"]["matching_cardinality"] == 12
    assert report["mesh"]["reference_corners"] == 12
    assert report["mesh"]["corners_checked"] == 12
    assert report["mesh"]["polygon_degrees_preserved"] is True

    # Corrupted fixture sharing identical XYZ coordinates with clean reference
    _, malformed_obs = fixtures["replace_one_seam"]
    assert [c[:3] for c in malformed_obs] == [c[:3] for c in clean_ref]
    passed, _ = baseline_reusable_neighbor_match(malformed_obs, clean_ref)
    assert passed is True

    report_file.unlink()
    assert not report_file.exists()
    bad_fake_obj = build_fake_mesh_object(malformed_obs)
    with pytest.raises(AssertionError):
        run_roundtrip_script(tmp_path, {"mesh": bad_fake_obj}, ref_data)
    assert not report_file.exists()


def test_roundtrip_metadata_guards(tmp_path: Path) -> None:
    """Production entrypoint rejects mismatched face counts and degree histograms."""
    fixtures = get_synthetic_fixtures()
    clean_ref, clean_obs = fixtures["identical"]
    fake_obj = build_fake_mesh_object(clean_obs)

    # Wrong face count
    bad_face_data = {"mesh": {"corners": clean_ref, "faces": 5, "degrees": {"3": 4}}}
    with pytest.raises(AssertionError):
        run_roundtrip_script(tmp_path, {"mesh": fake_obj}, bad_face_data)

    # Wrong degree histogram with same face count (4) to independently check degree
    bad_deg_data = {"mesh": {"corners": clean_ref, "faces": 4, "degrees": {"4": 4}}}
    with pytest.raises(AssertionError):
        run_roundtrip_script(tmp_path, {"mesh": fake_obj}, bad_deg_data)


def test_roundtrip_corner_count_guards(tmp_path: Path) -> None:
    """Production script rejects mismatched corner count even if faces/degrees match."""
    fixtures = get_synthetic_fixtures()
    clean_ref, clean_obs = fixtures["identical"]
    fake_obj = build_fake_mesh_object(clean_obs)

    # Add reference corner (13 ref vs 12 obs)
    ref_plus_one = {"mesh": {"corners": clean_ref + [clean_ref[0]], "faces": 4, "degrees": {"3": 4}}}
    with pytest.raises(AssertionError):
        run_roundtrip_script(tmp_path, {"mesh": fake_obj}, ref_plus_one)

    # Remove reference corner (11 ref vs 12 obs)
    ref_minus_one = {"mesh": {"corners": clean_ref[:11], "faces": 4, "degrees": {"3": 4}}}
    with pytest.raises(AssertionError):
        run_roundtrip_script(tmp_path, {"mesh": fake_obj}, ref_minus_one)


def test_augmenting_path_trap() -> None:
    """Eligibility [0,1], [0] under independent permutations; requires augmenting reassignment."""
    ref0 = [0.0, 0.0, 0.0, 0.0, 0.0]
    ref1 = [0.001, 0.0, 0.0, 0.0, 0.0]
    obs0 = [0.0005, 0.0, 0.0, 0.0, 0.0]
    obs1 = [-0.0015, 0.0, 0.0, 0.0, 0.0]
    for p_obs in itertools.permutations([obs0, obs1]):
        for p_ref in itertools.permutations([ref0, ref1]):
            res = match_corners(list(p_ref), list(p_obs))
            assert res.perfect is True
            assert res.cardinality == 2


def test_repeated_calls() -> None:
    """Verify clean, malformed, clean repeated calls to same helper have independent results."""
    clean_ref = [[0.0, 0.0, 0.0, 0.1, 0.1], [1.0, 0.0, 0.0, 0.2, 0.2]]
    clean_obs = [[1.0, 0.0, 0.0, 0.2, 0.2], [0.0, 0.0, 0.0, 0.1, 0.1]]
    malformed_obs = [[1.0, 0.0, 0.0, 0.9, 0.9], [0.0, 0.0, 0.0, 0.1, 0.1]]

    assert match_corners(clean_ref, clean_obs).perfect is True
    assert match_corners(clean_ref, malformed_obs).perfect is False
    assert match_corners(clean_ref, clean_obs).perfect is True


def test_repeated_tuple_multisets() -> None:
    """All 729 length-3 UV-label sequence pairs over 3 labels at coincident XYZ."""
    labels = [(0.1, 0.1), (0.2, 0.2), (0.3, 0.3)]
    seqs = list(itertools.product(labels, repeat=3))
    count = 0
    for seq_ref in seqs:
        for seq_obs in seqs:
            ref = [[0.0, 0.0, 0.0, u, v] for u, v in seq_ref]
            obs = [[0.0, 0.0, 0.0, u, v] for u, v in seq_obs]
            res = match_corners(ref, obs)
            assert res.perfect is (Counter(seq_ref) == Counter(seq_obs))
            assert res.cardinality == sum((Counter(seq_ref) & Counter(seq_obs)).values())
            count += 1
    assert count == 729


def test_empty_corners() -> None:
    """[] vs [] produces empty perfect matching with zero errors."""
    res = match_corners([], [])
    assert res.perfect is True
    assert res.cardinality == 0
    assert res.assignment == []
    assert res.max_uv_error == 0.0
    assert res.max_position_error_m == 0.0


def test_corner_count_guards() -> None:
    """Corner count inequality in both directions returns not perfect and cardinality min(counts)."""
    c0 = [0.0, 0.0, 0.0, 0.1, 0.1]
    r1 = match_corners([c0], [c0, c0])
    assert r1.perfect is False
    assert r1.cardinality == 1
    assert sorted(r1.assignment) == [-1, 0]

    r2 = match_corners([c0, c0], [c0])
    assert r2.perfect is False
    assert r2.cardinality == 1
    assert r2.assignment in ([0], [1])


def test_invalid_corners() -> None:
    """Malformed row widths and non-finite corners must be explicitly rejected with ValueError."""
    valid_corner = [0.0, 0.0, 0.0, 0.0, 0.0]
    for bad_row in [[0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]]:
        with pytest.raises(ValueError):
            match_corners([bad_row], [valid_corner])
        with pytest.raises(ValueError):
            match_corners([valid_corner], [bad_row])

    for bad_val in [float("nan"), float("inf"), float("-inf")]:
        bad_corner = [0.0, bad_val, 0.0, 0.0, 0.0]
        with pytest.raises(ValueError):
            match_corners([bad_corner], [valid_corner])
        with pytest.raises(ValueError):
            match_corners([valid_corner], [bad_corner])

    with pytest.raises(ValueError):
        match_corners(12345, [valid_corner])
