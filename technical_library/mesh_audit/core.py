"""Read-only topology inventory shared by DCC jobs; never certifies delivery."""
from collections import Counter, defaultdict
import itertools
import math


def _has_proper_crossing(poly):
    """Detect bounded proper edge crossings on a planar polygon.

    Uses maximal-magnitude cross-product projection to 2D and tests non-adjacent
    edge pairs against a signed determinant tolerance of +/-1e-10 m^2.
    When all vertex triples are collinear (no usable cross product, best_mag2 <= 0.0),
    returns False as a fallback; this zero return does not certify mesh or face validity.
    """
    if len(poly) < 4:
        return False
    best_cross = None
    best_mag2 = 0.0
    for p1, p2, p3 in itertools.combinations(poly, 3):
        v1 = (p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2])
        v2 = (p3[0] - p1[0], p3[1] - p1[1], p3[2] - p1[2])
        cx = v1[1] * v2[2] - v1[2] * v2[1]
        cy = v1[2] * v2[0] - v1[0] * v2[2]
        cz = v1[0] * v2[1] - v1[1] * v2[0]
        mag2 = cx * cx + cy * cy + cz * cz
        if mag2 > best_mag2:
            best_mag2 = mag2
            best_cross = (cx, cy, cz)
    if best_cross is None or best_mag2 <= 0.0:
        return False
    abs_c = (abs(best_cross[0]), abs(best_cross[1]), abs(best_cross[2]))
    drop = max(range(3), key=lambda k: abs_c[k])
    axes = [k for k in range(3) if k != drop]
    pts2d = [(p[axes[0]], p[axes[1]]) for p in poly]
    n = len(pts2d)
    for i in range(n):
        a = pts2d[i]
        b = pts2d[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue
            c = pts2d[j]
            d = pts2d[(j + 1) % n]
            cp1 = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            cp2 = (b[0] - a[0]) * (d[1] - a[1]) - (b[1] - a[1]) * (d[0] - a[0])
            if not ((cp1 > 1e-10 and cp2 < -1e-10) or (cp1 < -1e-10 and cp2 > 1e-10)):
                continue
            cp3 = (d[0] - c[0]) * (a[1] - c[1]) - (d[1] - c[1]) * (a[0] - c[0])
            cp4 = (d[0] - c[0]) * (b[1] - c[1]) - (d[1] - c[1]) * (b[0] - c[0])
            if not ((cp3 > 1e-10 and cp4 < -1e-10) or (cp3 < -1e-10 and cp4 > 1e-10)):
                continue
            return True
    return False


def inspect_mesh(vertices, faces, edges=None, material_ids=None, decimals=8, near_m=0.001):
    try:
        near_ok = math.isfinite(near_m) and near_m > 0
    except TypeError:
        near_ok = False
    if not near_ok:
        raise ValueError('near_m must be a finite number > 0')
    count = len(vertices)
    if any(len(v) != 3 or not all(math.isfinite(c) for c in v) for v in vertices):
        raise ValueError('Vertices must be finite XYZ triples')
    if any(len(f) < 3 or any(i < 0 or i >= count for i in f) for f in faces):
        raise ValueError('Invalid face indices')
    incidence = Counter(); used = set(); canonical = Counter(); material_edges = {}
    parent = list(range(count))

    def root(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def connect(a, b):
        parent[root(a)] = root(b)

    material_ids = [0]*len(faces) if material_ids is None else material_ids
    if len(material_ids) != len(faces):
        raise ValueError('Material IDs must match face count')
    zero_area = 0; bowties = 0; winding = defaultdict(list)
    for face, material in zip(faces, material_ids):
        face = list(face); used.update(face); canonical[tuple(sorted(face))] += 1
        area = 0.0; origin = vertices[face[0]]
        for i in range(1, len(face)-1):
            a = [vertices[face[i]][k]-origin[k] for k in range(3)]
            b = [vertices[face[i+1]][k]-origin[k] for k in range(3)]
            cross = [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
            area += math.sqrt(sum(c*c for c in cross))/2
        zero_area += area < 1e-12
        bowties += 1 if _has_proper_crossing([vertices[i] for i in face]) else 0
        for a,b in zip(face, face[1:]+face[:1]):
            edge = tuple(sorted((a,b))); incidence[edge] += 1; winding[edge].append(a)
            material_edges.setdefault(edge,set()).add(material); connect(a,b)
    all_edges = set(incidence)
    for a,b in edges or []:
        if a<0 or b<0 or a>=count or b>=count:
            raise ValueError('Invalid edge indices')
        all_edges.add(tuple(sorted((a,b)))); connect(a,b)
    rounded = [tuple(round(c,decimals) for c in v) for v in vertices]
    extent = [max(v[k] for v in vertices)-min(v[k] for v in vertices) for k in range(3)] if vertices else [0]*3
    cells = defaultdict(list)
    for index, point in enumerate(vertices):
        cells[tuple(int(math.floor(c/near_m)) for c in point)].append(index)
    near = set()
    for key, ids in cells.items():
        for dx,dy,dz in [(dx,dy,dz) for dx in (-1,0,1) for dy in (-1,0,1) for dz in (-1,0,1)]:
            for j in cells.get((key[0]+dx, key[1]+dy, key[2]+dz), ()):
                for i in ids:
                    if i<j and sum((vertices[i][k]-vertices[j][k])**2 for k in range(3))<=near_m**2:
                        near.add(j)
    return {'vertices':count,'faces':len(faces),'polygon_sizes':dict(Counter(map(len,faces))),
      'triangles':sum(len(f)-2 for f in faces),'connected_components':len({root(i) for i in range(count)}),
      'duplicate_vertices_rounded':count-len(set(rounded)),'duplicate_vertex_decimals':decimals,
      'duplicate_faces_by_vertex_set':sum(n-1 for n in canonical.values()),'zero_area_faces_fan':zero_area,
      'boundary_edges':sum(n==1 for n in incidence.values()),'multi_face_edges':sum(n>2 for n in incidence.values()),
      'loose_edges':len(all_edges-set(incidence)),'vertices_unused_by_faces':count-len(used),
      'material_face_counts':dict(Counter(material_ids)),
      'material_interface_edges':sum(len(ids)>1 for ids in material_edges.values()),'extent_m':extent,
      'inconsistent_winding_edges':sum(len(s)==2 and s[0]==s[1] for s in winding.values()),
      'near_duplicate_vertices':len(near),'near_duplicate_threshold_m':near_m,
      'self_intersecting_polygons':bowties,
      'intersection_test_performed':False,'delivery_passed':False}
