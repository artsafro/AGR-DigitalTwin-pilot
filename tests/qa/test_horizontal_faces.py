"""Horizontal-face orientation (issues #56 and #314). Every fixture is SYNTHETIC test data, not a real object."""
import copy

import numpy as np
import pytest

from test_orientation import WELD_M, _box, _built, _resize, _reverse
from twinqa.geometry import checks
from twinqa.geometry.mesh import edge_uses, from_dump, weld

_BENCHES = ["bench-b01-box", "bench-b02-corner-niche", "bench-b02t-terrace"]
_TOL = {"weld_m": WELD_M}


def _hcheck(dump, tol=None):
    return checks.check_horizontal_faces(from_dump(dump), _TOL if tol is None else tol)


def _row(result, name):
    return next(mesh for mesh in result["details"]["meshes"] if mesh["name"] == name)


def _split(dump, upward):
    """Move horizontal upward (or downward) triangles of every non-UCX mesh into `<name>_roof` / `<name>_soffit`.

    Coordinates and winding are unchanged. SYNTHETIC fixture helper."""
    out = copy.deepcopy(dump)
    fresh = []
    for mesh in out["meshes"]:
        if mesh["name"].startswith("UCX_"):
            continue
        tris = np.asarray(mesh["triangles"], int)
        if len(tris) == 0:
            continue
        corners = np.asarray(mesh["vertices"], float)[tris]
        normal = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
        length = np.linalg.norm(normal, axis=1)
        horizontal = np.abs(normal[:, 2]) >= (1.0 - checks.HORIZONTAL_COS_TOL) * length
        selected = horizontal & ((normal[:, 2] > 0) if upward else (normal[:, 2] < 0))
        if not np.any(selected):
            continue
        other = copy.deepcopy(mesh)
        other["name"] += "_roof" if upward else "_soffit"
        for key in ("triangles", "material_ids"):
            if key not in mesh:
                continue
            values = np.asarray(mesh[key])
            other[key] = values[selected].tolist()
            mesh[key] = values[~selected].tolist()
        fresh.append(other)
    out["meshes"] += fresh
    return out


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
    """An open box is its own part: the top faces up and passes; the flipped top is flagged."""
    result = _hcheck({"meshes": [_box(drop_bottom=True)]})
    assert result["status"] == "pass" and result["value"] == 0
    assert _row(result, "box")["horizontal_faces"] == 2
    assert _row(result, "box")["inward_faces"] == 0
    flipped = _box(drop_bottom=True)
    _reverse(flipped["triangles"], 0)
    _reverse(flipped["triangles"], 1)
    bad = _hcheck({"meshes": [flipped]})
    assert bad["status"] == "fail" and bad["value"] == 2
    assert set(bad["details"]["inward_triangles"]) == {0, 1}


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


def _detached_reversed_soffit_dump():
    body = _box("body")
    body_v = (np.asarray(body["vertices"], float) * np.array([10.0, 10.0, 6.0])).tolist()
    over_v, over_t = _overhang_with_detached_bottom()
    base = len(body_v)
    mesh = {"name": "body", "vertices": body_v + over_v,
            "triangles": body["triangles"] + [[a + base, b + base, c + base] for a, b, c in over_t],
            "material_ids": [1] * (len(body["triangles"]) + len(over_t))}
    return {"meshes": [mesh]}


def test_detached_reversed_soffit_passes_orientation_but_fails_here():
    dump = _detached_reversed_soffit_dump()
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


def test_separate_roof_mesh_passes():
    result = _hcheck(_split({"meshes": [_box()]}, True))
    assert result["status"] == "pass" and result["value"] == 0
    assert result["details"]["volumes"] == [["box", "box_roof"]]


def test_separate_soffit_mesh_passes():
    result = _hcheck(_split({"meshes": [_box()]}, False))
    assert result["status"] == "pass" and result["value"] == 0
    assert result["details"]["volumes"] == [["box", "box_soffit"]]


def test_reversed_separate_soffit_fails():
    dump = _split({"meshes": [_box()]}, False)
    soffit = next(mesh for mesh in dump["meshes"] if mesh["name"] == "box_soffit")
    for index in range(len(soffit["triangles"])):
        _reverse(soffit["triangles"], index)
    result = _hcheck(dump)
    assert result["status"] == "fail" and result["value"] == 2
    assert _row(result, "box_soffit")["inward_faces"] == 2


def test_reversed_separate_roof_fails():
    dump = _split({"meshes": [_box()]}, True)
    roof = next(mesh for mesh in dump["meshes"] if mesh["name"] == "box_roof")
    for index in range(len(roof["triangles"])):
        _reverse(roof["triangles"], index)
    result = _hcheck(dump)
    assert result["status"] == "fail" and result["value"] == 2
    assert _row(result, "box_roof")["inward_faces"] == 2


@pytest.mark.parametrize("bench", _BENCHES)
@pytest.mark.parametrize("upward", [True, False])
def test_bench_partition_clean_and_reversed(bench, upward):
    _spec, dump, tol = _built(bench)
    split = _split(dump, upward)
    clean = checks.check_horizontal_faces(from_dump(split), tol)
    assert clean["status"] == "pass" and clean["value"] == 0
    suffix = "_roof" if upward else "_soffit"
    names = [mesh["name"] for mesh in split["meshes"] if mesh["name"].endswith(suffix)]
    assert len(names) == 1
    name = names[0]
    n_tri = len(next(mesh for mesh in split["meshes"] if mesh["name"] == name)["triangles"])
    assert n_tri > 1
    flipped = copy.deepcopy(split)
    target = next(mesh for mesh in flipped["meshes"] if mesh["name"] == name)
    for index in range(n_tri):
        _reverse(target["triangles"], index)
    result = checks.check_horizontal_faces(from_dump(flipped), tol)
    assert result["status"] == "fail" and result["value"] == n_tri
    one = copy.deepcopy(split)
    target = next(mesh for mesh in one["meshes"] if mesh["name"] == name)
    _reverse(target["triangles"], 0)
    result = checks.check_horizontal_faces(from_dump(one), tol)
    assert result["status"] == "fail" and result["value"] == 1


