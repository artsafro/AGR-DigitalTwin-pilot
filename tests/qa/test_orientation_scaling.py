"""Synthetic orientation scaling and exact equivalence (no production data).

Pattern: n/a | new-case: issue-203 synthetic orientation acceleration probes.
"""
import numpy as np
import pytest

from twinqa.geometry import checks
from twinqa.geometry.mesh import Soup


def box(n, size=10.0):
    """Appendix A of mesh-audit-scaling-real-sizes, unchanged construction."""
    verts, index, tris = [], {}, []

    def vid(p):
        key = tuple(round(c, 9) for c in p)
        if key not in index:
            index[key] = len(verts)
            verts.append(key)
        return index[key]

    g = np.linspace(0.0, size, n + 1)
    for axis in range(3):
        for side in (0.0, size):
            u, w = [k for k in range(3) if k != axis]
            for i in range(n):
                for j in range(n):
                    q = []
                    for a, b in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)):
                        p = [0.0, 0.0, 0.0]
                        p[axis], p[u], p[w] = side, g[a], g[b]
                        q.append(vid(p))
                    t1, t2 = (q[0], q[1], q[2]), (q[0], q[2], q[3])
                    if (side == 0.0) == ((u - axis) % 3 == 1):
                        t1, t2 = t1[::-1], t2[::-1]
                    tris += [t1, t2]
    return soup(np.array(verts, float), np.array(tris, int))


def soup(v, t):
    return Soup(v, t, np.ones(len(t), int), np.full(len(t), 3), {}, 0,
                ("model",), np.zeros(len(t), int))


