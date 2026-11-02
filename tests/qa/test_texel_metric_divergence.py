"""new-case: texel metric verdict divergence characterization.

Scope: texel metric verdict divergence characterization of the current main
helpers only. ``twinqa.uv.density_findings`` / ``edge_densities`` sample ring
edges. ``ground_cake.texel_density`` returns a per-triangle area mean. The
directional column is an independent closed form of the known 2x2 map
(eigenvalues of ``A^T A``, no SVD, no production geometry helper).

S = 2048. The common illustrative closed band is [10, 40]. Callers pass that
band as ``min_px_per_m`` / ``max_px_per_m``. Those arguments are not the VPM
diffuse defaults, not a V008 Ground gate, and not a resolution of C36. No
metric is selected as normative. A pass or fail below is the current helper's
result on a synthetic polygon, not a defect label and not delivery acceptance.
Baseline on this tree is expected to pass.

Acceptance table (frozen affine planar rings, fan area, ring edges, edge
findings, directional extrema):

| fixture | area (each fan triangle) | ring-edge extrema | edge findings | directional oracle |
|---|---|---|---|---|
| 0.1 x 10 m quad, UV a 35 px square | 35, in band | 3.5 and 350 | both fail | 3.5 and 350, outside |
| shear tri world (0,0),(64,0),(0,64), UV (0,0),(.5,0),(1.125,.5) | 16, in band | 16 and 4*sqrt(97) | both pass | sqrt(904 ± 72*sqrt(145)), outside |
| 64 x 16 m rectangle rotated 45 deg, UV = diag(5/2048, 45/2048) * world | 15, in band | every ring edge sqrt(1025) | both pass | 5 and 45, outside |
| isotropic 64 m square, UV = world/128 | 16, in band | 16 and 16 | both pass | 16 and 16, in band |

Fan diagonals are built into the triangle corners passed to ``texel_density``
and are NOT the checker's ring-edge verdict. ``edge_densities`` walks the ring
only; a quad fan adds the diagonal segment, which these fixtures keep out of
that list.
"""
import copy
import math

import numpy as np
import pytest

from dt_ai.geometry.ground_cake import texel_density
import twinqa.uv as uv_mod

S = 2048
BAND_LO = 10
BAND_HI = 40
REL = 1e-12

# Brute-force grid. Counts are asserted in the probes (N/N).
_WIDTHS = (4.0, 16.0, 64.0)
_HEIGHTS = (4.0, 10.0, 32.0)
_SHEARS = (0.0, 0.5, 2.25)
_SCALES = (1.0 / 128.0, 5.0 / 2048.0, 35.0 / 2048.0)
_WORLD_SHIFTS = ((0.0, 0.0), (1024.0, 2048.0), (-512.0, 0.25), (1.0, -2.0))
_UV_SHIFTS = ((0.0, 0.0), (1.0, 2.0), (-4.0, 8.0), (0.5, -0.5))


def _finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"non-finite {label}: {value!r}")


def _apply(M, x, y):
    if len(M) != 2 or len(M[0]) != 2 or len(M[1]) != 2:
        raise ValueError("empty map")
    (a, b), (c, d) = M
    for name, value in (("a", a), ("b", b), ("c", c), ("d", d), ("x", x), ("y", y)):
        _finite(value, name)
    u = a * x + b * y
    v = c * x + d * y
    _finite(u, "u")
    _finite(v, "v")
    return (u, v)


def _det(M):
    (a, b), (c, d) = M
    for name, value in (("a", a), ("b", b), ("c", c), ("d", d)):
        _finite(value, name)
    det = a * d - b * c
    _finite(det, "det")
    if det == 0.0:
        raise ValueError("empty area: singular map")
    return det


def _area_px(M, size):
    """Area density S * sqrt(|det M|). Determinant of the known map, not an API."""
    _finite(size, "size")
    area = size * math.sqrt(abs(_det(M)))
    _finite(area, "area")
    return area


