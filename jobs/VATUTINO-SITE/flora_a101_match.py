"""Route A step 2 for Flora #426: match the 11 needed map pairs against the A101 Flora library.

Pattern: n/a | new-case: #1146 job-local A101 match table (maps the missing/proxy Vatutino positions to the
A101 Drive library, exact species only, and lists the remaining gaps for Artem).
The needed set is the missing+proxy rows of flora_species.py (positions 2, 4, 5, 6, 7, 8, 9, 10, 13, 16, Ива).
A101 files are copied from G:/Мой диск/AGR-assets/flora/a101/ (read-only; hashed, never edited). This module
does NOT read the Drive: A101_TEXTURES is a frozen copy of the TextureFlora PNG name list so `--check` stays
hermetic. The Drive copy + hashes are recorded in flora-a101-match.json under "copies".
Run: uv run python jobs/VATUTINO-SITE/flora_a101_match.py --check   (exit 1 when the committed files are stale)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def _load_species():
    spec = importlib.util.spec_from_file_location("flora_species", HERE / "flora_species.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_species = _load_species()
ROWS = _species.ROWS

# Frozen list of TextureFlora PNG names (G:/Мой диск/AGR-assets/flora/a101/TextureFlora/), 2026-11-09.
A101_TEXTURES = {
    "alium_paporotnik_t1_h120_high.png", "alium_paporotnik_t1_h120_low.png",
    "barbaris_t1_h40_high.png", "barbaris_t1_h40_low.png", "barbaris_t2_h80_high.png", "barbaris_t2_h80_low.png",
    "beresklet_krilatiy_t1_h150_high.png", "beresklet_krilatiy_t1_h150_low.png",
    "bereza_t1_h450_high.png", "bereza_t1_h450_low.png",
    "boyarishnik_t1_h150_high.png", "boyarishnik_t1_h150_low.png",
    "bush_t1_h120_high.png", "bush_t1_h120_low.png", "bush_t2_h60_high.png", "bush_t2_h60_low.png",
    "chbushnik_t1_h190_high.png", "chbushnik_t1_h190_low.png", "chbushnik_t2_h150_high.png", "chbushnik_t2_h150_low.png",
    "cheremuxa_t1_h450_high.png", "cheremuxa_t1_h450_low.png", "cheremuxa_t2_h250_high.png", "cheremuxa_t2_h250_low.png",
    "derbennik_ivolistniy_t1_h120_high.png", "derbennik_ivolistniy_t1_h120_low.png",
    "derbennik_ivolistniy_t1_h80_high.png", "derbennik_ivolistniy_t1_h80_low.png",
    "deren_t1_h120_high.png", "deren_t1_h120_low.png", "deren_t2_h150_high.png", "deren_t2_h150_low.png",
    "deren_t3_h100_high.png", "deren_t3_h100_low.png", "deren_t4_h120_high.png", "deren_t4_h120_low.png",
    "deren_t5_h100_high.png", "deren_t5_h100_low.png", "deren_t6_h80_high.png", "deren_t6_h80_low.png",
    "devichiy_vinograd_t1_h140_high.png", "devichiy_vinograd_t1_h140_low.png",
    "diervela_ruchejnaya_t1_h120_high.png", "diervela_ruchejnaya_t1_h120_low.png",
    "el_nidiformis_t1_h60_high.png", "el_nidiformis_t1_h60_low.png",
    "elka_t1_h400_high.png", "elka_t1_h400_low.png", "elka_t2_h300.png", "elka_t2_h300_low.png",
    "exinaceya_purpurnaya_t1_h80_high.png", "exinaceya_purpurnaya_t1_h80_low.png",
    "forzicia_yacevidnaya_t1_h100_high.png", "forzicia_yacevidnaya_t1_h100_low.png",
    "gortenzia_drevovidnaya_t1_h120_high.png", "gortenzia_drevovidnaya_t1_h120_low.png",
    "gortenzia_drevovidnaya_t2_h100_high.png", "gortenzia_drevovidnaya_t2_h100_low.png",
    "gortenzia_drevovidnaya_t3_h100_high.png", "gortenzia_drevovidnaya_t3_h100_low.png",
    "gortenzia_metelchataya_t1_h100_high.png", "gortenzia_metelchataya_t1_h100_low.png",
    "irga_lamarka_t1_h150_high.png", "irga_lamarka_t1_h150_low.png", "irga_lamarka_t2_h150_high.png", "irga_lamarka_t2_h150_low.png",
    "irga_lamarka_t3_h350_high.png", "irga_lamarka_t3_h350_low.png", "irga_lamarka_t4_h150_high.png", "irga_lamarka_t4_h150_low.png",
    "iris_bolotniy_t1_h80_high.png", "iris_bolotniy_t1_h80_low.png",
    "ism_t1_h80_high.png", "ism_t1_h80_low.png", "ism_t2_h60_high.png", "ism_t2_h60_low.png",
    "iva_bush_t1_h150_high.png", "iva_bush_t1_h150_low.png", "iva_bush_t2_h50_high.png", "iva_bush_t2_h50_low.png",
    "iva_lomkaya_t1_h450_high.png", "iva_lomkaya_t1_h450_low.png",
    "iva_polzuchaya_t1_h40_high.png", "iva_polzuchaya_t1_h40_low.png",
    "jimolost_t1_h150_high.png", "jimolost_t1_h150_low.png",
    "kalina_t1_h190_high.png", "kalina_t1_h190_low.png",
    "kizilnik_barbaris_t1_h100_high.png", "kizilnik_barbaris_t1_h100_low.png",
    "kizilnik_barbaris_t2_h80_high.png", "kizilnik_barbaris_t2_h80_low.png",
    "kizilnik_barbaris_t3_h100_high.png", "kizilnik_barbaris_t3_h100_low.png",
    "kizilnik_barbaris_t4_h60_high.png", "kizilnik_barbaris_t4_h60_low.png",
    "klen_ginnala_t1_h150_high.png", "klen_ginnala_t1_h150_low.png", "klen_ginnala_t2_h150_high.png", "klen_ginnala_t2_h150_low.png",
    "klen_t1_h175_high.png", "klen_t1_h175_low.png", "klen_t2_h175_high.png", "klen_t2_h175_low.png",
    "klen_t3_h350_high.png", "klen_t3_h350_low.png", "klen_t4_h350_high.png", "klen_t4_h350_low.png",
    "klen_t5_h500_high.png", "klen_t5_h500_low.png", "klen_t6_h500_high.png", "klen_t6_h500_low.png",
    "klen_t7_h550_high.png", "klen_t7_h550_low.png", "klen_t8_h700_high.png", "klen_t8_h700_low.png",
    "lapchatka_kustarnikovaya_t1_h100_high.png", "lapchatka_kustarnikovaya_t1_h100_low.png",
    "lapchatka_kustarnikovaya_t2_h80_high.png", "lapchatka_kustarnikovaya_t2_h80_low.png",
    "lipa_t1_h550_high.png", "lipa_t1_h550_low.png",
    "mojevelnik_t1_h40_high.png", "mojevelnik_t1_h40_low.png", "mojevelnik_t2_h400_high.png", "mojevelnik_t2_h400_low.png",
    "osoka_palmolistnaya_t1_h80_high.png", "osoka_palmolistnaya_t1_h80_low.png",
    "paxizandra_t1_h40_high.png", "paxizandra_t1_h40_low.png",
    "puzyreplodnik_kalinolistnyj_t1_h150_high.png", "puzyreplodnik_kalinolistnyj_t1_h150_low.png",
    "puzyreplodnik_kalinolistnyj_t2_h150_high.png", "puzyreplodnik_kalinolistnyj_t2_h150_low.png",
    "puzyreplodnik_kalinolistnyj_t3_h150_high.png", "puzyreplodnik_kalinolistnyj_t3_h150_low.png",
    "puzyreplodnik_t1_h150_high.png", "puzyreplodnik_t1_h150_low.png",
    "riabina_t1_h350_high.png", "riabina_t1_h350_low.png",
    "riabinnik_riabinolistniy_t1_h100_high.png", "riabinnik_riabinolistniy_t1_h100_low.png",
    "riabinnik_riabinolistniy_t2_h120_high.png", "riabinnik_riabinolistniy_t2_h120_low.png",
    "riabinnik_riabinolistniy_t3_h100_high.png", "riabinnik_riabinolistniy_t3_h100_low.png",
    "riabinnik_riabinolistniy_t4_h100_high.png", "riabinnik_riabinolistniy_t4_h100_low.png",
    "siren_t1_h160_high.png", "siren_t1_h160_low.png", "siren_t2_h150_high.png", "siren_t2_h150_low.png",
    "sosna_gornaya_t1_h60_high.png", "sosna_gornaya_t1_h60_low.png",
    "spireya_berezolistnaya_t1_h80_high.png", "spireya_berezolistnaya_t1_h80_low.png",
    "spireya_bumalda_yaponskaya_t1_h80_high.png", "spireya_bumalda_yaponskaya_t1_h80_low.png",
    "spireya_seraya_t1_h100_high.png", "spireya_seraya_t1_h100_low.png",
    "spireya_yaponskaya_t1_h80_high.png", "spireya_yaponskaya_t1_h80_low.png",
    "spireya_yaponskaya_t2_h80_high.png", "spireya_yaponskaya_t2_h80_low.png",
    "spireya_yaponskaya_t3_h40_high.png", "spireya_yaponskaya_t3_h40_low.png",
    "tree_t1_h500_high.png", "tree_t1_h500_low.png", "tree_t2_h300_high.png", "tree_t2_h300_low.png",
    "vishnya_t1_h500_high.png", "vishnya_t1_h500_low.png",
    "yablonya_t1_h350_high.png", "yablonya_t1_h350_low.png", "yablonya_t2_h450_high.png", "yablonya_t2_h450_low.png",
    "yasen_t1_h550_high.png", "yasen_t1_h550_low.png",
    "zlaki_t1_h150_high.png", "zlaki_t1_h150_low.png",
}

A101_PREVIEWS = {
    "el_nidiformis_t1_h60_PREVIEW.png",
    "puzyreplodnik_kalinolistnyj_t1_h150_PREVIEW.png",
    "puzyreplodnik_kalinolistnyj_t3_h150_PREVIEW.png",
}

# SHA256 of the copied A101 matches (G:/Мой диск/AGR-evidence/1146-flora-star/a101-matched/, 11 files, 2026-11-09).
# A101 TextureFlora PNGs are 2048x2048 RGBA (diffuse + alpha, already cut out); "high"/"low" are two variants.
COPIED_SHA256 = {
    "el_nidiformis_t1_h60_high.png": "7bfe86a2bc147ac875b7c267eaeb98313d14b76e6127a880a12c47ed024f7578",
    "el_nidiformis_t1_h60_low.png": "f2f348ad3434b8157a4935199a613da88c9a36b0f94c5dd1aa1da8a72008bcb5",
    "el_nidiformis_t1_h60_PREVIEW.png": "2e3a9a115bbd18bf5afc59f1702a99b4e140e222cefd98ce3a4f90ff52dd02f1",
    "puzyreplodnik_kalinolistnyj_t1_h150_high.png": "9af7c5682b032ab8c505265bc600fc9d14b51b2506800f66514e2d4d11ad00c8",
    "puzyreplodnik_kalinolistnyj_t1_h150_low.png": "a671588be5fd368b77420bae521ab93234568e65d0b9aae206182b095a64a8e1",
    "puzyreplodnik_kalinolistnyj_t1_h150_PREVIEW.png": "8c653d2019654d6ca1a46a8677d0235b6a94498645fc8049361b852d1a6828e6",
    "puzyreplodnik_kalinolistnyj_t2_h150_high.png": "46cdf92163b6fd565ca2258581aef74ba4221ce6d3dbda6ca2a8f11fd13484b4",
    "puzyreplodnik_kalinolistnyj_t2_h150_low.png": "6662e60fa193208351f9d99759b5e7492c7ff2b704c8b669979d802b36cad155",
    "puzyreplodnik_kalinolistnyj_t3_h150_high.png": "6293cea6f3f1e750270b357ed224a9709e46901c7063a09da86b9887b07e6365",
    "puzyreplodnik_kalinolistnyj_t3_h150_low.png": "c7b49cd8e314796fd20672d9809e9927ed351543265f8fe1a4f4de76ee7338e8",
    "puzyreplodnik_kalinolistnyj_t3_h150_PREVIEW.png": "e54b663320e496c3f29a531358c4a7a9d8d16903f463ad6c30f152728a8bc4c9",
}


def label_from_rgb(mean_rgb, red_gt_green):
    """Deterministic colour label from a mean-RGB measurement (opaque pixels, alpha >= 128).

    Matches the reviewer's classification of the pos-9 A101 variants: t1 yellow (139/123/6),
    t2 dark red (97/67/65), t3 yellow-green (170/180/68); generic puzyreplodnik_t1 green (109/126/47).
    """
    r, g, b = int(mean_rgb[0]), int(mean_rgb[1]), int(mean_rgb[2])
    if r > g and red_gt_green >= 0.9:
        return "dark red" if r < 130 else "red"
    if r > g and b < 40:
        return "yellow"
    if g >= r and r > 130:
        return "yellow-green"
    return "green"


# Measured colour of the pos-9 exact-species A101 variants (mean RGB of opaque pixels, alpha >= 128;
# computed with PIL 12.3.0 from the copied PNGs bound to COPIED_SHA256 above, 2026-11-09). The label is
# derived by label_from_rgb() and asserted equal to the pixel measurement in the tests. Bound to sha256:
# COLOURS keys are a subset of COPIED_SHA256, so a stale copy or a re-labelled file fails the colour test.
COLOURS = {
    "puzyreplodnik_kalinolistnyj_t1_h150_high.png": {"mean_rgb": [139, 123, 6], "red_gt_green": 0.82, "label": "yellow"},
    "puzyreplodnik_kalinolistnyj_t2_h150_high.png": {"mean_rgb": [97, 67, 65], "red_gt_green": 1.00, "label": "dark red"},
    "puzyreplodnik_kalinolistnyj_t3_h150_high.png": {"mean_rgb": [170, 180, 68], "red_gt_green": 0.30, "label": "yellow-green"},
}

# Measured colour of the generic puzyreplodnik_t1 candidate (not copied; name-only candidate, same as the
# other generic-genus candidates). Recorded here so the note can state its colour factually.
GENERIC_PUZYREPLODNIK_COLOUR = {"mean_rgb": [109, 126, 47], "red_gt_green": 0.19, "label": "green"}


def _variants(m):
    out = []
    for v in m.get("variants", []):
        c = COLOURS.get(v["file"])
        out.append({"file": v["file"], "mean_rgb": c["mean_rgb"] if c else None,
                    "red_gt_green": c["red_gt_green"] if c else None, "label": v["label"]})
    return out


# pos -> A101 resolution. "match" in {"exact", "exact-species", "no-match"}.
# exact / exact-species carry "files" (diffuse-only PNGs; opacity is cut out later in step 2) and "previews".
# no-match carries "reason" and optional "candidates" (closest A101 names, for Artem).
MATCHES = {
    2:  {"match": "no-match", "reason": "no Alnus (ольха) in A101", "candidates": []},
    4:  {"match": "no-match", "reason": "generic genus Malus (яблоня) only, no species/cultivar",
         "candidates": ["yablonya_t1_h350_high.png", "yablonya_t2_h450_high.png"]},
    5:  {"match": "no-match", "reason": "no Larix (лиственница) in A101", "candidates": []},
    6:  {"match": "no-match", "reason": "A101 = Amelanchier lamarckii (Ирга Ламарка), a different species; it is the current approved proxy",
         "candidates": ["irga_lamarka_t1_h150_high.png", "irga_lamarka_t2_h150_high.png", "irga_lamarka_t3_h350_high.png", "irga_lamarka_t4_h150_high.png"]},
    7:  {"match": "no-match", "reason": "generic genus Crataegus (боярышник) only, no species",
         "candidates": ["boyarishnik_t1_h150_high.png"]},
    8:  {"match": "no-match", "reason": "no Elaeagnus (лох) in A101", "candidates": []},
    9:  {"match": "exact-species",
         "reason": ("exact species Physocarpus opulifolius (пузыреплодник калинолистный), three colour variants "
                    "(mean RGB, opaque pixels alpha ≥ 128): t1 yellow (139/123/6), t2 dark red (97/67/65), "
                    "t3 yellow-green (170/180/68). t2 is the red-leaved form — an exact-species red candidate for "
                    "'Lady in Red' (replaces the 'Diabolo' proxy). Generic puzyreplodnik_t1 (green 109/126/47) "
                    "is also listed as a candidate."),
         "files": ["puzyreplodnik_kalinolistnyj_t1_h150_high.png", "puzyreplodnik_kalinolistnyj_t1_h150_low.png",
                   "puzyreplodnik_kalinolistnyj_t2_h150_high.png", "puzyreplodnik_kalinolistnyj_t2_h150_low.png",
                   "puzyreplodnik_kalinolistnyj_t3_h150_high.png", "puzyreplodnik_kalinolistnyj_t3_h150_low.png"],
         "variants": [
             {"file": "puzyreplodnik_kalinolistnyj_t1_h150_high.png", "label": "yellow"},
             {"file": "puzyreplodnik_kalinolistnyj_t2_h150_high.png", "label": "dark red"},
             {"file": "puzyreplodnik_kalinolistnyj_t3_h150_high.png", "label": "yellow-green"},
         ],
         "candidates": ["puzyreplodnik_t1_h150_high.png", "puzyreplodnik_t1_h150_low.png"],
         "previews": ["puzyreplodnik_kalinolistnyj_t1_h150_PREVIEW.png", "puzyreplodnik_kalinolistnyj_t3_h150_PREVIEW.png"]},
    10: {"match": "no-match", "reason": "generic genus Cornus (дёрен) only, no species",
         "candidates": ["deren_t1_h120_high.png", "deren_t2_h150_high.png", "deren_t3_h100_high.png",
                        "deren_t4_h120_high.png", "deren_t5_h100_high.png", "deren_t6_h80_high.png"]},
    13: {"match": "no-match", "reason": "no Hippophae (облепиха) in A101", "candidates": []},
    16: {"match": "exact", "reason": "exact species + cultivar Picea abies 'Nidiformis' (ель нидиформис)",
         "files": ["el_nidiformis_t1_h60_high.png", "el_nidiformis_t1_h60_low.png"],
         "previews": ["el_nidiformis_t1_h60_PREVIEW.png"]},
    "Ива": {"match": "no-match", "reason": "Salix genus present (ива), no Salix helvetica (ива швейцарская)",
            "candidates": ["iva_polzuchaya_t1_h40_high.png", "iva_bush_t1_h150_high.png",
                           "iva_bush_t2_h50_high.png", "iva_lomkaya_t1_h450_high.png"]},
}

# The set of positions the match must cover: the missing + proxy rows of the species sheet.
def needed_rows():
    return [(pos, ru, sched, exact, kind, lo, hi, n, key, status, mid)
            for pos, ru, sched, exact, kind, lo, hi, n, key, status, mid in ROWS
            if status in ("missing", "proxy")]


def validate():
    rows = needed_rows()
    if len(rows) != 11:
        raise ValueError(f"needed rows {len(rows)} != 11 (missing+proxy)")
    if set(MATCHES) != {r[0] for r in rows}:
        raise ValueError(f"MATCHES keys {sorted(MATCHES, key=str)} != needed positions {sorted((r[0] for r in rows), key=str)}")
    for pos, m in MATCHES.items():
        if m["match"] not in ("exact", "exact-species", "no-match"):
            raise ValueError(f"pos {pos}: unknown match {m['match']!r}")
        if m["match"] in ("exact", "exact-species"):
            files = m.get("files", [])
            if not files:
                raise ValueError(f"pos {pos}: {m['match']} without files")
            unknown = [f for f in files if f not in A101_TEXTURES]
            if unknown:
                raise ValueError(f"pos {pos}: unknown A101 files {unknown}")
            for p in m.get("previews", []):
                if p not in A101_PREVIEWS:
                    raise ValueError(f"pos {pos}: unknown A101 preview {p!r}")
        for c in m.get("candidates", []):
            if c not in A101_TEXTURES:
                raise ValueError(f"pos {pos}: unknown candidate {c!r}")
        for v in m.get("variants", []):
            if v["file"] not in A101_TEXTURES:
                raise ValueError(f"pos {pos}: unknown A101 variant {v['file']!r}")
            if v["file"] not in COLOURS:
                raise ValueError(f"pos {pos}: variant {v['file']!r} has no colour measurement")
            if v["file"] not in COPIED_SHA256:
                raise ValueError(f"pos {pos}: variant {v['file']!r} is not in COPIED_SHA256")
            if v["label"] != COLOURS[v["file"]]["label"]:
                raise ValueError(f"pos {pos}: variant {v['file']!r} label {v['label']!r} != measured "
                                 f"{COLOURS[v['file']]['label']!r}")
    # colour table self-consistency: each measured label is derived from the recorded mean RGB, and every
    # measured colour is bound to a copied (sha256-listed) file
    for fname, c in COLOURS.items():
        if fname not in COPIED_SHA256:
            raise ValueError(f"COLOURS {fname!r} is not in COPIED_SHA256 (colour not bound to a copy)")
        want = label_from_rgb(c["mean_rgb"], c["red_gt_green"])
        if c["label"] != want:
            raise ValueError(f"COLOURS {fname!r} label {c['label']!r} != label_from_rgb {want!r}")
    if GENERIC_PUZYREPLODNIK_COLOUR["label"] != label_from_rgb(GENERIC_PUZYREPLODNIK_COLOUR["mean_rgb"],
                                                                GENERIC_PUZYREPLODNIK_COLOUR["red_gt_green"]):
        raise ValueError("GENERIC_PUZYREPLODNIK_COLOUR label does not match its mean RGB")
    # every exact/exact-species file + preview is copied and hashed; the hash list covers exactly those files
    exact_files = sorted({f for m in MATCHES.values() if m["match"] in ("exact", "exact-species")
                          for f in m.get("files", []) + m.get("previews", [])})
    if exact_files and set(COPIED_SHA256) != set(exact_files):
        raise ValueError(f"COPIED_SHA256 {sorted(COPIED_SHA256)} != exact files {exact_files}")


def records():
    validate()
    by_pos = {r[0]: r for r in needed_rows()}
    out = []
    for pos in sorted((p for p in MATCHES if isinstance(p, int)), key=int):
        pos, ru, sched, exact, kind, lo, hi, n, key, status, mid = by_pos[pos]
        m = MATCHES[pos]
        out.append({"pos": pos, "russian": ru, "exact_latin": exact, "status": status,
                    "a101_match": m["match"], "reason": m["reason"],
                    "a101_files": m.get("files", []), "a101_previews": m.get("previews", []),
                    "a101_candidates": m.get("candidates", []), "a101_variants": _variants(m)})
    if "Ива" in MATCHES:
        pos, ru, sched, exact, kind, lo, hi, n, key, status, mid = by_pos["Ива"]
        m = MATCHES["Ива"]
        out.append({"pos": "Ива", "russian": ru, "exact_latin": exact, "status": status,
                    "a101_match": m["match"], "reason": m["reason"],
                    "a101_files": m.get("files", []), "a101_previews": m.get("previews", []),
                    "a101_candidates": m.get("candidates", []), "a101_variants": _variants(m)})
    return out


def summary(recs):
    exact = [r for r in recs if r["a101_match"] == "exact"]
    exact_sp = [r for r in recs if r["a101_match"] == "exact-species"]
    nomatch = [r for r in recs if r["a101_match"] == "no-match"]
    gaps = [r["pos"] for r in nomatch if not r["a101_candidates"]]
    return {
        "rows": len(recs), "exact": len(exact), "exact_species": len(exact_sp),
        "no_match": len(nomatch), "no_candidates": len(gaps),
        "gap_positions": [str(p) for p in gaps],
        "udim_tile": 1002,
    }


MD_HEAD = """# Vatutino Flora — A101 match table (route A step 2, #1146)

