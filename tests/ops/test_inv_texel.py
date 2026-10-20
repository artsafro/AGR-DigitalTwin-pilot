"""texel_ready kernel invariant: every face fits one texture tile at the profile density [D021, D097, D129] (#346)."""
import itertools
import math
from dataclasses import replace

import numpy as np
import pytest

from dt_ai.ops.invariants import InvariantReport, InvariantResult, Mesh, check_operation
from dt_ai.ops.inv_texel import (
    ASPECT_MAX,
    NPM_GROUND,
    PROFILES,
    VPM,
    PolyMesh,
    TexelParams,
    check_operation_texel,
    face_metrics,
    max_side,
    texel_ready,
    texel_report,
)


def rect(w, h, x0=0.0, y0=0.0):
    """One CCW quad w x h in the XY plane."""
    v = np.array([[x0, y0, 0], [x0 + w, y0, 0], [x0 + w, y0 + h, 0], [x0, y0 + h, 0]], float)
    return PolyMesh(v, [(0, 1, 2, 3)])


def tri(*pts):
    return PolyMesh(np.array([[*p, 0.0] for p in pts], float), [(0, 1, 2)])


def box(lo, hi):
    """Closed triangle box, CCW from outside (the `Mesh` of invariants.py)."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    v = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return Mesh(v, np.array([t for a, b, c, d in quads for t in ((a, b, c), (a, c, d))]))


def verdict(scene, profile, params=None):
    return texel_ready(scene, profile, params=params)


# ---- limits from the formula -------------------------------------------------------------------------------------

def test_max_side_formula():
    assert max_side(4096, 32, 1024) == 3.9375
    assert max_side(2048, 8, 40) == 50.8


def test_profile_limits_come_from_formula():
    assert VPM.review_side_m == max_side(4096, 32, 1024)
    assert VPM.hard_side_m == 4096 / 1024 == 4.0
    assert VPM.max_area_m2 == 16.0
    assert NPM_GROUND.hard_side_m == max_side(2048, 8, 40) == 50.8
    assert NPM_GROUND.review_side_m == NPM_GROUND.hard_side_m
    assert math.isclose(NPM_GROUND.max_area_m2, 2580.64)
    assert PROFILES["VPM-OKS"] is VPM and PROFILES["VPM-Ground"] is VPM
    assert PROFILES["NPM-OKS"].size_gated is False
    assert all(p.aspect_max == ASPECT_MAX == 8.0 for p in PROFILES.values())


def test_density_override_changes_verdict():
    s = {"wall": rect(3.9, 3.9)}
    assert verdict(s, "VPM-OKS").passed
    r = verdict(s, "VPM-OKS", params=replace(VPM, density_px_per_m=2048))   # one 4K tile = 2 m
    assert not r.passed and r.count == 1 and "edge 3.90 m > 2.0 m" in r.offenders[0]
    assert verdict({"g": rect(51, 10)}, "NPM-Ground", params=replace(NPM_GROUND, density_px_per_m=10)).passed


# ---- issue cases ------------------------------------------------------------------------------------------------

def test_vpm_39_passes_without_review():
    assert verdict({"w": rect(3.9, 3.9)}, "VPM-OKS").passed
    assert texel_report({"w": rect(3.9, 3.9)}, "VPM-OKS")["w"].review == ()


def test_vpm_395_passes_as_review():
    s = {"w": rect(3.95, 3.95)}
    assert verdict(s, "VPM-Ground").passed
    rep = texel_report(s, "VPM-Ground")["w"]
    assert rep.offenders == () and len(rep.review) == 1 and "w#0" in rep.review[0]


def test_vpm_41_by_1_fails_on_edge():
    r = verdict({"w": rect(4.1, 1.0)}, "VPM-OKS")
    assert not r.passed and r.count == 1
    assert r.offenders == ("w#0: edge 4.10 m > 4.0 m",)


def test_vpm_4_by_4_boundary_inclusive():
    s = {"w": rect(4.0, 4.0)}
    assert verdict(s, "VPM-OKS").passed
    assert len(texel_report(s, "VPM-OKS")["w"].review) == 1


def test_npm_ground_50_passes_51_fails():
    assert verdict({"g": rect(50, 50)}, "NPM-Ground").passed
    r = verdict({"g": rect(51, 10)}, "NPM-Ground")
    assert not r.passed and r.offenders == ("g#0: edge 51.00 m > 50.8 m",)


def test_npm_oks_reports_but_passes():
    s = {"b": rect(300, 300)}
    r = verdict(s, "NPM-OKS")
    assert r.passed and r.count == 0 and r.name == "texel_ready"
    rep = texel_report(s, "NPM-OKS")["b"]
    assert rep.max_edge_m == 300 and rep.max_area_m2 == 90000 and rep.offenders == ()
    assert rep.reported and "edge 300.00 m" in rep.reported[0]


@pytest.mark.parametrize("profile", sorted(PROFILES))
def test_aspect_10_fails_in_every_profile(profile):
    r = verdict({"p": rect(4.0, 0.4)}, profile)
    assert not r.passed and r.count == 1 and r.offenders == ("p#0: aspect 10.0 > 8",)


@pytest.mark.parametrize("profile", sorted(PROFILES))
def test_sliver_triangle_fails_on_aspect(profile):
    r = verdict({"t": tri((0, 0), (3, 0), (1.5, 0.01))}, profile)
    assert not r.passed and "aspect" in r.offenders[0]


def test_triangle_mesh_input_measured_per_triangle():
    r = verdict({"box": box((0, 0, 0), (2, 2, 2))}, "VPM-OKS")
    assert r.passed
    rep = texel_report({"box": box((0, 0, 0), (2, 2, 2))}, "VPM-OKS")["box"]
    assert rep.faces == 12 and math.isclose(rep.max_edge_m, 2 * math.sqrt(2)) and math.isclose(rep.max_aspect, 2.0)
    bad = verdict({"bar": box((0, 0, 0), (5, 1, 1))}, "VPM-OKS")
    assert not bad.passed and bad.count >= 4


def test_face_metrics():
    m = face_metrics(np.array([[0, 0, 0], [4, 0, 0], [4, 1, 0], [0, 1, 0]], float))
    assert (m.max_edge_m, m.area_m2, m.aspect) == (4.0, 4.0, 4.0)
    t = face_metrics(np.array([[0, 0, 0], [3, 0, 0], [0, 4, 0]], float))
    assert t.max_edge_m == 5.0 and t.area_m2 == 6.0 and math.isclose(t.aspect, 5 / (12 / 5))


def test_ngon_measured_by_longest_edge_or_diagonal():
    # hexagon: every edge <= 2.6 m, but the diagonal (0,0)-(4.5,1) is 4.61 m
    v = np.array([[0, 0, 0], [2.25, -1.3, 0], [4.5, 0, 0], [4.5, 1, 0], [2.25, 2.3, 0], [0, 1, 0]], float)
    r = verdict({"n": PolyMesh(v, [(0, 1, 2, 3, 4, 5)])}, "VPM-OKS")
    assert not r.passed and r.offenders == ("n#0: span 4.61 m > 4.0 m",)


def test_offenders_capped_count_full():
    s = {"g": PolyMesh(*_grid_of_quads(7, 4.2, 1.0))}
    r = verdict(s, "VPM-OKS")
    assert r.count == 7 and len(r.offenders) == 5
    assert len(texel_report(s, "VPM-OKS")["g"].offenders) == 7


def _grid_of_quads(n, w, h):
    v, f = [], []
    for i in range(n):
        q = rect(w, h, y0=2 * i)
        f.append(tuple(len(v) + k for k in range(4)))
        v.extend(q.vertices)
    return np.array(v), f


# ---- fail-closed probes -----------------------------------------------------------------------------------------

def test_empty_scene_fails():
    r = verdict({}, "VPM-OKS")
    assert not r.passed and "empty" in r.offenders[0]


@pytest.mark.parametrize("profile", sorted(PROFILES))
def test_part_without_faces_fails(profile):
    r = verdict({"p": PolyMesh(np.zeros((0, 3)), [])}, profile)
    assert not r.passed and "0 faces" in r.offenders[0]
    r = verdict({"m": Mesh(np.zeros((3, 3)), np.zeros((0, 3), int))}, profile)
    assert not r.passed


@pytest.mark.parametrize("profile", sorted(PROFILES))
def test_degenerate_faces_fail(profile):
    collinear = tri((0, 0), (1, 0), (2, 0))
    zero_edge = PolyMesh(np.array([[0, 0, 0], [0, 0, 0], [1, 1, 0], [0, 1, 0]], float), [(0, 1, 2, 3)])
    bowtie = PolyMesh(np.array([[0, 0, 0], [1, 1, 0], [1, 0, 0], [0, 1, 0]], float), [(0, 1, 2, 3)])
    for s in (collinear, zero_edge, bowtie):
        r = verdict({"d": s}, profile)
        assert not r.passed and "degenerate" in r.offenders[0]


def test_nan_and_bad_input_raise():
    with pytest.raises(ValueError):
        PolyMesh(np.array([[0, 0, np.nan], [1, 0, 0], [0, 1, 0]]), [(0, 1, 2)])
    with pytest.raises(ValueError):
        PolyMesh(np.array([[0, 0, np.inf], [1, 0, 0], [0, 1, 0]]), [(0, 1, 2)])
    with pytest.raises(ValueError):
        PolyMesh(np.zeros((3, 3)), [(0, 1)])
    with pytest.raises(ValueError):
        PolyMesh(np.zeros((3, 3)), [(0, 1, 3)])
    with pytest.raises(ValueError):
        PolyMesh(np.zeros((3, 3)), [(0, 1, -1)])
    with pytest.raises(ValueError):
        texel_ready({"p": "not a mesh"}, "VPM-OKS")


def test_unknown_profile_raises():
    for p in ("VPM-Flora", "npm-ground", "", None):
        with pytest.raises(ValueError):
            texel_ready({"w": rect(1, 1)}, p)


@pytest.mark.parametrize("kw", [dict(density_px_per_m=0), dict(density_px_per_m=-1), dict(density_px_per_m=math.nan),
                                dict(padding_px=2048), dict(padding_px=3000), dict(padding_px=-1),
                                dict(tile_px=0), dict(aspect_max=0.5), dict(aspect_max=math.inf),
                                dict(tile_px=None)])
def test_bad_params_raise(kw):
    with pytest.raises(ValueError):
        replace(VPM, **kw)


def test_unknown_part_in_parts_raises():
    with pytest.raises(ValueError):
        texel_ready({"w": rect(1, 1)}, "VPM-OKS", parts=["x"])
    r = texel_ready({"w": rect(1, 1)}, "VPM-OKS", parts=[])
    assert not r.passed


# ---- wrapper ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("size,texel_ok", [((2, 2, 2), True), ((5, 1, 1), False)])
def test_check_operation_texel_wrapper(size, texel_ok):
    after = {"a": box((0, 0, 0), size)}
    base = check_operation(None, after, ["a"])
    assert base.passed
    out = check_operation_texel(base, after, ["a"], "VPM-OKS")
    assert isinstance(out, InvariantReport)
    assert out.results[:-1] == base.results
    assert [r.name for r in out.results].count("texel_ready") == 1 and out.results[-1].name == "texel_ready"
    assert out.passed is texel_ok
    if not texel_ok:
        assert [r.name for r in out.broken] == ["texel_ready"]


def test_wrapper_measures_only_changed_parts():
    after = {"a": box((0, 0, 0), (2, 2, 2)), "big": box((10, 0, 0), (16, 1, 1))}
    base = check_operation(None, after, ["a"])
    assert check_operation_texel(base, after, ["a"], "VPM-OKS").results[-1].passed
    with pytest.raises(ValueError):
        check_operation_texel(base, after, ["missing"], "VPM-OKS")


# ---- probes for the stated guarantees ----------------------------------------------------------------------------

def test_probe_rectangles_against_brute_force():
    """Generated: every axis rectangle w x h, verdict == (max(w,h) <= hard and ratio <= 8), review band exact."""
    rng = np.random.default_rng(346)
    sizes = list(rng.uniform(0.05, 6.0, size=(400, 2))) + [(a, b) for a, b in itertools.product(
        [3.9375, 4.0, 4.0 + 1e-9, 0.5, 0.5 - 1e-9, 3.9375 + 1e-9], repeat=2)]
    for w, h in sizes:
        rep = texel_report({"p": rect(w, h)}, "VPM-OKS")["p"]
        ok = max(w, h) <= 4.0 and max(w, h) / min(w, h) <= 8.0 and w * h <= 16.0
        assert (rep.offenders == ()) is ok, (w, h, rep.offenders)
        in_band = ok and max(w, h) > 3.9375
        assert (len(rep.review) == 1) is in_band, (w, h)


def test_probe_rotation_and_translation_invariant():
    rng = np.random.default_rng(7)
    for _ in range(100):
        w, h = rng.uniform(0.3, 5.0, 2)
        q = rect(w, h)
        a, b = rng.uniform(0, 2 * np.pi, 2)
        rz = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
        rx = np.array([[1, 0, 0], [0, np.cos(b), -np.sin(b)], [0, np.sin(b), np.cos(b)]])
        moved = PolyMesh(q.vertices @ (rx @ rz).T + rng.uniform(-1e3, 1e3, 3), q.faces)
        r1, r2 = verdict({"p": q}, "VPM-OKS"), verdict({"p": moved}, "VPM-OKS")
        if abs(max(w, h) - 4.0) > 1e-6 and abs(max(w, h) / min(w, h) - 8) > 1e-6:
            assert r1.passed is r2.passed, (w, h)


def test_result_type():
    r = verdict({"w": rect(1, 1)}, "NPM-Ground")
    assert isinstance(r, InvariantResult) and r == InvariantResult("texel_ready", True, 0, ())
    assert isinstance(TexelParams(None, None, None), TexelParams)
