"""#1537: densify a named part for the [D012] UCX budget under the D108 invariants (no degenerate / mirrored faces).

All meshes are SYNTHETIC (strips, plates, boxes built here), not data of a real object.
Pattern: new-case: regression + probes of the densify operation (#1537).
"""
from itertools import product
import time

import numpy as np
import pytest

from dt_ai.geometry.ucx_build import ucx_triangle_limit
from dt_ai.ops.densify import (DEGENERATE_AREA_M2, UVPart, check_densify, densify_for_ucx_budget,
                               needed_model_triangles, subdivide, uv_signed_areas)
from dt_ai.ops.invariants import Mesh, border_edges
from dt_ai.ops.operations import _box_mesh

SESSION_DEGENERATE = 296   # SINTEZ on elv-tc-vpm after bisect+connect: «вырожденных полигонов ... - 296 шт.»
RUNTIME_BOUND_S = 10.0     # stated bound: one level on a 50 000-face part, invariants included


def plate(nx: int, ny: int, sx: float = 1.0, sy: float = 0.1, ids=None) -> UVPart:
    """Flat plate (z = 0) of nx * ny quads, two triangles each, CCW from +z; UV = planar (x / X, y / X)."""
    xs, ys = np.meshgrid(np.arange(nx + 1) * sx, np.arange(ny + 1) * sy, indexing="ij")
    v = np.stack([xs.ravel(), ys.ravel(), np.zeros(xs.size)], axis=1)
    i, j = np.meshgrid(np.arange(nx), np.arange(ny), indexing="ij")
    a = (i * (ny + 1) + j).ravel()
    b, c, d = a + (ny + 1), a + (ny + 2), a + 1           # (x+1, y), (x+1, y+1), (x, y+1)
    t = np.concatenate([np.stack([a, b, c], 1), np.stack([a, c, d], 1)])
    uv = v[t][:, :, :2] / (nx * sx)
    return UVPart(Mesh(v, t), uv, None if ids is None else np.full(len(t), ids))


def strip(n: int = 148) -> UVPart:
    """The flat strip of the regression: n quads of 1 m x 0.1 m in one row."""
    return plate(n, 1)


def session_bisect_connect(p: UVPart, min_len: float = 0.5) -> UVPart:
    """The session's method, reproduced: bisect every x-edge longer than `min_len` (the long edges of the strip),
    connect midpoints that share a face (in a triangulated strip none does), and triangulate each resulting n-gon as
    the exporter does, a fan from the start of the bisected edge: the ear (a, mid, b) has a straight angle at mid and
    zero area in 3D and in UV."""
    v, out_t, out_uv = list(p.mesh.vertices), [], []
    mids = {}
    for f, tri in enumerate(p.mesh.triangles):
        poly, puv = [], []
        for k in range(3):
            a, b = tri[k], tri[(k + 1) % 3]
            poly.append(a), puv.append(p.uv[f, k])
            d = p.mesh.vertices[b] - p.mesh.vertices[a]
            if abs(d[0]) > min_len and np.allclose(d[1:], 0):
                key = (min(a, b), max(a, b))
                if key not in mids:
                    mids[key] = len(v)
                    v.append(0.5 * (p.mesh.vertices[a] + p.mesh.vertices[b]))
                poly.append(mids[key]), puv.append(0.5 * (p.uv[f, k] + p.uv[f, (k + 1) % 3]))
        start = next((i - 1 for i, x in enumerate(poly) if x >= len(p.mesh.vertices)), 0) % len(poly)
        poly, puv = poly[start:] + poly[:start], puv[start:] + puv[:start]
        for i in range(1, len(poly) - 1):
            out_t.append((poly[0], poly[i], poly[i + 1])), out_uv.append((puv[0], puv[i], puv[i + 1]))
    return UVPart(Mesh(np.array(v), np.array(out_t)), np.array(out_uv))


