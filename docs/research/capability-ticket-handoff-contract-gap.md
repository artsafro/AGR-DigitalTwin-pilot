# Research: which handoff receipt checks survive capability-ticket replay?

Worktree HEAD `acdbec25649a1f059f40f4a44800f7939254a514`. PR #612 is merged. This note records source reads and one synthetic probe. It is not delivery acceptance, and it does not change the grader, the threshold, or the frozen reference.

## Summary

`capability_ticket` treats author receipts as four substrings. `check_handoff` parses a different set of lines, skips fenced blocks, and verifies `Regression evals:` with `check_receipt`. On the documented lexical fixture those two results diverge: the grader returns `4/4` / `passed: true` while `check_handoff` returns five problems (row a). Empty values and the same four labels inside a fence still produce lexical `4/4` (rows b, c). A well-formed receipt line fails closed when `report.json` is absent or the counts differ, and it passes when a synthetic regression report matches (rows e, f, f2). The lexical row stays true across those three receipt outcomes.

The frozen capability B reference regrades to `3/4` with the lexical row false, the same measured value as `reference/local-pr-report.json`. On this checkout its solution commit still resolves, so `check_handoff` judges the body: the Full suite line is the replay prohibition and is rejected as not evidence, and the regression line is not a receipt. A byte copy of the retained procedural report does match `check_receipt` for `0/0/10`, but the frozen body does not cite that file, and `reference.json` stays `passed: false`. Launcher readiness also requires a procedural exit code of 0. The frozen procedural report's exit code is 2.

## Frozen probe matrix (written before execution)

Synthetic inputs only, except row R which reads the frozen capability-ticket reference and does not modify it. Predictions in this section were written before the probe ran. The run is recorded under Findings.

Shared grader call: `capability_ticket` on exactly one body, one diff and one branch file. Diff for rows a–f, unless a row says otherwise:

```
diff --git a/docs/a.md b/docs/a.md
--- a/docs/a.md
+++ b/docs/a.md
@@ -0,0 +1 @@
+synthetic
```

Branch file text: `harness/capability-ticket-synthetic`.

Structural body S0, copied from `tests/test_capability_ticket.py` `body()` (the documented lexical fixture): heading `## Author receipts`, then `Pattern: new-case: synthetic control`, `Regression evals: not measured (synthetic)`, `Probe: synthetic`, then `## Agent trace` with every `TRACE_FIELDS` value `synthetic`.

Throwaway git repo (rows that call `check_handoff`): three local commits `base`, `red`, `head` in an isolated temp directory. `check_handoff` receives the temp repo as cwd and `head`'s full 40-hex sha. No commit is created in the shared checkout.

Report shape when a report is built: `selector.suite = regression`, counts `0 passed / 0 failed / 10 not measured`, ten rows with `passed: null`. Marked synthetic.

