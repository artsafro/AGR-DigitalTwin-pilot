"""GroundEl surface facts and V004 MAF findings on the FBX readback (#185)."""
import math
import random
import subprocess

import pytest

from test_scene import mesh, rb
from test_validator import PROFILES
from twinqa.geometry.maf_surface import surface_facts
from twinqa.maf_checks import maf_findings
from twinqa.scene import find_blender, readback, scene_findings

VERTS = [
    [0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0],
    [0.0, 0.0, 1.0], [1.0, 0.0, 1.0], [1.0, 1.0, 1.0], [0.0, 1.0, 1.0],
]
# Outward triangles. The last two lie on z = 0 (the sunk bottom).
TRIS = [
    (1, 2, 6), (1, 6, 5),
    (0, 4, 7), (0, 7, 3),
    (2, 3, 7), (2, 7, 6),
    (0, 1, 5), (0, 5, 4),
    (4, 5, 6), (4, 6, 7),
    (0, 3, 2), (0, 2, 1),
]
BOTTOM = {10, 11}
SPEC = {"SM_Test_GroundEl": [1.5, 0.6, 0.8]}


def _newell(pts):
    nx = ny = nz = 0.0
    for i, (x1, y1, z1) in enumerate(pts):
        x2, y2, z2 = pts[(i + 1) % len(pts)]
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    return (nx, ny, nz)


def _norm(v):
    length = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    return [c / length for c in v]


def _apply(point, rotation, translation):
    if rotation is None:
        moved = point
    else:
        moved = [sum(rotation[i][j] * point[j] for j in range(3)) for i in range(3)]
    return [moved[i] + translation[i] for i in range(3)]


def _corners(coords, polys, shading):
    normals = [_norm(_newell([coords[j] for j in poly])) for poly in polys]
    if shading == "hard":
        return [[normal for _ in poly] for poly, normal in zip(polys, normals)]
    acc = [[0.0, 0.0, 0.0] for _ in coords]
    for poly, normal in zip(polys, normals):
        for index in poly:
            for axis in range(3):
                acc[index][axis] += normal[axis]
    acc = [_norm(v) for v in acc]
    return [[acc[index] for index in poly] for poly in polys]


def box_mesh(*, flip=(), drop_bottom=False, shading="hard", rotation=None, translation=(0.0, 0.0, 0.0), duplicate=False):
    """Unit cube, 12 outward triangles. flip indexes faces after the bottom is dropped."""
    tris = [list(tri) for i, tri in enumerate(TRIS) if not (drop_bottom and i in BOTTOM)]
    for index in flip:
        a, b, c = tris[index]
        tris[index] = [a, c, b]
    if duplicate:
        coords, polys = [], []
        for tri in tris:
            base = len(coords)
            coords.extend(_apply(VERTS[i], rotation, translation) for i in tri)
            polys.append([base, base + 1, base + 2])
    else:
        coords = [_apply(v, rotation, translation) for v in VERTS]
        polys = tris
    return coords, polys, _corners(coords, polys, shading)


def folded_quads(angle_deg, shading):
    """Two quads sharing an edge, folded by angle_deg from coplanar, consistent winding."""
    theta = math.radians(angle_deg)
    cosine, sine = math.cos(theta), math.sin(theta)
    coords = [
        [0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0],
        [0.0, -cosine, -sine], [1.0, -cosine, -sine],
    ]
    polys = [[0, 1, 2, 3], [0, 4, 5, 1]]
    return coords, polys, _corners(coords, polys, shading)


def random_rotation(rng):
    columns = []
    while len(columns) < 3:
        vector = [rng.uniform(-1.0, 1.0) for _ in range(3)]
        for column in columns:
            dot = sum(a * b for a, b in zip(vector, column))
            vector = [a - dot * b for a, b in zip(vector, column)]
        length = math.sqrt(sum(a * a for a in vector))
        if length < 1e-8:
            continue
        columns.append([a / length for a in vector])
    det = (
        columns[0][0] * (columns[1][1] * columns[2][2] - columns[1][2] * columns[2][1])
        - columns[0][1] * (columns[1][0] * columns[2][2] - columns[1][2] * columns[2][0])
        + columns[0][2] * (columns[1][0] * columns[2][1] - columns[1][1] * columns[2][0])
    )
    if det < 0:
        columns[2] = [-a for a in columns[2]]
    return [[columns[j][i] for j in range(3)] for i in range(3)]


