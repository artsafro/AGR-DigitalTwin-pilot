"""Pattern: n/a | new-case: Source dump preserves triangle orientation under mirrored world transforms.

Synthetic native regression for `tools/source/measure_spec_blender.py` (the spec-extractor
source dump). A mirrored world transform (negative determinant of the object's world linear
transform) bakes world-space vertices that reverse the source orientation; the dumper must swap
two indices of every emitted triangle once so the emitted winding matches the world geometry,
and must leave a genuinely inward source untouched when the determinant is positive.

Select with `pytest -m dcc` (the default suite excludes this marker). Requires the pinned
Blender 5.1.2 (`DT_BLENDER`, `TWINQA_BLENDER` or the default Blender 5.1 installation).
delivery_passed is false. All fixtures are synthetic (a unit cube), generated into temp paths.
"""
import hashlib
import json
import math
import os
import subprocess
from pathlib import Path

import numpy as np
import pytest

from dt_ai.core.blender_runner import blender_executable

pytestmark = pytest.mark.dcc

ROOT = Path(__file__).resolve().parents[1]
MEASURE = ROOT / "tools" / "source" / "measure_spec_blender.py"

# Expected sign of det(world linear transform) per case. Fixture sanity, not the oracle.
EXPECTED_DET_SIGN = {
    "identity": 1,
    "neg_scale_x": -1,
    "neg_nonuniform": -1,
    "inherited_reflection": -1,
    "two_axis_neg": 1,
    "inward_control": 1,
}

# The generator writes one .blend per case plus a manifest with the exact local geometry
# (vertices, triangles, material ids, polygon sizes, UDIM tiles) and each object's world matrix.
GENERATOR = r'''
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

out = Path(sys.argv[sys.argv.index("--") + 1])
out.mkdir(parents=True, exist_ok=True)


def affine(scale, rot_deg, translation):
    S = Matrix.Diagonal([*scale, 1.0])
    R = Matrix.Rotation(math.radians(rot_deg), 4, "Z")
    T = Matrix.Translation(translation)
    return T @ R @ S


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def add_cube(name, inward=False):
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    obj = bpy.context.active_object
    obj.name = name
    mesh = obj.data
    mesh.name = name + "_mesh"
    if inward:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.flip_normals()
        bpy.ops.object.mode_set(mode="OBJECT")
    mat0 = bpy.data.materials.new("mat0")
    mat1 = bpy.data.materials.new("mat1")
    mesh.materials.append(mat0)
    mesh.materials.append(mat1)
    for poly in mesh.polygons:
        poly.material_index = 0 if poly.index < 4 else 1
    uv = mesh.uv_layers.new(name="tiles")
    uv.active = True
    for poly in mesh.polygons:
        u = 0.25 if poly.index < 4 else 1.25
        for li in poly.loop_indices:
            uv.data[li].uv = (u, 0.25)
    return obj


def local_geometry(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    mesh = obj.evaluated_get(depsgraph).to_mesh()
    mesh.calc_loop_triangles()
    uv = mesh.uv_layers.active.data if mesh.uv_layers.active else None

    def tile(t):
        u = sum(uv[i].uv[0] for i in t.loops) / 3
        v = sum(uv[i].uv[1] for i in t.loops) / 3
        return 1001 + int(math.floor(u)) + 10 * int(math.floor(v))

    data = {
        "vertices": [list(v.co) for v in mesh.vertices],
        "triangles": [list(t.vertices) for t in mesh.loop_triangles],
        "material_ids": [t.material_index + 1 for t in mesh.loop_triangles],
        "polygon_sizes": [len(p.vertices) for p in mesh.polygons],
        "udim_tiles": [tile(t) for t in mesh.loop_triangles],
    }
    obj.evaluated_get(depsgraph).to_mesh_clear()
    return data


def world_matrix(obj):
    bpy.context.view_layer.update()
    return [c for row in obj.matrix_world for c in row]


reset()
outward = add_cube("outward")
outward_local = local_geometry(outward)
reset()
inward = add_cube("inward", inward=True)
inward_local = local_geometry(inward)

manifest = {"outward_local": outward_local, "inward_local": inward_local, "cases": {}}


def save_case(name):
    bpy.ops.wm.save_as_mainfile(filepath=str(out / (name + ".blend")))


reset()
obj = add_cube("outward")
obj.matrix_world = affine((1, 1, 1), 0.0, (0, 0, 0))
manifest["cases"]["identity"] = {"object": "outward", "world": world_matrix(obj)}
save_case("identity")

reset()
obj = add_cube("outward")
obj.matrix_world = affine((-1, 1, 1), 0.0, (2, 0, 0))
manifest["cases"]["neg_scale_x"] = {"object": "outward", "world": world_matrix(obj)}
save_case("neg_scale_x")

reset()
obj = add_cube("outward")
obj.matrix_world = affine((-2, 1.5, 0.5), 30.0, (3, -2, 5))
manifest["cases"]["neg_nonuniform"] = {"object": "outward", "world": world_matrix(obj)}
save_case("neg_nonuniform")

reset()
parent = bpy.data.objects.new("mirror_parent", None)
bpy.context.scene.collection.objects.link(parent)
parent.matrix_world = affine((-1, 1, 1), 0.0, (1, 1, 1))
obj = add_cube("outward")
obj.parent = parent
obj.matrix_local = affine((1, 1, 1), 45.0, (0.5, -0.25, 0.0))
manifest["cases"]["inherited_reflection"] = {"object": "outward", "world": world_matrix(obj)}
save_case("inherited_reflection")

reset()
obj = add_cube("outward")
obj.matrix_world = affine((-1, -1, 1), 0.0, (0, 0, 0))
manifest["cases"]["two_axis_neg"] = {"object": "outward", "world": world_matrix(obj)}
save_case("two_axis_neg")

reset()
obj = add_cube("inward", inward=True)
obj.matrix_world = affine((1, 1, 1), 0.0, (0, 0, 0))
manifest["cases"]["inward_control"] = {"object": "inward", "world": world_matrix(obj)}
save_case("inward_control")

(out / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
print("GENERATED")
'''


