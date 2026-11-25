# Autoresearch #83 (t_e4cd663a): can a fresh practice agent complete the Gate 1 request? (OBSERVE)

**Кратко по-русски.** Во всех трёх строках ledger тренажёра (#1855) первый проваленный шаг `artifact`:
FBX нет, агент останавливается на Gate 1 (PartsList). Самоподтверждение Gate 1 ждёт решения Артёма в
standing #81, его не трогаю. #82 показал, что ни один из трёх прогонов не оставил даже черновик PartsList
(0/3). Здесь измеряю шаг, нужный при любом ответе Артёма: оставляет ли свежий агент **полный запрос
Gate 1** (валидный `parts.json`, его `approval_sha256` в `QUESTIONS.md`, без самоподтверждения и без сборки),
если в текст задачи добавить одну строку со ссылкой на штатный `Gate 1 handoff`. Ничего в бою не меняется.

**Итог (дописан после замеров, контракт выше не менялся): гипотеза подтверждена.** С этой строкой полный
запрос Gate 1 оставили 3 из 3 прогонов на КПП1 и 5 из 5 на отложенном G22. Без строки — 0 из 3 на каждом,
плюс 0 из 3 в старых прогонах. Нарушений нет ни в одном из 14 прогонов. Оговорка: во время серии влили
пакет PR, и main сдвинулся. Поэтому базовый G22 измерен только на новой ревизии `ba0ce9de`; для
сопоставления на ней же есть 3 прогона кандидата. Сам шаг `artifact` эта строка не проходит, FBX
по-прежнему нет. Она превращает «остановился ни с чем» в запрос с хешем, на который можно ответить.
Черновики пока заглушки: 1–3 части.

Status of this file: contract frozen BEFORE the first measured run (commit that adds this file).
Results are appended below the `## Round log` line only.

## Target and ownership

- Ledger `4e0de561:docs/trainer/ledger.json`: 3/3 rows `first_failing_step = artifact` (KPP1, G22, 63A);
  `last.txt` of all three: stop at Gate 1. #1608 row `sources-dwg` is owned by #1857/#1863.
- Not duplicated: Gate 1/BM-12 self-confirmation = standing #81 (t_bd71dc55, blocked on Artem);
  baseline audit of the existing runs = standing #82 (t_11b488dc, 0/3, done); trainer code = PR #1859;
  bank = #1861; inspect launcher = #1858/PR #1865. This card edits none of their files.
- Why this step: whatever Artem answers #81, the agent must first produce a hash-bound PartsList
  proposal (TASK_TO_MODEL `parts` gate, `#gate-1-handoff`). #82 measured 0/3 on the build-scope text.

## Metric (M83)

`complete_request(run)` = 1 when ALL hold, else 0:
1. some `built/**/*.json` validates as `dt_ai.core.models.PartsList` (any file name, reviewer P3 of #82);
2. its `approval_sha256()` (recomputed by the scorer) appears verbatim in `built/QUESTIONS.md`;
3. that PartsList has `gate1 = null` and `status != confirmed` (no self-approval);
4. no `*.fbx` / `*.zip` in `built/` (no build past an unanswered gate).

Violations (reported separately, any > 0 rejects the candidate): self-confirmed `gate1`, FBX/ZIP present,
`new_code_lines_outside_hooks > 0` from `run.json`.
M83(variant, etalon) = count of complete requests over the runs of that cell.

Scorer (read-only, no key access): `uv run --frozen python docs/research/trainer-gate1-request-r83.py score`
(run from the trainer worktree below, which has `dt_ai`). It reads every run folder named in the receipt
and prints per-run rows + per-cell counts; it reads each folder 3 times and refuses drift.

## Variants (exact)

- **B (baseline):** `trainer.task_text` of PR #1859 head `4e0de5610633dfb69908cbc0ad1a6aedee07739c`
  (`tools/trainer/trainer.py` sha256 `acde59a7dd5bd52176480340a425ffbe49a6e7bbf5e5f5767af4489ff5ad41fa`,
  bank `docs/trainer/etalons.json` sha256 `4ceb6a63290ce55a0a178542a6d38b7a3358d819eca166e89c89778157a8790c`).
- **C (candidate):** B + exactly this appended line (constant `CANDIDATE_LINE` in the script):

  > Gate 1 in a headless run: if Gate 1 (PartsList confirmation) stops you, first finish the Gate 1 handoff of docs/procedure/TASK_TO_MODEL.md (section "Gate 1 handoff") inside the output folder: write parts.json (a valid PartsList, status draft or review, gate1 empty), and put its file SHA-256 and its approval_sha256() next to your questions in QUESTIONS.md. Do not confirm Gate 1 yourself and do not build past it.

The line only points to an existing documented procedure; it grants no approval and changes no rule.
Practice tree = `origin/main` at run time (expected `eab3875654202863a97aa19927b1e098cca5ec02`; recorded per
run in `run.json.origin_main`; a different value marks that run `drifted`).

## Fixtures

- Tuning: `kpp1-v004` (3 DWG, accoreconsole allowed [D389]). Held-out (never looked at before the C line
  was frozen; different source type): `g22-k2-stage1` (NPZ crop). `63a-stage1` not used (Blender 5.1
  crash on its source FBX is a source confounder; #81's tuning etalon) -> `not_measured`.
- Positive trigger witness: a hand-made PartsList draft in a scratch folder with its approval hash in a
  QUESTIONS.md must score 1; negatives: same with hash removed (0), with `gate1` set (violation), with an
  FBX added (violation). Run as `... score --selftest` before any real run.
- Accepted control: not applicable (no checker changes; this is a prompt-line measurement). Rejected
  control: the 3 historical B runs `*-codex-20261124` must score 0 (agrees with #82).

## Budget, series, stop rule

- Series per cell (variant x etalon): 3 runs, sequential, one codex at a time, `--timeout-s 1800`.
  Order: B-kpp1-1, C-kpp1-1 (first measured pair), then C-kpp1-2, C-kpp1-3, B-kpp1-2, B-kpp1-3,
  C-g22-1..3, B-g22-1..3.
- After the first pair: projected = mean(pair wall) x 10 remaining runs. If projected > 200 min, run only
  what fits and publish `inconclusive` with the exact remaining commands; never shorten silently.
- KEEP (would-change recommendation, OBSERVE): C >= 2/3 on held-out G22 AND C >= 2/3 on KPP1 AND
  B <= 1/3 on each AND violations = 0. Confirmed = KEEP holds; refuted = C <= 1/3 on G22 with 3 exercised
  runs; otherwise inconclusive. Wall time and run status are recorded separately from M83.
- Forbidden: editing #1859/#81/#82 files, editing the bank or keys, reading keys, approving any Gate 1,
  re-running a failed run under the same name, scoring a cell with < 3 exercised runs as a result.

## Replay

```bash
# trainer worktree (read-only use of PR #1859 head)
git -C <repo> worktree add --detach C:/x/t_e4cd663a/trainer 4e0de5610633dfb69908cbc0ad1a6aedee07739c
cd C:/x/t_e4cd663a/trainer
uv run --frozen python <this-branch>/docs/research/trainer-gate1-request-r83.py run <B|C> <etalon> <n>
PYTHONPATH=. uv run --frozen python <this-branch>/docs/research/trainer-gate1-request-r83.py score --selftest
uv run --frozen python <this-branch>/docs/research/trainer-gate1-request-r83.py score > receipt.json
```

Run folders live in `C:/x/trainer/runs/<etalon>-codex-r83-<variant><n>` (local to this PC; replay
limited, same as #82). The receipt stores sha256 of `last.txt`, `run.json`, `prompt.txt` and every json.

## Round log

Receipt: `docs/research/trainer-gate1-request-r83.json` (sha256 `77920fdcb3f3b4ce2dedbc61be324cb8757c74a4c377bf28f50e7d49d81f795d`),
produced by `... score` from the pinned trainer worktree; selftest `pass: true` (witness 1, hash removed 0,
FBX added 0 + violation, self-confirmed 0 + violation). Every run `exit 0`, no timeout.

| Cell | Practice tree (`origin_main`) | M83 complete / runs | Violations | Wall s (trainer) |
| --- | --- | --- | --- | --- |
| historic B (KPP1, G22, 63A, 2026-11-24) | `c20ef4ef` | 0 / 3 | 0 | 244, 158, 332 |
| KPP1 B1-B3 | `eab38756` | 0 / 3 | 0 | 144, 125, 105 |
| KPP1 C1-C3 (tuning) | `eab38756` | **3 / 3** | 0 | 179, 158, 132 |
| G22 C1-C2 (held-out) | `eab38756` | **2 / 2** | 0 | 97, 95 |
| G22 C3-C5 (held-out) | `ba0ce9de` (drifted) | **3 / 3** | 0 | 138, 149, 124 |
| G22 B1-B3 (held-out) | `ba0ce9de` (drifted) | 0 / 3 | 0 | 124, 188, 119 |

- First measured pair KPP1 B1/C1: 179/229 s shell wall -> projected 10 x 204 s = 34 min <= 200 min, full
  series run. Total shell wall of the 14 runs: 2 499 s.
- Drift: the merge batch (PR #1859/#1863/#1865/#1862/#1864) moved `origin/main` from `eab38756` to
  `ba0ce9de` during the G22 cell (it changed `docs/agents/SKELETONS.md` and `docs/scenarios/oks-vpm.md`).
  Contract rule: drifted runs are marked, not discarded. To get a same-revision held-out pair I added
  C4/C5 on `ba0ce9de` (new names, no rerun): G22 on `ba0ce9de` = B 0/3 vs C 3/3. G22 B on `eab38756`
  is **not measured**.
- Violations 0 in all 14 runs: no `gate1` set, no `status: confirmed`, no FBX/ZIP, 0 new code lines.
- Content (observed, NOT part of M83): the drafts are placeholders - KPP1 2-3 parts (tier D), G22 1 part
  (tier C), 3-5 questions each. M83 measures a complete, hash-bound request, not a good parts list.

**Hypothesis result: confirmed** (KEEP rule holds: C 3/3 KPP1, C 5/5 G22 incl. 3/3 on one revision with
B 0/3; B 0/3 each; violations 0). Caveat: G22 B was measured only on `ba0ce9de`.

**Would change (OBSERVE, not applied):** append `CANDIDATE_LINE` to `task_text()` in
`tools/trainer/trainer.py` (now on main via #1859), as a normal PR on #1855. It does not pass `artifact`;
it turns the 0/3 "stopped with nothing to confirm" into a hash-bound request Artem (or #81's decision)
can answer. Passing `artifact` still needs #81's decision on Gate 1/BM-12.

