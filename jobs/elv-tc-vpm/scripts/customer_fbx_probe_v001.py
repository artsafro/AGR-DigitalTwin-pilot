"""elv-tc-vpm: read an FBX back (customer blank or ours) and dump facts + world triangles for overlays.

blender -b --factory-startup --python customer_fbx_probe_v001.py -- <in.fbx> <out.json> <out.npz>
Reports per mesh: transform, tris, slots, faces per slot, UV layers, UDIM tiles per slot, bbox (world and local),
open / non-manifold edges raw and after a 2 mm weld (copy), boundary loops of the welded copy (length, bbox).
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
src, out, npz = argv[0], argv[1], argv[2]
for p in (out, npz):
    if os.path.exists(p):
        raise SystemExit("output exists: " + p)
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.import_scene.fbx(filepath=src)
sc = bpy.context.scene


def r(v, n=4):
    return [round(float(x), n) for x in v]


def loops_of(bm, edges):
    """group boundary edges into connected chains; return list of (n_edges, length, bbox)."""
    es = set(edges)
    adj = {}
    for e in es:
        for v in e.verts:
            adj.setdefault(v, []).append(e)
    seen, res = set(), []
    for e in es:
        if e in seen:
            continue
        stack, comp = [e], []
        seen.add(e)
        while stack:
            x = stack.pop()
            comp.append(x)
            for v in x.verts:
                for y in adj[v]:
                    if y not in seen:
                        seen.add(y)
                        stack.append(y)
        pts = [v.co for x in comp for v in x.verts]
        res.append({"edges": len(comp), "length_m": round(sum(x.calc_length() for x in comp), 3),
                    "bbox": [r([min(p[i] for p in pts) for i in range(3)], 3), r([max(p[i] for p in pts) for i in range(3)], 3)]})
    res.sort(key=lambda d: -d["length_m"])
    return res


rep = {"fbx": src, "scene_unit": [sc.unit_settings.system, sc.unit_settings.scale_length], "objects": {}}
arrays = {}
ucx_tris = []
for ob in sc.objects:
    d = {"type": ob.type, "parent": ob.parent.name if ob.parent else None, "location": r(ob.location),
         "rotation_deg": r([x * 57.2957795 for x in ob.rotation_euler], 3), "scale": r(ob.scale, 6)}
    if ob.type != "MESH":
        rep["objects"][ob.name] = d
        continue
    me = ob.data
    mw = ob.matrix_world
    me.calc_loop_triangles()
    d.update(verts=len(me.vertices), faces=len(me.polygons), tris=len(me.loop_triangles),
             slots=[m.name if m else None for m in me.materials], uv_layers=[u.name for u in me.uv_layers],
             attrs=[a.name for a in me.attributes if not a.name.startswith(".")])
    lc = [v.co for v in me.vertices]
    wc = [mw @ v for v in lc]
    d["bbox_local"] = [r([min(v[i] for v in lc) for i in range(3)], 3), r([max(v[i] for v in lc) for i in range(3)], 3)]
    d["bbox_world"] = [r([min(v[i] for v in wc) for i in range(3)], 3), r([max(v[i] for v in wc) for i in range(3)], 3)]
    fpm = {}
    for p in me.polygons:
        k = me.materials[p.material_index].name if me.materials and me.materials[p.material_index] else str(p.material_index)
        fpm[k] = fpm.get(k, 0) + 1
    d["faces_per_material"] = fpm
    # UDIM per face (centroid of the first UV layer), per material
    if me.uv_layers:
        uvl = me.uv_layers[0].data
        tiles, cross, mirror = {}, 0, 0
        umin, umax = [1e9, 1e9], [-1e9, -1e9]
        for p in me.polygons:
            us = [uvl[i].uv for i in p.loop_indices]
            cu = sum(u.x for u in us) / len(us)
            cv = sum(u.y for u in us) / len(us)
            t = 1001 + int(math.floor(cu)) + 10 * int(math.floor(cv))
            k = me.materials[p.material_index].name if me.materials else "-"
            tiles.setdefault(str(t), {}).setdefault(k, 0)
            tiles[str(t)][k] += 1
            if len({(int(math.floor(u.x)), int(math.floor(u.y))) for u in us}) > 1:
                cross += 1
            for u in us:
                umin = [min(umin[0], u.x), min(umin[1], u.y)]
                umax = [max(umax[0], u.x), max(umax[1], u.y)]
            if len(us) >= 3:
                a = (us[1].x - us[0].x) * (us[2].y - us[0].y) - (us[1].y - us[0].y) * (us[2].x - us[0].x)
                if a < 0:
                    mirror += 1
        d["udim_faces"] = dict(sorted(tiles.items()))
        d["uv_faces_crossing_tiles"] = cross
        d["uv_faces_negative_winding"] = mirror
        d["uv_range"] = [r(umin, 3), r(umax, 3)]
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.transform(mw)
    d["open_edges_raw"] = sum(1 for e in bm.edges if e.is_boundary)
    d["nonmanifold_raw"] = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    d["loose_verts_raw"] = sum(1 for v in bm.verts if not v.link_edges)
    d["zero_area_faces"] = sum(1 for f in bm.faces if f.calc_area() < 1e-8)
    nv = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.002)
    d["weld_2mm_removed_verts"] = nv - len(bm.verts)
    be = [e for e in bm.edges if e.is_boundary]
    d["open_edges_weld2mm"] = len(be)
    d["nonmanifold_weld2mm"] = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    if not ob.name.startswith("UCX_"):
        lp = loops_of(bm, be)
        d["boundary_loops_weld2mm"] = len(lp)
        d["boundary_length_weld2mm_m"] = round(sum(x["length_m"] for x in lp), 2)
        d["boundary_loops_top40"] = lp[:40]
        d["shells_weld2mm"] = None
    bm.free()
    # world triangles
    tri = np.array([[mw @ me.vertices[i].co for i in t.vertices] for t in me.loop_triangles], dtype=np.float64)
    mat = np.array([t.material_index for t in me.loop_triangles], dtype=np.int32)
    if ob.name.startswith("UCX_"):
        ucx_tris.append(tri)
    else:
        key = "Glass" if ob.name.endswith("MainGlass") else ("Main" if ob.name.endswith("_Main") else "Other_" + ob.name)
        arrays[key + "_tri"] = tri
        arrays[key + "_mat"] = mat
        if me.uv_layers:
            uvl = me.uv_layers[0].data
            uvt = np.array([[uvl[li].uv[:] for li in t.loops] for t in me.loop_triangles], dtype=np.float64)
            arrays[key + "_uv"] = uvt
            c = uvt.mean(axis=1)
            arrays[key + "_udim"] = (1001 + np.floor(c[:, 0]) + 10 * np.floor(c[:, 1])).astype(np.int32)
    rep["objects"][ob.name] = d
if ucx_tris:
    arrays["UCX_tri"] = np.concatenate(ucx_tris)
rep["ucx_count"] = sum(1 for n in rep["objects"] if n.startswith("UCX_"))
rep["ucx_tris"] = sum(rep["objects"][n]["tris"] for n in rep["objects"] if n.startswith("UCX_"))
np.savez_compressed(npz, **arrays)
json.dump(rep, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("DONE", out, list(arrays.keys()))