def big_main(tris: int = 60_000) -> UVPart:
    return plate(tris // 200, 100, sx=0.5, sy=0.5)


def named(report, name):
    return next(r for r in report.results if r.name == name)


# ---- the regression ----------------------------------------------------------------------------------------------

def test_session_bisect_connect_on_flat_strip_is_rejected(capsys):
    before = {"Main": big_main(), "Letters": strip()}
    after = {**before, "Letters": session_bisect_connect(before["Letters"])}
    report = check_densify(before, after, "Letters")
    deg = named(report, "degenerate_3d_faces")
    with capsys.disabled():
        print(f"\n[#1537] session bisect+connect on a 148-quad strip: degenerate 3D faces new={deg.count} "
              f"(baseline {deg.baseline}, after {deg.after}); uv zero-area new="
              f"{named(report, 'uv_zero_area_faces').count}; broken={[r.name for r in report.broken]}")
    assert not report.passed
    assert deg.count == SESSION_DEGENERATE and deg.baseline == 0
    assert named(report, "uv_zero_area_faces").count == SESSION_DEGENERATE


def test_new_operation_on_the_same_strip_passes():
    before = {"Main": big_main(), "Letters": strip()}
    snapshot = {k: (p.mesh.vertices.copy(), p.mesh.triangles.copy(), p.uv.copy()) for k, p in before.items()}
    target = 3100                                      # limit(60 296) = 3015 < 3100
    result = densify_for_ucx_budget(before, "Letters", target)
    assert all(np.array_equal(a, b) for k, p in before.items()
               for a, b in zip(snapshot[k], (p.mesh.vertices, p.mesh.triangles, p.uv)))   # input not mutated
    assert result.object is not before and set(result.object) == set(before)
    assert result.applied, result.question
    assert result.report.passed and all(r.count == 0 for r in result.report.results)
    assert result.object["Main"] is before["Main"]
    assert result.notes["levels"] == 2 and result.notes["faces_after"] == 296 * 16
    assert result.notes["model_triangles_after"] >= result.notes["needed_model_triangles"] == 61_981
    assert ucx_triangle_limit(result.notes["model_triangles_after"]) >= target


def test_runtime_on_a_50k_face_part_is_under_the_bound(capsys):
    part = plate(250, 100, sx=0.02, sy=0.02)          # 50 000 faces
    assert len(part.mesh.triangles) == 50_000
    obj = {"Main": big_main(), "Plate": part}
    t0 = time.perf_counter()
    result = densify_for_ucx_budget(obj, "Plate", 6_000)   # 110 000 (limit 5 500) -> needs 119 981: one level
    elapsed = time.perf_counter() - t0
    with capsys.disabled():
        print(f"\n[#1537] densify_for_ucx_budget 50 000 -> {result.notes['faces_after']} faces, levels="
              f"{result.notes['levels']}: {elapsed:.2f} s total (bound {RUNTIME_BOUND_S} s)")
    assert result.applied, result.question
    assert result.notes["faces_after"] == 200_000
    assert elapsed < RUNTIME_BOUND_S
    long_strip = {"Main": big_main(), "Strip": strip(25_000)}   # 50 000 faces, 50 002 open border edges
    t0 = time.perf_counter()
    result = densify_for_ucx_budget(long_strip, "Strip", 6_000)
    elapsed = time.perf_counter() - t0
    with capsys.disabled():
        print(f"[#1537] same on a 25 000-quad strip (50 002 border edges): {elapsed:.2f} s")
    assert result.applied, result.question
    assert elapsed < RUNTIME_BOUND_S


@pytest.mark.parametrize("seed", range(10))
def test_probe_grid_cover_equals_brute_force(seed):
    from dt_ai.ops.densify import _covered, _point_triangle_distance
    rng = np.random.default_rng(seed)
    base = rng.uniform(0, 3, (40, 3, 3))
    base[::3, 2] = base[::3, 1]                              # every third one a segment
    base[::5] *= [1, 1, 0]                                   # some flat
    pick = rng.integers(0, len(base), 300)
    w = rng.dirichlet([1, 1, 1], (300, 2))
    items = np.einsum("pkc,pcd->pkd", w, base[pick])        # points inside base faces ...
    items[::4] += rng.normal(0, 1e-3, (75, 2, 3))           # ... some pushed off by ~1 mm
    items[1::7] += rng.normal(0, 2e-5, (len(items[1::7]), 2, 3))   # ... some within tol noise
    brute = np.zeros(len(items), bool)
    for s in range(len(base)):
        d = [_point_triangle_distance(items[:, k], np.repeat(base[s:s + 1], len(items), 0)) for k in range(2)]
        brute |= (d[0] <= 1e-4) & (d[1] <= 1e-4)
    assert brute.any() and (~brute).any()
    assert np.array_equal(_covered(items, base), brute)


# ---- [D012] and the question ---------------------------------------------------------------------------------------

def test_no_part_stops_with_the_question_which_part():
    obj = {"Main": big_main(), "Letters": strip(), "Plate": plate(10, 10)}
    result = densify_for_ucx_budget(obj, None, 3100)
    assert not result.applied and result.object is obj and result.report is None
    assert result.question.startswith("which part should be densified?")
    assert "Letters (296 tris)" in result.question and "Plate (200 tris)" in result.question
    assert "Main (" not in result.question
    assert result.notes["add_triangles"] == 61_981 - _tris(obj)


@pytest.mark.parametrize("name, protected", [
    ("SM_A_Main", True), ("SM_A_Main.001", True), ("main", True), ("SM_A_MainGlass", False),
])
def test_main_name_variants_require_confirmation(name, protected):
    obj = {"Big": big_main(), name: strip()}
    snapshot = {key: (p.mesh.vertices.copy(), p.mesh.triangles.copy(), p.uv.copy()) for key, p in obj.items()}
    question = densify_for_ucx_budget(obj, None, 3100)
    assert not question.applied and question.object is obj and question.report is None
    assert question.question is not None
    assert (f"{name} (296 tris)" in question.question) is not protected
    result = densify_for_ucx_budget(obj, name, 3100)
    if protected:
        assert not result.applied and result.object is obj and result.report is None
        assert result.question is not None and "never densified automatically" in result.question
        result = densify_for_ucx_budget(obj, name, 3100, allow_main=True)
    assert result.applied and result.report.passed, result.question
    assert result.part == name and set(result.object) == set(obj)
    assert result.object["Big"] is obj["Big"]
    assert all(np.array_equal(a, b) for key, p in obj.items()
               for a, b in zip(snapshot[key], (p.mesh.vertices, p.mesh.triangles, p.uv)))


@pytest.mark.parametrize("token", ["".join(chars) for chars in product(*zip("main", "MAIN"))])
@pytest.mark.parametrize("suffix", ["", ".000", ".001", ".999"])
@pytest.mark.parametrize("template", ["{}", "SM_A_{}", "SM_A_{}_Letters"])
def test_probe_main_case_suffix_and_token_positions(token, suffix, template):
    name = template.format(token) + suffix
    p = strip()
    # Shared mesh identity must not bypass protection or cause input mutations.
    obj = {"Big": big_main(), name: p, "SM_A_MainGlass.001": p}
    snapshot = (p.mesh.vertices.copy(), p.mesh.triangles.copy(), p.uv.copy())
    for _ in range(2):
        refused = densify_for_ucx_budget(obj, name, 3100)
        assert not refused.applied and refused.object is obj and refused.report is None
        assert refused.question is not None and "never densified automatically" in refused.question
    for allow_main in (False, True, False):
        question = densify_for_ucx_budget(obj, None, 3100, allow_main=allow_main)
        assert not question.applied and question.object is obj and question.report is None
        assert question.question is not None
        assert f"{name} (" not in question.question
        assert "SM_A_MainGlass.001 (296 tris)" in question.question
    assert all(np.array_equal(a, b) for a, b in zip(snapshot, (p.mesh.vertices, p.mesh.triangles, p.uv)))


def test_main_is_never_densified_without_explicit_confirmation():
    obj = {"elv_Main": strip(), "Plate": plate(2, 2)}
    obj_big = {**obj, "Other": big_main()}
    refused = densify_for_ucx_budget(obj_big, "elv_Main", 3100)
    assert not refused.applied and "never densified automatically" in refused.question
    assert refused.object is obj_big
    ok = densify_for_ucx_budget(obj_big, "elv_Main", 3100, allow_main=True)
    assert ok.applied


@pytest.mark.parametrize("n,u,need", [(40_000, 15_000, 40_000), (40_000, 15_001, 300_001), (60_000, 3_000, 60_000),
                                      (60_000, 3_001, 60_001), (60_000, 3_100, 61_981), (10, 100_000, 1_999_981)])
def test_needed_model_triangles_follows_d012(n, u, need):
    got = needed_model_triangles(n, u)
    assert got == need
    assert ucx_triangle_limit(got) >= u
    assert got == n or ucx_triangle_limit(got - 1) < u or got - 1 < n


def test_exactly_at_the_budget_needs_nothing():
    obj = {"Main": big_main(), "Letters": strip()}
    limit = ucx_triangle_limit(_tris(obj))
    result = densify_for_ucx_budget(obj, "Letters", limit)
    assert not result.applied and result.question is None and result.object is obj
    assert result.notes["reason"] == "UCX already within the budget"
    assert densify_for_ucx_budget(obj, "Letters", limit + 1).applied


def test_ucx_above_the_cap_is_a_question_not_a_densify():
    obj = {"Main": big_main(), "Letters": strip()}
    result = densify_for_ucx_budget(obj, "Letters", 100_001)
    assert not result.applied and "cap 100000" in result.question and result.object is obj
    with pytest.raises(ValueError, match="cap"):
        needed_model_triangles(1, 100_001)


@pytest.mark.parametrize("bad", [0, -1, True, 1.5, float("nan"), float("inf"), None, "3100"])
def test_target_must_be_a_positive_integer(bad):
    with pytest.raises(ValueError, match="target_tris"):
        densify_for_ucx_budget({"Main": big_main(), "Letters": strip()}, "Letters", bad)


def test_bad_object_or_part_is_an_error_naming_it():
    obj = {"Main": big_main(), "Letters": strip()}
    with pytest.raises(ValueError, match="'Nope'"):
        densify_for_ucx_budget(obj, "Nope", 3100)
    with pytest.raises(ValueError, match="UCX_Main_01"):
        densify_for_ucx_budget({**obj, "UCX_Main_01": strip()}, "Letters", 3100)
    with pytest.raises(ValueError, match="non-empty"):
        densify_for_ucx_budget({}, "Letters", 3100)
    with pytest.raises(ValueError, match="uv must be finite"):
        UVPart(Mesh(np.eye(3), [[0, 1, 2]]), [[[0, 0], [1, 0], [np.nan, 1]]])


def test_too_small_part_asks_for_another_part():
    obj = {"Main": big_main(), "Tiny": plate(1, 1)}
    result = densify_for_ucx_budget(obj, "Tiny", 3100)
    assert not result.applied and "which other part" in result.question and result.object is obj


def test_a_broken_invariant_rolls_back_with_a_question():
    tiny = 2e-5                                        # face area 2e-10: its children (5e-11) are degenerate
    small = UVPart(Mesh(np.array([[0, 0, 0], [tiny, 0, 0], [0, tiny, 0]], float), [[0, 1, 2]] * 1),
                   [[[0, 0], [1, 0], [0, 1]]])
    small = subdivide(small, 0)
    big = plate(300, 1)
    part = UVPart(Mesh(np.concatenate([big.mesh.vertices, small.mesh.vertices + [0, 5, 0]]),
                       np.concatenate([big.mesh.triangles, small.mesh.triangles + len(big.mesh.vertices)])),
                  np.concatenate([big.uv, small.uv]))
    obj = {"Main": big_main(), "Plate": part}
    result = densify_for_ucx_budget(obj, "Plate", 3100)
    assert not result.applied and result.object is obj
    assert "degenerate_3d_faces" in result.question and "rolled back" in result.question
    assert named(result.report, "degenerate_3d_faces").count == 4


def test_area_exactly_at_the_threshold_is_degenerate(monkeypatch):
    import dt_ai.ops.densify as densify
    side = 2.0 ** -16
    at = UVPart(Mesh(np.array([[0, 0, 0], [side, 0, 0], [0, side, 0]], float), [[0, 1, 2]]),
                [[[0, 0], [1, 0], [0, 1]]])
    monkeypatch.setattr(densify, "DEGENERATE_AREA_M2", float(densify.face_areas(at.mesh)[0]))   # exactly at it
    big = UVPart(Mesh(at.mesh.vertices * 1e3, at.mesh.triangles), at.uv)
    report = check_densify({"P": big}, {"P": at}, "P")
    assert named(report, "degenerate_3d_faces").count == 1
    monkeypatch.setattr(densify, "DEGENERATE_AREA_M2", float(densify.face_areas(at.mesh)[0]) * 0.999)
    assert named(check_densify({"P": big}, {"P": at}, "P"), "degenerate_3d_faces").count == 0


def test_pre_existing_degenerate_and_mirrored_faces_are_baseline_not_new():
    p = plate(20, 2)
    uv = p.uv.copy()
    uv[0] = uv[0][:, ::-1]                              # one mirrored UV face
    v = p.mesh.vertices.copy()
    t = np.concatenate([p.mesh.triangles, [[0, 3, 6]]])   # one zero-area 3D face along y = 0
    uv = np.concatenate([uv, [[[0, 0], [0.1, 0], [0.2, 0]]]])
    src = UVPart(Mesh(v, t), uv)
    assert uv_signed_areas(src.uv)[0] < 0
    obj = {"Main": big_main(), "Plate": src}
    result = densify_for_ucx_budget(obj, "Plate", 3100, max_levels=3)
    assert result.applied, result.question
    rep = result.report
    assert named(rep, "uv_mirrored_faces").baseline == 1 and named(rep, "uv_mirrored_faces").after == 64
    assert named(rep, "degenerate_3d_faces").baseline == 1 and named(rep, "degenerate_3d_faces").count == 0


def test_material_ids_are_carried():
    obj = {"Main": big_main(), "Plate": plate(20, 4, ids=7)}
    result = densify_for_ucx_budget(obj, "Plate", 3100)
    assert result.applied and set(result.object["Plate"].material_ids.tolist()) == {7}


# ---- probes: generated inputs and broken "after" scenes -------------------------------------------------------------

@pytest.mark.parametrize("seed", range(20))
def test_probe_random_parts_densify_under_the_invariants(seed):
    rng = np.random.default_rng(seed)
    if seed % 2:
        box = _box_mesh(rng.uniform(-5, 0, 3), rng.uniform(0.5, 5, 3))
        tri = box.vertices[box.triangles]
        part = UVPart(Mesh(tri.reshape(-1, 3), np.arange(36).reshape(12, 3)),   # unwelded, as an FBX readback
                      rng.uniform(0, 1, (12, 3, 2)) * [1, 0] + [[[0, 0], [0, 0], [0, 1]]])
    else:
        part = plate(int(rng.integers(2, 30)), int(rng.integers(1, 6)), rng.uniform(0.05, 2), rng.uniform(0.05, 2))
        noise = rng.normal(0, 0.01, part.mesh.vertices.shape) * [0, 0, 1]
        part = UVPart(Mesh(part.mesh.vertices + noise, part.mesh.triangles), part.uv)
    levels = int(rng.integers(1, 4))
    dense = subdivide(part, levels)
    report = check_densify({"P": part}, {"P": dense}, "P")
    assert report.passed, [(r.name, r.offenders) for r in report.broken]
    assert len(dense.mesh.triangles) == len(part.mesh.triangles) * 4 ** levels
    assert len(border_edges(dense.mesh)) == len(border_edges(part.mesh)) * 2 ** levels


def test_probe_check_rejects_each_broken_invariant():
    p = plate(10, 3)
    d = subdivide(p, 1)
    obj = {"Main": big_main(), "P": p}

    def broken(after_p, other=None):
        after = {**obj, "P": after_p}
        if other:
            after["Main"] = other
        return {r.name for r in check_densify(obj, after, "P").broken}

    assert broken(d) == set()
    v = d.mesh.vertices.copy()
    v[0] += [0, 0, -0.5]
    assert "bbox_unchanged" in broken(UVPart(Mesh(v, d.mesh.triangles), d.uv))   # the moved corner also opens edges
    uv = d.uv.copy()
    uv[5] = uv[5][::-1]
    assert "uv_mirrored_faces" in broken(UVPart(d.mesh, uv))
    uv = d.uv.copy()
    uv[0, 0] = [2.0, 2.0]
    assert "uv_bounds_unchanged" in broken(UVPart(d.mesh, uv))
    inner = np.flatnonzero(np.abs(d.mesh.corners().mean(1)[:, 1] - 0.15) < 0.03)[0]
    keep = np.arange(len(d.mesh.triangles)) != inner
    assert broken(UVPart(Mesh(d.mesh.vertices, d.mesh.triangles[keep]), d.uv[keep])) == {"open_edges"}
    assert broken(d, other=plate(10, 3)) == {"other_parts_unchanged"}
    assert "material_ids_kept" in broken(UVPart(d.mesh, d.uv, np.zeros(len(d.mesh.triangles), int)))


def _tris(obj):
    return sum(len(p.mesh.triangles) for p in obj.values())
