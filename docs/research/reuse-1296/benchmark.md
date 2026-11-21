# Benchmark specification — reuse and the $10 complete-building target

**Proposed experiment; not executed in #1296. No spend or production asset selection is authorized here.**
The research deliverables are real static measurements; this file is a task specification,
not a fabricated benchmark result. Source of target: Artem's 2026-11-13 statement in
[#1296](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1296): for $10 analyze
sources, model VPM and NPM, texture them, and pass all checkers on a cheaper model.

## Track A — first, repeatable reuse microbenchmark (better supported than brick seams)

**Task:** derive NPM OKS from a frozen approved mid-poly master and approved texture spec;
produce atlas, export, independent readback, xView and applicable NPM diagnostics. Existing
`dt derive atlas` and `dt derive npm` make this a comparison of reuse versus one-off scripting,
not a speculative brick-algorithm implementation. It does not claim construction from sources
or completion of the full $10 target. No UCX in NPM.

### Immutable packet / prerequisites

Operator selects a complete, already accepted KPP1-sized building snapshot (or another
approved source-equivalent object). **Do not automatically use historical KPP1 v002 as a
full-pass oracle**: STATE.md has deferred metadata, Ground and manual gates. Before launch:

- manifest of approved source drawing/album pages, geometry master, texture spec, map files,
  object/coordinate metadata, exact accepted PartsList/Gate-1 scope and reference exports;
- every path/size/SHA-256, provenance, units and version; copy originals, never move;
- frozen `TASK.md`, `job.yaml`; `passport.json` for AGR Tools route, equivalent D247 facts otherwise;
- numeric module/phase/joint dimensions, materials, atlas size/padding and protected geometry/IDs
  supplied by the packet; no “like KPP1” without measured values;
- reviewer-owned source-to-output accounting and visual references; acceptance-specific tolerances
  cited from current area sheets/decisions, not selected by the evaluated model;
- locked code commit, dependency lock, Python/Blender/OS versions and checker versions; frozen
  evaluator/checker/spec/tolerance bytes; new isolated worktree/output root per attempt.

Incomplete packet = **not ready**, not a failed model run and not a guessed source value.
The operator validates the reference with the same checks before using it as a positive oracle.

### Arms and fair execution

Compare **Claude**, **Codex**, and one **cheaper model** (Kimi recommended for first trial;
DeepSeek alternative). Cursor is a driver, not a model: record the actual model/version/provider
behind it. Do not choose exact versions or credentials in this research task.

For each model run two independent arms, with fresh context and identical packets:

1. **Baseline:** today's source entry/router and available tools, no candidate route handed in;
   do not force code writing or hide existing tools to inflate savings.
2. **Reuse:** the NPM/OKS route plus a short command catalog of **actually installed** tools;
   before `agr` exists use `dt derive` and the explicit current commands, never fake shell output.

Same shell/file permissions, no access to other attempts/known-answer solution, no mutable user
DCC, no prior model memory. Randomize arm order and record cache state; cold runs are the primary
comparison, warm-cache runs separate. Start with one paired run per model; propose three pairs
only after budget approval. No automatic retry to replace an unsuccessful result.

### Done / failure

- New atlas + NPM FBX + report, exact source/face/material disposition, geometry/IDs preserved
  except permitted profile derivation, correct naming/units/transforms/embedded textures;
- independent clean-process readback of **published exports**, topology/UV/materials/transforms,
  xView, applicable NPM validator stages; source/parts/outputs hashes bound to receipts;
- one result/reference comparison or opened scene path for Artem, no extra render iterations;
- reviewer checks exact exported files, not the producing script's own success marker;
- mandatory fail/review/not_run/missing checks remain **incomplete**, never pass;
- reported node QA is separate from manual architectural acceptance and delivery publication.

Safety evaluation: empty/partial/unsupported input, NaN/inf, threshold boundaries, unmapped
materials, duplicate/conflicting source entries, aliased input/output/report/temp (case, relative,
hardlink/junction), changed source/parts, stale receipts, interrupted/unknown write outcome and
preexisting temp files. Expected: nonzero/refusal without touching inputs or claiming a pass;
reconcile before any retry. Mutations use isolated synthetic packet copies and are **not** real
production evidence. Record each class and actual witness result, not just “guards exist”.

## Track B — the full $10 target (not replaced by Track A)

**Task:** from the authorized architectural sources, construct one complete OKS mid-poly master,
derive both VPM and NPM, texture, package and pass **every applicable checker plus manual gate**.
Inputs add source schedules/openings/levels/material legends, georeference/address/district/
required GeoJSON facts, both-profile references, and any explicitly required site package inputs.
Do not claim a building-only NPM archive satisfies a whole-project Ground requirement.

Follow all eight TASK_TO_MODEL gates in order: inputs → user-confirmed parts → operations →
budgets → exported-file readback → report → user visual acceptance → final SINTEZ. UCX belongs
to the VPM building, not the NPM. Final AGR Tools-native check waits for a separately available
Max slot; Blender does the geometry work in the meantime. A wait is not a pass or permission to
interrupt Artem's render. If a complete mandatory checker is unavailable within the attempt,
result = **incomplete**, with measured completed stages, remaining cost and exact blocker.

Budget objective: **actual paid API spend <= $10 for the complete cheaper-model attempt**,
including intake/retries/subagents/failed calls and any paid vision/OCR services. Price table
snapshot and provider invoices/usage counters required. Record taxes/credit rounding and FX
separately. Stop before a call whose reserved maximum cost would exceed remaining budget;
reserve output/reasoning allowance rather than discover overspend afterwards. If the provider
cannot bound billing, stop as budget-unverifiable. No free fallback provider that hides spend.
Claude/Codex subscription comparisons record tokens + actual cash if available; **subscription
quota is not converted into invented dollar cost**. Approval must specify comparison-arm budgets;
$10 is not assumed to cover three models times two arms times repeats.

Success requires both completed deliverables, correct materials/source fidelity, all mandatory
checks measured pass and both human gates, within cap. Correct artifact but cap exceeded = quality
pass / budget fail, not target achieved. Budget stop = failed budget objective or incomplete stages,
not zero-cost success. Human/Max wait wall time is counted and separated from active compute.

## Optional seam probe, only after source/algorithm approval

“Brick seams on a typical floor” is **not** the primary benchmark: inventory found related
cassette/sandwich/UV code, not a dedicated brick generator or measured brick-only session.
If selected later, freeze one source-defined floor/facade, course/bond, module, joint width,
phase zero, openings and protected silhouette/IDs. Oracle independently measures course/joint
counts, phase at corners/openings, physical and pixel seam width and unchanged dimensions;
new seams appear only where the source requires them. No arbitrary numeric defaults are supplied
here; that would make a model/data decision without Artem. Run the same metrics/arms/budget ledger.

## Measurements and scorecard (all arms)

Retain native transcript and billing logs, not synthesized Claude events for Codex/Kimi.
Unknown telemetry fields = `not_measured` with reason; missing costs cannot prove a budget pass.
CSV row per attempt:

```text
attempt_id,track,arm,provider,model,model_version,driver,source_manifest_sha256,code_commit,tool_catalog_sha256,checker_versions,start_utc,end_utc,wall_seconds,active_seconds,human_wait_seconds,dcc_wait_seconds,input_tokens,cached_input_tokens,output_tokens,reasoning_tokens,billed_usd,billing_source,tool_calls,dcc_calls,repeated_calls,failed_calls,new_code_files,new_code_lines,modified_code_lines,config_lines,render_count,readback_count,mandatory_pass,mandatory_fail,mandatory_review,mandatory_not_run,user_acceptance,quality_status,budget_status,overall_status,artifact_manifest_path
```

- Wall time from first source read to final verified handoff, including setup, retries and waits;
  active time and compute/DCC/human wait measured separately (do not sum overlapping clocks).
- Token categories use provider meanings, with overlap documented; record billed total if separate.
  Output-only historical savings estimates in report.md are not this total.
- Count calls from actual tool events, classify repeat/failure using #1273's published heuristics;
  record false-positive limits (identical reads after writes can be necessary).
- New/modified executable lines from retained initial/final Git trees and untracked/ignored files,
  including scratch-generated Python/MAXScript/shell; report config/docs separately. No gaming by
  writing scripts outside Git, generating a giant inline `python -c` or renaming code as config.
  Record inline executable payload lines too. Existing reused LOC is not new LOC.
- Hash frozen evaluator/source/config inputs before/after; any unauthorized change invalidates the
  attempt even if checks are green. Snapshot-only integrity cannot detect edits restored between
  snapshots; retain the transcript and use evaluator-owned read-only inputs where available.
- Archive all failed attempts and raw reports; versioned regrades never overwrite native evidence.
  Large binaries go to `G:/Мой диск/AGR-evidence/1296-reuse-benchmark/<attempt>/` + `SHA256SUMS.txt`
  (fallback `C:/x/t_f7f43daf/evidence/<attempt>/` pending transfer), never Git/LFS.

Primary comparison: paired delta in wall/active time, total reported tokens and new executable
files/lines, **conditional on identical quality gates**. Publish individual failures/incomplete
runs alongside medians; no cherry-picking. Track A goal: reduce one-off executable code toward
zero while preserving output. Track B goal: the complete cheaper-model result within $10.
No minimum percent speedup is invented before pilot variance is known.

## Questions for Artem

1. Freeze which accepted building/master/source packet, and is its Gate-1 approval reusable for Track A's exact scope?
2. Approve paired baseline/reuse Track A first, then the separately authorized full $10 Track B?
3. Which exact cheaper-model API and comparison cash caps may be used? Recommendation: Kimi first, no production run or spend until authorized.
