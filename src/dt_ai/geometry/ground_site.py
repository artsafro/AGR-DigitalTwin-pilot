"""Ground for any site in the D293 order: sources -> boundary / zero -> flat Ground -> triangles / seams / insets
-> textures by ID (UDIM = ID) -> projection onto the relief -> texture fix + skirt -> UCX (#1406).

Pattern: n/a | new-case: site-independent Ground orchestration over ground_cake (one owner for every site, #1406).

Program choice per step (one line why):
- sources / boundary / covers / relief points: ezdxf (DXF adapter below) - reads hatches, bgcolor and native Z
  without a DCC; any other reader (3ds Max / AGR Tools) passes the same plain polygons to ``build_site``.
- flat Ground, triangles, seams, insets, projection, skirt: ``dt_ai.geometry.ground_cake`` (shapely + numpy) -
  the existing layered-cake core; pure Python, so the same call works from the agent CLI and from Max Python.
- textures by ID: per-face UV shift by ``ID - 1`` tiles (UDIM 1000 + ID) - no DCC needed for a planar UV.
- UCX: not built here; owner is compaction 7 (#1404, ``ucx10_core.py`` [D225]); the report says ``not_run``.

The core never invents data: missing zero, unmapped covers, hatches without a background colour (unless the
site spec states the colour), relief misses and non-sequential IDs are errors naming the item.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from shapely.affinity import translate
from shapely.geometry import Polygon, box

from dt_ai.core.heights import height_values
from dt_ai.geometry import ground_cake as gc

STAGES = ("sources", "zero", "surfaces", "quads", "textures", "relief", "skirt", "ucx")
UCX_OWNER = "#1404 compaction 7 (ucx10_core.py, D225)"
MAX_ID = 10  # UDIM = 1000 + ID in the first row 1001-1010; slot "IDnn_" parsing assumes two digits


@dataclass
class Cover:
    id: int
    name: str
    polygons: list
    colour: tuple
    colour_source: str  # "hatch-bgcolor" | "spec"
    sources: list = field(default_factory=list)


@dataclass
class SiteResult:
    flat: gc.Mesh
    mesh: gc.Mesh
    slots: list
    report: dict


class SnapSampler(gc.ReliefSampler):
    """Relief sampler that accepts a vertex at most ``margin`` (the noding snap) outside the TIN: it takes the plane
    of the nearest TIN triangle. Snap rounding moves outlines <= snap / sqrt(2), so a vertex of a boundary that lies
    inside the TIN can land just outside it; anything farther is a miss (no extrapolation). Every use is counted."""

    def __init__(self, tin, margin: float):
        super().__init__(tin)
        self.margin = margin
        self.margin_uses: dict = {}

    def sample(self, xy, eps: float = 1e-7):
        import shapely
        xy = np.asarray(xy, float).reshape(-1, 2)
        z, hit = super().sample(xy, eps)
        for i in np.flatnonzero(~hit):
            p = shapely.Point(xy[i])
            t = int(self.tree.nearest(p))
            dist = self.polys[t].distance(p)
            if dist <= self.margin:
                z[i] = self.planes[t] @ [xy[i, 0], xy[i, 1], 1.0]
                hit[i] = True
                self.margin_uses[tuple(np.round(xy[i], 6))] = float(dist)
        return z, hit


def _finite(name: str, value, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number, got {value!r}")
    if positive and value <= 0:
        raise ValueError(f"{name} must be > 0, got {value!r}")
    return float(value)


def check_covers(covers: list[Cover], base_id: int) -> None:
    """IDs are 1..N without gaps (UDIM 1001.. sequential, GND-09); names unique; colour RGB 0..255."""
    if not covers:
        raise ValueError("no covers: the flat Ground needs at least one cover (hatch -> ID)")
    ids = sorted(c.id for c in covers)
    if ids != list(range(1, len(covers) + 1)):
        raise ValueError(f"cover IDs must be 1..{len(covers)} without gaps or repeats, got {ids}")
    if ids[-1] > MAX_ID:
        raise ValueError(f"cover ID {ids[-1]} > {MAX_ID}: ID {MAX_ID + 1} and above leave the first UDIM row "
                         f"(1001-{1000 + MAX_ID}); split the site or merge covers")
    names = [c.name for c in covers]
    if len(set(names)) != len(names):
        raise ValueError(f"duplicate cover names {sorted(n for n in set(names) if names.count(n) > 1)}")
    for c in covers:
        if not c.name or not all(ch.isalnum() or ch == "_" for ch in c.name):
            raise ValueError(f"cover name {c.name!r}: Latin letters, digits and _ only (GND-11)")
        if len(c.colour) != 3 or any(isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 255
                                     for v in c.colour):
            raise ValueError(f"cover {c.id} {c.name}: colour must be three integers 0..255, got {c.colour!r}")
        if not c.polygons:
            raise ValueError(f"cover {c.id} {c.name}: no polygons")
    if base_id not in ids:
        raise ValueError(f"base cover ID {base_id} is not one of the cover IDs {ids}")


def slot_name(cover: Cover) -> str:
    return f"ID{cover.id:02d}_{cover.name}"


def relief_margin(snap, extension):
    """Fail-closed explicit bound for a user-authorized nearest-TIN-plane continuation."""
    snap = _finite("snap", snap, positive=True)
    if extension is None:
        return snap
    if (not isinstance(extension, dict) or set(extension) != {"max_m", "reason"}
            or not isinstance(extension.get("reason"), str) or not extension["reason"].strip()):
        raise ValueError("relief_extension needs exactly max_m and a non-empty reason")
    bound = _finite("relief_extension max_m", extension["max_m"], positive=True)
    if bound <= snap:
        raise ValueError("relief_extension max_m must exceed snap")
    return bound


def build_site(boundary: Polygon, covers: list[Cover], base_id: int, relief_xyz, project_zero_m: float, *,
               origin_xy=None, cell: float = 4.0, chord: float = 0.02, step: float = 0.006, snap: float = 0.001,
               relief_tol: float = 0.01, skirt_m: float = 1.0, tex_px: int = 4096,
               footprint_min_area: float = 1000.0, crop_box=None, unhatched: dict | None = None,
               relief_extension: dict | None = None) -> SiteResult:
    """Build one site's Ground in the D293 order and return flat + projected meshes and the stage report.

    ``unhatched``: boundary area under no hatch (smaller than ``footprint_min_area``) lands on the base cover only
    with ``{"cover_id": base_id, "reason": ...}`` (e.g. D283 / D284); without it any such area is a finding.

    Coordinates: XY local = source XY - ``origin_xy``; Z local = source Z - ``project_zero_m`` (FBX Z 0 = ±0.000).
    """
    report: dict = {"order": list(STAGES), "passed": False, "stages": {}}
    zero = _finite("project_zero_m", project_zero_m)
    height_values(zero, 0.0, 0.0)  # same validation as the project zero command (D279)
    for name, value in (("cell", cell), ("step", step), ("relief_tol", relief_tol)):
        _finite(name, value, positive=True)
    skirt_m = _finite("skirt_m", skirt_m)
    if skirt_m < 1.0:
        raise ValueError(f"skirt drop {skirt_m} m < 1 m (GND-03, D251)")
    if boundary is None or boundary.is_empty or not boundary.is_valid or boundary.geom_type != "Polygon":
        raise ValueError("boundary must be one valid non-empty polygon")
    check_covers(covers, base_id)
    if crop_box is not None:
        if len(crop_box) != 4 or not all(math.isfinite(_finite("crop_box", v)) for v in crop_box):
            raise ValueError("crop_box must be [xmin, ymin, xmax, ymax]")
        clipped = boundary.intersection(box(*crop_box))
        if clipped.is_empty or clipped.geom_type != "Polygon":
            raise ValueError(f"crop_box {crop_box} does not give one polygon of the boundary")
        boundary = clipped
    if origin_xy is None:
        minx, miny, _, _ = boundary.bounds
        origin_xy = (math.floor(minx), math.floor(miny))
    ox, oy = (_finite("origin_xy", v) for v in origin_xy)
    local = lambda g: translate(g, xoff=-ox, yoff=-oy)  # noqa: E731
    report["stages"]["sources"] = {"origin_xy_m": [ox, oy], "boundary_m2": round(boundary.area, 6),
                                   "fragment": crop_box is not None, "crop_box": crop_box,
                                   "covers": len(covers), "relief_points": len(relief_xyz)}

    # zero: relief points and project zero -> local Z
    pts = []
    for p in relief_xyz:
        x, y, z = (_finite("relief point", v) for v in p)
        pts.append((x - ox, y - oy, z - zero))
    tin = gc.build_tin(pts)
    if tin.contradictory:
        raise ValueError(f"{len(tin.contradictory)} relief points with the same XY and other Z, first "
                         f"{tin.contradictory[0]}: resolve the source marks, no average")
    zabs = tin.pts[:, 2] + zero
    report["stages"]["zero"] = {"project_zero_m": zero, "h_relief": round(zero, 2), "fbx_z_of_zero_m": 0.0,
                                "relief_abs_range_m": [float(zabs.min()), float(zabs.max())],
                                "tin_points": int(len(tin.pts)), "tin_triangles": int(len(tin.tris)),
                                "merged_duplicates": tin.merged}

    # surfaces: covers -> IDs (ID colour = hatch background colour)
    by_name = {c.name: c for c in covers}
    base = next(c for c in covers if c.id == base_id)
    slots = {c.name: slot_name(c) for c in covers}
    plan = gc.plan_layers(local(boundary), {c.name: [local(p) for p in c.polygons] for c in covers}, base.name,
                          slots, footprint_min_area=footprint_min_area, step=step)
    sliver = float(plan.report.get("slivers_m2", 0.0))
    if unhatched is not None:
        if unhatched.get("cover_id") != base_id or not str(unhatched.get("reason", "")).strip():
            raise ValueError(f"unhatched policy must name the base cover {base_id} and a reason, got {unhatched}")
    report["stages"]["surfaces"] = {"plan": plan.report, "unhatched_m2": sliver,
                                    "unhatched_policy": unhatched, "ids": [
        {"id": c.id, "name": c.name, "slot": slots[c.name], "udim": 1000 + c.id, "colour_rgb": list(c.colour),
         "colour_source": c.colour_source, "sources": c.sources,
         "area_m2": round(sum(p.area for p in c.polygons), 6)} for c in covers]}

    # quads: flat Ground first (no relief), one partition with shared seams and inset layers
    flat = gc.build_flat(plan, cell=cell, chord=chord, origin=(0.0, 0.0), snap=snap)
    _udim_by_id(flat, by_name)
    cov = gc.measure_coverage(flat, plan, tol=snap)
    report["stages"]["quads"] = {"flat_triangles": int(len(flat.faces)), "flat_vertices": int(len(flat.verts)),
                                 "coverage": cov, "flat_z": sorted({float(z) for z in np.unique(flat.verts[:, 2])})}

    # relief: same partition refined by TIN edges where a face misses the relief by > tol, then Z-only lift
    sampler = SnapSampler(tin, relief_margin(snap, relief_extension))
    for stage in ("flat", "refined"):
        if stage == "refined":
            refined = gc.build_flat(plan, cell=cell, chord=chord, origin=(0.0, 0.0), snap=snap, sampler=sampler,
                                    tol=relief_tol)
        verts = flat.verts if stage == "flat" else refined.verts
        _, hit = sampler.sample(verts[:, :2])
        if hit.all():
            continue
        miss = verts[~hit][:5, :2] + [ox, oy]
        raise ValueError(f"{int((~hit).sum())} {stage} Ground vertices outside the relief TIN, first "
                         f"{miss.round(3).tolist()} (no extrapolation: extend the relief source or the crop)")
    mesh, misses = gc.project_z(refined, sampler, step)
    if misses:
        raise ValueError(f"projection missed {len(misses)} vertices")
    _udim_by_id(mesh, by_name)
    kept = _retained(flat.verts[:, :2], mesh.verts[:, :2], snap)
    err = gc.measure_relief_error(mesh, sampler, step, tol=relief_tol)
    report["stages"]["relief"] = {"triangles": int(len(mesh.faces)), "flat_vertices_retained": kept,
                                  "relief_error": err, "uv_unchanged_by_projection": True,
                                  "snap_margin_vertices": len(sampler.margin_uses),
                                  "snap_margin_max_m": max(sampler.margin_uses.values(), default=0.0)}

    if relief_extension is not None:
        continued = {p: d for p, d in sampler.margin_uses.items() if d > snap}
        report["stages"]["relief"]["continuation"] = {
            **relief_extension, "sampled_points": len(continued),
            "max_used_m": max(continued.values(), default=0.0),
            "samples": [{"local_xy": list(p), "distance_m": d} for p, d in sorted(continued.items())],
            "status": "assumed_nearest_plane", "not_source_elevations": True}

    # texture fix + skirt (outer edges of the base layer only, holes included as their own rings, D251)
    mesh = gc.add_skirt(mesh, skirt_m, slot="Skirt")
    _skirt_ids_and_uv(mesh, by_name, slots, cell)
    gaps = skirt_gaps(mesh, skirt_m)
    tiles = gc.uv_tile_report(mesh.uv)
    dens = gc.texel_density(mesh.verts, mesh.faces, mesh.uv, tex_px)
    top = mesh.level >= 0
    report["stages"]["textures"] = {"tiles": tiles, "expected_tiles": [1000 + c.id for c in covers
                                                                        if slots[c.name] in set(mesh.slot)],
                                    "tex_px": tex_px,
                                    "density_px_per_m_top": [float(np.nanmin(dens[top])), float(np.nanmax(dens[top]))]}
    report["stages"]["skirt"] = {"drop_m": skirt_m, "skirt_faces": int((~top).sum()), "skirt_gap_edges": gaps}
    report["stages"]["ucx"] = {"status": "not_run", "owner": UCX_OWNER}
    findings = []
    if tiles["straddling"] or tiles["outside_udim_range"]:
        findings.append(f"UV: {tiles['straddling']} straddling, {tiles['outside_udim_range']} outside UDIM range")
    if sorted(tiles["tiles"]) != sorted(report["stages"]["textures"]["expected_tiles"]):
        findings.append(f"UDIM tiles {tiles['tiles']} != IDs {report['stages']['textures']['expected_tiles']}")
    if sliver > 0 and unhatched is None:
        findings.append(f"unhatched {sliver} m2 has no cover (put on the base only with a stated policy)")
    if gaps:
        findings.append(f"skirt: {len(gaps)} outer edges drop < {skirt_m} m")
    if err.get("over_tol", 0):
        findings.append(f"relief: {err['over_tol']} samples over {relief_tol} m")
    if cov.get("uncovered_beyond_tol_m2", 0) > 1e-6:
        findings.append(f"flat coverage gap {cov['uncovered_beyond_tol_m2']} m2")
    findings.append("UCX not built: " + UCX_OWNER)
    report["findings"] = findings
    report["geometry_status"] = "fail" if len(findings) > 1 else "built"
    out_slots = [slots[c.name] for c in sorted(covers, key=lambda c: c.id)]
    return SiteResult(flat, mesh, out_slots, report)


def _udim_by_id(mesh: gc.Mesh, by_name: dict) -> None:
    """Stacked [0,1]^2 cell UV -> tile of the face's ID: u += ID - 1 (UDIM 1000 + ID)."""
    for i, slot in enumerate(mesh.slot):
        if slot == "Skirt":
            continue
        cid = int(slot[2:4])
        mesh.uv[i, :, 0] = mesh.uv[i, :, 0] - np.floor(mesh.uv[i, :, 0].min() + 1e-9) + (cid - 1)


