"""new-case: build the TEC26 VPM master (.blend) of one building from its Max poly dump (headless Blender).

Usage: blender --background --factory-startup --python build_master.py -- <dump.json> <spec.json> <textures_dir> <new.blend>

Scope (Artem 2026-10-22: «там задача только раскрасить, геометрию менять не надо»): geometry, topology, UCX and
the Multi/Sub IDs stay EXACTLY as in the source - no quadification, no texel cuts, no weld/seam repair, no hull rebuild.
- mesh = the Max mid-poly as is (same vertices, same polygons, same order);
- one finish per polygon from the approved Gate-1 mapping (finish_map.assign_finishes, fail-closed); the source
  material ID is kept per polygon in the `srcid` layer (dropped at export, the delivery has one material);
- UV only: one UDIM tile per finish, placeholder islands scaled into the tile with a 5 % margin (vpm_uv.pack_uv);
  finishes listed in spec `facade_uv` (joint patterns) get metre UVs from finish_map.facade_uv (u from the facade's
  left corner, v = z so joint rows start at ±0.000), shifted by whole periods into their full 4096 tile;
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

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
bm = bmesh.new()
fl = bm.faces.layers.int.new("finish")
bm.faces.layers.int.new("srcid")
uvx = bm.faces.layers.int.new("uvx")
uvm = bm.loops.layers.uv.new("UVM")
body_pts = [c for c in V if c[2] > spec["zero_m"]]
plan_lo = [min(c[0] for c in body_pts), min(c[1] for c in body_pts)]
plan_hi = [max(c[0] for c in body_pts), max(c[1] for c in body_pts)]
facade = set(spec.get("facade_uv", {}))
vs = [bm.verts.new(c) for c in V]
for f, m, fin in zip(faces, ids, fins):
    nf = bm.faces.new([vs[k] for k in f])
    nf[fl] = names.index(fin)
    nf[bm.faces.layers.int["srcid"]] = m
    if fin in facade:  # metre UVs from the facade corner / ±0.000 (joint phase), packed by whole periods
        nf[uvx] = 1
        for loop, (u, v) in zip(nf.loops, finish_map.facade_uv(V, f, plan_lo, plan_hi)):
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
          "master_tris": sum(len(p.vertices) - 2 for p in me.polygons), "max_edge_m": round(max_edge, 4),
          "faces_per_finish": counts, "uv_qa": uvqa, "density_px_per_m": density, "ucx": ucx_report, "perimeter_drop": drop}
json.dump(report, open(out + ".build.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("BUILD", json.dumps({k: report[k] for k in ("master_faces", "non_quads", "master_tris", "max_edge_m",
                                                  "faces_per_finish")}))
print("BUILD-UV", json.dumps(uvqa), json.dumps(density))
print("BUILD-UCX", json.dumps(ucx_report))
print("BUILD-DROP", json.dumps(drop))
