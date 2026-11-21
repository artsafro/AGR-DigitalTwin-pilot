"""Per-polygon UV, UDIM-tile, texel-density and duplicate-vertex checks with SINTEZ AGR Checker 1.6.1 semantics.

Pattern: n/a | new-case: per-polygon SINTEZ 1.6.1 parity of the scene UV checks (#1732, recurrence of #432).

SINTEZ judges every polygon of the imported FBX (an FBX export is triangles, so per triangle); our V008/V009
used to judge per mesh or per edge, so a mirrored, collapsed, tile-crossing or sliver triangle inside an otherwise
good island passed here and failed there (Staropetrovskiy VPM v001-v007, 2026-11-20). This module re-implements
the vendor rules from their documented behaviour (no vendor source copied) on the readback ``face_geometry``
(world ``vertices``, ``polygons`` in loop order, ``polygon_uv`` one pair per corner, ``polygon_material``):

- mirrored (2.5.2.1.4, VPM error): UV signed area opposite to the 3D winding (Newell normal of the polygon);
  a UV-collapsed polygon is never mirrored (orientation undefined).
- unwrapped (4.1.3, recommendation, both profiles): UV collapsed to a point (longest UV edge < 1e-7) or to a
  line (|UV area| < 1e-6 x longest UV edge^2) unless the polygon is as thin in 3D (UV thinness >= 1e-2 x 3D
  thinness, thinness = area / longest edge^2); 3D area < 1e-9 m2 is a degenerate polygon (also 4.1.3).
- out of tile (2.5.2.1.2, VPM error): the tiles of the corners, ``1000 + floor(v) * 10 + ceil(u)``, differ, or
  the tile has no texture (vendor quirk kept: a corner exactly on u = 0 or on an integer v belongs to the
  neighbour tile).
- texel density (2.6.2, VPM error): ``side * sqrt(uv_area / area_3d)`` px/m of each polygon in its own tile
  against 512..1706 px/m [D160]; tiles of <= 256 px (placeholders) are exempt; a zero UV or 3D area gives
  0.01 px/m (below the minimum, never dropped).
- duplicate vertices (2.3.7, NPM): 1..100 doubles at 0.002 m are a recommendation, > 100 an error; the VPM rule
  (2.3.11) only has the > 100 error, which the V004 topology finding already fails.

A SINTEZ recommendation is reported as ``review`` (never ``pass``); a SINTEZ error as ``fail``. Every finding
carries ``data.sintez_req`` / ``data.sintez_group`` so a run can be compared with the checker's report.
Not modelled: the opacity-tile split of mirrored polygons (2.5.2.1.4b recommendation): all mirrored polygons
fail here, stricter than SINTEZ; the 1/256 tile margin (2.5.2.1.5) stays with ``twinqa.uv.face_issue``.
"""
from __future__ import annotations

import math
from collections.abc import Callable

from twinqa.report import Finding

SINTEZ_VERSION = "1.6.1"
UV_THIN_RATIO = 1e-6
UV_POINT_EPS = 1e-7
GEO_EPS = 1e-9
UV_GEO_SLACK = 1e-2
DEGENERATE_DENSITY = 0.01  # px/m the checker gives a polygon with zero UV or 3D area
PLACEHOLDER_MAX_PX = 256
VPM_TEXEL_PX_PER_M = (512, 1706)
DOUBLES_DISTANCE_M = 0.002
DOUBLES_ERROR_ABOVE = 100
SAMPLE = 20  # polygon indices kept per mesh in the finding data


def sintez_tile(u: float, v: float) -> int:
    """UDIM number of one UV point as SINTEZ 1.6.1 computes it (u = 0.0 gives tile 1000)."""
    return 1000 + math.floor(v) * 10 + math.ceil(u)


