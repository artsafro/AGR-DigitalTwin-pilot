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
