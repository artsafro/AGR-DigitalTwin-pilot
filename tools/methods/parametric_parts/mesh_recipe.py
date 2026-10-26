"""Analytic meshes for the two parametric parts, in metres.

new-case: bench and KPP1 aerator recipes measured for issue #713.

Bench overall box is the catalogue spec row 49 (Скамейка стальная «Андромеда»): 1.8 x 0.5 x 0.72 m.
The aerator overall box is the abutted KPP1 TN_Аэратор stack: flange diameter 0.390 m and height
0.064 m, pipe diameter 0.100 m and length 0.110 m, cap diameter 0.180 m and height 0.150 m.
"""
from __future__ import annotations

import math

BENCH_LENGTH_M = 1.8
BENCH_WIDTH_M = 0.5
BENCH_HEIGHT_M = 0.72
BENCH_LENGTH_PARAM_M = 1.9

FLANGE_R_M = 0.195
FLANGE_H_M = 0.064
PIPE_R_M = 0.05
PIPE_LENGTH_M = 0.110
CAP_R_M = 0.09
CAP_H_M = 0.150
AERATOR_SIDES = 16
PIPE_LENGTH_PARAM_M = 0.210


def bench_profile(width: float, height: float):
    """Closed YZ silhouette. The bbox of the profile is exactly width by height."""
    leg = 0.06
    back = 0.04
    seat_top = 0.45
    seat_under = 0.40
    if not (0 < leg < width / 2 and 0 < back < width and 0 < seat_under < seat_top < height):
        raise ValueError("bench profile does not fit the spec box")
    return [
        (0.0, 0.0),
        (leg, 0.0),
        (leg, seat_under),
        (width - leg, seat_under),
        (width - leg, 0.0),
        (width, 0.0),
        (width, height),
        (width - back, height),
        (width - back, seat_top),
        (0.0, seat_top),
    ]


def _ring_fan(origin: int, ring: list[int], reverse: bool):
    """Triangles from a centre vertex to every edge of a closed ring."""
    tris = []
    n = len(ring)
    for i in range(n):
        j = (i + 1) % n
        tris.append((origin, ring[j], ring[i]) if reverse else (origin, ring[i], ring[j]))
    return tris


def _ear_clip(profile):
    """Triangles of a simple polygon (indices into profile). Concave silhouettes stay non-overlapping."""
    n = len(profile)
    area = 0.0
    for i, (y, z) in enumerate(profile):
        y2, z2 = profile[(i + 1) % n]
        area += y * z2 - y2 * z
    order = list(range(n))
    if area < 0:
        order.reverse()

    def inside(p, a, b, c):
        cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if cross <= 1e-15:
            return False
        w0 = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
        w1 = (c[0] - b[0]) * (p[1] - b[1]) - (c[1] - b[1]) * (p[0] - b[0])
        w2 = (a[0] - c[0]) * (p[1] - c[1]) - (a[1] - c[1]) * (p[0] - c[0])
        return w0 > 1e-15 and w1 > 1e-15 and w2 > 1e-15

    tris = []
    guard = 0
    while len(order) > 3:
        guard += 1
        if guard > n * n:
            raise ValueError("bench profile did not triangulate")
        clipped = False
        for i in range(len(order)):
            i0, i1, i2 = order[(i - 1) % len(order)], order[i], order[(i + 1) % len(order)]
            a, b, c = profile[i0], profile[i1], profile[i2]
            cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if cross <= 1e-15:
                continue
            if any(inside(profile[j], a, b, c) for j in order if j not in (i0, i1, i2)):
                continue
            tris.append((i0, i1, i2))
            del order[i]
            clipped = True
            break
        if not clipped:
            raise ValueError("bench profile has no ear")
    tris.append((order[0], order[1], order[2]))
    return tris


def _quads(a: list[int], b: list[int]):
    tris = []
    n = len(a)
    for i in range(n):
        j = (i + 1) % n
        tris.append((a[i], a[j], b[j]))
        tris.append((a[i], b[j], b[i]))
    return tris


def extrude_profile(profile, length: float):
    """Extrude a YZ profile along +X from 0 to length. One closed shell."""
    n = len(profile)
    verts = [(0.0, y, z) for y, z in profile] + [(length, y, z) for y, z in profile]
    start = list(range(n))
    end = list(range(n, 2 * n))
    tris = list(_quads(start, end))
    for a, b, c in _ear_clip(profile):
        tris.append((start[a], start[c], start[b]))
        tris.append((end[a], end[b], end[c]))
    return verts, tris


def bench_mesh(length_m: float = BENCH_LENGTH_M, width_m: float = BENCH_WIDTH_M, height_m: float = BENCH_HEIGHT_M):
    return extrude_profile(bench_profile(width_m, height_m), length_m)


def _ring(z: float, radius: float, sides: int):
    return [
        (radius * math.cos(2.0 * math.pi * i / sides), radius * math.sin(2.0 * math.pi * i / sides), z)
        for i in range(sides)
    ]


def aerator_mesh(pipe_length_m: float = PIPE_LENGTH_M, sides: int = AERATOR_SIDES):
    """Stepped revolve. A vertex sits on +X, so the bbox X/Y extents are the flange diameter."""
    z_flange = FLANGE_H_M
    z_pipe = FLANGE_H_M + pipe_length_m
    z_top = z_pipe + CAP_H_M
    rings = [
        _ring(0.0, FLANGE_R_M, sides),
        _ring(z_flange, FLANGE_R_M, sides),
        _ring(z_flange, PIPE_R_M, sides),
        _ring(z_pipe, PIPE_R_M, sides),
        _ring(z_pipe, CAP_R_M, sides),
        _ring(z_top, CAP_R_M, sides),
    ]
    verts = [(-0.0, 0.0, 0.0), (0.0, 0.0, z_top)]
    offsets = []
    for ring in rings:
        offsets.append(list(range(len(verts), len(verts) + sides)))
        verts.extend(ring)
    bottom, top = 0, 1
    outer0, outer1, inner1, inner2, cap0, cap1 = offsets
    tris = []
    tris.extend(_ring_fan(bottom, outer0, reverse=True))
    tris.extend(_quads(outer0, outer1))
    tris.extend(_quads(outer1, inner1))
    tris.extend(_quads(inner1, inner2))
    tris.extend(_quads(inner2, cap0))
    tris.extend(_quads(cap0, cap1))
    tris.extend(_ring_fan(top, cap1, reverse=False))
    return verts, tris


def write_ascii_fbx(path, verts, tris) -> None:
    """ASCII FBX in metres with UnitScaleFactor 100. Writes via a .partial sibling, then renames."""
    import os

    flat = []
    for x, y, z in verts:
        flat.extend((x, y, z))
    indices = []
    for a, b, c in tris:
        indices.extend((a, b, ~c))
    text = (
        "; FBX 7.4.0 project file\n"
        "GlobalSettings:  {\n"
        "  Properties70:  {\n"
        '    P: "UnitScaleFactor", "double", "Number", "", 100\n'
        "  }\n"
        "}\n"
        "Objects:  {\n"
        '  Geometry: 0, "Geometry::Part", "Mesh" {\n'
        f"    Vertices: *{len(flat)} {{\n"
        "      a: " + ",".join(repr(float(v)) for v in flat) + "\n"
        "    }\n"
        f"    PolygonVertexIndex: *{len(indices)} {{\n"
        "      a: " + ",".join(str(int(v)) for v in indices) + "\n"
        "    }\n"
        "  }\n"
        "}\n"
    )
    dest = os.path.abspath(path)
    partial = dest + ".partial"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(partial, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(partial, dest)
