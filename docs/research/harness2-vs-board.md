# Harness2 vs the AGR board loop

Research note for issue #714. Nothing here is applied to the board, skills, or crons.

## 1. Sources and versions

| Source | Version recorded |
|---|---|
| Paper | arXiv:2610.14224 **v1** only. Submitted Fri, 9 Oct 2026 18:34:25 UTC. Abs page `og:url` is `https://arxiv.org/abs/2610.14224v1`. HTML read: `https://arxiv.org/html/2610.14224v1`. No v2 on the abs submission history (checked 2026-10-26). |
| Harness2 repo | `https://github.com/google-research/harness2`, shallow clone `C:/x/t_99b4fb0c/harness2`, `HEAD` `1cfe254e8d25b15f37048c3730134686abe60335` (2026-10-13, "Fix arXiv link"). Not installed. |
| hermes_kanban | `C:\Users\artsafro\hermes_kanban`, `HEAD` `16e5785f2ed8f35d157a3199021aef6caf11a30b` (2026-10-25, "vacation: cron changes recorded"). |
| KPI snapshot | `kpi/kpi.json` `generated` 2026-10-26 18:04, board `agr-pilot`, 584 cards, 581 done. |
| Readiness snapshot | `kpi/readiness/2026-10-26_1734.json`, `overall` 47.0. |
| This note | 2026-10-26. |

PDF bytes were not parsed separately. Numbers below are from the v1 HTML (sections, tables, figures as rendered there).

## 2. Harness2 loop, step by step

Harness2 keeps model weights frozen and edits the harness around the model (§2.1). The execution harness has eight file-level components: system prompt, guardrails, memory, skills, tool guidance, scripts, subagents, middleware plugin (Figure 2; README "Harness components"). Each task starts from a common execution harness `H0`. There is no ground-truth label during the edit (§2.1, §3.1).

1. **Reference execution.** Run the current harness on the task. The record is trajectory plus deliverable. It shows behavior, not correctness (§2.2.1, "Propose").
2. **Propose.** From the task, current harness, reference, history, and the improvement library, write two executable candidates: an invariant edit (planning, tools, context, delegation) and a domain edit (knowledge and constraints of this task). Task-specific facts must be checked against this task's evidence (§2.2.1). Repo: `harness2/core/prompts.py` `propose`, called from `harness2/core/recursion.py` `run_parallel` (labels `INV` / `DOM`).
3. **Probe.** Execute each candidate on the same task, same model and environment. The contrast says whether the edit changed the targeted behavior, left it, or regressed it. The paper states that stochasticity and shared model bias limit how reliable that evidence is; the contrast does not verify task correctness (§2.2.1, "Probe").
4. **Compose.** Read the reference, both diffs, and the probes. Merge supported edits, revise conflicts, take one candidate, or keep the current harness. Each decision is tied to an observation, not a presumed score. Then execute the successor (§2.2.1, "Compose"). Invalid proposals get one retry, then inherit the current harness (`recursion.py` module docstring; `kept_base` on `Stage`).
5. **Task-level recursion budget `k`.** Parallel: `k` references, `k` invariant and `k` domain probes, then `k` independent compositions (Equation 2, Figure 4a; `run_parallel`). Sequential: `k` chained contrastive steps, each seeing the previous harness and accumulated history (Equation 3, Figure 4b; `run_sequential`). At `k=1` both forms are the single step and skip selection (§2.2.2). `recursion.py` says each mode schedules `4k` rollouts and `3k` improvement stages.
6. **Final selection (`k>1`).** An agent compares anonymized deliverables to the request and returns an existing output. It does not see the originating harness and does not write a new deliverable. Selection does not revise the harness. The star on `H*` means adopted, not proven optimal (§2.2.2). At `k=1` the code delivers the single final without a selector session (`harness2/core/selection.py`, "trivial pool").
7. **Reflect.** After the deliverable, review the full improvement record. Keep a lesson only when an execution contrast supports it. Picking an output does not by itself make the lesson transferable (§2.3).
8. **Update the improvement harness.** Store the adopted harness plus `EXPERIENCE.md` (situation, lesson, evidence) and an index (Equation 4, §2.3). The repo writes an entry only when `cue`, `lesson`, and `evidence` are non-empty strings (`library.py` `has_experience`, `Library.add`); otherwise it adds nothing. Layout: `<domain>/INDEX.md`, `harnesses/<task>/harness/`, `harnesses/<task>/EXPERIENCE.md` (`library.py` module docstring).
9. **Next task.** Starts again from `H0`. The library may be reused or adapted inside Propose. It is not copied in as the new execution harness. Stage instructions and the decision rule stay fixed (§2.3, "Reuse in Subsequent Improvement").

