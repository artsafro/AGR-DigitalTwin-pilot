"""One engine behind every overlap check (#556): the contact rule runs only in the fast core (`inv_xview_fast`).

The per-triangle-pair implementation that `inv_xview` used before #556 is kept here, and only here, as the test
oracle (`_reference_pairs`, brute force over every triangle pair, area rule without prefilter): the production
`_pairs_found` must return the identical {(i, j): (contact, area, separation)} dict on generated meshes.
"""
import numpy as np
import pytest

from dt_ai.ops import inv_xview as X
from dt_ai.ops import inv_xview_fast as F
from dt_ai.ops import xview_gate as G
from dt_ai.ops.inv_quads import PolyMesh
from tests.ops.xview_oracle import ref_contact as _ref_contact

TOL = X.XviewTolerance()


# ---- the oracle: the pre-#556 contact test, per triangle pair (tests/ops/xview_oracle.py) -----------------------------

def _reference_pairs(mesh, tol=TOL, active_parts=None):
    v = mesh.vertices
    tris, owner, poly_key = X._prepare(mesh)
    found: dict = {}
    if not len(tris):
        return found
    nv = len(v)
    p = v[tris]
    cr = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    ln = np.linalg.norm(cr, axis=1)
    live = ln / 2 > X.AREA_EPS_M2
    nrm = np.divide(cr, ln[:, None], out=np.zeros_like(cr), where=live[:, None])
    rank = np.empty(len(tris), np.int64)
    rank[np.argsort(p.min(1)[:, 0], kind="stable")] = np.arange(len(tris))
    s, t = np.triu_indices(len(tris), 1)
    ok = (owner[s] != owner[t]) & live[s] & live[t] & (np.abs(X._dot(nrm[s], nrm[t])) >= tol.parallel_cos_min)
    if active_parts is not None:
        ok &= active_parts[owner[s]] | active_parts[owner[t]]
    s, t = s[ok], t[ok]
    if not len(s):
        return found
    sw = rank[s] > rank[t]
    s, t = np.where(sw, t, s), np.where(sw, s, t)
    con = _ref_contact(v, tris, nrm, s, t, poly_key, owner, nv, tol.face_m) | \
        _ref_contact(v, tris, nrm, t, s, poly_key, owner, nv, tol.face_m)
    hit_a, sep, _ = X._area(v, tris, nrm, s, t, tol.face_m, prefilter=False)
    for k in np.flatnonzero(con | hit_a):
        i, j = sorted((int(owner[s[k]]), int(owner[t[k]])))
        prev = found.get((i, j), (False, False, np.inf))
        found[(i, j)] = (prev[0] or bool(con[k]), prev[1] or bool(hit_a[k]), min(prev[2], float(sep[k])))
    return found


def _production_pairs(mesh, tol=TOL, active_parts=None):
    tris, owner, poly_key = X._prepare(mesh)
    active = None if active_parts is None else active_parts[owner]
    return X._pairs_found(mesh.vertices, tris, owner, poly_key, tol, active)


# ---- generated meshes ----------------------------------------------------------------------------------------------

def _sheet(rng, n, origin, z, tilt_deg=0.0, jitter=0.0):
    xs, ys = np.meshgrid(np.arange(n + 1, dtype=float), np.arange(n + 1, dtype=float))
    pts = np.stack([xs.ravel(), ys.ravel(), np.zeros(xs.size)], 1) * rng.uniform(0.3, 1.5)
    pts[:, 2] = z + np.tan(np.radians(tilt_deg)) * pts[:, 0] + rng.uniform(-jitter, jitter, len(pts))
    pts[:, :2] += origin
    k = n + 1
    quads = [(i * k + j, i * k + j + 1, (i + 1) * k + j + 1, (i + 1) * k + j) for i in range(n) for j in range(n)]
    return pts, quads


