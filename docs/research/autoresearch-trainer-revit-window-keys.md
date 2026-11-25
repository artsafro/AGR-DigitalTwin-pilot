# Standing #89 — trainer Revit window-family keys (OBSERVE)

**Кратко.** Чаще всего в ledger тренажёра падает `artifact` (3/4; `sources-dwg` 1/4 — у #1880). #88 показал, что
после открытия адаптера Revit→BodyPlan все 6 вырезок 63A/63B останавливаются на `no window objects: check --keys`:
ключи по умолчанию (`Окно`, `балконная дверь`) не встречаются в именах этой модели Revit. Проверяем один вариант:
ключи окон по правилу именования семейств самой модели (`Окн_Окн_` — окна, `Окн_ББлок_` — балконные блоки;
ячейки витражей `Окн_Вит_` исключены явно), передаваемые штатным `--keys`, без изменения кода и допусков.

## Frozen contract (written before any r89 measurement)

- Ledger `docs/trainer/ledger.json` @ `08015022acc2a140994eeb188444f68a4388c15c`: 4 rows, first failing step
  `artifact` 3/4 (KPP1/G22/63A), `sources-dwg` 1/4 (#1608 r2). Owners skipped: #1880/#1874 DWG, #1889 Gate 1
  practice approval, #1901 tower map, #1859/#1877 practice isolation, #1861 bank. Form closed; atlas fallback
  inactive (ledger rows exist). This card continues the #88 harness (`research/autoresearch-standing-88@163b5505`),
  it does not start a new one.
- Code pinned at `08015022` exactly as in #88 (adapter `floor_from_dump.py`, cropper `revit_floor_dump.py`,
  `module_build.py`, `body_lattice.py`, `BodyPlan.schema.json`); cropper import call replaced by Blender 5.1.2
  built-in `bpy.ops.wm.fbx_import` exactly as #88 environment repair 2 (the legacy importer crashes 6/6 in #88).
  Inputs: the #88 pinned site FBX (`2b4d0201…a158d7`) and tower map `boxes63.json` (`e8a41981…d987e7`).
- **One variant, zero further candidates:** `trainer-revit-intake-r89/keys63.json` =
  defaults for `walls` and `baskets` unchanged, `windows = ["Окн_Окн_", "Окн_ББлок_"]`. Derivation: Revit
  object names in this model are `<Family> <Type> [ElementId]`; family names carry the category prefix `Окн_`
  (Windows) and a family-kind token: `Окн_Окн_` (type marks `ОК-…`, a window = default key `Окно`), `Окн_ББлок_`
  (type marks `ББ-…`, a balcony block = default key `балконная дверь`), `Окн_Вит_` (curtain-wall cells and the
  curtain-wall host, `Окн_Вит_Витраж`) — excluded: these are curtain-wall glazing panels, not punched windows,
  and one curtain wall yields many cells. No broad `Окн_` glob, no door family (`Двр_`), no other key or flag.
  Disclosure: the per-family name census of the #88 63A-1 **and** 63B-1 crops was read before freezing (same Revit
  file, so 63B is held out from tuning of parameters, not blind to the naming). No accepted plan, key, review
  evidence (`1619-body-training/tower-*`, `stage2-*`) or job parameter was read before the series.
- **Primary M89 = source-to-BodyPlan handoff**, identical to M88: 1 only if a fresh crop has triangles, the
  unmodified adapter with `--openings --keys keys63.json` emits a plan with at least one window whose reveal depth
  is > 0, JSON Schema, `validate_plan` and `build_module` pass. A witnessed deterministic adapter refusal = 0.
  Timeout, missing runtime, input hash mismatch = **not measured**. Exactly 3 paired observations per fixture,
  each re-imports and re-crops (no rescoring of #88 dumps). Baseline = same crop with default keys (in the same
  iteration, same crop bytes). Hypothesis H89 **confirmed** only if candidate 3/3 and baseline 0/3 on both 63A
  and held-out 63B; **refuted** if the candidate is deterministically rejected on either fixture (then report the
  new first stop); **inconclusive** if any required observation is not measured.
- Secondary (recorded, no keep decision): classified object counts per class, typical-floor run, reference-floor
  window count, `dropped` count/reasons, plan `counts`, wall times. Opening count vs Artem's accepted plan is
  **not measured** in the series (evaluation against accepted evidence only after the freeze, if at all, and
  labelled).
- Witness/controls: positive trigger witness = 63A crop where candidate keys classify > 0 windows and default keys
  classify 0. Injected negative = #88 synthetic empty crop with the candidate keys: expected refusal, no JSON
  (synthetic, not an Artem-rejected model). Collateral: the default `KEYS` are not changed, so G22/KPP1 inputs are
  **not_exercised** (no product default change is proposed in this round).
- Budget: one series, 6 crops; stop if wall time from series start exceeds min(8 min, 5 × first pair). A budget
  stop leaves the series inconclusive. Crop subprocess cap 60 s, adapter 30 s.
