"""new-case: UCX scene enclosed-volume eligibility is translation-stable (local frame).

scene._enclosed_volume sums signed tetrahedra about the global origin; the raw sum
cancels when a hull sits far from the origin, so a unit cube translated to
(1e8, 1e8, 1e8) measures ~1e8 m^3 instead of 1 m^3. The fix shifts every triangle by
the first vertex before the sum (translation-invariant), which keeps the absolute-volume
API, the empty result and the degenerate threshold unchanged. Witnesses here are frozen
(no oracle calls into either production volume helper for the analytic span product).
"""
import pytest

from twinqa.scene import _enclosed_volume, _ucx_piece, scene_findings

from test_scene import PROFILES, mesh, rb, statuses, ucx_box

# Frozen outward unit cube. Vertex index bits: 4 -> x hi, 2 -> y hi, 1 -> z hi.
UNIT_CUBE_VERTS = [
    (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (0.0, 1.0, 1.0),
    (1.0, 0.0, 0.0), (1.0, 0.0, 1.0), (1.0, 1.0, 0.0), (1.0, 1.0, 1.0),
]
UNIT_CUBE_TRIS = [
    (0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1),
    (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3),
]
MSK_LIKE = (600000.0, 7500000.0, 150.0)
STRESS = (1e8, 1e8, 1e8)  # exactly representable float64 conditioning stress control


def _shift(verts, t):
    return [(x + t[0], y + t[1], z + t[2]) for x, y, z in verts]


def _box_verts(lo, hi):
    return [(hi[0] if i & 4 else lo[0], hi[1] if i & 2 else lo[1], hi[2] if i & 1 else lo[2])
            for i in range(8)]


@pytest.mark.parametrize("t", [(0.0, 0.0, 0.0), MSK_LIKE, STRESS])
def test_unit_cube_volume_is_one_at_zero_msk_and_stress(t):
    assert _enclosed_volume(_shift(UNIT_CUBE_VERTS, t), UNIT_CUBE_TRIS) == pytest.approx(1.0, abs=1e-12)


def test_reversed_windings_same_absolute_volume():
    base = _enclosed_volume(UNIT_CUBE_VERTS, UNIT_CUBE_TRIS)
    flipped = [(b, a, c) for a, b, c in UNIT_CUBE_TRIS]
    assert _enclosed_volume(UNIT_CUBE_VERTS, flipped) == pytest.approx(base, abs=1e-15)


def test_triangle_and_vertex_order_permutations_same_volume():
    base = _enclosed_volume(UNIT_CUBE_VERTS, UNIT_CUBE_TRIS)
    for perm in (list(reversed(UNIT_CUBE_TRIS)), UNIT_CUBE_TRIS[1:] + UNIT_CUBE_TRIS[:1]):
        assert _enclosed_volume(UNIT_CUBE_VERTS, perm) == pytest.approx(base, abs=1e-12)
    mapping = [7, 6, 5, 4, 3, 2, 1, 0]
    inverse = {old: new for new, old in enumerate(mapping)}
    verts = [UNIT_CUBE_VERTS[i] for i in mapping]
    tris = [tuple(inverse[i] for i in tri) for tri in UNIT_CUBE_TRIS]
    assert _enclosed_volume(verts, tris) == pytest.approx(base, abs=1e-12)


def test_tenth_metre_cube_at_msk_matches_span_product():
    """Analytic witness: product of the *represented* coordinate spans, not an oracle."""
    lo = MSK_LIKE
    hi = (lo[0] + 0.1, lo[1] + 0.1, lo[2] + 0.1)
    verts = _box_verts(lo, hi)
    got = _enclosed_volume(verts, UNIT_CUBE_TRIS)
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    expected = (max(xs) - min(xs)) * (max(ys) - min(ys)) * (max(zs) - min(zs))
    assert got == pytest.approx(expected, rel=1e-12)


def test_empty_tris_and_verts_are_zero_volume():
    assert _enclosed_volume(UNIT_CUBE_VERTS, []) == 0.0
    assert _enclosed_volume([], []) == 0.0


def test_planar_closed_shell_is_zero_volume():
    """A flattened unit cube is a closed manifold (12 tris, every edge shared twice) with volume 0."""
    flat = [(x, y, 0.0) for x, y, _ in UNIT_CUBE_VERTS]
    assert _enclosed_volume(flat, UNIT_CUBE_TRIS) == 0.0


@pytest.mark.parametrize("t", [(0.0, 0.0, 0.0), STRESS])
def test_ucx_piece_unit_cube_translated_and_origin_supported_unchanged(t):
    verts = [list(v) for v in _shift(UNIT_CUBE_VERTS, t)]
    tris = [list(x) for x in UNIT_CUBE_TRIS]
    verts_before = [list(v) for v in verts]
    tris_before = [list(x) for x in tris]
    piece = _ucx_piece({"name": "UCX_cube", "hull": {"verts": verts, "tris": tris}})
    assert piece["reason"] is None
    assert piece["hull"] is not None
    assert verts == verts_before
    assert tris == tris_before


def test_separated_pair_at_stress_translation_is_measured():
    a = ucx_box("UCX_SM_Test_K_1_Main_001", (0, 0, 0), (1, 1, 1))
    b = ucx_box("UCX_SM_Test_K_1_Main_002", (1.005, 0, 0), (2.005, 1, 1))
    for piece in (a, b):
        piece["hull"]["verts"] = [[x + STRESS[0], y + STRESS[1], z + STRESS[2]]
                                  for x, y, z in piece["hull"]["verts"]]
    found = scene_findings(rb(mesh(), a, b), "vpm", "oks", PROFILES.vpm)
    st = statuses(found, "V010")
    assert st["UCX intersections"] == "pass"
    assert st["UCX intersections coverage"] == "pass"
    assert st["UCX piece gap (advisory)"] == "pass"
