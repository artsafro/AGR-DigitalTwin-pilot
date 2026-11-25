"""Blender writer of the volume body (#1784): meshes.json -> body.blend + body_quad.fbx (one object per volume + glass).

Pattern: n/a | new-case: thin Blender writer of `volume_body.py` output (no geometry logic here; faces, materials and
UVs come from the core + post-ops). Quad review copy only; triangulation is the delivery step [D270].

    blender44 -b --factory-startup --python tools/methods/body/volume_body_blender.py -- <meshes.json> <out_dir> [prefix]
"""
import json
import os
import sys

import bpy

COLORS = {"WALL": (0.82, 0.80, 0.76, 1), "WINDOW": (0.25, 0.45, 0.65, 1), "ROOF": (0.45, 0.45, 0.47, 1)}


def material(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    if name not in COLORS:
        raise ValueError("unmapped material %r" % name)
    m.diffuse_color = COLORS[name]
    return m


def make(name, data):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in data["verts"]], [], [tuple(f["v"]) for f in data["faces"]])
    me.validate(clean_customdata=False)
    mats = sorted({f["mat"] for f in data["faces"]})
    for m in mats:
        me.materials.append(material(m))
    uv = me.uv_layers.new(name="UVMap")
    li = 0
    for p, f in zip(me.polygons, data["faces"]):
        p.material_index = mats.index(f["mat"])
        for j in range(p.loop_total):
            uv.data[p.loop_start + j].uv = f["uv"][j]
        li += p.loop_total
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def main(argv):
    src, out = argv[0], argv[1]
    prefix = argv[2] if len(argv) > 2 else "SM_Sokolniki_OKS"
    os.makedirs(out, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with open(src, encoding="utf-8") as fh:
        meshes = json.load(fh)
    stats = {}
    for vn in sorted(meshes):
        for kind, data in meshes[vn].items():
            name = "%s_%s%s" % (prefix, vn, "" if kind == "body" else "_Glass")
            if not data["faces"]:
                stats[name] = {"skipped": "no faces"}
                continue
            ob = make(name, data)
            stats[name] = {"verts": len(ob.data.vertices), "faces": len(ob.data.polygons)}
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "body.blend"))
    bpy.ops.export_scene.fbx(filepath=os.path.join(out, "body_quad.fbx"), use_selection=False,
                             mesh_smooth_type="FACE", apply_unit_scale=True, axis_forward="-Y", axis_up="Z")
    with open(os.path.join(out, "blender_write.json"), "w", encoding="utf-8") as fh:
        json.dump({"blender": bpy.app.version_string, "objects": stats}, fh, indent=1)
    print("WROTE", len(stats), "objects")


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:])