| Row | Input frozen before the run | Tools | Prediction (not a result) |
|---|---|---|---|
| a | S0 plus the diff and branch above | `capability_ticket`; `check_handoff` with the temp head and an output dir that has no `report.json` | Grader `4/4`, `passed` true, lexical row true. Handoff lists missing Full suite, Before (RED), After (GREEN), Sample output, and a regression-evals format error. It does not list missing Regression evals. Empty problem list is not predicted. |
| b | S0 with empty values: `Pattern:`, `Regression evals:`, `Probe:` and the same trace, diff and branch | `capability_ticket`; `check_receipt("Regression evals:")`; `check_handoff` as in (a) | Grader still `4/4` because the four tokens remain. `check_receipt` raises `not a dt evals receipt`. Handoff still has that format error plus the four missing handoff lines, and does not treat empty Pattern/Probe as handoff fields. |
| c | The four lexical lines only inside one ``` fence; agent trace, diff and branch outside the fence | `capability_ticket`; `check_handoff` as in (a) | Grader still `4/4` (substring, fence ignored). Handoff lists missing Regression evals because the fence is skipped, and does not report `not a dt evals receipt`. |
| d | S0 with the `Probe:` line removed | `capability_ticket`; `check_handoff` as in (a) | Grader `3/4`, `passed` false, lexical row false, the other three rows true. |
| e | Valid handoff body (Full suite `suite_slot.py` on the temp head, `1 passed, 0 failed`; RED on the temp red commit with `3 failed`; GREEN on the temp head with `4 passed, 0 failed`; Sample output path). Receipt line names `<output>/report.json` and that file is absent. Author lines `## Author receipts`, `Pattern: new-case: synthetic control`, `Probe: synthetic` sit outside any fence. | `check_receipt`; `check_handoff`; `capability_ticket` | `check_receipt` and handoff report `report missing` only. Grader stays `4/4`. The missing file is a prerequisite failure, not a count disagreement. |
| f | Same body as (e) but the receipt names a real synthetic `report.json` with counts `0/0/10` and reason `no Claude transcript` | `check_receipt`; `check_handoff`; `capability_ticket` | `check_receipt` returns without error. `check_handoff` returns an empty problem list. Grader `4/4`. This does not grade the historical replay. |
| f2 | Same as (f) except the receipt claims `10 passed / 0 failed / 0 not measured` while the file stays `0/0/10` | same three | `check_receipt` and handoff report `counts differ`. Grader stays `4/4`. |
| h | Exact documented handoff fixture from `tests/test_evals_handoff.py` `lines()` / `body()`, including the Full suite value that starts with a backtick, plus the temp head and the (f) report | `check_handoff` only | Predicted from source: `_evidence_lines` skips a value that starts with `` ` ``, so the problem list includes `missing Full suite` and is not empty. Recorded even if the prediction is wrong. |
| R | Frozen `evals/capability-ticket/reference/{pr-body.md,local.diff,branch.txt}` unread and unmodified | `capability_ticket`; `check_handoff` with recorded solution sha `187a27fe16e55052e02757502f717f446b6984d8` and this worktree as cwd; `_evidence_lines` on the frozen body | Grader `3/4`, lexical false, matching `reference/local-pr-report.json`. `check_handoff` stops at `sha is not a commit` (object absent). That is a prerequisite failure, not a semantic RED/GREEN verdict. Label inventory is not a handoff verdict. |
| R-layout | Frozen directory as `--output`; receipt path `reference/procedural-report.json`; counts `0/0/10` | `check_receipt` | `report missing`, because the directory has no `report.json`. Not a green regrade. |
| R-copy | Byte copy of `procedural-report.json` into a temp dir as `report.json`; receipt names that copy with `0 passed / 0 failed / 10 not measured (no Claude transcript)` | `check_receipt` | Schema acceptance of the retained parent report only. The frozen body does not contain this line. `reference.json` `passed` stays false. |

Aggregate readiness is not the grader's `passed` field. The launcher was not invoked.

## Findings

Verified-by-me means this session read the cited file or ran the probe. Claimed means the sentence is taken from a PR, task file, or comment and was not re-executed here. Pytest, the full suite, and another agent were not run.

### F1. Two contracts, verified by the probe

Synthetic temp commits, not repository history: base `aa7ceb1079bfafaf8a3569eb517b0b86bed26b4f`, red `762d7f6d2f8d6404bbd86abdc91039a7dc8852e9`, head `664836a3d742b69c1af41e309823ee2729e6b569`.

| Row | Lexical row | Other local rows | Grader | `check_receipt` | `check_handoff` | Prediction |
|---|---|---|---|---|---|---|
| a | true | trace true, numeric true (`measured` 0), branch true | `4/4`, `passed` true | not called on its own | missing Full suite, Before (RED), After (GREEN), Sample output; `regression evals: not a dt evals receipt` | matched |
| b | true | same three true | `4/4`, `passed` true | `not a dt evals receipt` | same five problems as (a) | matched |
| c | true | same three true | `4/4`, `passed` true | not called | missing Full suite, Regression evals, Before (RED), After (GREEN), Sample output. No receipt-format problem | matched |
| d | false | same three true | `3/4`, `passed` false | not called | same five problems as (a) | matched |
| e | true | trace false (`absent`); numeric true; branch true | `3/4`, `passed` false | `report missing: .../no-report/report.json` | that same `report missing` line only | receipt half matched. Grader aggregate was `3/4` because the frozen (e) body has no `## Agent trace`. The lexical row still passed |
| f | true | trace false; numeric true; branch true | `3/4`, `passed` false | ok | empty list | receipt and handoff matched. Aggregate `4/4` was not produced, for the same missing trace |
| f2 | true | trace false; numeric true; branch true | `3/4`, `passed` false | `counts differ: receipt [10, 0, 0]; report [0, 0, 10]` | that same counts line only | receipt half matched; aggregate missed for the missing trace |
| h | not graded |  |  | not called | empty list. Parsed labels: Full suite, Regression evals, Before (RED), After (GREEN), Sample output | prediction wrong |

