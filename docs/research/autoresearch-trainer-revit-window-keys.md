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

## Result

(filled after the series)
