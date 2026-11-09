"""AC08 L4 rerun with kernel invariants relative to the source [D201] (#968): committed evidence, the UV/material
preservation verdict and kernel-output composition of alternative ops. Synthetic states are marked; no Blender.
Pattern: new-case: AC08 L4 rerun evidence under relative invariants (#968).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "jobs" / "TEC26-OKS" / "AC08" / "l4-e2e-v001" / "run_e2e.py"
EVIDENCE = DRIVER.parent / "evidence-d197"
BEFORE = DRIVER.parent / "evidence"

_spec = importlib.util.spec_from_file_location("ac08_l4_e2e_rel", DRIVER)
e2e = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = e2e
_spec.loader.exec_module(e2e)
rko = e2e.rko


def _load(d):
    return json.loads((d / "e2e.json").read_text(encoding="utf-8"))


def test_committed_relative_evidence_is_current_and_every_refusal_has_a_reason():
    r = _load(EVIDENCE)
    assert (EVIDENCE / "e2e.md").read_text(encoding="utf-8") == e2e.markdown(r)
    assert r["gates"] == json.loads(json.dumps(e2e.gates(r)))
    assert r["issue"] == 968 and r["invariants"] == "relative [D201]"
    assert sorted(r["inputs"].values()) == sorted(_load(BEFORE)["inputs"].values())   # same FBX, delivered, dump
    assert len(r["ops"]) == 19
    applied = [f"{o['op']}:{o['part']}" for o in r["ops"] if o["applied"]]
    assert applied == ["keep:AC08_body", "keep:AC08_knob", "keep:AC08_plate", "join_parts:AC08_body+AC08_plate",
                       "join_parts:AC08_knob+AC08_plate"]
    for o in r["ops"]:
        assert o["applied"] or o["refusal_or_rollback"], o["op"]
        co = o["check_operation"]
        if co is not None:
            names = {x["name"] for x in co["results"] if "baseline" in x}
            assert names == {"open_borders_hidden", "no_visible_back_faces", "no_close_overlap"}
            assert all(x["new"] == x["count"] and x["passed"] == (x["new"] == 0)
                       for x in co["results"] if "baseline" in x)
            bf = next(x for x in co["results"] if x["name"] == "no_visible_back_faces")
            assert bf["baseline"] == 3107
        if o["applied"]:
            assert co is not None and co["passed"] and o["preservation"] == []
    assert r["gates"]["source_baseline_recorded"]["passed"] and "kernel_invariants_on_source" not in r["gates"]
    assert r["before_visibility"]["no_visible_back_faces"]["count"] == 3107
    assert r["applied_not_composed"] == [{"op": "join_parts:AC08_knob+AC08_plate", "part": "AC08_plate",
                                          "conflicts_with": "join_parts:AC08_body+AC08_plate"}]


def test_relative_and_absolute_runs_keep_the_same_delivered_geometry():
    before, after = _load(BEFORE), _load(EVIDENCE)
    for k in ("kernel_to_delivered_max_m", "delivered_to_kernel_max_m", "kernel_area_m2", "kernel_faces"):
        assert after["delivered_comparison"][k] == pytest.approx(before["delivered_comparison"][k], abs=1e-9), k


def test_relative_side_files_match_the_absolute_run():
    for name in ("album_compare.json", "sintez_summary.json"):
        a = json.loads((BEFORE / name).read_text(encoding="utf-8"))
        b = json.loads((EVIDENCE / name).read_text(encoding="utf-8"))
        if name == "album_compare.json":
            assert a["facades"] == b["facades"]
        else:
            assert a["hp"] == b["hp"] and a.get("np", a.get("lp")) is not None
            assert [x["req"] for x in a["hp_failed"]] == b["hp_failed"]


def _state():
    """SYNTHETIC two-part polygon state with UV and two material ids."""
    v = np.array([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], float)
    uv = [[(0, 0), (1, 0), (1, 1), (0, 1)]]
    return {"A": {"v": v, "faces": ((0, 1, 2, 3),), "uv": list(uv), "mat": [1]},
            "B": {"v": v + 2, "faces": ((0, 1, 2, 3),), "uv": list(uv), "mat": [2]}}


def test_preservation_names_uv_loss_merged_and_vanished_materials():
    src = _state()
    assert rko.preservation(src, rko.copy_state(src)) == []
    lost = rko.copy_state(src)
    lost["A"]["uv"] = [None]
    assert rko.preservation(src, lost) == ["UV lost on 1 faces of ['A']"]
    merged = {"A+B": {"v": src["A"]["v"], "faces": ((0, 1, 2, 3),), "uv": [None], "mat": [0]}}
    why = rko.preservation(src, merged)
    assert any("merged" in w and "A+B" in w for w in why) and any("[1, 2] vanished" in w for w in why)


@pytest.mark.parametrize("relative", [True, False])
def test_kernel_output_alternative_ops_conflict(relative):
    src = _state()
    a1 = rko.copy_state(src)
    a1["A"]["v"] = a1["A"]["v"] + 5
    a2 = rko.copy_state(src)
    a2["A"]["v"] = a2["A"]["v"] + 7
    rows = [{"op": "x", "part": "A", "applied": True, "after_state": a1},
            {"op": "y", "part": "A", "applied": True, "after_state": a2}]
    if not relative:
        with pytest.raises(e2e.InputError, match="x:A and y:A"):
            e2e.kernel_output(src, rows)
        return
    skipped = []
    out, composed = e2e.kernel_output(src, rows, skipped)
    assert composed == ["x:A"] and out["A"]["v"].min() == 5
    assert skipped == [{"op": "y:A", "conflicts_with": "x:A", "part": "A"}]


def test_relative_gate_with_empty_baseline_fails():
    r = _load(EVIDENCE)
    r["before_visibility"] = {}
    assert e2e.gates(r)["source_baseline_recorded"]["passed"] is False


def test_cli_rejects_an_unknown_invariants_mode(tmp_path):
    with pytest.raises(SystemExit):
        e2e.main(["--source-fbx", "x", "--delivered-fbx", "y", "--work", str(tmp_path / "w"),
                  "--invariants", "lenient"])
    assert not (tmp_path / "w").exists()