def _finite_pairs(points, dim: int, label: str) -> list[tuple[float, ...]]:
    out = []
    for point in points:
        if isinstance(point, (str, bytes)):
            raise ValueError(f"partial {label}")
        try:
            values = tuple(point)
        except TypeError:
            raise ValueError(f"partial {label}") from None
        if len(values) != dim or any(isinstance(c, bool) or not isinstance(c, (int, float)) or not math.isfinite(c)
                                     for c in values):
            raise ValueError(f"non-finite or partial {label} {point!r}")
        out.append(tuple(float(c) for c in values))
    return out


def _indexed_surfaces(meshes):
    if not isinstance(meshes, list) or not meshes:
        raise ValueError("expected nonempty surface mesh inventory")
    result = {}
    for mesh in meshes:
        name = mesh.get("name") if isinstance(mesh, dict) else None
        if not isinstance(name, str) or not name.strip() or name in result:
            raise ValueError(f"missing or duplicated mesh identity: {name!r}")
        g = mesh.get("face_geometry")
        if not isinstance(g, dict):
            raise ValueError(f"{name}: missing face_geometry")
        vertices, faces, uv, materials = (g.get(k) for k in
                                          ("vertices", "polygons", "polygon_uv", "polygon_material"))
        if not (isinstance(vertices, list) and vertices and isinstance(faces, list) and faces
                and isinstance(uv, list) and isinstance(materials, list)
                and len(faces) == len(uv) == len(materials)):
            raise ValueError(f"{name}: incomplete surface arrays")
        xyz = _finite_pairs(vertices, 3, f"{name} XYZ")
        loops = []
        for i, (face, chart, material) in enumerate(zip(faces, uv, materials, strict=True)):
            if not isinstance(face, list) or len(face) != 3 or any(
                type(j) is not int or not 0 <= j < len(xyz) for j in face
            ) or len(set(face)) != 3:
                raise ValueError(f"{name}: invalid triangle {i}")
            if not isinstance(material, str) or not material.strip():
                raise ValueError(f"{name}: unmapped material on triangle {i}: {material!r}")
            if not isinstance(chart, list) or len(chart) != 3 or not all(isinstance(p, list) for p in chart):
                raise ValueError(f"{name}: incomplete loop UV on triangle {i}")
            loops.append(_finite_pairs(chart, 2, f"{name} triangle {i} UV"))
        result[name] = xyz, faces, loops, materials
    return result


def indexed_uv_drift(before: list[dict], after: list[dict]) -> dict:
    """Compare exported surface triangles in a proven, unchanged index frame (#1744).

    Exact-zero is intentional. No fuzzy matching, wrapping, dropped faces, or remeshing.
    Caller must bind complete fresh readbacks to the archives and verify the texture bytes
    and bindings separately. With unchanged maps, zero in both measures preserves the
    affine UV-to-world registration on every triangle, including baked joint patterns.
    """
    left, right = _indexed_surfaces(before), _indexed_surfaces(after)
    if left.keys() != right.keys():
        raise ValueError(f"unmatched surface meshes: {sorted(left.keys() ^ right.keys())}")
    corners, max_uv, max_world = 0, 0.0, 0.0
    for name, (xyz, faces, uv, materials) in left.items():
        other_xyz, other_faces, other_uv, other_mat = right[name]
        if len(xyz) != len(other_xyz) or faces != other_faces or materials != other_mat:
            raise ValueError(f"{name}: changed index topology or material assignment")
        max_world = max(max_world, max(math.dist(a, b) for a, b in zip(xyz, other_xyz, strict=True)))
        for face, other_face in zip(uv, other_uv, strict=True):
            max_uv = max(max_uv, max(math.dist(a, b) for a, b in zip(face, other_face, strict=True)))
            corners += len(face)
    if not math.isfinite(max_uv) or not math.isfinite(max_world):
        raise ValueError("non-finite displacement")
    return {"meshes": len(left), "corners": corners, "max_uv": max_uv, "max_world_m": max_world}


def _newell(xyz) -> tuple[float, float, float]:
    gx = gy = gz = 0.0
    px, py, pz = xyz[-1]
    for cx, cy, cz in xyz:
        gx += (py - cy) * (pz + cz)
        gy += (pz - cz) * (px + cx)
        gz += (px - cx) * (py + cy)
        px, py, pz = cx, cy, cz
    return gx, gy, gz


