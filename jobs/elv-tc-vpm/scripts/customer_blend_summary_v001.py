"""elv-tc-vpm: condense blend_inventory.json (customer blend) into a readable text summary.

py -3 -I customer_blend_summary_v001.py <blend_inventory.json> <out.txt>
"""
import sys, json, re, collections

d = json.load(open(sys.argv[1], encoding="utf-8"))
L = []
p = L.append
p(f"file {d['file']} | saved by Blender {d['blender_version_file']} | read with {d['blender_running']}")
p(f"counts {d['counts']} totals {d['totals']}")
objs = d["objects"]


def walk(c, ind, scene_objs):
    tris = sum(objs[o].get("tris", 0) for o in c["objects"] if o in objs)
    types = collections.Counter(objs[o]["type"] for o in c["objects"] if o in objs)
    hidden = sum(1 for o in c["objects"] if o in objs and (objs[o]["hide_render"] or objs[o].get("hide_get")))
    p(" " * ind + f"[{c['name']}] objs={len(c['objects'])} tris={tris} types={dict(types)} hidden_objs={hidden} "
      f"coll_hide_vp={c['hide_viewport']} coll_hide_r={c['hide_render']} sample={c['objects'][:4]}")
    for ch in c["children"]:
        walk(ch, ind + 2, scene_objs)


for s in d["scenes"]:
    p(f"\nSCENE {s['name']} units={s['unit_system']} scale={s['scale_length']} len={s['length_unit']} cam={s['camera']} "
      f"engine={s['render_engine']} props={s['props']}")
    excl = {k: v for vl in s["view_layers"].values() for k, v in vl.items() if v["exclude"] or v["hide_viewport"]}
    p(f"  excluded/hidden layer collections: {excl}")
    walk(s["collections"], 2, None)
p("\nLIBRARIES " + json.dumps(d["libraries"], ensure_ascii=False))
p("TEXTS " + json.dumps(d["texts"], ensure_ascii=False))
p("NODE_GROUPS " + json.dumps(d["node_groups"], ensure_ascii=False))
p("\nIMAGES")
for im in d["images"]:
    p("  " + json.dumps(im, ensure_ascii=False))
p("\nMATERIALS (name | users | pass_index | base colour / images)")
for m in d["materials"]:
    imgs = [n.get("image") for n in m.get("nodes", []) if n.get("image")]
    bs = [(n.get("base_color"), n.get("roughness"), n.get("metallic"), n.get("alpha"), n.get("transmission"))
          for n in m.get("nodes", []) if n["type"] == "BSDF_PRINCIPLED"]
    p(f"  {m['name']} | u={m['users']} | pi={m['pass_index']} | diffuse={m['diffuse']} | bsdf={bs} | img={imgs} | props={m['props']}")
p("\nMESH OBJECTS with most tris (top 40)")
ms = sorted(((k, v) for k, v in objs.items() if v["type"] == "MESH"), key=lambda kv: -kv[1].get("tris", 0))
for k, v in ms[:40]:
    p(f"  {k} tris={v.get('tris')} slots={v.get('slots')} fps={v.get('faces_per_slot_index')} uv={v.get('uv')} "
      f"loc={v['loc']} rot={v['rot_deg']} scale={v['scale']} coll={v['collections']} bbox={v.get('bbox_world')} "
      f"mods={v['modifiers']} props={v['props']} attrs={v.get('attrs')}")
p("\nNON-MESH objects by type")
nm = collections.Counter(v["type"] for v in objs.values() if v["type"] != "MESH")
p("  " + str(dict(nm)))
for k, v in objs.items():
    if v["type"] in ("CAMERA", "LIGHT", "EMPTY") and len(L) < 4000:
        p(f"  {v['type']} {k} loc={v['loc']} rot={v['rot_deg']} coll={v['collections']} inst={v['instance_collection']} props={v['props']}")
p("\nOBJECT NAME PREFIXES (first token before '_' x2) count / tris")
pref = collections.defaultdict(lambda: [0, 0])
for k, v in objs.items():
    key = "_".join(re.split(r"[_.]", k)[:2])
    pref[key][0] += 1
    pref[key][1] += v.get("tris", 0)
for k, (n, t) in sorted(pref.items(), key=lambda kv: -kv[1][0])[:80]:
    p(f"  {k}: {n} objs, {t} tris")
p("\nCUSTOM PROPS seen on objects (keys)")
pk = collections.Counter(k for v in objs.values() for k in v["props"])
p("  " + str(dict(pk)))
p("\nNON-IDENTITY transforms on mesh objects: rot!=0 " + str(sum(1 for v in objs.values() if v["type"] == "MESH" and any(abs(x) > 1e-3 for x in v["rot_deg"])))
  + " scale!=1 " + str(sum(1 for v in objs.values() if v["type"] == "MESH" and any(abs(x - 1) > 1e-4 for x in v["scale"]))))
p("modifiers seen: " + str(collections.Counter(m[0] for v in objs.values() for m in v["modifiers"])))
p("attrs seen: " + str(collections.Counter(a[0] for v in objs.values() for a in v.get("attrs", []))))
open(sys.argv[2], "w", encoding="utf-8").write("\n".join(L))
print("lines", len(L))
