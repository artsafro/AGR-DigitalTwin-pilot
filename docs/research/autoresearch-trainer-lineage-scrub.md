# Autoresearch #113 — trainer: accepted-lineage folders left in the practice tree (OBSERVE)

**Кратко (RU).** Фокус карточки — шаг, чаще всего проваливающийся в ledger тренажёра. Ledger @7762dcfe:
`artifact` 3/4, `sources-dwg` 1/4. Свежая серия #111: `artifact` первый отказ 7/8 оценённых прогонов, чистых
прохождений 0/9. Рычаги прохождения `artifact` уже заняты: KPP1 — фраза FBX-first (PR #1917, FBX 9/9 в r95/r99),
G22 — адаптер NPZ (PR #1928, FBX 3/3 в r97), 63A — офлайн-маршрут #90-#92 (3/3 офлайн). Единственный FBX на 63A в
#111 (r111-1) **сбежал**: агент прочитал `docs/research/body-training-1619/README.md`, нашёл там папку
`G:/Мой диск/AGR-evidence/1619-body-training/`, открыл принятую линию `tower-A/v005` и скопировал принятый план
`floor_v005.json` (отклонение 0.0). Чистка дерева тренажёра (`scrub_worktree`) прячет только путь, имя и хэш
ключа, а не папку, где лежит принятая линия эталона. Цель #113 — измерить эту «поверхность побега» и проверить
кандидата (токены папок линии в чистке) без изменения продукта.

Status: **contract frozen before any measurement.** Hypothesis result: see "Result".

## Why this target (and what is not taken)

- Ledger `docs/trainer/ledger.json` @ `7762dcfe2e78219155461bb633faaca2015e259b`: 4 rows, `artifact` 3/4.
- Stop census of 59 stored runs in `C:/x/trainer/runs` (grep of `last.txt` + `built/QUESTIONS.md`, observation
  only): FBX present KPP1 C/D arms 9/9 (#1917 sentence), KPP1 baselines 0/13; G22 r97 C 3/3 (#1928 adapter),
  other G22 runs 2/22; 63A/63B 2/14, both FBX runs contaminated (r87-3 per #87, r111-1 above). Finish-zone
  requests (D341/D344) appear also in the G22 runs that built an FBX, so they are not the decisive blocker.
- Owned elsewhere, not touched: #1917 (KPP1 prompt), #1928 (G22 adapter), #1866 (DWG truncation), #1872/#1867
  (scene prepare), #91/#92 route integration (trainer owner), #98/#99 several-FBX scorer rule. Form research
  closed; texture/atlas fallback inactive (ledger rows exist).
- A clean `artifact` pass on 63A needs an escape-free run; without closing the pointer the trainer counts copies
  of the accepted lineage as passes (63A r111-1 scored `artifact` pass, deviation 0.0).

## Frozen contract

**H113.** Adding each etalon's accepted-lineage evidence folders to the scrub tokens removes every practice-tree
file that names those folders (M113 = 0 on all practice-ready etalons), while the current product scrub leaves
M113 > 0 on 63A, and the candidate removes no route-critical file.

**Lineage tokens L(e)** (frozen, lower-cased, matched case-insensitively like `scan_tokens`):
- generic: the folder right after `AGR-evidence/` in the key, every rejected and the calibration path of e
  (63A/G22 -> `1855-trainer-v0`, the bank that holds the keys; KPP1 -> `1609-kpp1-package-v004`);
- declared (would be a bank field `lineage`): `1619-body-training` for `63a-stage1` and `g22-k2-stage1`
  (the #1619 folder holding their accepted versions, `tower-A/v005`, `round4-k2-stage1`); none for `kpp1-v004`.

**M113(e, tree)** = number of files in a practice tree (outside `.git/`) whose bytes contain any token of L(e)
(`trainer.leaking_files`). Reported per token too.

**Arms.** Baseline = unchanged `tools.trainer.trainer.practice_tree` at head `7762dcfe` (product scrub).
Candidate = the same call with `trainer.scan_tokens` replaced in-process by `scan_tokens(e) ∪ L(e)` (harness only;
product file untouched). Every tree is a NEW `git archive` of the pinned head, 3 repetitions per etalon and arm
(median of 3 and min/max; deterministic, spread expected 0).

**Fixtures.** Practice-ready etalons of the committed bank: `63a-stage1` (tuning + trigger witness: the escape
was observed there), held-out `kpp1-v004` and `g22-k2-stage1` (not looked at for the token choice of their
generic part; the declared G22 token is shared with 63A). Stored product trees of the nine #111 runs
(`C:/x/trainer/runs/*-codex-r111-*/wt`, head 7762dcfe) are measured with the baseline metric only (real, not
reconstructed trees; agent-written files included, reported separately).

**Positive trigger witness.** `docs/research/body-training-1619/README.md` (read by the 63A r111-1 agent before the
escape) must be removed by the candidate on 63A and present in the baseline tree.

**Collateral (accepted control where the rule fires).** For each etalon: files the candidate removes beyond the
baseline (`changed` count). Route-critical removed must be 0, route-critical = `AGENTS.md`, `CLAUDE.md`,
`GEMINI.md`, `docs/agents/**`, `routes/**`, `docs/domain/**`, `docs/procedure/**`, `.agents/skills/**`,
`tools/**`, `src/**`, `standards/**`, `schemas/**`. An etalon with changed = 0 is `not_exercised`, reported as
**not measured** for collateral.

**Perturbations (synthetic, in a scratch folder; expected direction).**
- p1 backslash form `G:\Мой диск\AGR-evidence\1619-body-training\tower-A\v005` -> caught by candidate (63A).
- p2 upper case `AGR-EVIDENCE/1619-BODY-TRAINING` -> caught (63A).
- p3 sibling evidence folder `AGR-evidence/1855-r111-ledger-fresh/` -> NOT caught (precision).
- p4 the repo folder name `docs/research/body-training-1619/` without the evidence folder -> NOT caught.
- p5 KPP1 key folder `G:/Мой диск/AGR-evidence/1609-kpp1-package-v004/draft-b25/` -> caught for KPP1 only,
  NOT caught for 63A (token scoping per etalon).

**KEEP / confirm rule.** Hypothesis confirmed iff: candidate M113 = 0 in 3/3 reps on all three etalons; baseline
63A M113 ≥ 1 in 3/3; trigger witness removed 3/3; route-critical removed = 0 on every exercised etalon;
p1, p2, p5(KPP1) caught and p3, p4, p5(63A) not. Refuted if a candidate tree still has M113 > 0, a route-critical
file is removed, or the witness is not removed. Incomplete measurement -> inconclusive. A KEEP here is a
would-change for the trainer owner (bank field `lineage` + scrub tokens), never applied by this card.

**Not measured (stated before running).** Live escape rate of fresh agents with the candidate scrub (the agent can
still list `G:/Мой диск/AGR-evidence/` without a pointer); live `artifact` pass; anything after `artifact`.
Next command for that is recorded in "Result".

**Budget.** One confirmation series, zero new candidates. Time the first (baseline, candidate) pair on 63A; cap the
whole series at 5x the projected 18-tree time and 40 min hard. No shortening the series; a budget stop is
inconclusive.

**Forbidden.** Editing `tools/trainer/trainer.py`, the bank, ledger, delivered packages, Drive evidence or other
cards' files; deselecting tests; changing tokens after the first measurement.

**Replay.** `uv run --frozen python docs/research/trainer_lineage_r113/measure.py --out C:/x/ev_t_70d0913e/r113-NEW`
from this branch (new output dir). Inputs pinned: head `7762dcfe` (git object), bank and `trainer.py` SHA-256
checked against the receipt before measuring; stored #111 trees read-only.

## Result — H113 confirmed for the practice-tree pointer surface (OBSERVE, no product change)

**Кратко (RU).** Гипотеза **подтверждена** для статической поверхности побега. В дереве тренажёра на голове
7762dcfe остаются файлы, называющие папки принятой линии: **63A — 5 файлов, G22 — 11, KPP1 — 0** (3/3 повтора,
разброс 0; те же 5/11/0 в девяти реальных деревьях прогонов #111). С токенами линии в чистке — **0/0/0** в 3/3
повторах; файл, через который сбежал агент 63A r111-1 (`docs/research/body-training-1619/README.md`), удалён 3/3;
файлов маршрута (AGENTS, docs/agents, routes, docs/domain, tools, …) не удалено ни одного. Отложенный G22
задействован (11 изменённых файлов), KPP1 — `not_exercised` (у него таких файлов нет: `jobs/KPP1` уже скрыт).
Что **не измерено**: доля побегов у живых агентов (папка `G:/Мой диск/AGR-evidence/` остаётся доступной для
листинга и без указателя) и прохождение `artifact`. Код продукта, банк и ledger не менялись; PR нет.

Run `C:/x/ev_t_70d0913e/r113-1`, status `finished`, wall 470.7 s (first 63A pair 45.5 s, derived cap 2047.9 s).
Measured harness = committed `404bffa2` bytes (SHA-256 `f0cb9f96…0d26c3`). Inputs pre = post: bank
`016aab0c…36635`, `trainer.py` `16fd8edb…aa4b5`. Tokens actually derived: 63A/G22 `1619-body-training`,
`1855-trainer-v0`; KPP1 `1609-kpp1-package-v004`, `1609-kpp1-lattice-posts` (a rejected version's folder).

| Etalon | role | baseline M113 median [min,max] | candidate M113 | changed (extra removed) | route-critical removed | witness |
|---|---|---:|---:|---:|---:|---|
| 63a-stage1 | tuning + trigger | 5 [5,5] | 0 [0,0] | 5 each rep | 0 | present → removed 3/3 |
| g22-k2-stage1 | held-out | 11 [11,11] | 0 [0,0] | 11 each rep | 0 | — |
| kpp1-v004 | held-out | 0 [0,0] | 0 [0,0] | 0 → `not_exercised` | not measured | — |

- Baseline files, 63A: `docs/research/body-training-1619/README.md`, `docs/research/autoresearch-trainer-gate1.md`
  (names the bank folder `1855-trainer-v0`), `docs/research/autoresearch-trainer-tower-id.md`,
  `docs/research/autoresearch-body-mesh-quality-harness/{calibrate.py,r0.json}`. G22 adds
  `docs/research/body-mesh-method.md` and six `jobs/POLY63-*` files (not hidden for G22).
- Parity: stored product trees of #111 (`C:/x/trainer/runs/*-codex-r111-*/wt`) give the same M113 as the fresh
  baseline: 63A 5/5/5, G22 11/11/11, KPP1 0/0/0 — the baseline arm reproduces the real practice scrub.
- Perturbations (synthetic, all as expected): p1 backslash caught, p2 upper case caught, p3 sibling evidence
  folder not caught, p4 repo folder name not caught, p5 KPP1 key folder caught for KPP1 and not for 63A.
  Product scrub caught none of p1-p5.
- Clean / injected / not measured: clean = the 3x3 fresh trees + 9 stored trees; injected = p1-p5 only;
  not measured = KPP1 collateral, live escape rate, live `artifact` passage, any step after `artifact`.

**Hypothesis result: confirmed** (static pointer surface only). **Would-change** (for the trainer owner, normal PR +
review): a bank field `lineage` (accepted-lineage evidence folders per etalon) plus generic key/rejected evidence
top folders added to `scan_tokens`; then the live check below. Replay limited to hosts with the stored #111 trees
for the parity line; the 3x3 fresh series needs only this repo at `7762dcfe`.

Next command (live check, not run here; ~2M input tokens and 2-5 min per run): build a scratch bank whose
`63a-stage1.hidden_repo_paths` adds the five 63A files above, then three fresh runs
`uv run agr trainer --bank <scratch bank> run 63a-stage1 --lane codex --out C:/x/trainer/runs/63a-stage1-codex-r113-L<k>`
and count escape commands to `AGR-evidence/1619-body-training` (r111 baseline: 1/3 escaped).

Affected tests: none changed (harness + docs only); `tests/tools/test_trainer.py` run as a regression guard.

Full suite: deferred to merge batch (rule 68).
