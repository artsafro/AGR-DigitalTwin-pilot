"""Frozen original oracle for #283.

Pattern: primitive-first | new-case: first-group indexing exact-parity and scan bounds.
All scenes here are synthetic, not delivery acceptance evidence.
"""
from __future__ import annotations

import copy
import itertools
import json
from collections import defaultdict

import pytest

import twinqa.geometry.complexity as complexity
from twinqa.geometry.checks import result
from twinqa.geometry.complexity import FRAME_GROUPS, _hash, check_complexity


def reference_complexity(scene: dict, tol: dict) -> dict:
    """Exact original check_complexity implementation using linear generator scans."""
    meshes, objects = scene["meshes"], scene["objects"]
    tris = defaultdict(int)
    for ob in objects:
        tris[ob["group"]] += len(meshes[ob["mesh"]]["triangles"])
    total = sum(tris.values())
    over = {g: [n, tol["budget"][g]] for g, n in tris.items() if g in tol["budget"] and n > tol["budget"][g]}
    unbudgeted = sorted(g for g in tris if g not in tol["budget"])
    decor = set(tol["decor_groups"])
    too_many, not_silhouette, missing = [], [], []
    for name, m in meshes.items():
        group = next((ob["group"] for ob in objects if ob["mesh"] == name), None)
        if group not in decor or group in FRAME_GROUPS:
            continue
        meta = m.get("meta", {})
        pts, dev = meta.get("section_points"), meta.get("silhouette_dev_m")
        if pts is None or (pts > 4 and dev is None):
            missing.append(name)
            continue
        if pts > tol["decor_section_points_max"]:
            too_many.append([name, pts])
        if pts > 4 and dev <= tol["silhouette_dev_min_m"]:
            not_silhouette.append([name, dev])
    by_hash = defaultdict(list)
    for name, m in meshes.items():
        group = next((ob["group"] for ob in objects if ob["mesh"] == name), None)
        if group in decor:
            by_hash[_hash(m)].append(name)
    not_instanced = [names for names in by_hash.values() if len(names) > 1]
    count = defaultdict(int)
    for ob in objects:
        count[ob["mesh"]] += 1
    types = {g: len({ob["mesh"] for ob in objects if ob["group"] == g}) for g in decor}
    elements = {g: sum(1 for ob in objects if ob["group"] == g) for g in decor}
    ok = (total <= tol["total_max"] and not over and not unbudgeted and not missing and not too_many
          and not not_instanced and not not_silhouette)
    return result("complexity", ok, total, tol["total_max"],
                  {"triangles_by_group": dict(tris), "over_budget": over, "unbudgeted_groups": unbudgeted, "metrics_missing": missing[:20],
                   "elements_by_group": elements, "types_by_group": types,
                   "section_points_over": too_many[:20], "copies_not_instanced": not_instanced[:20],
                   "profile_without_silhouette": not_silhouette[:20]})

TOL = {"budget": {"piers": 100000, "walls": 100000, "storey_bands": 100000},
       "total_max": 100000, "decor_groups": ["piers", "storey_bands"],
       "decor_section_points_max": 12, "silhouette_dev_min_m": .07}


def mesh(i=0, meta=None):
    return {"vertices": [[0, 0, 0], [1+i/100, 0, 0], [1+i/100, 1, 0]],
            "triangles": [[0, 1, 2]], "material_ids": [i],
            "meta": {"section_points": 4} if meta is None else meta}


def scene(k=8, n=None):
    return {"meshes": {f"m{i}": mesh(i) for i in range(k)},
            "objects": [{"mesh": f"m{i % k}", "group": "piers"}
                        for i in range(k if n is None else n)]}


class CountingObjects(list):
    def __init__(self, values):
        super().__init__(values)
        self.starts = 0

    def __iter__(self):
        self.starts += 1
        return super().__iter__()


@pytest.mark.parametrize("k", range(1, 33))
def test_single_index(k):
    sc = scene(k)
    sc["objects"] = CountingObjects(sc["objects"])
    check_complexity(sc, TOL)
    assert sc["objects"].starts == 7


def serialize(value):
    # No sorted keys: dictionary/list order and NaN/Infinity tokens are significant.
    return json.dumps(value, ensure_ascii=True, allow_nan=True, separators=(",", ":"))


def outcome(fn, sc, tol):
    try:
        return serialize(["result", fn(sc, tol)])
    except Exception as exc:
        return serialize(["exception", type(exc).__module__, type(exc).__qualname__, exc.args, str(exc)])


def assert_parity(sc, tol=TOL):
    before = serialize([sc, tol])
    expected = outcome(reference_complexity, sc, tol)
    assert serialize([sc, tol]) == before
    actual = outcome(check_complexity, sc, tol)
    assert actual == expected
    assert serialize([sc, tol]) == before


