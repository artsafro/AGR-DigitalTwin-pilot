"""elv-tc-vpm: clean reference scene from the Revit FBX import (job-local, Blender 5.1 background).

blender -b <building_import.blend> --python ref_clean.py -- <delete_ids.txt> <out_dir>

Removes the proposed objects (anomaly / true duplicates / interior, by exact Revit object name), unparents,
bakes world transforms into single-user meshes (0.3048 ft->m scale, mirrored objects get their winding flipped),
sorts the objects into category collections and saves <out_dir>/elv_ref_clean_v001.blend + report json.
Never overwrites: stops if the output exists.
"""
import bpy, bmesh, sys, os, re, json, collections
from mathutils import Matrix

argv = sys.argv[sys.argv.index("--") + 1:]
ids_path, out_dir = argv[0], argv[1]
out_blend = os.path.join(out_dir, "elv_ref_clean_v001.blend")
if os.path.exists(out_blend):
    raise SystemExit("output exists: " + out_blend)
os.makedirs(out_dir, exist_ok=True)

# rules are tried in order; the first hit wins (name regex, optional geometry test on world bbox dims)
RULES = [
    ("lights_arktos", r"Arktos", None),
    ("gate", r"\(DR\)-LG|LoadingSystem|Gate", None),
    ("door", r"\(DR\)|Дверь|Главный вход", None),
    ("window", r"\(WN\)|Окно", None),
    ("railing", r"Ограждение|перил", None),
    ("stair_ext", r"лестниц|марш|площадка", None),
    ("stemalit", r"Стемалит", None),
    ("glass", r"остеклен|\(CP\)_Glass", None),
    ("sign_frame", r"импост black", None),
    ("mullion", r"импост", None),
    ("canopy", r"Перекрытие \(Ext\)_metall kasset WOOD|Gutter|Водосточный", None),
    ("wood_cassette", r"metall kasset WOOD", None),
    ("metal_cassette", r"metall panels", None),
    ("rib_lamella", r"\(In\)_25\(DW-25", lambda d: d[2] > 2.0),
    ("sandwich", r"Sandwich|\(RAL7021\)_о", None),
    ("plinth", r"Цоколь|Базовая стена", lambda d, z=None: False),  # placeholder, real test below
    ("parapet_flashing", r"\(SC\)-Batten|Batten|^Низ ", None),
    ("roof", r"крыша|Перекрытие эксплуатируемая|Перекрытие Монолитный|Перекрытие плита|балка", None),
    ("equipment", r"Стакан|\(SC\)_pipes|Деталь|ADSK_|\(SI\)|Mirror", None),
    ("wall_ext", r"Базовая стена (\(Ext\)|\(WL\)-Ext|\(AR\)|С_|Минерал|Наружнее|монолитный|Кирпич|Пенополи|Основание)", None),
]
CATS = ["wall_ext", "curtain_wall", "mullion", "glass", "stemalit", "wood_cassette", "metal_cassette", "sandwich",
        "plinth", "roof", "parapet_flashing", "rib_lamella", "canopy", "door", "window", "gate", "railing",
        "stair_ext", "equipment", "lights_arktos", "sign_frame", "other"]


def classify(name, mn, mx):
    d = [mx[i] - mn[i] for i in range(3)]
    # plinth: exterior wall pieces whose top is at or below +0.25 (base course below the cassettes)
    if re.search(r"Цоколь", name) or (re.search(r"Базовая стена", name) and mx[2] <= 0.25 and mn[2] < 0.0
                                      and not re.search(r"\(In\)|-In_", name)):
        return "plinth"
    for cat, rx, test in RULES:
        if cat == "plinth":
            continue
        if re.search(rx, name) and (test is None or test(d)):
            return cat
    return "other"


names = [l.rstrip("\n").split("\t")[2] for l in open(ids_path, encoding="utf-8") if l.strip()]
todel = set(names)
sc = bpy.context.scene
found = [o for o in sc.objects if o.name in todel]
missing = sorted(todel - {o.name for o in found})
R = {"delete_list": len(todel), "deleted_found": len(found), "delete_missing": missing[:20]}
for o in found:
    bpy.data.objects.remove(o, do_unlink=True)

meshes = [o for o in sc.objects if o.type == "MESH"]
mirrored = 0
neg_vol_before = neg_vol_after = closed = 0


def signed_volume(me):
    bm = bmesh.new(); bm.from_mesh(me)
    ok = all(e.is_manifold for e in bm.edges) and len(bm.faces) > 0
    v = bm.calc_volume(signed=True) if ok else None
    bm.free()
    return v


for o in meshes:
    mw = o.matrix_world.copy()
    me = o.data.copy()  # single user, original data untouched for other users
    me.transform(mw)
    if mw.determinant() < 0:
        me.flip_normals()
        mirrored += 1
    o.data = me
    o.parent = None
    o.matrix_world = Matrix.Identity(4)
for o in [o for o in sc.objects if o.type != "MESH"]:
    bpy.data.objects.remove(o, do_unlink=True)
for o in meshes:
    v = signed_volume(o.data)
    if v is not None:
        closed += 1
        neg_vol_after += v < -1e-9
R.update(meshes=len(meshes), mirrored_flipped=mirrored, closed_meshes=closed, closed_negative_volume_after=neg_vol_after)

# collections
root = sc.collection
cols = {}
for c in CATS:
    cols[c] = bpy.data.collections.new(c)
    root.children.link(cols[c])
stats = {c: {"objects": 0, "tris": 0} for c in CATS}
for o in meshes:
    vs = [v.co for v in o.data.vertices]
    if not vs:
        cat = "other"; mn = mx = (0, 0, 0)
    else:
        mn = [min(v[i] for v in vs) for i in range(3)]; mx = [max(v[i] for v in vs) for i in range(3)]
        cat = classify(o.name, mn, mx)
    for c in list(o.users_collection):
        c.objects.unlink(o)
    cols[cat].objects.link(o)
    o["ref_category"] = cat
    o.data.calc_loop_triangles()
    stats[cat]["objects"] += 1; stats[cat]["tris"] += len(o.data.loop_triangles)
for c in [c for c in bpy.data.collections if c.name not in CATS]:
    bpy.data.collections.remove(c)
bpy.ops.outliner.orphans_purge(do_recursive=True)
R["collections"] = stats
R["total_objects"] = sum(s["objects"] for s in stats.values()); R["total_tris"] = sum(s["tris"] for s in stats.values())
R["other_names"] = sorted(collections.Counter(re.sub(r"(\s*\[\d+\].*$|_[0-9a-f]{7}(\.\d+)?$|\.\d+$)", "", o.name)
                                              for o in cols["other"].objects).items(), key=lambda kv: -kv[1])
sc.unit_settings.system = "METRIC"; sc.unit_settings.scale_length = 1.0
bpy.ops.wm.save_as_mainfile(filepath=out_blend, compress=True)
json.dump(R, open(os.path.join(out_dir, "ref_clean_report_v001.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("REF_CLEAN", json.dumps({k: R[k] for k in R if k not in ("other_names", "collections")}))
for c in CATS:
    print("  %-18s %5d obj %7d tris" % (c, stats[c]["objects"], stats[c]["tris"]))
