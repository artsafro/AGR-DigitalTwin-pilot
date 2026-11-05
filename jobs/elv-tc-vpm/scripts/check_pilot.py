"""elv-tc-vpm: mesh checks of the pilot blend (read-only): tris per part vs parts budget, quad share, max quad edge,
open / non-manifold edges (with clusters), wire/loose geometry, material slots, bbox.

blender -b <pilot.blend> --python check_pilot.py -- <parts.json> <out.json>
"""
import bpy, bmesh, sys, os, json, math
from collections import Counter, defaultdict

argv = sys.argv[sys.argv.index("--") + 1:]
parts_json, out = argv[0], argv[1]
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
PARTS = json.load(open(parts_json, encoding="utf-8"))
budget = {p["id"]: p["triangle_budget"]["vpm"] for p in PARTS["parts"]}
rep = {"objects": {}, "tris_by_part": Counter(), "budget_by_part": budget}


def cluster(points, d=0.5):
    cl = []
    for p in points:
        for c in cl:
            if math.dist(c["c"], p) < d * 4 and min(math.dist(q, p) for q in c["pts"][-20:]) < d:
                c["pts"].append(p)
                break
        else:
            cl.append({"c": p, "pts": [p]})
    out_ = []
    for c in cl:
        P = c["pts"]
        mn = [round(min(q[i] for q in P), 2) for i in range(3)]
        mx = [round(max(q[i] for q in P), 2) for i in range(3)]
        out_.append({"n_edges": len(P), "min": mn, "max": mx})
    return sorted(out_, key=lambda c: -c["n_edges"])


for ob in bpy.context.scene.objects:
    if ob.type != "MESH":
        continue
    me = ob.data
    ids = json.loads(ob.get("part_ids", "[]"))
    att = me.attributes.get("part_idx")
    bm = bmesh.new()
    bm.from_mesh(me)
    lay = bm.faces.layers.int.get("part_idx")
    tri_part, n_by_len = Counter(), Counter()
    max_quad_edge, long_quads = 0.0, 0
    mat_faces = Counter()
    for f in bm.faces:
        n = len(f.verts)
        n_by_len[min(n, 5)] += 1
        t = n - 2
        prt = ids[f[lay]] if (lay is not None and ids) else ob.name
        tri_part[prt] += t
        mat_faces[me.materials[f.material_index].name if me.materials else "-"] += t
        if n == 4:
            m = max(e.calc_length() for e in f.edges)
            max_quad_edge = max(max_quad_edge, m)
            if m > 3.95:
                long_quads += 1
    boundary = [e for e in bm.edges if len(e.link_faces) == 1]
    nonman = [e for e in bm.edges if len(e.link_faces) > 2]
    wire = [e for e in bm.edges if len(e.link_faces) == 0]
    zero = [f for f in bm.faces if f.calc_area() < 1e-8]
    mid = lambda e: tuple((e.verts[0].co + e.verts[1].co) / 2)  # noqa: E731
    o = {
        "faces": len(bm.faces), "tris": sum(tri_part.values()), "verts": len(bm.verts),
        "faces_by_vertex_count": {("5+" if k == 5 else str(k)): v for k, v in sorted(n_by_len.items())},
        "quad_share_faces": round(n_by_len[4] / max(1, len(bm.faces)), 4),
        "tri_faces": n_by_len[3], "ngon_faces": n_by_len[5],
        "max_quad_edge_m": round(max_quad_edge, 3), "quads_over_3.95m": long_quads,
        "open_edges": len(boundary), "nonmanifold_edges": len(nonman), "wire_edges": len(wire),
        "zero_area_faces": len(zero),
        "open_edge_clusters": cluster([mid(e) for e in boundary])[:40],
        "nonmanifold_clusters": cluster([mid(e) for e in nonman])[:20],
        "tris_by_material": dict(mat_faces),
        "material_slots": [m.name for m in me.materials],
        "location": list(ob.location), "rotation": list(ob.rotation_euler), "scale": list(ob.scale),
        "bbox_world": [[round(min((ob.matrix_world @ v.co)[i] for v in me.vertices), 3) for i in range(3)],
                       [round(max((ob.matrix_world @ v.co)[i] for v in me.vertices), 3) for i in range(3)]],
    }
    rep["objects"][ob.name] = o
    rep["tris_by_part"].update(tri_part)
    bm.free()
rep["tris_by_part"] = dict(sorted(rep["tris_by_part"].items()))
rep["parts_table"] = [{"part": k, "tris": rep["tris_by_part"].get(k, 0), "budget": b,
                       "within": rep["tris_by_part"].get(k, 0) <= b} for k, b in budget.items()]
rep["total_tris"] = sum(o["tris"] for o in rep["objects"].values())
rep["total_budget"] = PARTS["triangle_budget"]["vpm"]
json.dump(rep, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for r in rep["parts_table"]:
    print("PART %-26s %6d / %6d %s" % (r["part"], r["tris"], r["budget"], "" if r["within"] else "OVER"))
for k, o in rep["objects"].items():
    print("OBJ", k, {x: o[x] for x in ("faces", "tris", "quad_share_faces", "tri_faces", "ngon_faces",
                                         "max_quad_edge_m", "quads_over_3.95m", "open_edges", "nonmanifold_edges",
                                         "zero_area_faces")})
print("TOTAL", rep["total_tris"], "/", rep["total_budget"])