def _singular_px(M, size):
    """Singular values of ``size * M`` from the scalar 2x2 eigenvalue formula.

    ``s^2 = (trace(A^T A) ± sqrt(diff^2 + 4 off^2)) / 2``. No SVD.
    """
    _finite(size, "size")
    (a, b), (c, d) = M
    a, b, c, d = size * a, size * b, size * c, size * d
    for value in (a, b, c, d):
        _finite(value, "scaled map")
    trace = a * a + b * b + c * c + d * d
    diff = (a * a + c * c) - (b * b + d * d)
    off = a * b + c * d
    disc = math.sqrt(diff * diff + 4.0 * off * off)
    _finite(disc, "discriminant")
    low = (trace - disc) / 2.0
    high = (trace + disc) / 2.0
    if -1e-9 < low < 0.0:
        low = 0.0
    if low < 0.0 or high < 0.0 or not math.isfinite(low) or not math.isfinite(high):
        raise ValueError(f"non-finite singular value {(low, high)!r}")
    return math.sqrt(low), math.sqrt(high)


def _ring_ok(world, uv):
    if len(world) < 3 or len(world) != len(uv):
        raise ValueError("empty or mismatched ring")
    for (x, y), (u, v) in zip(world, uv):
        for name, value in (("x", x), ("y", y), ("u", u), ("v", v)):
            _finite(value, name)


def _edge_px(world, uv, size):
    """Ring densities ``size * hypot(duv) / hypot(dxy)``. Planar z is constant."""
    _ring_ok(world, uv)
    _finite(size, "size")
    values = []
    n = len(world)
    for i in range(n):
        j = (i + 1) % n
        dx = world[j][0] - world[i][0]
        dy = world[j][1] - world[i][1]
        du = uv[j][0] - uv[i][0]
        dv = uv[j][1] - uv[i][1]
        for name, value in (("dx", dx), ("dy", dy), ("du", du), ("dv", dv)):
            _finite(value, name)
        length = math.hypot(dx, dy)
        if length == 0.0 or not math.isfinite(length):
            raise ValueError("empty or non-finite world edge")
        density = size * math.hypot(du, dv) / length
        _finite(density, "edge density")
        values.append(density)
    if not values:
        raise ValueError("empty edges")
    return values


def _segment_px(p0, p1, q0, q1, size):
    """One open segment. Used for the fan diagonal, which is not a ring edge."""
    _finite(size, "size")
    dx = p1[0] - p0[0]
    dy = p1[1] - p0[1]
    du = q1[0] - q0[0]
    dv = q1[1] - q0[1]
    for name, value in (("dx", dx), ("dy", dy), ("du", du), ("dv", dv)):
        _finite(value, name)
    length = math.hypot(dx, dy)
    if length == 0.0 or not math.isfinite(length):
        raise ValueError("empty or non-finite diagonal")
    density = size * math.hypot(du, dv) / length
    _finite(density, "diagonal density")
    return density


def _cycle(points, k):
    if len(points) < 3:
        raise ValueError("empty or short ring")
    if isinstance(k, bool) or not isinstance(k, int):
        raise ValueError(f"non-finite shift {k!r}")
    k %= len(points)
    return points[k:] + points[:k]


def _reverse(points):
    if len(points) < 3:
        raise ValueError("empty or short ring")
    return points[::-1]


def _translate(world, uv, world_shift, uv_shift):
    if len(world_shift) != 2 or len(uv_shift) != 2:
        raise ValueError("empty translation")
    wx, wy = world_shift
    uo, vo = uv_shift
    for name, value in (("wx", wx), ("wy", wy), ("uo", uo), ("vo", vo)):
        _finite(value, name)
    _ring_ok(world, uv)
    moved_world = tuple((x + wx, y + wy) for x, y in world)
    moved_uv = tuple((u + uo, v + vo) for u, v in uv)
    return moved_world, moved_uv


def _reversed_edge_order(values):
    """Ring reversal keeps the closing edge last and reverses the others."""
    if len(values) < 3:
        raise ValueError("empty edges")
    return values[-2::-1] + values[-1:]


def _rot45(x, y):
    _finite(x, "x")
    _finite(y, "y")
    c = math.sqrt(0.5)
    out = (c * x - c * y, c * x + c * y)
    _finite(out[0], "rx")
    _finite(out[1], "ry")
    return out


def _mutable_copy(world, uv):
    _ring_ok(world, uv)
    xyz = [[x, y, 0.0] for x, y in world]
    coords = [[u, v] for u, v in uv]
    return xyz, coords