def _skirt_ids_and_uv(mesh: gc.Mesh, by_name: dict, slots: dict, cell: float) -> None:
    """Texture fix: each skirt quad takes the ID of the base face above it; vertical planar UV in that tile."""
    edge_slot = {}
    for f, lv, s in zip(mesh.faces, mesh.level, mesh.slot):
        if lv == 0:
            for a, b in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
                edge_slot[(min(a, b), max(a, b))] = s
    scale = 1.0 / (cell * math.sqrt(2.0) + 1.0)
    skirt = np.nonzero(mesh.level < 0)[0]
    if len(skirt) % 2:
        raise ValueError("skirt faces are not in quad pairs")
    for i, j in zip(skirt[0::2], skirt[1::2]):
        b, a, la = mesh.faces[i]
        lb = mesh.faces[j][2]
        if mesh.faces[j][0] != b or mesh.faces[j][1] != la:
            raise ValueError(f"skirt faces {i}, {j} are not one quad")
        s = edge_slot[(min(a, b), max(a, b))]
        cid = int(s[2:4])
        length = float(np.linalg.norm(mesh.verts[a, :2] - mesh.verts[b, :2]))
        depth = float(mesh.verts[b, 2] - mesh.verts[lb, 2])
        uv = {b: (0.0, 1.0), a: (length * scale, 1.0), la: (length * scale, 1.0 - depth * scale),
              lb: (0.0, 1.0 - depth * scale)}
        for f in (i, j):
            mesh.slot[f] = s
            for k, v in enumerate(mesh.faces[f]):
                mesh.uv[f, k] = (cid - 1 + uv[v][0], uv[v][1])


