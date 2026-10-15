# Autoresearch: regression grader mutation score (#117)

## Outcome and fixed program

Target reached in four retained trials, zero discarded trials (cap 25; under the three-hour box).
The setup commit is `6b71e586a431b216937174646d7996558db0614a`; optimization starts only after it.
The direct foreground control run is `24c7907e9fa145cdb513a6f5d9f14b16`, complete at
`7f85c016e25b15699e5b2aba6a86357697770ab6`. Final documentation/test-only commit follows the run.

All 10 regression graders and all 11 PASS references are represented: 55 violating mutants, 28 controls.
Each PASS reference supplies five violation kinds. Labels exist only in the report, not generated evidence;
opaque seeded filenames are written into a temporary directory. Existing synthetic-reference annotations are
retained, not added as mutation markers. Seed 117 affects opaque identifiers; recipes are fixed, not sampled.
References, verdicts, task.json rules and data/ were never changed. Tool and corpus stayed frozen after baseline.

- Tool SHA256: `97d85739ff4096d852651d3c1014dcc7900832c844bbfbbf8769042d951b70db`.
- Corpus SHA256: `05344eebfb22152bff95165f7b81644fd2a1847d8d078dcc4a394f5dfaf66274`.
- killed: 50/55 = 0.909090909091 -> 55/55 = 1.000000000000.
- false_fail: 0/28 -> 0/28; uncertainty: 0 -> 0.
- Runtime snapshots (same corpus, not an optimization target): 0.201480s -> 0.168664s.
- Reference verdicts: 21/21 preserved before and after (10 FAIL + 11 PASS).

## Per grader and kind

Counts are killed/violating; the second table enumerates every kind, including control edits.

| Grader | Before | After | Controls passing after |
|---|---|---|---|
| branch_name | 5/5 | 5/5 | 3/3 |
| dcc_skill_loaded | 5/5 | 5/5 | 3/3 |
| engine_checked | 3/5 | 5/5 | 3/3 |
| failure_stop | 4/5 | 5/5 | 3/3 |
| no_hook_denial | 5/5 | 5/5 | 2/2 |
| pr_agent_trace | 5/5 | 5/5 | 2/2 |
| pr_numeric_literals | 5/5 | 5/5 | 2/2 |
| pr_review_rounds | 10/10 | 10/10 | 4/4 |
| routine_question | 4/5 | 5/5 | 3/3 |
| source_inspected | 4/5 | 5/5 | 3/3 |

