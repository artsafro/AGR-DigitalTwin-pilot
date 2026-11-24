"""#1784 step 3 hook (stage `body`, point `after`), Blender side: v006 = accepted body v005 + inset objects.

Pattern: n/a | new-case: thin Blender writer - opens the v005 body.blend read-only (the body objects are not edited),
adds one object per inset family from inset_build.py's insets_meshes.json with its own material slots, saves a new
body_v006.blend + body_v006_quad.fbx (quad review copy; triangulation is the delivery step [D270]).

    blender44 -b --factory-startup --python jobs/sokolniki-uvk1000/hooks/inset_write_blender.py -- \
        BODY.blend INSETS_MESHES.json NEW_OUT_DIR [TAG=v006]

v007 [D384]: BODY.blend is the roof-well body (volume_body.py with body_config_v007.json), TAG v007.

Writes NEW_OUT_DIR/blender_write.json: per object verts/faces/materials and, for every v005 body object, the
sha256 of its world vertex coordinates + face indices before and after (equal = body untouched).

Render mode (folded in from inset_sheet_blender.py, the job keeps <= 5 listed hooks [D324]): straight orthographic
elevations for the v005 | v006 | v007 | Revit sheets - one camera per facade looking at it from outside, everything
more than `front_m` in front of the facade plane clipped - plus the iso and the close-ups of VIEWS.json:

    blender44 -b --factory-startup --python jobs/sokolniki-uvk1000/hooks/inset_write_blender.py -- \
        render MODEL(.blend|.fbx) VIEWS.json NEW_OUT_DIR TAG

Writes NEW_OUT_DIR/<TAG>_<id>.png, <TAG>_iso.png and <TAG>_<closeup id>.png.
"""
import hashlib
import json
import math  # noqa: F401  (render helpers)
import os
import sys


import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

COLORS = {"04_cassette_fin_RAL8023": (0.55, 0.30, 0.20, 1), "05_cw_structural_RAL7016": (0.30, 0.50, 0.68, 1),
          "10_mesh_20_RAL9003": (0.45, 0.62, 0.50, 1), "12_frame_RAL9003": (0.95, 0.95, 0.93, 1),
          "14_flashing_RAL7016": (0.22, 0.24, 0.26, 1), "M_Glass_01": (0.62, 0.82, 0.86, 1),
          "13_decor_relief_RAL9003": (0.97, 0.96, 0.92, 1), "15_roof_hatch_RAL7016": (0.25, 0.27, 0.30, 1),
          "16_pier_facade": (0.80, 0.78, 0.74, 1)}


def geo_hash(ob):
    h = hashlib.sha256()
    mw = ob.matrix_world
    for v in ob.data.vertices:
        h.update(("%.5f,%.5f,%.5f;" % tuple(mw @ v.co)).encode())
    for p in ob.data.polygons:
        h.update((",".join(str(i) for i in p.vertices) + "|%d;" % p.material_index).encode())
    return h.hexdigest()


def material(name):
    if name not in COLORS:
        raise ValueError("unmapped inset material %r" % name)
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
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
    for p, f in zip(me.polygons, data["faces"]):
        p.material_index = mats.index(f["mat"])
        for j in range(p.loop_total):
            uv.data[p.loop_start + j].uv = f["uv"][j]
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob, mats


