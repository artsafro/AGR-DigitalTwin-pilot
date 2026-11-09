"""Characterization of windows_glazing frame-depth readout on shared vs split (seam-index) cuboids.

Source: PR #757 report (windows-frame-depth-tessellation-sensitivity), Proposed next tasks 1.
Pattern: n/a | new-case: pin current behaviour only; no estimator adoption, windows stay parked.
"""

from __future__ import annotations

import copy
from collections import Counter

import pytest

from tests.methods.test_methods_catalog import BOX_T, mesh, mm

CUBOID = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 0, .07], [1, 0, .07], [1, 1, .07], [0, 1, .07]]
TRIS = [list(t) for t in BOX_T]
SPLIT_VERTS = [CUBOID[i] for t in TRIS for i in t]
SPLIT_TRIS = [[3 * k, 3 * k + 1, 3 * k + 2] for k in range(12)]
SHARED_EXPECT = {"depth": {"min": .07, "median": .07, "max": .07}, "components": 1, "polygons": 12}
SPLIT_EXPECT = {"depth": {"min": 0., "median": 0., "max": 0.}, "components": 12, "polygons": 12}


def scene(verts, tris):
    m = mesh("SM_Test_Main", verts, tris, materials=("M_Test_Main_Frame",))
    rb = {"readback_ok": True, "blender": "synthetic", "meshes": [m], "other_objects": [], "images": [],
          "materials": []}
    extra = {"ok": True, "meshes": {"SM_Test_Main": {
        "slots": ["M_Test_Main_Frame"], "polygons_by_material_index": {"0": len(tris)},
        "tris": len(tris), "polygon_material_index": [0] * len(tris)}}}
    return rb, extra


def read(verts, tris, fn=mm.windows_glazing):
    rb, extra = scene(verts, tris)
    before = copy.deepcopy((rb, extra))
    w = fn(rb, extra)
    assert (rb, extra) == before, "input dictionaries were mutated"
    assert w["frame_reason"] is None
    return w


def key(w):
    return {"depth": w["frame_depth_m"], "components": w["frame_components"], "polygons": w["frame_polygons"]}


def tri_multiset(verts, tris):
    return Counter(tuple(sorted(tuple(verts[i]) for i in t)) for t in tris)


def reindexed(verts, tris):
    """Deterministic vertex reindexing: reverse the vertex list, remap indices."""
    n = len(verts)
    return verts[::-1], [[n - 1 - i for i in t] for t in tris]


def quarter(verts):
    return [[-y, x, z] for x, y, z in verts]


def shifted(verts):
    return [[x + 2.0, y + 4.0, z + 8.0] for x, y, z in verts]


CASES = {"shared": (CUBOID, TRIS, SHARED_EXPECT), "split": (SPLIT_VERTS, SPLIT_TRIS, SPLIT_EXPECT)}


def test_inputs_are_the_same_surface():
    assert len(CUBOID) == 8 and len(TRIS) == 12 and len(SPLIT_VERTS) == 36
    assert len({tuple(v) for v in SPLIT_VERTS}) == 8
    assert tri_multiset(CUBOID, TRIS) == tri_multiset(SPLIT_VERTS, SPLIT_TRIS)
    # winding is preserved too, not only the vertex sets
    assert [[tuple(CUBOID[i]) for i in t] for t in TRIS] == [[tuple(SPLIT_VERTS[i]) for i in t] for t in SPLIT_TRIS]


@pytest.mark.parametrize("name", CASES)
def test_measured_expected_values(name):
    verts, tris, exp = CASES[name]
    w = read(verts, tris)
    assert key(w) == exp
    assert w["glass_objects"] == 0  # no delivery verdict or glass claim is added
    assert not any("pass" in k or "verdict" in k for k in w)


@pytest.mark.parametrize("name", CASES)
@pytest.mark.parametrize("op", ["reverse_faces", "reindex", "quarter_turn", "translate"])
def test_invariances(name, op):
    verts, tris, exp = CASES[name]
    base = read(verts, tris)
    if op == "reverse_faces":
        w = read(verts, tris[::-1])
        assert w == base  # complete public metrics
    elif op == "reindex":
        w = read(*reindexed(verts, tris))
        assert w == base
    elif op == "quarter_turn":
        w = read(quarter(verts), tris)
        assert key(w) == exp
    else:
        w = read(shifted(verts), tris)
        assert key(w) == exp


def test_flat_connected_ring_reads_zero_depth_one_component():
    out = [[0, 0, 0], [3, 0, 0], [3, 3, 0], [0, 3, 0]]
    inn = [[1, 1, 0], [2, 1, 0], [2, 2, 0], [1, 2, 0]]
    verts = out + inn
    tris = [[0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]]
    w = read(verts, tris)
    assert w["frame_depth_m"] == {"min": 0.0, "median": 0.0, "max": 0.0}
    assert w["frame_components"] == 1 and w["frame_polygons"] == 8