def _named(findings, name):
    return next(f for f in findings if f.name == name)


def groundel(facts, name="SM_Test_GroundEl"):
    item = mesh(name=name)
    item["maf_surface"] = facts
    return item


def test_hard_box_has_split_edges_and_outward_faces():
    facts = surface_facts(*box_mesh())
    assert facts["soft_edge_angles_deg"] == {}
    assert facts["flipped_faces"] == 0
    assert facts["inconsistent_edges"] == 0
    assert facts["components"] == 1
    assert facts["undetermined_components"] == 0


def test_soft_box_records_the_twelve_cube_edges():
    facts = surface_facts(*box_mesh(shading="soft"))
    assert facts["soft_edge_angles_deg"] == {"90.0": 12}
    assert facts["flipped_faces"] == 0


def test_one_flipped_triangle_and_inward_box():
    one = surface_facts(*box_mesh(flip={0}))
    assert one["flipped_faces"] == 1
    assert one["inconsistent_edges"] == 3
    inward = surface_facts(*box_mesh(flip=set(range(12))))
    assert inward["flipped_faces"] == 12
    assert inward["inconsistent_edges"] == 0


def test_open_bottom_shell_keeps_the_closed_sign():
    outward = surface_facts(*box_mesh(drop_bottom=True))
    assert outward["flipped_faces"] == 0
    assert outward["undetermined_components"] == 0
    inward = surface_facts(*box_mesh(drop_bottom=True, flip=set(range(10))))
    assert inward["flipped_faces"] == 10


def test_single_quad_plane_is_undetermined():
    coords = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]]
    normal = _norm(_newell(coords))
    facts = surface_facts(coords, [[0, 1, 2, 3]], [[normal, normal, normal, normal]])
    assert facts["undetermined_components"] == 1
    assert facts["flipped_faces"] == 0
    assert facts["components"] == 1


def test_duplicated_vertices_still_weld():
    facts = surface_facts(*box_mesh(duplicate=True))
    assert facts["components"] == 1
    assert facts["flipped_faces"] == 0
    assert facts["inconsistent_edges"] == 0


def test_smoothing_angle_is_strictly_greater():
    soft_35 = surface_facts(*folded_quads(35, "soft"))
    assert soft_35["soft_edge_angles_deg"] == {"35.0": 1}
    passed = maf_findings([groundel(soft_35)], "ground", "a.fbx")
    assert _named(passed, "MAF smoothing").status == "pass"
    failed = maf_findings([groundel(soft_35)], "ground", "a.fbx", smoothing_angle_deg=30)
    assert _named(failed, "MAF smoothing").status == "fail"
    soft_40 = surface_facts(*folded_quads(40, "soft"))
    assert soft_40["soft_edge_angles_deg"] == {"40.0": 1}
    exact = maf_findings([groundel(soft_40)], "ground", "a.fbx")
    assert _named(exact, "MAF smoothing").status == "pass"
    assert "above 40 deg" in _named(exact, "MAF smoothing").expected


def test_scene_findings_reports_groundel_smoothing_and_flips():
    good = scene_findings(rb(groundel(surface_facts(*box_mesh()))), "npm", "ground", PROFILES.npm)
    assert _named(good["V004"], "MAF smoothing").status == "pass"
    assert _named(good["V004"], "MAF flipped normals").status == "pass"
    smooth = scene_findings(rb(groundel(surface_facts(*box_mesh(shading="soft")))), "npm", "ground", PROFILES.npm)
    assert _named(smooth["V004"], "MAF smoothing").status == "fail"
    inward = scene_findings(rb(groundel(surface_facts(*box_mesh(flip=set(range(12)))))), "npm", "ground", PROFILES.npm)
    flip = _named(inward["V004"], "MAF flipped normals")
    assert flip.status == "fail"
    assert "undetermined" in flip.observed
    assert flip.source_pdf_pages == [8, 29]


