# Body mesh quality — standing #19, where R3 penalises accepted 63B v007 (OBSERVE)

**Кратко.** Штраф R3 на принятом 63B v007 найден: это **100 %** горизонтальные четырёхугольники с углами
45°/135° — скосы углов плана на верхних и нижних гранях перекрытий (3 угла плана, отметки 23,55 / 26,7 /
39,3 / 42,45 м, патчи из 5 граней, 64 грани, 45,6 м²). По форме это правильный скос, версия принята;
сверка с проектным чертежом не делалась. Но у отклонённых
63B v001–v005 R3 ловит тоже горизонтальные грани — треугольники на тех же перекрытиях (100 % площади), у v006 —
горизонтальные косые четырёхугольники. Поэтому заранее заданный кандидат R4 (не считать горизонтальные грани)
снял ложный штраф v007 (4,293 → **0,000**), но убрал и весь выигрыш R3: худший отрыв снова **0,427** < 0,5
(63C v002/v001). Не принято. Оценка, построители и поставки не менялись (OBSERVE).

## Frozen contract (written before any measurement)

Continues #17 (`autoresearch-body-mesh-neighbours-r3.md`, immutable harness `6ae13568ca85bb3880e84f4f1a30f22f6c23a96d`)
and #18 (`autoresearch-body-mesh-holdout.md`, `789b2c895ae181ad098dbbd912c183a4393d6990`). R3 lowers the ACCEPTED
63B v007 by 4.29 points (local share 0.621, 84.332 → 80.039); #18 found no false drop on 63A v005 / G22 k2 and
left the v007 penalty unexplained.

**Metric (one number):** R3 false drop on accepted 63B v007 = median(R0) − median(variant) in score points, three
repeats on the retained #15 dumps `C:/x/ar15/r1/tmp/63B-v007.{1,2,3}/dump.json` (byte-content equal, SHA-256 in the
receipt). Baseline R3 = 4.293 (pinned #17 receipt `r3.json`).

**Step A — localisation (observation, no candidate).** Splice into the R3 candidate a read-only sink that exposes
R3's own `bad` set and edge-neighbour patches (no arithmetic change; the spliced score must equal R3 bit-for-bit,
and R3 must equal #17's 80.039). Report for v007: top 10 seed patches by local share (seed face, local share,
patch area, centroid, normal, corner angles), and the irregular area of all faces in patches with local
≥ 0.5 × max local split by class: `horizontal` (|n_z| ≥ cos 1°), `vertical` (|n_z| ≤ sin 1°), `sloped`
(other), and separately triangles. Same class split for the six rejected 63B versions (diagnostic only).

**Decision table (frozen; exactly one branch):**

