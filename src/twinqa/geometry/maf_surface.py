"""new-case: MAF/GroundEl surface facts (smoothing, flipped faces) for the FBX readback (#185)."""
from __future__ import annotations

import math
from collections import defaultdict, deque


def _len2(v):
    return v[0] * v[0] + v[1] * v[1] + v[2] * v[2]


def _angle_deg(a, b):
    la, lb = math.sqrt(_len2(a)), math.sqrt(_len2(b))
    if la == 0.0 or lb == 0.0:
        return 180.0
    dot = (a[0] * b[0] + a[1] * b[1] + a[2] * b[2]) / (la * lb)
    dot = max(-1.0, min(1.0, dot))
    return math.degrees(math.acos(dot))


def _newell(pts):
    nx = ny = nz = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1, z1 = pts[i]
        x2, y2, z2 = pts[(i + 1) % n]
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    return (nx, ny, nz)


def _tet(o, a, b, c):
    ax, ay, az = a[0] - o[0], a[1] - o[1], a[2] - o[2]
    bx, by, bz = b[0] - o[0], b[1] - o[1], b[2] - o[2]
    cx, cy, cz = c[0] - o[0], c[1] - o[1], c[2] - o[2]
    return (ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)) / 6.0


def _weld_ids(coords, weld_m):
    table = {}
    ids = []
    for c in coords:
        key = (round(c[0] / weld_m), round(c[1] / weld_m), round(c[2] / weld_m))
        wid = table.get(key)
        if wid is None:
            wid = len(table)
            table[key] = wid
        ids.append(wid)
    return ids


def surface_facts(coords, polygons, corner_normals, weld_m=1e-5, split_tol_deg=1.0) -> dict:
    """Welded manifold facts: soft-edge dihedral histogram, winding and outward volume.

    Open bottoms on the plane z = zmin contribute no volume, so a sunk shell keeps the
    closed-shell sign. A flat component (tiny volume) is undetermined, not flipped.
    """
    weld = _weld_ids(coords, weld_m)
    face_n = []
    valid = []
    for i, poly in enumerate(polygons):
        normal = _newell([coords[j] for j in poly])
        face_n.append(normal)
        if _len2(normal) > 1e-24:
            valid.append(i)

    edges = defaultdict(list)
    for fi in valid:
        poly = polygons[fi]
        m = len(poly)
        for k in range(m):
            a = weld[poly[k]]
            b = weld[poly[(k + 1) % m]]
            if a == b:
                continue
            key = (a, b) if a < b else (b, a)
            edges[key].append((fi, a, b, k))

    def corner(face, corner_start, vertex, start, end):
        poly = polygons[face]
        idx = corner_start if vertex == start else (corner_start + 1) % len(poly)
        return corner_normals[face][idx]

    adj = defaultdict(list)
    inconsistent = 0
    hist = defaultdict(int)
    for key, occ in edges.items():
        if len(occ) != 2 or occ[0][0] == occ[1][0]:
            continue
        (f0, s0, e0, c0), (f1, s1, e1, c1) = occ
        same = (s0, e0) == (s1, e1)
        if same:
            inconsistent += 1
        adj[f0].append((f1, same))
        adj[f1].append((f0, same))
        split = False
        for vertex in key:
            ang = _angle_deg(corner(f0, c0, vertex, s0, e0), corner(f1, c1, vertex, s1, e1))
            if ang > split_tol_deg:
                split = True
                break
        if split:
            continue
        nb = face_n[f1]
        if same:
            nb = (-nb[0], -nb[1], -nb[2])
        dihedral = _angle_deg(face_n[f0], nb)
        if dihedral > 1.0:
            hist[f"{round(dihedral, 1):.1f}"] += 1

    components = undetermined = flipped = 0
    seen = set()
    for seed in valid:
        if seed in seen:
            continue
        flip = {seed: False}
        queue = deque([seed])
        seen.add(seed)
        faces = [seed]
        while queue:
            face = queue.popleft()
            for other, same in adj[face]:
                if other in flip:
                    continue
                flip[other] = flip[face] ^ same
                seen.add(other)
                queue.append(other)
                faces.append(other)
        components += 1
        xs, ys, zs, tris = [], [], [], []
        for face in faces:
            pts = [coords[j] for j in polygons[face]]
            if flip[face]:
                pts.reverse()
            xs.extend(p[0] for p in pts)
            ys.extend(p[1] for p in pts)
            zs.extend(p[2] for p in pts)
            for i in range(1, len(pts) - 1):
                tris.append((pts[0], pts[i], pts[i + 1]))
        cx = (min(xs) + max(xs)) / 2.0
        cy = (min(ys) + max(ys)) / 2.0
        origin = (cx, cy, min(zs))
        dx, dy, dz = max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)
        diag = math.sqrt(dx * dx + dy * dy + dz * dz)
        volume = sum(_tet(origin, a, b, c) for a, b, c in tris)
        if abs(volume) <= 1e-9 or abs(volume) <= 1e-6 * diag ** 3:
            undetermined += 1
            continue
        outward_is_propagated = volume > 0
        flipped += sum(flip[face] == outward_is_propagated for face in faces)

    return {
        "components": components,
        "undetermined_components": undetermined,
        "flipped_faces": flipped,
        "inconsistent_edges": inconsistent,
        "soft_edge_angles_deg": dict(hist),
        "weld_m": weld_m,
        "split_tol_deg": split_tol_deg,
    }
