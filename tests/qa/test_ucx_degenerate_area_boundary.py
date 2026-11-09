"""Exact area-threshold characterization for ``degenerate_triangles``.

Inventory against ``tests/qa/test_ucx_audit.py`` (kept there, not repeated): the named
constant ``1e-10``, areas ``1e-12`` and ``1e-8``, a collinear zero-area sliver, a repeated
vertex index, overflow NaN, and ``classify`` review. This module only adds the missing
exact inclusive boundary.

Acceptance:

| # | triangle (single, right)                  | h                             | analytic area h/2 vs T | expected ``degenerate_triangles`` indices |
|---|-------------------------------------------|-------------------------------|-------------------------|-------------------------------------------|
| 1 | (0,0,0),(1,0,0),(0, 2*T, 0)               | 2*T                           | == T (assert h/2 == T) | [0]                                       |
| 2 | (0,0,0),(1,0,0),(0, nextafter(2*T,0), 0)  | math.nextafter(2*T, 0)       | < T                     | [0]                                       |
| 3 | (0,0,0),(1,0,0),(0, nextafter(2*T,inf), 0)| math.nextafter(2*T, inf)     | > T                     | []                                        |

| # | scenario                                                     | expectation                                                                 |
|---|--------------------------------------------------------------|-----------------------------------------------------------------------------|
| 4 | same three h values with area_tol=0.125 (positive dyadic)   | identical [0]/[0]/[] against 0.125, proving parameter forwarding; default T unchanged elsewhere |
| 5 | reversed face winding (swap two vertices) for each h        | identical membership to the non-reversed case                               |
| 6 | mixed triangle order (e.g. a degenerate + a non-degenerate) | returned indices are remapped to input positions, independently of order    |
| 7 | original vertices/faces lists                                | unchanged after the call (no mutation of inputs)                            |
| 8 | task-local mutation: patch the inclusive comparison to strict ``<`` | the equality cases (h == threshold) now FAIL (return [] instead of [0]); unmodified source PASSES |

Synthetic threshold fixtures, not a delivery acceptance.

new-case: UCX degenerate_triangles exact area-threshold (inclusive <=) and area_tol forwarding characterization
"""
import copy
import inspect
import math

import pytest

from twinqa.geometry import ucx_audit as ua
from twinqa.geometry.ucx_audit import DEGENERATE_AREA_M2, degenerate_triangles

T = DEGENERATE_AREA_M2
DYADIC_TOL = 0.125
_INCLUSIVE = "if not math.isfinite(area) or area <= area_tol:"
_STRICT = "if not math.isfinite(area) or area < area_tol:"


def _boundary_cases(threshold):
    """Equal, next float below, next float above for a base-1 right triangle."""
    height = 2.0 * threshold
    return (
        ("equal", height, [0]),
        ("below", math.nextafter(height, 0.0), [0]),
        ("above", math.nextafter(height, math.inf), []),
    )


def _pin_analytic_area(kind, height, threshold):
    """Right triangle (0,0,0),(1,0,0),(0,h,0) has area h/2. Pin that before production."""
    area = height / 2.0
    if kind == "equal":
        assert area == threshold
    elif kind == "below":
        assert area < threshold
    elif kind == "above":
        assert area > threshold
    else:
        raise AssertionError(kind)
    return area


def _single(height, *, reverse=False):
    origin = (0.0, 0.0, 0.0)
    along_x = (1.0, 0.0, 0.0)
    along_y = (0.0, float(height), 0.0)
    verts = [origin, along_y, along_x] if reverse else [origin, along_x, along_y]
    return verts, [(0, 1, 2)]


def _indices(fn, height, area_tol=None, *, reverse=False):
    verts, tris = _single(height, reverse=reverse)
    if area_tol is None:
        return fn(verts, tris)
    return fn(verts, tris, area_tol=area_tol)


def _assemble(heights):
    verts, tris = [], []
    for height in heights:
        base = len(verts)
        verts.extend(((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, float(height), 0.0)))
        tris.append((base, base + 1, base + 2))
    return verts, tris


def _analytic_indices(heights, threshold):
    return [i for i, height in enumerate(heights) if (height / 2.0) <= threshold]


def _strict_degenerate_triangles():
    """In-memory copy of the checker with the area test flipped from ``<=`` to ``<``."""
    source = inspect.getsource(degenerate_triangles)
    assert source.count(_INCLUSIVE) == 1
    mutated = source.replace(_INCLUSIVE, _STRICT, 1)
    assert _STRICT in mutated and _INCLUSIVE not in mutated
    namespace = dict(ua.__dict__)
    exec(mutated, namespace)
    fn = namespace["degenerate_triangles"]
    assert fn is not degenerate_triangles
    return fn


def test_default_threshold_exact_boundary():
    """Rows 1-3: analytic h/2 is == / < / > T, then indices [0], [0], []."""
    cases = _boundary_cases(T)
    for kind, height, _expected in cases:
        _pin_analytic_area(kind, height, T)
    passed = 0
    for kind, height, expected in cases:
        assert _indices(degenerate_triangles, height) == expected
        passed += 1
    assert passed == 3