def skirt_gaps(mesh: gc.Mesh, drop_m: float, xy_tol: float = 1e-6) -> list:
    """Edge-level skirt check (review r1 P1-2): every outer (single-use) base edge (a, b) needs a skirt quad - two
    skirt triangles (a, b, la) + (b, la, lb) or (a, b, lb) + (a, lb, la) - whose lower vertices la, lb sit at the
    XY of a and b and at least ``drop_m`` below them. An edge without such a quad is a gap with its reason."""
    drop_m = _finite("drop_m", drop_m, positive=True)
    xy_tol = _finite("xy_tol", xy_tol, positive=True)
    if not np.isfinite(mesh.verts).all():
        raise ValueError("skirt vertices must be finite")
    count: dict = {}
    for f, lv in zip(mesh.faces, mesh.level):
        if lv == 0:
            for a, b in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
                count[(min(a, b), max(a, b))] = count.get((min(a, b), max(a, b)), 0) + 1
    tris = {frozenset(int(v) for v in f) for f, lv in zip(mesh.faces, mesh.level) if lv < 0}
    by_edge: dict = {}
    for t in tris:
        for v in t:
            for w in t:
                if v < w:
                    by_edge.setdefault((v, w), []).append(t)
    xy = mesh.verts[:, :2]
    z = mesh.verts[:, 2]

    def below(top, low):
        return low != top and float(np.abs(xy[low] - xy[top]).max()) <= xy_tol

    gaps = []
    for (a, b), n in count.items():
        if n != 1:
            continue
        a, b = int(a), int(b)
        best = None  # (min drop, la, lb) over every quad found on this edge
        for t in by_edge.get((a, b), []):
            (c,) = t - {a, b}
            for top, other in ((a, b), (b, a)):
                if not below(top, c):
                    continue
                # second triangle: (other, c, l_other) with l_other below `other`
                for t2 in by_edge.get((min(other, c), max(other, c)), []):
                    if t2 == t:
                        continue
                    (d,) = t2 - {other, c}
                    if below(other, d):
                        drop = min(float(z[top] - z[c]), float(z[other] - z[d]))
                        if best is None or drop > best[0]:
                            best = (drop, c, d)
        if best is None:
            gaps.append({"edge": [a, b], "reason": "no skirt quad", "drop_m": 0.0})
        elif best[0] < drop_m - 1e-9:
            gaps.append({"edge": [a, b], "reason": f"drop < {drop_m} m", "drop_m": round(best[0], 6)})
    return gaps


