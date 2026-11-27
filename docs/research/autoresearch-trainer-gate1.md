# Autoresearch #81 — trainer: most frequent first stop = Gate 1 in headless practice (OBSERVE)

**Кратко (RU).** Фокус карточки — шаг, который чаще всего проваливается в ledger тренажёра (#1855/#1608).
Пересчёт причин остановки по сырым ответам агентов: **Gate 1 (подтверждение PartsList) — 3 из 4 строк**
(KPP1, G22, 63A в ledger #1859; во всех трёх `first_failing_step = artifact`, но реальная остановка — правило
«Do not build before user Gate 1 confirms the PartsList»). `sources-dwg` — 1 из 4 (#1608), им владеют #1857/PR #1863,
а в прогоне тренажёра KPP1 этот шаг уже прошёл через accoreconsole (решение Артёма 2026-11-24 ~23:45).
Артём разрешил самоподтверждение только в тренажёре ([D391]); серия M81 выполнена: гипотеза опровергнута (0/6 FBX),
новая первая остановка — какая часть FBX площадки является башней (6/6). См. «Result».

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

## Result (M81 series, 2026-11-25 08:40-08:55, practice tree origin/main `7f005be5`)

**Кратко (RU).** Гипотеза **опровергнута**: самоподтверждение Gate 1 по [D391] снимает остановку на Gate 1
(6/6 агентов записали `gate1=practice-self` с хешами), но FBX не построен ни в одном прогоне — **0/3 на 63A
(настройка) и 0/3 на 63B (отложенный эталон)**. Новая первая остановка у всех 6: агент не может определить, какая
часть общего FBX площадки — башня A/B (контур/границы башни); в 4/6 ещё вопрос об источнике зон отделки (D341).
Порог KEEP (≥2/3 на обоих) не достигнут; изменение текста оставлено как исполнение решения [D391], не как KEEP.

| Run | wall s | tokens in | FBX | gate1=practice-self | BM-12 | Actual stop (last.txt / QUESTIONS.md) |
|---|---|---|---|---|---|---|
| 63a-1 | 245.7 | 1 693 474 | — | yes | not reached | tower A region in site FBX unknown; finish zones (D341) |
| 63a-2 | 227.3 | 2 270 090 | — | yes | not reached | no tower A contour/opening schedule; finish zones |
| 63a-3 | 292.9 | 2 679 546 | — | yes | not reached | tower A binding to source coordinates/objects |
| 63b-1 | 236.2 | 1 815 100 | — | yes | not reached | Revit→BodyPlan adapter absent in checkout; tower B contour |
| 63b-2 | 295.4 | 3 103 203 | — | yes | not reached | tower B boundary/zero at podium; adapter; finish zones |
| 63b-3 | 262.0 | 2 019 892 | — | yes | not reached | tower B link to K1–K4 / boundary coordinates |

- M81: tuning 0/3, held-out 0/3 (median 0, spread 0). Baseline 0/3 → candidate 0/6. **Hypothesis: refuted.**
- Secondary, exercised: Gate 1 stop removed 6/6 (positive witness = baseline 63A stopped at Gate 1); BM-12 `not_exercised`
  (no module built in any run) — **not measured**.
- Run status: 6/6 `exit 0`, voluntary stop at 227-295 s (timeout 1800 s never hit); series wall 15 min. Budget: 6/6 runs used.
- Key isolation check (contract): secret-token grep of events is **non-zero in 6/6** (1-19 hits per token): the tokens are
  job paths (`jobs/POLY63-*`, `jobs/garibaldi22`) quoted by docs inside the practice tree, and in 63b-1 a directory
  listing of `C:/x/ev_63b6/final/63B_Stage1_v006.fbx` (an older 63B version on this PC). No run opened a key file as far as
  the events show, but by the contract's own rule none of these runs is a clean count; it does not change a 0/6 result.
  Owner: #1859 (key leak) / #1877 (guard) — side finding, not fixed here.
- Candidate defect found by the runs: it named PartsList `status review`; the model allows `draft|confirmed` only and
  6/6 agents wrote `draft`. Text corrected to `status draft` after the series (regression assert in
  `tests/tools/test_trainer.py`); the correction itself is **not measured** (agents already behaved that way).
- Evidence (small text only, no binaries): `G:/Мой диск/AGR-evidence/1855-r81-gate1-practice/` (run.json, last.txt,
  prompt.txt, QUESTIONS.md, parts.json per run, scratch bank, series.sh/log), `SHA256SUMS.txt` SHA-256
  `d0b7ee8e4ec773b946d7fae13cb5a5ab23f8537a3ba73af0f32d5cefa2adb14b`. Full run dirs (worktrees): `C:/x/trainer/runs/63?-stage1-codex-r81-*` (local, replay limited).
- Replay: `bash series.sh` from the evidence folder at this branch's head (needs codex lane, 63B scratch bank above).

Next target (for the next standing card): the new most frequent first stop = **tower/region identity in a
site-wide source** (6/6). Either the etalon task text must name the tower region (bank owner #1855/#1861), or the
skeleton needs a source-identity step (inspect → pick building by labelled plan/coords); and the missing
Revit→BodyPlan adapter on main (63b-1).

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

## Question for Artem (answered 2026-11-25: yes, practice only → [D391])

В тренировочных прогонах (#1855, `agr trainer run`, свежий агент без пользователя) можно ли агенту самому
«подтверждать» Gate 1 (PartsList) и BM-12 (первый модуль): записать PartsList с хешем, отметить его как
`gate1=practice-self` и строить дальше, считая оценку по скрытому ключу заменой вашего подтверждения — только в
тренажёре, без изменения правила для настоящих задач? Рекомендация: да, только в тренажёре.

Replay of the preflight: `git show origin/research/issue-1855-trainer-v0:docs/trainer/ledger.json | sha256sum` and
`sha256sum C:/x/trainer/runs/*/last.txt` (local scratch; replay limited until #1861).
