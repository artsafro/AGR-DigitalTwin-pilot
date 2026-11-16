"""#1540: UCX pair resolution - clip the smaller convex hull by a face plane of the larger one with a D098 gap.

Pattern: n/a | new-case: regression + generated probes for ucx10_core.resolve, ucx_build.hull_deviation and the
`agr ucx --resolve` chain (synthetic convex boxes, synthetic data; Blender steps mocked).
"""
import importlib.util
import itertools
import json
import math
import random
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

from dt_ai.geometry import ucx_build as ub
from dt_ai.geometry import ucx_command as uc
from twinqa.geometry import ucx_audit as ua

ROOT = Path(__file__).resolve().parents[1]
GAP = 0.003  # the retro's working gap, inside D098
BAD = {"intersect", "nested", "too_close"}


def _core():
    spec = importlib.util.spec_from_file_location("agr_ucx10_core_1540", ROOT / "adapters/max/agr_tools/ucx10_core.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


core = _core()


def box(x0, x1, y0, y1, z0, z1):
    v = [[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    t = [[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5], [0, 4, 5], [0, 5, 1],
         [2, 3, 7], [2, 7, 6], [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]]
    return v, t


def row(h, name, b):
    return {"handle": h, "name": name, "verts": b[0], "tris": b[1]}


def scene():
    """Two overlapping boxes + a thin parapet hull crossing a slab hull (synthetic), with the model they wrap."""
    ucx = [row(1, "UCX_SM_T_Main_001", box(10, 11, 0, 1, 0, 1)),            # box A (larger)
           row(2, "UCX_SM_T_Main_002", box(10.9, 11.4, 0.2, 0.8, 0.1, 0.9)),  # box B overlaps A by 0.1 m
           row(3, "UCX_SM_T_Main_003", box(-0.02, 6.02, -0.02, 6.02, -0.02, 0.22)),  # slab hull
           row(4, "UCX_SM_T_Main_004", box(-0.02, 0.17, -0.02, 6.02, 0.10, 1.22))]   # parapet crosses the slab top
    model = [box(10.02, 10.98, 0.02, 0.98, 0.02, 0.98), box(11.0, 11.38, 0.22, 0.78, 0.12, 0.88),
             box(0, 6, 0, 6, 0, 0.2), box(0, 0.15, 0, 6, 0.2, 1.2)]
    return ucx, model


def arrays(boxes):
    vs, ts, off = [], [], 0
    for v, t in boxes:
        vs.append(np.asarray(v, float))
        ts.append(np.asarray(t) + off)
        off += len(v)
    return np.concatenate(vs), np.concatenate(ts)


def hulls(rows):
    return [{"name": r["name"], "verts": r["verts"], "tris": r["tris"]} for r in rows]


def after_rows(res):
    return [{"handle": h, "name": p["name"], "verts": p["verts"], "tris": p["tris"]} for h, p in res["pieces"].items()]


def kinds(rows):
    return {f["type"] for f in ua.collision_findings(hulls(rows))}


# --- the issue's regression -------------------------------------------------------------------------------------
def test_regression_boxes_and_parapet_over_slab():
    ucx, model = scene()
    assert "intersect" in kinds(ucx)  # before: intersections reported
    res = core.resolve(ucx, core.gap_options({"gap_m": GAP}))
    assert res["summary"]["ok"] is True, res["summary"]
    out = after_rows(res)
    # every hull closed and convex
    for r in out:
        c = ua.classify(r["verts"], r["tris"])
        assert c["closed"] is True and c["convex"] is True, (r["name"], c)
    # no pair intersects, no gap < 0.2 mm [D162]
    assert not kinds(out) & BAD
    # every resolved pair: plane + volume removed, gap inside D098
    resolved = [p for p in res["pairs"] if p["action"] == "clip"]
    assert {(p["clipped"], p["by"]) for p in resolved} == {("UCX_SM_T_Main_002", "UCX_SM_T_Main_001"),
                                                          ("UCX_SM_T_Main_004", "UCX_SM_T_Main_003")}
    for p in resolved:
        assert p["gap_before_m"] < 0 and 0.002 <= p["gap_after_m"] <= 0.010
        assert abs(p["gap_after_m"] - GAP) < 1e-6
        assert len(p["plane"]["normal"]) == 3 and math.isfinite(p["plane"]["offset_m"])
        assert p["volume_removed_m3"] > 0
        assert abs(p["volume_removed_m3"] - (p["volume_before_m3"] - p["volume_after_m3"])) < 1e-9
    par = next(p for p in resolved if p["clipped"] == "UCX_SM_T_Main_004")
    assert par["plane"]["normal"] == [0.0, 0.0, 1.0] and abs(par["plane"]["offset_m"] - 0.223) < 1e-9
    assert abs(par["volume_removed_m3"] - 0.19 * 6.04 * 0.123) < 1e-6
    # the larger hulls are never touched
    assert not res["pieces"][1]["changed"] and not res["pieces"][3]["changed"]
    # UCX poly count within D012
    mv, mt = arrays(model)
    tris = sum(len(r["tris"]) for r in out)
    assert tris == res["summary"]["triangles_after"] and tris <= ub.ucx_triangle_limit(len(mt))
    # model -> UCX within D134 (pedestrian-reachable OKS 30 cm, the strictest OKS limit)
    pts = ub.sample_surface(mv, mt, 0.05)
    assert float(ub.hull_deviation(pts, [(r["verts"], r["tris"]) for r in out]).max()) <= 0.30


def test_report_pairs_are_named_and_counted():
    ucx, _ = scene()
    res = core.resolve(ucx, core.gap_options({"gap_m": GAP}))
    s = res["summary"]
    assert s["pairs_resolved"] == 2 and s["pairs_ambiguous"] == 0 and s["left"] == []
    assert s["pieces"] == 4 and s["pieces_changed"] == 2 and s["gap_m"] == GAP
    assert s["volume_removed_m3"] == pytest.approx(sum(p["volume_removed_m3"] for p in res["pairs"]))


# --- probes: generated pairs ------------------------------------------------------------------------------------
def _random_scene(rng, n):
    rows = []
    for i in range(n):
        x, y, z = rng.uniform(0, 3), rng.uniform(0, 3), rng.uniform(0, 1)
        sx, sy, sz = rng.uniform(0.3, 1.5), rng.uniform(0.3, 1.5), rng.uniform(0.3, 1.0)
        rows.append(row(i, "UCX_SM_R_Main_{:03d}".format(i + 1), box(x, x + sx, y, y + sy, z, z + sz)))
    return rows


@pytest.mark.parametrize("seed", range(40))
def test_probe_generated_scenes_invariants(seed):
    rng = random.Random(seed)
    gap = rng.choice([0.002, 0.003, 0.004, 0.006, 0.010])
    rows = _random_scene(rng, rng.randint(2, 6))
    res = core.resolve(rows, core.gap_options({"gap_m": gap}))
    out = after_rows(res)
    before = {r["handle"]: r for r in rows}
    ambiguous = {(p["a"], p["b"]) for p in res["pairs"] if p["action"] == "ambiguous"}
    for r in out:
        c = ua.classify(r["verts"], r["tris"])
        assert c["closed"] and c["convex"]
        # a piece only ever shrinks: every new vertex lies inside its original hull
        b = before[r["handle"]]
        assert all(ua.inside_convex(v, b["verts"], b["tris"], tol=1e-7) for v in r["verts"])
    pieces = {r["name"]: core.piece(r["verts"], r["tris"]) for r in out}
    for a, b in itertools.combinations(sorted(pieces), 2):
        if (a, b) in ambiguous:
            continue
        assert core.separation(pieces[a], pieces[b])[0] >= gap - core.TOL_M, (seed, a, b)
    assert res["summary"]["ok"] is (not ambiguous and not res["summary"]["left"])
    # repeat: a resolved set is a fixed point
    again = core.resolve(out, core.gap_options({"gap_m": gap}))
    if res["summary"]["ok"]:
        assert again["summary"]["pairs_resolved"] == 0 and not any(p["changed"] for p in again["pieces"].values())


# --- real float32 pair from elv-tc-vpm v007 (UCX_..._Main_091 / _366): open hull before the cap cleanup ----------
V091 = [[43.410003662109375, 7.122529029846191, 14.039998054504395], [43.410003662109375, 24.34326934814453, 14.039992332458496],
        [43.410003662109375, 7.122528553009033, 12.509793281555176], [43.410003662109375, 24.34326934814453, 12.509787559509277],
        [43.95001220703125, 7.111025810241699, 14.039998054504395], [43.93000030517578, 24.363666534423828, 14.039992332458496],
        [43.95001220703125, 7.111025333404541, 12.509793281555176], [43.93000030517578, 24.363666534423828, 12.509787559509277]]
T091 = [[3, 2, 0], [0, 1, 3], [4, 6, 7], [7, 5, 4], [1, 0, 4], [4, 5, 1], [7, 6, 2], [2, 3, 7], [0, 2, 6], [6, 4, 0],
        [3, 1, 5], [5, 7, 3]]
V366 = [[44.37000274658203, 7.4569315910339355, 4.699997425079346], [44.37000274658203, 7.506930828094482, 4.699997425079346],
        [44.37000274658203, 7.506933689117432, 13.89999771118164], [44.37000274658203, 7.456934452056885, 13.89999771118164],
        [43.93596649169922, 7.4569315910339355, 4.699997425079346], [43.93596649169922, 7.456934452056885, 13.89999771118164],
        [43.93596649169922, 7.506930828094482, 4.699997425079346], [43.93596649169922, 7.506933689117432, 13.89999771118164]]
T366 = [[0, 1, 2], [2, 3, 0], [4, 0, 3], [3, 5, 4], [7, 2, 1], [1, 6, 7], [7, 5, 3], [3, 2, 7], [1, 0, 4], [4, 6, 1],
        [7, 6, 4], [4, 5, 7]]


def test_real_float32_pair_is_resolved_not_ambiguous():
    rows = [row(1, "UCX_SM_Elevatornaya_Vl_1_A_Main_091", (V091, T091)),
            row(2, "UCX_SM_Elevatornaya_Vl_1_A_Main_366", (V366, T366))]
    assert "intersect" in kinds(rows)
    res = core.resolve(rows, core.gap_options({"gap_m": GAP}))
    assert res["summary"]["ok"] is True and res["summary"]["pairs_resolved"] == 1, res["pairs"]
    cut = res["pieces"][2]
    c = ua.classify(cut["verts"], cut["tris"])
    assert c["closed"] and c["convex"] and not kinds(after_rows(res)) & BAD
    assert 0 < res["pairs"][0]["volume_removed_m3"] < 0.01


V064 = [[43.410003662109375, -6.109167098999023, 14.04000186920166], [43.410003662109375, -6.109167575836182, 12.509797096252441],
        [43.95000457763672, -6.097663879394531, 14.04000186920166], [43.95000457763672, -6.0976643562316895, 12.509797096252441],
        [43.30967712402344, -5.3886613845825195, 14.04000186920166], [43.30967712402344, -5.388661861419678, 12.509797096252441],
        [43.829376220703125, -5.23936128616333, 12.509797096252441], [43.829376220703125, -5.239360809326172, 14.04000186920166]]
T064 = [[4, 5, 1], [1, 0, 4], [7, 2, 3], [3, 6, 7], [2, 7, 4], [4, 0, 2], [5, 6, 3], [3, 1, 5], [3, 2, 0], [0, 1, 3],
        [7, 6, 5], [5, 4, 7]]
V337 = [[44.2384033203125, -5.144669055938721, 4.700001239776611], [44.2384033203125, -5.1446661949157715, 13.900001525878906],
        [44.224098205566406, -5.09476900100708, 4.700001239776611], [44.224098205566406, -5.094766139984131, 13.900001525878906],
        [43.82121276855469, -5.264441967010498, 4.700001239776611], [43.82121276855469, -5.264439105987549, 13.900001525878906],
        [43.806915283203125, -5.2146430015563965, 4.700001239776611], [43.806915283203125, -5.214640140533447, 13.900001525878906]]
T337 = [[2, 3, 1], [1, 0, 2], [4, 0, 1], [1, 5, 4], [7, 3, 2], [2, 6, 7], [1, 3, 7], [7, 5, 1], [4, 6, 2], [2, 0, 4],
        [7, 6, 4], [4, 5, 7]]


def test_real_cut_piece_stays_convex_after_float32_round_trip():
    """v007 _064/_337: the cut piece was convex in float64 but read back non-convex (worst 0.104 mm) from the FBX:
    cap points 0.34 mm off a cap edge made sliver triangles. Cap corners within 1 mm are dropped (piece only
    shrinks) and a cut that is not convex after a float32 round trip is never chosen."""
    rows = [row(1, "UCX_SM_Elevatornaya_Vl_1_A_Main_064", (V064, T064)),
            row(2, "UCX_SM_Elevatornaya_Vl_1_A_Main_337", (V337, T337))]
    res = core.resolve(rows, core.gap_options({"gap_m": GAP}))
    assert res["summary"]["ok"] is True and res["summary"]["pairs_resolved"] == 1
    cut = res["pieces"][2]
    hull = core._hull_core()
    assert hull.convexity(core._float32(cut["verts"]), cut["tris"])["ok"]
    assert all(ua.inside_convex(v, V337, T337, tol=1e-7) for v in cut["verts"])  # only shrinks
    f32 = [{"name": r["name"], "verts": core._float32(r["verts"]), "tris": r["tris"]} for r in after_rows(res)]
    assert not kinds(f32) & BAD


# --- fail-closed probes -----------------------------------------------------------------------------------------
def test_empty_scope_is_an_error():
    with pytest.raises(ValueError):
        core.resolve([], core.gap_options({"gap_m": GAP}))


@pytest.mark.parametrize("gap", [0.0019, 0.0101, float("nan"), float("inf"), True])
def test_gap_outside_d098_is_refused(gap):
    with pytest.raises(ValueError):
        core.gap_options({"gap_m": gap})


def test_duplicate_handle_is_an_error():
    ucx, _ = scene()
    with pytest.raises(ValueError):
        core.resolve([ucx[0], dict(ucx[1], handle=1)], core.gap_options({"gap_m": GAP}))


def test_nested_piece_is_ambiguous_never_cut_and_not_ok():
    rows = [row(1, "UCX_SM_T_Main_001", box(0, 2, 0, 2, 0, 2)), row(2, "UCX_SM_T_Main_002", box(0.5, 1, 0.5, 1, 0.5, 1))]
    res = core.resolve(rows, core.gap_options({"gap_m": GAP}))
    assert res["summary"]["ok"] is False and res["summary"]["pairs_ambiguous"] == 1
    assert not any(p["changed"] for p in res["pieces"].values())
    assert res["findings"][2][0][0] == "ucx_unresolved"


def test_exactly_at_gap_is_unchanged_and_just_below_is_resolved():
    at = [row(1, "UCX_SM_T_Main_001", box(0, 1, 0, 1, 0, 1)), row(2, "UCX_SM_T_Main_002", box(1 + GAP, 2, 0, 1, 0, 1))]
    res = core.resolve(at, core.gap_options({"gap_m": GAP}))
    assert res["summary"]["ok"] and res["summary"]["pairs_resolved"] == 0
    below = [at[0], row(2, "UCX_SM_T_Main_002", box(1 + GAP - 0.0001, 2, 0, 1, 0, 1))]
    res = core.resolve(below, core.gap_options({"gap_m": GAP}))
    assert res["summary"]["pairs_resolved"] == 1
    assert res["pairs"][0]["gap_after_m"] == pytest.approx(GAP, abs=1e-7)


def test_non_convex_nan_and_bad_name_are_reported_never_dropped():
    ucx, _ = scene()
    v, t = box(0, 1, 0, 1, 0, 1)
    nan = [list(p) for p in v]
    nan[0][0] = float("nan")
    rows = [ucx[0], ucx[1], row(7, "UCX_SM_T_Main_007", (nan, t)), row(8, "SM_T_Main", box(5, 6, 5, 6, 5, 6)),
            row(9, "UCX_SM_T_Main_009", (v, t[:-1]))]
    res = core.resolve(rows, core.gap_options({"gap_m": GAP}))
    assert res["summary"]["ok"] is False
    assert {s["item"] for s in res["skipped"]} == {"SM_T_Main"}
    assert {h for h in res["findings"] if res["findings"][h][0][0] == "ucx_not_convex"} == {7, 9}
    # every input ends in pieces, skipped or findings
    assert set(res["pieces"]) | {8} | {7, 9} == {1, 2, 7, 8, 9}


def test_input_rows_are_not_modified():
    ucx, _ = scene()
    snap = json.dumps(ucx)
    core.resolve(ucx, core.gap_options({"gap_m": GAP}))
    assert json.dumps(ucx) == snap


# --- hull_deviation (model -> UCX, D134) ------------------------------------------------------------------------
def test_hull_deviation_exact_against_brute_force():
    rng = np.random.default_rng(3)
    hs = [box(0, 1, 0, 1, 0, 1), box(2, 3, 0, 1, 0, 1)]
    pts = rng.uniform(-1, 4, size=(300, 3))
    got = ub.hull_deviation(pts, hs)
    for p, d in zip(pts, got):
        want = min(0.0 if ua.inside_convex(p, v, t) else
                   min(ua.point_triangle_distance(p, v[a], v[b], v[c]) for a, b, c in t) for v, t in hs)
        assert abs(d - want) < 1e-9


@pytest.mark.parametrize("bad", [[], [([], [])], [([[0, 0, float("nan")]], [[0, 0, 0]])]])
def test_hull_deviation_fail_closed(bad):
    with pytest.raises(ub.UcxBuildError):
        ub.hull_deviation(np.zeros((2, 3)), bad)


# --- agr ucx --resolve ------------------------------------------------------------------------------------------
@pytest.fixture
def model(tmp_path):
    p = tmp_path / "SM_T_Main.fbx"
    p.write_bytes(b"synthetic model")
    return p


def test_parse_resolve_flag_and_ground_refused(model, tmp_path):
    a = uc.parse([str(model), str(tmp_path / "o.fbx"), "Main", "--resolve"])
    assert a["resolve"] is True and a["build_report"].name == "o.fbx.ucx_resolve.json"
    with pytest.raises(uc.Refused):
        uc.parse([str(model), str(tmp_path / "o.fbx"), "Ground", "--resolve"])
    with pytest.raises(uc.Refused):
        uc.parse([str(model), str(tmp_path / "o.fbx"), "Main", "--resolve", "--resolve"])
    with pytest.raises(uc.Refused):
        uc.parse([str(model), str(tmp_path / "o.fbx"), "Main", "--resolve", "cell=0.25"])


def _resolved_rb():
    ucx, _ = scene()
    res = core.resolve(ucx, core.gap_options({"gap_m": GAP}))
    return {"readback_ok": True, "meshes": [{"name": "SM_T_Main"}] + [
        {"name": p["name"], "hull": {"verts": p["verts"], "tris": p["tris"]}} for p in res["pieces"].values()]}


RESOLVE_OK = {"ok": True, "gap_m": GAP, "pairs_resolved": 2, "pairs_ambiguous": 0, "left": [],
              "ucx_triangles": 48, "file_ucx_limit_D012": 15000, "model_to_ucx_max_m": 0.02,
              "model_to_ucx_limit_m": 1.0, "within_D012": True, "within_D134": True}


@pytest.mark.parametrize("patch,code", [({}, 0), ({"within_D134": False}, 1), ({"within_D012": False}, 1),
                                        ({"pairs_ambiguous": 1}, 1), ({"left": [{"a": "x"}]}, 1)])
def test_resolve_chain(patch, code, model, tmp_path, monkeypatch):
    from dt_ai.core import blender_runner as br
    from twinqa import scene as sc

    run = Mock(return_value=dict(RESOLVE_OK, **patch))
    monkeypatch.setattr(br, "run_blender", run)
    monkeypatch.setattr(sc, "readback", Mock(return_value=_resolved_rb()))
    monkeypatch.setattr(uc, "_v010", Mock(return_value=[{"name": "x", "status": "pass"}]))
    a = uc.parse([str(model), str(tmp_path / "o.fbx"), "Main", "--resolve"])
    got, report = uc.run(a)
    assert got == code, report
    assert run.call_args[0][0] == uc.RESOLVE_DRIVER
    assert run.call_args[0][1] == [str(model), str(tmp_path / "o.fbx"), f"gap={GAP}"]
    assert "build" not in report["steps"] and report["steps"]["resolve"]["pairs_resolved"] == 2
    assert report["steps"]["gap_check"]["ok"] is True


def test_resolve_driver_failure_is_exit_2(model, tmp_path, monkeypatch):
    from dt_ai.core import blender_runner as br

    def boom(*a, **k):
        raise br.BlenderRunError({"returncode": 2, "message": "import failed"})

    monkeypatch.setattr(br, "run_blender", boom)
    a = uc.parse([str(model), str(tmp_path / "o.fbx"), "Main", "--resolve"])
    code, report = uc.run(a)
    assert code == 2 and report["steps"]["resolve"]["ok"] is False


def test_resolve_driver_is_a_real_file():
    assert uc.RESOLVE_DRIVER.is_file()
