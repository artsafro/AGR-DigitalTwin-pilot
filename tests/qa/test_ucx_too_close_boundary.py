"""new-case: UCX too-close exact-boundary — freeze the strict < 0.2 mm rule (req 2.13.4, D162).

Freezes an Acceptance table for the existing strict `< 0.2 mm` too-close rule on
independently specified outward unit box hulls whose nearest X faces sit at exactly 0 and
g (left X in [-1, 0], right X in [g, 1+g]). The nearest-face gap is g by construction and
is never derived by subtracting `1 + g` from `1`.

The measured gap and the boundary are characterised, not re-tuned. For this particular
hull construction and measurement, the exact 0.2 mm boundary is not reachable through the
surface measurement: for g = 0.0002 the measurement lands 813 ulps below `TOUCH_M`
(`(0.0002 - WITNESS_0002) / math.ulp(0.0002) == 813.0`, an absolute difference of
`2.2036409155767878e-17`), so the strict `<` rule classifies it `touch`, not the
`below_band` an exact `TOUCH_M` reading would give. This single witness does not prove
global unreachability of the boundary for arbitrary hull constructions.
"""
import math

import pytest

from twinqa.geometry import ucx_audit as ua

BOX_TRIS = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1),
            (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]

REQ = ua.REQ_COLLISION  # "2.13.4"

# Arithmetic witness for the exact 0.2 mm boundary. With the nearest X faces specified at
# exactly 0 and 0.0002, ``surface_distance`` still measures 813 ulps BELOW ``TOUCH_M``
# (``(0.0002 - WITNESS_0002) / math.ulp(0.0002) == 813.0``; absolute difference
# ``2.2036409155767878e-17``): the vertex-triangle fallback clamps a diagonal bottom-face
# edge to t=1 and rebuilds its near endpoint as ``(1.0 + 0.0002) - 1.0``, which rounds
# below 0.0002 in float64. For this hull construction the exact boundary is therefore not
# reachable: ``measured == TOUCH_M`` does not hold for g = 0.0002. This witness does not
# prove global unreachability.
WITNESS_0002 = 0.00019999999999997797  # == 1.0 + 0.0002 - 1.0


def box(lo, hi):
    """8 vertices (index bits x,y,z) of an outward unit box."""
    pts = [(hi[0] if i & 4 else lo[0], hi[1] if i & 2 else lo[1], hi[2] if i & 1 else lo[2])
           for i in range(8)]
    return pts, list(BOX_TRIS)


def boundary_pair(g):
    """Two unit boxes whose nearest X faces are independently specified at 0 and g.

    Left X in [-1, 0] (its +X face at exactly 0); right X in [g, 1+g] (its -X face at
    exactly g). The nearest-face gap is g by construction, never `(1 + g) - 1`.
    """
    return box((-1.0, 0.0, 0.0), (0.0, 1.0, 1.0)), box((g, 0.0, 0.0), (1.0 + g, 1.0, 1.0))


def _reverse_winding(hull):
    """Reverse the triangle winding/order of a hull, keeping vertices and indices intact."""
    verts, tris = hull
    return list(verts), [(c, b, a) for a, b, c in tris]


# Frozen Acceptance table for the existing strict `< 0.2 mm` rule. Expected measured gaps
# are the specified face positions (0 and g), not a copy of the production thresholds;
# g=0.0002 is the single witness exception (813 ulps below TOUCH_M, still `touch`).
ACCEPTANCE = [
    # g         measured gap       class         finding types
    (0.000199,  0.000199,          "touch",      ("too_close", "gap_out_of_band")),
    (0.0002,    WITNESS_0002,      "touch",      ("too_close", "gap_out_of_band")),
    (0.000201,  0.000201,          "below_band", ("gap_out_of_band",)),
    (0.0,       0.0,               "touch",      ("too_close", "gap_out_of_band")),
]


@pytest.mark.parametrize("g,expected_gap,expected_class,expected_types", ACCEPTANCE)
def test_acceptance_table_measured_gap_class_findings(g, expected_gap, expected_class, expected_types):
    """Each control: measured gap matches the specified face positions, class and findings frozen."""
    a, b = boundary_pair(g)
    cls, measured, pen = ua.pair_relation(a, b)
    assert measured == expected_gap, (g, measured, expected_gap)
    assert cls == expected_class, (g, cls)
    assert pen == 0.0, (g, pen)
    findings = ua.pair_findings(a, b, name_a="L", name_b="R")
    assert [f["type"] for f in findings] == list(expected_types), (g, findings)
    assert all(f["penetration_m"] == 0.0 for f in findings)
    assert all(f["gap_m"] == measured for f in findings)


