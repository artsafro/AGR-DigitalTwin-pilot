"""Tests for planar polygon self-intersection auditing in mesh_audit.

Task #91 adoption tests covering bounded planar proper-crossing semantics.
Synthetic fixtures only; no delivery certification.
"""
from pathlib import Path
import pytest
from technical_library.mesh_audit.core import inspect_mesh

RAW_OUTLINES = {
    "square": ([(0, 0), (3, 0), (3, 3), (0, 3)], 0),
    "l": ([(0, 0), (3, 0), (3, 1), (1, 1), (1, 3), (0, 3)], 0),
    "u": ([(0, 0), (3, 0), (3, 3), (2, 3), (2, 1), (1, 1), (1, 3), (0, 3)], 0),
    "arrow": ([(0, 0), (3, 0), (1, 1), (3, 3), (0, 3)], 0),
    "crossed_a": ([(0, 0), (3, 3), (0, 3), (3, 0)], 1),
    "crossed_b": ([(0, 0), (4, 3), (0, 4), (3, 0)], 1),
}

PLANES = {
    "XY": lambda u, v: (u, v, 0),
    "XZ": lambda u, v: (u, 0, v),
    "YZ": lambda u, v: (0, u, v),
}


def _generate_variants():
    variants = []
    for name, (pts, expected) in RAW_OUTLINES.items():
        n = len(pts)
        for plane_name, proj in PLANES.items():
            for direction in ("forward", "reversed"):
                base = pts if direction == "forward" else pts[::-1]
                for shift in range(n):
                    shifted = base[shift:] + base[:shift]
                    v3d = [proj(u, v) for u, v in shifted]
                    faces = [tuple(range(n))]
                    var_id = f"{name}-{plane_name}-{direction}-s{shift}"
                    variants.append((var_id, v3d, faces, expected))
    return variants


ALL_VARIANTS = _generate_variants()
VARIANT_IDS = [v[0] for v in ALL_VARIANTS]


@pytest.mark.parametrize(
    "var_id,vertices,faces,expected_crossings",
    ALL_VARIANTS,
    ids=VARIANT_IDS,
)
def test_planar_outline_labels(var_id, vertices, faces, expected_crossings):
    result = inspect_mesh(vertices, faces)
    assert result["self_intersecting_polygons"] == expected_crossings
    assert result["delivery_passed"] is False
    assert result["intersection_test_performed"] is False


def test_three_repetitions_have_identical_counters():
    runs = []
    for _ in range(3):
        current_run = []
        for var_id, vertices, faces, expected in ALL_VARIANTS:
            rep = inspect_mesh(vertices, faces)
            assert rep["self_intersecting_polygons"] == expected, (
                f"Variant {var_id} expected {expected}, got {rep['self_intersecting_polygons']}"
            )
            current_run.append(rep)
        runs.append(current_run)

    assert runs[0] == runs[1] == runs[2]


def test_other_report_counters_unchanged():
    u_vertices = [
        (0, 0, 0),
        (3, 0, 0),
        (3, 3, 0),
        (2, 3, 0),
        (2, 1, 0),
        (1, 1, 0),
        (1, 3, 0),
        (0, 3, 0),
    ]
    u_faces = [(0, 1, 2, 3, 4, 5, 6, 7)]
    result = inspect_mesh(u_vertices, u_faces)
    expected_report = {
        "boundary_edges": 8,
        "connected_components": 1,
        "delivery_passed": False,
        "duplicate_faces_by_vertex_set": 0,
        "duplicate_vertex_decimals": 8,
        "duplicate_vertices_rounded": 0,
        "extent_m": [3, 3, 0],
        "faces": 1,
        "inconsistent_winding_edges": 0,
        "intersection_test_performed": False,
        "loose_edges": 0,
        "material_face_counts": {0: 1},
        "material_interface_edges": 0,
        "multi_face_edges": 0,
        "near_duplicate_threshold_m": 0.001,
        "near_duplicate_vertices": 0,
        "polygon_sizes": {8: 1},
        "self_intersecting_polygons": 0,
        "triangles": 6,
        "vertices": 8,
        "vertices_unused_by_faces": 0,
        "zero_area_faces_fan": 0,
    }
    assert result == expected_report


