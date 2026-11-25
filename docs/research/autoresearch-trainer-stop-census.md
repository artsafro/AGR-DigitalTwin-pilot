# Autoresearch #85: trainer stop census (OBSERVE)

Card t_9aa9bbc1, branch `research/autoresearch-standing-85`, base `origin/main@86852f3789f5c9f747db21314dddebe350986129`.

## Русское резюме

(заполняется после замера, см. «Round log» и «Result»)

## Why this target

Focus override (#1855 trainer): pick the most frequent first failing step. Ledger on main: 3/3 `artifact`
(KPP1 v004, G22 K2, 63A); PR #1875 adds a 2nd `sources-dwg` row (owned by #1874 / PR #1880).
`artifact` = "no FBX", which #81 traced to the Gate 1 stop; passing it needs Artem's decision on #81
(practice self-confirmation of Gate 1/BM-12, still blocked). #82-#84 measured the Gate 1 *handoff*.
Both #80 and #81 listed as a next target "record the actual stop reason separately from `artifact`", nobody did.
The ledger only says `artifact`, so the focus rule reads one undifferentiated bucket. This card measures whether the
stop reasons can be recovered automatically from the run folder, with no LLM and no new practice runs.

Skipped (owners): Gate 1 self-confirmation (#81, Artem), DWG stall (#1874/PR #1880), bank durability (#1861),
trainer launch guard (#1877), form (closed), texture fallback (superseded by the ledger).

## Contract (frozen before any classifier code)

- **Labels:** `docs/research/trainer-stop-census-r85/labels.json`, 7 binary labels per run
  (`fbx, gate1, bm12, finish_src, geo_src, geom_src, open_scene`), hand-read from `built/QUESTIONS.md`,
  committed before `census.py` existed (see git history). `null` = unreadable text, not measured.
- **Fixture:** all 17 run folders in `C:/x/trainer/runs` (exit 0 everywhere, no FBX anywhere).
  Tuning = KPP1 v004 (7 runs). Held-out = G22 K2 (9) + 63A (1), never looked at while writing the rules.
  Per-input SHA-256 of `QUESTIONS.md` and `run.json` pinned in `labels.json`; `census.py` refuses to score
  on any hash mismatch (full-manifest preflight).
- **Metric M85:** held-out micro-F1 over all measured (run, label) cells; second number: `gate1` held-out exact
  agreement. Baseline = what the ledger records today (`artifact` only, every other label 0) -> positives found 0.
- **Keep (H85 confirmed):** held-out micro-F1 >= 0.90 AND `gate1` held-out 9/10 or better AND every perturbation
  moves in the expected direction. Otherwise refuted (rules do not transfer) or inconclusive (preflight/fixture gaps).
- **Repeats:** the census is deterministic; 3 fresh runs must give identical output (stability = identical
  JSON hash), wall time reported per run.
- **Perturbations (scratch copies under `$TMPDIR`, originals untouched), expected direction:**
  P1 add `built/x.fbx` -> `fbx` 0->1, others unchanged; P2 delete `QUESTIONS.md` -> all question labels 0 and
  `handoff=missing`; P3 `run.json` exit `timeout` -> `exit_stop=timeout`; P4 replace the Gate 1 request by
  "Gate 1 approved" statement -> `gate1` 1->0 (positive trigger witness = kpp1 r83-C1, an accepted-control
  equivalent = held-out g22 r83-B2 where `gate1` must NOT fire).
- **Stop rule:** max 3 rule-revision rounds, tuning-only; held-out scored once per round and never used to edit.
  Budget: 60 min of card time.
- **Forbidden:** editing run folders, labels after the freeze commit, `tools/trainer/trainer.py`, ledger.json,
  other cards' branches; LLM judging; tuning on held-out.
- **OBSERVE:** the proposed ledger field (`stop_census`) is recorded as a would-change; no production change.

## Replay

`uv run --frozen python docs/research/trainer-stop-census-r85/census.py --labels docs/research/trainer-stop-census-r85/labels.json --out <NEW>.json`
(replay limited: run folders live only on this PC in `C:/x/trainer/runs`; hashes pinned.)

## Round log

(filled after measuring)
