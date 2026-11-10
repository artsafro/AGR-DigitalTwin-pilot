"""Route A step 1 for Flora #426: the 17 Vatutino schedule positions + Ива -> exact species, map status, source.

Pattern: n/a | new-case: #1146 job-local species sheet (one generator for flora-species.json/.md and the step-3 star spec).
Rows are transcribed from site-parts.md (schedule *T3509, SPOZU points inside 568BF); maps from library/flora/maps.json.
Run: uv run python jobs/VATUTINO-SITE/flora_species.py --check   (exit 1 when the committed files are stale)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SINGLE_SOURCE_TOTAL = 4915  # site-parts.md: 3,170 placed + 1,745 not placed (v006)

# pos, russian, schedule latin, exact latin, kind, cm lo, cm hi, SPOZU points in 568BF, approved map key, status, material id
ROWS = [
    (1, "Липа мелколистная", "Tilia cordata Greenspire", "Tilia cordata 'Greenspire'", "tree", 500, 550, 23, "Tilia cordata", "approved-species", 101),
    (2, "Ольха серая", "Alnus glutinosa Laciniata", "Alnus glutinosa 'Laciniata' (RU name = Alnus incana, F5)", "tree", 500, 550, 8, None, "missing", 131),
    (3, "Черемуха обыкновенная", "Prunus padus Watereri", "Prunus padus 'Watereri'", "tree", 300, 550, 11, "Prunus padus", "approved-species", 120),
    (4, "Яблоня Маковецкого", "Malus Makowieckiana", "Malus × purpurea 'Makowieckiana'", "tree", 300, 550, 21, "Malus niedzwetzkyana", "proxy", 128),
    (5, "Лиственница обыкновенная", "Larix decidua Pendula", "Larix decidua 'Pendula'", "tree", 150, 500, 13, None, "missing", 129),
    (6, "Ирга колосистая", "Amelanchier spicata", "Amelanchier spicata", "bush", 125, 350, 38, "Amelanchier lamarckii", "proxy", 240),
    (7, "Боярышник обыкновенный", "Crataegus laevigata Paul`s Scarlet", "Crataegus laevigata 'Paul's Scarlet'", "tree", 125, 350, 29, "Crataegus mollis", "proxy", 130),
    (8, "Лох узколистный", "Elaeagnus angustifolia", "Elaeagnus angustifolia", "bush", 125, 350, 25, None, "missing", 241),
    (9, "Пузыреплодник калинолистный", "Physocarpus opulifolius Lady in red", "Physocarpus opulifolius 'Lady in Red'", "bush", 125, 200, 191, "Physocarpus opulifolius 'Diabolo'", "proxy", 242),
    (10, "Дерен кроваво-красный", "Cornus sanguinea Anny Winter Orange", "Cornus sanguinea 'Anny's Winter Orange'", "bush", 125, 200, 439, None, "missing", 228),
    (11, "Рябинник рябинолистный", "Sorbaria sorbifolia", "Sorbaria sorbifolia", "bush", 125, 200, 866, "Sorbaria sorbifolia", "approved-exact", 212),
    (12, "Дерен отпрысковый 'Red Gnome'", "Cornus sericea 'Red Gnome'", "Cornus sericea 'Red Gnome'", "bush", 125, 200, 325, "Cornus sericea", "approved-species", 204),
    (13, "Облепиха крушиновидная", "Hippophae rhamnoides hikul", "Hippophae rhamnoides 'Hikul'", "bush", 125, 200, 1059, None, "missing", 243),
    (14, "Лапчатка кустарниковая", "Potentila fruticosa", "Dasiphora fruticosa", "bush", 80, 100, 558, "Dasiphora fruticosa", "approved-exact", 230),
    (15, "Стефанандра надрезаннолистная", "Stephanandra incisa", "Stephanandra incisa", "bush", 20, 60, 1002, "Stephanandra incisa 'Crispa'", "approved-species", 223),
    (16, "Ель нидиформис", "Picea abies Nidiformis", "Picea abies 'Nidiformis'", "bush", 60, 100, 70, None, "missing", 236),
    (17, "Сосна горная ф. Мугус", "Pinus mugo var. Mughus", "Pinus mugo var. mughus", "bush", 60, 100, 106, "Pinus mugo", "approved-species", 224),
    ("Ива", "Ива швейцарская (block only, not in *T3509)", "Salix helvetica", "Salix helvetica", "bush", None, None, 131, None, "missing", 244),
]
SOURCE = {
    "approved-exact": "approved map, exact species",
    "approved-species": "approved map, same species (cultivar differs)",
    "proxy": "NEW exact map (step 2); fallback = approved proxy map",
    "missing": "NEW map (step 2)",
}
STATUSES = set(SOURCE)


def records():
    maps = json.loads((ROOT / "library/flora/maps.json").read_text(encoding="utf-8"))
    out = []
    for pos, ru, sched, exact, kind, lo, hi, n, key, status, mid in ROWS:
        if status not in STATUSES:
            raise ValueError(f"pos {pos}: unknown map status {status!r}")
        if (key is None) != (status == "missing"):
            raise ValueError(f"pos {pos}: map key {key!r} inconsistent with status {status}")
        rec = {
            "pos": pos, "russian": ru, "schedule_latin": sched, "exact_latin": exact, "kind": kind,
            "schedule_cm": [lo, hi] if lo else None,
            "band_m": [round(lo / 100 * 0.8, 3), round(hi / 100 * 1.2, 3)] if lo else None,
            "target_height_m": round((lo + hi) / 200, 3) if lo else None,
            "plants_in_plot": n, "map_status": status, "map_key": key,
            "material_id": mid, "proposed_source": SOURCE[status],
        }
        if key is not None:
            entry = maps.get(key)
            if entry is None or entry.get("review_status") != "approved":
                raise ValueError(f"pos {pos}: map {key!r} is not an approved maps.json entry")
            rec["map"] = {k: entry[k] for k in ("diffuse", "opacity", "evidence")}
        out.append(rec)
    ids = [r["material_id"] for r in out]
    if len(set(ids)) != len(ids):
        raise ValueError(f"duplicate material ids: {sorted(i for i in set(ids) if ids.count(i) > 1)}")
    total = sum(r["plants_in_plot"] for r in out)
    if total != SINGLE_SOURCE_TOTAL:
        raise ValueError(f"plants in plot {total} != {SINGLE_SOURCE_TOTAL} (site-parts.md)")
    return out


def summary(recs):
    trees = sum(r["plants_in_plot"] for r in recs if r["kind"] == "tree")
    bushes = sum(r["plants_in_plot"] for r in recs if r["kind"] == "bush")
    by = {s: [r["pos"] for r in recs if r["map_status"] == s] for s in sorted(STATUSES)}
    return {"rows": len(recs), "plants": trees + bushes, "trees": trees, "bushes": bushes,
            "npm_tris_estimate": trees * 8 + bushes * 6, "by_map_status": by}


def star_spec(recs, include_proxy=True):
    """Step-3 spec for every row that has an approved map today (proxies only as labelled fallback)."""
    species = []
    for r in recs:
        if "map" not in r or (r["map_status"] == "proxy" and not include_proxy) or r["band_m"] is None:
            continue
        species.append({"key": f"pos{r['pos']:02d}_{r['material_id']}", "latin": r["exact_latin"]
                        if r["map_status"] != "proxy" else f"{r['map_key']} (proxy for {r['exact_latin']})",
                        "kind": r["kind"], "height_m": r["target_height_m"], "band_m": r["band_m"],
                        "diffuse": r["map"]["diffuse"], "opacity": r["map"]["opacity"],
                        "material_id": r["material_id"]})
    return species


def markdown(recs):
    s = summary(recs)
    lines = [
        "# Vatutino Flora species sheet — route A step 1 (#1146, [D232])", "",
        "Generated by `jobs/VATUTINO-SITE/flora_species.py` from `site-parts.md` (schedule `*T3509`, SPOZU points in 568BF) "
        "and `library/flora/maps.json`. Material ids: existing library id when an approved map is used; the catalogue "
        "stand-in gap id when one names the exact species (228, 236); otherwise the next free id in the #216 range "
        "(trees 128-131, bushes 240-244) — proposed, not yet in the catalogue.", "",
        "| Поз. | Schedule (RU / Latin) | Exact species | Kind | Height cm → band m | Plants in plot | Map | Source | Mat. id |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in recs:
        hb = f"{r['schedule_cm'][0]}–{r['schedule_cm'][1]} → {r['band_m'][0]:.2f}–{r['band_m'][1]:.2f}" if r["schedule_cm"] else "— (not in schedule)"
        lines.append(f"| {r['pos']} | {r['russian']} / *{r['schedule_latin']}* | *{r['exact_latin']}* | {r['kind']} | {hb} | "
                     f"{r['plants_in_plot']} | {r['map_status']}{': ' + r['map_key'] if r['map_key'] else ''} | {r['proposed_source']} | {r['material_id']} |")
    lines += ["", f"Rows **{s['rows']}**; plants **{s['plants']}** (trees {s['trees']}, bushes {s['bushes']}); "
              f"NPM star estimate {s['trees']} × 8 + {s['bushes']} × 6 = **{s['npm_tris_estimate']}** tris (budget 70,000 [D097]).", "",
              "Map status: " + "; ".join(f"{k} = {', '.join(map(str, v))}" for k, v in s["by_map_status"].items()) + ".", "",
              "Kind: trees = positions 1, 2, 3, 4, 5, 7 (route estimate ~105 trees); 6 Ирга and 8 Лох (1.25–3.5 m) are built as bushes.", ""]
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true")
    p.add_argument("--star-spec", help="write the step-3 star spec here (with --udim-tile)")
    p.add_argument("--udim-tile", type=int)
    a = p.parse_args(argv)
    recs = records()
    want = {HERE / "flora-species.json": json.dumps({"schema": "vatutino-flora-species-v1", "summary": summary(recs),
                                                       "species": recs}, indent=1, ensure_ascii=False) + "\n",
            HERE / "flora-species.md": markdown(recs)}
    if a.star_spec:
        if a.udim_tile is None:
            sys.exit("--star-spec needs --udim-tile (D210: first free tile after Ground); no default")
        out = Path(a.star_spec)
        if out.exists():
            sys.exit(f"refusing to overwrite {out}")
        out.write_text(json.dumps({"udim_tile": a.udim_tile, "species": star_spec(recs)}, indent=1, ensure_ascii=False), encoding="utf-8")
        return 0
    stale = [str(k.name) for k, v in want.items() if not k.exists() or k.read_text(encoding="utf-8") != v]
    if a.check:
        print(json.dumps({"stale": stale, **summary(recs)}, ensure_ascii=False))
        return 1 if stale else 0
    for k, v in want.items():
        k.write_text(v, encoding="utf-8", newline="\n")
    print(json.dumps(summary(recs), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