Judging against the benchmark rubric is a separate later pass (README "Run a benchmark": `harness2` then `harness2-judge`). Main tables use that external score; the edit loop itself does not (§3.1).

## 3. Mapping

| Harness2 step | Our step | Implementing file | Gap |
|---|---|---|---|
| Frozen executor, editable harness files | Workers are profiles (SOUL, skills, card body). Product code changes land as PRs. | `profiles/*/SOUL.md`; `skills/agr-kanban-orchestration/SKILL.md` "Facts" | We edit both the worker instructions and the product. Harness2's measured object is the harness, not the task repo. |
| Reference run of current harness | A card runs once in a worktree from current `main`. | `docs/pipeline.md` "Card flow"; `skills/agr-kanban-orchestration/SKILL.md` (worktree from primary HEAD) | No saved reference trajectory of the unchanged worker harness on that same card before an instruction edit. |
| Two scoped proposals (invariant, domain) | `dt-hypothesizer` files one falsifiable claim from a merged report, with metric, threshold, real input, and a `Risk` prior. | `profiles/dt-hypothesizer/SOUL.md`; `night_queue.json` `hypothesizer`, `hypothesis_batch` 6, `max_hypothesis_tests` 2 | One claim per issue, not two executable harness diffs probed on one task. |
| Matched probe | Experimenter takes a baseline on the same inputs, then one prototype under `experiments/`. | `profiles/dt-experimenter/SOUL.md` (siblings: `dt-experimenter-codex`, `dt-experimenter-cursor`); `night_queue.json` `experiment_workers` | Baseline-vs-prototype exists for product methods. It is not a pair of harness-file probes. |
| Selective compose, may keep current | Confirmed issue becomes `Adopt: #N`, implementing the issue's "If confirmed" scope. Reviewer can send the PR back. | `scripts/agr_refill.py` `ADOPT_BODY`; `profiles/dt-reviewer/SOUL.md`; `profiles/COORDINATION_RULES.md` rule 30 | Adopt implements a pre-written scope. It does not merge two diffs from a behavioral contrast, and it does not record `kept_base`. |
| Parallel / sequential `k` on one task | Several cards run at once (`max_active`). A card retries (`docs/pipeline.md`: `--max-retries 2`). Review rounds send the same PR back. | `night_queue.json`; `docs/pipeline.md`; `profiles/dt-reviewer/SOUL.md` | Parallelism is across tasks. A review round edits the PR, it does not chain a new harness plus the prior execution record. |
| Anonymized deliverable selector | Reviewer sees the diff, the author, and the tests. | `profiles/dt-reviewer/SOUL.md` | Not a blind pick among deliverables. |
| Evidence-gated library; next task from `H0` | Seen-report list, coordination rules, moltbook lessons, KPI grades. The next card starts from `main`, which already contains merged adopts. | `kpi/hypothesis_state.json`; `profiles/COORDINATION_RULES.md`; `moltbook/lessons.md`; `profiles/dt-evaluator/SOUL.md` (writes `kpi/evaluations/`, `kpi/grades.jsonl`, and rules) | Lessons are prose and rules. There is no full adopted instruction tree plus `cue`/`lesson`/`evidence` that is refused when evidence is empty. Merging to `main` inherits the execution change. Harness2 forbids that inheritance (§2.3). |
| Planner of what to try next | `night_queue.json` `"planner": "dt-worker-codex"`. Self-queue items. Evaluator writes `Plan:` cards only if `planner` names it. | `night_queue.json`; `self_queue.json`; `skills/agr-kanban-orchestration/SKILL.md` (hypothesis phase runs before the planner); `profiles/dt-evaluator/SOUL.md` | Planner picks tasks. It does not propose harness diffs. |
| Readiness assessor | Every 4 h, a card scores product hand-off readiness and writes one JSON file. Default assignee `dt-reviewer`. | `scripts/agr_readiness_card.py`; `docs/readiness_rubric.md` | Scores the pilot repo (47.0 on 2026-10-26 17:34). It does not score harness edits. |

`docs/pipeline.md` still describes the planner as Claude Code on the user's PC and a three-role pilot. The live loop is the night queue plus `agr_refill.py`. This note follows the live files.

## 4. What they do that we do not

