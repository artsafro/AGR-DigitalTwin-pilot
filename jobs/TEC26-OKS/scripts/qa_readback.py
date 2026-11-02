"""new-case: TEC26 FBX readback dump (headless Blender) for package QA.

Usage: blender --background --factory-startup --python qa_readback.py -- <in.fbx> <new_out.json>
The FBX is imported into an empty scene (embedded images unpack beside the FBX, so pass a COPY in a scratch dir).
Per mesh object: name, world vertices, polygons, UV layer names and per-loop UVs, materials with their image nodes
(name, size, channels, packed/embedded state). Objects of other types are listed. Never writes beside the input.
"""
import json
import os
import sys

import bpy

src, out = sys.argv[sys.argv.index("--") + 1:][:2]
if os.path.lexists(out) or os.path.realpath(out) == os.path.realpath(src):
    raise SystemExit(f"refusing to write {out}")
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src)
objs = []
for o in bpy.context.scene.objects:
    row = {"name": o.name, "type": o.type, "parent": o.parent.name if o.parent else None,
           "location": list(o.location), "rotation": list(o.rotation_euler), "scale": list(o.scale)}
    if o.type == "MESH":
        me = o.data
        mw = o.matrix_world
        row["vertices"] = [list(mw @ v.co) for v in me.vertices]
        row["faces"] = [list(p.vertices) for p in me.polygons]
        row["uv_layers"] = [u.name for u in me.uv_layers]
        if me.uv_layers:
            uv = me.uv_layers[0].data
            row["face_uvs"] = [[list(uv[li].uv) for li in p.loop_indices] for p in me.polygons]
        row["material_index"] = [p.material_index for p in me.polygons]
        mats = []
        for m in me.materials:
            imgs = []
            if m and m.use_nodes:
                for n in m.node_tree.nodes:
                    if n.type == "TEX_IMAGE" and n.image:
                        im = n.image
                        imgs.append({"name": im.name, "file": os.path.basename(im.filepath), "size": list(im.size),
                                     "channels": im.channels, "packed": bool(im.packed_file),
                                     "links": [l.to_socket.name for l in n.outputs["Color"].links] +
                                              ["alpha:" + l.to_socket.name for l in n.outputs["Alpha"].links]})
            mats.append({"name": m.name if m else None, "images": imgs})
        row["materials"] = mats
    objs.append(row)
json.dump({"fbx": os.path.abspath(src), "objects": objs}, open(out, "w", encoding="utf-8"))
print("READBACK", json.dumps([(o["name"], o["type"], len(o.get("faces", []))) for o in objs]))