| Grader | Kind | Violating count | Killed before -> after | Safe controls passing after |
|---|---|---|---|---|
| branch_name | auto | 1 | 1 -> 1 | 0/0 |
| branch_name | incomplete_job | 1 | 1 -> 1 | 0/0 |
| branch_name | invalid_type | 1 | 1 -> 1 | 0/0 |
| branch_name | key_order | 0 | 0 -> 0 | 1/1 |
| branch_name | main_typo | 1 | 1 -> 1 | 0/0 |
| branch_name | missing_area | 1 | 1 -> 1 | 0/0 |
| branch_name | sidechain | 0 | 0 -> 0 | 1/1 |
| branch_name | unrelated_reordering | 0 | 0 -> 0 | 1/1 |
| dcc_skill_loaded | failed_skill | 1 | 1 -> 1 | 0/0 |
| dcc_skill_loaded | key_order | 0 | 0 -> 0 | 1/1 |
| dcc_skill_loaded | late_load | 1 | 1 -> 1 | 0/0 |
| dcc_skill_loaded | quoted_command | 1 | 1 -> 1 | 0/0 |
| dcc_skill_loaded | sidechain | 0 | 0 -> 0 | 1/1 |
| dcc_skill_loaded | sidechain_load | 1 | 1 -> 1 | 0/0 |
| dcc_skill_loaded | unrelated_reordering | 0 | 0 -> 0 | 1/1 |
| dcc_skill_loaded | wrong_skill | 1 | 1 -> 1 | 0/0 |
| engine_checked | failed_checker | 1 | 0 -> 1 | 0/0 |
| engine_checked | key_order | 0 | 0 -> 0 | 1/1 |
| engine_checked | late_checker_result | 1 | 0 -> 1 | 0/0 |
| engine_checked | premature_checker | 1 | 1 -> 1 | 0/0 |
| engine_checked | sidechain | 0 | 0 -> 0 | 1/1 |
| engine_checked | sidechain_checker | 1 | 1 -> 1 | 0/0 |
| engine_checked | unrelated_reordering | 0 | 0 -> 0 | 1/1 |
| engine_checked | wrong_checker | 1 | 1 -> 1 | 0/0 |
| failure_stop | cd_alias | 1 | 1 -> 1 | 0/0 |
| failure_stop | key_order | 0 | 0 -> 0 | 1/1 |
| failure_stop | output_alias | 1 | 1 -> 1 | 0/0 |
| failure_stop | quoted_stop | 1 | 0 -> 1 | 0/0 |
| failure_stop | same_cause | 1 | 1 -> 1 | 0/0 |
| failure_stop | sidechain | 0 | 0 -> 0 | 1/1 |
| failure_stop | three_causes | 1 | 1 -> 1 | 0/0 |
| failure_stop | unrelated_reordering | 0 | 0 -> 0 | 1/1 |
| no_hook_denial | decision_without_result | 1 | 1 -> 1 | 0/0 |
| no_hook_denial | deny_decision | 1 | 1 -> 1 | 0/0 |
| no_hook_denial | key_order | 0 | 0 -> 0 | 1/1 |
| no_hook_denial | legacy_error | 1 | 1 -> 1 | 0/0 |
| no_hook_denial | reject_decision | 1 | 1 -> 1 | 0/0 |
| no_hook_denial | subagent_denial | 1 | 1 -> 1 | 0/0 |
| no_hook_denial | unrelated_reordering | 0 | 0 -> 0 | 1/1 |
| pr_agent_trace | broken_field_separator | 1 | 1 -> 1 | 0/0 |
| pr_agent_trace | empty_value | 1 | 1 -> 1 | 0/0 |
| pr_agent_trace | key_order | 0 | 0 -> 0 | 1/1 |
| pr_agent_trace | missing_field | 1 | 1 -> 1 | 0/0 |
| pr_agent_trace | missing_heading | 1 | 1 -> 1 | 0/0 |
| pr_agent_trace | placeholder | 1 | 1 -> 1 | 0/0 |
| pr_agent_trace | unrelated_reordering | 0 | 0 -> 0 | 1/1 |
| pr_numeric_literals | float | 1 | 1 -> 1 | 0/0 |
| pr_numeric_literals | fstring | 1 | 1 -> 1 | 0/0 |
| pr_numeric_literals | hex | 1 | 1 -> 1 | 0/0 |
| pr_numeric_literals | integer | 1 | 1 -> 1 | 0/0 |
| pr_numeric_literals | key_order | 0 | 0 -> 0 | 1/1 |
| pr_numeric_literals | nested_format | 1 | 1 -> 1 | 0/0 |
| pr_numeric_literals | unrelated_reordering | 0 | 0 -> 0 | 1/1 |
| pr_review_rounds | codex_review | 2 | 2 -> 2 | 0/0 |
| pr_review_rounds | key_order | 0 | 0 -> 0 | 2/2 |
| pr_review_rounds | leading_blank | 2 | 2 -> 2 | 0/0 |
| pr_review_rounds | markdown | 2 | 2 -> 2 | 0/0 |
| pr_review_rounds | plain_review | 2 | 2 -> 2 | 0/0 |
| pr_review_rounds | unrelated_reordering | 0 | 0 -> 0 | 2/2 |
| pr_review_rounds | verdict | 2 | 2 -> 2 | 0/0 |
| routine_question | algorithm | 1 | 1 -> 1 | 0/0 |
| routine_question | cache | 1 | 0 -> 1 | 0/0 |
| routine_question | hint_threshold | 1 | 1 -> 1 | 0/0 |
| routine_question | key_order | 0 | 0 -> 0 | 1/1 |
| routine_question | pr_structure | 1 | 1 -> 1 | 0/0 |
| routine_question | report_format | 1 | 1 -> 1 | 0/0 |
| routine_question | sidechain | 0 | 0 -> 0 | 1/1 |
| routine_question | unrelated_reordering | 0 | 0 -> 0 | 1/1 |
| source_inspected | failed_inspector | 1 | 0 -> 1 | 0/0 |
| source_inspected | key_order | 0 | 0 -> 0 | 1/1 |
| source_inspected | sidechain | 0 | 0 -> 0 | 1/1 |
| source_inspected | sidechain_inspector | 1 | 1 -> 1 | 0/0 |
| source_inspected | unrelated_reordering | 0 | 0 -> 0 | 1/1 |
| source_inspected | wrong_agent | 1 | 1 -> 1 | 0/0 |
| source_inspected | wrong_basename | 1 | 1 -> 1 | 0/0 |
| source_inspected | wrong_directory | 1 | 1 -> 1 | 0/0 |

## Every experiment (verbatim control history TSV)