def _pinned_blender():
    exe = os.environ.get("DT_BLENDER") or blender_executable()
    return str(exe) if exe and Path(exe).is_file() else None


def _signed_volume(vertices, triangles):
    v = np.asarray(vertices, dtype=np.float64)
    total = 0.0
    for a, b, c in triangles:
        total += float(np.dot(v[a], np.cross(v[b], v[c])))
    return total / 6.0


def _det_sign(world):
    m = np.asarray(world, dtype=np.float64).reshape(4, 4)
    det = float(np.linalg.det(m[:3, :3]))
    return 1 if det >= 0 else -1, det


def _apply_affine(world, vertices):
    m = np.asarray(world, dtype=np.float64).reshape(4, 4)
    v = np.asarray(vertices, dtype=np.float64)
    ones = np.ones((v.shape[0], 1))
    return (m @ np.hstack([v, ones]).T).T[:, :3]


@pytest.fixture(scope="module")
def blender():
    exe = _pinned_blender()
    if not exe:
        pytest.skip("Blender 5.1.2 not found (DT_BLENDER, TWINQA_BLENDER or the pinned installation)")
    ver = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=120,
                         encoding="utf-8", errors="replace")
    if ver.returncode != 0 or "5.1.2" not in (ver.stdout or ""):
        pytest.skip("Blender is not 5.1.2")
    return exe


@pytest.fixture(scope="module")
def generated(blender, tmp_path_factory):
    out = tmp_path_factory.mktemp("mirrored")
    gen = out / "generate.py"
    gen.write_text(GENERATOR, encoding="utf-8")
    run = subprocess.run([blender, "--background", "--factory-startup", "--python-exit-code", "1",
                          "--python", str(gen), "--", str(out)],
                         capture_output=True, text=True, timeout=600,
                         encoding="utf-8", errors="replace")
    assert run.returncode == 0 and "GENERATED" in run.stdout, run.stdout[-2000:] + run.stderr[-2000:]
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    hashes = {name: hashlib.sha256((out / (name + ".blend")).read_bytes()).hexdigest()
              for name in manifest["cases"]}
    return out, manifest, hashes


