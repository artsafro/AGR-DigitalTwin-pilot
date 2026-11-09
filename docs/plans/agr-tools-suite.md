# План: AGR Tools как полный набор для 3ds Max (#853)

Статус: исследование, план и макет. Ничего не реализовано. Реализация идёт отдельными версиями (одна версия = одна
issue) после «да» Артёма.

Запрос Артёма (2026-11-04, голосом): «хочу собрать полноценную большую тулзу по АГР, как вместо ГеоАГР, используя его
базу, его полезные тулзы … отсеять всякие шумы … добавить скрипты мои пользовательские, из Телеграма, из Эндрю Скриптс …
сначала блок по моделированию, потом блок по текстурам, коллизиям, юдимам, потом атласы, неатласы, замены объектов …
с иконками красиво, ещё можно добавить цвета в дизайн … и параллельно работать над MCP».

Границы: код GeoAGR не публикуется целиком. Здесь есть только ссылки на функции и строки `GeoAGR.ms:<строка>`
(снимок GeoAGR-private@7cd117c, `C:/x/geoagr-base`). Приватный репозиторий не менялся. Командные дефолты
по-прежнему не являются правилами сдачи [D180].

## 1. Что получилось (кратко)

- 92 кнопки: готово 13, взять 10, взять + исправить 32, слить дубли 21, новое 16; P1 41 / P2 33 / P3 18; в MCP 84; только чтение/выделение 40; шум 42; ссылок на строки GeoAGR.ms проверено 29. До аудита командных скриптов (05.11.2026, §12) было 90, после аудита 97; решения Артёма по конфликтам (05.11.2026, §12) — 92.
- 10 блоков: восемь блоков из списка Артёма в его порядке и ещё два, которых требуют доказательства:
  **0 Сцена и источник** и **9 Освещение ВПМ** (причины в таблице блоков).