Row h's backtick prediction was wrong. The documented fixture's Full suite value is a space, then a backtick. `_evidence_lines` skips a value only when the first character is a backtick (`handoff.py:123-124`). A leading space fails that test, then `strip().strip("`")` removes the fence-marker backtick (`handoff.py:126`). Calling `_evidence_lines` on that one line returns `Full suite` with the command text kept. The documented fixture is a passing handoff body when the temp head and the matching report exist.

Rows e, f and f2 isolate the receipt. Their grader aggregate is false because the probe body omitted the agent-trace block. That miss is in the probe construction. The lexical receipt row was true on all three, including the missing report and the count mismatch.

### F2. Frozen reference regrade

`reference/pr-body.md` sha256 `eb1afe737a73d34e9eca75d08b2d653290a47e708ae82ed123e2be4585c204ff` matches `reference.json` `committed_evidence`. After the probe the hash and `reference.json` `passed: false` were unchanged.

`capability_ticket` on the three frozen paths: `measured` `3/4`, `passed` false. Rows: agent trace true (`present, 10 fields`), numeric true (`measured` 0), named branch and nonempty diff true, lexical false. `reference/local-pr-report.json` already records `measured` `3/4`. This session reproduced that grade from the frozen files.

`git rev-parse --verify "187a27fe16e55052e02757502f717f446b6984d8^{commit}"` prints that sha and exits 0. `git cat-file -t` prints `commit`. `git merge-base --is-ancestor` of that commit against HEAD exits 1. `git branch -a --contains` printed no branch. The pre-run prediction that `check_handoff` would stop at `sha is not a commit` is wrong on this checkout. The object is still in the shared object store, on no branch.

Because the sha gate passed, `check_handoff` returned a body verdict:

- `missing Before (RED): line`
- `missing After (GREEN): line`
- `missing Sample output: line`
- `full suite is not evidence: 'not measured, explicitly prohibited by this replay. Benchmarks'`
- `regression evals: not a dt evals receipt`

`_evidence_lines` on the frozen body, which is an inventory and not by itself a verdict, found only:

- `Full suite` = `not measured, explicitly prohibited by this replay. Benchmarks` (first physical line only; `**` removed)
- `Regression evals` = `passed not measured, failed not measured,`

The following prose lines are not part of those values. `Pattern:` and `Probe:` are absent, which is why the lexical row is false. `RED at` and `GREEN at` do not match `Before (RED):` / `After (GREEN):`.

`check_receipt` against the reference directory, with a receipt path of `procedural-report.json`, raises `report missing: .../evals/capability-ticket/reference/report.json`. The retained file is not named `report.json`.

A temp copy of `procedural-report.json` named `report.json`, paired with a constructed line `0 passed / 0 failed / 10 not measured (no Claude transcript)`, makes `check_receipt` return without error. That line is not in the frozen body. The copy was not written back. This is schema compatibility of the parent procedural report, which is `suite: regression`, counts `0/0/10`, exit code 2, ten `passed: null` rows.

### F3. Contract table

Replay instructions are the ticket child prompt in `tools/qa/capability_b01.py:182-191` and the task file `evals/capability-ticket/task.md:100-105`. Retained files are what that launcher writes and what cleanup leaves.

