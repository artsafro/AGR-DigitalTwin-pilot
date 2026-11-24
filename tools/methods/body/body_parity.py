"""Parity read-back of a rebuilt stage-1 body against an accepted file (#1736 acceptance: geometry within 1 mm).

Pattern: n/a | new-case: two-file body parity (vertex + face-centroid Hausdorff, quad share, material face counts).

blender -b --factory-startup --python-exit-code 1 --python tools/methods/body/body_parity.py -- \
    ACCEPTED.fbx|.blend REBUILT.fbx|.blend OUT.json [--object SM_Body_Main] [--tol-mm 1.0]
Both files are read only (FBX import / blend append of the named object); world coordinates. OUT is opened with
"x". Exit 1 when the object is missing in either file, the face or vertex counts differ, the Hausdorff distance
of vertices or face centroids exceeds --tol-mm, the quad share differs, or the per-material face counts differ.
"""
import json
import os
import sys


def _load(bpy, path, name):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if path.lower().endswith(".fbx"):
        bpy.ops.import_scene.fbx(filepath=path)
    else:
        with bpy.data.libraries.load(path, link=False) as (src, dst):
            dst.objects = [n for n in src.objects if n == name]
        for ob in dst.objects:
            bpy.context.scene.collection.objects.link(ob)
    ob = bpy.data.objects.get(name)
    if ob is None or ob.type != "MESH":
        raise SystemExit("refused: no mesh object %r in %s" % (name, path))
    bpy.context.view_layer.update()
    mw = ob.matrix_world
    me = ob.data
    verts = [tuple(mw @ v.co) for v in me.vertices]
    cents = [tuple(mw @ p.center) for p in me.polygons]
    mats = {}
    for p in me.polygons:
        m = me.materials[p.material_index].name.split(".")[0] if me.materials else ""
        mats[m] = mats.get(m, 0) + 1
    quads = sum(1 for p in me.polygons if len(p.vertices) == 4)
    return {"verts": verts, "cents": cents, "mats": mats, "faces": len(me.polygons),
            "quad_share": quads / max(1, len(me.polygons)), "tris": sum(1 for p in me.polygons if len(p.vertices) == 3)}


def _haus(a, b):
    from mathutils.kdtree import KDTree

    def one(p, q):
        t = KDTree(len(q))
        for i, c in enumerate(q):
            t.insert(c, i)
        t.balance()
        return max((t.find(c)[2] for c in p), default=0.0)

    return max(one(a, b), one(b, a))


def main(argv):
    import bpy

    args = argv[argv.index("--") + 1:]
    acc, new, out = args[0], args[1], args[2]
    name = args[args.index("--object") + 1] if "--object" in args else "SM_Body_Main"
    tol = float(args[args.index("--tol-mm") + 1]) if "--tol-mm" in args else 1.0
    if len({os.path.realpath(p) for p in (acc, new, out)}) != 3:
        raise SystemExit("refused: ACCEPTED, REBUILT and OUT must be three different files")
    A, B = _load(bpy, acc, name), _load(bpy, new, name)
    rep = {"accepted": acc, "rebuilt": new, "object": name, "tol_mm": tol,
           "verts": [len(A["verts"]), len(B["verts"])], "faces": [A["faces"], B["faces"]],
           "tris": [A["tris"], B["tris"]], "quad_share": [round(A["quad_share"], 6), round(B["quad_share"], 6)],
           "materials": [A["mats"], B["mats"]],
           "vert_hausdorff_mm": round(_haus(A["verts"], B["verts"]) * 1000, 4),
           "centroid_hausdorff_mm": round(_haus(A["cents"], B["cents"]) * 1000, 4)}
    fails = []
    if rep["verts"][0] != rep["verts"][1] or rep["faces"][0] != rep["faces"][1]:
        fails.append("counts differ")
    if rep["vert_hausdorff_mm"] > tol or rep["centroid_hausdorff_mm"] > tol:
        fails.append("geometry deviates > %.3f mm" % tol)
    if rep["quad_share"][0] != rep["quad_share"][1]:
        fails.append("quad share differs")
    if sorted(A["mats"].values()) != sorted(B["mats"].values()) or set(A["mats"]) != set(B["mats"]):
        fails.append("material face counts differ")
    rep["fails"], rep["parity"] = fails, not fails
    with open(out, "x", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1)
    print("PARITY", json.dumps({k: rep[k] for k in ("verts", "faces", "quad_share", "vert_hausdorff_mm",
                                                     "centroid_hausdorff_mm", "fails")}))
    if fails:
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv)
