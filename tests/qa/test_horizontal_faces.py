"""Horizontal-face orientation (issue #56). Every fixture is SYNTHETIC test data, not a real object."""
import copy

import numpy as np
import pytest

from test_orientation import WELD_M, _box, _built, _resize, _reverse
from twinqa.geometry import checks
from twinqa.geometry.mesh import from_dump

_BENCHES = ["bench-b01-box", "bench-b02-corner-niche", "bench-b02t-terrace"]
_TOL = {"weld_m": WELD_M}


_PARTITION_CASES = None

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
    """Open components are outside #56, not an outward-normal certificate."""
    result = _hcheck({"meshes": [_box(drop_bottom=True)]})
    assert result["status"] == "not_measured" and result["value"] is None
    assert result["details"]["not_checked_triangles"] == list(range(10))
    assert result["details"]["not_checked_reason"] == "not checked (see #314)"

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
    # Historical A4 is now explicitly outside the narrowed contract, in either winding.
    dump = _detached_reversed_soffit_dump()
    assert checks.check_orientation(from_dump(dump), _TOL)["status"] == "pass"
    _assert_not_checked(_hcheck(dump), from_dump(dump))

@pytest.mark.parametrize("bench", _BENCHES)
def test_bench_step_ledge_and_window_head_reversed_fail(bench):
    # These engine bodies have intentional open inset joints; #314 owns their normals.
    spec, dump, tol = _built(bench)
    model = from_dump(dump)
    _assert_not_checked(_hcheck(dump, tol), model)
    horizontal, _, _ = _horiz_axes(model)
    _flip_global(dump, np.flatnonzero(horizontal))
    _assert_not_checked(_hcheck(dump, tol), from_dump(dump))
    report = checks.run(model, model, spec, tol)
    assert "horizontal_faces" in report["not_measured"] and not report["passed"]

@pytest.mark.parametrize("bench", _BENCHES)
def test_every_single_reversed_horizontal_face_is_flagged(bench):
    _, dump, tol = _built(bench)
    horizontal, _, _ = _horiz_axes(from_dump(dump))
    for index in np.flatnonzero(horizontal):
        trial = copy.deepcopy(dump)
        _flip_global(trial, [index])
        _assert_not_checked(_hcheck(trial, tol), from_dump(trial))

def _map_vertices(dump, fn):
    out = copy.deepcopy(dump)
    for mesh in out["meshes"]:
        mesh["vertices"] = fn(np.asarray(mesh["vertices"], float)).tolist()
    return out

def test_rigid_transform_keeps_clean_bench_clean():
    # Closed controls retain outward parity under Z rotation + translation, mirror reverses it.
    angle = np.deg2rad(37)
    c, s = np.cos(angle), np.sin(angle)
    rotation = np.array([[c,-s,0], [s,c,0], [0,0,1]])
    dump = _map_vertices({"meshes": [_box()]}, lambda v: v @ rotation.T + [123.4,-56.7,8.9])
    assert _hcheck(dump)["value"] == 0
    mirrored = _map_vertices(dump, lambda v: v * [-1,1,1])
    assert _hcheck(mirrored)["value"] == 4

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
    for reverse in (False, True):
        dump = {"meshes": [_sheet(reverse)]}
        _assert_not_checked(_hcheck(dump), from_dump(dump))

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
    _, dump, tol = _built(bench)
    split = _split(dump, upward)
    _assert_not_checked(_hcheck(split, tol), from_dump(split))
    horizontal, _, _ = _horiz_axes(from_dump(split))
    _flip_global(split, np.flatnonzero(horizontal))
    _assert_not_checked(_hcheck(split, tol), from_dump(split))

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
    dump = _split(_detached_reversed_soffit_dump(), True)
    _assert_not_checked(_hcheck(dump), from_dump(dump))

def _canonical_corners(dump):
    return sorted(tuple(c.ravel()) for c in from_dump(dump).corners())