def area_3d(xyz) -> float:
    gx, gy, gz = _newell(xyz)
    return 0.5 * math.sqrt(gx * gx + gy * gy + gz * gz)


def _uv_area2_and_edge2(uv) -> tuple[float, float]:
    area2, max_edge2 = 0.0, 0.0
    pu, pv = uv[-1]
    for cu, cv in uv:
        area2 += pu * cv - pv * cu
        e2 = (cu - pu) ** 2 + (cv - pv) ** 2
        max_edge2 = max(max_edge2, e2)
        pu, pv = cu, cv
    return area2, max_edge2


def _max_edge2_3d(xyz) -> float:
    best = 0.0
    prev = xyz[-1]
    for cur in xyz:
        best = max(best, sum((a - b) ** 2 for a, b in zip(cur, prev)))
        prev = cur
    return best


def polygon_uv_issues(xyz, uv, want_flipped: bool = True) -> set[str]:
    """Subset of {'mirrored', 'uv_zero', 'geo_zero'} for one polygon (SINTEZ uv_face_errors semantics)."""
    xyz = _finite_pairs(xyz, 3, "world coordinate")
    uv = _finite_pairs(uv, 2, "UV coordinate")
    if len(xyz) < 3 or len(uv) != len(xyz):
        raise ValueError(f"partial polygon: {len(xyz)} corners, {len(uv)} UV")
    issues = set()
    area = area_3d(xyz)
    if area < GEO_EPS:
        issues.add("geo_zero")
    area2, max_edge2 = _uv_area2_and_edge2(uv)
    uv_area = abs(area2) * 0.5
    if max_edge2 < UV_POINT_EPS ** 2 or uv_area < UV_THIN_RATIO * max_edge2:
        if max_edge2 >= UV_POINT_EPS ** 2:
            geo_edge2 = _max_edge2_3d(xyz)
            if geo_edge2 > 0.0 and uv_area / max_edge2 >= (area / geo_edge2) * UV_GEO_SLACK:
                return issues  # as thin as the polygon itself: an honest unwrap, orientation undefined
        issues.add("uv_zero")
    elif want_flipped:
        gx, gy, gz = _newell(xyz)
        orient = gx * gx + gy * gy + gz * gz  # Newell normal projected on itself: the 3D winding sign is +
        if orient and area2 < 0:
            issues.add("mirrored")
    return issues


def polygon_density(xyz, uv, side: float) -> float:
    """Texel density of one polygon in px/m: side * sqrt(uv_area / area_3d); 0.01 when either area is 0."""
    xyz = _finite_pairs(xyz, 3, "world coordinate")
    uv = _finite_pairs(uv, 2, "UV coordinate")
    if isinstance(side, bool) or not isinstance(side, (int, float)) or not math.isfinite(side) or side <= 0:
        raise ValueError(f"invalid texture side {side!r}")
    gm = area_3d(xyz)
    uv_area = abs(_uv_area2_and_edge2(uv)[0]) * 0.5
    if gm > 0 and uv_area > 0:
        return side * math.sqrt(uv_area) / math.sqrt(gm)
    return DEGENERATE_DENSITY


def _polygons(mesh: dict):
    """(index, xyz, uv, material) per polygon; ValueError naming the mesh on partial geometry."""
    name = mesh.get("name", "<unnamed mesh>")
    shape = mesh.get("face_geometry")
    if not isinstance(shape, dict):
        raise LookupError(f"{name}: no face_geometry")
    vertices, polygons, polygon_uv = shape.get("vertices"), shape.get("polygons"), shape.get("polygon_uv")
    if polygon_uv is None:
        raise LookupError(f"{name}: no polygon_uv")
    if not isinstance(vertices, list) or not isinstance(polygons, list) or not isinstance(polygon_uv, list) \
            or len(polygon_uv) != len(polygons):
        raise ValueError(f"partial UV geometry on {name}: polygon_uv does not match polygons")
    materials = shape.get("polygon_material") or []
    for index, (polygon, uv) in enumerate(zip(polygons, polygon_uv)):
        try:
            xyz = [vertices[i] for i in polygon]
        except (IndexError, TypeError) as exc:
            raise ValueError(f"partial UV geometry on {name}: polygon {index} index") from exc
        if not isinstance(uv, list) or len(uv) != len(xyz):
            raise ValueError(f"partial UV geometry on {name}: polygon {index} has {len(xyz)} corners")
        yield index, xyz, uv, materials[index] if index < len(materials) else None


