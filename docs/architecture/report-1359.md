# NPM/OKS route v2 — #1440 (original map #1359)

## Обновление для Артёма — 2026-11-15

Маршрут теперь содержит **11 шагов**: исходники → части → Gate 1 → модель →
UV/атлас → **версия НПМ на атласе** → экспорт/пакет → свежее чтение → проверки →
СИНТЕЗ → передача Артёму. На DCC-шаге агент выбирает Blender / Max / AGR Tools
и пишет причину одной строкой [D293]. Мастер: квады где возможно, неизбежные
треугольники с числом и долей по объекту, n-gon >4 запрещён до триангуляции [D312].
Ветка участка условная: это не требование строить Ground для каждой задачи ОКС.

- Облегчение только на копиях `<original>__<job>` вне библиотеки, с записью
  в манифест задания для очистки после сдачи [D301].
- НПМ: агент приносит варианты 50k / 60k / 70k, Артём сокращает
  ([дополнение #1412](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1412#issuecomment-6892291256));
  это не замена нормативного лимита ОКС [D010].
- Flora **всегда** имеет opacity: НПМ — отдельная карта формирует силуэт;
  ВПМ — Diffuse с alpha (тот же комментарий #1412; D-row пока отсутствует).
  Временные карты допустимы, Артём смотрит вид в конце [D299].
- 4096 tile: сторона квада 3.8–4 m, UV-острова могут перекрываться/stack:
  [Артём 2026-11-15, #1380 comment-6893094521](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1380#issuecomment-6893094521).
  D021 / conflicts item 26 даёт прежний ориентир около 4 × 4 m, но не регистрирует
  новое разрешение stack. В исходной карточке ссылка на тело #1380 неточна:
  источник — комментарий, тело задачи про compaction 5. Новую D-row здесь не создаём.
- Если есть участок: плоский Ground → ID/текстуры → рельеф → поправка текстур
  + юбка → UCX только ВПМ → МАФ/Flora → НПМ на атласе [D293].
  МАФ-ограды/навесы без UCX [D298]; не попавшие на поверхность объекты удаляются
  с записью в отчёте [D302]. Архив или Max-сцена с квадами — Артёму, он принимает
  и передаёт заказчику [D300].

### Красные блоки: текущее состояние (не статус приёмки модели)

| Block | Status / owner | Evidence |
|---|---|---|
| UDIM copies | Закрыто на живом маршруте #1376; `udimtile_core` | `contexts.yaml`, `tests/test_udim_compaction_1376.py` |
| Package copies / owner | Закрыто #1377/#1361; единственный ZIP writer `package_core._write_zip`; фасады `agr package-npm` / `package-vpm` | `contexts.yaml`, `tests/test_package_compaction_1377.py` |
| Blender launch copies | Закрыто #1378; `blender_runner.blender_command` / `run_blender` | `contexts.yaml`, `tests/test_blender_compaction_1378.py` |
| Historical copies | Сохранены с причинами; актуальные адреса/классы #1424 — в `contexts.yaml`, не в старом списке ниже | `report-1424.md` |
| Tool lock / master topology | Решено D293 / D312; не означает проверку реального мастера | `npm-oks-route.events.yaml` |
| Roof / windows | Правило выбора решено D292; история исходного расхождения сохранена | `routes/npm-oks.md` |
| Two atlases | Открыто #1141; владелец `atlas_core`, Python UDIM путь остаётся отдельным | `contexts.yaml` |
| xView / manual gates | Не пройдено в цитируемом benchmark #1343 (112/116); V015/V017 не закрываем этой картой | `docs/research/bench-npm-derivation.md` |
| SINTEZ CLI | Общей команды agr/dt нет; job runners остаются | `npm-oks-route.events.yaml` |

### Views / evidence

`npm-oks-route.events.yaml` → `uv run python tools/architecture/route_map.py` →
`npm-oks-route.svg` + `.excalidraw`. Context view использует текущий `contexts.yaml`
(owners после compaction 1–3); он не переписан этой задачей. #1425 / PR #1444
ещё OPEN при обновлении: новый двухвидовой генератор не заимствуем из чужой ветки.
PNG #1440 хранится отдельно от исторического рендера #1359, с SHA256SUMS.txt:
`G:/Мой диск/AGR-evidence/1440-npm-oks-route-v2/v001/`.

SHA-256 (перепроверены после копирования):
- `npm-oks-route-v2.png`: `1e74206ee74cccc0777ab017ebbf94c66763a04459fe49fd4e0d545dd73202e2`
- `npm-oks-contexts-v2.png`: `4ba37f680ff1a51600e5444fed26b231e851e72c6fea5a61b27d4fae98564228`

Проверка #1440: исходная регрессия — 1 failed (нет actor agent-dcc), после
обновления affected tests — 451 passed. `route_map.py --check` exit 0.
Full suite: deferred to merge batch (rule 68). PNG — карта, не свидетельство QA модели.

**Not done:** D-row for Flora opacity + 4096 quad rule, close C18 — decisions-fix
follow-up (compaction 5 will register the tile rule). `docs/decisions.md` и C18
в этой задаче не меняются. Это документация маршрута, не модель и не passed=true.

## Historical #1359 snapshot (superseded counts, owners and proposed order)

The remainder is the original audit evidence, not today's owner/status table.

## Кратко (для Артёма)

**Картинки:** `docs/architecture/npm-oks-route.svg` (маршрут) и `docs/architecture/contexts.svg` (карта
контекстов) открываются в браузере; для правки — те же `.excalidraw` на excalidraw.com («Open»). PNG лежат на
Drive: `G:/Мой диск/AGR-evidence/1359-event-storming/` (`SHA256SUMS.txt` рядом). Все подписи русские; команды,
пути и номера решений D — как в репозитории.

**Что видно на маршруте (10 шагов, КПП1):** исходники → состав частей → Gate 1 (Артём) → модель → UV/атлас →
экспорт и пакет → свежее чтение экспорта → проверки и xView → чекер СИНТЕЗ → сдано. У трёх шагов **нет команды
agr/dt** (Gate 1, СИНТЕЗ, сдача) — это делается руками или скриптами задания. Время теряется в семи точках:
шов парапет/кровля, окна, UDIM, два атласа, пакет, перекрытия xView (#1343: 112/116 граней), запуск СИНТЕЗ.

**Что видно на карте контекстов:** 5 контекстов + общее ядро UDIM. У каждого назван один модуль-владелец и его
функции (вход → выход). Вне владельцев найдено **83 копии**: 48 формул UDIM (30 в `jobs/`), 16 сборщиков ZIP
(14 в `jobs/`, из них 9 упаковщиков ВПМ), 5 копий атласа/UV, 5 копий проверок и запуска чекера, 6 своих запусков
Blender, 3 своих шва/сборки корпуса.

**Новая защита:** тест `duplicate_guard` падает, если в `jobs/` появится новая своя формула UDIM или свой сборщик
ZIP-пакета. Старые копии перечислены в `contexts.yaml` со ссылкой на задачу; переписывать их эта задача не стала.

**Предлагаю порядок слияния:** (1) UDIM на самом маршруте НПМ, (2) пакет — сначала решение, кто владелец,
(3) один запуск Blender, (4) проверки и команда СИНТЕЗ, (5) атлас после #1141, (6) шов корпуса.
Пять карточек — в конце. Если формат понравится — тот же метод становится 1-м этапом аудита всего репо (#1298).

## Method

- Sources of truth: `npm-oks-route.events.yaml` (stages, actors, commands, D-rows, evidence, hot spots) and
  `contexts.yaml` (contexts, owners, contracts, duplicates, relations). Both are a strict YAML subset read by the
  stdlib reader `tools/architecture/mini_yaml.py` (parity with PyYAML is tested).
- Generator: `uv run python tools/architecture/route_map.py` writes the two `.excalidraw` files and the two `.svg`
  files (stdlib, offline, deterministic). `--check` fails on drift (a committed file differing from the generator
  output) and on any command, D-row, path, owner function or `path:line` that does not exist.
- Renders: the SVG is produced **directly by the generator**, no Excalidraw renderer is used (none runs offline
  here). PNG = `magick -density 110 <svg> <png>` (ImageMagick 7.1.2-31, offline), stored on Drive (rule 57):
  `contexts.png` `7d4497887ef95ab227a5cebb6364aacf9237565664fcad7b1ad2bc3d53681a05`,
  `npm-oks-route.png` `6925c9e48b8b4b7e44759a5adf949cea35c717c98e008a15a2666b37291db82d`.
- Guard: `tools/architecture/duplicate_guard.py` (AST, stdlib). Rules `udim-tile` (owner
  `adapters/max/agr_tools/udimtile_core.py`, #1337) and `delivery-zip` (owner `adapters/max/agr_tools/package_core.py`,
  #1361/#1377; was `tools/derive/package_vpm.py`, now its facade). Rule-tagged `duplicates` rows of `contexts.yaml` are the allowlist (`path.py::function` + optional
  `hash` + issue; #1387 replaced the exact `path:line` key, so unrelated line shifts stay green). A new
  copy under `jobs/` fails; a listed row that is no longer found fails (stale); copies outside `jobs/` are
  documented and must still exist, but new ones there are not guarded yet. The `udim-tile` rule also resolves
  `Name = <int>` constants anywhere in the file (`FIRST_UDIM = 1001`, `U = 10`) and flags any job-local `def`
  named `udim_tile` / `udim_of_cell` / `tile_origin` / `face_tile` (review r1 of PR #1368: a verbatim copy of
  the owner was invisible before). That widening found 10 more copies outside `jobs/` (none new in `jobs/`).

## Evidence used

`routes/npm-oks.md`; `jobs/KPP1/{STATE.md,LESSONS.md,REPORT.md,spec-compare-v002.md,spec-compare-v003.md}`;
`jobs/KPP1/seam-1339/README.md` (#1339), `jobs/KPP1/windowgen-1338/README.md` (#1338);
`docs/research/bench-npm-derivation.md` (#1318 / PR #1343: xView 112/116 overlapping faces, validator 4 pass /
1 fail / 1 review / 2 not_run, V015/V017 manual pending); PR #1346 (#1337 "Other copies" list, confirmed and
extended by the guard scan); D-rows cited in the YAML (all checked against `docs/decisions.md`).

## Hot spots (where time is lost)

| Stage | Hot spot | Evidence |
|---|---|---|
| model | Parapet/roof seam: values provisional (D249) until D254; inset roof reworked in v007; seam measured in #1339 | seam-1339/README.md, STATE.md v007 |
| model | Windows: Revit vs mesh "no match" on openings only; C35 curtain-wall V004 pairs (D256); generator #1338 measurement only | spec-compare-v002.md, windowgen-1338 |
| uv | UDIM: 30 formulas in `jobs/`, 4 diverging copies before #1337; TEC26 `vpm_uv.py` = KPP1 ± 1 line | guard scan; `diff` |
| uv | Two atlases: Max `atlas_core` is canonical (D225), the route runs Python `npm_atlas_udim` (#1141 open) | D225, routes/npm-oks.md step 5 |
| export | Package: 9 job-local VPM packagers + 5 other ZIP writers; single FBX cannot pass (V001/V011/V013) | guard scan, LESSONS.md |
| validate | xView 112/116 overlaps on master/export, not passed | bench-npm-derivation.md |
| sintez | No `agr`/`dt` command; checker runner copied KPP1 → TEC26 (2 lines differ) | run_agr_checker.py ×2 |

## Duplicates per context (path:line), recommended merge order

Full machine list: `docs/architecture/contexts.yaml` (`duplicates`). Line numbers are checked by the tests.

1. **Shared kernel UDIM** (owner `udimtile_core.py`): on the NPM route itself `tools/derive/export_npm.py:144,149`,
   `tools/materials/npm_atlas_udim.py:375`, `tools/blender/fbx_readback.py:63` (twinqa readback),
   `src/dt_ai/geometry/uv.py:4,7`, `src/twinqa/uv.py:35`; Max cores `atlas_core.py:552`, `npm_core.py:109`,
   `npm2vpm_core.py:175`, `udim_core.py:50,53`, `udimplug_core.py:53`, `udimview_core.py:38`,
   `uvlayout_core.py:56,60,64`, `uvtile_core.py:64,67`; jobs (guarded, 30 rows): KPP1 `scripts/export_npm.py:88,93`, `readback_vpm.py:80`,
   `vpm_uv.py:151`, `benchmark-1318/{account_readback.py:51,prepare_master.py:54}`, `rerun-1230/build_blender.py:269`;
   TEC26 `export_npm.py:92,97`, `vpm_uv.py:151`, `qa_packages.py:224,236,340,380,406`, `compare_facades.py:152`;
   PSU275 `export_npm.py:98,103`; elv-tc-vpm 10 rows; VATUTINO `flora_v007_blender.py:53`; skug26 `uvverify.py:19`.
   First because the owner exists and the live route copies are few.
2. **Package** (owner `tools/derive/package_vpm.py`): jobs (guarded, 14): `KPP1/scripts/package_vpm.py:51`,
   `PSU275/scripts/package_vpm.py:53`, `TEC26-OKS/scripts/package_vpm.py:50`, `elv-tc-vpm/scripts/package_vpm_v001..v006`
   (`:83,85,116,119,122,131`), `KPP1/rerun-1230/build_blender.py:401`, `KPP1/site-1255/place_package.py:181,186`,
   `VATUTINO-SITE/npm_code.py:40`, `VATUTINO-SITE/run_delivery.py:67`; outside jobs `adapters/max/agr_tools/package_core.py:457`,
   `src/dt_ai/publish/bundle.py:20`. Needs a decision first: two owners (Python vs Max `package_core`), no shared NPM package step.
3. **DCC** (owner `src/dt_ai/core/blender_runner.py`): `src/dt_ai/core/build.py:16`, `src/twinqa/scene.py:59`,
   `tools/qa/run_benchmark.py:40`, `jobs/VATUTINO-SITE/flora_route_a.py:394`, `jobs/VATUTINO-SITE/place_site.py:59`,
   `jobs/OBR22-K02/scripts/run_profile_checks.py:191`.
4. **Validation** (owner `tools/qa/validate_package.py`): `jobs/KPP1/scripts/qa_master.py:37`,
   `jobs/TEC26-OKS/scripts/qa_master.py:37`, `jobs/TEC26-OKS/scripts/qa_packages.py:35`,
   `jobs/KPP1/scripts/run_agr_checker.py:47`, `jobs/TEC26-OKS/scripts/run_agr_checker.py:47`.
5. **UV/atlas** (owner `adapters/max/agr_tools/atlas_core.py`, D225): `tools/materials/npm_atlas_udim.py:779`,
   `jobs/KPP1/scripts/make_npm_atlas.py:28`, `jobs/TEC26-OKS/scripts/make_npm_atlas.py:28`,
   `jobs/KPP1/scripts/vpm_uv.py:155`, `jobs/TEC26-OKS/scripts/vpm_uv.py:155`. After #1141.
6. **Body** (owner `src/dt_ai/ops/operations.py`): `jobs/KPP1/scripts/seal.py:73,302` (vs `dt_ai.ops.seams.join_parts`),
   `jobs/KPP1/scripts/build_kpp1.py:194`.

Non-package ZIP writers seen by the scan and deliberately not listed (not delivery packages):
`tools/max/build_agr_tools.py:245` (MZP), `tools/methods/{ucx,windows}/run_benchmarks.py`,
`tools/research/checker_mutation.py:197`, `tools/sintez_parity.py:298`, `adapters/sketchup/*`.

## Proposed follow-up cards

1. **Route the live NPM-route UDIM copies to `udimtile_core`** (`tools/derive/export_npm.py`, `npm_atlas_udim.py`,
   `fbx_readback.py`, `dt_ai/geometry/uv.py`), then widen the guard scope from `jobs/` to `tools/` + `src/`.
   Done in #1376 (also `twinqa/uv.py::tile_origin`); the 8 copies the widened scope found off the NPM route
   (Ground, Flora, methods, experiment, source intake) are listed with #1397.
2. **Decide the package owner** (question for Artem): `tools/derive/package_vpm.py` or Max `package_core.py`;
   then one NPM package step and the KPP1/TEC26/PSU275 packagers marked historical.
   Done in #1377: owner `adapters/max/agr_tools/package_core.py` (`_write_zip`, already the one writer behind
   `agr package-npm` / `agr package-vpm` and AGR Tools after #1361); route step 6 packs with `agr package-npm`;
   the `delivery-zip` guard covers jobs/ + tools/ + src/ and every listed writer carries its reason (`ru`):
   15 job writers are historical deliveries (9 VPM packagers among them), 7 tools/src archives are not packages.
3. **One SINTEZ/checker command** (`agr checker` alias over the existing runner) from
   `jobs/KPP1/scripts/run_agr_checker.py` + TEC26 copy, so stage 9 has a command.
   Done in #1379: `agr checker FOLDER --output NEW.json` (`tools/qa/sintez_checker.py`) runs the one launch
   `tools/blender/sintez_checker.py` through `blender_runner` on a private copy of the ZIPs; the master QA moved to
   `tools/blender/qa_master.py`; the KPP1/TEC26 job files are shims; guard rules `sintez-checker` + `master-qa`.
   Rows that stay with a reason: elv-tc-vpm `run_agr_checker_v003.py` (frozen), PSU275 `qa_master_psu275.py`
   (variant), TEC26 `qa_packages.py` (job-specific package checks validate_package does not own).
4. **One Blender runner**: route `dt_ai/core/build.py`, `twinqa/scene.py find_blender`, `tools/qa/run_benchmark.py`
   through `blender_runner`.
5. **Audit stage 1 for the whole repo** with this method (other routes: VPM, Ground, MAF, Flora), adding guard
   rules per owned function (`pack_uv`, `qa_master`, seam welding) as owners appear.