Cited gains are on their benchmarks (WorkBuddy-Bench, JobBench, LAB), with Gemini 3.5 Flash or GLM-5 under OpenCode or Codex, editor Claude Opus 4.8 by default (§3.1). They are not measurements of this board.

| Claim | Number | Where |
|---|---|---|
| Largest one-step WorkBuddy average vs that config's base | +11.5 (64.2 to 75.7), GLM-5, OpenCode | Table 1; §3.2 |
| Largest one-step JobBench vs that config's base | +4.5 (31.5 to 36.0), Gemini, OpenCode | Table 2; §3.2 |
| Largest one-step LAB Partial vs that config's base | +11.8 pp (59.6 to 71.4), GLM-5, OpenCode | Table 2; §3.2 |
| One step, all four configs, all three benchmarks | improved vs base; LAB Partial exception: Meta-Harness leads Gemini+Codex | §3.2 |
| Drop the library (`k=1`, Gemini, OpenCode) | −3.1 WorkBuddy, −1.8 JobBench | Table 3; §4 |
| Drop invariant/domain scoping | −2.9 WorkBuddy, −3.7 JobBench | Table 3; §4 |
| Drop composition (keep the favoured probe only) | −1.6 WorkBuddy, −1.9 JobBench | Table 3; §4 |
| Parallel `k=5` on top of the one step | +2.9 to +3.9 WorkBuddy, +3.0 to +4.2 JobBench, +2.6 to +6.7 pp LAB Partial | §3.2 |
| Parallel vs `k` on WB-code / WB-office | 76.5 to 80.8 code; 79.5 to 83.4 office, `k` 1 to 5 | Figure 5; §4 |
| Tokens, Gemini+OpenCode, `k` 1 to 5 | gain over base 4.5 to 7.5 JobBench, 5.1 to 8.4 WorkBuddy | Figure 6; §4 |
| No reference, no probes, no library | Code 73.4 to 63.2; Web 69.9 to 65.0 | Figure 7 left; §4 |
| Library from `k=5`, no further probe | +0.9 / +4.4 / +5.1 Code, Web, Office | Figure 7; §4 |
| JobBench library transferred to WorkBuddy | +0.6 / +0.5 / +2.9 Code, Web, Office | Figure 7 right; §4 |
| Same model as editor and executor, OpenCode, `k=2` | five models improve on every benchmark; Opus 5 +3.3 / +5.5 / +3.0; GLM-5 +13.7 LAB | Figure 8; §4 |
| One JobBench case, not a mean | 43.1 to 77.8 | Figure 9; §4 |

- **One contrastive step over the base harness.** Largest one-step WorkBuddy average: GLM-5 + OpenCode, 64.2 to 75.7, **+11.5** points (Table 1; §3.2). JobBench: Gemini + OpenCode, 31.5 to 36.0, **+4.5** points (Table 2; §3.2). LAB Partial: GLM-5 + OpenCode, 59.6 to 71.4, **+11.8** percentage points (Table 2; §3.2). §3.2 also says one step improved every one of the four model–harness pairs on all three benchmarks. On LAB Partial, Meta-Harness still leads for Gemini under Codex (§3.2).
- **Scoped proposals and composition, isolated at `k=1`.** Table 3 (Gemini 3.5 Flash, OpenCode): full Harness2 77.5 WorkBuddy / 36.0 JobBench. Without the library: 74.4 / 34.2 (**−3.1 / −1.8**). Without scoping (two generic editors instead of invariant and domain): 74.6 / 32.3 (**−2.9 / −3.7**). Without composition (pick one probe, do not merge): 75.9 / 34.1 (**−1.6 / −1.9**). §4 states those drops.
- **More task-level budget.** Parallel `k=5` adds a further 2.9 to 3.9 points on WorkBuddy, 3.0 to 4.2 on JobBench, and 2.6 to 6.7 percentage points LAB Partial, over the single step (§3.2). Figure 5: parallel recursion on WB-code 76.5 to 80.8 and WB-office 79.5 to 83.4 as `k` goes from 1 to 5; both parallel and sequential rise across that range. Figure 6: for Gemini + OpenCode, raising `k` from 1 to 5 moves the gain over the base from 4.5 to 7.5 on JobBench and from 5.1 to 8.4 on WorkBuddy, counting execution and improvement tokens. Both plotted Harness2 points sit on that figure's empirical Pareto frontier (§4).
- **Library that later steps can use without another probe.** Figure 7 left: refining with no reference, no probes, and no library drops Code 73.4 to 63.2 and Web 69.9 to 65.0. A library built at `k=5` then supports **+0.9 / +4.4 / +5.1** on Code, Web, and Office with no further probing. A JobBench library transferred to WorkBuddy one-step refinement: **+0.6 / +0.5 / +2.9** (Figure 7 right).
- **Same model as editor and executor can still gain.** Figure 8, OpenCode, `k=2`: all five models improve on every benchmark. Opus 5: +3.3 WorkBuddy, +5.5 JobBench, +3.0 LAB. GLM-5: +13.7 on LAB (§4). The default setup still uses a stronger editor (§3.1).
- **Keep the base when the contrast does not support an edit**, and refuse a library row with empty evidence (`recursion.py` `kept_base`; `library.py` `has_experience`). Our adopt path implements the confirmed scope (`ADOPT_BODY`). It does not have that refuse-to-store gate.