def test_missing_or_failed_surface_is_not_run():
    bare = scene_findings(rb(mesh(name="SM_Test_GroundEl")), "npm", "ground", PROFILES.npm)
    assert _named(bare["V004"], "MAF smoothing").status == "not_run"
    assert "SM_Test_GroundEl" in _named(bare["V004"], "MAF smoothing").observed
    assert _named(bare["V004"], "MAF flipped normals").status == "not_run"
    broken = mesh(name="SM_Test_GroundEl")
    broken["maf_surface"] = {"error": "RuntimeError: boom"}
    found = maf_findings([broken], "ground", "a.fbx")
    assert {f.name: f.status for f in found} == {"MAF smoothing": "not_run", "MAF flipped normals": "not_run"}


def test_oks_glass_and_ucx_skip_maf_surface_findings():
    item = groundel(surface_facts(*box_mesh(shading="soft")))
    oks = scene_findings(rb(item), "npm", "oks", PROFILES.npm)
    assert [f.name for f in oks["V004"]] == ["applied transforms"]
    glass = scene_findings(rb(mesh(name="SM_Test_GroundElGlass")), "npm", "ground", PROFILES.npm)
    assert [f.name for f in glass["V004"]] == ["applied transforms"]
    ucx = scene_findings(rb(mesh(name="UCX_SM_Test_GroundEl")), "npm", "ground", PROFILES.npm)
    assert [f.name for f in ucx["V004"]] == ["applied transforms"]


def _dimension(bounds, sizes=SPEC, present=True):
    meshes = []
    if present:
        item = mesh(name="SM_Test_GroundEl")
        if bounds is not None:
            item["bounds_m"] = [[0.0, 0.0, 0.0], list(bounds)]
        meshes.append(item)
    found = maf_findings(meshes, "npm", "a.fbx", maf_sizes=sizes)
    return _named(found, "MAF dimensions vs specification")


def test_dimensions_against_specification():
    assert _dimension([1.5, 0.6, 0.9]).status == "pass"
    assert _dimension([0.6, 1.5, 0.9]).status == "pass"
    assert _dimension([1.5, 0.6, 0.8]).status == "pass"
    assert _dimension([1.5, 0.6, 1.01]).status == "fail"
    assert _dimension([1.601, 0.6, 0.9]).status == "fail"
    assert _dimension([1.5, 0.499, 0.9]).status == "fail"
    assert _dimension(None, present=False).status == "fail"
    assert "missing mesh" in _dimension(None, present=False).observed
    assert _dimension(None).status == "fail"
    none = maf_findings([mesh(name="SM_Test_GroundEl")], "ground", "a.fbx")
    assert all(f.name != "MAF dimensions vs specification" for f in none)
    wired = scene_findings(rb(mesh(name="SM_Test_GroundEl")), "npm", "oks", PROFILES.npm, maf_sizes=SPEC)
    assert _named(wired["V004"], "MAF dimensions vs specification").status == "fail"
    finding = _dimension([1.5, 0.6, 0.9])
    assert finding.expected == "|bbox - spec| <= 0.1 m per axis; Z = spec + 0.1 m sink [D094, D095]"
    assert finding.source_pdf_pages == [4, 24]


def test_invalid_size_and_angle_raise():
    for size in ([1.5, 0.6, 0], [-1.0, 1.0, 1.0], [1.0, 1.0], [float("nan"), 1.0, 1.0], [1.0, 1.0, float("inf")]):
        with pytest.raises(ValueError):
            maf_findings([], "ground", "a.fbx", maf_sizes={"SM_Test_GroundEl": size})
    for angle in (0, 180, -5, 180.0):
        with pytest.raises(ValueError):
            maf_findings([], "ground", "a.fbx", smoothing_angle_deg=angle)


def test_every_flip_subset_on_closed_and_open_boxes():
    poses = [(None, (0.0, 0.0, 0.0))]
    for seed in (1, 2, 3):
        rng = random.Random(seed)
        poses.append((random_rotation(rng), (rng.uniform(-3, 3), rng.uniform(-3, 3), rng.uniform(-3, 3))))
    for rotation, translation in poses:
        for mask in range(4096):
            flip = [i for i in range(12) if mask & (1 << i)]
            facts = surface_facts(*box_mesh(flip=flip, rotation=rotation, translation=translation))
            assert facts["flipped_faces"] == len(flip), (mask, rotation is not None)
    for mask in range(1024):
        flip = [i for i in range(10) if mask & (1 << i)]
        facts = surface_facts(*box_mesh(drop_bottom=True, flip=flip))
        assert facts["flipped_faces"] == len(flip)


