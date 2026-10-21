# Handoff — 2026-10-21 14:30

Branch: `job/vyatskaya-tow02-midpoly` · Commit: `3356de5` · Worktree: `C:\Users\artsafro\.AGR-DigitalTwin_pilot` · Job: `vyatskaya-tow02`
Transcript: `C:\Users\artsafro\.AGR-DigitalTwin_pilot\logs\transcripts\job-vyatskaya-tow02-midpoly-pr392-3b2419ea-6c25-47a5-9939-a7c341d40f06.jsonl`

<!-- Written by /handover (.claude/commands/handover.md), read by tools/hooks/session_context.py and /takeover.
Keep the `Branch:` line as is (the hook parses it). Facts only, no history: git log and the pull requests hold
that. The whole file stays under 7000 characters so the SessionStart hook passes it in full. Empty section: "-". -->

## Where we are

Goal: tower TOW02 (ул. Вятская вл. 47–49) mid-poly master → textured → NPM, OKS 013 [D156]. PR #392 (mid-poly master)
is merged into `main`. Commit `3356de5` (not pushed, no PR yet) adds the texturing and QA scripts:
`texture_atlas_blender.py` (source run strips, 31 strips, 77.25 px/m), `clean_glass_blender.py`,
`build_review_fixes_blender.py`, `fix_overlaps_blender.py`, `join_export_blender.py`, `xview_check.ms`.
Current result: `jobs/vyatskaya-tow02/outputs/build-v025/tow02_tex.blend` and joined
`outputs/export-v004/SM_Vyatskaya_Vl_47_49_013_Main.fbx` (35 480 faces, 35 368 quads + 112 tris). Verified in Blender on
the joined mesh: Overlapping Vertices 2 mm = 0, 0 mismatched-winding edges, 0 non-manifold; Overlapping Faces 5 mm =
121 pairs, all group F8 (`outputs/xview-v003/`). Numbers, chain and lessons: `jobs/vyatskaya-tow02/STATE.md`.

## In progress

- Local state outside git (keep, git-ignored): `jobs/vyatskaya-tow02/outputs/` — builds v002..v025 (v020–v022 and
  export-v003 superseded, marked `superseded.json`), exports v001..v004, review data `review-v001/` (the atlas script
  reads `review-v001/windows/runs_typed_xy.json`), QA `xview-v001..v003/`, user's Max glass `max-v001/`.
- Open apps: the user's 3ds Max 2024 `pravki2/scene.max` (PID 85072, unsaved, user's collapse test) — never touch.
  A hung 3ds Max PID 72172 (no window, not ours) — the user said leave it. Blender: none of ours.

## User decisions not in the code

- Max QA scope: only Overlapping Faces (0.005 m) and Overlapping Vertices (0.002 m) matter (user 2026-10-21).
- Overlap fixing: no deleting, prefer no cutting — embed or move parts so parallel faces are ≥ 6 mm apart; cut/weld
  only coincident points (user 2026-10-21). Applied in `fix_overlaps_blender.py` / `build_review_fixes_blender.py`.
- Roof boxes stay hollow as in the source (user 2026-10-21).
- Flat window = 1 quad, bends keep segments, 90° corner = 2 quads on one edge (user 2026-10-21, in code).

## Waiting for the user

- F8: 69 step strips < 6 mm at 8 ring joins (121 overlapping face pairs). Option A (snap upper wall + cut both walls
  so they share points; needs implementing in `build_body_blender.build_stack`) or B (6.5 mm ledge). Recommended A.
- Basket posts are hidden 7 mm behind the glass after the fixes; keep, or move the glass ~13 mm inward (> 1 cm).
- 12 bowtie vertices created by the top/top_glass seam weld at 65.4 (3ds Max splits them → coincident vertices).
- User re-check of export-v004 in 3ds Max xView; then NPM derivation.

## Next step

Get the three decisions above, apply them as build-v026+ through the same chain, re-check both overlaps = 0.

## Rules broken

- The first xView reading was reported as results although Max had split 6 298 mis-wound edges; corrected after
  comparing with Blender counts. Reveal winding error existed since build-v013 and was not caught by its checks.
- A subagent tried to drive an xView dialog field by a Win32 message; the permission classifier refused it.
- Subagent API network failure (~30 min lost); resumed from its transcript.
- Pre-commit hooks not installed in this clone (`core.hooksPath` unset): `tools/git-hooks/pre-commit` run by hand
  (exit 0); commit identity via `-c user.name/email` (artsafro).

## Open PRs and issues for this task

- #392 Job vyatskaya-tow02 mid-poly master — merged 2026-10-20. Commit `3356de5` needs a new PR at the next task
  boundary.

## Agent trace

- Sessions: `3b2419ea-6c25-47a5-9939-a7c341d40f06`
- Written by: -
- Subagents: none
- Skills: none
- Commands: handover 1
- Hook denials: none
- Retries: none
- Context at handover: 49 % (493k of 1000k tokens)
- Duration: 22 h 37 min (2026-10-20T13:22:22Z - 2026-10-21T12:00:01Z, UTC)
- Commits: `8e0f442..3356de5` (1 commits)
