"""Reproducible synthetic generated proper-crossing / count-once regression tests.

Follow-up to Task #105 (PR #104) covering bounded planar proper-crossing semantics
beyond hand-written #91 outlines.

Synthetic Data & Scope Notice:
- Synthetic dataset: generated deterministically using random.Random(105) over
  an integer grid [-15, 15]^2.
- Exclusions & Limitations:
  * No degeneracies: Any polygon with any collinear triple is strictly rejected
    using an independent exact integer orientation determinant. No touching edges,
    collinear overlaps, or zero-length edges are present in this test suite.
  * No near-tolerance certification: Vertices are discrete integers well outside
    float epsilon and the +/-1e-10 m^2 determinant tolerance boundary.
  * No delivery certification: inspect_mesh is a read-only basic topology inventory
    and never certifies delivery readiness (delivery_passed and
    intersection_test_performed remain False).
"""
import itertools
import json
from pathlib import Path
import random
import sys

# Ensure repository root is on sys.path for direct standalone invocation
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from technical_library.mesh_audit.core import inspect_mesh


def _orientation_det(p1, p2, p3):
    """Exact integer 2D orientation determinant for p1 -> p2 -> p3.

    Returns:
        > 0 if counterclockwise (left turn)
        < 0 if clockwise (right turn)
        == 0 if collinear
    """
    return (p2[0] - p1[0]) * (p3[1] - p1[1]) - (p2[1] - p1[1]) * (p3[0] - p1[0])


def _has_collinear_triple(poly):
    """Check if any three vertices in poly are collinear using exact integer arithmetic."""
    for p1, p2, p3 in itertools.combinations(poly, 3):
        if _orientation_det(p1, p2, p3) == 0:
            return True
    return False


def _count_proper_crossing_pairs(poly):
    """Independent integer oracle enumerating all nonadjacent edge pairs.

    Checks strict opposite signs on both sides using exact integer orientation
    determinants. Counts and returns the total number of crossing edge pairs.
    Must not call production helpers.
    """
    n = len(poly)
    crossing_pairs = 0
    for i in range(n):
        a = poly[i]
        b = poly[(i + 1) % n]
        for j in range(i + 1, n):
            # Exclude adjacent edge pairs (sharing a vertex)
            if j == i + 1 or (i == 0 and j == n - 1):
                continue
            c = poly[j]
            d = poly[(j + 1) % n]

            # Line ab must strictly separate c and d
            cp1 = _orientation_det(a, b, c)
            cp2 = _orientation_det(a, b, d)
            if not ((cp1 > 0 and cp2 < 0) or (cp1 < 0 and cp2 > 0)):
                continue

            # Line cd must strictly separate a and b
            cp3 = _orientation_det(c, d, a)
            cp4 = _orientation_det(c, d, b)
            if not ((cp3 > 0 and cp4 < 0) or (cp3 < 0 and cp4 > 0)):
                continue

            crossing_pairs += 1

    return crossing_pairs


def test_mesh_audit_generated_crossings():
    """Reproducible synthetic generated proper-crossing regression test.

    Samples 200 accepted non-collinear polygons using random.Random(105) on
    integer grid [-15, 15]^2 with vertex count n in 4..9.
    Evaluates every cyclic shift and both windings across XY, XZ, YZ, and oblique
    projections against the independent integer oracle.
    """
    seed = 105
    rng = random.Random(seed)
    grid_min, grid_max = -15, 15
    grid = [(x, y) for x in range(grid_min, grid_max + 1) for y in range(grid_min, grid_max + 1)]

    attempts = 0
    rejections = 0
    accepted = []

    while len(accepted) < 200:
        attempts += 1
        n = rng.randint(4, 9)
        poly = rng.sample(grid, n)
        if _has_collinear_triple(poly):
            rejections += 1
            continue
        accepted.append(poly)

    # Compute expected crossing pair counts with independent oracle
    polygon_pair_counts = []
    clean_count = 0
    crossed_count = 0
    multiple_count = 0

    for poly in accepted:
        pair_cnt = _count_proper_crossing_pairs(poly)
        polygon_pair_counts.append(pair_cnt)
        if pair_cnt == 0:
            clean_count += 1
        else:
            crossed_count += 1
            if pair_cnt > 1:
                multiple_count += 1

    # Assert population diversity
    assert clean_count > 0, f"Expected clean polygons in population, got {clean_count}"
    assert crossed_count > 0, f"Expected crossed polygons in population, got {crossed_count}"
    assert multiple_count > 0, (
        f"Expected multiple-crossing polygons in population, got {multiple_count}"
    )
    assert clean_count + crossed_count == len(accepted)
    assert multiple_count <= crossed_count

    projections = {
        "XY": lambda x, y: (float(x), float(y), 0.0),
        "XZ": lambda x, y: (float(x), 0.0, float(y)),
        "YZ": lambda x, y: (0.0, float(x), float(y)),
        "oblique": lambda x, y: (float(x), float(y), float(x + 2 * y)),
    }

    variants_checked = 0
    mismatches = []

    for poly_idx, (poly, pair_cnt) in enumerate(zip(accepted, polygon_pair_counts)):
        expected_flag = 1 if pair_cnt > 0 else 0
        n = len(poly)
        for plane_name, proj in projections.items():
            for direction in ("forward", "reversed"):
                base = list(poly) if direction == "forward" else list(reversed(poly))
                for shift in range(n):
                    shifted = base[shift:] + base[:shift]
                    v3d = [proj(x, y) for x, y in shifted]
                    faces = [tuple(range(n))]
                    variants_checked += 1

                    res = inspect_mesh(v3d, faces)

                    flag_error = None
                    if res.get("delivery_passed") is not False:
                        flag_error = "delivery_passed is not False"
                    elif res.get("intersection_test_performed") is not False:
                        flag_error = "intersection_test_performed is not False"

                    got_flag = res.get("self_intersecting_polygons")
                    if got_flag != expected_flag or flag_error is not None:
                        mismatches.append({
                            "poly_index": poly_idx,
                            "n_vertices": n,
                            "plane": plane_name,
                            "direction": direction,
                            "shift": shift,
                            "crossing_pairs": pair_cnt,
                            "expected_flag": expected_flag,
                            "got_flag": got_flag,
                            "flag_error": flag_error,
                            "poly_2d": poly,
                            "vertices_3d": v3d,
                        })

    summary = {
        "seed": seed,
        "bounds": [grid_min, grid_max],
        "attempts": attempts,
        "rejections": rejections,
        "accepted": len(accepted),
        "clean_population": clean_count,
        "crossed_population": crossed_count,
        "multiple_population": multiple_count,
        "populations": {
            "clean": clean_count,
            "crossed": crossed_count,
            "multiple": multiple_count,
        },
        "checked_variants": variants_checked,
        "mismatches": len(mismatches),
    }

    print(json.dumps(summary, indent=2))

    assert len(mismatches) == 0, (
        f"Encountered {len(mismatches)} mismatches out of {variants_checked} variants checked. "
        f"First mismatch context: {json.dumps(mismatches[0], indent=2)}"
    )


if __name__ == "__main__":
    test_mesh_audit_generated_crossings()