@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("roof_split", [False, True])
@pytest.mark.parametrize("offset", [0.0, 13.25, -101.75])
def test_detached_soffit_own_mesh_keeps_verdict(reverse, roof_split, offset):
    dump = _detached_reversed_soffit_dump()
    if not reverse:
        _flip_global(dump, [12,13])
    dump = _map_vertices(dump, lambda v: v + [offset,-offset,offset])
    out = _move_picked_to(dump, [12,13], "soffit")
    if roof_split:
        out = _split(out, True)
    assert _canonical_corners(dump) == _canonical_corners(out)
    _assert_not_checked(_hcheck(dump), from_dump(dump))
    _assert_not_checked(_hcheck(out), from_dump(out))

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
    for reverse in (False, True):
        result = _hcheck({"meshes": [_ground_span(reverse), _box_10x10x6()]})
        assert result["status"] == "pass" and result["value"] == 0
        assert result["details"]["coverage"] == "partial"
        assert result["details"]["not_checked_triangles"] == [0,1]
        assert result["details"]["checked_triangles"] == list(range(2,14))
        assert result["details"]["volumes"] == [["box"]]
        assert _row(result, "ground")["horizontal_faces"] == 0

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
        for index in (0,1):
            _reverse(lower["triangles"], index)
    upper = _resize(_box("upper", drop_bottom=True), 1, (0,0,2))
    dump = _map_vertices({"meshes": [lower,upper]}, lambda v: v + [offset,-offset,offset])
    if partition:
        dump = _random_partition(dump, 56)
    _assert_not_checked(_hcheck(dump), from_dump(dump))

@pytest.mark.parametrize("bench", _BENCHES)
@pytest.mark.parametrize("reverse", [False, True])
def test_ground_below_open_bench_is_independent(bench, reverse):
    _, dump, tol = _built(bench)
    dump = _split(dump, True)
    dump["meshes"].append(_resize(_sheet(reverse), 100, (-20,-20,-10)))
    _assert_not_checked(_hcheck(dump, tol), from_dump(dump))

@pytest.mark.parametrize("dz", [-0.0101,-0.01,-0.0099,0,0.0099,0.01,0.0101])
@pytest.mark.parametrize("reverse", [False,True])
def test_cap_join_distance_bound(dz, reverse):
    cap = _resize(_sheet(reverse), .8, (.1,.1,dz))
    dump = {"meshes": [_box("owner", drop_bottom=True),cap]}
    _assert_not_checked(_hcheck(dump), from_dump(dump))

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

@pytest.mark.parametrize("case", ["outside","concave_bridge","hole","inside_annulus"])
def test_cap_outside_footprint_stays_independent(case):
    import shapely
    if case == "concave_bridge":
        polygon = shapely.Polygon([(0,0),(3,0),(3,3),(2,3),(2,1),(1,1),(1,3),(0,3)])
        xy = [[.5,2.5],[1.5,.5],[2.5,2.5]]
    elif case in ("hole","inside_annulus"):
        polygon = shapely.Polygon([(0,0),(4,0),(4,4),(0,4)], [[(1,1),(1,3),(3,3),(3,1)]])
        xy = [[1.2,1.2],[2.8,1.2],[2,2.8]] if case == "hole" else [[.1,.1],[.9,.1],[.1,.9]]
    else:
        polygon = shapely.box(0,0,1,1)
        xy = [[.2,.2],[1.2,.2],[.2,.8]]
    cap = {"name":"cap", "vertices":[[x,y,0] for x,y in xy],
           "triangles":[[0,2,1]], "material_ids":[1]}
    dump = {"meshes":[_open_prism(polygon),cap]}
    _assert_not_checked(_hcheck(dump), from_dump(dump))

@pytest.mark.parametrize("seed", range(20))
def test_combined_cap_context_probe(seed):
    """SYNTHETIC exact-ID oracle; seed 5600..5619, order/partition/reset/transforms."""
    rng = np.random.default_rng(seed + 5600)
    base = _detached_reversed_soffit_dump()
    base["meshes"] += [_resize(_box("stack", drop_bottom=True), 2, (0,0,10)),
                       _resize(_box("inner", reverse=range(12)), .2, (1,1,1)),
                       _resize(_box("decor", reverse=range(12)), .2, (2,2,2)),
                       _resize(_sheet(), 20, (-5,-5,-1))]
    angle = rng.uniform(-np.pi,np.pi)
    c,s = np.cos(angle),np.sin(angle)
    rotation = np.array([[c,-s,0],[s,c,0],[0,0,1]])
    offset = rng.uniform(-500,500,3)
    base = _map_vertices(base, lambda v: v @ rotation.T + offset)
    base = _random_partition(base, seed)
    rng.shuffle(base["meshes"])
    model = from_dump(base)
    horizontal,_,_ = _horiz_axes(model)
    closed = np.array([name.startswith(("inner","decor")) for name in model.mesh_names])[model.mesh_index]
    expected = np.flatnonzero(horizontal & closed).tolist()
    skipped = np.flatnonzero(~closed).tolist()
    first = _hcheck(base)
    assert first["value"] == 8
    assert first["details"]["inward_triangles"] == expected
    assert first["details"]["not_checked_triangles"] == skipped
    # Repair all closed horizontal normals; open geometry never changes their verdict.
    clean = copy.deepcopy(base)
    _flip_global(clean, expected)
    assert _hcheck(clean)["value"] == 0
    assert _hcheck(base) == first
    base["meshes"].reverse()
    assert _hcheck(base)["value"] == 8

