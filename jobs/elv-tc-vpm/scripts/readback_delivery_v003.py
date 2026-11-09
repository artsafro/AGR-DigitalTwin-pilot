"""v003 copy (stem SM_Elevatornaya_Vl_1_A_001) of readback_delivery_v001.py.
elv-tc-vpm: clean-process readback of the delivered FBX (taken from the ZIP) - placement, objects, UCX shape.

blender -b --factory-startup --disable-autoexec --python-exit-code 1 --python readback_delivery_v001.py -- <in.fbx> <out.json>

Measures (read-only, never writes the FBX): object types / collections / parents, transforms, origins, bbox and
bbox-centre offset (reg p.32-33 §9, [D018]), polygon degrees (triangulated, reg p.29 §3.17), UV layers and
materials per object, UCX names, closed + convex + material slots + UV per piece, triangle totals vs [D012].
"""
import bpy
import json
import math
import os
import re
import sys

src, out = sys.argv[sys.argv.index("--") + 1:][:2]
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src)
sc = bpy.context.scene
objs = list(sc.objects)
rep = {"fbx": src, "unit": [sc.unit_settings.system, sc.unit_settings.scale_length],
       "non_mesh": [o.name for o in objs if o.type != "MESH"],
       "parented": [o.name for o in objs if o.parent], "collections": sorted({c.name for o in objs for c in o.users_collection})}
meshes = [o for o in objs if o.type == "MESH"]
ucx = [o for o in meshes if o.name.startswith("UCX_")]
model = [o for o in meshes if o not in ucx]
bad_tf = []
for o in meshes:
    r = [math.degrees(a) for a in o.rotation_euler]
    if (o.location.length > 1e-6 or any(abs(a) > 1e-6 for a in r) or any(abs(s - 1) > 1e-6 for s in o.scale)):
        bad_tf.append([o.name, list(o.location), r, list(o.scale)])
rep["non_identity_transforms"] = bad_tf[:20]
rep["non_identity_transform_count"] = len(bad_tf)


