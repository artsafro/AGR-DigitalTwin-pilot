"""FBX structure facts for the parts list, in an isolated factory Blender process [D110, D111] (#339).

    blender --background --factory-startup --python-exit-code 1 \\
        --python tools/blender/fbx_structure.py -- <model.fbx> <structure.json>

Facts only, no judgement: per object its type, parent, collections (layers), mesh data (shared = component),
material slots with per-face and per-triangle material index counts, triangles, world bounding box in metres and
connected components (vertex connectivity); bbox contacts within 2 mm; the FBX sha256, Blender version and units.
FBX carries no sections (`sections: "not_in_fbx"`). `src/dt_ai/parts/readers/fbx.py` turns the facts into a draft
parts list. Nothing is written on failure: exit 1 when the FBX does not import, exit 2 when it imports but holds no
non-empty mesh (like fbx_readback.py), exit 1 when the output path is the input.
Pattern: n/a | new-case: headless FBX structure facts for the gate-1 parts list (#339).
"""
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
TOLERANCE_M = 0.002


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_geometry = _load("parts_geometry", "src/dt_ai/parts/readers/geometry.py")
_header = _load("fbx_header", "src/twinqa/fbx_header.py")
_publish = _load("parts_publish", "src/dt_ai/parts/readers/publish.py")


def fail(code, message):
    print("FBX_STRUCTURE_ERROR", message, file=sys.stderr)
    print("FBX_STRUCTURE_ERROR", message)
    sys.stdout.flush()
    sys.exit(code)


def connected_components(mesh) -> int:
    parent = list(range(len(mesh.vertices)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for edge in mesh.edges:
        a, b = find(edge.vertices[0]), find(edge.vertices[1])
        if a != b:
            parent[a] = b
    return len({find(i) for i in range(len(parent))})


def object_facts(obj, scene, scale):
    facts = {"name": obj.name, "type": obj.type, "parent": obj.parent.name if obj.parent else None,
             "collections": sorted(c.name for c in obj.users_collection if c != scene.collection)}
    if obj.type != "MESH":
        return facts
    mesh = obj.data
    mesh.calc_loop_triangles()
    faces, tris = {}, {}
    for poly in mesh.polygons:
        faces[str(poly.material_index)] = faces.get(str(poly.material_index), 0) + 1
    for tri in mesh.loop_triangles:
        tris[str(tri.material_index)] = tris.get(str(tri.material_index), 0) + 1
    world = [obj.matrix_world @ v.co for v in mesh.vertices]
    if any(not math.isfinite(c) for p in world for c in p):
        raise ValueError("non-finite vertex coordinates: " + obj.name)
    if world:
        lo = [min(p[k] for p in world) * scale for k in range(3)]
        hi = [max(p[k] for p in world) * scale for k in range(3)]
    else:
        lo = hi = [0.0, 0.0, 0.0]
    facts.update({
        "mesh": mesh.name,
        "material_slots": [s.material.name if s.material else None for s in obj.material_slots],
        "face_material_counts": dict(sorted(faces.items(), key=lambda kv: int(kv[0]))),
        "triangle_material_counts": dict(sorted(tris.items(), key=lambda kv: int(kv[0]))),
        "triangles": len(mesh.loop_triangles), "polygons": len(mesh.polygons),
        "bbox": {"min": [round(c, 9) for c in lo], "max": [round(c, 9) for c in hi]},
        "connected_components": connected_components(mesh) if mesh.vertices else 0,
    })
    return facts


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(args) != 2:
        fail(1, "usage: ... -- <model.fbx> <structure.json>")
    source, out = Path(args[0]).resolve(), Path(args[1]).resolve()
    if out == source:
        fail(1, "the output path resolves to the input FBX")
    try:
        data = source.read_bytes()
    except OSError as exc:
        fail(1, f"cannot read {source}: {exc}")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    try:
        result = bpy.ops.import_scene.fbx(filepath=str(source))
    except Exception as exc:  # report, never hide
        fail(1, f"FBX import failed: {type(exc).__name__}: {exc}")
    if "FINISHED" not in result:
        fail(1, f"FBX import returned {sorted(result)}")
    scene = bpy.context.scene
    scale = float(scene.unit_settings.scale_length)
    objects = [object_facts(o, scene, scale) for o in sorted(scene.objects, key=lambda o: o.name)]
    meshes = [o for o in objects if o["type"] == "MESH"]
    if not any(o["triangles"] for o in meshes):
        fail(2, "FBX imports but holds no non-empty mesh")
    users = {}
    for o in meshes:
        users.setdefault(o["mesh"], []).append(o["name"])
    boxes = {o["name"]: (o["bbox"]["min"], o["bbox"]["max"]) for o in meshes if o["triangles"]}
    units = {"system": scene.unit_settings.system, "scale_length": scale,
             "length_unit": scene.unit_settings.length_unit, "bbox_unit": "m",
             "fbx": _header.fbx_units(data)}
    facts = {
        "format": "fbx_structure/1",
        "source": {"name": source.name, "path": str(source), "sha256": hashlib.sha256(data).hexdigest(),
                   "bytes": len(data)},
        "blender": bpy.app.version_string, "units": units, "sections": "not_in_fbx",
        "contact_tolerance_m": TOLERANCE_M, "objects": objects,
        "components": [{"mesh": m, "objects": sorted(n)} for m, n in sorted(users.items()) if len(n) > 1],
        "contacts": _geometry.contacts(boxes, TOLERANCE_M),
    }
    _publish.publish(out, json.dumps(facts, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8"))
    print("FBX_STRUCTURE_OK", len(meshes), "meshes", len(facts["components"]), "components",
          len(facts["contacts"]), "contacts")


try:
    main()
except SystemExit:
    raise
except Exception as exc:  # report, never hide; nothing written
    fail(1, f"{type(exc).__name__}: {exc}")
