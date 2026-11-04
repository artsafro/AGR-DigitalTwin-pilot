"""Mixed-component shell accounting and reason-unit controls for closed_shells.

Pattern: new-case: packed closed box, open box, doubled sheet and weld-collapsed triangle.
Reason values mix triangle and component units on purpose today.
A closed shell is not outward-normal or exterior acceptance.
"""
from __future__ import annotations

import copy
import inspect

import numpy as np

from tests.methods.test_building_body import rb_of
from tests.methods.test_methods_catalog import BOX_T, box, mesh, mm

# 0.02 mm is 0.2 of the 0.1 mm weld cell, so these points share one grid cell and sit clear of a .5 tie.
_COLLAPSE_SPAN_M = 2e-5
_PERMUTATIONS = 8


def _collapsed_triangle(origin):
    x, y, z = origin
    return [[x, y, z], [x, y, z + _COLLAPSE_SPAN_M], [x + _COLLAPSE_SPAN_M, y, z]], [[0, 1, 2]]


def _parts():
    """Four hand-written, spatially disjoint pieces. Triangle lists are counted here, not taken from the metric."""
    closed = (box((0.0, 0.0, 0.0), (1.0, 1.0, 1.0)), [list(t) for t in BOX_T])
    opened = (box((10.0, 0.0, 0.0), (11.0, 1.0, 1.0)), [list(t) for t in BOX_T[2:]])  # one face pair removed
    sheet = ([[20.0, 0.0, 0.0], [21.0, 0.0, 0.0], [20.0, 1.0, 0.0]], [[0, 1, 2], [0, 2, 1]])
    collapsed = _collapsed_triangle((30.0, 0.0, 0.0))
    parts = (closed, opened, sheet, collapsed)
    assert [len(tris) for _, tris in parts] == [12, 10, 2, 1]
    assert sheet[1][0] == [0, 1, 2] and sheet[1][1] == [0, 2, 1]
    return parts


def _weld_keys(verts):
    return np.round(np.asarray(verts, float) / mm.SHELL_WELD_M).astype(np.int64)


def _assert_parts_stay_separate(parts):
    assert mm.SHELL_WELD_M == 1e-4
    boxes = []
    for verts, tris in parts:
        pts = np.asarray(verts, float)
        assert np.isfinite(pts).all()
        quot = pts / mm.SHELL_WELD_M
        assert np.min(np.abs(quot - (np.floor(quot) + 0.5))) > 0.2  # clear of rounding ties
        boxes.append((pts.min(0), pts.max(0)))
        if len(tris) == 1 and len(verts) == 3:
            assert len(np.unique(_weld_keys(verts), axis=0)) == 1
        else:
            keys = _weld_keys(verts)
            for tri in tris:
                assert len({tuple(keys[i]) for i in tri}) == 3
    for i, (lo, hi) in enumerate(boxes):
        for lo2, hi2 in boxes[i + 1:]:
            gap = np.maximum(lo2 - hi, lo - hi2)
            assert float(gap.max()) >= 1.0


def _pack(parts):
    verts, tris = [], []
    for src_verts, src_tris in parts:
        base = len(verts)
        verts.extend([list(p) for p in src_verts])
        tris.extend([[a + base, b + base, c + base] for a, b, c in src_tris])
    return verts, tris


def _expected_packed():
    return {"closed_shell_share": round(12 / 25, 5), "components": 3, "closed_components": 1,
            "open_reasons": {"duplicated triangle (doubled sheet)": 1,
                             "edge not shared by exactly two triangles": 1,
                             "triangles collapsed by weld": 1},
            "weld_m": mm.SHELL_WELD_M, "reason": None}


def _packed_rb():
    verts, tris = _pack(_parts())
    assert len(tris) == 25 and len(verts) == 22
    return rb_of(mesh("SM_Test_Main", verts, tris))