- Forbidden: editing the adapter, cropper or schema; extra flags (`--clip`, `--seal`, `--fill`, `--snap`, …);
  per-tower keys; reading accepted keys/plans before the series; touching delivered packages, ledger or other
  cards' files; deselecting tests.
- Replay: `mkdir -p tmp && uv run -q python docs/research/trainer-revit-intake-r89/replay.py tmp/r89` (Blender 5.1.2
  at the #88 path, pinned inputs present; replay limited to hosts with those assets and `C:/x/trainer/runs/*-r87-*`
  snapshots for the baseline-adapter provenance). Receipt: `trainer-revit-intake-r89/receipt.json`.

## Result — H89 refuted for the handoff, stop moved one step (no KEEP)

**Итог по-русски.** Ключи окон по именованию семейств модели (`Окн_Окн_`, `Окн_ББлок_`) снимают остановку
`no window objects` на обеих башнях 3/3: адаптер выдаёт план (63A: 12 типовых этажей, 36 окон, откосы 0,25–0,35 м;
63B: 6 этажей, 33 окна, откосы 0,11–0,50 м; `dropped` 0). Но ядро `build_module` отклоняет план 6/6 жёсткой
проверкой замкнутости ринга [D373]: `ring not closed: level 0 breaks at s=44.565` (63A) / `s=17.554` (63B).
По контракту M89 = 0/3 на обеих башнях → **гипотеза H89 опровергнута** (BodyPlan не проходит). Новая первая
остановка детерминирована и одинакова на 63A и отложенной 63B: правый откос окна попадает на 0,1 мм раньше угла
контура (63A: откос 44.5651, угол 44.5652; 63B: 17.5541 / 17.5542) — сегмент-щепка 0,1 мм, который `--snap 0.03`
не сливает с вершиной контура. Изменений в продукте нет; прохождение `artifact` свежим агентом не измерялось.

| Fixture | Baseline (default keys) | Candidate M89 (`keys63.json`) | Paired gain median (range) | Windows classified | Plan windows / floors | Crop+2 adapters s, median (range) |
| --- | --- | --- | --- | --- | --- | --- |
| 63A tuning | 0/3 (`no window objects`) | 0/3 (`ring not closed` level 0, s=44.565) | 0 (0–0) | 0 → 730 objects | 36 / 12 | 31.284 (28.261–33.194) |
| 63B held out | 0/3 (`no window objects`) | 0/3 (`ring not closed` level 0, s=17.554) | 0 (0–0) | 0 → 557 objects | 33 / 6 | 28.633 (25.583–28.706) |

- Run status `finished`, series 177.683 s, first pair 57.529 s (budget min(480, 5×57.5) s not hit). Each of the 6
  observations re-imported the FBX and re-cropped (crop SHA differs per iteration, triangle/object counts identical:
  63A 1,676,862 / 9,795, 63B 1,142,968 / 5,370 — same as #88). Plan counts identical across iterations; plan bytes
  differ (crop ordering, as in #88). Source pre/post parity passed; native cropper SHA-256 `11b64625…590d72a` equals
  #88. Baseline here is the same crop with default keys (frozen), not the #87 snapshot provenance; the replay does
  not need `C:/x/trainer/runs`.
- Positive trigger witness: on 63A default keys classify 0 windows, candidate 730 (walls 3,112 and baskets 17
  unchanged — only `windows` moved; 63B: 0 → 557, walls 2,346, baskets 34). Injected negative (synthetic empty
  crop, candidate keys): exit 1 `no window objects: check --keys`, no JSON — clean.
- **Not measured:** opening count vs Artem's accepted 63A/63B plans (not read), visual/finish fidelity, fresh-agent
  `artifact` passage, other sites (G22/KPP1 inputs `not_exercised`: default `KEYS` unchanged), Blender legacy-importer
  parity (#88).
- Would change (OBSERVE, not applied): the trainer practice bank for 63A/63B could pass this keys file — useful only
  together with a fix for the new stop.
- Receipt: `trainer-revit-intake-r89/receipt.json` (per-row crop/plan SHA-256, class counts, logs, wall times).
  Replay limited to hosts with the pinned FBX/tower map and Blender 5.1.2.

Next (not run): window jamb within `--snap` of a contour corner — snap the jamb station onto the corner (or drop
the sliver segment) in the adapter before `build_module`; freeze on 63A, run unchanged on held-out 63B, M = the
same handoff, plus `ring_closure` counts and an accepted G22 plan as the collateral control (rule must not change it).

Affected tests: `uv run -q pytest -q tests/test_body_lattice_1736.py tests/test_body_training_1619.py tests/test_body_training_1619_stage2.py` → 89 passed; `repo_guards.sh` → 555 passed, GREEN.

Full suite: deferred to merge batch (rule 68).
