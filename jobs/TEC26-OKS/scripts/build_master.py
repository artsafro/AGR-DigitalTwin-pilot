"""new-case: build the TEC26 VPM master (.blend) of one building from its Max poly dump (headless Blender).

Usage: blender --background --factory-startup --python build_master.py -- <dump.json> <spec.json> <textures_dir> <new.blend>

Scope (Artem 2026-10-22: «там задача только раскрасить, геометрию менять не надо»): geometry, topology, UCX and
the Multi/Sub IDs stay as in the source - no quadification, no weld/seam repair, no hull rebuild. The ONLY geometry
edit is the one Artem allowed for panels that do not fit a tile («можно аккуратно порезать через loop или ring»):
edge-ring cuts at joint positions (finish_map.apply_cuts; quads only, boundary to boundary, new vertices on source
edges, every cut listed in the build report).
- mesh = the Max mid-poly (same source vertices, polygons in source order, ring-cut polygons replaced by their halves);
- one finish per polygon from the approved Gate-1 mapping (finish_map.assign_finishes, fail-closed); the source
  material ID is kept per polygon in the `srcid` layer (dropped at export, the delivery has one material);
- UV only: one UDIM tile per finish, placeholder islands scaled into the tile with a 5 % margin (vpm_uv.pack_uv);
  finishes listed in spec `facade_uv` (joint patterns) get metre UVs in their source face's joint frame
  (finish_map.facade_joint_uv + field_frames: joints at u' = n * P from the facade panel FIELD edge with the smaller
  world coordinate, P = field / ribs of the spec facades contract from the colour-solution sheet; v = z),
  shifted by whole periods into their full 4096 tile;
  UDIM material M_<A>_Main_1 (the source channel-1 UV is not laid out per finish tile, so it is replaced);
- the layer's collision mesh (no Multi/Sub) is renamed UCX_SM_<A>_Main_NNN, unchanged; closed/convex/outward are
  checked and REPORTED (a finding is listed, never fixed);
- writes <new.blend> and <new>.build.json (counts, per-finish UV QA, UCX checks, perimeter drop). Never overwrites.
"""
import json
import os
import sys

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import finish_map  # noqa: E402
import vpm_uv  # noqa: E402

dump_path, spec_path, tex_dir, out = sys.argv[sys.argv.index("--") + 1:][:4]
if os.path.lexists(out) or os.path.lexists(out + ".build.json"):
    raise SystemExit(f"refusing to overwrite {out}")
for p in (dump_path, spec_path):
    if os.path.realpath(p) == os.path.realpath(out):
        raise SystemExit("output aliases an input")
spec = finish_map.load(spec_path)
finish_map.validate_spec(spec, finish_map.load_kpp())
dump = finish_map.load(dump_path)
A = spec["address"]
bodies = [n for n in dump["nodes"] if n["multisub"]]
hulls = [n for n in dump["nodes"] if not n["multisub"]]
if len(bodies) != 1:
    raise SystemExit(f"expected exactly one Multi/Sub mesh on the layer, got {[n['name'] for n in bodies]}")
body = bodies[0]
used_ids = set(body["mat_ids"])
slot_ids = {s["id"] for s in body["multisub"]}
if used_ids - slot_ids:
    raise SystemExit(f"faces use IDs without a Multi/Sub slot: {sorted(used_ids - slot_ids)}")

names = sorted(spec["finishes"], key=lambda k: spec["finishes"][k]["udim"])
V = body["vertices"]
faces, ids = body["faces"], body["mat_ids"]
fins = finish_map.assign_finishes(V, faces, ids, spec)
drop = finish_map.perimeter_drop(V, faces, fins, spec["source_ids"]["1"]["below"]) \
    if spec["source_ids"].get("1", {}).get("split") == "below_zero" else None
plan_lo, plan_hi = finish_map.body_plan_bbox(V, spec["zero_m"])
fields = finish_map.field_frames(V, faces, fins, spec, plan_lo, plan_hi) if spec.get("facades") else None
cut = finish_map.apply_cuts(V, faces, fins, spec, plan_lo, plan_hi) if spec.get("ring_cuts") else \
    {"vertices": V, "faces": faces, "parents": list(range(len(faces))), "cuts": [],
     "frames": fields[0] if fields else
     [finish_map.joint_origin(V, f, plan_lo, plan_hi) if fin in spec.get("facade_uv", {}) else None
      for f, fin in zip(faces, fins)]}

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
bm = bmesh.new()
fl = bm.faces.layers.int.new("finish")
bm.faces.layers.int.new("srcid")
uvx = bm.faces.layers.int.new("uvx")
uvm = bm.loops.layers.uv.new("UVM")
CV = cut["vertices"]
vs = [bm.verts.new(c) for c in CV]
for f, src in zip(cut["faces"], cut["parents"]):
    fin, m = fins[src], ids[src]
    nf = bm.faces.new([vs[k] for k in f])
    nf[fl] = names.index(fin)
    nf[bm.faces.layers.int["srcid"]] = m
    if cut["frames"][src] is not None:  # metre UVs in the source face's joint frame, packed by whole periods
        nf[uvx] = 1
        for loop, (u, v) in zip(nf.loops, finish_map.facade_joint_uv(CV, f, cut["frames"][src])):
            loop[uvm].uv = (u, v)
