"""Real AC08 kernel-op evidence driver (#752): hash pin, element accounting, fail-closed paths, readback parity.

Fast tests only (no Blender): the Blender export/readback receipts are the committed evidence JSON, checked here
against a fresh in-memory recompute of the source metrics.
Pattern: new-case: tests for the job-local real-AC08 kernel-op evidence driver (#752).
"""
from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
JOB = ROOT / "jobs" / "TEC26-OKS" / "AC08" / "kernel-ops-v001"
EVIDENCE = JOB / "evidence" / "kernel_ops.json"


def _load():
    spec = importlib.util.spec_from_file_location("run_kernel_ops_752", JOB / "run_kernel_ops.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


K = _load()


def _box(offset=0.0):
    v = np.array([(x, y, z) for z in (0, 1) for y in (0, 1) for x in (0, 1)], float) + offset
    faces = ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5))
    uv = [[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)] for _ in faces]
    return {"v": v, "faces": faces, "uv": uv, "mat": [1] * 6}


def test_source_hash_pin_fails_closed(tmp_path):
    bad = tmp_path / "max-dump-008.json"
    shutil.copyfile(K.SOURCE, bad)
    bad.write_bytes(bad.read_bytes() + b" ")
    with pytest.raises(K.InputError, match=K.SOURCE_SHA256):
        K.load_source(bad)


def test_every_source_element_is_a_part_face_or_a_reported_drop():
    scene, drops = K.load_source()
    assert {k: len(p["faces"]) for k, p in scene.items()} == {"AC08_body": 143, "AC08_knob": 24, "AC08_plate": 13}
    ids = sorted(i for p in scene.values() for i in p["source_faces"])
    assert ids == list(range(180))                       # every polygon once, none duplicated
    assert drops == [{"element": "Colizii_044", "reason": "UCX collision hull, not a render part (UCX lane)"}]
    assert all(len(p["uv"]) == len(p["faces"]) == len(p["mat"]) for p in scene.values())


@pytest.mark.parametrize("which", ["existing", "alias_input"])
def test_outputs_refuse_existing_and_input_alias(tmp_path, which):
    if which == "existing":
        (tmp_path / "w").mkdir()
        with pytest.raises(K.InputError, match="exists"):
            K._require_new(tmp_path / "w", tmp_path / "a.json")
    else:
        with pytest.raises(K.InputError):
            K._require_new(tmp_path / "w", K.SOURCE)


def test_run_cli_refuses_existing_work_dir_and_writes_nothing(tmp_path):
    work, ev = tmp_path / "work", tmp_path / "ev"
    work.mkdir()
    assert K.main(["--work", str(work), "--evidence", str(ev), "--no-blender"]) == 1
    assert not ev.exists() and list(work.iterdir()) == []


def _metrics(state):
    return K.scene_metrics(K.rounded(state))


def test_parity_strict_tolerance_and_missing_part():
    mem_state = K.rounded({"b": _box(30.0)})
    m = K.scene_metrics(mem_state)
    near = {"b": {**mem_state["b"], "v": mem_state["b"]["v"] + 2e-6, "material_slots": 1}}
    rows = K.parity(m, K.scene_metrics(near), mem_state, near)
    assert all(r["equal_within_tol"] for r in rows)
    assert not all(r["equal"] for r in rows)               # bounds moved by 2 um: strictly unequal, reported
    far = {"b": {**mem_state["b"], "v": mem_state["b"]["v"] + 2e-5, "material_slots": 1}}
    rows = K.parity(m, K.scene_metrics(far), mem_state, far)
    bad = {r["metric"] for r in rows if not r["equal_within_tol"]}
    assert "vertex_max_abs_dev_m" in bad
    gone = K.parity(m, {"parts": {}, "cross_part_xview_face_pairs": 0})
    assert gone and not any(r["equal"] or r["equal_within_tol"] for r in gone if r["part"] == "b")


def test_uv_loss_is_reported_not_defaulted():
    s = _box()
    s["uv"][2] = None
    payload, notes = K.export_payload({"b": s})
    assert payload[0]["uv"] == [None] * 6 and "1 of 6" in notes["b"]
    assert K.part_metrics("b", s)["uv"]["faces_without_uv"] == 1


