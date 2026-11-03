"""Blender writer for the parametric MAF bench generator (#790, model-maf step 3).

    blender --background --factory-startup --python-exit-code 1 \
        --python tools/blender/maf_gen_bench_build.py -- <config.json> <plan-shapes.json> <atlas_uv.json> \
        <atlas.png> <out_dir> [row ...]

Pattern: new-case: generated MAF export - tools/library/maf_gen_bench.py builds one welded quad mesh per row
(plan centreline from verona-plan-shapes.json + section parameters from the config); this script only writes it:
`form` picks the builder (slab_on_posts | clad_box); atlas materials (approved list, 512 slots), box UV inside each slot
(or the generator's board-pattern `face_uv` when `params.seams` = texture), triangulation (MAF-18), hard edges by
angle, NPM + VPM FBX (same mesh: no light version unless the budget needs it [D164]) and a build report.
Refuses to overwrite an FBX (exit 2) and refuses a material outside the atlas (exit 3).
"""
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gen = _load("maf_gen_bench", "tools/library/maf_gen_bench.py")
mss = _load("maf_site_set", "tools/library/maf_site_set.py")

args = sys.argv[sys.argv.index("--") + 1:]
cfg = json.loads(Path(args[0]).read_text(encoding="utf-8"))
shapes = json.loads(Path(args[1]).read_text(encoding="utf-8"))
atlas = json.loads(Path(args[2]).read_text(encoding="utf-8"))
atlas_png = Path(args[3])
out_dir = Path(args[4])
only = set(args[5:])
rects = {name: m["uv"] for name, m in atlas["materials"].items()}
order = list(rects)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def row_spec(row):
    shape = shapes["rows"][str(row["row"])]
    if shape.get("status") != "found":
        raise SystemExit(f"row {row['row']}: plan shape status {shape.get('status')!r}, not 'found'")
    mats = {}
    for role, name in cfg["materials"].items():
        if name not in rects:
            print(f"material {name!r} for {role!r} is not in the atlas {order}", file=sys.stderr)
            sys.exit(3)
        mats[role] = order.index(name) + 1
    spec = dict(cfg["params"], path=shape["centreline_block_m"], materials=mats, name=row["set_id"])
    return spec, shape


def write(set_id, mesh_data, fbx_out):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.load(str(atlas_png))
    me = bpy.data.meshes.new(set_id + "_GroundEl")
    me.from_pydata([tuple(v) for v in mesh_data["verts"]], [], [tuple(f) for f in mesh_data["faces"]])
    me.update()
    for name in order:
        mat = bpy.data.materials.new("MAF_" + name)
        mat.use_nodes = True
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = image
        mat.node_tree.links.new(tex.outputs["Color"], mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
        me.materials.append(mat)
    for p, mid in zip(me.polygons, mesh_data["face_mat"]):
        p.material_index = mid - 1
    obj = bpy.data.objects.new(set_id + "_GroundEl", me)
    bpy.context.scene.collection.objects.link(obj)
    # UV: box projection per face, normalised by the object bounds, inside the material's slot rect
    uv = me.uv_layers.new(name="UVMap")
    co = [v.co for v in me.vertices]
    lo = [min(c[i] for c in co) for i in range(3)]
    span = [max(max(c[i] for c in co) - lo[i], 1e-9) for i in range(3)]
    face_uv = mesh_data.get("face_uv") or [None] * len(me.polygons)
    for p, fuv in zip(me.polygons, face_uv):
        rect = rects[order[p.material_index]]
        if fuv is not None:  # board-pattern UV from the generator: no inset, so the seam lines stay on the joints
            for li, st in zip(p.loop_indices, fuv):
                uv.data[li].uv = mss.remap_into_rect(tuple(st), rect, inset=0.0)
            continue
        axis = max(range(3), key=lambda i: abs(p.normal[i]))
        a, b = [i for i in range(3) if i != axis]
        for li in p.loop_indices:
            c = co[me.loops[li].vertex_index]
            st = (min(1.0, max(0.0, (c[a] - lo[a]) / span[a])), min(1.0, max(0.0, (c[b] - lo[b]) / span[b])))
            uv.data[li].uv = mss.remap_into_rect(st, rect, inset=0.02)
    quads = len(me.polygons)
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])  # MAF-18: derived FBX is triangulated, the master stays quads
    bm.to_mesh(me)
    bm.free()
    for o in bpy.data.objects:
        o.select_set(o is obj)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(cfg["smoothing_deg"]), keep_sharp_edges=False)
    fbx_out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.fbx(filepath=str(fbx_out), use_selection=True, object_types={"MESH"},
                             mesh_smooth_type="FACE", use_mesh_modifiers=True, path_mode="COPY",
                             embed_textures=True, bake_anim=False, add_leaf_bones=False)
    return {"quads_master": quads, "tris": len(me.polygons), "fbx": str(fbx_out).replace("\\", "/"),
            "sha256": sha256(fbx_out)}


rows = [r for r in cfg["rows"] if not only or str(r["row"]) in only]
for row in rows:
    for role in ("npm", "vpm"):
        f = out_dir / role / (row["set_id"] + ".fbx")
        if f.exists():
            print("refusing to overwrite", f, file=sys.stderr)
            sys.exit(2)
report = {"blender": bpy.app.version_string, "config": cfg.get("version"), "form": cfg.get("form", "slab_on_posts"), "smoothing_deg": cfg["smoothing_deg"],
          "atlas_png_sha256": sha256(atlas_png),
          "atlas_uv_json": str(Path(args[2])).replace("\\", "/"), "rows": []}
for row in rows:
    spec, shape = row_spec(row)
    builder = {"slab_on_posts": gen.build_bench, "clad_box": gen.build_clad_box}[cfg.get("form", "slab_on_posts")]
    mesh_data = builder(spec)
    facts = gen.mesh_facts(mesh_data)
    entry = {"row": row["row"], "set_id": row["set_id"], "block": shape["block"], "plan_rotation_deg":
             mesh_data["plan_rotation_deg"], "generator_facts": facts}
    for role in ("npm", "vpm"):
        entry[role] = write(row["set_id"], mesh_data, out_dir / role / (row["set_id"] + ".fbx"))
    report["rows"].append(entry)
    print("built", row["set_id"], facts["dims_m"], entry["npm"]["tris"])
rep = out_dir / "build-report.json"
n = 1
while rep.exists():
    n += 1
    rep = out_dir / f"build-report-{n}.json"
rep.write_text(json.dumps(report, indent=1), encoding="utf-8")
print("report", rep)
