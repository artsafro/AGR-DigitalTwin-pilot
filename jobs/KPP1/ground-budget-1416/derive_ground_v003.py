"""KPP1 #1416 [D308]: derived NPM Ground copy v003 = accepted v002 + #1371 bridge + V004 repairs + V012 names.

Pattern: n/a | new-case: job script (Blender headless) on OUR copy only; the customer original and v002
are read-only inputs (hash-checked). Steps per mesh: rename to SM_Kpp_1_<suffix>, apply the frame bridge
into the vertices (identity object transform), weld vertices <= 2 mm (reg tolerance), delete faces that
repeat a vertex set, dissolve degenerate (< 2 mm) edges, delete loose vertices/edges, and on GroundEl (MAF)
recalculate face normals outward. Every change is counted in repair-report.json.
Review P1 (#1418, Ground v004): the bmesh orientation missed 4 GroundEl faces that the FBX readback rule
(twinqa.geometry.maf_surface, position weld 1e-5 m, zero-area faces left out) still counts as flipped, so a
last pass reverses `ground_copy_plan.readback_flips` and re-checks with surface_facts itself (exit 2 when
flipped or inconsistent stays > 0). Output v004 = v003 + that winding pass; vertices / UV / counts unchanged.

Run: blender -b --factory-startup -noaudio --python derive_ground_v003.py -- <v002.fbx> <sha256> <customer.fbx> <sha256> <mapping.json> <new_out_dir>
(the customer FBX gives back the embedded textures v002 lost.)
Fail-closed: wrong hash, existing / aliasing output, unmapped mesh name, non-finite vertex, triangle total
above 180 000, renamed materials / UV layers, or UV bounds outside the input bounds exit 2 and leave only
`<out>.partial` (never the final dir).
"""
import hashlib
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ground_copy_plan as plan  # noqa: E402
import importlib.util  # noqa: E402

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
from adapters.max.agr_tools import build_manifest as bm  # noqa: E402

_MS = importlib.util.spec_from_file_location(
    "maf_surface", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
                                "src", "twinqa", "geometry", "maf_surface.py"))
maf_surface = importlib.util.module_from_spec(_MS)
_MS.loader.exec_module(maf_surface)

LIMIT = 180000
TOL = 0.002
MAF = "SM_Kpp_1_GroundEl"


def die(msg):
    print("DERIVE-FAIL", msg)
    sys.exit(2)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def meshes():
    return sorted((o for o in bpy.data.objects if o.type == "MESH"), key=lambda o: o.name)


def census():
    out = {}
    for o in meshes():
        me = o.data
        uv = me.uv_layers.active
        us = [d.uv for d in uv.data] if uv else []
        for v in me.vertices:
            if not all(math.isfinite(c) for c in v.co):
                die(f"non-finite vertex in {o.name}")
        ws = [o.matrix_world @ v.co for v in me.vertices]
        out[o.name] = {
            "tris": sum(len(p.vertices) - 2 for p in me.polygons), "polys": len(me.polygons),
            "verts": len(me.vertices), "materials": [m.name if m else None for m in me.materials],
            "uv_layers": [l.name for l in me.uv_layers],
            "uv_bounds": [min(u.x for u in us), min(u.y for u in us), max(u.x for u in us), max(u.y for u in us)] if us else None,
            "bounds": [min(p[i] for p in ws) for i in range(3)] + [max(p[i] for p in ws) for i in range(3)],
        }
    return out


def orient_closed_shells(bm):
    """Mirror of twinqa.geometry.maf_surface: per manifold component make the winding consistent and
    outward by the signed volume about (centre x, centre y, min z); flat components stay as they are."""
    from collections import deque
    bm.faces.ensure_lookup_table()
    bm.faces.index_update()
    seen, to_flip, comps, undet = set(), [], 0, 0
    for seed in bm.faces:
        if seed.index in seen:
            continue
        flip, queue, faces = {seed.index: False}, deque([seed]), [seed]
        seen.add(seed.index)
        while queue:
            f = queue.popleft()
            for loop in f.loops:
                e = loop.edge
                if len(e.link_faces) != 2:
                    continue
                g = e.link_faces[0] if e.link_faces[1] == f else e.link_faces[1]
                if g == f or g.index in flip:
                    continue
                other = next(lp for lp in g.loops if lp.edge == e)
                same = loop.vert == other.vert  # same direction along the shared edge = inconsistent
                flip[g.index] = flip[f.index] ^ same
                seen.add(g.index)
                queue.append(g)
                faces.append(g)
        comps += 1
        pts_all = [v.co for f in faces for v in f.verts]
        xs, ys, zs = [p.x for p in pts_all], [p.y for p in pts_all], [p.z for p in pts_all]
        ox, oy, oz = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, min(zs)
        vol = 0.0
        for f in faces:
            pts = [v.co for v in f.verts]
            if flip[f.index]:
                pts.reverse()
            for i in range(1, len(pts) - 1):
                a, b, c = pts[0], pts[i], pts[i + 1]
                ax, ay, az = a.x - ox, a.y - oy, a.z - oz
                bx, by, bz = b.x - ox, b.y - oy, b.z - oz
                cx, cy, cz = c.x - ox, c.y - oy, c.z - oz
                vol += (ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)) / 6
        diag = math.dist((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)))
        if abs(vol) <= 1e-9 or abs(vol) <= 1e-6 * diag ** 3:
            undet += 1
            continue
        outward_is_propagated = vol > 0
        to_flip.extend(f for f in faces if flip[f.index] == outward_is_propagated)
    if to_flip:
        bmesh.ops.reverse_faces(bm, faces=to_flip, flip_multires=False)
    bm.normal_update()
    return {"components": comps, "undetermined_components": undet, "faces_flipped": len(to_flip)}