def _retained(flat_xy: np.ndarray, xy: np.ndarray, tol: float) -> dict:
    keys = {tuple(k) for k in np.round(xy / tol).astype(np.int64).tolist()}
    fk = np.round(flat_xy / tol).astype(np.int64).tolist()
    lost = [i for i, k in enumerate(fk) if tuple(k) not in keys]
    return {"flat": len(fk), "missing": len(lost)}


# ---------------------------------------------------------------- output (OBJ + JSON) and readback


def write_obj(path: Path, mesh: gc.Mesh, slots: list, prefix: str, origin: str) -> None:
    order = {s: i for i, s in enumerate(slots)}
    lines = [f"# {origin}", f"o {prefix}"]
    lines += [f"v {x:.6f} {y:.6f} {z:.6f}" for x, y, z in mesh.verts]
    vt = 1
    groups = [("ground" if lv == 0 else f"ground_inset{lv}", mesh.level == lv)
              for lv in sorted({int(v) for v in mesh.level if v >= 0})] + [("skirt", mesh.level < 0)]
    for gname, mask in groups:
        lines.append(f"g {gname}")
        idx = sorted(np.nonzero(mask)[0], key=lambda i: (order[mesh.slot[i]], i))
        current = None
        for i in idx:
            if mesh.slot[i] != current:
                current = mesh.slot[i]
                lines.append(f"usemtl M_{prefix.removeprefix('SM_')}_{current}")
            for u, v in mesh.uv[i]:
                lines.append(f"vt {u:.7f} {v:.7f}")
            f = mesh.faces[i] + 1
            lines.append(f"f {f[0]}/{vt} {f[1]}/{vt + 1} {f[2]}/{vt + 2}")
            vt += 3
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def read_obj(path: Path) -> dict:
    """Readback of a written OBJ: vertices, per group Z, per material UDIM tiles, triangle count."""
    verts, uvs, groups, tiles, tris = [], [], {}, {}, 0
    group, mat = None, None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        head, _, rest = line.partition(" ")
        if head == "v":
            verts.append([float(t) for t in rest.split()])
        elif head == "vt":
            uvs.append([float(t) for t in rest.split()])
        elif head == "g":
            group = rest
        elif head == "usemtl":
            mat = rest
        elif head == "f":
            tris += 1
            corners = [c.split("/") for c in rest.split()]
            if len(corners) != 3:
                raise ValueError(f"{path}: non-triangle face {rest!r}")
            for vi, ti in corners:
                groups.setdefault(group, set()).add(int(vi) - 1)
            us = [uvs[int(ti) - 1] for _, ti in corners]
            # UDIM owner: udimtile_core (via ground_cake); a face crossing its tile raises here
            tiles.setdefault(mat, set()).add(gc._udimtile.face_tile(us, strict=True))
    arr = np.array(verts, float)
    for v in arr.ravel():
        if not math.isfinite(v):
            raise ValueError(f"{path}: non-finite vertex value")
    level_of: dict = {}
    for g, ix in groups.items():
        if g != "ground" and not (g or "").startswith("ground_inset"):
            continue
        lv = 0 if g == "ground" else int(g.removeprefix("ground_inset"))
        for i in ix:
            if level_of.setdefault(i, lv) != lv:
                raise ValueError(f"{path}: vertex {i + 1} in ground levels {level_of[i]} and {lv}")
    return {"vertices": len(verts), "triangles": tris,
            "z": {g: [float(arr[sorted(ix), 2].min()), float(arr[sorted(ix), 2].max())] for g, ix in groups.items()},
            "z_values": {g: arr[sorted(ix), 2].tolist() for g, ix in groups.items()},
            "points": [(*arr[i].tolist(), lv) for i, lv in sorted(level_of.items())],
            "tiles": {m: sorted(t) for m, t in tiles.items()}}


