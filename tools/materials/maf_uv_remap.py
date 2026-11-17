"""Shared UV transfer into an atlas slot (#1410, plan #425 step 6): one owner for MAF and Flora atlases.

Pattern: n/a | new-case: UV remap into atlas slot rects lifted out of tools/blender/maf_site_set_build.py
(MAF NPM 512 atlas, [D236]) and shared with the Flora atlas (tools/library/flora_atlas_from_scene.py,
``remap_uv``). No bpy / pymxs import: Blender (``maf_site_set_build.py``, ``maf_npm_light``) and 3ds Max
(AGR Tools Python) call the same functions with plain lists.

Two transfers:

* ``remap_into_rect`` - a normalised (s, t) in [0, 1]^2 into a slot rect [u0, v0, u1, v1] with an optional
  inset; the relative layout inside the slot is kept (Flora tiles use inset 0).
* ``box_project_uvs`` - a mesh without a usable UV (library MAF copies): per face, the dominant normal axis
  picks the projection plane, the coordinates are normalised by the object bounds and mapped into the face's
  slot rect. Every face ends inside its own rect; a face without a rect is an error naming it.

Fail closed: non-finite or out-of-range input, a rect that is not four finite numbers with u0 < u1 and v0 < v1,
an inset outside [0, 0.5), an empty mesh, a face with fewer than 3 vertices or an index out of range raise
``UvRemapError`` (a ``ValueError``) - never a default slot or a clamp of bad data.
"""

from __future__ import annotations

import math


class UvRemapError(ValueError):
    """Input that cannot be remapped into an atlas slot; nothing is guessed."""


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def check_rect(rect) -> tuple[float, float, float, float]:
    """Return a slot rect [u0, v0, u1, v1] as floats or raise: four finite numbers, positive area, inside 0..1."""
    if not isinstance(rect, (list, tuple)) or len(rect) != 4 or not all(_finite(x) for x in rect):
        raise UvRemapError(f"slot rect must be four finite numbers u0, v0, u1, v1, got {rect!r}")
    u0, v0, u1, v1 = (float(x) for x in rect)
    if not (u0 < u1 and v0 < v1):
        raise UvRemapError(f"slot rect {list(rect)} has no area (needs u0 < u1 and v0 < v1)")
    if min(u0, v0) < 0.0 or max(u1, v1) > 1.0:
        raise UvRemapError(f"slot rect {list(rect)} leaves the atlas 0..1")
    return u0, v0, u1, v1


def remap_into_rect(t, rect, inset: float = 0.0) -> tuple[float, float]:
    """Map a normalised (s, t) in [0, 1]^2 into rect [u0, v0, u1, v1] (with an optional inset)."""
    s, q = t
    if not (_finite(s) and _finite(q)) or not (0.0 <= s <= 1.0 and 0.0 <= q <= 1.0):
        raise UvRemapError("normalised coordinate must be finite and inside [0, 1]")
    if not _finite(inset) or not (0.0 <= inset < 0.5):
        raise UvRemapError(f"inset must be in [0, 0.5), got {inset!r}")
    u0, v0, u1, v1 = check_rect(rect)
    du, dv = (u1 - u0) * inset, (v1 - v0) * inset
    return (u0 + du + s * (u1 - u0 - 2 * du), v0 + dv + q * (v1 - v0 - 2 * dv))


def box_project_uvs(coords, polygons, normals, face_rects, inset: float = 0.02) -> list[list[tuple[float, float]]]:
    """Per face, the UV of each corner inside the face's slot rect (box projection by the dominant normal axis).

    coords: vertex positions (x, y, z); polygons: vertex index lists; normals: one normal per polygon;
    face_rects: one slot rect per polygon. Returns one list of (u, v) per polygon, in corner order.
    """
    coords = list(coords)
    polygons = list(polygons)
    normals = list(normals)
    face_rects = list(face_rects)
    if not coords or not polygons:
        raise UvRemapError("empty mesh: no vertices or no faces to project")
    if not (len(normals) == len(face_rects) == len(polygons)):
        raise UvRemapError(f"{len(polygons)} faces but {len(normals)} normals and {len(face_rects)} slot rects")
    for i, c in enumerate(coords):
        if len(c) != 3 or not all(_finite(x) for x in c):
            raise UvRemapError(f"vertex {i} is not three finite numbers: {tuple(c)!r}")
    lo = [min(c[i] for c in coords) for i in range(3)]
    span = [max(max(c[i] for c in coords) - lo[i], 1e-9) for i in range(3)]
    out = []
    for f, (poly, n, rect) in enumerate(zip(polygons, normals, face_rects)):
        if rect is None:
            raise UvRemapError(f"face {f} has no atlas slot rect")
        if len(poly) < 3:
            raise UvRemapError(f"face {f} has {len(poly)} vertices (needs >= 3)")
        if len(n) != 3 or not all(_finite(x) for x in n):
            raise UvRemapError(f"face {f} normal is not three finite numbers: {tuple(n)!r}")
        axis = max(range(3), key=lambda i: abs(n[i]))
        a, b = [i for i in range(3) if i != axis]
        face = []
        for vi in poly:
            if not (isinstance(vi, int) and 0 <= vi < len(coords)):
                raise UvRemapError(f"face {f} vertex index {vi!r} is out of range")
            c = coords[vi]
            s = min(1.0, max(0.0, (c[a] - lo[a]) / span[a]))
            q = min(1.0, max(0.0, (c[b] - lo[b]) / span[b]))
            face.append(remap_into_rect((s, q), rect, inset))
        out.append(face)
    return out