def test_decor_mesh_sharing_edge_stays_apart():
    body = _resize(_box("body"), 10.0)
    decor = _resize(_box("decor"), 10.0, (0.0, -10.0, 0.0))
    result = _hcheck({"meshes": [body, decor]})
    assert result["status"] == "pass" and result["value"] == 0
    assert result["details"]["volumes"] == [["body"], ["decor"]]
    decor_in = _resize(_box("decor", reverse=range(12)), 10.0, (0.0, -10.0, 0.0))
    bad = _hcheck({"meshes": [body, decor_in]})
    assert _row(bad, "decor")["inward_faces"] > 0
    assert _row(bad, "body")["inward_faces"] == 0
    assert bad["details"]["volumes"] == [["body"], ["decor"]]


def test_split_combined_with_enclosed_inner_box():
    body = _resize(_box("body"), 100.0)
    inner = _resize(_box("inner", reverse=range(12)), 0.2, (49.9, 49.9, 49.9))
    dump = _split({"meshes": [body]}, True)
    dump["meshes"].append(inner)
    result = _hcheck(dump)
    assert result["status"] == "fail"
    assert _row(result, "inner")["inward_faces"] == 4
    assert _row(result, "body")["inward_faces"] == 0
    assert _row(result, "body_roof")["inward_faces"] == 0


def test_split_combined_with_detached_soffit():
    result = _hcheck(_split(_detached_reversed_soffit_dump(), True))
    assert result["status"] == "fail" and result["value"] == 2


def _canonical_corners(dump):
    return sorted(tuple(c.ravel()) for c in from_dump(dump).corners())


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("roof_split", [False, True])
@pytest.mark.parametrize("offset", [0.0, 13.25, -101.75])
def test_detached_soffit_own_mesh_keeps_verdict(reverse, roof_split, offset):
    """SYNTHETIC. Moving the unwelded soffit into its own mesh keeps the joined-dump verdict."""
    dump = _detached_reversed_soffit_dump()
    mesh = dump["meshes"][0]
    picked = [12, 13]
    if not reverse:
        for i in picked:
            a, b, c = mesh["triangles"][i]
            mesh["triangles"][i] = [a, c, b]
    for one in dump["meshes"]:
        one["vertices"] = (np.asarray(one["vertices"]) + [offset, -offset, offset]).tolist()
    expected = 2 if reverse else 0
    baseline = checks.check_horizontal_faces(from_dump(dump), _TOL)
    assert baseline["value"] == expected
    out = copy.deepcopy(dump)
    main = out["meshes"][0]
    bottom = copy.deepcopy(main)
    bottom["name"] = "soffit"
    for key in ("triangles", "material_ids"):
        values = main[key]
        bottom[key] = [values[i] for i in picked]
        main[key] = [v for i, v in enumerate(values) if i not in picked]
    out["meshes"].append(bottom)
    if roof_split:
        out = _split(out, True)
    assert _canonical_corners(dump) == _canonical_corners(out)
    result = checks.check_horizontal_faces(from_dump(out), _TOL)
    assert result["value"] == expected
    assert result["status"] == ("fail" if expected else "pass")
    if reverse:
        # An upward soffit is what _split(..., True) moves into soffit_roof.
        holder = "soffit_roof" if roof_split else "soffit"
        assert _row(result, holder)["inward_faces"] == 2


def _random_partition(dump, seed):
    """SYNTHETIC. Scatter each non-UCX mesh's triangles across 2–5 meshes; keep ``decor`` whole."""
    rng = np.random.default_rng(seed)
    out = copy.deepcopy(dump)
    meshes = []
    for mesh in out["meshes"]:
        name = mesh["name"]
        if name.startswith("UCX_") or name == "decor" or len(mesh["triangles"]) == 0:
            meshes.append(mesh)
            continue
        n = len(mesh["triangles"])
        k = int(rng.integers(2, 6))
        assign = rng.integers(0, k, size=n)
        verts = mesh["vertices"]
        for part in range(k):
            chosen = np.flatnonzero(assign == part)
            if len(chosen) == 0:
                continue
            tris = [mesh["triangles"][int(i)] for i in chosen]
            used = sorted({int(p) for tri in tris for p in tri})
            remap = {old: new for new, old in enumerate(used)}
            piece = {
                "name": f"{name}_{part}",
                "vertices": [verts[i] for i in used],
                "triangles": [[remap[int(a)], remap[int(b)], remap[int(c)]] for a, b, c in tris]}
            if "material_ids" in mesh:
                mids = mesh["material_ids"]
                piece["material_ids"] = [mids[int(i)] for i in chosen]
            meshes.append(piece)
    out["meshes"] = meshes
    return out


_PARTITION_CASES = None


