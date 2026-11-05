"""elv-tc-vpm: read-only dump of the customer blend's ID scheme (face attributes, full AGR reports, props).

blender -b --disable-autoexec <copy.blend> --python customer_blend_ids_v001.py -- <out.json>
"""
import bpy, sys, os, json, collections

argv = sys.argv[sys.argv.index("--") + 1:]
out = argv[0]
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
rep = {"scene_props": {}, "objects": {}, "texts": {}, "groups": {}}
for sc in bpy.data.scenes:
    rep["scene_props"][sc.name] = {k: str(sc[k]) for k in sc.keys() if k != "agrfw_geo_img"}
for t in bpy.data.texts:
    rep["texts"][t.name] = t.as_string()
KEYS = ("FCD_Elevatornaya_1_001", "SM_Elevatornaya_Vl_1_A_001_Main", "SM_Elevatornaya_Vl_1_A_001_MainGlass",
        "SM_Elevatornaya_1_001_Main", "DIAG_v06_grid_FCD", "BAK_v05_FCD_Elevatornaya_1_001")
for name in KEYS:
    o = bpy.data.objects.get(name)
    if not o:
        continue
    me = o.data
    d = {"props": {k: str(o[k]) for k in o.keys()}, "slots": [s.material.name if s.material else None for s in o.material_slots]}
    fa = {}
    for a in me.attributes:
        if a.domain == "FACE" and a.data_type in ("INT", "BOOLEAN") and not a.name.startswith("."):
            vals = [x.value for x in a.data]
            fa[a.name] = dict(sorted(collections.Counter(vals).items()))
    d["face_attr_hist"] = fa
    # cross tables
    names = [a.name for a in me.attributes if a.domain == "FACE" and a.data_type == "INT" and not a.name.startswith(".")]
    if "fw_tile" in names:
        mi = [p.material_index for p in me.polygons]
        ft = [x.value for x in me.attributes["fw_tile"].data]
        d["fw_tile_x_material"] = {f"{k[0]}|{d['slots'][k[1]] if k[1] < len(d['slots']) else k[1]}": v
                                   for k, v in sorted(collections.Counter(zip(ft, mi)).items())}
        for other in ("fw_part", "agr_part", "agr_wk", "agr_tier", "agr_side"):
            if other in names:
                ov = [x.value for x in me.attributes[other].data]
                d[f"fw_tile_x_{other}"] = {f"{a}|{b}": v for (a, b), v in sorted(collections.Counter(zip(ft, ov)).items())}
        # area + normal per fw_tile
        acc = {}
        for p, t in zip(me.polygons, ft):
            n = p.normal
            k = "+Z" if n.z > 0.7 else "-Z" if n.z < -0.7 else ("+X" if abs(n.x) >= abs(n.y) and n.x > 0 else "-X" if abs(n.x) >= abs(n.y) else "+Y" if n.y > 0 else "-Y")
            e = acc.setdefault(t, {"area": 0.0, "dirs": {}, "zmin": 1e9, "zmax": -1e9})
            e["area"] += p.area
            e["dirs"][k] = round(e["dirs"].get(k, 0) + p.area, 2)
            e["zmin"] = min(e["zmin"], p.center.z)
            e["zmax"] = max(e["zmax"], p.center.z)
        d["fw_tile_area"] = {str(k): {"area": round(v["area"], 1), "dirs": v["dirs"], "zc": [round(v["zmin"], 2), round(v["zmax"], 2)]}
                             for k, v in sorted(acc.items())}
    rep["objects"][name] = d
# source helper groups: counts and prop samples
for c in bpy.data.collections:
    if c.name.startswith(("SRC_", "RV_", "AGR_", "_REVIEW", "RZ_")):
        objs = list(c.objects)
        if not objs:
            continue
        rep["groups"][c.name] = {"n": len(objs), "names": [o.name for o in objs][:60],
                                 "props_sample": [{k: str(o[k])[:160] for k in o.keys()} for o in objs[:3]]}
json.dump(rep, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("DONE", out)
