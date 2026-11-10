# Vatutino Flora route A — run v003 status (#1146, [D232], [D237])

Route: `docs/plans/flora-426-route-2026-11.md`. Status: **stopped at the step-9 visual gate (Artem)**; `passed=false`.
Script: `jobs/VATUTINO-SITE/flora_route_a.py all --run <dir>` (Blender part `flora_v007_blender.py`), offline only.
Evidence (outside git, rule 57): `G:/Мой диск/AGR-evidence/1146-flora-star/run-v003/` + `SHA256SUMS.txt`
(220 files, list sha256 `61de2cc4…2ce79d79`). Local copy `C:/x/ev_t_c9ff2af1/run-v003/` (+ `run-v003.log`).
Run v002 (same inputs) was discarded at the sheet: the two A101 maps are sheets with a side view **and** a top view,
v002 put both into the star cell (pos 9, 16 showed 3–4 plants per plane); v003 keeps only the side view
(`a101_side_view`, dropped 456,569 / 395,346 px of top view).

| # | Step | Result v003 | Status |
|---|---|---|---|
| 1–2 | Species sheet + maps [D237] | 18 map pairs: 2 A101 (9 t2, 16 `el_nidiformis`), 9 stand-in, 7 approved; inputs sha256 in `maps/maps.json` | done |
| 3 | NPM stars | 18/18: tree 8, bush 6 tris; height in band 18/18; FBX readback tris = built, 1 material | done |
| 4 | VPM shells | 18/18 closed planes, tree 48 / bush 36 tris, UDIM 1002, 0 UV outside the cell; **texel in the 2048 atlas 81–1,038 px/m, 16/18 below 520 [D097]** | open — see gate question |
| 5 | One 2048 atlas | 1 atlas `M_VATUTINO_Flora_1`, scale 0.2160, fill 77.4 %; opacity mismatch at cell resolution 0.0 % (vs full-res map 2.845 %) | done |
| 6 | Placement v007 on Ground v015 | 4,915/4,915 placed, 0 failed, 0 mismatches, sink 0.0999–0.1000 m, scene QA pass; NPM 29,700 tris (≤ 70,000 [D097]), VPM 178,200 | done (flora only, MAF FBX absent) |
| 7 | FBX readback | NPM + VPM v007 FBX 7400: 4,915 objects, 18 unique meshes, 1 material each, 0 UV outside the tile (1001 / 1002), 0 non-finite transforms | done |
| 8 | Site package + SINTEZ | not run | **waits-max** |
| 9 | Visual gate | `sheet/sheet-site-v007.png` (6 views), `sheet/sheet-species-v007.png` (18 × NPM/VPM, stand-ins in red) | **waiting for Artem** |

Texel per row (px/m in the atlas, `!` = below 520): pos01 81! 02 83! 03 103! 04 102! 05 124! 06 182! 07 182!
08 183! 09 141! 10 260! 11 261! 12 260! 13 267! 14 470! 15 1038 16 198! 17 502! Ива 543.
One 2048 atlas for 18 species (route step 5) and VPM texel 520–1,706 px/m (step 4, [D097]) cannot both hold; Artem decides.
Ground for placement: textured masters from `371-ground-v015-route-a-20261104/session-v001.zip` (sha256 checked).
Ива height 60–100 cm is assumed (not in schedule *T3509).
