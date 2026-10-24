# PR publication: why did Ground #654 receive the facade #655 description?

Card t_362d7f7f. Research only. `delivery_passed=false`. No PR was edited, no hook/guard/CI/procedure changed, no tests run.
Repo: `artsafro/AGR-DigitalTwin-pilot` (all PR numbers below are in it). Times are UTC (host local = UTC+2).

## Summary

- **Confirmed mispublication.** PR #654 (card t_3f8f00e2, branch `improve/issue-651-ground-footprint-hole`) had its body replaced at 2026-10-23T21:17:47Z by text that is byte-identical (SHA-256 prefix `265123791241`, CR stripped) to the body PR #655 (card t_fce04873, branch `improve/source-cut-legacy-four-normal-frames`) received at 20:48:02Z.
- **Strongest candidate cause (consistent with the evidence, not proven): a shared, generically named scratch file.** `C:/Users/artsafro/.hermes/profiles/dt-worker-cursor/cache/scratch/b.md` exists today; it has the same hash `265123791241` and mtime 20:48:01.5Z, 0.5 s before the #655 edit. Every dt-worker-cursor card shares that scratch directory. The same directory holds per-card names (`pr-t_3f8f00e2.md`, `pr-body-t_fce04873.md`) that match the *correct* first bodies of each PR, so the failing publication used the generic name.
- **Not measured:** the exact `gh pr edit` command line, its working directory and its `--body-file` argument for the 21:17:47Z edit. No readable command record was found (see Limitations). Wrong PR number, copied narrative and interleaved runs are therefore not excluded.
- GitHub shows one editor (`artsafro`) for all edits of both PRs: the account is shared by author and reviewer sessions, so the edit record cannot tell which profile edited.
- The foreign body stood for 4 min 8 s of GitHub time before the corrected one (21:21:45Z); reviewer R3 (21:19:57Z) saw it. The reviewer's "twice observed" claim is not independently provable from GitHub history: only one foreign-body edit exists in the edit log; the second observation is not in the record I read.
- **Identity checks do not bind a body to repo + PR + card + branch + commit.** `tools/ci_receipt.py` binds commit and branch (header keys) of a test run; `tools/review/common.py` binds a numeric task id only. Neither is applied to a PR body publication.

## Findings

### F1. Pinned-head timeline (UTC)

Sources: GitHub GraphQL `userContentEdits` and commit dates (verified by me, `gh api graphql`, `gh pr view --json commits`). Current bodies are not used as history; the edit log stores each historic body.

| time | PR | head at the time | event | body hash (first 12 hex) |
|---|---|---|---|---|
| 20:24:01 / 20:24:10 | #654 | `832578a0` | commit pushed, PR created with its own body | `4a17f5d87b43` (2111 chars; equals scratch `pr-t_3f8f00e2.md`) |
| 20:40:22 / 20:40:29 | #655 | `5ea10c13` | commit, PR created | `905b97d0bc40` (2880; equals scratch `pr-body-t_fce04873.md`) |
| 20:48:02 | #655 | `5ea10c13` | body edited to the longer facade body | `265123791241` (4968; equals scratch `b.md`) |
| 21:09:16 / 21:09:28 | #654 | `57bafa40` | R2 rework commit, body edited (Ground/OKS, correct) | `4a264fc820ce` (8937) |
| 21:17:36 | #654 | `34c10acb` | R3 rework commit pushed | n/a |
| **21:17:47** | **#654** | `34c10acb` | **body edited to the #655 facade body (11 s after the commit)** | **`265123791241`** |
| 21:19:57 | #654 | `34c10acb` | reviewer R3: "PR body is for another card (`t_fce04873`)... 0 Ground/OKS rows" | |
| 21:21:45 | #654 | `34c10acb` | body edited to the Ground/OKS body (22 rows) | `ef8d1a5d6bb0` (6111; equals scratch `pr654-body.md`) |
| 21:23:46 | #654 | `34c10acb` | reviewer: "clean (R3 description-correction verification)... No foreign facade table remains" | |

Evidence URLs:
- PR #654: https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/654
- PR #655: https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/655
- Reviewer R3 comment (21:19:57Z), verification comment (21:23:46Z) and R1/R2 are issue comments on #654; verdict link from the reviewer log: https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/654#issuecomment-6374956434
- Edit history (reproducible): GraphQL `repository.pullRequest(number:654|655).userContentEdits{createdAt editor{login} diff}`.

### F2. Confirmed vs. unproven causes

