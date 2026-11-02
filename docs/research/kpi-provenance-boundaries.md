# KPI provenance boundaries

Date: 2026-10-24

Card: t_1d512a9f

Documents proposal 2 of the #671 report (F2/F3, "Proposed next tasks" 2). The report is the scratch copy of `docs/research/kpi-card-kind-attribution-boundary.md` from `origin/docs/research-kpi-card-kind-attribution-boundary`. This note records the list-JSON, reviewer-gate, `kind_of`, and aggregation boundary, and a board-versus-snapshot count for Readiness cards. It does not change the collector.

No `docs/domain/` area covers this harness telemetry. None was applied.

## Frozen hashes

SHA-256 of each file read for this note. Tracked and deployed `agr_kpi.py` are byte-identical. This worktree has no `agr_kpi.py`.

| File | SHA-256 | Role |
|---|---|---|
| `C:/Users/artsafro/hermes_kanban/scripts/agr_kpi.py` | `daa1286999fe61c99dd449bced0ccb978d1742dca32800b9c502958ffcf83d30` | tracked collector |
| `C:/Users/artsafro/.hermes/scripts/agr_kpi.py` | `daa1286999fe61c99dd449bced0ccb978d1742dca32800b9c502958ffcf83d30` | deployed collector, same bytes |
| `C:/Users/artsafro/.hermes/hermes-agent/hermes_cli/kanban_output.py` | `7817f12a52c9446761a0ff0664441e615e343beec269a206c66d32a87e8339c5` | `list --json` task fields |
| `C:/Users/artsafro/.hermes/hermes-agent/hermes_cli/kanban.py` | `14131a7111cf9d30b735cdbc9c44f979228a8b1311b67c8c00c0f92cc33bc72d` | `list` calls `_task_to_dict` |
| `C:/Users/artsafro/.hermes/hermes-agent/hermes_cli/kanban_db.py` | `2ccf8698869975e335b4f302d6ed38bd37cec01959540e79fa5be88cfd6517b2` | `Task.idempotency_key`, `list_tasks` archive default |
| `C:/Users/artsafro/hermes_kanban/scripts/agr_readiness_card.py` | `f8a742a8c990812e9e56d02a431f8ba4da33888ba7737a8b175fed16488c007e` | cron that creates `Readiness:` cards |
| `C:/Users/artsafro/hermes_kanban/kpi/kpi.json` | `55f78e7ca336c3a4aaa5715199e00e0f5c39b3ca7532503b8f9cb4564de3ceca` | snapshot, `generated` `2026-10-24 12:39`, board `agr-pilot`, 514 rows |
| `C:/Users/artsafro/hermes_kanban/kpi/readiness/2026-10-24_1020.json` | `f5fbe502a687397c67ac318dcd2d2d6e532d0f10a6cee983922bcc1e30d672ab` | readiness report whose `task_id` is `t_c59182be` |
| `C:/Users/artsafro/hermes_kanban/kpi/readiness/2026-10-22_1008.json` | `dde2dcc4d2f7673d5a3f87c313cfd1de458167891bb00262a2befc991ed89c31` | report file whose `task_id` is `t_971c6b47` |
| `C:/Users/artsafro/.hermes/profiles/dt-worker-cursor/cache/scratch/report671.md` | `23604d44ed00bd50719dd83d3366e6db78f85c9fa196d72324c7300e736909d7` | #671 report read for this card |

The #671 report froze an earlier `kpi.json` (`8fa447b0e6afeffde7735a4657e37aeb9bf189bee1be9bd539f47c93fec6d72a`, `generated` `2026-10-24 11:08`). The hash above is the file on disk for this note.

## Not done

- `idempotency_key` stays off `hermes kanban list --json`. Nothing in the collector, evaluator, scoreboard, guards, hooks, or CI was edited.
- Race policy is open. The `gh-69-pilot` result below is the current predicate on a constructed dict. It is not an adopted label and it is not a reclassification of board card `t_68260486`.
- Taxonomy and the per-kind denominator are open. This note does not relabel Plan, Triage, Adopt, Hypothesis, or Prompt rows.
- The collector was not run. `kpi.json` was not rewritten.
- The #671 report was not edited.
- Git was not run.
- Headline board counts are one read-only transaction at `2026-10-24T13:27:38+02:00`. A later read at `2026-10-24T13:28:49+02:00` only names outcomes on the single 17-run Readiness card. The board can move after those times.

