"""#1607 [D339]: `agr ucx` measures EVERY pair of UCX pieces and reports the gap bands; it refuses nothing by gap size.

Pattern: n/a | new-case: gap-band census tests on synthetic boxes (synthetic data) and on read-back UCX hulls of the
etalons KPP1 / Skolkovo / Mashi (real files, sha-pinned, outside git; skipped when absent).
"""
import hashlib
import itertools
import json
import math
import random
from pathlib import Path

import pytest

from dt_ai.geometry import ucx_command as uc



def box(x0, x1, y0=0.0, y1=1.0, z0=0.0, z1=1.0):
    v = [[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    t = [[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5], [0, 4, 5], [0, 5, 1],
         [2, 3, 7], [2, 7, 6], [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]]
    return {"verts": v, "tris": t}


def mesh(name, hull):
    return {"name": name, "hull": hull}


def two(gap, fam_b="SM_T_Main"):
    return [mesh("UCX_SM_T_Main_001", box(0, 1)), mesh(f"UCX_{fam_b}_002", box(1 + gap, 2 + gap))]


def band_of(g):
    if g < -1e-5:
        return "overlap"
    if g < 0.002 - 1e-5:
        return "lt_2mm"
    if g <= 0.010 + 1e-5:
        return "2_10mm"
    if g <= 0.100 + 1e-5:
        return "10_100mm"
    if g <= 1.0 + 1e-5:
        return "100mm_1m"
    return "gt_1m"


# --- RED on origin/main: a 0.5 m gap passed silently, nothing measured it ---------------------------------------
def test_half_metre_gap_is_measured_and_reported_not_refused():
    res = uc.gap_check(two(0.5), 0.004)
    assert res["ok"] is True  # observe week [D339]: no refusal by gap size
    bands = res["gap_bands"]
    assert bands["same_family"]["100mm_1m"] == 1
    assert sum(bands["same_family"].values()) == 1 and sum(bands["cross_family"].values()) == 0
    [pair] = res["gap_pairs"]
    assert (pair["a"], pair["b"], pair["scope"], pair["band"]) == (
        "UCX_SM_T_Main_001", "UCX_SM_T_Main_002", "same_family", "100mm_1m")
    assert pair["gap_m"] == pytest.approx(0.5)


@pytest.mark.parametrize("gap,band", [(-0.05, "overlap"), (-0.005, "overlap"), (0.0, "lt_2mm"), (0.001, "lt_2mm"),
                                      (0.002, "2_10mm"), (0.004, "2_10mm"), (0.010, "2_10mm"),
                                      (0.0101, "10_100mm"), (0.05, "10_100mm"), (0.1, "10_100mm"),
                                      (0.1001, "100mm_1m"), (0.5, "100mm_1m"), (1.0, "100mm_1m"),
                                      (1.0001, "gt_1m"), (3.0, "gt_1m")])
def test_band_per_gap_and_no_refusal_by_size(gap, band):
    res = uc.gap_check(two(gap), 0.002)
    assert res["gap_bands"]["same_family"][band] == 1
    assert sum(res["gap_bands"]["same_family"].values()) == 1
    # overlap / under-gap handling is unchanged: only a pair under gap_m fails
    assert res["ok"] is (gap >= 0.002 - 1e-5)
    assert bool(res["pairs_under_gap"]) is (gap < 0.002 - 1e-5)
    listed = [p["band"] for p in res["gap_pairs"]]
    assert listed == ([] if band == "gt_1m" else [band])


def test_two_to_ten_mm_passes_and_overlap_still_fails():
    for g in (0.002, 0.004, 0.0075, 0.010):
        assert uc.gap_check(two(g), 0.002)["ok"] is True, g
    res = uc.gap_check(two(-0.005), 0.004)
    assert res["ok"] is False and [p["code"] for p in res["pairs_under_gap"]] == ["ucx_overlap"]


# --- cross-family pairs are measured; a violation is a warning, not a failure -----------------------------------
def test_cross_family_overlap_is_a_warning_not_a_failure():
    res = uc.gap_check(two(-0.005, fam_b="SM_U_Main"), 0.004)
    assert res["ok"] is True
    assert res["pairs_under_gap"] == []
    assert res["gap_bands"]["cross_family"]["overlap"] == 1
    [w] = res["warnings"]
    assert (w["code"], w["a"], w["b"], w["family_a"], w["family_b"]) == (
        "ucx_cross_family_gap", "UCX_SM_T_Main_001", "UCX_SM_U_Main_002", "SM_T_Main", "SM_U_Main")
    assert w["gap_m"] == pytest.approx(-0.005)


def test_cross_family_far_pair_is_counted_without_warning():
    res = uc.gap_check(two(0.5, fam_b="SM_U_Main"), 0.004)
    assert res["ok"] is True and res["warnings"] == []
    assert res["gap_bands"]["cross_family"]["100mm_1m"] == 1


def test_generated_boxes_band_matches_brute_force():
    # generated probe: 40 seeds x 8 axis-aligned boxes in 3 families. For two AABBs the SAT gap lies between the
    # largest axis separation and the Euclidean distance (face diagonals give extra axes); every pair is counted
    # exactly once in its scope, a listed pair carries the band of its gap, an unlisted pair is truly > 1 m away
    rng = random.Random(1607)
    for seed in range(40):
        boxes = []
        for i in range(8):
            lo = [rng.uniform(-2, 2) for _ in range(3)]
            hi = [c + rng.uniform(0.3, 1.0) for c in lo]
            boxes.append((f"UCX_SM_F{i % 3}_Main_{i + 1:03d}", lo, hi))
        meshes = [mesh(n, box(lo[0], hi[0], lo[1], hi[1], lo[2], hi[2])) for n, lo, hi in boxes]
        res = uc.gap_check(meshes, 0.004)
        listed = {(p["a"], p["b"]): p for p in res["gap_pairs"]}
        scopes = {"same_family": 0, "cross_family": 0}
        for (na, la, ha), (nb, lb, hb) in itertools.combinations(boxes, 2):
            seps = [max(lb[k] - ha[k], la[k] - hb[k]) for k in range(3)]
            lower = max(seps)
            euclid = math.sqrt(sum(s * s for s in seps if s > 0)) if lower > 0 else 0.0
            scope = "same_family" if na.split("_")[2] == nb.split("_")[2] else "cross_family"
            scopes[scope] += 1
            p = listed.get((na, nb)) or listed.get((nb, na))
            if p is None:
                assert euclid > 1.0, (seed, na, nb, euclid)
                continue
            assert p["scope"] == scope and p["band"] == band_of(p["gap_m"]), p
            assert lower - 1e-6 <= p["gap_m"] <= euclid + 1e-6, (p, lower, euclid)
        assert {s: sum(d.values()) for s, d in res["gap_bands"].items()} == scopes, seed
        assert sum(scopes.values()) == 28


# --- fail closed --------------------------------------------------------------------------------------------------
def test_non_finite_vertex_is_dropped_and_fails():
    bad = box(0, 1)
    bad["verts"][0][0] = float("nan")
    res = uc.gap_check([mesh("UCX_SM_T_Main_001", bad), mesh("UCX_SM_T_Main_002", box(2, 3))], 0.004)
    assert res["ok"] is False
    assert [d["name"] for d in res["dropped"]] == ["UCX_SM_T_Main_001"]


def test_unmeasured_piece_is_named():
    res = uc.gap_check([mesh("UCX_SM_T_Main_001", box(0, 1)), mesh("UCX_noindex", box(3, 4))], 0.004)
    assert res["ok"] is False
    assert [n["item"] for n in res["gap_not_measured"]] == ["UCX_noindex"]


def test_failed_cut_is_a_finding_not_a_crash(monkeypatch):
    core = uc._ucx10()

    def broken(*a, **k):
        raise ValueError("not a closed convex piece (convex=True, open edges=3)")

    monkeypatch.setattr(core, "_clip", broken)
    monkeypatch.setattr(uc, "_ucx10", lambda: core)
    res = uc.gap_check(two(0.001), 0.004)
    assert res["ok"] is False
    assert [p["action"] for p in core.plan(
        [{"handle": i, "name": m["name"], **m["hull"]} for i, m in enumerate(two(0.001))],
        core.gap_options({"gap_m": 0.004}))["pairs"]] == ["ambiguous"]
    codes = {c for v in res["findings"].values() for c, _ in v}
    assert codes == {"ucx_cut_failed"}
    assert res["ambiguous"] and "open edges=3" in res["ambiguous"][0]["reason"]


# --- etalons: read-back UCX hulls (real files outside git, sha-pinned) -------------------------------------------
EVIDENCE = (Path("C:/x/ev_t_8b761538"), Path("G:/Мой диск/AGR-evidence/1607-ucx-gap-bands"))
ETALONS = {
    "SM_Kpp_1": "ad6682472d179be607ba584734e160fc0fcd1fc21da039544064ca8cd5ce117e",
    "SM_BolshoyBulvar_64": "5ca2ef77c9b8c2c1563507e1c0387f04277e70cbc32e8c2f3688a7e03b8423c4",
    "SM_MashiPoryvaevoj_34_001": "09afc8f06319941a18f355ef10f3906d14b43c3f3b76bb7691ae31f25f1eed87",
}


def etalon(name):
    for d in EVIDENCE:
        p = d / f"{name}.ucx.json"
        if p.is_file():
            data = p.read_bytes()
            assert hashlib.sha256(data).hexdigest() == ETALONS[name], p
            return json.loads(data)["ucx"]
    pytest.skip(f"etalon readback {name} absent (customer data, outside git)")


@pytest.mark.parametrize("name", list(ETALONS))
def test_etalon_is_measured_without_crash_and_every_pair_counted(name):
    meshes = etalon(name)
    res = uc.gap_check(meshes, 0.002)
    assert "error" not in res
    assert res["pieces"] + len(res["dropped"]) == len(meshes)
    measured = res["pieces"] - len(res["gap_not_measured"])
    bands = res["gap_bands"]
    assert sum(sum(d.values()) for d in bands.values()) == math.comb(measured, 2)
    assert len(res["gap_pairs"]) == sum(sum(v for k, v in d.items() if k != "gt_1m") for d in bands.values())


def test_kpp1_passes():
    res = uc.gap_check(etalon("SM_Kpp_1"), 0.002)
    assert res["ok"] is True
    sf = res["gap_bands"]["same_family"]
    assert (sf["overlap"], sf["lt_2mm"], sf["2_10mm"], sf["10_100mm"], sf["100mm_1m"]) == (0, 0, 48, 1, 6)


def test_skolkovo_far_gaps_refuse_nothing():
    res = uc.gap_check(etalon("SM_BolshoyBulvar_64"), 0.002)
    sf = res["gap_bands"]["same_family"]
    assert (sf["2_10mm"], sf["10_100mm"], sf["100mm_1m"]) == (496, 52, 501)
    # the only failures are the pairs under the 2 mm gap (existing handling), never a far gap
    assert {(p["a"], p["b"]) for p in res["pairs_under_gap"]} and all(
        p["gap_before_m"] < 0.002 for p in res["pairs_under_gap"])


def test_mashi_negative_fixture_still_exactly_eight_overlaps():
    res = uc.gap_check(etalon("SM_MashiPoryvaevoj_34_001"), 0.002)
    assert res["ok"] is False
    assert res["gap_bands"]["same_family"]["overlap"] == 8
    assert sum(p["code"] == "ucx_overlap" for p in res["pairs_under_gap"]) == 8