def test_open_fragment_does_not_see_decor():
    for reverse in (False,True):
        dump = _detached_reversed_soffit_dump()
        if not reverse:
            _flip_global(dump, [12,13])
        dump = _move_picked_to(dump,[12,13],"decor")
        _assert_not_checked(_hcheck(dump), from_dump(dump))

def _assert_not_checked(result, model):
    assert result["status"] == "not_measured" and result["value"] is None
    assert result["details"]["inward_triangles"] == []
    assert result["details"]["checked_triangles"] == []
    assert result["details"]["not_checked_triangles"] == list(range(len(model.triangles)))
    assert result["details"]["not_checked_reason"] == "not checked (see #314)"

def test_existing_inset_roof_has_no_false_inward_faces():
    from test_geometry_checks import box_dump
    dump = box_dump()
    _assert_not_checked(_hcheck(dump), from_dump(dump))

def _closed_voxel_step():
    """SYNTHETIC union of four unit voxels; exposed ledge AND overhang soffit at z=1."""
    cells = {(0,0,0), (1,0,0), (1,0,1), (2,0,1)}
    faces = [((-1,0,0), [(0,0,0),(0,0,1),(0,1,1),(0,1,0)]),
             ((1,0,0), [(1,0,0),(1,1,0),(1,1,1),(1,0,1)]),
             ((0,-1,0),[(0,0,0),(1,0,0),(1,0,1),(0,0,1)]),
             ((0,1,0), [(0,1,0),(0,1,1),(1,1,1),(1,1,0)]),
             ((0,0,-1),[(0,0,0),(0,1,0),(1,1,0),(1,0,0)]),
             ((0,0,1), [(0,0,1),(1,0,1),(1,1,1),(0,1,1)])]
    vertices, triangles = [], []
    for cell in sorted(cells):
        for direction, quad in faces:
            neighbour = tuple(a+b for a,b in zip(cell,direction))
            if neighbour in cells:
                continue
            base = len(vertices)
            vertices.extend((np.array(quad) + cell).tolist())
            triangles.extend([[base,base+1,base+2], [base,base+2,base+3]])
    return {"meshes":[{"name":"step", "vertices":vertices, "triangles":triangles,
                       "material_ids":[1]*len(triangles)}]}

@pytest.mark.parametrize("seed", range(10))
def test_closed_step_every_flip_exact_probe(seed):
    """Closed step normals -> each single horizontal flip -> exact singleton, seed 560..569."""
    dump = _random_partition(_closed_voxel_step(), seed+560)
    model = from_dump(dump)
    horizontal, nz, z = _horiz_axes(model)
    assert np.any(horizontal & (nz > 0) & (z == 1))  # ledge
    assert np.any(horizontal & (nz < 0) & (z == 1))  # overhang soffit
    assert _hcheck(dump)["value"] == 0
    assert _hcheck(dump)["details"]["not_checked_triangles"] == []
    for index in np.flatnonzero(horizontal):
        trial = copy.deepcopy(dump)
        _flip_global(trial, [index])
        result = _hcheck(trial)
        assert result["value"] == 1
        assert result["details"]["inward_triangles"] == [int(index)]

def test_even_nonmanifold_edge_uses_are_not_closed_volume():
    mesh = _box()
    mesh["triangles"] *= 2
    mesh["material_ids"] *= 2
    dump = {"meshes":[mesh]}
    _assert_not_checked(_hcheck(dump), from_dump(dump))