| Field | Lexical requirement | `check_handoff` requirement | Replay instruction | Retained artifact | Compatibility | File:line |
|---|---|---|---|---|---|---|
| `## Author receipts` | Substring must occur | Unread | Prompt requires the Author receipts section | `pr-body.md` in the run directory | Presence check is replay-compatible. Rows a–c pass it with no handoff success | `capability.py:123-125`; heading not in `handoff.py:16-18` |
| `Pattern:` | Substring must occur. Empty text after the colon still contains the token (row b). A fenced copy still contains it (row c) | Unread. Rows a and b do not mention Pattern in the problem list | WORKFLOW wants `pattern id`, `new-case`, or `n/a if no new module` | Body text. The pattern index is not opened | Presence is compatible with offline replay. The WORKFLOW value shape is unchecked | `capability.py:123-125`; `WORKFLOW.md:89`; `handoff.py:16-18` |
| `Probe:` | Same substring rule. Removing the line flips only this row (row d) | Unread | WORKFLOW wants `invariant -> probe -> N/N` plus command, seed or bounds, and an evidence path, or `n/a: <reason>` | Body text. A path in the line is not opened. A file only inside the deleted worktree is gone | Same presence gap as Pattern. Row d shows the token is the whole check | `capability.py:123-125`; `WORKFLOW.md:91`; `test_capability_ticket.py:44-48` |
| `Regression evals:` | Substring must occur. `not measured (synthetic)`, an empty value, a missing report, and a count mismatch all keep the lexical row true (a, b, e, f2) | The single unfenced line is passed to `check_receipt`. Format, path `samefile` of `<output>/report.json`, suite `regression`, and equal counts are required. An all-not-measured report is a valid receipt | Child is told to record unavailable telemetry as not measured. Parent runs the regression suite after the child exits | Parent writes `<run>/evals-procedural/report.json` and does not delete the run directory. Frozen copy: `reference/procedural-report.json`. Frozen body does not name it. Reference directory has no `report.json` | Conflict between the two checkers. `check_receipt` is compatible only for a retained file the line names. Rows e, f, f2, R, R-layout, and R-copy are the witnessed pairs. The frozen body fails the format check | `capability.py:123-125`; `handoff.py:213-217`; `receipt.py:7-11`, `receipt.py:46-53`, `receipt.py:64-66`, `receipt.py:95-97`; `capability_b01.py:283-287` |
| `Local CI:` | Unchecked | Unchecked | Prompt forbids GitHub calls and publication | No `CI-RECEIPT` file is written | Production WORKFLOW line has no replay artifact and no ticket grader. Not probed with `ci_receipt.py` | `WORKFLOW.md:92`; `capability_b01.py:187-188`; `ci_receipt.py:1-8` |
| `Full suite:` | Unchecked | Must name `suite_slot`, name a resolved commit, show at least one passed and no unexplained failure, and must not be an omission or a delegation. `not measured` is an omission | Prompt: `run the full test suite` is forbidden. Focused tests are allowed. Task file: the full suite is prohibited in the child prompt | No suite log. Frozen body records the prohibition. Row f shows a synthetic `suite_slot.py` line can make this check pass when the other lines and the report are present | Conflict. An honest prohibition fails the production check (row R). A passing line is evidence the child was told not to produce. Row f is a synthetic control, not a replay result | `handoff.py:27-28`, `handoff.py:163-186`; `capability_b01.py:187-188`; `task.md:104-105` |
| `Before (RED):` | Unchecked | One line. Either `n/a: <reason>`, or a commit that resolves, is not the head, is an ancestor of the head, and has at least one failed or error | Focused tests are allowed, so a RED count can be honest | Prose in `pr-body.md` if the child wrote the label. The solution commit is not a file in the run directory. This checkout still resolves `187a27fe…` from the object store, and no branch contains it | The frozen body never reaches the ancestor check: the label is missing (row R). Object-store residue is not a file the launcher lists. A clone that lacks the object stops at `handoff.py:194-195` before any RED reading. That missing-object path was not observed here | `handoff.py:192-195`, `handoff.py:218-226`; `capability_b01.py:301-319`; `WORKFLOW.md:106-107` |
| `After (GREEN):` | Unchecked | Must name the head sha, have at least one passed and zero failed, and must not be `n/a` or an omission | Focused tests are allowed. GREEN has no `n/a` in the checker | Same as RED. `local.diff` is a patch against the base, not a commit object | Missing label on the frozen body (row R). The count check was not reached. A synthetic GREEN line passes inside row f when the temp head is named | `handoff.py:144-160`, `handoff.py:227-228`; `WORKFLOW.md:107-108` |
| `Sample output:` | Unchecked | Non-empty path or inline text, or `n/a: <reason>`. The path is not opened | The ticket prompt does not name this label | Whatever text is in `pr-body.md` | Once the sha gate passes, the check reads only the body. The frozen body has no such line (row R). No extra retained file is required for the check itself | `handoff.py:229-231`; `WORKFLOW.md:110` |
| `Affected tests:` | Unchecked | Optional. If present, it must be a passing run on the head. It becomes mandatory when Full suite names an ancestor of the head | Focused tests are allowed, so the line can be honest. It does not replace a forbidden full suite | Body text only, and only if the child wrote it | Not triggered on the frozen body: the Full suite line is an omission and returns before the ancestor rule. Row f has no Affected line and still passes because its Full suite names the temp head | `handoff.py:163-178`, `handoff.py:208-210`; `WORKFLOW.md:102-104` |