def test_seam_material_merge_is_zero_and_counted():
    class R:  # SeamResult shape: one polygon merged from two sources with different ids
        mesh = K.PolyMesh(_box()["v"], ((0, 2, 3, 1),))
        face_sources = ((("a", 0), ("b", 0)),)
        vertex_sources = ((("a", 0),), (), (("a", 2),), (("a", 3),), (), (), (), ())
    a, b = _box(), _box(5.0)
    b["mat"] = [2] * 6
    after, unmapped, merged = K.carry_seam({"a": a, "b": b}, R, ("a", "b"), "join_parts")
    assert after["a+b"]["mat"] == [0] and merged == 1 and unmapped == 4 and after["a+b"]["uv"] == [None]


def test_committed_evidence_is_current_and_failures_are_listed():
    r = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert r["source"]["sha256"] == r["source"]["sha256_after"] == K.SOURCE_SHA256
    scene, _ = K.load_source()
    fresh = json.loads(json.dumps(K.scene_metrics(scene), default=float))
    assert fresh == r["before"]
    assert len(r["ops"]) == 19 and all("label" in o for o in r["ops"])
    assert r["native_max_xview_parity"]["status"] == "not_run"
    exported = {k: v for k, v in r["readback"].items() if v.get("status") != "not_exported"}
    assert set(r["not_exported"]) == {k for k in r["readback"]} - set(exported) == {"S15_simplify_part_AC08_body"}
    assert len(exported) == 16 and all(v["readback_ok"] for v in exported.values())
    failed = {k for k, v in exported.items() if not v["accepted"]}
    assert failed == {"S16_simplify_part_AC08_knob", "S17_simplify_part_AC08_plate"}     # UV lost on export
    assert exported["S16_simplify_part_AC08_knob"]["export_uv_loss"] == {"simplified": 168}
    assert exported["S17_simplify_part_AC08_plate"]["export_uv_loss"] == {"simplified": 170}
    for k, v in exported.items():
        assert v["accepted"] == (v["all_equal_within_tol"] and not v["export_uv_loss"])
        assert v["payload_all_equal_within_tol"]
        assert any(x["metric"] == "polygon_material_ids" for x in v["parity"])
    for o in r["ops"]:      # a refused or rolled-back op carries its reason; nothing failing is marked applied
        assert o["applied"] == (o["check_operation"] is not None and o["check_operation"]["passed"])
        assert o["applied"] or o["refusal_or_rollback"]


# ---- review round 1 (PR #754): compare against the actual candidate, per-polygon materials, fail-closed readback ----

def _report(payload):
    """An fbx_readback.py-shaped report of exactly this export payload (what a faithful FBX round trip returns)."""
    meshes = []
    for o in payload:
        geo = {"vertices": [[round(float(x), 6) for x in p] for p in o["vertices"]],
               "polygons": [list(p) for p in o["polygons"]],
               "polygon_material": [f"ID_{m:02d}" for m in o["material_ids"]]}
        if all(c is not None for c in o["uv"]):
            geo["polygon_uv"] = [[[round(float(u), 6), round(float(w), 6)] for u, w in c] for c in o["uv"]]
        meshes.append({"name": o["name"], "materials": [f"ID_{n:02d}" for n in range(1, max(o["material_ids"]) + 1)],
                       "face_geometry": geo})
    return {"readback_ok": True, "blender": "synthetic", "meshes": meshes}


@pytest.fixture(scope="module")
def real_states():
    source, _ = K.load_source()
    rows = K.run_ops(K.copy_state(source))
    return source, [r["after_state"] for r in rows]


def test_real_source_control_is_accepted():
    source, _ = K.load_source()
    payload, _ = K.export_payload(source)
    c = K.compare_state(source, _report(payload))
    assert c["accepted"] and c["export_uv_loss"] == {}
    assert all(r["equal_within_tol"] for r in c["candidate_parity"])
    mats = [r for r in c["candidate_parity"] if r["metric"] == "polygon_material_ids"]
    assert len(mats) == 3 and all(r["equal"] for r in mats)


