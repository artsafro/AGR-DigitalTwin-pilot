# Autoresearch #109 — does the 63B Revit FBX carry wall-layer evidence for the bounds residual? (OBSERVE)

**Кратко (RU).** Продолжение #108 (next 1): прежде чем строить правило «оставить несущий слой» для остатка
Xmax +0,20 м на 63B, проверяем, есть ли вообще в исходном Revit FBX площадки 63 сведения о слоях стен,
привязанные к строкам стен. Это проверка достижимости источника, а не правило для `bounds`. Итог — в «Result».

Status: **contract frozen before the frozen series** (commit of this file). Hypothesis result: see "Result".

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

(filled after the frozen series)
