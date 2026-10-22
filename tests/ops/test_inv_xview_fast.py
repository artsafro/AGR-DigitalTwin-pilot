"""inv_xview_fast (#553): exact parity with the inv_xview contact rule (xView selection), fail-closed input, bench."""
import importlib.util
import itertools
import os
from pathlib import Path

import numpy as np
import pytest

from dt_ai.ops.inv_quads import PolyMesh
from dt_ai.ops.inv_xview import FACE_M, VERTEX_M, XviewTolerance, part_report
from dt_ai.ops.inv_xview_fast import xview_lists

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("xview_bench", ROOT / "tools" / "qa" / "xview_bench.py")
bench = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bench)


def baseline(v, f, tol=None):
    r = part_report("p", PolyMesh(np.asarray(v, float), tuple(tuple(x) for x in f)), tol or XviewTolerance())
    return tuple((i, j) for i, j, k, _ in r.face_pairs if "contact" in k), r.vertex_pairs, r.xview_faces, r.vertices


def assert_parity(v, f, tol=None):
    pairs, vp, xf, vs = baseline(v, f, tol)
    x = xview_lists(np.asarray(v, float), tuple(tuple(t) for t in f), tol)
    assert x["face_pairs"] == pairs
    assert x["vertex_pairs"] == vp
    assert (x["xview_faces"], x["vertices"]) == (xf, vs)
    return x


# ---- the bench's hand-derived edge cases (validation.md) -------------------------------------------------------------

@pytest.mark.parametrize("case", bench.synthetic(), ids=lambda c: c[0])
def test_edge_cases_match_hand_derived_lists_and_baseline(case):
    name, v, f, of, ov, tol = case
    x = assert_parity(v, f, tol)
    assert (x["xview_faces"], x["vertices"]) == (of, ov)


def test_thresholds_are_the_d152_constants():
    assert (VERTEX_M, FACE_M, XviewTolerance().parallel_cos_min) == (0.002, 0.005, 0.9999)


# ---- polygon classes: concave quad, n-gon, mixed, zero-area triangle ------------------------------------------------

def test_concave_quad_and_ngon_go_through_the_baseline_triangulation():
    # concave quad (dart) whose fan from vertex 0 would cover area outside it, a pentagon, a coplanar offset quad
    v = [(0, 0, 0), (2, 0, 0), (1, 0.5, 0), (0, 2, 0),                     # dart, reflex at 2
         (3, 0, 0), (4, 0, 0), (4.5, 1, 0), (3.5, 1.8, 0), (2.8, 1, 0),     # pentagon
         (1.0, 0.25, 0.003), (1.5, 0.25, 0.003), (1.5, 0.4, 0.003), (1.0, 0.4, 0.003),
         (3.5, 0.5, 0.004), (3.9, 0.5, 0.004), (3.9, 0.9, 0.004)]
    f = [(0, 1, 2, 3), (4, 5, 6, 7, 8), (9, 10, 11, 12), (13, 14, 15)]
    assert_parity(v, f)


def test_zero_area_triangle_takes_no_part_in_faces():
    v = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0.2, 0.2, 0.001), (0.4, 0.2, 0.001), (0.6, 0.2, 0.001)]
    x = assert_parity(v, [(0, 1, 2), (3, 4, 5)])
    assert x["xview_faces"] == ()


def test_shared_edge_coplanar_grid_is_clean():
    v = [(x, y, 0.0) for y in range(4) for x in range(4)]
    f = [(y * 4 + x, y * 4 + x + 1, y * 4 + x + 5, y * 4 + x + 4) for y in range(3) for x in range(3)]
    x = assert_parity(v, f)
    assert x["xview_faces"] == () and x["vertices"] == ()


def test_self_intersecting_polygon_is_an_error_like_the_baseline():
    v, f = [(0, 0, 0), (1, 1, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2, 3)]
    with pytest.raises(ValueError, match="self-intersecting"):
        baseline(v, f)
    with pytest.raises(ValueError, match="self-intersecting"):
        xview_lists(np.asarray(v, float), f)


# ---- generated parity probe: random near-parallel stacks around every threshold ------------------------------------