| claim | status | basis |
|---|---|---|
| #654 held #655's body between 21:17:47Z and 21:21:45Z | **confirmed** | identical hash in the edit log of both PRs |
| The 21:17:47Z edit happened in the #654 author run for t_3f8f00e2 | **likely, not proven** | 11 s after that run's commit `34c10acb`; the author's final report mentions the foreign body only as "replaced"; the shared account hides the editor profile |
| Shared scratch file reused (`b.md`) | **consistent, not proven** | file `b.md` still has the foreign hash; mtime 20:48:01.5Z matches #655's edit; per-card files of both cards exist with correct hashes. No command record ties the 21:17:47Z edit to `b.md` |
| Wrong PR number (body of #655 sent with number 654) | **not excluded** | would give the same result; no command record. Note a wrong *number* with a per-card file would still need the wrong file, so it needs a second error |
| Copied narrative (agent re-typed #655 text) | **unlikely** | equality of the full text (4968 chars with 53 CR characters; identical after CR stripping and identical in raw length in both PRs); a re-typed copy would hardly match exactly. I did not check the CR counts of the other bodies |
| Interleaved runs (two cards writing/publishing at once) | **not excluded** | #655 run finished ~22:48 local; #654 R3 rework ran from ~23:00 local; they overlap only in the shared scratch dir, not provably in time |
| Separate worktrees prevented it | **disproved as a defence** | worktrees isolate the repository tree; the body file lives in the scratch dir, outside every worktree |

Answer to the card's question: the worktree split does not cover publication artifacts. The body is read from a path outside the worktree, and `gh pr edit` takes a bare PR number.

### F3. Identity checks, read-only comparison

Compared by reading the code (not changed):

| check | repo | PR number | card | branch | commit |
|---|---|---|---|---|---|
| `tools/ci_receipt.py` (`HEADER_KEYS`: `commit, branch, dirty, started_utc, ...`) | no | no | no | yes (recorded) | yes (recorded; FAIL if head moves during the run) |
| `tools/review/common.py` `_parse_task` (`task` = positive integer) | no | no | partly (numeric task only) | no | no |
| PR body publication (`gh pr create/edit --body-file`) | by flag | by argument | none | by argument | none |

Conclusion: no existing check ties repository + PR number + card + branch + commit together, and none is applied to a PR body. This is a different gap from adopt-evidence-receipts, #653 and #657 (those concern missing formal evidence, not text published to the wrong task).

Static comparison, reproducible (no network write):

```bash
# edit hashes
gh api graphql -f query='query{repository(owner:"artsafro",name:"AGR-DigitalTwin-pilot"){
  a:pullRequest(number:654){userContentEdits(first:20){nodes{createdAt diff}}}
  b:pullRequest(number:655){userContentEdits(first:20){nodes{createdAt diff}}}}}' |
python -c "import json,sys,hashlib;d=json.load(sys.stdin)['data']['repository']
[print(k,n['createdAt'],len(n['diff']),hashlib.sha256(n['diff'].replace('\r','').encode()).hexdigest()[:12]) for k,v in d.items() for n in v['userContentEdits']['nodes']]"
# expected: a 21:17:47Z 4968 265123791241  ==  b 20:48:02Z 4968 265123791241
```

## How it applies to this repository

- Publication is described in `docs/agents/WORKFLOW.md` (Agent trace, section near line 291) and in the driver instructions of the worker profile; neither names a per-card body path or a post-edit readback. Not changed here.
- `tools/ci_receipt.py` and `tools/review/common.py` are unchanged; this card only reads them.

## Limitations (what is not measured)

- No command record with `gh pr edit 654 ... --body-file ...`, its cwd and timestamp was found. I searched `kanban/boards/agr-pilot/logs/t_3f8f00e2.log` and `t_fce04873.log` (final reports only, no tool-call lines), `profiles/dt-worker-cursor/logs/agent.log` and `process-results/*.json` (only `cursor-run.ps1` launches; they do not contain `gh`), without reading whole transcripts. The author session ids are in the card logs, but the matching session dump was not found by name; that source is **not measured**.
- Reviewer's "twice observed" is not reproducible: the edit log shows one foreign-body edit.
- Scratch mtimes are of the file's last write; an earlier write could have been overwritten.
- Reviewer-side logs (dt-reviewer) were not read beyond the comment text.

## Proposed next tasks (proposals only, no implementation)

1. **Bind a PR-body publication payload to its card (identity check, read-only).** Scope: a checker that takes a payload (`repo`, `pr`, `card`, `branch`, `head_commit`, `body_sha`) and the PR's actual `headRefName`/`headRefOid`/card trailer and refuses on any mismatch. Input -> expected: payload naming card `t_fce04873` and test file `tests/jobs/test_source_cut_legacy_frames.py` sent to PR #654 / card `t_3f8f00e2` -> **refuses**; correctly bound Ground payload (`pr=654`, card `t_3f8f00e2`, branch `improve/issue-651-ground-footprint-hole`, head `34c10acb`) -> **permits**; matching commit `34c10acb` alone but foreign card -> **refuses**. Value: high; effort: M. Archive: no roadmap link (a process-quality item; no open roadmap issue concerns PR publication).
2. **Post-publication body readback test.** Scope: after `gh pr create/edit`, compare the body's card id, branch and changed-file names against `gh pr view --json headRefName,files`; fixtures replay the #654/#655 pair. Input -> expected: #654 head files (`src/twinqa/scene.py`, `tools/qa/validate_package.py`, `tests/qa/test_scene.py`) with body naming only `tests/jobs/test_source_cut_legacy_frames.py` -> **fails**; the 21:21:45Z body -> **passes**. Value: medium; effort: S. Archive: no roadmap link.

Not proposed: a hook, guard, CI job or procedure change, a rename of scratch files, a publisher rewrite. These need a user decision.

## Open questions for the user

1. Are the author sessions for t_3f8f00e2 (R3 round) and t_fce04873 kept anywhere readable? Without them F2's "consistent, not proven" cannot be closed.
2. Should the reviewer's "twice observed" be reconciled with the edit log (one foreign edit)? Was a second observation made on a cached page or a different head?
3. Is the shared GitHub account for authors and reviewers intended? It removes the editor as evidence.
