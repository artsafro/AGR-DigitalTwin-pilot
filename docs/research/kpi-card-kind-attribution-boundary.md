# Worker KPI: how much orchestration work is counted as issue implementation?

Card t_c5e60274 (research, no GitHub issue). Read-only study. Nothing was edited, no collector was run, no KPI
output was rewritten. All commands were read-only: `sha256sum`, SQLite `mode=ro`, and a pure Python replay of
`kind_of` on frozen dictionaries (scratch: `C:/x/t_c5e60274/replay.py`, `an.py`, `rows.json`; not committed).
"Verified" below means I read the code or ran the replay myself; no outside web source was used.

## Summary

- **Deployed and tracked `agr_kpi.py` are byte-identical** (sha256 `daa1286999fe61c9...`). The discrepancy is not
  a deployed/tracked drift.
- **In the frozen snapshot, 340 of 514 rows have kind `issue`.** By title prefix (whole snapshot, snapshot
  `issue` rows only): `#N` = 207 rows, `Plan:` 51, `Hypotheses:` 26, `Triage:` 13, `Adopt:` 14, other titles 29
  (of those, 18 `Hypothesis:`, 5 `Prompt:`). So about 104 of 340 `issue` rows (31 %) carry an orchestration
  or adoption prefix. Unmatched rows are not subtracted from anything.
- **Largest effect is per implementer:** Codex `issue` = 94 rows / 6171.6 min, of which `Plan:` = 50 rows /
  172.5 min and `Adopt:` 1 / 110.2. Cursor `issue` = 81 rows / 5305.5 min, of which `Triage:` 13 / 28.4,
  `Hypothesis:` 6 / 70.4, `Adopt:` 3 / 135.4. In rows the orchestration share is large; in minutes it is small
  (Codex `Plan:` 172.5 of 6171.6 min = 2.8 %; Cursor `Triage:` 28.4 of 5305.5 = 0.5 %; `Adopt:` is larger: 135.4 min =
  2.6 % for Cursor), so row-based and minutes-based
  "issue" KPIs tell different stories.
- **Second, larger and separate finding (verified in code):** the key-based half of race detection in `kind_of`
  can never fire in production. `hermes kanban list --json` does not emit `idempotency_key`
  (`hermes_cli/kanban_output.py:16-22`, `_TASK_DICT_FIELDS`), and the collector feeds `kind_of` the `list`
  dict. A replay of the same `kind_of` on the same cards **with** the key from the DB gives 182 snapshot rows
  a different kind (180 `issue` -> `race`, 2 `harness` -> `race`): 182 of the 514 rows. That rule is also
  over-broad: 176 ordinary `gh-<N>-pilot` cards would be called races (`gh-<N>` has one dash and does not
  match), because `key.count("-") >= 2` also matches `gh-69-pilot`. So the missing field
  currently hides a rule that would be wrong if it were switched on. Do not "fix" it by exposing the field.
- **Changing labels alone cannot change per-implementer cards / first-pass / rounds / minutes totals** (replay:
  identical, and they match `kpi.json` `totals`). It does change the `implementer|kind` split and the `By card
  kind` table in `scoreboard.md`.
- Taxonomy and denominator choices (is `Adopt:` implementation? are Plan/Triage "cards worked"?) are the user's;
  listed under Open questions.

## Findings

### F1. Frozen inputs (verified)

| Input | sha256 | Note |
|---|---|---|
| `hermes_kanban/scripts/agr_kpi.py` | `daa1286999fe61c99dd449bced0ccb978d1742dca32800b9c502958ffcf83d30` | tracked |
| `.hermes/scripts/agr_kpi.py` | `daa1286999fe61c99dd449bced0ccb978d1742dca32800b9c502958ffcf83d30` | deployed, same as tracked |
| `hermes_kanban/kpi/kpi.json` | `8fa447b0e6afeffde7735a4657e37aeb9bf189bee1be9bd539f47c93fec6d72a` | `generated` = `2026-10-24 11:08`, board `agr-pilot`, 514 card rows |
| `hermes_kanban/kpi/evaluations/2026-10-24.md` | `14ce72d9183ce2dec6c01e6ed4334593b08a5d773b7268fc4e13a0ce63fbdd03` | window 23.10 07:07 -> 24.10 07:02, 67 rows |