def _split_rb():
    names = ("SM_Test_Closed", "SM_Test_Open", "SM_Test_Sheet", "SM_Test_Collapsed")
    return rb_of(*(mesh(name, verts, tris) for name, (verts, tris) in zip(names, _parts())))


def _collapsed_only_rb():
    first = _collapsed_triangle((40.0, 0.0, 0.0))
    second = _collapsed_triangle((50.0, 1.0, 0.0))
    verts, tris = _pack((first, second))
    assert len(tris) == 2 and len(np.unique(_weld_keys(first[0]), axis=0)) == 1
    assert len(np.unique(_weld_keys(second[0]), axis=0)) == 1
    return rb_of(mesh("SM_Test_Main", verts, tris))


def _expected_collapsed_only():
    return {"closed_shell_share": round(0 / 2, 5), "components": 0, "closed_components": 0,
            "open_reasons": {"triangles collapsed by weld": 2}, "weld_m": mm.SHELL_WELD_M, "reason": None}


def _ucx_only_rb():
    return rb_of(mesh("UCX_SM_Test_Main_001", box((0.0, 0.0, 0.0), (1.0, 1.0, 1.0)), [list(t) for t in BOX_T],
                      uv=False, materials=()))


def _expected_ucx_only():
    return {"closed_shell_share": None, "components": 0, "closed_components": 0, "open_reasons": {},
            "reason": "no model triangle"}


def _run(rb):
    before = copy.deepcopy(rb)
    out = mm.closed_shells(rb)
    assert rb == before
    return out


def _reorder(tris, order):
    return [list(tris[int(i)]) for i in order]


def _relabel(verts, tris, perm):
    inverse = np.empty(len(perm), dtype=int)
    inverse[np.asarray(perm, int)] = np.arange(len(perm))
    new_verts = [list(verts[int(i)]) for i in perm]
    new_tris = [[int(inverse[a]), int(inverse[b]), int(inverse[c])] for a, b, c in tris]
    return new_verts, new_tris


def _variant(replacements):
    """In-memory copy of closed_shells. Nothing is written back to the source file."""
    src = inspect.getsource(mm.closed_shells)
    for old, new in replacements:
        if src.count(old) != 1:
            raise AssertionError("mutation anchor was not unique")
        src = src.replace(old, new, 1)
    compiled = dict(mm.__dict__)
    exec(src, compiled)  # noqa: S102 - task-local variant, restored before the real readout
    return compiled["closed_shells"]


def _drop_collapsed_from_total():
    return _variant([
        ("        total += len(t)\n        key = np.round(v / weld_m).astype(np.int64)\n",
         "        key = np.round(v / weld_m).astype(np.int64)\n"),
        ("        t = t[keep]\n        if not len(t):\n            continue\n",
         "        t = t[keep]\n        total += len(t)\n        if not len(t):\n            continue\n"),
    ])


def _count_collapsed_as_components():
    old = ('        if (~keep).any():\n'
           '            reasons["triangles collapsed by weld"] = reasons.get("triangles collapsed by weld", 0) + '
           'int((~keep).sum())\n'
           '        t = t[keep]\n')
    new = ('        if (~keep).any():\n'
           '            n_collapsed = int((~keep).sum())\n'
           '            reasons["triangles collapsed by weld"] = reasons.get("triangles collapsed by weld", 0) + '
           'n_collapsed\n'
           '            comps += n_collapsed\n'
           '        t = t[keep]\n')
    return _variant([(old, new)])


def test_packed_defects_count_closed_triangles_over_every_model_triangle():
    parts = _parts()
    _assert_parts_stay_separate(parts)
    got = _run(_packed_rb())
    assert got == _expected_packed()
    assert got["closed_shell_share"] == round(12 / (12 + 10 + 2 + 1), 5) == 0.48
    assert got["reason"] is None
    # collapsed is a triangle count; the other two reasons are one component each
    assert got["open_reasons"]["triangles collapsed by weld"] == 1
    assert got["components"] == 3 and got["closed_components"] == 1