def ground_points(back: dict, origin_xy) -> list:
    """Ground-top vertices of a ``read_obj`` result in source XY: ``(x + ox, y + oy, z, level)``."""
    ox, oy = (_finite("origin_xy", v) for v in origin_xy)
    if not back.get("points"):
        raise ValueError("OBJ has no ground group: nothing to check (export the site with `dt ground site`)")
    return [(x + ox, y + oy, z, lv) for x, y, z, lv in back["points"]]


def relief_z_at(relief_xyz, margin: float = 0.001, origin_xy=(0.0, 0.0)):
    """Absolute relief sampler for the project zero check: TIN of the source points (no extrapolation; at most
    ``margin`` outside, the noding snap of ``build_site``). Returns ``f(list of (x, y)) -> list of Z or None``.
    The TIN is built around ``origin_xy`` (as in ``build_site``) so that large source XY stay well conditioned."""
    ox, oy = (_finite("origin_xy", v) for v in origin_xy)
    pts = []
    for p in relief_xyz:
        if len(p) != 3:
            raise ValueError(f"relief point {p!r}: expected (x, y, z)")
        x, y, z = (_finite("relief point", v) for v in p)
        pts.append((x - ox, y - oy, z))
    tin = gc.build_tin(pts)
    if tin.contradictory:
        raise ValueError(f"{len(tin.contradictory)} relief points with the same XY and other Z, first "
                         f"{tin.contradictory[0]}: resolve the source marks, no average")
    sampler = SnapSampler(tin, _finite("margin", margin))

    def at(xy):
        z, hit = sampler.sample(np.asarray(list(xy), float).reshape(-1, 2) - [ox, oy])
        return [float(v) if h else None for v, h in zip(z, hit)]
    return at


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_spec(path: Path) -> dict:
    """Strict JSON: duplicate keys and NaN / Infinity refused."""
    def pairs(rows):
        d = {}
        for k, v in rows:
            if k in d:
                raise ValueError(f"duplicate key {k!r} in {path}")
            d[k] = v
        return d

    def bad(token):
        raise ValueError(f"non-finite JSON value {token} in {path}")
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=bad)


