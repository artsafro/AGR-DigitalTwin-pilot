"""inv_xview speed path and incremental per-part re-check (#535).

All meshes here are SYNTHETIC (random near-parallel polygon stacks), except the TOW02 / Ground v014 parity tests,
which read the local job evidence of #514 / #370 and skip when it is not on this PC.
Pattern: none | new-case: speed-path equivalence, incremental per-part state and keep parity tests for inv_xview (#535).
"""
import json
import os
import time
from pathlib import Path

import numpy as np
import pytest

from dt_ai.ops.inv_quads import PolyMesh
from dt_ai.ops import inv_xview as X
from dt_ai.ops.inv_xview import XviewTolerance, face_pairs, xview_state, xview_state_incremental

TOL = XviewTolerance()


# ---- generated meshes ----------------------------------------------------------------------------------------------

def _rot(rng):
    a = rng.normal(size=3)
    a /= np.linalg.norm(a)
    th = rng.uniform(0, 2 * np.pi)
    k = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(th) * k + (1 - np.cos(th)) * k @ k


def stack(seed, n=40, origin=(400.0, 390.0, 30.0)):
    """Random polygons near one plane: offsets 0-8 mm, tilts 0-1.2 deg, triangles, convex / concave quads, pentagons,
    some welded corners and duplicated faces; rotated and moved to site coordinates."""
    rng = np.random.default_rng(seed)
    v, f = [], []
    for _ in range(n):
        kind = rng.integers(0, 5)
        c = rng.uniform(-1, 1, 2)
        s = rng.uniform(0.05, 0.8)
        if kind == 0:
            q = c + s * rng.uniform(-1, 1, (3, 2))
        elif kind == 1:
            q = c + s * np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]]) * rng.uniform(0.5, 1, (4, 2))
        elif kind == 2:
            q = c + s * np.array([[0, 0], [2, 0], [1, 0.3], [1, 2]]) * 0.5     # concave
        elif kind == 3:
            ang = np.sort(rng.uniform(0, 2 * np.pi, 5))
            q = c + s * np.c_[np.cos(ang), np.sin(ang)]
        else:
            q = c + s * np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]])          # grid-like, shares edges
            q = np.round(q, 1)
        z = rng.choice([0.0, rng.uniform(-0.008, 0.008), 0.005, -0.005])
        tilt = np.deg2rad(rng.choice([0.0, rng.uniform(0, 1.2), 0.81]))
        p = np.c_[q, z + np.tan(tilt) * q[:, 0]]
        base = len(v)
        v += [tuple(x) for x in p]
        idx = list(range(base, base + len(p)))
        if rng.random() < 0.5:
            idx = idx[::-1]
        f.append(tuple(idx))
        if rng.random() < 0.08:
            f.append(tuple(idx))                                                  # duplicated face
        if rng.random() < 0.15 and base:
            j = int(rng.integers(0, base))                                       # weld a corner onto an earlier vertex
            v[base] = v[j]
            f[-1] = tuple(j if i == base else i for i in f[-1])
    vv = np.asarray(v) @ _rot(rng).T + np.asarray(origin)
    ok = []
    for k, face in enumerate(f):                                          # drop the self-intersecting ones
        try:
            X._polygon_triangles(k, face, vv)
            ok.append(face)
        except ValueError:
            pass
    return vv, ok


