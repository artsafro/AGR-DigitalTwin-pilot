"""Hook `after` stage `body` (#1619 polygon 63B v007): join the module_build runs and close the belt caps.

Pattern: n/a | new-case: two-ring tower on the 63A module builder.

blender -b --factory-startup --python assemble63b.py -- STACK_DIR OUT_DIR

STACK_DIR holds b_<run>/body.blend (module_build.py outputs, runs A1 B1 A2 B2 A3) and caps.json (stack63b.py).
The cap cells are horizontal quads between the shared stations of ring A and ring B; their corners are looked up
among the existing loop vertices (1e-4 m), so a cap shares every edge with the walls (no T-junction). A cell where
ring A lies outside ring B tops the A storey at +23.55/+39.30 (+Z) and is the soffit of A at +26.70/+42.45 (-Z); a
cell where B pokes out past A (pilaster steps) is the other way round (cap_faces_up). Writes OUT_DIR/body.blend, body.fbx and
assemble.json; OUT_DIR must be new.
"""
import json
import os
import sys

RUNS = ["A1", "B1", "A2", "B2", "A3"]
TEX_M = 3.0


def cap_faces_up(xy, top, a_ccw):
    """Normal of a cap cell [A_i, A_i+1, B_i+1, B_i]: True = +Z. `top` = the level under a belt storey (+23.55,
    +39.30). The cell's plan winding agrees with ring A's where A is outside B; where B pokes out past A the cell is
    the soffit (top level) or the roof (bottom level) of B instead."""
    n = len(xy)
    area = 0.5 * sum(xy[k][0] * xy[(k + 1) % n][1] - xy[(k + 1) % n][0] * xy[k][1] for k in range(n))
    a_outside = (area > 0) == a_ccw
    return a_outside == top


def _run():
    import bmesh
    import bpy
    from mathutils import kdtree

    args = sys.argv[sys.argv.index("--") + 1:]
    stack, out = os.path.abspath(args[0]), os.path.abspath(args[1])
    if os.path.exists(out):
        sys.exit("refused: OUT_DIR exists")
    caps = json.load(open(os.path.join(stack, "caps.json"), encoding="utf-8"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    objs = []
    for r in RUNS:
        path = os.path.join(stack, "b_" + r, "body.blend")
        with bpy.data.libraries.load(path, link=False) as (src, dst):
            dst.objects = [n for n in src.objects if n == "SM_Body_Main"]
        ob = dst.objects[0]
        ob.name = "run_" + r
        bpy.context.scene.collection.objects.link(ob)
        objs.append(ob)
    # one material per finish name (appended copies get .001 suffixes)
    by_name = {}
    for m in list(bpy.data.materials):
        base = m.name.split(".")[0]
        by_name.setdefault(base, m)
    for ob in objs:
        for slot in ob.material_slots:
            if slot.material:
                slot.material = by_name[slot.material.name.split(".")[0]]
    for cell_mat in {c["mat"] for c in caps["cells"]}:
        if cell_mat not in by_name:
            sys.exit("refused: cap material %s is not on any wall" % cell_mat)
    bpy.ops.object.select_all(action="DESELECT")
    for ob in objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    body = objs[0]
    body.name = body.data.name = "SM_Body_Main"
    # world-space vertices (module_build sets object z = z0)
    body.data.transform(body.matrix_world)
    body.matrix_world.identity()
    me = body.data
    mat_index = {}
    for i, slot in enumerate(body.material_slots):
        mat_index.setdefault(slot.material.name.split(".")[0], i)
    bm = bmesh.new()
    bm.from_mesh(me)
    w0 = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-4)
    welded = w0 - len(bm.verts)
    bm.verts.ensure_lookup_table()
    kd = kdtree.KDTree(len(bm.verts))
    for v in bm.verts:
        kd.insert(v.co, v.index)
    kd.balance()
    uv = bm.loops.layers.uv.active or bm.loops.layers.uv.new("UVMap")
    made, missing = 0, []
    for zi, z in enumerate(caps["z"]):
        top = zi % 2 == 0  # 23.55 / 39.30: under a belt storey; 26.70 / 42.45: over it
        for c in caps["cells"]:
            up = cap_faces_up(c["xy"], top, caps["a_ccw"])
            vs = []
            for x, y in c["xy"]:
                co, idx, d = kd.find((x, y, z))
                if d is None or d > 1e-4:
                    missing.append([x, y, z])
                    break
                vs.append(bm.verts[idx])
            if len(vs) != len(c["xy"]):
                continue
            f = bm.faces.new(vs)
            f.normal_update()
            if (f.normal.z > 0) != up:
                f.normal_flip()
            f.material_index = mat_index[c["mat"]]
            for lp in f.loops:
                lp[uv].uv = (lp.vert.co.x / TEX_M, lp.vert.co.y / TEX_M)
            made += 1
    if missing:
        sys.exit("refused: %d cap corners have no wall vertex, first %r" % (len(missing), missing[:3]))
    bm.to_mesh(me)
    bm.free()
    os.makedirs(out)
    rep = {"runs": RUNS, "welded": welded, "cap_faces": made, "verts": len(me.vertices), "faces": len(me.polygons),
           "tris": sum(1 for p in me.polygons if len(p.vertices) == 3),
           "ngons": sum(1 for p in me.polygons if len(p.vertices) > 4)}
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "body.blend"), copy=True)
    bpy.ops.export_scene.fbx(filepath=os.path.join(out, "body.fbx"), use_selection=False, mesh_smooth_type="FACE",
                             path_mode="COPY", embed_textures=False)
    json.dump(rep, open(os.path.join(out, "assemble.json"), "w"), indent=1)
    print("ASSEMBLED", json.dumps(rep))


if __name__ == "__main__":
    _run()
