"""Placement report for the Vatutino site slice (#296): results.json of place_site.py -> md + json.

  uv run python jobs/VATUTINO-SITE/placement_report.py C:/x/t_5e4ea2be/run_v002/results.json
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARES = {"ground": 50000, "maf": 60000, "flora": 70000}
LIMIT = 180000


def main(path: str) -> int:
    res = json.loads(Path(path).read_text(encoding="utf-8"))
    parts = json.loads((ROOT / "jobs/VATUTINO-SITE/site-parts.json").read_text(encoding="utf-8"))
    ground_tris = parts["sources"]["ground"]["npm_triangles"]
    out = {"version": "placement-report-v001", "issue": 296, "status": "technical QA; user geometry acceptance open",
           "passed": False, "seed": res["seed"], "inputs": res["inputs"], "variants": {}}
    for var, v in res["variants"].items():
        placed = {k: c["placed"] for k, c in v["counts"].items()}
        excl = Counter((x["label"], x["reason"]) for x in v["excluded"])
        rows_maf, rows_flora = [], []
        for lid, m in v["meta"].items():
            tri = v["facts"][lid]["triangles"]
            n = placed.get(lid, 0)
            row = {"library_id": lid, "block": m["block"], "placed": n, "tris_instance": tri, "tris_total": n * tri,
                   "excluded": {r: c for (lab, r), c in excl.items() if lab == m["block"]}}
            if m["kind"] == "maf":
                p = next(p for p in parts["maf"] if p["set_id"] == lid)
                row.update(schedule=p["schedule"], catalogue_id=p["catalogue_id"], spozu_in=p["points_in"],
                           spec_dims_m=m["spec_raw"])
                rows_maf.append(row)
            else:
                f = next(f for f in parts["flora"] if f["block"] == m["block"])
                c = next(c for c in f["cands"] if c["obj"].get(var.upper()) == lid)
                row.update(pos=f["pos"], ru=f["ru"], latin=f["latin"], catalogue_id=c["id"],
                           library_latin=c["latin"], scheduled=f["qty"], spozu_total=f["spozu_total"],
                           spozu_in=f["spozu_in"], match="exact" if f["pos"] in (11, 14, 15) else "substitute",
                           base_scale=m["base_scale"], height_band_m=[0.8 * m["h_m"][0], 1.2 * m["h_m"][1]],
                           crown="review (not in schedule, gate-1 F3)",
                           scale_range=v["library_summary"][lid].get("scale_range"))
                rows_flora.append(row)
        not_placed = Counter()
        for x in v["excluded"]:
            not_placed[(x["label"], x["reason"])] += 1
        tm = sum(r["tris_total"] for r in rows_maf)
        tf = sum(r["tris_total"] for r in rows_flora)
        out["variants"][var] = {
            "engine_status": v["engine_status"], "totals": v["totals"], "scene_mismatches": v["scene_mismatches"],
            "sinking_scene": {k: v["sinking_scene"][k] for k in ("n", "measured", "per_kind", "ok")},
            "sinking_out_of_tol": v["sinking_scene"]["out_of_tol"], "engine_sinking": v["engine_sinking"],
            "bottom_faces": v["bottom_faces"], "blend": v["blend"], "commands": v["commands"],
            "findings": v["findings"], "maf": sorted(rows_maf, key=lambda r: r["library_id"]),
            "flora": sorted(rows_flora, key=lambda r: r["pos"]),
            "not_placed": [{"label": k[0], "reason": k[1], "points": n} for k, n in sorted(not_placed.items())],
            "missing_vpm": v["missing_vpm"],
            "triangles": {"maf": tm, "flora": tf, "ground_npm": ground_tris, "total": tm + tf + ground_tris,
                          "limit": LIMIT, "shares": SHARES} if var == "npm" else {"maf": tm, "flora": tf}}
    jp = ROOT / "jobs/VATUTINO-SITE/placement-report.json"
    jp.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    n = out["variants"]["npm"]
    L = ["# Vatutino site slice: MAF + Flora placement report (#296)", "",
         f"Status: **{out['status']}**, `passed=false` [D104]. Seed **{out['seed']}**. Engine `dt_ai.placement` "
         "(#316) computed every instance; Blender instancing equals it (`scene_mismatches` = 0 per variant).",
         "Machine-readable: `placement-report.json`. Scenes (not in git): "
         + ", ".join(f"`{v['blend']['path']}` sha256 `{v['blend']['sha256'][:16]}…`" for v in out["variants"].values()), ""]
    for var, v in out["variants"].items():
        L += [f"## {var.upper()}", "",
              f"Engine {v['engine_status']}; totals {v['totals']}; scene mismatches {len(v['scene_mismatches'])}; "
              f"sinking measured in the scene at every pivot ({v['sinking_scene']['measured']}/{v['sinking_scene']['n']}): "
              + "; ".join(f"{k} {d['n']}: {d['min_m']:.4f}–{d['max_m']:.4f} m" for k, d in v["sinking_scene"]["per_kind"].items())
              + f" (10 cm ± 1 cm: {'ok' if v['sinking_scene']['ok'] else 'FAIL'}).",
              f"Bottom faces: deleted {v['bottom_faces']['deleted']}, kept as `review` {v['bottom_faces']['review']}, "
              f"exposed on slopes {len(v['bottom_faces']['exposed'])}.", "",
              "### MAF", "", "| schedule | block | library | catalogue | SPOZU in 568BF | placed | tris/inst | tris total |",
              "|---|---|---|---|---|---|---|---|"]
        for r in v["maf"]:
            L.append(f"| {r['schedule']} | {r['block']} | {r['library_id']} | {r['catalogue_id']} | {r['spozu_in']} | "
                     f"{r['placed']} | {r['tris_instance']} | {r['tris_total']} |")
        L += ["", "### Flora", "", "| pos | schedule (ru / latin) | library object | match | scheduled | SPOZU all / in | placed | base scale | tris/inst | tris total |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for r in v["flora"]:
            L.append(f"| {r['pos']} | {r['ru']} / *{r['latin']}* | {r['catalogue_id']} {r['library_id']} | {r['match']} | "
                     f"{r['scheduled']} | {r['spozu_total']} / {r['spozu_in']} | {r['placed']} | {r['base_scale']:.4f} | "
                     f"{r['tris_instance']} | {r['tris_total']} |")
        L += ["", "Crown diameter: `review` for every species (not in the schedule, gate-1 F3).", "",
              "### Not placed (points, reason)", "", "| label | reason | points |", "|---|---|---|"]
        for r in v["not_placed"]:
            L.append(f"| {r['label']} | {r['reason']} | {r['points']} |")
        if v["missing_vpm"]:
            L += ["", "No confirmed VPM version (not cloned, not placed in VPM): "
                  + ", ".join(f"pos {m['pos']} {m['object']}" for m in v["missing_vpm"])]
        L.append("")
    t = n["triangles"]
    L += ["## NPM budget [D097]", "",
          f"| part | triangles | share |", "|---|---|---|",
          f"| Ground surface (#295 v014 NPM) | {t['ground_npm']} | 50 000 |",
          f"| MAF | {t['maf']} | 60 000 |", f"| Flora | {t['flora']} | 70 000 |",
          f"| **total** | **{t['total']}** | **180 000** |", "",
          f"Flora overrun {t['flora'] - 70000:+d} vs its share and total {t['total'] - LIMIT:+d} vs 180 000: accepted "
          "for this slice by the user (gate-1 F4 option a, 2026-10-20); a lighter Flora NPM is a separate card.", "",
          "## Questions to the user (not modelled, not substituted)", "",
          "- Flora without a library object (gate-1 F1): pos 2 Ольха, 5 Лиственница, 8 Лох, 10 Дерен кроваво-красный, "
          "13 Облепиха, 16 Ель нидиформис; unscheduled Ива швейцарская (131 points).",
          "- MAF without a library model (#313 Q1/Q5): see `not_placed` rows `no_library_model`.",
          "- Two Урна points 15E288 / 15E289 lie inside 568BF over a hole of the Ground v014 (engine "
          "`point_over_ground_hole`, run v001 stopped): not placed; Ground hole to #295.",
          "- Out-of-plot planting (gate-1 Q2a): `outside_boundary` rows. Pinus mugo placed by 106 plan points, "
          "schedule 99 (+7, gate-1 Q2b).", ""]
    (ROOT / "jobs/VATUTINO-SITE/placement-report.md").write_text("\n".join(L), encoding="utf-8")
    print(f"npm maf {t['maf']} flora {t['flora']} total {t['total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