Figure 9 is one JobBench case (Gemini, OpenCode): baseline score 43.1, composed re-run 77.8, after an invariant guardrail and a domain skill (§4). One task, not a table mean.

## 5. What we already do

- **Hypothesis, then a measured test, then adopt.** Reports on `main` trigger a `Hypotheses:` card, pilot issues labelled `hypothesis`, at most `max_hypothesis_tests` (2) open `Hypothesis: #N` cards, then a verdict, then `Adopt: #N` for a confirmed issue (`skills/agr-kanban-orchestration/SKILL.md`, "Hypotheses"; `scripts/agr_refill.py` around the hypothesis phase and `ADOPT_BODY`; `night_queue.json`).
- **Pre-registered reject rule.** The hypothesizer must fix a metric and a threshold that would reject the claim, name a real project input, and mark at least one risky claim per batch (`profiles/dt-hypothesizer/SOUL.md`). That is stricter than Harness2's probe, which is not a correctness verdict (§2.2.1).
- **Baseline before a prototype.** The experimenter runs the current implementation first and writes numbers (`profiles/dt-experimenter/SOUL.md`).
- **Independent review.** `dt-reviewer` runs affected tests and does not edit the branch (`profiles/dt-reviewer/SOUL.md`). Harness cards need an acceptance table (COORDINATION_RULES rule 21, cited there).
- **Separate product assessor.** Readiness is a weighted score with cited evidence, not a vibe (`docs/readiness_rubric.md`, `scripts/agr_readiness_card.py`). Latest file: overall **47.0**.
- **Routing grades.** `dt-evaluator` grades workers from runs, not from impressions (`profiles/dt-evaluator/SOUL.md`).
- **Caps.** `experimental_slots` default 2 shared by hypothesis-test, Adopt, and autoresearch (`SKILL.md`). Night caps in `night_queue.json` (`dt-hypothesizer` 6). Pipeline `--max-retries 2` (`docs/pipeline.md`).

Snapshot from `kpi/kpi.json` (2026-10-26 18:04), done cards only:

| Slice | Count | Notes |
|---|---|---|
| All done | 581 / 584 | First-pass 192/581 (33.0%). Mean review rounds 0.33. Mean impl runs 1.81. Mean minutes 37.6. |
| `kind: issue` | 374 | First-pass 110/374 (29.4%). Mean review rounds 0.39. Mean impl runs 2.03. Blocked runs 186 (0.50 per card). Failed runs 29 (0.08 per card). Impl runs ≥ 3: 85 cards. Review rounds ≥ 2: 30 cards. |
| Title `Hypothesis:` | 18, all done | Mean minutes 13.8. |
| Title `Hypotheses:` | 28 | Batch cards, all done in the scoreboard worker row for `dt-hypothesizer` (`kpi/scoreboard.md`: 28 cards, 28 done, avg 3 min). |
| Title `Adopt:` | 14, all done | First-pass 11/14. Mean review rounds 0.21. Mean minutes 48.9. |
| `kind: experiment` | 13 done | |

`kpi.json` does not store hypothesis labels (`confirmed` / `rejected` / `inconclusive`). 14 Adopt cards beside 18 Hypothesis cards is not a confirm rate.

Live caps that bound any Harness2-style budget (`night_queue.json`, read 2026-10-26): `max_active` 8, `plan_interval_minutes` 45, `max_plans` 20, `roadmap_gate` false, `hypothesis_min_reports` 2, `hypothesis_batch` 6, `max_hypotheses` 5, `max_hypothesis_tests` 2. `experimental_slots` (default 2) is shared by new hypothesis-test, Adopt, and autoresearch cards (`skills/agr-kanban-orchestration/SKILL.md`). A `k=5` parallel step, which `recursion.py` describes as `4k` rollouts, does not fit inside those slots. That is why candidate 3 stops at one extra step.