def frozen_cases():
    metadata = [(4, None), (12, .07), (13, .08), (8, None),
                (None, None), (8, float("nan")), (8, float("inf")), (float("nan"), .08)]
    for first, second, (pts, dev) in itertools.product(
            ("piers", "walls", "storey_bands", None),
            ("piers", "walls", "storey_bands", None), metadata):
        sc = scene(2)
        sc["meshes"]["m0"]["meta"] = {"section_points": pts, "silhouette_dev_m": dev}
        sc["objects"] = [{"mesh": "m0", "group": first}, {"mesh": "m0", "group": second}]
        tol = copy.deepcopy(TOL)
        tol["budget"][None] = 100000
        yield sc, tol
    yield {}, TOL
    yield {"meshes": {}}, TOL
    yield {"objects": []}, TOL
    yield {"meshes": {}, "objects": []}, TOL
    sc = scene(); del sc["objects"][0]["mesh"]; yield sc, TOL
    sc = scene(); del sc["objects"][0]["group"]; yield sc, TOL
    sc = scene(); sc["objects"][0]["mesh"] = "unknown"; yield sc, TOL
    sc = scene(); sc["objects"][0]["mesh"] = []; yield sc, TOL
    sc = scene(2); sc["meshes"]["m1"] = copy.deepcopy(sc["meshes"]["m0"]); yield sc, TOL
    sc = scene(1); sc["meshes"]["m0"].update(polygons=[[0, 1, 2]], polygon_sizes=[3]); yield sc, TOL
    sc = scene(1); sc["meshes"]["m0"]["vertices"] = [["bad", 0, 0]]; yield sc, TOL
    sc = scene(1); del sc["meshes"]["m0"]["meta"]; yield sc, TOL
    sc = scene(1); tol = copy.deepcopy(TOL); tol["budget"]["piers"] = tol["total_max"] = 1; yield sc, tol


@pytest.mark.parametrize("sc,tol", list(frozen_cases()))
def test_frozen_semantics(sc, tol):
    assert_parity(sc, tol)


@pytest.mark.parametrize("k", range(1, 33))
def test_hash_order(k, monkeypatch):
    sc = scene(k)
    expected = []
    actual = []
    real = complexity._hash
    # Both implementations still compute every real hash in mesh insertion order.
    monkeypatch.setitem(reference_complexity.__globals__, "_hash",
                        lambda m: (expected.append(serialize(m)), real(m))[1])
    monkeypatch.setattr(complexity, "_hash", lambda m: (actual.append(serialize(m)), real(m))[1])
    assert_parity(sc)
    assert actual == expected == [serialize(m) for m in sc["meshes"].values()]


def test_index_rebuilt():
    sc = scene(1)
    sc["objects"] = [{"mesh": "m0", "group": None}, {"mesh": "m0", "group": "piers"}]
    sc["meshes"]["m0"]["meta"] = {"section_points": 13, "silhouette_dev_m": .08}
    tol = copy.deepcopy(TOL); tol["budget"][None] = 100000
    assert_parity(sc, tol)
    assert check_complexity(sc, tol)["status"] == "pass"
    sc["objects"].reverse()
    assert_parity(sc, tol)
    assert check_complexity(sc, tol)["status"] == "fail"


def test_diagnostic_truncation():
    sc = scene(25)
    for m in sc["meshes"].values():
        m["meta"] = {"section_points": 13, "silhouette_dev_m": .03}
    assert_parity(sc)
    details = check_complexity(sc, TOL)["details"]
    assert details["section_points_over"] == [[f"m{i}", 13] for i in range(20)]
    assert details["profile_without_silhouette"] == [[f"m{i}", .03] for i in range(20)]


def test_timing_gate():
    import runpy
    from pathlib import Path

    gate = runpy.run_path(str(Path(__file__).resolve().parents[2] /
                             "experiments/complexity-group-index/driver.py"))["verdict"]
    good = [{"phase": phase, "k": k, "layout": layout, "parity": True,
             "pairs": [[1., .5] for _ in range(7 if phase == "primary" else 3)]}
            for phase, ks in (("primary", (32, 256, 1024)), ("confirmation", (1024,)))
            for k in ks for layout in ("grouped", "interleaved")]
    assert gate(good) == "SUPPORTED"
    assert gate([]) == gate(None) == "INCONCLUSIVE"
    for i in range(8):
        assert gate(good[:i] + good[i+1:]) == "INCONCLUSIVE"
        for field, value in (("parity", False), ("phase", "unsupported"), ("pairs", [])):
            bad = copy.deepcopy(good); bad[i][field] = value
            assert gate(bad) == "INCONCLUSIVE"
        for value in (float("nan"), float("inf"), 0., -1., "unsupported", True):
            bad = copy.deepcopy(good); bad[i]["pairs"][0][1] = value
            assert gate(bad) == "INCONCLUSIVE"
        for ratio in ((.8, .81) if good[i]["k"] == 1024 else (1.1, 1.11)):
            bad = copy.deepcopy(good)
            bad[i]["pairs"] = [[1., ratio] for _ in good[i]["pairs"]]
            assert gate(bad) == "REJECTED"