def _fan_area_densities(world, uv):
    """Explicit triangle faces and per-corner UVs for ``texel_density``.

    A quad is the fan (0, 1, 2), (0, 2, 3). Corner pair (0, 2) is the fan
    diagonal. That segment is not submitted to ``edge_densities``.
    """
    _ring_ok(world, uv)
    if len(world) == 3:
        faces = np.array([[0, 1, 2]], dtype=np.int64)
        corners = np.array([[uv[0], uv[1], uv[2]]], dtype=float)
    elif len(world) == 4:
        faces = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64)
        corners = np.array(
            [[uv[0], uv[1], uv[2]], [uv[0], uv[2], uv[3]]],
            dtype=float,
        )
    else:
        raise ValueError("empty or unexpected ring")
    verts = np.array([(x, y, 0.0) for x, y in world], dtype=float)
    before = (verts.copy(), faces.copy(), corners.copy())
    out = texel_density(verts, faces, corners, S)
    if not (
        np.array_equal(verts, before[0])
        and np.array_equal(faces, before[1])
        and np.array_equal(corners, before[2])
    ):
        raise AssertionError("texel_density mutated inputs")
    if out.size == 0 or not bool(np.isfinite(out).all()):
        raise ValueError(f"non-finite area density {out!r}")
    return tuple(float(value) for value in out)


def _statuses(edges):
    if not edges:
        raise ValueError("empty edges")
    low, high = min(edges), max(edges)
    _finite(low, "edge min")
    _finite(high, "edge max")
    return ("pass" if low >= BAND_LO else "fail", "pass" if high <= BAND_HI else "fail")


def _assert_against_oracle(world, uv, M):
    oracle_edges = _edge_px(world, uv, S)
    sigma = _singular_px(M, S)
    area = _area_px(M, S)
    xyz, coords = _mutable_copy(world, uv)
    snap = copy.deepcopy((xyz, coords))
    api_edges = uv_mod.edge_densities(xyz, coords, S)
    findings = uv_mod.density_findings(
        xyz, coords, S, min_px_per_m=BAND_LO, max_px_per_m=BAND_HI
    )
    if (xyz, coords) != snap:
        raise AssertionError("density API mutated inputs")
    areas = _fan_area_densities(world, uv)
    if len(findings) != 2 or not api_edges or not areas:
        raise ValueError("empty API result")
    for finding in findings:
        if finding.measured is None or not math.isfinite(finding.measured):
            raise ValueError(f"non-finite measured {finding.measured!r}")
    assert api_edges == pytest.approx(oracle_edges, rel=REL)
    assert (findings[0].status, findings[1].status) == _statuses(oracle_edges)
    assert findings[0].measured == pytest.approx(min(oracle_edges), rel=REL)
    assert findings[1].measured == pytest.approx(max(oracle_edges), rel=REL)
    assert findings[0].threshold == BAND_LO
    assert findings[1].threshold == BAND_HI
    assert findings[0].name == "texel density"
    assert findings[1].name == "texel density upper"
    assert all(value == pytest.approx(area, rel=REL) for value in areas)
    return oracle_edges, sigma, area, findings, areas


def _in_band(value):
    _finite(value, "band value")
    return BAND_LO <= value <= BAND_HI


def _dir_in_band(sigma):
    return _in_band(sigma[0]) and _in_band(sigma[1])


# --- frozen fixtures (built once, before any test runs) ---

WITNESS_WORLD = ((0.0, 0.0), (0.1, 0.0), (0.1, 10.0), (0.0, 10.0))
WITNESS_M = ((35 / 2048 / 0.1, 0.0), (0.0, 35 / 2048 / 10.0))
WITNESS_UV = (
    (0.0, 0.0),
    (35 / 2048, 0.0),
    (35 / 2048, 35 / 2048),
    (0.0, 35 / 2048),
)

SHEAR_WORLD = ((0.0, 0.0), (64.0, 0.0), (0.0, 64.0))
SHEAR_UV = ((0.0, 0.0), (0.5, 0.0), (1.125, 0.5))
SHEAR_M = ((1 / 128, 2.25 / 128), (0.0, 1 / 128))

_RECT_AXIS = ((0.0, 0.0), (64.0, 0.0), (64.0, 16.0), (0.0, 16.0))
RECT_M = ((5 / 2048, 0.0), (0.0, 45 / 2048))
RECT_WORLD = tuple(_rot45(x, y) for x, y in _RECT_AXIS)
RECT_UV = tuple(_apply(RECT_M, x, y) for x, y in RECT_WORLD)

