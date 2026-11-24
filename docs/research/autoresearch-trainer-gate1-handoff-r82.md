# Autoresearch #82 — Gate 1 handoff baseline (OBSERVE)

**Кратко (RU).** #81 уже проверяет идею тренировочного прохода Gate 1/BM-12 без пользователя и ждёт решения. Здесь до любых изменений измеряем более ранний, независимый шаг: существовала ли вообще версия PartsList, которую можно было привязать к штатному запросу подтверждения. Сборка, смена правил и чтение скрытых ключей исключены.

## Frozen contract

- M82 = number of the three #1859 trainer smoke runs with a candidate PartsList JSON in `built/` or `wt/jobs/`, accepted by `dt_ai.core.models.PartsList`, with a calculable `approval_sha256()`. Denominator is three smoke runs, not the separate #1608 execution. This is a necessary condition for an actionable handoff, not proof of a posted request, user approval or artifact production.
- Audit recording command: `uv run --frozen python docs/research/trainer-gate1-handoff-r82.py`; audit exactly three passes over the same local evidence, report the median and range. These are readback repeats, not independent training trials. Freeze case IDs `kpp1-v004`, `g22-k2-stage1`, `63a-stage1` (date `20261124`). Positive stop witness: 63A `last.txt`. Held-out `63b-stage1` remains unexecuted; it was not a practice-ready member in #1859. No accepted or rejected package is being scored.
- Candidate discovery: all case-insensitive `parts.json` / `partslist.json` files under the two output roots; exclude tracked and pre-existing committed files in `wt`, but not `built/` evidence. Exclude the staged input directories and avoid printing proposal content. Also record file presence, validation errors by class, both hashes of valid proposals and a content manifest for `last.txt`, `run.json`, worktree HEAD and candidate paths. Scope is conventional outputs only; this cannot exclude files elsewhere or establish whether a historical external request existed.
- One read-only baseline, no new training candidates or confirmation attempts. Stop after three audit passes, 90 seconds per command, or missing evidence. No keep threshold is being exercised. A future candidate would need to produce an independently measured increase (at least 2/3 complete handoffs on each of tuning and held-out) without converting a draft into approval; the current audit may only locate the gap. No policy change, historical approval reuse, input edits, full suite, delivered-package edits or source/held-out label changes. Parity: no evidence files or production behavior modified; check evidence digests on each pass and fail on drift.

## Result

**0 из 3** тренировочных прогонов оставили `parts.json` / `partslist.json` в проверенных выходных каталогах. Это остановка **до** подготовки запроса на согласование, а не отказ пользователя принять готовый список. Изменение способа прохождения Gate 1: **inconclusive**, новых сборок не было. Контрольная 63B, принятые и отклонённые сборки, внесённые дефекты и проверка опубликованных запросов — **not measured**.

The audit completed in 25.766 s including environment setup. M82 `[0, 0, 0]`; median 0, spread 0 (readback only). No pairs or real validation calls on trainer proposals: there were no candidates. The exact trainer ledger is `4e0de5610633dfb69908cbc0ad1a6aedee07739c:docs/trainer/ledger.json` (SHA-256 `44266b4f309c78200830d9363cca489e3105d9c605ee0bbfbd8d6fcbc38dd70e`); it labels these rows `artifact`. The separate [#1608 execution row](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1855#issuecomment-7146055090) stopped at `sources-dwg`; it is not in M82.

Replay (Bash; no writes to training evidence):

```bash
set -o pipefail
uv run --frozen python docs/research/trainer-gate1-handoff-r82.py | diff -u docs/research/trainer-gate1-handoff-r82.json -
```

An empty diff/exit 0 checks the digest and path census, not independent-run stability. The receipt pins both evidence files read per run, the archived worktree HEAD and the observed empty proposal sets. Replay is **limited** to the local run directories; the Drive bank is #1861. No accepted/rejected package, hidden key or DCC was opened. No production change is retained; no PR.