The useful overlap is the shape of the loop, not the scoreboard. We already separate propose (`dt-hypothesizer`), probe (`dt-experimenter*`), review (`dt-reviewer`), and a product assessor (`agr_readiness_card.py`). We already refuse a hypothesis that has no real input and no reject threshold (`profiles/dt-hypothesizer/SOUL.md`). What we do not do is treat the worker instructions as the thing being probed, keep a contrast against a frozen reference harness, or refuse to store a lesson that has no evidence string. Product merges also mean the next card inherits the last adopt. Harness2's next task does not inherit `H*` (§2.3). Copying their benchmark deltas onto first-pass rate would skip that difference. The candidates below test the missing gates on our cards, with our KPI as the baseline.

## 6. Three candidate changes

None of these are applied. Paper points are their benchmarks. Expected effect on this board is a hypothesis, which is why each row has a stop rule.

Rank is by expected effect against cost: the cheap library first (it matches a measured ablation and our missing gate), the scoped probe second (larger ablation, several extra runs), sequential recursion third (further gain in Figure 5, highest extra cost, and we already re-run cards).

### 1. Evidence-gated experience index for adopts

- **Change.** After an Adopt card is done, write one directory per issue: the instruction or skill diff that was merged, plus `EXPERIENCE.md` with non-empty `cue`, `lesson`, and `evidence` copied from the experiment report. If any field is empty, write nothing (same gate as `library.py` `has_experience`). The next hypothesizer card must cite an index row or write `Library: none`. Do not auto-paste the previous card's SOUL into the next card. Leave `main` inheritance as it is for product code; this index is for worker instructions and hypotheses only.
- **Expected effect.** Table 3: dropping the library costs 3.1 WorkBuddy points and 1.8 JobBench points at `k=1`. Figure 7: a populated library supports later refinement without extra probes; an empty context hurts. Our analogue is repeated hypotheses that do not say which earlier contrast they reuse (`kpi/hypothesis_state.json` is only a seen-path list).
- **Cost.** One short write per finished Adopt, read by the existing hypothesizer card. No extra executor rollout. Low.
- **Metric.** Among hypothesis issues opened during a 15-issue window, the fraction whose body contains `Library: <id>` or `Library: none`, and the fraction that reach an `Adopt:` card.
- **Baseline.** In this snapshot, 14 `Adopt:` cards and 18 `Hypothesis:` cards. No library field exists, so the citation fraction is 0 by construction. Confirm/reject counts are not in `kpi.json`; count labels on the pilot issues when the window runs.
- **Stop.** Stop if, after 15 new hypothesis issues, fewer than 12 have a `Library:` line, or if Adopt-card mean minutes rise above 1.5 × 48.9 (about 73 min) on the adopts in the window. Also stop if a stored lesson has an empty evidence field (the gate failed).
- **How to run.** Add the write to the orchestrator checklist for `Adopt:` completion only, under `hermes_kanban` (not the pilot repo). Compare the next `kpi/kpi.json` Adopt rows with the 14-card baseline. Do not change `night_queue.json` caps for this test.

### 2. One contrastive step (`k=1`) on worker-instruction cards

- **Change.** For a sample of `improve` or `Adopt:` cards whose acceptance is a named test or benchmark command: keep the current SOUL/skill as the reference and run that command once; propose one invariant edit and one domain edit; run the same command on each; compose only edits whose output moved the pre-registered metric and did not fail a named regression check; if neither does, keep the current text (`kept_base`). Do not merge the sample.
- **Expected effect.** Table 3: removing scoping costs 2.9 and 3.7 points; removing composition costs 1.6 and 1.9. That is the largest single-component drop they report, on JobBench for scoping. §2.2.1 warns the contrast is not a correctness proof, so the pre-registered command stays the judge (we already have that; they did not, during the edit).
- **Cost.** High. Their `k=1` step is reference + two probes + successor execution (`recursion.py`: `4k` rollouts at budget `k`). Here that is about four command runs per sample card, against today's one baseline plus one prototype (`profiles/dt-experimenter/SOUL.md`). Hypothesis cards in the snapshot average 13.8 min; four runs can exceed that by a wide margin.
- **Metric.** On 8 sample cards: (a) how often the two probes disagree on the pre-registered metric; (b) how often compose keeps the current text; (c) wall minutes per card.
- **Baseline.** Disagreement rate is unmeasured because we do not run two scoped probes. Time baseline for a short hypothesis card: mean 13.8 min (`Hypothesis:` rows). Issue-card mean impl runs 2.03 is a different population (product fixes), so it is context, not the control for this sample.
- **Stop.** Stop if fewer than 2 of 8 cards show a probe disagreement that changes the keep-or-edit decision, or if more than 4 of 8 cards exceed 3 × 13.8 min (41 min) before compose. Either result means the extra runs are not paying for themselves on this board.
- **How to run.** One manual batch of 8 cards, assignee an experimenter profile named in `night_queue.json` `experiment_workers`, bodies pointing at a copied SOUL under the card worktree only. Record the four command outputs in the card summary. Do not edit deployed `profiles/` or `skills/` until a later adopt that this note does not authorize.