def setup(tag):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "SINGLE" if tag == "revit" else "MATERIAL"
    sh.single_color = (0.78, 0.78, 0.76)
    sh.show_cavity = True
    sh.show_object_outline = True
    sh.show_backface_culling = False
    sc.render.film_transparent = False
    sc.world = sc.world or bpy.data.worlds.new("W")
    sc.render.image_settings.file_format = "PNG"
    cam = bpy.data.objects.new("CAM", bpy.data.cameras.new("CAM"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = "ORTHO"
    return sc, cam


def aim(cam, loc, direction):
    cam.location = Vector(loc)
    cam.rotation_euler = Vector(direction).to_track_quat("-Z", "Y").to_euler()


def render(argv):
    """Straight elevations + iso + close-ups of MODEL for the sheet (evidence only, never saves a .blend)."""
    src, views_path, out, tag = argv
    os.makedirs(out, exist_ok=True)
    if src.lower().endswith(".blend"):
        bpy.ops.wm.open_mainfile(filepath=src)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=src)
    with open(views_path, encoding="utf-8") as fh:
        views = json.load(fh)
    sc, cam = setup(tag)
    front, ppm = views["front_m"], views["px_per_m"]
    far = 400.0
    for f in views["facades"]:
        s0, s1 = f["s"]
        z0, z1 = f["z"]
        w, h = (s1 - s0) + 4.0, (z1 - z0) + 4.0
        sm, zm = (s0 + s1) / 2.0, (z0 + z1) / 2.0
        a, t, n = f["a"], f["t"], f["n"]
        dist = 60.0
        loc = (a[0] + t[0] * sm + n[0] * dist, a[1] + t[1] * sm + n[1] * dist, zm)
        aim(cam, loc, (-n[0], -n[1], 0.0))
        cam.data.ortho_scale = max(w, h)
        cam.data.clip_start = dist - front
        cam.data.clip_end = far
        sc.render.resolution_x = int(round(w * ppm))
        sc.render.resolution_y = int(round(h * ppm))
        cam.data.sensor_fit = "HORIZONTAL" if w >= h else "VERTICAL"
        sc.render.filepath = os.path.join(out, "%s_%s.png" % (tag, f["id"]))
        bpy.ops.render.render(write_still=True)
    iso = views.get("iso")
    if iso:
        d = Vector(iso["dir"]).normalized()
        aim(cam, Vector(iso["target"]) - d * 300.0, d)
        cam.data.ortho_scale = iso["scale"]
        cam.data.clip_start, cam.data.clip_end = 1.0, 1000.0
        cam.data.sensor_fit = "HORIZONTAL"
        sc.render.resolution_x, sc.render.resolution_y = 1800, 1200
        sc.render.filepath = os.path.join(out, "%s_iso.png" % tag)
        bpy.ops.render.render(write_still=True)
    shots = views.get("closeups", [])
    for c in shots:
        d = Vector(c["dir"]).normalized()
        aim(cam, Vector(c["target"]) - d * 200.0, d)
        cam.data.ortho_scale = c["scale"]
        cam.data.clip_start, cam.data.clip_end = 1.0, 1000.0
        cam.data.sensor_fit = "HORIZONTAL"
        sc.render.resolution_x, sc.render.resolution_y = c.get("res", [1400, 1000])
        sc.render.filepath = os.path.join(out, "%s_%s.png" % (tag, c["id"]))
        bpy.ops.render.render(write_still=True)
    print("RENDERED", tag, len(views["facades"]) + (1 if iso else 0) + len(shots))


def main(argv):
    body_blend, src, out = argv[:3]
    tag = argv[3] if len(argv) > 3 else "v006"  # v007 [D384]: the body is the v007 roof-well build
    if os.path.exists(os.path.join(out, "body_%s.blend" % tag)):
        print("refused: output exists", file=sys.stderr)
        sys.exit(2)
    os.makedirs(out, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=body_blend)
    body = {ob.name: geo_hash(ob) for ob in bpy.context.scene.objects if ob.type == "MESH"}
    with open(src, encoding="utf-8") as fh:
        meshes = json.load(fh)
    stats = {}
    for name in sorted(meshes):
        if name in body:
            raise ValueError("inset object %s collides with a body object" % name)
        ob, mats = make(name, meshes[name])
        stats[name] = {"verts": len(ob.data.vertices), "faces": len(ob.data.polygons), "materials": mats}
    after = {n: geo_hash(bpy.data.objects[n]) for n in body}
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "body_%s.blend" % tag), copy=True)
    bpy.ops.export_scene.fbx(filepath=os.path.join(out, "body_%s_quad.fbx" % tag), use_selection=False,
                             mesh_smooth_type="FACE", apply_unit_scale=True, axis_forward="-Y", axis_up="Z")
    doc = {"blender": bpy.app.version_string, "source_body": os.path.realpath(body_blend), "insets": stats,
           "body_unchanged": {n: {"before": body[n], "after": after[n], "equal": body[n] == after[n]} for n in body}}
    with open(os.path.join(out, "blender_write.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    print("WROTE", len(stats), "insets; body unchanged:", all(v["equal"] for v in doc["body_unchanged"].values()))


if __name__ == "__main__":
    _args = sys.argv[sys.argv.index("--") + 1:]
    if _args and _args[0] == "render":
        render(_args[1:])
    else:
        main(_args)
