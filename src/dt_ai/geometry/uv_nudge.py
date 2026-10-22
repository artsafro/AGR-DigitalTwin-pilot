"""Integer-tile UV nudge for repeating materials (issue #549).

Pattern: new-case: move UV islands of tiled materials by whole pattern periods.

Each UV island (faces connected through shared UV vertices) of a repeating
material is shifted by an integer number of pattern periods per axis, so the
island's bounding-box centre lands as close as possible to the centre of the
target UDIM tile while ``coord mod period`` (the phase of the tiled texture)
is unchanged (docs/domain/uv-textures.md, "Repeat shift"). Islands of
non-repeating materials are returned untouched.

Logic follows the team script ``GridUVLayout22.ms`` (layoutFacesOnGrid,
udimTileOffset): shift step ``1/stepU`` = the period here, rounding
``floor(x + 0.5)``. Differences: per island instead of per cut polygon, the
period comes per material, and no edges are cut (unwrapping and packing are
out of scope). Pure Python, no bpy.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from dt_ai.geometry.uv import tile_origin


@dataclass(frozen=True)
class NudgeResult:
    uv: list[tuple[float, float]]
    islands: list[dict] = field(default_factory=list)


def _period(material, value):
    if value is None:
        return None
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ValueError(f"material {material!r}: period must be (pu, pv) or None, got {value!r}")
    for p in value:
        if isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p) or p <= 0:
            raise ValueError(f"material {material!r}: period must be finite and > 0, got {value!r}")
    return float(value[0]), float(value[1])


def _uv_points(uv):
    points = []
    for i, point in enumerate(uv):
        try:
            u, v = point
        except (TypeError, ValueError):
            raise ValueError(f"partial UV vertex {i}: {point!r}") from None
        if isinstance(point, (str, bytes)):
            raise ValueError(f"partial UV vertex {i}: {point!r}")
        for c in (u, v):
            if isinstance(c, bool) or not isinstance(c, (int, float)) or not math.isfinite(c):
                raise ValueError(f"UV vertex {i} is not finite: {point!r}")
        points.append((u, v))
    return points


def _islands(faces, n):
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for face in faces:
        root = find(face[0])
        for i in face[1:]:
            other = find(i)
            if other != root:
                parent[other] = root
    groups: dict[int, list[int]] = {}
    for f, face in enumerate(faces):
        groups.setdefault(find(face[0]), []).append(f)
    return list(groups.values())


def nudge_repeating_islands(uv, faces, face_materials, periods, *, target_tile: int = 1001) -> NudgeResult:
    """Shift islands of repeating materials by whole periods towards ``target_tile``.

    ``uv``: UV vertices ``(u, v)``; ``faces``: UV-vertex index lists (>= 3 distinct);
    ``face_materials``: material id per face; ``periods``: every used material id ->
    ``(pu, pv)`` pattern period in UV units (``1 / repeats per tile``) or ``None``
    for a non-repeating material. An unmapped material, an island mixing
    repeating and non-repeating materials or different periods, a non-finite
    coordinate and an empty mesh are errors. The input is not modified.
    """
    tu, tv = tile_origin(target_tile)
    if not faces or not uv:
        raise ValueError("empty mesh: no faces or no UV vertices")
    if len(face_materials) != len(faces):
        raise ValueError(f"material list has {len(face_materials)} entries for {len(faces)} faces")
    points = _uv_points(uv)
    n = len(points)
    face_lists = []
    for f, face in enumerate(faces):
        face = list(face)
        for i in face:
            if isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < n:
                raise ValueError(f"face {f}: UV index {i!r} out of range 0..{n - 1}")
        if len(set(face)) < 3:
            raise ValueError(f"face {f}: needs >= 3 distinct UV vertices, got {face}")
        face_lists.append(face)
    resolved = {}
    for m in dict.fromkeys(face_materials):
        if m not in periods:
            raise ValueError(f"material {m!r} has no period entry (repeating or None)")
        resolved[m] = _period(m, periods[m])

    out = list(points)
    report = []
    for island in _islands(face_lists, n):
        mats = sorted(dict.fromkeys(face_materials[f] for f in island), key=str)
        island_periods = {resolved[m] for m in mats}
        if None in island_periods and len(island_periods) > 1:
            raise ValueError(f"island of faces {island} mixes repeating and non-repeating materials {mats}")
        if len(island_periods) > 1:
            raise ValueError(f"island of faces {island} mixes materials {mats} with different periods")
        period = island_periods.pop()
        entry = {"faces": island, "materials": mats, "target_tile": target_tile, "period": period}
        if period is None:
            entry.update(steps=(0, 0), shift=(0.0, 0.0), reason="non-repeating")
            report.append(entry)
            continue
        verts = sorted({i for f in island for i in face_lists[f]})
        us = [points[i][0] for i in verts]
        vs = [points[i][1] for i in verts]
        cu, cv = (min(us) + max(us)) / 2, (min(vs) + max(vs)) / 2
        pu, pv = period
        ku = math.floor((tu + 0.5 - cu) / pu + 0.5)
        kv = math.floor((tv + 0.5 - cv) / pv + 0.5)
        du, dv = ku * pu, kv * pv
        for i in verts:
            out[i] = (points[i][0] + du, points[i][1] + dv)
        entry.update(steps=(ku, kv), shift=(du, dv), reason="repeating")
        report.append(entry)
    return NudgeResult(uv=out, islands=report)
