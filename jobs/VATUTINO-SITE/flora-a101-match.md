# Vatutino Flora — A101 match table (route A step 2, #1146)

Artem 2026-11-09: do not generate new maps first — match the 11 needed pairs (7 missing + 4 proxies) against the
A101 Flora library on the Drive (`G:/Мой диск/AGR-assets/flora/a101/`), exact species only, and list the remaining
gaps. Files are copied read-only and hashed; the Drive originals are never edited.

Source library (read-only): `TextureFlora/` 180 PNG (`<species>_t<N>_h<cm>_{high,low}.png`), `PreviewFlora/` 81 previews,
`FLORIO_221.max` (needs Max — not used here). Copied matches: `G:/Мой диск/AGR-evidence/1146-flora-star/a101-matched/` + `SHA256SUMS.txt`.

| Поз. | Exact species | A101 match | A101 files | Note |
|---|---|---|---|---|
| 2 | Alnus glutinosa 'Laciniata' (RU name = Alnus incana, F5) | no-match | — | no Alnus (ольха) in A101 |
| 4 | Malus × purpurea 'Makowieckiana' | no-match | yablonya_t1_h350_high.png, yablonya_t2_h450_high.png | generic genus Malus (яблоня) only, no species/cultivar |
| 5 | Larix decidua 'Pendula' | no-match | — | no Larix (лиственница) in A101 |
| 6 | Amelanchier spicata | no-match | irga_lamarka_t1_h150_high.png, irga_lamarka_t2_h150_high.png, irga_lamarka_t3_h350_high.png, irga_lamarka_t4_h150_high.png | A101 = Amelanchier lamarckii (Ирга Ламарка), a different species; it is the current approved proxy |
| 7 | Crataegus laevigata 'Paul's Scarlet' | no-match | boyarishnik_t1_h150_high.png | generic genus Crataegus (боярышник) only, no species |
| 8 | Elaeagnus angustifolia | no-match | — | no Elaeagnus (лох) in A101 |
| 9 | Physocarpus opulifolius 'Lady in Red' | exact-species | puzyreplodnik_kalinolistnyj_t1_h150_high.png, puzyreplodnik_kalinolistnyj_t1_h150_low.png, puzyreplodnik_kalinolistnyj_t2_h150_high.png, puzyreplodnik_kalinolistnyj_t2_h150_low.png, puzyreplodnik_kalinolistnyj_t3_h150_high.png, puzyreplodnik_kalinolistnyj_t3_h150_low.png | exact species Physocarpus opulifolius (пузыреплодник калинолистный), three colour variants (mean RGB, opaque pixels alpha ≥ 128): t1 yellow (139/123/6), t2 dark red (97/67/65), t3 yellow-green (170/180/68). t2 is the red-leaved form — an exact-species red candidate for 'Lady in Red' (replaces the 'Diabolo' proxy). Generic puzyreplodnik_t1 (green 109/126/47) is also listed as a candidate. |
| 10 | Cornus sanguinea 'Anny's Winter Orange' | no-match | deren_t1_h120_high.png, deren_t2_h150_high.png, deren_t3_h100_high.png, deren_t4_h120_high.png, deren_t5_h100_high.png, deren_t6_h80_high.png | generic genus Cornus (дёрен) only, no species |
| 13 | Hippophae rhamnoides 'Hikul' | no-match | — | no Hippophae (облепиха) in A101 |
| 16 | Picea abies 'Nidiformis' | exact | el_nidiformis_t1_h60_high.png, el_nidiformis_t1_h60_low.png | exact species + cultivar Picea abies 'Nidiformis' (ель нидиформис) |
| Ива | Salix helvetica | no-match | iva_polzuchaya_t1_h40_high.png, iva_bush_t1_h150_high.png, iva_bush_t2_h50_high.png, iva_lomkaya_t1_h450_high.png | Salix genus present (ива), no Salix helvetica (ива швейцарская) |

Rows 11; exact 1, exact-species 1, no-match 9 (4 with no A101 genus at all: 2, 5, 8, 13).

Copied (read-only, hashed): 11 files to `G:/Мой диск/AGR-evidence/1146-flora-star/a101-matched/` + `SHA256SUMS.txt` (sha256 also committed in `flora-a101-match.json`). A101 PNGs are 2048×2048 RGBA — diffuse already cut out (alpha = opacity); `high`/`low` are two variants, both 2048².

G3 (UDIM): Ground v015 VPM = tile 1001 (single tile, D209/D210; `ground-build-v006.md` readback `tiles [1001]`); Flora goes to the next free tile **1002**.
G4 (texel): measure VPM texel in the final atlas/UDIM, no upscaling (Artem «мерить»).