def _partition_cases():
    """SYNTHETIC dumps whose horizontal-face value a render-mesh partition must not change."""
    global _PARTITION_CASES
    if _PARTITION_CASES is not None:
        return _PARTITION_CASES
    reversed_dump = _detached_reversed_soffit_dump()
    corrected = copy.deepcopy(reversed_dump)
    corrected_mesh = corrected["meshes"][0]
    for index in (12, 13):
        a, b, c = corrected_mesh["triangles"][index]
        corrected_mesh["triangles"][index] = [a, c, b]
    cases = [
        ("detached_reversed", reversed_dump, _TOL),
        ("detached_corrected", corrected, _TOL)]
    for bench in _BENCHES:
        _spec, dump, tol = _built(bench)
        cases.append((f"{bench}_clean", dump, tol))
        broken = copy.deepcopy(dump)
        horiz, _nz, _cz = _horiz_axes(from_dump(broken))
        _flip_global(broken, [int(np.flatnonzero(horiz)[0])])
        cases.append((f"{bench}_one", broken, tol))
    _PARTITION_CASES = cases
    return cases


@pytest.mark.parametrize("seed", range(10))
def test_random_partition_keeps_verdict(seed):
    """SYNTHETIC. Random render-mesh partitions keep the unpartitioned horizontal-face value."""
    for label, dump, tol in _partition_cases():
        baseline = checks.check_horizontal_faces(from_dump(dump), tol)["value"]
        parted = checks.check_horizontal_faces(from_dump(_random_partition(dump, seed)), tol)
        assert parted["value"] == baseline, label


def _ground_span(reverse=False):
    """SYNTHETIC open quad, z=0, x and y from -5 to 15."""
    tris = [[0, 2, 1], [0, 3, 2]] if reverse else [[0, 1, 2], [0, 2, 3]]
    return {"name": "ground",
            "vertices": [[-5, -5, 0], [15, -5, 0], [15, 15, 0], [-5, 15, 0]],
            "triangles": tris, "material_ids": [1, 1]}


def _box_10x10x6():
    """SYNTHETIC closed outward box, x and y in [0, 10], height 6, own vertices."""
    box = _box("box")
    box["vertices"] = (np.asarray(box["vertices"], float) * np.array([10.0, 10.0, 6.0])).tolist()
    return box


def test_open_ground_sheet_under_closed_box():
    """SYNTHETIC. An open sheet and a closed box are two contexts; the sheet does not see the box."""
    clean = _hcheck({"meshes": [_ground_span(), _box_10x10x6()]})
    assert clean["status"] == "pass" and clean["value"] == 0
    assert clean["details"]["volumes"] == [["ground"], ["box"]]
    bad = _hcheck({"meshes": [_ground_span(reverse=True), _box_10x10x6()]})
    assert bad["status"] == "fail" and bad["value"] == 2
    assert _row(bad, "ground")["inward_faces"] == 2
    assert _row(bad, "box")["inward_faces"] == 0
    assert bad["details"]["volumes"] == [["ground"], ["box"]]


def _move_picked_to(dump, picked, name):
    """SYNTHETIC. Move global triangles of the first mesh into a new mesh; coordinates unchanged."""
    out = copy.deepcopy(dump)
    main = out["meshes"][0]
    moved = copy.deepcopy(main)
    moved["name"] = name
    for key in ("triangles", "material_ids"):
        values = main[key]
        moved[key] = [values[i] for i in picked]
        main[key] = [v for i, v in enumerate(values) if i not in picked]
    out["meshes"].append(moved)
    return out


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("partition", [False, True])
@pytest.mark.parametrize("offset", [0.0, 13.25, -101.75])
def test_stacked_open_boxes_are_independent(reverse, partition, offset):
    lower = _box("lower", drop_bottom=True)
    if reverse:
        for index in (0, 1):
            _reverse(lower["triangles"], index)
    upper = _resize(_box("upper", drop_bottom=True), 1.0, (0, 0, 2))
    dump = _map_vertices({"meshes": [lower, upper]}, lambda v: v + [offset, -offset, offset])
    if partition:
        dump = _random_partition(dump, 56)
    result = _hcheck(dump)
    assert result["value"] == (2 if reverse else 0)


@pytest.mark.parametrize("bench", _BENCHES)
@pytest.mark.parametrize("reverse", [False, True])
def test_ground_below_open_bench_is_independent(bench, reverse):
    _, dump, tol = _built(bench)
    dump = _split(dump, True)
    corners = from_dump(dump).corners()
    lo, hi = corners.min(axis=(0, 1)), corners.max(axis=(0, 1))
    ground = _sheet(reverse)
    ground["vertices"] = [[lo[0]-1, lo[1]-1, lo[2]-1], [hi[0]+1, lo[1]-1, lo[2]-1],
                          [hi[0]+1, hi[1]+1, lo[2]-1], [lo[0]-1, hi[1]+1, lo[2]-1]]
    dump["meshes"].append(ground)
    result = checks.check_horizontal_faces(from_dump(dump), tol)
    assert result["value"] == (2 if reverse else 0)
    assert _row(result, "ground")["inward_faces"] == (2 if reverse else 0)


@pytest.mark.parametrize("dz", [-0.0101, -0.01, -0.0099, 0.0, 0.0099, 0.01, 0.0101])
@pytest.mark.parametrize("reverse", [False, True])
def test_cap_join_distance_bound(dz, reverse):
    cap = _sheet(reverse=not reverse)  # correct cap points down; reversed points up
    cap["name"] = "cap"
    cap["vertices"] = (np.asarray(cap["vertices"]) * [0.8, 0.8, 1] + [0.1, 0.1, dz]).tolist()
    result = _hcheck({"meshes": [_box("owner", drop_bottom=True), cap]})
    joined = abs(dz) <= 0.01
    assert result["value"] == (2 if reverse == joined else 0)
    assert result["details"]["volumes"] == ([["owner", "cap"]] if joined else [["owner"], ["cap"]])