def test_readme_documents_bounded_semantics():
    readme_path = (
        Path(__file__).resolve().parent.parent
        / "technical_library"
        / "mesh_audit"
        / "README.md"
    )
    assert readme_path.is_file(), f"README not found at {readme_path}"
    content = readme_path.read_text(encoding="utf-8").lower()

    # 1e-10 tolerance
    assert "1e-10" in content, "README should document 1e-10 tolerance"

    # projected proper crossings
    assert any(term in content for term in ("project", "проекц")), (
        "README should document projection"
    )
    assert (
        any(term in content for term in ("proper", "строг", "собственн"))
        and any(term in content for term in ("cross", "пересеч"))
    ), "README should document proper crossings"

    # unsupported scope: nonplanar, overlap, touch, repeated vertices
    assert any(
        term in content for term in ("nonplanar", "non-planar", "непланар")
    ), "README should document unsupported nonplanar faces"
    assert any(
        term in content for term in ("overlap", "наложен", "нахлест", "перекрыт")
    ), "README should document unsupported overlaps"
    assert any(
        term in content for term in ("touch", "касан", "соприкосновен")
    ), "README should document unsupported touches"
    assert any(
        term in content for term in ("repeated", "повтор")
    ), "README should document unsupported repeated vertices"

    # report-only flags
    assert (
        "delivery_passed" in content
        or "report-only" in content
        or "report only" in content
        or "отчет" in content
        or "отчёт" in content
    ), "README should document report-only status"


def test_empty_mesh_remains_report_only():
    result = inspect_mesh([], [])
    assert result["self_intersecting_polygons"] == 0
    assert result["delivery_passed"] is False
    assert result["intersection_test_performed"] is False


def test_collinear_face_preserves_zero_area_report():
    result = inspect_mesh([(0, 0, 0), (1, 0, 0), (2, 0, 0)], [(0, 1, 2)])
    assert result["self_intersecting_polygons"] == 0
    assert result["zero_area_faces_fan"] == 1
    assert result["delivery_passed"] is False
    assert result["intersection_test_performed"] is False


def test_collinear_quad_exercises_no_usable_cross_fallback():
    # 4 collinear vertices; exercises combinations loop and best_mag2 <= 0.0 fallback
    vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (3.0, 0.0, 0.0)]
    faces = [(0, 1, 2, 3)]
    result = inspect_mesh(vertices, faces)
    assert result["self_intersecting_polygons"] == 0
    assert result["zero_area_faces_fan"] == 1
    assert result["delivery_passed"] is False
    assert result["intersection_test_performed"] is False


def test_determinant_tolerance_boundary_on_tiny_bowtie():
    # Tests determinant tolerance (+/-1e-10 m^2), not general degeneracy certification.
    # (a) s = 1e-6 bowtie: orientation determinant is s*s = 1e-12, below 1e-10 tolerance -> 0
    s = 1e-6
    bowtie_tiny = [(0.0, 0.0, 0.0), (s, s, 0.0), (0.0, s, 0.0), (s, 0.0, 0.0)]
    assert inspect_mesh(bowtie_tiny, [(0, 1, 2, 3)])["self_intersecting_polygons"] == 0

    # (b) Exact representable coordinates [(0, 0), (1, h), (0, h), (1, 0)]
    # h = 0.5e-10 (5e-11) -> determinant 5e-11 <= 1e-10 -> 0 (below tolerance)
    h_sub = 0.5e-10
    poly_sub = [(0.0, 0.0, 0.0), (1.0, h_sub, 0.0), (0.0, h_sub, 0.0), (1.0, 0.0, 0.0)]
    assert inspect_mesh(poly_sub, [(0, 1, 2, 3)])["self_intersecting_polygons"] == 0

    # h = 2.0e-10 -> determinant 2e-10 > 1e-10 -> 1 (above tolerance)
    h_super = 2.0e-10
    poly_super = [(0.0, 0.0, 0.0), (1.0, h_super, 0.0), (0.0, h_super, 0.0), (1.0, 0.0, 0.0)]
    assert inspect_mesh(poly_super, [(0, 1, 2, 3)])["self_intersecting_polygons"] == 1


def test_star_polygon_with_multiple_proper_crossings_counts_once():
    # Explicit 5-point star pentagram with 5 verified interior proper crossings:
    # 1. Edge 0 ((0,10)->(3,-1)) x Edge 2 ((-4,6)->(4,6)) at (12/11, 6)
    # 2. Edge 0 ((0,10)->(3,-1)) x Edge 3 ((4,6)->(-3,-1)) at (12/7, 26/7)
    # 3. Edge 1 ((3,-1)->(-4,6)) x Edge 3 ((4,6)->(-3,-1)) at (0, 2)
    # 4. Edge 1 ((3,-1)->(-4,6)) x Edge 4 ((-3,-1)->(0,10)) at (-12/7, 26/7)
    # 5. Edge 2 ((-4,6)->(4,6)) x Edge 4 ((-3,-1)->(0,10)) at (-12/11, 6)
    star_vertices = [
        (0.0, 10.0, 0.0),
        (3.0, -1.0, 0.0),
        (-4.0, 6.0, 0.0),
        (4.0, 6.0, 0.0),
        (-3.0, -1.0, 0.0),
    ]
    star_faces = [(0, 1, 2, 3, 4)]
    result = inspect_mesh(star_vertices, star_faces)
    assert result["self_intersecting_polygons"] == 1
    assert result["delivery_passed"] is False
    assert result["intersection_test_performed"] is False