### 3. A second sequential step only when the first contrast is flat

- **Change.** Sequential recursion carries the refined harness and the evidence into the next step (Equation 3, Figure 4b). Use `k=2` only when step 1 kept the base or the metric did not cross the pre-registered threshold. Do not run `k=5`.
- **Expected effect.** Figure 5: both forms keep rising from `k=1` to `k=5`; at `k=2` both already beat every plotted baseline at `k=5` on WB-code and WB-office (§4). Figure 6 shows the token cost of a larger `k`. On our board, issue cards already average 2.03 impl runs and 0.39 review rounds, so a blanket second step mostly repeats work we do. The candidate is the flat-contrast slice only: 85 of 374 done issue cards already have impl runs ≥ 3, which is the population that might need a carried evidence step rather than another blind retry.
- **Cost.** Highest of the three. One extra full probe chain on an already long card. Adopt cards already average 48.9 min.
- **Metric.** On 8 cards that were flat after step 1: the pre-registered metric after step 2, and minutes of step 2.
- **Baseline.** Today there is no second harness step. Review rounds (mean 0.39 on 374 issue cards; 30 cards with ≥ 2 rounds) are code-review loops, not Equation 3. Treat the baseline second-step metric delta as 0 until measured.
- **Stop.** Stop if 0 of 8 second steps move the pre-registered metric across its threshold, or if step-2 minutes exceed the step-1 minutes on more than 4 of 8 cards.
- **How to run.** Only after candidate 2 has produced at least one flat card. Chain the second probe in that card's worktree with the step-1 log pasted into the prompt. Cap the batch at 8. `max_hypothesis_tests` stays 2; this test uses those slots, it does not raise them.

## 7. Not verified / limits

- **No v2.** Abs history shows only `[v1]` (9 Oct 2026). If a later version appears, the table numbers here need a re-read.
- **PDF not used.** Figures were read as HTML captions and the surrounding prose. Bar heights that the prose does not state are not quoted.
- **Appendix tables.** §2.1 points at Table 5 (component files) and Appendix H (stage prompts). Those appendices were not copied into this note. Component names used above are from Figure 2, §2.1, and the repo README.
- **Repo vs paper.** `library.py` refuses an entry without `cue`, `lesson`, and `evidence`. The paper's §2.3 says the same policy in prose. Prompt text inside `prompts.py` was not line-audited against Appendix H.
- **Their gains are not our gains.** WorkBuddy, JobBench, and LAB are office, job, and legal tasks scored by their judges (§3.1). This board's product checks are tests, benchmarks, and review. §2.2.1 says probe contrasts do not verify correctness. A +11.5 point cell does not predict first-pass rate on `agr-pilot`.
- **External scores vs the edit loop.** Main-table scores come from benchmark judging after the loop. The loop itself has no ground truth (§3.1, README judge step).
- **Board labels.** Confirmed / rejected / inconclusive counts were not read from GitHub. `kpi.json` has titles and run counts only.
- **`docs/pipeline.md` drift.** Role names there (planner = Claude Code, reviewer model string) disagree with `night_queue.json` (`planner` = `dt-worker-codex`) and `scripts/agr_readiness_card.py` (assessor default `dt-reviewer`). Live files win for the mapping.
- **Not run.** Harness2 was not installed. No board, skill, cron, or queue file was changed. No docs-only lint exists that targets `docs/research/` ( `tests/test_decisions.py` excludes that tree). The suggested `pytest -k "research or docs"` filter also matches product regression tests, which this card says to skip, so it was not run.
