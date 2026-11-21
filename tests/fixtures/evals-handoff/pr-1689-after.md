## Итог

В свободном слоте неизменённая команда merge-gate на зафиксированном срезе `main` (`c62ceddd`) уложилась в 30 минут во всех трёх валидных прогонах. Медиана — **22:58**. Все **27 454** идентификатора и исхода совпали. Оптимизации не понадобились: уже первый валидный прогон занял 24:48. PR добавляет только протокол, журнал и квитанции замеров; не меняет набор тестов, маркеры, проверки или допуски.

| Замер | Wall time команды | Passed / skipped / xfailed |
| --- | ---: | ---: |
| Исторический ориентир #1615 (только сводка pytest, не сопоставимый baseline) | 58:37 | — |
| Baseline B1 | 1487.896 s (24:48) | 27218 / 187 / 49 |
| Подтверждение C3 | 1327.091 s (22:07) | 27218 / 187 / 49 |
| Подтверждение C4 | 1377.597 s (22:58) | 27218 / 187 / 49 |
| **Итоговая медиана B1 + C3 + C4** | **1377.597 s (22:58)** | **27218 / 187 / 49** |

```text
$ diff -u baseline-002.nodes.tsv confirmation-003.nodes.tsv
[exit 0; 0 output lines]
$ diff -u baseline-002.nodes.tsv confirmation-004.nodes.tsv
[exit 0; 0 output lines]
```

Оба сравнения проверили отсортированные пары `(nodeid, outcome)`, включая `passed`, `skipped` и `xfailed`. Повторная обработка трёх журналов воспроизвела TSV байт-в-байт, 18 SHA-256 совпали. SHA-256 каждого TSV: `51e8655c16f0eaee17cc4fe891852fd3a4cc5fef4a26213426f043ec24f28d48`. Журналы и TSV: `C:/x/autoresearch-suite-wall/`, архив `suite-wall-parity-1615.zip` в карточке `t_82b1bc95`. [Протокол и журнал раундов](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/82a50a71a743e696237c936fe300d8b48b0b93db/docs/research/autoresearch-suite-wall.md).

Время ожидания слота не входит в метрику. Сравнение с 58:37 не доказывает ускорение, а замеры на `c62ceddd` не подтверждают время на обновившемся `main` или при конкуренции за ресурсы. `merge_chain` и `merge_batch` не изменены. OBSERVE: без автоматического слияния.

### Acceptance table