def tri(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


rep["model"] = {}
for o in model:
    me = o.data
    vs = [o.matrix_world @ v.co for v in me.vertices]
    lo = [min(p[i] for p in vs) for i in range(3)]
    hi = [max(p[i] for p in vs) for i in range(3)]
    rep["model"][o.name] = {
        "triangles": tri(o), "non_tri_polys": sum(len(p.vertices) != 3 for p in me.polygons),
        "uv_layers": [u.name for u in me.uv_layers], "materials": [m.name if m else None for m in me.materials],
        "bbox": [[round(v, 4) for v in lo], [round(v, 4) for v in hi]],
        "bbox_centre_xy": [round((lo[0] + hi[0]) / 2, 4), round((lo[1] + hi[1]) / 2, 4)],
        "bbox_centre_offset_pct_of_size": [round(100 * abs((lo[i] + hi[i]) / 2) / (hi[i] - lo[i]), 3) for i in (0, 1)],
        "origin": list(o.location), "custom_attributes": [a.name for a in me.attributes
                                                         if not a.name.startswith(".") and a.name not in
                                                         ("position", "sharp_face", "UV", "material_index")],
        "custom_props": list(o.keys())}
model_tris = sum(tri(o) for o in model)
name_re = re.compile(r"^UCX_SM_Elevatornaya_Vl_1_A_001_Main_(\d{3})$")
bad_name, not_closed, not_convex, with_mat, with_uv = [], [], [], [], []
for o in ucx:
    me = o.data
    if not name_re.match(o.name):
        bad_name.append(o.name)
    if len(me.materials):
        with_mat.append(o.name)
    if len(me.uv_layers):
        with_uv.append(o.name)
    ec = {}
    for p in me.polygons:
        for k in p.edge_keys:
            ec[k] = ec.get(k, 0) + 1
    if any(c != 2 for c in ec.values()):
        not_closed.append(o.name)
    vs = [v.co for v in me.vertices]
    for p in me.polygons:
        c, n = p.center, p.normal
        if any((v - c).dot(n) > 1e-4 for v in vs):
            not_convex.append(o.name)
            break
idx = sorted(int(name_re.match(o.name).group(1)) for o in ucx if name_re.match(o.name))
ucx_tris = sum(tri(o) for o in ucx)
budget = 15000 if model_tris < 50000 else min(math.ceil(model_tris * 0.05), 100000)
rep["ucx"] = {"pieces": len(ucx), "triangles": ucx_tris, "budget_D012": budget, "within_budget": ucx_tris <= budget,
              "index_contiguous_from_001": idx == list(range(1, len(idx) + 1)), "bad_names": bad_name,
              "not_closed": not_closed, "not_convex": not_convex, "with_material_slots": with_mat, "with_uv": with_uv}
rep["model_triangles_excl_ucx"] = model_tris

# UV / UDIM per model object and the PNG set next to the FBX (optional 3rd arg: folder with the PNGs)
import struct  # noqa: E402
from collections import Counter  # noqa: E402

for o in model:
    me = o.data
    uv = me.uv_layers[0].data if me.uv_layers else None
    tiles, mirrored, cross = Counter(), 0, 0
    for p in me.polygons if uv else []:
        pts = [uv[i].uv for i in p.loop_indices]
        tu = {(math.floor(q.x), math.floor(q.y)) for q in pts}
        cross += len(tu) > 1
        a, b = min(tu)
        tiles[1001 + a + 10 * b] += 1
        sa = sum(pts[i].x * pts[(i + 1) % len(pts)].y - pts[(i + 1) % len(pts)].x * pts[i].y for i in range(len(pts)))
        mirrored += sa < 0
    rep["model"][o.name].update(udim_tiles=dict(sorted(tiles.items())), faces_crossing_tiles=cross, mirrored_uv_faces=mirrored)
raw = open(src, "rb").read()
rep["png_refs_in_fbx"] = len(re.findall(rb"\.png", raw, re.I))
rep["texture_nodes_in_fbx"] = raw.count(b"Texture::") + raw.count(b"Video::")
args = sys.argv[sys.argv.index("--") + 1:]
if len(args) > 2:
    tex = args[2]
    pngs = {}
    for f in sorted(os.listdir(tex)):
        if not f.lower().endswith(".png"):
            continue
        m = re.fullmatch(r"T_Elevatornaya_1A_(Diffuse|ERM|Normal)_1\.(\d{4})\.png", f)
        b = open(os.path.join(tex, f), "rb").read(33)
        w, h, depth, ctype = struct.unpack(">IIBB", b[16:26])
        pngs[f] = [w, h, {2: "RGB", 6: "RGBA"}.get(ctype, str(ctype)) + str(depth), bool(m)]
    used = sorted(set(rep["model"]["SM_Elevatornaya_Vl_1_A_001_Main"]["udim_tiles"]) | set(rep["model"]["SM_Elevatornaya_Vl_1_A_001_MainGlass"]["udim_tiles"]))
    have = sorted({int(f.split(".")[-2]) for f in pngs})
    rep["png_checks"] = {
        "count": len(pngs), "names_ok": all(v[3] for v in pngs.values()), "tiles_used": used, "tiles_with_png": have,
        "same_set": used == have, "sequential_from_1001": used == list(range(1001, 1001 + len(used))),
        "triplets_complete": all(all(f"T_Elevatornaya_1A_{k}_1.{t}.png" in pngs for k in ("Diffuse", "ERM", "Normal")) for t in used),
        "sizes": dict(Counter(f"{v[0]}x{v[1]} {v[2]}" for v in pngs.values())),
        "no_alpha": all(v[2] == "RGB8" for v in pngs.values())}
with open(out, "w", encoding="utf-8") as fh:
    json.dump(rep, fh, ensure_ascii=False, indent=1)
print("READBACK", json.dumps({k: v for k, v in rep.items() if k != "model"}, ensure_ascii=False)[:1500])
