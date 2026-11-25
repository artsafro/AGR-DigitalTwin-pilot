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
uv run agr trainer run ETALON --lane codex --out NEW_DIR [--timeout-s 1800] [--dry-run]
uv run agr trainer score ETALON --built NEW_DIR/built --out NEW.json --png NEW.png [--vlm]
uv run agr trainer calibrate --out NEW_DIR
uv run agr trainer ledger --add NEW.json --lane codex --run NEW_DIR --date YYYY-MM-DD
uv run agr trainer ab ETALON --ab OLD_DIR NEW_DIR --scope INVARIANT|DOMAIN --out NEW_DIR [--lane codex] [--dry-run]
```

### A/B probe of a harness edit [D414]

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

У incomplete-эталонов в `etalons.json` указано поле `missing`: каких путей, хешей или цитат не хватает.

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