def brute(v, faces, tol=TOL):
    """Reference: per-polygon triangulation, every triangle pair, the #370 box test, no prefilter; separation =
    minimum over the hit triangle pairs (as #370)."""
    tris, owner = [], []
    for k, f in enumerate(faces):
        for t in X._polygon_triangles(k, f, v):
            tris.append(t)
            owner.append(k)
    tris, owner = np.asarray(tris, np.int64).reshape(-1, 3), np.asarray(owner, np.int64)
    nv = len(v)
    poly_key = np.unique(np.concatenate([np.full(len(f), k, np.int64) * nv + np.asarray(f) for k, f in
                                         enumerate(faces)]))
    p = v[tris]
    cr = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    ln = np.linalg.norm(cr, axis=1)
    live = ln / 2 > X.AREA_EPS_M2
    nrm = np.divide(cr, ln[:, None], out=np.zeros_like(cr), where=live[:, None])
    pad = tol.face_m / tol.parallel_cos_min + 1e-9
    lo, hi = p.min(1), p.max(1)
    order = np.argsort(lo[:, 0], kind="stable")
    rank = np.empty(len(tris), np.int64)
    rank[order] = np.arange(len(tris))
    s, t = np.triu_indices(len(tris), 1)
    sw = rank[s] > rank[t]
    s, t = np.where(sw, t, s), np.where(sw, s, t)
    ok = np.all((lo[t] <= hi[s] + pad) & (lo[s] <= hi[t] + pad), axis=1) & (owner[s] != owner[t]) & live[s] & live[t]
    s, t = s[ok], t[ok]
    ok = np.abs(np.einsum("ij,ij->i", nrm[s], nrm[t])) >= tol.parallel_cos_min
    s, t = s[ok], t[ok]
    found = {}
    if len(s):
        con = X._contact(v, tris, nrm, s, t, poly_key, owner, nv, tol.face_m) | \
            X._contact(v, tris, nrm, t, s, poly_key, owner, nv, tol.face_m)
        hit, sep, _ = X._area(v, tris, nrm, s, t, tol.face_m, prefilter=False)
        for k in range(len(s)):
            i, j = sorted((int(owner[s[k]]), int(owner[t[k]])))
            if con[k] or hit[k]:                                          # #370: hit triangle pairs only
                c0, a0, s0 = found.get((i, j), (False, False, np.inf))
                found[(i, j)] = (c0 or bool(con[k]), a0 or bool(hit[k]), min(s0, float(sep[k])))
    return [(i, j, X._kind(c, a), sp if np.isfinite(sp) else None)
            for (i, j), (c, a, sp) in sorted(found.items())]


def test_owns_equals_isin():
    rng = np.random.default_rng(5)
    key = np.unique(rng.integers(0, 500, 200))
    q = rng.integers(-5, 520, 3000)
    assert (X._owns(key, q) == np.isin(q, key)).all()
    assert not X._owns(np.zeros(0, np.int64), q).any()


@pytest.mark.parametrize("seed", range(12))
def test_probe_fast_face_pairs_equal_brute_force(seed):
    """Probe (seeds 0-11, 40-90 polygons each): grid broad phase + quad fan + area prefilter == brute force,
    pair set, kind and separation."""
    v, f = stack(seed, n=40 + 5 * seed)
    got = face_pairs(PolyMesh(v, tuple(f)), TOL)
    want = brute(v, f)
    assert [g[:3] for g in got] == [w[:3] for w in want]
    for g, w in zip(got, want):
        assert (g[3] is None) == (w[3] is None) and (g[3] is None or g[3] == w[3])


def test_probe_generated_stacks_do_hit():
    """The generator is not vacuous: contact and area pairs both occur."""
    kinds = set()
    for seed in range(12):
        v, f = stack(seed, n=40 + 5 * seed)
        kinds |= {p[2] for p in face_pairs(PolyMesh(v, tuple(f)), TOL)}
    assert {"contact", "area+contact"} <= kinds and len(kinds) >= 2


def test_fast_triangulation_equals_per_polygon():
    """Probe: `_triangulate` returns exactly the per-polygon triangles, also for tiny, degenerate and concave quads."""
    rng = np.random.default_rng(7)
    v = rng.uniform(-1, 1, (60, 3)) * np.array([1, 1, 1e-4]) + 400
    faces = [tuple(rng.choice(60, 4, replace=False)) for _ in range(300)]
    faces += [(0, 1, 2), (3, 4, 5), (6, 7, 8, 9)]
    v[9] = v[8] + 1e-5                                                     # sub-mm quad -> exact path
    good = []
    for k, f in enumerate(faces):
        try:
            good.append((f, X._polygon_triangles(k, f, v)))
        except ValueError:
            pass
    tris, owner = X._triangulate(PolyMesh(v, tuple(f for f, _ in good)))
    want = [t for _, ts in good for t in ts]
    assert [tuple(map(int, t)) for t in tris] == [tuple(map(int, t)) for t in want]
    assert len(good) > 100