def repair(o, flip):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    rep = {"verts_in": len(bm.verts), "faces_in": len(bm.faces)}
    n0 = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=TOL)
    rep["welded_verts"] = n0 - len(bm.verts)
    n0 = len(bm.faces)
    bmesh.ops.dissolve_degenerate(bm, dist=TOL, edges=bm.edges[:])
    rep["degenerate_faces_removed"] = n0 - len(bm.faces)
    seen, dup = set(), []
    for f in bm.faces:
        k = frozenset(v.index for v in f.verts)
        if k in seen:
            dup.append(f)
        else:
            seen.add(k)
    bmesh.ops.delete(bm, geom=dup, context="FACES_ONLY")
    rep["duplicate_faces_removed"] = len(dup)
    loose_e = [e for e in bm.edges if not e.link_faces]
    bmesh.ops.delete(bm, geom=loose_e, context="EDGES")
    loose_v = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose_v, context="VERTS")
    rep["loose_edges_removed"], rep["loose_verts_removed"] = len(loose_e), len(loose_v)
    # triangulate first: new diagonals must get the same hard-edge / winding treatment
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    if flip:
        rep.update(orient_closed_shells(bm))
        # MAF smoothing (V004): an edge whose faces meet at > 40 deg is hard, never soft
        hard = 0
        for e in bm.edges:
            if len(e.link_faces) == 2 and e.smooth and e.calc_face_angle(0.0) > math.radians(40.0):
                e.smooth = False
                hard += 1
        rep["edges_made_hard_gt_40deg"] = hard
    rep["verts_out"], rep["faces_out"] = len(bm.verts), len(bm.faces)
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()
    return rep


def readback_orient(o):
    """Reverse the faces the FBX readback rule still counts as flipped/inconsistent, then re-check with it."""
    me = o.data
    # the FBX importer runs Mesh.validate(): it drops the polygons triangulation made duplicate, which
    # rewires the adjacency the readback sees (5 GroundEl tris in v003). Apply the same cleanup here so
    # the oriented mesh IS the readback mesh; the dropped faces are counted in the report.
    n_before = len(me.polygons)
    me.validate(verbose=False, clean_customdata=False)
    dropped = n_before - len(me.polygons)
    coords = [tuple(v.co) for v in me.vertices]
    polys = [list(p.vertices) for p in me.polygons]
    if not polys:
        die(f"{o.name} has no faces")
    try:
        flips = plan.readback_flips(coords, polys)
    except plan.PlanError as exc:
        die(f"{o.name}: {exc}")
    if flips:
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        bmesh.ops.reverse_faces(bm, faces=[bm.faces[i] for i in sorted(flips)], flip_multires=False)
        bm.normal_update()
        bm.to_mesh(me)
        bm.free()
        me.update()
    polys = [list(p.vertices) for p in me.polygons]
    facts = maf_surface.surface_facts(coords, polys, [[(0.0, 0.0, 1.0)] * len(p) for p in polys])
    if facts["flipped_faces"] or facts["inconsistent_edges"]:
        die(f"{o.name}: readback still sees flipped {facts['flipped_faces']}, "
            f"inconsistent {facts['inconsistent_edges']}")
    return {"validate_faces_dropped": dropped, "readback_faces_flipped": len(flips), "readback_components": facts["components"],
            "readback_undetermined_components": facts["undetermined_components"]}


def transplant_materials(cust_objs):
    """v002 lost the embedded textures; give every v002 mesh the customer's own material datablocks
    (same names, same slot order) so the copy keeps the customer's textures. Missing / reordered
    slots or an image without pixels are errors naming them."""
    import re
    for o in meshes():
        if o.name.endswith("__cust"):
            continue
        c = cust_objs.get(o.name)
        if c is None:
            die(f"v002 mesh {o.name} has no customer counterpart")
        want = [m.name if m else None for m in c.data.materials]
        got = [re.sub(r"\.\d{3}$", "", m.name) if m else None for m in o.data.materials]
        if want != got:
            die(f"material slots differ on {o.name}: v002 {got} vs customer {want}")
        for i, m in enumerate(c.data.materials):
            o.data.materials[i] = m
    for c in cust_objs.values():
        bpy.data.objects.remove(c, do_unlink=True)
    for m in list(bpy.data.materials):
        if m.users == 0:
            bpy.data.materials.remove(m)
    imgs = {}
    for o in meshes():
        for m in o.data.materials:
            for n in (m.node_tree.nodes if m and m.use_nodes else []):
                if n.type == "TEX_IMAGE":
                    if n.image is None or n.image.size[0] == 0:
                        die(f"material {m.name} image {getattr(n.image, 'name', None)} has no pixels")
                    if not n.image.packed_file:
                        n.image.pack()
                    imgs[n.image.name] = list(n.image.size)
    if not imgs:
        die("no textures found on the customer materials")
    return imgs


