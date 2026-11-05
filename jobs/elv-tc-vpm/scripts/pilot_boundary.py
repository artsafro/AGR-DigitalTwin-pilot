"""elv-tc-vpm: list pilot faces that touch given x / y windows and the open (boundary) edges there (read-only).

blender -b elv_pilot_IA_v001.blend --python pilot_boundary.py -- <out.json>
"""
import bpy, bmesh, sys, os, json

argv = sys.argv[sys.argv.index("--") + 1:]
out = os.path.abspath(argv[0])
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
WIN = {"south_end": (41.70, 42.00, -51.5, -46.0), "north_end": (59.20, 59.60, -1.0, 4.0)}
res = {}
for ob in bpy.context.scene.objects:
    if ob.type != "MESH":
        continue
    ids = json.loads(ob.get("part_ids", "[]"))
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    lay = bm.faces.layers.int.get("part_idx")
    for key, (x0, x1, y0, y1) in WIN.items():
        fl = []
        for f in bm.faces:
            vs = [tuple(round(c, 4) for c in v.co) for v in f.verts]
            if any(x0 <= v[0] <= x1 and y0 <= v[1] <= y1 for v in vs):
                fl.append({"mat": f.material_index + 1, "part": ids[f[lay]] if lay is not None else None,
                           "n": [round(c, 3) for c in f.normal], "v": vs})
        bnd = []
        for e in bm.edges:
            if len(e.link_faces) == 1:
                a, b = e.verts[0].co, e.verts[1].co
                if all(x0 <= p[0] <= x1 and y0 <= p[1] <= y1 for p in (a, b)):
                    bnd.append([[round(c, 4) for c in a], [round(c, 4) for c in b]])
        res[f"{ob.name}:{key}"] = {"faces": fl, "open_edges": bnd}
    bm.free()
json.dump(res, open(out, "w", encoding="utf-8"), indent=0)
print("BOUNDARY", {k: (len(v["faces"]), len(v["open_edges"])) for k, v in res.items()})
