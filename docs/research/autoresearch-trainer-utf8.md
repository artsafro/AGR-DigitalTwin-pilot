# Standing #86 — trainer Gate 1 question transport (OBSERVE)

## Frozen contract (before replay or candidate code)

Ledger at `0ceaf135` has 3/4 `artifact` stops (KPP1, G22, 63A, no FBX), and 1/4 `sources-dwg`. Execution evidence in #1855/#1608 records three Gate 1 stops among those ledger rows, and a separate initial #1608 DWG stop. This does not count either DWG stop as a Gate 1 or geometry failure. #81 owns the explicit user decision and artifact experiment, #82–#84 own hash-bound PartsList handoff evidence, #85 owns stop classification, #1874/PR #1880 owns DWG, #1861 owns bank durability, and #1879 owns the Blender guard fix. Texture fallback is inactive and form is closed.

Target: an actionable Gate 1 question must survive the writer before it can be answered. Hypothesis H86: BOM-less UTF-8 native pipeline output (`$OutputEncoding = [System.Text.UTF8Encoding]::new($false)`, scoped to the Windows PowerShell command and paired with Python UTF-8 stdin) preserves text that is corrupted when a PowerShell here-string is piped to `python -`. #85 identified one native corrupted question file, G22 C3. We test this specific mechanism, not whether a prompt would make an agent adopt the writer, whether a human approves, or whether an artifact passes.

Inputs must match SHA-256 before use (root `C:/x/trainer/runs`; local, replay limited). Never execute captured commands; extract only the literal question text. No hidden keys or approved/rejected model files are read.

| Fixture | Event | events.jsonl SHA-256 | built/QUESTIONS.md SHA-256 |
| --- | --- | --- | --- |
| KPP1, `kpp1-v004-codex-20261124` (tuning, native intact control) | `item_25` | `a7f4358322cb44ab8d308042cb520ac13b173ff41a8d4edae44dde6f8191e461` | `81eea996a8b0f31d263e6077d7a2d49876af991e5d5dd28850dc20dfa05c1e8b` |
| G22, `g22-k2-stage1-codex-r83-C3` (held out for H86, native damaged trigger) | `item_15` | `053c3a2b4c2445db68cf9460f100d43a3b00bcd56471d0b19269e1bd6fd76a6d` | `d99e518d80d00b68dbccafb67a3102436282f53aa8cd8282ae9a89d273204301` |

- M86 = count of Unicode code points replaced or otherwise changed by the transport versus the authored literal (lower is better; use indexwise mismatch for equal lengths and mark a length change as a separate hard failure). Report each input separately; no pooling across assets. Protect the trainer's unchanged question count, newline semantics and strict UTF-8 readback. Clean native KPP1 must be byte/text-equivalent after matching its original newline convention, and the candidate must also exercise the full KPP1 payload through the pipeline (not skip it). Native damaged G22 must match the default replay byte-for-byte after matching its original newline convention. Candidate must match the authored literal exactly with zero changes, on both payloads. Expected default change: >0 on both non-ASCII pipeline replays; H86 is confirmed only if all these conditions hold. No claim about Artem's model acceptance: labels here refer only to native text transport.
- Controls: printable ASCII with real question marks and a numbered answer is run through both routes; expect 0 changes (ASCII preservation measured, non-ASCII recovery not exercised). Add `é — Ё 漢` to the KPP1 payload in memory as a mixed-script perturbation: expect >0 default changes and 0 candidate changes. No edit to native files. Newline or count changes fail the guard. Do not count a reread of an existing file as a fresh attempt.
- Run 3 fresh paired native processes per state, alternating between default-first and candidate-first; median of 3, per-pair spread and wall time separately. The historical native files are one observation each. Confirm budget is one series, no new candidates; stop after the series or 120 seconds of replay wall time, whichever comes first (overrun incomplete = inconclusive). First complete pair is the budget check, part of the series only if unchanged; no substitution with fewer samples. Record clean, injected and not-measured checks separately.
- Replay from this worktree (Git Bash): `PYTHONPATH=. uv run --frozen python docs/research/trainer-utf8-r86/replay.py --out <NEW.json>` (Windows PowerShell and pinned native files required). No app launch besides Windows PowerShell/Python, no model/package, other branches, production rules or deliverables edited, no new dependency, no weakened guards. A possible next change is a practice-only UTF-8 writer example, through normal review with the trainer owner. Nothing is applied in this card.

## Итог OBSERVE

**H86 подтверждена только для передачи текста.** На G22 исторический повреждённый `QUESTIONS.md` воспроизвёлся побайтно в 3/3 отдельных процессах с настройкой по умолчанию. При явном UTF-8 все 1097 потерянных символов сохранились в 3/3, число пунктов и переводов строк не изменилось. На KPP1 UTF-8 сохранил текст побайтно относительно исторического исправного файла. Это не подтверждение PartsList, не прохождение Gate 1 и не выпуск FBX. Изменения в тренажёр не вносились.

## Round log

Frozen contract: `90bc2e2d`. Ledger: `0ceaf135` (not merged into this branch). First attempted replay completed in 19.352 s but left 12 shell-renderer quote characters around three ASCII substitutions in the reconstructed G22 literal. It consequently failed byte parity. Preserved as `trainer-utf8-r86/preflight-extraction-error.json` (invalid for the candidate verdict). The repair strips only the three capture-specific wrappers, once each, before parsing the literal; the candidate, hashes, samples, order and decision thresholds are unchanged. Replayed the whole series; no pooling or chasing a new candidate. The ASCII path and two hash strings were taken from the hash-bound native output, while the original Cyrillic comes only from the saved command literal. No captured command was executed.

| State | Default → UTF-8 changed code points (median of 3) | Paired improvement min–max | Newlines / counted items | Native parity |
| --- | ---: | ---: | ---: | --- |
| KPP1, native clean | 985 → 0 | 985–985 | 8 / 3 | UTF-8 exact 3/3 |
| G22 C3, native damaged (held out for H86) | 1097 → 0 | 1097–1097 | 15 / 8 | default exact 3/3 |
| Injected printable ASCII | 0 → 0 | 0–0 | 2 / 2 | non-ASCII recovery not exercised |
| Injected mixed script on KPP1 | 989 → 0 | 989–989 | 10 / 3 | not a historical file |

Run `complete`, 17.584 s wall (24 fresh PowerShell processes); Python 3.14.7, Windows PowerShell from `SystemRoot`. Receipt: `trainer-utf8-r86/receipt.json`, SHA-256 `e6b9741df1769c430a7af064d73dd04138633097ab86c544b16c6c2380b8cb1d`. Replay is limited to the pinned local files and Windows host/runtime. Not measured: question-author adoption, passage beyond Gate 1/BM-12, regenerated models, model QA, 63B cold run. Affected tests: `tests/tools/test_trainer.py tests/test_trainer_inspect.py`, 82 passed (isolated `--basetemp`). Full suite: deferred to merge batch (rule 68).

Next experiment with the trainer owner: measure adoption of an explicit practice-only UTF-8 writer example in fresh runs; count readable question text by comparing the authoring event to the persisted questions, not by searching for `?`. Keep any permission/passage experiment with #81.
