"""Headless Blender export/readback of a UV seam on one shared vertex.

Pattern: n/a | new-case: signed numeric-margin reporting + per-corner UV seam preservation.

The unit square and the loop UVs match the review oracle: faces (0,1,2)/(0,2,3),
seam corners [(0,0),(1,0),(1,1)] / [(0.9,0.9),(1,1),(0,1)], diffuse 1024.
Readback must keep that second corner on vertex 0 of face 1, and density must
fail at about 102.4 px/m. Synthetic geometry only; not a delivery verdict.
"""
import json
import math
import struct
import subprocess
from pathlib import Path

import pytest

from test_sintez_uv_1732 import SIDE, _incident
from test_validator import PROFILES
from twinqa.scene import _texel_density_findings, find_blender, scene_findings

pytestmark = pytest.mark.blender

ROOT = Path(__file__).resolve().parents[2]
READBACK = ROOT / "tools" / "blender" / "fbx_readback.py"

EXPORT = r'''
import bpy
import sys
from pathlib import Path

out = Path(sys.argv[sys.argv.index("--") + 1])
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system = "METRIC"
bpy.context.scene.unit_settings.scale_length = 1.0
mesh = bpy.data.meshes.new("ReviewGeometry")
mesh.from_pydata([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [], [(0, 1, 2), (0, 2, 3)])
obj = bpy.data.objects.new("SM_Test_K_1_Main", mesh)
bpy.context.collection.objects.link(obj)
uv = mesh.uv_layers.new(name="UVMap")
for index, pair in enumerate([(0, 0), (1, 0), (1, 1), (0.9, 0.9), (1, 1), (0, 1)]):
    uv.data[index].uv = pair
image = bpy.data.images.new("review_diffuse", width=1024, height=1024)
image.filepath_raw = str(out.with_suffix(".png"))
image.file_format = "PNG"
image.save()
mat = bpy.data.materials.new("ReviewMaterial")
mat.use_nodes = True
tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
tex.image = image
mat.node_tree.links.new(tex.outputs["Color"], mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
obj.data.materials.append(mat)
bpy.ops.export_scene.fbx(
    filepath=str(out), use_selection=False, object_types={"MESH"}, path_mode="COPY", embed_textures=True,
)
print("EXPORTED")
'''


@pytest.fixture(scope="module")
def blender():
    exe = find_blender()
    if not exe:
        pytest.skip("Blender not found (DT_BLENDER or the pinned installation)")
    return exe


def _run(blender, script, args):
    return subprocess.run(
        [blender, "--background", "--factory-startup", "--disable-autoexec", "--threads", "1",
         "--python-exit-code", "1", "--python", script, "--", *args],
        capture_output=True, text=True, timeout=600, encoding="utf-8", errors="replace",
    )


def test_blender_readback_preserves_seam_corner_uv(blender, tmp_path):
    fbx = tmp_path / "seam.fbx"
    script = tmp_path / "export_seam.py"
    script.write_text(EXPORT, encoding="utf-8")
    exported = _run(blender, str(script), [str(fbx)])
    assert exported.returncode == 0 and "EXPORTED" in exported.stdout, exported.stdout[-2000:] + exported.stderr[-2000:]
    report_path = tmp_path / "seam.json"
    read = _run(blender, str(READBACK), [str(fbx), str(report_path)])
    assert read.returncode == 0 and report_path.is_file(), read.stdout[-2000:] + read.stderr[-2000:]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["readback_ok"] is True
    mesh = next(item for item in report["meshes"] if item["name"] == "SM_Test_K_1_Main")
    shape = mesh["face_geometry"]
    polygons = shape["polygons"]
    polygon_uv = shape["polygon_uv"]
    assert len(polygon_uv) == len(polygons)
    face = polygons[1]
    assert 0 in face
    corner = polygon_uv[1][list(face).index(0)]
    assert corner[0] == pytest.approx(0.9, abs=1e-5)
    assert corner[1] == pytest.approx(0.9, abs=1e-5)
    # The per-vertex channel still keeps the first loop. Density must not use it for this corner.
    assert shape["uv"][0][0] == pytest.approx(0.0, abs=1e-5)
    assert shape["uv"][0][1] == pytest.approx(0.0, abs=1e-5)
    ucx = [item for item in report["meshes"] if item["name"].upper().startswith("UCX_")]
    findings = _texel_density_findings(report, report["meshes"], ucx, "seam.fbx")
    lower = next(item for item in findings if item.name == "texel density")
    assert lower.status == "fail"
    assert lower.measured == pytest.approx(102.4)
    assert lower.threshold == 512
    assert lower.margin == pytest.approx((102.4 - 512) / 512)


