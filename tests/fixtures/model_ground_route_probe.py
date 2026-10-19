"""Blender probe for the `model-ground` skill, Steps 6 and 7 (#176). Synthetic in-memory data only.

Run: blender --background --factory-startup --python-exit-code 1 --python <this> -- <out.json>
Writes the measured result of the exact routes the skill names, plus the reviewer's failing routes as controls:

- Step 6 route: points -> merge exact XY duplicates (contradictory Z = finding) -> `mathutils.geometry.delaunay_2d_cdt`
  in XY -> faces over the original points, source Z kept. Control: `bmesh.ops.triangulate` on bare points.
- Step 7 route: each layer's vertical offset against the common flat datum is recorded, the relief is sampled at the
  vertex XY with a downward `BVHTree.ray_cast`, z = relief + offset; a miss is listed, never moved. Control: Shrinkwrap
  PROJECT along Z (collapses the layers).
"""
import json
import sys

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import delaunay_2d_cdt

OUT = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system = "METRIC"
bpy.context.scene.unit_settings.scale_length = 1.0


def relief_from_points(points, eps=1e-6):
    """Step 6: returns (verts xyz, faces, status, findings)."""
    merged, findings = {}, []
    for x, y, z in points:
        key = (round(x / eps), round(y / eps))
        if key in merged and abs(merged[key][2] - z) > 1e-6:
            findings.append({"xy": [x, y], "z": [merged[key][2], z]})
            continue
        merged.setdefault(key, (x, y, z))
    pts = list(merged.values())
    if findings:
        return [], [], "contradictory_z", findings
    if len(pts) < 3:
        return [], [], "too_few_points", findings
    verts2d, _e, faces, orig_verts, _oe, _of = delaunay_2d_cdt([Vector((x, y)) for x, y, _ in pts], [], [], 0, eps)
    if not faces:
        return [], [], "collinear", findings
    verts = []
    for i, co in enumerate(verts2d):
        if not orig_verts[i]:
            return [], [], "new_vertex_without_z", findings
        verts.append((co.x, co.y, pts[orig_verts[i][0]][2]))
    return verts, [tuple(f) for f in faces], "ok", findings


def make_obj(name, verts, faces):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def layer(name, z, half=0.5, material_index=0):
    obj = make_obj(name, [(-half, -half, z), (half, -half, z), (half, half, z), (-half, half, z)], [(0, 1, 2, 3)])
    uv = obj.data.uv_layers.new()
    for i, loop in enumerate(uv.data):
        loop.uv = (0.25 * i, 0.75)
    obj.data.polygons[0].material_index = material_index
    return obj


def snapshot(obj):
    me = obj.data
    return {"co": [list(v.co) for v in me.vertices], "uv": [list(l.uv) for l in me.uv_layers[0].data],
            "mat": [p.material_index for p in me.polygons]}


def project_vertical(obj, relief, datum):
    """Step 7: z = relief(x, y) + (z - datum); vertices outside the relief are listed, not moved."""
    deps = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(relief, deps)
    top = max(v.co.z for v in relief.data.vertices) + 1000.0
    misses = []
    for v in obj.data.vertices:
        hit, _n, _i, _d = bvh.ray_cast(Vector((v.co.x, v.co.y, top)), Vector((0, 0, -1)))
        if hit is None:
            misses.append(v.index)
            continue
        v.co.z = hit.z + (v.co.z - datum)
    return misses


result = {"blender": bpy.app.version_string}

# Step 6, the reviewer's input and degenerate inputs.
four = [(0, 0, 0), (1, 0, 0.1), (1, 1, 0.2), (0, 1, 0.1)]
bm = bmesh.new()
for p in four:
    bm.verts.new(p)
