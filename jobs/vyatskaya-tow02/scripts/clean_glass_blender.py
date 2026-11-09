"""TOW02 glass cleanup: one quad per flat window, segments only where the glass bends (runs inside Blender, headless).

Engine gap: EG6 (panelised curtain-wall source, docs/backlog.md).

User rule 2026-10-21 (shown by hand in 3ds Max on TOW02_body_glass): a flat window keeps only its 4 corner points;
a window on a corner bend keeps its segments so the bend survives; a 90-degree corner window is one element of two
quads sharing the corner edge (6 points), not two planes with one sticking out of the other. Applied to
TOW02_body_glass and TOW02_top_glass: coplanar neighbours are dissolved into one face and the straight-line vertices
left on its boundary are removed (bmesh dissolve_limit, ANGLE_DEG; then points within LINE_M of a straight edge),
so the glass ribbons stop following the body's column cuts. Corner slivers (< SLIVER_M) between two faces meeting
at more than CORNER_DEG are removed and the two faces share one vertical edge at their plan intersection. Every resulting face must be a quad; anything else fails.

Usage:
  blender -b <in.blend> --python scripts/clean_glass_blender.py -- <out_dir>
Writes <out_dir>/tow02_master.blend; the input is never saved.
"""
import collections
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

OBJECTS = ("TOW02_body_glass", "TOW02_top_glass")
ANGLE_DEG = 0.5
WELD_M = 0.001
LINE_M = 0.002
SLIVER_M = 0.06
CORNER_DEG = 45.0


def clean(obj):
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    before = len(bm.faces)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=WELD_M)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(ANGLE_DEG), use_dissolve_boundaries=False,
                             verts=list(bm.verts), edges=list(bm.edges), delimit={'NORMAL'})
    # A boundary point on a very short segment can bend the line by more than ANGLE_DEG while sitting a fraction
    # of a millimetre off it: drop 2-edge points closer than LINE_M to the line through their neighbours.
    loose = []
    for v in bm.verts:
        if len(v.link_edges) == 2 and len(v.link_faces) == 1:
            a, b = (e.other_vert(v).co for e in v.link_edges)
            ab = b - a
            if ab.length > 1e-9 and (v.co - a).cross(ab).length / ab.length < LINE_M:
                loose.append(v)
    bmesh.ops.dissolve_verts(bm, verts=loose)
    corners = join_corners(bm)
    sizes = collections.Counter(len(f.verts) for f in bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.update()
    if set(sizes) != {4}:
        raise RuntimeError(f"{obj.name}: non-quad faces after cleanup {dict(sizes)}")
    return dict(faces_before=before, faces_after=len(me.polygons), verts_after=len(me.vertices), corners_joined=corners)


def plan_line(face):
    """Bottom edge of a vertical quad in plan (two XY points)."""
    bottom = sorted(face.verts, key=lambda v: v.co.z)[:2]
    return [Vector((v.co.x, v.co.y)) for v in bottom]


def intersect(p, q):
    (a, b), (c, d) = p, q
    r, s = b - a, d - c
    den = r.x * s.y - r.y * s.x
    if abs(den) < 1e-9:
        return None
    t = ((c - a).x * s.y - (c - a).y * s.x) / den
    return a + r * t


def join_corners(bm):
    """Corner windows: drop a sliver face (bottom width < SLIVER_M) standing between two faces that meet at more than
    CORNER_DEG, and stitch the two faces on one vertical edge at the intersection of their plan lines (6 points)."""
    joined = 0
    bm.faces.ensure_lookup_table()
    for f in list(bm.faces):
        if not f.is_valid or len(f.verts) != 4:
            continue
        bottom = sorted(f.verts, key=lambda v: v.co.z)[:2]
        if (bottom[0].co.xy - bottom[1].co.xy).length >= SLIVER_M:
            continue
        sides = [e for e in f.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 0.5]
        nbrs = [next((g for g in e.link_faces if g is not f), None) for e in sides]
        if len(sides) != 2 or None in nbrs or nbrs[0].normal.angle(nbrs[1].normal) < math.radians(CORNER_DEG):
            continue
        p = intersect(plan_line(nbrs[0]), plan_line(nbrs[1]))
        if p is None:
            continue
        pairs = [[level(e.verts, key=lambda v: v.co.z) for e in sides] for level in (min, max)]
        for vs in pairs:
            for v in vs:
                v.co.x, v.co.y = p.x, p.y
            bmesh.ops.pointmerge(bm, verts=vs, merge_co=vs[0].co.copy())
        joined += 1
    bmesh.ops.dissolve_degenerate(bm, dist=WELD_M, edges=bm.edges[:])
    for f in [f for f in bm.faces if f.calc_area() < 1e-6]:
        bm.faces.remove(f)
    return joined


def main(out_dir):
    report = {name: clean(bpy.data.objects[name]) for name in OBJECTS}
    os.makedirs(out_dir, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.path.abspath(out_dir), "tow02_master.blend"), copy=False)
    print("CLEAN_DONE " + json.dumps(report))


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1])