def _scene(rng):
    """A few quads / triangles / concave quads on near-parallel planes; offsets and tilts sit on the thresholds."""
    v, f = [], []
    grid = np.arange(0, 2.01, 0.25)                                      # exact binary fractions: exact contacts
    offsets = [0.0, 0.001, 0.002, 0.004, 0.005, 0.0051, 0.01]
    tilts = [0.0, 0.5, 0.80, 0.81, 0.815, 1.0]
    for _ in range(rng.integers(2, 6)):
        kind = rng.choice(["quad", "tri", "dart"])
        x0, y0 = rng.choice(grid[:-2], 2)
        w, h = rng.choice(grid[1:5], 2)
        z = rng.choice(offsets) * rng.choice([1, -1])
        t = np.tan(np.radians(rng.choice(tilts))) * rng.choice([1, -1])
        if kind == "quad":
            pts = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
        elif kind == "tri":
            pts = [(x0, y0), (x0 + w, y0), (x0, y0 + h)]
        else:
            pts = [(x0, y0), (x0 + w, y0), (x0 + w / 2, y0 + h / 4), (x0, y0 + h)]
        if rng.random() < 0.5:
            pts = pts[::-1]
        base = len(v)
        v += [(px, py, z + t * (px - x0)) for px, py in pts]
        f.append(tuple(range(base, base + len(pts))))
    if rng.random() < 0.3:                                               # split vertex 0..2 mm away (vertex list)
        k = int(rng.integers(len(v)))
        v.append(tuple(np.add(v[k], (rng.choice([0.0, 0.001, 0.002, 0.0021]), 0, 0))))
        f.append((len(v) - 1, int(rng.integers(len(v) - 1)), int(rng.integers(len(v) - 1))))
        if len(set(f[-1])) < 3:
            f.pop()
    return v, f


def test_generated_scenes_match_the_baseline_pair_for_pair():
    rng = np.random.default_rng(553)
    checked = flagged = 0
    for _ in range(300):
        v, f = _scene(rng)
        try:
            pairs = baseline(v, f)
        except ValueError:                                               # unsupported polygon: both must refuse
            with pytest.raises(ValueError):
                xview_lists(np.asarray(v, float), f)
            continue
        x = xview_lists(np.asarray(v, float), tuple(f))
        assert (x["face_pairs"], x["vertex_pairs"]) == pairs[:2], (v, f)
        checked += 1
        flagged += bool(pairs[0])
    assert checked >= 250 and flagged >= 50                              # the probe really exercises both outcomes


# ---- fail-closed input ---------------------------------------------------------------------------------------------

V3 = np.array([(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)], float)


@pytest.mark.parametrize("faces,match", [
    (((0, 1, True),), "not an integer"),
    (((0, 1, 2.0),), "not an integer"),
    (((0, 1, 9),), "outside"),
    (((0, 1, -1),), "outside"),
    (((0, 1, 1),), "repeated"),
    (((0, 1),), "fewer than 3"),
    ((), "no faces"),
])
def test_bad_faces_raise(faces, match):
    with pytest.raises(ValueError, match=match):
        xview_lists(V3, faces)


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_non_finite_vertices_raise(bad):
    v = V3.copy()
    v[1, 2] = bad
    with pytest.raises(ValueError, match="finite"):
        xview_lists(v, ((0, 1, 2),))


@pytest.mark.parametrize("tol", [XviewTolerance(face_m=np.nan), XviewTolerance(vertex_m=-1.0),
                                 XviewTolerance(parallel_cos_min=0.0)])
def test_bad_thresholds_raise(tol):
    with pytest.raises(ValueError):
        xview_lists(V3, ((0, 1, 2),), tol)


def test_numpy_integer_indices_are_accepted():
    x = xview_lists(V3, ((np.int64(0), np.int32(1), 2),))
    assert x["xview_faces"] == ()


# ---- the frozen bench ------------------------------------------------------------------------------------------------

def test_bench_missing_data_exits_2(tmp_path, capsys):
    assert bench.main(["--candidate", "baseline", "--data", str(tmp_path), "--ground", str(tmp_path)]) == 2
    assert "missing input" in capsys.readouterr().err


def test_bench_check_rejects_any_difference():
    good = {"xview_faces": (1, 2), "vertices": (3, 4), "vertex_pairs": ((3, 4, 0.0),)}
    assert bench.check(good, (1, 2), (3, 4))["equal"]
    for bad in ({**good, "xview_faces": (1,)}, {**good, "vertices": (3,)}, {**good, "vertex_pairs": ()}):
        assert not bench.check(bad, (1, 2), (3, 4))["equal"]


