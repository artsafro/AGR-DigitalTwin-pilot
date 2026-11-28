# Тренажёр v0: банк эталонов, тренировочные прогоны, автооценка [D387]

Issue #1855. Репо учится строить, пересобирая принятые Артёмом объекты из их исходников. Каждый прогон оценивается
автоматически по скрытому ключу (принятой версии). Каждый провал превращается в изменение репо: правило, сценарий
или ядро. Саму модель в прогоне не правят. Машинный банк: [`etalons.json`](etalons.json). Журнал: [`ledger.json`](ledger.json).
Код: `tools/trainer/trainer.py` (`agr trainer`), тесты: `tests/tools/test_trainer.py`.
Улики (правило 57): `G:/Мой диск/AGR-evidence/1855-trainer-v0/` + `SHA256SUMS.txt`.
DCC в тренировочном прогоне [D389]: AutoCAD Core Console (headless DWG→DXF через конвертер скелета) и Blender
разрешены; живой 3ds Max исключён. Текст задачи говорит об этом агенту.

## Команды

```
uv run agr trainer check
uv run agr trainer run ETALON --lane codex --out NEW_DIR [--timeout-s 1800] [--dry-run] [--proxy]
uv run agr trainer metrics RUN_DIR [--score SCORE.json] [--usd-per-mtok IN OUT]
uv run agr trainer score ETALON --built NEW_DIR/built --out NEW.json --png NEW.png [--vlm]
uv run agr trainer calibrate --out NEW_DIR
uv run agr trainer ledger --add NEW.json --lane codex --run NEW_DIR --date YYYY-MM-DD
uv run agr trainer ab ETALON --ab OLD_DIR NEW_DIR --scope INVARIANT|DOMAIN --out NEW_DIR [--lane codex] [--dry-run]
```

### A/B probe of a harness edit [D415]

