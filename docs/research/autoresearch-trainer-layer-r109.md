# Autoresearch #109 — does the 63B Revit FBX carry wall-layer evidence for the bounds residual? (OBSERVE)

**Кратко (RU).** Продолжение #108 (next 1): прежде чем строить правило «оставить несущий слой» для остатка
Xmax +0,20 м на 63B, проверяем, есть ли вообще в исходном Revit FBX площадки 63 сведения о слоях стен,
привязанные к строкам стен. Это проверка достижимости источника, а не правило для `bounds`. Итог — в «Result».

Status: **contract frozen at `94fa9d86` before the frozen series; series complete.** Hypothesis result: **confirmed**
(see "Result"). Review readiness is separate.

## Focus and exclusions

- Ledger `7762dcfe2e78219155461bb633faaca2015e259b:docs/trainer/ledger.json` (= origin/main at start): 4 rows,
  first failing step `artifact` 3/4, `sources-dwg` 1/4. #100 recovered stored artifacts; #104–#108 carried the next
  stop, `bounds` on 63B (S107 Xmax +0.2002 m). #108: dropping the whole `Вентфасад 250` family fixes Xmax but breaks
  Ymin; its next target is "a source type/layer schedule or Revit wall compound structure tied to the 63B row IDs".
- Not duplicated: #1866 (DWG integrity), bank owner #1855/#1861 (task scope, 63B band/datum), #1928 (G22 adapter),
  #1924/#1927 (A/B method). Form research closed; atlas fallback inactive while the ledger exists.

## Exploration before freezing (not evidence, recorded for honesty)

Done in `C:/x/ev_t_92ddc620` before this contract: (1) Blender 4.4 import of the source: every mesh has 0 material
slots; (2) Blender loose-part split of every `Базовая стена *` row inside the 63A/63B boxes and stated bands:
1 connected component per row (63A 1 513 rows, 63B 1 884 rows); (3) raw FBX: 0 `Material` objects, but 15 247
`LayerElementMaterial` arrays with 1–5 distinct per-polygon indices; 5 sampled wall geometries showed one index
covering the whole solid and another a single face (e.g. `Вентфасад +100 100 медь`: 2 polygons, zero thickness).
These looks shaped the hypothesis; the frozen series below re-measures them on the full population.

## Hypothesis H109

The bank source `STLB-04_RR_AR.fbx` carries **no wall-layer partition** that a source-only selector could use to drop
the outer 250 mm of the 63B facade walls: for every `Базовая стена Вентфасад 250 250 *` geometry (whole site, a
superset of the 907 63B in-band rows) the layer-evidence count is 0. Expected direction: 0 of N.

## Metric and command (frozen)

- **M109 (primary)** = number of geometries of family `Базовая стена Вентфасад 250 250 ` (raw FBX Model name prefix,
  whole file) with layer evidence, where a geometry has layer evidence iff any of:
  (a) ≥ 2 vertex-connected components (polygon-vertex connectivity of the raw index buffer);
  (b) ≥ 1 non-manifold edge (an undirected edge used by > 2 polygons = an internal layer interface);
  (c) a per-polygon material-index partition that is **closed by itself** (every edge used an even number ≥ 2 of
  times within the partition) and is not the whole geometry (= a layer solid).
  Reported with N (geometries in the family) and per-criterion counts, and the same table for every other
  `Базовая стена *` family (context, not a verdict).
