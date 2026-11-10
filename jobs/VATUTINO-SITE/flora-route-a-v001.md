# Vatutino Flora route A — run v001 status (#1146, [D232])

Route: `docs/plans/flora-426-route-2026-11.md`. Status: **stopped at the step-2 gate (Artem)**; `passed=false`.
Evidence (outside git, rule 57): `G:/Мой диск/AGR-evidence/1146-flora-star/` + `SHA256SUMS.txt`
(51 files; `star-v001/report.json` sha256 `fa92b860…2edd86d7`, `step1-approved-maps-sheet-v001.png` `2a8093e0…30870e5b`,
`maps-plan-v001.json` `98ca45e6…df863e3246`). Local copy `C:/x/ev_t_d9171ddc/`.

| # | Step | Done-criterion (route) | Result v001 | Status |
|---|---|---|---|---|
| 1 | Species sheet | 18 rows, exact Latin, map `approved`/`missing`, chosen source | `flora-species.md/.json`: 18 rows, 4,915 plants (105 trees, 4,810 bushes); approved exact 2 (11, 14), approved same species 5 (1, 3, 12, 15, 17), proxy 4 (4, 6, 7, 9), missing 7 (2, 5, 8, 10, 13, 16, Ива) | done; F-questions to Artem |
| 2 | New map pairs | diffuse+opacity, binary ≥ 99 %, plant 80–95 % of frame; Artem «approved» per pair | A101 match table `flora-a101-match.md/.json` (Artem 2026-11-09: match against the A101 Drive library, no generation): 1 exact (16 «ель нидиформис»), 1 exact-species (9 «пузыреплодник калинолистный» — three colour variants t1 yellow 139/123/6, t2 dark red 97/67/65, t3 yellow-green 170/180/68; t2 = red candidate for 'Lady in Red'), 9 no-match; 11 files copied + sha256; gaps (2, 5, 8, 13 + proxies 4, 6, 7, 10, Ива, 9) for Artem | **waiting** (Artem approves the matches / decides the gaps) |
| 3 | NPM star builder | tests on synthetic maps; tree 8 / bush 6 tris; height within ±20 %; UV whole image 0–1 | `tools/flora/build_flora_star.py`; 11 stars from approved maps: tree 8, bush 6 tris; 11/11 height in band; FBX readback tris = built, 0 UV faces outside, 1 material each | done for 11/18 (7 wait for maps) |
| 4 | VPM = shell of the star | closed shell per plane; UDIM after Ground; texel 520–1706 px/m | 11/11 VPM: 12 tris per plane (tree 48, bush 36), every plane a closed 2-manifold, FBX readback 0 UV outside the tile; **G3: UDIM tile = 1002** (Ground v015 VPM = 1001, D209/D210); **G4: texel measured in the final atlas, no upscaling** (Artem «мерить») | partial: 7 species wait for maps |
| 5 | One 2048 site atlas | 1 atlas, UV in cells, pixel diff ≤ 2 % | not started: needs all 18 map pairs | waiting on step 2 |
| 6 | Placement v007 | 4,915 plants, 0 engine stops, NPM ≤ 70,000 | estimate 105 × 8 + 4,810 × 6 = **29,700** tris ≤ 70,000; not run | waiting on steps 2, 5 |
| 7 | FBX read-back QA | validate-delivery all pass | not run | waiting |
| 8 | Site package + SINTEZ | needs Max | not run (Max busy) | waiting |
| 9 | Visual acceptance | renders, Artem's words | not run | waiting |

Step 3 plane: the plant's opaque bbox + 1.5 % margin (D155: plane slightly larger than the plant), not the whole
image, so a readback bbox measures the plant (FLO-04); UVs are that rectangle inside 0–1.
The VPM shell is Blender-Solidify-like (front, back at 5 mm with flipped normals, rim), FLO-11 0.003–0.01 m.
`udim_tile` 1002 is now resolved (G3): Ground v015 VPM = tile 1001 (single tile, D209/D210), Flora VPM = 1002.