- `ab` (#1924, Harness2 arXiv 2610.14224) runs the SAME etalon twice, one arm after the other, on the same lane,
  model and `origin/main` commit. `OLD_DIR` / `NEW_DIR` are harness variants: folders of repo-relative files
  (rule, skill or doc text) laid over the practice tree after the scrub and committed as a second commit, so the
  agent's own diff stays separate. An empty folder is the unchanged baseline. Both arms are scored with `score`
  (Blender / Core Console only, never Max). Default: 1-2 etalons (cost).
- One contrast report `OUT/ab.json` + `OUT/ab.md`: per score step and per skeleton stage old / new / verdict,
  first-command tokens (first 4 tokens of the first command, shell wrapper removed), wrong-turns (commands with a
  non-zero exit), commands and input tokens with deltas, deliverable diff (added / removed / changed / same by
  sha256). Verdict of the edit: `fixed` (non-pass -> pass, or bypassed -> used, and nothing regresses),
  `regressed` (any pass -> non-pass or used -> bypassed; a mixed result is `regressed`), `unchanged`,
  `inconclusive` (an arm timed out, exited non-zero, failed before recording or was not scored; never `unchanged`).
- Refused with exit 2 and nothing written: identical or empty variants, OLD and NEW the same folder, an `--out`
  that exists or sits inside a variant, a variant file under `docs/trainer/`, `pairs_v1.json`, the etalon's
  `hidden_repo_paths` or `.git`, a symlink, a file that names the key, an unknown `--scope` or lane.
- Scope tag: `--scope INVARIANT` (entry, context, tools: AGENTS.md, SKELETONS, routes, CLI help) or
  `--scope DOMAIN` (OKS / Ground / MAF / Flora rules and scenarios). The two are probed in separate A/B runs, never
  mixed in one variant; an edited path that looks like the other scope is listed in `scope_warnings`.
- The verdict is the evidence of a job lesson (`jobs/<ID>/LESSONS.md`, form situation / lesson / evidence,
  `jobs/_template/LESSONS.md`; `tools/qa/lessons_check.py` warns on a new lesson without evidence).
- First real A/B (#1924, 2026-11-25, `origin/main` 54b63bab, codex / gpt-6.1-terra, g22-k2-stage1, INVARIANT):
  the only edit is one phrase in `AGENTS.md` ("read `docs/agents/SKELETONS.md` FIRST (it lists every stage
  command)"). Verdict `fixed`: old stopped at `artifact` (no FBX, 39 commands, 5 wrong-turns, 0.62 M input tokens);
  new built `typical_candidate/body.fbx` and passed artifact / readback / bounds / topology / form, first failing
  `form_v2` (36 commands, 6 wrong-turns, 1.68 M tokens), and also used `master-qa` and `readback`. First command:
  old reads the scenario skill, new reads SKELETONS.md first. One sample per arm: LLM run-to-run variance is not
  controlled, so this proves the A/B mechanism, not the edit. Report and arm records:
  `G:/Мой диск/AGR-evidence/1924-trainer-ab/` (`ab.md`, `ab.json`, `old/`, `new/`, `SHA256SUMS.txt`;
  `ab.json` sha256 8395028a84001fc6…).

- `run` использует план записи #1608. Свежая сессия `codex exec --ephemeral --ignore-user-config` работает
  в отдельной папке: `git archive origin/main` распаковывается в новую папку, чистится, затем `git init` и
  один коммит очищенного дерева (без origin, без истории, без общего индекса и refs с основным репо — ни
  `git log --all`, ни `git show HEAD:<скрытый путь>` ключ не находят). Сессия получает только текст задачи и копии исходников с проверкой sha256.
  Ключ, отклонённые версии и их хеши в промпт не попадают: `task_text` отказывает при утечке. История работы
  (`hidden_repo_paths`) удаляется из практической папки, вместе с `docs/trainer/` и
  `tools/qa/form_check/pairs_v1.json`. Затем папка сканируется на имена, пути, sha256 и 12-символьные
  префиксы хешей ключа и отклонённых версий. Каждый найденный файл удаляется и попадает в `run.json`
  (`scrubbed_files`); если после второго скана что-то осталось, `run` завершается с кодом 2 и называет файл.
  Замер r2 на `origin/main`: KPP1/G22/63A — 3/6/3 файла называли ключ до очистки, после очистки 0/0/0.
  Три прогона-проверки ниже сделаны до этой очистки, но агент ни разу не дошёл до модели, поэтому утечка
  на их первый провал не повлияла. Записывается: время, токены, команды, вопросы
  (`built/QUESTIONS.md`), использованные и пропущенные этапы скелета, новые строки .py вне `jobs/*/hooks/`.
- `score` проходит этапы по порядку: `artifact` (заголовок FBX; сам ключ не принимается), `readback`
  (`tools/blender/fbx_readback.py`), `bounds` (≤ 0,10 м), `topology` (доля квадов ≥ ключ − 0,02), `form`
  (двустороннее отклонение поверхностей через BVH, p95 ≤ 0,05 м, max ≤ 0,30 м, `tools/trainer/surface_dev.py`),
  `form_v2` (детектор формы v2 #1832, если у эталона есть пара), `vlm` (парный судья, оба порядка; только с
  `--vlm`), `package` (`agr validate`). Засчитывается только `pass`. Статусы `not_run`, `not_measured` и `error`
  считаются непройденными. Отчёт содержит первый непройденный этап.
- Правило held-out (#1803): изменение, сделанное по провалу на `tuning`-эталоне, перепроверяется на `held_out`-эталоне.
  Сейчас `tuning`: kpp1-v004, g22-k2-stage1, 63a-stage1. `held_out`: 63b-stage1 (полный) и остальные.

## Codex skill discovery

Each `run` (including each A/B arm) starts Codex with a fresh child-only home and `CODEX_HOME`.
The launcher copies only `auth.json`, if present, into the temporary Codex home and removes the home
after the child exits or times out. The original file is not modified. On a Windows timeout the launcher
attempts to terminate the process tree before cleanup. If files still prevent cleanup, the run still records
`"exit": "timeout"` in `run.json` and logs the remaining directory in `stderr.txt`. On Windows, Codex also discovers
skills from the OS profile even when `USERPROFILE` is redirected. The launcher explicitly disables
the skills under that profile's `.agents/skills` by path. The practice repository's `.agents/skills`
remain enabled. This controls automatic skill availability; it is not a filesystem access boundary.

## Windows `sources-dwg`

Use the in-sandbox route [D389] for DWG inputs. This procedure assumes a cold
`workspace-write` session has already been prepared; the legacy `agr trainer run`
command is not that Windows sandbox launcher. The session owner holds the shared
AutoCAD batch lock (`dcc_batch.py`, `acad`) for the attempt. Use AutoCAD 2025 Core
Console, one drawing at a time, with the source pinned by SHA-256 and a fresh,
single-owner output directory with an absolute ASCII path (no spaces)
inside the existing `workspace-write` sandbox. For example, with the prepared
workspace Python and `SOURCE.dwg` the frozen source copy:

```text
.venv/Scripts/python.exe tools/methods/body/dwg_to_dxf.py SOURCE.dwg tmp/r1/L01.dxf tmp/r1/L01.json --workdir tmp/r1 --copy-name working.dwg --timeout 60
.venv/Scripts/python.exe tools/methods/body/dxf_intake.py SOURCE.dwg tmp/r1/L01.dxf tmp/r1/L01.json tmp/r1/intake.json
```

Run intake only after converter exit 0. Before `plan_from_dxf.py extract`, require
intake exit 0 on the same unmodified bytes: `dwg-to-dxf/1` with matching DWG and
DXF SHA-256, complete ASCII DXF with terminal ENDSEC/EOF, strict parser readback,
nonempty model space and `$INSUNITS=4` (mm). Conversion and intake are not stage
passes by themselves; extraction still needs explicit source-layer and level mapping.

On timeout or any nonzero exit, stop at `sources-dwg`. Keep the converter receipt,
script and console log (or the CLI error if launch/preflight produced no receipt).
Record the source hash, executable/version from the log when available, native
outcome, elapsed/deadline and observed DXF size. Missing DXF and malformed DXF are
different failures: do not use or repair a timed-out output, and do not treat a
header-only check as strict intake (#1866 owns the separate converter false pass).
A timeout has no vendor exit code. Escalate the diagnostics to the operator, not
the sandbox permissions. The operator can run a separately locked, same-byte
host **control** to compare behavior; it is not trainer output or authorization
for the cold agent to run AutoCAD outside the sandbox. Never open the original
DWG or reuse accepted assets from a previous run.

## Банк эталонов

| id | объект | сценарий | статус | прогон | split | ключ (принято) | отклонено |
|---|---|---|---|---|---|---|---|
| kpp1-v004 | КПП-1 | oks-npm/vpm | complete | да | tuning | мастер v004 + пакеты NPM/VPM [D379], [D382] | шаг 3 v004 (ступень 110 мм в углу NW, 2026-11-22) [D380] |
| g22-k2-stage1 | G22 корп. 2, бадик + проёмы | oks-vpm | complete | да | tuning | v002r1, «все норм кроме b корпуса» 2026-11-18 | v001 (#1619) |
| 63a-stage1 | 63, башня A, этап 1 | oks-vpm | complete | да | tuning | v005, принят 2026-11-18 | — (v004 заменён, цитаты отказа нет) |
| 63b-stage1 | 63, башня B, этап 1 | oks-vpm | complete | нет | held_out | v007, 2026-11-20 | v004 (11-17), v005, v006 (11-18) |
| 63c-stage1-2 | 63, башня C | oks-vpm | incomplete | нет | held_out | тело v002 / этап 2 v001 [D355], [D356] | — |
| elv-delivered | ELV | oks-vpm | incomplete | нет | held_out | сдано (PASSPORT), [D377] | — |
| sokolniki-body-v005 | Сокольники УВК 1000 | oks-vpm | incomplete | нет | held_out | v005 [D378] | v006/v007 в PR #1833 |
| vatutino-ground-v015 | Ватутино, Ground | ground-vpm | incomplete | нет | held_out | v015 | — |
| tec26-ac08 | TEC26 AC08 | oks-vpm | incomplete | нет | held_out | v007/v010 | — |
| kpp1-ucx-v004 | КПП-1, UCX одного тела | oks-vpm | complete | да | tuning | основной FBX принятого VPM-пакета [D382] | — |
| moskovsky-ground-v002 | Школа 1200, пос. Московский, Ground | ground-npm | complete | да (только финальная проверка) | held_out | геометрия v002, принята 2026-11-26 | — |

У incomplete-эталонов в `etalons.json` указано поле `missing`: каких путей, хешей или цитат не хватает.

## User Proxy и короткие стадийные задачи (#2066)

План Артёма от 2026-11-27: «Не агент ради архитектуры, а архитектура ради эффективности агента».

**User Proxy и оценщик — разные роли.** Proxy — отдельный процесс `tools/trainer/user_proxy.py`. В прогоне с
`--proxy` он лежит в `RUN/proxy/ask.py` рядом со своим `pack.json`. Агент получает в задаче одну команду:
`python RUN/proxy/ask.py "<вопрос>"`. Proxy отвечает, только если вопрос совпал ровно с одним одобренным ответом.
Ответ выдаётся дословно, со ссылкой на источник. Если совпадений нет или их несколько, proxy пишет `UNRESOLVED`.
Агент тогда берёт документированное значение по умолчанию или останавливается. Каждый вопрос попадает в
`RUN/proxy/log.jsonl` вместе с классом остановки.

Как держится изоляция (тесты — `tests/tools/test_user_proxy.py`):
- proxy не импортирует trainer и не читает банк, ключ и критерии оценки;
- пакет собирает trainer (`proxy_pack`) из поля `proxy_answers` эталона. Пакет отклоняется, если ответа нет
  дословно в его источнике: D-строке, файле решений работы или экспорте фактов. Отклоняется он и тогда, когда
  ответ называет ключ, его хеш, папку принятой сдачи (`key_aliases`) или слова оценщика (допуски, шаги);
- `ask.py` сам отклоняет пакет с полями ключа или оценки (`key`, `sha256`, `tolerances`, `steps`, `score`). Он же
  отклоняет ответы с подсказкой метода: пути `tools/`, `src/`, `.py`, команды `agr …`;
- чтение `pack.json` или `log.jsonl` командой агента считается в метрике `proxy_pack_reads`;
- совпадение — только целыми словами (`curb*` — префикс слова), в каждой группе не меньше 2 разных терминов.
  Одно общее слово (`gap`, `distance`) пакет не пропускает: вопрос «What distance unit does the master use?»
  остаётся UNRESOLVED.
- ответ K1 (формула бюджета UCX [D012]) совпадает с критерием шага `ucx`: это публичное правило регламента
  (`answer_in_repo`), а не скрытый критерий;
- без совпадения класс остановки — тот, что указал агент (`--class`), иначе `unclassified`; поэтому
  `unnecessary_stops` — самооценка агента, смотреть её вместе с числом `unclassified`.

Классы остановок (`--class`; если ответ найден, класс берётся из пакета):

| класс | группа |
|---|---|
| `missing_source_data` — нет исходных данных | обоснованная |
| `customer_decision` — нужно решение заказчика или архитектора | обоснованная |
| `irreversible_sanction` — нужна санкция на необратимую операцию | обоснованная |
| `answer_in_repo` — ответ уже есть в репо | лишняя |
| `allowed_technical_choice` — агент не уверен в техническом выборе, который ему разрешён | лишняя |
| `tool_broken` — инструмент сломался, пути восстановления нет | проблема harness |
| `instructions_contradict` — инструкции противоречат друг другу | проблема контекста |

**Стадийные задачи** — блок `stage_tasks` в `etalons.json`. Проверка `bank_problems` требует dev = `tuning`,
holdout = `held_out` и хотя бы один holdout по незнакомому проекту, которого нет в dev.

| id | набор | проект | стадия | метрики оценщика | ответов proxy |
|---|---|---|---|---|---|
| g22-k2-stage1 | dev | G22 | тело + проёмы одного корпуса | holdout, artifact, readback, bounds, topology, form, form_v2 | 0 |
| 63a-stage1 | dev | POLY63 | линии + проёмы фасадов типовых этажей одной башни | holdout, artifact, readback, bounds, topology, form | 0 |
| kpp1-ucx-v004 | dev | KPP1 | UCX одного тела | holdout, artifact, readback, bounds, form, ucx | 3 (D012, D098, D134) |
| moskovsky-ground-v002 | holdout | moskovsky-sosh1200 (незнакомый) | геометрия Ground одного участка | holdout, artifact, readback, bounds, form | 7 (решения работы 2026-11-26) |

- Шаг `ucx` (только для `target: ucx`; у остальных эталонов он `not_applicable`, прежние оценки сравнимы)
  проходит, только если выполнено всё: UCX есть и укладывается в бюджет [D012]; каждый UCX замкнут и выпуклый
  (`ucx_audit.is_closed` / `is_convex`); доля точек поверхности модели в пределах R13 (1 м, модель -> UCX
  [D134]) не ниже доли у ключа минус 0,02; IoU объёма UCX с UCX ключа не ниже 0,80 (`UCX_TOL` в trainer).
  Калибровка на ключе kpp1-ucx-v004 (readback, 35 407 точек): ключ сам с собой — pass (доля 0,9508, IoU 1,0);
  один бокс по габариту — fail (IoU 0,729); бокс 1 м в центре — fail (IoU 0,0004); бокс за 500 м — fail
  (IoU 0); ключ без одного UCX — fail (доля 0,903, IoU 0,869).
- Ключ `kpp1-ucx-v004` — член `SM_Kpp_1.fbx` принятого VPM ZIP, извлечённый байт в байт. Лежит в
  `1855-trainer-v0/bank/kpp1-ucx-v004/` (`PROVENANCE.txt`, строка в `bank/SHA256SUMS.txt`).
- Holdout запускается один раз, как финальная проверка изменения. Подбирать что-либо по нему нельзя.
- Метрики прогона: `agr trainer metrics RUN [--score S.json] [--usd-per-mtok IN OUT]`. Это успех, балл качества,
  вмешательства человека (ответы proxy), `UNRESOLVED`, остановки по группам и лишние остановки по классам,
  токены и цена, время, повторённые и упавшие команды.
- Очевидные исправления (баг, уязвимость, битая ссылка) проверяются регрессионным тестом, а не экспериментом.
  Три повтора — предварительный замер, а не статистическое доказательство.

Пробные запуски (dry run) 2026-11-27, `agr trainer run <id> --out C:/x/ev_t_f2b55bfe/run-<id> --dry-run --proxy`:
у всех exit 0, папка прогона не создана. Пакет proxy собран и проверен: g22 — 0 ответов, 63a — 0, kpp1-ucx — 3,
moskovsky — 7. Текст задачи называет `ask.py` и не называет ключ.

## Калибровка: принятая версия выше отклонённой

`agr trainer calibrate`, ключ = принятая версия. Ранжирование «принятая выше» почти тавтологично, поэтому пара
засчитывается, только если отклонённая версия ещё и **не проходит** оценку.

| эталон | отклонено | балл принятой | балл отклонённой | p95 отклонённой, м | первый провал | форма v2 (прин./откл.) | ок |
|---|---|---|---|---|---|---|---|
| kpp1-v004 | шаг 3 v004 | 0,714 | 0,429 | 3,468 | bounds | — / — | да |
| g22-k2-stage1 | v001 | 0,857 | 0,571 | 0,610 | form | pass / fail | да |
| 63b-stage1 | v004 | 0,833 | 0,333 | 0,365 | bounds | — / — | да |
| 63b-stage1 | v005 | 0,833 | 0,333 | 0,365 | bounds | — / — | да |
| 63b-stage1 | v006 | 0,833 | 0,500 | 0,327 | bounds | — / — | да |

Итог 5/5 (`G:/Мой диск/AGR-evidence/1855-trainer-v0/calibration.json`, прогон r2). Балл — доля пройденных
применимых этапов. Он меньше 1, потому что `vlm` не запускался (`--vlm` выключен), а у KPP1 пакет не входит в оценку мастера. Форма v2 (#1832)
оценивается только у G22: принятая v002r1 проходит (29 pass / 0 fail), отклонённая v001 — дефект (10 fail).
У 63B детектор считает дефектом саму принятую v007 (7 fail), поэтому ранжировать по нему нельзя. Пара в банке
выключена (`form_check_pair_unused`), а не подогнана.

## Журнал: прогоны-проверки (Codex, `origin/main` c20ef4ef, 2026-11-24)

| эталон | первый провал | балл | время, с | токены вход/выход | вопросов | этапы | новый код | причина остановки |
|---|---|---|---|---|---|---|---|---|
| kpp1-v004 | artifact | 0 | 244 | 1 736 017 / 5 793 | 3 | sources-dwg, validate | 0 | DWG→DXF и контур сделаны; остановка на Gate 1 (PartsList), вопросы Артёму |
| g22-k2-stage1 | artifact | 0 | 158 | 734 035 / 5 051 | 4 | body (только чтение) | 0 | Gate 1 + BM-12; в NPZ нет материалов для зон отделки |
| 63a-stage1 | artifact | 0 | 332 | 2 759 494 / 6 289 | 3 | — | 0 | `scenario` SKILL: «Do not build before user Gate 1 confirms the PartsList» |

**Главная метрика: 0/3 = 0 %** эталонов собраны с первой попытки (ожидалось около 0). Листы:
`G:/Мой диск/AGR-evidence/1855-trainer-v0/<эталон>/sheet_ru.png`.

## Список пробелов (одна причина первого провала → одна задача)

1. **Gate 1 / BM-12 без пользователя.** Во всех трёх прогонах агент останавливается до постройки. Скилл
   `scenario` и `TASK_TO_MODEL.md` требуют подтверждения PartsList и первого модуля, а для headless-тренировки
   правила нет. Нужна задача на режим тренажёра: подтверждение заменяется автооценкой по ключу после этапа.
   Предложенные метки: ready-for-agent, level:medium.
2. **Неполный исходник G22.** NPZ-обрезка без материалов не даёт границ зон отделки [D344]. В банк нужен исходный
   Revit FBX G22 (путь и sha256). Метки: ready-for-agent, level:easy.
3. **Банк неполон для 6 эталонов.** Для них не хватает путей ключей, хешей исходников и цитат отказов (поле `missing`).
   Метки: ready-for-agent, level:easy.

## Сводка для Артёма

Что система умеет сама сегодня. Свежий агент по одному тексту задачи находит сценарий и нужный скелет. КПП-1
он принимает из DWG: DWG→DXF через accoreconsole, перепись слоёв, контур плана. Затем он правильно
**останавливается** и задаёт вопросы, а не строит наугад. Новый код вне хуков не пишет.

Где ломается. До геометрии не доходит ни один прогон (0 из 3): правила требуют подтвердить PartsList и первый
модуль, а в тренировке подтверждать некому. Это первый пробел, и его закрывает режим тренажёра, а не правка модели.
Автооценка уже отличает каждую принятую версию от каждой отклонённой (5 из 5 пар).

## #2067: non-blind A/D smoke test

Twelve scheduled slots (two dev tasks × A/D × three repeats). Snapshot `1c2f297b3753960d14eeb8b8bbd8c18be27e646a`, Codex CLI 0.160.1, `gpt-6.1-terra` high and a 900 s session limit; one session at a time. A used the common prompt; D added only decision-authority rules. Each run received verified source copies, a fresh scrubbed archive and the same task-specific User Proxy. Pair order was fixed within each task (G22: A then D; KPP1: D then A). The host could still expose the evaluation material. No evaluator scores, B/C runs or holdout runs.

Slots 01–04 survived the host interruption. The first attempt of slot 05 had no terminal receipt and is kept separately; only 05–12 were launched after the pause. The resumed prompts explicitly forbade 3ds Max in any mode in both arms; no Max invocation was seen in the captured command log.

### A vs D: scheduled slots only

| Metric | A | D |
| --- | --- | --- |
| 1. `missing_source_data` | 3 | 3 |
| 2. `customer_decision` | 0 | 0 |
| 3. `irreversible_sanction` | 0 | 0 |
| 4. `answer_in_repo` | 0 | 0 |
| 5. `allowed_technical_choice` | 0 | 0 |
| 6. `tool_broken` | 3 | 3 |
| 7. `instructions_contradict` | 0 | 0 |
| 8. `unclassified` | 0 | 0 |
| Human interventions | 0 | 0 |
| Proxy attempts | 3 | 3 |
| Proxy answers | 0 | 0 |
| Proxy unresolved | 3 | 3 |
| Completed shell operations | 162 | 176 |
| Repeated operations | 1 | 0 |
| Failed operations | 38 | 35 |
| Session error events | 0 | 0 |
| Session wall (s) | 1,676.10 | 837.49 |
| Timeouts | 0 | 0 |
| Sessions with token receipt | 6 | 6 |
| `input_tokens` (known only) | 7,683,605 | 5,599,604 |
| `cached_input_tokens` (known only) | 7,273,344 | 5,262,976 |
| `output_tokens` (known only) | 29,443 | 25,929 |
| Actual billed USD | Unavailable | Unavailable |
| Illustrative USD (known tokens, no cache discount) | 39.30 | 28.78 |
| Slots with bank/key audit hits | 0 | 0 |

### Per-run receipts

| Slot | Mode | Task | Repeat | Exit | Wall (s) | Input / cached / output tokens | Stops (class:count) | Human | Proxy attempts / answered / unresolved | Repeated / failed operations / session errors | Key/bank audit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 01-A | non-blind | `g22-k2-stage1` | 1 | 0 | 152.88 | 899,964 / 847,872 / 4,201 | 1:1 | 0 | 1 / 0 / 1 | 0 / 4 / 0 | No hits |
| 02-D | non-blind | `g22-k2-stage1` | 1 | 0 | 120.88 | 690,042 / 633,856 / 3,784 | 1:1 | 0 | 1 / 0 / 1 | 0 / 6 / 0 | No hits |
| 03-D | non-blind | `kpp1-ucx-v004` | 1 | 0 | 120.19 | 740,811 / 696,704 / 3,494 | 6:1 | 0 | 0 / 0 / 0 | 0 / 5 / 0 | No hits |
| 04-A | non-blind | `kpp1-ucx-v004` | 1 | 0 | 837.67 | 2,496,763 / 2,433,792 / 5,219 | 6:1 | 0 | 0 / 0 / 0 | 0 / 9 / 0 | No hits |
| 05-D | non-blind | `kpp1-ucx-v004` | 2 | 0 | 199.42 | 1,644,584 / 1,571,584 / 5,687 | 6:1 | 0 | 0 / 0 / 0 | 0 / 10 / 0 | No hits |
| 06-A | non-blind | `kpp1-ucx-v004` | 2 | 0 | 276.44 | 1,692,590 / 1,635,968 / 6,900 | 6:1 | 0 | 0 / 0 / 0 | 0 / 8 / 0 | No hits |
| 07-A | non-blind | `g22-k2-stage1` | 2 | 0 | 100.83 | 509,595 / 460,672 / 2,977 | 1:1 | 0 | 1 / 0 / 1 | 0 / 6 / 0 | No hits |
| 08-D | non-blind | `g22-k2-stage1` | 2 | 0 | 104.28 | 622,623 / 567,808 / 3,598 | 1:1 | 0 | 1 / 0 / 1 | 0 / 4 / 0 | No hits |
| 09-A | non-blind | `g22-k2-stage1` | 3 | 0 | 94.90 | 585,253 / 533,632 / 3,247 | 1:1 | 0 | 1 / 0 / 1 | 1 / 4 / 0 | No hits |
| 10-D | non-blind | `g22-k2-stage1` | 3 | 0 | 101.88 | 589,758 / 540,160 / 3,260 | 1:1 | 0 | 1 / 0 / 1 | 0 / 3 / 0 | No hits |
| 11-D | non-blind | `kpp1-ucx-v004` | 3 | 0 | 190.84 | 1,311,786 / 1,252,864 / 6,106 | 6:1 | 0 | 0 / 0 / 0 | 0 / 7 / 0 | No hits |
| 12-A | non-blind | `kpp1-ucx-v004` | 3 | 0 | 213.38 | 1,499,440 / 1,361,408 / 6,899 | 6:1 | 0 | 0 / 0 / 0 | 0 / 7 / 0 | No hits |
| 05-D first attempt (partial) | non-blind | `kpp1-ucx-v004` | 2 | Interrupted | Unknown | Unknown | 0 | 0 | 0 / 0 / 0 | 0 / 10 / 0 | No hits |

The first attempt of slot 05 is excluded from the A/D aggregates. Its recorded operations are a lower bound. Its duration, incurred tokens and billed cost are unknown; they are not zeros. The two driver clocks recorded 1,913.34 s through slot 04 and 1,469.48 s for resumed slots 05–12, including preparation. The first clock does not include the interrupted attempt or the pause.

Stops are observed proxy questions and distinct blocking reasons in `QUESTIONS.md` or the final response, excluding gate acknowledgements and duplicate notes. A proxy lookup is counted once as an intervention attempt even when it returns `UNRESOLVED`; no human answered sessions. Class 8 is an extra unclassified bucket, not an eighth stop class. Repeats are exact completed shell command strings after the first occurrence in that session; this does not imply avoidable work. Failed operations use item status/exit code; provider error events and timeouts are separate.

Token usage comes from completed-turn Codex receipts. Cached input is part of input, not additional usage. ChatGPT login exposed no billing receipt. Illustrative USD uses $5 per million input and $30 per million output tokens at full input price; it is not a bill or a spend ceiling.

Read audit: command/tool arguments at start and completion were matched with trainer `_reads_key` (including Drive aliases) plus known key/bank identifiers. A hit is an argument witness, not proof of a successful read; no hit is not proof of isolation. Raw transcripts and private input paths are not reproduced.

<details>
<summary>Source log SHA-256 and stop review adjustments</summary>

| Slot | Codex JSONL SHA-256 | Stop review adjustments |
| --- | --- | --- |
| 01-A | `7e201ecab137e867ac26c704cf0e82adb44994de716dc7ece53eea62a27c5aaf` | — |
| 02-D | `539922407799f6d84a9bc915d224715cb00d23d296971281c77a78feb4972dee` | — |
| 03-D | `0754300e740a8d6a92f38dae7b43ea4bed98db76912f77c6a0f5dffc04c2e26d` | — |
| 04-A | `35af434df6d63e5c37c35902a0a408349f0434115ff7e1411b51b10f6bf8ec5a` | +1 `tool_broken`: The final response reports the failed export and recovery timeout; the stop did not reach QUESTIONS.md. |
| 05-D | `a054eeee71bdcb58d5cb585c43d1401ba0ab1e4baf9839df05e1dbbf84b34d93` | -1 `tool_broken`: The second note lists unverified checks; it does not record a separate tool failure or escalation. |
| 06-A | `1eee630b0ab3b024d178579796ee9525bb1f2dc9d9143bd6c794bf0794a6a02c` | -1 `tool_broken`: The second note is a QA observation, not a separate unrecovered tool failure.; -1 `tool_broken`: The third note restates unavailable validation and lists unverified checks without a distinct operational stop. |
| 07-A | `eda45d59f567b2214933bf693de8b3d243ed34e3f85a355c8255a293c9d5cbb0` | — |
| 08-D | `d46ce4660b9441c5c48a2e4ed5490a1c8ef44ca2c02fed6183b8feea2839a9cd` | — |
| 09-A | `da898ecfabed85442f43f28a627d6d2d8e59edb8b2bbb377ae2df97b78fc3f96` | — |
| 10-D | `da7e8e6a4436648b29d3b0437ecfbd9d4b043cf932bbae2f08739a31a882d05e` | — |
| 11-D | `ee5c3c4adbb322812167dbc4325441e05e09903a9a3aa4a83679ad6ba37c99d5` | +1 `tool_broken`: The stop is present in the final response and in a structured note with a literal backtick-n prefix. |
| 12-A | `09e552060a4baece7c039adc905ba34261df04659c7c87bd5f173c34a476a5f1` | -1 `tool_broken`: The second note lists unverified checks and does not record a separate unrecovered operation. |
| 05-D first attempt | `010dd852ea6d6fb7e084b75e81aa38e6b62ff7482c0bd13a4efd9c2884b13322` | Incomplete |

</details>

### Итог и рекомендация

Остановки G22 по отсутствию исходных данных: A 3, D 3; остановки KPP1 по сбою инструмента: A 3, D 3. На один прогон 04-A пришлось 837.67 с; разницу общего времени не следует переносить на следующие задачи. Эта серия показывает, где прогоны останавливались, а не качество моделей или причинный эффект D. Перед расширением стоит проверить, что `agr ucx` запускает полный набор проверок в окружении builder, и взять для рабочего сравнения задачу с подтверждённо полными входами. Выбор B/C и запуск holdout — только после отдельного решения; для оценки качества нужна проверенная изоляция.
