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
import sys
import time
from pathlib import Path

import numpy as np
from shapely.geometry import MultiPoint, shape

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from dt_ai.geometry import ground_cake as gc  # noqa: E402

SLOTS = {"tile_light": "TileLight", "tile_red": "TileRed", "tile_dark": "TileDark", "pebbles": "Pebbles",
         "gravel_screening": "Gravel", "mulch": "Mulch", "lawn_reinforced": "LawnReinforced",
         "lawn_rolled": "LawnRolled", "decking": "Decking", **{f"flower_bed_0{i}": "FlowerBed" for i in range(1, 9)}}
NPM_PX, NPM_DENSITY = 2048, 30.0  # D097 band 10-40 px/m at 2K; 30 keeps steep faces above 10
VPM_PX = 4096  # one 4 m cell = one UDIM tile 1001 square -> 1024 px/m (band 520-1706)
STEP = 0.006
GND06 = [(500, 300_000), (1000, 705_000), (2500, 1_125_000), (5000, 1_650_000), (7500, 1_950_000),
         (10000, 2_625_000), (15000, 3_150_000), (math.inf, 4_500_000)]


def gnd06_limit(area_m2: float) -> int:
    for up, lim in GND06:
        if area_m2 <= up:
            return lim
    raise ValueError(area_m2)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("adapter_json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--cell", type=float, default=4.0)
    ap.add_argument("--chord", type=float, default=0.02)
    ap.add_argument("--footprint-min", type=float, default=1000.0)
    a = ap.parse_args(argv)
    src = Path(a.adapter_json)
    out = Path(a.out)
    if out.resolve() == src.resolve() or src.resolve().parent == out.resolve() and False:
        raise SystemExit("output path resolves to the input")
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    d = json.loads(src.read_text(encoding="utf-8"))
    boundary = shape(d["boundary"])
    cov = {t: list(getattr(shape(c["geometry"]), "geoms", [])) for t, c in d["coverings"].items()}
    base = d["base_covering"]
    plan = gc.plan_layers(boundary, cov, base, SLOTS, footprint_min_area=a.footprint_min, step=STEP)
    flat = gc.build_flat(plan, cell=a.cell, chord=a.chord)
    rep = {"input": str(src), "input_sha256": hashlib.sha256(src.read_bytes()).hexdigest(), "plan": plan.report,
           "layers": [{"slot": l.slot, "covering": l.covering, "level": l.level, "area_m2": round(l.geom.area, 3)}
                      for l in plan.layers],
           "flat": dict(flat.report)}
    rep["coverage"] = gc.measure_coverage(flat, plan)
    rep["inside"] = gc.measure_inside(flat, plan, tol=a.chord + 1e-3)
    # relief
    spots = [(e["x"], e["y"], e["z"]) for e in d["elevations"] if e.get("source", "point") == "point"]
    allp = [(e["x"], e["y"], e["z"]) for e in d["elevations"]]
    hull_s = MultiPoint([p[:2] for p in spots]).convex_hull
    tin_s = gc.build_tin(spots)
    _, hit_s = gc.ReliefSampler(tin_s).sample(flat.verts[:, :2])
    tin = gc.build_tin(allp)
    sampler = gc.ReliefSampler(tin)
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
    rep["xy_uv_mat_unchanged"] = bool(np.array_equal(proj.verts[:, :2], flat.verts[:, :2])
                                      and np.array_equal(proj.uv, flat.uv) and proj.slot == flat.slot)
    rep["steps"] = gc.measure_steps(proj, sampler, STEP)
    master = gc.add_skirt(proj, depth=1.0)
    surf_tris = int((master.level >= 0).sum())
    s_pz = sum(h.area for h in plan.holes)
    rep["budget"] = {"surface_triangles": surf_tris, "total_triangles": len(master.faces),
                     "npm_surface_limit_polygons": 50_000, "one_mesh_budget": 150_000,
                     "S_ter_m2": round(boundary.area, 2), "S_pz_m2": round(s_pz, 2),
                     "gnd06_vpm_limit": gnd06_limit(boundary.area - s_pz)}
    slots_order = sorted({*master.slot})
    k_npm = gc.uv_scale_for_density(a.cell, NPM_PX, NPM_DENSITY)
    surf = master.level >= 0
    for prof, k, px in (("vpm", 1.0, VPM_PX), ("npm", k_npm, NPM_PX)):
        uv = master.uv.copy()
        uv[surf] *= k
        m = gc.Mesh(master.verts, master.faces, master.slot, master.level, uv, master.cell, master.report)
        dens = gc.texel_density(m.verts, m.faces[surf], uv[surf], px)
        lo, hi = (10, 40) if prof == "npm" else (520, 1706)
        rep[f"density_{prof}"] = {"min": float(np.nanmin(dens)), "max": float(np.nanmax(dens)), "band": [lo, hi],
                                  "faces_below": int((dens < lo).sum()), "faces_above": int((dens > hi).sum()),
                                  "nan_faces": int(np.isnan(dens).sum()), "uv_cell_side": k}
        (out / f"ground_master_{prof}.json").write_text(json.dumps(gc.mesh_to_dict(m, slots_order)), encoding="utf-8")
    rep["slots"] = slots_order
    rep["seconds"] = round(time.time() - t0, 1)
    (out / "ground_report.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False, default=float),
                                            encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ("flat", "coverage", "inside", "relief", "steps", "budget",
                                          "density_vpm", "density_npm")}, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