def _sf(status, name, observed, expected, pages, src, req, group, severity, data=None, **numbers) -> Finding:
    payload = {"sintez_req": req, "sintez_group": group, "sintez_severity": severity,
               "sintez_version": SINTEZ_VERSION}
    payload.update(data or {})
    return Finding(name, status, f"{src}: {observed}", expected, list(pages), f"sintez_uv {SINTEZ_VERSION}",
                   [], numbers.get("measured"), numbers.get("threshold"), numbers.get("margin"), payload)


def _scan(meshes: list[dict], want_flipped: bool, side_of: Callable | None, texel: tuple[int, int] | None,
          untextured: tuple[str, ...] = ()):
    """One pass over every polygon; counts and sampled indices per mesh and per issue."""
    hits = {key: {} for key in ("mirrored", "uv_zero", "geo_zero", "out_of_tile", "td_less", "td_greater")}
    blocked, polygons, measured, exempt = [], 0, 0, 0
    worst = {"less": None, "greater": None}

    def add(key, name, index):
        bucket = hits[key].setdefault(name, [0, []])
        bucket[0] += 1
        if len(bucket[1]) < SAMPLE:
            bucket[1].append(index)

    for mesh in meshes:
        name = mesh.get("name", "<unnamed mesh>")
        try:
            for index, xyz, uv, material in _polygons(mesh):
                polygons += 1
                for issue in polygon_uv_issues(xyz, uv, want_flipped):
                    add(issue, name, index)
                if not want_flipped or name.endswith(untextured):
                    continue  # NPM (single atlas, no UDIM) or glass (no texture maps)
                corners = {sintez_tile(u, v) for u, v in uv}
                if len(corners) != 1:
                    add("out_of_tile", name, index)
                    continue
                if side_of is None:
                    continue  # tile textures unknown: coverage and density stay not_run
                tile = next(iter(corners))
                side = side_of(tile, material)
                if side is None:
                    add("out_of_tile", name, index)  # SINTEZ: a tile without a texture counts as outside
                    continue
                if texel is None:
                    continue
                if side <= PLACEHOLDER_MAX_PX:
                    exempt += 1
                    continue
                density = polygon_density(xyz, uv, side)
                measured += 1
                if density < texel[0]:
                    add("td_less", name, index)
                    if worst["less"] is None or density < worst["less"][0]:
                        worst["less"] = (density, f"{name} polygon {index}, tile {tile}")
                elif density > texel[1]:
                    add("td_greater", name, index)
                    if worst["greater"] is None or density > worst["greater"][0]:
                        worst["greater"] = (density, f"{name} polygon {index}, tile {tile}")
        except LookupError as exc:
            blocked.append(str(exc).strip("'\""))
        except ValueError as exc:
            raise ValueError(str(exc) if name in str(exc) else f"{name}: {exc}") from exc
    return hits, blocked, polygons, measured, exempt, worst


def _counts(bucket: dict) -> dict:
    return {name: count for name, (count, _) in bucket.items()}


def _faces(bucket: dict) -> dict:
    return {name: faces for name, (_, faces) in bucket.items()}