def test_grid_pairs_equal_box_brute_force_with_huge_triangle():
    rng = np.random.default_rng(3)
    lo = rng.uniform(0, 10, (400, 3))
    hi = lo + rng.uniform(0, 0.3, (400, 3))
    hi[0] = lo[0] + 1000                                                   # one huge box: coarser grid, same pairs
    got = {tuple(sorted(p)) for a, b in X._grid_pairs(lo, hi, 0.005) for p in zip(a.tolist(), b.tolist())}
    i, j = np.triu_indices(400, 1)
    ok = np.all((lo[j] <= hi[i] + 0.005) & (lo[i] <= hi[j] + 0.005), axis=1)
    assert got == set(zip(i[ok].tolist(), j[ok].tolist()))


def test_grid_pairs_exactly_at_pad_is_a_pair():
    lo = np.array([[0.0, 0, 0], [1.005, 0, 0]])
    hi = np.array([[1.0, 1, 1], [2.0, 1, 1]])
    assert [len(a) for a, _ in X._grid_pairs(lo, hi, 0.005)] == [1]
    assert sum(len(a) for a, _ in X._grid_pairs(lo, hi, 0.0049)) == 0


# ---- incremental ---------------------------------------------------------------------------------------------------

def parts_of(seed, n_parts=4):
    v, f = stack(seed, n=60)
    rng = np.random.default_rng(seed + 100)
    lab = [f"p{int(x)}" for x in rng.integers(0, n_parts, len(f))]
    # parts must not share vertex indices with edits: give every face its own vertices except deliberate welds
    return v, f, lab


def _move(v, f, lab, part, dz):
    v2 = v.copy()
    ids = sorted({i for face, x in zip(f, lab) if x == part for i in face})
    v2[ids, 2] += dz
    return v2


def _rt(x):
    return json.loads(json.dumps(x))


@pytest.mark.parametrize("seed", range(8))
def test_probe_incremental_equals_full_after_random_edits(seed):
    """Probe (seeds 0-7): move one part by -6..6 mm, delete faces of a second, add a new part; the incremental
    state equals a full run (JSON round trip of the previous report included)."""
    v, f, lab = parts_of(seed)
    prev = _rt(xview_state(v, f, lab))
    rng = np.random.default_rng(seed)
    # parts sharing vertices with the moved one change too: list every part touching a moved vertex
    moved = "p0"
    v2 = _move(v, f, lab, moved, float(rng.uniform(-0.006, 0.006)))
    touched = {x for face, x in zip(f, lab) if any((v2[i] != v[i]).any() for i in face)}
    keep_f = [k for k, x in enumerate(lab) if not (x == "p1" and k % 2)]
    f2 = [f[k] for k in keep_f] + [f[0]]
    lab2 = [lab[k] for k in keep_f] + ["new"]
    changed = touched | {"p1", "new", moved}
    full = _rt(xview_state(v2, f2, lab2))
    inc = _rt(xview_state_incremental(v2, f2, lab2, prev, changed))
    assert inc == full


def test_incremental_no_change_returns_previous():
    v, f, lab = parts_of(1)
    prev = _rt(xview_state(v, f, lab))
    assert _rt(xview_state_incremental(v, f, lab, prev, [])) == prev


def _fixture():
    v, f, lab = parts_of(2)
    return v, f, lab, _rt(xview_state(v, f, lab))


def test_incremental_edited_part_not_listed_is_an_error_naming_it():
    v, f, lab, prev = _fixture()
    v2 = _move(v, f, lab, "p2", 0.003)
    others = {x for face, x in zip(f, lab) if x != "p2" and any((v2[i] != v[i]).any() for i in face)}
    with pytest.raises(ValueError, match="p2"):
        xview_state_incremental(v2, f, lab, prev, others)