Timing caveat: the evaluation says it used `kpi.json` "from 06:33"; the file I froze says 11:08, i.e. it was
regenerated after the evaluation was written. Group numbers below are for the 11:08 file, so they are not
guaranteed identical to what the evaluator saw. The evaluator also states that the collector failed five times
in a row with the delegated-context CLI refusal (already documented elsewhere, out of scope here) and used the
older file plus the board DB.

Board: `C:/Users/artsafro/.hermes/kanban/boards/agr-pilot/kanban.db` (583 `tasks`, 1647 `task_runs`), read in
one `BEGIN ... COMMIT` transaction with `file:...?mode=ro` at `2026-10-24 12:22:09` local. (The root
`.hermes/kanban.db` has 0 tasks: wrong file.) Comparison with the snapshot:

- All 514 snapshot ids are present; `title[:90]` identical for all; no status changed since the snapshot.
- 534 cards have a non-reviewer run now: **20 new rows** after 11:08 (11 `race`, 7 `issue`, 1 `improve`, 1
  `research` under the DB-based replay). They are not counted in the tables below.
- `kind` stored in the snapshot differs from a replay on DB data in 182 rows (F3). The snapshot rows do not store
  `idempotency_key`, so the replay needs the DB.

### F2. Candidate title-prefix groups (report-only labels)