## Boundary

`agr_kpi.py` loads cards with `hk("list", "--json")` (line 52), drops cards whose runs are all reviewers (lines 56-58), then stores `kind_of(c)` (line 64) and sums by `implementer` and `implementer|kind` (lines 74-76). `kind` is a grouping key. It is not a filter on the per-implementer totals.

Reviewer profiles are `dt-reviewer` and `dt-evaluator` (line 21). A card with no remaining run is skipped before `kind_of`.

`kind_of` (lines 38-48) is this order:

```python
t = card.get("title", "")
key = card.get("idempotency_key") or ""
if "[race" in t or key.count("-") >= 2 and key.startswith("gh-"):
    return "race"
```

Then a title prefix `Research:`, `Experiment:`, `Improve:`, or `Evaluate:` (lines 43-45), then `branch_name` starting with `harness/` (lines 46-47), otherwise `issue` (line 48).

`and` binds before `or`, so the race test is: title contains `[race`, or (the key starts with `gh-` and contains at least two `-`). A missing key, JSON `null`, and `""` all become `""` because of `or ""`. `"".count("-") >= 2` is false, so the key disjunct is false. The title marker is the only race path that can fire.

`list --json` never supplies that key. `_cmd_list` prints `[_task_to_dict(t) for t in tasks]` (`kanban.py` lines 419-431). `_task_to_dict` copies `_TASK_DICT_FIELDS` (`kanban_output.py` lines 16-22 and 83-86). That tuple has 26 names, including `title` and `branch_name`, and it has no `idempotency_key`. The column still exists on `tasks` (`kanban_db.py` line 818) and on `Task` (line 635). `list_tasks` omits `status = 'archived'` unless the caller asks (lines 1459-1460). The collector does not pass `--archived`.

The withheld key is what keeps the second race disjunct inert. The disjunct is broad: `gh-69-pilot` has two dashes and starts with `gh-`, so the current function returns `race` when that string is passed in. A one-dash key such as `gh-111` fails `count("-") >= 2`. Report #671 calls the `gh-<N>-pilot` hit a false positive. This note does not choose whether pilot keys, agent suffixes, or only the `[race` marker should count as races.

On the official transaction, among non-archived cards that have at least one run whose profile is outside `{dt-reviewer, dt-evaluator}` (519 cards, the population that reaches `kind_of`):

- 192 keys start with `gh-` and contain at least two dashes. 167 of those are exactly `gh-<digits or other segment>-pilot` (two dashes, tail `pilot`).
- 12 titles contain `[race`. Those are already `race` from the list dict.
- 182 of the 192 have no `[race` marker. With the key withheld, the same predicate returns `issue` for 180 and `harness` for 2. Passing the stored key through the current function would return `race` for all 182. That counterfactual is a measured production count of the predicate. It is not applied to the snapshot.

Readiness keys are `readiness-<stamp>`. They do not start with `gh-`, so this race disjunct would still be false if the field were copied into the list dict. Readiness rows are missing from the snapshot because of the reviewer gate, not because of the dead key.

## Population

Two identification reads, each its own `file:...?mode=ro` connection, immediately before the official transaction: `C:/Users/artsafro/.hermes/kanban.db` has 0 tasks and 0 runs. `C:/Users/artsafro/.hermes/kanban/boards/agr/kanban.db` has 2 tasks and 2 runs. The KPI board in `agr_kpi.py` line 19 is `agr-pilot`.

Official sample: one `BEGIN` on `file:C:/Users/artsafro/.hermes/kanban/boards/agr-pilot/kanban.db?mode=ro`, all SELECTs inside it, `total_changes` 0, then rollback. Transaction clock `2026-10-24T13:27:38+02:00` (start and end in that same second). 586 tasks, 1650 runs, 565 non-archived tasks, 519 non-archived implementer-bearing tasks. The #671 report's earlier transaction at `2026-10-24 12:22:09` local counted 583 tasks and 1647 runs on this same file.

Snapshot store: `C:/Users/artsafro/hermes_kanban/kpi/kpi.json`, `generated` `2026-10-24 12:39`, 514 card rows. Zero titles start with `Readiness:`. `t_c59182be` is absent.

Prefix `Readiness:` on the board in that transaction:

| Quantity | Count |
|---|---|
| Cards, all statuses | 26, every status `done`, none archived |
| Runs | 42, every profile `dt-reviewer` |
| Reviewer-only cards | 26 |
| Implementer-bearing cards | 0 |
| Cards with zero runs | 0 |
| Cards present in `kpi.json` | 0 |
| `created_at` on or before `2026-10-24T12:22:09+02:00` | 26 |

Run histogram in that transaction: 25 cards with 1 run, 1 card with 17 runs. A second `mode=ro` transaction at `2026-10-24T13:28:49+02:00` still found one multi-run Readiness card, `t_971c6b47`, title `Readiness: 2026-10-22 06:07`: 16 runs `outcome=rate_limited` and 1 run `outcome=completed`, profile `dt-reviewer` on all 17. `total_changes` was 0.

`created_at` spans `2026-10-20T08:40:06+02:00` through `2026-10-24T10:20:22+02:00`. Stored titles match the cron string `Readiness: {stamp}` (`agr_readiness_card.py` lines 37-38), assignee default `dt-reviewer` (line 9). The one board title that contains the substring `eadiness` and does not use that prefix is this card, `t_1d512a9f`, whose title starts with `Improve:`.

`kpi/readiness/` has 26 JSON files and 25 distinct `task_id` values. `2026-10-22_0607.json` and `2026-10-22_1008.json` both name `t_971c6b47`. Board card `t_9d24b05c`, title `Readiness: 2026-10-22 10:08`, is not the `task_id` of any of those files. File count, distinct `task_id`, and board-card count are three figures.

Report #671 F2 says ``Readiness:`` matches 0 card titles on the board, and that the evaluator's 6 readiness reports are not stored under such a title. In this transaction the six cards whose `created_at` lies in the report's evaluation window `2026-10-23 07:07` through `2026-10-24 07:02` local are:

| Card | Title | Created |
|---|---|---|
| `t_c4b5f19c` | `Readiness: 2026-10-23 10:14` | `2026-10-23T10:14:22+02:00` |
| `t_29beec3f` | `Readiness: 2026-10-23 14:15` | `2026-10-23T14:15:22+02:00` |
| `t_ab5d6bd7` | `Readiness: 2026-10-23 18:16` | `2026-10-23T18:16:22+02:00` |
| `t_e182410e` | `Readiness: 2026-10-23 22:17` | `2026-10-23T22:17:22+02:00` |
| `t_972633fe` | `Readiness: 2026-10-24 02:18` | `2026-10-24T02:18:22+02:00` |
| `t_8b966fe4` | `Readiness: 2026-10-24 06:19` | `2026-10-24T06:19:22+02:00` |

Each of those titles is on the board. Each card is reviewer-only and absent from the 514-row snapshot. The snapshot's zero `Readiness:` rows are the reviewer gate (lines 56-58) applied to cards `list --json` does return. They are a different population from the board titles.

Five other non-archived implementer-bearing cards are also absent from the 12:39 snapshot (`t_0775177b`, `t_c5e60274`, `t_162557dd`, `t_c628f16a`, `t_1d512a9f`). That is snapshot age. It is a different gap from the 26 reviewer-only Readiness cards, which have no implementer run.

### `t_c59182be`

Measured in the official transaction. Title `Readiness: 2026-10-24 10:20`. Status `done`. Assignee `dt-reviewer`. `created_by` `agr_readiness`. `created_at` `2026-10-24T10:20:22+02:00`. `branch_name` null. `idempotency_key` `readiness-2026-10-24_1020`. One run, id 1645, profile `dt-reviewer`, status `done`, outcome `completed`, `2026-10-24T10:20:24+02:00` to `2026-10-24T10:24:13+02:00`. Population: reviewer-only. Absent from `kpi.json`. `kpi/readiness/2026-10-24_1020.json` records `"task_id": "t_c59182be"`. The board title exists. The snapshot row does not. Creation is after the evaluation window above, so this card is the example, not one of those six.

## Verification pairs

Isolated script `C:/Users/artsafro/.hermes/profiles/dt-worker-cursor/cache/scratch/t_1d512a9f_replay.py`. It `exec`s `kind_of` from the tracked file text after checking both copies' SHA-256, parses `_TASK_DICT_FIELDS` with `ast`, and does not import the collector, open the database, or write a file. The gate it replays is `agr_kpi.py` lines 56-58. Key output:

```text
tracked_sha256 daa1286999fe61c99dd449bced0ccb978d1742dca32800b9c502958ffcf83d30
deployed_sha256 daa1286999fe61c99dd449bced0ccb978d1742dca32800b9c502958ffcf83d30
task_dict_has_idempotency_key False
task_dict_field_count 26
---
pair: list dict without key -> key-based race condition inert
label: measured production sample
card: t_68260486
idempotency_key_in_dict: False
withheld_db_key: gh-69-pilot
result: {'retained': True, 'kind': 'issue', 'implementer_runs': 1}
kind_of_missing: issue
kind_of_empty_string: issue
kind_of_none: issue
---
pair: hypothetical gh-69-pilot with key -> current rule gives race
label: synthetic control
adopted: False
note: false-positive risk of the current predicate; race policy not decided
dict: {'title': '#69 hypothetical pilot', 'idempotency_key': 'gh-69-pilot', 'branch_name': 'fix/hypothetical'}
kind_of: race
same_dict_without_key: issue
dash_count: 2
---
pair: explicit [race marker -> race
label: measured production sample
card: t_2d0515fe
idempotency_key_in_dict: False
result: {'retained': True, 'kind': 'race', 'implementer_runs': 1}
marker_removed_synthetic_control: {'label': 'synthetic control', 'title': '#141 save_transcript: search the nonce in bounded chunks (P2 of #140)', 'kind_of': 'harness'}
---
pair: Readiness card with only dt-reviewer runs -> omitted before classification
label: measured production sample
card: t_c59182be
result: {'retained': False, 'kind': None, 'implementer_runs': 0}
---
pair: ordinary #N with a non-reviewer run -> retained
label: measured production sample
card: t_3d8c2f68
result: {'retained': True, 'kind': 'issue', 'implementer_runs': 1}
```

`t_68260486` is a real list-shaped dict: title `#69 main red: orientation check flags the corner pilaster (PR #45 x PR #5)`, branch `fix/orientation-corner-pilaster`, runs of `dt-worker-codex` then `dt-reviewer`. The database key `gh-69-pilot` was left out of the dict. Snapshot kind for that id is `issue`. Missing, empty, and null keys all stay `issue`, so the key disjunct does not fire.

The `gh-69-pilot` race result uses a constructed title `#69 hypothetical pilot` and branch `fix/hypothetical`. The same dict with the key removed returns `issue`. Report #671 documents this shape as a false-positive risk. This pair does not adopt that call, and it does not write a new kind for `t_68260486`.

`t_2d0515fe` is the list dict for `#141 save_transcript: search the nonce in bounded chunks (P2 of #140) [race claude]`, branch `harness/save-transcript-bounded-chunks-claude`, with a `dt-worker` run. Snapshot kind is `race`. The marker selects `race` while the key is absent. The synthetic control deletes ` [race claude]` from that title and returns `harness`, which is the branch test at lines 46-47 once the marker is gone.

`t_c59182be` stops at the gate. `kind` is null because `kind_of` is not called.

`t_3d8c2f68` is `#111 guard.py asks on writes to ~/.claude/plans in plan mode`, branch `fix/hooks-guard-plan-writes`, with a `dt-worker` run. The gate keeps it and `kind_of` on the list dict returns `issue`. Snapshot kind is `issue`.

The 180/2 split in the population section was computed inside the measurement script with the same predicate as lines 38-48 and the key forced empty. The pairs above are the execution of the function taken from the hashed file.

## User-only decisions

These stay with the user. This card does not pick them.

- Taxonomy. Whether `Adopt:`, `Plan:`, `Triage:`, `Hypotheses:`, `Hypothesis:`, `Prompt:`, and `Readiness:` are implementation work. `Readiness:` cards measured here never reach `kind_of`.
- Denominator. Whether per-kind first-pass rates drop orchestration rows. `agg` (lines 74-84) keeps implementer totals on the implementer key and uses `kind` only on the `implementer|kind` key.
- Race policy. Whether a key of the form `gh-<N>-pilot` (or `-build`, `-claude`, `-codex`, and the other multi-dash `gh-` tails), the title marker `[race`, or both, should return `race`. The current key disjunct is inert in production and over-broad if the field is copied through unchanged.