def record_export(fbx, src, want, cust, cwant, mapping, mapping_hash, names):
    """Record actual geometry, embedded-map and bridge dependencies per component role [D333].

    The source/customer FBX both contain all three components; grouping does not turn Flora into Ground.
    No delivery geometry or historical approved file is rewritten by this hook.
    """
    roles = {}
    for name in names:
        roles.setdefault(bm.role_of(name), []).append(name)
    dependencies = [{'role': role, 'master': path, 'master_sha256': digest, 'parts': sorted(parts)}
                    for role, parts in sorted(roles.items())
                    for path, digest in ((src, want), (cust, cwant), (mapping, mapping_hash))]
    return bm.write_export_derivation([fbx], src, os.path.join(os.path.dirname(fbx), 'derivation'),
        master_sha256=want, role='ground', dependencies=dependencies)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    if len(argv) != 6:
        die("usage: <v002.fbx> <sha256> <customer.fbx> <sha256> <mapping.json> <new_out_dir>")
    src, want, cust, cwant, mapping = (os.path.realpath(argv[0]), argv[1], os.path.realpath(argv[2]),
                                       argv[3], os.path.realpath(argv[4]))
    mapping_hash = sha(mapping)
    try:
        out = plan.check_out_dir(argv[5], [src, cust, mapping])
        rot, t = plan.load_bridge(mapping)
    except (plan.PlanError, OSError, KeyError, ValueError) as exc:
        die(str(exc))
    for path, h in ((src, want), (cust, cwant)):
        if sha(path) != h:
            die(f"input hash of {path} != {h}")
    got = want
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=cust)
    cust_objs = {}
    for o in meshes():
        cust_objs[o.name] = o
        o.name = o.name + "__cust"
    bpy.ops.import_scene.fbx(filepath=src)
    textures = transplant_materials(cust_objs)
    before = census()
    try:
        names = plan.rename_map(before)
    except plan.PlanError as exc:
        die(str(exc))
    bridge = Matrix(plan.column_matrix(rot, t))
    reps = {}
    for o in meshes():
        new = names[o.name]
        o.name, o.data.name = new, new
        if o.name != new:
            die(f"rename collided: {new}")
        o.data.transform(bridge @ o.matrix_world)
        o.matrix_world = Matrix.Identity(4)
        reps[new] = repair(o, flip=(new == MAF))
        if new == MAF:
            reps[new].update(readback_orient(o))
    after = census()
    total = sum(c["tris"] for c in after.values())
    if total > LIMIT:
        die(f"result {total} > {LIMIT}")
    for old, new in names.items():
        a, b = after[new], before[old]
        if a["materials"] != b["materials"] or a["uv_layers"] != b["uv_layers"]:
            die(f"materials / UV layers changed on {new}")
        if not (all(a["uv_bounds"][i] >= b["uv_bounds"][i] - 1e-6 for i in (0, 1))
                and all(a["uv_bounds"][i] <= b["uv_bounds"][i] + 1e-6 for i in (2, 3))):
            die(f"UV bounds of {new} left the input bounds (UDIM change)")
    part = out + ".partial"
    os.makedirs(part)
    fbx = os.path.join(part, "0000_Kpp_1_Ground.fbx")
    # export settings of tools/derive/export_npm.py (1 unit = 1 m, embedded textures) with per-edge
    # smoothing so the customer's hard MAF edges survive (v002's FACE smoothing softened them)
    bpy.ops.export_scene.fbx(filepath=fbx, use_selection=False, object_types={"MESH"},
                             axis_forward="Y", axis_up="Z", apply_unit_scale=True,
                             apply_scale_options="FBX_SCALE_UNITS", global_scale=1.0, bake_space_transform=False,
                             use_mesh_modifiers=False, mesh_smooth_type="EDGE", use_triangles=False,
                             use_custom_props=False, add_leaf_bones=False, bake_anim=False,
                             path_mode="COPY", embed_textures=True)
    record_export(fbx, src, want, cust, cwant, mapping, mapping_hash, names.values())
    report = {"source": src, "source_sha256": got, "mapping": mapping, "bridge_rotation_row": rot,
              "bridge_translation": t, "rename": names, "textures": textures, "customer_fbx": cust, "customer_sha256": cwant, "tol_m": TOL, "repairs": reps,
              "before": before, "after": after, "total_before": sum(c["tris"] for c in before.values()),
              "total_after": total, "output_fbx": "0000_Kpp_1_Ground.fbx", "output_sha256": sha(fbx),
              "blender": bpy.app.version_string}
    with open(os.path.join(part, "repair-report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    os.rename(part, out)
    print("DERIVE-OK", json.dumps({"total_before": report["total_before"], "total_after": total}), json.dumps(reps))


main()
