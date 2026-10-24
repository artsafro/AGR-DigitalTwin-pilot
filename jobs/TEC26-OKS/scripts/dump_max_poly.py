"""new-case: dump one TEC26 building layer (Editable Poly + its collision meshes) from a staged Max COPY to JSON.

Run headless on a copy only (never saves):
  python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --file dump_max_poly.py \
      --scene "C:/x/tec26-oks/sources-v001/Vlad_OKS/04-09 Geometry Final.max"
Environment: TEC26_LAYER (e.g. 008), TEC26_OUT (new JSON path; an existing file is refused).
Per node: name, handle, class, layer, world transform, vertices in world metres, polygons (0-based vertex
indices), material ID per polygon, map channel 1 (UV vertices + per-polygon UV indices) and the Multi/Sub
slot names. Units: the scene must be metres with unit scale 1.0, otherwise the script raises.
"""
import json
import os
from pymxs import runtime as rt

LAYER = os.environ.get("TEC26_LAYER", "008")
OUT = os.environ["TEC26_OUT"]
if os.path.exists(OUT):
    raise SystemExit(f"refusing to overwrite {OUT}")
if str(rt.units.SystemType).lower() != "meters" or abs(float(rt.units.SystemScale) - 1.0) > 1e-9:
    raise SystemExit(f"units not metres x1: {rt.units.SystemType} {rt.units.SystemScale}")


def vec(p):
    return [float(p.x), float(p.y), float(p.z)]


def dump(n):
    poly = rt.convertToPoly(rt.copy(n))  # work on a copy node: modifiers collapsed, source node untouched
    try:
        nv = int(rt.polyop.getNumVerts(poly))
        nf = int(rt.polyop.getNumFaces(poly))
        verts = [vec(rt.polyop.getVert(poly, i)) for i in range(1, nv + 1)]
        faces = [[int(i) - 1 for i in rt.polyop.getFaceVerts(poly, f)] for f in range(1, nf + 1)]
        mat_ids = [int(rt.polyop.getFaceMatID(poly, f)) for f in range(1, nf + 1)]
        uv = None
        if rt.polyop.getMapSupport(poly, 1):
            nm = int(rt.polyop.getNumMapVerts(poly, 1))
            uv = {"verts": [vec(rt.polyop.getMapVert(poly, 1, i))[:2] for i in range(1, nm + 1)],
                  "faces": [[int(i) - 1 for i in rt.polyop.getMapFace(poly, 1, f)] for f in range(1, nf + 1)]}
    finally:
        rt.delete(poly)
    m = n.material
    subs = None
    if m is not None and str(rt.classOf(m)) == "Multimaterial":
        subs = []
        for i in range(1, int(m.numsubs) + 1):
            s = m.materialList[i - 1]
            subs.append({"id": int(m.materialIDList[i - 1]), "name": None if s is None else str(s.name)})
    return {"name": str(n.name), "handle": int(n.handle), "class": str(rt.classOf(n)), "layer": str(n.layer.name),
            "pos": vec(n.pos), "scale": vec(n.scale), "material": None if m is None else str(m.name),
            "multisub": subs, "vertices": verts, "faces": faces, "mat_ids": mat_ids, "uv1": uv}


layer = rt.LayerManager.getLayerFromName(LAYER)
if layer is None:
    raise SystemExit(f"layer {LAYER} not found")
nodes = []
for n in rt.objects:
    if str(n.layer.name) == LAYER and rt.superClassOf(n) == rt.GeometryClass:
        nodes.append(dump(n))
if not nodes:
    raise SystemExit(f"layer {LAYER} has no geometry")
meta = {"scene": str(rt.maxFilePath) + str(rt.maxFileName), "max_version": str(rt.maxVersion()),
        "units": str(rt.units.SystemType), "unit_scale": float(rt.units.SystemScale), "layer": LAYER, "nodes": nodes}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(meta, fh, ensure_ascii=False)
print("DUMP-OK", OUT, [(d["name"], len(d["vertices"]), len(d["faces"])) for d in nodes])
