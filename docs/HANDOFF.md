# Handoff — 2026-10-20 09:10

Branch: `main` · Commit: `eed5074` · Worktree: `C:\Users\artsafro\agr-pilot\AGR-DigitalTwin (local; shared main snapshot)` · Job: `VATUTINO-SITE`
Transcript: `-`

<!-- Written by /handover (.claude/commands/handover.md), read by tools/hooks/session_context.py and /takeover.
Keep the `Branch:` line as is (the hook parses it). Facts only, no history: git log and the pull requests hold
that. The whole file stays under 7000 characters so the SessionStart hook passes it in full. Empty section: "-". -->

## Where we are

Goal: a repository from which any agent (Claude Code, ChatGPT, Codex) can model a digital-twin task by the rules.
The local Kanban board (orchestrator repo `hermes_kanban`, not this one) runs the work; this file records results.
Kernel plan C1-C7 of `docs/grill/modeling-architecture-2026-10-16.md` is on main: bpy headless probe, PartsList
schema, invariants, operations keep / embed / primitive_box / to_opacity_plane / rebuild_by_contour (#341), C5 album
PDF reader (#317), C7 context diet (#335, AGENTS.md reading list + generated `docs/PROJECT_STATE.md`), FBX structure
reader -> PartsList (#342). Site slice Vatutino: Ground (#295/PR #308, v014 NPM/VPM/UCX), UCX for Ground (#326/#334),
ground recipe textures (#319/#329, v002) + CLI fix (#330/#336), MAF selection (#313), placement engine (#316), Flora
VPM identity (#305/#328), map rebind tests (#312/#331), dt CLI tests (#343). Old PRs #266, #260 merged.
Verified: full non-DCC suite on main `eed5074`: 6936 passed, 15 skipped, 60 deselected, 0 failed (`kpi/manual_merge_20261020e.json` in hermes_kanban); the previous
batch on `3c7c54a`: 6794 passed. CI is not run (billing lock, D122); local receipts only.

## In progress

- Board cards (local PC): #296 MAF + Flora placement (PR #344, review round 2 changes needed), #340 Ground
  texture binding (v003 with CurbGarden / Stairs recipes), #345 quad_dominance invariant, #346 texel_ready
  invariant, #347 Flora NPM light variants, #348 visual review loop in 3ds Max (C:/x/review + pending.json),
  #350 asset store disk + Google Drive, #116 suite wall time round 2, #318 C6 CI receipt (4 tests in
  `tests/test_agent_trace.py` fail only inside the full receipt run, pass alone), #337 refresh of PR #252.
- Outputs live outside git under `C:/x/` (Ground `C:/x/t_d94665f2/ground_v014/`, textures
  `C:/x/vatutino-ground-textures/v002/`, Flora library `C:/x/flora-library/v003/flora-library-v003.max`).

## User decisions not in the code

- Gate 1 of #296 (user 2026-10-20): out-of-site Alnus/Malus not placed; Pinus mugo by plan points (106); six
  species without a model + Salix not placed; substitutions 1->101, 3->120, 4->115, 6->105, 7->103, 9->205,
  12->204, 17->224 accepted; height-only check +/-20 %; Flora NPM overrun 118 774 / 70 000 recorded (light NPM is
  #347); 2 urns 1 cm outside the Ground v014 cut-out not placed (bound to v014 only).
- #295 (user 2026-10-20): 12 vertices on ~81 deg faces with normal gap up to 36.9 mm accepted as an explicit
  exception list; the 20 mm gate stays for the rest.
- #319 (user 2026-10-19): tile scale error up to 1 % allowed; corrected output in a new version folder.
- Procedure principle (user 2026-10-20): gates strict, path free - an agent may deviate (workaround, new tool) if
  it logs the deviation and passes the same gates (#351).
- Visual review in 3ds Max; assets on local disk + Google Drive links (user 2026-10-20, #348, #350).
- MAF modelling of items without a model is deferred (user 2026-10-19).

## Waiting for the user

- #353 L4: paths of the first real building (source, delivered FBX, album PDF).
- #352 roof-equipment library: paths of the projects to pull meshes from.
- #350: one-time Google Drive login on this PC (Drive for desktop or rclone).
- #82 terrace parapets: a real object with different parapet thicknesses.

## Next step

Finish the site chain (#340 -> #296 -> #298) and the L4 preparation cards (#345-#351), then L4 (#353).

## Rules broken

- -

## Open PRs and issues for this task

- PR #344 (#296 placement) — review round 2, changes needed.
- PR #252 (#138 decision ids) — conflicting with main again, refresh card running (#337).
- PR #280 (research on #229) — no review; archive decision pending.
- PR #248 (#56 checker) — parked by the user with #314.
- Issues waiting: #353, #352, #350 (`waits-artem`); #302, #246 `needs-info`; hypotheses #281, #283.

## Agent trace

- Sessions: not measured (no transcript)
- Written by: Hermes orchestrator (Telegram session 20261019_095056_2dd1dd02, claude-opus-5-5)
- Subagents: not measured (no usage log, no transcript)
- Skills: not measured (no usage log, no transcript)
- Commands: not measured (no usage log, no transcript)
- Hook denials: not measured (no transcript)
- Retries: not measured (no transcript)
- Context at handover: not measured (no transcript)
- Duration: not measured (no transcript)
- Commits: `eed5074..eed5074` (0 commits)