# ---------------------------------------------------------------- DXF adapter (ezdxf)


def hatch_polygon(hatch, chord: float) -> Polygon:
    """Hatch boundary paths -> polygon by symmetric difference of the rings (nesting); invalid ring = error."""
    from ezdxf.path import from_hatch
    result = Polygon()
    for path in from_hatch(hatch):
        pts = [(v.x, v.y) for v in path.flattening(chord)]
        ring = Polygon(pts)
        if len(pts) < 3 or not ring.is_valid:
            raise ValueError(f"hatch {hatch.dxf.handle}: invalid boundary ring (not repaired)")
        result = result.symmetric_difference(ring)
    if result.is_empty:
        raise ValueError(f"hatch {hatch.dxf.handle}: empty region")
    return result


def hatch_colour(hatch, spec_colour=None) -> tuple[tuple, str]:
    """ID colour = hatch background colour (bgcolor), never the pattern line colour; else the spec colour."""
    bg = getattr(hatch, "bgcolor", None)
    if bg is not None:
        rgb = (int(bg[0]), int(bg[1]), int(bg[2]))
        return rgb, "hatch-bgcolor"
    if spec_colour is None:
        raise ValueError(f"hatch {hatch.dxf.handle} has no background colour: state the ID colour in the site spec"
                         " (colour + colour_reason); the pattern line colour is not used (hatch-colours)")
    return tuple(spec_colour), "spec"


