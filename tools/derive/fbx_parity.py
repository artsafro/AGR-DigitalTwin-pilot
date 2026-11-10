"""FBX metric parity for `dt derive` replays (headless Blender): same objects, geometry, UV, materials, textures.

Pattern: n/a | new-case: replay parity receipt for shared tools vs job scripts (#1106).

Blender's FBX writer gives every element a fresh UID, so two exports of the same scene differ in bytes; parity is
judged on the readback instead. Usage:
    blender --background --factory-startup --python tools/derive/fbx_parity.py -- <a.fbx> <b.fbx> <new report.json>
Per file it records, per mesh object: name, vertex/polygon/loop counts, SHA-256 of the world vertex coordinates
rounded to 1e-6 m, of the polygon vertex lists, of every UV layer rounded to 1e-7, of the material slot names,
and per image the name, size and SHA-256 of its pixels. Exit 0 when every field is equal, 1 when any differs
(the differing keys are listed), 2 on unreadable input / existing report.
"""
import hashlib
import json
import os
import sys

import bpy


def digest(values):
    h = hashlib.sha256()
    for v in values:
        h.update(repr(v).encode())
    return h.hexdigest()


def facts(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    objs = {}
    for o in sorted(bpy.data.objects, key=lambda x: x.name):
        if o.type != "MESH":
            objs[o.name] = {"type": o.type}
            continue
        me = o.data
        mw = o.matrix_world
        objs[o.name] = {
            "verts": len(me.vertices), "polys": len(me.polygons), "loops": len(me.loops),
            "xyz": digest(tuple(round(c, 6) for c in (mw @ v.co)) for v in me.vertices),
            "faces": digest(tuple(p.vertices) for p in me.polygons),
            "uv": {u.name: digest((round(d.uv.x, 7), round(d.uv.y, 7)) for d in u.data) for u in me.uv_layers},
            "materials": [s.material.name if s.material else None for s in o.material_slots],
            "material_index": digest(p.material_index for p in me.polygons),
        }
    images = {}
    for im in sorted(bpy.data.images, key=lambda x: x.name):
        if im.size[0] == 0:
            continue
        px = list(im.pixels)
        images[im.name] = {"size": list(im.size), "pixels": digest(round(p, 6) for p in px)}
    return {"objects": objs, "images": images}


def main(argv):
    a, b, out = argv
    if os.path.lexists(out) or os.path.realpath(out) in {os.path.realpath(a), os.path.realpath(b)}:
        print(f"refused: report {out} exists or aliases an input", file=sys.stderr)
        return 2
    for p in (a, b):
        if not os.path.isfile(p):
            print(f"refused: missing {p}", file=sys.stderr)
            return 2
    fa, fb = facts(a), facts(b)
    if not fa["objects"]:
        print(f"refused: {a} has no objects", file=sys.stderr)
        return 2
    diff = []
    for section in ("objects", "images"):
        for k in sorted(set(fa[section]) | set(fb[section])):
            if fa[section].get(k) != fb[section].get(k):
                diff.append(f"{section}:{k}")
    report = {"a": os.path.abspath(a), "b": os.path.abspath(b), "parity": not diff, "differences": diff,
              "a_facts": fa, "b_facts": fb}
    with open(out, "x", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    print("FBX-PARITY", json.dumps({"parity": not diff, "differences": diff,
                                    "objects": {k: [v.get("verts"), v.get("polys")] for k, v in fa["objects"].items()},
                                    "images": sorted(fa["images"])}))
    return 0 if not diff else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[sys.argv.index("--") + 1:]))