Artem 2026-11-09: do not generate new maps first — match the 11 needed pairs (7 missing + 4 proxies) against the
A101 Flora library on the Drive (`G:/Мой диск/AGR-assets/flora/a101/`), exact species only, and list the remaining
gaps. Files are copied read-only and hashed; the Drive originals are never edited.

Source library (read-only): `TextureFlora/` 180 PNG (`<species>_t<N>_h<cm>_{high,low}.png`), `PreviewFlora/` 81 previews,
`FLORIO_221.max` (needs Max — not used here). Copied matches: `G:/Мой диск/AGR-evidence/1146-flora-star/a101-matched/` + `SHA256SUMS.txt`.

| Поз. | Exact species | A101 match | A101 files | Note |
|---|---|---|---|---|
"""


def render_md(recs):
    lines = [MD_HEAD.rstrip()]
    for r in recs:
        if r["a101_match"] in ("exact", "exact-species"):
            files = ", ".join(r["a101_files"]) or "—"
        else:
            files = ", ".join(r["a101_candidates"]) or "—"
        lines.append(f"| {r['pos']} | {r['exact_latin']} | {r['a101_match']} | {files} | {r['reason']} |")
    s = summary(recs)
    lines.append("")
    lines.append(f"Rows {s['rows']}; exact {s['exact']}, exact-species {s['exact_species']}, no-match {s['no_match']} "
                 f"({s['no_candidates']} with no A101 genus at all: {', '.join(s['gap_positions'])}).")
    lines.append("")
    lines.append("Copied (read-only, hashed): 11 files to `G:/Мой диск/AGR-evidence/1146-flora-star/a101-matched/` + `SHA256SUMS.txt` "
                 "(sha256 also committed in `flora-a101-match.json`). A101 PNGs are 2048×2048 RGBA — diffuse already cut out "
                 "(alpha = opacity); `high`/`low` are two variants, both 2048².")
    lines.append("")
    lines.append("G3 (UDIM): Ground v015 VPM = tile 1001 (single tile, D209/D210; `ground-build-v006.md` readback `tiles [1001]`); Flora goes to the next free tile **1002**.")
    lines.append("G4 (texel): measure VPM texel in the final atlas/UDIM, no upscaling (Artem «мерить»).")
    return "\n".join(lines) + "\n"


def write_outputs(md_path, json_path):
    recs = records()
    data = {"schema": 1, "source_library": "G:/Мой диск/AGR-assets/flora/a101/",
            "copies": "G:/Мой диск/AGR-evidence/1146-flora-star/a101-matched/",
            "udim_tile": 1002, "texel_policy": "measure in final atlas, no upscale",
            "copied_sha256": COPIED_SHA256,
            "rows": recs, "summary": summary(recs)}
    md_path.write_text(render_md(recs), encoding="utf-8")
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Match the 11 needed Flora map pairs against the A101 library (step 2)")
    ap.add_argument("--check", action="store_true", help="exit 1 when the committed md/json are stale")
    args = ap.parse_args(argv)
    md_path = HERE / "flora-a101-match.md"
    json_path = HERE / "flora-a101-match.json"
    if not args.check:
        write_outputs(md_path, json_path)
        print(f"wrote {md_path.name} and {json_path.name}")
        return 0
    recs = records()
    if not md_path.exists() or not json_path.exists():
        print("stale: flora-a101-match.md/.json missing", file=sys.stderr)
        return 1
    if md_path.read_text(encoding="utf-8") != render_md(recs):
        print("stale: flora-a101-match.md differs from the generator", file=sys.stderr)
        return 1
    committed = json.loads(json_path.read_text(encoding="utf-8"))
    if committed.get("rows") != records():
        print("stale: flora-a101-match.json rows differ from the generator", file=sys.stderr)
        return 1
    print("flora-a101-match.md/.json up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