def _scene(seed):
    """Two to four welded sheets near each other: shared edges, contact at the 5 mm band, tilts at 0.81 deg, duplicates."""
    rng = np.random.default_rng(seed)
    verts, faces = [], []
    for _ in range(int(rng.integers(2, 5))):
        z = float(rng.choice([0.0, 0.002, 0.005, 0.0050001, 0.0049, 0.3, rng.uniform(-0.006, 0.006)]))
        tilt = float(rng.choice([0.0, 0.0, 0.5, 0.81, 0.815, 5.0]))
        pts, quads = _sheet(rng, int(rng.integers(1, 4)), rng.uniform(-1.0, 1.0, 2), z, tilt,
                            float(rng.choice([0.0, 0.0, 0.001])))
        if rng.random() < 0.3:                                    # triangles instead of quads
            quads = [t for q in quads for t in ((q[0], q[1], q[2]), (q[0], q[2], q[3]))]
        if rng.random() < 0.3:                                    # reversed winding
            quads = [tuple(reversed(q)) for q in quads]
        off = sum(len(x) for x in verts)
        verts.append(pts)
        faces += [tuple(i + off for i in q) for q in quads]
    if rng.random() < 0.3:                                        # a duplicate face on shared vertex indices
        faces.append(tuple(reversed(faces[int(rng.integers(len(faces)))])))
    v = np.vstack(verts)
    v[:, :2] += rng.uniform(-5e4, 5e4, 2) * float(rng.random() < 0.3)   # site coordinates far from the origin
    return PolyMesh(v, tuple(faces))


@pytest.mark.parametrize("seed", range(120))
def test_probe_pairs_found_equal_the_per_triangle_pair_oracle(seed):
    mesh = _scene(seed)
    assert _production_pairs(mesh) == _reference_pairs(mesh)


@pytest.mark.parametrize("seed", range(40))
def test_probe_active_pairs_equal_the_oracle_restricted_to_hot_parts(seed):
    mesh = _scene(1000 + seed)
    hot = np.random.default_rng(seed).random(len(mesh.faces)) < 0.3
    assert _production_pairs(mesh, active_parts=hot) == _reference_pairs(mesh, active_parts=hot)


def test_controls_kinds_and_separation_unchanged():
    """The F3 controls of docs/research/xview-fast-core-production-handoff.md, pair level."""
    s3 = 3 ** 0.5
    a = [(0, 0, 0), (2, 0, 0), (0, 2, 0)]

    def two(p, q):
        return PolyMesh(np.array(p + q, float), ((0, 1, 2), (3, 4, 5)))
    cases = {
        "clean": (two(a, [(10, 0, 0), (12, 0, 0), (10, 2, 0)]), []),
        "contact": (two(a, [(1, 1, 0), (3, 3, 0), (3, 4, 0)]), [(0, 1, "contact", None)]),
        "area": (two([(0, 0, 0), (6, 0, 0), (3, 3 * s3, 0)], [(6, 2 * s3, 0), (0, 2 * s3, 0), (3, -s3, 0)]),
                 [(0, 1, "area", 0.0)]),
        "combined": (two(a, [(.5, .5, 0), (3, .5, 0), (.5, 3, 0)]), [(0, 1, "area+contact", 0.0)]),
        "boundary_5mm": (two(a, [(.5, .5, .005), (3, .5, .005), (.5, 3, .005)]), [(0, 1, "area+contact", 0.005)]),
        "beyond_5mm": (two(a, [(.5, .5, .0050001), (3, .5, .0050001), (.5, 3, .0050001)]), []),
    }
    for name, (mesh, want) in cases.items():
        got = X.face_pairs(mesh, TOL)
        assert [(i, j, k) for i, j, k, _ in got] == [(i, j, k) for i, j, k, _ in want], name
        for (_, _, _, s), (_, _, _, w) in zip(got, want):
            assert (s is None and w is None) or s == pytest.approx(w, abs=1e-12), name


# ---- one implementation: every entry point goes through the fast core -----------------------------------------------

def test_the_per_triangle_pair_contact_test_is_gone_from_the_kernel():
    assert not hasattr(X, "_contact")


def _two_quads():
    v = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
                  [.5, .5, .001], [1.5, .5, .001], [1.5, 1.5, .001], [.5, 1.5, .001]], float)
    return v, ((0, 1, 2, 3), (4, 5, 6, 7))


