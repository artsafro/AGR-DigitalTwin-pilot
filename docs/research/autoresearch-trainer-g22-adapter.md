# Autoresearch #97: trainer G22 artifact with the Revit NPZ adapter visible (OBSERVE)

**Кратко (RU).** В ledger тренажёра (#1855, `docs/trainer/ledger.json` на main `e01aafc9`) чаще всего первым
проваливается шаг `artifact`: 3 из 4 строк (KPP1, G22, 63A). KPP1 уже разбирали #95/#96, 63A/63B — #87–#92. Остаётся
G22: в #95 агент 3/3 не нашёл адаптер NPZ→BodyPlan. SKELETONS (строка 3) называет его `floor_from_dump.py`, но файл
лежит в скрытых hooks `jobs/garibaldi22`. Единственный FBX по G22 (r95-C3) агент получил, выйдя из практики в
основной checkout, поэтому прогон не засчитан. Гипотеза H97: если перенести адаптер (и его импорт `module_build.py`) в
`tools/methods/body/` и указать в SKELETONS путь, то засчитанный `artifact` на G22 вырастет с 0/3 до ≥ 2/3, без
выходов из практики. Режим OBSERVE: перенос проверяется только в scratch-клоне, в main ничего не меняется.

Status: contract FROZEN before any measurement (this commit). Result section is appended after the series.

## Target selection (step 1)

- Ledger rows, main `e01aafc9`: first_failing_step `artifact` ×3 (kpp1-v004, g22-k2-stage1, 63a-stage1), `sources-dwg`
  ×1 (kpp1-v004 r2). The most frequent first failing step is `artifact`.
- Owned elsewhere, not repeated: KPP1 artifact/bounds (#95 PR #1917, #96), 63A/63B Revit route (#87–#92), escape audit
  (#93/#94), Blender guard (#1877), trainer A/B harness (#1924/PR #1927), DWG intake (#1880 merged), tower identity
  (#1901 merged). The atlas fallback is inactive because ledger rows exist. Form research is closed.
- Taken: backlog #95 next target 2, "expose the NPZ->BodyPlan adapter to the practice tree; measure G22 artifact rate".
  No open issue or PR names `floor_from_dump` (searched 2026-11-25).

## Positive trigger witness (frozen, pre-existing evidence)

`C:/x/trainer/runs/g22-k2-stage1-codex-r95-C3/events.jsonl`: the agent runs `rg 'floor_from_dump' tools/methods/body
docs/agents/SKELETONS.md`, then `Get-Content tools/methods/body/floor_from_dump.py`, which fails because the file is
absent. It then searches with `rg --files -uu`, reads the hidden copy in the MAIN checkout
`C:/Users/artsafro/agr-pilot/AGR-DigitalTwin/jobs/garibaldi22/body-training-1619/hooks/floor_from_dump.py` and runs it
on the input NPZ with `--openings`. That gives an FBX, which is not counted (E93 escape plus a refusal on several FBX).
r95 G22: B 0/3 and C 0/3 counted (`docs/research/trainer-artifact-first-r95/receipt.json` on
research/autoresearch-standing-95).

## Metric, arms, fixture

- **Fixture:** `g22-k2-stage1` only. Source NPZ sha256 `5eee4ac6911acb6c79e4d9d9871136d2eeb482fb5f8848f11ca179b397fc4622`
  (Drive bank). The key is read only by the scorer. The candidate is not tuned on any output: it is a file move of
  existing accepted code plus a path fix. G22 was never used for tuning (it was the held-out fixture in #95).
- **Arm B (baseline):** practice root `git clone --shared` of base `e01aafc9c3ad31ad924d230a5d2ed92445ee13a7`, with
  origin/main set to base.
- **Arm C (candidate):** the same base plus one commit, tree `55b2ae49a75f3ec76bc38e91cb3cd40f68ff7adc` (built 3 times,
  identical). The commit:
  - adds `tools/methods/body/floor_from_dump.py` (sha256 `c2eb4f85…2fbd1`), a byte copy of the G22 hook;
  - adds `tools/methods/body/module_build.py` (sha256 `e15f6c77…e5485`), the hook plus 2 path lines for the new depth;
  - changes `docs/agents/SKELETONS.md` row 3 from "Revit `floor_from_dump.py`" to
    "Revit NPZ crop `tools/methods/body/floor_from_dump.py`".

  Rebuild with `make_candidate.py`, which checks CAND_TREE. The task text, bank, scorer and timeout are identical in
  both arms. Hidden paths are the same (`jobs/garibaldi22` and `jobs/G22` stay hidden in both arms).
- **Runs:** 3 per arm, as pairs (B_i ‖ C_i) started together, `--timeout-s 1800`, lane codex (`gpt-6.1-terra`, the
  trainer default). Driver: `series.py`.
- **Scorer:** the unchanged base `tools/trainer/trainer.py score`, used for BOTH arms. A scorer refusal (for example
  several FBX) or no FBX counts as an `artifact` fail.
- **M97 (primary) = counted artifact passes per arm (0–3):** the score artifact step is `pass` AND the E93 audit counts
  0 escapes. The audit is `research/autoresearch-standing-93:docs/research/trainer-escape-r93/audit.py`, sha256
  `e78e4927…6ec3`.
- **H97:** CONFIRMED if C ≥ 2/3 and C > B; REFUTED if C ≤ B; otherwise inconclusive. A series with fewer than 3+3
  scored runs is inconclusive for this run, whatever the counts.
- **Secondary (reported, not decisive):**
  - FBX in built/ (any);
  - adapter runs (and runs via the promoted path);
  - first failing step after artifact (bounds/topology/form), score;
  - wall time, input tokens, escapes per arm.
- **Expected direction:** C up. Bounds: B 0–1/3 (r95 B 0/3); C ≥ 2/3 needed for KEEP-as-proposal.

## Controls, invariance, not measured

- **Invariance (practice tree):** C differs from B by exactly 2 added + 1 changed tracked files. This is checked with
  `git diff --stat` in the C root (recorded) and by the scrubbed-file counts per run in run.json (they must be equal in
  both arms).
- **Negative/representative:** arm B is the representative negative (adapter absent). No synthetic NPZ perturbation was
  run (**not measured**).
- **Accepted control where the rule fires:** in an offline, agent-free route, run the promoted adapter from the C root
  on the G22 NPZ (`floor_from_dump.py NPZ PLAN.json --openings`). Record its exit code and whether PLAN.json validates
  against `schemas/BodyPlan.schema.json`. This is informational: it shows the mechanism exists and is not counted in
  M97.
- **Not measured:**
  - collateral on other etalons whose practice trees would also contain the files (63A/63B: #88 showed that adapter
    visibility alone fails there; KPP1 is DWG);
  - package and quality steps;
  - fresh-agent isolation beyond the E93 audit (#1859).

## Forbidden shortcuts

- No edits to the git bank, `docs/trainer/*`, the scorer or `trainer.py`.
- No task-text hints.
- No rerun of a failed run, no changed arguments between pairs.
- No counting of escaped runs.
- No edits to delivered packages or other cards' files.
- No promotion in this branch: the candidate exists only in the scratch roots. A real move is a separate PR for the
  #1855 owner.

## Budget and stop rule

- One measured pair from #95 (G22 103–374 s wall per run, ≤ 2.75 M input tokens). The core budget is 3 pairs, with no
  new candidate (confirm budget = all 6 runs on one candidate).
- Stop rule: no new pair starts after 150 min from the series start. Unstarted runs are `not_run` and H97 is reported
  as inconclusive with the exact `series.py --only` command for the rest.
- Wall time and run status are recorded separately (series.log, run.json).

## Replay

```
uv run --frozen python docs/research/trainer-g22-adapter-r97/make_candidate.py C:/Users/artsafro/agr-pilot/AGR-DigitalTwin C:/x/r97s
uv run --frozen python docs/research/trainer-g22-adapter-r97/series.py C:/x/r97s
git show origin/research/autoresearch-standing-93:docs/research/trainer-escape-r93/audit.py > AUDIT.py
uv run --frozen python docs/research/trainer-g22-adapter-r97/analyze.py AUDIT.py NEW_receipt.json
```

Replay is limited: the run folders `C:/x/trainer/runs/g22-k2-stage1-codex-r97-*` are local. Evidence hashes go to
`G:/Мой диск/AGR-evidence/1855-r97-g22-adapter/SHA256SUMS.txt`. Fresh-agent runs are not deterministic: a replay
re-measures the series, it does not rescore a dump.

## Result (series 2026-11-25 20:24–20:33, 6/6 runs, no budget stop)

**Итог (RU).** Гипотеза H97 — **inconclusive**: в зачёт C 1/3 против B 0/3. Порог ≥ 2/3 не пройден, но C > B, так
что гипотеза не опровергнута. Сам механизм работает:
- с адаптером в `tools/methods/body` все 3/3 прогона C запустили его по новому пути, ни разу не выйдя из практики, и
  каждый собрал типовое тело;
- в B адаптера нет. Два прогона закончились без FBX. Третий (B1) собрал FBX, но только прочитав скрытые hooks в чужом
  worktree (8 выходов по E93), поэтому не засчитан.

Две из трёх побед C потеряны так же, как в #95: агент оставил в `built/` второй FBX (одноэтажный модуль или пилот), и
оценщик отказывается выбирать («several FBX»). Отдельно оценённые (не в зачёт) типовые тела C1/C3 проходят artifact,
bounds, topology и form (p95 1,3–1,4 см) и останавливаются на `form_v2` (4 из 29 проверок), как и засчитанный C2.
Следующий шаг после artifact на G22 — `form_v2`.

| Arm | n | FBX in built/ | artifact pass (scorer) | **M97 counted** | E93 escapes | adapter run (promoted path) | first_failing_step |
|---|---|---|---|---|---|---|---|
| B (base e01aafc9) | 3 | 1/3 | 1/3 | **0/3** | 1/3 (B1: 8 paths, hidden hooks in another worktree) | 0/3 | form_v2 (B1, escaped), artifact ×2 |
| C (+ promoted adapter, tree 55b2ae49) | 3 | 3/3 | 1/3 | **1/3** | 0/3 | 3/3 (3/3) | form_v2 (C2), scorer refusal ×2 (C1, C3) |

- **Contract check.** C ≥ 2/3 is false, so the hypothesis is not CONFIRMED. C ≤ B is false (1 > 0), so it is not
  REFUTED. Result: **inconclusive**.
- **Clean / injected / not measured.**
  - Clean: 6 fresh-agent runs, all exit 0. Wall 87–168 s, input tokens 0.48–1.62 M (per run in `receipt.json`).
  - Injected: none.
  - Not measured: synthetic NPZ perturbation, collateral on 63A/63B/KPP1 trees, package/quality steps, isolation
    beyond E93.
- **Invariance.**
  - The C tree differs from B by 2 added + 1 changed files: `git diff --stat` 3 files, +1276/−1.
  - Scrubbed files: 10 per run in all 6 runs, so the scrub behaves the same in both arms.
  - Both arms were scored by the same base scorer.
- **Positive trigger witness reproduced.** B2/B3 end without FBX. B1 reaches the hidden hook outside its run.
- **Offline accepted control (agent-free, informational).** From the C root:
  - `floor_from_dump.py NPZ plan.json --openings` exits 0 and the BodyPlan has 0 schema errors;
  - `agr body` writes one body FBX (9 floors, 45 openings, 4887 faces, 0 tris);
  - the score gives artifact/bounds/topology pass, form fail p95 6.29 m (default arguments; the agents chose a
    different floor setup and got p95 1.3 cm). This shows the mechanism, not the metric.
- **Informational, not counted** (`informational.json`), explicit `--built FILE` scores:

  | Run | FBX | first_failing_step | form p95 |
  |---|---|---|---|
  | C1 | typical | form_v2 | 0.0128 m |
  | C1 | module | bounds | 22.75 m |
  | C3 | typical | form_v2 | 0.0139 m |
  | C3 | pilot | bounds | 22.75 m |

Receipt: `docs/research/trainer-g22-adapter-r97/receipt.json` (Git LF SHA-256
`a178ddb88973ae20eaa06889662f9a4c9dc38211d55ae5559a6e367024042392`), `informational.json` (Git LF SHA-256
`7b3217dc4e1c2ccc9b32b3f926a88ffd9f5faffc32c9ebadc0a560d7c458f348`), `series.log`. Evidence (run.json, score.json,
events, built FBX, offline control): `G:/Мой диск/AGR-evidence/1855-r97-g22-adapter/SHA256SUMS.txt` (sha256
`847aeb38d84d59a3acef620d986c1a76b8b5f54d5bd1dddbddff9dc856a70cc5`, 112 files). Replay is limited: the run folders
are local.

**Kept changes:** none (OBSERVE). Proposals for the #1855 owner, not applied:
1. Promote `floor_from_dump.py` + `module_build.py` from the G22 hooks to `tools/methods/body/`, and give the path in
   SKELETONS row 3. This is the measured candidate (make_candidate.py, 2 path lines). It removed the G22 escape and made
   an FBX in 3/3 runs. A real move needs its own PR with tests (the hooks have callers in jobs/garibaldi22).
2. One-deliverable rule (same as #95 proposal 1): the scorer or task names a single deliverable path. On G22 it would
   have counted C1/C3. This is now the shared blocker of KPP1 (#95) and G22 (#97).