ISO_WORLD = ((0.0, 0.0), (64.0, 0.0), (64.0, 64.0), (0.0, 64.0))
ISO_M = ((1 / 128, 0.0), (0.0, 1 / 128))
ISO_UV = tuple((x / 128.0, y / 128.0) for x, y in ISO_WORLD)

FROZEN = (
    ("witness", WITNESS_WORLD, WITNESS_UV, WITNESS_M),
    ("shear", SHEAR_WORLD, SHEAR_UV, SHEAR_M),
    ("rect_rot45", RECT_WORLD, RECT_UV, RECT_M),
    ("iso", ISO_WORLD, ISO_UV, ISO_M),
)
_FROZEN_SNAPSHOT = copy.deepcopy(FROZEN)


def _generated_rings():
    rings = []
    for width in _WIDTHS:
        for height in _HEIGHTS:
            for shear in _SHEARS:
                for scale in _SCALES:
                    M = ((scale, shear / 128.0), (0.0, scale))
                    world = ((0.0, 0.0), (width, 0.0), (width, height), (0.0, height))
                    uv = tuple(_apply(M, x, y) for x, y in world)
                    rings.append((world, uv, M))
    if not rings:
        raise ValueError("empty generated grid")
    return tuple(rings)


def _base_rings():
    rings = [(world, uv, M) for _name, world, uv, M in FROZEN]
    rings.extend(_generated_rings())
    if len(rings) != 4 + len(_WIDTHS) * len(_HEIGHTS) * len(_SHEARS) * len(_SCALES):
        raise ValueError("empty or short ring catalogue")
    return tuple(rings)


def _orientations():
    items = []
    for world, uv, M in _base_rings():
        for k in range(len(world)):
            items.append((_cycle(world, k), _cycle(uv, k), M, k, world, uv))
    if not items:
        raise ValueError("empty orientations")
    return tuple(items)


def _same_metrics(left, right, *, edges_equal=True):
    l_edges, l_sigma, l_area, l_findings, l_areas = left
    r_edges, r_sigma, r_area, r_findings, r_areas = right
    if edges_equal:
        assert r_edges == pytest.approx(l_edges, rel=REL)
    else:
        assert sorted(r_edges) == pytest.approx(sorted(l_edges), rel=REL)
    assert r_sigma == pytest.approx(l_sigma, rel=REL)
    assert r_area == pytest.approx(l_area, rel=REL)
    assert r_areas == pytest.approx(l_areas, rel=REL)
    assert (r_findings[0].status, r_findings[1].status) == (
        l_findings[0].status,
        l_findings[1].status,
    )
    assert r_findings[0].measured == pytest.approx(l_findings[0].measured, rel=REL)
    assert r_findings[1].measured == pytest.approx(l_findings[1].measured, rel=REL)
    assert (r_findings[0].threshold, r_findings[1].threshold) == (BAND_LO, BAND_HI)


def _report(label, ok, total):
    if ok != total or total < 1:
        raise AssertionError(f"{label} {ok}/{total}")
    print(f"invariant {label} -> probe -> {ok}/{total}")


def test_frozen_fixtures_match_the_known_maps_and_stay_put():
    assert FROZEN == _FROZEN_SNAPSHOT
    for _name, world, uv, M in FROZEN:
        assert tuple(_apply(M, x, y) for x, y in world) == uv
        assert all(isinstance(point, tuple) for point in world)
        assert all(isinstance(point, tuple) for point in uv)


def test_witness_quad_area_in_band_and_both_edge_findings_fail():
    edges, sigma, area, findings, areas = _assert_against_oracle(
        WITNESS_WORLD, WITNESS_UV, WITNESS_M
    )
    assert area == pytest.approx(35.0)
    assert areas == pytest.approx((35.0, 35.0))
    assert all(_in_band(value) for value in areas)
    assert edges == pytest.approx((350.0, 3.5, 350.0, 3.5))
    assert sigma == pytest.approx((3.5, 350.0))
    assert [finding.status for finding in findings] == ["fail", "fail"]
    assert findings[0].measured == pytest.approx(3.5)
    assert findings[1].measured == pytest.approx(350.0)
    assert findings[0].margin == pytest.approx((3.5 - BAND_LO) / BAND_LO)
    assert findings[1].margin == pytest.approx((BAND_HI - 350.0) / BAND_HI)
    assert _in_band(area)
    assert not _in_band(edges[1]) and not _in_band(edges[0])
    assert not _dir_in_band(sigma)


