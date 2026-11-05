"""elv-tc-vpm: read the textured check FBX back in a fresh Blender: UV channels (names), UDIM tiles used per object,
material count/names, faces per tile, mirrored / out-of-tile UV faces, texture references left in the FBX.

blender -b --factory-startup --python readback_uv_fbx.py -- <in.fbx> <textures_dir> <out.json>
Also checks the PNG set: every tile used by Main has Diffuse/ERM/Normal, every PNG is used (reg p.30 §5.1.8),
sizes 4096 / 256 placeholders, 8-bit RGB without alpha, tiles sequential from 1001.
"""
import bpy, sys, os, json, math, re, hashlib
from collections import Counter

argv = sys.argv[sys.argv.index("--") + 1:]
src, tex, out = argv[0], argv[1], argv[2]
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
raw = open(src, "rb").read()
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.import_scene.fbx(filepath=src)
rep = {"fbx": src, "sha256": hashlib.sha256(raw).hexdigest(), "objects": {},
       "png_refs_in_fbx": len(re.findall(rb"\.png", raw, re.I)),
       "texture_nodes_in_fbx": raw.count(b"Texture::") + raw.count(b"Video::")}
for ob in bpy.context.scene.objects:
    if ob.type != "MESH":
        continue
    me = ob.data
    uvn = [u.name for u in me.uv_layers]
    uv = me.uv_layers[0].data if me.uv_layers else None
    tiles, mirrored, cross = Counter(), 0, 0
    for p in me.polygons:
        pts = [uv[i].uv for i in p.loop_indices]
        tu = {(math.floor(q.x), math.floor(q.y)) for q in pts}
        if len(tu) > 1:
            cross += 1
        a, b = min(tu)
        tiles[1001 + a + 10 * b] += 1
        sa = sum(pts[i].x * pts[(i + 1) % len(pts)].y - pts[(i + 1) % len(pts)].x * pts[i].y for i in range(len(pts)))
        mirrored += sa < 0
    rep["objects"][ob.name] = {"uv_layers": uvn, "materials": [m.name for m in me.materials],
                               "material_count": len(me.materials), "faces": len(me.polygons),
                               "udim_tiles": dict(sorted(tiles.items())), "faces_crossing_tiles": cross,
                               "mirrored_uv_faces": mirrored, "scale": list(ob.scale),
                               "rotation_deg": [round(math.degrees(x), 4) for x in ob.rotation_euler]}
import struct  # noqa: E402


def ihdr(path):
    b = open(path, "rb").read(33)
    w, h, depth, ctype = struct.unpack(">IIBB", b[16:26])
    return w, h, {2: "RGB", 6: "RGBA", 0: "L", 4: "LA", 3: "P"}.get(ctype, str(ctype)) + f"{depth}"


pngs = {}
for f in sorted(os.listdir(tex)):
    m = re.fullmatch(r"T_Elevatornaya_1A_(Diffuse|ERM|Normal)_(\d)\.(\d{4})\.png", f)
    if not m:
        pngs[f] = "BAD NAME"
        continue
    pngs[f] = list(ihdr(os.path.join(tex, f)))
rep["pngs"] = pngs
main = next(v for k, v in rep["objects"].items() if k.endswith("_Main"))
used = sorted(main["udim_tiles"])
have = sorted({int(f.split(".")[-2]) for f in pngs})
rep["png_checks"] = {
    "names_ok": all(v != "BAD NAME" for v in pngs.values()),
    "tiles_used_by_main": used, "tiles_with_png": have, "same_set": used == have,
    "sequential_from_1001": used == list(range(1001, 1001 + len(used))),
    "triplets_complete": all(all(f"T_Elevatornaya_1A_{k}_1.{t}.png" in pngs for k in ("Diffuse", "ERM", "Normal"))
                             for t in used),
    "sizes": dict(Counter(f"{v[0]}x{v[1]} {v[2]}" for v in pngs.values() if v != "BAD NAME")),
    "no_alpha": all(v[2] == "RGB8" for v in pngs.values() if v != "BAD NAME"),
}
json.dump(rep, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("READBACK", json.dumps({k: {x: v[x] for x in ("uv_layers", "materials", "faces", "faces_crossing_tiles",
                                                      "mirrored_uv_faces")} for k, v in rep["objects"].items()}))
print("TILES", json.dumps({k: v["udim_tiles"] for k, v in rep["objects"].items()}))
print("PNG", json.dumps(rep["png_checks"]), "png_refs", rep["png_refs_in_fbx"], "tex_nodes", rep["texture_nodes_in_fbx"])
