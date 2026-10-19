# Why merged PR #229 turned main red

## Summary

- PR #229 merged at 2026-10-15 23:41:23Z as `919114b056727a6544fd5b2d137e2e4ef54f5ab7`.
- Its base was `3e533744aa80e165343ab16816ff0da69850ddf1`; the failing test function was already present there.
- The test's contract scans tracked Markdown for dated user-decision language and requires a `[D<n>]` reference.
- #229 added `docs/experiments/flora-library-audit.md` with a dated line matching that contract but no D-id; the file was newly tracked on the PR head.
- This is primarily a merge-result/scope interaction, not a newly introduced test: the PR test does not see the not-yet-tracked file in its base checkout.
- Reviewer reported 20 targeted Flora tests and inspected author full-suite evidence (3,279 passed, 9 skipped, 13 deselected); the record does not establish that the decision-contract test ran on the combined merge result.
- A separate intervening PR merge did not introduce the test contract: `#218` was already the base of #229. However, #229 itself merged after multiple unrelated PRs, so review-base staleness is distinct from the new-file trigger.
- A merge-result check that runs `tests/test_decisions.py::test_every_dated_decision_carries_its_id` against current `origin/main` plus the PR would have caught the defect.

## Findings and timeline

Evidence labels: **Verified** means checked directly against Git objects, GitHub API/PR records, or the repository file contents in this research. **Source says** means a PR comment/report states it, without this research independently rerunning it. Times below are UTC unless noted.

| Time | Event | Evidence |
|---|---|---|
| 2026-10-15 18:11:58Z | Base history includes merge #169 (`7840debc7fd9a15d33f13870adea19be3b128f8a`). | Verified from GitHub commit API. |
| 2026-10-15 21:09:26Z | PR #218 merged as `3e533744aa80e165343ab16816ff0da69850ddf1`; this became #229's recorded base (`baseRefOid`). | Verified from GitHub API. |
| 2026-10-15 18:50:17Z onward | #229 head commits: `072feca34fdacfe37bad8db7990d03b46177848f` (test), `c41782bde9145d255c4e46059345d9cb02bbb0e6` (audit), `20420b43a689b689b8e4abbb766494bc81df7bae` (report), `886f29b3780167b37075ab2d137c1dab663476773` (archive/probe improvement), `28669ee6a3ef4a2a7a039550175f1b1a1092a08a` (verification). | Verified from PR #229 commits API. |
| 2026-10-15 22:09:15Z | Author's PR #229 review comment records a clean review of head `28669ee…`, targeted Flora tests **20 passed**, author full project suite **3,279 passed / 9 skipped / 13 deselected**, and CI not run (billing lock). | Source says: [PR #229 comment](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/229#issuecomment-6203302945). The reviewer states the full suite was author-only evidence and was not independently rerun during review. |
| 2026-10-15 23:41:23Z | #229 merged as `919114b056727a6544fd5b2d137e2e4ef54f5ab7`, with parents `31198c9fab24ad53a6e8539fdee751f075747ac4` and `28669ee6a3ef4a2a7a039550175f1b1a1092a08a`. | Verified from GitHub API. |
| 2026-10-15 23:57:47Z | Fix PR #244 opened, based on `5e7b85526a7bfac0dff5a7d6897bbbedd4e3a056`; review reproduced the contract failure at that base. | Source says: [PR #244 comment](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/244#issuecomment-6204813917). |
| 2026-10-15 23:59:38Z | #244 reviewer reports exact-base RED: one failure, dated user decision without `[D<n>]`; current head `8bade719c92ce6c269150b750013ffdabdf1f46c` decision tests **4 passed**. | Source says: same [PR #244 comment](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/244#issuecomment-6204813917). |
| 2026-10-16 07:53:25Z | #244 merged as `375e8fc0ca06326217e90ca951431affbb037af5`. | Verified from GitHub API. |

### Was the test on #229's base?

**Yes.** #229 records base OID `3e533744aa80e165343ab16816ff0da69850ddf1`; its merge-base with head is `7840debc7fd9a15d33f13870adea19be3b128f8a`. I verified that `tests/test_decisions.py` existed at that base, and `test_every_dated_decision_carries_its_id` was defined there. Its implementation obtains Markdown paths through `git ls-files`, then flags date/user-decision wording without a known D-id. This test was not a post-#229 addition.

