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
    assert len(exported) == 16 and all(v["readback_ok"] and v["all_equal_within_tol"] for v in exported.values())
    for o in r["ops"]:      # a refused or rolled-back op carries its reason; nothing failing is marked applied
        assert o["applied"] == (o["check_operation"] is not None and o["check_operation"]["passed"])
        assert o["applied"] or o["refusal_or_rollback"]
