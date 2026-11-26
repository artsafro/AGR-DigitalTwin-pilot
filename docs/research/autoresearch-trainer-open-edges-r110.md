# Trainer OBSERVE #110 — raw open edges versus exact-coordinate open edges

**Фокус (RU).** Проверяем, исчезает ли большая часть сигнала «открытые рёбра» из ревью #109 после точного сопоставления координат. Это проверка источника, не слоёв стен и не качества модели.

## Frozen contract

- Selection: origin/main ledger `7762dcfe2e78219155461bb633faaca2015e259b:docs/trainer/ledger.json` (Git blob SHA-256 `230eace1a0a434cb25091f449760d3895d5b7d169086a2f2ba049db88a8496a7`): scorer `artifact` 3/4, execution `sources-dwg` 1/4 (the #1855 comment and #1608 evidence). #100 recovered three stored artifacts, not fresh cold-run passes. The latest readiness blockers belong to other lanes. Do not duplicate DWG #1866, source workflow #1867, G22 #1928 or the closed form research. Bank owns scope; #110 does not continue the bounds selector or infer thickness.
- Source: `G:/Мой диск/AGR-evidence/1855-trainer-v0/bank/63a-stage1/STLB-04_RR_AR.fbx`, SHA-256 `2b4d0201d3d2454344bba263500363fcc528a322bd2702ece0fac38e39a158d7`. Reuse the raw FBX reader, wall family and edge helpers at `ca92876502dd89cacfe2e8d317e2f2ccdf9d76b5:docs/research/trainer_layer_r109/replay.py` (Git blob SHA-256 `e32b3a43b028d4dda3a4bc3a3593a0a96521d36238aaf60a4bda53a9bfd1d37f`). Retain exact XYZ only, within a single raw Geometry; no DCC, re-export, cross-object weld or distance tolerance.
- Metric M110: **count of target-family geometries** with at least one undirected edge incident once in raw polygon indices but with zero such edges after exact XYZ reindexing. Baseline = raw index identity. Candidate = representative index per exact finite XYZ triple, including signed zero equality; cyclic face ordering and every coordinate triplet preserved. Record open/multiplicity/collapsed-edge counts per geometry before/after (IDs and row counts), and other wall families separately as source context, not a held-out etalon. Zero-changed inputs are `not_exercised` for the transform. This counts edge incidence, not manifoldness, closure by geometry, a wall layer, or a repaired model.
- Parity: target denominator 1,210 and raw nonzero-open subset 148 (review r1/r2 of #109); all polygons retained, original vertex positions unchanged. Reject parity mismatches/nonfinite or invalid indexed data. Count collapsed edge occurrences and >2 edge incidences as collateral, not silently-welded successes; exclude from M110 any would-be recovered row with collapsed edges or an increase in >2 edge count.
- Frozen synthetic witnesses (computed each pair): closed unit tetrahedron with one face using exact duplicate indices (3 geometrical split seams, raw one-incidence count 6 → 0; no collapse or >2); same closed tetrahedron unmodified (0 → 0, no reindex); missing face plus exact split on a retained face (5 → 3 if one remaining shared edge splits, or 7 → 3 if two split; fixed case uses two); one shifted duplicate corner by 1/1024 along X (6 → 4, no collapse or >2). These exercise index splitting and real boundary preservation, not Artem's approval.
- Command: `uv run python -X utf8 docs/research/trainer_open_edges_r110/run_pair.py <full-variant-SHA> tmp/r110-NEW.json` (fresh output; run from repo root). Pin replay code at variant and verify source against SHA before the series, on each fresh read and after. For each of three fresh paired raw/exact censuses record wall, aggregate hashes, gains and spread. A completed first pair is confirmation only; if its elapsed time times two exceeds the remaining 180 s process budget, stop with an inconclusive partial receipt. Budget: three total pairs, zero new candidates. No repeated scoring of a frozen dump. No production KEEP under any outcome.
- H110 observational verdict: `confirmed` only if parity and controls pass for all 3 identical pairs and median M110 ≥ 74 (half of the 148 raw-open geometries). `refuted` if those checks pass and median < 74; otherwise `inconclusive`. Held-out accepted and rejected *model* checks and passage of the trainer failure are `not measured` under this diagnostic contract; no generalization or calibration claim. Do not change tests, tolerances, validators, delivered packages or read hidden keys.

## Result

**Итог (RU).** H110 **опровергнута для этого FBX**: точное совпадение XYZ не закрывает ни одну из 148 геометрий `Вентфасад 250 250` с открытыми рёбрами. Открытых рёбер осталось 2 628, ни один индекс угла полигона не изменился. Это исключает объяснение через точные дубликаты координат в этой выборке; не доказывает отсутствия слоёв, наличия дыр или пригодности обхода для `bounds`. Замена фильтра, качество модели и прохождение тренажёра не проверялись. Без KEEP и без PR.

| Check | Observation |
| --- | --- |
| Clean source, target family (1,210 geometries) | 148 → 148 with an edge of incidence 1; 2,628 → 2,628 edges; 0 changed corners, no additional high-incidence or collapsed edges. |
| Clean source, all wall families (9,118 geometries, includes target) | 683 → 683 with an edge of incidence 1; 0 changed geometries: native reindex `not_exercised`. |
| Injected exact split; split with missing face; shifted corner | Open edges 6 → 0, 7 → 3, 6 → 4; changed corners 3, 3, 2 respectively, with no collapsed or high-incidence edge. |
| Unchanged synthetic tetrahedron | 0 → 0; `not_exercised` for reindex. |
| Not measured | Active native positive/collateral controls, independent etalon, accepted/rejected scoring, trainer artifact or bounds pass. |

Run status `complete`, wall 38.186 s, pairs 12.950 / 11.824 / 12.450 s (median wall per pair 12.450 s). Gains `[0, 0, 0]`, median 0, paired spread 0. All row digests and control digests agreed. This refutes the narrow exact-duplicate mechanism, not approximate coincidences, nonconforming tessellation or missing surface.

Replay: `uv run python -X utf8 docs/research/trainer_open_edges_r110/run_pair.py 36b401bb8c17d8443eb96250d182401b504fc43b tmp/r110-NEW.json`. Fetch `origin/research/autoresearch-standing-109` if the pinned reader is missing. Replay is limited to lanes with the pinned Drive asset. The SHA-256 of the [receipt](trainer_open_edges_r110/receipt.json) is `5e65ee0aad3c969e4ea8b0c6e4add58a3a4d782f323bebf85262f211c2ab8cd4`. Per-geometry rows are in `G:/Мой диск/AGR-evidence/1855-r110-open-edges/geometry-rows.json.gz`; uncompressed SHA-256 `1c944c67f8f7dacec61b53d76a34fe95afea15d83ec11ca8a765d6a72c21e3ff`. The Drive `SHA256SUMS.txt` digest is `7ea6681289ae609c48b072606cf3c80be62515e94e1f1c3fb358ca2f5af5dc85`.

Next: let the bank owner bind an authoritative layer-bearing export or a per-face envelope instruction; use any new ledger row to reprioritize before running another 63B bounds round. If boundary analysis is later authorized, test collinear A–M–B versus A–B index seams before considering any distance weld, with an independently labelled active control and actual gap witnesses.

Affected tests: `uv run pytest -q tests/research/test_trainer_open_edges_r110.py tests/tools/test_trainer.py tests/test_trainer_inspect.py -p no:cacheprovider` — 111 passed, 1 basetemp warning; RED on raw-only implementation: 5 failed, 1 passed.

Repo guards: `bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh` — GREEN, 563 passed, 1 warning.

Full suite: deferred to merge batch (rule 68)