@pytest.mark.parametrize(("profile", "stage"), [("vpm", "V008"), ("npm", "V004")])
def test_blender_readback_preserves_slanted_uv_collapse(blender, tmp_path, profile, stage):
    incident = _incident()
    geometry = incident["face_geometry"]
    height = 0.12345678
    for point in geometry["vertices"]:
        point[2] = height
    vertices = geometry["vertices"]
    a, b, c = geometry["polygons"][6]
    x, y, z = vertices[a]
    geometry["polygons"][6] = [len(vertices), b, c]
    vertices.append([x + 0.0005, y, z])

    def f32(value):
        return struct.unpack("<f", struct.pack("<f", value))[0]

    geometry["polygon_uv"][6] = [
        [f32(0.15 + t * math.cos(0.7)), f32(0.20 + t * math.sin(0.7))]
        for t in (0.0, 0.025, 0.05)
    ]
    # Build a synthetic FBX from the mixed incident; the actual readback script writes the JSON.
    export = EXPORT[:EXPORT.index("mesh.from_pydata")] + f'''
mesh.from_pydata({vertices!r}, [], {geometry["polygons"]!r})
obj = bpy.data.objects.new({incident["name"]!r}, mesh)
bpy.context.collection.objects.link(obj)
uv = mesh.uv_layers.new(name="UVMap")
for index, pair in enumerate({[p for face in geometry["polygon_uv"] for p in face]!r}):
    uv.data[index].uv = pair
obj.data.materials.append(bpy.data.materials.new({incident["materials"][0]!r}))
bpy.ops.export_scene.fbx(filepath=str(out), object_types={{"MESH"}})
'''
    script = tmp_path / "export_incident.py"
    script.write_text(export, encoding="utf-8")
    fbx = tmp_path / "SM_Test_K_1.fbx"
    exported = _run(blender, str(script), [str(fbx)])
    assert exported.returncode == 0 and fbx.is_file(), exported.stdout + exported.stderr
    original = fbx.read_bytes()
    report_path = tmp_path / "incident.json"
    read = _run(blender, str(READBACK), [str(fbx), str(report_path)])
    assert read.returncode == 0 and "TWINQA_READBACK True" in read.stdout, read.stdout + read.stderr
    assert fbx.read_bytes() == original
    report = json.loads(report_path.read_text(encoding="utf-8"))
    scene = scene_findings(report, profile, "oks", getattr(PROFILES, profile), diffuse_px={(1, 1001): SIDE})
    findings = {f.name: f for f in scene[stage]}
    unwrapped = findings["unwrapped UV polygons"]
    assert unwrapped.status == "review"
    assert unwrapped.data["faces"] == {incident["name"]: [6]}
    facts = report["meshes"][0]["face_geometry"]
    assert facts["polygon_uv"][6] == geometry["polygon_uv"][6]
    assert [point[2] for point in facts["vertices"]] == pytest.approx([height] * len(vertices), abs=5e-8)
    if profile == "vpm":
        assert findings["mirrored UV polygons"].data["faces"] == {incident["name"]: [3]}
        assert findings["UV outside UDIM tile"].data["faces"] == {incident["name"]: [1]}
        density = next(f for f in scene["V009"] if f.name == "texel density per polygon")
        assert density.data["faces"]["less"] == {incident["name"]: [6]}
    else:
        assert findings["duplicate vertices"].status == "review"