def _open_prism(polygon):
    """SYNTHETIC open-bottom prism, including concave outlines/courtyard holes."""
    import shapely
    vertices, triangles = [], []
    def tri(coords):
        base = len(vertices)
        vertices.extend(coords)
        triangles.append([base, base + 1, base + 2])
    for face in shapely.get_parts(shapely.constrained_delaunay_triangles(polygon)):
        coords = np.asarray(face.exterior.coords)[:3, :2]
        if np.cross(np.append(coords[1]-coords[0], 0), np.append(coords[2]-coords[0], 0))[2] < 0:
            coords = coords[::-1]
        tri([[x, y, 1] for x, y in coords])
    for ring in [polygon.exterior, *polygon.interiors]:
        xy = list(ring.coords)
        for (x, y), (xx, yy) in zip(xy, xy[1:]):
            tri([[x, y, 0], [xx, yy, 0], [xx, yy, 1]])
            tri([[x, y, 0], [xx, yy, 1], [x, y, 1]])
    return {"name": "owner", "vertices": vertices, "triangles": triangles,
            "material_ids": [1] * len(triangles)}


@pytest.mark.parametrize("case", ["outside", "concave_bridge", "hole", "inside_annulus"])
def test_cap_outside_footprint_stays_independent(case):
    import shapely
    if case == "concave_bridge":
        polygon = shapely.Polygon([(0,0), (3,0), (3,3), (2,3), (2,1), (1,1), (1,3), (0,3)])
        xy = [[0.5,2.5], [1.5,0.5], [2.5,2.5]]  # CCW vertices inside; face crosses notch
    elif case in ("hole", "inside_annulus"):
        polygon = shapely.Polygon([(0,0), (4,0), (4,4), (0,4)],
                                  [[(1,1), (1,3), (3,3), (3,1)]])
        xy = [[1.2,1.2], [2.8,1.2], [2,2.8]] if case == "hole" else [[0.1,0.1], [0.9,0.1], [0.1,0.9]]
    else:
        polygon = shapely.box(0, 0, 1, 1)
        xy = [[0.2,0.2], [1.2,0.2], [0.2,0.8]]
    cap = {"name": "cap", "vertices": [[x,y,0] for x,y in xy],
           "triangles": [[0,2,1]], "material_ids": [1]}
    result = _hcheck({"meshes": [_open_prism(polygon), cap]})
    joined = case == "inside_annulus"
    assert result["value"] == (0 if joined else 1)
    assert result["details"]["volumes"] == ([["owner", "cap"]] if joined else [["owner"], ["cap"]])


@pytest.mark.parametrize("seed", range(20))
def test_combined_cap_context_probe(seed):
    """SYNTHETIC generated probe: partitions, transform, independent shells and per-call resets."""
    rng = np.random.default_rng(seed + 5600)
    base = _detached_reversed_soffit_dump()
    stack = _box("stack", drop_bottom=True)
    stack["vertices"] = (np.asarray(stack["vertices"]) * [10, 2, 1] + [0, 10, 8]).tolist()
    base["meshes"] += [stack,
                       _resize(_box("inner", reverse=range(12)), .2, (1, 1, 1)),
                       _resize(_box("decor", reverse=range(12)), .2, (2, 2, 2)),
                       _resize(_sheet(), 20, (-5, -5, -1))]
    angle = rng.uniform(-np.pi, np.pi)
    c, s = np.cos(angle), np.sin(angle)
    rotation = np.array([[c,-s,0], [s,c,0], [0,0,1]])
    offset = rng.uniform(-500, 500, 3)
    base = _map_vertices(base, lambda v: v @ rotation.T + offset)
    base = _random_partition(base, seed)
    rng.shuffle(base["meshes"])
    # Detached upward soffit 2 + reversed enclosed shell 4 + reversed decor 4.
    model = from_dump(base)
    horizontal, _, z = _horiz_axes(model)
    inverted = np.array([name.startswith(("inner", "decor")) for name in model.mesh_names])
    expected_wrong = np.flatnonzero(horizontal & (inverted[model.mesh_index] | np.isclose(z, 3 + offset[2], rtol=0, atol=1e-8))).tolist()
    result = _hcheck(base)
    assert result["value"] == 10
    assert result["details"]["inward_triangles"] == expected_wrong
    one = copy.deepcopy(base)
    model = from_dump(one)
    ground_meshes = [i for i, name in enumerate(model.mesh_names) if name.startswith("ground")]
    index = int(rng.choice(np.flatnonzero(np.isin(model.mesh_index, ground_meshes))))
    _flip_global(one, [index])
    assert _hcheck(one)["value"] == 11
    assert _hcheck(base)["value"] == 10  # no state survives the previous input
    base["meshes"].reverse()
    assert _hcheck(base)["value"] == 10


def test_open_fragment_does_not_see_decor():
    """SYNTHETIC. A quad moved into decor is judged without the body roof.

    Downward and alone, nothing is above it, so it is flagged. The same quad facing up passes.
    The body stays outward. The closed box and the open overhang keep separate index components:
    they only meet on a non-manifold welded edge, so they are two contexts of one render mesh.
    """
    picked = [12, 13]
    corrected = _detached_reversed_soffit_dump()
    mesh = corrected["meshes"][0]
    for index in picked:
        a, b, c = mesh["triangles"][index]
        mesh["triangles"][index] = [a, c, b]
    down = _hcheck(_move_picked_to(corrected, picked, "decor"))
    assert down["status"] == "fail" and down["value"] == 2
    assert _row(down, "decor")["inward_faces"] == 2
    assert _row(down, "body")["inward_faces"] == 0
    assert down["details"]["volumes"] == [["body"], ["body"], ["decor"]]
    up = _hcheck(_move_picked_to(_detached_reversed_soffit_dump(), picked, "decor"))
    assert up["status"] == "pass" and up["value"] == 0
    assert _row(up, "body")["inward_faces"] == 0
    assert up["details"]["volumes"] == [["body"], ["body"], ["decor"]]


