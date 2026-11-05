"""elv-tc-vpm: list quads with an edge > 3.95 m (object, part, centre, longest edge). Read-only.

blender -b <file.blend> --python long_quads.py
"""
import bpy, json

for ob in bpy.context.scene.objects:
    if ob.type != "MESH":
        continue
    ids = json.loads(ob.get("part_ids", "[]"))
    me = ob.data
    att = me.attributes.get("part_idx")
    for p in me.polygons:
        if len(p.vertices) != 4:
            continue
        vs = [me.vertices[i].co for i in p.vertices]
        m = max((vs[i] - vs[(i + 1) % 4]).length for i in range(4))
        if m > 3.95:
            print("LONG", ob.name[-9:], ids[att.data[p.index].value] if att else "-", [round(c, 2) for c in p.center],
                  round(m, 3))