@pytest.mark.parametrize("case", ["unknown", "added", "removed"])
def test_incremental_part_set_mismatch_is_an_error(case):
    v, f, lab, prev = _fixture()
    if case == "unknown":
        with pytest.raises(ValueError, match="ghost"):
            xview_state_incremental(v, f, lab, prev, ["ghost"])
    elif case == "added":
        with pytest.raises(ValueError, match="extra"):
            xview_state_incremental(v, f, lab[:-1] + ["extra"], prev, [lab[-1]])
    else:
        drop = [k for k, x in enumerate(lab) if x != "p3"]
        with pytest.raises(ValueError, match="p3"):
            xview_state_incremental(v, [f[k] for k in drop], [lab[k] for k in drop], prev, [])


def test_incremental_reordered_unchanged_faces_is_an_error():
    v, f, lab, prev = _fixture()
    order = sorted(range(len(f)), key=lambda k: (lab[k], k))           # within-part order kept
    with pytest.raises(ValueError, match="order"):
        xview_state_incremental(v, [f[k] for k in order], [lab[k] for k in order], prev, [])


def test_incremental_vertex_sharing_change_between_unchanged_parts_is_an_error():
    v = np.array([(0, 0, 0), (1, 0, 0), (0, 1, 0), (-1, 0, 0), (-1, 1, 0), (0, 0, 0.0)])
    welded = [(0, 1, 2), (0, 4, 3)]
    split = [(0, 1, 2), (5, 4, 3)]
    prev = _rt(xview_state(v, welded, ["a", "b"]))
    assert prev["face_pairs"] == []
    with pytest.raises(ValueError, match="sharing"):
        xview_state_incremental(v, split, ["a", "b"], prev, [])
    full = xview_state(v, split, ["a", "b"])
    assert full["xview_faces"] == [1, 2]                                    # unwelded corner = xView contact
    assert _rt(xview_state_incremental(v, split, ["a", "b"], prev, ["b"])) == _rt(full)


@pytest.mark.parametrize("bad", [
    {}, {"name": "x", "version": 1}, "thresholds", "pair_range", "pair_kind", "runs"])
def test_incremental_bad_previous_is_an_error(bad):
    v, f, lab, prev = _fixture()
    if isinstance(bad, dict):
        prev = bad
    elif bad == "thresholds":
        prev["thresholds"]["face_m"] = 0.004
    elif bad == "pair_range":
        prev["face_pairs"] = [[1, len(f) + 5, "contact", 0.0]]
    elif bad == "pair_kind":
        prev["face_pairs"] = [[1, 2, "touch", 0.0]]
    else:
        prev["runs"] = prev["runs"][:-1]
    with pytest.raises(ValueError):
        xview_state_incremental(v, f, lab, prev, [])


@pytest.mark.parametrize("bad", ["nan", "inf", "empty", "labels_short", "label_empty", "label_int"])
def test_state_fail_closed_inputs(bad):
    v, f, lab = parts_of(3)
    if bad in ("nan", "inf"):
        v = v.copy()
        v[0, 0] = np.nan if bad == "nan" else np.inf
    elif bad == "empty":
        f, lab = [], []
    elif bad == "labels_short":
        lab = lab[:-1]
    elif bad == "label_empty":
        lab = [""] + lab[1:]
    else:
        lab = [3] + lab[1:]
    with pytest.raises(ValueError):
        xview_state(v, f, lab)


def test_state_matches_part_report():
    v, f, lab = parts_of(4)
    s = xview_state(v, f, lab)
    r = X.part_report("m", PolyMesh(v, tuple(f)), TOL)
    assert s["xview_faces"] == list(r.xview_faces) and s["faces"] == list(r.faces)
    assert [tuple(p) for p in s["face_pairs"]] == [tuple(p) for p in r.face_pairs]
    assert [tuple(p) for p in s["vertex_pairs"]] == [tuple(p) for p in r.vertex_pairs]


# ---- parity on the stored xView lists (local evidence, #514 / #370) ------------------------------------------------

TOW02 = Path(os.environ.get("AGR_TOW02_REVIEW",
                            "C:/Users/artsafro/.AGR-DigitalTwin_pilot/jobs/vyatskaya-tow02/outputs/review-v002"))
