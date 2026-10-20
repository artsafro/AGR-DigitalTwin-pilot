"""new-case: #295 explicit, geometry-pinned user exception; all other samples stay <=20 mm."""
import copy
import hashlib
import json

import numpy as np
import pytest

from test_ground_review_r2 import _bg, _run


def _policy(rep):
    return {"decision": "Artem 2026-10-20 option a", "input_sha256": rep["input_sha256"],
            "surface_sha256": rep["surface_sha256"],
            "samples": copy.deepcopy(rep["stack_gaps"]["normal_gap_over_band_samples"])}


def test_explicit_gap_exception_allows_only_frozen_samples(tmp_path):
    code, out, rep = _run(tmp_path, steep=True)
    assert code == 1
    policy = _policy(rep)
    samples = policy["samples"]
    assert {s["kind"] for s in samples} == {"corner", "centroid"}
    assert all(s["upper_face"] >= 0 and s["lower_face"] >= 0 and s["gap_mm"] > 20 for s in samples)
    assert all(s["vertex"] >= 0 for s in samples if s["kind"] == "corner")
    bg = _bg()
    gate = bg.acceptance_gates(rep, policy)["normal_gap_max_20mm"]
    assert gate["pass"] and gate["value"]["accepted_samples"] == samples
    assert rep["stack_gaps"]["normal_gap_vertices_above"] > 0  # diagnostics never hidden
    policy_path = tmp_path / "exception.json"
    policy_path.write_text(json.dumps(policy))
    fresh = tmp_path / "accepted"
    assert bg.main([str(tmp_path / "a.json"), "--out", str(fresh), "--gap-exceptions", str(policy_path)]) == 0
    assert len(list(fresh.glob("ground_master_*.json"))) == 2


@pytest.mark.parametrize("change", ["source", "surface", "missing", "extra", "larger", "nan", "empty", "duplicate", "counter", "lower", "identity"])
def test_gap_exception_fail_closed(tmp_path, change):
    _, _, rep = _run(tmp_path, steep=True)
    policy = _policy(rep)
    if change in ("source", "surface"):
        policy["input_sha256" if change == "source" else "surface_sha256"] = "0" * 64
    elif change == "missing":
        policy["samples"].pop()
    elif change == "extra":
        policy["samples"].append({**policy["samples"][0], "upper_face": 999999})
    elif change == "larger":
        rep["stack_gaps"]["normal_gap_over_band_samples"][0]["gap_mm"] += 0.01
    elif change == "nan":
        policy["samples"][0]["gap_mm"] = float("nan")
    elif change == "empty":
        policy = {}
    elif change == "duplicate":
        policy["samples"].append(policy["samples"][0])
    elif change == "counter":
        rep["stack_gaps"]["normal_gap_vertices_above"] += 1
    elif change == "identity":
        rep["stack_gaps"]["normal_gap_over_band_samples"][0]["vertex"] = 999999
    else:
        rep["stack_gaps"]["normal_gap_vertices_below"] = 1
    gates = _bg().acceptance_gates(rep, policy)
    assert not all(g["pass"] for g in gates.values())


def test_surface_fingerprint_binds_geometry_and_order():
    bg = _bg()
    v = np.array([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]])
    f = np.array([[0, 1, 2]])
    original = bg.surface_fingerprint(v, f)
    assert original == bg.surface_fingerprint(v.copy(), f.copy())
    for axis in range(3):
        moved = v.copy()
        moved[0, axis] += 1e-6
        assert original != bg.surface_fingerprint(moved, f)
    assert original != bg.surface_fingerprint(v, f[:, ::-1])