def _issue_finding(hits, keys, name, expected, pages, src, req, group, severity, bad_status, blocked):
    merged = {}
    for key in keys:
        for mesh, (count, faces) in hits[key].items():
            entry = merged.setdefault(mesh, [0, []])
            entry[0] += count
            entry[1].extend(faces[:SAMPLE - len(entry[1])])
    data = {"counts": _counts(merged), "faces": _faces(merged), "per_issue": {k: _counts(hits[k]) for k in keys}}
    if merged:
        observed = ", ".join(f"{mesh}: {count} polygon(s)" for mesh, (count, _) in list(merged.items())[:5])
        return _sf(bad_status, name, observed, expected, pages, src, req, group, severity, data,
                   measured=sum(c for c, _ in merged.values()), threshold=0)
    if blocked:
        return _sf("not_run", name, f"no per-polygon UV in readback: {blocked[:5]}", expected, pages, src, req,
                   group, severity, data)
    return _sf("pass", name, "none", expected, pages, src, req, group, severity, data, measured=0, threshold=0)


def uv_findings(meshes: list[dict], kind: str, src: str, side_of: Callable | None = None,
                untextured: tuple[str, ...] = ()) -> dict[str, list[Finding]]:
    """{stage: findings} for the non-UCX render meshes of one FBX.

    VPM: V008 mirrored (fail), out of tile (fail), unwrapped (review); V009 per-polygon density (fail).
    ``side_of(tile, material) -> px | None`` is the Diffuse side of the polygon's tile; None (no archive
    textures) leaves out-of-tile and density not_run; meshes ending in ``untextured`` (glass: no texture maps,
    reg 2.4.2) skip both. NPM: V004 unwrapped (review).
    A malformed polygon (partial or non-finite) fails every finding naming the mesh.
    """
    render = [m for m in meshes if "ucx" not in m.get("name", "").lower()]
    vpm = kind == "vpm"
    pages_uv, pages_td = [31], [31, 32]
    unwrapped_expected = ("no polygon with UV collapsed to a point/line or zero 3D area "
                          "(SINTEZ 4.1.3 recommendation; fix it)")
    try:
        hits, blocked, polygons, measured, exempt, worst = _scan(
            render, vpm, side_of if vpm else None, VPM_TEXEL_PX_PER_M if vpm else None, tuple(untextured))
    except ValueError as exc:
        names = ["unwrapped UV polygons"] + (["mirrored UV polygons", "UV outside UDIM tile"] if vpm else [])
        out = {("V008" if vpm else "V004"): [
            _sf("fail", n, str(exc), "finite, complete per-polygon UV", pages_uv, src, "-", "-", "error")
            for n in names]}
        if vpm:
            out["V009"] = [_sf("fail", "texel density per polygon", str(exc), "finite, complete per-polygon UV",
                               pages_td, src, "2.6.2", "hp_texel", "error")]
        return out
    if not render:
        blocked = ["no render mesh"]
    unwrapped = _issue_finding(hits, ("uv_zero", "geo_zero"), "unwrapped UV polygons", unwrapped_expected,
                               pages_uv if vpm else [8], src, "4.1.3", "hp_uv" if vpm else "lp_uv",
                               "recommendation", "review", blocked)
    if not vpm:
        return {"V004": [unwrapped]}
    mirrored = _issue_finding(hits, ("mirrored",), "mirrored UV polygons",
                              "no polygon whose UV winding is opposite to its 3D winding (SINTEZ 2.5.2.1.4)",
                              pages_uv, src, "2.5.2.1.4", "hp_uv", "error", "fail", blocked)
    no_side = blocked + (["no archive Diffuse sides"] if side_of is None else [])
    out_of_tile = _issue_finding(hits, ("out_of_tile",), "UV outside UDIM tile",
                                 "every polygon inside one textured UDIM tile (SINTEZ 2.5.2.1.2)", pages_uv, src,
                                 "2.5.2.1.2", "hp_texel", "error", "fail", no_side)
    lo, hi = VPM_TEXEL_PX_PER_M
    expected_td = f"every polygon {lo}..{hi} px/m in its own tile (SINTEZ 2.6.2, [D160]; <= 256 px tiles exempt)"
    data = {"per_issue": {"less": _counts(hits["td_less"]), "greater": _counts(hits["td_greater"])},
            "faces": {"less": _faces(hits["td_less"]), "greater": _faces(hits["td_greater"])},
            "measured_polygons": measured, "placeholder_polygons": exempt, "polygons": polygons}
    n_less = sum(_counts(hits["td_less"]).values())
    n_greater = sum(_counts(hits["td_greater"]).values())
    if n_less or n_greater:
        parts = []
        if worst["less"]:
            parts.append(f"{n_less} polygon(s) < {lo} px/m (min {worst['less'][0]:.6g} at {worst['less'][1]})")
        if worst["greater"]:
            parts.append(f"{n_greater} polygon(s) > {hi} px/m (max {worst['greater'][0]:.6g} at "
                         f"{worst['greater'][1]})")
        density = _sf("fail", "texel density per polygon", "; ".join(parts), expected_td, pages_td, src, "2.6.2",
                      "hp_texel", "error", data, measured=n_less + n_greater, threshold=0)
    elif no_side or not measured and not exempt:
        reason = no_side or ["no polygon inside a textured tile"]
        density = _sf("not_run", "texel density per polygon", f"not measured: {reason[:5]}", expected_td, pages_td,
                      src, "2.6.2", "hp_texel", "error", data)
    else:
        density = _sf("pass", "texel density per polygon", f"{measured} polygon(s) in band, {exempt} on placeholder "
                      "tiles", expected_td, pages_td, src, "2.6.2", "hp_texel", "error", data, measured=0,
                      threshold=0)
    return {"V008": [mirrored, out_of_tile, unwrapped], "V009": [density]}