def _placed_hatch_paths(doc, hatch, chain, chord):
    """Resolve an outermost-first INSERT chain, then flatten in world units (including MINSERT cells)."""
    from ezdxf.math import Vec3
    from ezdxf.path import from_hatch

    if not isinstance(chain, list):
        raise ValueError(f"hatch {hatch.dxf.handle}: insert_chain must be a list")
    owner = doc.modelspace().block_record_handle
    matrices = []
    for ref in chain:
        if isinstance(ref, str):
            handle, cell = ref, None
        elif isinstance(ref, dict) and set(ref) <= {"handle", "cell"}:
            handle, cell = ref.get("handle"), ref.get("cell")
        else:
            raise ValueError(f"hatch {hatch.dxf.handle}: unsupported INSERT reference {ref!r}")
        ins = doc.entitydb.get(handle) if isinstance(handle, str) else None
        if ins is None or ins.dxftype() != "INSERT":
            raise ValueError(f"INSERT {handle!r}: not an INSERT in the DXF")
        if ins.dxf.owner != owner:
            raise ValueError(f"INSERT {handle}: broken insert_chain owner")
        block = ins.block()
        if block is None:
            raise ValueError(f"INSERT {handle}: missing block {ins.dxf.name}")
        owner = block.block_record_handle
        nr, nc = ins.dxf.row_count, ins.dxf.column_count
        if nr < 1 or nc < 1:
            raise ValueError(f"INSERT {handle}: invalid MINSERT counts {nr}, {nc}")
        if nr > 1 or nc > 1 or cell is not None:
            if (not isinstance(cell, list) or len(cell) != 2
                    or any(type(v) is not int for v in cell)
                    or not (0 <= cell[0] < nr and 0 <= cell[1] < nc)):
                raise ValueError(f"INSERT {handle}: MINSERT requires cell [row, column] within {nr} x {nc}")
        for name in ("xscale", "yscale", "zscale", "rotation", "row_spacing", "column_spacing"):
            _finite(f"INSERT {handle} {name}", ins.dxf.get(name, ins.DXFATTRIBS.get(name).default))
        if abs(ins.dxf.xscale) != abs(ins.dxf.yscale):
            raise ValueError(f"INSERT {handle}: non-uniform XY scale")
        if not all(math.isfinite(v) for v in (*ins.dxf.insert, *ins.dxf.extrusion)):
            raise ValueError(f"INSERT {handle}: non-finite insert/extrusion")
        if cell is not None:
            # ezdxf.multi_insert semantics: spacing in OCS, rotated but NOT scaled.
            placed = ins.copy()
            offset = Vec3(cell[1] * ins.dxf.column_spacing, cell[0] * ins.dxf.row_spacing)
            placed.dxf.insert += offset.rotate_deg(ins.dxf.rotation)
        else:
            placed = ins
        matrix = placed.matrix44()
        u, v = matrix.transform_direction(Vec3(1, 0, 0)), matrix.transform_direction(Vec3(0, 1, 0))
        scale = u.magnitude
        if (not all(math.isfinite(x) for x in matrix) or scale == 0 or v.magnitude == 0
                or ins.dxf.zscale == 0
                or not math.isclose(scale, v.magnitude, rel_tol=1e-12, abs_tol=0.0)
                or abs(u.dot(v)) > 1e-12 * scale * v.magnitude
                or abs(u.z) > 1e-12 * scale or abs(v.z) > 1e-12 * scale):
            raise ValueError(f"INSERT {handle}: non-uniform, singular or unsupported non-planar transform")
        matrices.append(matrix)
    if hatch.dxf.owner != owner:
        raise ValueError(f"hatch {hatch.dxf.handle}: insert_chain does not place its block definition")
    for path in from_hatch(hatch):
        for matrix in reversed(matrices):
            path = path.transform(matrix)
        pts = list(path.flattening(chord))
        if not pts or not all(math.isfinite(x) for p in pts for x in p):
            raise ValueError(f"hatch {hatch.dxf.handle}: non-finite or empty transformed boundary")
        if any(abs(p.z - pts[0].z) > 1e-9 for p in pts):
            raise ValueError(f"hatch {hatch.dxf.handle}: unsupported non-planar boundary")
        yield pts


def _even_odd_ring(xy):
    """Node existing segments without snapping; retain every positive-area odd-parity face [D343]."""
    from shapely.geometry import LineString
    from shapely.ops import polygonize, unary_union

    if xy[0] != xy[-1]:
        xy = [*xy, xy[0]]
    faces = []
    for face in polygonize(unary_union(LineString(xy))):
        x, y = face.representative_point().coords[0]
        odd = False
        for (ax, ay), (bx, by) in zip(xy, xy[1:]):
            if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
                odd = not odd
        if odd and face.area > 0:
            faces.append(face)
    return unary_union(faces)


def _placed_hatch_polygon(doc, hatch, chain, chord, self_touching=None):
    result = Polygon()
    for pts in _placed_hatch_paths(doc, hatch, chain, chord):
        xy = [(p.x, p.y) for p in pts]
        ring = Polygon(xy)
        if not ring.is_valid and self_touching == "even-odd":
            ring = _even_odd_ring(xy)
        if len(pts) < 3 or not ring.is_valid or ring.is_empty or not math.isfinite(ring.area):
            raise ValueError(f"hatch {hatch.dxf.handle}: invalid transformed boundary ring (not repaired)")
        result = result.symmetric_difference(ring)
    if result.is_empty or not result.is_valid or not math.isfinite(result.area):
        raise ValueError(f"hatch {hatch.dxf.handle}: empty or invalid transformed region")
    return result


