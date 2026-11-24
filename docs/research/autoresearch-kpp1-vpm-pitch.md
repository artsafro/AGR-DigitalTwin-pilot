# Standing #77 — VPM joint-pitch census specificity on a second object (KPP1, OBSERVE)

## Краткий итог (RU)

Проверяем, молчит ли метрика шага швов E72 (#72, подтверждена только на AC08: отклонённый v007 2.22, принятый v010 0.0016)
на втором объекте, который НЕ отклоняли: VPM КПП1 `_002`, переданный заказчику (приёмка 2026-11-14, D288).
Если метрика срабатывает на принятом объекте — она не годится в проверку без доработки. Только наблюдение,
производство и пакеты не меняются. Итог — в «Round log» ниже.

## Frozen contract (committed before the first score)

Confirm-vs-new budget: zero new metrics. The #72 census `pitch()` is loaded unchanged from Git object
`e9179247c4934756170f3db7c8e2e8fe36e05487:docs/research/vpm-joint-pitch-r72/replay.py`, `runs()` unchanged from
`01e48513aa9bba11553bc3c0c296414e7ba26c6d:jobs/TEC26-OKS/scripts/joint_count.py`. One candidate (E72 as is), exactly
three fresh rounds, no second candidate, no amendment after the first score is read.

Fixture (accepted control, not an Artem visual texture verdict): `G:/Мой диск/AGR-assets/KPP1/delivered-customer-2026-11-14/SM_77_05_0009005_117_002.zip`,
SHA-256 `caef3a21acdb8aee1fee9e496e26bd9f9adaeef2a17272e8189bb634aee13ecf` (matches the folder `SHA256SUMS.txt`), the
customer-delivered KPP VPM taken as reference in #1371 (`jobs/KPP1/delivered-1371/REPORT.md`, D288). Preflight hashes the ZIP
every round; every Diffuse member is decoded fresh from the ZIP each round.

Tile binding (the ZIP has one material and no finish names): a tile is bound to the `kind: full` finishes of
`01e48513:jobs/KPP1/scripts/vpm_textures.json` (unchanged since 2026-10-07, before the 2026-10-25 package) whose `rgb` equals
the tile's modal RGB exactly; all matching finishes must share `P[0]` and `S`, otherwise binding error (not measured). Only
4096 px tiles are candidates; 256 px tiles are solid placeholders (no texel requirement) and are `not_exercised`. A 4096 tile
without a binding is `not_exercised`.

Score per bound tile: E = |observed / expected - 1|, observed = `pitch()` (rows 25/50/75 %, dark < 0.8 x row median,
complete runs only, median pooled adjacent gap), expected = `P[0] * 4096 / S`. Fewer than 3 complete runs on a row ->
that tile not measured. E77 = max over measured tiles.

Hypothesis H77 (specificity): every measured bound tile has E <= 0.03 (the #72 accepted bound). Confirmed if all measured
tiles <= 0.03 in all three rounds and at least 3 tiles measured; refuted if any measured tile > 0.03 in a complete round set
with valid witnesses; otherwise inconclusive. Pre-registered expectation: cassette tiles (bars every 600 mm) and plinth
(300 mm) stay quiet; the perforated tile may fire (hole pitch is not the panel pitch) — if so it is the accepted control on
which the rule fires, reported as collateral, not hidden.

Witnesses (in memory, every round, every measured tile): half-pitch = columns `2*x % 4096` (#72 variant), expected E in
[0.45, 0.55] for tiles with clean E <= 0.03; brightness +8 RGB with saturation, |dE| <= 0.01. Changed-pixel counts are
recorded per tile and variant; a variant with zero changed pixels is `not_exercised`. Clean score is recomputed after the
variants to prove no mutation.

Budget/stop: three rounds; stop `budget_stop` (inconclusive) if the first round exceeds 30 s or the total exceeds 120 s.
Wall time and status recorded separately. Forbidden: threshold/row/dark tuning, rebinding after reading a score, editing or
re-exporting the delivered ZIP, other cards' files, deselecting tests. No keep: OBSERVE only, no production change.

Not measured here: AC08/NPM (#72/#73), MAF (#75/#76), Vatutino, Staropetrovskiy, KPP1 v004 drafts (no 4K textures), UV
placement, joint width, vertical pitch `P[1]`. Closed form research, G22 #1649, KPP1 #1817/#1818, Staropetrovskiy #1500,
MAF numbering #1809 not touched.

Replay from repo root: `uv run --frozen python docs/research/kpp1-vpm-pitch-r77/replay.py tmp/r77-NEW`
(needs Drive fixture above and the two pinned Git objects; replay limited outside this environment).

## Round log

- R1 (frozen harness, commit `da84071e` contract): first round 143.432 s > 30 s first-round limit -> `budget_stop`,
  **H77 inconclusive for R1** (one round, not three). The budget was frozen without a measured round (contract defect).
  Round-1 rows are preserved unchanged in `kpp1-vpm-pitch-r77/attempt-001.json` (committed LF blob SHA-256
  `c33e67d54f10eca5410c8f7ebc974a065d9fc676cc128522b19e89d77f57e1f6`) and are not used as evidence for the R2 verdict.
- Amendment A1 (committed before R2; implementation speed only): the modal colour for tile binding is computed with
  `np.bincount` over packed 24-bit RGB instead of `np.unique(axis=0)` (same argmax colour; ties resolve to the lowest
  packed value in both). Metric, census, binding rule, bounds, witnesses and budget limits (30 s / 120 s) unchanged.
  Parity proof: R2 per-tile `modal_rgb`, `finishes`, `expected_px` must equal R1 round-1 rows, otherwise R2 is void.
- R2 (harness at `ebb6448e`, A1): status `complete`, rounds 16.508 / 14.652 / 15.556 s (each < 30 s), total 46.716 s
  (< 120 s). A1 binding parity vs R1: true; every per-tile row of R2 round 1 is byte-equal (JSON) to R1 round 1; rows
  identical across all three rounds, spread 0.
  - Measured 5 bound 4K tiles; 10 x 256 px solid placeholders and tile 1015 (modal RGB 144/146/148, no `full` finish)
    `not_exercised`.
  - 1001 Plinth_RAL7004 300 -> 300 px, E 0; 1005/1007 Cassette_RAL5015(_Top) 600 -> 600 px, E 0; 1006 Cassette_RAL7047
    600 -> 600 px, E 0. Half-pitch witness exercised on all four (E 0.5, in [0.45, 0.55]); brightness +8 exercised
    (16 777 216 px changed per tile), dE 0.
  - **1008 Perforated_RAL9016: expected 600 px, observed 120 px, E 0.8 > 0.03 -> flagged on an accepted tile.** Runs per
    row 7 / 41 / 7: rows 25 % and 75 % see the 600 mm panel joints, the 50 % row crosses a perforation-hole row; the
    pooled-gap median is then the hole pitch (6 + 6 + 40 gaps). Brightness +8 dE 0; half-pitch E 0.9 (bound not
    applicable, clean already out of bound).
  - **H77 refuted** (OBSERVE): E72 unchanged is not specific on a second accepted object; E77 median 0.8, 1 of 5 measured
    accepted tiles flags (4/5 quiet, 0.0). The AC08 confirmation (#72) stands for plain vertical-joint panels only.
- Would change (not applied, new candidate needing its own frozen run): per-row median gap, then median over rows
  (here 600/120/600 -> 600, E 0), or restrict the census to finishes with `pattern` in {cassette, tile300, panel};
  either must still score AC08 v007 >= 1.0 and v010 <= 0.03 before any gate. No keep, no PR to production code.
