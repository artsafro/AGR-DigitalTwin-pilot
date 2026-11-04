# Ground v015 route A session (2026-11-04) — technical QA done, visually accepted by Artem

Card t_e35c49dd, issue #371, route A approved by Artem 2026-11-04 («принимаю рекомендации») and
recorded as [D193]. Branch merged `origin/main` first (ea1dad8); branch decision ids D169/D170 clashed
with TEC26 rows on `main` and became D191/D192 (D189/D190 are reserved by PR #803).

## Re-measure on merged code

- The D150 reference surface (`tmp/d150-original-surface-v001.npz`, ignored) was recreated by
  replaying `build_ground.py` on the v014 inputs (`--snap 0.003 --gap-exceptions ...`): fingerprint
  `26a646d3…5f41` equals `ground-gap-exceptions.json` `surface_sha256`.
- `build_ground_v015.py` (same command as v009, out `C:/x/t_e35c49dd/ground-v015-build-v010`):
  exit 0, 7 m 59 s. Both masters are **byte-identical** to v009
  (NPM `c26b7feb…ca1a`, VPM `59310ac9…2eb4`), so every v009 CPU number stays valid
  (relief 9.966668 mm, contours 2.2 mm, v014↔v015 sampled distance 6.047 mm max, 0 samples > 10 mm).

## Quads and triangle reasons per slot (v014 → v015)

v014 is 46,343 triangles, 0 quads (both profiles). D129 odd/pole and other residual counts are in
`ground-v015-texel-contract-checkpoint.md` (unchanged masters).

| Slot / fixed ID | v014 tris | NPM quads / tris | VPM quads / tris |
|---|---:|---:|---:|
| CurbGarden / 1 | 9,844 | 4,703 / 426 | 4,703 / 426 |
| FlowerBed / 2 | 134 | 48 / 38 | 44 / 46 |
| Gravel / 3 | 618 | 208 / 202 | 193 / 232 |
| LawnReinforced / 4 | 1,311 | 467 / 377 | 432 / 447 |
| LawnRolled / 5 | 2,088 | 668 / 752 | 643 / 802 |
| Mulch / 6 | 3,263 | 1,112 / 1,039 | 1,049 / 1,165 |
| Pebbles / 7 | 291 | 76 / 139 | 71 / 149 |
| Skirt / 8 | 3,578 | 1,798 / 89 | 1,798 / 89 |
| Stairs / 9 | 100 | 64 / 8 | 64 / 8 |
| TileDark / 10 | 509 | 214 / 81 | 214 / 81 |
| TileLight / 11 | 21,603 | 8,438 / 4,732 | 7,947 / 5,714 |
| TileRed / 12 | 3,004 | 1,187 / 630 | 1,154 / 696 |
| **Total** | 46,343 | **18,983 / 8,513 (30.96 % tris)** | **18,312 / 9,855 (34.99 % tris)** |

## xView

| Measurement | NPM OV / OF | VPM OV / OF |
|---|---:|---:|
| v014 masters, ours (`xview_overlaps`, main code) | 0 / 222 pairs | 0 / 222 pairs |
| v015 masters, ours | 0 / 0 | 0 / 0 |
| v015 Blender FBX readback, ours | 0 / 0 | 0 / 0 |
| v015 **real xView, headless Max 2024.2.5, delivered .max opened in a fresh process** | **0 / 0** | **0 / 0** |

v014 offenders by producing step (pairs, both profiles identical; `tmp/classify_xview.py`):
148 Skirt/Stairs and 18 Skirt/Skirt (`add_skirt` curtains), 29 CurbGarden/Stairs and 12
Stairs/Stairs (`build_details` stair/curb intersection), 9 CurbGarden/LawnReinforced and 6
CurbGarden/Mulch (`build_details` curb bottom datum vs the `raise_steep_layers` raised covering).
v015 removes them by construction (skirt clipping, stair side walls conformed to risers `a621607`,
12 mm stair clearance, pairing); ours finds none.

Max receipts (`fresh-reopen.json`, `max-reopen.json`, geometry text identical in all of them):

| Run | NPM OV / OF | VPM OV / OF |
|---|---:|---:|
| native-v001: import FBX → fixed IDs → save → reopen in the same process | 0 / 0 | 0 / **2 faces** |
| native-v001 fresh process, `fresh-reopen.json` | 0 / 0 | 0 / 0 |
| diagnostic v001 (fresh process; poly, Editable Mesh copy, tol 0.004 / 0.003) | — | 0 / 0 each |
| diagnostic v002 (fresh process; 3 × OV-then-OF, 3 × OF alone) | — | 0 / 0 each |
| native-v002: same in-session procedure as v001, new folder | — | 0 / 0 |

**Non-reproducible flag (open risk, reported, not waived):** in one of thirteen VPM checks Max
selected faces 13429 and 13438 — `TileRed` level-1 strip quads 0.40 × 4.00 m at x ≈
−7677.1…−7677.5, y ≈ −15340…−15344 and −15352…−15356 (MSK77) — with no partner face. Ours finds
no partner with either diagonal of the quad or of any neighbour; the nearest non-adjacent face is the
`TileLight` level-0 face beneath at **5.92–5.93 mm** (> 5 mm). The same geometry gave 0 in the twelve
other checks, including the identical in-session procedure. The delivered-file receipt is the
fresh-process one; the flake and its witness stay in the PR.

## Material IDs (fixed order `ground-material-ids-v015.json`)

Max reopen and Blender readback agree with the master on every face (0 mismatches, 0 unused, 0
duplicate, 12 bitmaps, map identity checked in Max):

| Slot | ID | NPM faces | VPM faces |
|---|---:|---:|---:|
| CurbGarden | 1 | 5,129 | 5,129 |
| FlowerBed | 2 | 86 | 90 |
| Gravel | 3 | 410 | 425 |
| LawnReinforced | 4 | 844 | 879 |
| LawnRolled | 5 | 1,420 | 1,445 |
| Mulch | 6 | 2,151 | 2,214 |
| Pebbles | 7 | 215 | 220 |
| Skirt | 8 | 1,887 | 1,887 |
| Stairs | 9 | 72 | 72 |
| TileDark | 10 | 295 | 295 |
| TileLight | 11 | 13,170 | 13,661 |
| TileRed | 12 | 1,817 | 1,850 |

## Texel exception [D193]

`jobs/VATUTINO-SITE/texel_exception_v015.py` freezes and checks the enumerated list; committed lists
`ground-texel-exception-v015-{npm,vpm}.json` are bound to the master SHA-256. Live check on v010:
NPM 8,511 / cap 8,511, VPM 11,430 / cap 11,430, 0 unlisted, exit 0. Tests:
`tests/test_ground_texel_exception_v015.py` 18 passed.

## UCX, placement, review render

- UCX (VPM, Blender audit): 727 pieces, 8,904 triangles (D012 limit 15,000), 0 overlaps, gap min
  3.99 mm, model 46,479 triangles excluding UCX.
- Placement compatibility (#298 consumer `GroundIndex`): 5,189 queries, 5,110 hits, 79 missing —
  the same 79 as v014; no exceptions copied; #298 stays on v014 until acceptance.
- Oblique textured render of the NPM FBX viewed: no holes or untextured regions seen (visual
  review only, not acceptance).

## Artefacts (not committed)

`C:/x/t_e35c49dd/`: `ground-v015-build-v010/`, `ground-v015-dcc-v001/` (FBX, UCX, textured,
readbacks), `ground-v015-native-v001/` (Max .max + receipts), `blender-readback-v001.json`,
`v014-xview-offenders-{npm,vpm}.json`, `review-oblique-npm-v001.png`, logs.

## Next

1. Visual review done: accepted 2026-11-04 (see "User acceptance").
2. If Max ever repeats the TileRed flag, raise that strip by construction (no exception) and rerun.
3. #298 re-placement on v015 only after acceptance (79 misses equal v014).

## User acceptance (separate status)

Artem, 2026-11-04, after opening `371-ground-v015-npm.max`: «принимаю, сделано более-менее, задача
тяжёлая, в идеал не вывести, считай что принимаю». Ground v015 NPM and VPM (route A) are accepted
as is; no further polishing rounds. `pending.json` rows `#371` set to `ok` with this quote
(`tools/review/verdict.py`). Publication / #298 re-placement on v015 remain separate steps
(Vatutino order: MAF #889, Flora, then #298).
