# Standing #66 — AC08 4K texture density calibration (OBSERVE)

## Frozen contract before runner implementation and scoring

H66: density error relative to the documented AC08 panel recipe (1000 px/m, issue #559 comment 6341991856) separates the visually rejected v007 from the accepted v010 (comment 6345392389). This is an NPM version-to-version diagnostic, **not** a regulatory density requirement for NPM OKS. The 96.9 px/m in `npm_atlas.json` describes the planning atlas cell, not the 4K package tile; 96.9 × 4096 / 397 is approximately 1000. Neither texture phase nor joint count follows from area density alone.

- Reuse #65's fresh Blender `twinqa.scene.readback` and existing SINTEZ `_polygons`/`polygon_density`. No production patch or second geometry extractor. This is not V009. Inputs: delivered `SM_Nku_1.zip`, external `npm_atlas.json`, under `G:/Мой диск/AGR-evidence/559-tec26-oks-ac08-pilot-v007/` and `...-v010/`, exact pins below; no repack/export. v007 target ID 1001 (PanelVJ_RAL5015), v010 targets 1001/1002 (PanelVJ30/12_RAL5015). Include only recipe-declared textured IDs with decoded square 4096 Diffuse; verify all other recipe IDs bind decoded square 256 Diffuse and exclude from the statistic. Match faces to the tile by UV centroid, verify target corners remain in-tile. Require both v010 IDs and v007 ID to have measured, positive, nondegenerate samples. Exclude UCX/glass by kind names, not by score.
- Per target ID compute median polygon density (unweighted, reflecting the indexed export topology); single score `E66 = max_ID(abs(median_density/1000 - 1))`. Report each ID's sample count, median and range as evidence. Three fresh paired rounds with independent Blender imports; report median of 3 E66 and spread for each state and paired `E66(rejected) - E66(accepted)`. Require exact zero spread (deterministic same build/bytes). Calibration requires clean accepted E66 ≤ 0.02 and rejected minus accepted ≥ 0.02. Two pct points is an experimental minimum separation, not a new check threshold.
- Positive witness and exercised accepted control: on both versions, contract every target polygon's UVs around its own centroid by factors 0.75 and 0.50 in fresh readback memory only. Require every target face changed, no non-target changes, no tile membership change, and signed median density ratios equal the factor ±1e-8 per ID (differential control, independent of clean result). Clean state changes zero by definition. Report per-ID changed faces and loops. Any zero-change injection is `not_exercised`, not measured. Check parity on in-memory original facts and hashes of ZIPs, plans, Blender executable and reference code before/after.
- Verdict: confirmed only if full parity, coverage, witness, stability and clean separation all hold; refuted if parity, coverage, witness and stability hold, but clean separation or accepted error fails; inconclusive if inputs, applicability, parity, witness, stability or run budget prevent the series. Zero production keep rounds. Budget: one first measured pair, then two confirmation pairs only; no tuning or new candidate; 60 s first-pair cap, 240 s total, require remaining >= twice measured first pair + 15 s; otherwise inconclusive/budget stop; replay same command in fresh directory in an idle slot. No shortcuts: no editing delivery/other cards' files, weakening standards/checks, deselecting tests, silent coverage drops, or repeated scoring of one dump as independent imports.
- Not taken: #58/#64 general render mean gave wrong ordering; #63 phase and #65 padding are separate signals. KPP1 #1817/#1818, Staropetrovskiy #1500, G22 #1649, MAF numbering #1809 are distinct lanes; no verified labelled density pairs for KPP1/Vatutino/Staropetrovskiy in this run, so no portability claim. Do not reopen form. Readiness report 2026-11-24 13:45: tracked blockers are #1507/#1608 and KPP1 #1817/D377.

Replay: `uv run --frozen python docs/research/atlas-texel-r66/replay.py tmp/r66-run-NEW` (limited: Windows, pinned Blender 5.1.2, and Drive permissions). Reference code and `uv.lock` must equal revision `e2d480997b452f03af3f37d54f6b5cc2122bcd06`; replay and receipt pinned by branch commits. Snapshot SHA-256:

| Asset | SHA-256 |
| --- | --- |
| v007 ZIP | `271ee11bf78200ef883814a4ac108ef289098d0f106da01e8d9fc57da888c295` |
| v010 ZIP | `2fe983791566477e297aeefa09f04a1b7d176312c3fce1a8c9f1cf26138013bb` |
| v007 planning JSON | `9feb8685a71dec4cd2bb746bd3695bccdce3e648199dc0f32cb3738f6c430ea2` |
| v010 planning JSON | `338edcd767c0c6c99f762d4b7a9dcfd9407da030086ccb5b96e551d3bffae0cc` |
| Blender executable | `1e6624af112b3c936f4b038b025ebd2bf00ae72c4b62881a6787166d71c58fa5` |

## R1 — refuted; completed, OBSERVE only

**Итог:** плотность не отличила отклонённую v007 от принятой v010: на обеих версиях около 1000 px/m по всем проверенным 4K ID. Проверка видит искусственное изменение масштаба UV, но не заменяет проверку количества, шага и фазы швов. Не включать этот сигнал как порог приёмки АС.08; пакеты и производственный код не менялись.

Three fresh pairs (3.469 / 3.037 / 3.037 s; total 9.869 s). Clean E66 v007 = `4.07612e-8`, v010 = `5.29454e-8`; median paired rejected-minus-accepted = `−1.21841e-8`, spread 0. The accepted bound passes and the required separation fails (the rejected score is numerically lower). All six state scores have spread 0. Clean density on each of the three IDs is within 0.001 px/m of 1000, including the observed per-face extrema.

| Version / textured tile | Clean faces; median px/m | Changed faces / UV loops at each factor | 0.75 / 0.50 median px/m |
| --- | ---: | ---: | ---: |
| v007 / 1001 | 38; 1000.000041 | 38 / 114 | 750.000031 / 500.000020 |
| v010 / 1001 | 30; 1000.000053 | 30 / 90 | 750.000040 / 500.000026 |
| v010 / 1002 | 8; 999.999983 | 8 / 24 | 749.999987 / 499.999992 |

Per version, 348 faces on three 256 px IDs were excluded and unchanged; they are **not measured** for density. Clean changes were zero for every measured ID. Injected states were exercised on both labels; their reported results are on readback arrays, not evidence of a native export after injection. Pinned input hashes and reference-code parity held after the run. [Machine receipt](atlas-texel-r66/receipt.json) retains round-level results, FBX member and runner hashes. Same command for idle-slot replay if the frozen timing condition stops a later run. No KPP1/MAF/Staropetrovskiy, VPM, padding/bleed or seam measurement in R1.

RED (research-only tests before runner): import missing (`ModuleNotFoundError: replay`); no production regression was in scope. Affected tests: `uv run --frozen python -m pytest -q --import-mode=prepend docs/research/atlas-texel-r66/test_replay.py tests/qa/test_sintez_uv_1732.py tests/qa/test_texel_metric_divergence.py` — 53 passed. Pilot guards: `bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh` — GREEN, 553 passed. Full suite: deferred to merge batch (rule 68); no merge requested.
