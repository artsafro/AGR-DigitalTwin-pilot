# Ported from AGR max/AGR_Workbench/check_fbx.py (sha256 e8c032b17279) and
# tools/profile_snapshot_common.py (sha256 cbb176e2b241) object/image facts on 2026-10-06; changes: one standalone
# script, no RunRecord/config files, adds triangles, polygon degrees, UV channels, UDIM tiles,
# mirrored UV triangles, transforms, embedded image facts, regulatory topology counts and GroundEl maf_surface
# (corner normals for smoothing and flipped faces) for the V002-V013 scene stages.
# material image maps by BSDF socket (2026-10-16, #191 Flora maps, V005).
"""Structural FBX readback in an isolated factory Blender process.

    blender --background --factory-startup --python-exit-code 1 \
        --python tools/blender/fbx_readback.py -- <model.fbx> <report.json>

Readback facts only; it does not judge the delivery (twinqa.scene does) and never writes
the source. Exit 2 when the file imports but holds no non-empty mesh.
"""
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import bpy

_TOPOLOGY = None


def _topology_module():
    """Load the regulatory counter by path. Blender runs this file as a script, not a package."""
    global _TOPOLOGY
    if _TOPOLOGY is None:
        path = Path(__file__).resolve().parents[2] / "src" / "twinqa" / "geometry" / "topology.py"
        spec = importlib.util.spec_from_file_location("regulatory_topology", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _TOPOLOGY = module
    return _TOPOLOGY
ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("maf_surface", ROOT / "src/twinqa/geometry/maf_surface.py")
_maf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_maf)
surface_facts = _maf.surface_facts

args = sys.argv[sys.argv.index("--") + 1:]
if len(args) != 2:
    raise SystemExit("usage: ... -- <model.fbx> <report.json>")
source, out = Path(args[0]).resolve(), Path(args[1]).resolve()


def _loop_normals(mesh):
    """Per-loop normals: corner_normals on Blender 4.1+, split normals on older builds."""
    count = len(mesh.loops)
    try:
        corners = mesh.corner_normals
        if len(corners) != count:
            raise RuntimeError("corner_normals length")
        return [corners[i].vector.copy() for i in range(count)]
    except (AttributeError, RuntimeError, TypeError):
        mesh.calc_normals_split()
        return [mesh.loops[i].normal.copy() for i in range(count)]


def udim(u, v):
    return 1001 + int(math.floor(u)) + 10 * int(math.floor(v)) if 0 <= u < 10 and v >= 0 else None


