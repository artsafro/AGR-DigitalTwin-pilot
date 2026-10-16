"""Horizontal-face orientation (issue #56). Every fixture is SYNTHETIC test data, not a real object."""
import copy

import numpy as np
import pytest

from test_orientation import WELD_M, _box, _built, _resize, _reverse
from twinqa.geometry import checks
from twinqa.geometry.mesh import from_dump

_BENCHES = ["bench-b01-box", "bench-b02-corner-niche", "bench-b02t-terrace"]
_TOL = {"weld_m": WELD_M}


def _hcheck(dump, tol=None):
    return checks.check_horizontal_faces(from_dump(dump), _TOL if tol is None else tol)


def _row(result, name):
    return next(mesh for mesh in result["details"]["meshes"] if mesh["name"] == name)


def _flip_global(dump, indices):
    pending = {int(i) for i in np.atleast_1d(indices)}
    offset = 0
    for mesh in dump["meshes"]:
        if mesh["name"].startswith("UCX_"):
            continue
        for local in range(len(mesh["triangles"])):
            if offset + local in pending:
                _reverse(mesh["triangles"], local)
        offset += len(mesh["triangles"])


def _horiz_axes(model):
    corners = model.corners()
    normal = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    length = np.linalg.norm(normal, axis=1)
    horiz = (length > 0) & (np.abs(normal[:, 2]) >= (1.0 - checks.HORIZONTAL_COS_TOL) * length)
    return horiz, normal[:, 2], corners.mean(1)[:, 2]


def _body_z(dump, model):
    names = [mesh["name"] for mesh in dump["meshes"] if not mesh["name"].startswith("UCX_")]
    zz = model.corners()[model.mesh_index == names.index("body")][..., 2]
    return float(zz.min()), float(zz.max())


def test_closed_box_passes():
    result = _hcheck({"meshes": [_box()]})
    assert result["status"] == "pass" and result["value"] == 0
    assert _row(result, "box")["horizontal_faces"] == 4
    assert _row(result, "box")["inward_faces"] == 0


def test_open_bottom_box_passes():
    result = _hcheck({"meshes": [_box(drop_bottom=True)]})
    assert result["status"] == "pass" and result["value"] == 0


def test_reversed_top_fails():
    result = _hcheck({"meshes": [_box(reverse={2, 3})]})
    assert result["status"] == "fail" and result["value"] == 2
    assert {2, 3} <= set(result["details"]["inward_triangles"])


def test_reversed_bottom_fails():
    result = _hcheck({"meshes": [_box(reverse={0, 1})]})
    assert result["status"] == "fail" and result["value"] == 2
    assert {0, 1} <= set(result["details"]["inward_triangles"])


def _overhang_with_detached_bottom():
    """Closed overhang whose bottom quad has its own vertices and faces up.

    The bottom corners are inset just past weld_m. Coincident copies would weld onto the
    wall corners, the reversed edges would be shared, and winding would catch them — not
    the blind spot (a downward soffit reversed and not welded to its neighbours)."""
    inset = WELD_M + 0.001
    verts = [
        [0, 10, 3], [10, 10, 3], [10, 12, 3], [0, 12, 3],
        [0, 10, 6], [10, 10, 6], [10, 12, 6], [0, 12, 6],
        [inset, 10 + inset, 3], [10 - inset, 10 + inset, 3],
        [10 - inset, 12 - inset, 3], [inset, 12 - inset, 3],
    ]
    tris = [
        [8, 10, 11], [8, 9, 10],
        [4, 5, 6], [4, 6, 7],
        [0, 1, 5], [0, 5, 4],
        [2, 3, 7], [2, 7, 6],
        [1, 2, 6], [1, 6, 5],
        [0, 4, 7], [0, 7, 3],
    ]
    return verts, tris


def test_detached_reversed_soffit_passes_orientation_but_fails_here():
    body = _box("body")
    body_v = (np.asarray(body["vertices"], float) * np.array([10.0, 10.0, 6.0])).tolist()
    over_v, over_t = _overhang_with_detached_bottom()
    base = len(body_v)
    mesh = {"name": "body", "vertices": body_v + over_v,
            "triangles": body["triangles"] + [[a + base, b + base, c + base] for a, b, c in over_t],
            "material_ids": [1] * (len(body["triangles"]) + len(over_t))}
    dump = {"meshes": [mesh]}
    assert checks.check_orientation(from_dump(dump), _TOL)["status"] == "pass"
    result = _hcheck(dump)
    assert result["status"] == "fail" and result["value"] == 2


@pytest.mark.parametrize("bench", _BENCHES)
def test_bench_step_ledge_and_window_head_reversed_fail(bench):
    spec, dump, tol = _built(bench)
    model = from_dump(dump)
    clean = checks.check_horizontal_faces(model, tol)
    assert clean["status"] == "pass" and clean["value"] == 0
    report = checks.run(model, model, spec, tol)
    assert next(c for c in report["checks"] if c["id"] == "horizontal_faces")["status"] == "pass"
    horiz, nz, cz = _horiz_axes(model)
    z0, z1 = _body_z(dump, model)
    groups = (
        np.flatnonzero(horiz & (nz > 0) & (cz > z0) & (cz < z1)),
        np.flatnonzero(horiz & (nz < 0) & (cz > z0)),
    )
    for indices in groups:
        broken = copy.deepcopy(dump)
        _flip_global(broken, indices)
        result = checks.check_horizontal_faces(from_dump(broken), tol)
        assert result["status"] == "fail" and result["value"] == len(indices)