`check_handoff` returns the sha error before it reads any line (`handoff.py:192-195`). Every handoff field above therefore depends on a resolved 40-hex commit even when the field itself only looks at text. Row R got past that gate on this machine. Rows a–f and h used the synthetic temp head.

### F4. Lexical `local_pr` success is not launcher readiness

Verified by reading the launcher and the frozen reference, and by rows a–c. The launcher was not executed.

`capability_ticket` sets `passed` true only when all four local rows are true (`capability.py:126-129`). The fourth row is the substring test. Rows a–c are that true result together with a non-empty `check_handoff` problem list. `evals/capability-ticket/task.md:71-76` says the same thing in prose: the receipt check verifies presence only, not truth, provenance, or issue correctness. That task sentence is claimed by the task file and matched by rows b, c, e, and f2.

The launcher's own `passed` flag is a different expression (`capability_b01.py:296-298`): session exit 0, capability-grader exit 0, procedural exit 0, protected inputs unchanged, and a clean commit whose sha differs from the replay base. `runner.exit_code` returns 2 when any row has `passed is None` and none has `passed is False` (`runner.py:231-234`). The frozen procedural report has `not_measured: 10` and `exit_code: 2`. A later lexical `4/4` would still leave procedural exit 2, and the launcher flag would stay false.

The threshold stored after the reference asks for 4 local checks and `procedural_not_measured: 0` (`reference.json` `threshold`, `task.md:81-85`). The stored reference itself is `local_pr` 0 passed / 1 failed / 0 not measured, procedural 0 / 0 / 10, `passed: false`. `tests/test_capability_ticket.py:19-32` asserts a synthetic launch whose `local_pr` is all passed and whose launcher `passed` is false. That test was read and not re-run.

PR #612's out-of-scope note, verified by `gh pr view 612`: "The capability-ticket grader keeps its lexical author-receipt check (`src/twinqa/evals/capability.py`). Switching it to `check_handoff` would change a grader's verdicts, so it needs its own `--references` run." This session did not run `--references`. Rows a–c are the verdict change that note is pointing at: today's lexical pass becomes a handoff failure on the same documented fixture.

### F5. The child full-suite prohibition blocks a production handoff pass

Verified by the prompt string, by row R's handoff output, and by row f as a contrasting synthetic control.

The child prompt forbids push, a real PR, GitHub, and the full test suite, and it allows focused tests (`capability_b01.py:187-188`). The frozen body says so on its Full suite line. With the solution commit resolved, `check_handoff` classifies that line as not evidence. The production checker has no status for "prohibited by the replay prompt". Omission words are problems (`handoff.py:164-168`, tests exist in `tests/test_evals_handoff.py` and were not re-run).

A body that satisfies `check_handoff` in row f names `suite_slot.py`, a resolved head, and `1 passed, 0 failed`. Writing that line as a real result means running the suite the prompt forbids. Using production exit 0 as a replay gate would reject the honest frozen body, which row R already did, and would demand a run the child is instructed not to make.

