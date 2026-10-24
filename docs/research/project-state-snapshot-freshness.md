# Project state: why origin/main still serves the 2026-10-21 snapshot

## Summary

`origin/main` is `dcb9237b08d0036df232fd4e061f34103bc0e9a7` (merge #660, commit time 2026-10-24T02:38:17+02:00). A `git fetch origin main` at 2026-10-24T05:25:43+02:00 left `FETCH_HEAD` equal to that SHA. The blob `docs/PROJECT_STATE.md` on that tip is `3f9c7474dfbe6905ce576b93e87d32525510ae2c`, the same blob as content commit `c5f5b5192709efbdbcf190b999eb0c7a4fdf8881` (2026-10-21T21:14:40+02:00), which merge #517 (`79a1cf24816df1d90887e7e033e6f2b7c5ba5f43`, 2026-10-21T21:21:12+02:00) brought onto main. Those twelve merge rows are the `git log` window at `c5f5b51`, newest #515. Refresh is manual: `AGENTS.md` and `docs/agents/WORKFLOW.md` say to regenerate on `main` after a merge, and no workflow calls `tools/state/project_state.py`. Seventy-two later `Merge pull request` commits are reachable after `c5f5b51`; the served blob is unchanged. #505 and #506 are `MERGED` and still listed open (`stale_open`). #660 is row 1 of the current twelve-merge window and is absent from the file (`stale_merges`). A scratch regeneration with HEAD equal to `origin/main` emitted #660 and the twelve newest-created open PRs, and did not touch the tracked file. Still-open #377 and #525 fall outside that limit of 12, so absence from the bounded list is truncation. A failed `gh` call is `evidence_missing`: the generator exits 1 and leaves the previous file in place. The capability lines are a separate readiness reprint, not a freshness verdict.

## Findings

Labels: **verified-by-command** means this run's git/gh/python output. **Source** means the cited file. Times from `gh` are UTC; git commit times below are +02:00 unless noted.

### F1 — What origin/main serves

**Verified-by-command.** After fetch, `git rev-parse FETCH_HEAD`, `origin/main`, `main`, and this worktree `HEAD` were all `dcb9237b08d0036df232fd4e061f34103bc0e9a7`. `git log -1` subject: `Merge pull request #660 from artsafro/docs/research-source-new-vertex-quantization-boundary`. `git rev-parse origin/main:docs/PROJECT_STATE.md` and `c5f5b5192709efbdbcf190b999eb0c7a4fdf8881:docs/PROJECT_STATE.md` are both `3f9c7474dfbe6905ce576b93e87d32525510ae2c`. Simplified `git log origin/main -- docs/PROJECT_STATE.md` shows `c5f5b51` as the newest content commit. Its subject is `docs: project state after #515; restore main's handoff overwritten by the #515 merge` (`git show -s`). The range `c5f5b51..origin/main --merges --grep=^Merge pull request #` printed 72 subjects. The newest 12 of `git log origin/main --merges --grep=^Merge pull request # -n 12` are #660, #659, #658, #652, #648, #646, #642, #641, #640, #639, #637, #636. The same command at `c5f5b51` is #515, #476, #501, #500, #499, #498, #497, #494, #492, #496, #495, #493, and those short SHAs match the committed file in that order.

Merge #517's result blob is `3f9c747…`. Its first parent is #515's merge `a29e63320cc540f5251d277d0ffcfa725346f713` (blob `3f9b6ff55ee3bbedb1bd6a9163332b5b7888ad76`). Its second parent is `c5f5b51` (blob `3f9c747…`). Sampled later merge results stay on `3f9c747…`: #505 `c0a2aa44`, #506 `3f3e883a`, #507 `9373df60`, #513 `aad71039`, #660 `dcb9237`. `git log --full-history` still names #505, #507, #508, and #513 because another parent carries a different blob; the merge result that main serves does not.

### F2 — Refresh ownership

**Source.** `AGENTS.md` (rules): update `docs/PROJECT_STATE.md` only on `main` after a merge, by `python tools/state/project_state.py`. `docs/agents/WORKFLOW.md` section "Project state (#119)" repeats that, names `git log --merges` and `gh pr list`, and says a task branch reports state in the handoff. **Verified-by-command.** A search of this worktree, including `.github`, finds callers only in `tools/state/project_state.py`, `tests/test_context_diet.py`, `tests/test_project_state.py`, `AGENTS.md`, `docs/agents/WORKFLOW.md`, and the generated file itself. No workflow invokes the generator. `tests/test_project_state.py` checks the heading set and the 80-line cap. `tests/test_context_diet.py::test_checked_in_project_state_names_the_generator` checks that the header names the command and that the file is under 80 lines. Neither test compares rows to live git or GitHub, so a stale snapshot still satisfies them.

### F3 — Generator source selection

**Source.** `generate()` in `tools/state/project_state.py` runs `git log --merges --grep=^Merge pull request # -n <max_merges>` with no revision, so the history is `HEAD` of `--repo`. It reads `git remote get-url origin`, requires a GitHub `owner/name`, then runs `gh pr list --repo <that> --state open --limit <max_open>`. Defaults in `main()` are `--max-merges 12` and `--max-open 12`. Results are sliced to those caps again. Open rows are sorted by PR number for display. Non-zero git or gh becomes `FailClosed("unsupported")`, exit 1, and the destination is not replaced (`_capture`). `test_gh_uses_origin_not_fork_parent` locks the `gh --repo` value to origin. `test_real_git_fixture_repo_generation` shows a non-PR merge subject is dropped and the PR merge subject is kept. This worktree's origin is `https://github.com/artsafro/AGR-DigitalTwin-pilot.git`. The upstream remote `https://github.com/artsafro/AGR-DigitalTwin.git` is not what the generator queries.

**Verified-by-command.** On this pin, generator `HEAD` and `origin/main` are the same SHA, so local-HEAD versus `origin/main` does not explain the committed file. The historical counterexample is the #515 merge blob: `git show a29e633:docs/PROJECT_STATE.md` lists newest merge `#328` and open rows such as #248 and #335. That branch-carried snapshot was the first parent of #517; #517's result kept `c5f5b51` instead. `docs/PROJECT_STATE.next.md` is absent here. The committed next-step sentence is the generator's default sentence.

### F4 — Controls #505, #506, #660

`gh` timestamp for `gh pr view` of #505, #506, #660, and #515: 2026-10-24T05:25:44+02:00. Repo `artsafro/AGR-DigitalTwin-pilot`.

| Control | GitHub at that time | Committed snapshot | Class |
|---|---|---|---|
| #505 | `MERGED` 2026-10-23T00:51:24Z, merge `c0a2aa44af895e774346007ac72f5f64443e8b37` | Listed under Open pull requests | `stale_open` |
| #506 | `MERGED` 2026-10-21T21:47:30Z, merge `3f3e883aa897b5cfd67df4ccb8757f5b832944e7` | Listed under Open pull requests | `stale_open` |
| #660 | `MERGED` 2026-10-24T00:38:18Z, merge `dcb9237b08d0036df232fd4e061f34103bc0e9a7` | Not among the twelve in-production rows | `stale_merges` |

#506's merge is later than `c5f5b51` (19:14:40Z) and later than #517 (19:21:12Z). #505's merge is two days later. Both were open in the frozen file and are merged now. They are absent from the live open set (below), so the max-open window is not what keeps them in the file. #660 is inside the declared window: it is the first of the twelve `git log --merges --grep=^Merge pull request # -n 12` rows on `origin/main`. The same window stops at #636, so #505 and #506 are outside it and a fresh file would omit them from In production as well.

The other open rows in the frozen file, viewed at 2026-10-24T05:28:18+02:00: #507, #508, #509, #513, and #516 are `MERGED`. #377 is `OPEN` (`createdAt` 2026-10-20T10:35:34Z, `updatedAt` 2026-10-20T20:30:06Z).

### F5 — max-open is a different discrepancy

**Verified-by-command.** `gh pr list --repo artsafro/AGR-DigitalTwin-pilot --state open --limit 12` at 2026-10-24T05:26:05+02:00 returned numbers 661, 656, 655, 654, 643, 633, 631, 629, 611, 610, 601, 599. `--limit 200` returned 29 numbers. `gh api search/issues?q=repo:artsafro/AGR-DigitalTwin-pilot+is:pr+is:open&per_page=1` at 2026-10-24T05:28:18+02:00 returned `total_count` 29 and `incomplete_results` false. #505 and #506 are not in those 29. `gh pr list --help` does not document sort order. The generator passes no sort flag. At 2026-10-24T05:29:57+02:00, `GET /repos/artsafro/AGR-DigitalTwin-pilot/pulls?state=open&per_page=12&sort=created&direction=desc` returned the same twelve numbers.

#525 is `OPEN`, `createdAt` 2026-10-21T20:40:19Z, `updatedAt` 2026-10-23T06:57:24Z, and is outside those twelve. Its update is later than #599 (`createdAt` 2026-10-23T01:45:13Z), the oldest of the twelve. #377 is older still and is also outside. Both are open. A bounded list omitting them does not mean they are closed. The frozen file has eight open rows, which is under the cap of 12; this run did not replay GitHub as of 2026-10-21, so those eight are the file's contents, matched to today's `gh pr view`, and their count is consistent with a full response under the cap.

### F6 — Scratch regeneration

**Verified-by-command.** At 2026-10-24T05:31:21+02:00, with `HEAD` and `origin/main` both `dcb9237b08d0036df232fd4e061f34103bc0e9a7`:

`python tools/state/project_state.py --repo . --output C:/x/t_36294cfe/state.md --max-merges 12 --max-open 12`

stdout empty, exit 0. Tracked `docs/PROJECT_STATE.md` SHA-256 stayed `F569098B204924EB777E316EA56545B861C79006EE8E8D1F84D07D36A62C5BD6`. Scratch SHA-256 `68230C934BDB4DA6DAEB3D440A648F0F26B18F299925A3FE1A725AA1AA8E8FF8`, 52 lines. In production in the scratch file is the same twelve short SHAs as `git log origin/main -n 12` above, starting with `` `dcb9237` Merge pull request #660 ``. Open rows are #599, #601, #610, #611, #629, #631, #633, #643, #654, #655, #656, #661, the same set as the limit-12 list, sorted by number. Capability A and B lines match the committed file word for word. `git log c5f5b51..origin/main -- evals/capability-b01/reference.json evals/capability-ticket/reference.json docs/PROJECT_STATE.next.md` printed nothing, so this regeneration reprints the same readiness sentences. That reprint is not evidence that the benchmarks are current. The 80-line refusal did not fire (52 < 80). `gh` was available, so this run did not observe `evidence_missing`. Source for that class: a non-zero `gh` raises `unsupported`, `main()` prints `project_state: unsupported` to stderr, returns 1, and does not publish.

### Diagnostic

Read-only, and it does not change the file, the caps, or refresh policy. Record one timestamp for the whole pass.

1. `git fetch origin main`, then require `git rev-parse FETCH_HEAD` = `git rev-parse origin/main`. Record that SHA.
2. Record `git rev-parse origin/main:docs/PROJECT_STATE.md` and `git log -1 --format=%H origin/main -- docs/PROJECT_STATE.md`.
3. Record `git rev-parse HEAD` and `git remote get-url origin` for the repo that would be `--repo`.
4. `git log origin/main --merges --grep=^Merge pull request # -n 12 --format=%H%x09%s` is the declared merge window. The same command at the content commit is the age baseline.
5. `gh pr list --repo artsafro/AGR-DigitalTwin-pilot --state open --limit 12 --json number,title,headRefName,isDraft`, plus `gh pr view` for every open number printed in the file. Use `gh api` search `total_count` before treating the list as complete. If `gh` fails or the JSON is empty or partial, stop with `evidence_missing`.
6. Verdicts, which may combine: `wrong_head` when step 3's HEAD or origin slug is not the pin (do not call that age); `stale_merges` when a window row such as #660 is missing from the file while the file's rows equal the content-commit log; `stale_open` when a listed open number is `MERGED` (#505, #506); `truncated_open` when `gh pr view` says `OPEN` for a number outside the limit (#377, #525) and `total_count` > 12; `current` when the file's merge rows equal the pinned window and its open numbers equal the limit-12 set after number sort. On this pin the tip is `stale_merges` and `stale_open` together, with `wrong_head` false and truncation visible only against a fresh limit-12 list.

## How it applies to this repository

- `docs/PROJECT_STATE.md` — served snapshot, blob `3f9c747…`, content commit `c5f5b51`, on `origin/main` `dcb9237`.
- `tools/state/project_state.py` — HEAD log, origin `gh` repo, caps 12/12, fail-closed publish.
- `tests/test_project_state.py`, `tests/test_context_diet.py` — shape, origin binding, and fixture git; no live freshness assert.
- `AGENTS.md`, `docs/agents/WORKFLOW.md` — manual regenerate-on-main ownership.
- `.github` — no snapshot job in this tree.
- `evals/capability-b01/reference.json`, `evals/capability-ticket/reference.json` — readiness lines, unchanged across this range.
- Origin `artsafro/AGR-DigitalTwin-pilot`; upstream `artsafro/AGR-DigitalTwin` is outside the generator's `gh` query.

## Proposed next tasks

### 1. Read-only PROJECT_STATE freshness classifier

Add a checker that performs the diagnostic above and prints `current`, `stale_open`, `stale_merges`, or `evidence_missing`, plus separate `wrong_head` and `truncated_open` flags. Acceptance on these pins: scratch output whose merge rows equal `git log dcb9237 --merges --grep=^Merge pull request # -n 12` and whose open numbers equal the 2026-10-24T05:26:05Z limit-12 set is `current`; the committed file listing #505 and #506 open after their recorded merges is `stale_open`; the same file missing #660 while #660 is inside that window is `stale_merges`; a non-zero `gh` is `evidence_missing` and is not `current`. It writes nothing under `docs/`, does not change `--max-open`, and does not refresh the snapshot.

Value: startup can see that the 2026-10-21 file is stale. Effort: S.

Advances: Archive: no roadmap link

### 2. Review check for a branch-carried PROJECT_STATE blob

Compare a PR tip's `docs/PROJECT_STATE.md` in-production rows with `git log <base> --merges --grep=^Merge pull request # -n 12`. Flag the PR when they differ. Acceptance on historical pins: #515 merge `a29e633` (newest row #328) flags against a base whose window is newer; #517 result blob `3f9c747` matches `git log c5f5b51` of that form and does not flag against that parent; a PR that leaves the blob unchanged does not flag. It does not regenerate the file and does not add a post-merge refresh.

Value: catches the overwrite that published a branch snapshot onto main at #515. Effort: S.

Advances: Archive: no roadmap link

Roadmap survey at 2026-10-24T05:28:21+02:00, `gh issue list --repo artsafro/AGR-DigitalTwin-pilot --state open --label roadmap --limit 100`: #426, #425, #371, #352, #349, #337, #298, #149. None of those issues is snapshot lifecycle.

## Open questions for the user

- Should `docs/PROJECT_STATE.md` stay a manual regenerate-on-main step, or should some later change publish a new snapshot after each merge? This note does not choose.
- Should `--max-merges` and `--max-open` stay 12? A faithful run then omits 17 of 29 open PRs, including still-open #377 and #525. This note does not change the caps.
- May a task branch commit `docs/PROJECT_STATE.md`? The #515 merge published a snapshot whose newest merge row was #328, until #517 replaced it.