The relevant input **was** new: `docs/experiments/flora-library-audit.md` is not present in #229's base, but was added by #229. Its line 15 says `user Flora grilling notes (2026-10-15)`, matching the test's `MENTION` expression but lacking `[D<n>]`. The test passes on the base without that file and would also miss an unstaged, untracked report because discovery uses the Git index; a checked-out PR head with the report tracked should fail too. The historical record does not establish whether the author's tested report was tracked, so an untracked-file testing context is a hypothesis, not a verified fact. This new tracked Markdown file plus the existing broad scan is the defect mechanism.

### Did author/reviewer run the full suite or only targeted tests?

The #229 reviewer comment records targeted acceptance tests: `experiments/flora-library-audit/test_catalogue.py` and `test_acceptance.py`, **20 passed**. It also explicitly labels the full suite as author-only evidence (**3,279 passed / 9 skipped / 13 deselected**); reviewer says they did not rerun it. The comment does not provide a command/output proving that either author or reviewer ran the decision-contract test against the merge result. Do not interpret the author full-suite count as proof that the failure-triggering new Markdown file was staged/tracked in that tested tree; that exact context is not documented in the PR comment.

### Merge-skew?

No intervening merge introduced the test contract. PR #218 is the merge recorded as #229's base, and the contract test is already in that base. So this is **not** the simple form of merge-skew where an intervening PR adds a new test after the feature branch diverges. There was nevertheless a gap between the PR's tested branch context and eventual integration: between #218 and #229's merge, many unrelated changes merged; #229's final merge parent was `31198c9…` (#208), not its recorded base. The concrete regression is still attributable to #229's added Markdown triggering an existing tracked-file-wide test when included in the merge result. The evidence does not show a later unrelated merge adding the rule that caught it.

## Root cause

`tests/test_decisions.py::test_every_dated_decision_carries_its_id` enforces a repository-wide tracked-Markdown contract: dated user-decision mentions must cite a known decision ID. #229 introduced a new tracked experiment report that described dated user-provided method context in language the detector classifies as a decision, but did not cite a D-id or otherwise avoid the detector's decision phrasing. The targeted #229 tests were scoped to the Flora audit and did not cover this repository-wide cross-file contract. The #244 comment identifies the offending line as `docs/experiments/flora-library-audit.md:15` and reports the test's precise failure.

## How it applies to this repository

- `tests/test_decisions.py`: contract implementation; `scope_files()` uses `git ls-files '*.md'` and excludes `docs/research/`, but not `docs/experiments/`.
- `docs/experiments/flora-library-audit.md:15`: triggering dated phrase, added in #229.
- `docs/decisions.md`: authoritative decision-ID registry consumed by the test.
- `docs/agents/WORKFLOW.md`: existing workflow reference for verification/review expectations; possible place to consider a future proposal, not changed here.
- PR evidence: [#229](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/229), [#244](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/244).

## Proposed next tasks

1. **Evaluate merge-result contract-test gate for PR review** — Prototype/recommend running repository contract tests on a temporary merge result of current `origin/main` and the PR head, with the precise input/expected output: `origin/main` + PR branch containing a new Markdown file with a dated decision statement but no `[D<n>]` -> `tests/test_decisions.py::test_every_dated_decision_carries_its_id` fails before merge; compliant file -> passes. Value **high**, effort **M**. Proposal only; this card changes no hooks, CI, or procedure.
2. **Add a focused cross-file regression fixture for tracked Markdown additions** — Design a test-level fixture that makes the tracked-file discovery context explicit. Input: a newly added tracked Markdown file containing the detector's dated decision wording but no ID -> diagnostic names that file and line; same text with a valid ID -> no diagnostic. Value **medium**, effort **S**. Proposal only; no test changes here.

## Open questions for the user

- Should review verification require the contract-test subset on the exact merge result, rather than relying on isolated branch targeted tests and author-reported suite totals?
- Should dated method/source attribution such as the Flora note be exempted/phrased differently, or should it continue to require a D-id? This report does not choose a policy.

## Sources

- **Verified directly:** GitHub PR/API metadata and commit graph for [#229](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/229) and [#244](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/244); Git object checks of the recorded base, merge-base, `tests/test_decisions.py`, and the newly added report. No test suite was run for this research card.
- **PR-comment claims, not rerun here:** [#229 review/evidence comment](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/229#issuecomment-6203302945) and [#244 RED/GREEN comment](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/244#issuecomment-6204813917).
