"""TOW02: join every TOW02_* part into one mesh SM_Vyatskaya_Vl_47_49_013_Main and export a quad FBX (runs inside
Blender, headless).

Engine gap: EG6 (panelised curtain-wall source, docs/backlog.md).

User request 2026-10-21: attach all Lego pieces into one object and check it in 3ds Max xView before NPM. No
triangulation, no transform reset here (NPM derivation does that later). Source objects (RC_*, SLAB_*) and helper
empties are not exported. Vertices are not welded across parts (the parts touch or embed by design), except the
three seams where two parts are built on the same points (xView Overlapping Vertices, groups V1-V3 of
outputs/xview-v002/qa/groups.json): body top loop / top band at 64.7, body bottom loop / soffit at 6.9, top walls /
top glass faces on the outline. Only vertex pairs of exactly these object pairs closer than SEAM_WELD_M are merged
(not a global merge by distance); the count per seam is printed. A pair whose parts would share only that point (a
bow-tie vertex) is not welded but moved apart (skip_point_contacts).

Usage:
  blender -b <textured.blend> --python scripts/join_export_blender.py -- <out_dir>
Writes <out_dir>/tow02_joined.blend and <out_dir>/SM_Vyatskaya_Vl_47_49_013_Main.fbx (+ .fbm textures); the input is
never saved.
"""
import json
import os
import sys

import bmesh
import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree

NAME = "SM_Vyatskaya_Vl_47_49_013_Main"
SEAM_WELD_M = 1e-5
POINT_SHIFT_M = 0.003     # seam pair that would touch only at a point: not welded, moved this far (skip_point_contacts)
SEAMS = (("TOW02_body", "TOW02_top"), ("TOW02_body", "TOW02_soffit"), ("TOW02_top", "TOW02_top_glass"))
SRC_ATTR = "tow02_src_part"


def weld_seams(obj, names):
    """Merge coincident vertices of the SEAMS object pairs only (names: source object of each attribute value)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    lay = bm.verts.layers.int.get(SRC_ATTR)
    bm.verts.ensure_lookup_table()
    kd = KDTree(len(bm.verts))
    for v in bm.verts:
        kd.insert(v.co, v.index)
    kd.balance()
    allowed = {frozenset(p) for p in SEAMS}
    rank = {n: i for i, n in enumerate(("TOW02_body", "TOW02_top", "TOW02_soffit", "TOW02_top_glass"))}
    targetmap, count = {}, {f"{a} | {b}": 0 for a, b in SEAMS}
    for v in bm.verts:
        a = names[v[lay]]
        for co, j, d in kd.find_range(v.co, SEAM_WELD_M):
            w = bm.verts[j]
            b = names[w[lay]]
            if j <= v.index or frozenset((a, b)) not in allowed or a == b:
                continue
            keep, drop = (v, w) if rank[a] < rank[b] else (w, v)
            while keep in targetmap:
                keep = targetmap[keep]
            if drop is keep or drop in targetmap:
                continue
            targetmap[drop] = keep
            pair = next(f"{x} | {y}" for x, y in SEAMS if {x, y} == {a, b})
            count[pair] += 1
    shifted = skip_point_contacts(bm, targetmap, count, names, lay)
    bmesh.ops.weld_verts(bm, targetmap=targetmap)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.attributes.remove(obj.data.attributes[SRC_ATTR])
    count["point_contacts_not_welded"] = shifted
    return count


def skip_point_contacts(bm, targetmap, count, names, lay):
    """A seam pair whose two parts would share only that point (no edge: e.g. a top_glass corner on a top wall
    column with more rows than the glass edge) would become a bow-tie vertex, which 3ds Max splits into coincident
    vertices. Such a pair is not welded; the dropped vertex is moved POINT_SHIFT_M into the other part's solid:
    along its face edge past the corner when it has one face there, else inward against its faces' normals
    (user decision 2026-10-21; 3 mm > Overlapping Vertices 2 mm, <= 1 cm rule)."""
    def root(v):
        while v in targetmap:
            v = targetmap[v]
        return v

    out, point = [], []
    for drop, keep in list(targetmap.items()):
        keep = root(keep)
        kn = {root(e.other_vert(keep)) for e in keep.link_edges}
        if not any(root(e.other_vert(drop)) in kn for e in drop.link_edges):
            point.append((drop, keep))
    for drop, keep in point:
        faces = list(drop.link_faces)
        if len(faces) == 1:
            nb = [e.other_vert(drop) for e in drop.link_edges if abs(e.other_vert(drop).co.z - drop.co.z) < 1e-6]
            d = (drop.co - nb[0].co) if nb else -faces[0].normal
        else:
            d = -sum((f.normal for f in faces), Vector())
        d.z = 0.0
        d.normalize()
        p0 = drop.co.copy()
        drop.co = p0 + d * POINT_SHIFT_M
        del targetmap[drop]
        pair = next(f"{x} | {y}" for x, y in SEAMS if {x, y} == {names[drop[lay]], names[keep[lay]]})
        count[pair] -= 1
        out.append(dict(part=names[drop[lay]], at=[round(c, 4) for c in p0], dir=[round(c, 3) for c in d],
                        faces=len(faces)))
    return out


def main(out_dir):
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    parts = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("TOW02_")]
    faces = sum(len(o.data.polygons) for o in parts)
    for o in list(bpy.data.objects):
        if o not in parts:
            bpy.data.objects.remove(o)
    names = sorted(o.name for o in parts)
    for o in parts:
        o.data = o.data.copy()  # never edit a mesh shared with another object
        at = o.data.attributes.new(SRC_ATTR, "INT", "POINT")
        at.data.foreach_set("value", [names.index(o.name)] * len(o.data.vertices))
    ctx = {"active_object": parts[0], "selected_editable_objects": parts, "selected_objects": parts}
    with bpy.context.temp_override(**ctx):
        bpy.ops.object.join()
    obj = parts[0]
    obj.name = obj.data.name = NAME
    if len(obj.data.polygons) != faces:
        raise RuntimeError(f"join lost faces: {faces} -> {len(obj.data.polygons)}")
    welded = weld_seams(obj, names)
    if len(obj.data.polygons) != faces:
        raise RuntimeError(f"seam weld lost faces: {faces} -> {len(obj.data.polygons)}")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, "tow02_joined.blend"), copy=False)
    for o in bpy.data.objects:
        o.select_set(o is obj)
    bpy.ops.export_scene.fbx(filepath=os.path.join(out_dir, f"{NAME}.fbx"), use_selection=True, object_types={"MESH"},
                             apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", axis_forward="-Z",
                             axis_up="Y", mesh_smooth_type="FACE", use_triangles=False, add_leaf_bones=False,
                             bake_anim=False, path_mode="COPY", embed_textures=False)
    sizes = {}
    for p in obj.data.polygons:
        sizes[len(p.vertices)] = sizes.get(len(p.vertices), 0) + 1
    print("JOIN_DONE " + json.dumps(dict(parts=len(parts), faces=len(obj.data.polygons), verts=len(obj.data.vertices),
                                         seams_welded=welded,
                                         face_sizes=sizes, materials=[m.name for m in obj.data.materials])))


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1])