- Каждая кнопка — функция одного ядра (`checks_core.py` / `runtime.py`), у которой два фронта: Qt-панель (#808) и
  сервер `agr-mcp` (`docs/plans/agr-mcp.md`). Имя инструмента MCP строится из id: `agr_<block>_<name>`
  (например, `qa.preflight` → `agr_qa_preflight`). Кнопки, которые правят сцену, в MCP берут только `preview` из
  прошлого ответа, как `agr_ucx_apply` в плане MCP.
- Правило безопасности, как в AGR Tools 0.1–0.5: проверка читает сцену. Правка идёт только на новых экспортных копиях,
  в новых файлах или внутри одной записи undo после пробного прогона. Кнопок, которые разрушают сцену, как Prepare LowPoly
  у GeoAGR (D6), в наборе нет.
- Порядок реализации — по ценности: сначала проверки, потом сдача, потом расстановка, потом моделирование. Порядок
  блоков в панели — как сказал Артём (вопрос 1).
- Макет: вкладки-рельс слева, у каждого блока свой цвет, внутри вкладки две сворачиваемые секции
  «Проверить» / «Исправить». Темы Dark и Light, картинки лежат на Drive (§7).

## 2. Источники и команды

Прочитано:

- GeoAGR (снимок `C:/x/geoagr-base`, GeoAGR-private@7cd117c): `repo/docs/reference/README.md` (карта панели, диалоги,
  что разрушает сцену, мёртвый UI, находки runtime-проверок), `PLAYBOOK.md` + `playbook.json` (14 рецептов, 69 задач с
  надёжностью works / works_with_caveat / broken / unverified), `AGR-REQUIREMENTS-MATRIX.md` +
  `agr_requirements_matrix.json` (303 требования, 13 главных пробелов, дефекты D1–D8), `catalog.json` (602 функции,
  68 rollout/диалогов), `analysis/ANALYSIS.md` (кандидаты C1–C8), `GeoAGR.ms` (сверка номеров строк),
  `declarations.json`.
- Командные скрипты на main пилота: `docs/research/team-scripts-audit.md` + `team-scripts-inventory.json` (Telegram, #537,
  рекомендации R1–R12), `docs/research/team-plugins-audit.md` + `archive/2026-11:docs/research/team-plugins-inventory.json` (плагины Артёма и
  Andrew_scripts, R13–R23, таблица расхождений), `docs/agr/inventory/ZAVOD_AND_MAX_PLUGINS_REVIEW.md` (MAX-26…MAX-39),
  `docs/decisions.md` (D010, D012, D015, D030, D098, D152, D156, D160, D169–D171, D180).
- Пилот: `adapters/max/agr_tools/README.md` + `CHANGELOG.md` (0.1–0.5), макет #808
  (`G:/Мой диск/AGR-evidence/808-ui-gate1/`, ветка `improve/issue-808-…` @ e7ed8ec9, `tools/max/agr_icons.py`),
  `docs/plans/agr-mcp.md` (16 инструментов v1), `docs/domain/areas/*.md` (список), `docs/methods/` (список).
- Работы: `docs/research/job-retro-tec26-oks-pr570.md`, `…-pr574.md`, `job-retro-vyatskaya-tow02-pr392.md`,
  `…-pr515.md`, `jobs/TEC26-OKS/STATE.md`, `jobs/KPP1/STATE.md` (заголовки), `jobs/VATUTINO-SITE/` (список файлов и
  `maf/`), issues #707, #722, #728, #731, #804, #808, #790, #841.

Команды (скрипты лежат на Drive рядом с картинками, §7):

```
grep -n "^#" README.md AGR-REQUIREMENTS-MATRIX.md ANALYSIS.md           # структура справочников GeoAGR
python pb853.py      # playbook.json: 69 задач (кнопка, строка, надёжность, доказательство)
python req853.py     # agr_requirements_matrix.json: 303 id + статус GeoAGR
python inv853.py     # team-scripts / team-plugins inventory: в репозитории своё, не стороннее
python cat853.py     # catalog.json: структура (функции, ui, runtime_findings)
gh issue list --repo artsafro/AGR-DigitalTwin-pilot --label block:max-tools --state all
python make_suite.py <worktree>        # suite_data.py -> docs/plans/agr-tools-suite.{json,md} + проверки
uv run --no-project --with pyside6 python make_mockup.py <new dir>   # картинки + проверки цвета
```

## 3. Блоки

| № | Блок | Кнопок | P1 | Готово | Почему добавлен |
|---|---|---|---|---|---|
| 0 | Сцена и источник | 6 | 2 | 0 | добавлен: TOW02 потерял ~1.5 ч, потому что класс источника не проверили до выбора маршрута (job-retro-vyatskaya-tow02-pr392); дефект GeoAGR D5 (тексель в 100 раз меньше в сцене в см) — это проблема единиц; TEC26 начался с 60-минутной переписи сцен (job-retro-tec26-oks-pr570). Все остальные блоки предполагают метры и известную сцену. |
| 1 | Моделирование | 18 | 2 | 0 | список Артёма |
| 2 | Текстуры и материалы | 11 | 3 | 1 | список Артёма |
| 3 | Коллизии UCX | 7 | 3 | 1 | список Артёма |
| 4 | UDIM и тексель | 11 | 3 | 2 | список Артёма |
| 5 | Атласы / не-атласы | 6 | 3 | 1 | список Артёма |
| 6 | Замены и расстановка | 8 | 4 | 0 | список Артёма |
| 7 | Проверки и сдача | 19 | 14 | 6 | список Артёма |
| 8 | Экспорт и пакет | 8 | 6 | 2 | список Артёма |
| 9 | Освещение ВПМ | 3 | 1 | 0 | добавлен: VPM-2.15-* (≤250 источников, только Omni/Spot, 5 м / 1.5 м, пивот корня) и VPM-2.1-2.b (FBX _Light) — правила сдачи; пробел GeoAGR №7 (Omni теряются в _Light.fbx, 66915) и три командных скрипта (Light.ms, Light_Metr.ms, FreeSpot_Tools.ms) показывают, что эта работа есть; ни один блок списка Артёма её не держит. |

Режимы в таблице: **чтение** — сцена не меняется; **выделение** — меняется только выделение; **копии** — пишет новые
узлы-копии для экспорта, оригиналы не трогает; **undo** — правит рабочие объекты одной записью undo после пробного
прогона; **новые файлы** — пишет файлы только по новому пути и никогда не перезаписывает исходники.

Вердикты: **готово** — уже есть в AGR Tools 0.1–0.5; **взять** — перенести как есть (поведение подтвердить на
одноразовой сцене, если в GeoAGR оно `unverified`); **взять + исправить** — перенести и закрыть названный дефект;
**слить дубли** — несколько скриптов/кнопок с одной задачей становятся одной кнопкой; **новое** — такого нет ни в
GeoAGR, ни в командных скриптах, но его требует работа или регламент.

## 4. Главная таблица

Одна строка — одна кнопка. «Источник»: `GeoAGR` — функция и строка `GeoAGR.ms`; `Andrew_scripts`, `Telegram`,
`plugins` — файлы из аудитов #537 / team-plugins; `AGR Tools` — наша версия; `pilot` — модуль или job-скрипт пилота.
Короткие примечания и ссылки в ячейках оставлены на английском, как в исходных аудитах. Ссылки вида
`btn_* GeoAGR.ms:N` сверены с исходником автоматически (`make_suite.py`). Короткая ссылка `:N` указывает строку
в том же файле и вручную взята из справочника.

| Блок | Кнопка (id) | Что делает | Источник | Вердикт | Ценность (доказательство) | Требования | Режим | MCP | Приор. | Версия |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 Сцена и источник | Перепись сцены (`scene.census`) | JSON: объекты, Multi/Sub, карты, пропавшие файлы, bbox, units, инстансы | pilot: jobs/TEC26-OKS/census scripts; zavod agr_inspect_max.ms (ZAVOD review §4); Telegram/pc: scene_load_report (треугольники по слоям/префиксам, топ тяжёлых); Optimise_info (меши >100k, карты >4096 — только отчёт); zavod: agr_inspect_max.ms (cyrillic_names, far_from_origin, renderer); SHA256: scene_load_report.ms a9b76b4fb8c2338ca5a9088831328457ac546a00fc2a0075076095d1dfda59a3, Optimise_info.ms b6725902dd869ec2b1b33a99be5651d08186b58ea49975517b73f9377e52fcd5, Optimise_info_2.ms 967f369dcb1c074713689b1ac59be1dec85111fb144a6d769fdbd82a009b7578, agr_inspect_max.ms ea79dfc035a918cf144d56ac1abcc7641ea086c05ed696d52e042905a6b4446e | новое: generic headless census adapter; the retro names it an engine candidate (M); team-audit: только чтение — Optimise_info при загрузке переименовывает (_from) и переносит слои, это не брать; дамп в UTF-8; проверить usedMaps на пропавшей карте (hypothesis T08) | TEC26: native census of 3 scenes, 60.4 min intake (docs/research/job-retro-tec26-oks-pr570.md); team-audit T04/scene_load_report, T04/optimise_info, T04/agr_inspect_max, T04/layers_polycount (GeoAGR-private work/team-scripts-audit) | NPM-2.1-1.b VPM-2.1-1.c | чтение | yes | P1 | 0.7 |
| 0 Сцена и источник | Единицы и гамма (`scene.units`) | Проверяет System Unit = метры, 1 unit = 1 m, гамму 2.2/1.0; предлагает исправить | GeoAGR: System Setup btn_set_meters GeoAGR.ms:12547, btn_set_alpha :12554 | взять + исправить: only check by default; Set Meters does not rescale geometry (playbook caveat); fixes D5 at the source | GeoAGR T06-02: texel 2048 px/m shown as 20.48 in a cm scene (D5) | NPM-1.2-1 VPM-1.2-1 | чтение | yes | P1 | 0.7 |
| 0 Сцена и источник | Пропавшие карты (`scene.missing_maps`) | Список битмапов с несуществующим путём и кандидаты для relink (без переименования файлов) | GeoAGR: Project Map btn_count_map GeoAGR.ms:15548; Collect Asset (third-party, read only part); downloads-telegram: AlexYo_TexFinder_v2 (кандидаты relink по маске T<base><suf>_1.*); SHA256: AlexYo_TexFinderV2 (2).ms 056bc4b47eba927af7eb027766b767758bc9edf5a307ded7f46799d494517e0a | взять + исправить: read-only list; GeoAGR Project Map deletes/renames files (README §6); team-audit: кандидаты по маске в отчёт, сама кнопка остаётся read-only; папка по умолчанию пустая (у TexFinder «123») | TEC26: KPP folder had no ERM, railing 4096 not 2048 (jobs/TEC26-OKS/STATE.md); team-audit T06/alexyo_texfinder_v2, T06/retarget_fbm_to_new (GeoAGR-private work/team-scripts-audit) | NPM-2.1-1.b VPM-2.4-2 | чтение | yes | P2 | 0.8 |
| 0 Сцена и источник | Класс источника (`scene.source_class`) | Связные части, доля крупнейшей → оболочка / панели / сетка; до выбора маршрута | new | новое: read-only pre-check before any builder | TOW02: ~1.5 h dead end, 5 561 parts fed to a shell engine (job-retro-vyatskaya-tow02-pr392.md) | - | чтение | yes | P2 | 1.0 |
| 0 Сцена и источник | Карты: использованные / лишние (`scene.maps_usage`) | Отчёт: какие файлы карт используются геометрией, какие лишние в папке maps, какие пропали; ничего не удаляет | zavod: audit_scene_maps.ms (исправленный отчёт), zavod_lib_maps.ms (guessPaths); SHA256: audit_scene_maps.ms e9601693458995c2b7e2cb0bd8ca546175960a83ed969a6802b5273930c4a382, zavod_lib_maps.ms 17cf0942739d0f83dc73169e3273e8c0b63f2a34790097957c4e165cffb08b03 | взять + исправить: перечисление через getClassInstances BitmapTexture / AssetManager (ручной walker дал 6 из 8 ложных «лишних»); ветку удаления не брать | team-audit T08/audit_scene_maps, T08/zavod_lib_maps (measured); team-audit T08/audit_scene_maps, T08/zavod_lib_maps, T08/collect_scene_maps (GeoAGR-private work/team-scripts-audit) | - | чтение | yes | P2 | 0.9 |
| 0 Сцена и источник | Мелкие детали (метизы) (`scene.small_parts`) | Находит крепёж, уголки, отливы по словам (целые слова) и размеру/полигонам; отчёт, затем перенос в слой optimize с записью исходного слоя | zavod: analyze_layers_for_optimize.ms (ключи, отчёт), move_fasteners_to_optimize.ms, move_guess_optimize.ms (перенос); SHA256: analyze_layers_for_optimize.ms 1a351fba9a1c415e6e4384e20c0d16310120c887129ba5eefeb0d9c4515747a8, move_fasteners_to_optimize.ms d903f1fbb10e3cd780de43e58d98d9cd594e848fffec7e1100cc6ae04da0d7b9, move_guess_optimize.ms 5e6236a4bc562c4b3a2028869459319143c276fcd944b78d063a1117e4a27f42 | слить дубли: подстроки без границ слова дают ложные: Studio, Minute, Шпиль, М120, Стеклопакет (измерено); не считать уже лежащие в optimize | team-audit T08/analyze_layers_for_optimize, T08/move_fasteners_to_optimize, T08/move_guess_optimize (measured); team-audit T08/analyze_layers_for_optimize, T08/move_fasteners_to_optimize, T08/move_guess_optimize (GeoAGR-private work/team-scripts-audit) | - | undo | yes | P3 | 1.0 |
| 1 Моделирование | Опуск периметра ≥1 м (`model.perimeter_drop`) | Проверяет, что полигоны по периметру ОКС/Ground опущены ниже ±0.000 не меньше чем на 1 м | new | новое: GeoAGR gap #10: no live check | TEC26: Artem «полигоны по периметру должны быть утоплены минимум на метр» (jobs/TEC26-OKS/STATE.md) | NPM-2.3-4 VPM-2.3-6 VPM-2.3-7.a | чтение | yes | P1 | 0.7 |
| 1 Моделирование | Триангуляция (Делоне) (`model.triangulate`) | Триангулирует n-гоны на экспортной копии по Делоне, без длинных клиньев | GeoAGR: Triangulate btn_TriangulateRight GeoAGR.ms:50991 (DelaunayCore.dll) | взять + исправить: лаборатория #907: sub-mm faces stay n-gons, redundant pairs; fix both; run only on export copies | TEC26: UCX triangulation fails SINTEZ 2.3.17 in both profiles (job-retro-tec26-oks-pr574.md) | NPM-2.3-11 VPM-2.3-17 | копии | yes | P1 | 0.8 |
| 1 Моделирование | Стекло плоскостями (`model.glass_planes`) | Сводит стекло окна к одной плоскости без толщины, режет рамы и дубли | pilot: jobs/vyatskaya-tow02 clean_glass_blender.py | новое: port the job script; matched Artem's hand result 787 vs 816 quads | TOW02: Artem rebuilt balcony glass by hand (job-retro-vyatskaya-tow02-pr515.md) | NPM-2.3-10 VPM-2.8-4 | копии | yes | P2 | 1.0 |
| 1 Моделирование | Граница Ground (`model.ground_border`) | Упрощает границу благоустройства и чинит веерную топологию | Andrew_scripts: Ground_Tools.ms 2024 (Simplify Douglas-Peucker, Point Splitter, Fan Fixer); SHA256: Andrew_scripts/Ground_Tools.ms a81a8633375a2e73cf54f4d331bea0a6bd004f960a1b3f2494288bf99d135ec3, telegram/Ground_Tools.ms f8a20ec23f4eaa673f27a23fcf8983fa74b12753136753014be4887e49026115 | взять + исправить: Point Splitter как есть; Simplify даёт n-угольники до 79 и схлопывает границу (Ground_Tools:387-404), Fan — нулевые и перевёрнутые грани (:737-751): исправить; Simplify конвертирует вне undo | Vatutino: ground-gap-exceptions.json, ground-exceptions.json; team-audit T05/ground_tools (measured); team-audit T05/ground_tools (GeoAGR-private work/team-scripts-audit) | NPM-2.3-1.a VPM-2.3-3 | undo | yes | P2 | 1.0 |
| 1 Моделирование | Нарезка рельефа сеткой (`model.ground_slice`) | Режет Ground сеткой 2.5–7.6 м по мировым осям | GeoAGR: Slicers btn_slice GeoAGR.ms:13928, btn_conv :14191, btn_remove :14196 | взять как есть: Max T03-01: slicepoly in world space correct | Vatutino: Ground v005…v015 builds (jobs/VATUTINO-SITE/ground-build-v0*.md) | NPM-2.6-1 | копии | yes | P2 | 1.0 |
| 1 Моделирование | Регулярная поверхность рельефа (`model.ground_surface`) | Заменяет триангулированную поверхность регулярной сеткой по высотам | GeoAGR: Replace Faces Selection btn_Projection GeoAGR.ms:58102/58399; Andrew_scripts: Ground_Tools.ms 2024 (Delaunay-деформация по высотам); SHA256: Andrew_scripts/Ground_Tools.ms a81a8633375a2e73cf54f4d331bea0a6bd004f960a1b3f2494288bf99d135ec3, telegram/Ground_Tools.ms f8a20ec23f4eaa673f27a23fcf8983fa74b12753136753014be4887e49026115 | слить дубли: 3D-Terrain из Ground_Tools пустой (:824, :893); IDW вне оболочки экстраполирует до 2,1 м — не брать | Vatutino: relief-constraints.md, ground-gate-r2.md (jobs/VATUTINO-SITE); team-audit T05/ground_tools (measured); team-audit T05/ground_tools, T05/lisp_spot_heights (GeoAGR-private work/team-scripts-audit) | NPM-2.6-1 NPM-2.3-1.a | копии | yes | P2 | 1.0 |
| 1 Моделирование | Раздвинуть задвойки (`model.move_apart`) | Раздвигает пары граней/вершин 0–2, 3–10, 10–20 мм до чистого xView | GeoAGR: Move Faces GeoAGR.ms:49657, Move Verts :50241, Move Edges :48952 | взять + исправить: T08-01/02: Move Faces test `d >= min and d <= min` never moves a pair inside the range | TOW02: xView 185 faces at 5 mm after own check said 0 (pr515 retro); KPP1 v005 overlaps (jobs/KPP1/STATE.md) | NPM-2.3-9 VPM-2.3-13 | undo | yes | P2 | 1.0 |
| 1 Моделирование | Выравнивание по 3 точкам (`model.three_pt_align`) | Совмещает объект с другим по трём парам точек | Telegram/plugins: 3pt_align.mcr | взять как есть: on the Octopus myscripts menu | team daily (team-plugins-audit Workflow step 4) | - | undo | no | P3 | 1.x |
| 1 Моделирование | Расстановка окон (`model.window_placer`) | Ставит окна по списку и привязывает к проёмам | GeoAGR: Geo Window Placer btn_run GeoAGR.ms:57080, btn_snap :57196 | взять как есть: unverified in Max: verify on a disposable scene first | methods: docs/methods/windows-glazing | NPM-2.3-10 | undo | no | P3 | 1.x |
| 1 Моделирование | Чистка сетки фасада (`model.grid_cleanup`) | Режимы: чистка лупов и 2-рёберных вершин; детриангуляция (убирает диагонали для правки в квадах); T-стыки окон и проёмов (резка рёбер в T-вершинах или сварка только в выделении, порог в метрах). Сохраняет углы проёмов, швы UV, SG и MatID; превью и применение на копии | downloads-telegram: AGR_Loop_Cleaner_v3.ms (проверки UV/SG/MatID); Telegram: edge_tool.ms (Border Loop Cleaner 0.2, структура и скорость), IN_tools-detriangulator.mcr (взаимно-длиннейшее ребро), VertexEdgeSplit_UI_v2.ms; plugins: ShivaTools VertexCleaner (финальный шаг, только идея); SHA256: AGR_Loop_Cleaner_v3.ms bd82c16ce7e8ccc5946c7506c8308877a7f87be5c5ad509efa403ff804e4a866, edge_tool.ms eb76545e709e948561ed6a4117011f945a4b4d1dde289f01868d38a32f50d7cb, IN_tools-detriangulator.mcr 2c41bfdb51b0d316739ca4cb26e9d3c17e0c51c4a025a2077634012020dc2101, VertexEdgeSplit_UI_v2.ms d9288242608790a8c78046dd01938b0b5f407bcf63ac8a3b9833e3692d1e05f6; GeoAGR (из model.detriangulate): Detriangulate GeoAGR.ms:48104; GeoAGR (из model.tjunction_weld): Edges Weld btn_EdgeWeld GeoAGR.ms:51802, Corners Weld :51542 | слить дубли: BLC сливает острова UV, LC3 оставляет скрытые копии (40 объектов), Detriangulator: SG 0 и ошибка без канала 1; допуски в метрах, не в мм сцены; решение Артёма 05.11.2026 (#973): model.detriangulate и model.tjunction_weld слиты сюда как режимы — GeoAGR Detriangulate без undo (режим только с undo/на копии); T08-04: LMB Edges Weld сваривает весь объект, не выделение; Corners Weld — в тот же режим | team-audit T03/agr_loop_cleaner3, T03/border_loop_cleaner, T03/vertex_cleaner, T03/detriangulator, T03/vertex_edge_split (measured Max 2026); team-audit T03/agr_loop_cleaner3, T03/border_loop_cleaner, T03/vertex_cleaner, T03/detriangulator, T03/vertex_edge_split, T03/clean_opening_grid (GeoAGR-private work/team-scripts-audit); TOW02: resolve_tjunctions moved into the engine (job-retro-vyatskaya-tow02-pr515.md §8) | NPM-2.3-7.b VPM-2.3-11.b | копия | yes | P2 | 1.0 |
| 1 Моделирование | Объединить по материалам (`model.attach_by_material`) | Аттачит выделенные объекты в один на материал (по имени материала), батчами, с уникальными именами и контролем Multi/Sub | plugins: quickattach_v1.82.mcr (режимы poly/mesh, батч); zavod: attach_by_material_mesh.ms (Editable_Mesh, перепривязка детей); GeoAGR: Turbo Attacher GeoAGR.ms:54818 (бинарный attach); SHA256: quickattach_v1.82.mcr a5b18cf9e5e3548ce8a927c22c522ddcb0cfbc0b981a3d1ab0ad9cc5b433897c, attach_by_material_mesh.ms a364809c79aa3808ca20b56ef77169691bd5ecc416c38d0f6e078499aa0c1ed9 | слить дубли: своя реализация: безымянный Multimaterial (QuickAttach), дубли ATT_<mat>_part, без undo на всю сцену (zavod) — не повторять | team-audit T03/quickattach, T03/attach_by_material_mesh (measured Max 2026); team-audit T03/quickattach, T03/attach_by_material_mesh (GeoAGR-private work/team-scripts-audit) | - | undo | yes | P2 | 1.0 |
| 1 Моделирование | Трубы → Lo-цилиндры (`model.pipe_lo`) | Заменяет куски труб и фланцы 9-гранными Lo-цилиндрами по оси PCA на слое <src>_Lo, гибы разбивает; режим упрощения на копии (ProOptimizer, слой _Op); исходник не меняется | zavod: pipe_to_cylinder9.ms, pipe_stub_segment_lo.ms, pipe_lo_axis_pca.ms, pipe_optimize_clone.ms; SHA256: pipe_to_cylinder9.ms 0d2acbc9545c2caad42f9c1dfe5441907ddb34422b2c7eceac3aed55be53de00, pipe_stub_segment_lo.ms 20bddd1bf34d34fa56abb30ad802eac075d1d46bc71d4800beef41d3a1b85642, pipe_lo_axis_pca.ms 9e99b17556128c601637fff5b91b8672a2aa48e29885eeb09f2767d6ca2cb22a, pipe_optimize_clone.ms 466809e8c0f55baab3a5612c38cecb6a9f869cf973bb8530a0abe21e7e743f1c | взять + исправить: двойная трансформация (ось 45–90° мимо), радиус из мирового AABB (74,25 вместо 5), центр в пивоте (сдвиг h/2) — всё измерено; PCA точно (Jacobi 3×3); ProOptimizer без select + Modify panel | team-audit T08/pipe_to_cylinder9, T08/pipe_optimize_clone (measured pipes_job3/4); team-audit T08/pipe_to_cylinder9, T08/pipe_stub_segment_lo, T08/pipe_lo_axis_pca, T08/pipe_optimize_clone (GeoAGR-private work/team-scripts-audit) | - | копии | yes | P3 | 1.x |
| 2 Текстуры и материалы | Текстуры (все объекты) (`tex.check`) | Размер, квадрат, заглушки, альфа, 8 бит/канал, размер файла, набор UDIM, паддинг | AGR Tools 0.5.0 textures; GeoAGR: Prepare LowPoly/HighPoly GeoAGR.ms:65278/65653 | готово: fixes D1 (last object only) and D3 | #804 | NPM-2.5-1.a NPM-2.5-2.a NPM-2.5-3 NPM-2.5-4 NPM-2.5-5 VPM-2.5-1.2 VPM-2.5-1.5 VPM-2.5-1.6 VPM-2.5-1.9 | чтение | yes | P1 | 0.5 |
| 2 Текстуры и материалы | Формат PNG: альфа, 24 бит, ≤3 МБ (`tex.format_fix`) | Пишет исправленные PNG в новую папку: без альфы, 24 бит, сжатие до лимита | GeoAGR: Format & Alpha Tex btn_alpha_remove GeoAGR.ms:40195, compress_file; Telegram: convert_8bit_to_24bit.py; Telegram/pc: PNG Compressor (compress_png_gui.py: новая папка, _compressed, явный лимит МБ); SHA256: compress_png.py 75ff969bc1d8165f2b61c751ff742eab4ab8dcd6d658b100664b4a59b78ef088, compress_png_gui.py e8cb568767dc306591857829b0beb3db396667817c3a9cc4166a897984cb441a | взять + исправить: GeoAGR overwrites without backup; identify passes RGBA/palette as 8-bit sRGB (65496); compress method 2 writes nothing; team-audit: lossless сначала, иначе палитра ≤256 с дизерингом (разрешено владельцем 05.11.2026), порог качества (сейчас 4096 → 8 цветов, RMSE 0.157 считается успехом), не квантовать файл уже под лимитом, temp удалять | TEC26: railing map 4096 instead of 2048 (STATE.md); team audit R18; team-audit T01/png_compressor, T01/convert24, T02/png_compressor_build (GeoAGR-private work/team-scripts-audit) | NPM-2.5-2.a NPM-2.5-3 NPM-2.5-5 VPM-2.5-1.6 VPM-2.5-1.9 | новые файлы | yes | P1 | 0.8 |
| 2 Текстуры и материалы | Тип материала (`tex.material_type`) | Только Standard/Physical; Corona/VRay и пр. — ошибка с именем материала | GeoAGR: Prepare LowPoly GeoAGR.ms:65278 (material class branch) | взять + исправить: read-only, no collapse (D6) | GeoAGR Export LowPoly requires Standard (playbook #63); AC08 material census (jobs/TEC26-OKS/census) | NPM-2.4-1.a NPM-2.4-1.b VPM-2.4-1.a VPM-2.4-1.b | чтение | yes | P1 | 0.7 |
| 2 Текстуры и материалы | Отступы карт (dilate) (`tex.dilate`) | Раздувает цвет за край островов по маске альфы/UV, оригинал поверх | GeoAGR: Fit Mat btn_UdimFitMat GeoAGR.ms:25021, IM dilate :8278 | взять + исправить: no padding on white background without alpha; uvdilate loses alpha (CLI finding); use ANALYSIS C6 alpha-guided dilation | GeoAGR ANALYSIS.md C6 | NPM-2.5-4 VPM-2.5-1.5 | новые файлы | yes | P2 | 1.0 |
| 2 Текстуры и материалы | ERM и нормали DirectX (`tex.erm_normal_check`) | Проверяет каналы ERM (R только свечение) и ориентацию нормалей DirectX | new | новое: GeoAGR gap #4 (no DirectX check); GeoAGR normal detection `-threshold 50%` misreads flat #8080FF (1685) | - | VPM-2.5-1.7 VPM-2.14-1 VPM-2.14-2 VPM-2.14-3 | чтение | yes | P2 | 0.9 |
| 2 Текстуры и материалы | Покраска по легенде (`tex.finish_map`) | ID → отделка по листу цветового решения: легенда, кольца швов, проверка | pilot: jobs/TEC26-OKS finish_map.py (608 lines) | новое: parameterise the job script (retro: one OKS colour pipeline) | TEC26: ~6 h downstream rework (pr570 retro), 6 contract changes, 10 builds (pr574 retro) | NPM-2.4-4 VPM-2.4-1.a | копии | yes | P2 | 0.9 |
| 2 Текстуры и материалы | Заглушки 256 / 128 (`tex.placeholders`) | Создаёт однотонные заглушки Diffuse/ERM/Normal нужного размера и цвета | GeoAGR: Make Diffuse/Normal/ERM btn_make_tex_diffuse GeoAGR.ms:42227, Set Normal/ERM btn_open_tex_normal :42333 / btn_open_tex_erm :42409; Andrew_scripts: Texture_Zaglushki_Ground.ms; Telegram: index to rgb.py (заглушка по среднему цвету текстуры); Andrew_scripts: Texture_Zaglushki_Ground.ms (Texture Placeholder Creator: 24-бит писатель, «не перезаписывать»); owner-tools: AtlasBuilder maf v9 (заглушки ERM metal/non-metal, имена T_<Addr>_<Map>_<slot>.<UDIM>); SHA256: index to rgb.py 90070bbf04c7545b066e2506618655efb9d6c22d3859b048582da40bce2750dc, Texture_Zaglushki_Ground.ms 888eacc9f477b3de8353819d4920ba842bf9af89b322c26fd0ab9415c414867c, atlas_builder.py e6477f519fd2159dff8977589b3a4d6feabb71edcc6559c54a279a14f7a1380e | слить дубли: GeoAGR Set Normal/ERM crash before the overwrite question (T07-01..03); Andrew script writes 24-bit; team-audit: средний цвет по видимым пикселям, round, вывод RGB 24 бит; запрет перезаписи дубля UDIM (6 записей → 3 файла); цвета нормали/ERM — вопрос Q03; решение Артёма 05.11.2026 (#973): «Texture Placeholder Creator» = Texture_Zaglushki_Ground.ms — подтверждено | Vatutino Ground textures (jobs/VATUTINO-SITE/ground-textures.md); team-audit T01/index_to_rgb, T05/texture_zaglushki_ground, T02/atlas_builder_v9_maf (GeoAGR-private work/team-scripts-audit) | VPM-2.5-3.1 VPM-2.5-3.3 VPM-2.5-3.4 NPM-2.5-7 | файл | yes | P2 | 0.8 |
| 2 Текстуры и материалы | Наборы ВПМ D+ERM+N (`tex.vpm_sets`) | Собирает Diffuse, ERM (R свечение, G шероховатость, B металл) и Normal на UDIM | GeoAGR: Render Material RMB btn_render_mat GeoAGR.ms:22888; Texture Map Generator (только normalize_address + транслитерация + схема T_{Address}[_Ground]_{Map}_{Slot}.{UDIM}); SHA256: texture_map_generator.py 19ab63998d36a40bb96de05e2545c0c47a28e1a9ae6a8d341a018e35d53c676e, utils.py af159d896d3f35cf7fe61e98655bdb46e1467abafae52332131d8a1dce5d4e5a | слить дубли: из TMG не брать генерацию ERM/нормалей из яркости (фиктивные данные), слот всегда 1, тип карты по подстроке (Germany → ERM) | KPP1 VPM sets (jobs/KPP1/STATE.md); team-audit T01/tmg (measured); team-audit T01/tmg, T02/tmg_yola (GeoAGR-private work/team-scripts-audit) | VPM-2.5-1.4.a VPM-2.11-0.h VPM-2.14-1 VPM-2.14-3 | новые файлы | yes | P2 | 1.0 |
| 2 Текстуры и материалы | Браузер текстур (`tex.browser`) | Показывает карты объекта и их размеры (только чтение) | GeoAGR: Controls/Bitmaps GeoAGR.ms:41653, Browser Tex bnt_hi :41779 | взять + исправить: drop «Only Highpoly» clean-up of UVs\<obj>\ | - | VPM-2.4-2 | чтение | no | P3 | 1.x |
| 2 Текстуры и материалы | Мультиматериал из карт (`tex.multimat`) | Собирает Multi/Sub из найденных карт ВПМ по именам T_ | GeoAGR: Multimat HP btn_multimat GeoAGR.ms:42706 | взять как есть: unverified: confirm on a disposable scene | - | VPM-2.4-3.b VPM-2.4-5 | undo | yes | P3 | 1.x |
| 2 Текстуры и материалы | Цвет заглушки (`tex.plug_colour`) | Проверяет, что заглушка одного (среднего) цвета, показывает разброс | GeoAGR: Colors Tex btn_count_colors GeoAGR.ms:39668 | взять + исправить: «most popular» colour is the first colour found | - | VPM-2.5-3.4 | чтение | yes | P3 | 1.x |
| 3 Коллизии UCX | UCX: аудит сцены (`ucx.audit`) | Готовые UCX: выпуклость, замкнутость, без материалов, имя, пересечения SAT, бюджет | pilot: twinqa ucx_audit; GeoAGR: Check Faces Count :60316, Check Convex :60910, ucx_check.exe :60449; Andrew_scripts: UCX_Check.ms; Telegram: Collizii_2.ms | слить дубли: ucx_check.exe misses containment, cuts names at a space; Collizii uses AABB; UCX_Check tol 0.01 scene units | TEC26: 63 + 60 + 33 collision candidates in census (jobs/TEC26-OKS/STATE.md) | VPM-2.13-1.a VPM-2.13-1.b VPM-2.13-1.c VPM-2.13-1.d VPM-2.13-3 VPM-2.13-4.a VPM-2.13-7.a VPM-2.13-7.b | чтение | yes | P1 | 0.7 |
| 3 Коллизии UCX | UCX: построить (`ucx.build`) | Вариант по WHEN.md (single-hull, kernel-boxes, slice-prisms), бюджет D012, аудит, копии | AGR Tools 0.3.0 ucx; GeoAGR: UCX Make Concave Form :63505; Telegram: UCX_N_29.09.ms, Narezka_Ucx.ms; Andrew_scripts: UCX_Tools.ms | готово: team splitters merged as variants; pads 0.04/0.035 not adopted (D180) | #728 | VPM-2.13-1.a VPM-2.13-1.b VPM-2.13-7.a VPM-2.13-7.b | копии | yes | P1 | 0.3 |
| 3 Коллизии UCX | UCX: триангуляция (`ucx.triangulate`) | Триангулирует UCX на копии и проверяет выпуклость после | GeoAGR: UCX Triangulate btn_UCX_connect GeoAGR.ms:62890; Telegram: AlexYo_ConcaveFixer.ms (Octopus «UCX_Concave», переворот вогнутой диагонали); Collizii_2.ms (flip диагонали с сохранением выпуклости); SHA256: AlexYo_ConcaveFixer.ms 1ff3ef251f3ffb2b631b158be803b34c1652419a4d338ffd117431d7bee7e40e, Collizii_2.ms 3f106e7c1378e2db3eb6befd0a9b510024c6cade86f16129c1f203152dbdc8cc, Collizii.ms a11bca545c5e46d66cc57cb20dd63fcf4a233d0bc2cee94fb380d66e2ea78c4d | взять + исправить: лаборатория #907: convexity can break after triangulation, non-Poly skipped silently; fix both; run on copies; team-audit: переворачивать только выпуклый в плане квад, проверять новое ребро, epsilon, до неподвижной точки, пост-проверка выпуклости; без схлопывания стека | TEC26: SINTEZ 2.3.17 fails on UCX triangulation (job-retro-tec26-oks-pr574.md, open); team-audit T03/concavefixer_ms, T03/concavefixer_mcr, T04/collizii (GeoAGR-private work/team-scripts-audit) | VPM-2.3-17 VPM-2.13-1.a | копии | yes | P1 | 0.8 |
| 3 Коллизии UCX | UCX: нарезка и зазор (`ucx.gap`) | Режимы ucx.build: split — режет меш 3D-сеткой ячеек или по выделенным рёбрам на выпуклые куски; gap — зазор 2 мм – 1 см сдвигом плоскостей у соседей, проверка SAT | zavod: collision_splitter_ucx.ms, ucx_edge_split.ms, ucx_inset_lib.ms; Telegram: UCX_N_29.09.ms (геометрия ячеек), Narezka_Ucx.ms, UCX_Razdv.ms (анти-пример); Andrew_scripts: UCX_Tools.ms Slice v2; GeoAGR: UCX Move/MultiPass GeoAGR.ms:61446/62416; SHA256: collision_splitter_ucx.ms 7f5261ef3682c21fef7363feb1d3dcaaecd6839a00f81940faae461d70d23453, ucx_edge_split.ms 2245d585f9053e3a8b3f383399c45d446c1e562c149b2f47468091ba840b86db, Narezka_Ucx.ms 9b48e62650d12c2d3c5cbc0cad07fe80f9af0612b3a336913364f2ac05a3d39a, ucx_gap_inset.ms c72c21d109fbe6cba6f1addb2d58f36f3336d1ba202a31f3a6cb16e8896a77ce, ucx_inset_lib.ms 7d3bffd2fb11866e45144854adcbedae81a89c49548a3c8e3041918fcf6138d9, UCX_Razdv.ms 64184337a8f76791e986be00f9aa275daf5eece681fdafe6a0acd89bc8a1ebed, UCX_N_29.09.ms 8ddb6eb2362b4fd792c1eb6a4ab54e61d2660a30810c99a76c8c4cb2e6e9bde7 | слить дубли: чужие UCX_* не удалять, зазор не удваивать, оболочка не по клипнутой поверхности (zavod 57–71 %), сдвиг вершин по нормали не брать (0,83 мм и пересечение), полузазор без decodeValue дробной строки; грани в плоскости разреза не в одну сторону | D098 (Artem: gap 2 mm – 1 cm); team-audit T04: UCX_N 100 % покрытия 0 невыпуклых; метод плоскостей 4,00 мм на всех сценах (measured Max 2024); team-audit T04/zavod_collision_splitter, T04/ucx_n_splitter, T04/ucx_tools_andrew, T04/ucx_edge_split, T04/ucx_gap_inset (GeoAGR-private work/team-scripts-audit) | VPM-2.13-4.a VPM-2.13-4.b | копии | yes | P2 | 1.0 |
| 3 Коллизии UCX | UCX рельефа (`ucx.ground`) | UCX Ground по верхним граням рельефа призмами по адаптивной сетке | GeoAGR: UCX Make Ground btn_UCX_makeground GeoAGR.ms:62929; ANALYSIS C1 | взять + исправить: unverified; take C1 greedy prisms | docs/domain/areas/ucx-evidence | VPM-2.13-3 VPM-2.13-7.b | копии | yes | P2 | 1.0 |
| 3 Коллизии UCX | UCX: имена (`ucx.rename`) | Переименовывает куски в UCX_SM_<Address>_Main/Ground_NNN | GeoAGR: UCX Rename btn_UCX_rename GeoAGR.ms:62907 | взять + исправить: requires the model name inside; UE4 two-digit namer dropped (R21) | #230 (UCX name grammar R08) | VPM-2.13-1.d VPM-2.10-4.2.b | undo | yes | P2 | 0.8 |
| 3 Коллизии UCX | UCX лестниц (`ucx.stairs`) | Проверяет, что лестница закрыта усечённой пирамидой, и допуски 10/30/100 см | new | новое: GeoAGR gap #8 | - | VPM-2.13-5 VPM-2.13-6 | чтение | yes | P3 | 1.x |
| 4 UDIM и тексель | ID → UDIM на копии (`udim.ids_to_udims`) | Раскладывает материал ID n в тайл 1000+n на экспортной копии | GeoAGR: IDs→UDIMs btn_udims_as_ids GeoAGR.ms:35920; Telegram: UDIM-MultiSub_Universal.ms (reverse); Telegram: UDIM_Tool_new.mzp v9.2 (idToUDIM_All — режим «сохранить раскладку» с разрезом швов); SHA256: UDIM_Tool_new.mzp ded25b7f71c9f717971d7ac70756a38f7baf198f846063045a7996ddae96e1cd | взять + исправить: only on export copies: IDs are a reading scheme (D030); UDIM-MultiSub ID=tile rule dropped (R5); team-audit: режим «сохранить раскладку» 5000/5000 на экспортной копии; floor вместо зажима, отказ ID>100 и U/V вне сетки | TEC26 KPP recipe: 19 tiles, ID→tile matched (census/kpp-recipe.md); team-audit T02/udim_tool_v92, T02/udim_tex_v85 (GeoAGR-private work/team-scripts-audit) | VPM-2.5-2.1.3.a VPM-2.5-2.1.3.b | копии | yes | P1 | 0.8 |
| 4 UDIM и тексель | UV-сдвиг на целый тайл (`udim.nudge`) | Сдвигает острова на целое число периодов повтора (в фазе текстуры) | AGR Tools 0.2.0 nudge; Telegram: GridUVLayout22.ms | готово: GridUVLayout merged (team audit R8) | #722 | VPM-2.5-2.1.3.a | копии | yes | P1 | 0.2 |
| 4 UDIM и тексель | Тексель px/м (`udim.texel`) | Мин/медиана px/м по мешу и материалу, полосы ВПМ 512–1706, НПМ 10–40 | AGR Tools 0.3.0 texel; GeoAGR: rocount_texel GeoAGR.ms:38183; plugins density.ms | готово: fixes D5 (system units); density.ms 4096 assumption dropped (R15) | #728; D160 | VPM-2.6-2 NPM-2.6-1 | чтение | yes | P1 | 0.3 |
| 4 UDIM и тексель | MatID → UDIM (МАФ) (`udim.matid_unwrap`) | Развёртка по MatID в тайлы с плотностью и упаковкой | Andrew_scripts: Maf Tools.mcr unwrapByMatIDToUDIM_Advanced :243, ua_packTiles :819, ua_run :922 | взять + исправить: wrap: keep source UV/MatID, units.SystemScale, sparse IDs (ZAVOD review MAX-31); MAF TD spinner unit unlabeled | Vatutino MAF set (jobs/VATUTINO-SITE/maf/site-maf-set.md) | VPM-2.6-2 VPM-2.5-2.1.3.a | копии | yes | P2 | 0.9 |
| 4 UDIM и тексель | Подгонка плотности (`udim.rescale`) | Масштабирует UV до целевой плотности синхронно с текстурами | GeoAGR: ReScale Density btn_Udim_Rescale GeoAGR.ms:43253; Andrew_scripts: Maf Tools tdt_OptimizedSetTD :495 | слить дубли: GeoAGR uses system units and overwrites maps; keep one tool on copies | D160 band | VPM-2.6-2 NPM-2.6-1 | копии | yes | P2 | 1.0 |
| 4 UDIM и тексель | UDIM: тайлы и слоты (`udim.slots`) | 1001… без пропусков, ≤100 карт на материал, SlotNumber 1…7 подряд | AGR Tools 0.5.0 textures/names (partly) | новое: add >100 maps → next slot check (manual in GeoAGR) | - | VPM-2.4-3.a VPM-2.4-3.b VPM-2.5-2.1.3.a VPM-2.11-0.b | чтение | yes | P2 | 0.9 |
| 4 UDIM и тексель | Развёртка плиток в UDIM (`udim.unwrap_tiles`) | Раскладывает плитки фасада по UDIM на копии | GeoAGR: Unwrap Tiles btn_bricks_unwrap GeoAGR.ms:33780 | взять + исправить: collapse + Undo Off clears history (clearUndoBuffer): only on copies | KPP1 v003 tiles (jobs/KPP1/STATE.md) | VPM-2.5-2.1.3.a | копии | yes | P2 | 1.0 |
| 4 UDIM и тексель | Искажения UV (`udim.distortion`) | Подсвечивает растянутые полигоны UV | GeoAGR: uvDistortionViewer GeoAGR.ms:16071 | взять как есть: read-only viewer | - | VPM-2.6-2 | чтение | no | P3 | 1.x |
| 4 UDIM и тексель | UDIM → ID (просмотр) (`udim.udims_to_ids`) | Показывает, какой тайл даёт какой ID, без записи | GeoAGR: UDIMs→IDs btn_ids_as_udims GeoAGR.ms:41355; Telegram: UDIM Viewer_V1.2.ms | слить дубли: port P41 defect: negative UV and U ≥ 10 | - | VPM-2.5-2.1.3.a | чтение | yes | P3 | 1.x |
| 4 UDIM и тексель | Просмотр UDIM (`udim.viewer`) | Показывает тайлы UDIM на объекте и карты из папки | Telegram: UDIM Viewer_V1.4.ms (вкладка просмотра, импорт папок модель+GeoJSON); UDIM Viewer_V1.2.ms (правило тайла, сканер имён); UDIM_Tool_new.mzp v9.2 (загрузчик карт); SHA256: UDIM Viewer_V1.4.ms 84a81d8506b6bcd3ca9ff0ce975a18c3205f2484be1aaf30b8c33b44fc68a0f7, UDIM Viewer_V1.2.ms 1f284bbd1b1bb438a603e4f3838b6c9bb68580cea94ab5ce66dcc128b62c2f95 | слить дубли: правило тайла V1.2 (центроид, floor, UDIM-1000); не брать ID-ранги и Blend/MultiTile V1.4, схлопывание стека | team daily (team-scripts-audit); team-audit T02/udim_viewer_v14, T02/udim_viewer_v12 (measured); team-audit T02/udim_viewer_v14, T02/udim_viewer_v12, T02/udim_tool_v92 (GeoAGR-private work/team-scripts-audit) | - | чтение | no | P3 | 1.x |
| 4 UDIM и тексель | Острова-заглушки в UDIM (`udim.plugs`) | Кладёт квадрат-заглушку в центр тайла 1000+ID на копии, в паре с tex.placeholders | Telegram: GridUVLayout22.ms layoutPlugs; SHA256: GridUVLayout22.ms 3d4be7e910f70367ce3e806010d8524d2a498ff476c2de840ade64615b2b7824 | взять + исправить: polyop.setMapVert на копии без Unwrap/Modify panel; проверять classOf node.baseObject (второй запуск блокируется); швы не рвать | team-audit T02/griduv22 (measured); team-audit T02/griduv22, T02/griduv3 (GeoAGR-private work/team-scripts-audit) | - | копии | yes | P3 | 1.x |
| 5 Атласы / не-атласы | Атлас Flora (`atlas.flora`) | Атлас диффуза флоры + атлас прозрачности, кроп по UV, тайл на текстуру | plugins: Flora Atlas V1.2.mcr; Andrew_scripts: FloraAtlas.ms; AGR Tools atlas_core.pack; SHA256: FloraAtlas.ms 0160f807f05e5ae36a32afd82e562ebb1b82bbf048f7444de05080632b511093, Flora Atlas V1.2.mcr a6bae6dafb9108cff4ffa70b2019549aa2aba22f2b5f857254401e8c67be6d29 | взять + исправить: без C# в рантайме (в Max 2026 молча не компилируется, прозрачность теряется — измерено); UV по уникальному мешу, не по узлу; паддинг ≥8 px; старая Flora Atlas — drop | flora jobs (archive/2026-11:jobs/flora-textures); tools/max_flora_*.py; team-audit T05/flora_atlas_v12 (measured Max 2026); team-audit T05/flora_atlas_v12, T05/flora_atlas_old (GeoAGR-private work/team-scripts-audit) | NPM-2.5-13.a NPM-2.5-13.b NPM-2.5-4 | новые файлы | yes | P1 | 0.9 |
| 5 Атласы / не-атласы | UDIM → атлас НПМ (`atlas.npm`) | Сводит UDIM в один атлас НПМ, ремап UV на копии, отступ ≥8 px | AGR Tools 0.2.0 atlas; GeoAGR: Unwrap to Atlas GeoAGR.ms:26796; Telegram: VPM_to_NPM.ms; Telegram: VPM_to_NPM.ms (новая: кроп по UV-области ID, аффинный ремап без запекания, Ground 35 px/м, отдельная Opacity); SHA256: VPM_to_NPM.ms 613925939568d17a55200f761347c163e5a7f81d587e63fb3c24479e4fd710e8 | готово: VPM_to_NPM 6 px padding and ≤512 plug not adopted (team audit R1, R9); team-audit: VPM_to_NPM пишет 32-бит ARGB и паддинг 6 px, размер атласа не уменьшается, TGA падает — в ядре 24 бит, паддинг ≥8; старая VPM_to_NPM — drop | #722; D156; team-audit T06/vpm_to_npm, T06/vpm_to_npm_old (GeoAGR-private work/team-scripts-audit) | NPM-2.5-4 NPM-2.5-11.a | копии | yes | P1 | 0.2 |
| 5 Атласы / не-атласы | Число текстурных наборов (`atlas.sets_count`) | ОКС ≤40 наборов (+1 кровля), Ground ≤20, GroundEl 1, Flora 1 | new | новое: GeoAGR: NPM-2.1-5.b unreachable, NPM-2.1-4.c manual | - | NPM-2.1-4.c NPM-2.1-5.b NPM-2.5-11.a NPM-2.5-11.b | чтение | yes | P1 | 0.7 |
| 5 Атласы / не-атласы | Фасадный атлас run-strip (`atlas.facade_strip`) | Атлас фасада полосами повторов для НПМ ОКС | pilot: archive/2026-11:jobs/FACADES-ATLAS, tools/remap_facades_atlas.py; D156 | новое: port the accepted job method | TOW02: OKS 013 run-strip atlas accepted (D156) | NPM-2.5-11.a NPM-2.5-4 | копии | yes | P2 | 1.0 |
| 5 Атласы / не-атласы | Атлас GroundEl ≤512 (`atlas.groundel`) | Один набор элементов благоустройства, ≤512 px | Telegram: A101AGRLP.ms:1374 (GroundEl cap); AGR Tools atlas core | слить дубли: atlas.npm with a groundel mode | Vatutino MAF showcase (jobs/VATUTINO-SITE/maf/site-maf-showcase.config.json) | NPM-2.5-12 NPM-2.1-5.b | копии | yes | P2 | 0.9 |
| 5 Атласы / не-атласы | Атлас → мультиматериал (`atlas.unatlas`) | Обратный путь НПМ → ВПМ: атлас в Multi/Sub по ячейкам | GeoAGR: UnAtlas btn_unwrap_material_from_lowpoly GeoAGR.ms:29390 | взять как есть: unverified; every map 2048²; only on copies | GeoAGR recipe npm_to_vpm (tech3.txt) | VPM-2.4-3.a | копии | yes | P3 | 1.x |
| 6 Замены и расстановка | Flora: ремонт и проверка (`place.flora_repair`) | Чинит трансформы и треугольники Flora, проверяет набор | pilot: tools/max_flora_transform_repair.py, max_flora_tri_repair.py, max_flora_verify.py | взять как есть: pilot tools, already used in Max | archive/2026-11:jobs/flora-textures | NPM-2.5-13.a NPM-2.3-14 | копии | yes | P1 | 0.9 |
| 6 Замены и расстановка | Проверки МАФ (`place.maf_checks`) | Летающие и утопленные МАФ: AABB-предфильтр, затем лучи вниз от нижних вершин к Ground с допуском; пересечения | Telegram: Maf_Fly.ms (Octopus «MAF_Fly»); Andrew_scripts: Maf Tools.mcr (EG_castRay, Maf Check); pilot: twinqa.maf_checks; SHA256: Maf_Fly.ms ae29be74e484d7d1b3b81bd0c5a14e78fa0d91a6b771c1ba0ad0a0581b84f0ef, Maf Tools.mcr df1a3a3ef97f4c195c284231291ec6b6285ac412983646e9a0481e378e19fa05 | слить дубли: только AABB пропускает «летающие» на склоне, Maf Check смотрит след в плане вместо 3D (оба измерены); скрытые не выделять | skill maf-set-blender-checks; Vatutino source-dimension-gate; team-audit T05/maf_fly, T05/maf_tools (measured); team-audit T05/maf_fly, T05/maf_tools (GeoAGR-private work/team-scripts-audit) | NPM-2.3-6.b NPM-2.5-12 | чтение | yes | P1 | 0.9 |
| 6 Замены и расстановка | Замена объектов (`place.replace`) | Заменяет объекты по маске имени или выделению на эталон (копия/инстанс) с трансформом, слоем, родителем и user props; режим «бокс-заглушка по oriented bbox» | Andrew_scripts: Zamena_V2.ms; plugins: H_instancer-1.0.mcr (точный трансформ); zavod: place_box001_on_doors.ms (бокс-заглушки дверей); SHA256: Zamena_V2.ms a44ac2310d5fe0a5b72e71be2a9e9b2753f2c6550e5eb8f1695d7d5dc60defa3, H_instancer-1.0.mcr 7c94827fb7a5b73f7d1c9c7ec9da5d4d8196fa9ef15ac5d800cb9557e9e99eda, place_box001_on_doors.ms 93eb2d12148646b50d35dd8abdb901295a6193c90e4505bfdbf652f0ca15a928 | слить дубли: сохранять слой/родителя/детей/user props (agr_id), мастер исключать из выделения, отчёт заменённых и несопоставленных, undo; у заглушек X/Y не путать, трансформ один раз | Vatutino: MAF placement by schedule (jobs/VATUTINO-SITE/place_site.py); team-audit T03/zamena_v2, T05/h_instancer, T03/place_box_doors (measured); team-audit T03/zamena_v2, T05/h_instancer, T03/place_box_doors (GeoAGR-private work/team-scripts-audit) | NPM-2.3-5 VPM-2.3-8 | undo | yes | P1 | 0.9 |
| 6 Замены и расстановка | Расстановка по ведомости (`place.schedule`) | Ставит МАФ по ведомости/плану и пишет отчёт: поставлено / нет эталона / нет места | pilot: tools/placement_site.py, jobs/VATUTINO-SITE/placement_report.py | новое: port the job tool, report-first | Vatutino placement-report.json; #790 | NPM-2.1-5.a | копии | yes | P1 | 0.9 |
| 6 Замены и расстановка | Посадить на рельеф (`place.drop_to_ground`) | Опускает выделенные объекты на Ground лучом вниз по нижней точке, опционально выравнивает по нормали | Andrew_scripts: Maf Tools.mcr Glue (EG_castRay + EG_getBottomOffset); Telegram: Maf_Fly.ms (предфильтр); SHA256: Maf Tools.mcr df1a3a3ef97f4c195c284231291ec6b6285ac412983646e9a0481e378e19fa05 | взять + исправить: знак offset без выравнивания топит на 0,20–0,25 м (Maf Tools.mcr:2514, 2525-2528); метры, не системные единицы; без 360 копий-поворотов | Vatutino relief (relief-constraints.md); team-audit T05/maf_tools (measured); team-audit T05/maf_tools, T05/maf_fly (GeoAGR-private work/team-scripts-audit) | - | undo | yes | P2 | 0.9 |
| 6 Замены и расстановка | Генератор МАФ (`place.maf_generator`) | Параметрический МАФ по семейству (первое — скамьи «Верона») | pilot: #790 (open); agent-jobs: silikatny-maf-viz maf_kit.py (build()/report(), 33 слота = MatID v005); pc: apply_maf_naming, extract_manufacturers (интейк ведомости); SHA256: maf_kit.py facabd41444dce797e80981fc44d901b2038a2b5fe8cf3b5943d6b56877fa2eb | взять как есть: maf_kit: исправить ZeroDivisionError в _fillet (:171); apply_maf_naming писать в новый столбец, не затирать «Условное обозначение» | Vatutino *T3508/1-10 (#790); team-audit T05/maf_kit (measured Blender 5.1.2); team-audit T05/maf_kit, T05/apply_maf_naming, T05/extract_manufacturers, T05/kasatkino_generators (GeoAGR-private work/team-scripts-audit) | NPM-2.5-12 | копии | yes | P2 | 1.0 |
| 6 Замены и расстановка | Скаттер (`place.scatter`) | Рассыпает объекты по поверхности с плотностью и случайностью | GeoAGR: Advanced Scatter GeoAGR.ms:54174; GeoAGR: Palette Randomizer :57812 | слить дубли: MultiScatter (commercial) stays outside; решение Артёма 05.11.2026 (#973): Object Randomizer (objectrandomizerv3.ms) остаётся личным скриптом, не источник | - | - | undo | no | P3 | 1.x |
| 6 Замены и расстановка | Деревья спрайтами (`place.tree_cards`) | Дерево из плоскостей-карточек с ID ствола/веток | GeoAGR: Tree GeoAGR.ms:43960, Find & Set ID trunks :46966; pc: Kasatkino generators (billboard-флора: скрещённые квады целого растения, нижнее выравнивание, bleed); SHA256: gen_place_scripts.py 6f18c8a6a6213d2ecec3e1d5a005daa1e9c7799fcccc1316cbe2183da38dcd36, gen_billboards.py 31c59f60ad047bc935340747509e76abac7892a7b15718108705c60b914b0265, gen_miscanthus.py 1e95f364736b74976b9fe47705cb6586ac45621a09f5576796680acad47996f6, build_atlas.py f526315b0a62fae719e42f86f92e0057e810ec3d35c114a70df84e4e38809274 | слить дубли: сгенерированные place_*.ms и billboard-меши Kasatkino — только как образец вывода; генератор брать, выходы нет | team-audit T05/kasatkino_generators (measured); team-audit T05/kasatkino_generators, T05/kasatkino_billboard_meshes (GeoAGR-private work/team-scripts-audit) | NPM-2.5-13.a VPM-2.3-16 | копии | no | P3 | 1.x |
| 7 Проверки и сдача | Разделение FBX (`qa.fbx_split`) | ОКС ≤20 FBX, ≤20 объектов на FBX, Ground обязателен, нумерация сквозная | new | новое: GeoAGR gap #11: no check | TEC26: 9 OKS surfaces in one scene (census) | NPM-2.1-2 NPM-2.1-4.a NPM-2.1-6 NPM-2.2-1 NPM-2.2-4 VPM-2.1-3.a VPM-2.1-4 | чтение | yes | P1 | 0.7 |
| 7 Проверки и сдача | Проверка GeoJSON (`qa.geojson`) | Проверка паспорта GeoJSON пилотным twinqa.geojson | AGR Tools 0.5.0 geojson | готово: GeoAGR gap #1 | #804 | GJ-1 GJ-2 GJ-3 VPM-2.2-1 | чтение | yes | P1 | 0.5 |
| 7 Проверки и сдача | Стекло (`qa.glass`) | MainGlass отдельно, ≤20 полупрозрачных, ≤7 материалов стекла, без текстур, 50 % | GeoAGR: Prepare LowPoly MainGlass branch :65330–65375 | взять + исправить: D2: MainGlass branch unreachable (T10-05); D3: VPM «no textures» fires always | TOW02 glass cleanup (pr515 retro) | NPM-2.7-2 NPM-2.1-4.b NPM-2.4-2 NPM-2.4-3.b NPM-2.4-6 VPM-2.8-1 VPM-2.8-2 VPM-2.3-4 | чтение | yes | P1 | 0.7 |
| 7 Проверки и сдача | MatID (`qa.matid`) | ID ≥1001, ID 0, пустые слоты Multi/Sub | AGR Tools 0.1.0 matid | готово: D030 | #707; #548 | NPM-2.4-5 VPM-2.4-5 | выделение | yes | P1 | 0.1 |
| 7 Проверки и сдача | Имена NPM/VPM (`qa.names`) | SM/UCX, M, T по маскам, SlotNumber 1…7 | AGR Tools 0.5.0 names; GeoAGR: check_names_all GeoAGR.ms:6907, _vpm :7331 | готово: fixes D2, D4 | #804 | NPM-2.10-1 NPM-2.10-2 NPM-2.10-3.3.a VPM-2.10-2.a VPM-2.11-0.a VPM-2.11-0.c | чтение | yes | P1 | 0.5 |
| 7 Проверки и сдача | Исправить имена (`qa.names_fix`) | Переименовывает объекты, материалы и файлы карт по маске на экспортных копиях | Telegram: AlexYo_AGR_renamerV2.ms (V13), A101AGRLP.ms naming UI; GeoAGR: Material Cloner :55623; Telegram: A101AGRLP.ms LPNaming (Octopus «A101LP»: адрес + № ОКС + слот → имена 7 ролей); AlexYo_AGR_renamerV2.ms V13 (таблица слотов → суффиксы); downloads-telegram: AlexYo AssetMaterialRenamer (копия материала, отдельная папка), AlexYo_CheckAssetNames_v8.ms (библиотечный профиль: невидимые символы, омоглифы); SHA256: A101AGRLP.ms 86c43d4d4cade95d122cd3e4c0a361827685ca3ae9c62651c39e326d73e96926, AlexYo_AGR_renamerV2.ms 2f49107c48f5d916f54b19f29feaf4bcdd8b626a8b1d8908ff6550cb88041632, AlexYo_AssetMaterialRenamer_v1i3.ms 7702230eb0611cd371a967b37e92ff4979a1dd53e4072decf917807d4ddf6a37, AlexYo_CheckAssetNames_v8.ms a3067e16bb825730c2978d6ca7af39eef16289e76facf2b1bcb40b9ba7a88cc1 | слить дубли: three renamers → one; A101 Ground FBX extra underscore (:388) not copied; Material Cloner overwrites files; team-audit: не перезаписывать чужие файлы (V13:26), _m из одного слота, база по маске SM_, адрес чистить полностью, проверка дублей после фикса; библиотечный профиль Brand_Name_Article_high\|low | A101LP is the daily naming button (team-plugins-audit step 7); team-audit T06/a101_lpnaming, T06/alexyo_renamer_v13, T06/alexyo_asset_material_renamer, T06/alexyo_check_asset_names_v8 (GeoAGR-private work/team-scripts-audit) | NPM-2.10-3.3.a NPM-2.10-3.4.a VPM-2.11-0.a VPM-2.10-4.3 | копии | yes | P1 | 0.8 |
| 7 Проверки и сдача | Проверка пакета ZIP (`qa.package`) | ZIP: размеры, состав FBX/PNG/GeoJSON, имена, битые файлы, readback | pilot: tools/qa/validate_package.py; Telegram: AGR Checker (Python ZIP), AGR Zipper v2.1; Telegram: AGR_Checker.zip (реестр ФНО fno_codes_utf8.csv, правила Light FBX, кросс GeoJSON ОКС↔Ground); AGR_Zipper.zip v2.1 (проверка НПМ/ВПМ); SHA256: AGR_Checker.zip 0c1e5f7454bf9aa5183e5e9d1893f6b801b3f0123638278cbb97651748693e4d, AGR_Zipper.zip 2bdd7ff2857cebfcba7a60f7e836512408e0d4d3c42758b88bd079117d35f4b7 | слить дубли: team checkers merged into the pilot validator (agr_package_validate); team-audit: сверка FNO_code/FNO_name с реестром ФНО (решение владельца 05.11.2026 — реестр переносится в AGR Tools); в корпус: ../ и абсолютные имена, вложенные папки ВПМ, не-PNG с .png, tRNS-альфа, битые ZIP; «центр XY» только с учётом UpAxis | TEC26: qa_packages 40/40 (pr574 retro); team-audit T04/agr_checker, T04/fbx_polygon_count, T06/agr_zipper_2506, T06/inspect_fbx_py (GeoAGR-private work/team-scripts-audit) | NPM-2.1-1.a NPM-2.1-1.b VPM-2.1-1.a VPM-2.1-1.b VPM-2.1-2.a VPM-2.1-2.c VPM-2.1-2.d | чтение | yes | P1 | 0.8 |
| 7 Проверки и сдача | Пивот (`qa.pivot`) | Z = 0 и один пивот на FBX (1 мм) | AGR Tools 0.5.0 pivot | готово | #804 | VPM-2.9-4.b VPM-2.9-5 | чтение | yes | P1 | 0.5 |
| 7 Проверки и сдача | Предсдача: все проверки (`qa.preflight`) | Запускает все проверки профиля одним нажатием, одна таблица, ничего не меняет | GeoAGR: Prepare LowPoly GeoAGR.ms:65278, Prepare HighPoly :65653; RulesCheck_lowpoly :9136 (dead UI) | взять + исправить: replaces the destructive buttons: D6 (ResetXForm+collapse), D1, D2, D7, D8 | GeoAGR requirements matrix §2 (13 gaps) | NPM-2.1-3.c VPM-2.3-1 | чтение | yes | P1 | 0.7 |
| 7 Проверки и сдача | Лишнее в сцене (`qa.scene_hygiene`) | Камеры, кости, анимация, слои, группы/иерархия, пустые объекты, модификаторы | GeoAGR: RulesCheck_lowpoly :9136 checkboxes (dead UI, D7); Telegram: agr_max_check_37.ms (hyg_hidden, hyg_frozen, objectOffset, правило «только слой 0»); SHA256: agr_max_check_37.ms ead3866924bfa3bf9efe54619072e2ce810141bc8b7b914b5169f2ff600e59a2 | взять + исправить: rules from the current rules2/rules4, not the old edition; решение владельца 05.11.2026: правило «вся геометрия в слое 0» — да | GeoAGR NPM-2.1-3.a/b unreachable; team-audit T04/agr_max_check_37 (GeoAGR-private work/team-scripts-audit) | NPM-2.1-3.a NPM-2.1-3.b NPM-2.1-3.c NPM-2.1-3.d NPM-2.3-5 VPM-2.3-1 VPM-2.3-2 VPM-2.3-8 VPM-2.3-11.d VPM-2.3-11.e | чтение | yes | P1 | 0.7 |
| 7 Проверки и сдача | Треугольники по FBX (`qa.tris`) | Лимиты на FBX: НПМ 150 000 / 180 000, ВПМ 1 000 000, Ground по площади, UCX | AGR Tools 0.5.0 tris | готово: fixes D8 | #804 | NPM-2.3-6.a NPM-2.3-6.b VPM-2.3-9 VPM-2.3-10 | чтение | yes | P1 | 0.5 |
| 7 Проверки и сдача | Трансформы сброшены (`qa.xform`) | Находит несброшенный масштаб/поворот/зеркало и родителей; сброс только на копии | GeoAGR: Prepare LowPoly ResetXForm :65536 (destructive) | взять + исправить: D6: check here, reset in export copies (cleanup/apply) | TOW02 dumper wrote negative-scale meshes inward (pr392 retro) | NPM-2.3-14 VPM-2.3-18 | чтение | yes | P1 | 0.7 |
| 7 Проверки и сдача | xView: перекрытия (`qa.xview`) | Нативный xView: вершины 2 мм, грани 5 мм, на вычисленных копиях | AGR Tools 0.1.0 xview; GeoAGR: xView Verts/Faces :48459/:48470 | готово: D152 | #707; TOW02 185 faces (pr515 retro) | NPM-2.3-7.a NPM-2.3-9 VPM-2.3-11.a VPM-2.3-13 | выделение | yes | P1 | 0.1 |
| 7 Проверки и сдача | Нулевые площади и рёбра (`qa.zero_area`) | Полигоны нулевой площади, рёбра нулевой длины, изолированные вершины | GeoAGR: Areas Poly ro_count_area GeoAGR.ms:36036; Telegram: VertexEdgeSplit, ShivaTools_VertexCleaner; Max 2024 scripts: FindThinFaces (sliver, угол <5°); Python: fbx_polygon_count (сверка нулевых площадей по FBX без Max); SHA256: FindThinFacesEditMesh (3).ms 724206451d34d47e1bbc4b3b32890e5bf926b4d506805e4910ba9a4fe0104a39, fbx_polygon_count.py 9b4136621c4417d24fa1069adb06edcbe22585612e7ddb52f26889158a41441d | взять + исправить: keep the finder; Remove Overlayed has probable errors; VertexCleaner weight is not metres; team-audit: advisory sliver_face (в исходнике порог фактически 0,087° вместо 5° — сравнивать градусы); FBX-сверка после экспорта | TOW02: 64 tris + 44 faces < 2 cm (pr392 retro); team-audit T04/find_thin_faces, T04/fbx_polygon_count (GeoAGR-private work/team-scripts-audit) | NPM-2.3-7.b NPM-2.3-7.c VPM-2.3-11.b VPM-2.3-11.c | чтение | yes | P1 | 0.7 |
| 7 Проверки и сдача | Адрес и улицы (`qa.address`) | Проверка Address по справочнику улиц, составных частей и длины | GeoAGR: Check Adress btn_check_names GeoAGR.ms:15355, Streets List btn_Streets_List :42460 | взять + исправить: address filter and/or defect (P28–P30) | - | NPM-1.3-2.a NPM-1.3-3.a VPM-1.3-2.a VPM-1.3-3.a | чтение | yes | P2 | 0.9 |
| 7 Проверки и сдача | Сравнение с листом фасада (`qa.facade_compare`) | Картинка «лист \| ВПМ \| НПМ» в одном масштабе и счёт швов | pilot: jobs/TEC26-OKS render_facades / joint_count / compare_facades (520 lines) | новое: after this picture existed there were no more rejections | TEC26 (job-retro-tec26-oks-pr574.md §Summary) | - | чтение | yes | P2 | 0.9 |
| 7 Проверки и сдача | Нормали и двойные грани (`qa.normals`) | Нормали к наблюдателю, двусторонние полигоны стекла/Flora, сглаживание | GeoAGR: Double Faces btn_DoubleFaces GeoAGR.ms:49204, View Normals btn_View_Normals GeoAGR.ms:47595 | взять как есть: unverified: confirm on a disposable scene | - | NPM-2.3-8.a NPM-2.3-15 VPM-2.3-14 VPM-2.3-15.a VPM-2.12-3 | чтение | yes | P2 | 0.9 |
| 7 Проверки и сдача | Сверка с SINTEZ (`qa.sintez`) | Сравнивает наши находки с отчётом SINTEZ по тем же правилам | pilot: tools/sintez_parity.py | взять как есть | TEC26: SINTEZ 2.3.17 fail (pr574 retro) | VPM-2.3-17 | чтение | yes | P2 | 0.9 |
| 7 Проверки и сдача | Процедурные объекты (`qa.procedural_objects`) | Находит несвёрнутые объекты Forest Pack, RailClone, MultiScatter, Chaos Scatter, tyFlow, RayFire и Populate перед экспортом FBX; только отчёт и выделение, ничего не сворачивает | team-audit T07 сторонние плагины: карточки scatter (Forest Pack Pro 9.2.4, RailClone Pro, MultiScatter 1.630, Chaos Scatter), vfx (RayFire 2024, tyFlow), splineland_populate (Populate); только имена классов объектов, без кода плагинов | новое: решение Артёма 05.11.2026 (#973), конфликт 8: только чтение; установка плагинов в Max 2024 measured (T07); неполный экспорт таких объектов в FBX — hypothesis, измерить в слайсе экспорта; свой scatter не писать; учесть в qa.tris | team-audit T07/scatter, T07/vfx, T07/splineland_populate; T07 REPORT топ-1 (GeoAGR-private work/team-scripts-audit/T07) | - | чтение | yes | P2 | 0.9 |
| 7 Проверки и сдача | Код ОМК ТЭ (`qa.omk_te`) | Поиск кода классификатора по таблице и вставка | GeoAGR: Get OMK TE Code btn_omkte GeoAGR.ms:66030 | взять + исправить: Copy to Clipboard with a filter copies the wrong code | - | NPM-2.10-3.1 | чтение | yes | P3 | 1.x |
| 8 Экспорт и пакет | Экспорт с проверкой (`export.checked`) | Один FBX на AGR_EXPORT_PATH: ворота → FBX → readback | AGR Tools 0.4.0 export; GeoAGR: Export LowPoly :66532, HighPoly :66904 | готово | #731 | NPM-1.1-1 VPM-1.1-1 NPM-2.1-3.c | новые файлы | yes | P1 | 0.4 |
| 8 Экспорт и пакет | Очистка перед экспортом (`export.cleanup`) | CA, UDP, лишние каналы, канал 1 «UV» — план, затем копии | AGR Tools 0.1.0 cleanup; Telegram: ClearCustomAttributesAndObjProp_010.ms; Telegram: ClearCustomAttributesAndObjProp_010.ms (CA & UDP Cleaner v010); SHA256: ClearCustomAttributesAndObjProp_010.ms c1c52e21cf5adf67e6c35a5719669754a7511335573f778128f2a0c26904e53c | готово: team audit R3; team-audit: opt-in удаление вершинных каналов 0/−1/−2 и ключей анимации только на копиях, по умолчанию выключено; AGR_EXPORT_PATH не трогать; заменяет Octopus «Delete CustomAtr» и A101 CleanCAandUDP | #707; #547; team-audit T06/clear_ca_udp_010, T06/a101_clean_ca_udp_mcr, T06/clear_ca_udp_001 (GeoAGR-private work/team-scripts-audit) | VPM-2.3-11.e | копии | yes | P1 | 0.1 |
| 8 Экспорт и пакет | Паспорт GeoJSON (`export.geojson_write`) | Пишет GeoJSON из сцены (пивот, положение, адрес, превью) и сразу проверяет | GeoAGR: GeoJSON Create/Save/Load GeoAGR.ms:64642–64644 (disabled), Base64 to Clipboard :64853 | новое: GeoAGR gap #1: buttons disabled, no validator | GeoJSON for every package (D-matrix 29 GJ rows, 25 manual) | VPM-2.2-1 VPM-2.2-2 VPM-2.2-6.a VPM-2.2-7 GJ-1 GJ-19.a GJ-19.b GJ-21.a VPM-2.10-4.1.e | новые файлы | yes | P1 | 0.8 |
| 8 Экспорт и пакет | FBX благоустройства (`export.ground_fbx`) | Ground, GroundEl, Flora, GroundGlass в один файл _Ground | GeoAGR: Export LowPoly :66532 (Ground branch); Telegram: A101AGRLP.ms Ground rollout :388 | взять + исправить: лаборатория #907: Flora not in _Ground, name from first selected, no triangulation; one export path with modes | Vatutino Ground v014/v015 | NPM-2.1-5.a VPM-2.1-4 | новые файлы | yes | P1 | 0.8 |
| 8 Экспорт и пакет | Пивот и положение (`export.pivot_place`) | НПМ в МСК с высотами, ВПМ в ноль (чистый пол); пивот на копиях | GeoAGR: Geojson Get/Set Pivot btn_pivot_get GeoAGR.ms:64763, btn_pivot_set :64778, Reset Transforms btn_resetXForm :64709, Combine near zero btn_combine_two_models :64730; codex-3ds-max: ac-pivot-align rotate_pivot_tool.ms (оси пивота, dry-run, откат); zavod: straighten_object.ms (ориентация по PCA), align_door_pivots.ms (пивот дверей); SHA256: rotate_pivot_tool.ms 6344571ffbe927de8a481462136d6dd84f9e0ff7d28d167198891b8fc5f41e20, straighten_object.ms 94005feffe55aff35a2a3201376e6c054d2627556555b661510d390fb5010221, align_door_pivots_to_bottom.ms e22ab117fb9741ce5afb9f8069bd63abe4ccab2d431a9b4609a12a4750611608 | взять + исправить: unverified; never move working objects; team-audit: пивот нативным setter, не сдвигом вершин (двери: меш уезжает на 491/1675); PCA пересчитывать после каждого поворота; сцены в см и далёкие координаты не проверены | TEC26 ±0.000 reference open (STATE.md); team-audit T06/ac_pivot_align, T08/straighten_object, T03/align_door_pivots (GeoAGR-private work/team-scripts-audit) | NPM-2.8-1 NPM-2.8-2 VPM-2.9-4.b VPM-2.9-5 | копии | yes | P1 | 0.8 |
| 8 Экспорт и пакет | Архив пакета (`export.zip`) | ZIP НПМ/ВПМ с лимитами 500 МБ / 1 ГБ (двоичные), проверка до и после | GeoAGR: Archivate All btn_archivate GeoAGR.ms:66229; Telegram: AGR Zipper v2.1; Telegram: AGR_Zipper.zip v2.1 25.06 (папка → ZIP, «в НПМ только FBX», единый Address); owner-tools: AGR_Arxiv 1.5 (только документация — контракт как спецификация); SHA256: AGR_Zipper.zip 2bdd7ff2857cebfcba7a60f7e836512408e0d4d3c42758b88bd079117d35f4b7, README.txt f16fca2a678374a25b1853b530fbd3889b591164b2ac099857814895ad994b02, Инструкция.md 3399a62cc220abd3d999f4b3de97f1a65114f1b9dc1989b783618c1c0983f66a, SHA256.txt 800aab31d729c9459fc4bf890526d989dfacf107714ac9417962d69ac53bd8e4 | слить дубли: bundled 7z.exe without 7z.dll creates nothing (CLI); _Light missing in VPM archive; Ground limit 500 MB vs 1 GB (66340); team-audit: контракт Arxiv — новая папка, без перезаписи, маркеры ГОТОВО/ОШИБКА; pickle-IPC Zipper не брать; ../ и абсолютные имена запрещены | D015 binary units; team-audit T06/agr_zipper_2506, T06/agr_arxiv (GeoAGR-private work/team-scripts-audit) | NPM-2.1-1.a VPM-2.1-1.a VPM-2.1-1.b VPM-2.1-2.b | новые файлы | yes | P1 | 0.8 |
| 8 Экспорт и пакет | Пакетный экспорт (`export.batch`) | Все FBX сцены по AGR_EXPORT_PATH одним запуском с одним отчётом | AGR Tools 0.4.0 export (one FBX) | новое | TEC26: 9 OKS + truba + KPP (census) | NPM-2.1-2 | новые файлы | yes | P2 | 0.9 |
| 8 Экспорт и пакет | Поставить по паспорту (`export.place_by_passport`) | Импортирует FBX и ставит его в координаты [x, y, h_relief] из GeoJSON-паспорта рядом | new-telegram: Import_HP_from_coordinates.ms; SHA256: Import_HP_from_coordinates.ms ecb001a9b2a5447ee7f7cc696a3af5412aad01348b249f088c0cf590f9778675 | взять + исправить: настоящий JSON-парсер вместо построчного execute (исполнение кода из файла данных); Dummy удалять при ошибке | team-audit T06/import_hp_from_coordinates (measured Max 2026); team-audit T06/import_hp_from_coordinates (GeoAGR-private work/team-scripts-audit) | - | undo | yes | P3 | 1.x |
| 9 Освещение ВПМ | Проверка света (`light.check`) | ≤250 источников, только Omni/Spot, Omni ≥5 м, Spot ≥1.5 м, корень и пивот | GeoAGR: Light Manager btn_Lights GeoAGR.ms:56146; Telegram: agr_max_check_37.ms lights, Light_Metr.ms; Telegram: Light_Metr.ms (исправленный: units.SystemScale, UX выделения нарушителей); agr_max_check_37.ms runLightCheck (правила файла света); SHA256: Light_Metr.ms 6a51ed409bb4c42eeb6eccb75fe0cfaabf1566b9438bcc717dd346e9b75e6af5, agr_max_check_37.ms ead3866924bfa3bf9efe54619072e2ce810141bc8b7b914b5169f2ff600e59a2 | слить дубли: GeoAGR distances in system units; light index cap 50 dropped (R6); team-audit: дистанции через SystemScale (decodeValue: 1.5m→1.0 на ru-RU, измерено); без лимита номера 050; 0.9 подтверждено Артёмом 05.11.2026 — ежедневная Light_Distance сейчас пропускает нарушения | GeoAGR gap #7; team-audit T05/light_metr, T04/agr_max_check_37 (GeoAGR-private work/team-scripts-audit) | VPM-2.15-2 VPM-2.15-4 VPM-2.15-5.a VPM-2.15-5.b VPM-2.15-6 VPM-2.15-8 VPM-2.15-9.b | выделение | yes | P1 | 0.9 |
| 9 Освещение ВПМ | FBX освещения _Light (`light.export`) | Отдельный FBX света с корнем, Omni не теряются, в архив ВПМ | GeoAGR: Export HighPoly :66904, ReSave Lights FBXs :65127 | взять + исправить: Omni do not reach _Light.fbx (66915, 66977); _Light not archived (66307) | GeoAGR gap #7 | VPM-2.1-2.b VPM-2.11-0.f VPM-2.11-0.g VPM-2.10-4.1.c VPM-2.10-4.5 | новые файлы | yes | P2 | 1.0 |
| 9 Освещение ВПМ | Расстановка Free Spot (`light.place`) | Ставит Free Spot по выделенным полигонам и прореживает | zavod: lighting/Light.ms (много полигонов, один undo); Telegram: Light.ms (Octopus «Light_to_Normal»); Andrew_scripts: FreeSpot_Tools.ms (FreeSpot Optimizer, прореживание grid/greedy); GeoAGR: Light Placer GeoAGR.ms:56468 / btn_process :56535 (кластеризация, отступ); SHA256: Light.ms 958b9268c72f99e0584fb1710a70fa84405b0cb48ee8277a13dd0a8735a55151, FreeSpot_Tools.ms 5bfa25787d9c8f0eff4c0e50da4eefd322581b5cfd76e23ac5909cb1b2ff09dd | слить дубли: математика размещения — zavod Light.ms; не брать: clusters 400→2 (FreeSpot:352-421), шаблонный спот в выборке, «последний полигон побеждает» (Light.ms:13-14), дистанции в системных единицах; FreeSpot_Tools сейчас не грузится (лишняя «)») | team-audit T05/light_zavod_multipoly, T05/freespot_tools, T05/light_to_normal_telegram (measured); team-audit T05/light_zavod_multipoly, T05/freespot_tools, T05/light_to_normal_telegram (GeoAGR-private work/team-scripts-audit) | VPM-2.15-1 VPM-2.15-3.c | undo | no | P3 | 1.x |

## 5. Шум: что сознательно отброшено

| # | Источник | Что | Почему отброшено |
|---|---|---|---|
| 1 | GeoAGR | Rules / Technologies rollouts (GeoAGR.ms:11452, :12282) | duplicate: rules1–5.csv and tech1–4.txt notes; standards/ and docs/domain are the source |
| 2 | GeoAGR | RulesCheck_lowpoly / RulesCheck_highpoly (:9136, :11204) | dead UI (D7), old rules2 edition; replaced by qa.preflight + qa.package |
| 3 | GeoAGR | Prepare LowPoly / Prepare HighPoly as buttons (:65278, :65653) | destructive (D6: ResetXForm + collapse + channel delete) and D1/D2/D3/D8; their checks move to qa.preflight |
| 4 | GeoAGR | File → Reset Scene and Import All (:64936) | destructive: resetMaxFile and units/gamma change without a question |
| 5 | GeoAGR | Archive import / Archivate via bundled 7z.exe (:3935, :4000, :64987) | broken: 7z.exe without 7z.dll creates nothing (CLI); export.zip uses Python zipfile |
| 6 | GeoAGR | UCX Make Box (:63673) | broken: crashes `undefined → Integer` (T10-03), deletes the last object on empty selection |
| 7 | GeoAGR | UCX Make All (:63721) | author PC only (GEOMOBIL) and radians passed to cos/sin |
| 8 | GeoAGR | UCX Make Concave Form (:63505) | duplicate: always a convex hull (T10-04) = ucx.build single-hull |
| 9 | GeoAGR | Faces Overlap Analyzer (:48481, FastFaceFinder.dll) | broken: FindOverlaps called with 17 args, DLL has 5 (T08-11); native xView is the gate (D152) |
| 10 | GeoAGR | Nearest / Target Weld (:51489) | broken index after the first weld (T08-07); Max native Target Weld |
| 11 | GeoAGR | Points from Clipboard (Obj_tools) | destructive: LMB executes clipboard text, RMB `delete $Point*` |
| 12 | GeoAGR | Turbo Attacher → Clean Scene (:54818) | destructive: breaks every group, deletes Dummy/Point, layer 0, undo off |
| 13 | GeoAGR | Make LowPoly MAF / Tree render passes (:43460, :43960) | needs Corona; switches renderer, gamma and layout without restore; our MAF set is built in Blender |
| 14 | GeoAGR | Blend Editor (:30416) | broken: bare set/off/modulate tokens in the magick command, file is not written |
| 15 | GeoAGR | Texture Editor / Edit Bitmaps floaters (:23574, :30251) | image editing; never used in pilot jobs; Photoshop/Substance do it |
| 16 | GeoAGR | World Align, UV Combine, UVs Arcs Aligner, UVs Grouper (:20557, :17529, :18986, :19666) | collapse the stack; RizomUV/UVTools are the daily UV tools (team-plugins-audit step 6) |
| 17 | GeoAGR | Unwrap Windows RMB (:16461) | broken: calls commented-out getIslands; the formula worsens the spread (T04-02) |
| 18 | GeoAGR | Spikes Finder (:53717) | broken on the last face vertex (T09-04); qa.zero_area covers degenerate faces |
| 19 | GeoAGR | Edges Cut, Select Angle Objects, Select in View | author PC only (GEOMOBIL) |
| 20 | GeoAGR | Handlers without controls and controls without handlers (README §7) | dead code |
| 21 | GeoAGR | TooltipReader + 42 tooltips_*.ini (:5546) | erases built-in tooltips; Qt tooltips in the 0.6 UI |
| 22 | GeoAGR | Docker → auto-update (:67038) | disabled; the .mzp package and CHANGELOG replace it |
| 23 | GeoAGR | Licence form, GeoAGR.exe, .mse encryption | not ported: no licensing or obfuscation (AGR Tools README) |
| 24 | GeoAGR | Check with Moscow borders (:64652) | broken: Moscow_boundaries_MSK.max is not in the archive; GeoJSON checker covers coordinates |
| 25 | GeoAGR | Light Manager «change type» (re-creates lights) | destructive; the check part is kept in light.check |
| 26 | Telegram | Light index cap 50 (agr_max_check_37.ms:460) | obsolete rule: names 001–250 (team audit R6) |
| 27 | Telegram | Overlap normal filter 2 % and Blender 2 mm / 8° checkers | differ from D152; native xView is the gate (R2) |
| 28 | Telegram | UCX generator pads 0.04 / 0.035 (UCX_N_29.09.ms:23-24) | team default, not a delivery rule (D180, R4) |
| 29 | Telegram | Material ID = UDIM tile (UDIM-MultiSub_Universal.ms:5) | contradicts D030: IDs are a reading scheme (R5) |
| 30 | Telegram | VPM_to_NPM 6 px padding, plug ≤512 (VPM_to_NPM.ms:12, :35) | below NPM 8 px; plug is 128 for flat MR only (R1, R9) |
| 31 | Telegram | AlexYo OneByOne library export (v18) | library ZIP Name_high/Name_low is not a delivery path (R12) |
| 32 | Telegram | apply_atlas_uv.ms camera bake | bakes through cameras; the pilot builds the atlas from UDIM tiles (atlas.npm) |
| 33 | Telegram | AutoCAD LISP (NUM2CIRCLE, SelectNumbers, EXPORTCIRCLESCSV) | not 3ds Max (R10) |
| 34 | Telegram | CoronaProxyDisplay_EN.ms | Corona viewport helper; Corona is not a delivery renderer (NPM-2.4-1.b) |
| 35 | plugins | h_instancer | instances are not exported (R20) |
| 36 | plugins | TS_NameUCXPrimitives.ms, TS_UE4FBXExporter.ms | UE4 two-digit UCX names and a 2014 exporter (R21) |
| 37 | plugins | layers_polycount.ms, Optimise_info(_2).ms | 100 000 polygons per layer and node moves; budgets are triangles per FBX (R16) |
| 38 | plugins | index to rgb.py | 8-bit palette plugs; delivery is 24-bit (R18) |
| 39 | plugins | density.ms | assumes a 4096 map (R15); udim.texel reads the real map size |
| 40 | plugins | A101 bitmap ladder 128–2048 and 8-bit warning (A101AGRLP.ms:1307-1327) | obsolete: 4096 legal in VPM, delivery is 24-bit (R13) |
| 41 | plugins | Flora Atlas defaults 2 px / 8192 | wrong for AGR; packer kept with profile values (R17) |
| 42 | plugins | Commercial daily tools (RizomUV, UVTools, SiNi, rapidTools, Prune Scene, MultiScatter, Copitor) | products, not repo code; the suite links to them where they are the step (R22) |

## 6. Дорожная карта

| Версия | Содержание | Статус | Кнопок | P1/P2/P3 | Оценка | Issue |
|---|---|---|---|---|---|---|
| 0.1 | Каркас пакета + xView, очистка, MatID | done | 3 | 3/0/0 | - | #707 |
| 0.2 | UV-сдвиг на целый тайл + UDIM → атлас НПМ | done | 2 | 2/0/0 | - | #722 |
| 0.3 | UCX-генератор + тексель | done | 2 | 2/0/0 | - | #728 |
| 0.4 | Экспорт с проверкой (ворота → FBX → readback) | done | 1 | 1/0/0 | - | #731 |
| 0.5 | Имена, треугольники по FBX, текстуры всех объектов, пивот, GeoJSON | done | 5 | 5/0/0 | - | #804 |
| 0.6 | Qt-панель: док, иконки Dark/Light, прогресс/отмена, меню, пакет | done | 0 | 0/0/0 | - | #808 |
| 0.7 | Предсдача: недостающие проверки (только чтение) + блоковые цвета UI + перепись сцены | done | 12 | 12/0/0 | L: ~2 дня агента (11 проверок на готовых twinqa-модулях, без правок сцены) | #860 |
| 0.8 | Сдача: имена, PNG, ID→UDIM, триангуляция, пивот, GeoJSON, ZIP, пакет | done | 13 | 10/3/0 | L: ~3 дня (правки только на копиях/новых файлах, каждая с preview) | #908 |
| 0.9 | Замены и расстановка, Flora/МАФ, покраска по легенде, сравнение с фасадом | done | 19 | 6/13/0 | L+: ~4–5 дней (3 дня плановых строк + доработки готовых 0.8-кнопок) | #979 |
| 1.0 | Моделирование, UDIM/UCX-инструменты, свет ВПМ (P2) | planned | 18 | 0/17/1 | XL: ~5–6 дней; резать на 1.0a модель+рельеф+сетка и 1.0b UCX+UDIM | new |
| 1.x | Хвост P3 (вспомогательные, по запросу) | backlog | 17 | 0/0/17 | по одной кнопке, S | - |

Состав версий (id кнопок):

- **0.1**: `qa.matid`, `qa.xview`, `export.cleanup`
- **0.2**: `udim.nudge`, `atlas.npm`
- **0.3**: `ucx.build`, `udim.texel`
- **0.4**: `export.checked`
- **0.5**: `tex.check`, `qa.geojson`, `qa.names`, `qa.pivot`, `qa.tris`
- **0.7**: `scene.census`, `scene.units`, `model.perimeter_drop`, `tex.material_type`, `ucx.audit`, `atlas.sets_count`, `qa.fbx_split`, `qa.glass`, `qa.preflight`, `qa.scene_hygiene`, `qa.xform`, `qa.zero_area`
- **0.8**: `scene.missing_maps`, `model.triangulate`, `tex.format_fix`, `tex.placeholders`, `ucx.triangulate`, `ucx.rename`, `udim.ids_to_udims`, `qa.names_fix`, `qa.package`, `export.geojson_write`, `export.ground_fbx`, `export.pivot_place`, `export.zip`
- **0.9**: `tex.erm_normal_check`, `tex.finish_map`, `udim.matid_unwrap`, `udim.slots`, `atlas.flora`, `atlas.groundel`, `place.flora_repair`, `place.maf_checks`, `place.replace`, `place.schedule`, `place.drop_to_ground`, `qa.address`, `qa.facade_compare`, `qa.normals`, `qa.sintez`, `export.batch`, `scene.maps_usage`, `light.check`, `qa.procedural_objects`
- **1.0**: `scene.source_class`, `model.glass_planes`, `model.ground_border`, `model.ground_slice`, `model.ground_surface`, `model.move_apart`, `tex.dilate`, `tex.vpm_sets`, `ucx.gap`, `ucx.ground`, `udim.rescale`, `udim.unwrap_tiles`, `atlas.facade_strip`, `place.maf_generator`, `light.export`, `scene.small_parts`, `model.grid_cleanup`, `model.attach_by_material`
- **1.x**: `model.three_pt_align`, `model.window_placer`, `tex.browser`, `tex.multimat`, `tex.plug_colour`, `ucx.stairs`, `udim.distortion`, `udim.udims_to_ids`, `udim.viewer`, `atlas.unatlas`, `place.scatter`, `place.tree_cards`, `qa.omk_te`, `light.place`, `model.pipe_lo`, `udim.plugs`, `export.place_by_passport`

Почему такой порядок:

1. **0.7 — сначала проверки.** Больше всего переделок в работах дали ошибки, которые никто не проверил до сдачи. В TOW02
   своя проверка показала 0 перекрытий, а xView нашёл 185 граней (~2.5 ч). В TEC26 опуск периметра ≥ 1 м добавили
   после первой картинки. У GeoAGR 13 главных пробелов: GeoJSON, стекло, разделение FBX, трансформы, опуск периметра.
   Все кнопки 0.7 только читают сцену, работают на готовых модулях `twinqa` и сразу становятся инструментами MCP.
   Это самая дешёвая версия на единицу пользы.
2. **0.8 — сдача.** Пакет собирается и проверяется в одном месте: имена, PNG, ID → UDIM, триангуляция, пивот, GeoJSON и
   ZIP. Это закрывает рецепт GeoAGR `export_archive`, который сейчас разрушает сцену (D6), архивирует через неработающий
   7z (CLI) и теряет `_Light`.
3. **0.9 — замены и расстановка.** Сюда входят МАФ/Flora (Vatutino), покраска по легенде и сравнение с листом фасада
   (TEC26: ~6 ч переделок и 10 сборок). Всё это переносится из job-скриптов, которые уже прошли приёмку.
4. **1.0 — моделирование и UV/UCX-инструменты (P2).** Это инструменты с правкой геометрии: у них самый высокий риск и
   ниже повторяемость между работами. Версию можно разрезать на 1.0a (модель + рельеф) и 1.0b (UCX + UDIM + свет).
5. **1.x — хвост P3**: делается по запросу, по одной кнопке.

Оценки даны в днях агента и включают тесты, ревью и один прогон в Max через общий lock. Это порядок величины, не
обещание.

## 7. Макет UI и цвет

Картинки (Drive, `G:/Мой диск/AGR-evidence/agr-tools-suite/`, хэши в `SHA256SUMS.txt`):

| Файл | Что показывает |
|---|---|
| `mockup_dark_qa.png`, `mockup_light_qa.png` | Панель 0.6, расширенная до всех блоков; открыта вкладка «7 Проверки», внизу таблица «Предсдачи» с находками из разных блоков |
| `mockup_dark_model.png`, `mockup_light_model.png` | Та же панель, открыта вкладка «1 Модель» |
| `suite_map_dark.png`, `suite_map_light.png` | Карта всех 90 кнопок по блокам; чип версии означает «ещё не сделано» |
| `icons_dark.png`, `icons_light.png` | Набор иконок по блокам в цвете блока: 13 из 0.6.0 и новые в том же стиле (сетка 24, штрих 1.6) |
| `palette.png`, `palette.tsv` | Цвета блоков и статусов для обеих тем с контрастом к фону |
| `make_mockup.py`, `make_suite.py`, `suite_data.py`, `plan_template.md`, `agr_icons_808.py`, `*853.py` | Как всё получено |

**Рекомендация: вкладки-рельс + сворачиваемые секции внутри вкладки.** Если сделать одну длинную панель из
сворачиваемых секций, получится 90 кнопок в 10 секциях. Это несколько экранов прокрутки, и таблица результатов
уходит вниз. Рельс слева держит все 10 блоков на виду: номер, короткое имя и значок в цвете блока. Таблица
результатов остаётся под рабочей областью всегда. Внутри вкладки у блока две секции с одинаковым смыслом во всех
блоках:

- «Проверить и выделить — сцена не меняется»;
- «Исправить — копии / undo / новые файлы».

Так безопасность кнопки видна по месту.

**Цвет.**

- У каждого блока один тон (hue). Он даёт полоску заголовка вкладки, полоску рельса и цвет значков.
- Тон берётся не готовым hex. Он **выводится из темы Max**. `accent(hue, theme)` берёт цвета window и base из Qt-палитры
  (в Max — палитра приложения или `colorMan`) и сдвигает светлоту от фона, пока контраст не станет ≥ 3:1 и к window,
  и к base (WCAG для нетекстовых элементов). Так Dark и Light читаются одинаково. Если контраст недостижим, функция
  падает с ошибкой и не отдаёт бледный цвет.
- Статусы (ошибка, внимание, ок) — отдельные тона 2°, 38° и 132°. Тон каждого блока отстоит от них не меньше чем на 25°.
  Кроме цвета, у каждого статуса есть своя форма значка: крест, треугольник, галочка. В таблице результатов статус
  показывает, *что* случилось, а значок блока в цвете блока — *где*.
- 0 «Сцена» нейтральная (почти серая), потому что это служебный блок.

Тона: 0 Сцена — нейтральный; 1 Модель 212°; 2 Текстуры 276°; 3 UCX 162°; 4 UDIM 234°; 5 Атласы 298°;
6 Замены 85°; 7 Проверки 190°; 8 Экспорт 256°; 9 Свет 320°. Тоны блоков отстоят друг от друга на 20–30°.
Это предел для 9 цветных блоков, если не заходить на тона статусов. Поэтому цвет — второй признак, первый признак —
номер и значок.

**Иконки.** Новые иконки нарисованы в стиле утверждённого листа 0.6.0: монохромный SVG на сетке 24, штрих 1.6, свои
примитивы, без сторонних шрифтов. Значки «применить / проверить / исправить / посмотреть» — это общие бейджи поверх
уменьшенного базового значка, как `*_apply` в 0.6.0. В панели значок окрашивается цветом блока: `currentColor`
заменяется на `accent()`.

## 8. MCP

Каждая кнопка с `MCP = yes` — это инструмент сервера `agr-mcp`. Он вызывает то же ядро, что и панель, и возвращает тот же
JSON-отчёт (`schema`, `tool`, `status`, `objects`). Из 90 кнопок «нет» стоит у тех, которые нужны только руками в
вьюпорте: выделение региона, выравнивание по 3 точкам, повтор операций Poly Actions, просмотрщики, скаттер. Фаза 0 MCP
(#841) берёт только кнопки «чтение». Кнопки с правкой подключаются версией вместе с их `preview`.

## 9. Проверки этого плана

- `make_suite.py` валидирует таблицу и при ошибке ничего не пишет. Ошибкой считаются: повтор id; неизвестный блок,
  вердикт, режим, приоритет или версия; id требования, которого нет в матрице GeoAGR; ссылка `btn_* GeoAGR.ms:N`, если
  в строках N±3 нет этого имени; «готово» без готовой версии; пустое поле.
- `make_mockup.py` проверяет цвет: тон блока против тона статуса ≥ 25°, тоны блоков попарно ≥ 20°, контраст всех 20
  цветов ≥ 3:1, недостижимый контраст вызывает ошибку. Ещё он проверяет, что каждая иконка — валидный SVG.
  Результаты прогона — в описании PR.

## 10. Вопросы Артёму (до 5)

1. **Порядок реализации.** Предлагаю строить по ценности: 0.7 проверки → 0.8 сдача → 0.9 замены/МАФ/Flora →
   1.0 моделирование. В панели блоки стоят в вашем порядке (моделирование первым). *Рекомендация: так и делать*, потому
   что переделки в работах шли от несданных проверок, а не от нехватки инструментов моделирования. Если моделирование
   нужно раньше, 1.0a (модель + рельеф) можно поставить второй.
2. **Вид панели.** Вкладки-рельс слева + две секции внутри вкладки или одна длинная панель секций, как в 0.6.0?
   *Рекомендация: рельс* — 90 кнопок в одной ленте займут несколько экранов.
3. **Когда цвет.** Макет #808 утверждён монохромным, и 0.6.0 сейчас в работе. *Рекомендация: 0.6.0 доделать как
   утверждено, цвета блоков и рельс ввести в 0.7.* Так не придётся снова открывать утверждённый gate #808.
4. **Два новых блока.** Оставить «0 Сцена и источник» и «9 Освещение ВПМ»? Свет ВПМ — 11 требований регламента, но в
   наших работах он ещё не встречался. *Рекомендация: оставить оба; «Свет» — P2 в 1.0, а «Сцена» идёт в 0.7, потому что
   без метров и переписи сцены остальные проверки врут (D5).*
5. **Как брать код GeoAGR.** Портировать в Python-ядро (`pymxs`) со ссылкой на строку, как в 0.5.0, или вставлять
   MAXScript-функции GeoAGR как есть? *Рекомендация: порт в Python-ядро.* Тогда одно ядро обслуживает и панель, и MCP,
   есть тесты без Max, а дефекты GeoAGR (D1–D8 и находки T…) закрываются при переносе. Командные скрипты (Andrew,
   Telegram) — так же: берём идею и порог из регламента, а не код и дефолты [D180].

После ответов карточка ждёт «да» на план и макет. Каждая версия 0.7–1.0 потом становится отдельной issue с этой
таблицей как спецификацией.

## 11. Тестовый полигон

Синтетическая сцена для кнопок AGR Tools лежит в `test-polygon/` (issue #885). Собранный `.max` и FBX туда не
коммитятся: их пишет сборщик в `G:/Мой диск/AGR-evidence/test-polygon/` (если диска нет — `C:/x/test-polygon/`).

Сцена — ряд баз по версиям, не зоны по блокам. Одна база = один цветной прямоугольник на земле и подпись
«База 0.x — что добавила версия, какие кнопки». Внутри — станции: объект (или небольшая группа) и подпись
«Станция 0.x.N: объект - нажми кнопка -> ожидаешь результат». Обход 0.1 → 0.7 проходит концепцию AGR Tools.
База 0.6 — панель без кнопок, станций у неё нет. Следующая версия добавляет свою базу в конец ряда.

Прямоугольники: слой `_bases`, имена `_base_*`. Подписи: слой `_labels` (его можно скрыть), имена `_label_*`.
Оба не экспортируются и не входят в проверки. Сборщик кладёт их только на эти слои с этими префиксами.
Раннер выбрасывает такие имена из отчёта до сравнения с `expected/`. Офлайн-ядра их не получают.

Порядок один и тот же в `test-polygon/bases.json`, в `expected/<id>.json` (`base`, `station`, `stations`),
в README и здесь: база → станция → кнопка → файл ожидания. Таблица самопроверки (`report.json` и `table.txt`)
группирует строки так же и добавляет колонку «получилось» (статус и коды живого отчёта). Код выхода — число
расхождений. Строка известной ошибки #886 печатается `НЕ OK (известная ошибка #886)` и считается в поле
`known_bug`, не в коде выхода. В `AGR_TEST` каждого объекта записан id станции (`station=0.3.2`).

`export.cleanup` и `export.checked` держат и PASS, и FAIL. FAIL очистки — объект с `AGR_TEST`. PASS —
прогон «Очистка → копии» (`apply_status` pass) на копии `*_AGR_export_`. FAIL экспорта — ворота `cleanup`
на том же грязном оригинале. PASS экспорта — эта копия пишется в новый FBX
`<результат>/export-pass/<имя копии>.fbx` и читается обратно (`plan.readback`). Без readback это не pass.

| База | Станция | Кнопка | Ожидание |
|---|---|---|---|
| 0.1 | 0.1.1 | `qa.matid` | `test-polygon/expected/qa.matid.json` |
| 0.1 | 0.1.2 | `qa.xview` | `test-polygon/expected/qa.xview.json` |
| 0.1 | 0.1.3 | `export.cleanup` | `test-polygon/expected/export.cleanup.json` |
| 0.2 | 0.2.1 | `udim.nudge` | `test-polygon/expected/udim.nudge.json` |
| 0.2 | 0.2.2 | `atlas.npm` | `test-polygon/expected/atlas.npm.json` |
| 0.3 | 0.3.1 | `ucx.build` | `test-polygon/expected/ucx.build.json` |
| 0.3 | 0.3.2 | `udim.texel` | `test-polygon/expected/udim.texel.json` |
| 0.4 | 0.4.1 | `export.checked` | `test-polygon/expected/export.checked.json` |
| 0.5 | 0.5.1 | `tex.check` | `test-polygon/expected/tex.check.json` |
| 0.5 | 0.5.2 | `qa.geojson` | `test-polygon/expected/qa.geojson.json` |
| 0.5 | 0.5.3 | `qa.names` | `test-polygon/expected/qa.names.json` |
| 0.5 | 0.5.4 | `qa.pivot` | `test-polygon/expected/qa.pivot.json` |
| 0.5 | 0.5.5 | `qa.tris` | `test-polygon/expected/qa.tris.json` |
| 0.6 | — | кнопок нет | площадка панели, без станции |
| 0.7 | 0.7.1–0.7.12 | 12 кнопок предсдачи | `test-polygon/expected/<id>.json` |

Версия кнопки читается из этого плана (`agr-tools-suite.json`), не из имени станции. Кнопки 0.8 и новее
пока без станции: в JSON есть `reason`.

Правило: каждая новая кнопка в том же изменении добавляет станцию на базу своей версии, объекты полигона и
файл `test-polygon/expected/<id>.json`. В записи есть хотя бы один PASS и один FAIL, либо явная причина, почему
одного из них нет. Id станций уникальны, станция принадлежит существующей базе. Офлайн-тест
`tests/max_tools/test_polygon_expected.py` сверяет это с каждым id из `docs/plans/agr-tools-suite.json`. Кнопка без
записи — ошибка, имя кнопки названо.

Раннер полигона не устанавливает и не удаляет `%APPDATA%\Autodesk\ApplicationPlugins\AGR-Tools.bundle`.
Установка, если она появится, сначала уносит этот каталог в сторону и в `finally` возвращает те же байты
(`polygon_core.preserve_user_bundle`). Пакет оператора не удаляется.

## 12. Аудит командных скриптов (утверждено Артёмом 05.11.2026)

Источник: GeoAGR-private `work/team-scripts-audit` (`SYNTHESIS.md` §4, `synthesis/plan_changes.json`, @1e9289cc).
Артём одобрил структуру («согласен»): в AGR Tools попадают только шаги сдачи НПМ/ВПМ; несколько скриптов одной
задачи — одна кнопка; личные удобства моделинга, рендер-инструменты и старые версии остаются вне AGR Tools.

Что изменено в таблице (`agr-tools-suite.json`, §4 и §6 выше):

- 15 строк дополнены (`source` и `verdict_note` дописаны, версия прежняя): доработка выпущенных кнопок 0.1/0.2/0.7/0.8
  идёт следующим выпуском. Исключение — `light.check`: 1.0 → **0.9**, P1, режим «выделение» (ежедневная
  Light_Distance пропускает нарушения).
- 12 плановых строк переписаны по группам аудита (`ucx.gap` теперь «UCX: нарезка и зазор» — режимы split/gap).
- 7 новых строк: 0.9 `scene.maps_usage`; 1.0 `model.grid_cleanup`, `model.attach_by_material`, `scene.small_parts`;
  1.x `udim.plugs`, `export.place_by_passport`, `model.pipe_lo`.
- В `source` каждой затронутой строки — имена командных файлов и их SHA256 (из `sources/team-scripts/MANIFEST.json`
  приватного репозитория); кода командных скриптов и GeoAGR здесь нет, только ссылки `GeoAGR.ms:<строка>`.
  В `evidence` — id карточек аудита.

Вне AGR Tools (строк в плане нет; 53 карточки аудита):

- **Личные скрипты моделинга (Octopus)** — только чинить баги: Poly X,Y,Z, Region Select, Poly Actions, Interior Box,
  Select Similar, MultiBridge, Edge Distributor, Floor Trace, ColorID, RndmWire, RemoveSelectedMaterials,
  OctopusMenuGenerator, переключатель CoronaProxy, Object Randomizer. Причина: не шаг сдачи НПМ/ВПМ.
- **Пилотный pipeline, не кнопки:** CLI zavod `tools/agr`, оценка File Link, intake-шаблоны (build_max, Ostrov,
  physical materials). Идеи — в source intake / AdapterReport пилота.
- **Только рендер:** Flora Lite, Corona proxy, Forest cleanup, CamSun, MasterSceneHelper, RAL- и Corona-материалы.
  Причина: вне сдачи НПМ/ВПМ.
- **Drop:** старые версии (UDIM Viewer v1, UDIM Tool v8.x, Renamer V11, OneByOne v18, AGR Zipper 22.06,
  Udim_Geo_Json, старая Flora Atlas); опасное или ненужное (maxxmlServer5 — удалённое исполнение по LAN, zavod Purge,
  SceneEventLogger, DriverMaster); шаблоны T09.

Конфликты PR #973 — решения Артёма 05.11.2026 («да»):

1. `ucx.build` split/gap — остаются в `ucx.gap` (1.0) «UCX: нарезка и зазор».
2. `atlas.npm` ← VPM_to_NPM — обновление строки, версия 0.2 прежняя.
3. `light.check` — в 0.9, подтверждено (`verdict_note`).
4. `model.detriangulate` и `model.tjunction_weld` слиты в `model.grid_cleanup` как режимы (детриангуляция,
   T-стыки); строки удалены, их источники (`GeoAGR.ms:48104`, `:51802`, `:51542`), требования и evidence
   перенесены в `model.grid_cleanup`.
5. `model.concave_fix` удалена: её источник (AlexYo_ConcaveFixer) теперь в `ucx.triangulate`.
6. `model.region_select`, `model.poly_actions`, `model.interior_box` удалены, Object Randomizer убран из
   источников `place.scatter` (см. «Вне AGR Tools» ниже).
7. OneByOne v19.3 (экспорт в библиотеку ассетов) — не добавлен, вопрос Q35 открыт.
8. Новая строка 0.9 `qa.procedural_objects` «Процедурные объекты» (только чтение): несвёрнутые Forest Pack,
   RailClone, MultiScatter, Chaos Scatter, tyFlow, RayFire, Populate до экспорта FBX. Источник — карточки T07
   сторонних плагинов (scatter, vfx, splineland_populate). Остальные пять предложений синтеза
   (`model.opening_grid_clean`, `model.ground_coverings_cad`, `model.three_pt_align` как своя реализация,
   `qa.instances`, `model.select_axis`) не добавлены.
9. «Texture Placeholder Creator» = Texture_Zaglushki_Ground.ms в `tex.placeholders` — подтверждено.

Итог: 92 строки (было 97: −6 удалённых, +1 новая); 0.9 = 19, 1.0 = 18, 1.x = 17; плановых 54.

Вне AGR Tools после решений (личные скрипты Артёма, строк нет): Region Select (Region_Cut.ms), Poly Actions
(Poly Actions Copy_V6.ms), Interior Box (Interier_Box.ms), Object Randomizer (objectrandomizerv3.ms); вопрос
Q35 — OneByOne v19.3.
