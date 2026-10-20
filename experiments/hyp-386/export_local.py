"""EXPERIMENT COPY for hypothesis #386 (not production; tools/export/export_mesh_blender.py is unchanged).

Only intervention: a dump mesh may carry `matrix_world` (4x4 rows); the local vertices go to
from_pydata unchanged and that matrix is assigned as the object's matrix_world. A 4th argument
receives a pre-FBX receipt (raw float32 local coords and stored matrix as Python floats, binary64
world reconstruction). Everything else (names, topology, materials, units, validation, FBX options)
is the production code verbatim.

    blender --background --factory-startup --disable-autoexec --python-exit-code 1 \
        --python experiments/hyp-386/export_local.py -- <dump.json> <out.blend> <out.fbx> <prefbx.json>

One mesh object per dump mesh, its polygons as given (`polygons`, else rebuilt from `polygon_sizes`
over triangles in fan order, else triangles); material slot index + 1 = material id
(docs/domain/materials.md), slots named ID_<n>; every LEVEL_<name> helper as an empty at its
location. Both outputs are new files: an existing path is refused. Units: metres, scale 1.
Pattern: none — export tooling, not a building node (REVIEW_CHECKLIST Q1: new-case).
"""
import json
import sys
from pathlib import Path

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
if len(args) != 4:
    raise SystemExit("usage: ... -- <dump.json> <out.blend> <out.fbx> <prefbx.json>")
source, blend, fbx, prefbx = (Path(a).resolve() for a in args)
for out in (blend, fbx, prefbx):
    if out.exists():
        raise SystemExit(f"{out} exists; write a new versioned output")
dump = json.loads(source.read_text(encoding="utf-8"))


def polygons(mesh):
    """(polygon vertex lists, material id per polygon). Anything that cannot be rebuilt exactly is an
    error: one material id per triangle, none 0, one id per polygon, and a polygon from
    `polygon_sizes` only when its triangles form a fan (else the triangles are written as they are)."""
    name, tris = mesh["name"], mesh["triangles"]
    mids = mesh.get("material_ids")
    if mids is None or len(mids) != len(tris):
        raise SystemExit(f"{name}: {0 if mids is None else len(mids)} material ids for {len(tris)} triangles")
    if any(m < 1 for m in mids):
        raise SystemExit(f"{name}: material id 0 (unassigned) has no slot; assign every face first")
    if "polygons" in mesh:
        groups = [list(p) for p in mesh["polygons"]]
    else:
        sizes = mesh.get("polygon_sizes")
        groups = None
        if sizes and sum(max(n - 2, 0) for n in sizes) == len(tris):
            groups, k = [], 0
            for n in sizes:
                fan = tris[k:k + n - 2]
                if any(t[0] != fan[0][0] or (i and t[1] != fan[i - 1][2]) for i, t in enumerate(fan)):
                    groups = None                       # not a fan: keep the triangles as they are
                    break
                groups.append([fan[0][0], fan[0][1]] + [t[2] for t in fan])
                k += n - 2
        if groups is None:
            groups = [list(t) for t in tris]
    out, k = [], 0
    for poly in groups:
        n = max(len(poly) - 2, 0)
        ids = set(mids[k:k + n])
        if len(ids) != 1 or len(set(poly)) != len(poly):
            raise SystemExit(f"{name}: polygon {len(out)} has ids {sorted(ids)} / repeated vertices {poly}")
        out.append((poly, ids.pop()))
        k += n
    if k != len(tris):
        raise SystemExit(f"{name}: polygons cover {k} of {len(tris)} triangles")
    return out


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system, scene.unit_settings.scale_length = "METRIC", 1.0
materials = {}
for m in dump["meshes"]:
    polys = polygons(m)
    data = bpy.data.meshes.new(m["name"])
    data.from_pydata([tuple(v) for v in m["vertices"]], [], [p for p, _ in polys])
    top = max(mid for _, mid in polys)
    for n in range(1, top + 1):
        if n not in materials:
            materials[n] = bpy.data.materials.new(f"ID_{n:02d}")
        data.materials.append(materials[n])
    for poly, (_, mid) in zip(data.polygons, polys):
        poly.material_index = mid - 1
    if data.validate(clean_customdata=False) or len(data.polygons) != len(polys):
        raise SystemExit(f"{m['name']}: Blender rejected or changed polygons ({len(data.polygons)} of {len(polys)})")
    data.update()
    obj = bpy.data.objects.new(m["name"], data)
    scene.collection.objects.link(obj)
    if "matrix_world" in m:                                  # #386 intervention
        from mathutils import Matrix
        obj.matrix_world = Matrix(m["matrix_world"])
for h in dump.get("helpers", []):
    empty = bpy.data.objects.new(h["name"], None)
    empty.location = h["location"]
    scene.collection.objects.link(empty)

bpy.context.view_layer.update()                              # #386 pre-FBX receipt
receipt = []
for ob in scene.objects:
    if ob.type != "MESH":
        continue
    mw = [[float(ob.matrix_world[r][c]) for c in range(4)] for r in range(4)]
    raw = [tuple(float(c) for c in v.co) for v in ob.data.vertices]
    world = [tuple(mw[r][0] * x + mw[r][1] * y + mw[r][2] * z + mw[r][3] for r in range(3)) for x, y, z in raw]
    receipt.append({"name": ob.name, "matrix_world": mw, "location": [float(c) for c in ob.location],
                    "rotation_euler": [float(c) for c in ob.rotation_euler], "scale": [float(c) for c in ob.scale],
                    "raw": raw, "world": world})
prefbx.parent.mkdir(parents=True, exist_ok=True)
prefbx.write_text(json.dumps({"blender": bpy.app.version_string, "objects": receipt}), encoding="utf-8")
blend.parent.mkdir(parents=True, exist_ok=True)
fbx.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=False, object_types={"MESH", "EMPTY"},
                         apply_unit_scale=True, use_mesh_modifiers=False, add_leaf_bones=False)
print(f"EXPORT-MESH {len(dump['meshes'])} meshes, {len(dump.get('helpers', []))} helpers -> {blend.name}, {fbx.name}")