def duplicate_vertex_finding(meshes: list[dict], src: str) -> Finding:
    """NPM (SINTEZ 2.3.7): 1..100 doubles at 0.002 m in a mesh = review (recommendation), > 100 = fail.

    Reads ``topology.duplicate_vertices`` (vertices minus 0.002 m clusters); a mesh without it, or counted at
    another tolerance, is not_run naming the mesh.
    """
    expected = (f"0 duplicate vertices at {DOUBLES_DISTANCE_M} m per mesh (SINTEZ 2.3.7: 1..{DOUBLES_ERROR_ABOVE} "
                f"recommendation, > {DOUBLES_ERROR_ABOVE} error)")
    blocked, recommend, error = [], {}, {}
    for mesh in meshes:
        name = mesh.get("name", "<unnamed mesh>")
        topo = mesh.get("topology")
        count = topo.get("duplicate_vertices") if isinstance(topo, dict) else None
        tol = topo.get("tol_m", DOUBLES_DISTANCE_M) if isinstance(topo, dict) else None
        if type(count) is not int or count < 0 or not isinstance(tol, (int, float)) \
                or abs(float(tol) - DOUBLES_DISTANCE_M) > 1e-12:
            blocked.append(name)
        elif count > DOUBLES_ERROR_ABOVE:
            error[name] = count
        elif count > 0:
            recommend[name] = count
    data = {"sintez_req": "2.3.7", "sintez_group": "lp_duplicates", "sintez_version": SINTEZ_VERSION,
            "recommendation": recommend, "error": error, "blocked": blocked}
    hits = {**recommend, **error}
    if error or recommend:
        status = "fail" if error else "review"
        data["sintez_severity"] = "error" if error else "recommendation"
        observed = ", ".join(f"{n}: {c} duplicate vertices" for n, c in list(hits.items())[:5])
        return Finding("duplicate vertices", status, f"{src}: {observed}", expected, [8], f"sintez_uv {SINTEZ_VERSION}",
                       [], sum(hits.values()), 0, None, data)
    if blocked or not meshes:
        return Finding("duplicate vertices", "not_run", f"{src}: no duplicate count for {blocked[:5] or 'any mesh'}",
                       expected, [8], f"sintez_uv {SINTEZ_VERSION}", [], None, None, None, data)
    return Finding("duplicate vertices", "pass", f"{src}: none", expected, [8], f"sintez_uv {SINTEZ_VERSION}", [],
                   0, 0, None, data)
