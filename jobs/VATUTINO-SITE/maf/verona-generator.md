# Vatutino «Верона» benches — MAF generator gen-v001 (#790, model-maf step 3)

Status: **stage 1 of 3** — plan shapes, section table and the pure generator are done; module reference,
rows 6–10 mapping and heights wait for Artem (questions below). No FBX is produced yet.

## Plan shapes (`verona-plan-shapes.json`)

Source: copy `C:/x/vatutino-maf/v001/src/main.dwg` (sha256 `64e22677…46e4`, same as the original recorded in
`site-schedule.md`; the original was not opened) -> DXF copy (sha256 `88ff8730…0ed9`) -> `ezdxf`. The schedule
says «DWG block —», but the benches are drawn as blocks on layer `!_А101_маф`, each one LWPOLYLINE outline + one
HATCH. Inside plot `568BF` there are exactly 10 bench inserts for the 10 rows.

| Row | Schedule L×W×H mm | Block (insert handle) | Polyline handle | Generated plan m | Deviation m | Status |
|---|---|---|---|---|---|---|
| 1 | 2500×3900×600 | Скамья индивид общ отд 2 (`18AA78`) | `18AA77` | 3.919 × 2.501 (L) | 0.019 / 0.001 | found |
| 2 | 2500×6700×600 | Скамья индивид общ отд 1 (`18AA68`) | `18AA67` | 6.699 × 2.500 (L) | 0.001 / 0.000 | found |
| 3 | 6250×600×— | Скамья верона (`132D24`) | `132D23` | 6.250 × 0.600 (straight) | 0.000 / 0.000 | found |
| 4 | 5800×2900×600 | скамья индивид под андромедой (`195E1A`) | `195E19` | 5.800 × 2.896 (U) | 0.000 / 0.004 | found |
| 5 | 6080×600×— | Скамья верона 2 (`132D32`) | `132D31` | 6.085 × 0.600 (straight) | 0.005 / 0.000 | found |
| 6–10 | 4960×5530×600 (all five) | candidates: пл. дети1-3лет (`18AA61`, 4.957 × 5.526, 5 turns of ~45°), лестн 1 ×2 (`19865D`, `19865E`, 2.0 × 0.6), лестн 2 (`198ADB`, 4.921 × 0.6), лестн 2.1 (`198BAC`, 4.249 × 0.6) | — | — | — | question |

Each block has a second insert outside `568BF` (the drawing repeats the site); those are listed, not used.
Method: centreline = the outer (longer) side of the drawn strip offset inward by 0.3 m (drawn inner sides and end
caps are skewed by up to 0.45 m; the outer legs carry the schedule sizes). The third schedule value «600» equals
the drawn seat depth of every outline, so it is read as depth, not height: **every row's height is `review`**.

## Section table (library analogue `MAF_0326`)

Analogue: `MAF_0326` (steel-loop legs + seat board + back panel; already used for `*T3510/1`), FBX
`C:/x/t_3e6ff1b3/library/fbx/MAF_0326_…_006.fbx` read in a factory Blender 5.1.2 (per connected part bbox;
`C:/x/vatutino-maf/gen-v001/probe/m0326.py`, exit 0; FBX sha256 identical before/after). Values Artem
disputes are changed only by him.

| Generator value | Catalogue id | Measured | Proposed |
|---|---|---|---|
| `seat_top` (seat height) | MAF_0326 | seat top 0.4465 − lowest −0.0196 = 0.466 m | 0.466 |
| `seat_thickness` | MAF_0326 | seat part z 0.3815..0.4465 = 0.065 m | 0.065 |
| `post` (leg tube section) | MAF_0326 | leg parts 0.0437 / 0.0391 / 0.0410 m thick | 0.040 |
| `post_inset` (leg from seat side) | MAF_0326 | leg frame 0.4417 under seat 0.4566 -> 0.0075 m | 0.0075 |
| `end_overhang` | MAF_0326 | seat end to leg centre 0.336 / 0.335 m | 0.335 |
| `max_leg_span` | MAF_0326 | leg centres 1.130 m apart | 1.130 |
| `depth` | DWG outlines (not the analogue) | 0.600 m in all ten outlines (MAF_0326 seat is 0.457) | 0.600 |
| board width, slat pitch | MAF_0326 | not measurable: solid seat, no slats | question |
| backrest | MAF_0326 | back panel 1.408 × 0.049 × 0.445, top 0.80 | question (depends on «Верона») |

## Generator

`tools/library/maf_gen_bench.py` (pure, no bpy): plan run + sections + material IDs -> one welded quad mesh
(posts let into the seat bottom as inserts, closed manifold, xView-clean, pivot bbox centre / Z 0, longest
segment on +X, plan rotation recorded). `centreline_from_outline` turns a DWG strip outline into the run.
Tests: `tests/test_maf_gen_bench.py` (synthetic straight / L / U / skewed runs). Next stage: the Blender writer
next to `tools/blender/maf_site_set_build.py` (smoothing by angle, v005 material IDs, 512 slots, NPM/VPM FBX,
readback, `maf_findings`, `inv_xview`) for row 1 only, after the answers.

Budget note: `site-maf-set.md` already counts NPM MAF 57 628 of the 60 000 share [D097]; the ten Verona rows add
5 176 triangles with the proposed sections (10 inserts; row 1: 516), so the budget table will need Artem's split [D167].