- **M109-B (secondary, Blender)** = per tower, in-box in-band `Базовая стена *` rows with ≥ 2 loose parts in
  `layer_dump_blender.py` output (same objects as the pinned `revit-fbx-dump/1`); the Вентфасад 250 subset on 63B
  must be 907 rows (parity with #108's removed-row count) or the run is invalid.
- Command: `uv run python docs/research/trainer_layer_r109/replay.py tmp/r109-NEW <full variant commit>`
  (fresh, nonexistent folder inside the worktree). It verifies the source SHA-256 against the pinned r105 manifest
  (`95ae5adb…:docs/research/autoresearch-trainer-storey-band-r105.md`, row `STLB-04_RR_AR.fbx`, and the Blender
  executable row) before and after, runs the raw-FBX census 3 times (median of 3 + per-run result hash) and the
  Blender layer dump once (63 s measured), and writes `receipt.json`.

## Controls (frozen)

- **Positive trigger witness** (unit tests on the same functions): two closed boxes sharing an interface face
  (b fires), two disjoint boxes (a fires), the shared-interface pair with one material index per box (c fires: each
  partition is a closed layer solid). Each must be detected; otherwise the run is invalid.
- **Negative control**: one closed box with one face painted another material index (the explored Revit pattern) —
  must NOT be detected; a detector firing here is invalid.
- **Real-source control**: the same census over all `Базовая стена *` families. If any family has layer evidence,
  record it as the exercised real control; if none, real-source positive is **not_exercised** (synthetic only).
- Parity: M109-B Вентфасад 250 count on 63B = 907; S107 selection is not re-scored here (no key read at all).

## Verdict rule, budget, forbidden

- **confirmed** if all three census runs agree, witnesses/negative pass, N ≥ 907 and M109 = 0;
  **refuted** if M109 > 0 in all three (then a layer-aware selector is reachable — next card measures `bounds`);
  otherwise **inconclusive**. Review readiness is separate.
- Budget: one variant, three census runs + one Blender dump, ≤ 10 min wall; no follow-up variant in this card.
- Forbidden: reading any key / accepted package for this metric, changing the bank, scorer, thresholds, tests of other
  cards, delivered packages; no 3ds Max. OBSERVE: no selector or product change is proposed for adoption here.

## Result

**Итог (RU).** H109 **подтверждена**: в исходном Revit FBX площадки 63 нет данных о слоях стен. Из 1 210 геометрий
семейства `Вентфасад 250 250` ни одна не содержит слоёв: нет отдельных тел, нет внутренних граней между слоями и нет
замкнутых «слоёв» по индексам материалов. В 1 152 геометриях несколько индексов материала, но без имён (в файле
0 объектов Material), и в просмотренных образцах это окраска грани, а не слой. В Blender все 907 строк 63B в полосе и
все прочие стены обеих башен — по одному телу. Значит, правило «оставить несущий слой» по этому источнику
построить нельзя: остаток Xmax +0,20 м на 63B из геометрии источника не снимается. Толщину слоя дают только имена
типов (`250`, `200`, `135`, `+100`) — использовать их или нет, решают владелец банка или Артём, не этот цикл. Модели,
банк, скорер и пороги не менялись, ключ не читался.

Variant `94fa9d8639a0213cafd86715b0be67594d0c951e`, run `complete`, wall 106.15 s (census 10.56 / 10.14 / 10.14 s,
Blender dump 74.09 s). Pinned source and Blender SHA-256 matched the r105 manifest before and after.

| Check | Result |
|---|---|
| **M109** `Вентфасад 250 250` geometries with layer evidence (3 runs, median) | **0 / 1 210** (0, 0, 0); a 0, b 0, c 0; 1 152 multi-material |
| Census runs agree | yes, result SHA-256 `7cfc9efe…5e123be` ×3 |
| **M109-B** Blender in-box in-band rows with ≥ 2 parts | 63A 0 / 1 513; 63B family 0 / 907 (parity 907 ✓), other 0 / 977 |
| Real-source control (all 28 `Базовая стена *` families) | exercised for (a) only: 5 multi-solid geometries — `(В) СВ-1.1` 3, `(К) ЖБ-180` 1, `(Н) СН-3.2` 1; (b) and (c) real **not_exercised** |
| Synthetic witnesses (a/b/c) + painted-face negative | pass (`tests/research/test_trainer_layer_r109.py`, 5 passed) |

- **Clean:** census and Blender dump on the pinned source. **Injected:** synthetic layered/disjoint/painted
  geometries only (unit tests). **Not measured:** `bounds` itself (no selector built — none is reachable from this
  source), any key or package, other sources (a Revit schedule/RVT export with compound structure is not in the bank),
  welded-vs-unwelded effects on (b) (raw index connectivity equals Blender's; unwelded duplicates would hide (b)).
- Would-change (OBSERVE, owner bank #1855/#1861): if the layer split matters for the 63B key, the task must state it
  or the bank must add a source carrying compound structure (RVT/IFC/schedule). Do not infer thickness from the key.

Replay: `uv run python docs/research/trainer_layer_r109/replay.py tmp/r109-NEW 94fa9d8639a0213cafd86715b0be67594d0c951e`
(needs the pinned Drive source and Blender 4.4; replay limited otherwise).
[Receipt](trainer_layer_r109/receipt.json) Git-LF SHA-256 `e1570399b8dd8cb39e0658df8114c31ad1473fb873ec407984d240568068d01e`.
Evidence (receipt, layer dump, exploration scripts): `G:/Мой диск/AGR-evidence/1855-r109-layer/SHA256SUMS.txt`
(7 entries), SHA-256 `73159ad3d46c6277df4facef6b0668c96016bc1ec4a08beaeeca21fd436d7c1c`.

## Next targets

1. Bank owner decision (#1855/#1861): does the 63B key envelope include the `Вентфасад 250` system on +X but not on
   −Y? Only the task text can say it; the source cannot.
2. Type-name thickness as a source signal: count 63B faces whose residual matches the thickness in the extremal row's
   type name (`250`, `200`, `135`) — needs a decision that type names are allowed evidence.
3. Leave 63B bounds; move to the next ledger row once a fresh practice run lands (ledger still 4 rows since 11-25).

Affected tests: `uv run pytest -q tests/research/test_trainer_layer_r109.py tests/tools/test_trainer.py tests/test_trainer_inspect.py -p no:cacheprovider` — 110 passed, 1 warning (new controls: 5 passed).

Repo guards: `bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh` — GREEN, 563 passed, 1 warning.

Full suite: deferred to merge batch (rule 68)