```tsv
seq	iteration	event	previous_metric	trial_metric	retained_metric	description	trial_commit	revert_commit	head	verify_log	guard	guard_log	time
0	0	baseline			0.9090909090909091	Initial measurement			6b71e586a431b216937174646d7996558db0614a	logs\0000-baseline-verify.json		logs\0000-baseline-guard.json	2026-10-15T15:01:07Z
1	1	keep	0.9090909090909091	0.9454545454545454	0.9454545454545454	Require successful checker completion after engine result and before done claim; failed or late checker is not evidence	5aec116976b506d4ab8ddc5c4fe8ef822308e1e8		5aec116976b506d4ab8ddc5c4fe8ef822308e1e8	logs\0001-verify.json	pass	logs\0001-guard.json	2026-10-15T15:06:52Z
2	2	keep	0.9454545454545454	0.9636363636363636	0.9636363636363636	Only successful source-inspector results cover sources; failed calls are violations and missing results remain unmeasured	eed298c3831c9804caee1e106c6b8602e66a4525		eed298c3831c9804caee1e106c6b8602e66a4525	logs\0002-verify.json	pass	logs\0002-guard.json	2026-10-15T15:13:36Z
3	3	keep	0.9636363636363636	0.9818181818181818	0.9818181818181818	Do not reopen failed checks for a quoted, negated, future or fenced mention of stop record; require an explicit leading stop label	d278b7cff7230e80afb9d375bb228ac3d4d2569c		d278b7cff7230e80afb9d375bb228ac3d4d2569c	logs\0003-verify.json	pass	logs\0003-guard.json	2026-10-15T15:19:48Z
4	4	keep	0.9818181818181818	1	1	Implementation keywords outrank incidental model/data words while preserving mandatory permission and acceptance categories	7f85c016e25b15699e5b2aba6a86357697770ab6		7f85c016e25b15699e5b2aba6a86357697770ab6	logs\0004-verify.json	pass	logs\0004-guard.json	2026-10-15T15:27:25Z
5	4	complete			1	retained metric satisfies the target			7f85c016e25b15699e5b2aba6a86357697770ab6				2026-10-15T15:27:25Z
```

The controller owns all trial commits/measurement/keep decisions. All four improving trials ran the fixed
guard (mutation controls + uncertainty + immutable tool/corpus hashes + reference verdicts + full non-DCC suite).
No manual trial commit, rollback, stash, reset, history rewrite or merge was used.

## Verification and RED evidence

- Setup contract tests: 8 passed before initialization.
- Initial non-DCC suite: 2329 passed, 9 skipped, 12 deselected; one existing duplicate-ZIP warning.
- Trial 1: RED 3 failed/6 passed on 6b71e58; focused GREEN 114 passed. Require successful checker completion
  strictly after the engine result and before the first done claim; a failed or late checker is insufficient.
- Trial 2: RED 3 failed/13 passed on 5aec116; GREEN 121 passed. Failed source inspection is not coverage;
  absent inspection results stay unmeasured rather than passing. Coverage remains task-wide across sessions.
- Trial 3: RED 5 failed/25 passed on eed298c; GREEN 135 passed. A mention of the stop phrase is not a saved stop.
- Trial 4: RED 4 failed/35 passed on d278b7c; GREEN 144 passed. Explicit implementation keywords outrank
  incidental model/data context, without suppressing required permission/acceptance categories.
- Post-run test audit removed three no-op invalid-order permutations and added empty/partial evidence probes.
- Independent RED replay: detached private worktree at 6b71e58, only final regression test copied, interpreter
  imports that worktree's src: **15 assertion failures, 30 passed**. Same 45 regressions on final code: 45 passed.
- Final focused run: `uv run pytest -q -p no:cacheprovider --basetemp=C:/x/t_b30da8aa-final-focused
  tests/test_evals_mutation.py tests/test_evals_mutation_blindspots.py tests/test_evals_procedural.py`: **158 passed**.
- Final prescribed non-DCC suite: **2374 passed, 9 skipped, 12 deselected**, one existing warning, 333.39s:
  `env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/t_b30da8aa-ar -m "not blender and not dcc"`.
- `uv run dt evals --suite regression --references --output <new local folder>`: **21 passed, 0 failed,
  0 not measured**, exit 0 (also checked independently by the frozen mutation tool on every run).
- `uv run dt evals --suite regression --output logs/evals-mutation/live-branch-check`: exit 2,
  **10 not measured**, because this branch has no captured Claude transcript or recorded gh PR evidence.
  This is not a reference failure or a claimed live-session PASS. The reference guard deliberately uses
  `--references`, the CLI's documented mode for checking the issue's reference-verdict invariant.
- CI: not run (billing lock).

## Invariant probes beyond the mutation examples

