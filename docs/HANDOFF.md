# Handoff — 2026-10-20 15:00

Branch: `main` · Commit: `2fd3b2e` · Worktree: `C:\Users\artsafro\agr-pilot\AGR-DigitalTwin (local; shared main snapshot)` · Job: `VATUTINO-SITE`
Transcript: `-`

<!-- Written by /handover (.claude/commands/handover.md), read by tools/hooks/session_context.py and /takeover.
Keep the `Branch:` line as is (the hook parses it). Facts only, no history: git log and the pull requests hold
that. The whole file stays under 7000 characters so the SessionStart hook passes it in full. Empty section: "-". -->

## Where we are

Goal: a repository from which any agent (Claude Code, ChatGPT, Codex) can model a digital-twin task by the rules.
The local Kanban board (orchestrator repo `hermes_kanban`, not this one) runs the work; this file records results.
Merged into main since the 09:10 handoff: site placement #344 (#296), Flora NPM light variants #362 (#347),
Ground v003 map binding #368 (#340), kernel invariants quad_dominance #354 (#345), texel_ready #356 (#346),
xview_overlaps #380 (#370, D152), procedure playbook #363 (#351), asset store #372 (#350, D151 source-only),
eval receipt check `dt evals --check-receipt` #375 (#302), local CI receipt #376 (#318), #283 adoption #374,
research #280 #367 #379 #383, improves #364 #366 #382, hypothesis reports #357 #360 #378 #381.
Verified: full non-DCC suite on `c2c9007`: 7676 passed, 2 failed, 15 skipped - both failures are
`tests/qa/test_orientation_scaling.py::test_orientation_real_size_budget[box-10.0|slivers-5.0]`, the known
load-sensitive wall-clock budgets of #361 (they fail on main without these changes too).
**Main is red** on `98eead4` (batch #382 #364 #380 #372 #363 #381 #378): 7995 passed, 1 failed -
`tests/test_task_to_model.py::test_repository_walks`: #363 pins sha256 of live source files (`invariants.py`,
`build_ground.py`) as gate evidence, #380 / #368 changed them. Repair issue #387 (card running); merges paused.
CI is not run (billing lock, D122); local receipts only. Visual acceptance of #344 / #362 is still Artem's.

## In progress

- #371 Ground v015: quad-dominant, one material ID per texture (Multi/Sub), xView 0.002 / 0.005 = 0 (D152).
- #369 Flora texture diagnosis (PR #377, NOT accepted by Artem): per-island UV-vs-atlas-pixel check. Rule (user
  2026-10-20): a UV island on a sprite covers 80-95 % of it; NPM whole-plant planes cover most of the image or
  slightly more (opacity edges not cut); continuous bark strips are checked by containment (>= 95 % of the island
  on bark pixels), not coverage. Calibrate on the originals, then route per species: rebind original atlas /
  regenerate atlas under the UV / re-unwrap; the fix goes into a follow-up issue.
- #361 perf lane: wall-clock budgets move to a `perf` marker out of the default suite (DeepSeek lane card).
- #337 refresh of PR #252: two dated backfills for the 2026-10-19 Ground decisions (relief TIN cuts only where
  > 1 cm, issue #295 comment 6265799957; steep-layer local raise 5-20 mm, comment 6274902891).
- #348 visual review loop (PR #373, review round 1 changes needed).
- Outputs outside git under `C:/x/` (Ground v014 `C:/x/t_d94665f2/ground_v014/`, Flora `C:/x/flora-library/v003/`,
  light variants `C:/x/flora-light/v001/`, review scenes `C:/x/review/2026-10-20/` + `pending.json`).

## User decisions not in the code

- Deliverables (user 2026-10-20, D152 on main): quads, MatID per texture, xView-clean - Ground v015 must meet it.
- #298 site assembly waits for #371 and #369; then re-placement with the #347 light Flora (~166 200 tris), not
  the #296 scene (220 520 > 180 000).
- #82 terrace parapets: card archived, D065 stays (one parapet thickness per building).
- #248 / #56 / #314: parked by Artem.

## Waiting for the user

- #353 L4: paths of the first real building (source, delivered FBX, album PDF).
- #352 roof-equipment library: project paths to pull meshes from.
- #350: one-time Google Drive login on this PC.
- Visual acceptance: Ground v014 and Flora v003 review scenes in `C:/x/review/2026-10-20/`, #344 placement, #362.

## Next step

Repair red main (#387), then Ground v015 (#371) and the Flora UV verdict (#369), then #298 assembly with light Flora, then L4 (#353).

## Rules broken

- Merge batch #363 + #380 / #368 together without an integration run between them turned main red (#387).

## Open PRs and issues for this task

- PR #377 (#369) rework after Artem's review; PR #373 (#348) changes needed; PR #252 (#138) refresh by #337,
  needs a new review on its new head; PR #248 parked.
- Issues waiting: #353, #352 (`waits-artem`); #246 parked with #45.

## Agent trace

- Sessions: not measured (no transcript)
- Written by: Hermes orchestrator (Telegram session 20261020_091940_f745c6a8, claude-opus-5-5)
- Subagents: not measured (no usage log, no transcript)
- Skills: not measured (no usage log, no transcript)
- Commands: not measured (no usage log, no transcript)
- Hook denials: not measured (no transcript)
- Retries: not measured (no transcript)
- Context at handover: not measured (no transcript)
- Duration: not measured (no transcript)
- Commits: `eed5074..2fd3b2e` (119 commits)