def test_exact_boundary_precondition_fails_and_witness_reported():
    """For this hull construction the exact 0.2 mm boundary is not reachable: g=0.0002
    measures 813 ulps below TOUCH_M, not a single ulp.

    This reports the arithmetic witness instead of weakening it with ``approx`` or
    inventing a production bug. The strict `<` rule therefore classifies the specified
    0.2 mm face gap as `touch`, not `below_band`. This witness is specific to this hull
    construction and measurement and does not prove global unreachability.
    """
    a, b = boundary_pair(0.0002)
    measured = ua.pair_relation(a, b)[1]
    # The exact-measurement precondition `measured == TOUCH_M` does NOT hold:
    assert measured != ua.TOUCH_M
    # The actual arithmetic witness, named and pinned:
    assert measured == WITNESS_0002
    assert WITNESS_0002 == 1.0 + 0.0002 - 1.0  # provenance: diagonal-edge closest-point
    # Corrected quantitative claim: 813 ulps below TOUCH_M, not 1 ulp.
    assert (ua.TOUCH_M - WITNESS_0002) / math.ulp(ua.TOUCH_M) == 813.0
    assert measured < ua.TOUCH_M  # 813 ulps below the boundary -> strict `<` says touch
    assert ua.pair_relation(a, b)[0] == "touch"
    assert [f["type"] for f in ua.pair_findings(a, b)] == ["too_close", "gap_out_of_band"]


def test_witness_is_exactly_813_ulps_below_touch_m():
    """Brute-force ulp count: 813 ``math.nextafter`` steps down from TOUCH_M land on the
    witness exactly and 814 overshoot — an independent check of the 813-ulp claim that does
    not divide by ``math.ulp``.
    """
    probe = ua.TOUCH_M
    for _ in range(813):
        probe = math.nextafter(probe, -math.inf)
    assert probe == WITNESS_0002  # exactly 813 ulps below TOUCH_M
    assert math.nextafter(probe, -math.inf) != WITNESS_0002  # 814 ulps would overshoot


def test_reverse_winding_preserves_measured_gap():
    """Reversing triangle winding/order is an invariance control, not a sub-ulp guarantee."""
    for g in (0.000199, 0.0002, 0.000201, 0.0):
        a, b = boundary_pair(g)
        assert ua.pair_relation(a, b) == ua.pair_relation(_reverse_winding(a), _reverse_winding(b))


def test_findings_carry_req_2134_names_and_do_not_mutate_hulls():
    """Explicit req 2.13.4, caller name preservation, zero penetration, unchanged hull arrays."""
    a, b = boundary_pair(0.0002)
    va, ta = [list(v) for v in a[0]], list(a[1])
    vb, tb = [list(v) for v in b[0]], list(b[1])
    findings = ua.pair_findings(a, b, name_a="L", name_b="R")
    assert findings[0]["req"] == "2.13.4"
    assert ua.REQ_COLLISION == "2.13.4"
    assert [f["a"] for f in findings] == ["L", "L"]
    assert [f["b"] for f in findings] == ["R", "R"]
    assert all(f["penetration_m"] == 0.0 for f in findings)
    # Input hull arrays are read-only and unchanged.
    assert a[0] == [tuple(v) for v in va] and a[1] == ta
    assert b[0] == [tuple(v) for v in vb] and b[1] == tb


def _pair_relation_loose_touch(a, b):
    """Process-local copy of ``pair_relation`` with `<` mutated to `<=` at the TOUCH_M gate.

    Never committed: exists only to characterise what a too-loose boundary would do
    (baseline-GREEN characterization, not historical RED).
    """
    sep = ua.sat_separation(a, b)
    if sep < -ua.OVERLAP_EPS_M:
        return "overlap", 0.0, -sep
    gap = ua.surface_distance(a, b) if sep > ua.OVERLAP_EPS_M else 0.0
    if gap <= ua.TOUCH_M:  # mutated: `<` -> `<=`
        return "touch", gap, max(0.0, -sep)
    if gap < ua.GAP_BAND_M[0] - ua.BAND_TOL_M:
        return "below_band", gap, 0.0
    if gap <= ua.GAP_BAND_M[1] + ua.BAND_TOL_M:
        return "in_band", gap, 0.0
    if gap <= ua.NEIGHBOUR_M:
        return "wide", gap, 0.0
    return "apart", gap, 0.0


def test_pair_relation_strict_lt_vs_mutated_le(monkeypatch):
    """Strict `<` places gap == TOUCH_M in `below_band`; a `<=` mutation flips it to `touch`.

    The box construction measures 813 ulps below TOUCH_M (see the witness test), so the gap
    is pinned to exactly TOUCH_M here to make the strict-vs-loose boundary observable.
    """
    a, b = boundary_pair(0.0002)
    monkeypatch.setattr(ua, "sat_separation", lambda x, y: 0.001)
    monkeypatch.setattr(ua, "surface_distance", lambda x, y: ua.TOUCH_M)

    cls, gap, pen = ua.pair_relation(a, b)
    assert gap == ua.TOUCH_M  # exact boundary
    assert cls == "below_band"  # ordinary strict `<`: the equality assertion holds

    monkeypatch.setattr(ua, "pair_relation", _pair_relation_loose_touch)
    mutated_cls, mutated_gap, _ = ua.pair_relation(a, b)
    assert mutated_gap == ua.TOUCH_M
    assert mutated_cls == "touch"  # `<=` flips the boundary
    assert mutated_cls != "below_band"  # the strict-boundary equality assertion now fails
