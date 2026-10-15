"""Read-only mesh dump of the open 3ds Max scene for the window library.

Writes JSON (verts, faces, material ids) to the path in AGR_WINDOW_DUMP, default
C:/x/windows-library/mesh_dump.json. Never saves the scene.
"""
import json
import os

from pymxs import runtime as rt

out_path = os.environ.get("AGR_WINDOW_DUMP", r"C:/x/windows-library/mesh_dump.json")
out = []
for o in rt.objects:
    d = {"name": str(o.name), "class": str(rt.classOf(o)), "parent": str(o.parent.name) if o.parent else None,
         "layer": str(o.layer.name), "hidden": bool(o.isHidden), "mat": str(o.material.name) if o.material else None,
         "pos": [float(o.pos.x), float(o.pos.y), float(o.pos.z)],
         "mods": [str(m.name) for m in o.modifiers]}
    m = rt.snapshotAsMesh(o)
    d["verts"] = [[round(float(p.x), 5), round(float(p.y), 5), round(float(p.z), 5)]
                  for p in (rt.getVert(m, i) for i in range(1, m.numverts + 1))]
    fs = []
    for f in range(1, m.numfaces + 1):
        v = rt.getFace(m, f)
        fs.append([int(v.x) - 1, int(v.y) - 1, int(v.z) - 1, int(rt.getFaceMatID(m, f))])
    d["faces"] = fs
    rt.delete(m)
    mt = o.material
    if mt is not None and rt.classOf(mt) == rt.Multimaterial:
        d["submats"] = {int(i): str(s.name) if s else None for i, s in zip(mt.materialIDList, mt.materialList)}
    out.append(d)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump({"file": str(rt.maxFilePath) + str(rt.maxFileName), "units": str(rt.units.SystemType), "objects": out},
              f, ensure_ascii=False)
print("AGR_DONE", len(out))