def test_four_model_meshes_match_the_packed_public_result():
    assert _run(_split_rb()) == _run(_packed_rb()) == _expected_packed()


def test_face_order_reversal_and_vertex_relabeling_are_invariant():
    verts, tris = _pack(_parts())
    assert _run(rb_of(mesh("SM_Test_Main", verts, tris[::-1]))) == _expected_packed()
    reversed_verts, reversed_tris = _relabel(verts, tris, np.arange(len(verts))[::-1])
    assert _run(rb_of(mesh("SM_Test_Main", reversed_verts, reversed_tris))) == _expected_packed()
    face_hits = vertex_hits = 0
    rng = np.random.default_rng(20261102)
    for _ in range(_PERMUTATIONS):
        reordered = _reorder(tris, rng.permutation(len(tris)))
        assert _run(rb_of(mesh("SM_Test_Main", verts, reordered))) == _expected_packed()
        face_hits += 1
        moved, moved_tris = _relabel(verts, tris, rng.permutation(len(verts)))
        assert _run(rb_of(mesh("SM_Test_Main", moved, moved_tris))) == _expected_packed()
        vertex_hits += 1
    assert (face_hits, vertex_hits) == (_PERMUTATIONS, _PERMUTATIONS)


def test_a_disjoint_ucx_box_does_not_change_the_packed_result():
    packed = _packed_rb()
    ucx = mesh("UCX_SM_Test_Main_001", box((60.0, 0.0, 0.0), (61.0, 1.0, 1.0)), [list(t) for t in BOX_T],
               uv=False, materials=())
    packed["meshes"].append(ucx)
    assert _run(packed) == _expected_packed()


def test_two_collapsed_triangles_stay_in_the_denominator():
    got = _run(_collapsed_only_rb())
    assert got == _expected_collapsed_only()
    assert got["closed_shell_share"] == 0
    assert got["components"] == 0 and got["closed_components"] == 0
    assert got["open_reasons"] == {"triangles collapsed by weld": 2}
    assert got["reason"] is None and got["reason"] != "no model triangle"


def test_ucx_only_input_has_no_model_triangle():
    got = _run(_ucx_only_rb())
    assert got == _expected_ucx_only()
    assert got["closed_shell_share"] is None and got["components"] == 0 and got["closed_components"] == 0
    assert got["reason"] == "no model triangle"


def test_dropping_collapsed_triangles_from_the_total_is_caught(monkeypatch):
    real = mm.closed_shells
    variant = _drop_collapsed_from_total()
    monkeypatch.setattr(mm, "closed_shells", variant)
    try:
        mutated = mm.closed_shells(_packed_rb())
        assert mutated != _expected_packed()
        assert mutated["closed_shell_share"] != _expected_packed()["closed_shell_share"]
        only = mm.closed_shells(_collapsed_only_rb())
        assert only != _expected_collapsed_only()
        assert only["reason"] == "no model triangle"
    finally:
        monkeypatch.setattr(mm, "closed_shells", real)
    assert _run(_packed_rb()) == _expected_packed()
    assert _run(_collapsed_only_rb()) == _expected_collapsed_only()


def test_counting_collapsed_triangles_as_components_is_caught(monkeypatch):
    real = mm.closed_shells
    variant = _count_collapsed_as_components()
    monkeypatch.setattr(mm, "closed_shells", variant)
    try:
        mutated = mm.closed_shells(_packed_rb())
        assert mutated != _expected_packed()
        assert mutated["components"] != _expected_packed()["components"]
        only = mm.closed_shells(_collapsed_only_rb())
        assert only != _expected_collapsed_only()
        assert only["components"] != 0
    finally:
        monkeypatch.setattr(mm, "closed_shells", real)
    assert mm.closed_shells is real
    assert _run(_packed_rb()) == _expected_packed()
    assert _run(_collapsed_only_rb()) == _expected_collapsed_only()