def _extruded_step(cut):
    """SYNTHETIC closed outward prism. XZ profile extruded across y=0..1.

    Caps are four triangles each (indices 0..7). Bottom quads are indices 8 and 9:
    8 has centroid x=2/3, 9 has centroid x=1/3. A cut at 1/3 aligns a vertical wall
    with triangle 9; a cut at 2/3 aligns it with triangle 8.
    """
    profile = [(0.0, 0.0), (1.0, 0.0), (1.0, 2.0), (float(cut), 2.0), (float(cut), 1.0), (0.0, 1.0)]
    n = len(profile)
    verts = [[x, 0.0, z] for x, z in profile] + [[x, 1.0, z] for x, z in profile]
    cap = [(0, 4, 5), (0, 1, 4), (1, 3, 4), (1, 2, 3)]
    # Profile is CCW in XZ: the y=0 cap faces -Y and the y=1 cap faces +Y.
    tris = [[a, b, c] for a, b, c in cap]
    tris += [[a + n, c + n, b + n] for a, b, c in cap]
    tris.append([0, n + 1, 1])
    tris.append([0, n, n + 1])
    xyz = np.asarray(verts, float)
    for i in range(1, n):
        j = (i + 1) % n
        dx = profile[j][0] - profile[i][0]
        dz = profile[j][1] - profile[i][1]
        outward = np.array([dz, 0.0, -dx])
        candidates = ([i, j, i + n], [j, j + n, i + n])
        corner = xyz[candidates[0]]
        if np.cross(corner[1] - corner[0], corner[2] - corner[0]) @ outward < 0:
            candidates = ([i, i + n, j], [j, i + n, j + n])
        tris.extend(candidates)
    return {"name": "step", "vertices": verts, "triangles": tris, "material_ids": [1] * len(tris)}


def test_boundary_aligned_ray_closed_step_clean_and_flipped():
    """Round-4 P1: a +Z ray along a vertical wall must not invert a closed face."""
    clean = _hcheck({"meshes": [_extruded_step(1 / 3)]})
    assert clean["status"] == "pass" and clean["value"] == 0
    assert clean["details"]["inward_triangles"] == []
    flipped = {"meshes": [_extruded_step(1 / 3)]}
    _reverse(flipped["meshes"][0]["triangles"], 9)
    bad = _hcheck(flipped)
    assert bad["status"] == "fail" and bad["value"] == 1
    assert bad["details"]["inward_triangles"] == [9]
    mirrored = {"meshes": [_extruded_step(2 / 3)]}
    assert _hcheck(mirrored)["value"] == 0
    _reverse(mirrored["meshes"][0]["triangles"], 8)
    mirrored_bad = _hcheck(mirrored)
    assert mirrored_bad["status"] == "fail" and mirrored_bad["value"] == 1
    assert mirrored_bad["details"]["inward_triangles"] == [8]


@pytest.mark.parametrize("cut", [0.3, 0.7, 1 / 3 + 1e-5, 1 / 3 - 1e-5])
def test_boundary_ray_offset_controls_pass(cut):
    result = _hcheck({"meshes": [_extruded_step(cut)]})
    assert result["status"] == "pass" and result["value"] == 0
    assert result["details"]["inward_triangles"] == []


def _open_top(name="wall"):
    mesh = _box(name)
    keep = [i for i in range(len(mesh["triangles"])) if i not in (2, 3)]
    mesh["triangles"] = [mesh["triangles"][i] for i in keep]
    mesh["material_ids"] = [1] * len(mesh["triangles"])
    return mesh


def _ledge_cap(dz, upward):
    cap = _sheet(reverse=not upward)
    cap["name"] = "cap"
    cap["vertices"] = (np.asarray(cap["vertices"], float) * [0.8, 0.8, 1] + [0.1, 0.1, 1.0 + dz]).tolist()
    return cap


@pytest.mark.parametrize("dz", [-0.0101, -0.01, -0.0099, 0.0, 0.0099, 0.01, 0.0101])
def test_ledge_cap_joins_only_within_one_centimetre(dz):
    """A ledge cap faces up, away from the wall below. Joined within 0.01 m; farther stays independent."""
    joined = abs(dz) <= 0.01
    up = _hcheck({"meshes": [_open_top(), _ledge_cap(dz, True)]})
    down = _hcheck({"meshes": [_open_top(), _ledge_cap(dz, False)]})
    if joined:
        assert up["status"] == "pass" and up["value"] == 0
        assert up["details"]["volumes"] == [["wall", "cap"]]
        assert down["status"] == "fail" and down["value"] == 2
        assert _row(down, "cap")["inward_faces"] == 2
        assert _row(down, "wall")["inward_faces"] == 0
        assert down["details"]["volumes"] == [["wall", "cap"]]
    else:
        assert up["details"]["volumes"] == [["wall"], ["cap"]]
        assert down["details"]["volumes"] == [["wall"], ["cap"]]
        assert _row(up, "cap")["inward_faces"] == 0
        assert _row(down, "cap")["inward_faces"] == 2
        assert _row(up, "wall")["inward_faces"] == _row(down, "wall")["inward_faces"]