def mesh_facts(obj):
    mesh = obj.data
    mesh.calc_loop_triangles()
    world = [obj.matrix_world @ v.co for v in mesh.vertices]
    if any(not math.isfinite(c) for p in world for c in p):
        raise ValueError("non-finite vertex coordinates: " + obj.name)
    degrees = {}
    for poly in mesh.polygons:
        degrees[len(poly.vertices)] = degrees.get(len(poly.vertices), 0) + 1
    facts = {
        "name": obj.name,
        "vertices": len(mesh.vertices),
        "polygons": len(mesh.polygons),
        "triangles": len(mesh.loop_triangles),
        "polygon_degrees": {str(k): v for k, v in sorted(degrees.items())},
        "bounds_m": [[min(p[i] for p in world) for i in range(3)],
                     [max(p[i] for p in world) for i in range(3)]] if world else None,
        "location": list(obj.location),
        "rotation_euler_deg": [math.degrees(a) for a in obj.rotation_euler],
        "scale": list(obj.scale),
        "world_scale": list(obj.matrix_world.to_scale()),
        "parent": obj.parent.name if obj.parent else None,
        "uv_channels": len(mesh.uv_layers),
        "materials": [s.material.name if s.material else None for s in obj.material_slots],
        "udim_tiles": [],
        "mirrored_uv_triangles": 0,
    }
    uv = mesh.uv_layers.active
    if uv:
        tiles, mirrored = set(), 0
        for tri in mesh.loop_triangles:
            a, b, c = (uv.data[i].uv for i in tri.loops)
            area = (b.x - a.x) * (c.y - a.y) - (c.x - a.x) * (b.y - a.y)
            mirrored += area < 0  # negative winding in UV = mirrored island (reg p.31)
            tiles.add(udim((a.x + b.x + c.x) / 3, (a.y + b.y + c.y) / 3))
        facts["udim_tiles"] = sorted(t for t in tiles if t is not None)
        facts["uv_outside_udim_grid"] = None in tiles
        facts["mirrored_uv_triangles"] = mirrored
    try:
        from mathutils.bvhtree import BVHTree

        coords = [[float(p.x), float(p.y), float(p.z)] for p in world]
        polys = [list(p.vertices) for p in mesh.polygons]
        edge_ix = [tuple(int(i) for i in e.vertices) for e in mesh.edges]
        tree = BVHTree.FromPolygons(world, polys, epsilon=0.0)
        overlaps = tree.overlap(tree) or []
        pairs = [(int(a), int(b)) for a, b in overlaps if a != b]
        facts["topology"] = _topology_module().count_defects(coords, polys, edge_ix, candidate_pairs=pairs)
    except Exception as exc:  # record, never hide, never crash the readback
        facts["topology"] = {"error": f"{type(exc).__name__}: {exc}"}
    if obj.name.endswith("_GroundEl"):
        try:
            xform = obj.matrix_world.to_3x3().inverted_safe().transposed()
            loops = _loop_normals(mesh)
            world_loops = []
            for normal in loops:
                transformed = xform @ normal
                length = transformed.length
                if length:
                    transformed /= length
                world_loops.append([transformed.x, transformed.y, transformed.z])
            coords = [[c for c in p] for p in world]
            polys = [list(p.vertices) for p in mesh.polygons]
            corner_normals = [world_loops[p.loop_start:p.loop_start + p.loop_total] for p in mesh.polygons]
            facts["maf_surface"] = surface_facts(coords, polys, corner_normals)
        except Exception as exc:
            facts["maf_surface"] = {"error": f"{type(exc).__name__}: {exc}"}
    return facts


def image_facts():
    images = []
    for image in bpy.data.images:
        if image.type != "IMAGE":
            continue
        packed = bytes(image.packed_file.data) if image.packed_file else None
        images.append({"name": image.name, "size": list(image.size), "packed": packed is not None,
                       "packed_bytes": len(packed) if packed else 0,
                       "packed_sha256": hashlib.sha256(packed).hexdigest() if packed else None,
                       "filepath": image.filepath})
    return images


def material_facts():
    """Per material: image maps as the BSDF input socket they reach (e.g. Base Color, Alpha, Normal)."""
    materials = []
    for mat in bpy.data.materials:
        maps = []
        tree = mat.node_tree if mat.use_nodes else None
        for node in (tree.nodes if tree else []):
            if node.type != "TEX_IMAGE" or node.image is None:
                continue
            todo, seen = [(link, link.from_socket.name) for out in node.outputs for link in out.links], set()
            while todo:
                link, output = todo.pop()
                if link.as_pointer() in seen:
                    continue
                seen.add(link.as_pointer())
                if link.to_node.type.startswith("BSDF_"):
                    maps.append({"image": node.image.name, "output": output, "socket": link.to_socket.name})
                else:
                    todo.extend((nxt, output) for out in link.to_node.outputs for nxt in out.links)
        unique = {(m["socket"], m["image"], m["output"]): m for m in maps}
        materials.append({"name": mat.name, "maps": [unique[k] for k in sorted(unique)]})
    return materials


report = {"source": str(source), "readback_ok": False, "blender": bpy.app.version_string,
          "scope": "structural readback only; not a delivery verdict", "meshes": [], "other_objects": []}
try:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(source))
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH":
            report["meshes"].append(mesh_facts(obj))
        else:
            report["other_objects"].append({"name": obj.name, "type": obj.type})
    report["images"] = image_facts()
    report["materials"] = material_facts()
    report["readback_ok"] = bool(report["meshes"]) and all(m["polygons"] > 0 for m in report["meshes"])
    if not report["readback_ok"]:
        report["error"] = "no non-empty meshes"
except Exception as exc:  # report, never hide
    report["error"] = f"{type(exc).__name__}: {exc}"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print("TWINQA_READBACK", report["readback_ok"])
if not report["readback_ok"]:
    sys.exit(2)
