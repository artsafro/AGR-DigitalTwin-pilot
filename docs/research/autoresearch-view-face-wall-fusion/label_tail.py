"""Append type rays to the pinned #167 adapter, in its fresh native Blender scene.

new-case: docs/research/autoresearch-view-face-wall-fusion/label_tail.py - type rays clipped to physical walls
"""

import math

import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def wall_type_maps(scene, depsgraph, wall_rows, hidden_names, params, type_name, outdir):
    vertices, triangles, labels, types = [], [], [], {}
    for obj in sorted(scene.objects, key=lambda item: item.name):
        if obj.type != 'MESH' or obj.name in hidden_names:
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            offset = len(vertices)
            transform = obj.matrix_world
            vertices.extend(transform @ vertex.co for vertex in mesh.vertices)
            label = types.setdefault(type_name(obj.name), len(types) + 1)
            for triangle in mesh.loop_triangles:
                triangles.append(tuple(offset + idx for idx in triangle.vertices))
                labels.append(label)
        finally:
            evaluated.to_mesh_clear()
    tree = BVHTree.FromPolygons(vertices, triangles, all_triangles=True)

    res = 0.2  # #149 metric label grid
    z0, z1 = params['band_z']
    front, back = params['depth_front_m'], params['depth_back_m']
    maps = {}
    for wall in wall_rows:
        a = math.radians(wall['az'])
        n = Vector((math.cos(a), math.sin(a), 0.0))
        right = Vector((-n.y, n.x, 0.0))
        center_u = (wall['u0'] + wall['u1']) / 2
        width = wall['length'] + 2 * params['lateral_margin_m']
        nx, nz = math.ceil(width / res), math.ceil((z1 - z0) / res)
        arr = np.zeros((nz, nx), np.int32)
        for x in range(nx):
            u = center_u + (x + 0.5 - nx / 2) * res
            p = n * (wall['d'] + front) + right * u
            for y in range(nz):
                p.z = (z1 + z0) / 2 + (nz / 2 - y - 0.5) * res
                hit = tree.ray_cast(p, -n, front + back)
                if hit[0] is not None:
                    arr[y, x] = labels[hit[2]]
        maps[wall['id']] = arr
    np.savez_compressed(f'{outdir}/wall_types.npz', **maps)