| Dominant class of v007 worst-patch irregular area | Step B |
| --- | --- |
| horizontal quads/ngons ≥ 50 % | R4 = R3 with horizontal faces (\|n_z\| ≥ cos 1°, the core's `flat_deg`) excluded from `bad` (seeds and counted area); global share unchanged |
| vertical, sloped or triangles | no candidate this round; report the face groups for a design-source check |

**Step B keep threshold (in-sample + held-out, still OBSERVE):** v007 drop ≤ 0.500; worst accepted-minus-rejected
margin over the nine #13 pairs ≥ 0.500 at shifts (0,0,0) and (−5,7,11) m with identical scores across shifts;
drop on held-out accepted 63A v005 (`C:/x/ev_t_f55bc192/63A.dump.json`, from the #18 readback) and G22 k2 v002r1
(`C:/x/ev_1619/r7/k2_v002r1.mq.json`, SHA-256 `2e922754…431b`) ≤ 0.500; three repeats identical; report parity with
R0 outside `score`, `penalties.irregular_area_share`, `local_irregular_area_share` (#14 `canonical`); #14 clean
rectangle + reset and injected skew witnesses pass. A keep only licenses a separate PR on `mesh_quality_core`
after an independent labelled pair; nothing is applied here.

**Budget / stop rule:** one confirmation (R0 + R3 reproduce #17 for all 13 inputs at (0,0,0)), at most one new
candidate (R4, only via the table), zero retunes. Wall cap 30 min. Harness-mechanics failures: up to 3 different
repairs, each logged with its error. A valid negative result ends the round.

**Forbidden:** changing R3/R4 beyond the table, weights, zones, `irregular_deg`, inputs or dumps; editing
`tools/qa/mesh_quality_core.py`, body builders, delivered packages, test selection, or files of #1736/#1742
(builder / causes), #1739/#1751 (skeleton), #1722 (63B stage 2), #1649 (atlas), #1609 (KPP1), #1315/#1622
(cold runs), #1615 (suite). Distance-to-etalon on G22 k1 is not used (it rewards the rejection, #12).

Replay: `../../.venv/Scripts/python.exe docs/research/autoresearch-body-mesh-r3-localize-harness/localize.py C:/x/ar15/r1/tmp <out.json>`.

## Round log

Contract commit `ff115566` (before any measurement). Run 1 (04:13): harness failure, `FileNotFoundError
C:/x/ar15/r1/tmp/KPP1-v003-rest.1/dump.json` — KPP1 rest/corners share one FBX and #17 keyed the dumps by the
first key of a source. Repair 1 (mechanics only): reuse the first key's dumps per source path; dump SHA-256
are still asserted equal to the #17 receipt. Run 2: 04:20:27 → 04:23:39, 3 min 12 s, exit 0.

Receipt [`r19.json`](autoresearch-body-mesh-r3-localize-harness/r19.json), SHA-256
`d12443044428ceb621aef805114d330aba60e52d9c1afc9d8be85dcee86dfb28` (LF, `-text`); harness `localize.py`
SHA-256 `e84c7bef192e1aa3f7a9a3295869d26a4d8e961bc6d976514e6f730340f160d7`.

Step A (confirmation + localisation, shift (0,0,0)): R0 and R3 reproduce the #17 receipt score-for-score on
all 13 inputs; the sink splice is neutral (spliced score == R3). Worst-patch irregular area (patches with
local ≥ 0.5 × max) by class:

| 63B version | label | faces | area m² | class |
| --- | --- | ---: | ---: | --- |
| v001–v004 | rejected | 448 | 338.06 | 100 % triangles (horizontal, e.g. seed 8591 at z 23.55, corners 35.8/82.2/62.0°) |
| v005 | rejected | 507 | 357.43 | 100 % triangles |
| v006 | rejected | 297 | 294.94 | 100 % horizontal quads (seed 10374, corners 71.8/180/72.7/35.5° — a degenerate quad) |
| v007 | accepted | 64 | 45.63 | 100 % horizontal quads, corners 45.5/45.5/134.5/134.6° at plan (69.0, 30.6), (75.9, 7.2), (78.8, 10.6) |

Decision: v007 horizontal share 1.0 ≥ 0.5 → branch R4 (R4 SHA-256 in the receipt).

Step B (R4, shifts (0,0,0) and (−5,7,11), identical): v007 drop **0.000** (≤ 0.5 ✓); holdout drops 63A v005
0.000, G22 k2 0.000 ✓; but R4 local share is 0 on every 63B/63C input, so every margin returns to R0:
worst **0.427** (63C v002/v001) < 0.500 ✗ → **keep = false**. Paired spread 0.000, three repeats identical.

Clean: #14 rectangle + reset witness, canonical parity outside the named fields, dump hashes equal to the
#17/#18 receipts. Injected: #14 skew witness passed for R3 and R4. Not measured: an independent labelled pair,
a clean curved/oblique envelope, fresh native readback, body builders, delivery QA.

**Would change (not applied, not measured):** the defect signal and the false penalty live on the same
horizontal slab caps; orientation cannot separate them. The separating feature is the corner itself: v007's
caps are regular 45°/135° chamfers, the rejected ones are triangles or degenerate quads (a 180° corner).
A next single candidate R5 = R3 with only horizontal *quads whose corners are all within 1° of a multiple of
45°* excluded from `bad`; keep criteria unchanged (v007 drop ≤ 0.5, worst margin ≥ 0.5, holdouts ≤ 0.5), and it
must then be checked on an independent labelled pair before any `mesh_quality_core` PR.