ENTRY_POINTS = {
    "part_report": lambda v, f: X.part_report("p", PolyMesh(v, f), TOL),
    "mesh_report": lambda v, f: X.mesh_report(v, f),
    "xview_overlaps": lambda v, f: X.xview_overlaps({"p": PolyMesh(v, f)}, "NPM"),
    "gate": lambda v, f: G.part_gate(G.Part("p", v, f, None), TOL, "as-stored"),
    "xview_state": lambda v, f: X.xview_state(v, f, ["a", "b"]),
    "xview_state_incremental": lambda v, f: X.xview_state_incremental(
        v, f, ["a", "b"], X.xview_state(v, f, ["a", "b"]), ["b"]),
}


class _Called(Exception):
    pass


@pytest.mark.parametrize("entry", sorted(ENTRY_POINTS))
def test_every_entry_point_calls_the_fast_core(entry, monkeypatch):
    v, f = _two_quads()
    ENTRY_POINTS[entry](v, f)                                    # works before the patch

    def boom(*a, **k):
        raise _Called

    monkeypatch.setattr(F, "contact_tri_pairs", boom)
    with pytest.raises(_Called):
        ENTRY_POINTS[entry](v, f)


def test_flat_welded_grid_never_reaches_shapely(monkeypatch):
    """Adjacent coplanar triangles share an edge or a corner with zero overlap: the separating-axis prefilter skips
    them, so a clean flat grid makes no shapely intersection call (before #556: one per neighbour pair)."""
    import shapely
    calls = []
    real = shapely.intersection
    monkeypatch.setattr(shapely, "intersection", lambda *a, **k: calls.append(len(a[0])) or real(*a, **k))
    _, quads = _sheet(np.random.default_rng(0), 12, (0.0, 0.0), 0.0)
    xs, ys = np.meshgrid(np.arange(13, dtype=float), np.arange(13, dtype=float))
    v = np.stack([xs.ravel(), ys.ravel(), np.zeros(xs.size)], 1)
    r = X.part_report("grid", PolyMesh(v, tuple(quads)), TOL)
    assert r.face_pairs == () and r.vertex_pairs == ()
    assert sum(calls) == 0


def test_probe_sat_skip_never_hides_an_overlap_area():
    """Generated 2D triangle pairs (shared edges, shared corners, touching, slivers, 1e5 m site offsets): whenever
    `_sat_zero` skips a pair, shapely's intersection area is <= AREA_MIN_M2 / 2 (so the old code had no hit either)."""
    import shapely
    rng = np.random.default_rng(556)
    n = 20000
    a = rng.uniform(-1, 1, (n, 3, 2)) * rng.choice([1e-3, 0.1, 1.0, 30.0], (n, 1, 1))
    b = rng.uniform(-1, 1, (n, 3, 2)) * rng.choice([1e-3, 0.1, 1.0, 30.0], (n, 1, 1))
    kind = rng.integers(0, 4, n)
    b[kind == 1, :2] = a[kind == 1, :2]                                  # shared edge, third vertex anywhere
    b[kind == 2, 0] = a[kind == 2, 0]                                    # shared corner
    mirror = a[:, :2].mean(1)                                            # third vertex mirrored: opposite side
    b[kind == 3, :2] = a[kind == 3, :2]
    b[kind == 3, 2] = 2 * mirror[kind == 3] - a[kind == 3, 2] + rng.normal(0, 1e-9, (int((kind == 3).sum()), 2))
    off = rng.uniform(-1e5, 1e5, (n, 1, 2)) * (rng.random((n, 1, 1)) < 0.5)
    a, b = a + off, b + off
    skip = X._sat_zero(a, b)
    area = shapely.area(shapely.intersection(shapely.polygons(a), shapely.polygons(b)))
    assert skip.sum() > 5000                                             # the probe exercises the skip
    assert np.all(area[skip] <= X.AREA_MIN_M2 / 2), np.max(area[skip])
    assert np.all(~skip[area > X.AREA_MIN_M2])


def test_xview_lists_output_unchanged_by_the_triangle_level_api():
    v, f = _two_quads()
    out = F.xview_lists(v, f, TOL)
    assert out["face_pairs"] == ((1, 2),) and out["xview_faces"] == (1, 2)