@pytest.mark.parametrize("op_no,with_uv,faces", [(16, 168, 169), (17, 170, 174)])
def test_real_partial_uv_states_fail_candidate_parity(real_states, op_no, with_uv, faces):
    _, states = real_states
    st = states[op_no - 1]
    assert sum(c is not None for c in st["simplified"]["uv"]) == with_uv and len(st["simplified"]["uv"]) == faces
    payload, _ = K.export_payload(st)
    c = K.compare_state(st, _report(payload))
    assert not c["accepted"]
    assert c["export_uv_loss"] == {"simplified": with_uv}
    bad = {(r["part"], r["metric"]) for r in c["candidate_parity"] if not r["equal_within_tol"]}
    assert ("simplified", "uv") in bad
    assert all(r["equal_within_tol"] for r in c["payload_parity"])     # the FBX round trip itself is faithful


def test_real_material_mutation_fails_parity():
    source, _ = K.load_source()
    assert source["AC08_body"]["mat"][0] == 1
    payload, _ = K.export_payload(source)
    rep = _report(payload)
    body = next(m for m in rep["meshes"] if m["name"] == "AC08_body")
    slots = len(body["materials"])
    assert slots >= 2
    body["face_geometry"]["polygon_material"][0] = "ID_02"
    c = K.compare_state(source, rep)
    assert not c["accepted"] and len(body["materials"]) == slots
    bad = {(r["part"], r["metric"]) for r in c["candidate_parity"] if not r["equal_within_tol"]}
    assert ("AC08_body", "polygon_material_ids") in bad and ("AC08_body", "materials") in bad
    assert {p for p, _ in bad} == {"AC08_body"}


@pytest.mark.parametrize("name", ["Foo", None])
def test_readback_unmapped_material_is_error(name):
    payload, _ = K.export_payload({"b": _box()})
    rep = _report(payload)
    rep["meshes"][0]["face_geometry"]["polygon_material"][3] = name
    with pytest.raises(K.InputError, match=f"{name}.*polygon 3|polygon 3.*{name}"):
        K.state_from_readback(rep)


@pytest.mark.parametrize("case", ["empty", "short_material", "no_material", "nan", "inf", "not_ok", "duplicate"])
def test_readback_fail_closed(case):
    payload, _ = K.export_payload({"b": _box(), "c": _box(5.0)})
    rep = _report(payload)
    geo = rep["meshes"][0]["face_geometry"]
    if case == "empty":
        rep["meshes"] = []
    elif case == "short_material":
        geo["polygon_material"].pop()
    elif case == "no_material":
        del geo["polygon_material"]
    elif case in ("nan", "inf"):
        geo["vertices"][0][0] = float(case)
    elif case == "not_ok":
        rep["readback_ok"] = False
    else:
        rep["meshes"][1]["name"] = rep["meshes"][0]["name"]
    with pytest.raises(K.InputError):
        K.compare_state({"b": _box(), "c": _box(5.0)}, rep)


def test_real_missing_part_is_not_accepted():
    source, _ = K.load_source()
    payload, _ = K.export_payload(source)
    rep = _report(payload)
    rep["meshes"] = [m for m in rep["meshes"] if m["name"] != "AC08_knob"]
    c = K.compare_state(source, rep)
    knob = [r for r in c["candidate_parity"] if r["part"] == "AC08_knob"]
    assert not c["accepted"] and knob and not any(r["equal_within_tol"] for r in knob)


# ---- review round 2 (PR #754): readback numbers are typed strictly, never coerced ----

BAD_INDEX = [0.25, False, True, 1.0, "0", None, [0], float("nan")]
BAD_NUMBER = [True, False, "1.5", None, [1.0], float("nan"), float("inf")]


def _real_report():
    source, _ = K.load_source()
    payload, _ = K.export_payload(source)
    return source, _report(payload)


