"""Trainer v0 [D387] surface deviation, Blender side (read-only import, never saves).

new-case: tools/trainer/surface_dev.py - two-sided built<->key surface distance for the trainer form step.

    blender -b --factory-startup --python tools/trainer/surface_dev.py -- BUILT.fbx KEY.fbx OUT.json

Samples = all world vertices + face centres of one side, distance = BVH nearest point on the other side's
triangles. Writes {built_to_key: {n, p50, p95, max}, key_to_built: {...}}. Exit 2 when a side has no mesh.
"""
import json
import sys

import bpy
from mathutils.bvhtree import BVHTree


def load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    verts, tris = [], []
    dg = bpy.context.evaluated_depsgraph_get()
    for ob in bpy.context.scene.objects:
        if ob.type != "MESH" or ob.name.upper().startswith("UCX_"):
            continue
        me = ob.evaluated_get(dg).to_mesh()
        me.calc_loop_triangles()
        base = len(verts)
        verts += [ob.matrix_world @ v.co for v in me.vertices]
        tris += [tuple(base + i for i in t.vertices) for t in me.loop_triangles]
    return verts, tris


def stats(dists):
    if not dists:
        return {"n": 0, "p50": None, "p95": None, "max": None}
    d = sorted(dists)
    return {"n": len(d), "p50": d[len(d) // 2], "p95": d[min(len(d) - 1, int(0.95 * len(d)))], "max": d[-1]}


def one_way(src, dst_tree):
    verts, tris = src
    pts = list(verts) + [(verts[a] + verts[b] + verts[c]) / 3 for a, b, c in tris]
    out = []
    for p in pts:
        hit = dst_tree.find_nearest(p)
        if hit[0] is not None:
            out.append(hit[3])
    return stats(out)


def main(argv):
    built, key, out = argv
    b, k = load(built), load(key)
    if not b[1] or not k[1]:
        print("ERROR: a side has no triangles", file=sys.stderr)
        sys.exit(2)
    tb, tk = BVHTree.FromPolygons(b[0], b[1]), BVHTree.FromPolygons(k[0], k[1])
    rep = {"built": built, "key": key, "built_to_key": one_way(b, tk), "key_to_built": one_way(k, tb)}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=1)


main(sys.argv[sys.argv.index("--") + 1:])
