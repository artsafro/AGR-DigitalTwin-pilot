# Standing #73 — NPM atlas joint pitch (OBSERVE)

Card t_b8ec6b71, branch `research/autoresearch-standing-73`, base `origin/main` 36d185ce. Continues #72 (t_82ef7ef0)
next target 1: the same source-bound pitch census, but on the delivered **NPM** 2048 atlas instead of the VPM 4K tiles.
Focus: NPM/VPM texture and atlas quality (Artem 2026-11-24).

## Краткий итог (RU)

См. раздел «Round log» ниже; заполняется только после замера. Контракт ниже заморожен до первого запуска.

## Frozen contract (before any measurement)

Confirm-vs-new budget: two prior loaders reused unchanged (#71 `load`/`crop` at `b105d8bc`, `runs` of
`jobs/TEC26-OKS/scripts/joint_count.py` at base `4288c54d`) and the #72 `pitch` census copied verbatim (rows at 25/50/75 %,
dark = `< 0.8 * row median` of summed RGB, complete runs only, >= 3 per row, median pooled adjacent centre gap). One new
diagnostic only, exactly three fresh paired rounds, no second candidate.

Fixture: TEC26 AC08 `T_Nku_1_001_Main_d_1.png` (2048 px NPM atlas) + `npm_atlas.json` + `SM_Nku_1.zip` from Drive
`G:/Мой диск/AGR-evidence/559-tec26-oks-ac08-pilot-<v>/`, v007 (Artem rejected: 600 mm panel pitch / seams) and v010
(visually accepted; not a package QA pass). The #71 hash preflight pins all three files per label (SHA-256 in #71
`PINS`, equal to each folder's `SHA256SUMS.txt`). External atlas = embedded FBX Video bytes for v007/v010 (#70 receipt
`atlas_embedded_byte_parity`); not re-proven here. Target finishes and source periods: `jobs/TEC26-OKS/AC08/vpm_textures.json`
at base `4288c54d` (`PanelVJ30_RAL5015` P 0.195316833 m, `PanelVJ12_RAL5015` P 0.186277667 m, S 4.096 m).
Region binding: v010 regions of the same names; v007 has one shared patterned finish `PanelVJ_RAL5015` (udim 1001, region
origin u0 0.0029296875) used for both targets, same rule as #72 R2; `Panel_RAL5015` (solid, `px_per_m` null) excluded.
Every bound region must have `px_per_m` 96.9 and the 397 px region of a 2048 atlas.

Score E73 = max over the two targets of `|observed_px / expected_px - 1|`, `expected_px = P * region / S`
(18.93 / 18.05 px). Command: `uv run --frozen python docs/research/npm-atlas-pitch-r73/replay.py tmp/r73-NEW`
(writes `receipt.json`). Each round re-reads and re-hashes the Drive bytes and decodes the PNG again (no frozen dump).

Hypothesis H73: the #72 VPM ordering survives on the NPM atlas. Expected: accepted v010 E73 <= 0.05 (wider than #72's
0.03: 397 px region, LANCZOS-resampled 1.5 px joints, integer-ish centres), rejected v007 E73 >= 1.0 (600 mm -> 58.2 px
vs 18.9). Confirmed: those bounds on the medians, every paired difference > 0, median paired difference >= 0.95,
paired range <= 0.01, witnesses valid. Refuted: complete series with valid witnesses that contradicts ordering/bounds.
Otherwise (preflight, unreadable row, < 3 complete runs, budget stop, witness out of bound) inconclusive / not measured.

Positive trigger witness (in memory, both labels): region columns `2*x % 397` (half pitch). Accepted control must cross
its bound: v010 E73 in [0.45, 0.55]; rejected v007 expected in [0.50, 0.70] (29.1 px vs 18.05 -> ~0.61, not a gate).
Illumination control: +8 RGB levels with saturation; record changed pixels per region; |E change| <= 0.01.
Clean score is recomputed after both variants and must be identical (no mutation). Unchanged inputs/regions are labelled
`not_exercised` and reported as not measured.

Budget: core 60 s; after the first paired round stop `budget_stop` if it took > 20 s; never start a round after 60 s.
Wall time and status recorded separately. A budget stop is inconclusive for this run, not a hypothesis result.

Keep threshold: none (OBSERVE). Even if confirmed: candidate diagnostic only, no gate, no production change, no PR to
delivery code. Forbidden: RGB tuning, image alignment, dynamic threshold fitting, tolerance relaxation, test deselection,
new exports, edits to delivered bytes or to other cards' files.

Not measured (no byte-bound label pair on Drive for this lane): KPP1 v004, Vatutino MAF, Staropetrovskiy MAF. Not this
lane: G22 #1649, Staropetrovskiy #1500, KPP1 #1817/#1818, MAF numbering #1809, closed form research. Joint width,
visibility, UV placement and renders are not covered.

## Round log