def covers_from_dxf(doc, rows: list, chord: float) -> list[Cover]:
    """String modelspace handles or {handle, insert_chain} references; repeated hatch identity is refused."""
    chord = _finite("chord", chord, positive=True)
    if not isinstance(rows, list) or not rows:
        raise ValueError("no covers: expected a non-empty list")
    covers, seen = [], {}
    msp = doc.modelspace()
    for row in rows:
        allowed = {"id", "name", "hatches", "colour", "colour_reason", "self_touching"}
        if not isinstance(row, dict) or set(row) - allowed:
            raise ValueError(f"unsupported cover row or keys: {row!r}")
        handles = row.get("hatches") or []
        if not handles:
            raise ValueError(f"cover {row.get('id')}: no hatch handles")
        polys, colours = [], []
        for ref in handles:
            if isinstance(ref, str):
                h, chain = ref.upper(), []
            elif isinstance(ref, dict) and set(ref) == {"handle", "insert_chain"} and isinstance(ref["handle"], str):
                h, chain = ref["handle"].upper(), ref["insert_chain"]
            else:
                raise ValueError(f"cover {row.get('id')}: unsupported hatch reference {ref!r}")
            if h in seen:
                raise ValueError(f"hatch {h} listed by covers {seen[h]} and {row.get('id')}")
            seen[h] = row.get("id")
            e = doc.entitydb.get(h)
            if e is None or e.dxftype() != "HATCH":
                raise ValueError(f"cover {row.get('id')}: handle {h} is not a HATCH in the DXF")
            if not chain and e.dxf.owner != msp.block_record_handle:
                raise ValueError(f"hatch {h} is inside a block definition: give its insert_chain")
            if "colour" in row and not row.get("colour_reason"):
                raise ValueError(f"cover {row.get('id')}: spec colour needs colour_reason")
            colours.append(hatch_colour(e, row.get("colour")))
            policy = row.get("self_touching")
            if policy is not None and policy != "even-odd":
                raise ValueError(f"cover {row.get('id')}: unsupported self_touching {policy!r}")
            g = _placed_hatch_polygon(doc, e, chain, chord, policy)
            polys += list(getattr(g, "geoms", [g]))
        if len({c for c, _ in colours}) != 1:
            raise ValueError(f"cover {row.get('id')}: hatches have different background colours {colours}")
        covers.append(Cover(row.get("id"), row.get("name"), polys, colours[0][0], colours[0][1], list(handles)))
    return covers


def relief_from_spec(spec_path: Path) -> tuple[list, dict]:
    """Relief points (absolute) of a site spec: the spec's DXF (sha256 checked) and relief selector."""
    spec = load_spec(spec_path)
    for key in ("dxf", "relief"):
        if not isinstance(spec.get(key), dict):
            raise ValueError(f"spec {spec_path} misses {key!r}")
    dxf = Path(spec["dxf"]["path"])
    digest = sha256(dxf)
    if digest != spec["dxf"].get("sha256"):
        raise ValueError(f"DXF sha256 {digest} != spec {spec['dxf'].get('sha256')}")
    import ezdxf
    return relief_from_dxf(ezdxf.readfile(str(dxf)), spec["relief"]), spec


def relief_from_dxf(doc, spec: dict, chord: float = 0.01) -> list:
    """Native Z of planning marks (INSERT names) and design contours (layers) in a block or model space."""
    from ezdxf.path import make_path
    name = spec.get("block")
    space = doc.blocks.get(name) if name else doc.modelspace()
    if space is None:
        raise ValueError(f"relief block {name!r} not in the DXF")
    inserts, layers = set(spec.get("insert_names") or []), set(spec.get("contour_layers") or [])
    if not inserts and not layers:
        raise ValueError("relief needs insert_names and/or contour_layers")
    pts = []
    for e in space:
        if e.dxftype() == "INSERT" and e.dxf.name in inserts:
            pts.append(tuple(e.dxf.insert))
        elif e.dxf.layer in layers and e.dxftype() in ("LWPOLYLINE", "POLYLINE", "LINE", "SPLINE"):
            pts += [tuple(p) for p in make_path(e).flattening(chord)]
    if len(pts) < 3:
        raise ValueError(f"relief: {len(pts)} points found in {name or 'model space'}")
    return pts


def boundary_from_dxf(doc, handle: str) -> Polygon:
    e = doc.entitydb.get(handle)
    if e is None or e.dxftype() != "LWPOLYLINE":
        raise ValueError(f"boundary handle {handle} is not an LWPOLYLINE in the DXF")
    poly = Polygon([(p[0], p[1]) for p in e.get_points()])
    if not poly.is_valid or poly.is_empty:
        raise ValueError(f"boundary {handle} is not a valid closed polygon")
    return poly