def test_shear_triangle_edges_pass_while_directional_extrema_lie_outside():
    smin = math.sqrt(904.0 - 72.0 * math.sqrt(145.0))
    smax = math.sqrt(904.0 + 72.0 * math.sqrt(145.0))
    edges, sigma, area, findings, areas = _assert_against_oracle(
        SHEAR_WORLD, SHEAR_UV, SHEAR_M
    )
    assert area == pytest.approx(16.0)
    assert areas == pytest.approx((16.0,))
    assert _in_band(area)
    assert edges == pytest.approx((16.0, 2.0 * math.sqrt(82.0), 4.0 * math.sqrt(97.0)))
    assert min(edges) == pytest.approx(16.0)
    assert max(edges) == pytest.approx(4.0 * math.sqrt(97.0))
    assert sigma == pytest.approx((smin, smax))
    assert [finding.status for finding in findings] == ["pass", "pass"]
    assert findings[0].measured == pytest.approx(16.0)
    assert findings[1].measured == pytest.approx(4.0 * math.sqrt(97.0))
    assert _in_band(findings[0].measured) and _in_band(findings[1].measured)
    assert not _dir_in_band(sigma)


def test_rotated_rectangle_ring_edges_pass_while_directional_extrema_lie_outside():
    edges, sigma, area, findings, areas = _assert_against_oracle(
        RECT_WORLD, RECT_UV, RECT_M
    )
    assert area == pytest.approx(15.0)
    assert areas == pytest.approx((15.0, 15.0))
    assert all(_in_band(value) for value in areas)
    assert edges == pytest.approx((math.sqrt(1025.0),) * 4)
    assert all(_in_band(value) for value in edges)
    assert sigma == pytest.approx((5.0, 45.0))
    assert [finding.status for finding in findings] == ["pass", "pass"]
    assert findings[0].measured == pytest.approx(math.sqrt(1025.0))
    assert findings[1].measured == pytest.approx(math.sqrt(1025.0))
    assert not _dir_in_band(sigma)


def test_isotropic_square_area_edges_and_directional_extrema_agree():
    edges, sigma, area, findings, areas = _assert_against_oracle(ISO_WORLD, ISO_UV, ISO_M)
    assert area == pytest.approx(16.0)
    assert areas == pytest.approx((16.0, 16.0))
    assert edges == pytest.approx((16.0, 16.0, 16.0, 16.0))
    assert sigma == pytest.approx((16.0, 16.0))
    assert [finding.status for finding in findings] == ["pass", "pass"]
    assert findings[0].measured == pytest.approx(16.0)
    assert findings[1].measured == pytest.approx(16.0)
    assert _in_band(area) and _dir_in_band(sigma)
    assert all(_in_band(value) for value in edges)


def test_fan_diagonal_is_not_the_ring_edge_verdict():
    """The quad fan diagonal is a different segment from every ring edge.

    ``texel_density`` still returns the area mean on each fan triangle. The
    ring checker never sees that diagonal.
    """
    witness_diagonal = 35.0 * math.sqrt(2.0) / math.hypot(0.1, 10.0)
    cases = (
        (WITNESS_WORLD, WITNESS_UV, WITNESS_M, witness_diagonal),
        (RECT_WORLD, RECT_UV, RECT_M, None),
    )
    for world, uv, M, closed in cases:
        ring = _edge_px(world, uv, S)
        diagonal = _segment_px(world[0], world[2], uv[0], uv[2], S)
        if closed is None:
            # Rotated-rectangle ring is sqrt(1025) on every side; the diagonal is not.
            assert abs(diagonal - math.sqrt(1025.0)) > 1.0
        else:
            assert diagonal == pytest.approx(closed, rel=REL)
        assert all(abs(value - diagonal) > 1.0 for value in ring)
        xyz, coords = _mutable_copy(world, uv)
        snap = copy.deepcopy((xyz, coords))
        api = uv_mod.edge_densities(xyz, coords, S)
        findings = uv_mod.density_findings(
            xyz, coords, S, min_px_per_m=BAND_LO, max_px_per_m=BAND_HI
        )
        assert (xyz, coords) == snap
        assert len(api) == len(world)
        assert all(abs(value - diagonal) > 1.0 for value in api)
        assert findings[0].measured == pytest.approx(min(ring), rel=REL)
        assert findings[1].measured == pytest.approx(max(ring), rel=REL)
        assert abs(findings[0].measured - diagonal) > 1.0
        assert abs(findings[1].measured - diagonal) > 1.0
        areas = _fan_area_densities(world, uv)
        assert len(areas) == 2
        assert all(value == pytest.approx(_area_px(M, S), rel=REL) for value in areas)


