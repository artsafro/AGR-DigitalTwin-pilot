# Handoff — 2026-10-21 18:00

Branch: `job/vyatskaya-tow02-midpoly` · Commit: `fd399e7` · Worktree: `C:\Users\artsafro\.AGR-DigitalTwin_pilot` · Job: `vyatskaya-tow02`
Transcript: `C:\Users\artsafro\.AGR-DigitalTwin_pilot\logs\transcripts\job-vyatskaya-tow02-midpoly-pr515-dda7a500-3c9f-4186-98c9-299703e97a3a.jsonl`

<!-- Written by /handover (.claude/commands/handover.md), read by tools/hooks/session_context.py and /takeover.
Keep the `Branch:` line as is (the hook parses it). Facts only, no history: git log and the pull requests hold
that. The whole file stays under 7000 characters so the SessionStart hook passes it in full. Empty section: "-". -->

## Where we are

Goal: tower TOW02 (ул. Вятская вл. 47–49) mid-poly master → textured → NPM, OKS 013 [D156]. Stage done: our
export-v005 (`outputs/export-v005/SM_Vyatskaya_Vl_47_49_013_Main.fbx`, F8 option A in `build_stack`, no bow-ties)
was finished by the user by hand in 3ds Max and accepted as a base (2026-10-21: "ты неплохо справился с задачей, с
этим можно работать"). Committed `c363f8a` + merge of `origin/main` `fd399e7`; PR #515 open. Case row in
`docs/cases.md` + `docs/agr/case_studies/VYATSKAYA_TOW02_MIDPOLY.md`. Review of the case = issue #514.
QA facts: Blender own check Overlapping Faces 5 mm = 0 was wrong; 3ds Max xView at 0.005/0.002 m = 185 faces / 0
vertices (`outputs/xview-v005/xview_tol_report.jsonl`); independent check 23 pairs. Details: `jobs/vyatskaya-tow02/STATE.md`.

## In progress

- Local state outside git (keep, git-ignored): `jobs/vyatskaya-tow02/outputs/` — builds v002..v030, exports v001..v005,
  QA `xview-v001..v005/`. The user's finished model: `outputs/xview-v005/tow02_ovl23_v001.max` (SHA-256
  `1c4c3a8e…01fddf`) — never overwrite; it replaced our marker scene of the same name. xView helpers in
  `outputs/xview-v005/` (`run.ms`, `open_ovl.ms`, `ovl_pairs_blender.py`).
- Open apps: the user's 3ds Max 2024 PID 85072 (`pravki2/scene.max`, unsaved) and PID 129136 (the finished model,
  the user is working in it) — never touch. The MCP 3ds Max bridge was released (no instance pinned).
- Max 2026 batch instances of other sessions may run (`agr-3dsmax-*` listener logs) — not ours.

## User decisions not in the code

- Max QA scope: only Overlapping Faces 0.005 m and Overlapping Vertices 0.002 m (user 2026-10-21).
- Overlaps: no deleting, prefer moving/embedding ≥ 6 mm; cut/weld only coincident points (user 2026-10-21).
- F8 = option A, basket posts kept hidden behind the glass, 65.4 bow-ties resolved (user 2026-10-21) — in code.
- NPM comes from the user's finished model, not from export-v005 (user 2026-10-21, "базу ты выполнил, я допилил").
- Stop launching DCC runs while the user edits by hand ("хватит запускать, дай поправить", 2026-10-21).

## Waiting for the user

- Confirm that `outputs/xview-v005/tow02_ovl23_v001.max` is the final version for the comparison in #514.
- Merge command for PR #515.

## Next step

Issue #514: compare export-v005 with the user's finished model, lessons with cause classes, then NPM from it.

## Rules broken

- Reported export-v005 as "0 / 0" from the builder's own Blender check before xView; xView at 5 mm found 185 faces.
  Corrected after the independent check and the real xView run; lesson in STATE.md and the case.
- Followed the user's "разрезом" for bow-ties only in spirit: the builder moved 12 glass corners 3 mm instead of
  cutting (a cut leaves coincident vertices); reported to the user.
- Launched a second 3ds Max that stopped at "Startup Failure Detection"; the user had to click it.
- Independent checker could not write evidence files (read-only subagent hook); numbers only in its report.
- Local tests not run: this clone lacks `shapely` / `dt_ai` install; CI on PR #515.
- Pre-commit hooks not installed (`core.hooksPath` unset): `tools/git-hooks/pre-commit` run by hand (exit 0);
  commit identity via `-c user.name/email`.

## Open PRs and issues for this task

- #515 Job vyatskaya-tow02: textured master OKS 013, F8 fix, export-v005 — open, waiting for review / merge command.
- #514 Review: our export-v005 vs the user's hand-finished model, lessons — open.

## Agent trace

- Sessions: `dda7a500-3c9f-4186-98c9-299703e97a3a`
- Written by: -
- Subagents: general-purpose 1, independent-checker 1
- Skills: 3dsmax-mcp-dev 1, experience-transfer 1
- Commands: takeover 1
- Hook denials: 1: mcp__3dsmax-mcp__list_max_instances - Load the `3dsmax-mcp-dev` skill first (Skill tool), follow it, then repeat this 
- Retries: none
- Context at handover: 23 % (225k of 1000k tokens)
- Duration: 6 h 37 min (2026-10-21T12:02:46Z - 2026-10-21T18:40:17Z, UTC)
- Commits: `d64a2b3..fd399e7` (4 commits)
