# Autoresearch #81 — trainer: most frequent first stop = Gate 1 in headless practice (OBSERVE)

**Кратко (RU).** Фокус карточки — шаг, который чаще всего проваливается в ledger тренажёра (#1855/#1608).
Пересчёт причин остановки по сырым ответам агентов: **Gate 1 (подтверждение PartsList) — 3 из 4 строк**
(KPP1, G22, 63A в ledger #1859; во всех трёх `first_failing_step = artifact`, но реальная остановка — правило
«Do not build before user Gate 1 confirms the PartsList»). `sources-dwg` — 1 из 4 (#1608), им владеют #1857/PR #1863,
а в прогоне тренажёра KPP1 этот шаг уже прошёл через accoreconsole (решение Артёма 2026-11-24 ~23:45).
Измерение не запущено: способ пройти Gate 1 без пользователя — это изменение правила пользовательского гейта,
нужен ответ Артёма (вопрос ниже). Контракт заморожен до любого замера.

Status: **user decision received ([D391], Artem 2026-11-25 ~09:00); candidate frozen (amendment below) before measuring.**
Hypothesis result: see "Result" (filled after the series).

## Amendment A1 (2026-11-25, frozen BEFORE any M81 run)

- Decision: [D391] (`docs/decisions.md`; D390 is taken by `feat/issue-1867-scene-prepare`).
- **Candidate = the `Practice gates [D391]` paragraph of `task_text`** in `tools/trainer/trainer.py`
  (file SHA-256 `65c02ce9e0e96eb0f0cb76d7ed062ab3d47c50380506f5456842c08a4e213a53` at the measurement commit).
  It replaces "or stop" only for Gate 1 / BM-12; parts.json stays `status: review`, `gate1` empty (no fake approval),
  the label `gate1=practice-self` + file SHA-256 + `approval_sha256()` goes to `QUESTIONS.md`.
- **Held-out 63b-stage1** is `practice_ready: false` in the committed bank ("practice not scheduled in v0; held-out for
  changes made on 63A/G22"). The committed bank stays untouched; runs use a scratch copy
  `C:/x/ev_t_bd71dc55/bank_63b_heldout.json` (SHA-256 `610c9789…` pre-fill → final `496c3bea69f51995d7bf9a93d71ab9594035b9514252ecc981bf8990951523b8`) where only 63b gets `practice_ready: true`
  and its key `sha256` filled from the file (needed by `bank_problems`; the key is never in the prompt — `task_text`
  leak check + secret-token grep of events).
- Practice tree = `origin/main` at launch (recorded per run in `run.json:origin_main`).
- Run order: pairs (63a_i, 63b_i) concurrently, i = 1..3, `--timeout-s 1800`. Per-run artifact = any `*.fbx` in `built/`.
- Not measured here: KPP1 / G22 (no new runs; r83 runs belong to #83), scoring steps after `artifact` are secondary.

## Preflight (measured, read-only)

Ledger source: `origin/research/issue-1855-trainer-v0@7607975b29cc9ad337d2708fc3198fc0b235eb36`
`docs/trainer/ledger.json` (blob SHA-256 `44266b4f…dd70e`), `docs/trainer/ETALONS.md` (`b1d86390…b9adf`), plus #1608 row
(#1855 comment 2026-11-24T22:17Z, PR #1860 merged).

| Run | Ledger first_failing_step | Actual stop (agent's `last.txt`) | last.txt SHA-256 |
|---|---|---|---|
| kpp1-v004 codex 2026-11-24 | artifact | Gate 1 PartsList (DWG→DXF via accoreconsole passed L01-L03) | `bb1cbb59…8fe2d` |
| g22-k2-stage1 codex 2026-11-24 | artifact | Gate 1 PartsList (+ BM-12, NPZ without materials) | `e0fd9bff…e755` |
| 63a-stage1 codex 2026-11-24 | artifact | Gate 1 PartsList (scenario SKILL quote); Blender 5.1 crash on import also seen | `8dfe65b4…a520` |
| KPP1 v004 #1608 | sources-dwg | sources-dwg (AutoCAD not allowed then) | — |

Count: Gate 1 = 3/4, sources-dwg = 1/4. Run dirs: `C:/x/trainer/runs/<run>/` (local scratch, replay limited; #1861
owns moving the bank to Drive). The prompt (`tools/trainer/trainer.py:216`) says "continue with the documented default
or stop"; no documented headless default for Gate 1 exists on main (`git grep -i "trainer\|practice"` over
`.agents/skills/scenario/SKILL.md`, `docs/procedure/TASK_TO_MODEL.md` = 0 hits).

Ownership: #1857/#1863 (sources-dwg), #1858/#1865 (inspect launcher), #1859 (trainer v0, under rework: P1 key leak),
#1861 (bank on Drive). The Gate 1 gap is gap #1 in #1859's ETALONS.md, **no issue filed** — not owned.

## Contract (frozen before any measurement)

- **Metric M81** = share of practice runs whose agent produces the deliverable FBX in `built/` (artifact step passes)
  instead of stopping at Gate 1. Secondary: first_failing_step after artifact, wall s, tokens in.
- **Candidate (one variant)**: a documented trainer-mode default in the practice prompt/skeleton, text frozen after the
  user decision (e.g. "practice run: write the hash-bound PartsList to built/PARTSLIST.json, record it in QUESTIONS.md as
  `gate1=practice-self`, then continue; the hidden-key score replaces the user's confirmation; never valid outside
  `agr trainer run`").
- **Baseline**: the three rows above (0/3 artifact).
- **Fixtures**: tuning = 63a-stage1 (cheapest representative of the Gate 1 stop with an FBX source); held-out =
  63b-stage1 (`split: held_out`, never used for tuning). Positive trigger witness: baseline 63A run stops at Gate 1.
- **Series**: 3 fresh Codex runs per fixture with the candidate (median of 3), run through `agr trainer run` on a
  #1859 head that has the P1-2 key-leak fix (r3 `7607975b` or later, re-verified by `git grep` of secret tokens = 0).
- **Keep threshold**: artifact produced in ≥2/3 runs on BOTH tuning and held-out, with no key access (secret-token
  grep of the agent's events = 0) and no Gate-1 text applied outside practice runs (grep of main skills unchanged).
- **Stop rule**: 6 runs max or 4 h wall; budget stop = inconclusive. Confirm-vs-new-candidate budget: 0 new candidates
  (one variant only).
- **Forbidden**: changing production Gate 1 / BM-12 rules, auto-approving in real jobs, reading keys, editing delivered
  packages or other cards' files (#1857/#1859/#1861/#1863/#1865), counting a run that read the key.
- **OBSERVE**: the result is recorded; any prompt/skeleton change goes through a normal PR on #1855/#1859's owner.

## Open question for Artem (blocking)

В тренировочных прогонах (#1855, `agr trainer run`, свежий агент без пользователя) можно ли агенту самому
«подтверждать» Gate 1 (PartsList) и BM-12 (первый модуль): записать PartsList с хешем, отметить его как
`gate1=practice-self` и строить дальше, считая оценку по скрытому ключу заменой вашего подтверждения — только в
тренажёре, без изменения правила для настоящих задач? Рекомендация: да, только в тренажёре.

Replay of the preflight: `git show origin/research/issue-1855-trainer-v0:docs/trainer/ledger.json | sha256sum` and
`sha256sum C:/x/trainer/runs/*/last.txt` (local scratch; replay limited until #1861).
