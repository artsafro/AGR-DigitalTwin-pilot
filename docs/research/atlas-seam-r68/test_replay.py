"""Synthetic (not real-object data) unit checks for the #67 cross-seam continuity runner."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from replay import measure  # noqa: E402

SIDE = 64
LINE_ROW = 38  # one dark horizontal "joint" row, uniform along u


def _image():
    img = np.full((SIDE, SIDE, 3), 200, dtype=np.uint8)
    img[LINE_ROW] = 20
    return img


def _rb(b_v0=0.2, c_uv=None):
    """Corner of two walls (A normal +X, B normal +Y) sharing edge (0, 3); C continues A over edge (1, 2)."""
    vertices = [[0, 0, 0], [0, 0.05, 0], [0, 0.05, 0.05], [0, 0, 0.05], [0.05, 0, 0.05], [0.05, 0, 0],
                [0, 0.10, 0], [0, 0.10, 0.05]]
    polygons = [[0, 1, 2, 3], [0, 3, 4, 5], [1, 6, 7, 2]]
    a = [[0.5, 0.2], [0.9, 0.2], [0.9, 0.6], [0.5, 0.6]]
    b = [[0.4, b_v0], [0.4, b_v0 + 0.4], [0.1, b_v0 + 0.4], [0.1, b_v0]]
    c = c_uv or [[0.9, 0.2], [0.95, 0.2], [0.95, 0.6], [0.9, 0.6]]
    return {"meshes": [{"name": "SM_Test_Main", "face_geometry": {
        "vertices": vertices, "polygons": polygons, "polygon_uv": [a, b, c]}}]}


def test_same_phase_corner_scores_zero_and_counts_edges():
    out = measure(_rb(), {1001: _image()}, {1001})
    clean = out["states"]["clean"]
    assert clean["tiles"][1001]["seam_edges"] == 1
    assert clean["tiles"][1001]["samples"] == 50
    assert clean["score"] == 0
    assert out["edges"]["continuous"] == 1


def test_phase_break_scores_positive():
    assert measure(_rb(b_v0=0.25), {1001: _image()}, {1001})["states"]["clean"]["score"] > 0


def test_witness_shifts_only_plus_x_faces_and_raises_score():
    rb = _rb()
    before = copy.deepcopy(rb)
    out = measure(rb, {1001: _image()}, {1001}, witness="plus_x")
    assert rb == before
    for state in ("+2px", "+5px"):
        s = out["states"][state]
        assert s["changed_faces"] == 2 and s["non_target_changed_faces"] == 0  # faces A and C point to +X
        assert s["score"] > out["states"]["clean"]["score"]
    assert out["states"]["clean"]["changed_faces"] == 0


def test_r2_witness_shifts_first_side_of_each_seam_only():
    rb = _rb(c_uv=[[0.1, 0.2], [0.15, 0.2], [0.15, 0.6], [0.1, 0.6]])  # seams A-B (0,3) and A-C (1,2)
    out = measure(rb, {1001: _image()}, {1001})
    assert out["witness"] == "seam_first"
    assert out["states"]["+5px"]["changed_faces"] == 1
    assert out["states"]["+5px"]["score"] > out["states"]["clean"]["score"]
    assert out["states"]["clean"] == measure(rb, {1001: _image()}, {1001}, witness="plus_x")["states"]["clean"]


def test_local_contrast_gain_preserves_ratio_on_eligible_seam_samples():
    image = np.random.default_rng(68).integers(0, 125, size=(SIDE, SIDE, 3), dtype=np.uint8)
    rb = _rb(b_v0=0.25)
    original = measure(rb, {1001: image}, {1001})["states"]["clean"]["contrast"]
    brighter = measure(rb, {1001: 2 * image}, {1001})["states"]["clean"]["contrast"]
    assert 0 < original["samples"] <= 50
    assert not original["floor_used"]
    assert brighter["cross"] == 2 * original["cross"]
    assert brighter["within"] == 2 * original["within"]
    assert brighter["ratio"] == pytest.approx(original["ratio"], abs=1e-12)


def test_cross_tile_edge_is_border_not_seam():
    rb = _rb(c_uv=[[0.1, 0.2], [0.15, 0.2], [0.15, 0.6], [0.1, 0.6]])
    rb["meshes"][0]["face_geometry"]["polygon_uv"][1] = [[x + 1, y] for x, y in
                                                          rb["meshes"][0]["face_geometry"]["polygon_uv"][1]]
    out = measure(rb, {1001: _image(), 1002: _image()}, {1001})
    assert out["edges"]["border"] == 1
    assert out["states"]["clean"]["tiles"][1001]["seam_edges"] == 1  # A-C seam remains
    assert out["states"]["clean"]["contrast"]["status"] == "not_exercised"  # C is narrower than 6 px


def test_no_seam_samples_is_not_exercised():
    rb = _rb()
    rb["meshes"][0]["face_geometry"]["polygon_uv"][1] = [[x + 1, y] for x, y in
                                                          rb["meshes"][0]["face_geometry"]["polygon_uv"][1]]
    with pytest.raises(ValueError, match="not_exercised"):
        measure(rb, {1001: _image(), 1002: _image()}, {1001})
