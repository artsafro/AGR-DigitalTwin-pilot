"""Blender readback: check the actual stage-1 FBX, not its build counters.

blender -b --factory-startup --python-exit-code 1 --python check_corners.py -- body.fbx
"""
import json
import sys
from collections import Counter
from pathlib import Path

import bpy
from mathutils import Vector


def check(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(Path(path).resolve()))
    body, = bpy.context.scene.objects
    mesh = body.data
    pts = [v.co.copy() for v in mesh.vertices]
    incidence = Counter(e for p in mesh.polygons for e in p.edge_keys)
    # The inner lip is an open boundary, the outer lip shared with the facade.
    bottom = min(p.z for p in pts)
    top = max(p.z for p in pts)
    vertical_faces = Counter(e for p in mesh.polygons if abs(p.normal.z) < .01 for e in p.edge_keys)
    caps = corners = bad = tris = 0
    loop_offset = skew = 0.0
    for p in mesh.polygons:
        tris += len(p.vertices) == 3
        if abs(p.normal.z) < .99:
            continue
        caps += 1
        edges = list(p.edge_keys)
        back = [e for e in edges if incidence[e] == 1]
        # At the base of the tower the sill's outer edge is open too.
        if len(edges) != 4 or not (len(back) == 1 or (len(back) == 2 and not set(back[0]) & set(back[1]))):
            bad += 1
            continue
        i, j = back[0]
        pairs = [(b, next(k for e in edges if b in e for k in e if k not in (i, j))) for b in (i, j)]
        front = (pts[pairs[1][1]] - pts[pairs[0][1]]).normalized()
        for b, f in pairs:
            edge = tuple(sorted((b, f)))
            if incidence[edge] != 2 or vertical_faces[edge] != 1:
                bad += 1  # the sill/head must share the depth edge with its jamb
            if len(back) == 2 and pts[b].z not in (bottom, top):
                bad += 1  # detached from the facade inside the floor stack
            delta = pts[b] - pts[f]
            skew = max(skew, abs(delta.dot(front)))
            loop_offset = max(loop_offset, abs(delta.z))
            corners += 1
    # A vertical ring must stay at exactly the same XY through all floor bands.
    ring_offset = max(((pts[i]-pts[j]).xy.length for i,j in incidence if pts[i].z != pts[j].z), default=0)
    result = dict(triangles=tris, nonquads=sum(len(p.vertices)!=4 for p in mesh.polygons),
                  corners=corners, cap_faces=caps, bad_caps=bad, ring_xy_offset_m=ring_offset,
                  loop_z_offset_m=loop_offset, depth_along_facade_m=skew)
    print(json.dumps(result))
    # XY normals are rotated relative to world axes: allow float32 projection noise only.
    assert caps == 726 and corners == 1452 and not any((tris, bad, result['nonquads'], loop_offset, ring_offset)) and skew < 2e-5, result


if __name__ == '__main__':
    check(sys.argv[sys.argv.index('--')+1])