def test_cap_tol_sweep_and_exact_threshold():
    """Generated distances around 0.01 m. Exact 0.01 m joins; a flipped cap there fails, never a silent pass."""
    rng = np.random.default_rng(314)
    distances = np.unique(np.concatenate([
        np.array([0.0, 0.01, -0.01, 0.0100000001, -0.0100000001]),
        rng.uniform(0.0, 0.009, size=15),
        rng.uniform(0.0101, 0.08, size=15),
    ]))
    for dz in distances:
        joined = abs(float(dz)) <= 0.01
        clean = _hcheck({"meshes": [_box("owner", drop_bottom=True), _sheet_at(dz, downward=True)]})
        flipped = _hcheck({"meshes": [_box("owner", drop_bottom=True), _sheet_at(dz, downward=False)]})
        assert clean["status"] != "not_run" and flipped["status"] != "not_run"
        assert clean["details"]["volumes"] == ([["owner", "cap"]] if joined else [["owner"], ["cap"]])
        if joined:
            assert flipped["status"] == "fail"          # flipped (up) cap joined -> inward
            assert clean["status"] == "pass" and clean["value"] == 0
        else:
            assert _row(clean, "cap")["inward_faces"] == 2    # down detached -> inward (standalone-down)
            assert _row(flipped, "cap")["inward_faces"] == 0  # up detached -> outward (standalone-up)
            assert _row(flipped, "owner")["inward_faces"] == _row(clean, "owner")["inward_faces"] == 0


def _sheet_at(dz, downward):
    cap = _sheet(reverse=downward)
    cap["name"] = "cap"
    cap["vertices"] = (np.asarray(cap["vertices"], float) * [0.8, 0.8, 1] + [0.1, 0.1, dz]).tolist()
    return cap


def test_touching_unwelded_open_boxes_do_not_share_a_verdict():
    """Boxes almost touch, farther apart than weld_m, so a flipped top does not condemn its neighbour."""
    gap = WELD_M + 1e-4
    lower = _box("lower", drop_bottom=True)
    upper = _resize(_box("upper", drop_bottom=True), 1.0, (0.0, 0.0, 1.0 + gap))
    clean = _hcheck({"meshes": [lower, upper]})
    assert clean["status"] == "pass" and clean["value"] == 0
    assert clean["details"]["volumes"] == [["lower"], ["upper"]]
    bad_lower = _box("lower", drop_bottom=True)
    _reverse(bad_lower["triangles"], 0)
    _reverse(bad_lower["triangles"], 1)
    result = _hcheck({"meshes": [bad_lower, upper]})
    assert result["status"] == "fail" and result["value"] == 2
    assert _row(result, "lower")["inward_faces"] == 2
    assert _row(result, "upper")["inward_faces"] == 0
    assert result["details"]["volumes"] == [["lower"], ["upper"]]


@pytest.mark.parametrize("seed", range(8))
def test_triangle_permutation_keeps_inward_count(seed):
    rng = np.random.default_rng(1000 + seed)
    dump = _detached_reversed_soffit_dump()
    baseline = _hcheck(dump)["value"]
    mesh = dump["meshes"][0]
    order = rng.permutation(len(mesh["triangles"]))
    mesh["triangles"] = [mesh["triangles"][int(i)] for i in order]
    mesh["material_ids"] = [mesh["material_ids"][int(i)] for i in order]
    assert _hcheck(dump)["value"] == baseline


def test_fail_closed_empty_degenerate_and_nonfinite():
    empty = _hcheck({"meshes": []})
    assert empty["status"] == "not_measured" and empty["value"] is None
    collapsed = {"name": "deg", "vertices": [[0, 0, 0], [0, 0, 0], [1, 0, 0], [0, 1, 0]],
                 "triangles": [[0, 1, 2], [0, 0, 0]], "material_ids": [1, 1]}
    degenerate = _hcheck({"meshes": [collapsed]})
    assert degenerate["status"] in ("not_measured", "fail") and degenerate["status"] != "pass"
    for bad_value in (np.nan, np.inf, -np.inf):
        verts = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        verts[0][2] = bad_value
        mesh = {"name": "bad", "vertices": verts, "triangles": [[0, 1, 2], [0, 2, 3]], "material_ids": [1, 1]}
        result = _hcheck({"meshes": [mesh]})
        assert result["status"] in ("not_measured", "fail")
        assert result["status"] != "pass"
        assert result["value"] in (None,) or (isinstance(result["value"], (int, float)) and result["value"] != 0) or result["status"] == "not_measured"


def test_partial_index_input_errors_instead_of_passing():
    with pytest.raises((IndexError, ValueError)):
        _hcheck({"meshes": [{"name": "partial", "vertices": [[0, 0, 0], [1, 0, 0]],
                             "triangles": [[0, 1, 2]], "material_ids": [1]}]})


@pytest.mark.parametrize("upward", [False, True])
def test_detached_soffit_under_closed_slab(upward):
    """SYNTHETIC. A detached sheet under a closed slab faces down, away from that solid."""
    slab = _resize(_box("slab"), 1.0, (0, 0, 1))
    soffit = _sheet(reverse=not upward)
    soffit["name"] = "soffit"
    soffit["vertices"] = [[.1 + .8 * x, .1 + .8 * y, .5] for x, y, z in soffit["vertices"]]
    result = _hcheck({"meshes": [slab, soffit]})
    assert result["details"]["inward_triangles"] == ([12, 13] if upward else [])
    assert result["status"] == ("fail" if upward else "pass")


@pytest.mark.parametrize("gap", [0, .0001, .01])
def test_independent_open_parts(gap):
    """SYNTHETIC. Touching unwelded open boxes keep two contexts, including inside weld_m."""
    lower = _box("lower", drop_bottom=True)
    upper = _resize(_box("upper", drop_bottom=True), 1, (0, 0, 1 + gap))
    result = _hcheck({"meshes": [lower, upper]})
    assert result["details"]["volumes"] == [["lower"], ["upper"]]
    assert result["status"] == "pass" and result["value"] == 0