def test_area_tol_forwarding_leaves_default_threshold():
    """Row 4: area_tol=0.125 forwards; the default parameter stays T."""
    cases = _boundary_cases(DYADIC_TOL)
    for kind, height, _expected in cases:
        _pin_analytic_area(kind, height, DYADIC_TOL)
    passed = 0
    for kind, height, expected in cases:
        assert _indices(degenerate_triangles, height, DYADIC_TOL) == expected
        passed += 1
    constant_before = ua.DEGENERATE_AREA_M2
    default_before = inspect.signature(degenerate_triangles).parameters["area_tol"].default
    _pin_analytic_area("equal", 2.0 * T, T)
    assert _indices(degenerate_triangles, 2.0 * T) == [0]
    passed += 1
    assert (2.0 * DYADIC_TOL) / 2.0 > T
    assert _indices(degenerate_triangles, 2.0 * DYADIC_TOL) == []
    passed += 1
    assert ua.DEGENERATE_AREA_M2 == constant_before == T
    assert inspect.signature(degenerate_triangles).parameters["area_tol"].default == default_before == T
    passed += 1
    assert passed == 6


def test_reversed_winding_keeps_membership():
    """Row 5: swapping two vertices does not change membership for each boundary h."""
    probes = 0
    for threshold, area_tol in ((T, None), (DYADIC_TOL, DYADIC_TOL)):
        cases = _boundary_cases(threshold)
        for kind, height, _expected in cases:
            _pin_analytic_area(kind, height, threshold)
        for kind, height, expected in cases:
            forward = _indices(degenerate_triangles, height, area_tol)
            reverse = _indices(degenerate_triangles, height, area_tol, reverse=True)
            assert forward == expected
            assert reverse == expected
            assert forward == reverse
            probes += 1
    assert probes == 6


def test_mixed_order_indices_follow_input_positions():
    """Row 6: degenerate membership is the input index, for either triangle order."""
    probes = 0
    for threshold, area_tol in ((T, None), (DYADIC_TOL, DYADIC_TOL)):
        _equal, height_eq, _eq_idx = _boundary_cases(threshold)[0]
        _below, height_lo, _lo_idx = _boundary_cases(threshold)[1]
        _above, height_hi, _hi_idx = _boundary_cases(threshold)[2]
        height_unit = 1.0
        assert height_unit / 2.0 > threshold
        orders = (
            ((height_eq, height_unit), [0]),
            ((height_unit, height_eq), [1]),
            ((height_hi, height_eq, height_lo), [1, 2]),
            ((height_lo, height_hi, height_eq), [0, 2]),
        )
        for heights, literal in orders:
            assert _analytic_indices(heights, threshold) == literal
        for heights, literal in orders:
            verts, tris = _assemble(heights)
            if area_tol is None:
                found = degenerate_triangles(verts, tris)
            else:
                found = degenerate_triangles(verts, tris, area_tol=area_tol)
            assert found == literal
            probes += 1
    assert probes == 8


def test_vertices_and_faces_unchanged():
    """Row 7: the call does not mutate the caller's vertex or face lists."""
    probes = []

    def _run(verts, tris, area_tol=None):
        before = copy.deepcopy((verts, tris))
        if area_tol is None:
            degenerate_triangles(verts, tris)
        else:
            degenerate_triangles(verts, tris, area_tol=area_tol)
        assert (verts, tris) == before
        probes.append(1)

    for threshold, area_tol in ((T, None), (DYADIC_TOL, DYADIC_TOL)):
        for _kind, height, _expected in _boundary_cases(threshold):
            verts, tris = _single(height)
            mutable_verts = [list(point) for point in verts]
            mutable_tris = [list(tri) for tri in tris]
            _run(mutable_verts, mutable_tris, area_tol)
            reversed_verts, reversed_tris = _single(height, reverse=True)
            _run([list(point) for point in reversed_verts], [list(tri) for tri in reversed_tris], area_tol)
        _equal, height_eq, _idx = _boundary_cases(threshold)[0]
        _above, height_hi, _hi = _boundary_cases(threshold)[2]
        mixed_verts, mixed_tris = _assemble((height_hi, height_eq))
        _run([list(point) for point in mixed_verts], [list(tri) for tri in mixed_tris], area_tol)
    assert len(probes) == 14


def test_strict_less_mutation_fails_equality_cases(monkeypatch):
    """Row 8: flipping ``<=`` to ``<`` fails only the equality rows; unmodified source still passes."""
    strict = _strict_degenerate_triangles()
    monkeypatch.setattr(ua, "degenerate_triangles", strict)
    failures = []
    for label, threshold, area_tol in (
        ("row 1", T, None),
        ("row 4", DYADIC_TOL, DYADIC_TOL),
    ):
        height = 2.0 * threshold
        _pin_analytic_area("equal", height, threshold)
        got = _indices(ua.degenerate_triangles, height, area_tol)
        if got == [0]:
            raise AssertionError(f"{label} equality h={height!r} tol={threshold!r} still returned [0]")
        failures.append((label, height, threshold, got))
        for kind in ("below", "above"):
            _kind, other_h, expected = next(case for case in _boundary_cases(threshold) if case[0] == kind)
            _pin_analytic_area(kind, other_h, threshold)
            assert _indices(ua.degenerate_triangles, other_h, area_tol) == expected
    assert failures == [
        ("row 1", 2.0 * T, T, []),
        ("row 4", 2.0 * DYADIC_TOL, DYADIC_TOL, []),
    ]
    assert _indices(degenerate_triangles, 2.0 * T) == [0]
    assert _indices(degenerate_triangles, 2.0 * DYADIC_TOL, DYADIC_TOL) == [0]
    assert ua.degenerate_triangles is strict
