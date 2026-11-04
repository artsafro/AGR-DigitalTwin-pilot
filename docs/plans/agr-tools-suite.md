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

- 90 кнопок: готово 13, взять 16, взять + исправить 27, слить дубли 18, новое 16; P1 40 / P2 32 / P3 18; в MCP 77; только чтение/выделение 39; шум 42; ссылок на строки GeoAGR.ms проверено 29.
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
  рекомендации R1–R12), `docs/research/team-plugins-audit.md` + `team-plugins-inventory.json` (плагины Артёма и
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
| 0 | Сцена и источник | 4 | 2 | 0 | добавлен: TOW02 потерял ~1.5 ч, потому что класс источника не проверили до выбора маршрута (job-retro-vyatskaya-tow02-pr392); дефект GeoAGR D5 (тексель в 100 раз меньше в сцене в см) — это проблема единиц; TEC26 начался с 60-минутной переписи сцен (job-retro-tec26-oks-pr570). Все остальные блоки предполагают метры и известную сцену. |
| 1 | Моделирование | 15 | 2 | 0 | список Артёма |
| 2 | Текстуры и материалы | 11 | 3 | 1 | список Артёма |
| 3 | Коллизии UCX | 7 | 3 | 1 | список Артёма |
| 4 | UDIM и тексель | 10 | 3 | 2 | список Артёма |
| 5 | Атласы / не-атласы | 6 | 3 | 1 | список Артёма |
| 6 | Замены и расстановка | 8 | 4 | 0 | список Артёма |
| 7 | Проверки и сдача | 19 | 14 | 6 | список Артёма |
| 8 | Экспорт и пакет | 7 | 6 | 2 | список Артёма |
| 9 | Освещение ВПМ | 3 | 0 | 0 | добавлен: VPM-2.15-* (≤250 источников, только Omni/Spot, 5 м / 1.5 м, пивот корня) и VPM-2.1-2.b (FBX _Light) — правила сдачи; пробел GeoAGR №7 (Omni теряются в _Light.fbx, 66915) и три командных скрипта (Light.ms, Light_Metr.ms, FreeSpot_Tools.ms) показывают, что эта работа есть; ни один блок списка Артёма её не держит. |

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
| 0 Сцена и источник | Перепись сцены (`scene.census`) | JSON: объекты, Multi/Sub, карты, пропавшие файлы, bbox, units, инстансы | pilot: jobs/TEC26-OKS/census scripts; zavod agr_inspect_max.ms (ZAVOD review §4) | новое: generic headless census adapter; the retro names it an engine candidate (M) | TEC26: native census of 3 scenes, 60.4 min intake (docs/research/job-retro-tec26-oks-pr570.md) | NPM-2.1-1.b VPM-2.1-1.c | чтение | yes | P1 | 0.7 |
| 0 Сцена и источник | Единицы и гамма (`scene.units`) | Проверяет System Unit = метры, 1 unit = 1 m, гамму 2.2/1.0; предлагает исправить | GeoAGR: System Setup btn_set_meters GeoAGR.ms:12547, btn_set_alpha :12554 | взять + исправить: only check by default; Set Meters does not rescale geometry (playbook caveat); fixes D5 at the source | GeoAGR T06-02: texel 2048 px/m shown as 20.48 in a cm scene (D5) | NPM-1.2-1 VPM-1.2-1 | чтение | yes | P1 | 0.7 |
| 0 Сцена и источник | Пропавшие карты (`scene.missing_maps`) | Список битмапов с несуществующим путём и кандидаты для relink (без переименования файлов) | GeoAGR: Project Map btn_count_map GeoAGR.ms:15548; Collect Asset (third-party, read only part) | взять + исправить: read-only list; GeoAGR Project Map deletes/renames files (README §6) | TEC26: KPP folder had no ERM, railing 4096 not 2048 (jobs/TEC26-OKS/STATE.md) | NPM-2.1-1.b VPM-2.4-2 | чтение | yes | P2 | 0.8 |
| 0 Сцена и источник | Класс источника (`scene.source_class`) | Связные части, доля крупнейшей → оболочка / панели / сетка; до выбора маршрута | new | новое: read-only pre-check before any builder | TOW02: ~1.5 h dead end, 5 561 parts fed to a shell engine (job-retro-vyatskaya-tow02-pr392.md) | - | чтение | yes | P2 | 1.0 |
| 1 Моделирование | Опуск периметра ≥1 м (`model.perimeter_drop`) | Проверяет, что полигоны по периметру ОКС/Ground опущены ниже ±0.000 не меньше чем на 1 м | new | новое: GeoAGR gap #10: no live check | TEC26: Artem «полигоны по периметру должны быть утоплены минимум на метр» (jobs/TEC26-OKS/STATE.md) | NPM-2.3-4 VPM-2.3-6 VPM-2.3-7.a | чтение | yes | P1 | 0.7 |
| 1 Моделирование | Триангуляция (Делоне) (`model.triangulate`) | Триангулирует n-гоны на экспортной копии по Делоне, без длинных клиньев | GeoAGR: Triangulate btn_TriangulateRight GeoAGR.ms:50991 (DelaunayCore.dll) | взять как есть: Max T08-08..10 correct; run only on export copies | TEC26: UCX triangulation fails SINTEZ 2.3.17 in both profiles (job-retro-tec26-oks-pr574.md) | NPM-2.3-11 VPM-2.3-17 | копии | yes | P1 | 0.8 |
| 1 Моделирование | Стекло плоскостями (`model.glass_planes`) | Сводит стекло окна к одной плоскости без толщины, режет рамы и дубли | pilot: jobs/vyatskaya-tow02 clean_glass_blender.py | новое: port the job script; matched Artem's hand result 787 vs 816 quads | TOW02: Artem rebuilt balcony glass by hand (job-retro-vyatskaya-tow02-pr515.md) | NPM-2.3-10 VPM-2.8-4 | копии | yes | P2 | 1.0 |
| 1 Моделирование | Граница Ground (`model.ground_border`) | Упрощает границу благоустройства и чинит веерную топологию | Andrew_scripts: Ground_Tools.ms (border simplify, fan fix) | взять как есть: team tool, byte-identical in both copies (team-plugins-audit) | Vatutino: ground-gap-exceptions.json, ground-exceptions.json | NPM-2.3-1.a VPM-2.3-3 | undo | yes | P2 | 1.0 |
| 1 Моделирование | Нарезка рельефа сеткой (`model.ground_slice`) | Режет Ground сеткой 2.5–7.6 м по мировым осям | GeoAGR: Slicers btn_slice GeoAGR.ms:13928, btn_conv :14191, btn_remove :14196 | взять как есть: Max T03-01: slicepoly in world space correct | Vatutino: Ground v005…v015 builds (jobs/VATUTINO-SITE/ground-build-v0*.md) | NPM-2.6-1 | копии | yes | P2 | 1.0 |
| 1 Моделирование | Регулярная поверхность рельефа (`model.ground_surface`) | Заменяет триангулированную поверхность регулярной сеткой по высотам | GeoAGR: Replace Faces Selection btn_Projection GeoAGR.ms:58102/58399; Andrew_scripts: Ground_Tools.ms terrain-from-height | слить дубли: T09-01: LMB averages `v` instead of `nv`; T09-03 ray miss crashes; keep one tool | Vatutino: relief-constraints.md, ground-gate-r2.md (jobs/VATUTINO-SITE) | NPM-2.6-1 NPM-2.3-1.a | копии | yes | P2 | 1.0 |
| 1 Моделирование | Раздвинуть задвойки (`model.move_apart`) | Раздвигает пары граней/вершин 0–2, 3–10, 10–20 мм до чистого xView | GeoAGR: Move Faces GeoAGR.ms:49657, Move Verts :50241, Move Edges :48952 | взять + исправить: T08-01/02: Move Faces test `d >= min and d <= min` never moves a pair inside the range | TOW02: xView 185 faces at 5 mm after own check said 0 (pr515 retro); KPP1 v005 overlaps (jobs/KPP1/STATE.md) | NPM-2.3-9 VPM-2.3-13 | undo | yes | P2 | 1.0 |
| 1 Моделирование | Повтор операций по фасаду (`model.poly_actions`) | Записывает extrude/inset/MatID/connect и повторяет на группах полигонов | Andrew_scripts: Poly Actions Copy_V6.ms (UI v7.6.0) | взять + исправить: `.pac` import runs execute(readLine) (line 765): replace by a JSON action list | TEC26: 10 builds of repeated rib cuts (job-retro-tec26-oks-pr574.md); ZAVOD review MAX-32 | - | undo | no | P2 | 1.0 |
| 1 Моделирование | Сварка T-стыков (`model.tjunction_weld`) | Сваривает T-стыки окон и проёмов только в выделении, с порогом в метрах | GeoAGR: Edges Weld btn_EdgeWeld GeoAGR.ms:51802, Corners Weld :51542 | взять + исправить: T08-04: LMB welds the whole object, not the selection; merge Corners Weld | TOW02: resolve_tjunctions moved into the engine (job-retro-vyatskaya-tow02-pr515.md §8) | NPM-2.3-7.b VPM-2.3-11.b | undo | yes | P2 | 1.0 |
| 1 Моделирование | Вогнутые полигоны (`model.concave_fix`) | Находит и режет вогнутые полигоны | Telegram: AlexYo_ConcaveFixer.ms, SelectConcavePolygons.ms | слить дубли: two scripts, one tool | - | NPM-2.3-11 | undo | no | P3 | 1.x |
| 1 Моделирование | Детриангуляция (`model.detriangulate`) | Убирает диагонали триангуляции для правки в квадах | GeoAGR: Detriangulate GeoAGR.ms:48104; Telegram: IN_tools-detriangulator.mcr | слить дубли: GeoAGR runs without undo; keep one with undo | - | - | undo | no | P3 | 1.x |
| 1 Моделирование | Интерьерная коробка (`model.interior_box`) | Заменяет интерьер сплошной коробкой со стенами ≥10 см | Andrew_scripts: Interier_Box.ms | взять как есть | - | VPM-2.3-12.a VPM-2.3-12.b | undo | no | P3 | 1.x |
| 1 Моделирование | Выделить регион (`model.region_select`) | Растит выделение полигонов до замкнутого региона | Andrew_scripts: Region_Cut.ms | взять как есть: selection helper | team daily (team-plugins-audit Workflow step 4) | - | выделение | no | P3 | 1.x |
| 1 Моделирование | Выравнивание по 3 точкам (`model.three_pt_align`) | Совмещает объект с другим по трём парам точек | Telegram/plugins: 3pt_align.mcr | взять как есть: on the Octopus myscripts menu | team daily (team-plugins-audit Workflow step 4) | - | undo | no | P3 | 1.x |
| 1 Моделирование | Расстановка окон (`model.window_placer`) | Ставит окна по списку и привязывает к проёмам | GeoAGR: Geo Window Placer btn_run GeoAGR.ms:57080, btn_snap :57196 | взять как есть: unverified in Max: verify on a disposable scene first | methods: docs/methods/windows-glazing | NPM-2.3-10 | undo | no | P3 | 1.x |
| 2 Текстуры и материалы | Текстуры (все объекты) (`tex.check`) | Размер, квадрат, заглушки, альфа, 8 бит/канал, размер файла, набор UDIM, паддинг | AGR Tools 0.5.0 textures; GeoAGR: Prepare LowPoly/HighPoly GeoAGR.ms:65278/65653 | готово: fixes D1 (last object only) and D3 | #804 | NPM-2.5-1.a NPM-2.5-2.a NPM-2.5-3 NPM-2.5-4 NPM-2.5-5 VPM-2.5-1.2 VPM-2.5-1.5 VPM-2.5-1.6 VPM-2.5-1.9 | чтение | yes | P1 | 0.5 |
| 2 Текстуры и материалы | Формат PNG: альфа, 24 бит, ≤3 МБ (`tex.format_fix`) | Пишет исправленные PNG в новую папку: без альфы, 24 бит, сжатие до лимита | GeoAGR: Format & Alpha Tex btn_alpha_remove GeoAGR.ms:40195, compress_file; Telegram: convert_8bit_to_24bit.py | взять + исправить: GeoAGR overwrites without backup; identify passes RGBA/palette as 8-bit sRGB (65496); compress method 2 writes nothing | TEC26: railing map 4096 instead of 2048 (STATE.md); team audit R18 | NPM-2.5-2.a NPM-2.5-3 NPM-2.5-5 VPM-2.5-1.6 VPM-2.5-1.9 | новые файлы | yes | P1 | 0.8 |
| 2 Текстуры и материалы | Тип материала (`tex.material_type`) | Только Standard/Physical; Corona/VRay и пр. — ошибка с именем материала | GeoAGR: Prepare LowPoly GeoAGR.ms:65278 (material class branch) | взять + исправить: read-only, no collapse (D6) | GeoAGR Export LowPoly requires Standard (playbook #63); AC08 material census (jobs/TEC26-OKS/census) | NPM-2.4-1.a NPM-2.4-1.b VPM-2.4-1.a VPM-2.4-1.b | чтение | yes | P1 | 0.7 |
| 2 Текстуры и материалы | Отступы карт (dilate) (`tex.dilate`) | Раздувает цвет за край островов по маске альфы/UV, оригинал поверх | GeoAGR: Fit Mat btn_UdimFitMat GeoAGR.ms:25021, IM dilate :8278 | взять + исправить: no padding on white background without alpha; uvdilate loses alpha (CLI finding); use ANALYSIS C6 alpha-guided dilation | GeoAGR ANALYSIS.md C6 | NPM-2.5-4 VPM-2.5-1.5 | новые файлы | yes | P2 | 1.0 |
| 2 Текстуры и материалы | ERM и нормали DirectX (`tex.erm_normal_check`) | Проверяет каналы ERM (R только свечение) и ориентацию нормалей DirectX | new | новое: GeoAGR gap #4 (no DirectX check); GeoAGR normal detection `-threshold 50%` misreads flat #8080FF (1685) | - | VPM-2.5-1.7 VPM-2.14-1 VPM-2.14-2 VPM-2.14-3 | чтение | yes | P2 | 0.9 |
| 2 Текстуры и материалы | Покраска по легенде (`tex.finish_map`) | ID → отделка по листу цветового решения: легенда, кольца швов, проверка | pilot: jobs/TEC26-OKS finish_map.py (608 lines) | новое: parameterise the job script (retro: one OKS colour pipeline) | TEC26: ~6 h downstream rework (pr570 retro), 6 contract changes, 10 builds (pr574 retro) | NPM-2.4-4 VPM-2.4-1.a | копии | yes | P2 | 0.9 |
| 2 Текстуры и материалы | Заглушки 256 / 128 (`tex.placeholders`) | Создаёт однотонные заглушки Diffuse/ERM/Normal нужного размера и цвета | GeoAGR: Make Diffuse/Normal/ERM GeoAGR.ms:42227, Set Normal/ERM :42333/:42409; Andrew_scripts: Texture_Zaglushki_Ground.ms | слить дубли: GeoAGR Set Normal/ERM crash before the overwrite question (T07-01..03); Andrew script writes 24-bit | Vatutino Ground textures (jobs/VATUTINO-SITE/ground-textures.md) | VPM-2.5-3.1 VPM-2.5-3.3 VPM-2.5-3.4 NPM-2.5-7 | новые файлы | yes | P2 | 0.8 |
| 2 Текстуры и материалы | Наборы ВПМ D+ERM+N (`tex.vpm_sets`) | Собирает Diffuse, ERM (R свечение, G шероховатость, B металл) и Normal на UDIM | GeoAGR: Render Material RMB btn_render_mat GeoAGR.ms:22888; team Texture Map Generator 2.0 | слить дубли: GeoAGR path is mouse-only (rightClick not scriptable, T04-01); Texture Map Generator names match VPM (R19) | KPP1 VPM sets (jobs/KPP1/STATE.md) | VPM-2.5-1.4.a VPM-2.11-0.h VPM-2.14-1 VPM-2.14-3 | новые файлы | yes | P2 | 1.0 |
| 2 Текстуры и материалы | Браузер текстур (`tex.browser`) | Показывает карты объекта и их размеры (только чтение) | GeoAGR: Controls/Bitmaps GeoAGR.ms:41653, Browser Tex bnt_hi :41779 | взять + исправить: drop «Only Highpoly» clean-up of UVs\<obj>\ | - | VPM-2.4-2 | чтение | no | P3 | 1.x |
| 2 Текстуры и материалы | Мультиматериал из карт (`tex.multimat`) | Собирает Multi/Sub из найденных карт ВПМ по именам T_ | GeoAGR: Multimat HP btn_multimat GeoAGR.ms:42706 | взять как есть: unverified: confirm on a disposable scene | - | VPM-2.4-3.b VPM-2.4-5 | undo | yes | P3 | 1.x |
| 2 Текстуры и материалы | Цвет заглушки (`tex.plug_colour`) | Проверяет, что заглушка одного (среднего) цвета, показывает разброс | GeoAGR: Colors Tex btn_count_colors GeoAGR.ms:39668 | взять + исправить: «most popular» colour is the first colour found | - | VPM-2.5-3.4 | чтение | yes | P3 | 1.x |
| 3 Коллизии UCX | UCX: аудит сцены (`ucx.audit`) | Готовые UCX: выпуклость, замкнутость, без материалов, имя, пересечения SAT, бюджет | pilot: twinqa ucx_audit; GeoAGR: Check Faces Count :60316, Check Convex :60910, ucx_check.exe :60449; Andrew_scripts: UCX_Check.ms; Telegram: Collizii_2.ms | слить дубли: ucx_check.exe misses containment, cuts names at a space; Collizii uses AABB; UCX_Check tol 0.01 scene units | TEC26: 63 + 60 + 33 collision candidates in census (jobs/TEC26-OKS/STATE.md) | VPM-2.13-1.a VPM-2.13-1.b VPM-2.13-1.c VPM-2.13-1.d VPM-2.13-3 VPM-2.13-4.a VPM-2.13-7.a VPM-2.13-7.b | чтение | yes | P1 | 0.7 |
| 3 Коллизии UCX | UCX: построить (`ucx.build`) | Вариант по WHEN.md (single-hull, kernel-boxes, slice-prisms), бюджет D012, аудит, копии | AGR Tools 0.3.0 ucx; GeoAGR: UCX Make Concave Form :63505; Telegram: UCX_N_29.09.ms, Narezka_Ucx.ms; Andrew_scripts: UCX_Tools.ms | готово: team splitters merged as variants; pads 0.04/0.035 not adopted (D180) | #728 | VPM-2.13-1.a VPM-2.13-1.b VPM-2.13-7.a VPM-2.13-7.b | копии | yes | P1 | 0.3 |
| 3 Коллизии UCX | UCX: триангуляция (`ucx.triangulate`) | Триангулирует UCX на копии и проверяет выпуклость после | GeoAGR: UCX Triangulate GeoAGR.ms:62890 | взять как есть: unverified: confirm in Max; run on copies | TEC26: SINTEZ 2.3.17 fails on UCX triangulation (job-retro-tec26-oks-pr574.md, open) | VPM-2.3-17 VPM-2.13-1.a | копии | yes | P1 | 0.8 |
| 3 Коллизии UCX | UCX: зазор 2 мм – 1 см (`ucx.gap`) | Сдвигает куски UCX внутрь по нормалям до зазора в полосе D098 | GeoAGR: UCX Move/MultiPass GeoAGR.ms:61446/62416; Telegram: UCX_Razdv.ms, UCX gap inset | слить дубли: T10-01: MultiPass pushes by AABB (false pushes); Razdv default 5 mm is inside the band | D098 (Artem: gap 2 mm – 1 cm) | VPM-2.13-4.a VPM-2.13-4.b | копии | yes | P2 | 1.0 |
| 3 Коллизии UCX | UCX рельефа (`ucx.ground`) | UCX Ground по верхним граням рельефа призмами по адаптивной сетке | GeoAGR: UCX Make Ground btn_UCX_makeground GeoAGR.ms:62929; ANALYSIS C1 | взять + исправить: unverified; take C1 greedy prisms | docs/domain/areas/ucx-evidence | VPM-2.13-3 VPM-2.13-7.b | копии | yes | P2 | 1.0 |
| 3 Коллизии UCX | UCX: имена (`ucx.rename`) | Переименовывает куски в UCX_SM_<Address>_Main/Ground_NNN | GeoAGR: UCX Rename btn_UCX_rename GeoAGR.ms:62907 | взять + исправить: requires the model name inside; UE4 two-digit namer dropped (R21) | #230 (UCX name grammar R08) | VPM-2.13-1.d VPM-2.10-4.2.b | undo | yes | P2 | 0.8 |
| 3 Коллизии UCX | UCX лестниц (`ucx.stairs`) | Проверяет, что лестница закрыта усечённой пирамидой, и допуски 10/30/100 см | new | новое: GeoAGR gap #8 | - | VPM-2.13-5 VPM-2.13-6 | чтение | yes | P3 | 1.x |
| 4 UDIM и тексель | ID → UDIM на копии (`udim.ids_to_udims`) | Раскладывает материал ID n в тайл 1000+n на экспортной копии | GeoAGR: IDs→UDIMs btn_udims_as_ids GeoAGR.ms:35920; Telegram: UDIM-MultiSub_Universal.ms (reverse) | взять + исправить: only on export copies: IDs are a reading scheme (D030); UDIM-MultiSub ID=tile rule dropped (R5) | TEC26 KPP recipe: 19 tiles, ID→tile matched (census/kpp-recipe.md) | VPM-2.5-2.1.3.a VPM-2.5-2.1.3.b | копии | yes | P1 | 0.8 |
| 4 UDIM и тексель | UV-сдвиг на целый тайл (`udim.nudge`) | Сдвигает острова на целое число периодов повтора (в фазе текстуры) | AGR Tools 0.2.0 nudge; Telegram: GridUVLayout22.ms | готово: GridUVLayout merged (team audit R8) | #722 | VPM-2.5-2.1.3.a | копии | yes | P1 | 0.2 |
| 4 UDIM и тексель | Тексель px/м (`udim.texel`) | Мин/медиана px/м по мешу и материалу, полосы ВПМ 512–1706, НПМ 10–40 | AGR Tools 0.3.0 texel; GeoAGR: rocount_texel GeoAGR.ms:38183; plugins density.ms | готово: fixes D5 (system units); density.ms 4096 assumption dropped (R15) | #728; D160 | VPM-2.6-2 NPM-2.6-1 | чтение | yes | P1 | 0.3 |
| 4 UDIM и тексель | MatID → UDIM (МАФ) (`udim.matid_unwrap`) | Развёртка по MatID в тайлы с плотностью и упаковкой | Andrew_scripts: Maf Tools.mcr unwrapByMatIDToUDIM_Advanced :243, ua_packTiles :819, ua_run :922 | взять + исправить: wrap: keep source UV/MatID, units.SystemScale, sparse IDs (ZAVOD review MAX-31); MAF TD spinner unit unlabeled | Vatutino MAF set (jobs/VATUTINO-SITE/maf/site-maf-set.md) | VPM-2.6-2 VPM-2.5-2.1.3.a | копии | yes | P2 | 0.9 |
| 4 UDIM и тексель | Подгонка плотности (`udim.rescale`) | Масштабирует UV до целевой плотности синхронно с текстурами | GeoAGR: ReScale Density btn_Udim_Rescale GeoAGR.ms:43253; Andrew_scripts: Maf Tools tdt_OptimizedSetTD :495 | слить дубли: GeoAGR uses system units and overwrites maps; keep one tool on copies | D160 band | VPM-2.6-2 NPM-2.6-1 | копии | yes | P2 | 1.0 |
| 4 UDIM и тексель | UDIM: тайлы и слоты (`udim.slots`) | 1001… без пропусков, ≤100 карт на материал, SlotNumber 1…7 подряд | AGR Tools 0.5.0 textures/names (partly) | новое: add >100 maps → next slot check (manual in GeoAGR) | - | VPM-2.4-3.a VPM-2.4-3.b VPM-2.5-2.1.3.a VPM-2.11-0.b | чтение | yes | P2 | 0.9 |
| 4 UDIM и тексель | Развёртка плиток в UDIM (`udim.unwrap_tiles`) | Раскладывает плитки фасада по UDIM на копии | GeoAGR: Unwrap Tiles btn_bricks_unwrap GeoAGR.ms:33780 | взять + исправить: collapse + Undo Off clears history (clearUndoBuffer): only on copies | KPP1 v003 tiles (jobs/KPP1/STATE.md) | VPM-2.5-2.1.3.a | копии | yes | P2 | 1.0 |
| 4 UDIM и тексель | Искажения UV (`udim.distortion`) | Подсвечивает растянутые полигоны UV | GeoAGR: uvDistortionViewer GeoAGR.ms:16071 | взять как есть: read-only viewer | - | VPM-2.6-2 | чтение | no | P3 | 1.x |
| 4 UDIM и тексель | UDIM → ID (просмотр) (`udim.udims_to_ids`) | Показывает, какой тайл даёт какой ID, без записи | GeoAGR: UDIMs→IDs btn_ids_as_udims GeoAGR.ms:41355; Telegram: UDIM Viewer_V1.2.ms | слить дубли: port P41 defect: negative UV and U ≥ 10 | - | VPM-2.5-2.1.3.a | чтение | yes | P3 | 1.x |
| 4 UDIM и тексель | Просмотр UDIM (`udim.viewer`) | Показывает тайлы UDIM на объекте и карты из папки | Telegram/Andrew_scripts: UDIM Viewer_V1.4.ms, Udim_Geo_Json.ms | взять как есть: viewer part only; GeoJSON import part goes to qa.geojson | team daily (team-scripts-audit) | - | чтение | no | P3 | 1.x |
| 5 Атласы / не-атласы | Атлас Flora (`atlas.flora`) | Пакует диффуз и отдельную прозрачность Flora в один набор ≤2048, отступ ≥8 px | Andrew_scripts: FloraAtlas.ms; plugins: Flora Atlas V1.2.mcr | взять + исправить: defaults 2 px / 8192 are wrong for AGR (R17): size and padding by profile | flora jobs (jobs/flora-textures); tools/max_flora_*.py | NPM-2.5-13.a NPM-2.5-13.b NPM-2.5-4 | новые файлы | yes | P1 | 0.9 |
| 5 Атласы / не-атласы | UDIM → атлас НПМ (`atlas.npm`) | Сводит UDIM в один атлас НПМ, ремап UV на копии, отступ ≥8 px | AGR Tools 0.2.0 atlas; GeoAGR: Unwrap to Atlas GeoAGR.ms:26796; Telegram: VPM_to_NPM.ms | готово: VPM_to_NPM 6 px padding and ≤512 plug not adopted (team audit R1, R9) | #722; D156 | NPM-2.5-4 NPM-2.5-11.a | копии | yes | P1 | 0.2 |
| 5 Атласы / не-атласы | Число текстурных наборов (`atlas.sets_count`) | ОКС ≤40 наборов (+1 кровля), Ground ≤20, GroundEl 1, Flora 1 | new | новое: GeoAGR: NPM-2.1-5.b unreachable, NPM-2.1-4.c manual | - | NPM-2.1-4.c NPM-2.1-5.b NPM-2.5-11.a NPM-2.5-11.b | чтение | yes | P1 | 0.7 |
| 5 Атласы / не-атласы | Фасадный атлас run-strip (`atlas.facade_strip`) | Атлас фасада полосами повторов для НПМ ОКС | pilot: jobs/FACADES-ATLAS, tools/remap_facades_atlas.py; D156 | новое: port the accepted job method | TOW02: OKS 013 run-strip atlas accepted (D156) | NPM-2.5-11.a NPM-2.5-4 | копии | yes | P2 | 1.0 |
| 5 Атласы / не-атласы | Атлас GroundEl ≤512 (`atlas.groundel`) | Один набор элементов благоустройства, ≤512 px | Telegram: A101AGRLP.ms:1374 (GroundEl cap); AGR Tools atlas core | слить дубли: atlas.npm with a groundel mode | Vatutino MAF showcase (jobs/VATUTINO-SITE/maf/site-maf-showcase.config.json) | NPM-2.5-12 NPM-2.1-5.b | копии | yes | P2 | 0.9 |
| 5 Атласы / не-атласы | Атлас → мультиматериал (`atlas.unatlas`) | Обратный путь НПМ → ВПМ: атлас в Multi/Sub по ячейкам | GeoAGR: UnAtlas btn_unwrap_material_from_lowpoly GeoAGR.ms:29390 | взять как есть: unverified; every map 2048²; only on copies | GeoAGR recipe npm_to_vpm (tech3.txt) | VPM-2.4-3.a | копии | yes | P3 | 1.x |
| 6 Замены и расстановка | Flora: ремонт и проверка (`place.flora_repair`) | Чинит трансформы и треугольники Flora, проверяет набор | pilot: tools/max_flora_transform_repair.py, max_flora_tri_repair.py, max_flora_verify.py | взять как есть: pilot tools, already used in Max | jobs/flora-textures | NPM-2.5-13.a NPM-2.3-14 | копии | yes | P1 | 0.9 |
| 6 Замены и расстановка | Проверки МАФ (`place.maf_checks`) | Пересечения, висящие над рельефом (AABB не касается), масштаб, треугольники | Andrew_scripts: Maf Tools.mcr (intersection check); Telegram: Maf_Fly.ms; pilot: twinqa.maf_checks | слить дубли: Maf_Fly is AABB only: keep as a pre-filter | skill maf-set-blender-checks; Vatutino source-dimension-gate | NPM-2.3-6.b NPM-2.5-12 | чтение | yes | P1 | 0.9 |
| 6 Замены и расстановка | Замена объектов (`place.replace`) | Заменяет объекты по маске имени на эталон с сохранением трансформа и имени | Andrew_scripts: Zamena_V2.ms; plugins: Zamena | взять + исправить: report every replaced and every unmatched object; undo; no instances in delivery | Vatutino: MAF placement by schedule (jobs/VATUTINO-SITE/place_site.py) | NPM-2.3-5 VPM-2.3-8 | undo | yes | P1 | 0.9 |
| 6 Замены и расстановка | Расстановка по ведомости (`place.schedule`) | Ставит МАФ по ведомости/плану и пишет отчёт: поставлено / нет эталона / нет места | pilot: tools/placement_site.py, jobs/VATUTINO-SITE/placement_report.py | новое: port the job tool, report-first | Vatutino placement-report.json; #790 | NPM-2.1-5.a | копии | yes | P1 | 0.9 |
| 6 Замены и расстановка | Посадить на рельеф (`place.drop_to_ground`) | Опускает МАФ/деревья на поверхность Ground по лучу | Andrew_scripts: Maf Tools.mcr (glue) | взять как есть | Vatutino relief (relief-constraints.md) | - | undo | yes | P2 | 0.9 |
| 6 Замены и расстановка | Генератор МАФ (`place.maf_generator`) | Параметрический МАФ по семейству (первое — скамьи «Верона») | pilot: #790 (open) | новое: UI front end of the #790 generator | Vatutino *T3508/1-10 (#790) | NPM-2.5-12 | копии | yes | P2 | 1.0 |
| 6 Замены и расстановка | Скаттер (`place.scatter`) | Рассыпает объекты по поверхности с плотностью и случайностью | GeoAGR: Advanced Scatter GeoAGR.ms:54174; plugins: objectrandomizerv3.ms; GeoAGR: Palette Randomizer :57812 | слить дубли: MultiScatter (commercial) stays outside | - | - | undo | no | P3 | 1.x |
| 6 Замены и расстановка | Деревья спрайтами (`place.tree_cards`) | Дерево из плоскостей-карточек с ID ствола/веток | GeoAGR: Tree GeoAGR.ms:43960, Find & Set ID trunks :46966 | взять + исправить: stems ID broken (T07-05/06, leaked global pp); render part needs Corona → not ported | - | NPM-2.5-13.a VPM-2.3-16 | копии | no | P3 | 1.x |
| 7 Проверки и сдача | Разделение FBX (`qa.fbx_split`) | ОКС ≤20 FBX, ≤20 объектов на FBX, Ground обязателен, нумерация сквозная | new | новое: GeoAGR gap #11: no check | TEC26: 9 OKS surfaces in one scene (census) | NPM-2.1-2 NPM-2.1-4.a NPM-2.1-6 NPM-2.2-1 NPM-2.2-4 VPM-2.1-3.a VPM-2.1-4 | чтение | yes | P1 | 0.7 |
| 7 Проверки и сдача | Проверка GeoJSON (`qa.geojson`) | Проверка паспорта GeoJSON пилотным twinqa.geojson | AGR Tools 0.5.0 geojson | готово: GeoAGR gap #1 | #804 | GJ-1 GJ-2 GJ-3 VPM-2.2-1 | чтение | yes | P1 | 0.5 |
| 7 Проверки и сдача | Стекло (`qa.glass`) | MainGlass отдельно, ≤20 полупрозрачных, ≤7 материалов стекла, без текстур, 50 % | GeoAGR: Prepare LowPoly MainGlass branch :65330–65375 | взять + исправить: D2: MainGlass branch unreachable (T10-05); D3: VPM «no textures» fires always | TOW02 glass cleanup (pr515 retro) | NPM-2.7-2 NPM-2.1-4.b NPM-2.4-2 NPM-2.4-3.b NPM-2.4-6 VPM-2.8-1 VPM-2.8-2 VPM-2.3-4 | чтение | yes | P1 | 0.7 |
| 7 Проверки и сдача | MatID (`qa.matid`) | ID ≥1001, ID 0, пустые слоты Multi/Sub | AGR Tools 0.1.0 matid | готово: D030 | #707; #548 | NPM-2.4-5 VPM-2.4-5 | выделение | yes | P1 | 0.1 |
| 7 Проверки и сдача | Имена NPM/VPM (`qa.names`) | SM/UCX, M, T по маскам, SlotNumber 1…7 | AGR Tools 0.5.0 names; GeoAGR: check_names_all GeoAGR.ms:6907, _vpm :7331 | готово: fixes D2, D4 | #804 | NPM-2.10-1 NPM-2.10-2 NPM-2.10-3.3.a VPM-2.10-2.a VPM-2.11-0.a VPM-2.11-0.c | чтение | yes | P1 | 0.5 |
| 7 Проверки и сдача | Исправить имена (`qa.names_fix`) | Переименовывает объекты, материалы и файлы карт по маске на экспортных копиях | Telegram: AlexYo_AGR_renamerV2.ms (V13), A101AGRLP.ms naming UI; GeoAGR: Material Cloner :55623 | слить дубли: three renamers → one; A101 Ground FBX extra underscore (:388) not copied; Material Cloner overwrites files | A101LP is the daily naming button (team-plugins-audit step 7) | NPM-2.10-3.3.a NPM-2.10-3.4.a VPM-2.11-0.a VPM-2.10-4.3 | копии | yes | P1 | 0.8 |
| 7 Проверки и сдача | Проверка пакета ZIP (`qa.package`) | ZIP: размеры, состав FBX/PNG/GeoJSON, имена, битые файлы, readback | pilot: tools/qa/validate_package.py; Telegram: AGR Checker (Python ZIP), AGR Zipper v2.1 | слить дубли: team checkers merged into the pilot validator (agr_package_validate) | TEC26: qa_packages 40/40 (pr574 retro) | NPM-2.1-1.a NPM-2.1-1.b VPM-2.1-1.a VPM-2.1-1.b VPM-2.1-2.a VPM-2.1-2.c VPM-2.1-2.d | чтение | yes | P1 | 0.8 |
| 7 Проверки и сдача | Пивот (`qa.pivot`) | Z = 0 и один пивот на FBX (1 мм) | AGR Tools 0.5.0 pivot | готово | #804 | VPM-2.9-4.b VPM-2.9-5 | чтение | yes | P1 | 0.5 |
| 7 Проверки и сдача | Предсдача: все проверки (`qa.preflight`) | Запускает все проверки профиля одним нажатием, одна таблица, ничего не меняет | GeoAGR: Prepare LowPoly GeoAGR.ms:65278, Prepare HighPoly :65653; RulesCheck_lowpoly :9136 (dead UI) | взять + исправить: replaces the destructive buttons: D6 (ResetXForm+collapse), D1, D2, D7, D8 | GeoAGR requirements matrix §2 (13 gaps) | NPM-2.1-3.c VPM-2.3-1 | чтение | yes | P1 | 0.7 |
| 7 Проверки и сдача | Лишнее в сцене (`qa.scene_hygiene`) | Камеры, кости, анимация, слои, группы/иерархия, пустые объекты, модификаторы | GeoAGR: RulesCheck_lowpoly :9136 checkboxes (dead UI, D7) | взять + исправить: rules from the current rules2/rules4, not the old edition | GeoAGR NPM-2.1-3.a/b unreachable | NPM-2.1-3.a NPM-2.1-3.b NPM-2.1-3.c NPM-2.1-3.d NPM-2.3-5 VPM-2.3-1 VPM-2.3-2 VPM-2.3-8 VPM-2.3-11.d VPM-2.3-11.e | чтение | yes | P1 | 0.7 |
| 7 Проверки и сдача | Треугольники по FBX (`qa.tris`) | Лимиты на FBX: НПМ 150 000 / 180 000, ВПМ 1 000 000, Ground по площади, UCX | AGR Tools 0.5.0 tris | готово: fixes D8 | #804 | NPM-2.3-6.a NPM-2.3-6.b VPM-2.3-9 VPM-2.3-10 | чтение | yes | P1 | 0.5 |
| 7 Проверки и сдача | Трансформы сброшены (`qa.xform`) | Находит несброшенный масштаб/поворот/зеркало и родителей; сброс только на копии | GeoAGR: Prepare LowPoly ResetXForm :65536 (destructive) | взять + исправить: D6: check here, reset in export copies (cleanup/apply) | TOW02 dumper wrote negative-scale meshes inward (pr392 retro) | NPM-2.3-14 VPM-2.3-18 | чтение | yes | P1 | 0.7 |
| 7 Проверки и сдача | xView: перекрытия (`qa.xview`) | Нативный xView: вершины 2 мм, грани 5 мм, на вычисленных копиях | AGR Tools 0.1.0 xview; GeoAGR: xView Verts/Faces :48459/:48470 | готово: D152 | #707; TOW02 185 faces (pr515 retro) | NPM-2.3-7.a NPM-2.3-9 VPM-2.3-11.a VPM-2.3-13 | выделение | yes | P1 | 0.1 |
| 7 Проверки и сдача | Нулевые площади и рёбра (`qa.zero_area`) | Полигоны нулевой площади, рёбра нулевой длины, изолированные вершины | GeoAGR: Areas Poly ro_count_area GeoAGR.ms:36036; Telegram: VertexEdgeSplit, ShivaTools_VertexCleaner | взять + исправить: keep the finder; Remove Overlayed has probable errors; VertexCleaner weight is not metres | TOW02: 64 tris + 44 faces < 2 cm (pr392 retro) | NPM-2.3-7.b NPM-2.3-7.c VPM-2.3-11.b VPM-2.3-11.c | чтение | yes | P1 | 0.7 |
| 7 Проверки и сдача | Адрес и улицы (`qa.address`) | Проверка Address по справочнику улиц, составных частей и длины | GeoAGR: Check Adress btn_check_names GeoAGR.ms:15355, Streets List :42460 | взять + исправить: address filter and/or defect (P28–P30) | - | NPM-1.3-2.a NPM-1.3-3.a VPM-1.3-2.a VPM-1.3-3.a | чтение | yes | P2 | 0.9 |
| 7 Проверки и сдача | Сравнение с листом фасада (`qa.facade_compare`) | Картинка «лист \| ВПМ \| НПМ» в одном масштабе и счёт швов | pilot: jobs/TEC26-OKS render_facades / joint_count / compare_facades (520 lines) | новое: after this picture existed there were no more rejections | TEC26 (job-retro-tec26-oks-pr574.md §Summary) | - | чтение | yes | P2 | 0.9 |
| 7 Проверки и сдача | Нормали и двойные грани (`qa.normals`) | Нормали к наблюдателю, двусторонние полигоны стекла/Flora, сглаживание | GeoAGR: Double Faces btn_DoubleFaces GeoAGR.ms:49204, View Normals | взять как есть: unverified: confirm on a disposable scene | - | NPM-2.3-8.a NPM-2.3-15 VPM-2.3-14 VPM-2.3-15.a VPM-2.12-3 | чтение | yes | P2 | 0.9 |
| 7 Проверки и сдача | Сверка с SINTEZ (`qa.sintez`) | Сравнивает наши находки с отчётом SINTEZ по тем же правилам | pilot: tools/sintez_parity.py | взять как есть | TEC26: SINTEZ 2.3.17 fail (pr574 retro) | VPM-2.3-17 | чтение | yes | P2 | 0.9 |
| 7 Проверки и сдача | Код ОМК ТЭ (`qa.omk_te`) | Поиск кода классификатора по таблице и вставка | GeoAGR: Get OMK TE Code btn_omkte GeoAGR.ms:66030 | взять + исправить: Copy to Clipboard with a filter copies the wrong code | - | NPM-2.10-3.1 | чтение | yes | P3 | 1.x |
| 8 Экспорт и пакет | Экспорт с проверкой (`export.checked`) | Один FBX на AGR_EXPORT_PATH: ворота → FBX → readback | AGR Tools 0.4.0 export; GeoAGR: Export LowPoly :66532, HighPoly :66904 | готово | #731 | NPM-1.1-1 VPM-1.1-1 NPM-2.1-3.c | новые файлы | yes | P1 | 0.4 |
| 8 Экспорт и пакет | Очистка перед экспортом (`export.cleanup`) | CA, UDP, лишние каналы, канал 1 «UV» — план, затем копии | AGR Tools 0.1.0 cleanup; Telegram: ClearCustomAttributesAndObjProp_010.ms | готово: team audit R3 | #707; #547 | VPM-2.3-11.e | копии | yes | P1 | 0.1 |
| 8 Экспорт и пакет | Паспорт GeoJSON (`export.geojson_write`) | Пишет GeoJSON из сцены (пивот, положение, адрес, превью) и сразу проверяет | GeoAGR: GeoJSON Create/Save/Load GeoAGR.ms:64642–64644 (disabled), Base64 to Clipboard :64853 | новое: GeoAGR gap #1: buttons disabled, no validator | GeoJSON for every package (D-matrix 29 GJ rows, 25 manual) | VPM-2.2-1 VPM-2.2-2 VPM-2.2-6.a VPM-2.2-7 GJ-1 GJ-19.a GJ-19.b GJ-21.a VPM-2.10-4.1.e | новые файлы | yes | P1 | 0.8 |
| 8 Экспорт и пакет | FBX благоустройства (`export.ground_fbx`) | Ground, GroundEl, Flora, GroundGlass в один файл _Ground | GeoAGR: Export LowPoly :66532 (Ground branch); Telegram: A101AGRLP.ms Ground rollout :388 | слить дубли: A101 writes an extra underscore; one export path with modes | Vatutino Ground v014/v015 | NPM-2.1-5.a VPM-2.1-4 | новые файлы | yes | P1 | 0.8 |
| 8 Экспорт и пакет | Пивот и положение (`export.pivot_place`) | НПМ в МСК с высотами, ВПМ в ноль (чистый пол); пивот на копиях | GeoAGR: Geojson Get/Set Pivot GeoAGR.ms:64763/64778, Reset Transforms :64709, Combine near zero :64730 | взять + исправить: unverified; never move working objects | TEC26 ±0.000 reference open (STATE.md) | NPM-2.8-1 NPM-2.8-2 VPM-2.9-4.b VPM-2.9-5 | копии | yes | P1 | 0.8 |
| 8 Экспорт и пакет | Архив пакета (`export.zip`) | ZIP НПМ/ВПМ с лимитами 500 МБ / 1 ГБ (двоичные), проверка до и после | GeoAGR: Archivate All btn_archivate GeoAGR.ms:66229; Telegram: AGR Zipper v2.1 | слить дубли: bundled 7z.exe without 7z.dll creates nothing (CLI); _Light missing in VPM archive; Ground limit 500 MB vs 1 GB (66340) | D015 binary units | NPM-2.1-1.a VPM-2.1-1.a VPM-2.1-1.b VPM-2.1-2.b | новые файлы | yes | P1 | 0.8 |
| 8 Экспорт и пакет | Пакетный экспорт (`export.batch`) | Все FBX сцены по AGR_EXPORT_PATH одним запуском с одним отчётом | AGR Tools 0.4.0 export (one FBX) | новое | TEC26: 9 OKS + truba + KPP (census) | NPM-2.1-2 | новые файлы | yes | P2 | 0.9 |
| 9 Освещение ВПМ | Проверка света (`light.check`) | ≤250 источников, только Omni/Spot, Omni ≥5 м, Spot ≥1.5 м, корень и пивот | GeoAGR: Light Manager btn_Lights GeoAGR.ms:56146; Telegram: agr_max_check_37.ms lights, Light_Metr.ms | слить дубли: GeoAGR distances in system units; light index cap 50 dropped (R6) | GeoAGR gap #7 | VPM-2.15-2 VPM-2.15-4 VPM-2.15-5.a VPM-2.15-5.b VPM-2.15-6 VPM-2.15-8 VPM-2.15-9.b | чтение | yes | P2 | 1.0 |
| 9 Освещение ВПМ | FBX освещения _Light (`light.export`) | Отдельный FBX света с корнем, Omni не теряются, в архив ВПМ | GeoAGR: Export HighPoly :66904, ReSave Lights FBXs :65127 | взять + исправить: Omni do not reach _Light.fbx (66915, 66977); _Light not archived (66307) | GeoAGR gap #7 | VPM-2.1-2.b VPM-2.11-0.f VPM-2.11-0.g VPM-2.10-4.1.c VPM-2.10-4.5 | новые файлы | yes | P2 | 1.0 |
| 9 Освещение ВПМ | Расстановка Free Spot (`light.place`) | Ставит Free Spot по выделенным полигонам и прореживает | GeoAGR: Light Placer GeoAGR.ms:56468 / btn_process :56535; Andrew_scripts: FreeSpot_Tools.ms; Telegram: Light.ms | слить дубли: three placers → one | - | VPM-2.15-1 VPM-2.15-3.c | undo | no | P3 | 1.x |

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
| 0.7 | Предсдача: недостающие проверки (только чтение) + блоковые цвета UI + перепись сцены | in work | 12 | 12/0/0 | L: ~2 дня агента (11 проверок на готовых twinqa-модулях, без правок сцены) | #860 |
| 0.8 | Сдача: имена, PNG, ID→UDIM, триангуляция, пивот, GeoJSON, ZIP, пакет | planned | 13 | 10/3/0 | L: ~3 дня (правки только на копиях/новых файлах, каждая с preview) | new |
| 0.9 | Замены и расстановка, Flora/МАФ, покраска по легенде, сравнение с фасадом | planned | 16 | 5/11/0 | L: ~3 дня (перенос job-скриптов Vatutino/TEC26 в ядро) | new |
| 1.0 | Моделирование, UDIM/UCX-инструменты, свет ВПМ (P2) | planned | 18 | 0/18/0 | XL: ~4–5 дней; можно разрезать на 1.0a модель+рельеф и 1.0b UCX+UDIM+свет | new |
| 1.x | Хвост P3 (вспомогательные, по запросу) | backlog | 18 | 0/0/18 | по одной кнопке, S | - |

Состав версий (id кнопок):

- **0.1**: `qa.matid`, `qa.xview`, `export.cleanup`
- **0.2**: `udim.nudge`, `atlas.npm`
- **0.3**: `ucx.build`, `udim.texel`
- **0.4**: `export.checked`
- **0.5**: `tex.check`, `qa.geojson`, `qa.names`, `qa.pivot`, `qa.tris`
- **0.7**: `scene.census`, `scene.units`, `model.perimeter_drop`, `tex.material_type`, `ucx.audit`, `atlas.sets_count`, `qa.fbx_split`, `qa.glass`, `qa.preflight`, `qa.scene_hygiene`, `qa.xform`, `qa.zero_area`
- **0.8**: `scene.missing_maps`, `model.triangulate`, `tex.format_fix`, `tex.placeholders`, `ucx.triangulate`, `ucx.rename`, `udim.ids_to_udims`, `qa.names_fix`, `qa.package`, `export.geojson_write`, `export.ground_fbx`, `export.pivot_place`, `export.zip`
- **0.9**: `tex.erm_normal_check`, `tex.finish_map`, `udim.matid_unwrap`, `udim.slots`, `atlas.flora`, `atlas.groundel`, `place.flora_repair`, `place.maf_checks`, `place.replace`, `place.schedule`, `place.drop_to_ground`, `qa.address`, `qa.facade_compare`, `qa.normals`, `qa.sintez`, `export.batch`
- **1.0**: `scene.source_class`, `model.glass_planes`, `model.ground_border`, `model.ground_slice`, `model.ground_surface`, `model.move_apart`, `model.poly_actions`, `model.tjunction_weld`, `tex.dilate`, `tex.vpm_sets`, `ucx.gap`, `ucx.ground`, `udim.rescale`, `udim.unwrap_tiles`, `atlas.facade_strip`, `place.maf_generator`, `light.check`, `light.export`
- **1.x**: `model.concave_fix`, `model.detriangulate`, `model.interior_box`, `model.region_select`, `model.three_pt_align`, `model.window_placer`, `tex.browser`, `tex.multimat`, `tex.plug_colour`, `ucx.stairs`, `udim.distortion`, `udim.udims_to_ids`, `udim.viewer`, `atlas.unatlas`, `place.scatter`, `place.tree_cards`, `qa.omk_te`, `light.place`

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
