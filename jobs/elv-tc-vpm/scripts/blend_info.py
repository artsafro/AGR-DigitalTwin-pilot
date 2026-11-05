"""elv-tc-vpm: print objects, material slots, UV layers, attributes and custom props of a blend (read-only).

blender -b <file.blend> --python blend_info.py
"""
import bpy, json

for o in bpy.context.scene.objects:
    d = {"type": o.type, "loc": list(o.location)}
    if o.type == "MESH":
        me = o.data
        d.update(faces=len(me.polygons), verts=len(me.vertices), slots=[m.name if m else None for m in me.materials],
                 uv=[u.name for u in me.uv_layers], attrs=[(a.name, a.domain, a.data_type) for a in me.attributes],
                 props={k: str(o[k])[:300] for k in o.keys()})
    print("INFO", o.name, json.dumps(d, ensure_ascii=False))
for m in bpy.data.materials:
    print("MAT", m.name, [round(c, 3) for c in m.diffuse_color], m.use_nodes and [n.type for n in m.node_tree.nodes])
