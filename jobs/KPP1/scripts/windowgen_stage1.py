"""#1338 stage 1: KPP1-W01..W03 isolated -> winplace_core.plan -> build_type(vpm) -> OBJ -> Blender readback.

Pattern: new-case (see kpp1_windowgen.py).
Usage: blender --background --factory-startup --python windowgen_stage1.py -- <new out_dir> [type ids...]
Blender: the KPP1 pipeline and its readbacks are Blender-native and headless; Max adds nothing for an OBJ round trip.
"""
import bpy, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kpp1_windowgen as kw  # noqa: E402
import windowgen_core as wg  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
out, ids = args[0], (args[1:] or ["KPP1-W01", "KPP1-W02", "KPP1-W03"])
if os.path.exists(out):
    raise SystemExit(f"out dir exists (never overwritten): {out}")
os.makedirs(out)
types, standard = kw.load_library()
iso = kw.isolated_plan(ids, types, standard)
rows = []
for tid in ids:
    mesh = iso[tid]["mesh"]
    path = os.path.join(out, tid + ".obj")
    open(path, "x", encoding="utf-8").write(wg.to_obj(mesh, tid))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.obj_import(filepath=path, forward_axis="Y", up_axis="Z", use_split_objects=True, use_split_groups=True)
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    verts, faces, parts, glass = [], 0, {"frame": 0, "glass": 0}, []
    for o in objs:
        part = "glass" if o.name.endswith("_glass") else "frame" if o.name.endswith("_frame") else None
        if part is None:
            raise SystemExit(f"unexpected readback object {o.name}")
        m = o.data
        ws = [o.matrix_world @ v.co for v in m.vertices]
        verts += [tuple(round(c, 6) for c in p) for p in ws]
        faces += len(m.polygons)
        parts[part] += len(m.polygons)
        if part == "glass":
            for p in m.polygons:
                pts = [ws[i] for i in p.vertices]
                glass.append([round(min(q.x for q in pts), 6), round(min(q.z for q in pts), 6),
                              round(max(q.x for q in pts), 6), round(max(q.z for q in pts), 6), round(pts[0].y, 6)])
    uniq = sorted(set(verts))
    got = {"verts": len(uniq), "faces": faces, "parts": parts, "glass": sorted(glass),
           "bbox": [[min(v[i] for v in uniq) for i in range(3)], [max(v[i] for v in uniq) for i in range(3)]]}
    want = kw.mesh_summary(mesh)
    diff = kw.compare_readback(want, got)
    entry = next(t for t in types if t["id"] == tid)
    rows.append({"type": tid, "size_m": [entry["width_m"], entry["height_m"]], "library_panes_m": entry["panes_m"],
                 "library_glass_m": entry["source"].get("glass_m"), "standardized_fields": mesh["fields"],
                 "family": mesh["family"], "depth_m": mesh["depth_m"], "glass_y_m": mesh["glass_y_m"],
                 "win_place": iso[tid]["action"], "built": want, "readback": got, "diff": diff,
                 "readback_ok": not diff, "obj": os.path.basename(path)})
    print("STAGE1", tid, "ok" if not diff else diff)
res = {"schema": "kpp1-windowgen-stage1/1", "blender": bpy.app.version_string, "types": rows,
       "note": "build_type always standardizes (windowgen_core.build_type -> standardize): outer edges snap to the "
               "F100 face 57 mm, so the library panes (50 mm) move 7 mm inward."}
json.dump(res, open(os.path.join(out, "stage1_readback.json"), "x", encoding="utf-8"), indent=1, ensure_ascii=False)
if any(r["diff"] for r in rows):
    sys.exit(1)