@pytest.fixture(scope="module")
def dumps(blender, generated):
    out, manifest, _ = generated
    result = {}
    for name in manifest["cases"]:
        blend = out / (name + ".blend")
        dump_path = out / (name + ".dump.json")
        run = subprocess.run(
            [blender, "--background", "--factory-startup", "--disable-autoexec", "--python-exit-code",
             "1", "--python", str(MEASURE), "--", str(blend), str(dump_path)],
            capture_output=True, text=True, timeout=600, encoding="utf-8", errors="replace")
        assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]
        result[name] = json.loads(dump_path.read_text(encoding="utf-8"))
    return result


CASE_NAMES = list(EXPECTED_DET_SIGN)


def _local(manifest, name):
    return manifest[manifest["cases"][name]["object"] + "_local"]


def test_fixture_det_signs(generated):
    _, manifest, _ = generated
    for name in CASE_NAMES:
        sign, _ = _det_sign(manifest["cases"][name]["world"])
        assert sign == EXPECTED_DET_SIGN[name], name
    # the fixtures are genuinely outward / inward in local space
    assert _signed_volume(manifest["outward_local"]["vertices"],
                          manifest["outward_local"]["triangles"]) > 0
    assert _signed_volume(manifest["inward_local"]["vertices"],
                          manifest["inward_local"]["triangles"]) < 0


@pytest.mark.parametrize("name", CASE_NAMES)
def test_vertices_match_affine_oracle(generated, dumps, name):
    _, manifest, _ = generated
    dump = dumps[name]
    local = _local(manifest, name)
    world = manifest["cases"][name]["world"]
    expected = _apply_affine(world, local["vertices"])
    got = np.asarray(dump["meshes"][0]["vertices"], dtype=np.float64)
    assert dump["meshes"][0]["name"] == manifest["cases"][name]["object"]
    assert got.shape == expected.shape
    assert np.allclose(got, expected, atol=1e-4, rtol=0.0)


@pytest.mark.parametrize("name", CASE_NAMES)
def test_triangle_winding_and_signed_volume(generated, dumps, name):
    _, manifest, _ = generated
    dump = dumps[name]
    local = _local(manifest, name)
    world = manifest["cases"][name]["world"]
    sign, det = _det_sign(world)

    expected_tris = local["triangles"]
    if sign < 0:
        expected_tris = [[a, c, b] for a, b, c in expected_tris]
    assert dump["meshes"][0]["triangles"] == expected_tris

    v_local = _signed_volume(local["vertices"], local["triangles"])
    v_dump = _signed_volume(dump["meshes"][0]["vertices"], dump["meshes"][0]["triangles"])
    assert math.isclose(v_dump, abs(det) * v_local, rel_tol=1e-4, abs_tol=1e-4)
    # orientation follows the source, never silently flipped by the sign of the volume
    assert (v_dump > 0) == (v_local > 0)


@pytest.mark.parametrize("name", CASE_NAMES)
def test_material_udim_polygon_unchanged(generated, dumps, name):
    _, manifest, _ = generated
    dump = dumps[name]
    local = _local(manifest, name)
    mesh = dump["meshes"][0]
    assert mesh["material_ids"] == local["material_ids"]
    assert mesh["udim_tiles"] == local["udim_tiles"]
    assert mesh["polygon_sizes"] == local["polygon_sizes"]
    # two material slots and two UDIM tiles so the per-triangle association is real
    assert set(mesh["material_ids"]) == {1, 2}
    assert set(mesh["udim_tiles"]) == {1001, 1002}


@pytest.mark.parametrize("name", CASE_NAMES)
def test_source_hashes_unchanged(generated, dumps, name):
    out, manifest, hashes = generated
    dump = dumps[name]
    # the dumper reports the source hash it read, and never rewrites the source file
    assert dump["sha256"] == hashes[name]
    assert hashlib.sha256((out / (name + ".blend")).read_bytes()).hexdigest() == hashes[name]


def test_inward_control_preserved_not_repaired(generated, dumps):
    _, manifest, _ = generated
    dump = dumps["inward_control"]
    local = manifest["inward_local"]
    v_local = _signed_volume(local["vertices"], local["triangles"])
    v_dump = _signed_volume(dump["meshes"][0]["vertices"], dump["meshes"][0]["triangles"])
    assert v_local < 0
    assert dump["meshes"][0]["triangles"] == local["triangles"]
    assert math.isclose(v_dump, v_local, rel_tol=1e-4, abs_tol=1e-4)
    assert v_dump < 0