The parent procedural report is a regression-eval report, not a pytest full suite. It is written after the child has already written `pr-body.md` (`capability_b01.py:271-287`). The child cannot cite that path at authoring time. Row R-copy shows the file's schema can satisfy `check_receipt` after a rename into `report.json`. Row R shows the frozen prose does not.

RED, GREEN, and Sample are not forbidden. They are absent as labels, so row R records missing lines. Their git ancestry check needs a commit object. The launcher deletes the worktree and the temporary branch and writes no bundle (`capability_b01.py:301-319`). This checkout still has the dangling object. That is local residue, not an artifact listed in `reference.json` `committed_evidence`.

## How it applies to this repository

- Grader: `src/twinqa/evals/capability.py` (`capability_ticket`), wired at `src/twinqa/evals/graders.py` for evidence keys `body`, `diff`, `branch`.
- Handoff and receipt: `src/twinqa/evals/handoff.py`, `src/twinqa/evals/receipt.py`, CLI in `src/dt_ai/cli/main.py` (`--check-handoff` accepts only `--sha` and `--output`).
- Launcher: `tools/qa/capability_b01.py`. One launcher for eval A and eval B.
- Policy text the checker enforces: `docs/agents/WORKFLOW.md` sections "Author receipts in PR" and "Handoff evidence check (#584)". `docs/agents/CAPABILITIES.md` points at the handoff command.
- Frozen negative reference: `evals/capability-ticket/reference.json`, `task.md`, `task.json`, and `reference/pr-body.md`, `local.diff`, `branch.txt`, `local-pr-report.json`, `procedural-report.json`.
- Tests that already encode the two contracts, not re-run here: `tests/test_capability_ticket.py`, `tests/test_evals_handoff.py`, `tests/test_evals_receipt.py`.
- Local CI producer, unread by both graders: `tools/ci_receipt.py`.

## Proposed next tasks

No policy is adopted here. No threshold change, no full-suite requirement for the child, and no new approval.

Open roadmap issues on `artsafro/AGR-DigitalTwin-pilot` are #426, #425, #371, #352, #349, #337, #298, and #149. #149 is the NPM/VPM production capability spec (L1/L2/L3 sheets). None of those issues is this grader gap. Both proposals are `Archive: no roadmap link`.

1. **Retained-report row beside the lexical row.** Value M / effort M. `Archive: no roadmap link`.

   Add a separate `capability_ticket` row that runs `check_receipt` against a report file the run directory already keeps. Leave the lexical row in place so existing `4/4` and `3/4` meanings stay visible until a `--references` run is a deliberate later change. Evidence discovery: `capability_b01.py` writes `<run>/evals-procedural/report.json` and cleanup removes the worktree, `agent-home`, and the temporary branch, not the run directory. The frozen reference stores that report as `reference/procedural-report.json` and has no `report.json`. The child writes the body before the parent report exists, so the row must name a file the launcher retained, not a path that existed only in the worktree.

   Input to expected output, using the pairs this probe already saw:

   - Retained report counts `0/0/10` and receipt `Regression evals: <that file as report.json>; 0 passed / 0 failed / 10 not measured (no Claude transcript)` -> `check_receipt` success (row R-copy / row f).
   - Same file, receipt claims `10 passed / 0 failed / 0 not measured` -> `counts differ: receipt [10, 0, 0]; report [0, 0, 10]` (row f2).
   - Well-formed receipt whose `report.json` is absent -> `report missing: <output>/report.json` (row e). The lexical row may stay true; the new row must fail.
   - Frozen `reference/pr-body.md` with output = the reference directory -> lexical regrade stays `3/4` and the new row does not pass. Do not edit `reference.json` or flip `passed`.

