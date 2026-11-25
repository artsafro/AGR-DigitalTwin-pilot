"""Blender writer + CLI of the shared body core (#1736): plan -> module.blend, body.blend, body.fbx, build.json.

Pattern: n/a | new-case: Blender front of tools/methods/body/body_lattice.py (the geometry is built there, pure Python).

blender -b --factory-startup --python-exit-code 1 --python tools/methods/body/body_lattice_blender.py -- \
    PLAN.json OUT_DIR [--tex DIR] [--max-side M]
(`uv run agr body PLAN.json OUT_DIR ...` finds Blender and runs this.) OUT_DIR must be new; PLAN must not be inside
it. --tex: DIR/<material>.png is bound to that material when present. Objects: SM_Body_Module (module.blend only) and
SM_Body_Main at location z = plan z0; materials only those used; FBX = all objects, face smoothing.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import body_lattice as core  # noqa: E402


def _mesh(bpy, name, data, mats):
    me = bpy.data.meshes.new(name)
    me.from_pydata(data["verts"], [], [f["v"] for f in data["faces"]])
    me.validate(clean_customdata=False)
    if len(me.polygons) != len(data["faces"]):
        raise SystemExit("refused: Blender dropped %d faces of %s" % (len(data["faces"]) - len(me.polygons), name))
    uv = me.uv_layers.new(name="UVMap")
    idx = {m: i for i, m in enumerate(data["materials"])}
    for p, f in zip(me.polygons, data["faces"]):
        p.material_index = idx[f["mat"]]
        for li, (u, v) in zip(p.loop_indices, f["uv"]):
            uv.data[li].uv = (u, v)
    for m in data["materials"]:
        me.materials.append(mats[m])
    return me


def main(argv):
    import bpy

    args = argv[argv.index("--") + 1:] if "--" in argv else argv
    if len(args) < 2:
        raise SystemExit("usage: -- PLAN.json OUT_DIR [--tex DIR] [--max-side M]")
    plan_path, out = os.path.realpath(args[0]), os.path.realpath(args[1])
    tex_dir = args[args.index("--tex") + 1] if "--tex" in args else None
    max_side = float(args[args.index("--max-side") + 1]) if "--max-side" in args else None
    if os.path.exists(out):
        raise SystemExit("refused: OUT_DIR exists, outputs are versioned (new folder per run)")
    if os.path.splitdrive(plan_path)[0].lower() == os.path.splitdrive(out)[0].lower() \
            and os.path.commonpath([plan_path, out]) == out:
        raise SystemExit("refused: PLAN is inside OUT_DIR")
    plan = core.load_plan(plan_path)
    module = core.build_module(plan, max_side=max_side)
    body = core.replicate(module, plan)
    os.makedirs(out)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mats = {}
    for n in module["materials"]:
        m = bpy.data.materials.new(n)
        m.diffuse_color = (*plan["materials"][n], 1.0)
        img = os.path.join(tex_dir, n + ".png") if tex_dir else None
        if img and os.path.exists(img):
            m.use_nodes = True
            t = m.node_tree.nodes.new("ShaderNodeTexImage")
            t.image = bpy.data.images.load(img)
            m.node_tree.links.new(t.outputs["Color"], m.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
        mats[n] = m
    z0 = float(plan["z0"])
    mod = bpy.data.objects.new("SM_Body_Module", _mesh(bpy, "SM_Body_Module", module, mats))
    bpy.context.scene.collection.objects.link(mod)
    mod.location.z = z0
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "module.blend"), copy=True)
    bpy.data.objects.remove(mod)
    ob = bpy.data.objects.new("SM_Body_Main", _mesh(bpy, "SM_Body_Main", body, mats))
    bpy.context.scene.collection.objects.link(ob)
    ob.location.z = z0
    report = body["report"]
    report["core"] = "tools/methods/body/body_lattice.py"
    report["plan"] = plan_path
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "body.blend"), copy=True)
    bpy.ops.export_scene.fbx(filepath=os.path.join(out, "body.fbx"), use_selection=False, mesh_smooth_type="FACE",
                             path_mode="COPY", embed_textures=False)
    with open(os.path.join(out, "build.json"), "x", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    print("BUILT", json.dumps(report))


if __name__ == "__main__":
    try:
        main(sys.argv)
    except ValueError as e:
        raise SystemExit("refused: %s" % e)