def test_bench_reps_must_be_positive():
    assert bench.main(["--candidate", "baseline", "--reps", "0"]) == 2


def test_cartesian_threshold_grid_matches_baseline():
    """Brute force over offset x tilt x flip on the face rule's boundaries (guarantee: same list as the baseline)."""
    for dz, th, flip in itertools.product([0.0049, 0.005, 0.0051], [0.0, 0.81, 0.815], [False, True]):
        t = np.tan(np.radians(th)) * 2.5
        v = [(0, 0, 0), (4, 0, 0), (4, 4, 0), (0, 4, 0), (0.5, 0.5, dz), (3, 0.5, dz + t), (3, 1.5, dz + t)]
        assert_parity(v, [(0, 1, 2, 3), (4, 6, 5) if flip else (4, 5, 6)])


def test_random_t_vertices_on_edges_are_boundary_contacts_like_the_baseline():
    """A vertex on another triangle's edge (float coordinates, rounding either side) is counted: the 1e-12 slack."""
    rng = np.random.default_rng(5530)
    for _ in range(200):
        a, b, c = rng.random((3, 3))
        e = (a, b, c, a)[int(rng.integers(3)):][:2]                       # edge ab, bc or ca
        p = e[0] + rng.random() * (e[1] - e[0])
        n = np.cross(b - a, c - a)
        n /= np.linalg.norm(n)
        u = np.cross(n, [1.0, 0, 0])
        u /= np.linalg.norm(u)
        v = np.array([a, b, c, p, p + 0.3 * u, p + 0.3 * np.cross(n, u)])
        x = assert_parity(v, ((0, 1, 2), (3, 4, 5)))
        assert x["xview_faces"] == (1, 2)


@pytest.fixture
def fake_bench(tmp_path, monkeypatch):
    """The bench on the synthetic cases only (the real fixtures are local data), with one fake input file."""
    inp = tmp_path / "oracle.keep"
    inp.write_text("oracle", encoding="utf-8")
    cases = bench.synthetic()
    cases = [("tow02_v005", *cases[0][1:])] + cases[1:]
    monkeypatch.setattr(bench, "fixtures", lambda data, ground: (cases, [inp]))
    monkeypatch.syspath_prepend(str(tmp_path))
    return tmp_path, inp


def test_bench_synthetic_run_passes_and_writes_out(fake_bench):
    tmp, _ = fake_bench
    assert bench.main(["--candidate", "dt_ai.ops.inv_xview_fast", "--reps", "1", "--out", str(tmp / "r.json")]) == 0
    assert '"parity": true' in (tmp / "r.json").read_text(encoding="utf-8")


@pytest.mark.parametrize("alias", ["same", "hardlink", "bench"])
def test_bench_out_that_is_an_input_exits_2_and_writes_nothing(fake_bench, alias):
    tmp, inp = fake_bench
    out = {"same": inp, "bench": Path(bench.__file__)}.get(alias)
    if alias == "hardlink":
        out = tmp / "link.keep"
        os.link(inp, out)
    before = Path(out).read_bytes()
    assert bench.main(["--candidate", "baseline", "--reps", "1", "--out", str(out)]) == 2
    assert Path(out).read_bytes() == before


def test_bench_crashing_candidate_is_a_failure(fake_bench):
    tmp, _ = fake_bench
    (tmp / "crash_cand.py").write_text("def xview_lists(v, f, tol):\n    raise RuntimeError('boom')\n")
    assert bench.main(["--candidate", "crash_cand", "--reps", "1"]) == 1


def test_bench_wrong_candidate_is_a_failure(fake_bench):
    tmp, _ = fake_bench
    (tmp / "empty_cand.py").write_text(
        "def xview_lists(v, f, tol):\n    return {'xview_faces': (), 'vertices': (), 'vertex_pairs': ()}\n")
    assert bench.main(["--candidate", "empty_cand", "--reps", "1"]) == 1


def test_bench_input_changed_during_the_run_exits_2(fake_bench):
    tmp, inp = fake_bench
    (tmp / "mut_cand.py").write_text(
        "from pathlib import Path\nfrom dt_ai.ops.inv_xview_fast import xview_lists as f0\n"
        f"def xview_lists(v, f, tol):\n    Path({str(inp)!r}).write_text('changed')\n    return f0(v, f, tol)\n")
    assert bench.main(["--candidate", "mut_cand", "--reps", "1"]) == 2