GROUND = Path(os.environ.get("AGR_GROUND_V014_DUMPS",
                             str(Path(os.environ.get("LOCALAPPDATA", "C:/nonexistent")) / "Temp/agr-max-t_3013550d")))
FIX = Path(__file__).resolve().parents[1] / "fixtures" / "xview"


def _npz_faces(path):
    z = np.load(path)
    lv = z["loop_vert"]
    return z["vertices"], [tuple(int(x) for x in lv[s:s + t]) for s, t in zip(z["loop_start"], z["loop_total"])]


@pytest.mark.skipif(not (TOW02 / "xview/ours_v005.keep").exists(), reason="TOW02 review-v002 evidence not on this PC")
def test_tow02_v005_fast_equals_xview_185_within_10_s():
    keep = json.loads((TOW02 / "xview/ours_v005.keep").read_text(encoding="cp1251"))
    v, f = _npz_faces(TOW02 / "xcheck/raw/arrays_ours.npz")
    t = time.perf_counter()
    r = X.mesh_report(v, f, "NPM")
    dt = time.perf_counter() - t
    xv = sorted(i[0] for i in keep["facesCheck"]["items"])
    stored = [int(x) for x in (FIX / "tow02_v005_xview_faces.txt").read_text().split()]
    assert r["xview_faces"] == xv == stored and len(xv) == 185
    assert r["vertex_pairs"] == 0 == keep["verticesCheck"]["count"]
    assert dt <= 10.0, f"inv_xview on TOW02 v005 took {dt:.1f} s"


@pytest.mark.skipif(not (TOW02 / "xcheck/raw/arrays_user_local.npz").exists(), reason="user 013 arrays not on this PC")
def test_tow02_user_013_fast_is_0_faces_10_vertices():
    v, f = _npz_faces(TOW02 / "xcheck/raw/arrays_user_local.npz")
    r = X.mesh_report(v, f, "NPM")
    assert r["xview_faces"] == [] and len(r["vertices"]) == 10


@pytest.mark.skipif(not (GROUND / "npm_xview.json").exists(), reason="Ground v014 xView dumps not on this PC")
def test_ground_v014_parity_146():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "qa"))
    import xview_parity
    rows = xview_parity.compare(json.loads((GROUND / "npm_xview.json").read_text(encoding="utf-8")))
    stored = [int(x) for x in (FIX / "ground_v014_npm_xview_faces.txt").read_text().split()]
    assert len(rows) == 1 and rows[0]["equal"] and rows[0]["max_faces"] == 146 == len(stored)


# ---- tools/qa/xview_parity.py --keep / --npz (#535) ----------------------------------------------------------------

def _parity():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "qa"))
    import xview_parity
    return xview_parity


def _keep_case(tmp_path, items=(1, 2), count=None, faces=None):
    """SYNTHETIC: two unwelded triangles touching at a corner (xView: faces 1, 2)."""
    v = np.array([(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 0), (-1, 0, 0), (-1, 1, 0.0)])
    np.savez(tmp_path / "a.npz", vertices=v, loop_start=np.array([0, 3]), loop_total=np.array([3, 3]),
             loop_vert=np.array([0, 1, 2, 3, 5, 4]))
    keep = {"node": "n", "faces": 2 if faces is None else faces, "verts": 6, "tolFaces": 0.005, "tolVerts": 0.002,
            "verticesCheck": {"count": 2, "items": [[1, 1], [4, 1]]},
            "facesCheck": {"count": len(items) if count is None else count, "items": [[i, 1] for i in items]}}
    (tmp_path / "k.keep").write_text(json.dumps(keep), encoding="cp1251")
    return ["--keep", str(tmp_path / "k.keep"), "--npz", str(tmp_path / "a.npz")]


def test_parity_keep_equal_exit_0(tmp_path):
    out = tmp_path / "p.json"
    assert _parity().main(_keep_case(tmp_path) + ["--out", str(out)]) == 0
    assert json.loads(out.read_text())[0]["equal"]