bm.normal_update()
unused = [v for v in bm.verts if not v.link_faces]
if unused:
    raise SystemExit(f"{len(unused)} source vertices are not used by any polygon")
nb = bm
uvqa = vpm_uv.pack_uv(nb, names, spec)
density = vpm_uv.density_qa(nb, names, spec)
bad = {k: q for k, q in uvqa.items() if q["overflow"]}
if bad:
    raise SystemExit(f"UV islands overflow their UDIM tile: {bad}")
nfl = nb.faces.layers.int["finish"]
counts = {n: 0 for n in names}
for f in nb.faces:
    counts[names[f[nfl]]] += 1
non_quads = sum(1 for f in nb.faces if len(f.verts) != 4)
max_edge = max(e.calc_length() for e in nb.edges)
me = bpy.data.meshes.new(f"SM_{A}_Main")
nb.to_mesh(me)
nb.free()
for uvl in [u for u in me.uv_layers if u.name != "UVMap"]:
    me.uv_layers.remove(uvl)
me.uv_layers["UVMap"].active = True
main = bpy.data.objects.new(f"SM_{A}_Main", me)
sc.collection.objects.link(main)
main["finish_names"] = ",".join(names)
main.data.materials.append(vpm_uv.main_material(bpy, spec, tex_dir))

ucx_report = []
for k, h in enumerate(sorted(hulls, key=lambda n: n["name"]), start=1):
    hb = bmesh.new()
    hv = [hb.verts.new(c) for c in h["vertices"]]
    for f in h["faces"]:
        hb.faces.new([hv[i] for i in f])
    hb.normal_update()
    closed = all(len(e.link_faces) == 2 for e in hb.edges)
    centre = sum((v.co for v in hb.verts), Vector()) / len(hb.verts)
    outward = all((f.calc_center_median() - centre).dot(f.normal) > 0 for f in hb.faces)
    convex = all((v.co - f.calc_center_median()).dot(f.normal) <= 1e-5 for f in hb.faces for v in hb.verts)
    hme = bpy.data.meshes.new(f"UCX_SM_{A}_Main_{k:03d}")
    hb.to_mesh(hme)
    hb.free()
    ho = bpy.data.objects.new(hme.name, hme)
    sc.collection.objects.link(ho)
    tris = sum(len(p.vertices) - 2 for p in hme.polygons)
    ucx_report.append({"source": h["name"], "name": ho.name, "verts": len(hme.vertices), "faces": len(hme.polygons),
                       "tris": tris, "closed": closed, "convex": convex, "normals_outward": outward,
                       "uv_layers": len(hme.uv_layers), "materials": len(hme.materials)})

bpy.ops.wm.save_as_mainfile(filepath=out)
report = {"dump": os.path.abspath(dump_path), "spec": os.path.abspath(spec_path), "blend": os.path.abspath(out),
          "source": {"name": body["name"], "vertices": len(V), "polygons": len(body["faces"])},
          "master_faces": len(me.polygons), "non_quads": non_quads,
          "ring_cuts": cut["cuts"], "cut_vertices_added": len(CV) - len(V),
          "master_tris": sum(len(p.vertices) - 2 for p in me.polygons), "max_edge_m": round(max_edge, 4),
          "faces_per_finish": counts, "uv_qa": uvqa, "density_px_per_m": density, "ucx": ucx_report, "perimeter_drop": drop,
          "facade_fields": fields[1] if fields else None}
json.dump(report, open(out + ".build.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("BUILD", json.dumps({k: report[k] for k in ("master_faces", "non_quads", "master_tris", "max_edge_m",
                                                  "faces_per_finish")}))
print("BUILD-UV", json.dumps(uvqa), json.dumps(density))
print("BUILD-UCX", json.dumps(ucx_report))
print("BUILD-DROP", json.dumps(drop))
print("BUILD-CUTS", json.dumps(cut["cuts"]))