def test_cyclic_starts_probe():
    """Invariant: cyclic starts. Probe: every start of every frozen and generated ring."""
    ok = 0
    total = 0
    for world, uv, M, k, base_world, base_uv in _orientations():
        base = _assert_against_oracle(base_world, base_uv, M)
        shifted = _assert_against_oracle(world, uv, M)
        _same_metrics(base, shifted, edges_equal=False)
        assert shifted[0] == pytest.approx(base[0][k:] + base[0][:k], rel=REL)
        ok += 1
        total += 1
    expected = (
        len(_WIDTHS) * len(_HEIGHTS) * len(_SHEARS) * len(_SCALES) * 4
        + 4 + 4 + 4 + 3
    )
    assert total == expected == 339
    _report("cyclic starts", ok, total)


def test_paired_winding_reversals_probe():
    """Invariant: paired winding reversals. World and UV reverse together."""
    ok = 0
    total = 0
    for world, uv, M, _k, _base_world, _base_uv in _orientations():
        forward = _assert_against_oracle(world, uv, M)
        backward = _assert_against_oracle(_reverse(world), _reverse(uv), M)
        _same_metrics(forward, backward, edges_equal=False)
        assert backward[0] == pytest.approx(_reversed_edge_order(forward[0]), rel=REL)
        restored = _assert_against_oracle(_reverse(_reverse(world)), _reverse(_reverse(uv)), M)
        _same_metrics(forward, restored, edges_equal=True)
        ok += 1
        total += 1
    assert total == 339
    _report("winding reversals", ok, total)


def test_exact_translations_probe():
    """Invariant: exactly representable world and UV translations, including +(1024, 2048) and +(1, 2)."""
    ok = 0
    total = 0
    for world, uv, M in _base_rings():
        base = _assert_against_oracle(world, uv, M)
        for world_shift in _WORLD_SHIFTS:
            for uv_shift in _UV_SHIFTS:
                moved_world, moved_uv = _translate(world, uv, world_shift, uv_shift)
                moved = _assert_against_oracle(moved_world, moved_uv, M)
                _same_metrics(base, moved, edges_equal=True)
                ok += 1
                total += 1
    expected = (4 + len(_WIDTHS) * len(_HEIGHTS) * len(_SHEARS) * len(_SCALES)) * len(
        _WORLD_SHIFTS
    ) * len(_UV_SHIFTS)
    assert total == expected == 1360
    _report("translations", ok, total)
    assert FROZEN == _FROZEN_SNAPSHOT


def test_helpers_fail_closed_on_nonfinite_and_empty():
    with pytest.raises(ValueError):
        _finite(float("nan"), "x")
    with pytest.raises(ValueError):
        _finite(float("inf"), "x")
    with pytest.raises(ValueError):
        _finite(float("-inf"), "x")
    with pytest.raises(ValueError):
        _edge_px((), (), S)
    with pytest.raises(ValueError):
        _edge_px(((0.0, 0.0),), ((0.0, 0.0),), S)
    with pytest.raises(ValueError):
        _fan_area_densities((), ())
    with pytest.raises(ValueError):
        _singular_px(((float("nan"), 0.0), (0.0, 1.0)), S)
    with pytest.raises(ValueError):
        _area_px(((1.0, 0.0), (0.0, 0.0)), S)
    with pytest.raises(ValueError):
        _segment_px((0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (1.0, 0.0), S)
    with pytest.raises(ValueError):
        _cycle((), 0)
    with pytest.raises(ValueError):
        _reverse(())
    with pytest.raises(ValueError):
        _translate((), (), (float("nan"), 0.0), (0.0, 0.0))
    with pytest.raises(ValueError):
        _apply(((float("inf"), 0.0), (0.0, 1.0)), 0.0, 0.0)