@pytest.mark.parametrize("bench", _BENCHES)
def test_every_single_reversed_horizontal_face_is_flagged(bench):
    _, dump, _tol = _built(bench)
    model = from_dump(dump)
    horiz, _, _ = _horiz_axes(model)
    indices = np.flatnonzero(horiz)
    assert len(indices) > 0
    for index in indices:
        trial = copy.copy(model)
        trial.triangles = model.triangles.copy()
        row = trial.triangles[index].copy()
        trial.triangles[index] = (row[0], row[2], row[1])
        _inward, _horizontal, wrong = checks.inward_horizontal_faces(trial)
        assert int(index) in wrong and len(wrong) == 1


def _map_vertices(dump, fn):
    out = copy.deepcopy(dump)
    for mesh in out["meshes"]:
        mesh["vertices"] = fn(np.asarray(mesh["vertices"], float)).tolist()
    return out


def test_rigid_transform_keeps_clean_bench_clean():
    _spec, dump, tol = _built("bench-b02t-terrace")
    angle = np.deg2rad(37.0)
    c, s = np.cos(angle), np.sin(angle)

    def spin(verts):
        x, y = verts[:, 0], verts[:, 1]
        out = np.empty_like(verts)
        out[:, 0] = c * x - s * y + 123.4
        out[:, 1] = s * x + c * y - 56.7
        out[:, 2] = verts[:, 2] + 8.9
        return out

    turned = checks.check_horizontal_faces(from_dump(_map_vertices(dump, spin)), tol)
    assert turned["status"] == "pass" and turned["value"] == 0
    mirrored = checks.check_horizontal_faces(
        from_dump(_map_vertices(dump, lambda v: v * np.array([-1.0, 1.0, 1.0]))), tol)
    assert mirrored["value"] == sum(mesh["horizontal_faces"] for mesh in mirrored["details"]["meshes"])
    assert mirrored["status"] == "fail"


def test_enclosed_inverted_inner_box_is_flagged():
    body = _resize(_box("body"), 100.0)
    inner = _resize(_box("inner", reverse=range(12)), 0.2, (49.9, 49.9, 49.9))
    result = _hcheck({"meshes": [body, inner]})
    assert result["status"] == "fail"
    assert _row(result, "inner")["inward_faces"] == 4
    assert _row(result, "body")["inward_faces"] == 0


def _sheet(reverse=False):
    tris = [[0, 2, 1], [0, 3, 2]] if reverse else [[0, 1, 2], [0, 2, 3]]
    return {"name": "ground", "vertices": [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
            "triangles": tris, "material_ids": [1, 1]}


def test_open_ground_sheet():
    assert _hcheck({"meshes": [_sheet()]})["status"] == "pass"
    assert _hcheck({"meshes": [_sheet()]})["value"] == 0
    flipped = _hcheck({"meshes": [_sheet(reverse=True)]})
    assert flipped["status"] == "fail" and flipped["value"] == 2


def test_no_horizontal_faces_is_not_measured():
    empty = _hcheck({"meshes": []})
    assert empty["status"] == "not_measured" and empty["value"] is None
    wall = {"name": "wall", "vertices": [[0, 0, 0], [0, 0, 1], [0, 1, 0]],
            "triangles": [[0, 1, 2]], "material_ids": [1]}
    vertical = _hcheck({"meshes": [wall]})
    assert vertical["status"] == "not_measured" and vertical["value"] is None


def _shared_edge_box(reverse_bottom=False):
    """Unit box: bottom diagonal (1,0)-(0,1), top diagonal (0,0)-(1,1), outward."""
    verts = [
        [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
        [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1],
    ]
    bottom = [[0, 1, 3], [1, 2, 3]] if reverse_bottom else [[0, 3, 1], [1, 3, 2]]
    tris = bottom + [
        [4, 5, 6], [4, 6, 7],
        [0, 1, 5], [0, 5, 4],
        [2, 3, 7], [2, 7, 6],
        [1, 2, 6], [1, 6, 5],
        [0, 4, 7], [0, 7, 3],
    ]
    return {"name": "box", "vertices": verts, "triangles": tris, "material_ids": [1] * len(tris)}


def test_ray_through_shared_edge_counts_once():
    dump = {"meshes": [_shared_edge_box()]}
    assert checks.check_orientation(from_dump(dump), _TOL)["status"] == "pass"
    clean = _hcheck(dump)
    assert clean["status"] == "pass" and clean["value"] == 0
    flipped = _hcheck({"meshes": [_shared_edge_box(reverse_bottom=True)]})
    assert flipped["status"] == "fail" and flipped["value"] == 2


def test_does_not_mutate_input():
    model = from_dump({"meshes": [_box()]})
    vertices, triangles = model.vertices.copy(), model.triangles.copy()
    material_ids = model.material_ids.copy()
    checks.check_horizontal_faces(model, _TOL)
    checks.inward_horizontal_faces(model)
    assert np.array_equal(model.vertices, vertices)
    assert np.array_equal(model.triangles, triangles)
    assert np.array_equal(model.material_ids, material_ids)


def test_run_lists_horizontal_faces_after_orientation():
    spec, dump, tol = _built("bench-b01-box")
    model = from_dump(dump)
    ids = [item["id"] for item in checks.run(model, model, spec, tol)["checks"]]
    assert ids[ids.index("orientation") + 1] == "horizontal_faces"