def test_parity_keep_differs_exit_1(tmp_path):
    assert _parity().main(_keep_case(tmp_path, items=(1,))) == 1


@pytest.mark.parametrize("case", ["partial", "other_mesh", "out_is_input", "no_npz", "id_range"])
def test_parity_keep_fail_closed_exit_2_writes_nothing(tmp_path, case):
    kw = {"partial": {"count": 3}, "other_mesh": {"faces": 3}, "id_range": {"items": (1, 9)}}.get(case, {})
    args = _keep_case(tmp_path, **kw)
    out = tmp_path / "p.json"
    if case == "out_is_input":
        args += ["--out", args[1]]
        before = Path(args[1]).read_bytes()
        assert _parity().main(args) == 2 and Path(args[1]).read_bytes() == before
        return
    if case == "no_npz":
        args = args[:2]
    assert _parity().main(args + ["--out", str(out)]) == 2 and not out.exists()


# ---- review round 1 (#554): incomplete previous state, malformed NPZ indices --------------------------------------

_CORNER_V = np.array([(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 0), (-1, 0, 0), (-1, 1, 0.0)])
_CORNER_F = [(0, 1, 2), (3, 5, 4)]                       # SYNTHETIC: unwelded corner touch, xView faces 1, 2


def _corner_prev():
    prev = _rt(xview_state(_CORNER_V, _CORNER_F, ["a", "b"]))
    assert prev["xview_faces"] == [1, 2]
    return prev


def test_incremental_intact_cache_and_changed_part_controls():
    prev = _corner_prev()
    full = _rt(xview_state(_CORNER_V, _CORNER_F, ["a", "b"]))
    assert _rt(xview_state_incremental(_CORNER_V, _CORNER_F, ["a", "b"], prev, [])) == full
    assert _rt(xview_state_incremental(_CORNER_V, _CORNER_F, ["a", "b"], prev, ["b"])) == full


@pytest.mark.parametrize("bad", [
    "pairs_missing", "pairs_empty", "pairs_empty_summaries_too", "pairs_dropped_row", "pairs_duplicated",
    "pairs_not_list", "pair_swapped", "pair_bool_id", "pair_nan_sep", "pair_short_row", "faces_summary",
    "xview_summary", "digest_missing", "parts_missing", "part_faces_bool", "part_hash_missing", "runs_counts",
    "links_missing", "vertex_pairs_missing"])
def test_incremental_incomplete_previous_is_an_error(bad):
    prev = _corner_prev()
    if bad == "pairs_missing":
        del prev["face_pairs"]
    elif bad == "pairs_empty":
        prev["face_pairs"] = []
    elif bad == "pairs_empty_summaries_too":                  # a consistent-looking truncation: only the digest sees it
        prev["face_pairs"], prev["faces"], prev["xview_faces"] = [], [], []
    elif bad == "pairs_dropped_row":
        prev["face_pairs"] = prev["face_pairs"][1:]
    elif bad == "pairs_duplicated":
        prev["face_pairs"] = prev["face_pairs"] * 2
    elif bad == "pairs_not_list":
        prev["face_pairs"] = {"1": 2}
    elif bad == "pair_swapped":
        prev["face_pairs"][0][:2] = prev["face_pairs"][0][1::-1]
    elif bad == "pair_bool_id":
        prev["face_pairs"][0][0] = True
    elif bad == "pair_nan_sep":
        prev["face_pairs"][0][3] = float("nan")
    elif bad == "pair_short_row":
        prev["face_pairs"][0] = prev["face_pairs"][0][:3]
    elif bad == "faces_summary":
        prev["faces"] = []
    elif bad == "xview_summary":
        prev["xview_faces"] = [1]
    elif bad == "digest_missing":
        del prev["face_pairs_sha256"]
    elif bad == "parts_missing":
        del prev["parts"]
    elif bad == "part_faces_bool":
        prev["parts"]["a"]["faces"] = True
    elif bad == "part_hash_missing":
        del prev["parts"]["a"]["hash"]
    elif bad == "runs_counts":                                # same total, wrong per-part counts
        prev["parts"]["a"]["faces"], prev["parts"]["b"]["faces"] = 2, 0
    elif bad == "links_missing":
        del prev["links"]
    else:
        del prev["vertex_pairs"]
    with pytest.raises(ValueError, match="previous"):
        xview_state_incremental(_CORNER_V, _CORNER_F, ["a", "b"], prev, [])


