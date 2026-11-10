"""repair.flip_close on the real AC08 source and its L4 e2e rerun (#1144). No Blender: the Blender receipts are the
committed evidence-1144 JSON, checked against a fresh in-memory recompute.
Pattern: new-case: AC08 repair op evidence and fail-closed driver checks (#1144).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

pytestmark = pytest.mark.job

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "jobs" / "TEC26-OKS" / "AC08" / "l4-e2e-v001" / "run_e2e.py"
EVIDENCE = DRIVER.parent / "evidence-1144"
UVFIX = DRIVER.parent / "evidence-1144-uvfix"
BEFORE = DRIVER.parent / "evidence-d197"

_spec = importlib.util.spec_from_file_location("ac08_l4_e2e_1144", DRIVER)
e2e = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = e2e
_spec.loader.exec_module(e2e)
K = e2e.rko


def _load(d):
    return json.loads((d / "e2e.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def repaired():
    source, _ = K.load_source()
    after, rec = K.repair_flip_close(source)
    return source, after, rec


def test_real_repair_reduces_back_faces_and_borders_with_no_new_violators(repaired):
    source, after, rec = repaired
    assert rec["applied"] is True and rec["refusal_or_rollback"] is None
    assert rec["back_face_px"][0] > 3000 and rec["back_face_px"][1] == 0
    assert rec["open_borders_unhidden"] == [20, 0]
    assert all(x.get("new", 0) == 0 and x["passed"] for x in rec["check_operation"]["results"])
    assert rec["flipped"] == {"AC08_body": [], "AC08_knob": [], "AC08_plate": []}     # AC08 has no mis-wound face
    assert [(c["points"], c["material"]) for c in rec["caps"]["AC08_body"]] == [(16, 1)]
    assert [(c["points"], c["material"]) for c in rec["caps"]["AC08_plate"]] == [(4, 3)]
    assert rec["caps"]["AC08_knob"] == [] and rec["skipped"]["AC08_knob"] == [{"points": 12, "reason": "not selected"}]


def test_real_repair_keeps_every_source_polygon_uv_and_material(repaired):
    source, after, rec = repaired
    for k, p in source.items():
        n = len(p["faces"])
        assert after[k]["faces"][:n] == tuple(p["faces"])          # nothing flipped on AC08: identical polygons
        assert after[k]["uv"][:n] == p["uv"] and after[k]["mat"][:n] == p["mat"]
        caps = after[k]["faces"][n:]
        assert len(caps) == len(rec["caps"][k])
        for c in after[k]["uv"][n:]:
            q = np.asarray(c)
            assert np.isfinite(q).all() and q.min() >= 0 and q.max() <= 1
    assert K.preservation(source, after) == []
    payload, notes = K.export_payload(after)
    assert notes == {}


def _open_box(mats):
    v = np.array([(x, y, z) for z in (0, 1) for y in (0, 1) for x in (0, 1)], float)
    faces = ((4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5))
    uv = [[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)] for _ in faces]
    return {"box": {"v": v, "faces": faces, "uv": uv, "mat": list(mats)}}


def test_cap_on_a_loop_with_two_material_ids_is_an_error_naming_them():
    with pytest.raises(K.InputError, match=r"material ids \[1, 2\]"):
        K.repair_flip_close(_open_box([1, 1, 2, 1, 1]))


def test_synthetic_open_box_flip_and_cap():
    """SYNTHETIC: a unit box without its bottom and with one side face reversed."""
    s = _open_box([4] * 5)
    f = list(s["box"]["faces"])
    f[2] = f[2][::-1]
    s["box"]["faces"] = tuple(f)
    s["box"]["uv"][2] = [(0.0, 0.0), (0.1, 0.0), (0.2, 0.0), (0.3, 0.0)]
    after, rec = K.repair_flip_close(s)
    assert rec["flipped"] == {"box": [2]} and len(rec["caps"]["box"]) == 1 and rec["caps"]["box"][0]["material"] == 4
    g = after["box"]["faces"][2]
    assert g == (f[2][0],) + tuple(f[2][1:][::-1])
    assert after["box"]["uv"][2] == [(0.0, 0.0), (0.3, 0.0), (0.2, 0.0), (0.1, 0.0)]    # UV follows its corner


def test_repair_gate_fails_when_not_reduced_or_not_applied():
    rep = {"applied": True, "back_face_px": [5, 5], "open_borders_unhidden": [3, 0], "flipped": {}, "caps": {},
           "cap_area_m2": 0.0, "check_operation": {"results": []}}
    assert e2e._repair_gate(rep)["passed"] is False
    rep["back_face_px"] = [5, 0]
    assert e2e._repair_gate(rep)["passed"] is True
    rep["applied"] = "yes"
    assert e2e._repair_gate(rep)["passed"] is False


def test_cli_repair_with_absolute_invariants_exits_2_and_writes_nothing(tmp_path, capsys):
    src = tmp_path / "s.fbx"
    src.write_bytes(b"x")
    code = e2e.main(["--source-fbx", str(src), "--delivered-fbx", str(src), "--work", str(tmp_path / "w"),
                     "--evidence", str(tmp_path / "e"), "--invariants", "absolute", "--repair"])
    assert code == 2 and "relative" in capsys.readouterr().err
    assert not (tmp_path / "w").exists() and not (tmp_path / "e").exists()


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_delivered_area_with_nan_added_area_fails(bad):
    r = _load(BEFORE)
    dc = r["delivered_comparison"]
    assert not abs(dc["kernel_area_m2"] - dc["delivered_area_m2"] - bad) < 1.0


def test_committed_uvfix_evidence_s15_s17_keep_uv():
    """#1144 acceptance 1: the rerun without repair - S15-S17 exported and accepted, UV loss 0 (was 168/170 and
    S15 not exported in evidence-d197)."""
    r, old = _load(UVFIX), _load(BEFORE)
    assert (UVFIX / "e2e.md").read_text(encoding="utf-8") == e2e.markdown(r)
    assert sorted(r["inputs"].values()) == sorted(old["inputs"].values())
    for lab in ("S15_simplify_part_AC08_body", "S16_simplify_part_AC08_knob", "S17_simplify_part_AC08_plate"):
        x = r["readback"][lab]
        assert x.get("status") != "not_exported" and x["accepted"] and x["export_uv_loss"] == {}
    assert old["readback"]["S16_simplify_part_AC08_knob"]["export_uv_loss"] == {"simplified": 168}
    assert r["not_exported"] == {}


def test_committed_repair_evidence_is_current_and_gated():
    r = _load(EVIDENCE)
    assert (EVIDENCE / "e2e.md").read_text(encoding="utf-8") == e2e.markdown(r)
    assert r["gates"] == json.loads(json.dumps(e2e.gates(r)))
    assert r["issue"] == 1144 and r["gates"]["repair_flip_close"]["passed"]
    assert r["repair"]["back_face_px"][1] == 0 and r["repair"]["open_borders_unhidden"] == [20, 0]
    assert len(r["ops"]) == 19 and "R00_repair_flip_close" in r["readback"]
    assert r["readback"]["R00_repair_flip_close"]["accepted"]
    assert sorted(r["inputs"].values()) == sorted(_load(BEFORE)["inputs"].values())