Snapshot rows with stored `kind == "issue"`. Rows and implementation minutes (the snapshot's `minutes`, i.e. all
non-reviewer runs). Candidate label: `plan`, `hypotheses`, `readiness`, `triage`, `adopt` by explicit
`Prefix:` title; `issue` only if the title starts with `#<digits>`; every other title -> `unlabeled` (titled
but not matching; shown below as "unknown" in my raw output). Missing/empty title -> `unknown`; **no row in the
board has an empty title**, so that branch is untested on real data. `Readiness:` matches **0** card titles on
the board (the evaluator's 6 readiness reports are not stored under such a title); the label is listed only
because the card asks for it.

Whole snapshot (not subtracted from each other; groups are disjoint by construction, so they sum to the
implementer's `issue` row):

| implementer | `#N` issue | Plan | Hypotheses | Triage | Adopt | unlabeled | `issue` row total |
|---|---|---|---|---|---|---|---|
| dt-worker-codex | 43 / 5888.9 | 50 / 172.5 | - | - | 1 / 110.2 | - | 94 / 6171.6 |
| dt-worker-cursor | 59 / 5071.3 | - | - | 13 / 28.4 | 3 / 135.4 | 6 / 70.4 | 81 / 5305.5 |
| dt-worker (Claude) | 53 / 4090.6 | 1 / 1.6 | - | - | 2 / 83.3 | 2 / 7.0 | 58 / 4182.5 |
| dt-worker-agy | 23 / 684.1 | - | - | - | 7 / 289.1 | 2 / 74.6 | 32 / 1047.8 |
| dt-worker-pi | 13 / 597.6 | - | - | - | 1 / 66.5 | 8 / 410.3 | 22 / 1074.4 |
| dt-worker-deepseek | 16 / 977.6 | - | - | - | - | 2 / 103.0 | 18 / 1080.6 |
| dt-hypothesizer | - | - | 26 / 74.1 | - | - | - | 26 / 74.1 |
| dt-prompt-engineer | - | - | - | - | - | 5 / 36.3 | 5 / 36.3 |
| dt-experimenter(-cursor) | - | - | - | - | - | 4 / 49.1 | 4 / 49.1 |

(cells = rows / minutes; "unlabeled" is mostly `Hypothesis:` singular, 18 rows, and `Prompt:`, 5 rows; the
`Hypothesis:`/`Prompt:` naming is a separate candidate group, I did not decide whether it is orchestration.)

Evaluation window (23.10 07:07 -> 24.10 07:02 local, selecting snapshot rows whose first implementer run
started in the window): 72 rows in the window, of which 41 are stored `issue`. By group:

| implementer | `#N` issue | Plan | Hypotheses | Triage | Adopt | unlabeled |
|---|---|---|---|---|---|---|
| dt-worker-codex | 1 / 68.7 | 25 / 66.7 | - | - | - | - |
| dt-worker-cursor | 2 / 87.8 | - | - | 3 / 2.2 | 1 / 46.3 | 1 / 1.5 |
| dt-worker (Claude) | - | - | - | - | 1 / 34.8 | 2 / 7.0 |
| dt-hypothesizer | - | - | 5 / 14.0 | - | - | - |

My window has 72 rows against the evaluator's 67 (it excluded reviewer, hypothesizer 5, readiness 6, itself,
and one running card, and included 2 cards that started before the window). The Plan numbers agree with the
evaluator: 25 planner cards. Inside the window the stored `issue` rows are mostly orchestration by title: for
Codex 25 of 26 rows (66.7 of 135.4 min), for Cursor 4 of 7 rows (48.5 of 137.8 min, counting Triage + Adopt;
unlabeled excluded). I do not infer anything about model quality from this: the groups differ in kind of work,
not in how well it was done.

### F3. `kind_of` precedence and where the key rule is dead (verified)

`agr_kpi.py:38-48`, in order:

1. `"[race" in title` **or** (`idempotency_key` starts with `gh-` and has >= 2 dashes) -> `race`.
2. title starts with `Research:` / `Experiment:` / `Improve:` / `Evaluate:` -> that kind.
3. `branch_name` starts with `harness/` -> `harness`.
4. anything else -> `issue`.

Facts:

- `list --json` fields (`kanban_output.py:16-22`) include `title` and `branch_name` but **not**
  `idempotency_key`. So in production step 1 is title-only; the key half is never true.
- Key shapes on the 534 rows (DB): `gh-N-pilot` 176, `gh-N` 45, `gh-N-build` 5, `gh-N-codex` 3, `gh-N-pilot-pi` 3,
  `gh-N-pilot-rN` 3, `gh-N-claude` 2, `-agy` 2, `-cursor` 2, `-pilot-rebase` 2, plus singles. Title `[race`
  appears on 13 rows, all with a 3+-dash key. With the key visible, `gh-N-pilot` (176 non-race cards), `-build`,
  `-rebase`, `-rN` would also be called race. Two of the key-visible changes hit `harness` rows (precedence: a
  `harness/` branch loses to the key rule).
- Counts of snapshot rows that the key rule would flip to `race` (all implementers; mutually informative, not
  for subtraction): Claude 44 / 3588.1 min, Cursor 48 / 4442.1, Codex 35 (+2 harness) / 5082.4 (+90.0),
  agy 22 / 658.2, pi 16 / 898.0, deepseek 15 / 958.2.
- Title-based `[race` race detection: 12 snapshot rows (13 DB rows, the 13th is newer than the snapshot).
- `Plan:`, `Hypotheses:`, `Triage:`, `Adopt:`, `Prompt:`, `Hypothesis:` match none of the title prefixes in step
  2, so they fall through to step 3/4 and become `issue` (`Adopt:` rows with an `improve/` branch also stay `issue`).

### F4. Input -> observed -> candidate rows (replay, frozen dictionaries)

| card | title (cut) | key / branch | snapshot kind | `kind_of` with key | candidate (report-only) |
|---|---|---|---|---|---|
| t_3d8c2f68 | `#111 guard.py asks on writes ...` | `gh-111` / `fix/hooks-guard...` | issue | issue | **issue** (ordinary `#N` stays issue) |
| t_0956c926 | `Plan: next tasks 2026-10-20 09:57` | `plan-2026-10-20-09:57` / - | issue | issue | **plan** |
| t_82ede69c | `Hypotheses: 2026-10-15 14:10` | `hypotheses-...` / - | issue | issue | **hypotheses** |
| t_88f8d7db | `Triage: pilot issues 2026-10-15` | `triage-2026-10-15` / - | issue | issue | **triage** |
| t_6e3ee263 | `Adopt: #83 Bijective facade ...` | `adopt-hyp-83` / `improve/hyp-83` | issue | issue | **adopt** (taxonomy open; reported separately) |
| t_2d0515fe | `#141 save_transcript ... [race ...]` | `gh-141-claude` / `harness/save-transcrip...` | race | race | **race** (title marker wins; race before harness) |
| t_b99a8069 | `#127 Guardrails: permission matrix ...` | `gh-127` / `harness/guardrails...` | harness | harness | **harness** (existing rule 3 retained) |
| t_6f811afa | `Measure opening x_m/w_m ...` | `gh-22` / `fix/extractor-...` | issue | issue | **unknown** (no `#N`, no known prefix: evidence is missing, not proof of production) |
| t_2f086b88 | `#58 Pi guard extension ...` | `gh-58-pilot` / `harness/pi-guard...` | harness | **race** | harness (key rule not adopted: it is a false positive, `gh-N-pilot` is not a race) |
| t_0124904e | `#41 Harness inventory ...` | `gh-41-pilot-pi` / `docs/inventory...` | issue | race | issue (explicit race marker absent; key is ambiguous, see O2) |

The candidate function is: keep `kind_of` unless it returned `issue`; then `Plan|Hypotheses|Readiness|Triage|Adopt`
explicit prefix -> that label; `#<digits>` start -> `issue`; empty title -> `unknown`; anything else ->
`unknown`/`unlabeled`. It never overrides race, the four existing prefixes or harness. It is a function of
`kind_of(card)` output plus the title, so the independent-reviewer boundary is unaffected: reviewer runs are
filtered out before `kind_of` is reached, and I did not change that filter.

### F5. Do relabels change totals? (verified by replay)

- Per-implementer `cards`, `first_pass`, `review_rounds` and `minutes` totals under the candidate labels equal
  the snapshot values, and equal `kpi.json` `totals` for `cards`, `first_pass`, `review_rounds` for every
  implementer. `kind` is only a grouping key in `agg` (`agr_kpi.py:76`) and a column in `scoreboard.md`.
- What changes: the `implementer|kind` split. Example (Cursor): the old `issue` row has 81 cards, first_pass 17,
  rounds 60; after relabel `#N` issue = 59 / 16 / 58, `adopt` = 3 / 1 / 2, `triage` = 13 / 0 / 0, unlabeled = 6 / 0 / 0. For Codex: 43 / first_pass 26 / rounds 13 for `#N`; Plan 50
  cards, 0 first-pass, 0 rounds (no reviewer run, so they are never first-pass; `first_pass` needs `bool(rev)`).
- So a reader who divides first-pass by `cards` per kind sees different first-pass *rates* after the relabel
  (Codex issue: 27/94 = 29 % before, 26/43 = 60 % after; the 1 Adopt first-pass moves to `adopt`) although the implementer total does not change. That is a
  denominator change, which is the user's decision, not a bug.
- Not measured: a live re-run of the collector (forbidden), any grade in `grades.jsonl`.

## How it applies to this repository

This is harness telemetry (outside the pilot repo): `C:/Users/artsafro/hermes_kanban/scripts/agr_kpi.py`
(`kind_of`, `agg`), `kpi/kpi.json`, `kpi/scoreboard.md`, evaluator reading rules in
`profiles/COORDINATION_RULES.md`. In this repo it feeds the evaluation prose used for model-choice decisions
(`docs/decisions.md`), so a per-kind "issue" figure that includes Plan/Triage/Adopt rows can be misread as
implementation load. This card changes none of those files; proposals below are separate cards.

## Proposed next tasks

All are harness-side; no open roadmap issue (#149, #298, #337, #349, #352, #371, #425, #426) is advanced by them.

1. **Report-only candidate-kind column in the evaluator's own table** - the evaluator (not the collector) adds
   a column derived from title prefix (`plan|hypotheses|triage|adopt|issue|unlabeled`) next to stored kind and
   prints both row and minutes. Verification pair: replay of F4 rows -> expected labels; totals equal to
   `kpi.json` `totals`. Value M / effort S. `Archive: no roadmap link`.
2. **Document, do not toggle, the dead key rule** - a short note in the KPI docs: `list --json` has no
   `idempotency_key`, so key-based race is inert; `gh-N-pilot` would be a false positive if exposed. Verification
   pair: `list --json` field list vs `kind_of`; a unit replay on the 6 shapes in F3. Value M / effort S.
   `Archive: no roadmap link`.
3. **Collector change (needs approval, see O1/O3)** - adds the candidate label as a new field `kind_report`
   without changing `kind`, with a regression test: relabel leaves `totals` identical. Value M / effort M.
   `Archive: no roadmap link`.
4. **Decide how `Adopt:` / `Hypothesis:` / `Prompt:` are classified** - user-only; not a coding task.
   `Archive: no roadmap link`.

These are disjoint: 1 touches only the evaluator output, 2 only documentation, 3 only the collector.

## Open questions for the user

- O1. Is `Adopt:` implementation work (it has a branch and a PR, 41.4 min typical) or adoption/orchestration?
  I left it as its own row, as asked.
- O2. Is a key of the form `gh-<N>-pilot[-<agent>]` ever meant to mark a race, or only `[race ...]` in the title
  (and `-codex/-agy/-cursor/-claude/-pi` suffixes)? Determines whether the dead key rule is deleted or fixed.
- O3. Should per-kind first-pass rates exclude Plan/Triage/Hypotheses (denominator), or stay as-is and just be
  shown next to the new labels?
- O4. `Readiness:` and `Prompt:`/`Hypothesis:` titles: where do they belong in the taxonomy (zero titled
  `Readiness:` exist on the board)?