def test_open_part_gap_sweep_never_shares_a_verdict():
    """SYNTHETIC. Gaps through weld_m and the 1 cm band never merge two open boxes.

    Exactly weld_m and exactly 0.01 m stay independent. A flipped neighbour fails alone.
    """
    gaps = [0.0, 1e-6, 1e-4, WELD_M / 2, WELD_M, WELD_M + 1e-9, 0.009, 0.01, 0.0101]
    for gap in gaps:
        lower = _box("lower", drop_bottom=True)
        upper = _resize(_box("upper", drop_bottom=True), 1, (0, 0, 1 + gap))
        clean = _hcheck({"meshes": [lower, upper]})
        assert clean["status"] == "pass" and clean["value"] == 0, gap
        assert clean["details"]["volumes"] == [["lower"], ["upper"]], gap
        assert clean["status"] != "not_run"
        bad_lower = _box("lower", drop_bottom=True)
        _reverse(bad_lower["triangles"], 0)
        _reverse(bad_lower["triangles"], 1)
        result = _hcheck({"meshes": [bad_lower, upper]})
        assert result["status"] == "fail" and result["value"] == 2, gap
        assert _row(result, "lower")["inward_faces"] == 2
        assert _row(result, "upper")["inward_faces"] == 0
        assert result["details"]["volumes"] == [["lower"], ["upper"]]


def _combine_parts(parts):
    """One render mesh, separate vertex indices. SYNTHETIC fixture helper."""
    out = copy.deepcopy(parts[0])
    out["name"] = "combined"
    for part in parts[1:]:
        offset = len(out["vertices"])
        out["vertices"] += copy.deepcopy(part["vertices"])
        out["triangles"] += [[v + offset for v in tri] for tri in part["triangles"]]
        out["material_ids"] += list(part["material_ids"])
    return out


@pytest.mark.parametrize("gap", [0, .0001, .01])
@pytest.mark.parametrize("flipped", [False, True])
@pytest.mark.parametrize("combine", [False, True])
def test_unwelded_parts_keep_identity(gap, flipped, combine):
    """SYNTHETIC Acceptance rows. Same geometry, one render mesh or two.

    | gap (m) | flipped | combine | contexts | status | inward |
    | 0, 0.0001, 0.01 | no | no or yes | 2 | pass | [] |
    | 0, 0.0001, 0.01 | yes | no or yes | 2 | fail | [0, 1] |

    Gap 0 and 0.0001 touch inside weld. Gap 0.01 is the cap-join threshold and still
    leaves two open boxes apart. Render-mesh membership does not share the verdict.
    """
    a = _box("lower", drop_bottom=True)
    b = _resize(_box("upper", drop_bottom=True), 1, (0, 0, 1 + gap))
    if flipped:
        _reverse(a["triangles"], 0)
        _reverse(a["triangles"], 1)
    if combine:
        offset = len(a["vertices"])
        a["vertices"] += copy.deepcopy(b["vertices"])
        a["triangles"] += [[v + offset for v in t] for t in b["triangles"]]
        a["material_ids"] += b["material_ids"]
        a["name"] = "combined"
        meshes = [a]
    else:
        meshes = [a, b]
    result = _hcheck({"meshes": meshes})
    assert result["status"] == ("fail" if flipped else "pass"), result
    assert result["value"] == (2 if flipped else 0), result
    assert result["details"]["inward_triangles"] == ([0, 1] if flipped else []), result
    assert len(result["details"]["volumes"]) == 2, result


@pytest.mark.parametrize("seed", range(16))
def test_combined_touching_permutation_keeps_two_contexts(seed):
    """SYNTHETIC probe. Touching unwelded parts in one mesh keep two contexts under reorder."""
    rng = np.random.default_rng(9000 + seed)
    gap = float(rng.choice([0.0, 1e-4]))
    flipped = bool(rng.integers(0, 2))
    lower = _box("lower", drop_bottom=True)
    upper = _resize(_box("upper", drop_bottom=True), 1, (0, 0, 1 + gap))
    if flipped:
        _reverse(lower["triangles"], 0)
        _reverse(lower["triangles"], 1)
    first_upper = bool(rng.integers(0, 2))
    parts = [upper, lower] if first_upper else [lower, upper]
    mesh = _combine_parts(parts)
    offset = len(upper["vertices"]) if first_upper else 0
    bad = {tuple(v + offset for v in lower["triangles"][i]) for i in (0, 1)} if flipped else set()
    order = rng.permutation(len(mesh["triangles"]))
    mesh["triangles"] = [mesh["triangles"][int(i)] for i in order]
    mesh["material_ids"] = [mesh["material_ids"][int(i)] for i in order]
    result = _hcheck({"meshes": [mesh]})
    assert len(result["details"]["volumes"]) == 2, (gap, flipped, result)
    assert result["status"] == ("fail" if flipped else "pass"), result
    assert result["value"] == (2 if flipped else 0), result
    found = {tuple(mesh["triangles"][i]) for i in result["details"]["inward_triangles"]}
    assert found == bad, result


def test_combined_mesh_cap_join_matches_separate_meshes():
    """SYNTHETIC probe. Exact 0.01 m cap join, and a sweep around it, is unchanged in one mesh."""
    rng = np.random.default_rng(314)
    distances = np.unique(np.concatenate([
        np.array([0.0, 0.01, -0.01, 0.0099, 0.0101, 0.0100000001, -0.0100000001]),
        rng.uniform(-0.009, 0.009, size=8),
        rng.uniform(0.0101, 0.05, size=8),
        rng.uniform(-0.05, -0.0101, size=8),
    ]))
    for dz in distances:
        for upward in (True, False):
            wall = _open_top()
            cap = _ledge_cap(float(dz), upward)
            separate = _hcheck({"meshes": [copy.deepcopy(wall), copy.deepcopy(cap)]})
            combined = _hcheck({"meshes": [_combine_parts([wall, cap])]})
            joined = abs(float(dz)) <= 0.01
            assert combined["status"] == separate["status"], (float(dz), upward, combined, separate)
            assert combined["value"] == separate["value"], (float(dz), upward)
            assert len(combined["details"]["volumes"]) == len(separate["details"]["volumes"])
            assert len(combined["details"]["volumes"]) == (1 if joined else 2), (float(dz), upward)
            assert combined["status"] != "not_run"


