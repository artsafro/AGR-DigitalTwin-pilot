"""Synthetic UV fixture for the bpy parity harness. delivery_passed=false.

    blender --background --factory-startup --disable-autoexec --python-exit-code 1 \
        --python experiments/bpy-benchmark-parity/make_uv_fixture.py -- <out.blend> <out.fbx>

One mesh UV_FIXTURE: 4 quads (8 triangles), material slot ID_01, one UV layer.
Quad centres sit at u/v 0.5 or 1.5 so the tiles are 1001, 1002, 1011, 1012.
Each quad spans [i+0.1, i+0.9], so both loop-triangle centres stay in that tile.
Not a real object and not a delivery.
"""
import sys
from pathlib import Path

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
if len(args) != 2:
    raise SystemExit("usage: ... -- <out.blend> <out.fbx>")
blend, fbx = (Path(a).resolve() for a in args)
for out in (blend, fbx):
    if out.exists():
        raise SystemExit(f"{out} exists; write a new versioned output")

# (tile_u, tile_v) in polygon order. Tile = 1001 + tile_u + 10 * tile_v.
QUADS = ((0, 0), (1, 0), (0, 1), (1, 1))

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system, scene.unit_settings.scale_length = "METRIC", 1.0

vertices, faces = [], []
for index, _tile in enumerate(QUADS):
    origin = index * 2.0
    base = index * 4
    vertices.extend([(origin, 0.0, 0.0), (origin + 1.0, 0.0, 0.0),
                     (origin + 1.0, 1.0, 0.0), (origin, 1.0, 0.0)])
    faces.append((base, base + 1, base + 2, base + 3))

mesh = bpy.data.meshes.new("UV_FIXTURE")
mesh.from_pydata(vertices, [], faces)
material = bpy.data.materials.new("ID_01")
mesh.materials.append(material)
for polygon in mesh.polygons:
    polygon.material_index = 0
if mesh.validate(clean_customdata=False) or len(mesh.polygons) != 4:
    raise SystemExit(f"UV_FIXTURE: Blender rejected the synthetic quads ({len(mesh.polygons)})")
mesh.update()

layer = mesh.uv_layers.new(name="UVMap")
for polygon, (tile_u, tile_v) in zip(mesh.polygons, QUADS):
    u0, u1 = tile_u + 0.1, tile_u + 0.9
    v0, v1 = tile_v + 0.1, tile_v + 0.9
    corners = ((u0, v0), (u1, v0), (u1, v1), (u0, v1))
    for loop_index, corner in zip(polygon.loop_indices, corners):
        layer.data[loop_index].uv = corner
mesh.update()

obj = bpy.data.objects.new("UV_FIXTURE", mesh)
scene.collection.objects.link(obj)

blend.parent.mkdir(parents=True, exist_ok=True)
fbx.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=False, object_types={"MESH", "EMPTY"},
                         apply_unit_scale=True, use_mesh_modifiers=False, add_leaf_bones=False)
print("SYNTHETIC UV_FIXTURE 4 quads tiles 1001 1002 1011 1012; delivery_passed=false")
