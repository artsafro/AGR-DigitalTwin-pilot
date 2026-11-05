"""elv-tc-vpm: explain xView face pairs / bow-ties of a pilot blend (read-only).

blender -b <pilot.blend> --python xview_explain.py -- <xview.json> [max_pairs]
Prints for each pair: kind, part and material of both faces, normals, vertices (1-based polygon ids in the report).
"""
import bpy, sys, json

argv = sys.argv[sys.argv.index("--") + 1:]
rep = json.load(open(argv[0], encoding="utf-8"))
mx = int(argv[1]) if len(argv) > 1 else 40
for p in rep["parts"]:
    ob = bpy.data.objects[p["part"]]
    me = ob.data
    parts = json.loads(ob["part_ids"])
    att = me.attributes.get("part_idx")
    print("==", p["part"], "pairs", len(p["face_pairs"]))
    for fp in p["face_pairs"][:mx]:
        out = []
        for k in ("a", "b"):
            f = me.polygons[fp[k] - 1]
            out.append("%s %s n=(%.2f,%.2f,%.2f) v=%s" % (
                parts[att.data[f.index].value] if att else "?", me.materials[f.material_index].name,
                *f.normal, [tuple(round(c, 3) for c in me.vertices[i].co) for i in f.vertices]))
        print(fp["kind"], fp.get("separation_m"), "\n   A:", out[0], "\n   B:", out[1])
    for b in p.get("bowtie_vertices", [])[:mx]:
        v = me.vertices[b["vertex"] - 1] if b["vertex"] - 1 < len(me.vertices) else None
        print("bowtie", b)