def test_combined_mesh_collapsed_part_never_passes():
    """SYNTHETIC. A collapsed face in one unwelded part of a combined mesh is not a pass.

    The collapsed welded edge is skipped in ``_regroup_open_part``, so it cannot glue the
    clean neighbour into a silent certificate.
    """
    good = _box("lower", drop_bottom=True)
    bad = _resize(_box("upper", drop_bottom=True), 1, (0, 0, 1))
    bad["triangles"][0] = [4, 4, 4]
    result = _hcheck({"meshes": [_combine_parts([good, bad])]})
    assert result["status"] != "pass"
    assert result["value"] != 0
    assert len(result["details"]["volumes"]) == 2


def _outward_step(cut):
    """SYNTHETIC closed outward step. XZ profile, extruded across y, CCW caps face outward."""
    import shapely
    polygon = shapely.Polygon([(0, 0), (1, 0), (1, 2), (cut, 2), (cut, 1), (0, 1)])
    vertices, triangles = [], []

    def add(coords, desired):
        c = np.asarray(coords, float)
        if np.cross(c[1] - c[0], c[2] - c[0]) @ desired < 0:
            c = c[::-1]
        base = len(vertices)
        vertices.extend(c.tolist())
        triangles.append([base, base + 1, base + 2])

    for face in shapely.get_parts(shapely.constrained_delaunay_triangles(polygon)):
        for y in (0, 1):
            add([[x, y, z] for x, z in list(face.exterior.coords)[:3]], [0, 2 * y - 1, 0])
    ring = list(polygon.exterior.coords)
    for (x, z), (xx, zz) in zip(ring, ring[1:]):
        q = [[x, 0, z], [xx, 0, zz], [xx, 1, zz], [x, 1, z]]
        add([q[0], q[1], q[2]], [zz - z, 0, -(xx - x)])
        add([q[0], q[2], q[3]], [zz - z, 0, -(xx - x)])
    return {"name": "step", "vertices": vertices, "triangles": triangles,
            "material_ids": [1] * len(triangles)}


@pytest.mark.parametrize("scale,flipped", [
    (1, False), (1, True), (10, False), (10, True), (100, False), (100, True),
])
def test_closed_step_scale_invariance(scale, flipped):
    """SYNTHETIC. A vertical-wall ray keeps its parity when the solid is scaled."""
    mesh = _outward_step(1 / 3)
    mesh["vertices"] = (np.asarray(mesh["vertices"]) * scale).tolist()
    model = from_dump({"meshes": [mesh]})
    edges, counts, _sides = edge_uses(model.triangles, weld(model.vertices, .002))
    assert np.all(counts == 2) and np.all(edges[:, 0] != edges[:, 1])
    corners = model.corners()
    volume = np.einsum("ij,ij->i", corners[:, 0], np.cross(corners[:, 1], corners[:, 2])).sum() / 6
    assert volume == pytest.approx((2 - 1 / 3) * scale ** 3)
    if flipped:
        _reverse(mesh["triangles"], 9)
    result = _hcheck({"meshes": [mesh]})
    assert result["details"]["inward_triangles"] == ([9] if flipped else [])
    assert result["status"] == ("fail" if flipped else "pass")


@pytest.mark.parametrize("scale", [1, 3, 10, 30, 100])
def test_closed_step_scale_sweep(scale):
    """SYNTHETIC sweep. Clean stays pass and a flipped bottom stays fail at every scale."""
    mesh = _outward_step(1 / 3)
    mesh["vertices"] = (np.asarray(mesh["vertices"]) * scale).tolist()
    clean = _hcheck({"meshes": [mesh]})
    assert clean["status"] == "pass" and clean["value"] == 0
    flipped = {"meshes": [_outward_step(1 / 3)]}
    flipped["meshes"][0]["vertices"] = (np.asarray(flipped["meshes"][0]["vertices"]) * scale).tolist()
    _reverse(flipped["meshes"][0]["triangles"], 9)
    bad = _hcheck(flipped)
    assert bad["status"] == "fail" and bad["value"] == 1
    assert bad["details"]["inward_triangles"] == [9]
    assert bad["status"] != "not_run"


def test_sheet_between_two_closed_solids_is_not_a_clean_pass():
    """SYNTHETIC. A sheet covered from above and from below has no single owner side."""
    below = _resize(_box("below"), 1.0, (0, 0, -2))
    above = _resize(_box("above"), 1.0, (0, 0, 1))
    sheet = _sheet()
    sheet["name"] = "sheet"
    sheet["vertices"] = [[.1 + .8 * x, .1 + .8 * y, .5] for x, y, z in sheet["vertices"]]
    result = _hcheck({"meshes": [below, above, sheet]})
    assert result["status"] != "pass"
    assert set(result["details"]["inward_triangles"]) >= {24, 25}


def test_partial_degenerate_is_not_a_clean_certificate():
    """SYNTHETIC. One collapsed triangle beside a valid quad is not a clean pass."""
    mesh = _sheet()
    mesh["vertices"].append([9, 9, 9])
    mesh["triangles"].append([4, 4, 4])
    mesh["material_ids"].append(1)
    result = _hcheck({"meshes": [mesh]})
    assert result["status"] != "pass"