bmesh.ops.triangulate(bm, faces=list(bm.faces))
result["control_bmesh_triangulate_points"] = {"vertices": len(bm.verts), "faces": len(bm.faces)}
bm.free()
cases = {
    "four": four,
    "empty": [],
    "two": [(0, 0, 0), (1, 0, 1)],
    "collinear": [(0, 0, 0), (1, 1, 1), (2, 2, 2)],
    "duplicate_same_z": four + [(1, 1, 0.2)],
    "duplicate_contradictory_z": four + [(1, 1, 0.5)],
}
step6 = {}
for name, pts in cases.items():
    verts, faces, status, findings = relief_from_points(pts)
    src = {(round(x, 6), round(y, 6)): z for x, y, z in pts}
    step6[name] = {"status": status, "faces": len(faces), "vertices": len(verts), "findings": findings,
                   "max_dz_vs_source_m": max((abs(z - src[(round(x, 6), round(y, 6))]) for x, y, z in verts),
                                             default=None)}
result["step6"] = step6

# Step 7, two overlapping layers 6 mm apart, relief z = x.
relief = make_obj("synthetic_relief", [(-2, -2, -2), (2, -2, 2), (2, 2, 2), (-2, 2, -2)], [(0, 1, 2, 3)])
datum = 2.0
base, top_layer = layer("synthetic_base", datum, material_index=0), layer("synthetic_top", datum + 0.006, material_index=1)
before = {o.name: snapshot(o) for o in (base, top_layer)}
misses = {o.name: project_vertical(o, relief, datum) for o in (base, top_layer)}
after = {o.name: snapshot(o) for o in (base, top_layer)}
outside = layer("synthetic_outside", datum, half=3.0)


def gap_below(upper, lower, x, y):
    """Vertical distance between two layer surfaces at XY (face-centre check)."""
    deps = bpy.context.evaluated_depsgraph_get()
    zs = []
    for obj in (upper, lower):
        hit = BVHTree.FromObject(obj, deps).ray_cast(Vector((x, y, 1000.0)), Vector((0, 0, -1)))[0]
        zs.append(None if hit is None else hit.z)
    return None if None in zs else zs[0] - zs[1]


result["step7"] = {"before": before, "after": after, "misses": misses, "datum": datum,
                   "outside_misses": project_vertical(outside, relief, datum),
                   "face_centre_gap_m": gap_below(top_layer, base, 0.0, 0.0)}

# Ridge inside a cell: relief z = -|x|; base is one 2 x 2 m cell, top is the same extent split at x = 0, so the
# corner vertices agree and only the face interior shows the bend.
ridge = make_obj("synthetic_ridge", [(-2, -2, -2), (0, -2, 0), (0, 2, 0), (-2, 2, -2), (2, -2, -2), (2, 2, -2)],
                 [(0, 1, 2, 3), (1, 4, 5, 2)])
rb = layer("ridge_base", datum, half=1.0)
rt = make_obj("ridge_top", [(x, y, datum + 0.006) for x, y in ((-1, -1), (0, -1), (1, -1), (1, 1), (0, 1), (-1, 1))],
              [(0, 1, 4, 5), (1, 2, 3, 4)])
for o in (rb, rt):
    project_vertical(o, ridge, datum)
result["ridge"] = {"corner_gap_m": rt.data.vertices[0].co.z - rb.data.vertices[0].co.z,
                   "face_centre_gap_m": gap_below(rt, rb, 0.0, 0.0)}

# Control: Shrinkwrap PROJECT along Z on fresh copies.
shrink = []
for i, z in enumerate((datum, datum + 0.006)):
    obj = layer(f"control_layer_{i}", z)
    mod = obj.modifiers.new("ctl", "SHRINKWRAP")
    mod.target, mod.wrap_method, mod.use_project_z = relief, "PROJECT", True
    mod.use_negative_direction = mod.use_positive_direction = True
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    shrink.append([v.co.z for v in obj.data.vertices])
result["control_shrinkwrap_gaps_m"] = [b - a for a, b in zip(*shrink)]

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(result, fh, indent=1)
print("MODEL_GROUND_PROBE_OK", OUT)