def bipyramid(faces):
    m = max(faces // 2, 3)
    a = np.linspace(0, 2 * np.pi, m, endpoint=False)
    v = np.vstack([np.stack([10 * np.cos(a), 10 * np.sin(a), np.zeros(m)], 1),
                   [[0, 0, 10.0]], [[0, 0, -10.0]]])
    t = [(i, (i + 1) % m, m) for i in range(m)] + [((i + 1) % m, i, m + 1) for i in range(m)]
    return soup(v, np.array(t, int))


def assert_equivalent(model, monkeypatch):
    import orientation_reference as ref
    expected = ref._orientation_hits(model)
    implementation = checks._first_back_hits

    def compare_direction(*args):
        old, new = ref._first_back_hits(*args), implementation(*args)
        for a, b in zip(old, new):
            np.testing.assert_array_equal(a, b)
        return new

    with monkeypatch.context() as patch:
        patch.setattr(checks, "_first_back_hits", compare_direction)
        actual = checks._orientation_hits(model)
    for a, b in zip(actual, expected):
        np.testing.assert_array_equal(a, b)
    observed = checks.check_orientation(model, {"weld_m": 0.003})
    with monkeypatch.context() as patch:
        patch.setattr(checks, "_orientation_hits", ref._orientation_hits)
        assert checks.check_orientation(model, {"weld_m": 0.003}) == observed


@pytest.mark.parametrize("seed", range(8))
def test_exact_randomized_corpus(seed, monkeypatch):
    rng = np.random.default_rng(seed)
    models = [box(2), bipyramid(80)]
    for source in [box(2), bipyramid(80)]:
        source.vertices = source.vertices @ np.linalg.qr(rng.normal(size=(3, 3)))[0]
        source.vertices = source.vertices * rng.uniform(0.1, 3, size=3) + rng.normal(size=3)
        flip = rng.random(len(source.triangles)) < 0.3
        source.triangles[flip] = source.triangles[flip, ::-1]
        models.append(source)
    shell = box(2)
    shell.triangles = shell.triangles[rng.random(len(shell.triangles)) > 0.25]
    shell.material_ids = shell.material_ids[:len(shell.triangles)]
    shell.mesh_index = shell.mesh_index[:len(shell.triangles)]
    models.append(shell)
    outer, inner = box(1), box(1)
    nested = soup(np.vstack([outer.vertices, inner.vertices * 0.2 + 4]),
                  np.vstack([outer.triangles, inner.triangles[:, ::-1] + len(outer.vertices)]))
    nested.mesh_names = ("outer", "inner")
    nested.mesh_index[12:] = 1
    models.append(nested)
    for model in models:
        assert_equivalent(model, monkeypatch)


@pytest.mark.parametrize("shape", ["box", "slivers"])
def test_orientation_real_size_exact(shape):
    """Real-size inputs return the exact clean-model result; no wall-clock budget (see the perf test)."""
    model = box(65) if shape == "box" else bipyramid(5000)
    result = checks.check_orientation(model, {"weld_m": 0.003})
    assert result["status"] == "pass"
    assert result["value"] == 0
    for mesh in result["details"]["meshes"]:
        assert mesh["outside_back_faces"] == 0
        assert mesh["winding_bad_edges"] == 0


@pytest.mark.perf
@pytest.mark.parametrize("shape,limit", [("box", 10.0), ("slivers", 5.0)])
def test_orientation_real_size_budget(shape, limit, measure_process_time):
    """Opt-in CPU-time budget: warm-up then median of 5 runs; wall time reported only."""
    model = box(65) if shape == "box" else bipyramid(5000)
    median, wall = measure_process_time(lambda: checks.check_orientation(model, {"weld_m": 0.003}))
    print(f"[perf] {shape} ({len(model.triangles)} tris): median CPU {median:.4f}s, "
          f"wall {wall:.4f}s, budget {limit}s")
    assert median < limit, f"{len(model.triangles)} triangles: {median:.4f}s >= {limit}s"


def test_orientation_real_size_exact_fails_on_wrong_result(monkeypatch):
    """The default-suite exact-result assertion catches a spurious back face, not only timing."""
    model = box(2)
    real = checks._orientation_hits

    def wrong(model_):
        backs, judged, rays, nondeg = real(model_)
        backs = backs.copy()
        backs[0] = 1
        return backs, judged, rays, nondeg

    monkeypatch.setattr(checks, "_orientation_hits", wrong)
    result = checks.check_orientation(model, {"weld_m": 0.003})
    assert result["status"] == "fail"
    assert result["value"] >= 1


@pytest.mark.parametrize("case", ["box", "inverted", "tiny", "decor", "nested", "open", "mirrored",
                                  "flip1", "cap", "elevated", "sloped", "d093", "b01", "b02", "b02t"])
def test_legacy_fixtures_exact(case, monkeypatch):
    from test_orientation import _box, _resize, _corner_pilaster, _built
    from twinqa.geometry.mesh import from_dump
    if case.startswith("b0"):
        _, dump, _ = _built({"b01": "bench-b01-box", "b02": "bench-b02-corner-niche",
                             "b02t": "bench-b02t-terrace"}[case])
    elif case == "d093":
        _, dump = _corner_pilaster()
    elif case in ("cap", "elevated", "sloped"):
        z = -3.25 + (0.01 if case == "elevated" else 0)
        face = {"name": "cap", "vertices": [[0, 0, z], [0, 1, z],
                [1, 0, z + (0.01 if case == "sloped" else 0)]], "triangles": [[0, 1, 2]]}
        dump = {"meshes": [_box("body", shift=(10, 10, -3.25)), face]}
    else:
        body = _box(reverse=range(12) if case in ("inverted", "tiny") else ({4} if case == "flip1" else ()),
                    drop_bottom=case == "open", mirror=case == "mirrored")
        if case == "tiny":
            body = _resize(body, 0.05)
        meshes = [body]
        if case in ("decor", "nested"):
            meshes = [_resize(_box("body"), 100),
                      _resize(_box("inner", reverse=range(12)), 0.2,
                              (49.9, 49.9, 49.9) if case == "nested" else (101, 50, 50))]
        dump = {"meshes": meshes}
    assert_equivalent(from_dump(dump), monkeypatch)


@pytest.mark.parametrize("seed", range(16))
def test_projected_candidates_exact(seed):
    """Arbitrary projections, boundaries, near-singular triangles and tied depths."""
    import orientation_reference as ref
    rng = np.random.default_rng(seed + 203)
    xy = rng.uniform(-2, 2, (80, 3, 2))
    # Long slivers over many orders of magnitude, including legacy numeric ghosts.
    for i, width in enumerate(np.logspace(-12, -1, 12)):
        xy[i] = [[-1, -1], [1, 1], [1, 1 + width]]
    xy[12:16] = xy[16]  # exact depth/dot ties across chunk boundaries
    depth = np.zeros((80, 3))
    dot = rng.choice([-1.0, 1.0], 80)
    dot[12:17] = 1
    points = np.vstack([rng.uniform(-2, 2, (300, 2)), xy.reshape(-1, 2), xy.mean(1)])
    points = np.vstack([points, points + 1e-10, points - 1e-10])
    args = xy[:, :, 0], xy[:, :, 1], depth, dot, points[:, 0], points[:, 1]
    for a, b in zip(ref._first_back_hits(*args), checks._first_back_hits(*args)):
        np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("scale,offset", [(1e-6, 0.), (1., 1e9), (1e6, -1e12)])
def test_projection_scale_and_translation(scale, offset):
    import orientation_reference as ref
    rng = np.random.default_rng(203)
    xy = rng.normal(size=(40, 3, 2)) * scale + offset
    points = np.vstack([rng.normal(size=(200, 2)) * scale + offset, xy.mean(1), xy.reshape(-1, 2)])
    args = (xy[:, :, 0], xy[:, :, 1], rng.normal(size=(40, 3)), rng.choice([-1., 1.], 40),
            points[:, 0], points[:, 1])
    for a, b in zip(ref._first_back_hits(*args), checks._first_back_hits(*args)):
        np.testing.assert_array_equal(a, b)


def test_pair_working_set_is_bounded(monkeypatch):
    """One crowded cell: quadratic pair count, bounded batches, stable ties."""
    import orientation_reference as ref
    n, nr, bound = 250, 300, 127
    s = np.tile([0., 1., 0.], (n, 1))
    t = np.tile([0., 0., 1.], (n, 1))
    depth = np.zeros_like(s)
    dot = np.ones(n)
    dot[200] = -1  # later batch must replace earlier back hits on a depth tie
    rays = np.full(nr, 0.25)
    expected = ref._first_back_hits(s, t, depth, dot, rays, rays)
    original = checks._orientation_pair_hits
    sizes = []

    def bounded(*args):
        sizes.append(len(args[-1]))
        assert len(args[-1]) <= bound
        return original(*args)

    monkeypatch.setattr(checks, "_ORI_PAIRS", bound)
    monkeypatch.setattr(checks, "_ORI_ROWS", 1024)
    monkeypatch.setattr(checks, "_orientation_pair_hits", bounded)
    actual = checks._first_back_hits(s, t, depth, dot, rays, rays)
    for a, b in zip(expected, actual):
        np.testing.assert_array_equal(a, b)
    assert len(sizes) > 1 and sum(sizes) == n * nr


@pytest.mark.parametrize("n,nr", [(0, 0), (0, 4), (4, 0)])
def test_empty_projection(n, nr):
    result = checks._first_back_hits(np.zeros((n, 3)), np.zeros((n, 3)), np.zeros((n, 3)),
                                     np.ones(n), np.zeros(nr), np.zeros(nr))
    assert all(a.shape == (0,) and a.dtype == np.int64 for a in result)