def test_dihedral_sweep_and_hard_normals_never_fail():
    cache = {}
    for angle in range(2, 89):
        cache[angle] = (
            surface_facts(*folded_quads(angle, "soft")),
            surface_facts(*folded_quads(angle, "hard")),
        )
    for angle in range(2, 89):
        soft, hard = cache[angle]
        for threshold in range(30, 46):
            soft_status = _named(maf_findings([groundel(soft)], "ground", "a.fbx", smoothing_angle_deg=threshold),
                                 "MAF smoothing").status
            hard_status = _named(maf_findings([groundel(hard)], "ground", "a.fbx", smoothing_angle_deg=threshold),
                                 "MAF smoothing").status
            assert (soft_status == "fail") is (angle > threshold), (angle, threshold, soft["soft_edge_angles_deg"])
            assert hard_status == "pass"


def test_dimension_deltas_fail_beyond_ten_centimetres():
    spec = [1.5, 0.6, 0.8]
    base_cm = [150, 60, 90]
    for axis in range(3):
        for cm in range(-20, 21):
            bbox_cm = base_cm.copy()
            bbox_cm[axis] += cm
            status = _dimension([c / 100 for c in bbox_cm], {"SM_Test_GroundEl": spec}).status
            assert (status == "fail") is (abs(cm) > 10), (axis, cm)
        for delta in (-0.10, 0.10):
            bounds = [1.5, 0.6, 0.9]
            bounds[axis] += delta
            assert _dimension(bounds, {"SM_Test_GroundEl": spec}).status == "pass"


BLENDER = find_blender()
MAKE_MAF = r"""
import bpy, sys
out, variant = sys.argv[sys.argv.index("--") + 1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add(size=2)
obj = bpy.context.object
obj.name = "SM_Test_GroundEl"
bpy.ops.object.modifier_add(type="TRIANGULATE")
bpy.ops.object.modifier_apply(modifier="Triangulate")
mesh = obj.data
if variant == "good":
    for edge in mesh.edges:
        edge.use_edge_sharp = True
    mesh.shade_flat()
    smooth = "FACE"
else:
    for edge in mesh.edges:
        edge.use_edge_sharp = False
    mesh.shade_smooth()
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")
    mesh.polygons[0].select = True
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.flip_normals()
    bpy.ops.object.mode_set(mode="OBJECT")
    for edge in mesh.edges:
        edge.use_edge_sharp = False
    mesh.shade_smooth()
    smooth = "OFF"
props = bpy.ops.export_scene.fbx.get_rna_type().properties.keys()
kwargs = {"filepath": out, "mesh_smooth_type": smooth, "add_leaf_bones": False}
if "use_mesh_edges" in props:
    kwargs["use_mesh_edges"] = True
bpy.ops.export_scene.fbx(**kwargs)
"""


@pytest.mark.blender
@pytest.mark.skipif(BLENDER is None, reason="Blender not installed")
@pytest.mark.parametrize("variant", ["good", "bad"])
def test_blender_groundel_roundtrip(tmp_path, variant):
    fbx_path = tmp_path / f"{variant}.fbx"
    subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                    "--python-expr", MAKE_MAF, "--", str(fbx_path), variant],
                   check=True, capture_output=True, timeout=300)
    report = readback(fbx_path, blender=BLENDER)
    item = next(m for m in report["meshes"] if m["name"] == "SM_Test_GroundEl")
    assert "error" not in item["maf_surface"], item["maf_surface"]
    found = scene_findings(report, "npm", "ground", PROFILES.npm, maf_sizes={"SM_Test_GroundEl": [2, 2, 1.9]})
    statuses = {f.name: f.status for f in found["V004"]}
    if variant == "good":
        assert statuses["MAF smoothing"] == "pass", item["maf_surface"]
        assert statuses["MAF flipped normals"] == "pass", item["maf_surface"]
        assert statuses["MAF dimensions vs specification"] == "pass"
    else:
        assert statuses["MAF smoothing"] == "fail", item["maf_surface"]
        assert statuses["MAF flipped normals"] == "fail", item["maf_surface"]