План проверок зафиксирован до реализации в [`48b4fb55`](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/48b4fb55/docs/research/autoresearch-suite-wall.md#acceptanceprobe-plan-before-harness-implementation). Ниже — его фактические результаты и проверка правки R1. `good` — точный контроль из `probe_observer.py`: `collection(gw0, ['a']) → setup(a, passed, 0.0) → call(a, passed, 0.0) → teardown(a, passed, 0.0) → finish(0)`.

| # | Acceptance point | Input (exact) | Expected output | Test | Result |
|---|---|---|---|---|---|
| A1 | «same passed, skipped and xfailed node ids» — наблюдение xdist | `test_sample.py` с `test_ok`, `test_skip`, `test_xfail`, `test_nested`; `python -m pytest -q -n 2 -o addopts=` | Exit 0; два одинаковых набора выбранных ID; исходы `passed, passed, skipped, xfailed` | `probe_observer.py::ObserverProbe.test_real_xdist_and_nested_and_clobber` | 2 коллекции, 4 исхода: 2 / 1 / 1 |
| A2 | No evidence clobber (план) | Повтор той же команды A1 с тем же `AR_WALL_EVENTS=events.jsonl`; отдельно `sub/../receipt.json` при `receipt.json` со строкой `source` | Ненулевой exit и неизменный журнал; альтернативный путь даёт `FileExistsError` и сохраняет `source` | A1 и `probe_runner.py::RunnerProbe.test_existing_alias_output_is_not_overwritten` | 2/2 отказа, 0 перезаписей |
| A3 | Nested subprocess isolation (план) | В `test_nested` запускается свежий `python -m pytest -q child_case.py -o addopts=` с `test_child` | Дочерний exit 0, `test_child` отсутствует во внешнем журнале | A1 | 1 успешный дочерний процесс, 0 дочерних ID во внешней выборке |
| A4 | «sorted node id lists of baseline and final diff to empty» | `baseline-002.nodes.tsv` против `confirmation-003.nodes.tsv` и `confirmation-004.nodes.tsv`; в A1 заменить `passed` на `skipped` при тех же ID | Реальные diff пусты; изменённый исход не равен исходному списку | Два `diff -u` выше; A1 (`assertNotEqual`) | 2 × exit 0 и 0 строк на 27 454 парах; 1/1 изменение исхода обнаружено |
| A5 | «median of 3 runs on an idle slot» | `baseline-002.json`, `confirmation-003.json`, `confirmation-004.json` — 1487.896, 1327.091, 1377.597 s на `c62ceddd` | 3 валидных замера, медиана < 1800 s | Replay квитанций и медиана из отчёта | 3/3 валидны; 1377.597 s |
| A6 | No merge overlap (план) | `agr-suite-slot-0.lock`: PID `122`/`merge-old`, PID `123`/`merge-live`, затем `partial`; запрос процессов возвращает `{"ProcessId":456}`; C1 `confirmation-001.json`: `merge20261117red3` | Мёртвый holder игнорируется; живой holder / chain виден; битый lock даёт отказ; C1 не учитывается | `probe_runner.py::RunnerProbe.test_holders_dead_live_and_malformed`, `test_process_query_fails_closed_and_detects_chain`; квитанция C1 | 0 мёртвых / 1 живой holder, 1 chain обнаружен, 1 испорченный lock отклонён, 1 реальный замер прерван на 968.460 s |
| A7 | No stale source (план) | Неотслеживаемый `new.py`: содержимое `a` → `b` между снимками `tracked()` | Подписи различаются; такой снимок не годится для сравнения | `probe_runner.py::RunnerProbe.test_source_signature_detects_untracked_mutation` (проверка сигнала, не полный прогон) | 1/1 изменение обнаружено |
| E1 | edge: order / position | `good[:2] + good[1:]` (две соседние фазы `setup` для `a`); `good + [{'kind':'unknown'}]` (событие после `finish`) | Оба журнала дают `ValueError` | `probe_observer.py::ObserverProbe.test_validator_rejects_malformed` | 2/2 отклонены |
| E2 | edge: reset | Три последовательных ответа запроса процессов: exit `1`, stderr `query unavailable` → exit `0`, stdout `''` → exit `0`, stdout `{"ProcessId":456}` | `RuntimeError` → `[]` → обнаружен chain; предыдущий запрос не влияет на новый | `probe_runner.py::RunnerProbe.test_process_query_fails_closed_and_detects_chain` | 3/3 ожидаемых результата |
| E3 | edge: repeated refusals | Для `call` в `good` независимо подставить длительности `NaN`, `inf`, `-1.0`, затем исходы `bogus`, `failed`, `xpassed`; отдельно `finish(1)` | Все варианты дают `ValueError` | `probe_observer.py::ObserverProbe.test_validator_rejects_malformed` | 7/7 отклонены |
| E4 | edge: empty | `[]`; отдельно `good` с `gw0.ids=[]` | Ни один из входов не считается валидным | `probe_observer.py::ObserverProbe.test_validator_rejects_malformed` | 2/2 отклонены |
| E5 | edge: partial / changed selection | `good` без `finish` или без `teardown`; `gw0.ids=['a','a']` или `['b']`; перед `good` добавить `collection(gw1, ['b'])` | Ни один из пяти журналов не считается валидным | `probe_observer.py::ObserverProbe.test_validator_rejects_malformed` | 5/5 отклонены |
| E6 | edge: no false positive | Неизменённый `good` с `duration=0.0` на всех фазах | Точно `[('a', 'passed')]` | `probe_observer.py::ObserverProbe.test_validator_rejects_malformed` (положительный контроль) | 1/1 принят, 1 пара |
| R1 | [R1/P1: отсутствует обязательная Acceptance table](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/1689#issuecomment-7001350997) | Фактическое тело `gh pr view 1689 -R artsafro/AGR-DigitalTwin-pilot --json state,body,headRefOid,baseRefName,autoMergeRequest` до и после правки | До: exit 1 без таблицы; после: exit 0, 14 заполненных строк, исходный текст вне вставки сохранён, `Closes #1615` последней строкой | `tmp/check_pr_1615_r1.py` (метаданные, содержимое и структура опубликованного PR) | 1/1 ожидаемый отказ до правки; 14/14 строк в проверяемой версии |

Итого: 14 строк; 6 методов стенда прошли (включая 16 отклонённых синтетических журналов). Отдельно: 2 сравнения TSV, проверка квитанций, проверка опубликованного тела PR. Полная suite на этом head не повторялась.

## Out-of-scope fixes

- Только в окружении измерительного процесса: Git Bash поставлен перед системной заглушкой WSL; PowerShell preflight выбирает первый найденный `bash.exe`. Глобальный PATH, тесты и runner не менялись.

## Out of scope

- [Сбой WSL в B0](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/82a50a71a743e696237c936fe300d8b48b0b93db/docs/research/autoresearch-suite-wall.md#b0-diagnosis-and-environment-only-repair-2026-11-17): 6 ошибок воспроизвелись на `origin/main` с системным Bash; с Git Bash прошли все 12 проверок. Настройки машины не исправлялись.
- [Конкуренция за слот в C1](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/82a50a71a743e696237c936fe300d8b48b0b93db/docs/research/autoresearch-suite-wall.md#b1-validated-and-unchanged-corpus-confirmations): замер отклонён; планировщик, CI и политика не менялись.

## Author receipts

Pattern: n/a (documentation and audit snapshots only; no new runtime module)

Before (RED): 48b4fb55 `uv run python tmp/wall_harness/probe_observer.py`: 2 errors (observer not yet implemented)

After (GREEN): 82a50a71a743e696237c936fe300d8b48b0b93db `uv run python -m unittest discover -s tmp/wall_harness -p 'probe_*.py' -v`: 6 passed, 0 failed

Affected tests (head 82a50a71a743e696237c936fe300d8b48b0b93db): 6 passed, 0 failed

Full suite: deferred to merge batch (rule 68)

The three benchmark runs above are authorized measurements on their recorded source revisions, not a final-head merge CI receipt.

Regression evals: tmp/evals/report.json; 0 passed / 0 failed / 11 not measured (no matching transcript or PR-view evidence at author run)

Probe: identical four-worker collection and complete terminal outcome per node -> synthetic xdist pass/skip/xfail, nested pytest isolation, clobber refusal and 16 malformed-ledger cases -> all checks passed in the 6-method harness run (`tmp/final-harness.log`).

Sample output: tmp/final-parity.log

repo_guards: GREEN (442 passed; run before final whitespace-only cleanup)
## Agent trace

- Sessions: not measured (no transcript)
- Written by: Hermes / dt-worker-codex
- Subagents: not measured (no usage log, no transcript)
- Skills: not measured (no usage log, no transcript)
- Commands: not measured (no usage log, no transcript)
- Hook denials: not measured (no transcript)
- Retries: not measured (no transcript)
- Context at handover: not measured (no transcript)
- Duration: not measured (no transcript)
- Commits: `c62ceddd..82a50a71` (8 commits)

Closes #1615