2. **Replay classification that leaves production `check_handoff` exit codes alone.** Value M / effort S. `Archive: no roadmap link`.

   A read-only classifier for capability-ticket bodies. It does not make `check_handoff` return success for a prohibited suite, and it does not change the readiness threshold.

   - Frozen parsed Full suite value `not measured, explicitly prohibited by this replay. Benchmarks` -> class `prohibited-by-replay`. Production `check_handoff`, when the solution sha resolves, already returns `full suite is not evidence: 'not measured, explicitly prohibited by this replay. Benchmarks'` (row R). The class must keep that production failure.
   - Synthetic `Full suite: suite_slot.py on <resolved head>: 1 passed, 0 failed` plus a matching retained receipt (row f, empty handoff list) -> class `full-suite-claimed`. That class records a conflict with the child prompt. It is not replay readiness.
   - Matching `0/0/10` receipt and report -> receipt success. Claimed `10/0/0` against `0/0/10` -> `counts differ`. Absent `report.json` -> `report missing`. Same pairs as task 1.
   - `git rev-parse --verify <solution_commit>^{commit}` fails -> record `sha is not a commit` and do not emit RED/GREEN semantic problems. This checkout is the other case: the sha resolves, no branch contains it, and the body verdict above is the one to keep. Discovery is that rev-parse plus `git branch -a --contains`, then a regrade of the three frozen paths. Expected regrade remains lexical `3/4`, `reference.json` `passed` false.

## Open questions for the user

1. Should RED/GREEN resolution accept a dangling object that `git rev-parse` can still see after the launcher deleted the branch, or only a commit object stored under the run directory?
2. May a future receipt row cite the parent `evals-procedural/report.json` even though that file does not exist when the child writes `pr-body.md`?

## Source SHAs

`git rev-parse HEAD` = `acdbec25649a1f059f40f4a44800f7939254a514`. `git log -1 --format=%H -- <file>`:

| File | Commit |
|---|---|
| `src/twinqa/evals/capability.py` | `deb68d684f481e90241b9e4397d6dd8dc7f56908` |
| `src/twinqa/evals/handoff.py` | `a13a811d8584c389ccd764a1e7e68d99f8b9cfcf` |
| `src/twinqa/evals/receipt.py` | `48d2d10e0ff02f42e8da1f1abed39ed58878eb36` |
| `src/twinqa/evals/pr_graders.py` | `ccd3196bc55fbc67f6fbeeeca7ee55b4d792fbb3` |
| `src/twinqa/evals/runner.py` | `ceebe18d3609d7fbf78d54a8c951498992b5454c` |
| `src/twinqa/evals/graders.py` | `deb68d684f481e90241b9e4397d6dd8dc7f56908` |
| `src/dt_ai/cli/main.py` | `3560ee709365b0400de29361cde6bc16ce7badbc` |
| `tools/qa/capability_b01.py` | `11fee791818c9ac9dd8610ac4f421033e67abebc` |
| `tools/ci_receipt.py` | `59390f258938d11d5ada702dacba5ec7363cca7c` |
| `evals/capability-ticket/task.md` | `ccd3196bc55fbc67f6fbeeeca7ee55b4d792fbb3` |
| `evals/capability-ticket/task.json` | `deb68d684f481e90241b9e4397d6dd8dc7f56908` |
| `evals/capability-ticket/reference.json` and `reference/*` | `ccd3196bc55fbc67f6fbeeeca7ee55b4d792fbb3` |
| `tests/test_capability_ticket.py` | `4d98d838f1a4eb6bbf8bb5a921ae86a8daf97e76` |
| `tests/test_evals_handoff.py` | `a13a811d8584c389ccd764a1e7e68d99f8b9cfcf` |
| `tests/test_evals_receipt.py` | `48d2d10e0ff02f42e8da1f1abed39ed58878eb36` |
| `docs/agents/WORKFLOW.md` | `eabc9d17223d3d536111d107dabc1e2c3d1ab2d3` |
| `docs/agents/CAPABILITIES.md` | `3560ee709365b0400de29361cde6bc16ce7badbc` |

I should pin graders.py too since I mentioned it. Let me quickly get that SHA and patch the table if I left it vague. I said "not separately probed" which is a bit sloppy. I'll get the SHA and fix that one cell.

Also I should verify graders.py line 776 is still accurate - I grepped it earlier.

And I claimed cli main line about --check-handoff accepts only --sha and --output. I read main.py 158-163. Good.

Let me pin graders.py and fix the table cell. Also verify I didn't leave the .venv. Already removed.

Double-check capability_b01 line numbers for 182-191 and 301-319 from the read. Yes.

I'll fix graders.py SHA with a small search_replace after a git log.