def _arrays(**kw):
    a = {"vertices": _CORNER_V, "loop_start": np.array([0, 3]), "loop_total": np.array([3, 3]),
         "loop_vert": np.array([0, 1, 2, 3, 5, 4])}
    a.update(kw)
    return a


_KEEP = {"node": "n", "faces": 2, "verts": 6, "tolFaces": 0.005, "tolVerts": 0.002,
         "verticesCheck": {"count": 2, "items": [[1, 1], [4, 1]]}, "facesCheck": {"count": 2, "items": [[1, 1], [2, 1]]}}

_BAD_ARRAYS = {
    "loop_vert_fractional": {"loop_vert": np.array([0, 1, 2, 3, 5, 4]) + 0.25},
    "loop_vert_float_integral": {"loop_vert": np.array([0, 1, 2, 3, 5, 4], dtype=float)},
    "loop_vert_bool": {"loop_vert": np.array([0, 1, 1, 0, 1, 1], dtype=bool)},
    "loop_vert_unused_suffix": {"loop_vert": np.array([0, 1, 2, 3, 5, 4, 999, 998, 997])},
    "loop_vert_out_of_range": {"loop_vert": np.array([0, 1, 2, 3, 5, 6])},
    "loop_vert_negative": {"loop_vert": np.array([0, 1, 2, 3, 5, -1])},
    "loop_vert_2d": {"loop_vert": np.array([[0, 1, 2], [3, 5, 4]])},
    "loop_start_overlap": {"loop_start": np.array([0, 2])},
    "loop_start_gap": {"loop_start": np.array([0, 4]), "loop_vert": np.array([0, 1, 2, 7, 3, 5, 4])},
    "loop_start_not_zero": {"loop_start": np.array([1, 4]), "loop_vert": np.array([9, 0, 1, 2, 3, 5, 4])},
    "loop_start_float": {"loop_start": np.array([0.0, 3.0])},
    "loop_total_fractional": {"loop_total": np.array([3.5, 3])},
    "loop_total_below_3": {"loop_start": np.array([0, 2]), "loop_total": np.array([2, 4])},
    "vertices_shape": {"vertices": _CORNER_V[:, :2]},
}


def test_parity_arrays_valid_control():
    rows = _parity().compare_keep(dict(_KEEP), _arrays())
    assert rows[0]["equal"]


@pytest.mark.parametrize("case", sorted(_BAD_ARRAYS))
def test_parity_malformed_arrays_are_a_dump_error_naming_the_array(case):
    P = _parity()
    with pytest.raises(P.DumpError, match="loop_|vertices"):
        P.compare_keep(dict(_KEEP), _arrays(**_BAD_ARRAYS[case]))


@pytest.mark.parametrize("case", ["loop_vert_fractional", "loop_vert_unused_suffix", "valid"])
def test_parity_cli_fresh_process_malformed_npz_exit_2_writes_nothing(tmp_path, case):
    import subprocess
    import sys
    np.savez(tmp_path / "a.npz", **_arrays(**_BAD_ARRAYS.get(case, {})))
    (tmp_path / "k.keep").write_text(json.dumps(_KEEP), encoding="cp1251")
    out = tmp_path / "p.json"
    tool = Path(__file__).resolve().parents[2] / "tools" / "qa" / "xview_parity.py"
    r = subprocess.run([sys.executable, str(tool), "--keep", str(tmp_path / "k.keep"), "--npz", str(tmp_path / "a.npz"),
                        "--out", str(out)], capture_output=True, text=True, timeout=120)
    if case == "valid":
        assert r.returncode == 0 and json.loads(out.read_text())[0]["equal"], r.stderr
    else:
        assert r.returncode == 2 and not out.exists() and "loop_" in r.stderr, (r.returncode, r.stderr)