@pytest.mark.parametrize("bad", BAD_INDEX, ids=repr)
def test_real_polygon_index_must_be_strict_int(bad):
    """Witness: real AC08 body polygon 0 corner 0 -> 0.25 / False was coerced by int() and accepted 58/58."""
    source, rep = _real_report()
    body = next(m for m in rep["meshes"] if m["name"] == "AC08_body")
    assert body["face_geometry"]["polygons"][0][0] == 0
    body["face_geometry"]["polygons"][0][0] = bad
    with pytest.raises(K.InputError, match=r"AC08_body.*polygon 0.*corner 0"):
        K.compare_state(source, rep)


def test_real_untouched_control_with_strict_types_is_accepted():
    source, rep = _real_report()
    assert K.compare_state(source, rep)["accepted"]


@pytest.mark.parametrize("bad", BAD_NUMBER, ids=repr)
@pytest.mark.parametrize("where", ["vertex", "uv"])
def test_readback_numbers_must_be_strict_finite(where, bad):
    source, rep = _real_report()
    geo = next(m for m in rep["meshes"] if m["name"] == "AC08_body")["face_geometry"]
    if where == "vertex":
        geo["vertices"][0][1] = bad
    else:
        geo["polygon_uv"][0][0][1] = bad
    with pytest.raises(K.InputError, match=r"AC08_body"):
        K.compare_state(source, rep)


@pytest.mark.parametrize("case", ["short_polygon", "polygon_not_list", "uv_corner_count", "vertex_arity",
                                  "polygons_missing", "vertices_missing"])
def test_readback_shape_fail_closed(case):
    source, rep = _real_report()
    geo = next(m for m in rep["meshes"] if m["name"] == "AC08_body")["face_geometry"]
    if case == "short_polygon":
        geo["polygons"][0] = geo["polygons"][0][:2]
    elif case == "polygon_not_list":
        geo["polygons"][0] = "0 1 2"
    elif case == "uv_corner_count":
        geo["polygon_uv"][0] = geo["polygon_uv"][0][:-1]
    elif case == "vertex_arity":
        geo["vertices"][0] = geo["vertices"][0][:2]
    elif case == "polygons_missing":
        del geo["polygons"]
    else:
        del geo["vertices"]
    with pytest.raises(K.InputError, match="AC08_body"):
        K.compare_state(source, rep)


def test_combined_regressions_material_index_uv_missing_repeat(real_states):
    """Round-1 and round-2 witnesses together: each alone is rejected, the control is accepted on repeat."""
    source, rep = _real_report()
    for _ in range(2):                                  # repeat: no state leaks between comparisons
        assert K.compare_state(source, json.loads(json.dumps(rep)))["accepted"]
    mixed = json.loads(json.dumps(rep))
    body = next(m for m in mixed["meshes"] if m["name"] == "AC08_body")
    body["face_geometry"]["polygon_material"][0] = "ID_02"
    assert not K.compare_state(source, mixed)["accepted"]           # material mutation alone
    body["face_geometry"]["polygons"][0][0] = False
    with pytest.raises(K.InputError, match="corner 0"):            # + malformed index -> error wins
        K.compare_state(source, mixed)
    partial = json.loads(json.dumps(rep))
    partial["meshes"] = [m for m in partial["meshes"] if m["name"] != "AC08_knob"]
    assert not K.compare_state(source, partial)["accepted"]         # missing part
    _, states = real_states
    st = states[15]
    payload, _ = K.export_payload(st)
    assert not K.compare_state(st, _report(payload))["accepted"]    # S16 UV loss still fails


NATIVE_S00 = Path("C:/x/ev_t_1483e1fa/v002/readback/S00_source.json")


@pytest.mark.skipif(not NATIVE_S00.is_file(), reason="native v002 readback receipt is local evidence (Drive)")
@pytest.mark.parametrize("bad", [None, 0.25, False])
def test_native_s00_receipt_corner_mutation(bad):
    """Reviewer's exact witness on the real Blender receipt; None = untouched control."""
    source, _ = K.load_source()
    rep = json.loads(NATIVE_S00.read_text(encoding="utf-8"))
    if bad is None:
        assert K.compare_state(source, rep)["accepted"]
        return
    body = next(m for m in rep["meshes"] if m["name"] == "AC08_body")
    body["face_geometry"]["polygons"][0][0] = bad
    with pytest.raises(K.InputError, match="corner 0"):
        K.compare_state(source, rep)
