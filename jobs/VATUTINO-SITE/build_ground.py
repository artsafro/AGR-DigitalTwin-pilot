"""VATUTINO-SITE Ground master (#295): adapter JSON -> layered cake -> relief -> skirt -> NPM/VPM mesh JSON + report.

Usage:
  uv run python jobs/VATUTINO-SITE/build_ground.py <adapter.json> --out <dir> [--cell 4] [--chord 0.02]

Writes <dir>/ground_master_vpm.json, ground_master_npm.json (same geometry, UV scaled per profile) and
<dir>/ground_report.json. Gate 1 answers (user, 2026-10-19): footprints = uncovered parts >= 1000 m2 are holes,
slivers -> base tile_light; tile types 3/4 one TileLight; flower beds one FlowerBed slot; levels +6 / +12 mm;
cell 4 m one mesh for both profiles (correction of answer E); heights = spot heights + VP contours.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
from shapely.geometry import MultiPoint, shape

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from dt_ai.geometry import ground_cake as gc  # noqa: E402
from dt_ai.geometry import ground_details as gd  # noqa: E402
from dt_ai.ops.inv_xview import mesh_report  # noqa: E402  (#370 report-only)

SLOTS = {"tile_light": "TileLight", "tile_red": "TileRed", "tile_dark": "TileDark", "pebbles": "Pebbles",
         "gravel_screening": "Gravel", "mulch": "Mulch", "lawn_reinforced": "LawnReinforced",
         "lawn_rolled": "LawnRolled", "decking": "Decking", **{f"flower_bed_0{i}": "FlowerBed" for i in range(1, 9)}}
NPM_PX, NPM_DENSITY = 2048, 30.0  # D097 band 10-40 px/m at 2K; 30 keeps steep faces above 10
VPM_PX, VPM_DENSITY = 4096, 1280.0  # band 520-1706; 1280 flat keeps faces up to ~2.4x slope stretch above 520
STEP = 0.006
GND06 = [(500, 300_000), (1000, 705_000), (2500, 1_125_000), (5000, 1_650_000), (7500, 1_950_000),
         (10000, 2_625_000), (15000, 3_150_000), (math.inf, 4_500_000)]


def gnd06_limit(area_m2: float) -> int:
    for up, lim in GND06:
        if area_m2 <= up:
            return lim
    raise ValueError(area_m2)


def check_aliases(src: Path, out: Path, targets: list[Path]) -> str | None:
    """Reason string when the input is (or would be overwritten by) an output, else None. Resolves links."""
    rs = src.resolve()
    if out.exists() and not out.is_dir():
        return f"--out {out} exists and is not a directory"
    if out.resolve() == rs:
        return f"--out {out} resolves to the input {rs}"
    for t in targets:
        if t.resolve() == rs or (t.exists() and src.exists() and os.path.samefile(t, src)):
            return f"output {t} resolves to the input {rs}"
    return None


def site_plan(data: dict, settings: dict, footprint_min: float):
    """Apply explicit site data to the SAME method-C planner; no inferred design elevations.

    Flat computational TIN corners describe the user-authorized datum, not survey points.
    Large uncovered components remain the existing planner's footprint rule; smaller ones
    can receive an explicitly named covering instead of inheriting this job's base material.
    """
    from shapely.geometry import box
    from shapely.ops import unary_union
    required = {"slots", "flat_datum_m", "uncovered_covering"}
    if (not isinstance(settings, dict) or not required.issubset(settings)
            or set(settings) - required - {"separate_curbs", "covering_priority"}):
        raise ValueError(f"site settings require {sorted(required)}, optional separate_curbs/covering_priority; got {settings!r}")
    if type(settings.get("separate_curbs", False)) is not bool:
        raise ValueError("separate_curbs must be a boolean approved joint policy")
    datum = settings["flat_datum_m"]
    if isinstance(datum, bool) or not isinstance(datum, (float, int)) or not math.isfinite(datum):
        raise ValueError("flat_datum_m must be finite numeric metres")
    if not math.isfinite(footprint_min) or footprint_min <= 0:
        raise ValueError("footprint_min must be positive finite")
    boundary = shape(data["boundary"])
    if boundary.is_empty or not boundary.is_valid or boundary.geom_type != "Polygon":
        raise ValueError("valid nonempty Polygon boundary required")
    slots, uncovered = settings["slots"], settings["uncovered_covering"]
    if not isinstance(uncovered, str) or not uncovered or uncovered in data["coverings"]:
        raise ValueError("uncovered_covering must name a new covering")
    expected = set(data["coverings"]) | {uncovered}
    if not isinstance(slots, dict) or set(slots) != expected:
        raise ValueError(f"unmapped or unknown covering slots: {sorted(expected.symmetric_difference(slots))}")
    for key, slot in slots.items():
        if not isinstance(slot, str) or not slot or not slot.isascii() or not slot.replace('_', '').isalnum():
            raise ValueError(f"invalid material slot for {key!r}: {slot!r}")
    cov = {}
    for key, entry in data["coverings"].items():
        geom = shape(entry["geometry"])
        if geom.is_empty or not geom.is_valid or geom.geom_type not in {"Polygon", "MultiPolygon"}:
            raise ValueError(f"invalid or empty covering {key!r}")
        cov[key] = gc._polys(geom)
    priority = settings.get("covering_priority", [])
    known = set(slots.values()) - {slots[data['base_covering']], slots[uncovered]}
    if not isinstance(priority, list):
        raise ValueError("covering_priority must be a list of visible/hidden slot pairs")
    used = set()
    for pair in priority:
        if (not isinstance(pair, list) or len(pair) != 2
                or any(not isinstance(s, str) or s not in known for s in pair)
                or pair[0] == pair[1] or any(s in used for s in pair)):
            raise ValueError(f"invalid, unknown, duplicate or conflicting covering_priority: {pair!r}")
        used.update(pair)
    drops = []
    if priority:
        import shapely
        # Same polygon-only precision as the planner, before overlay of mixed-dimensional clips.
        cov = {k: gc._polys(shapely.set_precision(shapely.make_valid(unary_union(ps)), gc.GRID))
               for k, ps in cov.items()}
        for visible, hidden in priority:
            mask = unary_union([p for k, ps in cov.items() if slots[k] == visible for p in ps])
            for key in cov:
                if slots[key] != hidden:
                    continue
                original = unary_union(cov[key])
                removed = original.intersection(mask)
                cov[key] = gc._polys(original.difference(mask))
                drops.append(dict(visible_slot=visible, hidden_covering=key,
                                  removed_m2=float(removed.area), reason='hidden_by_visible_covering'))
    free = gc._polys(boundary.difference(unary_union([p for ps in cov.values() for p in ps])))
    cov[uncovered] = [p for p in free if p.area < footprint_min]
    plan = gc.plan_layers(boundary, cov, data["base_covering"], slots,
                          footprint_min_area=footprint_min, step=STEP, normalize_clips=True)
    if priority:
        plan.report['covering_priority_dispositions'] = drops
    x0, y0, x1, y1 = boundary.bounds
    points = [(x, y, datum) for x, y in list(box(x0 - 1, y0 - 1, x1 + 1, y1 + 1).exterior.coords)[:4]]
    return plan, points


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("adapter_json")
    ap.add_argument("--site-settings", type=Path, help="explicit flat datum, covering slots and unhatched covering JSON")
    ap.add_argument("--gap-exceptions", type=Path, help="explicit source/geometry-pinned user decision manifest")
    ap.add_argument("--out", required=True)
    ap.add_argument("--cell", type=float, default=4.0)
    ap.add_argument("--chord", type=float, default=0.02)
    ap.add_argument("--footprint-min", type=float, default=1000.0)
    ap.add_argument("--relief-tol", type=float, default=0.01)
    ap.add_argument("--snap", type=float, default=0.001)
    ap.add_argument("--gap-min", type=float, default=0.0055, help="steep-raise target normal gap, m (V004 >= 5 mm)")
    ap.add_argument("--gap-max", type=float, default=0.02, help="steep-raise normal gap bound, m (V004 <= 20 mm)")
    a = ap.parse_args(argv)
    src = Path(a.adapter_json)
    out = Path(a.out)
    targets = [out / f"ground_master_{p}.json" for p in ("vpm", "npm")] + [out / "ground_report.json"]
    alias = check_aliases(src, out, targets)
    if not alias and a.gap_exceptions:
        alias = check_aliases(a.gap_exceptions, out, targets)
    if not alias and a.site_settings:
        alias = check_aliases(a.site_settings, out, targets)
    if alias:
        print(f"refused before any write: {alias}", file=sys.stderr)
        return 2
    t0 = time.time()
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result
    source_bytes = src.read_bytes()
    d = json.loads(source_bytes, object_pairs_hook=unique_pairs)
    settings = None
    if a.site_settings:
        if out.exists() and any(out.iterdir()):
            raise ValueError("configured site --out must be new or empty; stale exports forbidden")
        settings_bytes = a.site_settings.read_bytes()
        settings = json.loads(settings_bytes, object_pairs_hook=unique_pairs)
        configured_plan, flat_points = site_plan(d, settings, a.footprint_min)
    out.mkdir(parents=True, exist_ok=True)
    boundary = shape(d["boundary"])
    cov = {t: list(getattr(shape(c["geometry"]), "geoms", [])) for t, c in d["coverings"].items()}
    base = d["base_covering"]
    plan = configured_plan if a.site_settings else gc.plan_layers(boundary, cov, base, SLOTS, footprint_min_area=a.footprint_min, step=STEP)
    # relief first: the TIN drives the selective cuts (user decision 2026-10-19: cut along TIN edges only in
    # cells deviating > 10 mm, all other cells stay 4 x 4 m)
    spots = [(e["x"], e["y"], e["z"]) for e in d["elevations"] if e.get("source", "point") == "point"]
    allp = [(e["x"], e["y"], e["z"]) for e in d["elevations"]]
    if a.site_settings:
        spots = allp = flat_points  # computational plane, not source elevation observations
    tin = gc.build_tin(allp)
    sampler = gc.ReliefSampler(tin)
    detail, dispositions, joints = gd.build_details(d.get("ground_elements", []), plan.surface, sampler,
                                                    separate_curbs=(settings or {}).get("separate_curbs", False))
    stair_footprints = [shape(r["footprint"]) for r in dispositions if r.get("footprint")]
    if stair_footprints:
        from shapely.ops import unary_union
        stairs = unary_union(stair_footprints)
        plan.surface = gc.MultiPolygon(gc._polys(plan.surface.difference(stairs)))
        for layer in plan.layers:
            layer.geom = gc.MultiPolygon(gc._polys(layer.geom.difference(stairs)))
        plan.report["modeled_stairs_replace_surface_m2"] = stairs.area
    flat = gc.build_flat(plan, cell=a.cell, chord=a.chord, sampler=sampler, tol=a.relief_tol, snap=a.snap)
    rep = {"input": str(src), "input_sha256": hashlib.sha256(source_bytes).hexdigest(), "plan": plan.report,
           "layers": [{"slot": l.slot, "covering": l.covering, "level": l.level, "area_m2": round(l.geom.area, 3)}
                      for l in plan.layers],
           "flat": dict(flat.report)}
    rep["coverage"] = gc.measure_coverage(flat, plan, tol=a.snap)
    rep["inside"] = gc.measure_inside(flat, plan, tol=a.chord + a.snap + 1e-3)  # chord + snap grid
    # relief
    hull_s = MultiPoint([p[:2] for p in spots]).convex_hull
    tin_s = gc.build_tin(spots)
    _, hit_s = gc.ReliefSampler(tin_s).sample(flat.verts[:, :2])
    proj, misses = gc.project_z(flat, sampler, STEP)
    zt, hitt = sampler.sample(tin.pts[:, :2])
    rep["relief"] = {
        "spot_points": len(spots), "contour_vertices": len(allp) - len(spots), "tin_points": len(tin.pts),
        "tin_triangles": len(tin.tris), "merged": tin.merged, "contradictory": tin.contradictory[:50],
        "contradictory_count": len(tin.contradictory),
        "through_points_max_dz_mm": float(np.nanmax(np.abs(zt - tin.pts[:, 2])) * 1000),
        "plot_outside_spot_hull_m2": round(plan.surface.difference(hull_s).area, 2),
        "vertex_misses_spots_only": int((~hit_s).sum()), "vertex_misses": len(misses),
        "plot_outside_tin_m2": round(plan.surface.difference(MultiPoint(tin.pts[:, :2].tolist()).convex_hull).area, 3),
    }
    if a.site_settings:
        rep["site_settings_sha256"] = hashlib.sha256(settings_bytes).hexdigest()
        rep["relief"].update(mode="flat by user decision", flat_datum_m=settings["flat_datum_m"],
                            spot_points=0, contour_vertices=0, computational_plane_corners=4)
    rep["xy_uv_mat_unchanged"] = bool(np.array_equal(proj.verts[:, :2], flat.verts[:, :2])
                                      and np.array_equal(proj.uv, flat.uv) and proj.slot == flat.slot)
    proj = gc.clean_topology(proj)
    rep["cleanup"] = proj.report["cleanup"]
    # user decision 2026-10-19: on steep relief raise a layer locally so its gap along the face normal is 5-20 mm
    proj, offsets, rep["steep_raise"] = gc.raise_steep_layers(proj, STEP, gap_min=a.gap_min, gap_max=a.gap_max)
    rep["coverage"] = gc.measure_coverage(proj, plan, tol=0.0022)
    rep["inside"] = gc.measure_inside(proj, plan, tol=a.chord + a.snap + 1e-3)
    rep["steps"] = gc.measure_steps(proj, sampler, STEP, offsets=offsets)
    rep["relief_error"] = gc.measure_relief_error(proj, sampler, STEP, tol=a.relief_tol, offsets=offsets)
    rep["stack_gaps"] = gc.measure_stack_gaps(proj, STEP, offsets=offsets)
    rep["surface_sha256"] = surface_fingerprint(proj.verts, proj.faces)
    rep["open_edges"] = gc.measure_open_edges(proj, plan, eps=0.0022)
    master = gc.add_skirt(proj, depth=1.0)
    rep["details"] = dispositions
    rep["curb_joints"] = joints
    rep["detail_triangles"] = len(detail.faces)
    master = gc.clean_topology(gd.combine([master, detail]))
    rep["codirectional"] = gc.measure_codirectional(master, band_min=0.005)
    # #370: xView overlapping vertices 2 mm / faces 5 mm, report-only (not in `gates`) until v014 parity is accepted
    rep["xview_overlaps"] = mesh_report(master.verts, master.faces, profile="NPM-GROUND", part="ground_master")
    surf_tris = int((master.level >= 0).sum())
    s_pz = sum(h.area for h in plan.holes)
    rep["budget"] = {"surface_triangles": surf_tris, "total_triangles": len(master.faces),
                     "npm_surface_limit_polygons": 50_000, "one_mesh_budget": 150_000,
                     "S_ter_m2": round(boundary.area, 2), "S_pz_m2": round(s_pz, 2),
                     "gnd06_vpm_limit": gnd06_limit(boundary.area - s_pz)}
    slots_order = sorted({*master.slot})
    surf = master.level >= 0
    meshes = {}
    for prof in ("vpm", "npm"):
        uv, layout = profile_uv(master, prof)
        px = VPM_PX if prof == "vpm" else NPM_PX
        lo, hi = (10, 40) if prof == "npm" else (520, 1706)
        dens = gc.texel_density(master.verts, master.faces[surf], uv[surf], px)
        tiles = gc.uv_tile_report(uv[surf])
        rep[f"density_{prof}"] = {"min": float(np.nanmin(dens)), "max": float(np.nanmax(dens)), "band": [lo, hi],
                                  "faces_below": int((dens < lo).sum()), "faces_above": int((dens > hi).sum()),
                                  "nan_faces": int(np.isnan(dens).sum()), **layout}
        rep[f"uv_tiles_{prof}"] = tiles
        meshes[prof] = gc.Mesh(master.verts, master.faces, master.slot, master.level, uv, master.cell, master.report)
    exceptions = json.loads(a.gap_exceptions.read_text(encoding="utf-8")) if a.gap_exceptions else None
    rep["gates"] = gates = acceptance_gates(rep, exceptions)
    rep["slots"] = slots_order
    rep["seconds"] = round(time.time() - t0, 1)
    failed = [k for k, v in gates.items() if not v["pass"]]
    if a.site_settings and (src.read_bytes() != source_bytes or a.site_settings.read_bytes() != settings_bytes):
        raise ValueError("inputs changed during build; no deliverable written")
    if not failed:  # fail closed: geometry that misses a gate is never written as a deliverable
        for prof, m in meshes.items():
            (out / f"ground_master_{prof}.json").write_text(json.dumps(gc.mesh_to_dict(m, slots_order)),
                                                            encoding="utf-8")
    (out / "ground_report.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False, default=float),
                                            encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ("flat", "coverage", "inside", "relief", "steps", "relief_error", "stack_gaps",
                                          "open_edges", "steep_raise", "codirectional", "budget", "density_vpm", "density_npm", "uv_tiles_vpm",
                                          "gates")}, default=float))
    if failed:
        print(f"FAILED gates {failed}: no mesh written", file=sys.stderr)
        return 1
    return 0


def profile_uv(master: "gc.Mesh", prof: str) -> tuple[np.ndarray, dict]:
    """Per-profile UV from the one master.

    VPM (GND-09, UDIM): the master's stacked cell UV unchanged, one 4 m cell = exactly one UDIM tile [0, 1]^2
    (1001), so every triangle is tile-contained and a shared cell border maps u = 1 to u = 0 of the next cell: the
    same texel of the tiling texture, no added seam. Flat density = 4096 / 4 = 1024 px/m.
    NPM (GND-08): world-continuous top-down UV, one texture repeat per ``NPM_PX / NPM_DENSITY`` metres (no
    seam anywhere; NPM is an atlas contract, not UDIM).
    """
    surf = master.level >= 0
    uv = master.uv.copy()
    if prof == "vpm":
        uv[surf] = np.clip(uv[surf], 0., 1.)  # <=2.1 mm weld drift on original cell border
        px, lo, length, lay = VPM_PX, 520, master.cell, {"layout": "stacked cell = UDIM 1001, side 1.0",
                                                         "flat_px_per_m": VPM_PX / master.cell}
    else:
        length = NPM_PX / NPM_DENSITY
        px, lo, lay = NPM_PX, 10, {"layout": "world top-down", "repeat_m": length, "flat_px_per_m": NPM_DENSITY}
        org = np.floor(master.verts[:, :2].min(axis=0))
        uv[surf] = (master.verts[master.faces[surf], :2] - org) / length
    us, ids = gc.side_project_uv(master.verts, master.faces[surf], uv[surf], px, lo, length, wrap=prof == "vpm")
    uv[surf] = us
    detail = master.level == -2
    if detail.any():
        uv[detail] = gd.triangle_uv(master.verts, master.faces[detail], 4. if prof == "vpm" else NPM_PX/NPM_DENSITY)
    P = master.verts[master.faces[surf][ids]]
    lay.update({"side_projected_faces": int(len(ids)),
                "side_projected_area_m2": float(0.5 * np.linalg.norm(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]),
                                                                    axis=1).sum()) if len(ids) else 0.0})
    return uv, lay


def surface_fingerprint(verts, faces) -> str:
    """Bind source-local vertex/face IDs to exact geometry and ordering, independent of JSON formatting."""
    h = hashlib.sha256()
    for arr, dtype in ((verts, "<f8"), (faces, "<i8")):
        a = np.asarray(arr, dtype=dtype)
        h.update(str(a.shape).encode("ascii"))
        h.update(a.tobytes())
    return h.hexdigest()


def accepted_gap_samples(rep: dict, policy: dict | None) -> list:
    """Only an exact frozen sample set may waive the upper bound; malformed/partial evidence fails closed."""
    try:
        sg = rep["stack_gaps"]
        actual = sg["normal_gap_over_band_samples"]
        if not policy or not policy["decision"] or not actual:
            return []
        if any(policy[k] != rep[k] for k in ("input_sha256", "surface_sha256")):
            return []
        def indexed(rows):
            result = {}
            for s in rows:
                key = (s["kind"], s["upper_face"], s["lower_face"], s["vertex"])
                if (s["kind"] not in ("corner", "centroid") or key in result
                        or not math.isfinite(s["gap_mm"]) or s["gap_mm"] <= 20):
                    raise ValueError("invalid exception sample")
                result[key] = s["gap_mm"]
            return result
        frozen, measured = indexed(policy["samples"]), indexed(actual)
        if frozen.keys() != measured.keys():
            return []
        if any(measured[k] > frozen[k] + 1e-6 for k in measured):
            return []
        if (sum(s["kind"] == "corner" for s in actual) != sg["normal_gap_vertices_above"]
                or sum(s["kind"] == "centroid" for s in actual) != sg["normal_gap_centroids_above"]):
            return []
        return actual
    except (KeyError, TypeError, ValueError):
        return []


def acceptance_gates(rep: dict, exceptions: dict | None = None) -> dict:
    """Mandatory geometry gates checked before any deliverable is written (review round 1 of PR #308)."""
    g = {
        "relief_within_tol": {"pass": rep["relief_error"]["faces_over_tol"] == 0, "value": rep["relief_error"]},
        "faces_inside_contour": {"pass": rep["inside"]["outside"] == 0, "value": rep["inside"]},
        "projection_misses_0": {"pass": rep["relief"]["vertex_misses"] == 0, "value": rep["relief"]["vertex_misses"]},
        "no_cracks": {"pass": rep["open_edges"]["open_edges_off_outline"] == 0, "value": rep["open_edges"]},
        "npm_surface_budget": {"pass": rep["budget"]["surface_triangles"] <= 50_000,
                               "value": rep["budget"]["surface_triangles"]},
    }
    for prof in ("vpm", "npm"):
        d = rep[f"density_{prof}"]
        g[f"density_{prof}"] = {"pass": d["faces_below"] == 0 and d["faces_above"] == 0 and d["nan_faces"] == 0,
                                "value": {k: d[k] for k in ("min", "max", "faces_below", "faces_above", "nan_faces")}}
    sg = rep["stack_gaps"]
    # User decision 2026-10-19: the normal gap of a locally raised layer is 5-20 mm. Both bounds are mandatory gates
    # (review round 2 of PR #308): a V004 "review" above 20 mm is not a waiver, so over-band geometry is never
    # written as a deliverable unless each over-band sample matches an explicit frozen user exception.
    # [D150] User 2026-10-20 option a: only the pinned 12 junction vertices and 6 face centres.
    gap_value = {k: sg[k] for k in sg if k.startswith("normal_gap")}
    g["normal_gap_min_5mm"] = {"pass": sg["normal_gap_centroids_below"] == 0 and sg["normal_gap_vertices_below"] == 0,
                               "value": gap_value}
    accepted = accepted_gap_samples(rep, exceptions)
    upper_ok = bool(accepted) or (sg["normal_gap_centroids_above"] == 0 and sg["normal_gap_vertices_above"] == 0)
    g["normal_gap_max_20mm"] = {"pass": upper_ok,
                                "value": {**gap_value, "accepted_samples": accepted,
                                          "decision": (exceptions or {}).get("decision") if accepted else None,
                                          "over_gap_max_vertices": rep.get("steep_raise", {}).get("over_gap_max_vertices")}}
    g["v004_codirectional_below_5mm_0"] = {"pass": rep["codirectional"]["pairs_below"] == 0,
                                           "value": rep["codirectional"]}
    t = rep["uv_tiles_vpm"]
    g["vpm_uv_tile_contained"] = {"pass": t["straddling"] == 0 and t["outside_udim_range"] == 0 and t["tiles"] == list(range(1001, 1001 + len(t["tiles"]))),
                                  "value": t}
    return g


if __name__ == "__main__":
    raise SystemExit(main())
