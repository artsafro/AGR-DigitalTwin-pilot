"""elv-tc-vpm customer-clarify-v001: read-only probe of the customer blend for the three open TZ items.

blender -b --disable-autoexec <copy.blend> --python clarify_blend_probe_v001.py -- <out.json>
Dumps (coordinates converted to OUR frame: world - their pivot + register shift):
  - every object of collection SRC_Накладки_MAN02 (bbox, dims, material, props, verts/faces);
  - islands of FCD_Elevatornaya_1_001 faces per fw_part (1 reveals, 2 frames, 3 fake rooms, 5 glass);
  - full AGR window/box reports. Never saves the blend.
"""
import bpy, bmesh, sys, os, json, collections
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
out = argv[0]
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
PIVOT = Vector((9676.3555, -7135.6997, 167.65))
SHIFT = Vector((-0.064, 0.578, 0.0))  # register_v001 (theirs local -> ours)


def to_ours(p):
    return p - PIVOT + SHIFT


def r(v, n=3):
    return [round(x, n) for x in v]


rep = {"pivot": list(PIVOT), "shift": list(SHIFT), "nakl": [], "fcd": {}, "reports": {}, "src_colls": {}}
sc = bpy.data.scenes["Scene"]
for k in sc.keys():
    if k.startswith("agrfw_") and k != "agrfw_geo_img":
        rep["reports"][k] = str(sc[k])

col = bpy.data.collections.get("SRC_Накладки_MAN02")
dg = bpy.context.evaluated_depsgraph_get()
for o in col.all_objects:
    d = {"name": o.name, "type": o.type, "props": {k: str(o[k])[:300] for k in o.keys()},
         "mods": [m.type for m in o.modifiers], "loc_world": r(o.matrix_world.translation),
         "mats": [s.material.name if s.material else None for s in o.material_slots]}
    if o.type == "MESH":
        me = o.data
        d["nv"], d["nf"] = len(me.vertices), len(me.polygons)
        ps = [to_ours(o.matrix_world @ v.co) for v in me.vertices]
        if ps:
            lo = Vector([min(p[i] for p in ps) for i in range(3)])
            hi = Vector([max(p[i] for p in ps) for i in range(3)])
            d["bbox"] = [r(lo), r(hi)]
            d["dims"] = r(hi - lo)
            # normals of the largest faces (which way the strip faces)
            nrm = collections.Counter()
            for p in me.polygons:
                n = (o.matrix_world.to_3x3() @ p.normal).normalized()
                key = "+X" if n.x > 0.7 else "-X" if n.x < -0.7 else "+Y" if n.y > 0.7 else "-Y" if n.y < -0.7 else "+Z" if n.z > 0.7 else "-Z" if n.z < -0.7 else "oblique"
                nrm[key] += p.area
            d["normal_area"] = {k: round(v, 3) for k, v in nrm.items()}
    rep["nakl"].append(d)

for c in bpy.data.collections:
    if c.name.startswith("SRC_") or c.name.startswith("RZ_"):
        rep["src_colls"][c.name] = {"n": len(c.all_objects), "names": [o.name for o in c.all_objects][:40]}

fcd = bpy.data.objects["FCD_Elevatornaya_1_001"]
rep["fcd"]["matrix_translation"] = r(fcd.matrix_world.translation)
rep["fcd"]["props"] = {k: str(fcd[k])[:4000] for k in fcd.keys()}
me = fcd.data
bm = bmesh.new()
bm.from_mesh(me)
bm.faces.ensure_lookup_table()
attr = {a.name: [x.value for x in a.data] for a in me.attributes
        if a.domain == "FACE" and a.data_type == "INT" and not a.name.startswith(".")}
fw = attr["fw_part"]
M = fcd.matrix_world
islands = {}
for part in (1, 2, 3, 5):
    seen = set()
    isl = []
    for f in bm.faces:
        if fw[f.index] != part or f.index in seen:
            continue
        stack, comp = [f], []
        seen.add(f.index)
        while stack:
            g = stack.pop()
            comp.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen and fw[h.index] == part:
                        seen.add(h.index)
                        stack.append(h)
        ps = [to_ours(M @ v.co) for g in comp for v in g.verts]
        lo = Vector([min(p[i] for p in ps) for i in range(3)])
        hi = Vector([max(p[i] for p in ps) for i in range(3)])
        nrm = collections.Counter()
        for g in comp:
            n = (M.to_3x3() @ g.normal).normalized()
            key = "+X" if n.x > 0.7 else "-X" if n.x < -0.7 else "+Y" if n.y > 0.7 else "-Y" if n.y < -0.7 else "+Z" if n.z > 0.7 else "-Z" if n.z < -0.7 else "obl"
            nrm[key] += g.calc_area()
        extra = {}
        for k in ("agr_wall", "agr_side", "agr_tier"):
            if k in attr:
                extra[k] = sorted(set(attr[k][g.index] for g in comp))
        isl.append({"nf": len(comp), "bbox": [r(lo), r(hi)], "dims": r(hi - lo),
                    "area": round(sum(g.calc_area() for g in comp), 2),
                    "normal_area": {k: round(v, 2) for k, v in nrm.items()}, **extra})
    islands[str(part)] = isl
rep["fcd"]["islands"] = islands
json.dump(rep, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("DONE", out, len(rep["nakl"]), {k: len(v) for k, v in islands.items()})