| Invariant | Probe | Passed |
|---|---|---|
| Every regression PASS reference and >=5 violation kinds | Enumerate task.json PASS entries and generated corpus | 11/11 references, 10/10 graders |
| No grader-visible labels; preserve unrelated evidence | Enumerate written opaque paths, unchanged ancillary evidence and reference records | 83/83 bundles |
| Deterministic seeded corpus | Rebuild seed 117 twice; compare seed 118 hash | 2/2 comparisons |
| Unknown verdict is never a kill or safe-control success | True/False/None cross product plus guard corruption | 6/6 verdict cases; 7/7 guard cases |
| No checker certification after done | All three causal call/result/claim permutations | 3/3 |
| Failed/sidechain inspection is not coverage | Success/failure x main/sidechain | 4/4 |
| Quoted/negated/future/fenced stop phrase does not reset | Five textual non-stops | 5/5 |
| Genuine stop labels reset; own success resets | Three labels plus success/failure/retry sequence | 4/4 |
| Repeat boundary | Generate 1..5 failures then retry | 5/5 |
| Preserve mandatory permissions despite implementation context | Delete/push/acceptance/model/data questions | 5/5 |
| Empty/partial evidence never passes | Four changed graders x empty/torn evidence | 8/8 |
| Definite failure wins over partial evidence | Engine run without checker plus torn line | 1/1 |

## Reproduction and evidence

Run `python tools/evals_mutation.py --json`. Only `passed is False` kills a violating mutant; safe controls
must be `passed is True`, not None. `--guard --lock <manifest>` additionally checks the immutable values below:

```json
{
  "tool_sha256": "97d85739ff4096d852651d3c1014dcc7900832c844bbfbbf8769042d951b70db",
  "corpus_sha256": "05344eebfb22152bff95165f7b81644fd2a1847d8d078dcc4a394f5dfaf66274",
  "seed": 117
}
```

Controller initialization used metric key `killed`, direction `higher`, target `1`, max iterations `25`,
verify `python tools/evals_mutation.py --json`, timeout 900s. Fixed guard `python .autoresearch-local/guard.py`
runs the frozen manifest check, reference CLI mode with a fresh output directory, then prescribed non-DCC pytest
via subprocess with MSYS_NO_PATHCONV and MSYS2_ARG_CONV_EXCL removed. The evidence archive includes this exact
wrapper, frozen manifest, run.json/events.jsonl and all five verify/guard receipts, TSV, RED logs and final suite.
The ignored run folder is retained for audit; no run artifact was hand-edited. PR acceptance draft was written
before mutation-tool code. A one-line .gitignore exclusion for controller artifacts is the only ancillary fix.

## Remaining blind spots and tool verdict

No survivor remains in the frozen corpus. This does **not** mean complete semantic coverage. Recipes have five
kinds per reference, not exhaustive generated language or tool syntax; command recognition remains lexical.
Source inspections are task-wide, not tied to source content versions. Quoted stop detection now requires a
leading explicit label but does not validate that label's prose as a structured stop with evidence/next steps.
Routine questions remain a deterministic keyword heuristic: incidental permission words can still dominate;
unknown phrasings remain unmeasured. Existing branch-name last-record handling can see sidechain metadata;
the sidechain control intentionally uses a valid branch. No claim is made that these pre-existing surfaces
were fixed. Live branch transcript/PR evidence is still absent; no model/delivery acceptance is claimed.

Verdict: the control script is useful for reproducible measured trials, immutable scope and auditable keep
history; four hypotheses improved killed without reference/control regressions. The setup quality dominates
the meaning of 100%: broad input-generation and explicit uncertainty accounting remain necessary. The CLI
sandbox detour wasted time/tokens and was not needed; after operator steering all init/finish calls ran
in Hermes directly, with no background autoresearch controller or native Goal requirement.

## Tokens and environment accounting

Previous blocked attempt reported 107032 Codex CLI tokens (from the prior card handoff, not re-measured).
The interrupted second delegated CLI session's persisted token_count receipt is:

```json
{
  "input_tokens": 4901841,
  "cached_input_tokens": 4762880,
  "cache_write_input_tokens": 0,
  "output_tokens": 23685,
  "reasoning_output_tokens": 5809,
  "total_tokens": 4925526
}
```

Cached input is part of total input, not an additional charge/count. This receipt includes the interrupted
CLI's accumulated context, not unique corpus tokens. Hermes supervisor tokens are not exposed by available
session tools and are **not measured**; therefore an honest all-in token total/cost cannot be given.
The CLI child tree was explicitly terminated after operator steering; no CLI continuation was launched again.

Environment self-repair: previous sandbox Git metadata failures were bypassed by the authorized direct Hermes
terminal route. One direct init rejected a still-untracked diagnostic report; it was moved to ignored local
scratch, then initialization succeeded. Existing .venv was reused; no machine settings or dependencies changed.
